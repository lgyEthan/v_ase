# Render images

Export a figure at exact pixel dimensions, with a deliberate crop and
background. Open **Render Area** to set composition, then **Export > Image**.
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


## Render Area

Image, video, and HTML use one persistent **Render Area**. Its visible boundary
and gray outside mask define the exact saved composition.

- **Follow viewport** keeps the export camera synchronized while you orbit,
  pan, zoom, and align the working view.
- Disable it and choose **Set from Current View** to lock a composition while
  continuing to inspect or edit in the main viewport.
- In Edit, the Render Area eye can be selected and moved with `G`, translating
  its camera and target together.

The Render Area owns aspect ratio, dimensions, projection/camera, overlay
choices, quality, and crop. Picking inside it uses the same camera, so pointer
selection remains aligned with visible atoms.

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
