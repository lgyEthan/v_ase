"""Validation for the installable, vendor-neutral v_ase agent skill."""

from __future__ import annotations

import asyncio
import re
import tomllib
from pathlib import Path

from v_ase import __version__
from v_ase.ai import ai_skill_path
from v_ase.server import ai_control_schema, ai_skill


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT
    / "v_ase"
    / "skills"
    / "visualizing-atomic-structures-with-v-ase"
)
SKILL = SKILL_ROOT / "SKILL.md"
REFERENCES = SKILL_ROOT / "references"


def _frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(?P<header>.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    header = match.group("header")
    name = re.search(r"^name:\s*(.+)$", header, re.MULTILINE)
    description = re.search(r"^description:\s*(.+)$", header, re.MULTILINE)
    assert name and description
    return name.group(1).strip(), description.group(1).strip()


def _documented_skill_text() -> str:
    return "\n".join([
        SKILL.read_text(encoding="utf-8"),
        *[
            path.read_text(encoding="utf-8")
            for path in sorted(REFERENCES.glob("*.md"))
        ],
    ])


def _capability_values(source: str, key: str) -> set[str]:
    match = re.search(rf"{key}:\s*\[(?P<body>.*?)\]", source, re.DOTALL)
    assert match, f"Could not locate aiCapabilities().{key}"
    return set(re.findall(r"'([^']+)'", match.group("body")))


def test_skill_metadata_follows_discovery_contract():
    text = SKILL.read_text(encoding="utf-8")
    name, description = _frontmatter(text)

    assert name == SKILL_ROOT.name
    assert 1 <= len(name) <= 64
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
    assert "anthropic" not in name and "claude" not in name
    assert 1 <= len(description) <= 1024
    assert "<" not in description and ">" not in description
    assert description.startswith("Controls ")
    assert "Use when " in description
    assert len(text.splitlines()) <= 500


def test_skill_uses_one_level_progressive_references():
    text = SKILL.read_text(encoding="utf-8")
    linked = re.findall(r"\]\((references/[^)]+\.md)\)", text)
    assert len(linked) == 7
    assert len(linked) == len(set(linked))

    for relative in linked:
        assert relative.count("/") == 1
        path = SKILL_ROOT / relative
        assert path.is_file()
        reference = path.read_text(encoding="utf-8")
        if len(reference.splitlines()) > 100:
            assert "## Contents" in reference


def test_skill_covers_every_live_operation_and_export():
    main_js = (ROOT / "v_ase/static/main.js").read_text(encoding="utf-8")
    documented = _documented_skill_text()

    operations = _capability_values(main_js, "operations")
    exports = _capability_values(main_js, "exports")
    assert operations
    assert exports
    for value in sorted(operations | exports):
        assert f"`{value}`" in documented, value


def test_skill_version_install_and_environment_contract_are_current():
    skill_text = SKILL.read_text(encoding="utf-8")
    cli_text = (REFERENCES / "cli-and-environments.md").read_text(encoding="utf-8")
    assert f'v_ase-gui=={__version__}' in skill_text
    assert f'v_ase-gui=={__version__}' in cli_text
    for required in (
        "v_ase gui STRUCTURE --cli",
        "persistent process",
        "do **not** wait",
        "from v_ase.visualize import view",
        "No API key",
        "HOST:/",
        "--stream-frames",
        "rhino3dm",
    ):
        assert required in skill_text + cli_text


def test_skill_explains_vendor_neutral_agent_handoff():
    setup = (REFERENCES / "agent-setup.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    compatibility = (ROOT / "v_ase" / "skills_v_ase.md").read_text(encoding="utf-8")

    for required in (
        "Codex",
        "Claude Code",
        "ChatGPT desktop agents",
        "Gemini-based agents",
        "SKILL.md",
        "agent-setup.md",
        "semantic-api.md",
        "v_ase gui STRUCTURE --cli",
        "first stdout line as JSON",
        "window.v_aseAI",
        "command_url",
        "schema",
        "operation_parameters",
        "human_url",
        "events_url",
        "event_protocol",
        "event_delivery",
        "command_transport",
        "accepts_natural_language",
        "stdin_commands",
        "expectedRevision",
        "standalone `html` export",
    ):
        assert required in setup + readme + compatibility
    assert "CAD-ready" not in readme
    assert "--for-ai" not in setup + readme + compatibility
    assert "does not accept natural language itself" in readme
    assert "external agent launches" in readme.lower()
    assert "structured CLI" in readme
    assert "same live v_ase GUI" in readme
    assert "There is no natural-language endpoint and no command loop on stdin." in setup
    assert "can reduce token use" in readme


def test_skill_documents_bidirectional_same_document_collaboration():
    collaboration = (REFERENCES / "collaboration.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    evaluation = (REFERENCES / "evaluation.md").read_text(encoding="utf-8")

    for required in (
        "same live document",
        "v_ase.collaboration.v1",
        "ndjson-after-handshake",
        "source",
        "changed_paths",
        "document_revision",
        "expectedRevision",
        "state.resync-required",
        "human_url",
        '"sessionId":"EVENT_SESSION_ID"',
        "Human and external AI agent working in one live v_ase document",
        "readme_ai_collaboration.png",
        "stale-revision",
    ):
        assert required.lower() in (
            collaboration + readme + evaluation
        ).lower(), required


def test_skill_documents_offline_html_handoff_contract():
    documented = _documented_skill_text()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        '`html`',
        "view-only",
        "embedded `.vase`",
        "file://",
        "zero network requests",
        "embedProject",
        "v_ase gui FILE.html",
    ):
        assert required in documented
    assert "Export HTML View" in readme
    assert "without v_ase, Python, a server, or a CDN" in readme


def test_skill_trigger_evaluation_has_positive_and_negative_boundaries():
    evaluation = (REFERENCES / "evaluation.md").read_text(encoding="utf-8")
    assert evaluation.count("`[trigger]`") >= 10
    assert evaluation.count("`[no-trigger]`") >= 10
    for required in (
        "Structure and camera",
        "Selection and measurement",
        "Edit and constraints",
        "Periodic structure",
        "Constraints rendering",
        "Trajectory",
        "Exports",
        "Live collaboration and documents",
    ):
        assert required in evaluation


def test_skill_has_explicit_safety_and_verify_loops():
    documented = _documented_skill_text()
    for required in (
        "Plan",
        "Validate",
        "Execute",
        "Verify",
        "Never delete atoms",
        "applyConstraints: true",
        "chemicalSymbols",
        "cellOffset",
        "Do not suppress an error",
        "do not report completion",
    ):
        assert required.lower() in documented.lower()
    assert 'pivot: "active"' in documented
    assert "last explicit index" in documented


def test_runtime_and_distribution_point_to_canonical_skill():
    installed = Path(ai_skill_path())
    assert installed.name == "SKILL.md"
    assert installed.parent.name == SKILL_ROOT.name
    assert installed.read_text(encoding="utf-8").startswith("---\n")

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]["v_ase"]
    assert "skills/visualizing-atomic-structures-with-v-ase/SKILL.md" in package_data
    assert "skills/visualizing-atomic-structures-with-v-ase/references/*.md" in package_data
    assert "skills/visualizing-atomic-structures-with-v-ase/agents/*.yaml" in package_data


def test_agent_endpoints_serve_the_canonical_skill_and_schema():
    response = asyncio.run(ai_skill())
    assert response.media_type.startswith("text/markdown")
    assert response.body.decode("utf-8") == SKILL.read_text(encoding="utf-8")

    schema = asyncio.run(ai_control_schema())
    assert schema["control_schema"]["$id"].endswith(
        "/skills/visualizing-atomic-structures-with-v-ase/SKILL.md"
    )
    assert schema["protocol"] == "v_ase.ai.v1"
    assert schema["command_transport"] == "http-json-bridge"
    assert schema["command_endpoint"]["workspace"].endswith("/{workspace_id}")
    assert schema["command_endpoint"]["document"].endswith("/{session_id}")
    assert "schema" in schema["command_endpoint"]["methods"]
    assert "vector" in schema["operation_parameters"]["move-selection"]["required"]
    assert schema["operation_parameters"]["set-constraints"]["notes"].startswith(
        "kind is fixed_line or fixed_plane"
    )
    assert "embedProject" in schema["export_parameters"]["html"]["optional"]
    assert schema["accepts_natural_language"] is False
    assert schema["stdin_commands"] is False
    assert schema["collaboration"]["protocol"] == "v_ase.collaboration.v1"
    assert schema["collaboration"]["delivery"] == "ndjson-after-handshake"
    assert (
        schema["control_schema"]["properties"]["expectedRevision"]["minimum"]
        == 0
    )


def test_legacy_guide_is_a_resolving_compatibility_link():
    legacy = ROOT / "v_ase/skills_v_ase.md"
    text = legacy.read_text(encoding="utf-8")
    target = re.search(r"\]\((skills/[^)]+/SKILL\.md)\)", text)
    assert target
    assert (legacy.parent / target.group(1)).resolve() == SKILL.resolve()
