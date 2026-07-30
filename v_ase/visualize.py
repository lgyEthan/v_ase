"""Public visualization API for v_ase.

This module mirrors the ASE-style import shape:

    from v_ase.visualize import view
"""

from .notebook import register_notebook_magic
from .viewer import ASEEditor, view, view_edit, view_file

register_notebook_magic()

__all__ = ["ASEEditor", "view", "view_edit", "view_file"]
