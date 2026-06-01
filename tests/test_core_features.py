import asyncio
import os
import pickle

import numpy as np
import pytest
from ase import Atoms
from ase.data import atomic_numbers, covalent_radii
from ase.data.colors import jmol_colors
from ase.io import write
from ase.build import molecule
from ase.calculators.emt import EMT
from fastapi import HTTPException

from v_ase.export import export_pickle_response, export_poscar_response
from v_ase.relax import start_relaxation
from v_ase.serialization import atoms_to_json
from v_ase.server import (
    apply_positions,
    apply_supercell,
    apply_supercell_matrix,
    delete_atoms,
    get_atoms,
    load_visual_settings,
    reset,
    reset_coordinates,
    save_visual_settings,
    set_frame,
    undo,
    wrap,
)
from v_ase.session import EditorSession, sessions
from v_ase.viewer import normalize_atoms_input

ASE_GUI_RADIUS_SCALE = 0.89


def make_session(atoms):
    session = EditorSession("feature-test", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session
    return session


class BytesRequest:
    def __init__(self, data):
        self.data = data

    async def body(self):
        return self.data


def ase_gui_jmol_hex(symbol):
    rgb = jmol_colors[atomic_numbers[symbol]]
    return "#{:02X}{:02X}{:02X}".format(*[int(float(v) * 255) for v in rgb])


def test_atoms_serialization_uses_ase_visual_data_and_hover_metadata():
    atoms = Atoms(
        symbols=["O", "H", "C"],
        positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        cell=[6, 6, 6],
        pbc=True,
    )
    atoms.set_tags([7, 8, 9])
    atoms.set_initial_charges([-0.2, 0.1, 0.0])
    atoms.set_initial_magnetic_moments([0.0, 1.0, 2.0])
    atoms.arrays["forces"] = np.array([[0.1, 0.2, 0.3], [0.0, 0.0, 0.1], [0.2, 0.0, 0.0]])

    data = atoms_to_json(atoms)

    assert data["visual"]["color_source"] == "ase.gui.view.View.colors using ase.data.colors.jmol_colors"
    assert data["visual"]["radius_source"] == "ase.gui.images.Images.get_radii: ase.data.covalent_radii * 0.89"
    assert data["visual"]["radius_scale"] == ASE_GUI_RADIUS_SCALE
    assert data["visual"]["colors"] == [ase_gui_jmol_hex(symbol) for symbol in ["O", "H", "C"]]
    assert data["visual"]["radii"] == [
        float(covalent_radii[atomic_numbers[symbol]] * ASE_GUI_RADIUS_SCALE)
        for symbol in ["O", "H", "C"]
    ]
    assert data["visual"]["covalent_radii"] == data["visual"]["radii"]
    assert data["tags"] == [7, 8, 9]
    assert data["charges"] == [-0.2, 0.1, 0.0]
    assert data["magmoms"] == [0.0, 1.0, 2.0]
    assert np.allclose(data["forces"], atoms.arrays["forces"])


def test_apply_reset_undo_and_wrap_endpoints():
    atoms = molecule("H2O")
    atoms.set_cell([4, 4, 4])
    atoms.set_pbc([True, True, True])
    session = make_session(atoms)

    proposed = atoms.positions.copy()
    proposed[1] += [1.0, 0.0, 0.0]

    applied = asyncio.run(apply_positions(session.session_id, {"positions": proposed.tolist()}))
    assert np.isclose(applied["positions"][1][0], proposed[1][0])

    undone = asyncio.run(undo(session.session_id))
    assert np.allclose(undone["positions"], atoms.positions)

    wrapped = asyncio.run(wrap(session.session_id, {"positions": (atoms.positions + 10.0).tolist()}))
    assert np.all(np.array(wrapped["positions"]) >= -1e-9)
    assert np.all(np.array(wrapped["positions"]) <= 4.0 + 1e-9)

    reset_data = asyncio.run(reset(session.session_id))
    assert np.allclose(reset_data["positions"], atoms.positions)


def test_delete_endpoint_removes_atoms_and_remaps_supported_constraints():
    from ase import Atoms
    from ase.constraints import FixAtoms, FixedLine, FixedPlane, Hookean

    atoms = Atoms(
        symbols=["O", "H", "H", "C"],
        positions=[[0, 0, 0], [1, 0, 0], [3, 0, 0], [4, 0, 0]],
        cell=[8, 8, 8],
        pbc=True,
    )
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(1, [1, 0, 0]),
        FixedPlane(2, [0, 0, 1]),
        Hookean(1, 2, rt=1.5, k=5.0),
    ])
    session = make_session(atoms)

    data = asyncio.run(delete_atoms(session.session_id, {"indices": [0, 3]}))

    assert data["symbols"] == ["H", "H"]
    assert data["constraints"]["fixed_indices"] == []
    assert data["constraints"]["fixed_line"]["0"] == [1.0, 0.0, 0.0]
    assert data["constraints"]["fixed_plane"]["1"] == [0.0, 0.0, 1.0]
    assert data["constraints"]["hookean"][0]["indices"] == [0, 1]


def test_export_poscar_and_pickle_without_calculator():
    atoms = molecule("H2O")
    atoms.calc = EMT()
    session = make_session(atoms)
    session.working_atoms.calc = atoms.calc

    poscar = export_poscar_response(session, {"positions": atoms.positions.tolist()})
    assert os.path.exists(poscar.path)
    with open(poscar.path, "r", encoding="utf-8") as handle:
        text = handle.read()
    assert "O" in text and "H" in text

    pkl = export_pickle_response(session, {"include_calculator": False})
    assert os.path.exists(pkl.path)
    with open(pkl.path, "rb") as handle:
        loaded = pickle.load(handle)
    assert loaded.calc is None
    assert len(loaded) == len(atoms)


def test_relax_requires_calculator():
    atoms = molecule("H2O")
    session = make_session(atoms)

    class BackgroundTasks:
        def add_task(self, *args, **kwargs):
            raise AssertionError("Relaxation should not start without a calculator")

    response = asyncio.run(start_relaxation(session, {}, BackgroundTasks()))
    assert response["status"] == "error"


def test_atoms_endpoint_includes_view_config():
    atoms = molecule("H2O")
    session = make_session(atoms)
    session.config.update({"show_cell": False, "show_axes": False, "show_bonds": True})

    data = asyncio.run(get_atoms(session.session_id))

    assert data["metadata"]["config"]["show_cell"] is False
    assert data["metadata"]["config"]["show_axes"] is False
    assert data["metadata"]["config"]["show_bonds"] is True


def test_trajectory_frame_switching():
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [1.0, 2.0, 3.0]
    frames = normalize_atoms_input([first, second])
    session = EditorSession("trajectory-test", frames[0].copy(), frames[0].copy(), original_frames=frames, trajectory_frames=[f.copy() for f in frames])
    sessions[session.session_id] = session

    data = asyncio.run(get_atoms(session.session_id))
    assert data["metadata"]["frame_count"] == 2
    assert data["metadata"]["current_frame"] == 0

    data = asyncio.run(set_frame(session.session_id, {"index": 1}))
    assert data["metadata"]["current_frame"] == 1
    assert np.allclose(data["positions"], second.positions)


def test_trajectory_supercell_and_wrap_apply_to_all_frames():
    first = Atoms("NaCl", positions=[[0.2, 0.2, 0.2], [1.8, 1.8, 1.8]], cell=[2, 2, 2], pbc=True)
    second = Atoms("NaCl", positions=[[2.3, -0.2, 0.2], [1.7, 2.4, 1.8]], cell=[2, 2, 2], pbc=True)
    frames = [first.copy(), second.copy()]
    session = EditorSession(
        "trajectory-all-frame-edit",
        frames[0].copy(),
        frames[0].copy(),
        original_frames=[f.copy() for f in frames],
        trajectory_frames=[f.copy() for f in frames],
    )
    sessions[session.session_id] = session

    wrapped = asyncio.run(wrap(session.session_id, {"positions": first.positions.tolist()}))
    assert wrapped["metadata"]["frame_count"] == 2
    for frame in session.trajectory_frames:
        positions = frame.get_positions()
        assert np.all(positions >= -1e-9)
        assert np.all(positions <= 2.0 + 1e-9)

    supercell = asyncio.run(apply_supercell(session.session_id, {
        "positions": session.working_atoms.positions.tolist(),
        "reps": [2, 1, 1],
        "apply_constraint": True,
    }))
    assert supercell["metadata"]["natoms"] == 4
    assert np.allclose(supercell["cell"][0], [4.0, 0.0, 0.0])
    assert [len(frame) for frame in session.trajectory_frames] == [4, 4]
    assert all(np.allclose(frame.cell[0], [4.0, 0.0, 0.0]) for frame in session.trajectory_frames)

    frame_2 = asyncio.run(set_frame(session.session_id, {"index": 1}))
    assert frame_2["metadata"]["natoms"] == 4
    assert np.allclose(frame_2["cell"][0], [4.0, 0.0, 0.0])

    reset_data = asyncio.run(reset_coordinates(session.session_id))
    assert reset_data["metadata"]["natoms"] == 2
    assert np.allclose(reset_data["cell"][0], [2.0, 0.0, 0.0])
    assert [len(frame) for frame in session.trajectory_frames] == [2, 2]
    assert all(np.allclose(frame.cell[0], [2.0, 0.0, 0.0]) for frame in session.trajectory_frames)


def test_make_supercell_matrix_applies_to_all_frames_and_preserves_constraints():
    from ase.constraints import FixAtoms, FixedLine

    first = Atoms("NaCl", positions=[[0.2, 0.2, 0.2], [1.2, 1.2, 1.2]], cell=[2, 2, 8], pbc=[True, True, False])
    second = first.copy()
    second.positions += [0.1, 0.0, 0.0]
    first.set_constraint([FixAtoms(indices=[0]), FixedLine(1, [1, 0, 0])])
    second.set_constraint([FixAtoms(indices=[0]), FixedLine(1, [1, 0, 0])])
    session = EditorSession(
        "matrix-supercell-all-frame-edit",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session

    data = asyncio.run(apply_supercell_matrix(session.session_id, {
        "positions": first.positions.tolist(),
        "matrix": [[2, 1, 0], [0, 1, 0], [0, 0, 1]],
        "apply_constraint": True,
    }))

    assert data["metadata"]["natoms"] == 4
    assert np.allclose(data["cell"], [[4.0, 2.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 8.0]])
    assert [len(frame) for frame in session.trajectory_frames] == [4, 4]
    assert sorted(data["constraints"]["fixed_indices"]) == [0, 2]
    assert data["constraints"]["fixed_line"]["1"] == [1.0, 0.0, 0.0]
    assert data["constraints"]["fixed_line"]["3"] == [1.0, 0.0, 0.0]

    frame_2 = asyncio.run(set_frame(session.session_id, {"index": 1}))
    assert frame_2["metadata"]["natoms"] == 4
    assert np.allclose(frame_2["cell"], [[4.0, 2.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 8.0]])


def test_make_supercell_matrix_rejects_nonperiodic_axis_tilt():
    atoms = Atoms("NaCl", positions=[[0.2, 0.2, 0.2], [1.2, 1.2, 1.2]], cell=[2, 2, 8], pbc=[True, True, False])
    session = make_session(atoms)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(apply_supercell_matrix(session.session_id, {
            "positions": atoms.positions.tolist(),
            "matrix": [[1, 0, 0], [0, 1, 0], [1, 0, 1]],
            "apply_constraint": True,
        }))

    assert excinfo.value.status_code == 400
    assert "non-periodic axis 3" in excinfo.value.detail


def test_visual_settings_save_and_load_pickle_roundtrip():
    atoms = molecule("H2O")
    session = make_session(atoms)
    settings = {
        "schema": "v_ase.visual_settings.v1",
        "display": {
            "showBonds": True,
            "bondMode": "element",
            "elementBondCutoffs": {"H-O": 1.35},
            "atomRadiusScale": 1.4,
            "elementRadii": {"O": 0.72},
            "supercell": [1, 1, 1],
        },
        "applyConstraints": False,
        "sphereQuality": "high",
    }

    response = asyncio.run(save_visual_settings(session.session_id, {"settings": settings}))
    payload = pickle.loads(response.body)
    assert payload["schema"] == "v_ase.visual_settings.v1"
    assert payload["settings"]["display"]["elementBondCutoffs"]["H-O"] == 1.35

    loaded = asyncio.run(load_visual_settings(session.session_id, BytesRequest(response.body)))
    assert loaded["settings"]["display"]["atomRadiusScale"] == 1.4
    assert loaded["settings"]["sphereQuality"] == "high"


def test_trajectory_file_input(tmp_path):
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.5, 0.0, 0.0]
    path = tmp_path / "frames.extxyz"
    write(path, [first, second])

    frames = normalize_atoms_input(path)

    assert len(frames) == 2
    assert np.allclose(frames[1].positions, second.positions)
