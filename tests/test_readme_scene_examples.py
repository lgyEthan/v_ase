from ase.constraints import FixedLine, FixedPlane, Hookean
from ase.io import read

from examples.readme_scenes import SCENE_NAMES, write_scene_assets


def test_readme_scene_assets_write_reopenable_traj_files(tmp_path):
    written = write_scene_assets(tmp_path)
    written_names = {path.name for path in written}

    assert set(SCENE_NAMES) == {"fixedline", "fixedplane", "hookean", "ferrocene", "showcase"}
    assert "README.md" in written_names
    assert "fixedline.traj" in written_names
    assert "fixedplane.traj" in written_names
    assert "hookean.traj" in written_names
    assert "ferrocene.traj" in written_names
    assert "showcase.traj" in written_names
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)
