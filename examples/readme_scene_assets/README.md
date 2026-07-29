# v_ase README Scene Assets

## phosphorene

Armchair black-phosphorene ribbon edited to the paper-tabulated 36 degree target one puckered ridge at a time.

- Static: `phosphorene_twisted_nanoribbon_36deg.cif`
- Suggested selected indices: `62, 63, 66, 67, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131`
- Source coordinates: DOI 10.1039/C6CP05566D.
- Twist model: DOI 10.1039/C6NR04354B, H-APNR theta = 36 degrees.
- Scope: deterministic v_ase editing example, not the paper's periodic DFT cell or a relaxed structure.
- Each trajectory stage starts from the previously edited coordinates and advances by one puckered ridge.
- Additional: `phosphorene_nanosheet.cif`
- Additional: `phosphorene_twist_36deg.traj`

Open command:

```bash
v_ase gui examples/readme_scene_assets/phosphorene_twisted_nanoribbon_36deg.cif --show-bonds
```

## commensurate

Graphene/hBN stack for the periodic commensurate rotation guide.

- Static: `graphene_hbn_commensurate.traj`
- Suggested selected indices: `72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143`
- Select the hBN layer, press R then Z, and rotate toward a displayed cell match.

Open command:

```bash
v_ase gui examples/readme_scene_assets/graphene_hbn_commensurate.traj --show-bonds
```

## fixedline

Li ion constrained to a FixedLine inside a carbon nanotube channel.

- Static: `fixedline.traj`
- Suggested selected indices: `128`
- Select the Li atom to show the FixedLine guide.

Open command:

```bash
v_ase gui examples/readme_scene_assets/fixedline.traj --show-bonds
```

## fixedplane

Li ion constrained to a FixedPlane over a Cu(111) surface.

- Static: `fixedplane.traj`
- Suggested selected indices: `32`
- Select the Li atom to show the FixedPlane guide.

Open command:

```bash
v_ase gui examples/readme_scene_assets/fixedplane.traj --show-bonds
```

## hookean

Ethanol-like adsorbate on Cu(111) with a Hookean C-O bond constraint.

- Static: `hookean.traj`
- Suggested selected indices: `33, 34, 35`
- Move the O/H group away from the carbon to engage the Hookean spring.

Open command:

```bash
v_ase gui examples/readme_scene_assets/hookean.traj --show-bonds
```

## relaxation

Compressed C60 relaxed with the built-in repulsive fallback calculator and ASE FIRE.

- Static: `crowded_c60_relaxed.cif`
- Suggested selected indices: ``
- This is a clash-removal demonstration, not a predictive chemical potential.
- Energy: 32.644 -> 0.008 eV.
- Additional: `crowded_c60_initial.cif`
- Additional: `crowded_c60_relaxation.traj`

Open command:

```bash
v_ase gui examples/readme_scene_assets/crowded_c60_relaxed.cif --show-bonds
```

## measurement

Ethane with an H-C-C-H ordered selection for distance, angle, and torsion measurement.

- Static: `ethane_measurement.cif`
- Suggested selected indices: `3, 0, 1, 6`
- Select the listed atoms in order to display a1 through a4.

Open command:

```bash
v_ase gui examples/readme_scene_assets/ethane_measurement.cif --show-bonds
```

## ferrocene

Idealized ferrocene scene used for X-axis rotate demonstrations.

- Static: `ferrocene.traj`
- Suggested selected indices: `1, 2, 3, 4, 5, 6, 7, 8, 9, 10`
- Select the top ring and use R X to recreate the rotate interaction.

Open command:

```bash
v_ase gui examples/readme_scene_assets/ferrocene.traj --show-bonds
```

## showcase

Solid-state all-in-one NaCl showcase with FixAtoms, FixedLine, FixedPlane, Hookean, PBC bonds, and wrap test.

- Static: `showcase.traj`
- Suggested selected indices: `1, 2`
- Use this when you want one compact scene with all major constraint types.

Open command:

```bash
v_ase gui examples/readme_scene_assets/showcase.traj --show-bonds
```
