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
11. `[trigger]` Plot a signed charge-density-difference isosurface from three CHGCAR files.
12. `[trigger]` Calculate total and Cu-O partial RDF curves and export CSV.

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

1. start `v_ase gui EXAMPLE --cli`;
2. parse the first-line handshake and verify later stdout remains valid NDJSON;
3. open `human_url`, then call `capabilities` through
   `v_ase api "$COMMAND_URL"`;
4. compare every reported state field, apply key, operation, and export with
   `references/semantic-api.md`;
5. compare the JSON Schema at `schema_url`;
6. verify `events_url`, collaboration protocol, and `expectedRevision`;
7. fail if code has an undocumented capability or the skill documents a
   nonexistent capability.

Current operation coverage:

- wrap, translate-all, set-supercell, make-supercell;
- add-atom, delete-selection, set-identity, set-constraints;
- move-selection, rotate-selection, undo, redo, reset-coordinates;
- start-relaxation, stop-relaxation, refresh-displacements;
- load-volumetric, show-volumetric, combine-volumetric, remove-volumetric;
- calculate-rdf.

Current export coverage:

- image, video, poscar, pickle, blender, 3dm, obj, html, project, settings,
  rdf-csv.

## End-To-End Scenarios

Run all scenarios, not only static document checks:

1. **Launch and discovery**
   - install the built wheel in a clean environment;
   - verify `v_ase --version` and `from v_ase.visualize import view`;
   - launch `--cli`, parse handshake, fetch skill/schema/state;
   - verify `command_transport` is `http-json-bridge`;
   - use a separate `v_ase api` process for ready/describe/apply/render/export
     without evaluating page-main-world JavaScript.
2. **Structure and camera**
   - describe a periodic structure;
   - align `+X`, `-Y`, and `+Z`;
   - orbit left/right/up/down and roll both directions;
   - verify camera changes do not enter undo history.
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
9. **Volumetric and RDF analysis**
   - load VASP CHGCAR/LOCPOT/PARCHG/ELFCAR plus Cube and XSF fixtures;
   - compare parsed shape, cell, origin, PBC, scalar range, quantity, and units
     with the source fixture;
   - create single and signed isosurfaces, verify nonblank triangles, colors,
     opacity, and step-size behavior;
   - verify the first loaded grid is visible at a valid default level and
     changing opacity restyles the existing mesh without regenerating it;
   - display-repeat and visually translate atoms and meshes together;
   - physically materialize a supercell, verify atom and grid dimensions in
     every affected state, then undo both;
   - form `[1,-1,-1]` from three compatible grids and reject each incompatible
     shape/cell/origin/PBC/endpoint/units case;
   - load the same precision-sensitive fixture as FP32 and FP64, verify dtype,
     retained scalar difference, and the expected twofold grid-memory change;
   - save and reopen `.vase`, then require exactly the same bounded FP32/FP64
     volume and visualization settings;
   - calculate total RDF at several cutoffs for a homogeneous periodic system,
     including a radius that needs images beyond a fixed `2 x 2 x 2`
     repetition, and verify its non-edge plateau approaches one and aligns
     with the plotted `g(r) = 1` reference;
   - calculate active, all, and no-partial modes; verify the
     concentration-weighted partial RDF relation reconstructs the total;
   - reject partial PBC, retain an explicit long triclinic cutoff, verify the
     returned image extent/span, render the Plotly drawer, and export matching
     CSV columns and row count.
10. **Exports**
   - render exact PNG/WebP dimensions and compare decoded pixels;
   - verify JPEG and PDF preserve dimensions and use opaque output;
   - export 72 source frames at 30 FPS, decode exactly 72 frames, and verify
     2.40 seconds of playback;
   - enable displacement vectors and verify they are present in captured video
     frames;
   - reopen POSCAR, pickle, `.vase`, settings, OBJ metadata, and 3DM;
   - open lightweight standalone HTML from `file://`, verify saved camera and
     trajectory, orbit the canvas, confirm view-only controls, require no
     embedded-project download, and fail on any HTTP/HTTPS request;
   - separately export with `embedProject: true`, extract its nonempty
     embedded `.vase`, and reopen the HTML through `v_ase gui FILE.html`;
   - reopen standalone HTML with JavaScript disabled and require the poster to
     fill the exact export rectangle with no logo, header, border, or page
     margin; compare it to the first WebGL frame and reject any frame-bound
     movement during the cross-fade;
   - execute a real notebook using `%v_ase inline`, `%v_ase browser`, and
     `%v_ase auto`; confirm inline produces one iframe while browser mode
     creates the ordinary external workspace session;
   - syntax-check Blender output and inspect camera, bonds, cell, and light;
   - probe MOV/AVI dimensions, FPS, and frame count.
   - verify image progress is monotonic, reports an ETA, emits 100 exactly
     once, and reaches it only after the destination write.
11. **Live collaboration and documents**
    - create and switch independent documents;
    - verify state isolation and distinct `.vase` output;
    - open `human_url` and confirm it shows the AI-modified state;
    - change camera, selection, and appearance in the GUI and verify compact
      `source: human` NDJSON events reach the CLI;
    - verify a child-tab event includes its `session_id` and
      `document_revision`;
    - send an agent command with the prior `expectedRevision` and require a
      conflict, then re-describe and retry with the current revision;
    - verify agent-originated mutations are reported as `source: agent`.
    - run a fresh zero-context agent with only canonical `SKILL.md`; require it
      to launch the CLI, open `human_url`, use `command_url`, exercise every
      advertised operation/export or report an intentional optional-dependency
      failure, and verify semantic plus rendered results.
12. **Settings and resets**
    - save and reload display supercell and visual translation;
    - verify Reset Coordinates preserves both;
    - verify full Reset returns translation to zero;
    - verify pairwise rows expose enabled/max only and retain a resized label
      column.
13. **README scientific examples**
    - verify the phosphorene media starts from a flat sheet and records the
      production left-drag marquee selecting ridge 2 through the tail;
    - verify the Transform panel visibly contains Selection COM, X,
      `1.538889`, and **Rotate Selection**, then repeats with the box boundary
      advanced to ridge 3;
    - verify every actual browser selection matches the intended atom indices,
      reduces the active tail by one 12-atom puckered ridge, keeps the first
      ridge fixed, and accumulates exactly 13.85 degrees after 9 backend
      commits;
    - verify the final phosphorene frames orbit the camera from above the
      edited ribbon to below it without changing atom coordinates;
    - verify the phosphorene upper/lower ridge labels remain ASE phosphorus and
      render in the documented green/purple sublayer colors;
    - verify the ferrocene media Shift-selects Fe last, uses the Active atom
      pivot for both Z and X rotations, keeps Fe fixed, and places the active
      axis through Fe;
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
    - inspect the collaboration figure and verify it contains the actual live
      N3/Li GUI, a human natural-language request, structured agent steps, two
      real GUI-originated NDJSON events, and the re-synchronization rule;
    - compare three identical Cu13 clusters and verify Standard, Metal, and
      Rubber remain visibly distinct without changing ASE element, radius, or
      color;
    - inspect the Cu2O(111)/Cu(111) bonding scene from strict +Z and verify the
      complete 6 x 6 primitive oxide / 7 x 7 Cu coincidence cell remains in
      frame, one interfacial O is top-registered, only the documented
      oxide/interface Cu-O label pairs are enabled, and the thick custom bond
      color remains distinguishable over the touching-sphere substrate;
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
- FixedLine and line-like FixScaled guides contain one center axis and no ring
  geometry; during `G`, they add one longer original-position direction guide.
  FixedPlane and plane-like FixScaled guides retain one local ring;
- selected atoms use a yellow sphere outline with no billboard RingGeometry;
- rotation axis, fixed start, moving current, and commensurate candidate guides
  remain visually distinguishable;
- live View checkboxes hide and restore world axes and the unit cell without
  affecting the orientation gizmo;
- Hookean spring has X and Z span around its axis and wire radius smaller than
  its coil radius;
- signed volumetric surfaces have distinct positive/negative coverage, repeat
  with the displayed supercell, move by the same visual translation as atoms,
  appear automatically for a newly loaded grid, and update opacity live;
- FP64 volumetric import remains FP64 through combination and `.vase`
  round-trip while the browser receives only compact mesh geometry;
- the RDF drawer is nonblank, labeled in Angstrom and `g(r)`, and exposes the
  retained cutoff, `g(r) = 1` bulk reference, and required periodic-image span
  without clipping; the amorphous regression reaches a flat long-range
  plateau;
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
