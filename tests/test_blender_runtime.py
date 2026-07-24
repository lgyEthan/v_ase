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
    moved = atoms.copy()
    moved.positions += [0.3, 0.2, 0.1]
    data["frames"] = [atoms_to_json(atoms), atoms_to_json(moved)]
    data["display"] = {
        "showBonds": True,
        "bondStyle": "cylinder",
        "bondThickness": 0.18,
        "bondColorMode": "split",
        "labelColors": {"Cu": "#c47a2c", "O": "#e51c23"},
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
assert bpy.data.objects.get("v_ase_sun_source") is not None
assert bpy.data.objects.get("v_ase_sun_target") is not None
source = bpy.data.objects["v_ase_sun_source"]
target = bpy.data.objects["v_ase_sun_target"]
assert tuple(round(value, 6) for value in source.location) == (7.0, -9.0, 12.0)
assert tuple(round(value, 6) for value in target.location) == (1.0, 0.0, 0.0)
bpy.context.view_layer.update()
evaluated_sun = sun.evaluated_get(bpy.context.evaluated_depsgraph_get())
actual_direction = (evaluated_sun.matrix_world.to_quaternion() @ Vector((0, 0, -1))).normalized()
expected_direction = (target.matrix_world.translation - source.matrix_world.translation).normalized()
assert (actual_direction - expected_direction).length < 1e-5
atom_groups = [obj for obj in bpy.data.objects if obj.get("v_ase_atom_group")]
assert len(atom_groups) == 2
assert sum(int(obj.get("v_ase_atom_count", 0)) for obj in atom_groups) == 2
assert all(any(mod.type == "NODES" for mod in obj.modifiers) for obj in atom_groups)
assert all(obj.data.shape_keys is not None and len(obj.data.shape_keys.key_blocks) == 3 for obj in atom_groups)
scene.frame_set(2)
bpy.context.view_layer.update()
for group in atom_groups:
    atom_index = int(group.data.attributes["atom_index"].data[0].value)
    actual = group.data.shape_keys.key_blocks["frame_00002"].data[0].co
    expected = Vector({moved.positions.tolist()!r}[atom_index])
    assert (actual - expected).length < 1e-5
scene.frame_set(1)
assert bpy.data.objects.get("unit_cell_edges") is not None
assert len([obj for obj in bpy.data.objects if obj.name.startswith("bond_group_")]) == 2
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
