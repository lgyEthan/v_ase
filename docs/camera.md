# Camera, projection and lighting

Compose a figure without moving the atoms. Camera controls work in View and
Edit. Use [Rotate atoms](rotate.md) only when coordinates must change.

## Find a useful view

| Control | Action |
| --- | --- |
| Middle-mouse drag | Orbit around the target |
| Shift + middle-mouse drag | Pan |
| Wheel | Zoom; atomic scale updates in pixels per Å |
| `X`, `Y`, `Z` outside a transform | Align to a canonical Cartesian view |
| Same axis key again from that exact pose | Flip to the opposite axis view |
| Camera toolbar arrows | View-relative tilt, orbit and roll |

Orthographic projection avoids perspective size distortion. Choose perspective
when depth is part of the composition. Grid, axes, cell and background are
independent display controls. Camera motion is not in Undo/Redo history.

## Example: show a surface from the side

Download {download}`cu5o4-labeled.extxyz <assets/examples/cu5o4-labeled.extxyz>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui cu5o4-labeled.extxyz
```

1. In View, press `X` to look along x. The slab thickness is visible.
2. Pan and zoom until the slab and oxide fit. Use the toolbar to tilt the view
   slightly if atoms overlap along the viewing direction.
3. Choose a white viewport background and hide the grid. Keep the unit cell
   visible when periodic geometry needs to be communicated.
4. For a polished sphere view, choose Studio Sun or Sun + Soft Shadow and
   adjust the Sun direction. Set an [image render area](render-images.md)
   before exporting; viewport size alone does not define output pixels.

```{figure} assets/readme_cu5o4_view_appearance.png
:alt: A tilted surface view reveals substrate and oxide layers.

A tilted surface view reveals substrate and oxide layers.
```


## Lighting, quality, and theme

Viewport quality controls include antialiasing and atom smoothness. Lighting
supports the current modeling/studio choices, a user-controlled Sun, and
shadowed rendering where available. A scene using only standard/rubber
materials does not allocate the metal reflection environment.

The **System** interface theme follows the browser/OS preference. Explicit
Light or Dark persists in that browser. Interface theme and viewport background
are distinct settings, although explicit Dark selects a matching dark viewport
for a coherent starting point.
