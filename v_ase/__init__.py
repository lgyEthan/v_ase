"""v_ase: a browser-based ASE GUI replacement."""

from importlib.metadata import PackageNotFoundError, version

from v_ase.calculators import Conditioner, DefaultRepulsionCalculator, RepulsionCalculator
from v_ase.viewer import ASEEditor, view, view_edit, view_file

try:
    __version__ = version("v_ase-gui")
except PackageNotFoundError:
    __version__ = "0.0.66"

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
