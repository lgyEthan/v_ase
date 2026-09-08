# Move atoms

Move selected atoms by a distance in Å. Use this to shift an adsorbate, adjust
an interlayer gap, or translate an ion along a channel.

**Where:** switch to **Edit**, select atoms, then return focus to the viewport.
**Shortcut:** press `G`, then an optional axis, then a distance. These are
successive keys: `G → X → 1 → Enter` moves by **+1 Å along global x**.

## Choose a direction and distance

| Input | Result |
| --- | --- |
| `G`, move pointer | Translation in the current screen plane |
| `G → X` / `Y` / `Z`, move pointer | Translation along that global Cartesian axis |
| `G → X → 1.5 → Enter` | Exactly +1.5 Å along x, subject to active constraints |
| `G → Z → -2 → Enter` | Exactly −2 Å along z, subject to active constraints |
| `Enter` or left-click | Commit the preview |
| `Esc` or right-click | Cancel and restore the starting coordinates |

Type a number **after choosing an axis** for an unambiguous distance. The axes
are Cartesian x/y/z, not the a/b/c vectors of a skewed cell. Outside a transform,
`X`, `Y`, and `Z` align the **camera** instead.

For pointer movement in fixed steps, set **Structure > Transform & Cell Match >
Move increment / A**. `0` means continuous movement; `0.1` snaps pointer movement
to 0.1 Å steps. Typed distances bypass this increment.

## Example: Li moving through a carbon nanotube

Download {download}`fixedline.traj <assets/examples/fixedline.traj>`. This input contains 128 C atoms and
Li **#128**, with an existing `FixedLine([0, 0, 1])` constraint on Li. Indices are
zero-based. The geometry is an illustrative channel, not a diffusion calculation.

```bash
v_ase gui fixedline.traj --interactive
```

### 1. Select the mobile ion

Click Li in the center of the tube. Check **Li #128** in the selection readout.
Leave **Apply constraints** on. Orbit with the middle mouse button until the
channel is visible from the side. The example camera makes global z run
horizontally on screen; screen-horizontal does not imply global x.

```{figure} assets/steps/move-start.png
:alt: 1. Initial Li position. A short cyan segment indicates its allowed line.

**Step 1.** Initial Li position. A short cyan segment indicates its allowed line.
```

### 2. Move in the allowed direction

Press `G → Z → 2.2`. The long cyan guide passes through the original Li position.
Inspect the preview, then press `Enter`. Its z coordinate increases by 2.2 Å;
x and y remain unchanged. The carbon coordinates are unchanged.

```{figure} assets/steps/move-positive.png
:alt: 2. Positive z displacement in the GIF. The line remains anchored at the starting position.

**Step 2.** Positive z displacement in the GIF. The line remains anchored at the starting position.
```

### 3. Compare the opposite displacement

Undo with `Ctrl+Z` to restore the initial position. Use `G → Z → -2.2 → Enter`.
The ion now moves to the other side. Undo again when finished.

```{figure} assets/steps/move-negative.png
:alt: 3. Negative z displacement. The same allowed line is used in both directions.

**Step 3.** Negative z displacement. The same allowed line is used in both directions.
```

The stills are extracted from the existing animation, which sweeps continuously
between approximately ±2.2 Å. The typed values above reproduce its endpoints;
the selected GIF frames lie near those endpoints.

```{vase-animation} assets/readme_fixedline.gif
:alt: Continuous Li motion along a FixedLine constraint
:fallback: assets/readme_constraints.png


```

## How constraints change a move

| Constraint | What you see | What is committed |
| --- | --- | --- |
| `FixAtoms` | Distinct fixed surface; an X marker in flat 2D | The atom stays fixed |
| `FixedLine` | Short cyan axis; a longer line during `G` | Only displacement along the allowed line |
| `FixedPlane` | Ring, crosshair and normal; translucent plane during `G` | Only displacement within the allowed plane |
| `FixScaled` | Cell-aware line or plane for allowed fractional directions | Motion consistent with the original cell-based mask |

For the nanotube example, `G → X → 1 → Enter` has no allowed component and Li
stays put. For an oblique FixedLine, ASE can project a requested x displacement
onto that oblique line: the final motion need not remain parallel to x.
Check the **committed** coordinates, not only the mouse preview. See
[Constraints](constraints.md) for creation, removal and combined constraints.

## Move the picture or move the structure?

Use camera pan to move the view, or **Visual Translation** to offset displayed
atoms without changing ASE positions. `G` in Edit changes coordinates. Physical
trajectory-wide translations are a separate [cell operation](cell-tools.md).
If a light, plane or insertion region is selected, `G` controls that object;
select the atoms first. Save a [project](save-projects.md) to keep edits and style.
