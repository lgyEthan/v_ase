"""Small, transport-independent tool discovery and workflow excerpts."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

GUIDE_TOPICS = {
    "skill": None,
    "scene": "scene-workflow.md",
    "rendering": "deterministic-rendering.md",
    "structures": "structures.md",
    "polyhedra": "polyhedra.md",
    "trajectories": "trajectories.md",
    "volumetric": "volumetric.md",
    "rdf": "rdf.md",
    "interfaces": "interfaces.md",
    "insertion": "insertion.md",
    "constraints": "constraints.md",
    "exports": "exports.md",
    "collaboration": "collaboration.md",
    "setup": "native-tools.md",
    "errors": "safety-and-errors.md",
}

CORE_TOOL_NAMES = frozenset({
    "vase_scene_snapshot", "vase_style_scene", "vase_search_tools", "vase_tool_schema", "vase_read_guide",
    "vase_render", "vase_inspect_image", "vase_describe", "vase_ready",
    "vase_documents", "vase_activate", "vase_events",
})

SEARCH_PROPERTIES = {
    "query": {"type": "string", "minLength": 1, "maxLength": 160,
              "description": "A feature phrase or exact vase tool name. Search names and the tool's own description, never host namespace boilerplate."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
}
TOOL_SCHEMA_PROPERTIES = {
    "names": {"type": "array", "items": {"type": "string", "minLength": 1},
              "minItems": 1, "maxItems": 4, "uniqueItems": True},
}
GUIDE_PROPERTIES = {
    "topic": {"enum": list(GUIDE_TOPICS)},
    "section": {"type": "string", "maxLength": 160,
                "description": "Optional exact Markdown heading. The response lists available headings when it cannot find the section."},
    "offset": {"type": "integer", "minimum": 0, "default": 0},
    "maxCharacters": {"type": "integer", "minimum": 512, "maximum": 12000, "default": 5000},
    "expectedSha256": {"type": "string", "pattern": "^[0-9a-f]{64}$",
                       "description": "Use the prior page's hash while paging an excerpt."},
}

_SYNONYMS = {
    "screenshot": {"render", "scene"}, "figure": {"scene", "render"},
    "hide": {"display"}, "color": {"colorscale", "style", "display"},
    "colours": {"colorscale", "style"}, "movie": {"video", "playback"},
    "trajectory": {"frame", "playback", "displacements"},
    "density": {"volumetric"}, "isosurface": {"volumetric"},
    "slice": {"plane"}, "section": {"plane"},
    "repulsion": {"scatter", "calculator", "insertion"},
    "random": {"scatter"}, "homogeneous": {"scatter"},
    "rdf": {"rdf"}, "commensurate": {"commensurate", "registry"},
    "polyhedra": {"polyhedra", "coordination"}, "octahedron": {"polyhedra"},
    "constraint": {"constraints"}, "save": {"export"},
}

GROUP_DESCRIPTIONS = {
    "scene": "Atomic figure appearance, camera, framing and selection.",
    "fields": "Volumetric scalar fields, sections, surfaces and colormaps.",
    "trajectory": "Trajectory frames, playback, stored atomic properties and vectors.",
    "interfaces": "Commensurate lattices, supercell proposals and registry analysis.",
    "insertion": "Atomic and molecular placement, repulsion and staging lifecycle.",
    "constraints": "Scientific constraints, calculators and relaxation.",
    "exports": "Render images and export geometry, projects, movies or analysis tables.",
    "analysis": "Radial distribution and structural measurements.",
    "workspace": "Documents, files, connection state and collaboration events.",
    "structures": "Build and edit physical atomic structures and cells.",
}


def tool_group(spec):
    """Small searchable native namespaces; tools keep their globally unique names."""
    name = spec.name
    for group, markers in (
        ("exports", ("export_", "vase_render", "inspect_image")),
        ("interfaces", ("commensurate", "registry")),
        ("insertion", ("scatter", "add_atoms", "insertion", "molecule_catalog")),
        ("constraints", ("constraint", "calculator", "relaxation")),
        ("fields", ("volumetric", "colormap")),
        ("trajectory", ("frame", "playback", "scalar", "force_vector", "displacement", "atom_properties")),
        ("analysis", ("rdf", "measure")),
        ("scene", ("scene", "display", "camera", "render_area", "quality", "bonds", "selection", "compose_view")),
        ("workspace", ("document", "vase_files", "vase_ready", "vase_activate", "vase_events", "capabilities", "settings")),
    ):
        if any(marker in name for marker in markers):
            return group
    return "structures"


def search_catalog(catalog, query: str, limit=4):
    words = set(re.findall(r"[a-z0-9]+", query.lower())) - {"vase", "ase", "v", "tools", "tool"}
    if not words:
        return {"tools": [], "totalMatches": 0,
                "hint": "Use a feature such as scene, bonds, volumetric plane, RDF or an exact tool name."}
    exact = query.strip().lower().replace("-", "_")
    if "__" in exact:
        exact = exact.rsplit("__", 1)[-1]
    if not exact.startswith("vase_"):
        exact = "vase_" + exact
    expansions = set().union(*(_SYNONYMS.get(word, set()) for word in words))
    scored = []
    for name, spec in catalog.items():
        tokens = set(re.findall(r"[a-z0-9]+", name.lower())) - {"vase"}
        description = set(re.findall(r"[a-z0-9]+", spec.description.lower()))
        score = (1000 if exact == name else 0) + 20 * len(words & tokens)
        score += 8 * len(expansions & tokens) + len(words & description)
        if score:
            # Reward matching a whole multiword feature, then prefer a short name.
            score += 12 if words <= tokens else 0
            scored.append((-score, len(tokens), name))
    scored.sort()
    matches = []
    for _, _, name in scored[:limit]:
        spec = catalog[name]
        description = re.sub(r"^\S+\. Mode: [^.]+\. ", "", spec.description)
        matches.append({"name": name, "description": description.split(". ", 1)[0][:240],
                        "mutates": spec.mutates, "method": spec.method})
    return {"tools": matches, "totalMatches": len(scored), "limit": limit,
            "next": "Call an available tool directly; request vase_tool_schema only if its typed schema has not been loaded."}


def read_guide(skill_path, topic, *, section=None, offset=0, max_characters=5000,
               expected_sha256=None):
    root = Path(skill_path).parent
    name = GUIDE_TOPICS[topic]
    path = root / "references" / name if name else Path(skill_path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError("Guide changed while paging. Restart at offset 0.")
    text = raw.decode("utf-8")
    headings = [(m.start(), len(m[1]), m[2].strip())
                for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE)]
    if section:
        match = next((h for h in headings if h[2].casefold() == section.strip().casefold()), None)
        if match is None:
            return {"topic": topic, "sha256": digest, "sectionFound": False,
                    "headings": [h[2] for h in headings], "text": ""}
        end = next((h[0] for h in headings if h[0] > match[0] and h[1] <= match[1]), len(text))
        text = text[match[0]:end]
    excerpt = text[offset:offset+max_characters]
    end = offset + len(excerpt)
    return {"topic": topic, "section": section, "sha256": digest,
            "text": excerpt, "offset": offset, "characters": len(excerpt),
            "totalCharacters": len(text), "nextOffset": end if end < len(text) else None,
            "truncated": end < len(text)}
