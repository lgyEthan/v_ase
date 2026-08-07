"""Lazy Matplotlib color-map registry access for browser LUT rendering."""

from __future__ import annotations

import numpy as np


_CATEGORY_MEMBERS = {
    "Perceptually uniform sequential": {
        "viridis", "plasma", "inferno", "magma", "cividis",
    },
    "Sequential": {
        "Greys", "Purples", "Blues", "Greens", "Oranges", "Reds",
        "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu", "GnBu",
        "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn", "binary", "gist_yarg",
        "gist_gray", "gray", "bone", "pink", "spring", "summer", "autumn",
        "winter", "cool", "Wistia", "hot", "afmhot", "gist_heat", "copper",
    },
    "Diverging": {
        "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu", "Spectral",
        "coolwarm", "bwr", "seismic",
    },
    "Cyclic": {"twilight", "twilight_shifted", "hsv"},
    "Qualitative": {
        "Pastel1", "Pastel2", "Paired", "Accent", "Dark2", "Set1", "Set2",
        "Set3", "tab10", "tab20", "tab20b", "tab20c",
    },
}


def _registry():
    from matplotlib import colormaps

    return colormaps


def colormap_catalog() -> dict:
    """Return every registered map; Matplotlib is imported only on demand."""
    names = sorted(_registry(), key=str.casefold)
    maps = []
    for name in names:
        base_name = name[:-2] if name.endswith("_r") else name
        category = next(
            (label for label, members in _CATEGORY_MEMBERS.items() if base_name in members),
            "Other",
        )
        maps.append({"name": name, "category": category, "reversed_variant": name.endswith("_r")})
    return {
        "provider": "Matplotlib",
        "default": "viridis",
        "maps": maps,
    }


def colormap_lut(name: str, samples: int = 256, reverse: bool = False) -> dict:
    registry = _registry()
    if name not in registry:
        raise ValueError(f"Unknown Matplotlib colormap '{name}'.")
    count = max(16, min(2048, int(samples)))
    cmap = registry[name]
    if reverse:
        cmap = cmap.reversed()
    rgba = np.asarray(cmap(np.linspace(0.0, 1.0, count)), dtype=float)
    rgb = np.rint(np.clip(rgba[:, :3], 0.0, 1.0) * 255.0).astype(np.uint8)
    colors = ["#{:02X}{:02X}{:02X}".format(*channels) for channels in rgb.tolist()]
    return {
        "provider": "Matplotlib",
        "name": str(name),
        "reverse": bool(reverse),
        "samples": count,
        "colors": colors,
    }
