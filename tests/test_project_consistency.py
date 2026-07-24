"""Repository-wide documentation, naming, and release consistency checks."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from v_ase import __version__
from v_ase.io import ATOM_LABEL_ARRAY, atom_labels, set_atom_labels


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")


def test_local_markdown_links_resolve():
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    missing = []
    for document in markdown_files:
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing, "Broken local Markdown links:\n" + "\n".join(missing)


def test_release_version_is_synchronized():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == __version__

    versioned_assets = [
        ROOT / "v_ase/static/index.html",
        ROOT / "v_ase/static/main.js",
        ROOT / "v_ase/static/workspace.html",
    ]
    for asset in versioned_assets:
        assert __version__ in asset.read_text(encoding="utf-8"), asset

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {__version__}" in changelog


def test_source_distribution_includes_release_documents():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    included = {line.removeprefix("include ").strip() for line in manifest if line.startswith("include ")}
    assert {"README.md", "CHANGELOG.md", "LICENSE", "requirements.txt"} <= included


def test_requirements_include_every_runtime_dependency():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = {
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert set(project["project"]["dependencies"]).issubset(requirements)


def test_legacy_project_names_do_not_reappear():
    checked = [
        ROOT / "README.md",
        *sorted((ROOT / "docs").glob("*.md")),
        *sorted((ROOT / "v_ase").glob("*.py")),
    ]
    forbidden = ("ase_pro_viewer", "ASE Pro Viewer", "changes.md")
    matches = []
    for path in checked:
        text = path.read_text(encoding="utf-8")
        for value in forbidden:
            if value in text:
                matches.append(f"{path.relative_to(ROOT)}: {value}")
    assert not matches, "Legacy names found:\n" + "\n".join(matches)


def test_canonical_atom_label_api_is_public():
    assert ATOM_LABEL_ARRAY == "v_ase_atom_type"
    assert callable(atom_labels)
    assert callable(set_atom_labels)
