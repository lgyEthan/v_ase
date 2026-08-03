"""Generate and capture the reproducible symmetry-branch README examples."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

import numpy as np
from ase.build import bulk
from ase.calculators.emt import EMT
from ase.io import write
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capture_readme_screenshots import (  # noqa: E402
    append_hold,
    collapse_inspector,
    configure_inspector,
    open_scene,
    save_gif,
    screenshot_frame,
    set_atomic_scale,
    set_camera,
    set_display,
    set_readme_lighting,
    settle_view,
)
from v_ase.io import set_atom_labels  # noqa: E402
from v_ase.phonon import (  # noqa: E402
    create_phonon_model,
    generate_finite_displacements,
    generate_mode_trajectory,
    phonon_band_structure,
    phonon_modes_at_q,
    phonopy_to_ase,
)
from v_ase.symmetry import analyze_symmetry, transform_by_symmetry  # noqa: E402

EXAMPLE_DIR = ROOT / "examples" / "symmetry_branch"
ASSET_DIR = ROOT / "docs" / "assets"
GITHUB_ASSET_DIR = ASSET_DIR / "github"


def _write_cif(path: Path, atoms) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, atoms, format="cif")


def generate_examples() -> dict[str, object]:
    """Build every documented structure from public ASE/Phonopy APIs."""
    EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    silicon_primitive = bulk("Si", "diamond", a=5.4304)
    silicon_conventional, transform_metadata = transform_by_symmetry(
        silicon_primitive,
        "conventional",
        type_basis="element",
    )
    _write_cif(EXAMPLE_DIR / "si_diamond_primitive.cif", silicon_primitive)
    _write_cif(EXAMPLE_DIR / "si_diamond_conventional.cif", silicon_conventional)

    nacl = bulk("NaCl", "rocksalt", a=5.64)
    set_atom_labels(nacl, ["Na_site", "Cl_site"])
    _write_cif(EXAMPLE_DIR / "nacl_primitive.cif", nacl)
    _, finite_displacements, displacement_metadata = generate_finite_displacements(
        nacl,
        supercell_matrix=(2, 2, 2),
        distance=0.01,
    )
    _write_cif(
        EXAMPLE_DIR / "nacl_2x2x2_displacement_001.cif",
        finite_displacements[0],
    )
    write(
        EXAMPLE_DIR / "nacl_2x2x2_finite_displacements.extxyz",
        finite_displacements,
        format="extxyz",
    )

    aluminum = bulk("Al", "fcc", a=4.05)
    set_atom_labels(aluminum, ["Al_fcc"])
    _write_cif(EXAMPLE_DIR / "al_fcc_primitive.cif", aluminum)
    phonon_model = create_phonon_model(
        aluminum,
        supercell_matrix=(2, 2, 2),
    )
    phonon_model.phonon.generate_displacements(distance=0.01)
    forces = []
    for displaced_supercell in phonon_model.phonon.supercells_with_displacements:
        displaced_atoms = phonopy_to_ase(displaced_supercell)
        displaced_atoms.calc = EMT()
        forces.append(displaced_atoms.get_forces())
    phonon_model.phonon.forces = forces
    phonon_model.phonon.produce_force_constants()
    phonopy_project = EXAMPLE_DIR / "al_emt_phonopy_params.yaml"
    phonon_model.phonon.save(
        phonopy_project,
        settings={"force_constants": True},
    )

    band_structure = phonon_band_structure(
        phonon_model,
        reference_distance=0.08,
    )
    x_segment = next(
        segment
        for segment in band_structure["segments"]
        if segment["end_label"] == "X"
    )
    qpoint = x_segment["qpoints"][-1]
    modes = phonon_modes_at_q(
        phonon_model,
        qpoint,
        projection_direction=[0.0, 1.0, 0.0],
    )
    selected_mode = max(modes["bands"], key=lambda item: item["frequency_thz"])
    mode_trajectory, mode_metadata = generate_mode_trajectory(
        phonon_model,
        qpoint=qpoint,
        band=selected_mode["band"],
        amplitude=2.0,
        dimension=(4, 4, 2),
        frames=24,
        oscillation=True,
    )
    write(
        EXAMPLE_DIR / "al_x_mode_trajectory.extxyz",
        mode_trajectory,
        format="extxyz",
    )

    silicon_analysis = analyze_symmetry(silicon_conventional)
    manifest = {
        "schema": "v_ase.symmetry-readme-examples.v1",
        "silicon": {
            "space_group": {
                "international": silicon_analysis["international"],
                "number": silicon_analysis["number"],
                "pointgroup": silicon_analysis["pointgroup"],
                "crystal_system": silicon_analysis["crystal_system"],
                "operation_count": silicon_analysis["operation_count"],
                "orbits": silicon_analysis["orbits"],
            },
            "primitive_atoms": len(silicon_primitive),
            "conventional_atoms": len(silicon_conventional),
            "transform": transform_metadata,
        },
        "finite_displacements": displacement_metadata,
        "phonon_mode": {
            **mode_metadata,
            "force_calculator": "ASE EMT",
            "force_constant_supercell": [2, 2, 2],
            "finite_displacement_angstrom": 0.01,
            "selected_mode": selected_mode,
            "band_structure": {
                "convention": band_structure["convention"],
                "path_source": band_structure["path_source"],
                "spacegroup_number": band_structure["spacegroup_number"],
                "bravais_lattice": band_structure["bravais_lattice"],
                "qpoint_count": band_structure["qpoint_count"],
                "band_count": band_structure["band_count"],
                "ticks": band_structure["ticks"],
                "selected_label": "X",
                "selected_qpoint": qpoint,
            },
        },
    }
    (EXAMPLE_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "silicon_primitive": silicon_primitive,
        "silicon_conventional": silicon_conventional,
        "nacl": nacl,
        "finite_displacements": finite_displacements,
        "aluminum": aluminum,
        "phonopy_project": phonopy_project,
        "mode_trajectory": mode_trajectory,
        "mode_metadata": mode_metadata,
        "band_structure": band_structure,
    }


def _focus_panel(page, panel_name: str) -> None:
    page.evaluate(
        """(panelName) => {
            const content = document.getElementById('inspector-content');
            const panel = document.querySelector(`[data-panel="${panelName}"]`);
            if (!content || !panel) return;
            const contentTop = content.getBoundingClientRect().top;
            content.scrollTop = Math.max(
                0,
                content.scrollTop + panel.getBoundingClientRect().top - contentTop - 8
            );
        }""",
        panel_name,
    )
    page.wait_for_timeout(120)


def _focus_element(page, selector: str) -> None:
    page.evaluate(
        """(selector) => {
            const content = document.getElementById('inspector-content');
            const element = document.querySelector(selector);
            if (!content || !element) return;
            const contentTop = content.getBoundingClientRect().top;
            content.scrollTop = Math.max(
                0,
                content.scrollTop + element.getBoundingClientRect().top - contentTop - 72
            );
        }""",
        selector,
    )
    page.wait_for_timeout(120)


def _science_display(page, *, bonds: bool) -> None:
    set_display(
        page,
        {
            "projectionMode": "orthographic",
            "viewportBackground": "white",
            "showGrid": False,
            "showAxes": False,
            "showCell": True,
            "showBonds": bonds,
            "atomRadiusScale": 0.62,
            "antialias": True,
            "sphereQuality": "ultra",
        },
    )


def capture_symmetry_analysis(browser, atoms) -> None:
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        _science_display(page, bonds=True)
        configure_inspector(page, "analysis", ["symmetry"], width=520)
        center = np.mean(atoms.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([8.2, -10.5, 7.4])).tolist(),
            fov=36,
        )
        set_atomic_scale(page, 110.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.75,
            position_offset=(-9.0, -12.0, 15.0),
        )
        page.click("#btn-analyze-symmetry")
        page.wait_for_function(
            "window.__V_ASE_APP__.state.symmetryResult?.number === 227"
        )
        page.click("#btn-symmetry-path")
        page.wait_for_function(
            "Array.isArray(window.__V_ASE_APP__.state.symmetryPath?.path)"
        )
        _focus_panel(page, "symmetry")
        screenshot_frame(page).save(
            ASSET_DIR / "readme_symmetry_analysis.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_standard_cell(browser, primitive) -> None:
    editor, page = open_scene(browser, primitive, show_bonds=True)
    try:
        _science_display(page, bonds=True)
        configure_inspector(page, "analysis", ["symmetry"], width=520)
        page.evaluate(
            """async () => {
                const app = window.__V_ASE_APP__;
                const result = await app.api.transformBySymmetry({
                    mode: 'conventional',
                    symprec: 1e-5,
                    angle_tolerance: -1,
                    type_basis: 'element',
                    magnetic: false,
                    idealize: true,
                    positions: app.backendPositionsPayload()
                });
                app.setAtomsData(result, { clearSelection: true });
                await app.analyzeCurrentSymmetry();
                app.toast('Conventional cell created: 2 -> 8 atoms.', 'success');
            }"""
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.metadata.natoms === 8"
        )
        positions = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        center = np.mean(positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([8.5, -11.0, 7.8])).tolist(),
            fov=36,
        )
        set_atomic_scale(page, 83.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.75,
            position_offset=(-9.0, -12.0, 15.0),
        )
        _focus_panel(page, "symmetry")
        screenshot_frame(page).save(
            ASSET_DIR / "readme_symmetry_standard_cell.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_finite_displacements(browser, atoms) -> None:
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        _science_display(page, bonds=True)
        configure_inspector(page, "analysis", ["phonons"], width=520)
        page.evaluate(
            """async () => {
                const app = window.__V_ASE_APP__;
                const result = await app.api.generatePhononDisplacements({
                    supercell_matrix: [2, 2, 2],
                    distance: 0.01,
                    symprec: 1e-5,
                    positions: app.backendPositionsPayload()
                });
                app.state.phononModelSummary = result.phonon;
                app.state.phononModes = null;
                app.setAtomsData(result, { clearSelection: true });
                app.renderPhononModelSummary(result.phonon);
            }"""
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.loadedFrameCount() > 1"
        )
        positions = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        center = np.mean(positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([10.0, -13.0, 9.0])).tolist(),
            fov=37,
        )
        set_atomic_scale(page, 65.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.8,
            position_offset=(-10.0, -13.0, 17.0),
        )
        _focus_panel(page, "phonons")
        screenshot_frame(page).save(
            ASSET_DIR / "readme_phonon_displacements.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_physical_mode(browser, examples: dict[str, object]) -> None:
    aluminum = examples["aluminum"]
    metadata = examples["mode_metadata"]
    editor, page = open_scene(browser, aluminum, show_bonds=True)
    try:
        _science_display(page, bonds=True)
        configure_inspector(page, "analysis", ["phonons"], width=520)
        al_label = page.evaluate("window.__V_ASE_APP__.state.atoms.symbols[0]")
        al_pair = f"{al_label}-{al_label}"
        set_display(
            page,
            {
                "showBonds": True,
                "showPeriodicBonds": True,
                "bondMode": "pairwise",
                "pairwiseBondRanges": {
                    al_pair: {"enabled": True, "min": 0, "max": 3.05},
                },
                "pairwiseBondCutoffs": {al_pair: 3.05},
                "bondStyle": "cylinder",
                "bondThickness": 0.11,
                "bondColorMode": "custom",
                "bondCustomColor": "#746d69",
                "supercell": [4, 4, 2],
            },
        )
        page.set_input_files(
            "#phonopy-project-file",
            str(examples["phonopy_project"]),
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.phononModelSummary?.has_force_constants === true"
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.phononBandStructure?.convention === 'HPKOT'"
        )
        page.wait_for_function(
            "document.querySelectorAll('.phonon-band-branch').length === 18"
        )
        page.select_option("#phonon-projection-axis", "y")

        preview_atoms = aluminum.repeat((4, 4, 2))
        preview_center = np.mean(preview_atoms.positions, axis=0)
        settle_view(
            page,
            target=preview_center.tolist(),
            position=(preview_center + np.array([3.0, -4.0, 22.0])).tolist(),
            fov=36,
        )
        set_atomic_scale(page, 53.0)
        set_readme_lighting(
            page,
            preview_center.tolist(),
            intensity=2.85,
            position_offset=(-12.0, -15.0, 20.0),
        )
        _focus_element(page, "#phonon-model-status")
        page.locator("#phonon-band-plot").scroll_into_view_if_needed()

        def band_point(label: str, band: int) -> dict[str, float]:
            return page.evaluate(
                """({ label, band }) => {
                    const app = window.__V_ASE_APP__;
                    const result = app.state.phononBandStructure;
                    const segment = result.segments.find(item => item.end_label === label);
                    if (!segment) throw new Error(`HPKOT ${label} point is missing.`);
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

        frames = []

        def select_mode(label: str, band: int) -> None:
            point = band_point(label, band)
            page.mouse.move(point["x"], point["y"])
            page.wait_for_timeout(140)
            append_hold(frames, page, 4)
            page.mouse.click(point["x"], point["y"])
            page.wait_for_function(
                """({ label, band }) => {
                    const selected = window.__V_ASE_APP__.state.phononBandSelection;
                    return selected?.pathLabel === label && selected?.band === band
                        && window.__V_ASE_APP__.state.phononModes?.band_count === 3;
                }""",
                arg={"label": label, "band": band},
            )
            append_hold(frames, page, 5)

        def generate_selected_mode(
            displacement_color: str,
            expected_qpoint: list[float],
        ) -> None:
            page.fill("#phonon-mode-amplitude", "2.00")
            page.fill("#phonon-mode-frames", "24")
            page.fill("#phonon-mode-super-x", "4")
            page.fill("#phonon-mode-super-y", "4")
            page.fill("#phonon-mode-super-z", "2")
            set_display(page, {"supercell": [1, 1, 1]})
            page.click("#btn-phonon-modulate")
            page.click("#modal-confirm-action")
            page.wait_for_function(
                """(expected) => {
                    const app = window.__V_ASE_APP__;
                    const actual = app.state.phononTrajectoryMetadata?.qpoint;
                    return app.loadedFrameCount() === 24
                        && Array.isArray(actual)
                        && actual.every((value, index) => (
                            Math.abs(Number(value) - Number(expected[index])) < 1e-10
                        ));
                }""",
                arg=expected_qpoint,
            )
            page.evaluate(
                """async (color) => {
                    const app = window.__V_ASE_APP__;
                    Object.assign(app.state.display, {
                        showDisplacements: true,
                        displacementReferenceMode: 'frame',
                        displacementReferenceFrame: 12,
                        displacementMic: true,
                        displacementStyle: '3d',
                        displacementScale: 8.0,
                        displacementThickness: 0.12,
                        displacementColor: color
                    });
                    app.syncDisplacementControls();
                    app.renderer.setDisplayOptions(app.state.display);
                    await app.loadFrame(0);
                    await app.refreshDisplacementAnalysis({ suppressBusy: true });
                }""",
                displacement_color,
            )
            page.wait_for_function(
                "Number(window.__V_ASE_APP__.renderer.domElement.dataset.displacementCount || 0) > 0"
            )
            set_display(
                page,
                {
                    "atomRadiusScale": 0.48,
                    "showBonds": True,
                    "showPeriodicBonds": False,
                    "bondMode": "pairwise",
                    "pairwiseBondRanges": {
                        al_pair: {"enabled": True, "min": 0, "max": 3.05},
                    },
                    "pairwiseBondCutoffs": {al_pair: 3.05},
                    "bondThickness": 0.11,
                    "bondColorMode": "custom",
                    "bondCustomColor": "#746d69",
                },
            )
            page.wait_for_function(
                "Number(window.__V_ASE_APP__.renderer.domElement.dataset.bondCount || 0) > 0"
            )
            positions = np.asarray(
                page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
                dtype=float,
            )
            center = np.mean(positions, axis=0)
            settle_view(
                page,
                target=center.tolist(),
                position=(center + np.array([3.0, -4.0, 22.0])).tolist(),
                fov=36,
            )
            set_atomic_scale(page, 53.0)
            set_readme_lighting(
                page,
                center.tolist(),
                intensity=2.85,
                position_offset=(-12.0, -15.0, 20.0),
            )
            _focus_element(page, "#phonon-model-status")
            page.evaluate(
                "window.__V_ASE_APP__.refreshDisplacementAnalysis({ suppressBusy: true })"
            )
            page.wait_for_function(
                "Number(window.__V_ASE_APP__.renderer.domElement.dataset.displacementCount || 0) > 0"
            )
        def append_mode_cycle() -> None:
            append_hold(frames, page, 3)
            for frame_index in range(24):
                page.evaluate(
                    """async (frameIndex) => {
                        const app = window.__V_ASE_APP__;
                        await app.loadFrame(frameIndex);
                        await app.refreshDisplacementAnalysis({ suppressBusy: true });
                        app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
                    }""",
                    frame_index,
                )
                page.wait_for_timeout(35)
                frames.append(screenshot_frame(page))

        append_hold(frames, page, 3)
        selected_band = int(metadata["band"])
        select_mode("L", selected_band)
        generate_selected_mode("#2f8fbf", [0.5, 0.5, 0.5])
        append_mode_cycle()

        page.locator("#phonon-band-plot").scroll_into_view_if_needed()
        select_mode("X", selected_band)
        generate_selected_mode("#dc6b35", [0.5, 0.0, 0.5])
        screenshot_frame(page).save(
            ASSET_DIR / "readme_phonon_mode.png",
            optimize=True,
        )
        append_mode_cycle()
        save_gif(
            frames,
            ASSET_DIR / "readme_phonon_mode.gif",
            duration=85,
        )
    finally:
        page.close()
        editor.close()


def capture_all(examples: dict[str, object]) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    original_open = webbrowser.open
    webbrowser.open = lambda *args, **kwargs: True
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                capture_symmetry_analysis(browser, examples["silicon_primitive"])
                capture_standard_cell(browser, examples["silicon_primitive"])
                capture_finite_displacements(browser, examples["nacl"])
                capture_physical_mode(browser, examples)
            finally:
                browser.close()
    finally:
        webbrowser.open = original_open

    GITHUB_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    for name in (
        "readme_symmetry_analysis.png",
        "readme_symmetry_standard_cell.png",
        "readme_phonon_displacements.png",
        "readme_phonon_mode.png",
        "readme_phonon_mode.gif",
    ):
        shutil.copy2(ASSET_DIR / name, GITHUB_ASSET_DIR / name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--structures-only",
        action="store_true",
        help="Generate scientific example files without launching Chromium.",
    )
    args = parser.parse_args()
    examples = generate_examples()
    if not args.structures_only:
        capture_all(examples)
    print(f"Wrote symmetry examples to {EXAMPLE_DIR}")
    if not args.structures_only:
        print(f"Wrote symmetry README media to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
