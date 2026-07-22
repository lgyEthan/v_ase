# v_ase - Current Public Surface

The PyPI distribution is `v_ase-gui`; the Python package and command remain
`v_ase`.

## Current Public Surface
- Python API: `from v_ase.visualize import view`
- Convenience imports: `from v_ase import view, view_edit, view_file`
- Calculator API: `from v_ase.calculators import RepulsionCalculator`
- Calculator aliases: `from v_ase import RepulsionCalculator`, `from v_ase.calculator import RepulsionCalculator`, and `from v_ase.repulsion import RepulsionCalculator`
- CLI: `v_ase gui FILE`
- Empty file-loading workspace: `v_ase gui`
- ASE-style shortcut: `v_ase FILE`
- Default mode: lightweight visualization
- Atom-editing mode: `v_ase gui FILE --interactive`

## Implemented Viewer Features
- Browser-based Three.js viewport for ASE `Atoms` objects and trajectories,
  including live movie scrubbing, FPS, and frame skip.
- GPU-instanced, demand-rendered atoms, bonds, and supercell replicas for large
  structures; the default visualization mode omits edit/calculator overhead.
- Blender-style selection and modal transforms in interactive mode.
- Constraint-aware editing for ASE constraints including `FixAtoms`, `FixCartesian`, `FixedLine`, `FixedPlane`, `FixScaled`, and `Hookean`.
- Hookean constraint visualization with inactive cutoff gap, threshold gate, lock marker, and active spring.
- Existing ASE calculators are preserved. Interactive mode adds the default
  soft repulsion calculator only when no calculator is attached, with optional
  torch CPU/CUDA acceleration and a NumPy fallback.
- Relaxation can restart from newly edited coordinates while it is already
  running in interactive mode.
- Label-pair bond cutoffs, manual bonds, cell-local/MIC display, live bond
  topology updates, supercell preview, and supercell-to-cell conversion.
- Full-frame output-ratio image preview, PNG/WebM, POSCAR, ASE pickle, and
  optimized Blender Python scene export.
- Reusable visual-settings JSON and complete validated `.vase` project save/load.
- Browser Open preserves the active visual settings and camera when replacing an
  ordinary structure or trajectory; `.vase` restores its own complete state.
- Supercell replicas share the source atoms' exact material and lighting response
  in both modes, with mode-specific selection behavior only.
- ASE chemical TYPE controls default color and radius; custom labels remain
  independently selectable and styleable without implicit color drift.
- Optional relaxation when an ASE calculator is attached.

## Packaging Changes
- The implementation moved from the old prototype package layout into `v_ase/`.
- `pyproject.toml` defines the `v_ase-gui` distribution and `v_ase` console script.
- Static browser assets are packaged from `v_ase/static/`.
- Tests and documentation now use the `v_ase` import path.
