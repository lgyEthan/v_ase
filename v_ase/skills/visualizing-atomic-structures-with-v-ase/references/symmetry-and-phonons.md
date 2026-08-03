# Symmetry And Phonons

## Contents

1. Scientific boundary
2. Dependencies and discovery
3. Space-group analysis
4. Reciprocal path
5. Standardized structures
6. Finite-displacement inputs
7. Loading force constants
8. Inspecting physical modes
9. Generating a mode trajectory
10. Verification and errors

## Scientific Boundary

Geometry alone can be displaced before a phonon calculation, but it does not
define a physical phonon branch. A uniform displacement of every atom is a
rigid translation. A physical mode at q requires force constants, the
q-dependent dynamical matrix, and its mass-weighted eigenvector.

Use `generate-phonon-displacements` to prepare external force calculations.
Use `inspect-phonon-modes` and `generate-phonon-mode` only after loading a
completed Phonopy YAML containing force constants.

## Dependencies And Discovery

Install this checked-out alpha:

```bash
python -m pip install -e ".[symmetry,phonon]"
```

Call `schema` and read `scientific_endpoints`. Missing optional dependencies
produce HTTP 424. Input/cell errors produce HTTP 400. Do not suppress either.

## Space-Group Analysis

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "operation":{
    "name":"analyze-symmetry",
    "symprec":1e-5,
    "angleTolerance":-1,
    "typeBasis":"element",
    "magnetic":false,
    "toleranceScan":true
  }
}'
```

`typeBasis: "element"` uses ASE chemical elements as crystallographic types
and reports when custom labels were ignored. `"label"` uses each
`(element,label)` pair as a distinct type. Use label basis only when labels
encode physically distinct sites, not merely colors or display names.

Verify `describe().analysis.symmetry`: international symbol/number, point
group, operation count, independent orbits, Wyckoff letters, site symmetries,
type basis, tolerances, and warnings. Analysis must not change coordinates,
frame count, history, selection, or camera.

## Reciprocal Path

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "operation":{
    "name":"symmetry-path",
    "symprec":1e-5,
    "angleTolerance":-1,
    "typeBasis":"element"
  }
}'
```

Verify `describe().analysis.symmetryPath` has a nonempty HPKOT path, named
reduced reciprocal coordinates, reciprocal primitive lattice, and the expected
space group. SeeK-path may standardize the primitive reciprocal basis; do not
assume the labels are coordinates in the original reciprocal basis.

## Standardized Structures

This is destructive to the current trajectory and therefore low freedom:

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "mode":"edit",
  "operation":{
    "name":"standardize-symmetry",
    "transform":"conventional",
    "symprec":1e-5,
    "angleTolerance":-1,
    "typeBasis":"element",
    "idealize":true
  }
}'
```

`transform` is `primitive`, `conventional`, or `refine`. Confirm user intent,
record the source count/cell, execute once, then verify the result count/cell
and `symmetry_transform.warnings`. Constraints, calculators, and unmapped
per-atom arrays are deliberately removed when ordering or multiplicity
changes. Verify `undo` restores the full prior trajectory.

## Finite-Displacement Inputs

No force constants are required:

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "mode":"edit",
  "operation":{
    "name":"generate-phonon-displacements",
    "supercell":[2,2,2],
    "distance":0.01,
    "symprec":1e-5
  }
}'
```

This replaces the document trajectory with symmetry-reduced displaced
supercells for external force calculations. Verify:

- `phonon.forces_required` is true;
- frame count equals `phonon.displacement_count`;
- every frame has the same supercell, identity, ordering, and PBC;
- displacement magnitude and supercell matrix match the request;
- no frequency or physical mode is claimed;
- `undo` restores the original trajectory.

## Loading Force Constants

The agent must upload a completed Phonopy YAML as bytes. Derive the loopback
origin and active `session_id` from the handshake/state, then use the endpoint
template returned by `schema.scientific_endpoints.phonopy_upload`:

```bash
curl --fail-with-body -X POST \
  -H "Content-Type: application/octet-stream" \
  --data-binary @phonopy_params.yaml \
  "$ORIGIN/api/analysis/phonon/load/$SESSION_ID?filename=phonopy_params.yaml"
```

Do not send a local path inside `apply()` and do not expose the session URL.
The YAML must contain force constants for mode inspection. Verify the response
has `has_force_constants: true`, unit/primitive/supercell atom counts, matrix,
and THz frequency unit. Upload is rejected unless its atom order, elements,
cell metric, and periodic positions match the active structure. A rigid
Cartesian cell rotation or common periodic origin shift is aligned
automatically; a non-rigid lattice-basis change is rejected. The loaded model
is document-local runtime state and is not serialized into a normal `.vase`
project in this alpha.

## Inspecting Physical Modes

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "operation":{
    "name":"inspect-phonon-modes",
    "qpoint":[0.5,0,0],
    "projectionDirection":[1,0,0]
  }
}'
```

Optional `nacDirection` defines the limiting direction at Gamma when the
loaded model supports non-analytical corrections. `projectionDirection` is
normalized and reports each mode's polarization fraction along that Cartesian
direction. It ranks calculated eigenmodes; it does not invent or rotate one.

Verify `describe()` reports the q-point, band count, THz frequencies, imaginary
flags, dominant axis/atom, and projection fraction. The semantic state is
deliberately compact. Call the direct `phonon_modes` scientific endpoint from
`schema.scientific_endpoints` only when full participation arrays and complex
eigenvectors are required. Negative frequencies remain visible as imaginary
modes.

## Generating A Mode Trajectory

Use a 1-based band and a mode supercell commensurate with q:

```bash
v_ase api "$COMMAND_URL" apply --params '{
  "mode":"edit",
  "operation":{
    "name":"generate-phonon-mode",
    "qpoint":[0.5,0,0],
    "band":4,
    "amplitude":0.10,
    "phaseDegrees":0,
    "dimension":[2,1,1],
    "frames":24,
    "oscillation":true
  }
}'
```

The periodicity condition is `P.T @ q = integer`, where `P` is the requested
integer mode-supercell matrix. An incommensurate request must fail instead of
creating a discontinuous structure.

Phonopy's modulation convention is used:

```text
u_jl = A / sqrt(N_a m_j)
       Re[exp(i phi) e_j(q,nu) exp(i q.r_jl)].
```

Verify q-point, 1-based band, frequency, imaginary flag, amplitude, all phases,
commensurability residual, frame count, atom count, cell, and a nonzero
displacement. For one frozen structure set `frames: 1` and
`oscillation: false`. Verify `undo` restores the prior trajectory.

Generated mode coordinates are unwrapped around the corresponding
unmodulated-supercell atom. Consecutive frames must remain continuous when an
atom crosses a cell boundary; a jump by one lattice vector is a failed
trajectory even though the two coordinates are periodically equivalent.

## Verification And Errors

Use this low-freedom sequence:

1. Plan the requested physical operation and state whether force constants are
   required.
2. Validate cell invertibility, 3D PBC, atom identity basis, q-point, band,
   amplitude, and supercell matrix.
3. Execute one operation with the current collaboration revision.
4. Describe the semantic result and verify every field above.
5. Render a clear frame or play the generated trajectory.
6. Inspect pixels for nonblank atoms and visible displacement.
7. Undo a test mutation or save to a new output only after verification.

Never reinterpret an arbitrary trial displacement as a calculated eigenmode,
hide an imaginary frequency, bypass `P.T @ q`, or silently preserve stale
calculator/constraint data after standardization. Reload force constants after
a physical coordinate, element, topology, or cell edit; label-only changes are
safe and are propagated to generated mode trajectories.
