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
from ase.constraints import FixedPlane
from fastapi import HTTPException

import v_ase.relax as relax_module
from v_ase.export import export_pickle_response, export_poscar_response
from v_ase.relax import exit_relaxation, start_relaxation, stop_relaxation
from v_ase import DefaultRepulsionCalculator as RootDefaultRepulsionCalculator
from v_ase import RepulsionCalculator as RootRepulsionCalculator
from v_ase.calculator import RepulsionCalculator as SingularRepulsionCalculator
from v_ase.calculators import Conditioner, DefaultRepulsionCalculator, RepulsionCalculator
from v_ase.repulsion import RepulsionCalculator as ImplementationRepulsionCalculator
from v_ase.repulsion import is_vase_repulsion_calculator
from v_ase.io import atom_labels, set_atom_labels
from v_ase.project import read_project_archive
from v_ase.serialization import atoms_to_json
from v_ase.server import (
    add_atoms,
    append_structure_path,
    append_structure_file,
    apply_positions,
    apply_supercell,
    apply_supercell_matrix,
    apply_translation,
    browse_launch_directory,
    cancel_session_autoclose,
    calculate_displacements,
    delete_atoms,
    get_atoms,
    ai_control_schema,
    ai_semantic_state,
    load_structure_path,
    load_structure_file,
    load_visual_settings,
    load_project,
    reset,
    reset_coordinates,
    save_visual_settings,
    save_project,
    schedule_session_autoclose,
    set_frame,
    set_unit_cell,
    undo,
    update_atom_identity,
    update_calculator,
    update_constraints,
    update_session_mode,
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


class StreamRequest:
    def __init__(self, data):
        self.data = data
        self.headers = {"content-length": str(len(data))}

    async def stream(self):
        midpoint = max(1, len(self.data) // 2)
        yield self.data[:midpoint]
        yield self.data[midpoint:]


def test_append_file_preserves_working_frame_and_registers_new_trajectory_labels(tmp_path):
    first = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=[8, 8, 8], pbc=True)
    second = first.copy()
    second.positions[0, 0] = 0.5
    session = EditorSession(
        "append-trajectory",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), first.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={
            "viz_only": True,
            "empty_workspace": False,
            "document_name": "existing.extxyz",
            "initial_design_settings": {"display": {"atomRadiusScale": 1.4}},
        },
    )
    sessions[session.session_id] = session

    carbon = Atoms("C", positions=[[1.0, 0.0, 0.0]], cell=[9, 9, 9], pbc=True)
    oxygen = Atoms("OO", positions=[[0, 0, 0], [1.2, 0, 0]], cell=[9, 9, 9], pbc=True)
    set_atom_labels(carbon, ["C_bulk"])
    set_atom_labels(oxygen, ["O_ads", "O_bridge"])
    source = tmp_path / "added.extxyz"
    write(source, [carbon, oxygen], format="extxyz")

    try:
        data = asyncio.run(
            append_structure_file(
                session.session_id,
                StreamRequest(source.read_bytes()),
                filename=source.name,
                input_format="extxyz",
                index=":",
            )
        )
        assert data["loaded_file"]["kind"] == "append"
        assert data["loaded_file"]["appended_frames"] == 2
        assert data["metadata"]["frame_count"] == 4
        assert data["metadata"]["current_frame"] == 1
        assert session.working_atoms.positions[0, 0] == pytest.approx(0.5)
        assert session.config["document_name"] == "existing.extxyz"
        assert session.config["initial_design_settings"]["display"]["atomRadiusScale"] == pytest.approx(1.4)
        identity = session.config["trajectory_identity"]
        assert identity["labels"] == ["H", "C_bulk", "O_ads", "O_bridge"]
        assert identity["elements"] == {
            "H": ["H"],
            "C_bulk": ["C"],
            "O_ads": ["O"],
            "O_bridge": ["O"],
        }

        asyncio.run(set_frame(session.session_id, {"index": 3}))
        assert atom_labels(session.working_atoms) == ["O_ads", "O_bridge"]
    finally:
        sessions.pop(session.session_id, None)


def test_append_vase_imports_frames_without_replacing_current_visual_settings(tmp_path):
    project_atoms = Atoms("He", positions=[[2.0, 0.0, 0.0]])
    project_last = project_atoms.copy()
    project_last.positions[0, 0] = 3.0
    project_session = EditorSession(
        "append-project-source",
        project_atoms.copy(),
        project_last.copy(),
        original_frames=[project_atoms.copy(), project_atoms.copy()],
        trajectory_frames=[project_atoms.copy(), project_last.copy()],
        current_frame=1,
        config={"viz_only": True},
    )
    target_atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]])
    target_settings = {"display": {"atomRadiusScale": 1.75, "showBonds": True}}
    target = EditorSession(
        "append-project-target",
        target_atoms.copy(),
        target_atoms.copy(),
        config={
            "viz_only": True,
            "empty_workspace": False,
            "initial_design_settings": target_settings,
            "document_name": "target.xyz",
        },
    )
    sessions[project_session.session_id] = project_session
    sessions[target.session_id] = target
    response = asyncio.run(
        save_project(
            project_session.session_id,
            {
                "positions": project_last.positions.tolist(),
                "settings": {"display": {"atomRadiusScale": 3.0}},
            },
        )
    )
    archive = Path(response.path)

    try:
        data = asyncio.run(
            append_structure_file(
                target.session_id,
                StreamRequest(archive.read_bytes()),
                filename="source.vase",
                input_format="vase",
                index="-1",
            )
        )
        assert data["loaded_file"]["project_settings_ignored"] is True
        assert data["loaded_file"]["appended_frames"] == 1
        assert target.frame_count == 2
        assert target.config["initial_design_settings"] == target_settings
        assert target.config["document_name"] == "target.xyz"
        assert target.config["trajectory_identity"]["labels"] == ["H", "He"]
        asyncio.run(set_frame(target.session_id, {"index": 1}))
        assert target.working_atoms.positions[0, 0] == pytest.approx(3.0)
    finally:
        sessions.pop(project_session.session_id, None)
        sessions.pop(target.session_id, None)
        archive.unlink(missing_ok=True)


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


def test_add_endpoint_appends_every_requested_atom_and_label():
    session = make_session(Atoms("C", positions=[[0.0, 0.0, 0.0]]))

    payload = asyncio.run(
        add_atoms(
            session.session_id,
            {
                "symbols": ["O_bridge", "H_water"],
                "base_symbols": ["O", "H"],
                "positions": [[1.2, 0.0, 0.0], [1.8, 0.6, 0.0]],
            },
        )
    )

    assert payload["metadata"]["natoms"] == 3
    assert session.working_atoms.get_chemical_symbols() == ["C", "O", "H"]
    assert atom_labels(session.working_atoms) == ["C", "O_bridge", "H_water"]
    np.testing.assert_allclose(
        session.working_atoms.positions,
        [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [1.8, 0.6, 0.0]],
    )


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


def test_pickle_export_preserves_ase_data_and_valid_single_point_results_only():
    atoms = molecule("H2O")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc(True)
    atoms.set_constraint(FixedPlane(0, (0, 0, 1)))
    set_atom_labels(atoms, ["O_surface", "H_a", "H_b"])
    atoms.set_array("site_class", np.array([4, 5, 6], dtype=np.int16))
    atoms.calc = SinglePointCalculator(atoms, energy=-1.75, forces=np.full((3, 3), 0.25))
    session = make_session(atoms)
    session.working_atoms = atoms

    response = export_pickle_response(session, {"positions": atoms.positions.tolist()})
    with open(response.path, "rb") as handle:
        loaded = pickle.load(handle)

    assert atom_labels(loaded) == ["O_surface", "H_a", "H_b"]
    np.testing.assert_array_equal(loaded.arrays["site_class"], [4, 5, 6])
    assert isinstance(loaded.calc, SinglePointCalculator)
    assert loaded.get_potential_energy() == pytest.approx(-1.75)
    np.testing.assert_allclose(loaded.get_forces(apply_constraint=False), 0.25)
    assert isinstance(loaded.constraints[0], FixedPlane)


def test_pickle_export_drops_stale_single_point_results_after_coordinate_edit():
    atoms = molecule("H2")
    atoms.calc = SinglePointCalculator(atoms, energy=-0.5, forces=np.zeros((2, 3)))
    session = make_session(atoms)
    session.working_atoms = atoms
    moved = atoms.positions.copy()
    moved[1, 0] += 0.2

    response = export_pickle_response(session, {"positions": moved.tolist()})
    with open(response.path, "rb") as handle:
        loaded = pickle.load(handle)

    assert loaded.calc is None
    np.testing.assert_allclose(loaded.positions, moved)


def test_browser_file_load_replaces_empty_workspace_with_all_trajectory_frames(tmp_path):
    first = molecule("H2O")
    second = first.copy()
    second.positions += [0.5, 0.0, 0.0]
    source = tmp_path / "water.extxyz"
    write(source, [first, second], format="extxyz")
    empty = Atoms()
    session = EditorSession(
        "browser-file-load",
        empty.copy(),
        empty.copy(),
        config={"viz_only": True, "empty_workspace": True},
    )
    sessions[session.session_id] = session

    data = asyncio.run(load_structure_file(
        session.session_id,
        StreamRequest(source.read_bytes()),
        filename="water.extxyz",
        input_format=None,
        index=":",
    ))

    assert data["loaded_file"]["filename"] == "water.extxyz"
    assert data["loaded_file"]["kind"] == "trajectory"
    assert data["metadata"]["frame_count"] == 2
    assert data["metadata"]["natoms"] == 3
    assert session.config["empty_workspace"] is False
    np.testing.assert_allclose(session.trajectory_frames[1].positions, second.positions)


def test_browser_file_load_accepts_explicit_format_for_extensionless_input(tmp_path):
    atoms = molecule("NH3")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc(True)
    source = tmp_path / "ABCD"
    write(source, atoms, format="vasp")
    empty = Atoms()
    session = EditorSession(
        "browser-extensionless-load",
        empty.copy(),
        empty.copy(),
        config={"viz_only": True, "empty_workspace": True},
    )
    sessions[session.session_id] = session

    data = asyncio.run(load_structure_file(
        session.session_id,
        StreamRequest(source.read_bytes()),
        filename="ABCD",
        input_format="poscar",
        index="-1",
    ))

    assert data["loaded_file"]["format"] == "vasp"
    assert session.working_atoms.get_chemical_formula() == "H3N"


def test_launch_directory_browser_loads_and_appends_without_path_escape(tmp_path):
    launch_root = tmp_path / "launch"
    launch_root.mkdir()
    nested = launch_root / "structures"
    nested.mkdir()
    source = nested / "water.extxyz"
    write(source, molecule("H2O"), format="extxyz")
    second = nested / "water_2.extxyz"
    moved = molecule("H2O")
    moved.positions += [0.4, 0.0, 0.0]
    write(second, moved, format="extxyz")
    (nested / "empty.xyz").touch()
    (launch_root / ".hidden.xyz").write_text("0\nhidden\n")
    outside = tmp_path / "outside.extxyz"
    write(outside, molecule("NH3"), format="extxyz")

    empty = Atoms()
    session = EditorSession(
        "launch-directory-load",
        empty.copy(),
        empty.copy(),
        config={
            "viz_only": True,
            "empty_workspace": True,
            "launch_directory": str(launch_root),
        },
    )
    sessions[session.session_id] = session
    try:
        root_listing = asyncio.run(browse_launch_directory(session.session_id))
        assert root_listing["root"] == str(launch_root.resolve())
        assert root_listing["directory"] == ""
        assert root_listing["parent"] is None
        assert [entry["name"] for entry in root_listing["entries"]] == ["structures"]

        nested_listing = asyncio.run(
            browse_launch_directory(session.session_id, "structures")
        )
        assert nested_listing["parent"] == ""
        assert [entry["name"] for entry in nested_listing["entries"]] == [
            "empty.xyz",
            "water.extxyz",
            "water_2.extxyz",
        ]

        loaded = asyncio.run(load_structure_path(
            session.session_id,
            {"path": "structures/water.extxyz", "input_format": "extxyz", "index": ":"},
        ))
        assert loaded["metadata"]["natoms"] == 3
        assert loaded["loaded_file"]["filename"] == "water.extxyz"

        appended = asyncio.run(append_structure_path(
            session.session_id,
            {"path": "structures/water_2.extxyz", "input_format": "extxyz", "index": ":"},
        ))
        assert appended["loaded_file"]["appended_frames"] == 1
        assert appended["metadata"]["frame_count"] == 2

        with pytest.raises(HTTPException) as empty_file:
            asyncio.run(load_structure_path(
                session.session_id,
                {"path": "structures/empty.xyz", "index": ":"},
            ))
        assert empty_file.value.status_code == 400
        assert "empty" in empty_file.value.detail.lower()

        with pytest.raises(HTTPException) as traversal:
            asyncio.run(load_structure_path(
                session.session_id,
                {"path": "../outside.extxyz", "index": ":"},
            ))
        assert traversal.value.status_code == 403

        outside_link = launch_root / "outside-link.extxyz"
        try:
            outside_link.symlink_to(outside)
        except OSError:
            pass
        else:
            with pytest.raises(HTTPException) as symlink_escape:
                asyncio.run(load_structure_path(
                    session.session_id,
                    {"path": outside_link.name, "index": ":"},
                ))
            assert symlink_escape.value.status_code == 403
    finally:
        sessions.pop(session.session_id, None)


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
        "cutoff_scale": 0.7,
        "k_repulsion": 3.5,
    }))

    details = data["metadata"]["calculator_details"]
    assert details["is_default_repulsion"] is True
    assert details["requested_device"] == "cpu"
    assert details["cpu_threads"] == 2
    assert details["cutoff_scale"] == pytest.approx(0.7)
    assert details["k_repulsion"] == pytest.approx(3.5)
    assert 1 in details["cpu_thread_options"]


def test_default_repulsion_cutoff_scale_controls_the_physical_threshold():
    # H-H covalent-radius sum is 0.62 A in ASE. At 0.50 A, the default
    # 0.70 scale is inactive while the legacy 1.0 scale is repulsive.
    atoms = Atoms("HH", positions=[[0, 0, 0], [0.50, 0, 0]])
    atoms.calc = RepulsionCalculator(cutoff_scale=0.7, k_repulsion=2.0)
    assert atoms.get_potential_energy() == pytest.approx(0.0, abs=1e-12)

    atoms.calc = RepulsionCalculator(cutoff_scale=1.0, k_repulsion=2.0)
    assert atoms.get_potential_energy() > 0


def test_ai_semantic_state_and_schema_are_machine_readable():
    atoms = Atoms("BN", positions=[[0, 0, 0], [1.45, 0, 0]], cell=[5, 5, 12], pbc=[True, True, False])
    set_atom_labels(atoms, ["B_site", "N_site"])
    session = make_session(atoms)

    schema = asyncio.run(ai_control_schema())
    state = asyncio.run(ai_semantic_state(session.session_id))

    assert schema["protocol"] == "v_ase.ai.v1"
    assert schema["control_schema"]["properties"]["camera"]["properties"]["axis"]["enum"] == [
        "+X", "-X", "+Y", "-Y", "+Z", "-Z"
    ]
    assert state["ai"]["protocol"] == "v_ase.ai.v1"
    assert state["ai"]["units"]["length"] == "angstrom"
    assert state["ai"]["label_counts"] == {"B_site": 1, "N_site": 1}
    np.testing.assert_allclose(state["positions"], atoms.positions)


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


def test_repulsion_separates_exactly_coincident_atoms_without_a_cell():
    atoms = Atoms("HH", positions=np.zeros((2, 3)))
    atoms.calc = RepulsionCalculator(cutoff_scale=1.0, k_repulsion=2.0)

    forces = atoms.get_forces()

    assert np.linalg.norm(forces[0]) > 0.1
    np.testing.assert_allclose(forces[0], -forces[1], atol=1e-12)


def test_default_relaxation_moves_coincident_scratch_atoms_without_a_cell():
    atoms = Atoms("HH", positions=np.zeros((2, 3)), pbc=False)
    session = EditorSession(
        "scratch-relax-no-cell",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": False, "empty_workspace": False},
    )

    response = asyncio.run(start_relaxation(
        session,
        {"steps": 50, "fmax": 0.01},
        None,
    ))
    assert response["status"] == "started"
    deadline = time.monotonic() + 5.0
    while session.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.01)

    assert session.is_relaxing is False
    separation = np.linalg.norm(
        session.working_atoms.positions[0] - session.working_atoms.positions[1]
    )
    assert separation > 0.1
    assert np.linalg.det(session.working_atoms.cell.array) == pytest.approx(0.0)
    assert session.working_atoms.pbc.tolist() == [False, False, False]


def test_relaxation_mode_can_restore_or_keep_while_worker_is_active(monkeypatch):
    atoms = Atoms("HH", positions=[[0, 0, 0], [0.25, 0, 0]])
    session = make_session(atoms)
    monkeypatch.setattr(relax_module, "_launch_relax_thread", lambda *_args: None)

    asyncio.run(start_relaxation(session, {"steps": 20}, None))
    session.working_atoms.positions += [1.0, 0.0, 0.0]
    session.sync_current_frame()
    restored = asyncio.run(exit_relaxation(session, keep=False))
    assert restored == {"status": "exited", "kept": False}
    np.testing.assert_allclose(session.working_atoms.positions, atoms.positions)
    assert session.relaxation_mode_active is False
    assert session.is_relaxing is False

    asyncio.run(start_relaxation(session, {"steps": 20}, None))
    kept_positions = session.working_atoms.positions + [0.5, 0.0, 0.0]
    session.working_atoms.set_positions(kept_positions)
    session.sync_current_frame()
    kept = asyncio.run(exit_relaxation(session, keep=True))
    assert kept == {"status": "exited", "kept": True}
    np.testing.assert_allclose(session.working_atoms.positions, kept_positions)
    assert session.undo() is not None
    np.testing.assert_allclose(session.working_atoms.positions, atoms.positions)


def test_empty_edit_session_accepts_explicit_triclinic_cell():
    session = make_session(Atoms())
    cell = [[4.0, 0.0, 0.0], [1.2, 5.0, 0.0], [0.4, 0.7, 6.0]]

    data = asyncio.run(set_unit_cell(session.session_id, {
        "cell": cell,
        "pbc": [True, True, False],
    }))

    np.testing.assert_allclose(data["cell"], cell)
    assert data["pbc"] == [True, True, False]
    assert data["positions"] == []
    assert data["metadata"]["config"]["empty_workspace"] is False


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


def test_cartesian_translation_moves_all_frames_without_changing_cell_and_undoes():
    cell = np.array([[4.0, 0.0, 0.0], [0.5, 5.0, 0.0], [0.2, 0.4, 6.0]])
    first = Atoms("NaCl", positions=[[0.2, 0.4, 0.6], [1.5, 1.7, 1.9]], cell=cell, pbc=True)
    second = first.copy()
    second.positions += [0.3, -0.2, 0.1]
    originals = [first.copy(), second.copy()]
    session = EditorSession(
        "cartesian-translation-all-frames",
        first.copy(),
        first.copy(),
        original_frames=[frame.copy() for frame in originals],
        trajectory_frames=[frame.copy() for frame in originals],
    )
    sessions[session.session_id] = session
    shift = np.array([1.25, -0.5, 0.75])

    data = asyncio.run(apply_translation(session.session_id, {
        "positions": first.positions.tolist(),
        "vector": shift.tolist(),
        "coordinate_mode": "cartesian",
        "apply_constraint": True,
    }))

    np.testing.assert_allclose(data["positions"], originals[0].positions + shift)
    np.testing.assert_allclose(data["cell"], cell)
    for frame, original in zip(session.trajectory_frames, originals):
        np.testing.assert_allclose(frame.positions, original.positions + shift)
        np.testing.assert_allclose(frame.cell.array, cell)

    undone = asyncio.run(undo(session.session_id))
    np.testing.assert_allclose(undone["positions"], originals[0].positions)
    for frame, original in zip(session.trajectory_frames, originals):
        np.testing.assert_allclose(frame.positions, original.positions)
        np.testing.assert_allclose(frame.cell.array, cell)


def test_fractional_translation_uses_full_monoclinic_cell_for_all_frames():
    cell = np.array([[3.0, 0.0, 0.0], [0.8, 4.0, 0.0], [0.4, 0.6, 5.0]])
    first = Atoms("SiO", positions=[[0.1, 0.2, 0.3], [1.1, 1.2, 1.3]], cell=cell, pbc=True)
    second = first.copy()
    second.positions += [0.2, 0.1, -0.1]
    originals = [first.copy(), second.copy()]
    session = EditorSession(
        "fractional-translation-all-frames",
        first.copy(),
        first.copy(),
        original_frames=[frame.copy() for frame in originals],
        trajectory_frames=[frame.copy() for frame in originals],
    )
    sessions[session.session_id] = session
    fractional = np.array([0.5, -0.25, 0.125])
    cartesian = np.dot(fractional, cell)

    data = asyncio.run(apply_translation(session.session_id, {
        "positions": first.positions.tolist(),
        "vector": fractional.tolist(),
        "coordinate_mode": "fractional",
        "apply_constraint": True,
    }))

    np.testing.assert_allclose(data["positions"], originals[0].positions + cartesian)
    np.testing.assert_allclose(data["cell"], cell)
    for frame, original in zip(session.trajectory_frames, originals):
        np.testing.assert_allclose(frame.positions, original.positions + cartesian)
        np.testing.assert_allclose(frame.cell.array, cell)


def test_frame_index_prevents_cross_frame_coordinate_and_cell_leakage_in_supercell():
    first_cell = np.array([
        [3.0, 0.0, 0.0],
        [0.4, 4.0, 0.0],
        [0.2, 0.3, 5.0],
    ])
    second_cell = np.array([
        [5.0, 0.0, 0.0],
        [1.1, 3.5, 0.0],
        [0.6, 0.2, 6.0],
    ])
    first = Atoms("NaCl", positions=[[0.2, 0.3, 0.4], [1.0, 1.1, 1.2]], cell=first_cell, pbc=True)
    second = Atoms("NaCl", positions=[[0.7, 0.8, 0.9], [2.0, 2.1, 2.2]], cell=second_cell, pbc=True)
    session = EditorSession(
        "frame-specific-supercell",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=0,
    )
    sessions[session.session_id] = session
    displayed_second_positions = second.positions + np.array([0.25, -0.15, 0.35])

    data = asyncio.run(apply_supercell(session.session_id, {
        "frame_index": 1,
        "positions": displayed_second_positions.tolist(),
        "reps": [2, 1, 1],
        "apply_constraint": True,
    }))

    assert data["metadata"]["current_frame"] == 1
    np.testing.assert_allclose(session.trajectory_frames[0].cell.array, np.diag([2, 1, 1]) @ first_cell)
    np.testing.assert_allclose(session.trajectory_frames[1].cell.array, np.diag([2, 1, 1]) @ second_cell)
    np.testing.assert_allclose(session.trajectory_frames[0].positions[:2], first.positions)
    np.testing.assert_allclose(session.trajectory_frames[1].positions[:2], displayed_second_positions)
    np.testing.assert_allclose(data["positions"][:2], displayed_second_positions)


def test_fractional_translation_uses_each_frame_cell_after_frontend_frame_sync():
    first_cell = np.array([
        [3.0, 0.0, 0.0],
        [0.3, 4.0, 0.0],
        [0.1, 0.4, 5.0],
    ])
    second_cell = np.array([
        [4.5, 0.0, 0.0],
        [1.2, 3.2, 0.0],
        [0.7, 0.2, 6.5],
    ])
    first = Atoms("SiO", positions=[[0.1, 0.2, 0.3], [1.1, 1.2, 1.3]], cell=first_cell, pbc=True)
    second = Atoms("SiO", positions=[[0.4, 0.5, 0.6], [1.6, 1.7, 1.8]], cell=second_cell, pbc=True)
    session = EditorSession(
        "frame-specific-fractional-translation",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=0,
    )
    sessions[session.session_id] = session
    fractional = np.array([0.25, -0.5, 0.125])
    displayed_second_positions = second.positions + [0.05, 0.1, -0.2]

    data = asyncio.run(apply_translation(session.session_id, {
        "frame_index": 1,
        "positions": displayed_second_positions.tolist(),
        "vector": fractional.tolist(),
        "coordinate_mode": "fractional",
        "apply_constraint": True,
    }))

    np.testing.assert_allclose(
        session.trajectory_frames[0].positions,
        first.positions + fractional @ first_cell,
    )
    np.testing.assert_allclose(
        session.trajectory_frames[1].positions,
        displayed_second_positions + fractional @ second_cell,
    )
    np.testing.assert_allclose(data["cell"], second_cell)
    assert data["metadata"]["current_frame"] == 1


def test_wrap_uses_each_trajectory_frame_cell_after_frontend_frame_sync():
    first_cell = np.array([
        [3.0, 0.0, 0.0],
        [0.5, 4.0, 0.0],
        [0.1, 0.3, 5.0],
    ])
    second_cell = np.array([
        [5.0, 0.0, 0.0],
        [1.0, 3.0, 0.0],
        [0.7, 0.2, 6.0],
    ])
    first = Atoms(
        "HH",
        scaled_positions=[[1.2, -0.1, 0.5], [0.4, 1.3, -0.25]],
        cell=first_cell,
        pbc=True,
    )
    second = Atoms(
        "HH",
        scaled_positions=[[-0.4, 0.25, 1.2], [1.5, -0.2, 0.3]],
        cell=second_cell,
        pbc=True,
    )
    session = EditorSession(
        "frame-specific-wrap",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=0,
    )
    sessions[session.session_id] = session
    displayed_second = second.copy()
    displayed_second.positions += np.array([0.1, -0.2, 0.3])

    data = asyncio.run(wrap(session.session_id, {
        "frame_index": 1,
        "positions": displayed_second.positions.tolist(),
    }))

    assert data["metadata"]["current_frame"] == 1
    for frame, expected_cell in zip(
        session.trajectory_frames,
        (first_cell, second_cell),
    ):
        np.testing.assert_allclose(frame.cell.array, expected_cell)
        scaled = frame.get_scaled_positions(wrap=False)
        assert np.all(scaled >= -1e-12)
        assert np.all(scaled < 1.0 + 1e-12)


def test_cell_matrix_transform_uses_each_trajectory_frame_cell():
    first_cell = np.array([
        [2.5, 0.0, 0.0],
        [0.4, 3.0, 0.0],
        [0.2, 0.1, 4.0],
    ])
    second_cell = np.array([
        [4.0, 0.0, 0.0],
        [1.2, 2.5, 0.0],
        [0.6, 0.4, 5.5],
    ])
    first = Atoms("Li", positions=[[0.2, 0.3, 0.4]], cell=first_cell, pbc=True)
    second = Atoms("Li", positions=[[0.8, 0.7, 0.6]], cell=second_cell, pbc=True)
    session = EditorSession(
        "frame-specific-cell-matrix",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=0,
    )
    sessions[session.session_id] = session
    matrix = np.array([[2, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=int)

    data = asyncio.run(apply_supercell_matrix(session.session_id, {
        "frame_index": 1,
        "positions": second.positions.tolist(),
        "matrix": matrix.tolist(),
        "apply_constraint": True,
    }))

    assert data["metadata"]["current_frame"] == 1
    assert [len(frame) for frame in session.trajectory_frames] == [2, 2]
    np.testing.assert_allclose(
        session.trajectory_frames[0].cell.array,
        matrix @ first_cell,
    )
    np.testing.assert_allclose(
        session.trajectory_frames[1].cell.array,
        matrix @ second_cell,
    )
    np.testing.assert_allclose(data["cell"], matrix @ second_cell)


def test_displacement_analysis_supports_mic_and_stable_particle_id_mapping():
    reference = Atoms(
        "HH",
        positions=[[9.8, 0.0, 0.0], [2.0, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    current = Atoms(
        "HHH",
        positions=[[2.4, 0.0, 0.0], [0.2, 0.0, 0.0], [5.0, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    reference.set_array("particle_id", np.array([11, 22], dtype=int))
    current.set_array("particle_id", np.array([22, 11, 33], dtype=int))
    session = EditorSession(
        "displacement-particle-id",
        reference.copy(),
        current.copy(),
        original_frames=[reference.copy(), current.copy()],
        trajectory_frames=[reference.copy(), current.copy()],
        current_frame=1,
    )
    sessions[session.session_id] = session

    direct = calculate_displacements(session, {
        "frame_index": 1,
        "reference_mode": "frame",
        "reference_frame": 0,
        "mic": False,
    })
    mic = calculate_displacements(session, {
        "frame_index": 1,
        "reference_mode": "frame",
        "reference_frame": 0,
        "mic": True,
    })

    assert direct["mapping"] == "particle-id:particle_id"
    assert direct["indices"] == [0, 1]
    np.testing.assert_allclose(direct["vectors"], [[0.4, 0.0, 0.0], [-9.6, 0.0, 0.0]])
    np.testing.assert_allclose(mic["vectors"], [[0.4, 0.0, 0.0], [0.4, 0.0, 0.0]])
    np.testing.assert_allclose(direct["starts"], [[2.4, 0.0, 0.0], [0.2, 0.0, 0.0]])
    np.testing.assert_allclose(mic["starts"], [[2.4, 0.0, 0.0], [0.2, 0.0, 0.0]])
    assert mic["matched"] == 2
    assert mic["unmatched_current"] == 1


def test_view_to_edit_mode_merges_identity_for_variable_topology_frames():
    first = Atoms("HO", positions=[[0, 0, 0], [1, 0, 0]])
    second = Atoms("HHO", positions=[[0, 0, 0], [0.8, 0, 0], [1.6, 0, 0]])
    set_atom_labels(first, ["H_water", "O_water"])
    set_atom_labels(second, ["H_water", "H_extra", "O_water"])
    session = EditorSession(
        "mode-variable-topology",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={"viz_only": True},
    )
    sessions[session.session_id] = session

    data = asyncio.run(update_session_mode(session.session_id, {
        "frame_index": 0,
        "viz_only": False,
        "labels": ["H_selected", "O_selected"],
        "chemical_symbols": ["H", "O"],
        "positions": first.positions.tolist(),
    }))

    assert data["metadata"]["current_frame"] == 0
    assert atom_labels(session.trajectory_frames[0]) == ["H_selected", "O_selected"]
    assert atom_labels(session.trajectory_frames[1]) == ["H_selected", "O_selected", "O_water"]
    assert data.get("mode_transition_warnings")


def test_variable_topology_identity_and_constraints_skip_absent_indices():
    from ase.constraints import FixAtoms

    first = Atoms("H", positions=[[0, 0, 0]])
    second = Atoms("HH", positions=[[0, 0, 0], [1, 0, 0]])
    set_atom_labels(first, ["H_base"])
    set_atom_labels(second, ["H_base", "H_extra"])
    session = EditorSession(
        "edit-variable-topology",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={"viz_only": False},
    )
    sessions[session.session_id] = session

    asyncio.run(update_atom_identity(session.session_id, {
        "frame_index": 1,
        "indices": [1],
        "label": "O_added",
        "base_symbol": "O",
        "positions": second.positions.tolist(),
    }))
    assert atom_labels(session.trajectory_frames[0]) == ["H_base"]
    assert atom_labels(session.trajectory_frames[1]) == ["H_base", "O_added"]
    assert session.trajectory_frames[1].symbols[1] == "O"

    asyncio.run(update_constraints(session.session_id, {
        "frame_index": 1,
        "indices": [1],
        "fix_atoms": True,
        "positions": session.trajectory_frames[1].positions.tolist(),
    }))
    assert not session.trajectory_frames[0].constraints
    assert isinstance(session.trajectory_frames[1].constraints[0], FixAtoms)
    assert session.trajectory_frames[1].constraints[0].index.tolist() == [1]


def test_fractional_translation_requires_defined_cell():
    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]])
    session = make_session(atoms)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(apply_translation(session.session_id, {
            "positions": atoms.positions.tolist(),
            "vector": [0.5, 0.0, 0.0],
            "coordinate_mode": "fractional",
            "apply_constraint": True,
        }))

    assert excinfo.value.status_code == 400
    assert "defined unit cell" in excinfo.value.detail


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
            "bondMode": "pairwise",
            "pairwiseBondCutoffs": {"H-O": 1.35},
            "bondStyle": "flat",
            "bondThickness": 0.24,
            "bondColorMode": "custom",
            "bondCustomColor": "#18a7d8",
            "atomRadiusScale": 1.4,
            "labelRadii": {"O": 0.72},
            "supercell": [2, 1, 1],
            "translation": [0.25, -0.5, 0.75],
            "translationMode": "fractional",
            "pairwiseLabelColumnWidth": 318,
        },
        "applyConstraints": False,
        "sphereQuality": "high",
    }

    response = asyncio.run(save_visual_settings(session.session_id, {"settings": settings}))
    payload = json.loads(response.body)
    assert payload["schema"] == "v_ase.visual_settings.v3"
    assert payload["settings"]["display"]["pairwiseBondCutoffs"]["H-O"] == 1.35
    assert payload["settings"]["display"]["bondStyle"] == "flat"
    assert payload["settings"]["display"]["bondThickness"] == 0.24
    assert payload["settings"]["display"]["bondCustomColor"] == "#18a7d8"
    assert payload["settings"]["display"]["supercell"] == [2, 1, 1]
    assert payload["settings"]["display"]["translation"] == [0.25, -0.5, 0.75]
    assert payload["settings"]["display"]["translationMode"] == "fractional"
    assert payload["settings"]["display"]["pairwiseLabelColumnWidth"] == 318
    assert payload["settings"]["display"]["pairwiseBondRanges"]["H-O"]["min"] == 0.0

    loaded = asyncio.run(load_visual_settings(session.session_id, BytesRequest(response.body)))
    assert loaded["settings"]["display"]["atomRadiusScale"] == 1.4
    assert loaded["settings"]["display"]["bondColorMode"] == "custom"
    assert loaded["settings"]["display"]["translation"] == [0.25, -0.5, 0.75]
    assert loaded["settings"]["sphereQuality"] == "high"

    legacy = pickle.dumps({"schema": "v_ase.visual_settings.v1", "settings": settings})
    legacy_loaded = asyncio.run(load_visual_settings(session.session_id, BytesRequest(legacy)))
    assert legacy_loaded["settings"]["display"]["bondThickness"] == 0.24

    executable_pickle = pickle.dumps(os.system)
    with pytest.raises(HTTPException, match="global objects are not allowed"):
        asyncio.run(load_visual_settings(session.session_id, BytesRequest(executable_pickle)))


def test_visual_settings_migrate_legacy_element_named_display_keys():
    atoms = molecule("H2O")
    session = make_session(atoms)
    legacy_settings = {
        "schema": "v_ase.visual_settings.v2",
        "display": {
            "bondMode": "element",
            "elementBondCutoffs": {"H-O": 1.2},
            "elementRadii": {"O_surface": 0.7},
            "elementColors": {"O_surface": "#e51c23"},
            "elementVisible": {"H_water": False},
        },
    }

    response = asyncio.run(
        save_visual_settings(session.session_id, {"settings": legacy_settings})
    )
    payload = json.loads(response.body)
    display = payload["settings"]["display"]

    assert payload["schema"] == "v_ase.visual_settings.v3"
    assert display["bondMode"] == "pairwise"
    assert display["pairwiseBondCutoffs"] == {"H-O": 1.2}
    assert display["labelRadii"] == {"O_surface": 0.7}
    assert display["labelColors"] == {"O_surface": "#e51c23"}
    assert display["labelVisible"] == {"H_water": False}
    assert "elementBondCutoffs" not in display
    assert "elementRadii" not in display
    assert "elementColors" not in display
    assert "elementVisible" not in display


def test_vase_project_rejects_invalid_archives(tmp_path):
    invalid = tmp_path / "invalid.vase"
    invalid.write_bytes(b"not a project archive")
    with pytest.raises(ValueError, match="Invalid .vase project archive"):
        read_project_archive(invalid)


def test_vase_project_roundtrip_restores_trajectory_edits_constraints_and_settings():
    from ase.constraints import FixedPlane
    from v_ase.io import atom_labels, set_atom_labels

    first = molecule("H2O")
    first.set_cell([8, 8, 8])
    first.set_pbc(True)
    first.set_constraint(FixedPlane(0, (0, 0, 1)))
    set_atom_labels(first, ["O_surface", "H_a", "H_b"])
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
            "bondMode": "pairwise",
            "pairwiseBondCutoffs": {"H_a-O_surface": 1.4},
            "sphereQuality": "ultra",
            "sunIntensity": 3.75,
            "sunPosition": [11, -7, 16],
            "sunTarget": [1, 2, 3],
            "supercell": [2, 1, 1],
            "translation": [0.4, -0.25, 0.75],
            "translationMode": "cartesian",
            "labelMaterials": {
                "O_surface": "metal",
                "H_a": "standard",
                "H_b": "standard",
            },
            "atomMaterials": {"2": "rubber"},
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
    assert atom_labels(target.working_atoms) == ["O_surface", "H_a", "H_b"]
    assert target.working_atoms.constraints
    np.testing.assert_allclose(target.working_atoms.positions, second.positions)
    np.testing.assert_array_equal(target.working_atoms.arrays["site_class"], [4, 5, 6])
    assert target.working_atoms.info["workflow"]["stage"] == "adsorption"
    assert target.working_atoms.get_potential_energy() == pytest.approx(-1.5)
    np.testing.assert_allclose(target.working_atoms.get_forces(apply_constraint=False), 0.2)
    assert loaded["project"]["settings"]["display"]["sunIntensity"] == 3.75
    assert loaded["project"]["settings"]["display"]["supercell"] == [2, 1, 1]
    assert loaded["project"]["settings"]["display"]["translation"] == [0.4, -0.25, 0.75]
    assert loaded["project"]["settings"]["display"]["translationMode"] == "cartesian"
    assert loaded["project"]["settings"]["display"]["labelMaterials"]["O_surface"] == "metal"
    assert loaded["project"]["settings"]["display"]["atomMaterials"] == {"2": "rubber"}
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
        cutoff_scale=0.65,
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
    assert restored.cutoff_scale == pytest.approx(0.65)
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
