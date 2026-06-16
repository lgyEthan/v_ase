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

    def __post_init__(self):
        ensure_default_calculator(self.original_atoms)
        ensure_default_calculator(self.working_atoms)
        # Ensure working atoms has the calculator
        if self.original_atoms.calc:
            self.working_atoms.calc = copy_calculator(self.original_atoms.calc)
        if not self.original_frames:
            self.original_frames = [self.original_atoms.copy()]
            if self.original_atoms.calc:
                self.original_frames[0].calc = copy_calculator(self.original_atoms.calc)
        if not self.trajectory_frames:
            self.trajectory_frames = [self.working_atoms.copy()]
            if self.working_atoms.calc:
                self.trajectory_frames[0].calc = copy_calculator(self.working_atoms.calc)
        for frame in self.original_frames:
            ensure_default_calculator(frame)
        for frame in self.trajectory_frames:
            ensure_default_calculator(frame)

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
        self.working_atoms = new_atoms

    @property
    def frame_count(self) -> int:
        return len(self.trajectory_frames)

    def sync_current_frame(self):
        if not self.trajectory_frames:
            return
        self.trajectory_frames[self.current_frame] = self.working_atoms.copy()
        if self.working_atoms.calc:
            self.trajectory_frames[self.current_frame].calc = copy_calculator(self.working_atoms.calc)

    def set_frame(self, frame_index: int) -> Atoms:
        if not self.trajectory_frames:
            return self.working_atoms
        if frame_index < 0 or frame_index >= len(self.trajectory_frames):
            raise IndexError(f"Frame index {frame_index} is out of range")
        self.current_frame = frame_index
        self.working_atoms = self.trajectory_frames[frame_index].copy()
        if self.trajectory_frames[frame_index].calc:
            self.working_atoms.calc = copy_calculator(self.trajectory_frames[frame_index].calc)
        else:
            ensure_default_calculator(self.working_atoms)
        return self.working_atoms

    def reset_current_frame(self):
        source = self.original_frames[self.current_frame] if self.current_frame < len(self.original_frames) else self.original_atoms
        self.working_atoms = source.copy()
        if source.calc:
            self.working_atoms.calc = copy_calculator(source.calc)
        else:
            ensure_default_calculator(self.working_atoms)
        self.sync_current_frame()

    def reset_all_frames(self):
        """Restore every trajectory frame to the originally loaded coordinates/cell."""
        if self.original_frames:
            self.trajectory_frames = [copy_atoms_with_calc(frame) for frame in self.original_frames]
        else:
            self.trajectory_frames = [copy_atoms_with_calc(self.original_atoms)]
        self.current_frame = min(self.current_frame, len(self.trajectory_frames) - 1)
        self.working_atoms = copy_atoms_with_calc(self.trajectory_frames[self.current_frame])

sessions: Dict[str, EditorSession] = {}

def copy_atoms_with_calc(atoms: Atoms) -> Atoms:
    copied = atoms.copy()
    if atoms.calc:
        copied.calc = copy_calculator(atoms.calc)
    else:
        ensure_default_calculator(copied)
    return copied

def get_session(session_id: str) -> EditorSession:
    if session_id not in sessions:
        raise ValueError(f"Session {session_id} not found")
    return sessions[session_id]
