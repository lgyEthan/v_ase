# Atom colors, labels and materials

Give different colors to scientific groups, including groups of the **same
element**. Change radius, opacity and material without changing coordinates.
Start in **Appearance**; View mode is sufficient for label styling.

## Choose what to style

| Scope | Use it for |
| --- | --- |
| Element defaults | A quick conventional element-color view |
| LABEL row | Persistent groups such as substrate, surface oxide or fixed layer |
| Selected atoms | A local exception at known atom indices |
| Numeric colorscale | A continuous stored property; see [Scalar colors](scalar-colors.md) |

TYPE is the chemical element. LABEL is a visual grouping. Changing a Cu LABEL
to `Cu_substrate` keeps the atom Cu. The visualizer does not decide which atoms
are a step, substrate or active site: supply those indices or labels.

## Example: distinguish Cu surface oxide from substrate

Download {download}`cu5o4-labeled.extxyz <assets/examples/cu5o4-labeled.extxyz>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui cu5o4-labeled.extxyz
```

1. Load the input in View and open **Structure > Appearance**. Use the supplied
   {download}`group index list <assets/examples/cu5o4-groups.json>` to select
   the **32 substrate Cu atoms**; the other 5 Cu and 4 O form the surface oxide.
2. Apply LABEL `Cu_substrate` to the selected atoms. Keep TYPE `Cu` unchanged.
   The five oxide Cu atoms keep LABEL `Cu`.
3. Give substrate Cu **Metal**, white `#ffffff`, and label radius **2.00 Å**.
   Style oxide Cu with `#d4934d`, radius **1.28 Å**, and oxygen with `#d9363e`,
   radius **0.76 Å** and Rubber material. Keep the global atom-radius multiplier
   at **0.60**. Label radius values are multiplied by this global scale.
4. In **Structure > Bonding**, enable only `Cu–O_surface_oxide` at **2.25 Å**;
   disable the other pairs. Set bond thickness **0.22**, with split endpoint colors.
5. Start from a side view, then orbit toward a top view as in the GIF. Save a
   project to retain grouping and style. Coordinates and elements are unchanged.

For a related translucent-support figure, reduce substrate opacity afterward.
That is an optional variation; the recorded example uses the white metal support.

```{vase-animation} assets/readme_cu5o4_view_appearance.gif
:alt: The existing Cu5O4 demonstration separates same-element groups before styling.
:fallback: assets/readme_cu5o4_view_appearance.png

The existing Cu5O4 demonstration separates same-element groups before styling.
```


## Label-level appearance

```{figure} assets/readme_cu5o4_view_appearance.png
:alt: Cu5O4 atoms styled by label in the Appearance panel.

Different appearance groups can share the same chemical element.
```

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

Selected base-atom indices can carry persistent color, relative
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

## 3D and flat 2D rendering

```{figure} assets/readme_materials.png
:alt: The same atom layout rendered with Standard, Metal and Rubber materials.

Standard, Metal and Rubber change appearance, not atomic coordinates.
```

**3D** draws spheres, bond geometry, lighting, materials, and depth. **2D flat**
turns atoms, bonds, vectors, cell edges, and constraint guides into a
diagram-like view with adaptive outlines. Lighting and 3D material effects are
disabled in flat mode so the result is determined by colors, opacity, width,
and depth ordering.

The mode changes rendering only. Coordinates, selection, analysis, and saved
structure remain the same.

## Reusing a style

- **Export Preset** saves portable, structure-independent visual settings.
- **Import Preset** applies compatible settings to another document.
- **Set Current as Default** stores an OS-user default for new structures/tabs.
- **Restore App Defaults** requires confirmation and removes that personal
  visual default.

Personal defaults exclude coordinates, cell contents, trajectory data,
absolute camera placement, and per-atom index overrides. Use a `.vase` project
when the exact document state must be recovered.
