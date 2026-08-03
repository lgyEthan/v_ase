# v_ase README Scene Assets

## phosphorene

Short, wide 5 x 6 armchair black-phosphorene ribbon twisted to the paper-reported 13.85 degree model in 9 ridge edits.

- Static: `phosphorene_twisted_nanoribbon_13p85deg.cif`
- Suggested selected indices: `50, 51, 54, 55, 58, 59, 62, 63, 66, 67, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119`
- Source coordinates: DOI 10.1039/C6CP05566D.
- Twist model: DOI 10.1039/C6NR04354B, H-APNR theta = 13.85 degrees.
- Each of the 9 trajectory edits starts from the previously committed coordinates and advances by one puckered ridge.
- Additional: `phosphorene_nanosheet.cif`
- Additional: `phosphorene_twist_13p85deg.traj`

Open command:

```bash
v_ase gui examples/readme_scene_assets/phosphorene_twisted_nanoribbon_13p85deg.cif --show-bonds
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

## ai-edit

AI-generated Li site over a pyridinic N3 vacancy in a 6 x 6 ASE graphene sheet.

- Static: `ai_pyridinic_n3_li_graphene.cif`
- Suggested selected indices: `29, 42, 31, 71`
- The central C is deleted, its three nearest neighbors become N_pyridinic, and Li is added above the vacancy.
- Additional: `ai_graphene_source.cif`
- Additional: `ai_pyridinic_n3_graphene.cif`
- Additional: `ai_pyridinic_n3_li_graphene.traj`

Open command:

```bash
v_ase gui examples/readme_scene_assets/ai_pyridinic_n3_li_graphene.cif --show-bonds
```

## bonding

Coherent Cu2O(111)/Cu(111) interface used to demonstrate label-pair bond control.

- Static: `cu2o111_on_cu111_pairwise_bonds.traj`
- Suggested selected indices: ``
- A 3x3 ASE conventional surface repeat gives a 6x6 primitive Cu2O(111) mesh matched to 7x7 Cu(111) with about 1.22 percent in-plane compression.
- One interfacial O is registered directly above a top-layer substrate Cu atom before relaxation.
- Cu_oxide-O_oxide and Cu_substrate-O_oxide are enabled; Cu-Cu and O-O pairs are disabled.
- The scene contains 196 substrate Cu, 72 oxide Cu, and 36 oxide O atoms.

Open command:

```bash
v_ase gui examples/readme_scene_assets/cu2o111_on_cu111_pairwise_bonds.traj --show-bonds
```

## materials

Identical Cu13 clusters for Standard, Metal, and Rubber material comparison.

- Static: `material_presets.traj`
- Suggested selected indices: ``
- Labels map left-to-right to Standard, Metal, and Rubber.
- Each material group contains 13 Cu atoms.

Open command:

```bash
v_ase gui examples/readme_scene_assets/material_presets.traj --show-bonds
```

## fixedline

Li ion constrained to a FixedLine inside a carbon nanotube channel.

- Static: `fixedline.traj`
- Suggested selected indices: `128`
- The short center axis remains visible without selection.
- Starting G shows the longer original-position direction guide.

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

Idealized ferrocene scene for rotations around an active Fe atom pivot.

- Static: `ferrocene.traj`
- Suggested selected indices: `1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0`
- Select the top ring, Shift-select Fe last, choose Active atom, and use R Z or R X.

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
