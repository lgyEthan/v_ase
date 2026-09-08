# Import and process scalar fields

Inspect grid geometry, precision and integrals, or combine compatible fields.
Use **Analysis > Volumetric Data** after opening Cube, CHGCAR or another supported
field. Choose [Isosurfaces](isosurfaces.md) or [Planes](field-planes.md) for display.

## Supported inputs

Open these directly or add them to an existing document:

- VASP `CHG`/`CHGCAR` charge density;
- VASP `PARCHG` partial density;
- VASP `LOCPOT` potential;
- VASP `ELFCAR` electron-localization field;
- Gaussian Cube; and
- XSF `DATAGRID_3D`, including Quantum ESPRESSO `pp.x` exports.

VASP stems accept `.`, `_`, or `-` calculation suffixes, including
`PARCHG_band_12`, `LOCPOT.vacuum`, and `CHGCAR-difference`. Use an explicit
reader for an ambiguous filename:

```bash
v_ase gui GRID --format CHGCAR
v_ase gui charge.dat --format qe-cube
v_ase gui potential.dat --format qe-xsf
```

Opening a volumetric file creates the associated atomic structure and one or
more scalar dataset descriptors. In an existing document, use **Analysis >
Volumetric Data > Add Grid Data**.

## Choose precision before import

**Import precision** and the CLI option select storage precision while reading:

```bash
v_ase gui CHGCAR --volumetric-precision fp32
v_ase gui CHGCAR --volumetric-precision fp64
```

Python exposes the same choice:

```python
from v_ase.visualize import view

view("CHGCAR", volumetric_precision="fp64")
```

- FP32 is the lower-memory default.
- FP64 preserves double-precision input and uses twice the grid memory.

Changing a display control later does not convert the stored dataset. Verify
the descriptor's precision and backend memory size after loading.

## Dataset state

Each dataset has a stable ID and reports scientific metadata including:

- source name and canonical format;
- quantity, component, units, and precision;
- grid dimensions, cell, origin, and PBC;
- endpoint convention and memory bytes;
- minimum, maximum, mean, and integral; and
- fixed 256-bin raw and absolute-value histograms.

Histogram counts sum to the source voxel count and remain unchanged when
isosurface, plane, camera, color, or opacity settings change. Select datasets
by ID rather than list position when automating a multi-grid document.

### Interpret the integral

VASP charge grids are divided by cell volume on import; their integral equals
the average raw grid value (the electron count for an ordinary total-charge
grid). LOCPOT values retain eV and are not divided by volume. Cube and XSF
retain their reported/native scalar units; do not infer an electron count from
an unlabeled field.

Endpoint-exclusive grids use equal voxel weights. For endpoint-inclusive grids,
periodic closing planes are excluded once, while finite axes use trapezoidal
half weights at both endpoints. The determinant of the complete triclinic cell
supplies the volume Jacobian. `mean` is the arithmetic mean of stored samples;
it need not equal the integration-weighted mean on an endpoint-inclusive grid.

:::{admonition} Source grids are immutable analysis inputs
:class: important
Isovalue changes, Gaussian smearing, mesh smoothing, color, opacity, and
planar sampling operate on display products. They do not replace the stored
FP32/FP64 scalar field, its integral, or the arrays used in a linear
combination.
:::

## Example: verify field subtraction without changing the grid

Download {download}`graphene-pi.cube <assets/examples/graphene-pi.cube>`. Open the same file as two datasets,
A and B, so their cell, origin and grid match exactly.

1. In field arithmetic, choose A as the base and subtract B.
2. Create a new derived dataset; preserve both sources.
3. Check that the resulting range and integral are zero within roundoff.
4. A zero field has no nonzero signed isosurface. This is a useful consistency
   exercise; a scientific difference density requires appropriately defined
   full-system and fragment calculations on a compatible grid.

```{figure} assets/readme_volumetric.png
:alt: The analytic source field before the subtraction exercise; this is not the zero-field result.

The analytic source field before the subtraction exercise; this is not the zero-field result.
```


## Combine compatible datasets

Combination accumulates bounded slabs in FP64 and rounds once to the requested
output precision. FP32 remains the memory-saving default when all inputs are
FP32; import FP64 before subtraction when small differences matter. Converting
an already rounded FP32 source later cannot recover lost input digits.

Open **Analysis > Volumetric Data > Combine** and enter finite coefficients.
A common charge-density-difference form is:

```text
Δρ = ρ_combined - ρ_fragment_A - ρ_fragment_B
```

The source datasets must match exactly in:

- grid dimensions;
- cell and origin;
- PBC and endpoint convention; and
- physical units.

v_ase refuses mismatched grids instead of silently interpolating or
resampling. When output precision is omitted, a combination promotes to FP64
if any input is FP64; otherwise it remains FP32. The new dataset receives its
own stable ID, descriptor, and histogram.

## Cell, replication, and reset behavior

Visual `display.supercell` repeats the isosurface and planes with the atoms
without changing stored data. Visual translation moves atoms, bonds,
constraints, surfaces, and planes together.

**Set Supercell as Cell** physically repeats atoms and every stored volumetric
grid for a diagonal integer repetition, with one atomic Undo entry. A general
non-diagonal cell matrix is rejected while grids are loaded because an
explicit scientific interpolation policy would be required.

After a materialized diagonal supercell, **RESET COORDS** restores the original
atoms, cell, and scalar grids together. Undo/Redo preserves the atom/grid
pairing.

## Save and export volumetric work

Reopening a project restores and samples all visible saved planes before the
document reports ready, so its first render includes the same planar rasters.

A `.vase` project retains stored datasets, precision, current frame, visual
settings, and supported analysis state without pickle. A project-embedded HTML
save contains the complete validated `.vase` plus a browser-ready view.
Lightweight HTML contains the rendered/view-only scene but is not a lossless
editable scalar-grid interchange.

Images and HTML use the persistent Render Area. Before export, verify surface
or plane visibility, opacity, crop, camera, axes, cell, background, and exact
render dimensions. Use `.vase` as the editable source of truth.

## Limits and failure behavior

- A scalar array must be three-dimensional with at least two samples per axis.
- The default source-grid ceiling is 134,217,728 points. Override
  `V_ASE_MAX_VOLUMETRIC_POINTS` only after confirming available memory.
- The default surface safety ceiling is 2,000,000 triangles per surface.
- Smearing is limited to 0–8 voxels; smoothing to 0–30 passes.
- Semantic surface step is 1, 2, or 4; plane resolution is 128, 256, 512, or
  1024.
- Dataset removal requires an exact stable ID.
- Relative semantic paths cannot escape the GUI launch directory.
- Constant fields remain stored but cannot produce an isosurface crossing.
- A mismatched linear combination or invalid plane edit is rejected without
  partially mutating the document.
