# v_ase Documentation Board

## Project Status
- [x] **Phase 1: Basic viewer** (Three.js, Box selection, Blender navigation)
- [x] **Phase 2: Basic editing** (G/R modal, numeric input, axis locking)
- [x] **Phase 3: ASE compatibility** (Constraints enforcement, Fixed atom visualization)
- [x] **Phase 4: Export** (POSCAR, Pickle, PNG image, Blender Python scene)
- [x] **Phase 5: Relax** (Real-time sync via WebSockets, fmax/energy monitoring)
- [x] **Phase 6: Jupyter** (IFrame support, non-blocking handle)
- [x] **Phase 7: Default calculator** (Repulsion fallback, optional torch/CUDA, CPU thread controls)
- [x] **Phase 8: Calculator API** (`from v_ase.calculators import RepulsionCalculator`)
- [x] **Phase 9: Interactive constraints** (selected-atom FixAtoms, FixedLine, FixedPlane editing)
- [x] **Phase 10: Portable state** (cross-structure JSON presets and complete `.vase` projects)
- [x] **Phase 11: Production export** (Geometry Nodes Blender scenes, exact Sun/camera, 15k-atom runtime benchmark)
- [x] **Phase 12: Document workflow** (empty GUI, browser file loading, strict ASE Pickle, JSON presets, and `.vase` projects)
- [x] **Phase 13: Commensurate rotation** (cell-boundary strain search, viewport candidate rays, magnetic angle snapping, and consistent free/axis-locked mouse direction)

## Core Documentation
- [Shortcuts & Controls](shortcuts.md)
- [Features & Architecture](features.md)
- [API Reference](api.md)
- [Rendering Performance](performance.md)
- [Commensurate Cell-Aware Rotation](unit_cell_aware_rotate.md)

## Getting Started
To run a comprehensive demo of all features:
```bash
python examples/pro_demo.py
v_ase gui
v_ase gui POSCAR
v_ase POSCAR
v_ase gui saved_project.vase
```
