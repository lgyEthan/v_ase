from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from ase import Atoms
import pytest

from v_ase.export import _blender_script
from v_ase.serialization import atoms_to_json


MACOS_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
BLENDER = shutil.which("blender") or (str(MACOS_BLENDER) if MACOS_BLENDER.exists() else None)


@pytest.mark.skipif(BLENDER is None, reason="Blender executable is not available")
def test_optimized_blender_scene_keeps_15000_atoms_in_few_editable_point_groups(tmp_path):
    atom_count = 15_000
    indices = np.arange(atom_count, dtype=float)
    positions = np.column_stack((indices % 50, (indices // 50) % 30, indices // 1500)) * 1.6
    numbers = np.where((np.arange(atom_count) % 3) == 0, 8, 1)
    atoms = Atoms(numbers=numbers, positions=positions, cell=[82, 50, 18], pbc=True)
    data = atoms_to_json(atoms)
    data["display"] = {
        "showBonds": False,
        "blenderExportMode": "instanced",
        "sphereQuality": "auto",
        "lightingMode": "studio",
    }
    data["lighting"] = {
        "mode": "studio",
        "intensity": 2.2,
        "position": [35, -45, 60],
        "target": [35, 24, 8],
    }

    blend_path = tmp_path / "large_scene.blend"
    script_path = tmp_path / "large_scene.py"
    validation = f'''
groups = [obj for obj in bpy.data.objects if obj.get("v_ase_atom_group")]
assert len(groups) == 2
assert sum(int(obj["v_ase_atom_count"]) for obj in groups) == {atom_count}
assert len(bpy.data.objects) < 12
bpy.ops.wm.save_as_mainfile(filepath={str(blend_path)!r})
'''
    script_path.write_text(_blender_script(data) + validation, encoding="utf-8")

    started = time.perf_counter()
    result = subprocess.run(
        [BLENDER, "--background", "--factory-startup", "--python", str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    elapsed = time.perf_counter() - started
    print(f"BLENDER_15000_ATOM_IMPORT_SECONDS={elapsed:.3f}")
    blender_log = result.stdout + "\n" + result.stderr
    assert result.returncode == 0, blender_log
    assert blend_path.exists() and blend_path.stat().st_size > 50_000
    assert elapsed < 20.0, f"15,000-atom Blender scene took {elapsed:.2f}s\n{blender_log}"
