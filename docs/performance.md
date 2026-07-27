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
