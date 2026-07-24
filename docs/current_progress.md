# Current Implementation Contract

This document is the concise implementation source of truth for maintainers.
User-facing behavior belongs in the [README](../README.md); scientific
cell-rotation details belong in
[unit_cell_aware_rotate.md](unit_cell_aware_rotate.md).

## Product Contract

- Distribution: `v_ase-gui`
- Python package and console command: `v_ase`
- Primary Python entry point: `from v_ase.visualize import view`
- CLI entry points: `v_ase gui` and `v_ase gui FILE`
- Default mode: visualization-only
- Editable mode: `--interactive` or `view(..., viz_only=False)`
- Full project format: `.vase`
- Reusable presentation preset: visual-settings JSON

`view_edit()` remains a compatibility alias for interactive mode. New examples
and documentation use `view()`.

## Ownership Boundaries

### Python Backend

- `v_ase/io.py`: canonical file-format aliases and structure/trajectory input.
- `v_ase/session.py`: document state, history, calculator-preserving copies,
  trajectory sources, and workspace lifetime.
- `v_ase/server.py`: local FastAPI and WebSocket contract.
- `v_ase/project.py`: visual-settings migration and validated `.vase` archives.
- `v_ase/serialization.py`: browser payloads and ASE visual defaults.
- `v_ase/export.py`: scientific, image-supporting, Blender, 3DM, and OBJ export.
- `v_ase/viewer.py`: Python API and local server lifecycle.

### Browser Frontend

- `static/main.js`: application state, UI workflows, API orchestration, and
  trajectory playback.
- `static/renderer.js`: Three.js scene, camera, instancing, bonds, constraints,
  supercells, lighting, measurements, and capture.
- `static/selection.js`: click and box-selection hit testing.
- `static/transform.js`: modal move/rotate state.
- `static/api.js`: typed local HTTP payload handling and download helpers.
- `static/workspace.js`: independent multi-document shell.

## Core Invariants

1. The caller's original `Atoms` object is never mutated.
2. Structural edits use a working copy and preserve supported calculators.
3. ASE is authoritative for constrained commits:
   `Atoms.set_positions(..., apply_constraint=True)`.
4. Browser previews may be immediate, but committed coordinates return from the
   backend.
5. Left drag is box selection; middle drag is unrestricted orbit.
6. Renderer inertia/damping is disabled.
7. Visualization mode does not attach the fallback calculator or maintain
   interactive edit history it cannot use.
8. Interactive supercell replicas are display-only until committed as the
   current cell; visualization-mode replicas remain selectable and measurable.
9. Label identity and chemical TYPE are independent. Labels key appearance,
   selection, and pairwise cutoffs; ASE chemical symbols control element
   defaults and calculations.
10. Settings survive structure refreshes and trajectory changes. Ordinary file
    Open reconciles the active visual state; `.vase` replaces it.
11. Demand rendering must remain idle when camera, structure, playback, and UI
    are unchanged.

## Canonical Names And Compatibility

Visual settings use schema `v_ase.visual_settings.v3`.

Canonical display keys:

- `pairwiseBondCutoffs`
- `labelRadii`
- `labelColors`
- `labelVisible`
- bond mode `pairwise`

Loaders migrate the previous `elementBondCutoffs`, `elementRadii`,
`elementColors`, `elementVisible`, and bond mode `element` names. Saved output
contains only canonical v3 keys.

Canonical Python label helpers are `atom_labels()` and `set_atom_labels()`.
`atom_type_labels()`, `set_atom_type_labels()`, and `ATOM_TYPE_ARRAY` remain
compatibility aliases for code written against v_ase 0.0.77 or earlier.

Canonical atom-identity route:

```text
POST /api/atom-identity/{session_id}
```

The old `/api/atom-types/{session_id}` route remains hidden and forwards to the
same implementation for compatibility.

## Data And Save Contracts

- ASE Pickle contains the current `Atoms`, labels, constraints, portable arrays,
  and valid `SinglePointCalculator` results. It excludes visual state and
  arbitrary executable calculators.
- Visual Settings JSON contains presentation state but no coordinates.
- `.vase` is a validated ZIP archive containing every trajectory frame, current
  frame, edits, cells/PBC, constraints, labels, safe arrays and metadata,
  cached standard results, supported built-in calculator configuration, and
  visual settings. It does not reference the source file.
- Browser Open keeps visual state for ordinary structures and trajectories.
  Opening `.vase` restores the project state instead.

## Performance Contract

- Atoms, bonds, selections, and supercell replicas use GPU instancing.
- The renderer is request-driven and has no permanent animation loop.
- Large numeric LAMMPS dumps are memory-mapped and byte-offset indexed.
- Compatible trajectories are transferred once as contiguous float32
  coordinates for playback.
- Position-only frame updates modify instance translation columns rather than
  rebuilding geometry or complete matrices.
- Auto and pairwise bonds use a cell-list search with a displacement-validated
  neighbor candidate cache for large structures.
- Bond cutoff checks remain live each frame; cylinder instance matrices are
  written directly into GPU buffers.
- Supercell boundary topology is inferred once per update and reused for direct
  and replica-bridge bonds.
- Modeling mode allocates no shadow map; rendered lighting cost is opt-in.
- Inactive workspace tabs suspend rendering and playback.
- Local servers use readiness polling and are stopped/joined by their owning
  editor or blocking session.

Current benchmark method and results are in [performance.md](performance.md).

## Validation Before Release

1. `python -m compileall -q v_ase tests scripts`
2. JavaScript syntax checks for every first-party module.
3. Full `pytest` suite.
4. Real Chromium browser workflows, including large trajectories, supercells,
   bonds, constraints, preview/export parity, and multiple documents.
5. 15,000-atom browser benchmark with zero idle render frames.
6. Blender runtime and 15,000-atom optimized scene benchmark when Blender is
   available.
7. Rhino export tests in an environment containing `rhino3dm`.
8. Wheel and sdist build, metadata check, clean-environment installation,
   `v_ase --version`, and console entry-point execution.
9. Documentation and displayed/static version synchronization.
