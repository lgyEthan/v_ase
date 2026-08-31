"""Contracts for the compact Read the Docs navigation and live examples."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


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


def test_all_documentation_captures_use_live_demo_with_fallback():
    demo_blocks = []
    direct_images = []
    for path in sorted(DOCS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        direct_images.extend(
            f"{path.name}:{line_number}"
            for line_number, line in enumerate(text.splitlines(), start=1)
            if line.startswith("![")
        )
        demo_blocks.extend((path, match) for match in DEMO_BLOCK.finditer(text))

    assert not direct_images, "Documentation captures must use vase-demo: " + ", ".join(
        direct_images
    )
    assert demo_blocks

    referenced_scenes = set()
    for page, match in demo_blocks:
        scene = match.group("scene")
        body = match.group("body")
        referenced_scenes.add(scene)
        fallback = re.search(r"^:fallback:\s*(.+?)\s*$", body, re.MULTILINE)
        assert fallback is not None, f"{page.name}:{scene} has no fallback"
        assert re.search(r"^:alt:\s*\S.+$", body, re.MULTILINE), (
            f"{page.name}:{scene} has no useful alt text"
        )
        assert (DOCS / fallback.group(1)).is_file(), f"Missing fallback for {scene}"

    scene_dir = DOCS / "_interactive" / "scenes"
    scene_files = {path.stem for path in scene_dir.glob("*.json")}
    assert scene_files == referenced_scenes


def test_interactive_scene_payloads_and_distribution_contract():
    scene_dir = DOCS / "_interactive" / "scenes"
    for path in sorted(scene_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"] == "v_ase.html-view.v1"
        assert payload["frames"]
        assert payload["referenceImage"]

    extension = (DOCS / "_ext" / "vase_demo.py").read_text(encoding="utf-8")
    assert 'HTML_BUILDERS = {"html", "dirhtml", "singlehtml"}' in extension
    assert 'return [nodes.image(uri=fallback, alt=alt)]' in extension

    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include docs/_ext *.py" in manifest
    assert "recursive-include docs/_interactive *.html *.json" in manifest


def test_public_docs_links_use_latest_until_stable_exists():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "readthedocs.io/en/stable/" not in readme
    assert "version=stable" not in readme
    assert "readthedocs.io/en/latest/" in readme
    assert "/en/latest/" in project["project"]["urls"]["Changelog"]
