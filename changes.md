# v_ase - Wrap-up Summary

This project is now packaged under the single public name `v_ase`.

## Current Public Surface
- Python API: `from v_ase.visualize import view`
- Convenience imports: `from v_ase import view, view_edit, view_file`
- CLI: `v_ase gui FILE`
- ASE-style shortcut: `v_ase FILE`

## Implemented Viewer Features
- Browser-based Three.js viewport for ASE `Atoms` objects and trajectories.
- Blender-style selection and modal transforms.
- Constraint-aware editing for ASE constraints including `FixAtoms`, `FixCartesian`, `FixedLine`, `FixedPlane`, `FixScaled`, and `Hookean`.
- Hookean constraint visualization with inactive cutoff gap, threshold gate, lock marker, and active spring.
- Periodic bond inference, element-pair cutoff controls, supercell preview, and supercell-to-cell conversion.
- Viewport image export, POSCAR export, pickle export, and Blender Python scene export.
- Optional relaxation when an ASE calculator is attached.

## Packaging Changes
- The implementation moved from the old prototype package layout into `v_ase/`.
- `pyproject.toml` defines the `v_ase` distribution and `v_ase` console script.
- Static browser assets are packaged from `v_ase/static/`.
- Tests and documentation now use the `v_ase` import path.
