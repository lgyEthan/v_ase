# Relax structures

Use an attached ASE calculator to relax coordinates, or use the built-in
repulsion model to remove short contacts. Open **Edit > Structure > Relaxation**.
Read which calculator is active before interpreting any energy or force.

## Relaxation prerequisites

Open **Structure > Relaxation** in Edit. Ordinary structure relaxation requires
an attached ASE calculator. When a structure enters Edit without a calculator,
v_ase attaches its built-in soft-repulsion fallback; View mode does not attach
one. User-supplied ASE calculators are preserved.

:::{warning}
The built-in calculator is a geometry conditioner for obvious short contacts.
It is not a predictive interatomic potential. Attach an appropriate scientific
ASE calculator before interpreting optimized energies, forces, structures, or
reaction pathways physically.
:::

## Built-in repulsion calculator

Visual bonds and repulsive contacts are independent. Hiding a bond never
disables repulsion, and drawing a bond never creates a force.

For an enabled label pair with separation `r` below its onset `r_cut`, the
fallback pair energy is:

```text
E_pair = 0.5 k_repulsion (r_cut - r)^2
```

Energy and force are exactly zero at and beyond `r_cut`. Therefore `r_cut` is
the zero-force onset distance, not a hard minimum separation. Optimizer
tolerance and any other forces determine the final distance.

### Absolute pair distances

**Pair distances / Å** is the default cutoff definition. Each unordered
complete-label pair owns an independent physical onset in angstrom, for
example `Cu_surface|O_ads`. Suggested values come from ASE covalent-radius
sums; van der Waals sums can be selected as a reference. A disabled pair or a
value of `0` disables only that pair.

### Scaled reference distances

**Reference distances × multiplier** multiplies the chosen reference table by
one dimensionless contact multiplier. It is useful when all enabled contacts
should be adjusted together. It does not reinterpret the result as a hard
constraint.

### Compute device

CPU is the default. **CPU threads** configures the built-in calculator's
parallel work. Torch is optional; without it the calculator uses NumPy. CUDA
is available only when torch reports a working CUDA runtime. An unavailable
CUDA request falls back to CPU and the effective device is reported in state.

The compiled matscipy neighbor engine filters candidate label pairs. This is
an acceleration detail only: it does not alter cutoff values, minimum-image
semantics, pair energy, or forces.

## Run an ordinary relaxation

1. Confirm the active structure/frame and attached calculator.
2. Review **Apply constraints**.
3. Configure calculator/contact settings where the built-in calculator is
   active.
4. Enter positive `fmax` and an integer step limit.
5. Choose **Start Relaxation**.
6. Follow the dedicated Relaxation timeline and energy/force status.
7. Stop, restart, clear the movie, or exit deliberately.

Every optimizer step is retained in an operation-specific mode timeline. A
loaded source trajectory remains separate; use the timeline selector below the
viewport to distinguish them. Starting relaxation is one user-level history
entry rather than one Undo entry per optimizer frame.

### Stop and restart

**Stop Relaxation** requests a safe stop and retains the newest committed
coordinates. A stopped run can be started again without leaving relaxation
mode. Very short runs may finish before a visible running indicator appears;
their initial, optimizer, and final states remain in the timeline.

### Clear the trajectory

**Clear Relaxation Trajectory** removes only the optimization movie and leaves
the mode active. Choose whether to retain the displayed frame or final frame.
The retained structure becomes the current coordinate state.

### Exit relaxation mode

**Exit Relaxation Mode** works while a run is active or after it stops. It
invalidates the worker, removes the temporary timeline, and offers two
scientifically distinct outcomes:

- **Keep Current** retains current coordinates; or
- **Restore Before Relaxation** restores the exact baseline from mode entry.

The source trajectory is not deleted.

![Dedicated repulsive-relaxation timeline](assets/readme_relaxation.png)


## Example: inspect crowded C60 contact removal

Download {download}`crowded_c60_relaxation.traj <assets/examples/crowded_c60_relaxation.traj>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui crowded_c60_relaxation.traj
```

1. Open the recorded trajectory and compare its first and last frames.
2. To run your own relaxation, open the first structure in Edit and inspect
   the active calculator and its contact-distance settings.
3. Set FIRE and the desired force tolerance and step limit, then start relaxation.
4. Inspect the energy/force trace and short distances. Use Undo or the relaxation
   exit choice to restore the baseline when needed.
5. Save the accepted geometry and trajectory. A reduced repulsion penalty is
   not evidence of a physically stable fullerene arrangement.

```{vase-animation} assets/readme_relaxation.gif
:alt: Crowded C60 fragments moving under the illustrative repulsion model.
:fallback: assets/readme_relaxation.png

Crowded C60 fragments moving under the illustrative repulsion model.
```


## Batch-placement relaxation

When an Add Atoms/Molecules staging session is active, the common **Start
Relaxation** control routes through one `AdditionRepulsionCalculator` over the
complete staged structure.

- The pre-session host remains immutable.
- **Temporarily fix existing atoms** is enabled by default.
- All inserted batches remain mobile/staged.
- Minimum-image search runs over the complete structure.
- Rigid molecule groups preserve their internal geometry when requested.
- Optional domain confinement keeps staged origins in the Allow-minus-Reject
  region.
- Every optimizer step goes to the separate Add Atoms timeline.

Appending another batch after relaxation resets the topology-specific Add
timeline but retains the original host and all staged content. **Finish** is
allowed only after the optimizer is inactive. It commits inserted atoms while
restoring host coordinates, constraints, arrays, and calculator state exactly.
**Cancel** restores the complete state from before the first placement.

See [Editing structures](insertion-regions.md#batch-insertion-workspace) for placement
and region semantics.

## Rigid-translation relaxation

**Analysis > Rigid Translation** has a separate optimizer mode for moving one
selected component without changing its internal geometry. It can use two
coordinates in a periodic `(hkl)` plane or three bounded Cartesian
coordinates. Host atoms and cell vectors remain fixed. Its registry timeline,
finish, and cancel semantics are distinct from ordinary structure relaxation.
See [Trajectories and analysis](trajectories-analysis.md#rigid-translation-timeline)
and [Periodic interfaces](cell-tools.md).
