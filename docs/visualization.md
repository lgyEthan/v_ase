# Visualization and styling

Appearance in v_ase is layered. Element defaults establish a readable scene,
label-level settings style scientific groups, atom-index overrides handle
exceptions, and an optional scalar colorscale maps numeric per-atom data.
Projects and supported exports preserve the resolved result.

## Label and atom identity

The Appearance table separates two concepts:

- **TYPE** is the ASE chemical element used for atomic defaults and scientific
  operations.
- **LABEL** is the user-visible grouping key used for selection, appearance,
  bonds, and pairwise analysis.

Changing a LABEL does not change the element. Changing TYPE is a scientific
identity edit and should be deliberate. Labels may contain descriptive text
that is not a valid chemical symbol.

## Label-level appearance

Each label row can control:

- visibility;
- text label;
- color;
- radius scale;
- opacity; and
- material preset.

The global atom radius multiplies the label or per-atom relative scale. This
changes only drawn sphere size; it never scales coordinates or the unit cell.
Materials include the current standard, metal, and rubber-like presets and are
used consistently by compatible geometry exports.

## Per-atom overrides

In 0.2.35, selected base-atom indices can carry persistent color, relative
radius, opacity, and material overrides. Apply controls are field-scoped: an
opacity edit need not replace a custom color or material already assigned to
the same indices.

Index overrides are appropriate for local defects or highlighted sites. Use a
new label instead when the identity should remain meaningful after atom
reordering or across trajectories with changing topology. Compatible frames
can retain index overrides; incompatible indices are pruned rather than
silently remapped.

**Selected appearance affects bonds** lets connected bond segments inherit
selected atoms' material/opacity behavior. It is enabled by default.

## Numeric colorscales

Per-atom colorscales can use:

- Cartesian `x`, `y`, or `z` coordinates;
- stored force magnitude or components;
- numeric ASE per-atom arrays;
- already stored per-atom calculator results.

The GUI's selected scope follows the live selection. Automation can attach an
explicit index list to a selected-scope colorscale when the subset must remain
fixed while the researcher changes the GUI selection.

Vector and compact tensor arrays expose a norm and components. Inspecting a
stored force or property never runs the attached calculator. If a value is not
already present, it is unavailable rather than being calculated as a side
effect.

The current-frame fit resolves one value range and holds it during ordinary
playback. A deliberate full-trajectory scan streams frames to obtain global
extrema without allocating one complete value cube. Manual minimum/maximum,
reverse, and gamma contrast remain available.

All Matplotlib colormaps installed in the active Python environment are
available. Custom maps contain 2–64 positioned hexadecimal color stops and can
use continuous interpolation or discrete bands. Their definition, resolved
range, and playback behavior are stored in projects and standalone HTML.

## Bonds

Bond visibility and bond appearance are separate from physical constraints or
calculator connectivity.

### Topology modes

- Automatic mode infers contacts from element/covalent information and the
  active cutoff scale.
- Label-pair mode uses explicit enabled/cutoff records for each label pair.
- Manual bonds preserve explicitly selected pairs.

Periodic bonds can be shown across cell boundaries. Export uses the same
minimum-image topology and, for skewed cells, ASE's exact minimum-image
resolution rather than component-wise fractional rounding.

### Appearance

Global or label-pair settings can control:

- cylinder or flat shape;
- thickness;
- material;
- opacity; and
- split-by-atom or custom color.

Version 0.2.35 adds independent thickness to each label-pair row. Pair records
are preserved by `.vase`, project/view HTML, Blender, OBJ, and 3DM output.
Visual bond cutoffs and repulsive-calculator contact distances are configured
separately; a drawn bond is not an energy model.

## 3D and flat 2D rendering

**3D** draws spheres, bond geometry, lighting, materials, and depth. **2D flat**
turns atoms, bonds, vectors, cell edges, and constraint guides into a
diagram-like view with adaptive outlines. Lighting and 3D material effects are
disabled in flat mode so the result is determined by colors, opacity, width,
and depth ordering.

The mode changes rendering only. Coordinates, selection, analysis, and saved
structure remain the same.

## Camera and projection

Orthographic projection is the default for new documents and avoids perspective
size distortion. Perspective is useful when spatial depth is part of the
composition. Axis alignment and toolbar orbit/tilt actions operate relative to
the current camera orientation, so their screen direction remains predictable
after arbitrary camera motion.

Camera navigation is not added to Undo/Redo history. Exact export composition
belongs to the persistent Render Area described in
[Projects, rendering, and export](projects-export.md).

## Cell, axes, grid, and overlays

The unit cell has independent color, thickness, and material. Displayed
supercell edges are deduplicated so shared boundaries do not darken. Axes, grid,
measurements, constraint guides, insertion regions, stored force vectors, and
analysis overlays can be included or excluded from the viewport and export
composition as supported by each output.

`display.supercell` and visual translation are presentation settings. They do
not build a physical repeated ASE object or change atom coordinates. See
[Periodic cells and interfaces](periodic-interfaces.md) before exporting a
structure expected to contain repeated atoms.

## Lighting, quality, and theme

Viewport quality controls include antialiasing and atom smoothness. Lighting
supports the current modeling/studio choices, a user-controlled Sun, and
shadowed rendering where available. A scene using only standard/rubber
materials does not allocate the metal reflection environment.

The **System** interface theme follows the browser/OS preference. Explicit
Light or Dark persists in that browser. Interface theme and viewport background
are distinct settings, although explicit Dark selects a matching dark viewport
for a coherent starting point.

## Reusing a style

- **Export Preset** saves portable, structure-independent visual settings.
- **Import Preset** applies compatible settings to another document.
- **Set Current as Default** stores an OS-user default for new structures/tabs.
- **Restore App Defaults** requires confirmation and removes that personal
  visual default.

Personal defaults exclude coordinates, cell contents, trajectory data,
absolute camera placement, and per-atom index overrides. Use a `.vase` project
when the exact document state must be recovered.
