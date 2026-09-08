# Insertion regions

Place atoms only inside chosen volumes. Allow boxes define the permitted
union; Reject boxes subtract excluded volumes. Use **+ Add atoms > Batch** in Edit.
This page uses the Cu(111) interior-insertion example.

Download {download}`Cu(111) host <assets/examples/cu111_oxygen_add_atoms.traj>` for the example below.

## Batch insertion workspace

For a complete feature walkthrough, including distribution choice, mixing,
repulsion equations, and a runnable Python example, see
[Atomic and molecular distributions](atomic-distributions.md).

Open **+ Add atoms > Batch**. Choose **Atoms** or **Molecules**, add one or more
composition rows, then define placement and domain settings before selecting
**Place atoms** or **Place molecules**.

The first placement starts one reversible staging session. Later placement
calls append to the same session after any active placement relaxation has
stopped. The structure that existed before the first placement remains the
immutable host; every inserted batch remains staged and mobile until
**Finish**. **Cancel** restores the exact pre-session structure and history.

:::{warning}
Batch atom and molecule insertion is restricted to one structure. It is
rejected for a trajectory because adding a different topology to only one
frame would make frame identity ambiguous. Open the intended frame as a new
standalone document first.
:::

### Placement distributions

| Mode | Meaning |
| --- | --- |
| **Random** | Volume-uniform sampling in an orthogonal or triclinic cell; a seed makes it reproducible |
| **Homogeneous** | Low-discrepancy candidates with maximin spacing; Cartesian Å distance is the default, fractional spacing is optional |
| **Regular grid** | One global Cartesian lattice clipped to the exact allowed domain |

**Account for periodic boundaries** uses the complete triclinic minimum image
for spacing. Random sampling remains volume-uniform under either coordinate
basis. Homogeneous refinement is bounded for large batches. An explicitly
entered regular-grid spacing is never silently reduced: if too few accessible
sites exist, placement fails and reports the available count.

### Allow and Reject regions

Each region is an axis-aligned Cartesian box with stable name/ID, role, and
`xmin/xmax`, `ymin/ymax`, `zmin/zmax` bounds. With a finite cell, the exact
domain is:

```text
unit cell ∩ (union of Allow regions, or full cell when none exist)
          ∖ union of Reject regions
```

Overlapping volume is counted once. Orthogonal and triclinic box/cell
intersections are calculated analytically rather than estimated with voxels.
With region MIC enabled, lattice-translated images are clipped to the primary
cell while one intact source box remains visible.

Click a region row or a visible region edge; Shift-click selects several.
`G` translates their bounds together. `S`, optionally followed by `X`, `Y`, or
`Z`, scales them about their shared center. `R` is deliberately unavailable
because a rotated box could no longer be represented by the six displayed
Cartesian bounds.

Regions control initial sampling. **Enforce Allow and Reject regions during
relaxation** is off by default. Enable it only when staged atoms must remain in
the Boolean domain during repulsive placement; rigid molecules are tested by
their native ASE template origin.

### Molecules and density

**Batch > Molecules** reads the installed ASE G2 molecule catalog. It supports:

- several molecule species in one placement;
- integer **Count** mode;
- target **Density** in `g/cm³`;
- Haar-uniform random orientation; and
- **Preserve molecular geometry during placement**, enabled by default.

Molecules are placed and rotated around the native ASE template origin; v_ase
does not silently recenter them. In density mode, each row count is an integer
composition ratio. v_ase reduces the ratio, uses the exact accessible volume
and ASE molar masses, then chooses the nearest complete composition
multiplier. It reports target and realized density rather than creating
fractional molecules or rounding species independently.

With rigid geometry enabled, internal pair repulsion is excluded and forces
are projected onto rigid translation and rotation. Move or rotate complete
molecules; a partial transform that changes an internal distance is rejected.

### Relax, append, finish, or cancel

**Temporarily fix existing atoms** is enabled by default. It freezes the
immutable host only inside the staging optimizer and adds a temporary visual
overlay; it does not modify committed ASE constraints or saved atom
appearance.

Use **Open Relaxation** to configure the common settings under **Structure >
Relaxation**, then start placement relaxation. After it becomes inactive:

- edit regions and append another batch;
- select **Select added** to restore selection of all accumulated content;
- choose **Finish** to commit all inserted atoms while restoring every host
  coordinate, constraint, array, and calculator state; or
- choose **Cancel** to restore the complete pre-session baseline.

See [Constraints and relaxation](constraints.md) for the calculator
and optimizer contract.

![Batch insertion and relaxation](assets/readme_add_atoms.png)

## Insert oxygen into a Cu(111) slab

```bash
v_ase gui cu111_oxygen_add_atoms.traj --interactive
```

The fixture is a five-layer, 210-atom Cu(111) slab. Use these Allow bounds in Å:

| x min / max | y min / max | z min / max |
| --- | --- | --- |
| 1.7893337098 / 16.1040033881 | 1.0625886504 / 12.2197694798 | 8.0435605 / 14.3049245 |

The {download}`exact settings <assets/examples/oxygen-insertion.json>` record
unrounded bounds and seed. A reproducible staging workflow is:

1. Open **+ Add atoms > Batch > Atoms**.
2. Add 18 atoms with TYPE `O`, LABEL `O_subsurface`, and seed `2021`.
3. Create an Allow region spanning the three bulk-like interior layers.
4. Leave host freezing enabled so all pre-existing Cu coordinates, arrays,
   labels, constraints, and calculator state remain unchanged.
5. Place, inspect contacts, open the shared Relaxation controls, and run the
   staged repulsive optimizer: onset **2.40 Å**, strength **3.0 eV/Å²**,
   force tolerance **0.010 eV/Å**, and **220 steps**.
6. Add another batch and relax again without pressing **Finish** when an
   accumulated staging session is intended.
7. Finish only after verifying atom count and host invariance; Cancel must
   restore the exact baseline.

The region is intersected with the half-open primary periodic cell, and
periodic images use the full triclinic lattice. Region bounds define initial
sampling unless confinement is explicitly enabled.

![Batch atom insertion in a bounded region](assets/readme_add_atoms.png)

```{vase-animation} assets/readme_add_atoms_allowed.gif
:alt: Oxygen placement in an allowed interior region, followed by staged repulsion.
:fallback: assets/readme_add_atoms.png

Oxygen placement in an allowed interior region, followed by staged repulsion.
```
