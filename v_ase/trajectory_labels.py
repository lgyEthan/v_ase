"""Validate index-based appearance changes against effective trajectory labels."""

import numpy as np

from .io import atom_labels
from .project import project_frame_identity_labels


def effective_labels(frames, overrides=None):
    overrides_by_frame = project_frame_identity_labels(frames, {"viewIdentityOverrides": overrides})
    return [atom_labels(atoms) if saved is None else saved
            for atoms, saved in zip(frames, overrides_by_frame)]


def appearance_scope_reason(reference, reference_labels, frames_and_labels, indices, reference_index):
    composition = np.sort(reference.numbers)
    if not indices:
        return "Select atoms to check trajectory scope."
    for number, (atoms, frame_labels) in enumerate(frames_and_labels, 1):
        pair = f"Frames {reference_index + 1} and {number} have"
        if len(atoms) != len(reference):
            return f"{pair} different atom counts."
        if not np.array_equal(np.sort(atoms.numbers), composition):
            return f"{pair} different element compositions."
        if not np.array_equal(atoms.numbers[indices], reference.numbers[indices]):
            return f"{pair} different elements at the selected indices."
        for key in ("id", "atom_id", "atom_ids"):
            left, right = reference.arrays.get(key), atoms.arrays.get(key)
            if left is None and right is None:
                continue
            if left is None or right is None or not np.array_equal(left[indices], right[indices]):
                return f"{pair} different atom IDs at the selected indices."
        if any(frame_labels[i] != reference_labels[i] for i in indices):
            return f"{pair} different labels at the selected indices."
    return None
