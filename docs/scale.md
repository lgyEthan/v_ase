# Scale atom spacing

Expand or contract selected coordinates around a pivot. This is useful for
controlled geometric changes to a fragment. **Edit mode is required.**

## Controls

1. Select the atoms and choose **Rotate pivot** under **Transform & Cell Match**.
   The same pivot menu is used for scaling; see [pivot definitions](rotate.md).
2. Press `S` and type a factor: `1.1` expands distances from the pivot by 10%.
3. Use `X`, `Y` or `Z` to scale only that Cartesian component.
4. Press `Enter` to commit, or `Esc` to cancel. Check the final coordinates when
   **Apply constraints** is on.

`S` changes atom spacing. **Atom radius** changes sphere appearance.
[Cell tools](cell-tools.md) change the unit cell. These controls are independent.

## Example: expand the upper ferrocene ring

Download {download}`ferrocene.traj <assets/examples/ferrocene.traj>`. Open in Edit, select atoms **1–10**,
and choose **Selection COM**. Use `S → 1.1 → Enter`.
The ring center stays fixed and every unconstrained intraring distance grows by
10%. Fe and the lower ring are unchanged. Undo to restore the original geometry.

```{figure} assets/steps/rotate-start.png
:alt: Use the upper ring from this input. For this scaling exercise, exclude Fe atom 0 from the selection.

Use the upper ring from this input. For this scaling exercise, exclude Fe #0 from the selection.
```

This image identifies the fragment; it is a rotation-GIF frame, not a scaling
result. Scaling bond distances prepares a geometry and does not optimize it.
