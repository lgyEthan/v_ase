# Water surfaces

Show H₂O as a continuous translucent surface while keeping ions and solids
atomistic. This visualisation is derived from atomic coordinates; it does not
run a fluid simulation or measure a physical liquid boundary.

## Show the water

1. Open a structure or trajectory containing water.
2. Open **Style → Water** and enable **Show water surface**.
3. Adjust **Color**, **Opacity** and **Lighting & reflections**.
4. Leave **Replace molecular spheres** on for a continuous water view, or turn
   it off to inspect the molecules beneath the surface.

**Objects → Water surface** shows or hides the same layer.

```{vase-animation} assets/water-surface-experiment.gif
:alt: A translucent water surface surrounding ions and an atomistic membrane.
:fallback: assets/water-surface-experiment.png

Water surface visualisation in an illustrative trajectory.
```

## Adjust the shape

| Control | Effect |
| --- | --- |
| **Kernel width** | How far each water oxygen contributes to the surface, in Å. Increase it for a broader, more connected envelope. |
| **Density threshold** | The relative level used to draw the envelope. Lower values expand it; higher values shrink it. This is not density in g/cm³. |
| **Grid spacing** | Sampling resolution. Smaller spacing captures finer detail but takes more time and memory. |
| **Selected water oxygens → Use current selection** | Limit the surface to the selected oxygen indices. Later selection changes do not change this saved group. |

If separate pools appear connected through a narrow pore or membrane, reduce
the kernel width or increase the threshold. Check the underlying molecules
before interpreting the surface as an interface.

## Molecular-scale defaults

New scenes start with a **2.0 Å kernel width**, **0.63 threshold**, **0.65 Å grid
spacing**, **subdivision 1** and **20 smoothing passes**. Existing project settings
are retained.

The initial length scale is comparable to the volume occupied by a water
molecule in ambient liquid water. It is a visual starting point, not a calibrated
molecular volume or interface measurement. The density reference is
[NIST's water-density data](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=923093).

## Renderer quality and recovery

Use **Render → Renderer → Quality → Surface finish** to smooth an existing
water surface or isosurface without changing its source data.

| Control | Range | Use it for |
| --- | --- | --- |
| **Smoothing passes** | 0–100 | Reduce mesh ripples. Start with 20; use 0 to compare with the original surface. |
| **Subdivision** | 0–8 | Add surface detail. Each level multiplies the triangle count by four, so increase it gradually. |
| **Atom & bond segments** | Even values from 8–128 | Smooth sphere and cylinder silhouettes together. It does not change physical radii or bond lengths. |

Smoothing changes the displayed approximation and can hide fine features;
compare with zero passes when those features matter. Increasing subdivision
alone does not remove ripples in the original mesh. Anti-aliasing smooths pixel
edges but cannot make a coarse sphere silhouette round.

Use **Style → Isosurfaces** to change an isovalue, extraction settings, signed
levels, color or opacity. The Renderer controls only finish the resulting mesh
and are disabled when no corresponding surface is visible. Coordination
polyhedra keep their planar faces.

If a change is too slow, use **Cancel** or **Esc** while it is being prepared.
**Revert quality** restores the previous quality after completion;
**Lightweight** returns to 12 atom/bond segments and unrefined surfaces.
A request that exceeds the mesh limit reports an error rather than silently
changing your scientific isovalue. Lower subdivision or reduce repetitions.

## What the surface means

The surface is an isosurface of Gaussian contributions centred on water oxygens.
When the source contains positive integer molecule IDs (`mol`, `molecule_id`,
`molecule_ids`, `molid` or `mol-id`), each water group must contain one O and two H
within the O–H cutoff (default **1.25 Å**), including periodic neighbours.

Without molecule IDs, detection assigns each H to its nearest O within that
cutoff and looks for groups with exactly two H. This is a geometric heuristic:
hydronium, hydroxide, coarse-grained water and heavily dissociated structures
may not be identified as H₂O. Molecule IDs help distinguish water from surface
hydroxyls. The visualisation does not change source coordinates or molecule IDs.

Saved oxygen selections are tracked by index across frames. This does not imply
that an index represents the same molecule in a reactive simulation.

## Playback and output

Water follows the displayed trajectory frame, including interpolated frames.
Changing the camera or material does not require rebuilding its shape.
If molecule IDs change between frames, export the original source frames
rather than interpolating across that change.

Images, movies, GIFs and offline HTML include the displayed surface. Save a
`.vase` project to retain the water settings. In flat 2D mode the surface is unlit.
[Blender export](export-structures.md#blender) includes editable water meshes and
animation. OBJ and Rhino exports currently require water surfaces to be disabled.

## Performance and bounds

For smoother playback, lower subdivision or smoothing passes, increase grid
spacing, or reduce displayed repetitions. **Replace molecular spheres** also
removes the participating water atom and bond drawings while leaving their
scientific data available.

Surface quality is limited by the size of your dataset and available resources.
Grid spacing may be increased to fit the supported grid budget; the effective
spacing is shown in the controls. Surface finishing permits up to **8 million
triangles per surface**, or **12 million across finished surfaces**. Level 8 is
therefore useful only for small meshes. Export waits for the chosen frame's
surface to finish, even when live playback cannot keep up.

Periodic copies contribute to one combined visible surface. The envelope can
extend beyond cell faces; it is not clipped to the simulation box.

## Reproducible example

From a source checkout:

```bash
python examples/water_surface.py
```

The example contains 24 synthetic frames with 150 water molecules, a perforated
sheet and ions. It illustrates the display controls; it is not an MD trajectory
or a membrane-permeability result.
