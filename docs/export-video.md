# Export trajectory videos

Export a trajectory using the same camera, crop and resolution as image
rendering. Open **Render → Video** with a multi-frame document. The route shows
container, FPS, interpolation and MIC controls with a live output-frame and
duration estimate; the Export dialog previews the complete render options.

## Example: export the C60 relaxation

Download {download}`crowded_c60_relaxation.traj <assets/examples/crowded_c60_relaxation.traj>` and open it.

1. Choose the camera and Render Area before opening Video export.
2. Choose the output dimensions under **Renderer**, then set the Video format
   and frame rate on **Video**.
3. Choose source frames for a direct record, or interpolation for a smooth
   visual transition. Interpolation does not add calculated physical data.
4. Export MOV or AVI and inspect both the first and last output frames.
5. Check duration and crop; overlay state should follow the exported frame.

The Video dialog can use the viewport-derived frame scale or an independent
physical output scale in px/Å. Set the latter explicitly for comparable
dimensions across different viewport zoom levels. Property-radius mappings
are evaluated for each source frame; interpolated frames interpolate the raw
continuous property before applying the locked mapping. Categorical values
use the nearest endpoint, and a missing value falls back to the neutral factor.

```{vase-animation} assets/readme_relaxation.gif
:alt: The source relaxation sequence; a GIF preview is not the exported MOV/AVI.
:fallback: assets/readme_relaxation.png

The source relaxation sequence; a GIF preview is not the exported MOV/AVI.
```


## Video output

Trajectory video supports H.264 MOV and MPEG-4 AVI at a constant requested
frame rate. The browser captures each rendered frame, then the bundled
imageio-ffmpeg runtime transcodes the final portable file.

At interpolation multiplier `1x`, every source frame appears exactly once. For
`N` source frames and multiplier `m`, the output has
`(N - 1) * m + 1` frames. Optional MIC interpolation uses adjacent cells and
shared periodic axes; it never mutates the source trajectory.

The video background is opaque white. Visible analysis overlays are refreshed
for each output frame rather than copied from one source frame.

## Deterministic video frames

MOV and AVI exports encode one indexed raster per source or interpolated frame.
Frame timestamps come from the chosen FPS, not the time taken to render. With
N source frames and interpolation factor k, the output contains (N−1)k+1 frames,
including both endpoints. Native dimensions must be even integers in 64..8192;
FPS is 1..60, and interpolation is an integer from 1 through 64. The GUI retains
its 256-pixel minimum input controls. Encoding never pads a typed request or
invents a missing scientific frame. PNG uploads apply encoder backpressure so
only one raster needs to be staged at a time. Video is opaque.

The original GUI frame is restored after export. Semantic edits and another
capture wait until the video is complete. Closing the page aborts its encoder;
failed sequences do not return a partial movie as a successful export.
