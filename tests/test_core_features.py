import asyncio
import json
import os
import pickle
from pathlib import Path
import time

import numpy as np
import pytest
from ase import Atoms
from ase.data import atomic_numbers, covalent_radii
from ase.data.colors import jmol_colors
from ase.io import write
from ase.build import molecule
from ase.calculators.emt import EMT
from ase.calculators.singlepoint import SinglePointCalculator
from fastapi import HTTPException

import v_ase.relax as relax_module
from v_ase.export import export_pickle_response, export_poscar_response
from v_ase.relax import start_relaxation, stop_relaxation
from v_ase import DefaultRepulsionCalculator as RootDefaultRepulsionCalculator
from v_ase import RepulsionCalculator as RootRepulsionCalculator
from v_ase.calculator import RepulsionCalculator as SingularRepulsionCalculator
from v_ase.calculators import Conditioner, DefaultRepulsionCalculator, RepulsionCalculator
from v_ase.repulsion import RepulsionCalculator as ImplementationRepulsionCalculator
from v_ase.repulsion import is_vase_repulsion_calculator
from v_ase.project import read_project_archive
from v_ase.serialization import atoms_to_json
from v_ase.server import (
    apply_positions,
    apply_supercell,
    apply_supercell_matrix,
    cancel_session_autoclose,
    delete_atoms,
    get_atoms,
    load_visual_settings,
    load_project,
    reset,
    reset_coordinates,
    save_visual_settings,
    save_project,
    schedule_session_autoclose,
    set_frame,
    undo,
    update_calculator,
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


def test_default_repulsion_calculator_is_attached_when_missing():
    atoms = molecule("H2O")
    session = make_session(atoms)

    data = asyncio.run(get_atoms(session.session_id))

    assert is_vase_repulsion_calculator(session.working_atoms.calc)
    assert data["metadata"]["calculator"] == "Repulsion"
    assert data["metadata"]["has_calculator"] is True
    assert data["metadata"]["calculator_details"]["is_default_repulsion"] is True
    assert np.asarray(data["forces"]).shape == (len(atoms), 3)


def test_repulsion_calculator_public_api_imports():
    atoms = Atoms("HH", positions=[[0, 0, 0], [0.25, 0, 0]])
    atoms.calc = RepulsionCalculator(device="cpu", cpu_threads=1)

    assert Conditioner is RepulsionCalculator
    assert DefaultRepulsionCalculator is RepulsionCalculator
    assert RootRepulsionCalculator is RepulsionCalculator
    assert RootDefaultRepulsionCalculator is RepulsionCalculator
    assert SingularRepulsionCalculator is RepulsionCalculator
    assert ImplementationRepulsionCalculator is RepulsionCalculator
    assert atoms.get_potential_energy() > 0
    assert np.asarray(atoms.get_forces()).shape == (2, 3)


def test_existing_singlepoint_calculator_is_not_replaced():
    atoms = molecule("H2O")
    atoms.calc = SinglePointCalculator(
        atoms,
        energy=-1.23,
        forces=np.zeros((len(atoms), 3)),
    )
    original = atoms.copy()
    original.calc = atoms.calc
    working = atoms.copy()
    working.calc = atoms.calc
    session = EditorSession("singlepoint-calc", original, working)
    sessions[session.session_id] = session

    data = asyncio.run(get_atoms(session.session_id))

    assert not is_vase_repulsion_calculator(session.working_atoms.calc)
    assert data["metadata"]["calculator"] == "SinglePointCalculator"
    assert data["metadata"]["calculator_details"]["is_default_repulsion"] is False


def test_default_repulsion_calculator_device_settings_are_configurable():
    atoms = Atoms("HH", positions=[[0, 0, 0], [0.25, 0, 0]])
    session = make_session(atoms)

    data = asyncio.run(update_calculator(session.session_id, {
        "device": "cpu",
        "cpu_threads": 2,
    }))

    details = data["metadata"]["calculator_details"]
    assert details["is_default_repulsion"] is True
    assert details["requested_device"] == "cpu"
    assert details["cpu_threads"] == 2
    assert 1 in details["cpu_thread_options"]


def test_relaxation_starts_with_default_repulsion_calculator(monkeypatch):
    atoms = Atoms("HH", positions=[[0, 0, 0], [0.25, 0, 0]])
    session = make_session(atoms)
    messages = []
    monkeypatch.setattr(
        relax_module.ws_manager,
        "broadcast_sync",
        lambda message, session_id: messages.append((message, session_id)),
    )

    response = asyncio.run(start_relaxation(session, {"steps": 0}, None))

    assert response["status"] == "started"
    for _ in range(50):
        if not session.is_relaxing:
            break
        time.sleep(0.01)
    finished = [message for message, sid in messages if sid == session.session_id and message["type"] == "relax_finished"]
    assert finished
    assert finished[-1]["status"] == "converged"
    assert len(finished[-1]["positions"]) == len(atoms)
    asyncio.run(stop_relaxation(session))


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


def test_visual_settings_save_and_load_json_roundtrip_and_legacy_pickle():
    atoms = molecule("H2O")
    session = make_session(atoms)
    settings = {
        "schema": "v_ase.visual_settings.v1",
        "display": {
            "showBonds": True,
            "bondMode": "element",
            "elementBondCutoffs": {"H-O": 1.35},
            "bondStyle": "flat",
            "bondThickness": 0.24,
            "bondColorMode": "custom",
            "bondCustomColor": "#18a7d8",
            "atomRadiusScale": 1.4,
            "elementRadii": {"O": 0.72},
            "supercell": [1, 1, 1],
        },
        "applyConstraints": False,
        "sphereQuality": "high",
    }

    response = asyncio.run(save_visual_settings(session.session_id, {"settings": settings}))
    payload = json.loads(response.body)
    assert payload["schema"] == "v_ase.visual_settings.v2"
    assert payload["settings"]["display"]["elementBondCutoffs"]["H-O"] == 1.35
    assert payload["settings"]["display"]["bondStyle"] == "flat"
    assert payload["settings"]["display"]["bondThickness"] == 0.24
    assert payload["settings"]["display"]["bondCustomColor"] == "#18a7d8"

    loaded = asyncio.run(load_visual_settings(session.session_id, BytesRequest(response.body)))
    assert loaded["settings"]["display"]["atomRadiusScale"] == 1.4
    assert loaded["settings"]["display"]["bondColorMode"] == "custom"
    assert loaded["settings"]["sphereQuality"] == "high"

    legacy = pickle.dumps({"schema": "v_ase.visual_settings.v1", "settings": settings})
    legacy_loaded = asyncio.run(load_visual_settings(session.session_id, BytesRequest(legacy)))
    assert legacy_loaded["settings"]["display"]["bondThickness"] == 0.24

    executable_pickle = pickle.dumps(os.system)
    with pytest.raises(HTTPException, match="global objects are not allowed"):
        asyncio.run(load_visual_settings(session.session_id, BytesRequest(executable_pickle)))


def test_vase_project_rejects_invalid_archives(tmp_path):
    invalid = tmp_path / "invalid.vase"
    invalid.write_bytes(b"not a project archive")
    with pytest.raises(ValueError, match="Invalid .vase project archive"):
        read_project_archive(invalid)


def test_vase_project_roundtrip_restores_trajectory_edits_constraints_and_settings():
    from ase.constraints import FixedPlane
    from v_ase.io import atom_type_labels, set_atom_type_labels

    first = molecule("H2O")
    first.set_cell([8, 8, 8])
    first.set_pbc(True)
    first.set_constraint(FixedPlane(0, (0, 0, 1)))
    set_atom_type_labels(first, ["O_surface", "H_a", "H_b"])
    first.set_array("site_class", np.array([4, 5, 6], dtype=np.int16))
    first.info["workflow"] = {"stage": "adsorption", "converged": False}
    first.calc = SinglePointCalculator(first, energy=-1.25, forces=np.zeros((3, 3)))
    second = first.copy()
    second.positions += [0.25, 0.5, 0.0]
    second.calc = SinglePointCalculator(second, energy=-1.5, forces=np.full((3, 3), 0.2))
    session = EditorSession(
        "project-roundtrip",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={"viz_only": False},
    )
    session.trajectory_frames[0].calc = SinglePointCalculator(
        session.trajectory_frames[0], energy=-1.25, forces=np.zeros((3, 3))
    )
    session.trajectory_frames[1].calc = SinglePointCalculator(
        session.trajectory_frames[1], energy=-1.5, forces=np.full((3, 3), 0.2)
    )
    session.working_atoms = session.trajectory_frames[1].copy()
    session.working_atoms.calc = SinglePointCalculator(
        session.working_atoms, energy=-1.5, forces=np.full((3, 3), 0.2)
    )
    sessions[session.session_id] = session
    settings = {
        "schema": "v_ase.visual_settings.v1",
        "display": {
            "showBonds": True,
            "bondMode": "element",
            "elementBondCutoffs": {"H_a-O_surface": 1.4},
            "sphereQuality": "ultra",
            "sunIntensity": 3.75,
            "sunPosition": [11, -7, 16],
            "sunTarget": [1, 2, 3],
            "supercell": [2, 1, 1],
        },
    }

    response = asyncio.run(save_project(session.session_id, {
        "positions": second.positions.tolist(),
        "settings": settings,
        "apply_constraint": True,
    }))
    archive = Path(response.path)
    assert archive.suffix == ".vase" and archive.stat().st_size > 500

    target = make_session(molecule("CH4"))
    loaded = asyncio.run(load_project(target.session_id, BytesRequest(archive.read_bytes())))
    assert loaded["metadata"]["frame_count"] == 2
    assert loaded["metadata"]["current_frame"] == 1
    assert atom_type_labels(target.working_atoms) == ["O_surface", "H_a", "H_b"]
    assert target.working_atoms.constraints
    np.testing.assert_allclose(target.working_atoms.positions, second.positions)
    np.testing.assert_array_equal(target.working_atoms.arrays["site_class"], [4, 5, 6])
    assert target.working_atoms.info["workflow"]["stage"] == "adsorption"
    assert target.working_atoms.get_potential_energy() == pytest.approx(-1.5)
    np.testing.assert_allclose(target.working_atoms.get_forces(apply_constraint=False), 0.2)
    assert loaded["project"]["settings"]["display"]["sunIntensity"] == 3.75
    assert loaded["project"]["settings"]["display"]["supercell"] == [2, 1, 1]
    asyncio.run(response.background())


def test_vase_project_captures_client_side_viz_only_coordinates():
    atoms = molecule("H2O")
    atoms.set_cell([6, 6, 6])
    atoms.set_pbc(True)
    session = EditorSession(
        "project-viz-only-coordinates",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    displayed_positions = atoms.positions.copy()
    displayed_positions[0] += [3.0, 1.0, 0.5]

    response = asyncio.run(save_project(session.session_id, {
        "positions": displayed_positions.tolist(),
        "settings": {"display": {"supercell": [2, 2, 1]}},
        "apply_constraint": False,
    }))
    archive = Path(response.path)
    project = read_project_archive(archive)
    np.testing.assert_allclose(project.frames[0].positions, displayed_positions)
    assert project.settings["display"]["supercell"] == [2, 2, 1]
    asyncio.run(response.background())


def test_vase_project_restores_builtin_repulsion_calculator_configuration():
    atoms = molecule("H2")
    atoms.calc = RepulsionCalculator(
        min_bondinfo=1.1,
        k_repulsion=2.75,
        max_force_norm=4.5,
        mic=False,
        device="cpu",
        cpu_threads=2,
        backend="numpy",
    )
    session = EditorSession(
        "project-repulsion-calculator",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": False},
    )
    session.original_atoms.calc = atoms.calc
    session.working_atoms.calc = atoms.calc
    session.trajectory_frames[0].calc = atoms.calc
    sessions[session.session_id] = session

    response = asyncio.run(save_project(session.session_id, {
        "positions": atoms.positions.tolist(),
        "settings": {"display": {}},
        "apply_constraint": True,
    }))
    project = read_project_archive(response.path)
    restored = project.frames[0].calc
    assert is_vase_repulsion_calculator(restored)
    assert restored.min_bondinfo == pytest.approx(1.1)
    assert restored.k_repulsion == pytest.approx(2.75)
    assert restored.max_force_norm == pytest.approx(4.5)
    assert restored.mic is False
    assert restored.cpu_threads == 2
    assert restored.backend == "numpy"
    assert np.isfinite(project.frames[0].get_potential_energy())
    asyncio.run(response.background())


def test_blocking_cli_session_finalizes_after_browser_disconnect_grace():
    atoms = molecule("H2")
    session = EditorSession(
        "browser-close-autoclose",
        atoms.copy(),
        atoms.copy(),
        config={"auto_close_on_disconnect": True},
    )
    sessions[session.session_id] = session
    try:
        schedule_session_autoclose(session.session_id, delay=0.01)
        assert session.done_event.wait(timeout=1.0)
        assert session.result_atoms is not None
        np.testing.assert_allclose(session.result_atoms.positions, atoms.positions)
    finally:
        cancel_session_autoclose(session.session_id)
        sessions.pop(session.session_id, None)


def test_blocking_cli_session_autoclose_can_be_cancelled_on_reconnect():
    atoms = molecule("H2")
    session = EditorSession(
        "browser-close-reconnect",
        atoms.copy(),
        atoms.copy(),
        config={"auto_close_on_disconnect": True},
    )
    sessions[session.session_id] = session
    try:
        schedule_session_autoclose(session.session_id, delay=0.05)
        cancel_session_autoclose(session.session_id)
        time.sleep(0.08)
        assert not session.done_event.is_set()
        assert session.result_atoms is None
    finally:
        cancel_session_autoclose(session.session_id)
        sessions.pop(session.session_id, None)


def test_trajectory_file_input(tmp_path):
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.5, 0.0, 0.0]
    path = tmp_path / "frames.extxyz"
    write(path, [first, second])

    frames = normalize_atoms_input(path)

    assert len(frames) == 2
    assert np.allclose(frames[1].positions, second.positions)
