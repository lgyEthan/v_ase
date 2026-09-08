# Volumetric planes

Cut a scalar field with a crystallographic plane and color the sampled values.
Use **Analysis > Volumetric Data > Planes**. Plane parameters work in View;
Edit additionally provides `G`/`R` viewport transforms.

## Example: move a section through the graphene field

Download {download}`graphene-pi.cube <assets/examples/graphene-pi.cube>`. Open it and select the dataset.

1. Hide isosurfaces to expose the plane. Add an **hkl = (1, 0, 0)** section.
2. Choose `coolwarm`, opacity **0.84**, and resolution **1024**. Set a fixed
   symmetric color range at ±30% of the field's maximum absolute value.
3. Drag the offset slider through the cell. The plane is clipped to the cell;
   its color changes because it samples a different part of the same field.
4. In Edit, select the plane and press `G` to move along its own normal.
   Press `R` to change its orientation. Confirm or cancel as for atom transforms.
5. Compare the live offset/hkl readout with the plane list before saving.

```{vase-animation} assets/readme_volumetric_plane.gif
:alt: A moving crystallographic section through the analytic graphene field.
:fallback: assets/readme_volumetric_plane.png

A moving crystallographic section through the analytic graphene field.
```


## Add planar sections

Open **Analysis > Volumetric Data > Planes** and choose **Add Plane**. Each
plane contains:

- stable ID and editable name;
- dataset ID and visibility;
- a nonzero reciprocal-space `(h k l)` normal;
- signed distance from the stored grid origin in angstrom;
- settled resolution of 128, 256, 512, or 1024;
- a registered Matplotlib colormap and reverse state;
- automatic or manual `vmin`/`vmax`; and
- opacity.

`(h k l)` defines a Cartesian normal using the reciprocal cell. `[0,0,0]` is
invalid. The distance is measured from the dataset's stored grid origin along
that unit normal, not from an atom, selection, or inferred cell center. If no
offset is supplied, v_ase centers the plane in the displayed cell/supercell.

The backend clips the section to the exact orthogonal or triclinic displayed
cell and samples it with periodic trilinear interpolation. Only the compact 2D
raster and clipping polygon reach the browser; displayed supercells do not
materialize a repeated 3D grid.

![Cell-clipped hkl scalar-field plane](assets/readme_volumetric_plane.png)

### Edit one or several planes

Select plane rows with click or Shift-click. Shared values remain visible;
mixed values are blank until a common replacement is entered. One edit is
applied atomically to every selected ID. An unknown ID, zero normal,
unsupported resolution/colormap, opacity outside its range, or manual
`vmin >= vmax` rejects the complete edit.

Use **Fit Selected** to resolve the range from the selected plane data. Use a
fixed manual range when several planes must remain directly comparable.

### View and Edit mode behavior

Planes can be created and configured in View. This changes only analysis and
display state, never ASE atom coordinates.

In Edit, a selected plane can also be manipulated in the viewport:

- `G` moves each selected plane along its own normal; and
- `R`, optionally locked with `X`, `Y`, or `Z`, changes the normal and `(hkl)`.

The distance, slider, `(hkl)` fields, and list label follow the live transform.
Interactive motion uses a lower-resolution preview, then restores the
configured settled resolution. A newly typed `(hkl)` becomes authoritative
immediately even if an older high-resolution request is still pending.
