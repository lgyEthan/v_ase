# Insert molecules and set density

Fill a pore or solvent region with complete molecules. Choose **+ Add atoms >
Batch > Molecules** in Edit. Counts or target density determine how many complete
molecules are inserted; rigid placement can preserve their internal geometry.

## Controls to set before placement

1. Choose a molecule and a count, or enable density mode and enter g/cm³.
2. Define [Allow/Reject regions](insertion-regions.md) for the solvent volume.
3. Choose random or homogeneous anchor placement and enter a seed.
4. Enable **Randomize molecular orientation** for uniform 3D orientations.
5. Enable **Preserve molecular geometry** to keep intramolecular distances.
6. Place, inspect realized density, relax if needed, then **Finish** or **Cancel**.

Density is based on accessible volume and realizable complete composition.
Inspect the reported value; it may differ slightly from the target. An insertion
anchor uses the molecule's native origin and is not necessarily its mass center.
## Fill two solvent chambers with rigid water

```bash
v_ase gui layered_water_channel.traj --interactive
```

This periodic graphene-oxide fixture has an exact accessible solvent volume of
1926.683 Å³. Two 2 Å-thick Reject regions cover the oxide planes while leaving
distinct left and right solvent chambers.

Use these two **Reject** boxes in Å. Set y max to the cell y length
**7.378536440243417 Å** in both rows:

| Region | x min / max | y min / max | z min / max |
| --- | --- | --- | --- |
| Lower GO | 5.15 / 22.34 | 0 / cell y length | 2 / 4 |
| Upper GO | 5.15 / 22.34 | 0 / cell y length | 8 / 10 |

The {download}`exact molecule settings <assets/examples/water-insertion.json>`
include these bounds, density and seed.

1. Open **+ Add atoms > Batch > Molecules** and choose water from the ASE G2
   catalog. Set Random placement and seed **1207**.
2. Enable density mode with a target of 1.00 g/cm³.
3. Keep **Randomize molecular orientation** and **Preserve molecular geometry**
   enabled.
4. Place the nearest realizable complete composition: 64 rigid H2O molecules.
5. Inspect the reported realized density (**0.9936947024 g/cm³**) and both
   chambers before relaxation.

Random orientation is uniform over 3D rotations. Molecules rotate about their
native coordinate origin, and rigid placement preserves every internal bond
length while allowing whole-molecule translation and rotation.

Download {download}`layered_water_channel.traj <assets/examples/layered_water_channel.traj>` to run this example without a source checkout.

```{vase-animation} assets/readme_add_molecules.gif
:alt: Water fills two accessible chambers around a graphene-oxide host.
:fallback: assets/readme_add_molecules.png

Water fills two accessible chambers around a graphene-oxide host.
```
