# Export structures and 3D scenes

Save physical structures for scientific programs, or export scene geometry
for Blender, OBJ-compatible tools or Rhino. Open **Render → Geometry**
and choose the export format. Structure-only POSCAR and
ASE Pickle are also available from the File commands.

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

Water surfaces are included from 0.4.9. **Render → Geometry → Blender** downloads
`v_ase_blender_scene.py`. In Blender's Scripting workspace, open that file in the
Text Editor and choose **Run Script**. Run generated scripts only from trusted
projects. The export sets up the scene; use a new Blender file if you have an
unrelated scene open.

The water object, `v_ase_water_surface`, is an editable mesh with smooth normals,
color, opacity, roughness and lit/unlit material. Its physical mesh matches the
viewport's density grid, smoothing and subdivision. Only displayed water copies
are included; hidden molecular atoms/bonds stay hidden, while ions and solids
remain atomistic. Source coordinates and molecule IDs are unchanged.

For trajectories, scrub Blender's timeline after running the script to see the
water surface change with each frame. Save a `.blend` for a static editable scene. To resume
procedural trajectory playback after reopening, run the generated script again;
the animation is not baked as independent mesh objects for every frame.

Export rejects more than four million refined water triangles in a frame or two
million combined surface vertices/sites across animation frames. Lower water
subdivision, repetitions, or export a shorter source trajectory. The scientific
isovalue is not automatically altered. Blender needs neither ASE nor a running
v_ase server to run the generated file.

### OBJ/MTL

OBJ export is a static scene packaged with MTL plus camera/metadata sidecar
information. It has no optional Python dependency.

### Rhino 3DM

3DM export uses block-instanced atoms and bonds, metadata, materials, and saved
views. Install the optional dependency first:

```bash
python -m pip install "v_ase-gui[rhino]"
```
