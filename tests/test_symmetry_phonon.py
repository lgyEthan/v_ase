import asyncio
import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.build import bulk
from ase.io import read
from fastapi import HTTPException
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.io import atom_labels, set_atom_labels
from v_ase.phonon import (
    PhononModel,
    create_phonon_model,
    generate_finite_displacements,
    generate_mode_trajectory,
    load_phonon_model,
    phonon_band_structure,
    phonon_modes_at_q,
    phonopy_to_ase,
    qpoint_commensurability,
    validate_phonon_model_for_atoms,
)
from v_ase.symmetry import (
    analyze_symmetry,
    high_symmetry_path,
    symmetry_tolerance_scan,
    transform_by_symmetry,
)
from v_ase.server import (
    ai_schema_payload,
    apply_positions,
    phonon_bands,
    phonon_displacements,
    phonon_modes,
    symmetry_analysis,
    symmetry_transform,
)
from v_ase.session import EditorSession, sessions
from v_ase.viewer import find_free_port, view


pytest.importorskip("spglib")

ROOT = Path(__file__).resolve().parents[1]


def test_spacegroup_orbits_and_tolerance_scan_for_diamond_silicon():
    atoms = bulk("Si", "diamond", a=5.4304)
    result = analyze_symmetry(atoms)

    assert result["number"] == 227
    assert result["international"] == "Fd-3m"
    assert result["pointgroup"] == "m-3m"
    assert result["crystal_system"] == "cubic"
    assert result["operation_count"] == 48
    assert result["primitive_atom_count"] == 2
    assert len(result["orbits"]) == 1
    assert result["orbits"][0]["multiplicity"] == 2
    assert result["orbits"][0]["site_symmetry"] == "-43m"
    assert result["orbits"][0]["wyckoff"] in {"a", "b"}

    scan = symmetry_tolerance_scan(atoms, tolerances=[1e-6, 1e-5, 1e-4])
    assert [entry["number"] for entry in scan] == [227, 227, 227]


def test_custom_labels_can_be_ignored_or_treated_as_crystallographic_types():
    atoms = bulk("Si", "diamond", a=5.43)
    set_atom_labels(atoms, ["Si_A", "Si_B"])

    by_element = analyze_symmetry(atoms, type_basis="element")
    by_label = analyze_symmetry(atoms, type_basis="label")

    assert by_element["number"] == 227
    assert len(by_element["orbits"]) == 1
    assert by_element["warnings"]
    assert len(by_label["orbits"]) == 2
    assert by_label["number"] != by_element["number"]


def test_partial_pbc_is_reported_as_a_3d_spglib_approximation():
    atoms = bulk("C", "diamond", a=3.57)
    atoms.pbc = [True, True, False]
    result = analyze_symmetry(atoms)
    assert any("three-dimensional periodic symmetry" in item for item in result["warnings"])


def test_primitive_conventional_and_refined_cells_preserve_valid_identity():
    primitive = bulk("Si", "diamond", a=5.43)
    set_atom_labels(primitive, ["Si_A", "Si_B"])

    conventional, metadata = transform_by_symmetry(
        primitive,
        "conventional",
        type_basis="label",
    )
    assert len(conventional) == 8
    assert set(conventional.get_chemical_symbols()) == {"Si"}
    assert set(atom_labels(conventional)) == {"Si_A", "Si_B"}
    assert metadata["result_atom_count"] == 8

    recovered, _ = transform_by_symmetry(
        conventional,
        "primitive",
        type_basis="label",
    )
    assert len(recovered) == 2
    refined, _ = transform_by_symmetry(recovered, "refine", type_basis="label")
    assert len(refined) >= 2


def test_seekpath_returns_standard_primitive_reciprocal_path():
    pytest.importorskip("seekpath")
    atoms = bulk("Al", "fcc", a=4.05)
    path = high_symmetry_path(atoms)
    assert path["spacegroup_number"] == 225
    assert path["path"]
    assert "GAMMA" in path["point_coords"]
    assert np.asarray(path["reciprocal_primitive_lattice"]).shape == (3, 3)
    assert path["path"] == [
        ["GAMMA", "X"],
        ["X", "U"],
        ["K", "GAMMA"],
        ["GAMMA", "L"],
        ["L", "W"],
        ["W", "X"],
    ]


def test_phonon_band_structure_maps_hpkot_path_into_phonopy_basis():
    pytest.importorskip("phonopy")
    model = load_phonon_model(
        ROOT / "examples" / "symmetry_branch" / "al_emt_phonopy_params.yaml"
    )
    result = phonon_band_structure(model, reference_distance=0.15)

    assert result["spacegroup_international"] == "Fm-3m"
    assert result["spacegroup_number"] == 225
    assert result["bravais_lattice"] == "cF"
    assert result["band_count"] == 3
    assert [(segment["start_label"], segment["end_label"]) for segment in result["segments"]] == [
        ("GAMMA", "X"),
        ("X", "U"),
        ("K", "GAMMA"),
        ("GAMMA", "L"),
        ("L", "W"),
        ("W", "X"),
    ]
    x_point = result["segments"][0]
    qpoint = x_point["qpoints"][-1]
    assert qpoint == pytest.approx([0.5, 0.0, 0.5], abs=1e-12)
    assert x_point["suggested_dimensions"][-1] == [2, 1, 2]
    assert qpoint_commensurability(
        qpoint,
        x_point["suggested_dimensions"][-1],
    )["commensurate"] is True
    direct = phonon_modes_at_q(model, qpoint)
    assert x_point["frequencies"][-1] == pytest.approx(
        [mode["frequency_thz"] for mode in direct["bands"]],
        abs=1e-10,
    )
    assert x_point["nac_directions"][0] is not None
    assert any(tick["label"] == "U|K" for tick in result["ticks"])


def test_phonon_band_structure_requires_force_constants():
    model = create_phonon_model(bulk("Al", "fcc", a=4.05), supercell_matrix=(1, 1, 1))
    with pytest.raises(ValueError, match="force constants"):
        phonon_band_structure(model)


def _synthetic_phonopy_model() -> PhononModel:
    pytest.importorskip("phonopy")
    atoms = Atoms(
        "Si2",
        scaled_positions=[[0, 0, 0], [0.25, 0.25, 0.25]],
        cell=[[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]],
        pbc=True,
    )
    atoms.set_masses([28.0, 30.0])
    set_atom_labels(atoms, ["Si_framework", "Si_guest"])
    model = create_phonon_model(atoms, supercell_matrix=(1, 1, 1))
    force_constants = np.zeros((2, 2, 3, 3), dtype=float)
    force_constants[0, 0] = np.eye(3) * 10.0
    force_constants[1, 1] = np.eye(3) * 20.0
    model.phonon.force_constants = force_constants
    return model


def _monatomic_chain_model() -> PhononModel:
    """Nearest-neighbour chain used to validate the analytical dispersion."""
    pytest.importorskip("phonopy")
    atoms = Atoms(
        "Si",
        positions=[[0, 0, 0]],
        cell=np.diag([1.0, 5.0, 5.0]),
        pbc=True,
    )
    model = create_phonon_model(
        atoms,
        supercell_matrix=(2, 1, 1),
        primitive_matrix=np.eye(3),
    )
    spring = 10.0
    force_constants = np.zeros((2, 2, 3, 3), dtype=float)
    force_constants[0, 0, 0, 0] = 2 * spring
    force_constants[0, 1, 0, 0] = -2 * spring
    force_constants[1, 0, 0, 0] = -2 * spring
    force_constants[1, 1, 0, 0] = 2 * spring
    model.phonon.force_constants = force_constants
    return model


def test_finite_displacements_are_generated_before_force_constants_exist():
    pytest.importorskip("phonopy")
    atoms = bulk("NaCl", "rocksalt", a=5.64)
    set_atom_labels(atoms, ["Na_site", "Cl_site"])
    model, frames, metadata = generate_finite_displacements(
        atoms,
        supercell_matrix=(2, 2, 2),
        distance=0.01,
    )

    assert not model.has_force_constants
    assert frames
    assert metadata["forces_required"] is True
    assert all(len(frame) == 16 for frame in frames)
    assert {"Na_site", "Cl_site"} <= set(atom_labels(frames[0]))
    assert frames[0].info["v_ase_phonon_displacement"]["distance_angstrom"] == 0.01


def test_mode_generation_requires_force_constants_and_commensurate_qpoint():
    pytest.importorskip("phonopy")
    atoms = bulk("Al", "fcc", a=4.05)
    empty = create_phonon_model(atoms, supercell_matrix=(1, 1, 1))
    with pytest.raises(ValueError, match="require force constants"):
        phonon_modes_at_q(empty, [0, 0, 0])

    check = qpoint_commensurability([0.5, 0, 0], [2, 1, 1])
    assert check["commensurate"] is True
    assert qpoint_commensurability([1 / 3, 0, 0], [2, 1, 1])["commensurate"] is False

    non_diagonal = [[2, 1, 0], [0, 1, 0], [0, 0, 1]]
    assert qpoint_commensurability([0.5, 0.5, 0], non_diagonal)["commensurate"] is True
    assert qpoint_commensurability([0.5, 0, 0], non_diagonal)["commensurate"] is False
    with pytest.raises(ValueError, match="finite integers"):
        qpoint_commensurability([0, 0, 0], [1.5, 1, 1])


def test_frozen_mode_trajectory_uses_frequency_band_phase_and_amplitude():
    model = _synthetic_phonopy_model()
    modes = phonon_modes_at_q(model, [0, 0, 0], projection_direction=[1, 0, 0])
    assert modes["band_count"] == 6
    assert all(item["frequency_thz"] > 0 for item in modes["bands"])
    assert modes["projection_direction"] == [1.0, 0.0, 0.0]
    assert all(0 <= item["directional_fraction"] <= 1 for item in modes["bands"])

    trajectory, metadata = generate_mode_trajectory(
        model,
        qpoint=[0, 0, 0],
        band=1,
        amplitude=0.1,
        dimension=(1, 1, 1),
        frames=8,
    )
    assert len(trajectory) == 8
    assert metadata["frame_count"] == 8
    assert metadata["frequency_thz"] == pytest.approx(modes["bands"][0]["frequency_thz"])
    displacement = trajectory[0].positions - trajectory[4].positions
    expected_peak_to_peak = 2 * 0.1 / np.sqrt(2 * 28.0)
    assert np.linalg.norm(displacement) == pytest.approx(expected_peak_to_peak)
    assert trajectory[0].info["v_ase_phonon_mode"]["band"] == 1
    assert atom_labels(trajectory[0]) == ["Si_framework", "Si_guest"]
    assert trajectory[0].get_masses() == pytest.approx([28.0, 30.0])
    assert metadata["coordinates_unwrapped"] is True

    # Preserve the nearest periodic image around the reference atom so a
    # boundary atom oscillates continuously instead of jumping by one cell.
    boundary_motion = np.asarray([frame.positions[0] for frame in trajectory])
    assert np.max(np.linalg.norm(boundary_motion, axis=1)) < 0.1
    closed_cycle = np.vstack([boundary_motion, boundary_motion[0]])
    assert np.max(np.linalg.norm(np.diff(closed_cycle, axis=0), axis=1)) < 0.1

    with pytest.raises(ValueError, match="not commensurate"):
        generate_mode_trajectory(
            model,
            qpoint=[1 / 3, 0, 0],
            band=1,
            amplitude=0.1,
            dimension=(2, 1, 1),
        )


def test_monatomic_chain_matches_the_analytical_nearest_neighbour_dispersion():
    model = _monatomic_chain_model()
    gamma = phonon_modes_at_q(model, [0, 0, 0])
    quarter = phonon_modes_at_q(model, [0.25, 0, 0])
    boundary = phonon_modes_at_q(model, [0.5, 0, 0])

    assert [band["frequency_thz"] for band in gamma["bands"]] == pytest.approx(
        [0.0, 0.0, 0.0],
        abs=1e-10,
    )
    quarter_longitudinal = max(
        quarter["bands"],
        key=lambda item: item["frequency_thz"],
    )
    boundary_longitudinal = max(
        boundary["bands"],
        key=lambda item: item["frequency_thz"],
    )
    assert quarter_longitudinal["dominant_axis"] == "x"
    assert quarter_longitudinal["longitudinal_fraction"] == pytest.approx(1.0)
    assert (
        quarter_longitudinal["frequency_thz"]
        / boundary_longitudinal["frequency_thz"]
    ) == pytest.approx(np.sin(np.pi / 4), rel=1e-10)

    active = phonopy_to_ase(model.phonon.unitcell)
    quarter_turn = np.asarray([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    active.set_cell(np.asarray(active.cell) @ quarter_turn, scale_atoms=True)
    validate_phonon_model_for_atoms(model, active)
    rotated_quarter = max(
        phonon_modes_at_q(model, [0.25, 0, 0])["bands"],
        key=lambda item: item["frequency_thz"],
    )
    assert rotated_quarter["dominant_axis"] == "y"
    assert rotated_quarter["longitudinal_fraction"] == pytest.approx(1.0)


def test_phonopy_project_compatibility_checks_cell_species_order_and_positions():
    model = _synthetic_phonopy_model()
    matching = phonopy_to_ase(model.phonon.unitcell)
    validate_phonon_model_for_atoms(model, matching)

    wrong_cell = matching.copy()
    wrong_cell.cell[0, 0] += 0.02
    with pytest.raises(ValueError, match="lattice metric does not match"):
        validate_phonon_model_for_atoms(model, wrong_cell)

    wrong_species = matching.copy()
    wrong_species[0].symbol = "Ge"
    with pytest.raises(ValueError, match="chemical elements"):
        validate_phonon_model_for_atoms(model, wrong_species)

    wrong_position = matching.copy()
    wrong_position.positions[1, 0] += 0.02
    with pytest.raises(ValueError, match="fractional positions"):
        validate_phonon_model_for_atoms(model, wrong_position)


def test_phonopy_project_can_align_a_rigid_cartesian_cell_rotation():
    model = _synthetic_phonopy_model()
    matching = phonopy_to_ase(model.phonon.unitcell)
    angle = np.deg2rad(37.0)
    rotation = np.asarray(
        [
            [np.cos(angle), -np.sin(angle), 0.0],
            [np.sin(angle), np.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    rotated = matching.copy()
    rotated.set_cell(np.asarray(matching.cell) @ rotation, scale_atoms=True)

    validate_phonon_model_for_atoms(model, rotated)
    assert model.cartesian_transform == pytest.approx(rotation)
    assert model.summary()["aligned_to_active_structure"] is True

    trajectory, _ = generate_mode_trajectory(
        model,
        qpoint=[0, 0, 0],
        band=1,
        amplitude=0.1,
        frames=1,
        oscillation=False,
    )
    assert np.asarray(trajectory[0].cell) == pytest.approx(np.asarray(rotated.cell))


def test_saved_phonopy_project_reloads_with_force_constants(tmp_path: Path):
    model = _synthetic_phonopy_model()
    project = tmp_path / "phonopy_params.yaml"
    model.phonon.save(project, settings={"force_constants": True})

    loaded = load_phonon_model(project)
    assert loaded.has_force_constants
    summary = loaded.summary()
    assert summary["unit_atoms"] == 2
    assert summary["frequency_unit"] == "THz"


def _editor_session(name: str, atoms: Atoms, *, viz_only: bool = False) -> EditorSession:
    session = EditorSession(
        name,
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": viz_only},
    )
    sessions[name] = session
    return session


def test_server_symmetry_analysis_is_available_in_view_mode_without_mutation():
    atoms = bulk("Si", "diamond", a=5.43)
    session = _editor_session("symmetry-view-analysis", atoms, viz_only=True)
    before = session.working_atoms.positions.copy()
    try:
        result = asyncio.run(symmetry_analysis(session.session_id, {
            "symprec": 1e-5,
            "type_basis": "element",
            "tolerances": [1e-6, 1e-5],
        }))
    finally:
        sessions.pop(session.session_id, None)

    assert result["number"] == 227
    assert len(result["tolerance_scan"]) == 2
    assert np.allclose(session.working_atoms.positions, before)
    assert session.history == []


def test_server_phonon_band_plot_is_read_only_and_available_in_view_mode():
    model = load_phonon_model(
        ROOT / "examples" / "symmetry_branch" / "al_emt_phonopy_params.yaml"
    )
    atoms = phonopy_to_ase(model.phonon.unitcell)
    session = _editor_session("phonon-band-view", atoms, viz_only=True)
    session.phonon_model = model
    before = session.working_atoms.positions.copy()
    try:
        result = asyncio.run(phonon_bands(session.session_id, {
            "reference_distance": 0.15,
            "symprec": 1e-5,
        }))
    finally:
        sessions.pop(session.session_id, None)

    assert result["status"] == "ok"
    assert result["band_count"] == 3
    assert result["segments"][0]["end_label"] == "X"
    assert np.allclose(session.working_atoms.positions, before)
    assert session.history == []


def test_phonon_band_operation_is_discoverable_to_agents_and_the_gui():
    discovery = ai_schema_payload()
    assert discovery["operation_parameters"]["phonon-band-structure"]["mode"] == "view-or-edit"
    assert discovery["scientific_endpoints"]["phonon_band_structure"].endswith(
        "/api/analysis/phonon/band-structure/{session_id}"
    )
    index = (ROOT / "v_ase" / "static" / "index.html").read_text(encoding="utf-8")
    main = (ROOT / "v_ase" / "static" / "main.js").read_text(encoding="utf-8")
    assert 'id="phonon-band-plot"' in index
    assert 'id="btn-phonon-bands"' in index
    assert "'phonon-band-structure'" in main


def test_browser_selects_a_band_point_and_animates_the_physical_mode():
    pytest.importorskip("phonopy")
    project = ROOT / "examples" / "symmetry_branch" / "al_emt_phonopy_params.yaml"
    model = load_phonon_model(project)
    atoms = phonopy_to_ase(model.phonon.unitcell)
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        allow_relax=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__V_ASE_APP__?.state?.atoms")
            page.evaluate(
                """() => {
                    const app = window.__V_ASE_APP__;
                    app.setInspectorCollapsed(false, false);
                    app.setInspectorGroup('analysis', false);
                    const panel = document.querySelector('[data-panel="phonons"]');
                    if (panel) panel.open = true;
                }"""
            )
            page.set_input_files("#phonopy-project-file", str(project))
            page.wait_for_function(
                "window.__V_ASE_APP__.state.phononBandStructure?.convention === 'HPKOT'"
            )
            page.wait_for_function(
                "document.querySelectorAll('.phonon-band-branch').length === 18"
            )

            labels = page.locator("#phonon-band-plot .phonon-band-label").all_text_contents()
            assert labels == ["Γ", "X", "U|K", "Γ", "L", "W", "X"]
            page.locator("#phonon-band-plot").scroll_into_view_if_needed()

            def plot_point(label: str, band: int) -> dict[str, float]:
                return page.evaluate(
                    """({ label, band }) => {
                    const app = window.__V_ASE_APP__;
                    const result = app.state.phononBandStructure;
                    const segment = result.segments.find(item => item.end_label === label);
                    const pointIndex = segment.qpoints.length - 1;
                    const plot = document.getElementById('phonon-band-plot');
                    const rect = plot.getBoundingClientRect();
                    const geometry = plot.__vAseBandGeometry;
                    const x = geometry.x(Number(segment.distances[pointIndex]));
                    const y = geometry.y(Number(segment.frequencies[pointIndex][band - 1]));
                    return {
                        x: rect.left + x * rect.width / geometry.width,
                        y: rect.top + y * rect.height / geometry.height
                    };
                }""",
                    {"label": label, "band": band},
                )

            l_point = plot_point("L", 3)
            page.mouse.move(l_point["x"], l_point["y"])
            page.wait_for_function(
                "document.querySelector('.phonon-band-hover-point').getAttribute('visibility') === 'visible'"
            )
            page.mouse.click(l_point["x"], l_point["y"])
            page.wait_for_function(
                "window.__V_ASE_APP__.state.phononBandSelection !== null"
            )
            l_selection = page.evaluate(
                "window.__V_ASE_APP__.state.phononBandSelection"
            )
            assert l_selection["pathLabel"] == "L"
            assert l_selection["band"] == 3
            assert l_selection["qpoint"] == pytest.approx([0.5, 0.5, 0.5])
            l_selected_x = float(
                page.locator(".phonon-band-selected-point").get_attribute("cx")
            )
            assert "Selected L · ν3" in page.locator("#phonon-band-selection").inner_text()

            click_point = plot_point("X", 3)
            page.mouse.move(click_point["x"], click_point["y"])
            assert page.locator(".phonon-band-selected-point").get_attribute("visibility") == "visible"
            page.mouse.click(click_point["x"], click_point["y"])
            page.wait_for_function(
                """() => {
                    const q = ['phonon-q-x', 'phonon-q-y', 'phonon-q-z']
                        .map(id => Number(document.getElementById(id).value));
                    return Math.abs(q[0] - 0.5) < 1e-10
                        && Math.abs(q[1]) < 1e-10
                        && Math.abs(q[2] - 0.5) < 1e-10
                        && window.__V_ASE_APP__.state.phononModes?.band_count === 3;
                }"""
            )
            assert float(
                page.locator(".phonon-band-selected-point").get_attribute("cx")
            ) != pytest.approx(l_selected_x)
            assert "Selected X · ν3" in page.locator("#phonon-band-selection").inner_text()
            page.locator(".phonon-mode-row").nth(2).click()
            page.wait_for_function(
                "window.__V_ASE_APP__.state.phononBandSelection?.band === 3"
            )
            assert [
                page.input_value(f"#phonon-mode-super-{axis}")
                for axis in "xyz"
            ] == ["2", "1", "2"]

            page.fill("#phonon-mode-amplitude", "2")
            page.fill("#phonon-mode-frames", "24")
            for axis, value in zip("xyz", (4, 4, 2), strict=True):
                page.fill(f"#phonon-mode-super-{axis}", str(value))
            page.click("#btn-phonon-modulate")
            page.click("#modal-confirm-action")
            page.wait_for_function("window.__V_ASE_APP__.loadedFrameCount() === 24")
            page.wait_for_function(
                """() => document.querySelectorAll('.phonon-band-branch').length === 18
                    && window.__V_ASE_APP__.state.phononBandSelection?.band === 3"""
            )
            page.evaluate(
                """() => {
                    const app = window.__V_ASE_APP__;
                    const label = app.state.atoms.symbols[0];
                    const key = app.labelPairKey(label, label);
                    Object.assign(app.state.display, {
                        showBonds: true,
                        showPeriodicBonds: false,
                        bondMode: 'pairwise',
                        pairwiseBondRanges: {
                            [key]: { enabled: true, min: 0, max: 3.05 }
                        },
                        pairwiseBondCutoffs: { [key]: 3.05 },
                        bondThickness: 0.11,
                        bondColorMode: 'custom',
                        bondCustomColor: '#746d69'
                    });
                    app.renderer.setDisplayOptions(app.state.display);
                    app.renderer.renderNow();
                }"""
            )
            page.wait_for_function(
                "Number(window.__V_ASE_APP__.renderer.domElement.dataset.bondCount || 0) > 0"
            )
            first = np.asarray(page.evaluate("window.__V_ASE_APP__.state.atoms.positions"))
            page.evaluate("window.__V_ASE_APP__.loadFrame(12)")
            page.wait_for_function(
                "window.__V_ASE_APP__.state.atoms.metadata.current_frame === 12"
            )
            opposite = np.asarray(page.evaluate("window.__V_ASE_APP__.state.atoms.positions"))
            assert not np.allclose(first, opposite)
            assert page.locator("#phonon-band-result").is_visible()
            assert page.locator("#phonon-band-status .analysis-status-title").inner_text() == (
                "cF phonon dispersion"
            )
            browser.close()
    finally:
        editor.close()


def test_server_symmetry_transform_replaces_trajectory_and_can_undo():
    atoms = bulk("Si", "diamond", a=5.43)
    session = _editor_session("symmetry-transform-edit", atoms)
    original_count = len(session.working_atoms)
    try:
        result = asyncio.run(symmetry_transform(session.session_id, {
            "mode": "conventional",
            "symprec": 1e-5,
            "type_basis": "element",
        }))
        assert result["metadata"]["natoms"] == 8
        assert session.frame_count == 1
        assert len(session.working_atoms) == 8
        restored = session.undo()
    finally:
        sessions.pop(session.session_id, None)

    assert restored is not None
    assert len(restored) == original_count


def test_server_finite_displacements_become_calculation_input_trajectory():
    pytest.importorskip("phonopy")
    atoms = bulk("NaCl", "rocksalt", a=5.64)
    session = _editor_session("phonon-displacement-edit", atoms)
    try:
        result = asyncio.run(phonon_displacements(session.session_id, {
            "supercell_matrix": [2, 2, 2],
            "distance": 0.01,
        }))
        assert result["phonon"]["forces_required"] is True
        assert session.frame_count == result["phonon"]["displacement_count"]
        assert session.phonon_model is not None
        assert session.phonon_model.has_force_constants is False
        generated_model = session.phonon_model
        with pytest.raises(HTTPException, match="require force constants") as error:
            asyncio.run(phonon_modes(session.session_id, {"qpoint": [0, 0, 0]}))
        assert error.value.status_code == 400
        session.undo()
        assert session.phonon_model is None
        session.redo()
        assert session.phonon_model is generated_model
        session.undo()
    finally:
        sessions.pop(session.session_id, None)

    assert session.frame_count == 1
    assert len(session.working_atoms) == len(atoms)


def test_physical_edit_invalidates_loaded_phonon_model_and_undo_restores_it():
    model = _synthetic_phonopy_model()
    atoms = phonopy_to_ase(model.phonon.unitcell)
    session = _editor_session("phonon-model-edit-invalidation", atoms)
    session.phonon_model = model
    moved = atoms.positions.copy()
    moved[0, 0] += 0.02
    try:
        asyncio.run(apply_positions(session.session_id, {"positions": moved.tolist()}))
        assert session.phonon_model is None
        session.undo()
        assert session.phonon_model is model
    finally:
        sessions.pop(session.session_id, None)


def test_scientific_endpoints_report_invalid_user_input_without_mutation():
    atoms = bulk("Si", "diamond", a=5.43)
    session = _editor_session("scientific-invalid-input", atoms)
    before = session.working_atoms.copy()
    try:
        with pytest.raises(HTTPException) as symmetry_error:
            asyncio.run(symmetry_analysis(session.session_id, {"symprec": 0}))
        with pytest.raises(HTTPException) as phonon_error:
            asyncio.run(phonon_displacements(session.session_id, {
                "supercell_matrix": [0, 2, 2],
                "distance": 0.01,
            }))
    finally:
        sessions.pop(session.session_id, None)

    assert symmetry_error.value.status_code == 400
    assert phonon_error.value.status_code == 400
    assert len(session.history) == 0
    assert session.frame_count == 1
    assert np.allclose(session.working_atoms.positions, before.positions)


def test_reproducible_symmetry_readme_structures_match_the_manifest():
    pytest.importorskip("phonopy")
    example_dir = ROOT / "examples" / "symmetry_branch"
    manifest = json.loads((example_dir / "manifest.json").read_text(encoding="utf-8"))

    primitive_si = read(example_dir / "si_diamond_primitive.cif")
    conventional_si = read(example_dir / "si_diamond_conventional.cif")
    assert len(primitive_si) == manifest["silicon"]["primitive_atoms"] == 2
    assert len(conventional_si) == manifest["silicon"]["conventional_atoms"] == 8
    primitive_analysis = analyze_symmetry(primitive_si)
    assert primitive_analysis["international"] == "Fd-3m"
    assert primitive_analysis["number"] == 227
    assert primitive_analysis["operation_count"] == 48
    assert manifest["silicon"]["space_group"]["operation_count"] == 192

    displacement_frames = read(
        example_dir / "nacl_2x2x2_finite_displacements.extxyz",
        index=":",
    )
    assert len(displacement_frames) == manifest["finite_displacements"]["displacement_count"] == 2
    assert {len(frame) for frame in displacement_frames} == {16}
    assert manifest["finite_displacements"]["forces_required"] is True
    assert manifest["finite_displacements"]["distance_angstrom"] == pytest.approx(0.01)

    mode_frames = read(example_dir / "al_x_mode_trajectory.extxyz", index=":")
    assert len(mode_frames) == manifest["phonon_mode"]["frame_count"] == 24
    assert {len(frame) for frame in mode_frames} == {32}
    assert not np.allclose(mode_frames[0].positions, mode_frames[12].positions)
    assert manifest["phonon_mode"]["coordinates_unwrapped"] is True
    assert manifest["phonon_mode"]["commensurability"]["commensurate"] is True

    model = load_phonon_model(example_dir / "al_emt_phonopy_params.yaml")
    assert model.has_force_constants
    qpoint = manifest["phonon_mode"]["band_structure"]["selected_qpoint"]
    assert qpoint == pytest.approx([0.5, 0.0, 0.5], abs=1e-12)
    modes = phonon_modes_at_q(model, qpoint, projection_direction=[0, 1, 0])
    documented = manifest["phonon_mode"]["selected_mode"]
    actual = next(mode for mode in modes["bands"] if mode["band"] == documented["band"])
    assert actual["frequency_thz"] == pytest.approx(documented["frequency_thz"], rel=2e-8)
    assert actual["frequency_thz"] == pytest.approx(7.9913903014, rel=1e-8)
    assert not (example_dir / "al_x_mode_peak.cif").exists()


def test_symmetry_readme_uses_actual_synchronized_application_captures():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "capture_symmetry_readme_assets.py").read_text(
        encoding="utf-8"
    )
    css = (ROOT / "v_ase" / "static" / "style.css").read_text(encoding="utf-8")
    source_manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    required_media = (
        "readme_symmetry_analysis.png",
        "readme_symmetry_standard_cell.png",
        "readme_phonon_displacements.png",
        "readme_phonon_mode.png",
        "readme_phonon_mode.gif",
    )
    for filename in required_media:
        canonical = ROOT / "docs" / "assets" / filename
        github = ROOT / "docs" / "assets" / "github" / filename
        assert canonical.read_bytes() == github.read_bytes()
        with Image.open(canonical) as image:
            assert image.size == (1920, 1080)
            pixels = np.asarray(image.convert("RGB"), dtype=float)
            assert pixels.std() > 20
            if filename.endswith(".gif"):
                # Pillow coalesces repeated hold frames. The output still
                # contains the L hover/select, X hover/select, and all 24
                # distinct physical-mode frames.
                assert getattr(image, "n_frames", 1) >= 29
        if filename != "readme_phonon_mode.png":
            assert filename in readme

    for filename in (
        "si_diamond_primitive.cif",
        "si_diamond_conventional.cif",
        "nacl_2x2x2_displacement_001.cif",
        "nacl_2x2x2_finite_displacements.extxyz",
        "al_emt_phonopy_params.yaml",
        "al_x_mode_trajectory.extxyz",
        "manifest.json",
    ):
        assert filename in readme

    assert "ASE EMT" in script
    assert "generate_finite_displacements" in script
    assert "generate_mode_trajectory" in script
    assert 'band_point("L", int(metadata["band"]))' in script
    assert 'band_point("X", int(metadata["band"]))' in script
    assert '"max": 3.05' in script
    assert 'background: transparent;' in css
    for extension in ("*.cif", "*.extxyz", "*.yaml", "*.json"):
        assert extension in source_manifest
    assert "The figures below are screenshots from this branch, not mockups." in readme
