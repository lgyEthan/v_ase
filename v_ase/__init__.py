"""v_ase: a browser-based ASE GUI replacement.

The public objects are imported lazily so lightweight commands such as
``v_ase --version`` and remote-runtime configuration remain available even
when an environment's compiled NumPy/SciPy stack needs repair.
"""

from importlib import import_module

from v_ase._version import __version__
from v_ase.notebook import register_notebook_magic

register_notebook_magic()

_LAZY_EXPORTS = {
    "ASEEditor": ("v_ase.viewer", "ASEEditor"),
    "view": ("v_ase.viewer", "view"),
    "view_edit": ("v_ase.viewer", "view_edit"),
    "view_file": ("v_ase.viewer", "view_file"),
    "RepulsionCalculator": ("v_ase.calculators", "RepulsionCalculator"),
    "DefaultRepulsionCalculator": ("v_ase.calculators", "DefaultRepulsionCalculator"),
    "Conditioner": ("v_ase.calculators", "Conditioner"),
}


def __getattr__(name):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value

__all__ = [
    "ASEEditor",
    "view",
    "view_edit",
    "view_file",
    "RepulsionCalculator",
    "DefaultRepulsionCalculator",
    "Conditioner",
    "__version__",
]
