# Symmetry And Phonon Methodology

## Contents

- [Scope](#scope)
- [Crystallographic identity](#crystallographic-identity)
- [Symmetry analysis](#symmetry-analysis)
- [Finite-displacement preparation](#finite-displacement-preparation)
- [Physical phonon modes](#physical-phonon-modes)
- [Mode modulation](#mode-modulation)
- [Commensurability](#commensurability)
- [Validation](#validation)
- [Reproducible README examples](#reproducible-readme-examples)
- [Data handling](#data-handling)
- [Dependencies and references](#dependencies-and-references)

## Scope

This document describes the experimental `symmetry` branch. It separates two
operations that must not be confused:

1. **Preparing displaced structures:** possible before force constants exist.
2. **Following a physical phonon eigenmode:** requires force constants and the
   dynamical matrix at the requested q-point.

An arbitrary edit can be a useful trial geometry, but it is not automatically
a normal mode. Moving every atom by the same vector is a rigid translation.

## Crystallographic Identity

The symmetry panel offers two type bases:

- `element`: atoms with the same chemical element may be symmetry-equivalent;
  custom v_ase labels are ignored and a warning is reported.
- `label`: the pair `(chemical element, v_ase label)` defines a distinct
  crystallographic type.

`label` is useful for deliberately distinct sites. It can also lower the
detected symmetry when labels are only visualization metadata, so `element` is
the default.

## Symmetry Analysis

spglib supplies:

- international space-group symbol and number;
- Hall symbol, Hall number, choice, and point group;
- symmetry rotations and translations;
- Wyckoff letters and site-symmetry symbols;
- equivalent atoms and crystallographic orbits;
- primitive and standardized-cell mappings.

v_ase also scans nearby positional tolerances. A space group that changes over
the scan should be treated as tolerance-sensitive rather than reported as an
unqualified exact result.

Partial-PBC structures are reported with a warning because spglib performs
three-dimensional periodic symmetry analysis. Slab results therefore depend on
the supplied vacuum cell.

Primitive, conventional, and refined structures are created through spglib.
When atom ordering or multiplicity changes, v_ase removes constraints,
calculator state, and per-atom arrays without an exact mapping instead of
silently attaching stale data.

## Finite-Displacement Preparation

Finite-displacement inputs do not require pre-existing phonon results. Phonopy
uses the unit-cell symmetry and requested supercell matrix to reduce the set of
displaced supercells. Each generated frame is an input for an external force
calculation.

The workflow is:

1. choose a valid 3D periodic unit cell;
2. select the supercell matrix and displacement distance;
3. generate symmetry-reduced displaced structures;
4. calculate forces for every structure;
5. construct force constants in Phonopy;
6. save a completed phonopy YAML project.

No frequency or physical eigenmode is inferred from the uncalculated
displacement inputs.

## Physical Phonon Modes

Using Phonopy's phase convention, the dynamical matrix is

```text
D_ab(jj', q) = 1 / sqrt(m_j m_j')
               sum_l' Phi_ab(j0, j'l')
               exp(i q . [r(j'l') - r(j0)])
```

and a normal mode satisfies

```text
sum_j'b D_ab(jj', q) e_b(j', q nu)
    = omega(q nu)^2 e_a(j, q nu).
```

Therefore a physical band direction requires force constants `Phi`, the
q-dependent dynamical matrix, and its eigenvector `e(q, nu)`. Geometry alone
cannot provide the frequency or the eigenvector mixing at that q-point.

v_ase reports each mode's frequency, imaginary-frequency flag, dominant
Cartesian axis, atom participation, longitudinal fraction when q is nonzero,
and optional projection onto a user-specified Cartesian direction.

The projection fraction is

```text
P_d(q, nu) = sum_j |e_j(q, nu) . d_hat|^2
             / sum_j |e_j(q, nu)|^2.
```

It ranks existing eigenmodes by polarization. It does not replace or rotate the
calculated eigenvectors.

## Mode Modulation

v_ase delegates frozen-mode structures to Phonopy's modulation implementation.
For atom `j` in cell `l`, Phonopy uses

```text
u_jl = A / sqrt(N_a m_j)
       Re[exp(i phi) e_j(q, nu) exp(i q . r_jl)].
```

`A` is the requested amplitude, `phi` is the phase, `N_a` is the number of
atoms in the modulation supercell, and `m_j` is the atomic mass. Multiple
frames sample phase values over one display cycle. This is a visualization of
the selected harmonic mode, not a molecular-dynamics time integration.

Phonopy writes modulated coordinates wrapped into the requested supercell.
For trajectory display, v_ase resolves each periodic displacement relative to
the corresponding unmodulated supercell atom. Coordinates therefore remain
continuous when an atom oscillates across a cell boundary; this changes only
the periodic image shown, not the physical modulation.

Negative frequencies are shown as imaginary modes and are not hidden. Their
interpretation depends on convergence, cell choice, and the physical system.

## Commensurability

A periodic modulation requires the selected supercell matrix `P` and reduced
q-point to satisfy

```text
P^T q = integer vector.
```

v_ase rejects an incommensurate request and reports the residual instead of
creating a discontinuous periodic structure.

At Gamma with non-analytical corrections, the optional NAC direction defines
the limiting direction. Away from Gamma, the q-point itself determines the
direction used by Phonopy.

## Validation

The scientific regressions compare the implementation against published or
canonical reference cases:

- Diamond Si at 298 K uses `a = 5.4304 A` and space group `Fd-3m` (No. 227)
  in [COD 9013102](https://www.crystallography.net/cod/9013102.html). The test
  checks No. 227, point group `m-3m`, one `-43m` symmetry-independent site,
  the two-atom primitive cell, and the eight-atom conventional cell. The
  Wyckoff letter may be `a` or `b` under the two accepted origin choices.
- The fcc reciprocal path is checked against the crystallography-derived HPKOT
  convention implemented by SeeK-path: `GAMMA-X`, `X-U`, `K-GAMMA`,
  `GAMMA-L`, `L-W`, and `W-X`.
- A nearest-neighbour monatomic chain is checked against
  `omega(q) = 2 sqrt(K/M) |sin(qa/2)|`. The Gamma acoustic frequency is zero,
  the zone-boundary mode is longitudinal, and the frequency ratio at one
  quarter of the reciprocal coordinate is `sin(pi/4)`.
- Mode trajectories are generated by Phonopy itself and tested for requested
  phase count, nonzero displacement, atom-label retention, isotope-mass
  retention, continuous boundary motion, and `P^T q` commensurability for both
  diagonal and non-diagonal integer supercell matrices.

These regressions validate the implementation and conventions. Synthetic force
constants used in UI plumbing tests are not presented as a physical silicon
phonon model.

## Reproducible README Examples

Run the branch-local generator from the repository root:

```bash
conda run -n python311 python scripts/capture_symmetry_readme_assets.py
```

It recreates the files under `examples/symmetry_branch/`, opens those exact
structures in v_ase, and captures the four Analysis-panel figures under
`docs/assets/` and `docs/assets/github/`.

The examples cover separate scientific states:

| Example | Verified state |
| --- | --- |
| Diamond-Si primitive cell | `Fd-3m` No. 227, `m-3m`, 48 operations, one site, HPKOT cF path |
| Diamond-Si conventional cell | explicit 2-to-8 atom standardization, 192 conventional-cell operations |
| NaCl 2 x 2 x 2 finite displacements | two 16-atom force-calculation inputs at 0.01 A; no force constants |
| fcc-Al X-point mode | ASE EMT forces, Phonopy force constants, band 3 at 7.9188 THz, commensurate 4 x 4 x 2 movie |

The Al example uses a real dynamical-matrix eigenvector produced from the
included force constants. EMT is selected to make the example fast and fully
reproducible; its numerical frequency is a workflow regression, not a
reference-quality prediction for aluminum.

## Data Handling

- Symmetry analysis and reciprocal-path queries do not mutate the structure.
- Standardization and generated trajectories require Edit mode and create an
  Undo checkpoint.
- A newly opened document clears the document's loaded phonopy model.
- A phonopy project is accepted only when atom order, elements, cell, and
  periodic fractional positions match the active structure.
- A rigid Cartesian rotation and common periodic origin shift are aligned to
  the active scene. A different lattice metric or non-rigid basis change is
  rejected.
- Physical coordinate, element, topology, or cell edits invalidate the loaded
  phonopy model; Undo restores the prior structure and model together.
- A label-only edit preserves the model and updates labels used by generated
  mode trajectories.
- Phonopy models are held in the current document session; they are not
  serialized into a normal `.vase` project in this experimental branch.
- Standardization never reuses cached calculator results for a changed cell.

## Dependencies And References

Install all experimental backends from the repository root:

```bash
python -m pip install -e ".[symmetry,phonon]"
```

Primary implementations and methodology:

- [Phonopy formulation](https://phonopy.github.io/phonopy/formulation.html)
- [Phonopy modulation settings](https://phonopy.github.io/phonopy/setting-tags.html#modulation)
- [Phonopy Python API](https://phonopy.github.io/phonopy/phonopy-module.html)
- [spglib Python interface](https://spglib.readthedocs.io/en/stable/python-interface.html)
- [spglib symmetry dataset](https://spglib.readthedocs.io/en/stable/dataset.html)
- [SeeK-path documentation](https://seekpath.readthedocs.io/en/latest/)
- [Hinuma et al., Band structure diagram paths based on crystallography,
  Computational Materials Science 128, 140-184
  (2017)](https://doi.org/10.1016/j.commatsci.2016.10.015)
- [Togo et al., Implementation strategies in phonopy and phono3py,
  J. Phys.: Condens. Matter 35, 353001
  (2023)](https://doi.org/10.1088/1361-648X/acd831)
- [Togo and Tanaka, First-principles phonon calculations in materials science,
  Scripta Materialia 108, 1-5
  (2015)](https://doi.org/10.1016/j.scriptamat.2015.07.021)

v_ase calls these open-source Python APIs. It does not copy another
application's UI assets or proprietary implementation.
