import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional
from ase import Atoms
import numpy as np
from .repulsion import copy_calculator, ensure_default_calculator

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
    
    # State
    selection: Set[int] = field(default_factory=set)
    atom_colors: Dict[int, str] = field(default_factory=dict) # index -> hex
    element_colors: Dict[str, str] = field(default_factory=dict) # element -> hex
    
    # History
    history: List[Atoms] = field(default_factory=list)
    redo_stack: List[Atoms] = field(default_factory=list)
    
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

    def _attach_default_calculator(self) -> bool:
        return not bool((self.config or {}).get("viz_only", False))

    def _ensure_session_calculator(self, atoms: Atoms):
        if atoms.calc is None and self._attach_default_calculator():
            ensure_default_calculator(atoms)

    def _copy_atoms(self, atoms: Atoms) -> Atoms:
        return copy_atoms_with_calc(atoms, attach_default=self._attach_default_calculator())

    def __post_init__(self):
        self._ensure_session_calculator(self.original_atoms)
        self._ensure_session_calculator(self.working_atoms)
        # Ensure working atoms has the calculator
        if self.original_atoms.calc:
            self.working_atoms.calc = copy_calculator(self.original_atoms.calc)
        if not self.original_frames:
            self.original_frames = [self._copy_atoms(self.original_atoms)]
        if self.trajectory_source is None and not self.trajectory_frames:
            self.trajectory_frames = [self._copy_atoms(self.working_atoms)]
        for frame in self.original_frames:
            self._ensure_session_calculator(frame)
        if self.trajectory_source is None:
            for frame in self.trajectory_frames:
                self._ensure_session_calculator(frame)

    def push_history(self):
        """Save current state to history for Undo."""
        # We store copies to prevent mutation
        state = self.working_atoms.copy()
        if self.working_atoms.calc:
            state.calc = copy_calculator(self.working_atoms.calc)
        
        self.history.append(state)
        if len(self.history) > 50:
            self.history.pop(0)
        self.redo_stack.clear() # New action clears redo stack

    def undo(self) -> Optional[Atoms]:
        if not self.history:
            return None
        
        # Save current to redo
        current = self.working_atoms.copy()
        if self.working_atoms.calc:
            current.calc = copy_calculator(self.working_atoms.calc)
        self.redo_stack.append(current)
        
        # Restore from history
        self.working_atoms = self.history.pop()
        return self.working_atoms

    def redo(self) -> Optional[Atoms]:
        if not self.redo_stack:
            return None
            
        # Save current to history
        current = self.working_atoms.copy()
        if self.working_atoms.calc:
            current.calc = copy_calculator(self.working_atoms.calc)
        self.history.append(current)
        
        # Restore from redo
        self.working_atoms = self.redo_stack.pop()
        return self.working_atoms

    def preserve_calculator(self, new_atoms: Atoms):
        """Helper to ensure calculator follows structure changes."""
        if self.working_atoms.calc:
            new_atoms.calc = copy_calculator(self.working_atoms.calc)
        else:
            self._ensure_session_calculator(new_atoms)
        self.working_atoms = new_atoms

    @property
    def frame_count(self) -> int:
        if self.trajectory_source is not None:
            return int(self.trajectory_source.frame_count)
        return len(self.trajectory_frames)

    def sync_current_frame(self):
        if self.trajectory_source is not None:
            return
        if not self.trajectory_frames:
            return
        self.trajectory_frames[self.current_frame] = self.working_atoms.copy()
        if self.working_atoms.calc:
            self.trajectory_frames[self.current_frame].calc = copy_calculator(self.working_atoms.calc)

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
        self.working_atoms = self.trajectory_frames[frame_index].copy()
        if self.trajectory_frames[frame_index].calc:
            self.working_atoms.calc = copy_calculator(self.trajectory_frames[frame_index].calc)
        else:
            self._ensure_session_calculator(self.working_atoms)
        return self.working_atoms

    def reset_current_frame(self):
        if self.trajectory_source is not None:
            self.set_frame(self.current_frame)
            return
        source = self.original_frames[self.current_frame] if self.current_frame < len(self.original_frames) else self.original_atoms
        self.working_atoms = source.copy()
        if source.calc:
            self.working_atoms.calc = copy_calculator(source.calc)
        else:
            self._ensure_session_calculator(self.working_atoms)
        self.sync_current_frame()

    def reset_all_frames(self):
        """Restore every trajectory frame to the originally loaded coordinates/cell."""
        if self.trajectory_source is not None:
            self.set_frame(self.current_frame)
            return
        if self.original_frames:
            self.trajectory_frames = [self._copy_atoms(frame) for frame in self.original_frames]
        else:
            self.trajectory_frames = [self._copy_atoms(self.original_atoms)]
        self.current_frame = min(self.current_frame, len(self.trajectory_frames) - 1)
        self.working_atoms = self._copy_atoms(self.trajectory_frames[self.current_frame])

    def cleanup_temporary_files(self):
        for path in tuple(self.temporary_files):
            try:
                os.unlink(path)
            except OSError:
                pass
        self.temporary_files.clear()

sessions: Dict[str, EditorSession] = {}

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
    session.current_frame = frame_index
    session.original_atoms = copy_atoms_with_calc(original_frames[0], attach_default=attach_default)
    session.working_atoms = copy_atoms_with_calc(working_frames[frame_index], attach_default=attach_default)
    session.result_atoms = None
    session.selection.clear()
    session.atom_colors.clear()
    session.element_colors.clear()
    session.history.clear()
    session.redo_stack.clear()
    session.stop_relax = False
    session.is_relaxing = False
    session.relax_restart_requested = False
    session.relax_run_id += 1
    session.relax_params.clear()
    session.config["initial_design_settings"] = initial_design_settings
