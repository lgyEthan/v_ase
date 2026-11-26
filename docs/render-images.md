# Render images

Export a figure at exact pixel dimensions, with a deliberate crop and
background. Open **Render → Image** to set dimensions, framing, output px/Å, format and
background. **Preview framing** shows the Render Area. Expand **Advanced render
settings** for shared lighting, camera details and quality, or open **Render → Renderer**.
The live viewport and saved image can have different aspect ratios.

## Example: export the styled Cu surface

Download {download}`cu5o4-labeled.extxyz <assets/examples/cu5o4-labeled.extxyz>` and follow the
[appearance example](appearance.md). Then:

1. Set the camera and open Render Area. Choose **1600 × 1000** pixels.
2. Adjust the frame until the whole oxide and the intended substrate layers fit.
3. Choose whether to include the unit cell, axes and grid; use a white or
   transparent background according to the destination.
4. Export PNG, open the saved image and check its dimensions and edges.
5. Save a project as well if you will refine the figure later.

```{figure} assets/readme_cu5o4_view_appearance.png
:alt: Use this surface composition as the input; the exported image excludes the surrounding GUI.

Use this surface composition as the input; the exported image excludes the surrounding GUI.
```


## Render lighting

1. Open **Render → Renderer** (or use `⌘Shift+A` on macOS, `Ctrl+Shift+A` on Windows/Linux). The sphere button in the canvas **View** menu opens the same lighting controls.
2. Choose **Modeling**, **Studio Sun**, or **Sun + Soft Shadow**.
3. For the sun modes, adjust **Brightness**, source and target coordinates.
4. Close with **×**, **Escape**, or a click outside the panel.

These lighting settings apply to the live scene and exported images.

```{figure} assets/render-lighting-controls.png
:alt: Open Render Lighting controls above the Cu surface viewport, with the Renderer selector accessible outside the scrolling toolbar.
:width: 900px

The sphere button opens a separate panel; it remains clickable below the toolbar.
```

## Render Area

The render area defines the camera and crop used for image, video and HTML
output. Open **Render → Renderer → Render area & scale**, choose the output
width and height, and turn on the **Camera** icon to see the frame.

Type in **Output scale** to zoom the structure in the canvas and change the
output framing at the same time. This works in **Viewport** and **Physical
scale**, with the frame visible or hidden. Doubling px/Å doubles the projected
size in both views. In perspective, px/Å is measured at the camera target.

| Control | When to use it |
| --- | --- |
| **Camera icon** | Show or hide the camera and frame. Turning it on returns to the saved camera view. The viewport and Renderer icons control the same object. |
| **Align camera to current view** | Replace the output viewpoint with the view you have just arranged. |
| **Lock camera to viewport** | Adjust the composition while keeping the frame on screen. Turn it off to inspect or edit the structure from another angle without moving the output camera. |
| **Viewport** | Keep the camera's vertical span when the output height changes. The field shows the resulting output px/Å. |
| **Physical scale** | Keep the specified output px/Å when the output dimensions change. |
| **Copy viewport scale** in the export dialog | Use the current viewing scale as a starting point for a physical-scale export. |

The camera is fixed in the scene by default. Hiding it also turns off viewport
lock, while retaining the saved composition. To return from another viewpoint,
toggle the camera icon off and on.

### Move or resize the render area

Click the **Camera** badge on the frame, or the camera outline in the scene.
Press **G** to move, **R** to rotate or **S** to scale it; use **X/Y/Z** for an
axis constraint. **Enter** applies and **Esc** cancels. Camera transforms work in
View and Edit modes and do not change atom coordinates.

With **S**, an axis that projects into the frame changes its width or height
according to the projection. An axis along the camera's line of sight changes
magnification. **Fix ratio** in **Render area & scale** keeps width and height
proportional during an axis resize or a dimension edit. The option starts off.
With **Lock camera to viewport** enabled, moving, rotating, or changing
magnification keeps the frame in place while the scene moves within it.

### Choose what appears in the output

Use the visibility controls in **Scene** for atoms, bonds, cell, grid, axes and
constraints. The Atoms eye hides glyphs only and retains bonds and constraints.
These choices also apply to rendering. Constraint visibility is independent of
constraint enforcement.

Set **2D flat / 3D spheres** under **Style → Viewport** or the Renderer quality
controls. In flat mode, **Outline width** sets one stroke width in Å for the
atom rims and the bond edges. **Thickness** in Bonds sets the total ribbon
width. **Atom & bond segments** controls geometry quality in both modes.
Lighting and materials apply to 3D spheres.

Image opens with exact dimensions, framing, background and format. Video and
Interactive HTML expose their own format settings and export action. Expand **Advanced render settings** to change the same Render
Area, scale, lighting and quality from any of those panels.
After saving an image, its filename appears beside the canvas. Smaller raster
outputs show a thumbnail. **Save a copy** writes the completed image to another
destination. Use the close button to dismiss the result.
Output scale is independent of atom size: changing px/Å magnifies the figure,
while changing atom radius changes the spheres themselves.

## Image output

Images support:

- optimized PNG;
- JPEG;
- lossless WebP; and
- a single-page 300 dpi PDF containing the rendered pixels.

Choose dimensions from 64 to 8192 pixels per side. PNG and WebP support a
transparent background; JPEG and PDF are opaque. The exported image uses the
render area rather than the size of the application window.
