# Rendering Performance

## Performance Rules

v_ase keeps the lightweight viewer path independent from optional editing and
rendering costs:

- visualization mode does not attach the fallback calculator or invoke
  interactive edit paths;
- changing to Edit materializes lazy trajectory frames once, with a visible
  busy state, before ASE-backed editing is enabled;
- Modeling lighting creates no shadow map;
- renderer updates are demand-driven;
- inactive document tabs suspend rendering and playback.

The viewport uses GPU instancing for atoms, bonds, selections, and supercell
replicas. Large scenes reduce device pixel ratio adaptively, reuse geometry and
materials, and avoid one JavaScript/Three.js object per visible atom.

Displacement analysis is opt-in. When hidden, it performs no request and
allocates no geometry. When enabled, all vectors share one instanced shaft
mesh and one instanced head mesh. Changing arrow style, scale, thickness, or
color updates the cached GPU batches without repeating the ASE/MIC calculation.
Backend mapping runs off the event loop and shows a delayed busy state only
when it is not effectively instantaneous.

Video interpolation is also opt-in. `1x` follows the existing one-render-per-
source-frame path. Higher multipliers retain only two flattened endpoint frames
at a time, generate one temporary subframe buffer, and reuse the existing atom,
bond, selection, constraint, and supercell batches. No interpolated frame is
stored in the backend trajectory.
Canvas capture uses manual frame requests when the browser supports them.
Transcoding enforces the selected FPS and expected output count, so a 60 Hz
display cannot silently multiply identical video frames.

## Output Encoding

The render canvas is always created at the user-selected width and height.
Storage optimization occurs after rendering:

- lossless WebP uses exact RGBA encoding and is the compact image default;
- PNG concatenates and validates the browser IDAT stream, then performs a
  higher-effort lossless DEFLATE pass while preserving all non-IDAT chunks;
- PNG falls back to the original browser bytes when recompression is larger;
- MOV uses H.264 with a slow preset and quality-based rate control;
- AVI uses MPEG-4 quality-based rate control.

None of these paths resize the canvas, lower the atom sphere quality, or alter
the selected renderer. Browser recording retains a high-quality intermediate
bitrate; only the final ffmpeg pass performs storage compression. The browser
sends binary image blobs instead of base64 strings so large captures do not
require an additional 33% text copy.

Reference storage check on the development Mac:

| 1920 x 1080 workload | Previous/output bytes | Optimized bytes | Reduction |
| --- | ---: | ---: | ---: |
| Lossless README overview image | 532,460 PNG | 340,158 WebP | 36.1% |
| 3 s, 30 FPS MOV transcode | 3,699,245 | 3,035,709 | 17.9% |

The image comparison decoded to byte-identical RGBA. The video comparison kept
all 90 frames at 1920 x 1080; it changes only the final H.264 encoding profile.

## Large LAMMPS Pipeline

Numeric LAMMPS text dumps use:

1. memory-mapped frame boundary indexing;
2. one ASE template from the first requested frame;
3. byte-range numeric parsing through NumPy;
4. one contiguous float32 trajectory payload for browser playback;
5. translation-only instance-matrix updates for each frame.

The initial browser JSON never embeds every trajectory frame. Manual frame
scrubbing can read one indexed frame and synchronize Python; active playback
uses the browser's binary cache with no per-frame HTTP or JSON.

The local Uvicorn server is readiness-polled instead of using a fixed startup
sleep. `ASEEditor.close()` and blocking session finalization stop and join the
owned server, so repeated test and API sessions do not leave background
threads.

## Bond Pipeline

Automatic and pair-specification bonds use a spatial cell list above the
small-scene threshold. For repeated cells, one periodic candidate search
supplies both base-cell topology and internal supercell bridge records. Manual
pairs bypass neighbor inference.

Large scenes cache a `maximum cutoff + skin` neighbor candidate list. Actual
distances and pair minimum/maximum ranges are still evaluated every frame, so
bonds form and break live. The candidate list is rebuilt when an atom moves
more than half the skin or when labels, visibility, cutoffs, cell, PBC,
periodic policy, or constraints change. Cylinder instance matrices are written
directly to the GPU buffer; unchanged topology reuses the existing instanced
bond batches.

The Metal preset creates one shared 192 x 96 studio environment and converts it
to a PMREM texture on first use. It is reused by all metal atom groups.
Standard/rubber-only scenes skip this work, and metal atoms remain instanced by
material group.

Bond controls use a dedicated animation-frame-coalesced update path. Editing a
pair range or bond material does not reparse the Appearance table, supercell
inputs, transform controls, or export settings.

## Browser Benchmark

Run:

```bash
python scripts/benchmark_large_trajectory.py
python scripts/benchmark_large_trajectory.py --benchmark-bonds
```

The default workload is a deterministic 15,000-atom, 16-frame numeric LAMMPS
dump. The benchmark starts a fresh local server and Chromium page at
1280 x 720, waits for all atom instances and the first rendered canvas frame,
loads the binary trajectory cache, verifies idle rendering, and updates all
frames.

Reference result for the 0.0.92 working tree on the project development Mac:

| Check | Result |
| --- | ---: |
| Input size | 8,719,654 bytes |
| Backend input + server ready | 0.340 s |
| Browser navigation + first render | 0.264 s |
| Fully ready total | 0.604 s |
| Displayed atoms | 15,000 |
| Trajectory frames | 16 |
| Browser trajectory cache | 2,880,000 bytes |
| 16-frame modeling update sweep | 19.8 ms |
| Mean modeling position update | 1.24 ms/frame |
| Mean Studio position update | 0.98 ms/frame |
| Mean Sun + Soft Shadow update | 0.77 ms/frame |
| Extra render frames during 0.9 s idle | 0 |

A separate single-frame 15,000-atom material regression measured 0.392 s from
navigation to all atom instances being available. Standard-to-Metal label
switching retained one instanced atom group for all 15,000 atoms.

With automatic bonds enabled, the same synthetic scene contains 73,952 logical
bonds. Cached topology inference measured 10.5 ms, direct geometry-buffer
update 13.8 ms, and a four-frame sweep that includes candidate-list rebuilds
averaged 30.53 ms/frame.

Browser, GPU, storage, trajectory columns, bond density, and machine load
affect absolute timing; these values are regression references, not universal
guarantees. Background browser tabs may throttle timer frequency, so playback
FPS is not inferred from a headless hidden-tab timer.

## Blender Benchmark

`tests/test_blender_performance.py` generates a 15,000-atom, two-label periodic
scene. Optimized export writes one point mesh per visual label and instances
smooth spheres through Geometry Nodes. Trajectory frames become point-mesh
shape keys; bonds are grouped by material; the unit cell is one multi-spline
curve.

The regression verifies:

- all 15,000 atoms are retained;
- atom data is held in a small number of editable point groups;
- total scene object count remains small;
- Blender executes the generated script and saves a native `.blend`;
- the runtime remains below a conservative machine-independent ceiling.

`tests/test_blender_runtime.py` separately renders a colored bonded scene and
checks smooth atoms, split bond materials, camera, cell, trajectory animation,
and exact directional Sun source/target/intensity.

## Remote Cluster Validation

The 0.0.95 candidate wheel was installed into an isolated environment on an
x86_64 Linux physics cluster with Python 3.13.9 and ASE 3.27.0. From the
development Mac, an existing 18-atom periodic CIF on that host was opened with
the public one-command workflow:

```bash
v_ase gui physics:/remote/path/cod_9001665.cif
```

No port was supplied or reserved. v_ase selected both loopback endpoints,
started the remote backend, established the SSH forwarding connection, and
opened the local browser. The test verified version 0.0.95, all 18 atoms,
`TTT` PBC, the unit cell, and a nonblank rendered scene. Closing the browser
page released the local launcher, tunnel, and remote process.

A separate two-frame LAMMPS dump validated the remote trajectory contract. The
initial response reported `trajectory_streaming=true`, contained no inline
trajectory coordinates, and advertised no whole-trajectory binary cache.
Requesting frame 2 returned only its six float32 coordinates. This policy is
enabled for every remote trajectory regardless of source-file size: the source
file, reader, ASE state, and scientific operations remain on the server while
the browser receives only the data needed for the displayed frame.

## Regression Coverage

Performance-sensitive static contracts are locked by
`tests/test_frontend_regressions.py`. Real browser tests cover:

- zero idle render loop;
- binary trajectory initialization and frame changes;
- live bond formation/breaking;
- supercell atom and bond instancing in skewed cells;
- label visibility and appearance updates;
- visualization-mode replica selection;
- frame-persistent selection and displacement-vector instancing;
- frame-specific cell/PBC handling for wrap, translation, and supercells;
- output preview/capture parity;
- inactive multi-document suspension.
