# Rotate atoms

Rotate a selected fragment around a chosen point. Use this to turn a ligand,
tilt an adsorbate or construct a layer twist.

**Where:** **Edit > Structure > Transform & Cell Match**.
**Shortcut:** `R`, optional `X`/`Y`/`Z`, angle in degrees, then `Enter`.

## Choose the pivot before rotating

The pivot is a **point**. The axis determines the **direction through that point**.
These are separate choices.

| Rotate pivot menu | Rotation center | Useful for |
| --- | --- | --- |
| Selection COM | Arithmetic mean of the selected editable atom coordinates | Turning a fragment around its own center |
| Active atom (last selected) | Position of the last selected atom | Turning a ligand about a metal center |
| Global origin | Cartesian `(0, 0, 0)` | A structure already centered on a known origin |
| Unit-cell center | Geometric center of the defined cell | Turning a fragment around the cell center |

**Current label detail:** “Selection COM” currently means the geometric centroid,
not a mass-weighted center of mass. For a mixed-element selection, these can differ.
An unavailable active atom or undefined cell falls back to the selection centroid
with a message. Read the displayed pivot before committing.

## Choose the rotation axis

| Operation | Meaning |
| --- | --- |
| `R`, move pointer | Rotation in the screen plane about the viewing direction |
| `R → X` / `Y` / `Z` | Rotation about a global Cartesian axis through the pivot |
| `R → Z → 30 → Enter` | Commit +30° about global z through the chosen pivot |
| `R → X → -15 → Enter` | Commit −15° about global x |
| Exact selection rotation: Axis, Angle / deg, Rotate Selection | The same physical rotation entered in the panel |

Axis-locked positive angles follow the right-hand rule. **Rotate increment / deg**
snaps pointer rotation; `0` means continuous. Typed angles bypass that increment.
Disable **Commensurate atoms** for an ordinary exact-angle exercise so magnetic
candidate snapping does not change the requested angle.

A neutral radial line marks the starting direction and an amber line follows
the current angle. Cyan commensurate guides belong to
[cell matching](commensurate.md), not a second rotation pivot.
`Enter`/left-click commits; `Esc`/right-click cancels.

## Example: turn a ferrocene ring around Fe

Download {download}`ferrocene.traj <assets/examples/ferrocene.traj>`. This is an idealized geometry for
showing pivot behavior, not a calculated reaction path.

```bash
v_ase gui ferrocene.traj --interactive
```

| Group | Atom indices |
| --- | --- |
| Central Fe | `0` |
| Upper-ring C and H | `1–10` |
| Lower-ring C and H | `11–20` |

### 1. Select the ring, then the pivot

Box-select the upper five C and five H atoms. **Shift-click Fe last**. Confirm
11 selected atoms and Fe #0 as the last atom. Set **Rotate pivot > Active atom
(last selected)**; turn **Commensurate atoms** off. Fe is included in the selection
but sits exactly at the pivot, so this rotation leaves its coordinate unchanged.

```{figure} assets/steps/rotate-start.png
:alt: 1. Upper ring and central Fe selected. Fe atom 0 is the active pivot at the origin.

**Step 1.** Upper ring and central Fe selected. Fe #0 is the active pivot at the origin.
```

### 2. Turn the ring about z

Press `R → Z → 72 → Enter`. The ring turns around the Fe-centered z axis.
The Fe atom and lower ring stay in place; upper-ring internal distances are
preserved. A fivefold ring has equivalent geometry after a 72° turn, so follow
the angle guide or individual atom indices rather than silhouette alone.

```{figure} assets/steps/rotate-z.png
:alt: 2. Near the 72° z-rotation endpoint. The amber radius shows the accumulated angle.

**Step 2.** Near the 72° z-rotation endpoint. The amber radius shows the accumulated angle.
```

### 3. Try a different axis from the original geometry

Undo the committed turn. Keep the same selection and pivot, then use
`R → X → 38 → Enter`. The upper ring folds around an x axis through Fe.
Its center moves on an arc because the pivot is Fe, not the ring center.

```{figure} assets/steps/rotate-x.png
:alt: 3. Near the 38° x-rotation endpoint, starting from the original geometry.

**Step 3.** Near the 38° x-rotation endpoint, starting from the original geometry.
```

The original GIF animates each angle out and back; these are sampled frames,
not three successive committed structures.

```{vase-animation} assets/readme_ferrocene_pivot.gif
:alt: Ferrocene rotation first about z, then about x, with an active Fe pivot
:fallback: assets/readme_rotate.png


```

## Example: cumulative phosphorene twist

Download {download}`phosphorene_nanosheet.cif <assets/examples/phosphorene_nanosheet.cif>` and open it in Edit. This
120-atom sheet has ten ridges of twelve atoms. The operation is about **global X**,
using **Selection COM**, with **Commensurate atoms off**.

1. Select ridges 2–10 and rotate by **13.85 / 9 = 1.538888889°**.
2. On the edited structure, select ridges 3–10 and apply the same angle.
3. Continue through ridge 10: nine committed rotations in total. The last ridge
   accumulates 13.85°. Each step has a new selection centroid.

```{figure} assets/steps/twist-select.png
:alt: Select a tail of the phosphorene sheet; the other atoms keep their positions.

Select a tail of the phosphorene sheet; the other atoms keep their positions.
```
```{figure} assets/steps/twist-rotate.png
:alt: Use Exact selection rotation about X, then advance the selection by one ridge.

Use Exact selection rotation about X, then advance the selection by one ridge.
```
```{figure} assets/steps/twist-result.png
:alt: The cumulative twist after repeated tail selections and rotations.

The cumulative twist after repeated tail selections and rotations.
```

Compare against the provided {download}`reference trajectory <assets/examples/phosphorene_twist_13p85deg.traj>`.
This is a geometric construction, not an energy-minimized twisted ribbon.
[Example provenance](worked-examples.md#build-a-cumulative-phosphorene-twist).

## Constraints and camera rotation

ASE constraints remain authoritative at commit. They can change an attempted
rigid rotation, so distances need not be preserved when some atoms are constrained.
An active pivot is not an ASE fixed-atom constraint for later relaxation.

Middle-mouse orbit and the camera toolbar change your viewpoint; they never
rotate ASE coordinates. See [Camera](camera.md). For an in-plane periodic
rotation that also yields a common cell, use [Commensurate atoms](commensurate.md).
