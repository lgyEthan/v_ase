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
are retained. Detection uses actual chemical symbols and nearest O–H neighbours,
not labels or display bonds. Exactly two assigned hydrogens are required.

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
The prototype bounds grid size/kernel work and displayed molecule/triangle counts;
do not claim arbitrary-size realtime performance. Use the synthetic
`examples/water_surface.py` only as rendering evidence, not physical simulation.
