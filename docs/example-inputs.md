# Example inputs

Download an input, open it in v_ase, then follow the linked feature page.
You do not need a copy of the source repository for these files.
Atom indices in the guides are **zero-based** and refer to these exact inputs.

| Example | Input | Illustrated guide |
| --- | --- | --- |
| Rutile IrO2 | {download}`IrO2_polyhedra.extxyz <assets/examples/IrO2_polyhedra.extxyz>` | [Polyhedra](polyhedra.md) |
| Cubic SrTiO3 | {download}`SrTiO3_polyhedra.traj <assets/examples/SrTiO3_polyhedra.traj>` | [Polyhedra](polyhedra.md) |
| Ferrocene | {download}`ferrocene.traj <assets/examples/ferrocene.traj>` | [Rotate](rotate.md), [Scale](scale.md) |
| Li in a carbon nanotube | {download}`fixedline.traj <assets/examples/fixedline.traj>` | [Move](move.md) |
| Li above Cu(111) | {download}`fixedplane.traj <assets/examples/fixedplane.traj>` | [Constraints](constraints.md) |
| Surface C–O restraint | {download}`hookean.traj <assets/examples/hookean.traj>` | [Hookean example](constraints.md#example-stretch-a-hookean-restraint) |
| Phosphorene sheet | {download}`phosphorene_nanosheet.cif <assets/examples/phosphorene_nanosheet.cif>` | [Cumulative twist](rotate.md#example-cumulative-phosphorene-twist) |
| Cu5O4 surface | {download}`cu5o4-labeled.extxyz <assets/examples/cu5o4-labeled.extxyz>` · {download}`group indices <assets/examples/cu5o4-groups.json>` | [Appearance](appearance.md) |
| Oxide/support interface | {download}`cu2o111_on_cu111_pairwise_bonds.traj <assets/examples/cu2o111_on_cu111_pairwise_bonds.traj>` | [Bonds](bonds.md) |
| Graphene/hBN | {download}`graphene_hbn_commensurate.traj <assets/examples/graphene_hbn_commensurate.traj>` | [Cell tools](cell-tools.md), [Registry](registry.md) |
| Graphene/MoS2 | {download}`host <assets/examples/graphene_host.extxyz>` · {download}`guest <assets/examples/mos2_guest.extxyz>` | [Commensurate cells](commensurate.md) |
| Ethane | {download}`ethane_measurement.cif <assets/examples/ethane_measurement.cif>` | [Selection and measurements](selection.md) |
| Stored Cu surface forces | {download}`stored-forces.traj <assets/examples/stored-forces.traj>` | [Vectors](vectors.md), [Scalar colors](scalar-colors.md) |
| Cu–Zr pair statistics | {download}`cuzr-rdf.traj <assets/examples/cuzr-rdf.traj>` | [RDF](rdf.md) |
| Analytic graphene field | {download}`graphene-pi.cube <assets/examples/graphene-pi.cube>` | [Isosurfaces](isosurfaces.md), [Planes](field-planes.md) |
| Crowded C60 | {download}`crowded_c60_relaxation.traj <assets/examples/crowded_c60_relaxation.traj>` | [Trajectories](trajectories.md), [Relaxation](relaxation.md) |
| Cu(111) insertion host | {download}`cu111_oxygen_add_atoms.traj <assets/examples/cu111_oxygen_add_atoms.traj>` | [Insertion regions](insertion-regions.md) |
| Graphene-oxide solvent host | {download}`layered_water_channel.traj <assets/examples/layered_water_channel.traj>` | [Molecules](molecules.md) |

## Open a downloaded file

From the folder containing the download:

```bash
v_ase gui ferrocene.traj
```

For physical edits, switch to Edit in the GUI, or open directly in Edit:

```bash
v_ase gui ferrocene.traj --interactive
```

ASE `.traj` preserves supported constraints, labels and stored calculation
results. CIF and POSCAR are useful coordinate formats but do not carry the same
constraint and display state. Save `.vase` after styling to preserve the figure.

## What these examples establish

The figures demonstrate visualization and geometry controls. The graphene
field and probe-force trajectory are analytic fixtures, not DFT data. The Cu–Zr
input is a seeded hard-core distribution, not an equilibrium glass. Repulsion
relaxations condition geometry; they do not establish material stability.
Literature-derived example sources are recorded in [Worked examples](worked-examples.md).

Step images are cropped frames of the existing README GIFs. Their source hashes,
frame indices, timestamps and crops are recorded in the
{download}`frame manifest <assets/steps/manifest.json>`. They show sampled animation
states; captions distinguish them from exact typed endpoint commands.
