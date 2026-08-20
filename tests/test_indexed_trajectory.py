import asyncio

import numpy as np
import pytest
from ase import Atoms
from ase.io.trajectory import Trajectory
from fastapi import HTTPException

from v_ase.io import ATOM_LABEL_ARRAY, read_indexed_trajectory
from v_ase.server import (
    _file_read_error_detail,
    append_structure_file,
    load_structure_file,
)
from v_ase.session import EditorSession, sessions


class StreamRequest:
    def __init__(self, data: bytes):
        self.data = data
        self.headers = {"content-length": str(len(data))}

    async def stream(self):
        yield self.data


def write_xdatcar(path):
    path.write_text(
        """v_ase indexed trajectory test
1.0
2.0 0.0 0.0
0.0 3.0 0.0
0.0 0.0 4.0
O O
1 1
Direct configuration=     1
0.10 0.20 0.30
0.40 0.50 0.60
Direct configuration=     2
0.20 0.30 0.40
0.50 0.60 0.70
""",
        encoding="utf-8",
    )


def test_xdatcar_is_offset_indexed_and_preserves_repeated_species_labels(tmp_path):
    path = tmp_path / "XDATCAR"
    write_xdatcar(path)

    result = read_indexed_trajectory(path, ":", "vasp-xdatcar")

    assert result is not None
    assert result.trajectory.frame_count == 2
    assert result.atoms.arrays[ATOM_LABEL_ARRAY].tolist() == ["O_1", "O_2"]
    np.testing.assert_allclose(
        result.trajectory.read_positions(1),
        [[0.4, 0.9, 1.6], [1.0, 1.8, 2.8]],
    )
    np.testing.assert_allclose(result.trajectory.cells[0], np.diag([2.0, 3.0, 4.0]))


def test_native_ase_trajectory_uses_random_access_selection(tmp_path):
    path = tmp_path / "short.traj"
    with Trajectory(path, mode="w") as trajectory:
        for offset in range(4):
            trajectory.write(Atoms("H", positions=[[offset, 0, 0]]))

    result = read_indexed_trajectory(path, "1:4:2", "traj")

    assert result is not None
    assert result.trajectory.frame_count == 2
    np.testing.assert_allclose(result.atoms.positions, [[1, 0, 0]])
    np.testing.assert_allclose(result.trajectory.read_positions(1), [[3, 0, 0]])


def test_view_mode_upload_keeps_indexed_xdatcar_on_demand(tmp_path):
    path = tmp_path / "XDATCAR"
    write_xdatcar(path)
    session = EditorSession(
        session_id="indexed-xdatcar-upload",
        original_atoms=Atoms(),
        working_atoms=Atoms(),
        config={"viz_only": False, "empty_workspace": True, "stream_trajectory": True},
    )
    sessions[session.session_id] = session
    try:
        data = asyncio.run(load_structure_file(
            session.session_id,
            StreamRequest(path.read_bytes()),
            filename="XDATCAR",
            index=":",
            runtime_mode="view",
        ))
        assert session.trajectory_source is not None
        assert session.frame_count == 2
        assert data["metadata"]["virtual_trajectory"] is True
        assert len(session.temporary_files) == 1
    finally:
        session.cleanup_temporary_files()
        sessions.pop(session.session_id, None)


def test_view_mode_upload_falls_back_when_fast_xdatcar_indexing_is_unavailable(
    monkeypatch,
):
    session = EditorSession(
        session_id="indexed-xdatcar-fallback",
        original_atoms=Atoms(),
        working_atoms=Atoms(),
        config={"viz_only": False, "empty_workspace": True},
    )
    sessions[session.session_id] = session
    fallback = Atoms("He", positions=[[1.0, 2.0, 3.0]])

    def reject_fast_reader(*_args, **_kwargs):
        raise ValueError("unsupported XDATCAR header variant")

    monkeypatch.setattr("v_ase.io.read_indexed_trajectory", reject_fast_reader)
    monkeypatch.setattr(
        "v_ase.io.read_structure_frames",
        lambda *_args, **_kwargs: [fallback.copy()],
    )
    try:
        data = asyncio.run(load_structure_file(
            session.session_id,
            StreamRequest(b"valid but unusual XDATCAR"),
            filename="XDATCAR",
            index=":",
            runtime_mode="view",
        ))
        assert session.trajectory_source is None
        assert data["metadata"]["natoms"] == 1
        np.testing.assert_allclose(data["positions"], [[1.0, 2.0, 3.0]])
    finally:
        session.cleanup_temporary_files()
        sessions.pop(session.session_id, None)


def test_unknown_append_format_returns_a_useful_client_error():
    session = EditorSession(
        session_id="unknown-append-format",
        original_atoms=Atoms("H"),
        working_atoms=Atoms("H"),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    try:
        with pytest.raises(HTTPException) as caught:
            asyncio.run(append_structure_file(
                session.session_id,
                StreamRequest(b"not a structure"),
                filename="trajectory.unknown-extension",
            ))
        assert caught.value.status_code == 400
        assert "Could not determine the file format" in caught.value.detail
        assert "Internal Server Error" not in caught.value.detail
    finally:
        sessions.pop(session.session_id, None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FileNotFoundError("private/path/POSCAR"), "no longer exists"),
        (PermissionError("private/path/POSCAR"), "Permission was denied"),
        (IsADirectoryError("private/path"), "is a directory"),
        (EOFError(), "ended unexpectedly"),
        (
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
            "not valid text",
        ),
    ],
)
def test_file_read_errors_are_sanitized_for_common_failures(error, expected):
    detail = _file_read_error_detail("load", "structure.dat", error)
    assert detail.startswith("Could not load structure.dat:")
    assert expected in detail
    assert "private/path" not in detail
