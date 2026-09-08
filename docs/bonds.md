# Bond display

Choose which contacts to draw and style each label pair separately. Open
**Structure > Bonding**. Displayed bonds are a visual topology, not a force field.


## Example: show an oxide network above a Cu support

Download {download}`cu2o111_on_cu111_pairwise_bonds.traj <assets/examples/cu2o111_on_cu111_pairwise_bonds.traj>`. Open it with **File > Open**, or run this in the folder containing the download:

```bash
v_ase gui cu2o111_on_cu111_pairwise_bonds.traj
```

1. Open **Bonding** and choose label-pair controls.
2. Enable `Cu_oxide–O_oxide` and `Cu_substrate–O_oxide`, both at **2.08 Å**.
   Disable Cu–Cu and O–O pairs to expose the oxide network.
3. Set bond thickness **0.30** and split endpoint colors. Use substrate Cu
   `#744637` / Metal, oxide Cu `#efb34f` / Standard, and O `#df2935` / Rubber.
   Enable periodic bonds if contacts cross the cell edge.
4. Orbit and inspect boundary connections. A thickness change should not add
   new bonds; only a topology/cutoff change should do that.

```{figure} assets/readme_bonds.png
:alt: Cu2O(111) on Cu(111), with label-pair bond controls.

Cu2O(111) on Cu(111), with label-pair bond controls.
```


## Bonds

```{figure} assets/readme_bonds.png
:alt: Pair-specific bond settings on a copper oxide film over copper.

Inspect the exact pairs and effective style in the Bonding panel.
```

Bond visibility and bond appearance are separate from physical constraints or
calculator connectivity.

### Topology modes

- Automatic mode infers contacts from element/covalent information and the
  active cutoff scale.
- Label-pair mode uses explicit enabled/cutoff records for each label pair.
- Manual bonds preserve explicitly selected pairs.

Periodic bonds can be shown across cell boundaries. Export uses the same
minimum-image topology and, for skewed cells, ASE's exact minimum-image
resolution rather than component-wise fractional rounding.

### Appearance

Global or label-pair settings can control:

- cylinder or flat shape;
- thickness;
- material;
- opacity; and
- split-by-atom or custom color.

Each label-pair row has an independent thickness. Pair records
are preserved by `.vase`, project/view HTML, Blender, OBJ, and 3DM output.
Visual bond cutoffs and repulsive-calculator contact distances are configured
separately; a drawn bond is not an energy model.
