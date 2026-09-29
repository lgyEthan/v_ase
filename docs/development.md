# Contributing to v_ase

Architecture, scientific validation, performance notes, documentation policy,
and the release contract for contributors and maintainers.

## Work on the source

```bash
git clone https://github.com/lgyEthan/v_ase.git
cd v_ase
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

For desktop builds, use the [desktop source guide](https://github.com/lgyEthan/v_ase/blob/main/desktop/README.md).
To install and use the released app, start with [Installation](installation.md).

## Contributor reference

```{toctree}
:maxdepth: 1

features
current_progress
performance
scientific-validation
scientific-source-audit
unit_cell_aware_rotate
commensurate_validation
contributing-docs
release_checklist
```
