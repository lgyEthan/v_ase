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

The toolbar popover follows its button and stays inside the
window when resized. On short windows, scroll inside the panel to reach all
controls. These settings affect the shared scene and its rendered exports.

```{figure} assets/render-lighting-controls.png
:alt: Open Render Lighting controls above the Cu surface viewport, with the Renderer selector accessible outside the scrolling toolbar.
:width: 900px

The sphere button opens a separate panel; it remains clickable below the toolbar.
```

## Render Area

Image, video and HTML share the stored **Render Area** camera and dimensions.
**Show output frame** draws a boundary and outside mask on the same editable
canvas. It does not draw another scene or introduce another picking camera.
Select, move and measure atoms normally inside or outside the guide; opening
or resizing the inspector does not shift its composition.

The frame toggle, dimensions, px/Å and camera controls live together under
**Output frame & scale**. Lighting, Quality and Overlays are separate sections.

- **Navigate → Scene** lets you orbit, pan, zoom, use X/Y/Z and edit atoms while
  preserving the output camera and px/Å.
- **Navigate → Camera** applies subsequent navigation to the output composition.
  Switching between Scene and Camera does not recapture the current editor zoom
  or resize the output frame.
- **Look through camera** fits the saved frame on screen and switches to Scene.
  Wheel zoom then changes only the editor zoom, including in perspective.
- **Align camera to view** deliberately replaces the output pose with the editing
  viewpoint. This is an action, not another navigation mode.
- Off-axis, a wire camera body and oriented output-plane outline show position,
  facing direction and framing without a filled surface that covers atoms.
  Click its outline or the camera button on the crop guide to select it.
- **G** translates camera and target together; **R** rotates around the output
  center (X/Y/Z constrain the world axis); **S** uniformly scales the frame,
  inversely changing physical px/Å when enabled. Enter applies, Escape restores
  both camera and scale. Camera transforms work in View as well as Edit and
  compose all rendered geometry, including the unit cell.
- Output lighting, overlays and transparency apply when rendering. Both
  **Style → Viewport** and **Render → Quality → Atom rendering** expose
  **2D flat / 3D spheres**, independently of camera projection.
- The viewport work grid is an adaptive analytic plane with a fading horizon.
  It has no finite mesh edge and never writes depth or masks atoms. Camera clip
  limits adapt to the rendered structure without changing stored composition.

The distinction between navigating a camera view and moving the camera follows
[Blender's camera-view interaction](https://docs.blender.org/manual/en/latest/editors/3dview/navigate/camera_view.html).

For exact physical sizing, choose **Physical scale** and enter output px/Å on
the Renderer page. The Image, Video and Interactive HTML routes also show
these shared frame controls alongside their format-specific settings and
export actions. Image selects PNG, JPEG, WebP or PDF; Video offers MOV/AVI/GIF, source-frame ranges, repeat mode,
FPS, interpolation/MIC and an output-duration estimate; Interactive HTML
chooses whether to embed the editable project and explains its offline poster.
**Copy viewport scale** takes the current camera scale as a starting value;
afterward output scale is independent of viewport zoom and the global atom
sphere-size multiplier. Canceling an image or HTML export does not change a
saved project's HTML output profile.
Committed changes on the shared Renderer page update a reopened editable
HTML project's matching output profile; one-shot export-dialog drafts do not.

## Image output

Images support:

- optimized PNG;
- JPEG;
- lossless WebP; and
- a single-page 300 dpi PDF containing the rendered pixels.

The semantic renderer normalizes width/height to 64–8192 pixels. The chosen
dimensions and Render Area camera determine the exact output; JPEG and PDF are
opaque, while PNG/WebP can retain supported transparency.

Lossless WebP and optimized PNG preserve the requested pixel dimensions and
RGBA result. PNG recompression is used only when it is smaller than the browser
source.
