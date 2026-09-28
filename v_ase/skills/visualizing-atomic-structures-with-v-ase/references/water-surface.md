# Water surface (experimental)

Discover `capabilities().waterSurface` and `display.waterSurface` in the live display schema. Read `describe().analysis.waterSurface` for build/error diagnostics. Use the existing typed
display control, preserving document/revision preconditions. Read and merge the
current nested water settings when modifying one field; the object carries its
own defaults. Example display payload:

```json
{"waterSurface":{"enabled":true,"source":"auto","color":"#65aaca","opacity":0.48,"lighting":true,"hideMolecules":true,"smoothing":1.45,"level":0.65,"spacing":0.65,"ohCutoff":1.25,"roughness":0.18,"indices":[]}}
```

`source:"selected"` uses captured **oxygen base indices**, not the current GUI
selection. Empty indices select no molecules; indices missing in a short frame
are retained. Detection uses actual elements and valid positive source molecule IDs first
(`mol`, `molecule_id`, `molecule_ids`, `molid`, `mol-id`), with nearest O–H fallback only for
unassigned atoms. A declared molecule must contain one O and two H and satisfy
the periodic O–H cutoff. Mutable labels and visual bond settings do not define
water. Read `method`, `topologyMolecules`, `builds`, `vertices`, `triangles`,
`spacing` and `buildMs` in the water report.

This is a Gaussian-density isosurface for presentation, not fluid/MD simulation
or a physical mass-density measurement. Smoothing can bridge small gaps. Never
claim a membrane permeability, liquid boundary or new scientific result from it.
Source coordinates, chemical elements and constraints must remain unchanged.

The GUI is **Style → Water**; Objects shares its enabled checkbox. `lighting:false`
uses an unlit surface while preserving other objects' lighting. Surface material
is unlit in flat mode. The same geometry path serves viewport, PNG/movie/GIF and
self-contained HTML; project settings persist in .vase. Geometry CAD/Blender
exports do not currently carry the envelope; report this limitation.

Capacity failures appear in the water status and restore molecular spheres.
Interior sphere/bond instances are excluded from GPU draw counts. An indexed
boundary mesh is cached during camera/material changes, rebuilt for coordinates
and displayed signed supercell offsets, and shared by exact exports.
The prototype bounds grid size/kernel work and displayed molecule counts;
do not claim arbitrary-size realtime performance. Use the synthetic
`examples/water_surface.py` only as rendering evidence, not physical simulation.

Stored molecule IDs stay synchronized with streamed coordinates, even while the
layer is off. If water-enabled video interpolation reports changed molecule IDs,
export source frames with `interpolationMultiplier:1`; never interpolate molecule
identity. In-memory fixed-topology trajectories keep their coordinate cache; lazy
sources that may change IDs use one synchronized frame response. Capacity errors
restore atom glyphs, and returning to valid settings rebuilds the envelope.
