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

- image, video, poscar, pickle, blender, 3dm, obj, html, project, settings.

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
   - verify FixedPlane keeps one local marker per atom and adds one original-
     position motion plane per selected constrained atom during `G`;
   - verify every rotation shows axis/start/current references and that the
     current reference follows the actual rotation sign;
   - verify returned backend coordinates;
   - add, relabel, change element, and delete a test atom.
   - run the generated 72-atom graphene workflow: delete the center-nearest C,
     remap its three neighbor indices after deletion, change them to ASE N with
     label `N_pyridinic`, and verify 71 atoms, three N elements, and three
     matching labels before rendering.
5. **Periodic structure**
   - wrap atoms;
   - display a monoclinic supercell;
   - apply Cartesian and fractional visual offsets after repetition;
   - verify View replicas remain selectable while Edit replicas do not;
   - materialize repetitions and an integer cell transform;
   - verify every trajectory frame gets its own transformed cell.
6. **Appearance**
   - change radius, color, visibility, and material;
   - verify standard, metal, rubber, 2D, and 3D;
   - undo and redo a label color, radius, and material change; verify both
     semantic display state and rendered pixels, with one history step per
     completed field edit;
   - verify bonds, pairwise cutoffs, MIC toggle, cell styling, and lighting.
7. **Constraints rendering**
   - inspect FixAtoms, FixScaled, FixedLine, FixedPlane, and Hookean;
   - verify persistent FixedPlane markers remain depth-tested while its
     motion-only plane remains readable above the moving atom scene;
   - verify the active Hookean spring has nonzero depth and visible coil pitch.
8. **Trajectory**
   - step frames, retain selection, play, change FPS/skip;
   - compute displacement with and without MIC;
   - verify current-position vector anchors, supercell repetition, and equal
     endpoint translation without changing vector values;
   - render interpolation with known frame count.
9. **Exports**
   - render exact PNG/WebP dimensions and compare decoded pixels;
   - verify JPEG and PDF preserve dimensions and use opaque output;
   - export 72 source frames at 30 FPS, decode exactly 72 frames, and verify
     2.40 seconds of playback;
   - enable displacement vectors and verify they are present in captured video
     frames;
   - reopen POSCAR, pickle, `.vase`, settings, OBJ metadata, and 3DM;
   - open standalone HTML from `file://`, verify saved camera and trajectory,
     orbit the canvas, confirm view-only controls, extract its embedded
     `.vase`, and fail on any HTTP/HTTPS request;
   - syntax-check Blender output and inspect camera, bonds, cell, and light;
   - probe MOV/AVI dimensions, FPS, and frame count.
   - verify image progress is monotonic, reports an ETA, emits 100 exactly
     once, and reaches it only after the destination write.
10. **Human takeover and documents**
    - create and switch independent documents;
    - verify state isolation and distinct `.vase` output;
    - open `human_url` and confirm it shows the AI-modified state.
11. **Settings and resets**
    - save and reload display supercell and visual translation;
    - verify Reset Coordinates preserves both;
    - verify full Reset returns translation to zero;
   - verify pairwise rows expose enabled/max only and retain a resized label
     column.
12. **README scientific examples**
    - verify the phosphorene media starts from a flat sheet, reduces the active
      tail selection by one 6-atom puckered ridge at each step, keeps the first
      ridge fixed, and accumulates exactly 36 degrees at the final ridge using
      21 Selection-COM increments;
    - verify the phosphorene upper/lower ridge labels remain ASE phosphorus and
      render in the documented green/purple sublayer colors;
    - verify the ferrocene media keeps Fe outside the selected ring and places
      the active axis through the Origin pivot;
    - inspect graphene/hBN from top view with world axes hidden and confirm the
      neutral start, amber current, and cyan commensurate candidates remain
      distinguishable;
    - select the ethane H-C-C-H order and verify the media visibly transitions
      through distance, angle, and torsion;
    - inspect the separate displacement image for nonzero vectors and readable
      frame/reference statistics;
    - play the semantic graphene edit and verify one center vacancy, three
      `N_pyridinic` neighbors, one `Li_site` 2.15 A above the vacancy, the
      documented source/intermediate/final CIF files, and a nonblank oblique
      render;
    - compare three identical Cu13 clusters and verify Standard, Metal, and
      Rubber remain visibly distinct without changing ASE element, radius, or
      color;
    - play the compressed-C60 FIRE trajectory and verify energy and fmax
      decrease before publishing its relaxation example.

## Visual Assertions

Every browser render test must check:

- canvas/export is nonblank;
- output dimensions exactly match the request;
- structure occupies the expected frame without clipping;
- axis-view direction and projection are correct;
- atom colors and materials are distinguishable;
- visible constraints have nonzero pixel coverage;
- FixedPlane motion planes have a visible surface, perimeter, and two in-plane
  axes without replacing the compact persistent per-atom marker;
- FixedLine and line-like FixScaled guides contain no ring geometry, while
  FixedPlane and plane-like FixScaled guides retain one local ring;
- selected atoms use a yellow sphere outline with no billboard RingGeometry;
- rotation axis, fixed start, moving current, and commensurate candidate guides
  remain visually distinguishable;
- live View checkboxes hide and restore world axes and the unit cell without
  affecting the orientation gizmo;
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
