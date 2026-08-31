# What is new in 0.2.35

Version 0.2.35 focuses on precise per-atom and bond appearance together with
more usable dense scientific controls.

## Versioned documentation

The complete user, integration, semantic-agent, scientific-validation, and
maintainer manual now builds with Sphinx/MyST on Read the Docs. Its sidebar is
organized into four task-oriented hubs. The atomistic home-page logo is an
interactive WebGL scene aligned exactly along +Z, while scientific application
examples use their exact PNG/GIF captures so isosurfaces, plots, constraints,
and GUI overlays cannot disappear in a lightweight viewer. HTML, external
links, PDF, and ePub are validated from the same sources. The repository
README retains the GIF-rich visual workflow tour, while this versioned guide
remains the separate searchable reference for detailed workflows and
reproducible fixtures.

The semantic bridge also rejects unknown top-level apply fields and keeps its
colorscale, staged-relaxation, registry, export, and workspace/document
discovery schemas synchronized with the canonical Agent Skill.

## Atom-index overrides

Selected atom indices can now carry persistent overrides for:

- color;
- relative radius;
- opacity; and
- material.

Each field has scoped Apply behavior, so changing one property does not erase
other index-level overrides. Compatible trajectory frames retain the same
index mapping. Connected bonds can follow the selected atoms' material and
opacity; this behavior is enabled by default.

## Label-pair bond thickness

Each label-pair row can independently set bond thickness in addition to its
enabled state, distance cutoff, shape, material, color, and opacity. The same
result is preserved in projects, standalone HTML, Blender, OBJ, and optional
3DM output.

## Selection consistency

Shift-click, Shift-box, and `Shift+Ctrl+A` consistently invert membership in
the existing selection. This replaces the former add-only behavior in affected
paths and makes click, box, and select-all modifiers agree.

## Dense dialog and appearance layout

Long dialogs now scroll while keeping their action rows visible. The default
scratch insertion region starts centered, and Appearance uses a single
horizontal table with a fixed TYPE column instead of wrapping rows.

For changes from earlier versions, read the
[complete changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md).
