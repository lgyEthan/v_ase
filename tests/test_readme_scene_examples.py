from pathlib import Path

import numpy as np
import pytest
from ase.constraints import FixedLine, FixedPlane, Hookean
from ase.io import read
from ase.neighborlist import neighbor_list
from ase.units import Bohr
from PIL import Image

from examples.readme_scenes import (
    SCENE_NAMES,
    make_ai_pyridinic_graphene_scene,
    make_amorphous_cuzr_rdf_scene,
    make_benzene_pi_volumetric_scene,
    make_black_phosphorene_unit_cell,
    make_copper_oxide_bond_scene,
    make_crowded_c60_relaxation_scene,
    make_ferrocene_scene,
    make_material_preset_scene,
    make_phosphorene_twist_scene,
    write_scene_assets,
)
from v_ase.io import atom_labels
from v_ase.analysis import calculate_rdf

ROOT = Path(__file__).resolve().parents[1]


def test_readme_scene_assets_write_reopenable_traj_files(tmp_path):
    written = write_scene_assets(tmp_path)
    written_names = {path.name for path in written}

    assert set(SCENE_NAMES) == {
        "phosphorene",
        "commensurate",
        "ai-edit",
        "bonding",
        "materials",
        "fixedline",
        "fixedplane",
        "hookean",
        "relaxation",
        "measurement",
        "ferrocene",
        "showcase",
    }
    assert "README.md" in written_names
    assert "graphene_hbn_commensurate.traj" in written_names
    assert "fixedline.traj" in written_names
    assert "fixedplane.traj" in written_names
    assert "hookean.traj" in written_names
    assert "ferrocene.traj" in written_names
    assert "showcase.traj" in written_names
    assert "phosphorene_nanosheet.cif" in written_names
    assert "phosphorene_twisted_nanoribbon_13p85deg.cif" in written_names
    assert "phosphorene_twist_13p85deg.traj" in written_names
    assert "crowded_c60_initial.cif" in written_names
    assert "crowded_c60_relaxed.cif" in written_names
    assert "crowded_c60_relaxation.traj" in written_names
    assert "ethane_measurement.cif" in written_names
    assert "ai_graphene_source.cif" in written_names
    assert "ai_pyridinic_n3_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.traj" in written_names
    assert "cu2o111_on_cu111_pairwise_bonds.traj" in written_names
    assert "material_presets.traj" in written_names
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")
    phosphorene_frames = read(tmp_path / "phosphorene_twist_13p85deg.traj", index=":")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)
    assert len(phosphorene_frames) == 19
    assert all(
        frame.info["twist_target_degrees"] == pytest.approx(13.85)
        for frame in phosphorene_frames
    )


def test_phosphorene_scene_uses_published_cell_angle_and_single_puckered_ridges():
    unit = make_black_phosphorene_unit_cell()
    source, twisted, frames, metadata = make_phosphorene_twist_scene()

    assert unit.cell.lengths() == pytest.approx(
        [8.628 * Bohr, 6.243 * Bohr, 51.930 * Bohr],
        abs=1e-8,
    )
    assert len(source) == len(twisted) == 120
    assert len(frames) == 19
    assert metadata["axis"] == "X"
    assert metadata["ribbon_direction"] == "armchair"
    assert metadata["target_twist_degrees"] == pytest.approx(13.85)
    assert metadata["angle_increment_degrees"] == pytest.approx(13.85 / 9.0)
    assert metadata["ridge_count"] == 10
    assert len(metadata["selected_ridge"]) == 12
    assert len(metadata["operations"]) == 9
    assert [operation["ridge_start"] for operation in metadata["operations"]] == list(range(1, 10))
    assert [len(operation["selected_indices"]) for operation in metadata["operations"]] == [
        108, 96, 84, 72, 60, 48, 36, 24, 12,
    ]
    assert all(
        operation["angle_degrees"] == pytest.approx(13.85 / 9.0)
        for operation in metadata["operations"]
    )
    assert np.max(np.linalg.norm(twisted.positions - source.positions, axis=1)) > 1.0
    assert np.allclose(frames[0].positions, source.positions)
    assert np.allclose(frames[-1].positions, twisted.positions)
    assert set(atom_labels(source)) == {"P_upper", "P_lower"}
    assert metadata["sublayer_colors"] == {
        "P_upper": "#6faf68",
        "P_lower": "#8064a2",
    }

    ridge_ids = np.asarray(metadata["ridge_ids"])
    sublayer_ids = np.asarray(metadata["sublayer_ids"])
    assert np.bincount(ridge_ids).tolist() == [12] * 10
    assert [
        int(np.unique(sublayer_ids[ridge_ids == ridge_id]).item())
        for ridge_id in range(10)
    ] == [1, 0] * 5
    assert np.allclose(
        source.positions[ridge_ids == 0],
        twisted.positions[ridge_ids == 0],
    )
    last_ridge = np.flatnonzero(ridge_ids == 9)
    same_x = last_ridge[
        np.isclose(
            source.positions[last_ridge, 0],
            np.min(source.positions[last_ridge, 0]),
        )
    ]
    lower_y = same_x[np.argmin(source.positions[same_x, 1])]
    upper_y = same_x[np.argmax(source.positions[same_x, 1])]
    initial_vector = source.positions[upper_y, 1:3] - source.positions[lower_y, 1:3]
    final_vector = twisted.positions[upper_y, 1:3] - twisted.positions[lower_y, 1:3]
    accumulated_angle = np.degrees(np.arctan2(
        initial_vector[0] * final_vector[1] - initial_vector[1] * final_vector[0],
        np.dot(initial_vector, final_vector),
    ))
    assert accumulated_angle == pytest.approx(13.85, abs=1e-8)

    bond_i, bond_j = neighbor_list("ij", source, 2.45)
    unique_bonds = bond_i < bond_j
    bond_i, bond_j = bond_i[unique_bonds], bond_j[unique_bonds]
    initial_lengths = np.linalg.norm(
        source.positions[bond_j] - source.positions[bond_i],
        axis=1,
    )
    final_lengths = np.linalg.norm(
        twisted.positions[bond_j] - twisted.positions[bond_i],
        axis=1,
    )
    bond_strain_percent = 100.0 * (final_lengths / initial_lengths - 1.0)
    assert np.max(np.abs(bond_strain_percent)) < 10.1

    for operation_index in range(len(metadata["operations"])):
        start = frames[operation_index * 2].positions
        end = frames[(operation_index + 1) * 2].positions
        ridge_start = operation_index + 1
        frozen = ridge_ids < ridge_start
        moving = ridge_ids >= ridge_start
        assert np.allclose(start[frozen], end[frozen])
        assert np.max(np.linalg.norm(end[moving] - start[moving], axis=1)) > 0.01


def test_relaxation_scene_is_an_actual_fire_trajectory_with_lower_repulsion():
    initial, relaxed, frames, metrics = make_crowded_c60_relaxation_scene()

    assert len(initial) == len(relaxed) == 60
    assert len(frames) >= 20
    assert metrics["final_energy"] < metrics["initial_energy"] * 0.01
    assert metrics["final_fmax"] < 0.05
    assert not np.allclose(initial.positions, relaxed.positions)


def test_ai_graphene_scene_is_generated_and_matches_the_n3_vacancy_edit():
    source, final, metadata = make_ai_pyridinic_graphene_scene()
    intermediate = metadata["intermediate"]

    assert len(source) == 72
    assert len(intermediate) == 71
    assert len(final) == 72
    assert source.get_chemical_formula() == "C72"
    assert final.get_chemical_symbols().count("N") == 3
    assert final.get_chemical_symbols().count("Li") == 1
    assert atom_labels(final).count("N_pyridinic") == 3
    assert atom_labels(final).count("Li_site") == 1
    assert final.positions[metadata["li_index"]] == pytest.approx(
        metadata["li_position"]
    )
    assert metadata["li_position"][2] - metadata["vacancy_position"][2] == pytest.approx(
        2.15
    )
    assert len(metadata["neighbors_before"]) == 3
    assert len(metadata["neighbors_after"]) == 3
    assert all(
        source.get_distance(
            metadata["vacancy_index"],
            index,
            mic=True,
        ) == pytest.approx(1.42028166, abs=1e-6)
        for index in metadata["neighbors_before"]
    )


def test_copper_oxide_bond_scene_is_coherent_cu2o111_on_cu111():
    atoms, groups = make_copper_oxide_bond_scene()

    assert len(groups["substrate_copper"]) == 196
    assert len(groups["oxide_copper"]) == 72
    assert len(groups["oxide_oxygen"]) == 36
    assert set(atom_labels(atoms)) == {
        "Cu_substrate",
        "Cu_oxide",
        "O_oxide",
    }
    assert set(atoms.get_chemical_symbols()) == {"Cu", "O"}
    assert atoms.get_chemical_formula() == "Cu268O36"
    assert atoms.info["in_plane_oxide_strain_percent"] == pytest.approx(
        -1.2202548,
        abs=1e-5,
    )
    assert len(groups["interfacial_oxygen"]) == 9
    assert len(groups["registry_anchor"]) == 2
    substrate_anchor, oxygen_anchor = groups["registry_anchor"]
    assert atoms.positions[oxygen_anchor, :2] == pytest.approx(
        atoms.positions[substrate_anchor, :2],
        abs=1e-10,
    )
    assert atoms.info["interface_anchor_lateral_distance_angstrom"] == pytest.approx(
        0.0,
        abs=1e-10,
    )
    assert "6x6 primitive Cu2O(111)" in atoms.info["model"]
    assert "top-anchored" in atoms.info["interface_registry"]
    assert "10.1021/acs.jpcc.0c04453" in " ".join(atoms.info["references"])

    primitive_surface_cell = np.array([
        atoms.cell[0, :2] / 7.0,
        atoms.cell[1, :2] / 7.0,
    ])
    interface_offsets = (
        atoms.positions[groups["interfacial_oxygen"], :2]
        - atoms.positions[oxygen_anchor, :2]
    )
    primitive_coordinates = np.linalg.solve(
        primitive_surface_cell.T,
        interface_offsets.T,
    ).T
    phase_coordinates = np.mod(
        np.round(primitive_coordinates, decimals=8),
        1.0,
    )
    phase_coordinates[np.isclose(phase_coordinates, 1.0)] = 0.0
    expected_phases = {
        (first, second)
        for first in (0.0, 1.0 / 3.0, 2.0 / 3.0)
        for second in (0.0, 1.0 / 3.0, 2.0 / 3.0)
    }
    assert {
        tuple(np.round(phase, decimals=6))
        for phase in phase_coordinates
    } == {
        tuple(np.round(phase, decimals=6))
        for phase in expected_phases
    }
    oxide_bonds = sum(
        np.count_nonzero(
            atoms.get_distances(index, groups["oxide_copper"], mic=True) < 2.08
        )
        for index in groups["oxide_oxygen"]
    )
    interface_bonds = sum(
        np.count_nonzero(
            atoms.get_distances(index, groups["substrate_copper"], mic=True) < 2.08
        )
        for index in groups["oxide_oxygen"]
    )
    assert oxide_bonds == 108
    assert interface_bonds == 7


def test_material_scene_keeps_elements_equal_while_labels_separate_presets():
    atoms, groups = make_material_preset_scene()

    assert len(atoms) == 39
    assert set(atoms.get_chemical_symbols()) == {"Cu"}
    assert list(groups) == ["Cu_standard", "Cu_metal", "Cu_rubber"]
    assert all(len(indices) == 13 for indices in groups.values())
    assert set(atom_labels(atoms)) == set(groups)


def test_analysis_examples_show_signed_isosurfaces_and_a_flat_amorphous_rdf_tail():
    molecule, values = make_benzene_pi_volumetric_scene()
    assert molecule.get_chemical_formula() == "C6H6"
    assert values.dtype == np.float32
    assert values.shape == (56, 56, 56)
    assert float(values.min()) < 0 < float(values.max())
    assert float(values.max()) == pytest.approx(-float(values.min()), rel=1e-6)

    amorphous = make_amorphous_cuzr_rdf_scene()
    assert len(amorphous) == 900
    assert np.all(amorphous.pbc)
    assert set(atom_labels(amorphous)) == {"Cu_glass", "Zr_glass"}
    result = calculate_rdf(
        amorphous,
        cutoff=11.0,
        bins=180,
        pair_mode="none",
    )
    tail = result.total[result.radius > 7.0]
    assert np.mean(tail) == pytest.approx(1.0, abs=0.05)
    assert np.std(tail) < 0.08
    assert result.total.max() > 1.4


def test_brand_logo_is_native_high_resolution_transparent_png():
    docs_logo = ROOT / "docs" / "assets" / "v_ase-logo.png"
    static_logo = ROOT / "v_ase" / "static" / "v_ase-logo.png"

    assert docs_logo.read_bytes() == static_logo.read_bytes()
    with Image.open(docs_logo) as image:
        assert image.size == (6144, 1890)
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (0, 255)
        alpha = np.asarray(image.getchannel("A"))
        partial_alpha = np.count_nonzero((alpha > 8) & (alpha < 247))
        opaque_alpha = np.count_nonzero(alpha >= 247)
        assert partial_alpha / opaque_alpha < 0.05


def test_brand_logo_generation_uses_approved_palette_and_separated_letter_atoms():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    assert 'LOGO_SUBSTRATE_COLOR", "#71493f"' in source
    assert 'LOGO_LETTER_COLOR", "#d7f26f"' in source
    assert 'LOGO_LETTER_RADIUS", "0.67"' in source
    assert "def sync_github_readme_assets()" in source
    assert "shutil.copy2(source, github_dir / source.name)" in source


def test_readme_presents_real_manipulation_and_analysis_workflows():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    ai = readme.index("## Work With An AI Agent")
    structure = readme.index("## Structure Manipulation")
    select = readme.index("### Select", structure)
    move = readme.index("### Move", select)
    rotate = readme.index("### Rotate", move)
    ferrocene = readme.index("#### Ferrocene: Use Fe As The Active Pivot", rotate)
    phosphorene = readme.index("#### Phosphorene: Build The Twist One Edit At A Time", ferrocene)
    commensurate = readme.index(
        "#### Commensurate Atoms: Match Periodic 2D Cells",
        phosphorene,
    )
    measurement = readme.index("## Measurement And Analysis", commensurate)

    assert ai < structure < select < move < rotate < ferrocene < phosphorene < commensurate < measurement
    normalized_readme = " ".join(
        line.lstrip("> ").strip() for line in readme.lower().splitlines()
    )
    assert "remove the carbon nearest the cell center" in normalized_readme
    assert "`N_pyridinic` labels" in readme
    assert "`Li_site`" in readme
    assert "2.15 A above the vacancy" in readme
    assert "three" in readme[ai:structure]
    assert "external ai agent" in normalized_readme
    assert "v_ase is the scientific application between you and an external ai agent" in normalized_readme
    assert "does not interpret natural language itself" in normalized_readme
    assert "exact, structured cli/api commands" in normalized_readme
    assert "gui edits enter the same document" in normalized_readme
    assert "instead of overwriting it" in normalized_readme
    assert "can reduce token use" in normalized_readme
    assert "Standard Metal and Rubber atom materials" in readme
    assert "Cu_substrate-Cu_substrate" in readme
    assert "Cu_oxide-O_oxide" in readme
    assert "Materials affect rendering only." in readme
    assert "reaches 100% once" in readme
    assert "structure and visualization-setting changes" in readme
    assert "camera navigation is excluded" in readme
    assert "Try the exact assets" not in readme
    assert "playback of a finished model" not in readme
    assert "long sequence of repetitive steps" not in readme
    assert "production `left-drag`" not in readme
    assert "visible amber box" in readme
    assert "from the **second ridge through the end**" in normalized_readme
    assert "from the **third ridge through the end**" in normalized_readme
    assert "**Rotate Selection**" in readme
    assert "**Active atom (last selected)**" in readme
    assert "Shift-select Fe last" in readme
    assert "`5 x 6` model contains 10 puckered ridges" in readme
    assert "12 atoms per ridge" in normalized_readme
    assert "backend commits" not in readme
    assert "final ridge is rotated by exactly 13.85 degrees" in readme
    assert "from above to below" in normalized_readme
    assert "green and purple distinguish" in normalized_readme
    assert "the upper and lower p sublayers" in normalized_readme
    assert "`6 x 6 Cu2O(111)` film on `7 x 7 Cu(111)`" in readme
    assert "substrate Cu top site" in readme
    assert "in-plane compression" not in readme
    assert "10.1021/acs.jpcc.0c04453" not in readme
    assert "**Axes** and **Unit Cell** switches update the working viewport" in readme
    assert "**Field smearing σ**" in readme
    assert "**Mesh smoothing passes**" in readme
    assert "source scalar field" in readme

    for filename in (
        "readme_phosphorene_twist.gif",
        "readme_ferrocene_pivot.gif",
        "readme_commensurate.gif",
        "readme_ai_edit.gif",
        "readme_ai_collaboration.png",
        "readme_ai_collaboration_live.png",
        "readme_materials.png",
        "readme_measurement.gif",
        "readme_displacement.png",
        "readme_volumetric.png",
        "readme_rdf.png",
    ):
        assert (ROOT / "docs" / "assets" / filename).is_file()
        assert (ROOT / "docs" / "assets" / "github" / filename).is_file()

    with Image.open(ROOT / "docs" / "assets" / "readme_ai_collaboration.png") as figure:
        assert figure.size == (2400, 1200)

    figure_source = (
        ROOT / "docs" / "design" / "ai_collaboration_figure.html"
    ).read_text(encoding="utf-8")
    for required in (
        "EXACT CLI / API COMMANDS",
        "EXACT STATE + REVISION",
        "LIVE 3D DOCUMENT",
        "GUI REFINEMENT",
        "scientific workspace in the cycle",
    ):
        assert required in figure_source
    assert "LIVE FEEDBACK LOOP" not in figure_source
    assert 'class="feedback"' not in figure_source


def test_phosphorene_capture_drives_the_production_selection_and_rotation_ui():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()

    assert "page.mouse.down(button=\"left\")" in source
    assert "page.mouse.move(" in source
    assert "page.mouse.up(button=\"left\")" in source
    assert "selected != expected" in source
    assert 'page.select_option("#selection-rotate-axis", "X")' in source
    assert 'page.locator("#selection-rotate-angle")' in source
    assert 'page.locator("#btn-rotate-selection-exact")' in source
    assert "detailed = operation_index < 2" in source
    assert "np.allclose(actual_positions, twisted.positions" in source


def test_readme_ferrocene_and_copper_bond_media_use_documented_visual_controls():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    _, ferrocene_groups = make_ferrocene_scene()

    assert ferrocene_groups["iron"] == [0]
    assert 'pivot_mode="active"' in source
    assert 'pivot_index=indices["iron"][0]' in source
    assert '"1/2 | active pivot: Fe #0 | R Z"' in source
    assert '"2/2 | active pivot: Fe #0 | R X ring fold"' in source
    assert '"bondThickness": 0.30' in source
    assert '"bondColorMode": "split"' in source
    assert '"Cu_substrate": "#744637"' in source
    assert '"Cu_oxide": "#efb34f"' in source
    assert '"O_oxide": "#df2935"' in source
    assert '"Cu_substrate": "metal"' in source
    assert '"Cu_oxide": "standard"' in source
    assert '"O_oxide": "rubber"' in source


def test_readme_volumetric_media_uses_refined_isosurface_controls():
    source = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text()
    assert "smearingSigma: 0.45" in source
    assert "smoothingIterations: 7" in source
    assert "document.getElementById('volume-smearing')?.value" in source
    assert "document.getElementById('volume-smoothing')?.value" in source
    assert "#176f8c" not in source

    image = np.asarray(
        Image.open(ROOT / "docs" / "assets" / "readme_bonds.png").convert("RGB")
    )[60:, :1360]
    oxide_red = (
        (image[:, :, 0] > 150)
        & (image[:, :, 1] < 100)
        & (image[:, :, 2] < 110)
    )
    warm_oxide_copper = (
        (image[:, :, 0] > 170)
        & (image[:, :, 1] > 95)
        & (image[:, :, 1] < 190)
        & (image[:, :, 2] < 100)
    )
    dark_metallic_copper = (
        (image[:, :, 0] > 55)
        & (image[:, :, 0] < 155)
        & (image[:, :, 1] > 25)
        & (image[:, :, 1] < 105)
        & (image[:, :, 2] < 90)
    )
    assert int(oxide_red.sum()) > 1_500
    assert int(warm_oxide_copper.sum()) > 7_500
    assert int(dark_metallic_copper.sum()) > 30_000
