"""Lazy Matplotlib color-map registry access for browser LUT rendering."""

from __future__ import annotations

import re
from functools import lru_cache

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

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PREVIEW_SAMPLES = 24
_MAX_CUSTOM_STOPS = 64


def _registry():
    from matplotlib import colormaps

    return colormaps


def _rgb_hex(values: np.ndarray) -> list[str]:
    rgb = np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
    return ["#{:02X}{:02X}{:02X}".format(*channels) for channels in rgb.tolist()]


def normalize_custom_colormap(value) -> dict:
    """Validate a portable custom color-map definition."""
    if not isinstance(value, dict):
        raise ValueError("Custom colormap must be an object.")
    mode = str(value.get("mode") or "continuous").strip().lower()
    if mode not in {"continuous", "discrete"}:
        raise ValueError("Custom colormap mode must be continuous or discrete.")
    source = value.get("stops")
    if not isinstance(source, list) or len(source) < 2:
        raise ValueError("Custom colormap requires at least two color stops.")
    if len(source) > _MAX_CUSTOM_STOPS:
        raise ValueError(f"Custom colormap supports at most {_MAX_CUSTOM_STOPS} stops.")
    stops = []
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("Every custom colormap stop must be an object.")
        try:
            position = float(item.get("position"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Custom colormap stop positions must be numeric.") from exc
        color = str(item.get("color") or "").strip().upper()
        if not np.isfinite(position) or position < 0.0 or position > 1.0:
            raise ValueError("Custom colormap stop positions must be between 0 and 1.")
        if not _HEX_COLOR.fullmatch(color):
            raise ValueError("Custom colormap colors must use #RRGGBB notation.")
        stops.append({"position": position, "color": color})
    stops.sort(key=lambda item: item["position"])
    if any(
        right["position"] - left["position"] <= 1e-12
        for left, right in zip(stops, stops[1:])
    ):
        raise ValueError("Custom colormap stop positions must be unique.")
    stops[0]["position"] = 0.0
    stops[-1]["position"] = 1.0
    return {"mode": mode, "stops": stops}


def custom_colormap_lut(value, samples: int = 256, reverse: bool = False) -> dict:
    """Sample a continuous or piecewise-constant custom color map."""
    specification = normalize_custom_colormap(value)
    count = max(16, min(2048, int(samples)))
    positions = np.asarray(
        [stop["position"] for stop in specification["stops"]], dtype=float
    )
    colors = np.asarray([
        [int(stop["color"][offset:offset + 2], 16) / 255.0 for offset in (1, 3, 5)]
        for stop in specification["stops"]
    ])
    sample_positions = np.linspace(0.0, 1.0, count)
    if specification["mode"] == "continuous":
        rgba = np.column_stack([
            np.interp(sample_positions, positions, colors[:, channel])
            for channel in range(3)
        ])
    else:
        indices = np.searchsorted(positions, sample_positions, side="right") - 1
        rgba = colors[np.clip(indices, 0, len(colors) - 1)]
    palette = _rgb_hex(rgba)
    if reverse:
        palette.reverse()
    return {
        "provider": "Custom",
        "name": "custom",
        "reverse": bool(reverse),
        "samples": count,
        "mode": specification["mode"],
        "stops": specification["stops"],
        "colors": palette,
    }


@lru_cache(maxsize=1)
def colormap_catalog() -> dict:
    """Return every registered map; Matplotlib is imported only on demand."""
    names = sorted(_registry(), key=str.casefold)
    maps = []
    registry = _registry()
    sample_positions = np.linspace(0.0, 1.0, _PREVIEW_SAMPLES)
    for name in names:
        base_name = name[:-2] if name.endswith("_r") else name
        category = next(
            (label for label, members in _CATEGORY_MEMBERS.items() if base_name in members),
            "Other",
        )
        rgba = np.asarray(registry[name](sample_positions), dtype=float)
        maps.append({
            "name": name,
            "category": category,
            "reversed_variant": name.endswith("_r"),
            "preview": _rgb_hex(rgba[:, :3]),
        })
    return {
        "provider": "Matplotlib",
        "default": "viridis",
        "preview_samples": _PREVIEW_SAMPLES,
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
    colors = _rgb_hex(rgba[:, :3])
    return {
        "provider": "Matplotlib",
        "name": str(name),
        "reverse": bool(reverse),
        "samples": count,
        "colors": colors,
    }
