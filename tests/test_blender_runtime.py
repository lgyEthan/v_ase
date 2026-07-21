from pathlib import Path
import shutil
import subprocess

import numpy as np
from ase import Atoms
from PIL import Image
import pytest

from v_ase.export import _blender_script
from v_ase.serialization import atoms_to_json


MACOS_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
BLENDER = shutil.which("blender") or (str(MACOS_BLENDER) if MACOS_BLENDER.exists() else None)


@pytest.mark.skipif(BLENDER is None, reason="Blender executable is not available")
def test_generated_scene_renders_principled_atom_colors_bonds_cell_and_sun(tmp_path):
    atoms = Atoms(
        "CuO",
        positions=[[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        cell=[5.0, 5.0, 5.0],
        pbc=True,
    )
    data = atoms_to_json(atoms)
    data["display"] = {
        "showBonds": True,
        "bondStyle": "cylinder",
        "bondThickness": 0.18,
        "bondColorMode": "split",
        "elementColors": {"Cu": "#c47a2c", "O": "#e51c23"},
        "lightingMode": "studio-shadow",
    }
    data["bonds"] = [{
        "i": 0,
        "j": 1,
        "start": [0.0, 0.0, 0.0],
        "end": [2.0, 0.0, 0.0],
        "length": 2.0,
    }]
    data["camera"] = {
        "position": [7.0, -9.0, 6.0],
        "target": [1.0, 0.0, 0.0],
        "projection": "orthographic",
        "ortho_scale": 7.0,
    }
    data["lighting"] = {
        "mode": "studio-shadow",
        "intensity": 3.4,
        "position": [7.0, -9.0, 12.0],
        "target": [1.0, 0.0, 0.0],
        "color": [1.0, 0.9, 0.8],
    }

    render_path = tmp_path / "render.png"
    script_path = tmp_path / "scene.py"
    validation = f'''
scene = bpy.context.scene
atom_materials = [mat for mat in bpy.data.materials if mat.name.startswith("atom ")]
assert len(atom_materials) == 2
for mat in atom_materials:
    assert mat.use_nodes
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    assert bsdf is not None
    color = bsdf.inputs["Base Color"].default_value
    assert max(color[:3]) - min(color[:3]) > 0.10
sun = bpy.data.objects.get("v_ase_studio_sun")
assert sun is not None and sun.data.type == "SUN"
assert abs(sun.data.energy - 3.4) < 1e-5
assert tuple(round(value, 6) for value in sun["v_ase_target"]) == (1.0, 0.0, 0.0)
assert len([obj for obj in bpy.data.objects if obj.name.startswith("unit_cell_edge_")]) == 12
assert len([obj for obj in bpy.data.objects if obj.name.startswith("bond_0_1_")]) == 2
scene.render.resolution_x = 320
scene.render.resolution_y = 240
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = {str(render_path)!r}
bpy.ops.render.render(write_still=True)
'''
    script_path.write_text(_blender_script(data) + validation, encoding="utf-8")

    result = subprocess.run(
        [BLENDER, "--background", "--factory-startup", "--python", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    blender_log = result.stdout + "\n" + result.stderr
    assert result.returncode == 0, blender_log
    assert "Traceback (most recent call last)" not in blender_log, blender_log
    assert render_path.exists() and render_path.stat().st_size > 1_000

    pixels = np.asarray(Image.open(render_path).convert("RGB"), dtype=np.int16)
    chroma = pixels.max(axis=2) - pixels.min(axis=2)
    assert int(np.count_nonzero(chroma > 24)) > 100
