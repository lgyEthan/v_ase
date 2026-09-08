# Add, copy and delete atoms

Create atoms, build a bulk crystal, or edit an existing fragment. Use **Edit**
for topology changes. Use [Distributions](atomic-distributions.md) for batches
and [Molecule insertion](molecules.md) for complete molecules.

## Example: add oxygen to a Cu host

Download {download}`Cu(111) host <assets/examples/cu111_oxygen_add_atoms.traj>`.

1. Open in Edit and inspect the initial **210 Cu atoms**.
2. Use **+ Add atoms > Batch > Atoms** to add **18 O** with LABEL `O_subsurface`.
3. Follow the [insertion-region example](insertion-regions.md) for its exact
   bounds, seed and relaxation settings.
4. Finish the staging session. The structure now contains **228 atoms**;
   the original Cu coordinates are unchanged. Undo restores the baseline.

![Oxygen added inside a bounded Cu host region](assets/readme_add_atoms.png)

For a single new atom or an ASE bulk crystal, use the controls below.

## Build from an empty document

Run:

```bash
v_ase gui
```

The empty document starts in Edit. A typical periodic workflow is:

1. Open **Structure > Cell & Replication**.
2. Enter the Cartesian `3 x 3` cell matrix and choose the three PBC axes.
3. Select **Set Unit Cell**. This defines the ASE cell without scaling or
   moving any atom.
4. Open **+ Add atoms** and use **Single**, **Batch**, or **Build with ASE**.
5. Inspect labels, positions, cell, and PBC before saving.

A finite nonperiodic model can be built without a cell. Batch placement then
requires at least one finite **Allow** region because a Reject-only or unbounded
domain has no finite sampling volume.

## Add one atom

Open **+ Add atoms > Single** in Edit:

1. Choose the chemical **Type**.
2. Enter a visual **Label**.
3. Enter Cartesian **Position / Å**, or initialize it from **View Center** or
   **Selection**.
4. Select **Add** and verify the new index and element.

Typing a valid element symbol as the label also selects that type in the GUI,
but a later explicit Type choice is authoritative. Automation should always
send the element and label separately rather than infer a chemical element
from an arbitrary label.

## Build a periodic bulk crystal with ASE

Use **+ Add atoms > Build with ASE**. The panel executes the installed
`ase.build.bulk` rather than a copied structure table.

1. Enter a formula.
2. Choose **Automatic from ASE** or an explicit prototype.
3. Choose a compatible **Native / primitive**, **Orthorhombic**, or **Cubic**
   cell form.
4. Supply the enabled lattice parameters, angle, `c/a`, internal `u`, or
   fractional `N x 3` basis as requested.
5. Select **Validate**. Review the exact atom count, lengths, angles, and any
   structured missing-field message.
6. Select **Build Structure**.

Automatic reference data is available only where the installed ASE version
provides it. A custom compound such as CuO needs an explicit compatible
prototype and lattice parameter. `c` and `c/a` are mutually exclusive.

Building creates one fully periodic frame and clears the previous trajectory.
A nonempty document is replaced only after confirmation, and the whole change
is one Undo entry.

## Copy, paste, duplicate, and delete

`Ctrl+C` and `Ctrl+V` copy selected atoms and paste an exact-coordinate
duplicate near the selected center. A duplicate preserves:

- ASE element and complete visual label;
- position, tag, charge, magnetic moment, and portable per-atom arrays;
- compatible per-atom constraints;
- valid per-atom single-point results; and
- applicable atom-index appearance.

Whole-structure energy is not copied because it is invalid after the atom
count changes. After duplicating or deleting atoms, re-read indices before
performing another index-based operation.

## Labels, chemical types, and identity

Every atom has two related identities:

- **TYPE** is the ASE chemical element and controls atomic number, mass,
  element defaults, builders, and scientific calculations.
- **LABEL** is the complete user-facing group name used by appearance,
  selection, bond pairs, RDF pairs, and repulsion pairs.

Repeated VASP species blocks can therefore remain `O_1` and `O_2` while both
retain chemical element `O`. Custom names such as `Cu_surface` and
`O_adsorbate` must not be truncated or reinterpreted as element symbols.

View mode can split or rename visual identities without changing ASE element
types or coordinates. In Edit, changing TYPE is a physical identity edit. For
a stable-topology trajectory, a visual label can follow the same atom index
through every frame; if topology or element order differs, v_ase asks whether
to limit the change to the active frame.

## Undo, redo, and reset

`Ctrl+Z` and `Ctrl+Shift+Z` traverse committed structure and visual-setting
actions. Camera navigation is excluded. One confirmed transform, panel Apply,
placement batch, or relaxation start is one history entry; intermediate
pointer or optimizer frames are not separate Undo steps.

During Add Atoms, Undo/Redo can traverse individual placement batches while
**Cancel** still restores the baseline from before the first batch.

- **RESET COORDS** restores original physical coordinates and cell-related
  source state while preserving visual translation and display replication.
- **RESET** restores structure and visual settings together after confirmation.
