import asyncio
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from ase.data import atomic_numbers, covalent_radii
from ase.data.colors import jmol_colors

from v_ase.export import (
    export_blender_response,
    export_pickle_response,
    export_poscar_response,
)
from v_ase.serialization import atoms_to_json
from v_ase.server import EditorSession, apply_positions, apply_supercell, delete_atoms, wrap
from v_ase.session import sessions


ROOT = Path(__file__).resolve().parents[1]
ASE_GUI_RADIUS_SCALE = 0.89


def ase_gui_jmol_hex(symbol):
    rgb = jmol_colors[atomic_numbers[symbol]]
    return "#{:02X}{:02X}{:02X}".format(*[int(float(v) * 255) for v in rgb])


def constrained_demo_atoms():
    atoms = Atoms(
        symbols=["O", "H", "H"],
        positions=[
            [0.00, 0.00, 0.00],
            [1.25, 0.75, 0.00],
            [3.05, 0.75, 0.00],
        ],
        cell=[8.0, 8.0, 8.0],
        pbc=[True, True, True],
    )
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=2.25, k=5.0),
    ])
    return atoms


def register_session(name, atoms):
    session = EditorSession(name, atoms.copy(), atoms.copy())
    sessions[name] = session
    return session


def test_complete_user_requested_workflow_showcase():
    atoms = constrained_demo_atoms()

    # 1. Every requested ASE constraint is serialized for the browser.
    serialized = atoms_to_json(atoms)
    assert serialized["constraints"]["fixed_indices"] == [0]
    assert serialized["constraints"]["fixed_line"]["1"] == [1.0, 0.0, 0.0]
    assert serialized["constraints"]["fixed_plane"]["2"] == [0.0, 0.0, 1.0]
    assert serialized["constraints"]["hookean"] == [{
        "kind": "two atoms",
        "indices": [1, 2],
        "threshold": 2.25,
        "spring": 5.0,
    }]
    assert serialized["visual"]["color_source"] == "ase.gui.view.View.colors using ase.data.colors.jmol_colors"
    assert serialized["visual"]["radius_source"] == "ase.gui.images.Images.get_radii: ase.data.covalent_radii * 0.89"
    assert serialized["visual"]["radius_scale"] == ASE_GUI_RADIUS_SCALE
    assert serialized["visual"]["colors"] == [ase_gui_jmol_hex(symbol) for symbol in ["O", "H", "H"]]
    assert serialized["visual"]["radii"] == [
        float(covalent_radii[atomic_numbers[symbol]] * ASE_GUI_RADIUS_SCALE)
        for symbol in ["O", "H", "H"]
    ]
    assert serialized["tags"] == [0, 0, 0]
    assert serialized["charges"] == [0.0, 0.0, 0.0]
    assert serialized["magmoms"] == [0.0, 0.0, 0.0]

    # 2. apply_constraint=True: FixAtoms, FixedLine, FixedPlane all constrain edits.
    constrained_session = register_session("showcase-constrained", atoms)
    proposed = atoms.positions.copy()
    proposed[0] += [0.5, 0.5, 0.5]
    proposed[1] += [1.0, 1.0, 1.0]
    proposed[2] += [1.0, 1.0, 1.0]

    constrained = asyncio.run(apply_positions(constrained_session.session_id, {
        "positions": proposed.tolist(),
        "apply_constraint": True,
    }))
    constrained_positions = np.array(constrained["positions"])

    assert np.allclose(constrained_positions[0], atoms.positions[0])
    assert constrained_positions[1, 0] != atoms.positions[1, 0]
    assert np.isclose(constrained_positions[1, 1], atoms.positions[1, 1])
    assert np.isclose(constrained_positions[1, 2], atoms.positions[1, 2])
    assert np.isclose(constrained_positions[2, 2], atoms.positions[2, 2])

    # 3. apply_constraint=False: the same edit is accepted exactly for free Blender-like editing.
    free_session = register_session("showcase-free-edit", atoms)
    free = asyncio.run(apply_positions(free_session.session_id, {
        "positions": proposed.tolist(),
        "apply_constraint": False,
    }))
    assert np.allclose(free["positions"], proposed)

    # 4. Export paths exist and Blender export contains editable Hookean threshold/marker geometry.
    export_session = register_session("showcase-export", atoms)
    blender = export_blender_response(export_session, {
        "positions": atoms.positions.tolist(),
        "apply_constraint": False,
    })
    blender_script = Path(blender.path).read_text(encoding="utf-8")
    assert blender.filename == "v_ase_blender_scene.py"
    assert len(blender_script) > 1000
    assert "threshold_y = left_center + threshold" in blender_script
    assert "_inactive_gap" in blender_script
    assert "_dead_zone_rail" in blender_script
    assert "_cutoff_gate" in blender_script
    assert "_lock_pin" in blender_script
    assert "ATOM_COLORS = VISUAL.get(\"colors\", [])" in blender_script
    assert "get_atom_radius(idx)" in blender_script

    poscar = export_poscar_response(export_session, {
        "positions": atoms.positions.tolist(),
        "apply_constraint": False,
    })
    pickle_file = export_pickle_response(export_session, {
        "positions": atoms.positions.tolist(),
        "apply_constraint": False,
        "include_calculator": False,
    })
    assert poscar.filename == "POSCAR"
    assert Path(poscar.path).stat().st_size > 0
    assert pickle_file.filename == "atoms.pkl"
    assert Path(pickle_file.path).stat().st_size > 0

    # 5. Set Supercell as Cell creates real editable atoms/cell, not translucent ghosts.
    supercell_session = register_session("showcase-supercell", atoms)
    supercell = asyncio.run(apply_supercell(supercell_session.session_id, {
        "positions": atoms.positions.tolist(),
        "reps": [2, 1, 1],
        "apply_constraint": True,
    }))
    assert supercell["metadata"]["natoms"] == 6
    assert np.allclose(supercell["cell"][0], [16.0, 0.0, 0.0])
    assert sorted(supercell["constraints"]["fixed_indices"]) == [0, 3]
    assert supercell["constraints"]["fixed_line"]["1"] == [1.0, 0.0, 0.0]
    assert supercell["constraints"]["fixed_line"]["4"] == [1.0, 0.0, 0.0]
    assert supercell["constraints"]["fixed_plane"]["2"] == [0.0, 0.0, 1.0]
    assert supercell["constraints"]["fixed_plane"]["5"] == [0.0, 0.0, 1.0]
    assert [item["indices"] for item in supercell["constraints"]["hookean"]] == [[1, 2], [4, 5]]

    # 6. Delete and Wrap are available as Blender-like editing actions.
    delete_session = register_session("showcase-delete", atoms)
    deleted = asyncio.run(delete_atoms(delete_session.session_id, {"indices": [0]}))
    assert deleted["metadata"]["natoms"] == 2
    assert deleted["constraints"]["fixed_indices"] == []
    assert deleted["constraints"]["fixed_line"]["0"] == [1.0, 0.0, 0.0]
    assert deleted["constraints"]["fixed_plane"]["1"] == [0.0, 0.0, 1.0]
    assert deleted["constraints"]["hookean"][0]["indices"] == [0, 1]

    wrap_atoms = constrained_demo_atoms()
    wrap_atoms.positions[1] += [8.2, -8.1, 0.0]
    wrap_session = register_session("showcase-wrap", wrap_atoms)
    wrapped = asyncio.run(wrap(wrap_session.session_id, {"positions": wrap_atoms.positions.tolist()}))
    wrapped_positions = np.array(wrapped["positions"])
    assert np.all(wrapped_positions >= -1e-9)
    assert np.all(wrapped_positions <= 8.0 + 1e-9)

    # 7. The browser-side controls and math paths for rotate constraints, PBC bonds,
    # Hookean state display, exports, and supercell UI are wired in one place.
    main_js = (ROOT / "v_ase/static/main.js").read_text(encoding="utf-8")
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text(encoding="utf-8")
    api_js = (ROOT / "v_ase/static/api.js").read_text(encoding="utf-8")
    index_html = (ROOT / "v_ase/static/index.html").read_text(encoding="utf-8")

    assert "chk-constraints" in index_html
    assert "btn-set-supercell" in index_html
    assert "btn-wrap" in index_html
    assert "btn-delete-selection" in index_html
    assert "move-increment" in index_html
    assert "rotate-increment" in index_html
    assert "hover-readout" in index_html
    assert "sphere-quality" in index_html
    assert "element-bond-list" in index_html
    assert "this.constrainedMoveDelta(idx, rotatedTarget.sub(origVec))" in main_js
    assert "this.transform.rotationAngle -= delta" in main_js
    assert "snapMoveDelta" in main_js
    assert "snapRotationAngle" in main_js
    assert "formatMoveReadout" in main_js
    assert "formatRotateReadout" in main_js
    assert "atomHoverText" in main_js
    assert "alignViewToAxis" in main_js
    assert "showMarquee" in main_js
    assert "deleteSelection" in main_js
    assert "e.code === 'Delete'" in main_js
    assert "renderElementBondControls" in main_js
    assert "parseElementBondCutoffs" in main_js
    assert "state.applyConstraints" in main_js
    assert "apply_constraint" in api_js
    assert "applySupercell" in api_js
    assert "deleteAtoms" in api_js
    assert "minimumImageDelta" in renderer_js
    assert "cartToFrac" in renderer_js
    assert "addSupercellCellPreview" in renderer_js
    assert "sphereQualitySegments" in renderer_js
    assert "elementBondCutoff" in renderer_js
    assert "hookeanDistance" in renderer_js
    assert "hookeanThreshold" in renderer_js
    assert "hookeanExtension" in renderer_js
    assert "hookeanGuide" in renderer_js
    assert "lockPin" in renderer_js
    assert "springLine.visible = state !== 'inactive'" in renderer_js
    assert "atomVisualRadius" in renderer_js
    assert "atomVisualColor" in renderer_js
    assert "includeAxes" in renderer_js
    assert "export-axes" in main_js
