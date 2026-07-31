from __future__ import annotations

import asyncio
import io
from pathlib import Path
import zipfile

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.vasp import VaspChargeDensity
from ase.io.cube import write_cube
from ase.io.xsf import write_xsf

from v_ase.volumetric import (
    ISOSURFACE_BINARY_MAGIC,
    VolumetricData,
    _max_grid_points,
    combine_volumetric_datasets,
    generate_isosurface,
    read_volumetric_file,
    resolve_volumetric_format,
)
from v_ase.project import (
    MAX_ARCHIVE_MEMBERS,
    read_project_archive,
    write_project_archive,
)
from v_ase.server import (
    apply_supercell,
    create_volumetric_difference,
    reset_coordinates,
    session_atoms_to_json,
    undo as undo_session,
    volumetric_isosurface,
)
from v_ase.session import EditorSession, sessions


def test_volumetric_format_detection_covers_vasp_and_qe_exchange_formats(tmp_path):
    assert resolve_volumetric_format(tmp_path / "CHGCAR") == "vasp-density"
    assert resolve_volumetric_format(tmp_path / "LOCPOT") == "vasp-potential"
    assert resolve_volumetric_format(tmp_path / "PARCHG") == "vasp-partial-density"
    assert resolve_volumetric_format(tmp_path / "density.cube") == "cube"
    assert resolve_volumetric_format(tmp_path / "density.xsf") == "xsf"
    assert resolve_volumetric_format(tmp_path / "unknown.dat") is None
    assert resolve_volumetric_format(tmp_path / "anything", "qe-cube") == "cube"


def test_documented_volumetric_grid_limit_environment_variable_is_authoritative(
    monkeypatch,
):
    monkeypatch.setenv("V_ASE_MAX_VOLUME_POINTS", "1100000")
    monkeypatch.setenv("V_ASE_MAX_VOLUMETRIC_POINTS", "1250000")
    assert _max_grid_points() == 1_250_000


def test_cube_reader_preserves_grid_cell_origin_and_atoms(tmp_path):
    atoms = Atoms(
        "HO",
        positions=[[0.2, 0.3, 0.4], [1.1, 1.0, 0.9]],
        cell=[[4.0, 0.0, 0.0], [0.4, 5.0, 0.0], [0.2, 0.3, 6.0]],
        pbc=True,
    )
    grid = np.arange(4 * 5 * 6, dtype=float).reshape(4, 5, 6) / 17.0
    path = tmp_path / "qe-density.cube"
    with path.open("w", encoding="utf-8") as handle:
        write_cube(handle, atoms, data=grid, origin=[0.1, 0.2, 0.3])

    datasets = read_volumetric_file(path)

    assert len(datasets) == 1
    dataset = datasets[0]
    np.testing.assert_allclose(dataset.values, grid, rtol=2e-6, atol=2e-6)
    np.testing.assert_allclose(dataset.cell, atoms.cell.array, rtol=2e-6, atol=2e-6)
    np.testing.assert_allclose(dataset.origin, [0.1, 0.2, 0.3], atol=2e-6)
    assert dataset.atoms is not None
    assert dataset.atoms.get_chemical_symbols() == ["H", "O"]
    assert dataset.source_format == "cube"


def test_vasp_reader_preserves_density_axis_order_and_locpot_native_values(tmp_path):
    atoms = Atoms(
        "SiO",
        positions=[[0.1, 0.2, 0.3], [1.0, 1.2, 1.4]],
        cell=[[4.0, 0.0, 0.0], [0.5, 5.0, 0.0], [0.2, 0.3, 6.0]],
        pbc=True,
    )
    density = np.arange(5 * 6 * 7, dtype=float).reshape(5, 6, 7) / 100.0
    writer = VaspChargeDensity(None)
    writer.atoms = [atoms]
    writer.chg = [density]
    chgcar = tmp_path / "CHGCAR"
    writer.write(chgcar, format="chgcar")

    loaded_density = read_volumetric_file(chgcar)[0]
    np.testing.assert_allclose(loaded_density.values, density, rtol=1e-6, atol=1e-7)
    assert loaded_density.quantity == "charge_density"
    assert loaded_density.units == "1/angstrom^3"

    potential = density * 3.25 - 1.75
    potential_writer = VaspChargeDensity(None)
    potential_writer.atoms = [atoms]
    potential_writer.chg = [potential / atoms.get_volume()]
    locpot = tmp_path / "LOCPOT"
    potential_writer.write(locpot, format="chgcar")

    loaded_potential = read_volumetric_file(locpot)[0]
    np.testing.assert_allclose(loaded_potential.values, potential, rtol=2e-6, atol=2e-6)
    assert loaded_potential.quantity == "electrostatic_potential"
    assert loaded_potential.units == "eV"


def test_vasp_reader_streams_spin_component_without_losing_grid_order(tmp_path):
    atoms = Atoms(
        "Fe",
        positions=[[0.3, 0.4, 0.5]],
        cell=[[4.0, 0.0, 0.0], [0.3, 4.5, 0.0], [0.1, 0.2, 5.0]],
        pbc=True,
    )
    total = np.arange(4 * 5 * 6, dtype=float).reshape(4, 5, 6) / 70.0
    magnetization = np.cos(
        np.linspace(0, 2 * np.pi, total.size, endpoint=False)
    ).reshape(total.shape)
    writer = VaspChargeDensity(None)
    writer.atoms = [atoms]
    writer.chg = [total]
    writer.chgdiff = [magnetization]
    path = tmp_path / "CHGCAR.spin"
    writer.write(path, format="chgcar")

    datasets = read_volumetric_file(path)

    assert len(datasets) == 2
    np.testing.assert_allclose(datasets[0].values, total, rtol=2e-6, atol=2e-6)
    np.testing.assert_allclose(
        datasets[1].values,
        magnetization,
        rtol=2e-6,
        atol=2e-6,
    )
    assert datasets[1].quantity == "magnetization_density"
    assert datasets[1].component == "spin_difference"


def test_xsf_reader_supports_qe_pp_exchange_grid(tmp_path):
    atoms = Atoms(
        "C2",
        positions=[[0.4, 0.5, 0.6], [1.6, 1.5, 1.4]],
        cell=[[4.0, 0.0, 0.0], [0.3, 4.5, 0.0], [0.1, 0.2, 5.0]],
        pbc=True,
    )
    values = np.sin(np.linspace(0, 2 * np.pi, 6 * 7 * 8)).reshape(6, 7, 8)
    path = tmp_path / "qe-pp.xsf"
    with path.open("w", encoding="utf-8") as handle:
        write_xsf(
            handle,
            [atoms],
            data=values,
            origin=[0.1, 0.2, 0.3],
            span_vectors=atoms.cell.array,
        )

    dataset = read_volumetric_file(path)[0]

    np.testing.assert_allclose(dataset.values, values, rtol=3e-5, atol=1e-6)
    np.testing.assert_allclose(dataset.origin, [0.1, 0.2, 0.3])
    np.testing.assert_allclose(dataset.cell, atoms.cell.array)
    assert dataset.endpoint_inclusive is True
    assert dataset.source_format == "xsf"


def test_charge_density_difference_requires_matching_physical_grids():
    cell = np.diag([5.0, 6.0, 7.0])
    first = VolumetricData("first", np.ones((8, 9, 10)), cell, units="1/angstrom^3")
    second = VolumetricData("second", np.full((8, 9, 10), 0.25), cell, units="1/angstrom^3")

    difference = combine_volumetric_datasets([first, second], [1.0, -1.0])

    np.testing.assert_allclose(difference.values, 0.75)
    assert difference.quantity == "charge_density_difference"
    assert difference.metadata["sources"] == [first.dataset_id, second.dataset_id]
    with pytest.raises(ValueError, match="identical dimensions"):
        combine_volumetric_datasets(
            [first, VolumetricData("bad", np.zeros((7, 9, 10)), cell)],
            [1.0, -1.0],
        )


def test_volumetric_supercell_preserves_endpoint_conventions_and_integral():
    cell = np.array([[4.0, 0.0, 0.0], [0.4, 5.0, 0.0], [0.2, 0.3, 6.0]])
    exclusive_values = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    exclusive = VolumetricData(
        "exclusive",
        exclusive_values,
        cell,
        pbc=True,
        endpoint_inclusive=False,
    )
    repeated_exclusive = exclusive.replicated([2, 1, 3])
    np.testing.assert_array_equal(
        repeated_exclusive.values,
        np.tile(exclusive_values, (2, 1, 3)),
    )
    np.testing.assert_allclose(
        repeated_exclusive.cell,
        np.diag([2, 1, 3]) @ cell,
    )
    assert repeated_exclusive.integral == pytest.approx(exclusive.integral * 6)

    core = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
    inclusive_values = np.concatenate((core, core[:1]), axis=0)
    inclusive_values = np.concatenate(
        (inclusive_values, inclusive_values[:, :1]),
        axis=1,
    )
    inclusive_values = np.concatenate(
        (inclusive_values, inclusive_values[:, :, :1]),
        axis=2,
    )
    inclusive = VolumetricData(
        "inclusive",
        inclusive_values,
        cell,
        pbc=True,
        endpoint_inclusive=True,
    )
    repeated_inclusive = inclusive.replicated([2, 2, 1])
    assert repeated_inclusive.values.shape == (5, 7, 5)
    np.testing.assert_array_equal(
        repeated_inclusive.values[:-1, :-1, :-1],
        np.tile(core, (2, 2, 1)),
    )
    np.testing.assert_array_equal(
        repeated_inclusive.values[-1],
        repeated_inclusive.values[0],
    )
    assert repeated_inclusive.integral == pytest.approx(inclusive.integral * 4)
    with pytest.raises(ValueError, match="finite integers"):
        exclusive.replicated([1.5, 1, 1])


def test_set_supercell_as_cell_updates_and_undoes_volumetric_data_atomically():
    atoms = Atoms("He", positions=[[0.5, 0.5, 0.5]], cell=[3, 4, 5], pbc=True)
    values = np.arange(4 * 5 * 6, dtype=np.float32).reshape(4, 5, 6)
    dataset = VolumetricData(
        "density",
        values,
        atoms.cell.array,
        pbc=True,
        atoms=atoms,
    )
    session = EditorSession(
        "volumetric-supercell",
        atoms.copy(),
        atoms.copy(),
        volumetric_datasets=[dataset],
    )
    sessions[session.session_id] = session
    try:
        asyncio.run(apply_supercell(
            session.session_id,
            {
                "reps": [2, 1, 2],
                "positions": atoms.positions.tolist(),
                "frame_index": 0,
            },
        ))
        assert len(session.working_atoms) == 4
        repeated = session.volumetric_datasets[0]
        assert repeated.values.shape == (8, 5, 12)
        np.testing.assert_array_equal(repeated.values, np.tile(values, (2, 1, 2)))
        np.testing.assert_allclose(repeated.cell, np.diag([6, 4, 10]))

        asyncio.run(reset_coordinates(session.session_id))
        assert len(session.working_atoms) == 1
        reset_dataset = session.volumetric_datasets[0]
        np.testing.assert_array_equal(reset_dataset.values, values)
        np.testing.assert_allclose(reset_dataset.cell, atoms.cell.array)

        asyncio.run(undo_session(session.session_id))
        assert len(session.working_atoms) == 4
        repeated_again = session.volumetric_datasets[0]
        np.testing.assert_array_equal(
            repeated_again.values,
            np.tile(values, (2, 1, 2)),
        )
        np.testing.assert_allclose(repeated_again.cell, np.diag([6, 4, 10]))

        asyncio.run(undo_session(session.session_id))
        assert len(session.working_atoms) == 1
        restored = session.volumetric_datasets[0]
        np.testing.assert_array_equal(restored.values, values)
        np.testing.assert_allclose(restored.cell, atoms.cell.array)
    finally:
        sessions.pop(session.session_id, None)


def test_periodic_isosurface_closes_cell_seams_and_uses_cartesian_cell(monkeypatch):
    pytest.importorskip("skimage")
    shape = (18, 16, 14)
    fractional = np.stack(
        np.meshgrid(
            *[np.arange(size) / size for size in shape],
            indexing="ij",
        ),
        axis=-1,
    )
    center_delta = fractional - np.array([0.05, 0.5, 0.5])
    center_delta -= np.round(center_delta)
    values = 0.22 - np.linalg.norm(center_delta, axis=-1)
    cell = np.array([[4.0, 0.0, 0.0], [1.0, 5.0, 0.0], [0.2, 0.4, 6.0]])
    dataset = VolumetricData("periodic sphere", values, cell, pbc=[True, True, True])

    mesh = generate_isosurface(dataset, 0.0)
    payload = mesh.binary()

    assert payload.startswith(ISOSURFACE_BINARY_MAGIC)
    assert len(mesh.faces) > 0
    assert np.min(mesh.vertices[:, 0]) < 0.5
    assert np.max(mesh.vertices[:, 0]) > 3.5
    assert np.all(np.isfinite(mesh.vertices))


def test_vase_project_roundtrips_volumetric_data_without_pickle(tmp_path):
    atoms = Atoms("Li", positions=[[0.5, 0.5, 0.5]], cell=[4, 5, 6], pbc=True)
    values = np.linspace(-0.4, 0.8, 7 * 8 * 9, dtype=np.float32).reshape(7, 8, 9)
    dataset = VolumetricData(
        "density difference",
        values,
        atoms.cell.array,
        quantity="charge_density_difference",
        units="1/angstrom^3",
        source_format="linear-combination",
        atoms=atoms,
        metadata={"sources": ["a", "b"], "coefficients": [1.0, -1.0]},
    )
    session = EditorSession(
        "volumetric-project",
        atoms.copy(),
        atoms.copy(),
        volumetric_datasets=[dataset],
    )
    destination = tmp_path / "volumetric.vase"

    write_project_archive(
        destination,
        session,
        {
            "display": {
                "showVolumetric": True,
                "volumetricDatasetId": dataset.dataset_id,
                "volumetricLevel": 0.15,
                "supercell": [2, 1, 1],
                "translation": [0.2, 0.3, 0.4],
            }
        },
    )
    restored = read_project_archive(destination)

    assert len(restored.volumetric_datasets) == 1
    loaded = restored.volumetric_datasets[0]
    assert loaded.dataset_id == dataset.dataset_id
    assert loaded.quantity == "charge_density_difference"
    assert loaded.units == "1/angstrom^3"
    np.testing.assert_array_equal(loaded.values, values)
    np.testing.assert_allclose(loaded.cell, atoms.cell.array)
    assert restored.settings["display"]["supercell"] == [2, 1, 1]
    assert restored.settings["display"]["translation"] == [0.2, 0.3, 0.4]


def test_vase_project_rejects_unexpected_nested_volumetric_arrays(tmp_path):
    atoms = Atoms("He", positions=[[0.5, 0.5, 0.5]], cell=[4, 4, 4], pbc=True)
    dataset = VolumetricData(
        "density",
        np.ones((4, 4, 4), dtype=np.float32),
        atoms.cell.array,
        atoms=atoms,
    )
    session = EditorSession(
        "nested-npz-security",
        atoms.copy(),
        atoms.copy(),
        volumetric_datasets=[dataset],
    )
    original = tmp_path / "original.vase"
    tampered = tmp_path / "tampered.vase"
    write_project_archive(original, session, {})

    nested = io.BytesIO()
    np.savez(
        nested,
        values=dataset.values,
        cell=dataset.cell,
        origin=dataset.origin,
        pbc=dataset.pbc,
        unexpected=np.ones(1, dtype=np.float32),
    )
    with zipfile.ZipFile(original, mode="r") as source:
        members = {
            info.filename: source.read(info.filename)
            for info in source.infolist()
        }
    members["volumetric/0000.npz"] = nested.getvalue()
    with zipfile.ZipFile(tampered, mode="w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, payload in members.items():
            target.writestr(name, payload)

    with pytest.raises(ValueError, match="unexpected arrays"):
        read_project_archive(tampered)


def test_vase_project_rejects_excessive_archive_member_counts(tmp_path):
    archive_path = tmp_path / "member-bomb.vase"
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("structure.traj", b"")
        for index in range(MAX_ARCHIVE_MEMBERS - 1):
            archive.writestr(f"extra/{index:05d}", b"")

    with pytest.raises(ValueError, match="too many archive members"):
        read_project_archive(archive_path)


def test_volumetric_api_exposes_metadata_difference_and_binary_mesh():
    pytest.importorskip("skimage")
    atoms = Atoms("He", positions=[[1.5, 1.5, 1.5]], cell=[3, 3, 3], pbc=True)
    coordinates = np.stack(
        np.meshgrid(
            *[np.arange(12, dtype=float) / 12.0 for _ in range(3)],
            indexing="ij",
        ),
        axis=-1,
    )
    delta = coordinates - 0.5
    delta -= np.round(delta)
    first = VolumetricData(
        "first",
        0.3 - np.linalg.norm(delta, axis=-1),
        atoms.cell.array,
        units="1/angstrom^3",
        atoms=atoms,
    )
    second = VolumetricData(
        "second",
        np.full((12, 12, 12), 0.05),
        atoms.cell.array,
        units="1/angstrom^3",
        atoms=atoms,
    )
    session = EditorSession(
        "volumetric-api",
        atoms.copy(),
        atoms.copy(),
        volumetric_datasets=[first, second],
    )
    sessions[session.session_id] = session
    try:
        metadata = session_atoms_to_json(session)["metadata"]["volumetric_datasets"]
        assert [entry["id"] for entry in metadata] == [first.dataset_id, second.dataset_id]

        difference = asyncio.run(create_volumetric_difference(
            session.session_id,
            {
                "dataset_ids": [first.dataset_id, second.dataset_id],
                "coefficients": [1.0, -1.0],
                "name": "difference",
            },
        ))
        assert difference["dataset"]["name"] == "difference"
        assert len(session.volumetric_datasets) == 3

        response = asyncio.run(volumetric_isosurface(
            session.session_id,
            {
                "dataset_id": first.dataset_id,
                "level": 0.0,
                "step_size": 1,
            },
        ))
        assert response.body.startswith(ISOSURFACE_BINARY_MAGIC)
        assert response.media_type == "application/vnd.v-ase.isosurface"
    finally:
        sessions.pop(session.session_id, None)
