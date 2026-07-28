from pathlib import Path

import numpy as np
import pytest
from ase.constraints import FixedLine, FixedPlane, Hookean
from ase.io import read
from ase.units import Bohr
from PIL import Image

from examples.readme_scenes import (
    SCENE_NAMES,
    make_black_phosphorene_unit_cell,
    make_crowded_c60_relaxation_scene,
    make_phosphorene_twist_scene,
    write_scene_assets,
)

ROOT = Path(__file__).resolve().parents[1]


def test_readme_scene_assets_write_reopenable_traj_files(tmp_path):
    written = write_scene_assets(tmp_path)
    written_names = {path.name for path in written}

    assert set(SCENE_NAMES) == {
        "phosphorene",
        "commensurate",
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
    assert "phosphorene_twisted_nanoribbon_15deg.cif" in written_names
    assert "phosphorene_twist_15deg.traj" in written_names
    assert "crowded_c60_initial.cif" in written_names
    assert "crowded_c60_relaxed.cif" in written_names
    assert "crowded_c60_relaxation.traj" in written_names
    assert "ethane_measurement.cif" in written_names
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)


def test_phosphorene_scene_uses_published_cell_and_cumulative_tail_rotations():
    unit = make_black_phosphorene_unit_cell()
    source, twisted, frames, metadata = make_phosphorene_twist_scene()

    assert unit.cell.lengths() == pytest.approx(
        [8.628 * Bohr, 6.243 * Bohr, 51.930 * Bohr],
        abs=1e-8,
    )
    assert len(source) == len(twisted) == 132
    assert len(frames) == 31
    assert metadata["axis"] == "X"
    assert metadata["angle_step_degrees"] == pytest.approx(15.0)
    assert len(metadata["selected_slice"]) == 12
    assert len(metadata["operations"]) == 10
    assert [operation["slice_start"] for operation in metadata["operations"]] == list(range(10))
    assert [len(operation["selected_indices"]) for operation in metadata["operations"]] == [
        132, 120, 108, 96, 84, 72, 60, 48, 36, 24,
    ]
    assert all(
        operation["angle_degrees"] == pytest.approx(15.0)
        for operation in metadata["operations"]
    )
    assert np.max(np.linalg.norm(twisted.positions - source.positions, axis=1)) > 2.0
    assert np.allclose(frames[0].positions, source.positions)
    assert np.allclose(frames[-1].positions, twisted.positions)

    slice_ids = np.asarray(metadata["slice_ids"])
    for operation_index in range(1, len(metadata["operations"])):
        start = frames[operation_index * 3].positions
        end = frames[(operation_index + 1) * 3].positions
        frozen = slice_ids < operation_index
        moving = slice_ids >= operation_index
        assert np.allclose(start[frozen], end[frozen])
        assert np.max(np.linalg.norm(end[moving] - start[moving], axis=1)) > 0.1


def test_relaxation_scene_is_an_actual_fire_trajectory_with_lower_repulsion():
    initial, relaxed, frames, metrics = make_crowded_c60_relaxation_scene()

    assert len(initial) == len(relaxed) == 60
    assert len(frames) >= 20
    assert metrics["final_energy"] < metrics["initial_energy"] * 0.01
    assert metrics["final_fmax"] < 0.05
    assert not np.allclose(initial.positions, relaxed.positions)


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
    structure = readme.index("## Structure Manipulation")
    select = readme.index("### Select", structure)
    move = readme.index("### Move", select)
    rotate = readme.index("### Rotate", move)
    ferrocene = readme.index("#### Ferrocene: Choose The Pivot", rotate)
    phosphorene = readme.index("#### Phosphorene: Build The Twist One Edit At A Time", ferrocene)
    commensurate = readme.index("#### Graphene/hBN: Find A Commensurate Rotation", phosphorene)
    measurement = readme.index("## Measurement And Analysis", commensurate)

    assert structure < select < move < rotate < ferrocene < phosphorene < commensurate < measurement
    assert "Try the exact assets" not in readme
    assert "playback of a finished model" in readme
    assert "**Axes** and **Unit Cell** switches update the working viewport" in readme

    for filename in (
        "readme_phosphorene_twist.gif",
        "readme_ferrocene_pivot.gif",
        "readme_commensurate.gif",
        "readme_measurement.gif",
        "readme_displacement.png",
    ):
        assert (ROOT / "docs" / "assets" / filename).is_file()
        assert (ROOT / "docs" / "assets" / "github" / filename).is_file()
