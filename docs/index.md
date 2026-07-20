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

## Core Documentation
- [Shortcuts & Controls](shortcuts.md)
- [Features & Architecture](features.md)
- [API Reference](api.md)
- [Rendering Performance](performance.md)
- [Unit-Cell-Aware Rotate](unit_cell_aware_rotate.md)

## Getting Started
To run a comprehensive demo of all features:
```bash
python examples/pro_demo.py
v_ase gui POSCAR
v_ase POSCAR
```
