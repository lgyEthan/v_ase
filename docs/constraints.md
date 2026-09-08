# Constraints and their visual guides

Keep atoms fixed, restrict motion to a line or plane, or display an ASE Hookean
restraint. Open **Edit > Structure > Constraints**. Constraint markers preserve
element colors, so a fixed layer can still have its own scientific color group.

## Read the guide before moving

| Constraint | Persistent marker | During `G` |
| --- | --- | --- |
| FixAtoms | Fixed surface appearance; X in flat 2D | Atom remains fixed |
| FixedLine | Short cyan direction segment | Long cyan line through the original atom |
| FixedPlane | Ring/crosshair and a normal | Translucent allowed plane through the original atom |
| FixScaled | Cell-aware allowed direction(s) | Uses the cell basis, including skew |
| Hookean | Spring only while active | A restraint force, not a hard motion lock |

## Constraint enforcement

Open **Structure > Constraints** in Edit. **Apply constraints** is enabled by
default. A viewport transform is previewed interactively, then the proposed
coordinates are committed through ASE and the backend returns the constrained
result.

Turning **Apply constraints** off permits an unconstrained coordinate commit.
It does not remove the constraint from the ASE object. Re-enable it before the
next operation when subsequent edits should respect the stored constraint.

:::{admonition} Verify the committed coordinates
:class: important
The browser preview is not the scientific result. After moving a constrained
atom, inspect the returned position or reopen the structure state. FixedLine
and FixedPlane may remove components of the pointer-driven displacement.
:::

## Example: keep Li at a fixed height above Cu(111)

Download {download}`fixedplane.traj <assets/examples/fixedplane.traj>`. Open in Edit and select **Li #32**.
The lower Cu layer already has `FixAtoms`; Li already has
`FixedPlane([0, 0, 1])`.

### 1. Inspect or set the plane

Open **Constraints**, choose **FixedPlane**, set normal `(0, 0, 1)` and press
**Apply Direction** if creating it yourself. Keep **Apply constraints** enabled.
The normal is perpendicular to the allowed plane: z is blocked, x/y are free.

```{figure} assets/steps/plane-start.png
:alt: 1. Li above Cu(111). The plane guide shows the allowed constant-height motion.

**Step 1.** Li above Cu(111). The plane guide shows the allowed constant-height motion.
```

### 2. Move and confirm

Press `G → X → 1 → Enter`. Li moves 1 Å in x and its height stays fixed.
Try `G → Z → 1 → Enter`: there is no allowed z displacement.
The GIF sweeps in two in-plane directions; its plane stays anchored at the
original height. Multiple selected plane-constrained atoms each have their own
plane, not one plane at the selection center.

```{figure} assets/steps/plane-move.png
:alt: 2. Li has moved within its plane while the fixed substrate remains in place.

**Step 2.** Li has moved within its plane while the fixed substrate remains in place.
```

```{vase-animation} assets/readme_fixedplane.gif
:alt: Li moving in a FixedPlane above a Cu slab
:fallback: assets/steps/plane-start.png


```

### 3. Remove only the intended constraint

**Clear Direction** removes FixedLine/FixedPlane from the selected atoms.
It does not remove a separate FixAtoms constraint. Turning **Apply constraints**
off temporarily bypasses enforcement but retains stored ASE constraints.

## Example: stretch a Hookean restraint

Download {download}`hookean.traj <assets/examples/hookean.traj>`. The C #33–O #34 pair has
`rt = 1.50 Å`, `k = 12 eV/Å²`. Select O #34 and its H #35, then move the group
away from C. The helix appears only when the pair exceeds the threshold.
It indicates an active restoring force; it does not prohibit the drag.

```{vase-animation} assets/readme_hookean.gif
:alt: An active C–O Hookean restraint in the surface demonstration.
:fallback: assets/readme_hookean.png

An active C–O Hookean restraint in the surface demonstration.
```


## Supported constraint state

v_ase preserves and serializes common ASE constraints, including FixAtoms,
FixCartesian, FixedLine, FixedPlane, FixScaled, and Hookean. The built-in
constraint editor creates or clears FixAtoms and the supported directional
FixedLine/FixedPlane forms. Existing FixScaled, FixCartesian, and Hookean
objects are preserved and rendered according to their ASE semantics rather
than converted into a different backend constraint.

### FixAtoms

FixAtoms prevents all Cartesian motion for its atom indices. Fixed atoms keep
their element color but use a distinct constrained surface treatment. In the
scene-wide **2D flat** rendering mode they also receive an X marker.

To change selected atoms, use the **FixAtoms** control and apply the change.
Recheck the selected indices afterward, especially if topology was edited.

### FixedLine

FixedLine allows motion only along one direction vector. Each constrained atom
has its own short cyan axis, visible without selection. Starting `G` adds one
long guide through the atom's original position; rings and plane discs are not
used for a line constraint.

To create it:

1. Select the intended atoms in Edit.
2. Choose **Directional > FixedLine**.
3. enter a nonzero three-component **Vector**;
4. select **Apply Direction**; and
5. move the atom and verify that only the vector-parallel displacement
   survives the backend commit.

![Constraint direction and plane guides](assets/readme_constraints.png)

### FixedPlane

FixedPlane allows motion inside the plane whose normal is the stored direction
vector. Each constrained atom retains a local ring, crosshair, and normal
marker. Starting `G` adds a larger translucent permitted plane anchored at
that atom's original position. A multi-selection keeps independent per-atom
planes; v_ase does not substitute one center-of-mass plane.

Create it by selecting **Directional > FixedPlane**, supplying a nonzero
normal vector, and choosing **Apply Direction**. Confirm a test move with both
in-plane and normal components and verify that the normal component was
removed.

![Constraint direction and plane guides](assets/readme_constraints.png)

### FixScaled and FixCartesian

VASP selective dynamics commonly enters ASE as FixScaled. v_ase derives its
guide from allowed fractional cell directions:

- no allowed directions renders as fully fixed;
- one allowed direction renders as a line along the corresponding cell
  vector; and
- two allowed directions render as a plane spanned by those cell vectors.

This visualization remains cell-aware in skewed cells. Existing FixCartesian
component masks are retained in serialized scientific state. Use ASE/Python
when a workflow needs to author a constraint form that the GUI editor does not
create directly.

### Hookean

For ASE `Hookean(a1, a2, rt, k)`, the spring is inactive at `r <= rt` and the
restoring-force magnitude after activation is:

```text
|F| = k (r - rt),  for r > rt
```

v_ase reads `rt` and `k` from the live constraint. The 3D helix appears only
when the displayed distance is beyond the threshold and follows every
trajectory frame. It adds no numerical annotation that could obscure a dense
structure and does not modify ASE's force calculation.

![Hookean threshold and active spring](assets/readme_hookean.png)

### Clear a directional constraint

Select the atoms and choose **Clear Direction**. This removes the supported
FixedLine/FixedPlane state while leaving the separate FixAtoms setting as
configured. Verify the constraint summary before continuing.

## Constraint-safe topology operations

Deletion, duplication, supercell construction, and trajectory-wide changes
must remap or repeat supported atom indices. v_ase performs these operations in
the backend and records them in history. After any atom-count change:

- inspect the constraint summary again;
- do not reuse old atom indices blindly;
- confirm that a supercell repeated each intended constraint; and
- verify that an Undo restores both topology and constraints.

Temporary fixed-host markers during Batch Add Atoms are not committed ASE
constraints. They exist only in the staging optimizer and disappear after
**Finish** or **Cancel**.
