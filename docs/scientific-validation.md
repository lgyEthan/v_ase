# Scientific validation

This page records what the 0.3.1 audit establishes and how to reproduce it.
It separates mathematical correctness of a calculation from physical validity
of the model supplied to that calculation.

```{contents} On this page
:local:
:depth: 1
```

## Scope and independent references

| Feature | Independent check | Interpretation boundary |
| --- | --- | --- |
| Random positions | Fractional moments and voxel occupancy in skew cells | Uniform volume sampling, not thermodynamic sampling |
| Homogeneous positions | Exact ASE triclinic MIC; spacing and probe coverage | Bounded greedy construction, not optimal packing |
| Repulsion | Analytic harmonic derivative, finite differences, momentum/torque, cell repetition | Overlap penalty, not a material potential |
| Commensurate search | Analytic hexagonal series, published strain components, unscreened small searches | Finite lattice search, not interface energy minimization |
| RDF | Explicit image enumeration and concentration reconstruction | Bulk or finite-system normalization, not a slab correction |
| Scalar grids | Known integrals, axis order, endpoint conventions, cancellation | Source values and display approximations remain distinct |
| GUI and CLI | Live semantic state, exact pixel sizes, exports, revision rejection | HTTP success alone is insufficient |

The periodic pair definition follows the shift-vector convention in the
[ASE neighbor-list reference](https://docs.ase-lib.org/ase/neighborlist.html).
For commensurate matching, [Stradi et al.](https://arxiv.org/abs/1702.00933)
describe integer supercells, relative rotation, and strain-based comparison.
v_ase uses a different bounded HNF/reduced-basis implementation and a singular-
value acceptance criterion; the paper-style mean strain is an additional plot
descriptor. See [commensurate validation](commensurate_validation.md) for exact
equations, fixtures, and citations.

## Corrections found during the audit

### Energy and force consistency

The old default applied `10*tanh(|F|/10)` to the magnitude of each force while
reporting the unmodified harmonic energy. Even small forces changed. The
default is now uncapped for both the fallback and placement calculators;
explicit legacy caps remain available in Python and are documented as
nonconservative. Exact overlaps still need deterministic symmetry breaking.

Periodic pairs previously omitted interactions with images of the same basis
atom. For one atom in a 1 Å cubic cell, a 1.2 Å onset and unit strength give
six neighbors and energy `3 × 0.5 × 0.2² = 0.06 eV` per cell. The corrected
calculator returns that value and the same energy per atom after repetition.
Rigid molecule copies interact across periodic boundaries; only pairs internal
to the reference molecule are excluded.

Numeric `min_bondinfo` now controls its absolute onset when no explicit global
distance overrides it. Changing the covalent/van-der-Waals basis updates the
actual calculator reference as well as its status.

### Chemical assignment in generated structures

Grid traversal and maximin selection have spatial order. Assigning successive
species blocks directly to that order could impose artificial chemical
segregation or species-dependent spacing. A seeded permutation of sampled sites
now assigns mixed atoms and molecular anchors while preserving entry order,
counts, labels, and rigid-group identities.

### RDF boundaries and invalid inputs

Periodic histograms now include the exact final cutoff edge within roundoff,
matching the finite-distribution and NumPy histogram convention. Fractional,
Boolean, NaN, and infinite bin counts fail clearly. Nonfinite coordinates or
periodic cells fail before neighbor search. The existing shell normalization,
periodic image enumeration, and partial weighting remain unchanged.

### Field arithmetic and integration

The old endpoint-inclusive integral dropped every last plane, including real
finite boundaries. The corrected integration drops redundant periodic planes
and uses trapezoidal weights on finite axes. It integrates affine test fields
exactly in both fully finite and mixed-boundary triclinic grids.

Linear combinations now accumulate each bounded slab in FP64 before one cast
to the selected storage type. For FP32 inputs `1e8 + 1 − 1e8`, the representable
answer 1 is retained instead of rounding to zero after the first addition.
This cannot repair precision lost when reading the original input in FP32.

The semantic combination operation now uses `resultName`. Earlier documentation
used duplicate `name` keys, overwriting the command selector. A real CLI/browser
test now checks the resulting name, integral, and unchanged input fields; all
documentation JSON blocks are checked for duplicate keys.

### Commensurate geometry

The former normal-alignment cutoff 0.985 admitted nearly 10° of tilt. Such
inputs could appear valid after projection while hiding out-of-plane mismatch.
The new tolerance is `1 − 1e-10`; tilted planes are rejected before matching.
Maximum principal strain remains the acceptance criterion, and the GUI now
explains its meaning at the control.

### Fresh-agent state and reopening checks

An independent agent used the canonical Skill and HTTP JSON bridge in its own
sessions. It found three additional gaps: hidden force arrows left semantic
trajectory arrays stale; copying a frame dropped stored calculator results;
and initial project loading restored plane descriptors without sampling their
rasters. The corrected paths read stored frame properties without calculator
evaluation and await saved plane rendering before readiness. Browser regressions
verify exact forces/tags/charges and actual raster pixels after project reopening.

The same evaluation clarified document-versus-placement calculator state,
active commensurate proposal angle, adaptive preview halo, and CSV area bounds.
An explicit preview-fit control now frames all visible preview geometry without
changing the default camera-preservation behavior.

## Repulsion performance

The overlap fallback now groups candidate coincidences in NumPy before entering
Python. Normal optimizer steps avoid a per-atom dictionary loop and a full
neighbor-pair set. The measured energy and forces agreed with the old kernel
to `1e-10` for the benchmark configurations.

Median calculation times on the release development machine, NumPy backend,
periodic random H at 0.025 atoms/Å³, 2 Å onset, seed 73; five timed repetitions
after one warmup:

| Atoms | Before | 0.3.1 | Ratio |
| ---: | ---: | ---: | ---: |
| 1,000 | 7.62 ms | 2.35 ms | 3.25× |
| 5,000 | 16.34 ms | 7.89 ms | 2.07× |
| 12,000 | 34.51 ms | 21.17 ms | 1.63× |

These are kernel measurements, not end-to-end optimizer or GPU speedups.
Density, cutoffs, labels, hardware, and exact overlaps change the cost. The
calculator still uses matscipy's neighbor search and bounded interaction lists;
homogeneous placement retains its explicit 1,024-entity refinement limit.

## Reproduce the validation

Run the focused analytic and oracle tests:

```bash
python -m pytest -q tests/test_scientific_audit.py tests/test_matscipy_scientific_equivalence.py tests/test_rdf_analysis.py tests/test_commensurate.py tests/test_volumetric.py
```

Run the complete release matrix, including browser and notebook tests:

```bash
python -m pytest -q
python scripts/capture_readme_screenshots.py
python -m build
python -m twine check dist/*
```

Use a Python environment with the development dependencies and Playwright
Chromium installed, and permission to bind local TCP ports. Browser tests must
actually run rather than being counted as successful skips. Optional external
applications are reported separately when unavailable. Follow the complete
[release checklist](release_checklist.md) for documentation builds, publication,
and a clean installation of the published wheel.
