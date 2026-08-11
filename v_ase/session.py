import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from ase import Atoms

from .io import atom_labels
from .repulsion import copy_calculator, ensure_default_calculator


@dataclass
class SessionHistoryState:
    working_atoms: Atoms
    current_frame: int
    trajectory_frames: Optional[List[Atoms]] = None
    original_atoms: Optional[Atoms] = None
    original_frames: Optional[List[Atoms]] = None
    volumetric_datasets: Optional[List[Any]] = None


@dataclass
class EditorSession:
    session_id: str
    original_atoms: Atoms
    working_atoms: Atoms
    result_atoms: Optional[Atoms] = None
    original_frames: List[Atoms] = field(default_factory=list)
    trajectory_frames: List[Atoms] = field(default_factory=list)
    trajectory_source: Any = None
    current_frame: int = 0
    # Scalar grids are immutable by convention. History stores references only
    # for operations that replace them, avoiding copies of large arrays.
    volumetric_datasets: List[Any] = field(default_factory=list)
    original_volumetric_datasets: List[Any] = field(default_factory=list)
    # Optional second structure used only by the commensurate host/guest
    # workspace until a validated common cell is materialized.
    commensurate_guest_atoms: Optional[Atoms] = None
    commensurate_guest_name: Optional[str] = None
    commensurate_search_cache: Optional[Dict[str, Any]] = field(
        default=None,
        repr=False,
    )
    # Active random insertion workflow.  The concrete dataclass lives in
    # v_ase.add_atoms to keep the session core independent of optimizer code.
    atom_addition: Any = field(default=None, repr=False)
    # Active rigid XY translation workflow.  Stored as Any for the same reason.
    registry_relaxation: Any = field(default=None, repr=False)
    
    # History
    history: List[SessionHistoryState] = field(default_factory=list)
    redo_stack: List[SessionHistoryState] = field(default_factory=list)
    
    # Events & Controls
    done_event: threading.Event = field(default_factory=threading.Event)
    cancelled: bool = False
    stop_relax: bool = False
    is_relaxing: bool = False
    relax_restart_requested: bool = False
    relax_run_id: int = 0
    relax_params: Dict[str, Any] = field(default_factory=dict)
    
    # Communication
    websockets: List[Any] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    temporary_files: Set[str] = field(default_factory=set, repr=False)
    mode_transition_lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
    )
    collaboration_revision: int = 0
    collaboration_events: deque = field(
        default_factory=lambda: deque(maxlen=512),
        repr=False,
    )
    collaboration_condition: threading.Condition = field(
        default_factory=threading.Condition,
        repr=False,
    )
    _trajectory_layout_compatible: Optional[bool] = field(
        default=None,
        repr=False,
    )

    def _attach_default_calculator(self) -> bool:
        return not bool((self.config or {}).get("viz_only", False))

    def _ensure_session_calculator(self, atoms: Atoms):
        if atoms.calc is None and self._attach_default_calculator():
            ensure_default_calculator(atoms)

    def _copy_atoms(self, atoms: Atoms) -> Atoms:
        return copy_atoms_with_calc(atoms, attach_default=self._attach_default_calculator())

    def __post_init__(self):
        self._ensure_session_calculator(self.original_atoms)
        if self.working_atoms.calc is None and self.original_atoms.calc:
            self.working_atoms.calc = copy_calculator(self.original_atoms.calc)
        else:
            self._ensure_session_calculator(self.working_atoms)
        if not self.original_frames:
            self.original_frames = [self._copy_atoms(self.original_atoms)]
        if self.trajectory_source is None and not self.trajectory_frames:
            self.trajectory_frames = [self._copy_atoms(self.working_atoms)]
        for frame in self.original_frames:
            self._ensure_session_calculator(frame)
        if self.trajectory_source is None:
            for frame in self.trajectory_frames:
                self._ensure_session_calculator(frame)
        if not self.original_volumetric_datasets:
            self.original_volumetric_datasets = list(self.volumetric_datasets)
        self.refresh_trajectory_identity()

    def publish_collaboration_event(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append one compact GUI/agent change event and wake CLI listeners."""
        with self.collaboration_condition:
            self.collaboration_revision += 1
            event = {
                "protocol": "v_ase.collaboration.v1",
                "type": str(payload.get("type") or "state.changed"),
                "revision": self.collaboration_revision,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": str(payload.get("source") or "human"),
                "categories": list(payload.get("categories") or []),
                "changed_paths": list(payload.get("changed_paths") or []),
                "summary": str(payload.get("summary") or "Session state changed."),
                "session_id": self.session_id,
                "document": str(
                    payload.get("document")
                    or (self.config or {}).get("document_name")
                    or "Untitled"
                ),
                "frame": int(payload.get("frame") or 0),
                "atom_count": int(payload.get("atom_count") or 0),
                "selection_count": int(payload.get("selection_count") or 0),
                "state_path": f"/api/ai/state/{self.session_id}",
            }
            self.collaboration_events.append(event)
            self.collaboration_condition.notify_all()
            return dict(event)

    def collaboration_events_after(
        self,
        after_revision: int,
        *,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        """Long-poll compact collaboration events newer than a revision."""
        after = max(0, int(after_revision))
        wait_seconds = max(0.0, min(float(timeout), 30.0))
        deadline = time.monotonic() + wait_seconds
        with self.collaboration_condition:
            while (
                self.collaboration_revision <= after
                and wait_seconds > 0
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.collaboration_condition.wait(timeout=remaining)

            events = [
                dict(event)
                for event in self.collaboration_events
                if int(event["revision"]) > after
            ]
            earliest_revision = (
                int(self.collaboration_events[0]["revision"])
                if self.collaboration_events
                else self.collaboration_revision + 1
            )
            return {
                "protocol": "v_ase.collaboration.v1",
                "session_id": self.session_id,
                "revision": self.collaboration_revision,
                "events": events,
                "gap": bool(after < earliest_revision - 1),
            }

    def _history_state(
        self,
        *,
        include_trajectory: bool = False,
        include_original: bool = False,
        include_volumetric: bool = False,
    ) -> SessionHistoryState:
        return SessionHistoryState(
            working_atoms=self._copy_atoms(self.working_atoms),
            current_frame=int(self.current_frame),
            trajectory_frames=(
                [self._copy_atoms(frame) for frame in self.trajectory_frames]
                if include_trajectory
                else None
            ),
            original_atoms=(
                self._copy_atoms(self.original_atoms)
                if include_original
                else None
            ),
            original_frames=(
                [self._copy_atoms(frame) for frame in self.original_frames]
                if include_original
                else None
            ),
            volumetric_datasets=(
                list(self.volumetric_datasets)
                if include_volumetric
                else None
            ),
        )

    def _restore_history_state(self, state: SessionHistoryState) -> None:
        if state.trajectory_frames is not None:
            self.trajectory_frames = [
                self._copy_atoms(frame)
                for frame in state.trajectory_frames
            ]
            self.trajectory_source = None
        if state.original_atoms is not None:
            self.original_atoms = self._copy_atoms(state.original_atoms)
        if state.original_frames is not None:
            self.original_frames = [
                self._copy_atoms(frame)
                for frame in state.original_frames
            ]
        if state.volumetric_datasets is not None:
            self.volumetric_datasets = list(state.volumetric_datasets)
        frame_count = max(1, len(self.trajectory_frames))
        self.current_frame = max(0, min(int(state.current_frame), frame_count - 1))
        self.working_atoms = self._copy_atoms(state.working_atoms)
        self.invalidate_trajectory_layout()
        self.refresh_trajectory_identity()

    def push_history(
        self,
        *,
        include_trajectory: bool = False,
        include_original: bool = False,
        include_volumetric: bool = False,
    ):
        """Save the mutation's complete affected scope for Undo."""
        self.history.append(self._history_state(
            include_trajectory=include_trajectory,
            include_original=include_original,
            include_volumetric=include_volumetric,
        ))
        if len(self.history) > 50:
            self.history.pop(0)
        self.redo_stack.clear()

    def undo(self) -> Optional[Atoms]:
        if not self.history:
            return None

        state = self.history.pop()
        self.redo_stack.append(self._history_state(
            include_trajectory=state.trajectory_frames is not None,
            include_original=state.original_frames is not None,
            include_volumetric=state.volumetric_datasets is not None,
        ))
        self._restore_history_state(state)
        return self.working_atoms

    def redo(self) -> Optional[Atoms]:
        if not self.redo_stack:
            return None

        state = self.redo_stack.pop()
        self.history.append(self._history_state(
            include_trajectory=state.trajectory_frames is not None,
            include_original=state.original_frames is not None,
            include_volumetric=state.volumetric_datasets is not None,
        ))
        self._restore_history_state(state)
        return self.working_atoms

    def preserve_calculator(self, new_atoms: Atoms):
        """Helper to ensure calculator follows structure changes."""
        if self.working_atoms.calc:
            new_atoms.calc = copy_calculator(self.working_atoms.calc)
        else:
            self._ensure_session_calculator(new_atoms)
        self.working_atoms = new_atoms
        self.invalidate_trajectory_layout()

    @property
    def frame_count(self) -> int:
        if self.trajectory_source is not None:
            return int(self.trajectory_source.frame_count)
        return len(self.trajectory_frames)

    def invalidate_trajectory_layout(self) -> None:
        self._trajectory_layout_compatible = None

    def refresh_trajectory_identity(self) -> Dict[str, Any]:
        """Cache ordered labels and their ASE elements for the whole trajectory."""
        if self.trajectory_source is not None:
            template = getattr(self.trajectory_source, "template_atoms", None)
            frames = [template] if isinstance(template, Atoms) else [self.working_atoms]
        else:
            frames = self.trajectory_frames or [self.working_atoms]

        labels: List[str] = []
        elements: Dict[str, List[str]] = {}
        for frame in frames:
            if not isinstance(frame, Atoms):
                continue
            frame_labels = atom_labels(frame)
            frame_elements = frame.get_chemical_symbols()
            for label, element in zip(frame_labels, frame_elements):
                if label not in elements:
                    labels.append(label)
                    elements[label] = []
                if element not in elements[label]:
                    elements[label].append(element)

        payload = {"labels": labels, "elements": elements}
        self.config["trajectory_identity"] = payload
        return payload

    def sync_current_frame(self):
        if self.trajectory_source is not None:
            return
        if not self.trajectory_frames:
            return
        self.trajectory_frames[self.current_frame] = self._copy_atoms(self.working_atoms)

    def set_frame(self, frame_index: int) -> Atoms:
        if self.trajectory_source is not None:
            if frame_index < 0 or frame_index >= self.frame_count:
                raise IndexError(f"Frame index {frame_index} is out of range")
            self.current_frame = frame_index
            self.working_atoms = self.trajectory_source.read_atoms(frame_index)
            if self.original_atoms.calc:
                self.working_atoms.calc = copy_calculator(self.original_atoms.calc)
            else:
                self._ensure_session_calculator(self.working_atoms)
            return self.working_atoms
        if not self.trajectory_frames:
            return self.working_atoms
        if frame_index < 0 or frame_index >= len(self.trajectory_frames):
            raise IndexError(f"Frame index {frame_index} is out of range")
        self.current_frame = frame_index
        self.working_atoms = self._copy_atoms(self.trajectory_frames[frame_index])
        return self.working_atoms

    def reset_current_frame(self):
        if self.trajectory_source is not None:
            self.set_frame(self.current_frame)
            return
        source = self.original_frames[self.current_frame] if self.current_frame < len(self.original_frames) else self.original_atoms
        self.working_atoms = self._copy_atoms(source)
        self.invalidate_trajectory_layout()
        self.sync_current_frame()

    def reset_all_frames(self):
        """Restore every trajectory frame to the originally loaded coordinates/cell."""
        if self.trajectory_source is not None:
            self.set_frame(self.current_frame)
            self.volumetric_datasets = list(self.original_volumetric_datasets)
            return
        if self.original_frames:
            self.trajectory_frames = [self._copy_atoms(frame) for frame in self.original_frames]
        else:
            self.trajectory_frames = [self._copy_atoms(self.original_atoms)]
        self.current_frame = min(self.current_frame, len(self.trajectory_frames) - 1)
        self.working_atoms = self._copy_atoms(self.trajectory_frames[self.current_frame])
        self.volumetric_datasets = list(self.original_volumetric_datasets)
        self.invalidate_trajectory_layout()

    def cleanup_temporary_files(self):
        for path in tuple(self.temporary_files):
            try:
                os.unlink(path)
            except OSError:
                pass
        self.temporary_files.clear()

sessions: Dict[str, EditorSession] = {}


@dataclass
class EditorWorkspace:
    """A browser workspace containing independent editor documents."""

    workspace_id: str
    host_session: EditorSession
    session_ids: List[str] = field(default_factory=list)
    closed: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    collaboration_revision: int = 0
    collaboration_events: deque = field(
        default_factory=lambda: deque(maxlen=1024),
        repr=False,
    )
    collaboration_condition: threading.Condition = field(
        default_factory=threading.Condition,
        repr=False,
    )

    @property
    def host_session_id(self) -> str:
        return self.host_session.session_id

    def publish_collaboration_event(
        self,
        document_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append one document event to the workspace-wide CLI stream."""
        with self.collaboration_condition:
            self.collaboration_revision += 1
            event = {
                **dict(document_event),
                "revision": self.collaboration_revision,
                "document_revision": int(document_event["revision"]),
                "workspace_id": self.workspace_id,
            }
            self.collaboration_events.append(event)
            self.collaboration_condition.notify_all()
            return dict(event)

    def collaboration_events_after(
        self,
        after_revision: int,
        *,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        """Long-poll all document changes in this workspace."""
        after = max(0, int(after_revision))
        wait_seconds = max(0.0, min(float(timeout), 30.0))
        deadline = time.monotonic() + wait_seconds
        with self.collaboration_condition:
            while (
                self.collaboration_revision <= after
                and wait_seconds > 0
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.collaboration_condition.wait(timeout=remaining)
            events = [
                dict(event)
                for event in self.collaboration_events
                if int(event["revision"]) > after
            ]
            earliest_revision = (
                int(self.collaboration_events[0]["revision"])
                if self.collaboration_events
                else self.collaboration_revision + 1
            )
            return {
                "protocol": "v_ase.collaboration.v1",
                "workspace_id": self.workspace_id,
                "revision": self.collaboration_revision,
                "events": events,
                "gap": bool(after < earliest_revision - 1),
            }


workspaces: Dict[str, EditorWorkspace] = {}
_workspaces_lock = threading.RLock()


def create_workspace(host_session: EditorSession) -> EditorWorkspace:
    workspace_id = str(uuid.uuid4())
    host_session.config["workspace_id"] = workspace_id
    host_session.config["workspace_auto_close_on_disconnect"] = bool(
        host_session.config.get(
            "workspace_auto_close_on_disconnect",
            host_session.config.get("auto_close_on_disconnect", True),
        )
    )
    # Document sockets must never finalize the host independently. The
    # workspace socket owns browser-close behavior through the preserved flag.
    host_session.config["auto_close_on_disconnect"] = False
    host_session.config.setdefault("document_name", "Untitled")
    workspace = EditorWorkspace(
        workspace_id=workspace_id,
        host_session=host_session,
        session_ids=[host_session.session_id],
    )
    with _workspaces_lock:
        workspaces[workspace_id] = workspace
    return workspace


def get_workspace(workspace_id: str) -> EditorWorkspace:
    with _workspaces_lock:
        workspace = workspaces.get(workspace_id)
    if workspace is None or workspace.closed:
        raise ValueError(f"Workspace {workspace_id} not found")
    return workspace


def create_workspace_session(
    workspace: EditorWorkspace,
    *,
    source_session_id: str | None = None,
) -> EditorSession:
    """Create a blank document with the workspace's operating mode."""
    with workspace.lock:
        source = sessions.get(source_session_id or "") or workspace.host_session
        source_config = source.config or {}
        config = {
            key: source_config.get(key)
            for key in (
                "show_cell",
                "show_axes",
                "show_bonds",
                "apply_constraint",
                "allow_relax",
                "viz_only",
                "theme",
                "launch_directory",
            )
            if key in source_config
        }
        config.update({
            "initial_design_settings": None,
            "empty_workspace": True,
            "auto_close_on_disconnect": False,
            "workspace_id": workspace.workspace_id,
            "document_name": "Untitled",
        })
        session_id = str(uuid.uuid4())
        original = Atoms()
        working = Atoms()
        session = EditorSession(
            session_id=session_id,
            original_atoms=original,
            working_atoms=working,
            original_frames=[original.copy()],
            trajectory_frames=[working.copy()],
            config=config,
        )
        sessions[session_id] = session
        workspace.session_ids.append(session_id)
        return session


def remove_workspace_session(workspace: EditorWorkspace, session_id: str) -> None:
    """Remove one document without finalizing the surrounding workspace."""
    with workspace.lock:
        if session_id not in workspace.session_ids:
            raise ValueError(f"Session {session_id} is not part of workspace {workspace.workspace_id}")
        workspace.session_ids.remove(session_id)
        session = sessions.get(session_id)
        if session is None:
            return
        session.stop_relax = True
        session.relax_restart_requested = False
        session.relax_run_id += 1
        if session.registry_relaxation is not None:
            session.registry_relaxation.stop_requested = True
            session.registry_relaxation.run_id += 1
        if session_id != workspace.host_session_id:
            sessions.pop(session_id, None)
            session.cleanup_temporary_files()


def finalize_workspace(workspace_id: str) -> None:
    """Close all child documents and release the blocking host session."""
    with _workspaces_lock:
        workspace = workspaces.get(workspace_id)
    if workspace is None:
        return
    with workspace.lock:
        if workspace.closed:
            return
        workspace.closed = True
        host = workspace.host_session
        host.stop_relax = True
        host.relax_restart_requested = False
        host.relax_run_id += 1
        if host.registry_relaxation is not None:
            host.registry_relaxation.stop_requested = True
            host.registry_relaxation.run_id += 1
        host.result_atoms = copy_atoms_with_calc(
            host.working_atoms,
            attach_default=not bool((host.config or {}).get("viz_only", False)),
        )
        for session_id in tuple(workspace.session_ids):
            session = sessions.get(session_id)
            if session is None:
                continue
            session.stop_relax = True
            session.relax_restart_requested = False
            session.relax_run_id += 1
            if session.registry_relaxation is not None:
                session.registry_relaxation.stop_requested = True
                session.registry_relaxation.run_id += 1
            if session_id != workspace.host_session_id:
                sessions.pop(session_id, None)
                session.cleanup_temporary_files()
        workspace.session_ids.clear()
        host.done_event.set()
    with _workspaces_lock:
        workspaces.pop(workspace_id, None)

def copy_atoms_with_calc(atoms: Atoms, attach_default: bool = True) -> Atoms:
    copied = atoms.copy()
    if atoms.calc:
        copied.calc = copy_calculator(atoms.calc)
    elif attach_default:
        ensure_default_calculator(copied)
    return copied

def get_session(session_id: str) -> EditorSession:
    if session_id not in sessions:
        raise ValueError(f"Session {session_id} not found")
    return sessions[session_id]


def replace_session_frames(
    session: EditorSession,
    frames: List[Atoms],
    *,
    trajectory_source=None,
    current_frame: int = 0,
    initial_design_settings: Optional[Dict[str, Any]] = None,
    volumetric_datasets: Optional[List[Any]] = None,
) -> None:
    """Replace the loaded document while preserving the session's UI mode."""
    if not frames or not all(isinstance(frame, Atoms) for frame in frames):
        raise ValueError("A loaded document must contain at least one ASE Atoms frame.")

    attach_default = not bool((session.config or {}).get("viz_only", False))
    original_frames = [copy_atoms_with_calc(frame, attach_default=attach_default) for frame in frames]
    working_frames = [copy_atoms_with_calc(frame, attach_default=attach_default) for frame in frames]
    frame_index = max(0, min(int(current_frame), len(working_frames) - 1))

    session.original_frames = original_frames
    session.trajectory_frames = working_frames
    session.trajectory_source = trajectory_source
    session.volumetric_datasets = list(volumetric_datasets or [])
    session.original_volumetric_datasets = list(volumetric_datasets or [])
    session.commensurate_guest_atoms = None
    session.commensurate_guest_name = None
    session.commensurate_search_cache = None
    session.atom_addition = None
    session.registry_relaxation = None
    session.current_frame = frame_index
    session.original_atoms = copy_atoms_with_calc(original_frames[0], attach_default=attach_default)
    session.working_atoms = copy_atoms_with_calc(working_frames[frame_index], attach_default=attach_default)
    session.result_atoms = None
    session.history.clear()
    session.redo_stack.clear()
    session.stop_relax = False
    session.is_relaxing = False
    session.relax_restart_requested = False
    session.relax_run_id += 1
    session.relax_params.clear()
    session.invalidate_trajectory_layout()
    session.config["initial_design_settings"] = initial_design_settings
    session.refresh_trajectory_identity()


def append_session_frames(session: EditorSession, frames: List[Atoms]) -> int:
    """Append frames while preserving the active frame and its working edits."""
    if not frames or not all(isinstance(frame, Atoms) for frame in frames):
        raise ValueError("At least one ASE Atoms frame is required for trajectory append.")

    attach_default = not bool((session.config or {}).get("viz_only", False))
    is_empty = bool((session.config or {}).get("empty_workspace", False)) and len(session.working_atoms) == 0

    if is_empty:
        existing_original: List[Atoms] = []
        existing_working: List[Atoms] = []
        current_frame = 0
    elif session.trajectory_source is not None:
        existing_original = [
            copy_atoms_with_calc(
                session.trajectory_source.read_atoms(index),
                attach_default=attach_default,
            )
            for index in range(session.frame_count)
        ]
        existing_working = [
            copy_atoms_with_calc(frame, attach_default=attach_default)
            for frame in existing_original
        ]
        current_frame = max(0, min(session.current_frame, len(existing_working) - 1))
        existing_working[current_frame] = copy_atoms_with_calc(
            session.working_atoms,
            attach_default=attach_default,
        )
    else:
        session.sync_current_frame()
        existing_working = [
            copy_atoms_with_calc(frame, attach_default=attach_default)
            for frame in (session.trajectory_frames or [session.working_atoms])
        ]
        existing_original = [
            copy_atoms_with_calc(frame, attach_default=attach_default)
            for frame in (session.original_frames or [session.original_atoms])
        ]
        if len(existing_original) < len(existing_working):
            existing_original.extend(
                copy_atoms_with_calc(frame, attach_default=attach_default)
                for frame in existing_working[len(existing_original):]
            )
        current_frame = max(0, min(session.current_frame, len(existing_working) - 1))

    appended_original = [
        copy_atoms_with_calc(frame, attach_default=attach_default)
        for frame in frames
    ]
    appended_working = [
        copy_atoms_with_calc(frame, attach_default=attach_default)
        for frame in frames
    ]
    session.original_frames = existing_original + appended_original
    session.trajectory_frames = existing_working + appended_working
    session.trajectory_source = None
    session.current_frame = current_frame
    session.original_atoms = copy_atoms_with_calc(
        session.original_frames[0],
        attach_default=attach_default,
    )
    session.working_atoms = copy_atoms_with_calc(
        session.trajectory_frames[current_frame],
        attach_default=attach_default,
    )
    session.result_atoms = None
    session.atom_addition = None
    session.registry_relaxation = None
    session.history.clear()
    session.redo_stack.clear()
    session.stop_relax = False
    session.is_relaxing = False
    session.relax_restart_requested = False
    session.relax_run_id += 1
    session.relax_params.clear()
    session.invalidate_trajectory_layout()
    session.config["empty_workspace"] = False
    session.refresh_trajectory_identity()
    session.cleanup_temporary_files()
    return len(appended_working)
