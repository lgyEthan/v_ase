import os
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Union

from ase import Atoms

from .io import read_fast_lammps_dump, read_structure_frames
from .repulsion import copy_calculator, ensure_default_calculator
from .session import (
    EditorSession,
    copy_atoms_with_calc,
    create_workspace,
    finalize_workspace,
    sessions,
)


@dataclass
class _LocalServer:
    server: Any
    thread: threading.Thread
    owners: int = 1


_local_servers: dict[int, _LocalServer] = {}
_local_servers_lock = threading.RLock()


def find_free_port() -> int:
    """Return an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def wait_for_local_server(port: int, timeout: float = 5.0) -> None:
    """Wait until the local HTTP server accepts connections."""
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.01)
    raise RuntimeError(
        f"v_ase local server did not start on port {port} within {timeout:.1f}s"
    ) from last_error


def acquire_local_server(app, port: int) -> None:
    """Start or retain one managed Uvicorn server for a local port."""
    with _local_servers_lock:
        existing = _local_servers.get(port)
        if existing and existing.thread.is_alive():
            existing.owners += 1
            wait_for_local_server(port)
            return

        import uvicorn

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            timeout_graceful_shutdown=1,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(
            target=server.run,
            name=f"v_ase-server-{port}",
            daemon=True,
        )
        _local_servers[port] = _LocalServer(server=server, thread=thread)
        thread.start()

    try:
        wait_for_local_server(port)
    except Exception:
        release_local_server(port, force=True)
        raise


def release_local_server(port: int, *, force: bool = False) -> None:
    """Release an owner and stop the server after its final session closes."""
    with _local_servers_lock:
        handle = _local_servers.get(port)
        if handle is None:
            return
        if not force:
            handle.owners -= 1
            if handle.owners > 0:
                return
        _local_servers.pop(port, None)
        handle.server.should_exit = True

    if handle.thread is threading.current_thread():
        return
    handle.thread.join(timeout=3)
    if handle.thread.is_alive():
        handle.server.force_exit = True
        handle.thread.join(timeout=1)


def normalize_atoms_input(atoms_or_frames, *, attach_default: bool = True) -> list[Atoms]:
    """Accept an Atoms object, an Atoms sequence, or an ASE-readable trajectory file."""
    if isinstance(atoms_or_frames, (str, os.PathLike)):
        frames = read_structure_frames(os.fspath(atoms_or_frames), index=":")
    elif isinstance(atoms_or_frames, Atoms):
        frames = [atoms_or_frames]
    elif isinstance(atoms_or_frames, Sequence):
        frames = list(atoms_or_frames)
    else:
        raise TypeError("view() expects an ase.Atoms object, an Atoms sequence, or an ASE-readable trajectory file path")

    if not frames or not all(isinstance(frame, Atoms) for frame in frames):
        raise TypeError("Trajectory input must contain one or more ase.Atoms objects")
    return [copy_atoms_with_calc(frame, attach_default=attach_default) for frame in frames]


class ASEEditor:
    """Handle for non-blocking viewer sessions."""
    def __init__(self, session_id: str, port: int, workspace_id: str | None = None):
        self.session_id = session_id
        self.port = port
        self.workspace_id = workspace_id
        self._closed = False
        self._close_lock = threading.Lock()
        if workspace_id and session_id in sessions:
            done_event = sessions[session_id].done_event
            threading.Thread(
                target=self._close_after_workspace_finishes,
                args=(done_event,),
                name=f"v_ase-session-watch-{session_id[:8]}",
                daemon=True,
            ).start()

    def _close_after_workspace_finishes(self, done_event: threading.Event) -> None:
        done_event.wait()
        self.close()

    @property
    def url(self) -> str:
        if self.workspace_id:
            return (
                f"http://127.0.0.1:{self.port}/workspace"
                f"?workspace_id={self.workspace_id}&session_id={self.session_id}"
            )
        return f"http://127.0.0.1:{self.port}/?session_id={self.session_id}"

    def get_atoms(self) -> Optional[Atoms]:
        if self.session_id in sessions:
            session = sessions[self.session_id]
            attach_default = not bool((session.config or {}).get("viz_only", False))
            return copy_atoms_with_calc(session.working_atoms, attach_default=attach_default)
        return None

    def get_positions(self):
        atoms = self.get_atoms()
        return atoms.get_positions() if atoms is not None else None

    def set_atoms(self, atoms: Atoms):
        if self.session_id in sessions:
            session = sessions[self.session_id]
            session.push_history()
            session.working_atoms = atoms.copy()
            if atoms.calc:
                session.working_atoms.calc = copy_calculator(atoms.calc)
            else:
                attach_default = not bool((session.config or {}).get("viz_only", False))
                if attach_default:
                    ensure_default_calculator(session.working_atoms)

    def close(self):
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        if self.workspace_id:
            finalize_workspace(self.workspace_id)
        if self.session_id in sessions:
            session = sessions.pop(self.session_id)
            session.cleanup_temporary_files()
        release_local_server(self.port)

    def export_poscar(self, filename="POSCAR"):
        from ase.io import write
        atoms = self.get_atoms()
        if atoms is None:
            raise RuntimeError("Editor session is closed")
        write(filename, atoms, format="vasp")
        return filename

    def export_pickle(self, filename="atoms.pkl", include_calculator=False):
        import pickle
        from .export import atoms_for_pickle_export

        atoms = self.get_atoms()
        if atoms is None:
            raise RuntimeError("Editor session is closed")
        atoms = atoms_for_pickle_export(atoms)
        with open(filename, "wb") as handle:
            pickle.dump(atoms, handle)
        return filename

    def _repr_html_(self):
        return (
            f'<iframe src="http://127.0.0.1:{self.port}/?session_id={self.session_id}" '
            'width="100%" height="700" style="border:0"></iframe>'
        )

def view(
    atoms: Atoms | Sequence[Atoms] | str | os.PathLike,
    *,
    notebook: bool = False,
    block: bool = True,
    port: Optional[int] = None,
    show_cell: bool = True,
    show_axes: bool = True,
    show_bonds: bool = False,
    respect_constraints: bool = True,
    allow_relax: bool = True,
    viz_only: bool = True,
    theme: str = "auto",
    return_mode: str = "atoms",
    trajectory_source=None,
    initial_frame: int = 0,
    initial_design_settings: Optional[dict[str, Any]] = None,
    document_name: str | None = None,
    close_on_disconnect: bool = True,
) -> Union[Atoms, ASEEditor, None]:
    """
    Open the v_ase structure viewer/editor.
    
    Parameters:
    -----------
    atoms : ase.Atoms, sequence of ase.Atoms, or path
        The structure or trajectory to visualize/edit.
    notebook : bool
        If True, render inside a Jupyter IFrame.
    block : bool
        If True, block execution until the browser document is closed or the
        session is finalized through the local API.
    ...
    """
    source_path = os.fspath(atoms) if isinstance(atoms, (str, os.PathLike)) else None
    if document_name is None:
        document_name = os.path.basename(source_path) if source_path else "Untitled"

    if source_path and source_path.lower().endswith(".vase"):
        from .project import read_project_archive

        project = read_project_archive(atoms)
        atoms = project.frames
        initial_frame = project.current_frame
        if initial_design_settings is None:
            initial_design_settings = project.settings
    elif source_path and viz_only and trajectory_source is None:
        suffix = os.path.splitext(source_path)[1].lower()
        if suffix in {".lammpstrj", ".dump"}:
            try:
                fast = read_fast_lammps_dump(source_path, ":")
            except ValueError:
                pass
            else:
                atoms = [fast.atoms]
                trajectory_source = fast.trajectory
                initial_frame = fast.initial_frame

    session_id = str(uuid.uuid4())
    attach_default = not viz_only
    frames = normalize_atoms_input(atoms, attach_default=attach_default)
    
    # normalize_atoms_input() already owns independent copies. Keep those as
    # immutable reset sources and create only the separate working trajectory.
    original_frames = frames
    working_frames = [copy_atoms_with_calc(frame, attach_default=attach_default) for frame in frames]
    original_atoms = original_frames[0]
    initial_frame = max(0, min(int(initial_frame), len(working_frames) - 1))
    working_atoms = working_frames[initial_frame]
        
    session = EditorSession(
        session_id=session_id,
        original_atoms=original_atoms,
        working_atoms=working_atoms,
        original_frames=original_frames,
        trajectory_frames=working_frames,
        trajectory_source=trajectory_source,
        current_frame=initial_frame,
        config={
            "show_cell": show_cell,
            "show_axes": show_axes,
            "show_bonds": show_bonds,
            "apply_constraint": respect_constraints,
            "allow_relax": allow_relax,
            "viz_only": viz_only,
            "theme": theme,
            "initial_design_settings": initial_design_settings,
            "empty_workspace": len(frames) == 1 and len(frames[0]) == 0,
            "auto_close_on_disconnect": bool(close_on_disconnect and not notebook),
            "document_name": document_name or "Untitled",
        }
    )
    sessions[session_id] = session
    workspace = None
    
    server_enabled = True
    if port is None:
        try:
            port = find_free_port()
        except PermissionError:
            server_enabled = False
            port = 0

    if server_enabled:
        try:
            import webbrowser
            from .server import app
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "v_ase web mode requires 'fastapi' and 'uvicorn'. "
                "Install them with: pip install fastapi uvicorn"
            ) from exc

        acquire_local_server(app, port)
    
    if server_enabled and not notebook:
        workspace = create_workspace(session)
        url = (
            f"http://127.0.0.1:{port}/workspace"
            f"?workspace_id={workspace.workspace_id}&session_id={session_id}"
        )
    else:
        url = f"http://127.0.0.1:{port}/?session_id={session_id}"
    
    if notebook:
        try:
            from IPython.display import IFrame, display
            display(IFrame(src=url, width="100%", height="700px"))
        except ModuleNotFoundError:
            pass
        return ASEEditor(session_id, port)
    else:
        if server_enabled:
            webbrowser.open(url)
        elif not block:
            raise RuntimeError("Cannot open v_ase because this environment does not allow local sockets.")
        
        if block:
            try:
                session.done_event.wait()
            except KeyboardInterrupt:
                pass
            try:
                if session.cancelled:
                    res = copy_atoms_with_calc(
                        session.original_atoms,
                        attach_default=attach_default,
                    )
                else:
                    res = session.result_atoms if session.result_atoms else session.working_atoms
                    res = copy_atoms_with_calc(res, attach_default=attach_default)

                if return_mode == "atoms":
                    return res
                if return_mode == "positions":
                    return res.get_positions()
                if return_mode == "none":
                    return None
                raise ValueError(
                    "return_mode must be one of: 'atoms', 'positions', 'none'"
                )
            finally:
                if workspace is not None:
                    finalize_workspace(workspace.workspace_id)
                closed_session = sessions.pop(session_id, None)
                if closed_session is not None:
                    closed_session.cleanup_temporary_files()
                release_local_server(port)
        else:
            return ASEEditor(
                session_id,
                port,
                workspace_id=workspace.workspace_id if workspace else None,
            )


def view_edit(
    atoms: Atoms | Sequence[Atoms] | str | os.PathLike,
    *,
    notebook: bool = False,
    block: bool = True,
    port: Optional[int] = None,
    show_cell: bool = True,
    show_axes: bool = True,
    show_bonds: bool = False,
    respect_constraints: bool = True,
    allow_relax: bool = True,
    export: bool = True,
    return_mode: str = "atoms",
    close_on_disconnect: bool = True,
):
    """Compatibility alias for opening v_ase in interactive mode."""
    return view(
        atoms,
        notebook=notebook,
        block=block,
        port=port,
        show_cell=show_cell,
        show_axes=show_axes,
        show_bonds=show_bonds,
        respect_constraints=respect_constraints,
        allow_relax=allow_relax,
        viz_only=False,
        return_mode=return_mode,
        close_on_disconnect=close_on_disconnect,
    )


def view_file(filename, **kwargs):
    """Open an ASE-readable structure or trajectory file."""
    return view(filename, **kwargs)
