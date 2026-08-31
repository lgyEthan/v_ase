"""Contracts for compact navigation, exact captures, and the live logo."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DEMO_BLOCK = re.compile(
    r"^```\{vase-demo\}\s+(?P<scene>[a-z0-9-]+)\s*$\n"
    r"(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
TOCTREE = re.compile(
    r"^```\{toctree\}\s*$\n(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


def _toctree_entries(text: str) -> list[str]:
    entries: list[str] = []
    for match in TOCTREE.finditer(text):
        for raw_line in match.group("body").splitlines():
            line = raw_line.strip()
            if line and not line.startswith((":", "#")):
                entries.append(line)
    return entries


def test_sidebar_starts_with_four_task_hubs():
    index = (DOCS / "index.md").read_text(encoding="utf-8")
    assert _toctree_entries(index) == ["start", "workflows", "automation", "reference"]

    for hub in ("start", "workflows", "automation", "reference"):
        entries = _toctree_entries((DOCS / f"{hub}.md").read_text(encoding="utf-8"))
        assert entries, f"{hub}.md must own at least one navigation child"


def test_only_logo_is_live_and_scientific_captures_are_static():
    demo_blocks = []
    direct_images: list[tuple[Path, str, str]] = []
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            image = re.fullmatch(r"!\[(.+)]\(([^)]+)\)", line)
            if image:
                direct_images.append((path, image.group(1), image.group(2)))
        demo_blocks.extend((path, match) for match in DEMO_BLOCK.finditer(text))

    assert [(page.name, match.group("scene")) for page, match in demo_blocks] == [
        ("index.md", "logo")
    ]
    assert len(direct_images) >= 18

    for page, alt, target in direct_images:
        assert alt.strip(), f"{page.name} has an image without alt text"
        assert target.startswith("assets/"), f"{page.name} uses a non-versioned image"
        assert (DOCS / target).is_file(), f"{page.name} references missing {target}"

    scientific_pages = {
        "index.md": "readme_overview.png",
        "editing.md": "readme_add_atoms.png",
        "constraints-relaxation.md": "readme_constraints.png",
        "trajectories-analysis.md": "readme_atom_colorscale.png",
        "volumetric-guide.md": "readme_volumetric.png",
        "periodic-interfaces.md": "readme_registry_map.png",
        "worked-examples.md": "readme_measurement.png",
    }
    for filename, asset in scientific_pages.items():
        text = (DOCS / filename).read_text(encoding="utf-8")
        assert f"](assets/{asset})" in text
        assert "```{vase-demo}" not in text or filename == "index.md"

    scene_dir = DOCS / "_interactive" / "scenes"
    scene_files = {path.stem for path in scene_dir.glob("*.json")}
    assert scene_files == {"logo"}


def test_interactive_scene_payloads_and_distribution_contract():
    scene_dir = DOCS / "_interactive" / "scenes"
    payload = json.loads((scene_dir / "logo.json").read_text(encoding="utf-8"))
    assert payload["schema"] == "v_ase.html-view.v1"
    assert payload["frames"]
    assert payload["referenceImage"] == "v_ase-logo.png"

    cameras = []

    def collect_cameras(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "camera" and isinstance(child, dict):
                    cameras.append(child)
                collect_cameras(child)
        elif isinstance(value, list):
            for child in value:
                collect_cameras(child)

    collect_cameras(payload)
    assert cameras
    for camera in cameras:
        assert camera["position"][:2] == pytest.approx([0.0, 0.0], abs=1e-12)
        assert camera["position"][2] > 0
        assert camera["target"] == pytest.approx([0.0, 0.0, 0.0], abs=1e-12)
        assert camera["up"] == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)

    extension = (DOCS / "_ext" / "vase_demo.py").read_text(encoding="utf-8")
    assert 'HTML_BUILDERS = {"html", "dirhtml", "singlehtml"}' in extension
    assert 'return [nodes.image(uri=fallback, alt=alt)]' in extension

    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include docs/_ext *.py" in manifest
    assert "recursive-include docs/_interactive *.html *.json" in manifest

    capture = (ROOT / "scripts" / "capture_readme_screenshots.py").read_text(
        encoding="utf-8"
    )
    assert capture.count("save_docs_interactive_scene(") == 2


def test_public_docs_links_use_latest_until_stable_exists():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "readthedocs.io/en/stable/" not in readme
    assert "version=stable" not in readme
    assert "readthedocs.io/en/latest/" in readme
    assert "/en/latest/" in project["project"]["urls"]["Changelog"]
