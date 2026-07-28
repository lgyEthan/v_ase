# Evaluation

## Contents

1. Trigger Evaluation
2. Capability Audit
3. End-To-End Scenarios
4. Visual Assertions
5. Release Gate

## Trigger Evaluation

The description should trigger for these requests even when v_ase is not named:

1. `[trigger]` Render a publication-quality image of this POSCAR.
2. `[trigger]` Measure bond lengths and angles in an ASE structure.
3. `[trigger]` Edit selected atomic coordinates with FixedPlane enforced.
4. `[trigger]` Play an extxyz trajectory and export a MOV.
5. `[trigger]` Show a 2x2x1 periodic supercell and MIC bonds.
6. `[trigger]` Create a Blender scene from an atomistic model.
7. `[trigger]` Save this visual setup as a reusable atomistic project.
8. `[trigger]` Analyze trajectory displacement vectors.
9. `[trigger]` Find a clear camera angle for graphene on hBN.
10. `[trigger]` Let an AI inspect an atomic structure without screenshot OCR.

It should not trigger for these nearby but unrelated requests:

1. `[no-trigger]` Render a Blender character animation.
2. `[no-trigger]` Plot a generic CSV time series.
3. `[no-trigger]` Explain Hooke's law without an atomic structure.
4. `[no-trigger]` Edit a PNG logo in an image editor.
5. `[no-trigger]` Run a molecular dynamics simulation from scratch.
6. `[no-trigger]` Design a general-purpose website.
7. `[no-trigger]` Convert a CAD building model to OBJ.
8. `[no-trigger]` Install an unrelated Python visualization package.
9. `[no-trigger]` Summarize a materials-science paper.
10. `[no-trigger]` Configure a generic FastAPI server.

Review both lists whenever the skill description changes.

## Capability Audit

Before every release:

1. start `v_ase gui EXAMPLE --for-ai`;
2. call `capabilities()`;
3. compare every reported state field, apply key, operation, and export with
   `references/semantic-api.md`;
4. compare the JSON Schema at `schema_url`;
5. fail if code has an undocumented capability or the skill documents a
   nonexistent capability.

Current operation coverage:

- wrap, translate-all, set-supercell, make-supercell;
- add-atom, delete-selection, set-identity, set-constraints;
- move-selection, rotate-selection, undo, redo, reset-coordinates;
- start-relaxation, stop-relaxation, refresh-displacements.

Current export coverage:

- image, video, poscar, pickle, blender, 3dm, obj, project, settings.

## End-To-End Scenarios

Run all scenarios, not only static document checks:

1. **Launch and discovery**
   - install the built wheel in a clean environment;
   - verify `v_ase --version` and `from v_ase.visualize import view`;
   - launch `--for-ai`, parse handshake, fetch skill/schema/state.
2. **Structure and camera**
   - describe a periodic structure;
   - align `+X`, `-Y`, and `+Z`;
   - orbit left/right/up/down and roll both directions;
   - verify camera changes and undo.
3. **Selection and measurement**
   - select one through four ordered atoms;
   - verify atom summary, direct/MIC distance, angle, and torsion;
   - select a replica and verify its `cellOffset`.
4. **Edit and constraints**
   - enter Edit, move and rotate atoms, then undo/redo;
   - apply FixAtoms, FixedLine, and FixedPlane;
   - verify returned backend coordinates;
   - add, relabel, change element, and delete a test atom.
5. **Periodic structure**
   - wrap atoms;
   - display a monoclinic supercell;
   - materialize repetitions and an integer cell transform;
   - verify every trajectory frame gets its own transformed cell.
6. **Appearance**
   - change radius, color, visibility, and material;
   - verify standard, metal, rubber, 2D, and 3D;
   - verify bonds, pairwise cutoffs, MIC toggle, cell styling, and lighting.
7. **Constraints rendering**
   - inspect FixAtoms, FixScaled, FixedLine, FixedPlane, and Hookean;
   - verify the active Hookean spring has nonzero depth and visible coil pitch.
8. **Trajectory**
   - step frames, retain selection, play, change FPS/skip;
   - compute displacement with and without MIC;
   - render interpolation with known frame count.
9. **Exports**
   - render exact PNG/WebP dimensions and compare decoded pixels;
   - reopen POSCAR, pickle, `.vase`, settings, OBJ metadata, and 3DM;
   - syntax-check Blender output and inspect camera, bonds, cell, and light;
   - probe MOV/AVI dimensions, FPS, and frame count.
10. **Human takeover and documents**
    - create and switch independent documents;
    - verify state isolation and distinct `.vase` output;
    - open `human_url` and confirm it shows the AI-modified state.

## Visual Assertions

Every browser render test must check:

- canvas/export is nonblank;
- output dimensions exactly match the request;
- structure occupies the expected frame without clipping;
- axis-view direction and projection are correct;
- atom colors and materials are distinguishable;
- visible constraints have nonzero pixel coverage;
- Hookean spring has X and Z span around its axis and wire radius smaller than
  its coil radius;
- preview and exported image decode to the same composition;
- README assets are inspected after regeneration, not merely written.

## Release Gate

Required commands:

```bash
conda run -n python311 python -m pytest -q
conda run -n python311 python -m pytest tests/test_agent_skill.py -q
conda run -n python311 python -m build
conda run -n python311 python -m twine check dist/*
```

Also run the optional Rhino tests in an environment containing `rhino3dm`.

Do not release when:

- a skill reference is stale or missing;
- an AI operation lacks semantic and rendered verification;
- generated README media is outdated;
- clean-wheel installation or `v_ase` entry point fails;
- GitHub, PyPI, README, skill, and renderer assets would describe different
  versions.
