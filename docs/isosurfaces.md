# Volumetric isosurfaces

Display a scalar field as a surface at a chosen level. Signed levels show
positive and negative lobes separately. Open a volumetric file, then use
**Analysis > Volumetric Data > Isosurfaces**.

## Example: signed lobes around graphene

Download {download}`graphene-pi.cube <assets/examples/graphene-pi.cube>`. Open the Cube file in v_ase. It contains
a deterministic analytic field built from alternating carbon-centered pz-like
Gaussians. **It is not a DFT wavefunction or charge density.**

1. Select the imported dataset and enable signed positive/negative levels.
2. Set opacity to **0.56**, field smearing to **0.45 voxel**, and mesh smoothing
   to **7 passes**. Use blue `#258fbd` and pink `#dc5976` for opposite signs.
3. Sweep the magnitude of the level from 5% to 46% of the maximum absolute
   source value. Higher levels leave smaller lobes; the underlying field is unchanged.
4. Inspect the source range and the surface's post-smearing range separately.
5. Save a project to retain the field and display settings.

```{vase-animation} assets/readme_volumetric.gif
:alt: The threshold changes across a fixed analytic graphene field.
:fallback: assets/readme_volumetric.png

The threshold changes across a fixed analytic graphene field.
```


## Create an isosurface

Open **Analysis > Volumetric Data > Isosurface**:

1. Select a **Dataset**.
2. Enable **Show isosurface**.
3. Choose **Single level** or **Positive + negative**.
4. Set a finite **Isovalue**.
5. Choose mesh detail, colors, opacity, smearing, and smoothing.
6. Select **Update Isosurface**.
7. Inspect the rendered topology from more than one camera direction.

A newly loaded nonconstant dataset is selected and displayed at an in-range
default level. Replace that preview value with the scientifically requested
threshold before publishing a result.

![Signed volumetric isosurfaces](assets/readme_volumetric.png)

### Single and signed levels

**Single level** requests one finite scalar level. **Positive + negative** uses
the magnitude of a nonzero level and extracts `+abs(level)` and `-abs(level)`
with independent colors.

After field smearing, one requested sign may lie outside the displayed range.
v_ase retains the valid sign, marks the result as a partial signed surface, and
does not invent the missing mesh. Verify rendered levels and surface count.

### Mesh detail

The semantic mesh step is `1`, `2`, or `4`:

- `1` / **Fine** preserves the most grid detail;
- `2` / **Balanced** reduces work; and
- `4` / **Fast** is the coarsest preview.

Use the smallest step needed to preserve the features of interest. Repeating
the same dataset, level, sign mode, detail, smearing, and smoothing request
reuses a bounded mesh cache. Changing only color or opacity restyles the
existing browser mesh without rerunning marching cubes.

### Field smearing

**Field smearing σ (voxels)** accepts `0` through `8`. It applies a Gaussian
filter to a display copy before surface extraction. Periodic axes wrap and
nonperiodic axes reflect at their boundaries.

Sigma is measured in grid steps, so equal sigma on differently spaced or skew
axes is not an isotropic Gaussian in physical Å. Use it as a display filter.

Smearing can merge small features or move an isovalue outside the displayed
range. Start around `0.3`–`0.5` only when grid artifacts require it, compare
against `0`, and do not describe a heavily smeared topology as raw data.

### Mesh smoothing

**Mesh smoothing passes** accepts integer `0` through `30`. It fairs the
extracted mesh after marching cubes while fixing cell-boundary vertices. It
does not smooth the source field. Use `0` to disable it.

### Colors and opacity

Positive/negative colors are six-digit hexadecimal colors. Isosurface opacity
is `0.05`–`1`. These are presentation settings and do not affect scalar
values. Isosurfaces follow display replication and visual translation with the
atoms.

## Inspect the result scientifically

The active surface summary reports:

- dataset ID and source range;
- requested and rendered levels;
- post-smearing display minimum and maximum;
- smearing sigma and smoothing passes;
- surface and triangle counts; and
- whether a signed surface is partial.

An HTTP success is not enough. Render the result, check that it is nonblank,
inspect cell seams and topology, then compare the source dataset descriptor to
confirm the display refinement did not replace it.
