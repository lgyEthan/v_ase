# Render images

Export a figure at exact pixel dimensions, with a deliberate crop and
background. Open **Render → Renderer** to set lighting, quality, dimensions,
output px/Å and the Render Area, then choose **Render → Image**.
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

1. Open **Render → Renderer** (or use `⌘Shift+A` on macOS, `Ctrl+Shift+A` on Windows/Linux). The sphere button beside
   the canvas grid button opens the same lighting controls as a convenience.
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

| Control | When to use it |
| --- | --- |
| **Camera icon** | Show or hide the camera and frame. Turning it on returns to the saved camera view. The viewport and Renderer icons control the same object. |
| **Align camera to current view** | Replace the output viewpoint with the view you have just arranged. |
| **Lock camera to viewport** | Adjust the composition while keeping the frame on screen. Turn it off to inspect or edit the structure from another angle without moving the output camera. |
| **Physical scale** | Set an exact output scale in pixels per Å. |
| **Copy viewport scale** | Use the current viewing scale as a starting point for the output. |

The camera is fixed in the scene by default. Hiding it also turns off viewport
lock, while retaining the saved composition. To return from another viewpoint,
toggle the camera icon off and on.

### Move or resize the render area

Click the **Camera** badge on the frame, or the camera outline in the scene.
Press **G** to move, **R** to rotate or **S** to scale it; use **X/Y/Z** for an
axis constraint. **Enter** applies and **Esc** cancels. Camera transforms work in
View and Edit modes and do not change atom coordinates.

With **Lock camera to viewport** enabled, the frame stays in place while the
scene moves within it. Scaling the frame changes physical output px/Å when that
setting is enabled. Opening the right panel does not change the saved camera.

### Choose what appears in the output

Use **Objects** to show or hide atoms, bonds, cell, grid, axes and constraints.
These choices also apply to rendering. Hiding constraint marks does not remove
the underlying constraints.

Set **2D flat / 3D spheres** under **Style → Viewport** or the Renderer quality
controls. Lighting and materials apply to 3D spheres, not flat 2D drawing.

The Image, Video and HTML export sections use the same frame settings.
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
