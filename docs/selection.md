# Select atoms and measure geometry

Select a fragment for styling or editing, or select atoms in order to measure
distance, angle and torsion. Selection works in **View and Edit**.

## Select atoms deliberately

The retained selection controls transforms, measurements, constraint edits,
appearance overrides, and several analysis tools.

| Input | Selection behavior |
| --- | --- |
| Left-click | Replace the selection with one atom |
| Shift + left-click | Add or remove the clicked atom |
| Left-drag | Replace the selection with atoms inside the box |
| Shift + left-drag | Invert membership for atoms inside the box |
| `Ctrl+A` | Select all visible atoms |
| `Shift+Ctrl+A` | Invert all visible atoms; clear when all were selected |

Selection order is meaningful. Two selected atoms define a distance, three
define the angle `a1-a2-a3`, and four define the signed torsion
`a1-a2-a3-a4`. Do not sort the selection when reproducing a measurement or a
pivot workflow.

### Base atoms and periodic replicas

In View, a displayed supercell replica is a distinct visual reference. Its
identity contains both the base index and a cell offset such as `12@[1,0,0]`,
so direct measurements use the position actually displayed. Hiding that
reference in View does not delete an ASE atom.

In Edit, a clicked replica resolves to its unique base atom. All displayed
equivalents receive a small selection ring, while the editable primary atom
keeps the full halo. This prevents a display-only periodic image from becoming
an accidental duplicate topology edit.

:::{warning}
**Delete Selected** has mode-dependent meaning. In View it hides the exact
selected visual references and their bonds. In Edit it physically deletes the
deduplicated base atoms and remaps supported constraints.
:::


## Example: measure ethane

Download {download}`ethane_measurement.cif <assets/examples/ethane_measurement.cif>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui ethane_measurement.cif
```

1. Click H #3, then Shift-click C #0. The HUD shows the distance.
2. Shift-click C #1. The ordered H–C–C angle appears.
3. Shift-click H #6. The H–C–C–H signed torsion appears.
4. Read direct-coordinate and MIC values separately; use the visible replica
   coordinates when measuring across displayed cells.

```{vase-animation} assets/readme_measurement.gif
:alt: Ethane: the selection grows from distance to angle to torsion.
:fallback: assets/readme_measurement.png

Ethane: the selection grows from distance to angle to torsion.
```


## Ordered geometry through a trajectory

Select atoms in the intended order:

- one atom shows label, element, displayed Cartesian/fractional position, and
  lazy per-atom properties;
- two show direct and minimum-image distances where applicable;
- three show the `a1-a2-a3` angle at `a2`;
- four show the signed `a1-a2-a3-a4` torsion; and
- larger selections show total and per-label counts.

The retained Measure overlay follows the selected source or optimizer frame
and committed `G`/`R`/`S` edits without relying on hover state.

![Ordered distance, angle, and torsion measurement](assets/readme_measurement.png)
