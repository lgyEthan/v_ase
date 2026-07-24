# v_ase Documentation

## User Documentation

- [README](../README.md): installation, commands, controls, workflows, and exports.
- [Shortcuts](shortcuts.md): complete mouse and keyboard reference.
- [Commensurate Rotation](unit_cell_aware_rotate.md): cell-boundary matching,
  angle guides, snapping, and scientific references.

## Developer Documentation

- [Public API](api.md): Python API, CLI contract, save formats, and local API.
- [Architecture And Features](features.md): ownership boundaries and feature
  implementation contracts.
- [Performance](performance.md): large-system design, benchmark method, and
  regression checks.
- [Current Implementation](current_progress.md): concise source of truth for
  invariants, schemas, compatibility aliases, and release validation.

## Manual Validation

Open the all-features solid-state scene:

```bash
python tests/manual_showcase.py
```

Run the reproducible 15,000-atom browser benchmark:

```bash
python scripts/benchmark_large_trajectory.py
```
