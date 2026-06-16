import asyncio
import numpy as np
from ase.build import molecule
from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean
from v_ase.export import export_blender_response
from v_ase.serialization import atoms_to_json
from v_ase.server import apply_positions, apply_supercell, update_constraints
from v_ase.server import EditorSession

def test_fix_atoms_enforcement():
    atoms = molecule("H2O")
    atoms.set_constraint(FixAtoms(indices=[0])) # Fix Oxygen
    pos0_orig = atoms.positions[0].copy()
    
    sess = EditorSession("test", atoms.copy(), atoms.copy())
    
    # Try to move Oxygen
    proposed = atoms.get_positions()
    proposed[0] += [1.0, 1.0, 1.0] # Move by 1A
    
    # Apply via backend logic
    sess.working_atoms.set_positions(proposed, apply_constraint=True)
    
    # Assertion: Oxygen must NOT have moved
    assert np.allclose(sess.working_atoms.positions[0], pos0_orig), "FixAtoms failed backend enforcement"

def test_fixed_line_enforcement():
    atoms = molecule("H2O")
    # Fix Hydrogen 1 to move only along X axis
    atoms.set_constraint(FixedLine(1, [1, 0, 0]))
    
    sess = EditorSession("test", atoms.copy(), atoms.copy())
    pos1_orig = atoms.positions[1].copy()
    
    # Try to move H1 in XYZ
    proposed = atoms.get_positions()
    proposed[1] += [1.0, 1.0, 1.0]
    
    sess.working_atoms.set_positions(proposed, apply_constraint=True)
    
    # Assertion: Y and Z should be unchanged relative to original
    assert np.isclose(sess.working_atoms.positions[1][1], pos1_orig[1])
    assert np.isclose(sess.working_atoms.positions[1][2], pos1_orig[2])
    assert sess.working_atoms.positions[1][0] != pos1_orig[0]

def test_fixed_plane_enforcement():
    atoms = molecule("H2O")
    # Fix Hydrogen 2 to move only in XY plane (Normal = Z)
    atoms.set_constraint(FixedPlane(2, [0, 0, 1]))
    
    sess = EditorSession("test", atoms.copy(), atoms.copy())
    pos2_orig = atoms.positions[2].copy()
    
    proposed = atoms.get_positions()
    proposed[2] += [1.0, 1.0, 1.0]
    
    sess.working_atoms.set_positions(proposed, apply_constraint=True)
    
    # Assertion: Z should be unchanged
    assert np.isclose(sess.working_atoms.positions[2][2], pos2_orig[2])


def test_constraint_serialization_line_plane_and_hookean():
    atoms = molecule("H2O")
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=1.4, k=5.0),
    ])

    data = atoms_to_json(atoms)

    assert data["constraints"]["fixed_indices"] == [0]
    assert data["constraints"]["fixed_line"]["1"] == [1.0, 0.0, 0.0]
    assert data["constraints"]["fixed_plane"]["2"] == [0.0, 0.0, 1.0]
    assert data["constraints"]["hookean"] == [{
        "spring": 5.0,
        "threshold": 1.4,
        "kind": "two atoms",
        "indices": [1, 2],
    }]


def test_apply_endpoint_enforces_fixed_line_and_plane():
    atoms = molecule("H2O")
    atoms.set_constraint([
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
    ])
    session = EditorSession("constraint-endpoint", atoms.copy(), atoms.copy())
    from v_ase.session import sessions
    sessions[session.session_id] = session

    proposed = atoms.positions.copy()
    proposed[1] += [1.0, 1.0, 1.0]
    proposed[2] += [1.0, 1.0, 1.0]

    data = asyncio.run(apply_positions(session.session_id, {"positions": proposed.tolist()}))

    assert np.isclose(data["positions"][1][1], atoms.positions[1][1])
    assert np.isclose(data["positions"][1][2], atoms.positions[1][2])
    assert np.isclose(data["positions"][2][2], atoms.positions[2][2])


def test_apply_endpoint_can_disable_constraints_for_free_editing():
    atoms = molecule("H2O")
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
    ])
    session = EditorSession("constraint-disabled", atoms.copy(), atoms.copy())
    from v_ase.session import sessions
    sessions[session.session_id] = session

    proposed = atoms.positions.copy()
    proposed[0] += [0.5, 0.5, 0.5]
    proposed[1] += [1.0, 1.0, 1.0]
    proposed[2] += [1.0, 1.0, 1.0]

    data = asyncio.run(apply_positions(session.session_id, {
        "positions": proposed.tolist(),
        "apply_constraint": False,
    }))

    assert np.allclose(data["positions"], proposed)


def test_constraint_editor_endpoint_sets_and_clears_selected_constraints():
    atoms = molecule("H2O")
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=1.4, k=5.0),
    ])
    session = EditorSession("constraint-editor", atoms.copy(), atoms.copy())
    from v_ase.session import sessions
    sessions[session.session_id] = session

    edited = asyncio.run(update_constraints(session.session_id, {
        "indices": [1, 2],
        "fix_atoms": True,
        "directional_kind": "fixed_plane",
        "vector": [0, 1, 0],
    }))

    assert sorted(edited["constraints"]["fixed_indices"]) == [0, 1, 2]
    assert "1" not in edited["constraints"]["fixed_line"]
    assert edited["constraints"]["fixed_plane"]["1"] == [0.0, 1.0, 0.0]
    assert edited["constraints"]["fixed_plane"]["2"] == [0.0, 1.0, 0.0]
    assert edited["constraints"]["hookean"][0]["indices"] == [1, 2]

    cleared = asyncio.run(update_constraints(session.session_id, {
        "indices": [1, 2],
        "fix_atoms": False,
        "directional_kind": "none",
    }))

    assert cleared["constraints"]["fixed_indices"] == [0]
    assert cleared["constraints"]["fixed_line"] == {}
    assert cleared["constraints"]["fixed_plane"] == {}
    assert cleared["constraints"]["hookean"][0]["indices"] == [1, 2]


def test_apply_supercell_sets_repeated_structure_as_editable_cell():
    atoms = molecule("H2O")
    atoms.set_cell([5, 6, 7])
    atoms.set_pbc([True, True, True])
    session = EditorSession("set-supercell", atoms.copy(), atoms.copy())
    from v_ase.session import sessions
    sessions[session.session_id] = session

    data = asyncio.run(apply_supercell(session.session_id, {
        "positions": atoms.positions.tolist(),
        "reps": [2, 1, 1],
        "apply_constraint": True,
    }))

    assert data["metadata"]["natoms"] == len(atoms) * 2
    assert np.allclose(data["cell"][0], [10.0, 0.0, 0.0])


def test_blender_export_includes_constraints_and_hookean_spring():
    atoms = molecule("H2O")
    atoms.set_constraint([
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=1.4, k=5.0),
    ])
    session = EditorSession("blender-export", atoms.copy(), atoms.copy())

    response = export_blender_response(session, {
        "positions": atoms.positions.tolist(),
        "camera": {
            "position": [4.0, -5.0, 6.0],
            "target": [0.0, 0.0, 0.0],
            "up": [0.0, 0.0, 1.0],
            "fov": 38.0,
            "near": 0.05,
            "far": 500.0,
        },
    })
    with open(response.path, "r", encoding="utf-8") as handle:
        script = handle.read()

    assert "bpy.ops.mesh.primitive_uv_sphere_add" in script
    assert "'fixed_line': {'1': [1.0, 0.0, 0.0]}" in script
    assert "'fixed_plane': {'2': [0.0, 0.0, 1.0]}" in script
    assert "add_hookean_spring" in script
    assert "hookean_state" in script
    assert "threshold_y = left_center + threshold" in script
    assert "_inactive_gap" in script
    assert "_dead_zone_rail" in script
    assert "_cutoff_gate" in script
    assert "_lock_pin" in script
    assert "'indices': [1, 2]" in script
    assert "CAMERA = DATA.get(\"camera\", {})" in script
    assert "'position': [4.0, -5.0, 6.0]" in script
    assert "add_scene_camera()" in script
    assert "look_at_camera(obj, target)" in script


def test_blender_export_includes_trajectory_keyframes_when_frames_match():
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.25, 0.0, 0.0]
    session = EditorSession(
        "blender-trajectory-export",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )

    response = export_blender_response(session, {"positions": first.positions.tolist()})
    with open(response.path, "r", encoding="utf-8") as handle:
        script = handle.read()

    assert "'frames':" in script
    assert "FRAMES = DATA.get(\"frames\", [])" in script
    assert "keyframe_insert(data_path=\"location\"" in script
    assert "bpy.context.scene.frame_end = len(FRAMES)" in script
