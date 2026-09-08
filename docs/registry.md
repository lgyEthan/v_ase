# Registry maps and rigid translation

Explore lateral alignment between a known selected fragment and its host.
Open **Analysis > Rigid Translation**. A map
samples translations; rigid relaxation searches translations without changing
internal fragment geometry.

## Registry maps

Registry analysis translates one rigid selected component over a periodic
`(hkl)` plane and evaluates a geometric metric on a bounded 2D grid. Available
metrics include current short-contact and bond-strain screens. The result keeps
the exact plane basis and Cartesian translations so a point can be reproduced
or exported to CSV.

These maps are geometric screens, not potential-energy surfaces. Their meaning
depends on the selected component, plane, pair cutoffs, reference bonds, and
grid resolution.

## Rigid registry relaxation

After choosing the moving component, v_ase can optimize one shared rigid
translation in either:

- a compatible periodic `(hkl)` plane; or
- bounded Cartesian x/y/z translation.

All selected atoms preserve internal geometry. The optimization timeline can
be scrubbed before Finish or Cancel. Plane and Cartesian modes have explicit
bounds; invariant-geometry and finite-difference checks protect the rigid
contract.

Use **Finish** to commit the selected result. **Cancel** restores the exact
pre-workflow structure. Stopping leaves the workspace and current result open
for inspection.

![Registry map and rigid translation](assets/readme_registry_map.png)

## Example: translate a known bilayer fragment

Download {download}`graphene_hbn_commensurate.traj <assets/examples/graphene_hbn_commensurate.traj>`. Open in Edit and select
the upper hBN layer (all B and N atoms), leaving the C host unselected.

1. Choose a 2D periodic translation plane and a sampling resolution in the registry panel.
2. Choose **Short-contact score** or **Interfacial bond strain** for the optional
   map. These are geometric scores, not calculated binding energies.
3. Run the map and compare the current and lowest sampled translations.
4. Apply a chosen translation and confirm that intralayer distances are unchanged.
5. Alternatively start rigid translation relaxation, inspect its own timeline,
   and explicitly keep or restore the resulting translation.

```{vase-animation} assets/readme_registry_relax.gif
:alt: The existing rigid-translation demonstration explores registry without deforming the fragment.
:fallback: assets/readme_registry_map.png

The existing rigid-translation demonstration explores registry without deforming the fragment.
```

A discrete map minimum is only the best sampled translation for that objective.
See [relaxation](relaxation.md) for the distinction from unconstrained atom motion.
