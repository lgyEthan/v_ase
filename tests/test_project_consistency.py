"""Repository-wide documentation, naming, and release consistency checks."""

from __future__ import annotations

import hashlib
import re
import tomllib
from pathlib import Path

from v_ase._version import __version__
from v_ase.io import ATOM_LABEL_ARRAY, atom_labels, set_atom_labels


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
MYST_TOCTREE = re.compile(
    r"^```\{toctree\}\s*$\n(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
FENCED_CODE = re.compile(
    r"^```[^\n]*\n(?P<body>.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)


def _yaml_scalar(path: Path, key: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.MULTILINE)
    assert match is not None, f"{path.relative_to(ROOT)} has no {key!r} field"
    return match.group(1).strip().strip('"').strip("'")


def _toctree_entries(index_text: str) -> list[str]:
    entries = []
    for match in MYST_TOCTREE.finditer(index_text):
        for raw_line in match.group("body").splitlines():
            line = raw_line.strip()
            if not line or line.startswith((":", "#")):
                continue
            titled = re.fullmatch(r".+?\s*<([^<>]+)>", line)
            entries.append((titled.group(1) if titled else line).strip())
    return entries


def test_local_markdown_links_resolve():
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
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


def test_documentation_release_metadata_is_synchronized():
    index = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    documented = re.search(
        r"This manual describes \*\*v_ase ([^*]+)\*\*\.",
        index,
    )
    assert documented is not None, "docs/index.md has no current-release declaration"
    assert documented.group(1) == __version__

    citation = ROOT / "CITATION.cff"
    assert _yaml_scalar(citation, "version") == __version__
    assert _yaml_scalar(citation, "repository-artifact") == (
        f"https://pypi.org/project/v-ase-gui/{__version__}/"
    )


def test_readthedocs_configuration_and_toctree_targets_exist():
    readthedocs = ROOT / ".readthedocs.yaml"
    conf = ROOT / "docs/conf.py"
    requirements = ROOT / "docs/requirements.txt"
    for path in (readthedocs, conf, requirements):
        assert path.is_file(), path.relative_to(ROOT)

    readthedocs_text = readthedocs.read_text(encoding="utf-8")
    assert re.search(
        r"^\s*configuration:\s*docs/conf\.py\s*$",
        readthedocs_text,
        re.MULTILINE,
    )
    assert re.search(
        r"^\s*-?\s*requirements:\s*docs/requirements\.txt\s*$",
        readthedocs_text,
        re.MULTILINE,
    )

    index_path = ROOT / "docs/index.md"
    entries = _toctree_entries(index_path.read_text(encoding="utf-8"))
    assert entries, "docs/index.md contains no MyST toctree entries"
    missing = []
    for entry in entries:
        target = entry.split("#", 1)[0]
        if not target or target == "self" or target.startswith(("http://", "https://")):
            continue
        base = index_path.parent / target
        candidates = [base]
        if not base.suffix:
            candidates.extend(
                [
                    base.with_suffix(".md"),
                    base.with_suffix(".rst"),
                    base / "index.md",
                    base / "index.rst",
                ]
            )
        if not any(candidate.is_file() for candidate in candidates):
            missing.append(target)
    assert not missing, "Missing docs/index.md toctree targets:\n" + "\n".join(missing)


def test_api_apply_examples_use_the_current_command_shape():
    api = (ROOT / "docs/api.md").read_text(encoding="utf-8")
    inline_apply_examples = []
    legacy_apply_examples = []
    for match in FENCED_CODE.finditer(api):
        body = match.group("body")
        if re.search(r"\bapply\b", body) and '"parameters"' in body:
            legacy_apply_examples.append(body)
        if "v_ase api" in body and re.search(r"\bapply\s+--params(?!-)", body):
            inline_apply_examples.append(body)
    assert not legacy_apply_examples, (
        "docs/api.md must not restore the obsolete top-level "
        "{name, parameters} apply shape:\n" + "\n\n".join(legacy_apply_examples)
    )
    assert inline_apply_examples, "docs/api.md has no inline v_ase api apply example"
    for example in inline_apply_examples:
        if '"name"' in example:
            assert '"operation"' in example, (
                "An inline apply example places name outside the current "
                "top-level operation object:\n" + example
            )


def test_scientific_binary_dependencies_follow_supported_python_abis():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = set(project["project"]["dependencies"])

    assert "numpy>=1.24,<2.0; python_version < '3.13'" in dependencies
    assert "matscipy>=1.1.1,<1.2.0; python_version < '3.13'" in dependencies
    assert "numpy>=2.0; python_version >= '3.13'" in dependencies
    assert "matscipy>=1.2.0; python_version >= '3.13'" in dependencies


def test_release_license_is_agpl_and_vendor_license_is_preserved():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    frontend = (ROOT / "v_ase/static/main.js").read_text(encoding="utf-8")

    assert project["project"]["license"] == "AGPL-3.0-or-later"
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    assert "AGPL-3.0-or-later" in readme
    assert 'href="/license"' in frontend
    assert (ROOT / "v_ase/static/vendor/THREE_LICENSE").is_file()


def test_source_distribution_includes_release_documents():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    included = {line.removeprefix("include ").strip() for line in manifest if line.startswith("include ")}
    assert {
        "README.md",
        "AGENTS.md",
        "CHANGELOG.md",
        "LICENSE",
        "requirements.txt",
    } <= included


def test_release_contract_covers_user_agent_and_rendered_docs():
    contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs/release_checklist.md").read_text(encoding="utf-8")
    for required in (
        "README.md",
        "v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md",
        "scripts/capture_readme_screenshots.py",
        "docs/assets/github/",
        "GitHub",
        "PyPI",
    ):
        assert required in contract
        assert required in checklist


def test_readme_render_assets_are_synchronized_for_github():
    source_dir = ROOT / "docs/assets"
    github_dir = source_dir / "github"
    names = {
        path.name
        for path in source_dir.iterdir()
        if path.is_file() and path.name.startswith("readme_")
    }
    assert names
    for name in sorted(names):
        source = source_dir / name
        github = github_dir / name
        assert github.exists(), name
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(
            github.read_bytes()
        ).digest(), name


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
