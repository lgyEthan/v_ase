"""Validation for the installable, vendor-neutral v_ase agent skill."""

from __future__ import annotations

import asyncio
import re
import tomllib
from pathlib import Path

from ase.io import read

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
        "scikit-image",
        "Plotly",
        "CHGCAR",
        "qe-cube",
    ):
        assert required in skill_text + cli_text


def test_skill_explains_vendor_neutral_agent_handoff():
    documented = " ".join(_documented_skill_text().split())
    setup = (REFERENCES / "agent-setup.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    compatibility = (ROOT / "v_ase" / "skills_v_ase.md").read_text(encoding="utf-8")

    for required in (
        "Codex",
        "Claude Code",
        "GitHub Copilot",
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
    readable_readme = " ".join(readme.split())
    assert "CAD-ready" not in readme
    assert "--for-ai" not in setup + readme + compatibility
    assert "You describe the scientific result to an external AI Agent" in readable_readme
    assert "the Agent uses the Skill and structured CLI/API" in readable_readme
    assert "the result appears in the same live GUI" in readable_readme
    assert "A manual GUI edit becomes the next document revision" in readable_readme
    assert "There is no natural-language endpoint and no command loop on stdin." in setup
    assert "`viewportBackground` controls the interactive GUI only" in documented
    assert "terminate the persistent CLI process while the human GUI is still open" in documented
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

    assert "pristine 6 x 6 graphene" in collaboration
    assert "preserve PBC" not in collaboration


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
    workflows = (REFERENCES / "workflows-and-examples.md").read_text(encoding="utf-8")
    assert 'embedProject: false' in workflows
    assert "`hasEmbeddedProject` is false" in workflows
    assert 'embedProject: true' in workflows
    assert "a nonzero `.vase` download" in workflows
    assert "Export HTML View" in readme
    assert "without v_ase, Python, a server, or a CDN" in readme


def test_skill_defines_auto_notebook_mode_and_revision_discovery():
    skill = SKILL.read_text(encoding="utf-8")
    environments = (REFERENCES / "cli-and-environments.md").read_text(encoding="utf-8")
    assert "%v_ase auto" in skill
    assert "restores automatic active-kernel" in (skill + environments)
    source = (ROOT / "v_ase" / "static" / "main.js").read_text(encoding="utf-8")
    assert "'expectedRevision', 'frame'" in source


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
        "Volumetric and RDF analysis",
        "Exports",
        "Live collaboration and documents",
    ):
        assert required in evaluation


def test_skill_trajectory_workflow_names_a_real_multiframe_fixture():
    relative = Path("examples/readme_scene_assets/crowded_c60_relaxation.traj")
    documented = _documented_skill_text()

    assert relative.as_posix() in documented
    frames = read(ROOT / relative, index=":")
    assert len(frames) == 42


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
    assert schema["operation_parameters"]["load-volumetric"]["required"] == ["path"]
    assert "precision" in schema["operation_parameters"]["load-volumetric"]["optional"]
    assert schema["operation_parameters"]["show-volumetric"]["required"] == [
        "datasetId",
        "level",
    ]
    assert {
        "smearingSigma",
        "smoothingIterations",
    }.issubset(schema["operation_parameters"]["show-volumetric"]["optional"])
    operation_object = schema["control_schema"]["properties"]["operation"]["oneOf"][1]
    show_schema = next(
        item["then"]
        for item in operation_object["allOf"]
        if (
            item["if"]["properties"]["name"].get("const")
            == "show-volumetric"
        )
    )
    show_properties = show_schema["properties"]
    assert show_schema["required"] == ["datasetId", "level"]
    assert show_properties["surfaceMode"]["enum"] == ["single", "signed"]
    assert show_properties["stepSize"]["enum"] == [1, 2, 4]
    assert show_properties["smearingSigma"] == {
        "type": "number",
        "minimum": 0,
        "maximum": 8,
    }
    assert show_properties["smoothingIterations"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 30,
    }
    assert show_properties["opacity"] == {
        "type": "number",
        "minimum": 0.05,
        "maximum": 1,
    }
    assert show_properties["positiveColor"]["pattern"] == "^#[0-9A-Fa-f]{6}$"
    assert schema["operation_parameters"]["combine-volumetric"]["required"] == [
        "datasetIds",
        "coefficients",
    ]
    assert "precision" in schema["operation_parameters"]["combine-volumetric"]["optional"]
    assert {
        "cutoff",
        "bins",
        "pairMode",
        "activePairs",
    }.issubset(schema["operation_parameters"]["calculate-rdf"]["optional"])
    assert schema["operation_parameters"]["rotate-to-commensurate"]["required"] == [
        "angleDeg",
        "selection-or-indices",
    ]
    assert {
        "maxAreaRatio",
        "strainTolerance",
        "maxAngleDifferenceDeg",
        "showAtoms",
    }.issubset(
        schema["operation_parameters"]["rotate-to-commensurate"]["optional"]
    )
    assert schema["operation_parameters"]["apply-commensurate-cell"]["mode"] == "edit"
    assert schema["operation_parameters"]["load-commensurate-guest"]["required"] == [
        "path"
    ]
    assert {
        "strainTarget",
        "strainTolerance",
        "maxAreaRatio",
        "angleDeg",
        "gap",
        "showAtoms",
    }.issubset(
        schema["operation_parameters"]["load-commensurate-guest"]["optional"]
    )
    assert {
        "mode",
        "strainTarget",
        "strainTolerance",
        "maxAreaRatio",
        "angleDeg",
        "gap",
        "showAtoms",
        "snap",
    }.issubset(
        schema["operation_parameters"]["calculate-commensurate"]["optional"]
    )
    assert schema["operation_parameters"]["calculate-registry-map"]["required"] == [
        "selection-or-indices"
    ]
    assert schema["operation_parameters"]["calculate-registry-map"]["optional"] == [
        "indices",
        "metric",
        "gridX",
        "gridY",
        "pairCutoffs",
    ]
    assert schema["operation_parameters"]["set-interface-theme"] == {
        "mode": "view-or-edit",
        "required": ["theme"],
        "optional": [],
        "notes": schema["operation_parameters"]["set-interface-theme"]["notes"],
    }
    assert schema["operation_parameters"]["set-personal-visual-default"]["mode"] == (
        "view-or-edit"
    )
    assert schema["operation_parameters"]["restore-app-visual-defaults"]["required"] == [
        "confirm"
    ]
    operation_names = operation_object["properties"]["name"]["enum"]
    assert {
        "set-interface-theme",
        "set-personal-visual-default",
        "restore-app-visual-defaults",
    }.issubset(operation_names)
    restore_schema = next(
        item["then"]
        for item in operation_object["allOf"]
        if (
            item["if"]["properties"]["name"].get("const")
            == "restore-app-visual-defaults"
        )
    )
    assert restore_schema["required"] == ["confirm"]
    assert restore_schema["properties"]["confirm"] == {"const": True}
    assert schema["export_parameters"]["rdf-csv"]["optional"] == [
        "cutoff",
        "bins",
        "pairMode",
        "activePairs",
    ]
    assert "maxAreaRatio" in schema["export_parameters"]["commensurate-csv"]["optional"]
    assert schema["export_parameters"]["registry-csv"]["optional"] == [
        "indices",
        "metric",
        "gridX",
        "gridY",
        "pairCutoffs",
    ]
    assert schema["accepts_natural_language"] is False
    assert schema["stdin_commands"] is False
    assert schema["collaboration"]["protocol"] == "v_ase.collaboration.v1"
    assert schema["collaboration"]["delivery"] == "ndjson-after-handshake"
    assert (
        schema["control_schema"]["properties"]["expectedRevision"]["minimum"]
        == 0
    )


def test_skill_documents_volumetric_and_rdf_end_to_end_contracts():
    documented = _documented_skill_text()
    for required in (
        "`load-volumetric`",
        "`show-volumetric`",
        "`combine-volumetric`",
        "`remove-volumetric`",
        "`calculate-rdf`",
        "`rdf-csv`",
        "analysis.volumetricDatasets",
        "identical dimensions, cell, origin, PBC",
        "`periodicImageSpan`",
        "fixed `2 x 2 x 2`",
        "FP32",
        "FP64",
        "smearingSigma",
        "smoothingIterations",
        "display copy",
        "cell-boundary vertices",
        "analysis.volumetricSurface",
        "partialSignedSurface",
        "2,000,000",
        "concentration-weighted",
        "fully periodic 3D",
        "V_ASE_MAX_VOLUMETRIC_POINTS",
    ):
        assert required in documented, required


def test_skill_documents_commensurate_and_registry_end_to_end_contracts():
    documented = _documented_skill_text()
    normalized = " ".join(documented.split())
    for required in (
        "`load-commensurate-guest`",
        "`remove-commensurate-guest`",
        "`calculate-commensurate`",
        "`rotate-to-commensurate`",
        "`apply-commensurate-cell`",
        "`dismiss-commensurate-cell`",
        "`calculate-registry-map`",
        "`commensurate-csv`",
        "`registry-csv`",
        "maxAreaRatio",
        "default `maxAreaRatio` of 16",
        "Paper strain projection",
        "max principal strain",
        "mean absolute strain",
        "actual host-plus-guest atom count",
        "examples/commensurate_host_guest",
        "1..128",
        "global Z",
        "cells-only",
        "one-primitive-cell boundary shell",
        "geometry scores, not energies",
        "icon-only CSV",
        "CellMatch",
        "Stradi",
    ):
        assert required in documented or required in normalized, required


def test_legacy_guide_is_a_resolving_compatibility_link():
    legacy = ROOT / "v_ase/skills_v_ase.md"
    text = legacy.read_text(encoding="utf-8")
    target = re.search(r"\]\((skills/[^)]+/SKILL\.md)\)", text)
    assert target
    assert (legacy.parent / target.group(1)).resolve() == SKILL.resolve()
