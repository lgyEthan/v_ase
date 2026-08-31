# What is new in 0.2.35a1+symmetry

This experimental build synchronizes the symmetry branch with v_ase 0.2.35
and adds crystal-symmetry analysis, independent-site and tolerance reporting,
primitive/conventional/refined cell operations, HPKOT paths,
symmetry-reduced finite-displacement inputs, completed Phonopy project loading,
interactive phonon dispersion selection, and commensurate mode trajectories.

Mode displacement arrows are anchored at the unperturbed phonon-equilibrium
sites, so their direction and phase have a direct physical interpretation.

## Inherited from main 0.2.35

Version 0.2.35 focuses on precise per-atom and bond appearance together with
more usable dense scientific controls.

## Versioned documentation

The complete user, integration, semantic-agent, scientific-validation, and
maintainer manual now builds with Sphinx/MyST on Read the Docs. HTML, external
links, PDF, and ePub are validated from the same sources. The repository README
is a concise starting page; detailed workflows and reproducible fixtures live
in this versioned guide.

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
[complete changelog](https://github.com/lgyEthan/v_ase/blob/symmetry/CHANGELOG.md).
