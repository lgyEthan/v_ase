# v_ase README Scene Assets

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
