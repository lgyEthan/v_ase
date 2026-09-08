# Export structures and 3D scenes

Save physical structures for scientific programs, or export scene geometry
for Blender, OBJ-compatible tools or Rhino. Open **Export** and choose the
format required by the destination.

## Structure and data output

| Output | Contents and intended use |
| --- | --- |
| POSCAR | Current physical ASE structure in VASP format |
| ASE Pickle | Current `Atoms`, labels, constraints, arrays, and safe stored calculator results |
| RDF CSV | Radius, total `g(r)`, and requested partial curves |
| Commensurate CSV | Candidate angles/matrices, area ratios, residual strain, search metadata |
| Registry CSV | Complete translation grid, plane basis, Cartesian vectors, metric values |

The CLI `-o/--output` path writes the finalized physical structure through ASE;
`--output-format` overrides ambiguous output detection.

## Example: continue a surface figure in Blender

1. Open and style the [oxide/support example](bonds.md).
2. Choose Blender export and optimized label-group geometry.
3. Include the camera, bonds, cell or trajectory only as needed.
4. Import in Blender and inspect the atom groups, material mapping and camera.
5. For a simulation instead, export the ASE structure and verify chemical
   elements, physical atom count, cell and PBC. Display replicas are not atoms.

```{figure} assets/readme_bonds.png
:alt: Source oxide/support figure before export; this screenshot is from v_ase, not Blender.

Source oxide/support figure before export; this screenshot is from v_ase, not Blender.
```


## 3D scene output

### Blender

The generated Python scene uses grouped/instanced atom geometry, bond styles,
optional cell, trajectory animation, camera, and lighting. Optimized output
avoids one Blender object per atom; select individual-object output only when
atom-by-atom Blender editing is required.

### OBJ/MTL

OBJ export is a static scene packaged with MTL plus camera/metadata sidecar
information. It has no optional Python dependency.

### Rhino 3DM

3DM export uses block-instanced atoms and bonds, metadata, materials, and saved
views. Install the optional dependency first:

```bash
python -m pip install "v_ase-gui[rhino]"
```
