# Rendering Performance

## Performance Rules

v_ase keeps the lightweight viewer path independent from optional editing and
rendering costs:

- visualization mode does not attach the fallback calculator or invoke
  interactive edit paths;
- Modeling lighting creates no shadow map;
- renderer updates are demand-driven;
- inactive document tabs suspend rendering and playback.

The viewport uses GPU instancing for atoms, bonds, selections, and supercell
replicas. Large scenes reduce device pixel ratio adaptively, reuse geometry and
materials, and avoid one JavaScript/Three.js object per visible atom.

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

Automatic and pairwise bonds use a spatial cell list above the small-scene
threshold. For repeated cells, one periodic candidate search supplies both
base-cell topology and internal supercell bridge records. Manual pairs bypass
neighbor inference.

Large scenes cache a `maximum cutoff + skin` neighbor candidate list. Actual
distances and pair cutoffs are still evaluated every frame, so bonds form and
break live. The candidate list is rebuilt when an atom moves more than half the
skin or when labels, visibility, cutoffs, cell, PBC, periodic policy, or
constraints change. Cylinder instance matrices are written directly to the GPU
buffer; unchanged topology reuses the existing instanced bond batches.

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

Reference result for the 0.0.78 working tree on the project development Mac:

| Check | Result |
| --- | ---: |
| Input size | 8,719,654 bytes |
| Backend input + server ready | 0.46 s |
| Browser navigation + first render | 0.38 s |
| Fully ready total | 0.84 s |
| Displayed atoms | 15,000 |
| Trajectory frames | 16 |
| Browser trajectory cache | 2,880,000 bytes |
| 16-frame translation update sweep | 18.1 ms |
| Mean position update | 1.13 ms/frame |
| Extra render frames during 0.9 s idle | 0 |

With automatic bonds enabled, the same synthetic scene contains 73,062 logical
bonds. Cached topology inference measured 8.3 ms, direct geometry-buffer update
12.5 ms, and a four-frame sweep that includes candidate-list rebuilds averaged
26.35 ms/frame.

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
- output preview/capture parity;
- inactive multi-document suspension.
