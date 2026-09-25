# Atom colors, labels and materials

Give different colors to scientific groups, including groups of the **same
element**. Change radius, opacity and material without changing coordinates.
Start in **Style → Atoms**; View mode is sufficient for label styling.

## Choose what to style

| Scope | Use it for |
| --- | --- |
| Element defaults | A quick conventional element-color view |
| LABEL row | Persistent groups such as substrate, surface oxide or fixed layer |
| Selected atoms | Immediately split and style the selected group |
| Numeric colorscale | A continuous stored property; see [Scalar colors](scalar-colors.md) |
| Property radius mapping | A separate multiplicative size factor from an actual numeric field |

TYPE is the chemical element. LABEL is a visual grouping. Changing a Cu LABEL
to `Cu_substrate` keeps the atom Cu. The visualizer does not decide which atoms
are a step, substrate or active site: supply those indices or labels.

## Example: distinguish Cu surface oxide from substrate

Download {download}`cu5o4-labeled.extxyz <assets/examples/cu5o4-labeled.extxyz>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui cu5o4-labeled.extxyz
```

1. Load the input in View and open **Style → Atoms**. Use the supplied
   {download}`group index list <assets/examples/cu5o4-groups.json>` to select
   the **32 substrate Cu atoms**; the other 5 Cu and 4 O form the surface oxide.
2. Apply LABEL `Cu_substrate` to the selected atoms. Keep TYPE `Cu` unchanged.
   The five oxide Cu atoms keep LABEL `Cu`.
3. Give substrate Cu **Metal**, white `#ffffff`, and label radius **2.00 Å**.
   Style oxide Cu with `#d4934d`, radius **1.28 Å**, and oxygen with `#d9363e`,
   radius **0.76 Å** and Rubber material. Keep the global atom-radius multiplier
   at **0.60**. Label radius values are multiplied by this global scale.
4. In **Style → Bonds**, enable only `Cu–O_surface_oxide` at **2.25 Å**;
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
- radius in Å (before the global size and property multipliers);
- opacity; and
- material preset.

The global atom radius multiplies the label or per-atom relative scale. This
changes only drawn sphere size; it never scales coordinates or the unit cell.
Materials include the current standard, metal, and rubber-like presets and are
used consistently by compatible geometry exports.

## Property radius mapping

For a step-by-step setup, presets, scope and range semantics, see
[Size atoms from a numeric property](property-radius.md).

Under **Style → Atoms**, the global-size slider has an editable number.
Enable **Property radius mapping** and choose a field from the live scalar
catalog. Coordinate fields, numeric ASE arrays and already stored calculator
results are distinct sources; a serialized initial charge is not a substitute
for a calculator charge descriptor. Choose identity or absolute magnitude,
then lock a current-frame or full-trajectory input range. The output minimum,
maximum and exponent turn the normalized value into a multiplicative size
factor. The occupancy presets are explicit choices and do not infer an absent
occupancy array. Custom and charge presets fit the finite values in the current
frame and current scope; an invalid or empty numeric edit leaves the prior
mapping intact. **Frozen selected atoms** stores their base indices; later
selection changes do not change the radius scope. Duplicating a scoped atom
includes its duplicate, deleting atoms remaps surviving indices, and making an
editable supercell repeats the source-atom scope. Changing only a label keeps
the scope; replacing the document with unrelated atoms clears it.

The mapping multiplies label radius × global size × manual per-atom multiplier.
Missing values and atoms outside the frozen scope use factor 1. A factor of 0
removes the visible glyph but leaves the scientific atom and bonding policy
intact. A request to set a positive final radius in Å on a zero-factor atom
fails explicitly until its mapping is changed or disabled. Mapping is stored
in `.vase`, and frame-specific factors are included in offline HTML, video,
Blender, OBJ/3DM geometry and cell-match previews. Verify the actual rendered
artifact when publishing a mapped-size figure.
Optimizer/relaxation frames use their displayed positions for coordinate
mapping. If a stored per-atom property was not recorded for those frames, the
editor explicitly uses neutral factor 1 instead of borrowing values from the
loaded source trajectory.

(per-atom-overrides)=
## Live selected appearance

The **Selected atoms** controls apply immediately in View and Edit; there is
no Apply button. Enter a new label and press Enter or leave the field to split
that group. Escape cancels an uncommitted label draft. If you edit color,
material, opacity or radius first, v_ase creates `Element_2`, incrementing the
suffix until unused. Mixed elements or existing styles receive separate labels.
The same label rows immediately show color, material, opacity and the resulting
radius in Å. A radius multiplier is folded into that label radius, avoiding a
second hidden size override. The global size and property mapping still apply.

Undo reverses the first split and its first appearance gesture together. Later
adjustments each have normal undo/redo. Entering an existing label asks whether
to merge; **Yes, merge** inherits its color, radius, opacity, material, visibility
and bond settings. Chemical elements and coordinates stay unchanged. A later
selected-only change separates that subset again, preserving unselected atoms.
Edit-mode label changes follow base indices across source frames, skipping absent
indices; changing mode alone preserves the other frames' elements and labels.
View-mode label edits on incompatible trajectories remain local to that frame.

**Selected appearance affects bonds** links selected atoms' material/opacity
to connected bond segments. It is enabled by default. The semantic API also
continues to accept explicit per-index overrides for automated workflows and
older projects; these are distinct from the GUI's new label-based workflow.

## 3D and flat 2D rendering

```{figure} assets/readme_materials.png
:alt: The same atom layout rendered with Standard, Metal and Rubber materials.

Standard, Metal and Rubber change appearance, not atomic coordinates.
```

**3D** draws spheres, bond geometry, lighting, materials, and depth. **2D flat**
turns atoms, bonds, vectors, cell edges, and constraint guides into a
diagram-like view with adaptive outlines. Lighting and 3D material effects are
disabled, including their controls, in flat mode so the result is determined by colors, opacity, width,
and depth ordering.

Fixed atoms use sharp crossed strokes. In **Objects**, toggle **Constraints**
to show or hide constraint marks in the viewport and exports; this does not
change constraint enforcement.

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

## Bond pair editing

**Style → Bonds** opens **Pair specifications** by default. Each label pair has
an enable checkbox and a maximum distance in Å. **Reset to suggested cutoffs**
restores element-radius-derived suggestions; **Manual index pairs** remains
available for explicitly chosen edges. There is no separate Automatic radii
choice in this GUI. Existing automatic project settings are converted into
editable suggested pairs, preserving their cutoff multiplier. Guest-only labels
in a cell-match preview use their own suggested distances until they enter the
document's editable pair table; existing configured pairs remain unchanged.

Click a cutoff and press Ctrl+A (also supported on Mac) or Command+A on Mac
to replace the whole value. Tab moves to the next cutoff; Shift+Tab moves to
the previous one. Resize the label column with its divider or widen the entire
right panel. Controls reflow within the available width. The relaxation
calculator's pair distances are independent of these displayed bonds.

## Read the Atoms panel

**Style → Atoms** groups global size, per-label appearance, surface material,
selected-atom overrides, and property visualization separately. The per-label
editor is a table with one row per label: label, color, visibility, selection,
element, radius in Å, opacity, material and count. Scroll it horizontally to
reach additional columns, or widen the floating inspector. Its label column
stays visible while scrolling. Selected-atom overrides remain a separate scope;
property mappings multiply manual radii or replace colors at their fixed targets.

Long label and bond tables scroll within their own borders. Their column headers
stay flush with the top edge while rows move underneath; the label column stays
visible during horizontal scrolling. Relaxation cutoff tables use the same
header treatment.

## Colorscale targets and single-atom data

**Apply to** offers **All atoms**, **Selected atoms**, and the document's labels.
Selected atoms captures the current base indices; **Use current selection** is
an explicit button below the selector to replace them. Selecting a label captures
its current indices using the same semantics. This does not add any FixAtoms
constraint. Targets do not follow later GUI selections or changing element names.
Shorter trajectory frames skip absent indices without deleting them, including
when saved and reopened on a shorter frame. Offline HTML uses these saved targets,
not the atoms currently highlighted in the editor.

The property catalog loads in advance. Stored scalar values and optional color
palettes are fetched only when needed; unchanged catalogs preserve the dropdown's
options rather than rebuilding them during interaction.

Select one atom to see its current label, Cartesian XYZ, and stored properties
in the bottom status strip. Custom arrays, including `existence`, and stored
calculator results such as forces appear there; intrinsic element, mass, and
fractional-coordinate fields are omitted. The strip scrolls for long values and
its text can be selected and copied. Full ASE attributes remain available through
the atom-properties API.

Hold Shift when adding atoms to a measurement; picks pass through the bottom
readout so it cannot intercept a nearby atom. Release Shift to scroll or copy
property text.
