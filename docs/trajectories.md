# Play and inspect trajectories

Step through structures, inspect stored values and export motion. Open an ASE
trajectory or supported multi-frame file; use the bottom timeline in View.

## Open a trajectory

```bash
v_ase gui trajectory.extxyz
v_ase gui XDATCAR --index :
v_ase gui relaxation.traj --index -1
v_ase gui dump.lammpstrj --stream-frames
```

`--index :` selects all frames, `-1` selects the last frame, and an integer
selects one zero-based frame. A loaded file starts in View unless
`--interactive` is supplied.

### Lazy and streamed sources

View mode can avoid materializing the whole trajectory:

- XDATCAR uses coordinate byte offsets when its layout can be proved safe;
- native ASE `.traj` uses random access;
- compatible numeric LAMMPS dumps use a byte-indexed, memory-mapped path; and
- `--stream-frames` requests frames individually for other supported local
  sources.

Remote `HOST:/path` inputs always keep frame storage and parsing on the remote
host. Switching to Edit materializes the frames required for topology-wide
physical operations. An unsupported fast layout falls back to the compatible
ASE reader instead of guessing.

## Timeline controls

Use the bottom timeline or keyboard:

| Control | Action |
| --- | --- |
| `Space` | Play or pause the active timeline |
| Left/Right Arrow | Previous or next active-timeline frame |
| Previous/Next buttons | Step one frame |
| **FPS** | Playback rate |
| **Skip** | Advance by more than one source frame |

v_ase can show several timeline kinds without merging them:

- **Source frames** loaded from a file or Python sequence;
- ordinary structure **Relaxation** frames;
- **Add Atoms** placement-relaxation frames; and
- **Rigid Translation** registry-relaxation frames.

The selected timeline alone receives playback and arrow-key input. Optimizer
timelines are mode state, not silently appended source trajectories.

### Add or replace frames

**Open** can replace the current document, append compatible frames, or open a
new tab. Appending keeps the active frame, camera, and visual state. Appending
a `.vase` imports only its structures; replacing or opening it in a new tab
restores the complete saved project.

If appended frames introduce new labels, v_ase registers them without
discarding existing appearance. A variable atom count or changed element order
is allowed for inspection but limits identity propagation and some analysis.

## Frame identity and selection

Selection persists by stable atom index when topology permits. For a stable
atom count and element order, View-mode visual labels and atom-index appearance
can follow the same particles through the trajectory. If topology is
incompatible, v_ase exposes the mismatch and limits changes to valid frames
instead of applying an incorrect identity globally.

Do not reuse an atom index merely because the viewport looks similar. Verify
the active frame, count, labels, chemical elements, and any particle-ID array
before a coordinate-dependent operation.


## Example: inspect a recorded contact-removal run

Download {download}`crowded_c60_relaxation.traj <assets/examples/crowded_c60_relaxation.traj>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui crowded_c60_relaxation.traj
```

1. Drag the timeline to frame 0 and inspect the crowded input.
2. Play, pause and step one frame at a time to compare intermediate geometry.
3. Choose original frames for scientific inspection. Interpolation creates a
   visual path between stored frames and adds no calculated dynamics.
4. Keep atom identity consistent before applying index selections across frames.
5. Export the chosen range through [Video export](export-video.md).

```{vase-animation} assets/readme_relaxation.gif
:alt: A saved relaxation sequence used as a trajectory playback example.
:fallback: assets/readme_relaxation.png

A saved relaxation sequence used as a trajectory playback example.
```


## Analysis frame synchronization

Changing a displayed frame refreshes every enabled frame-dependent result:

- RDF or finite pair distribution;
- atom colorscale values;
- stored force vectors;
- displacement vectors; and
- frame-associated volumetric surfaces and planes.

Ordinary-sized RDF frame/results are prefetched for smooth playback; larger
products use a bounded rolling window. A pending result may leave the previous
curve visible until calculation completes, but semantic verification must
confirm the reported result frame. A missing frame-associated volumetric field
is hidden rather than reusing stale data.
