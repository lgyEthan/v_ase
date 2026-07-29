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
    make_black_phosphorene_unit_cell,
    make_copper_oxide_bond_scene,
    make_crowded_c60_relaxation_scene,
    make_material_preset_scene,
    make_phosphorene_twist_scene,
    write_scene_assets,
)
from v_ase.io import atom_labels

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
    assert "phosphorene_twisted_nanoribbon_36deg.cif" in written_names
    assert "phosphorene_twist_36deg.traj" in written_names
    assert "crowded_c60_initial.cif" in written_names
    assert "crowded_c60_relaxed.cif" in written_names
    assert "crowded_c60_relaxation.traj" in written_names
    assert "ethane_measurement.cif" in written_names
    assert "ai_graphene_source.cif" in written_names
    assert "ai_pyridinic_n3_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.cif" in written_names
    assert "ai_pyridinic_n3_li_graphene.traj" in written_names
    assert "cu111_oxygen_pairwise_bonds.traj" in written_names
    assert "material_presets.traj" in written_names
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")
    phosphorene_frames = read(tmp_path / "phosphorene_twist_36deg.traj", index=":")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)
    assert len(phosphorene_frames) == 43
    assert all(
        frame.info["twist_target_degrees"] == pytest.approx(36.0)
        for frame in phosphorene_frames
    )


def test_phosphorene_scene_uses_published_cell_angle_and_single_puckered_ridges():
    unit = make_black_phosphorene_unit_cell()
    source, twisted, frames, metadata = make_phosphorene_twist_scene()

    assert unit.cell.lengths() == pytest.approx(
        [8.628 * Bohr, 6.243 * Bohr, 51.930 * Bohr],
        abs=1e-8,
    )
    assert len(source) == len(twisted) == 132
    assert len(frames) == 43
    assert metadata["axis"] == "X"
    assert metadata["ribbon_direction"] == "armchair"
    assert metadata["target_twist_degrees"] == pytest.approx(36.0)
    assert metadata["angle_increment_degrees"] == pytest.approx(36.0 / 21.0)
    assert metadata["ridge_count"] == 22
    assert len(metadata["selected_ridge"]) == 6
    assert len(metadata["operations"]) == 21
    assert [operation["ridge_start"] for operation in metadata["operations"]] == list(range(1, 22))
    assert [len(operation["selected_indices"]) for operation in metadata["operations"]] == [
        126, 120, 114, 108, 102, 96, 90, 84, 78, 72, 66,
        60, 54, 48, 42, 36, 30, 24, 18, 12, 6,
    ]
    assert all(
        operation["angle_degrees"] == pytest.approx(36.0 / 21.0)
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
    assert np.bincount(ridge_ids).tolist() == [6] * 22
    assert [
        int(np.unique(sublayer_ids[ridge_ids == ridge_id]).item())
        for ridge_id in range(22)
    ] == [1, 0] * 11
    assert np.allclose(
        source.positions[ridge_ids == 0],
        twisted.positions[ridge_ids == 0],
    )
    last_ridge = np.flatnonzero(ridge_ids == 21)
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
    assert accumulated_angle == pytest.approx(36.0, abs=1e-8)

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
    assert np.max(np.abs(bond_strain_percent)) < 10.0

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


def test_copper_oxide_bond_scene_has_separate_surface_and_adsorbate_labels():
    atoms, groups = make_copper_oxide_bond_scene()

    assert len(groups["copper"]) == 48
    assert len(groups["oxygen"]) == 4
    assert set(atom_labels(atoms)) == {"Cu_surface", "O_ads"}
    assert set(atoms.get_chemical_symbols()) == {"Cu", "O"}
    cu_o = atoms.get_distances(
        groups["oxygen"][0],
        groups["copper"],
        mic=True,
    )
    assert np.count_nonzero(cu_o < 2.25) == 3


def test_material_scene_keeps_elements_equal_while_labels_separate_presets():
    atoms, groups = make_material_preset_scene()

    assert len(atoms) == 39
    assert set(atoms.get_chemical_symbols()) == {"Cu"}
    assert list(groups) == ["Cu_standard", "Cu_metal", "Cu_rubber"]
    assert all(len(indices) == 13 for indices in groups.values())
    assert set(atom_labels(atoms)) == set(groups)


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
    ai = readme.index("## Ask An AI To Edit A Structure")
    structure = readme.index("## Structure Manipulation")
    select = readme.index("### Select", structure)
    move = readme.index("### Move", select)
    rotate = readme.index("### Rotate", move)
    ferrocene = readme.index("#### Ferrocene: Choose The Pivot", rotate)
    phosphorene = readme.index("#### Phosphorene: Build The Twist One Edit At A Time", ferrocene)
    commensurate = readme.index("#### Graphene/hBN: Find A Commensurate Rotation", phosphorene)
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
    assert "no screenshot ocr or coordinate guessing is required." in normalized_readme
    assert "Standard Metal and Rubber atom materials" in readme
    assert "Cu_surface-Cu_surface" in readme
    assert "Cu_surface-O_ads" in readme
    assert "Materials affect rendering only." in readme
    assert "reaches 100% once" in readme
    assert "appearance, bond, and rendering changes" in readme
    assert "Try the exact assets" not in readme
    assert "playback of a finished model" in readme
    assert "one half-cell ridge per step" in readme
    assert "6 atoms at this ribbon" in readme
    assert "final ridge is rotated by exactly 36 degrees" in readme
    assert "Green and purple distinguish" in readme
    assert "the upper and lower P sublayers" in readme
    assert "**Axes** and **Unit Cell** switches update the working viewport" in readme

    for filename in (
        "readme_phosphorene_twist.gif",
        "readme_ferrocene_pivot.gif",
        "readme_commensurate.gif",
        "readme_ai_edit.gif",
        "readme_materials.png",
        "readme_measurement.gif",
        "readme_displacement.png",
    ):
        assert (ROOT / "docs" / "assets" / filename).is_file()
        assert (ROOT / "docs" / "assets" / "github" / filename).is_file()
