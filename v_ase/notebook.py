"""IPython display-mode controls for v_ase."""

from __future__ import annotations

from .viewer import get_notebook_display_mode, set_notebook_display_mode


def register_notebook_magic(ipython=None) -> bool:
    """Register ``%v_ase`` in an active IPython shell."""
    try:
        from IPython import get_ipython
        from IPython.core.magic import Magics, line_magic, magics_class
    except ModuleNotFoundError:
        return False

    shell = ipython or get_ipython()
    if shell is None:
        return False
    if getattr(shell, "_v_ase_display_magic_registered", False):
        return True

    @magics_class
    class VAseDisplayMagics(Magics):
        @line_magic
        def v_ase(self, line=""):
            """Select auto, inline, or external-browser display for ``view()``."""
            requested = str(line or "").strip().lower()
            if requested in {"", "status"}:
                mode = get_notebook_display_mode()
            else:
                mode = set_notebook_display_mode(requested)
            detail = {
                "auto": "Jupyter kernels display inline; ordinary Python opens a browser.",
                "inline": "view() displays an interactive model below the notebook cell.",
                "browser": "view() opens the full interface in an external browser.",
            }[mode]
            print(f"v_ase display: {mode} - {detail}")
            return mode

    shell.register_magics(VAseDisplayMagics)
    shell._v_ase_display_magic_registered = True
    return True


def load_ipython_extension(ipython) -> None:
    """IPython extension entry point for ``%load_ext v_ase.notebook``."""
    register_notebook_magic(ipython)


def unload_ipython_extension(ipython) -> None:
    """Keep the registered magic stable for the life of the kernel."""


__all__ = [
    "get_notebook_display_mode",
    "load_ipython_extension",
    "register_notebook_magic",
    "set_notebook_display_mode",
    "unload_ipython_extension",
]
