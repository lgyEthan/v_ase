from pathlib import Path

import numpy as np
from ase.constraints import FixedLine, FixedPlane, Hookean
from ase.io import read
from PIL import Image

from examples.readme_scenes import SCENE_NAMES, write_scene_assets

ROOT = Path(__file__).resolve().parents[1]


def test_readme_scene_assets_write_reopenable_traj_files(tmp_path):
    written = write_scene_assets(tmp_path)
    written_names = {path.name for path in written}

    assert set(SCENE_NAMES) == {
        "commensurate",
        "fixedline",
        "fixedplane",
        "hookean",
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
    assert not any(path.name.endswith("_motion.traj") for path in written)

    fixedline = read(tmp_path / "fixedline.traj")
    fixedplane = read(tmp_path / "fixedplane.traj")
    hookean = read(tmp_path / "hookean.traj")
    showcase = read(tmp_path / "showcase.traj")

    assert any(isinstance(constraint, FixedLine) for constraint in fixedline.constraints)
    assert any(isinstance(constraint, FixedPlane) for constraint in fixedplane.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in hookean.constraints)
    assert any(isinstance(constraint, Hookean) for constraint in showcase.constraints)


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
