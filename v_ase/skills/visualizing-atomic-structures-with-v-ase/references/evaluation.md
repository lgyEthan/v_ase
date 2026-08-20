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
13. `[trigger]` Twist this 2D layer to the nearest commensurate cell below 16x area.
14. `[trigger]` Match this hBN guest cell to a graphene host below one percent strain.
15. `[trigger]` Translate this selected layer rigidly in the periodic (1 0 0) plane and map its geometric score.
16. `[trigger]` Randomly add 20 Li and 10 H atoms to this triclinic cell and repel only the new atoms from short contacts.
17. `[trigger]` Build a cubic Cu crystal from ASE defaults, or rocksalt CuO with a specified lattice parameter.

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

- wrap, translate-all, set-unit-cell, build-bulk, set-supercell, make-supercell;
- add-atom, scatter-atoms, scatter-molecules, update-add-atoms-region,
  scale-add-atoms-regions, relax-added-atoms, stop-added-atoms,
  finish-add-atoms, cancel-add-atoms, delete-selection, set-identity,
  set-constraints;
- move-selection, rotate-selection, scale-selection, rotate-to-commensurate,
  load-commensurate-guest, remove-commensurate-guest,
  calculate-commensurate, apply-commensurate-cell,
  dismiss-commensurate-cell, calculate-registry-map,
  start-registry-relaxation, set-registry-translation, run-registry-relaxation,
  stop-registry-relaxation, finish-registry-relaxation,
  cancel-registry-relaxation, undo, redo,
  reset-coordinates;
- start-relaxation, stop-relaxation, exit-relaxation-mode,
  refresh-displacements;
- load-volumetric, show-volumetric, add-volumetric-plane,
  update-volumetric-planes, remove-volumetric-planes, combine-volumetric,
  remove-volumetric;
- calculate-rdf, set-atom-colorscale;
- set-interface-theme, set-personal-visual-default,
  restore-app-visual-defaults.

Current export coverage:

- image, video, poscar, pickle, blender, 3dm, obj, html, project, settings,
  rdf-csv, commensurate-csv, registry-csv.

## End-To-End Scenarios

Run all scenarios, not only static document checks:

1. **Launch and discovery**
   - install the built wheel in a clean environment;
   - verify `v_ase --version` and `from v_ase.visualize import view`;
   - launch `v_ase gui STRUCTURE --interactive --cli`, parse the handshake,
     and fetch skill/schema/state;
   - verify `command_transport` is `http-json-bridge`;
   - use a separate `v_ase api` process for ready/describe/apply/render/export
     without evaluating page-main-world JavaScript.
   - open a remote 15-frame XDATCAR in View mode and require one byte-offset index pass
     plus on-demand frame reads rather than a complete trajectory
     transfer; repeat with native ASE `.traj`, then verify an unsupported or
     unusual XDATCAR header falls back to the standard ASE reader;
   - submit an unknown extension and require a concise reader message such as
     `Could not guess file type` in the GUI, never an unexplained
     `Internal Server Error` or a Python traceback.
2. **Structure and camera**
   - describe a periodic structure;
   - align `+X`, `-Y`, and `+Z`;
   - orbit left/right/up/down and roll both directions;
   - verify camera changes do not enter undo history;
   - switch the complete scene to 2D and require flat unlit atoms, adaptive
     outlines, flat bonds/vectors/cell/regions, and an X on FixAtoms while
     preserving atom color and radius; switch back and require the prior 3D
     materials and lighting to return without reloading structure data;
   - capture a persistent Render Area, disable Follow Viewport, orbit the work
     camera, and require the stored export camera to remain unchanged; select
     through the gray-masked frame and require picking to use the Render Area
     projection, then move its eye with `G` in Edit and verify
     `describe().renderArea` and image/video/HTML exports share that camera;
   - play a trajectory while moving the Sun and Render Area and changing atom
     appearance; require uninterrupted playback and immediate visual updates.
3. **Selection and measurement**
   - select one through four ordered atoms;
   - verify one-atom displayed Cartesian/fractional position, standard ASE
     attributes, arbitrary scalar/vector/string arrays, and stored calculator
     results, then verify direct/MIC distance, angle, and torsion;
   - change trajectory frame while keeping one atom selected and verify every
     property comes from the displayed frame without duplicate requests or a
     calculator evaluation;
   - select a View replica and verify its `cellOffset`, then apply appearance
     to that exact replica without disabling the controls;
   - hide one View replica with Delete and require only that reference and its
     bonds to become invisible/non-interactive; opening structural analysis
     must show a Continue or Switch to Edit & Delete decision before plotting;
   - enter Edit, select repeated images by click and box, and require one
     deduplicated base index per physical atom, including periodic boundaries.
4. **Edit and constraints**
   - launch with no input file, require Edit mode, define a triclinic 3 x 3
     cell, add atoms, and verify the empty-workspace prompt disappears after
     either a region, cell, or atom is created;
   - query the installed ASE bulk catalog; build automatic cubic Cu and verify
     four atoms, then require `crystalStructure` and `a` for CuO, preview cubic
     rocksalt CuO, require approval before replacement, build eight atoms, and
     Undo back to the complete original trajectory and visual settings;
   - enter Edit, move and rotate atoms, then undo/redo;
   - copy and paste constrained atoms at exactly identical coordinates; require
     labels, custom arrays, tags, momenta, charges, supported constraints,
     per-atom stored calculator values, and per-atom material overrides to
     survive while invalidated global total energy is omitted;
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
	   - on a complex single periodic structure, start Add Atoms with two
	     element/label populations and a fixed seed; verify the highlighted cell
	     or Cartesian region, requested counts, label order, and new selection;
	   - start placement through common `start-relaxation` with the exact
	     Structure > Relaxation calculator/cutoff/device/fmax/steps payload; after
	     completion, edit a region, append a molecule batch without Finish, and
	     verify `placement_count`, `last_batch_new_count`, total staged count, one
	     history entry, one immutable pre-session host, and a newly reset Add
	     timeline before the next relaxation;
	   - verify the staged host appears in the semantic constraint summary while
     the ASE constraints remain unchanged, then verify the temporary summary
     disappears after finish and cancel;
   - verify 100,000 fractional samples in a skewed triclinic cell have the
     expected mean, variance, and 4 x 4 x 4 voxel occupancy, and verify a
     Cartesian AABB never returns two periodic representations of one voxel;
   - compare random Cartesian and fractional requests and prove both remain
     physical-volume uniform; compare homogeneous Cartesian and fractional
     placement, verify the selected metric, deterministic seed, and exact
     triclinic MIC when `pbcAware:true`;
   - compare homogeneous odd-count point sets against nearest-neighbor and
     covering-radius diagnostics; compare automatic and explicit Regular grid
     placement in orthogonal/triclinic cells, require global Cartesian spacing,
     half-open PBC uniqueness, and a clear insufficient-site failure without
     silently shrinking explicit spacing;
   - test overlapping multiple Allow and Reject Cartesian regions against an
     independent convex-polyhedron volume reference, including reject-only
     fallback to a finite cell and the required error without a finite cell;
     verify stable IDs, exact union-minus-union volume, default
     `allowEscape:true`, confined `allowEscape:false`, Shift multi-selection,
     group `G` translation and global-Cartesian `S` scaling of all selected
     bounds, edge-only nested-box selection, and rejected `R` without moving
     staged atoms;
   - translate a region through each face of a skew triclinic cell with region
     MIC enabled; require clipped lattice-equivalent pieces on the opposite
     face, one intact source cuboid at the original Cartesian bounds, no
     zero-shift wrapped fragment, no duplicate wrapped edge, translation-
     invariant volume, and sampled membership identical to the backend domain;
   - run pairwise repulsive placement with MIC and the host temporarily fixed;
     require finite progress events, then finish and prove every host
     coordinate, constraint, tag, charge, custom array, label, and calculator
     survives exactly while only staged atoms remain added;
   - require an `add-atoms` movie timeline with at least two accepted frames
     during placement and require it to disappear after finish or cancel;
   - discover the molecule catalog from `capabilities`, place several H2O
     molecules with homogeneous Cartesian centers and random 3D orientation,
     verify native ASE-origin anchoring and element-prefixed labels, then run
     rigid repulsive placement and prove every molecular pair-distance matrix
     is invariant; repeat with density mode over multiple Allow/Reject regions
     and require exact accessible volume, primitive-ratio reduction, nearest
     complete composition batch, target and actual density, and unchanged
     staged topology after a region update;
   - change `regionMic` while the workspace is active and require the backend
     domain, clipped triclinic preview images, and confinement policy to update
     together without moving staged atoms;
   - place an out-of-domain point beside a skew periodic face and require the
     shortest triclinic MIC confinement vector rather than a direct Cartesian
     jump;
   - reject fractional, string, and Boolean atom/molecule counts without
     mutating the structure;
   - translate and rotate complete staged rigid molecules, then attempt one
     partial molecular edit and require rejection without coordinate mutation;
     repeat with rigid mode disabled and verify atomwise motion is permitted;
   - repeat and cancel; require exact structure/history/redo restoration and a
     hidden insertion region; verify a trajectory is rejected before mutation;
   - perform the same scatter, asynchronous placement, polling, and finish from
     a fresh external CLI agent that knows only this Skill, and inspect the
     resulting live GUI rather than accepting an HTTP success alone.
   - on a cell-free scratch cluster, start fallback repulsion from exactly
     coincident atoms, stop, restart, and verify separation; exit once with
     Keep Current and once with Restore Before Relaxation while a worker is
     active, requiring correct button state and exact baseline restoration;
   - select atoms and apply GUI/semantic isotropic plus X/Y/Z scaling. Require
     coordinates to follow the selected pivot in global Cartesian axes while
     atom radii, bond diameter, and cell remain bitwise unchanged.
5. **Periodic structure**
   - wrap atoms;
   - display a monoclinic supercell;
   - apply Cartesian and fractional visual offsets after repetition;
   - verify View replicas remain independently selectable while Edit replicas
     select and deduplicate their corresponding base atoms;
   - materialize repetitions and an integer cell transform;
   - verify every trajectory frame gets its own transformed cell.
   - rotate a selected graphene layer near `21.2` degrees with
     `rotate-to-commensurate`; verify exact `21.786789` degrees, area ratio 7,
     zero boundary strain, positive-determinant source/target matrices,
     `(√7 × √7)` notation, opaque core, and one-cell shell;
   - project the complete proposal bounds through the live camera and verify
     they remain inside the viewport, then dismiss and verify camera restore;
   - set `maxAreaRatio` to 6 and verify the area-7 proposal is rejected;
   - enable the commensurate workspace before rotating and verify cells-only
     preview, monotonic progress, the preserved direct angle, no green common
     cell or materialization control at an unmatched initial angle, and a live
     current-angle plane on the 3D overview; require host and guest primitive
     grids to expose their integer grid dimensions, remain readable as separate
     black/orange lattices, and retain identical shapes and host origins across
     unmatched and matched angles; at an exact candidate angle require one
     green common-cell boundary without resizing either parent grid;
   - verify the 3D overview has a horizontal angle axis, an orthogonal depth
     axis for area ratio, a vertical strain axis, a gridded candidate surface,
     candidate markers, a live current-angle plane, perspective depth, and
     readable axis titles rather than a flat collection of disconnected lines;
     require dotted symmetry periods only for an exact detected lattice
     symmetry and never infer them for a generic oblique host/guest pair;
   - switch to Paper strain projection and verify mean absolute strain, actual
     common-cell atom count, angle color, and an unchanged accepted candidate;
   - reconstruct the six published Stradi Table 3 mean-strain values from its
     printed tensor components within one final-table rounding unit;
   - compare the accelerated search against complete enumeration through area
     ratio 5, and verify the full analytic `(m,m+1)` TBG series through
     `(31,32)` plus an equivalent oblique integer basis;
   - load the graphene/MoS2 visual fixture from
     `examples/commensurate_host_guest`, verify visibly different `2.46 Å` and
     `3.18 Å` parent grids, fixed grid extents and origins, cells-only default,
     independent atom visibility, and the rectangular graphene
     `(√7 × √21) R±19.11°` area-14 / MoS2 `2 × 2` area-4 result at
     `|19.10660535|` degrees with `2.3357%` maximum principal strain;
   - load the graphene/Cu(111) strict numerical fixture from the same directory,
     verify the `√13` / `√12` result at `|16.10211375|` degrees, both documented
     strain values, and 38 atoms; verify absolute
     and parent-traversal paths are rejected, and compare guest-strain and
     host-strain matches without conflating their integer matrices;
   - enable atom preview and verify opaque host/guest cores, one-cell shells,
     and boundary bonds while host, guest, and common cells remain visually
     distinct;
   - verify non-Z commensurate rotation is rejected, global-Z rotation updates
     only the current marker until a new bounded search is required, and CSV
     contains angle, matrices, area, both strain definitions, atom counts, and
     references;
   - materialize only after explicit approval and verify atom count, cell
     determinant, PBC, constraints, and cleared proposal state.
   - reject materialization for trajectories and volumetric documents instead
     of applying one frame or dropping grids;
   - activate rigid planar translation with and without a precomputed map;
     compare its two-coordinate energy gradient to central finite differences,
     verify `projected_force` units and convergence, require host/cell/selected
     internal invariants, inspect the mode-only timeline, cancel to exact
     baseline, then finish another run and undo it in one step;
   - for skew cells, test `(0,0,1)`, `(1,0,0)`, and `(2,1,1)` against exact
     integer lattice vectors satisfying `h*u+k*v+l*w=0`; reject a plane whose
     primitive basis uses a disabled PBC vector;
6. **Appearance**
   - change radius, color, opacity, visibility, and material; verify opacity
     `0..1` in ordinary, instanced, repeated-supercell, and flat-2D rendering;
   - discover and render coordinate, stored force-norm, scalar-array,
     vector-component, vector-norm, charge, magnetic-moment, and MLIP-specific
     per-atom colorscales; test all-atoms and selected-only scope;
   - fit the current frame, advance to a frame with a disjoint value range,
     and verify the resolved `vmin`/`vmax` remain locked;
   - scan the complete trajectory and compare its global extrema with an
     independent finite-value reference; verify a bounded scalar cache is
     fetched once, reused across frames, and does not race a single-frame
     prefetch, while oversized inputs use backend range scanning;
   - verify manual `vmin`/`vmax`, gamma contrast, standalone HTML and media
     export all preserve the same trajectory-wide range and that each frame's
     colors change only from its values, not from per-frame normalization;
   - verify disabling the feature performs no scalar/LUT request and restores
     the prior label/per-atom colors immediately;
   - enable force vectors on a trajectory with stored forces, require exact
     normalized Cartesian arrow direction and `scale * |F|` length on every
     frame, verify 2D/3D styling and supercell repetition, and ensure a missing
     force frame does not evaluate its calculator;
   - verify standard, metal, rubber, 2D, and 3D;
   - undo and redo a label color, radius, opacity, and material change; verify both
     semantic display state and rendered pixels, with one history step per
     completed field edit;
   - verify bonds, pairwise cutoffs, MIC toggle, cell styling, and lighting.
7. **Constraints rendering**
   - inspect FixAtoms, FixScaled, FixedLine, FixedPlane, and Hookean;
   - verify persistent FixedPlane markers remain depth-tested while its
     motion-only plane remains readable above the moving atom scene;
   - derive `rt` and `k` from the actual ASE Hookean constraint; verify zero
     constraint force and no active spring at `r <= rt`, force magnitude
     `k(r-rt)` plus an annotation-free 3D helix at `r > rt`, nonzero depth, and
     visible coil pitch on every trajectory frame.
8. **Trajectory**
   - open `examples/readme_scene_assets/crowded_c60_relaxation.traj` with
     `--index :` and assert `frameCount == 42` before testing frame controls;
   - step frames, retain selection, play, change FPS/skip;
   - compute displacement with and without MIC;
   - verify current-position vector anchors, supercell repetition, and equal
     endpoint translation without changing vector values;
   - render interpolation with known frame count.
9. **Volumetric and RDF analysis**
   - open a multi-frame trajectory with two explicitly frame-associated scalar
     fields, keep RDF, per-atom colors, force/displacement vectors, and the
     isosurface visible, then step frames and require every result to report the
     active frame; step to a frame without a field and require the previous
     surface and its semantic summary to disappear;
   - load VASP CHGCAR/LOCPOT/PARCHG/ELFCAR plus Cube and XSF fixtures, including
     VASP basenames with `.`, `_`, and `-` calculation suffixes;
   - compare parsed shape, cell, origin, PBC, scalar range, quantity, and units
     with the source fixture;
   - create single and signed isosurfaces, verify nonblank triangles, colors,
     opacity, and step-size behavior;
   - move the README isovalue slider through several values, require the
     histogram/slider marker and mesh to update at every level, and prove the
     source distribution is computed once rather than regenerated per mesh;
   - compare zero and nonzero field smearing, verify FP32/FP64 source arrays
     remain unchanged, periodic axes wrap, and nonperiodic axes do not bleed
     across their boundary;
   - compare zero and nonzero mesh smoothing, verify interior vertices move
     while cell-boundary vertices and periodic seams remain closed;
   - verify semantic state reports rendered levels, post-smearing range,
     surface/triangle counts, and partial signed status while the source
     dataset descriptor stays unchanged;
   - reject an invalid sign mode, step size, sigma, fractional smoothing pass,
     opacity, color, and zero signed level rather than clamping;
   - verify a volumetric import emits an `analysis` collaboration event and
     never a false `trajectory.frames` change;
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
   - benchmark representative 15-million-point PARCHG and LOCPOT grids in
     FP32 and FP64; require complete parsing below the documented readiness
     threshold, nonblank browser meshes, and a cache hit for an identical mesh
     request;
   - calculate total RDF at several cutoffs for a homogeneous periodic system,
     including a radius that needs images beyond a fixed `2 x 2 x 2`
     repetition, and verify its non-edge plateau approaches one and aligns
     with the plotted `g(r) = 1` reference;
   - calculate a trajectory RDF once, play through cached frames without the
     Plotly drawer disappearing, and force the bounded rolling-cache path with
     a large frame/bin/curve product;
   - calculate a distribution, preview and commit a selected-atom `G` move,
     and require the same open drawer to replace its curve with one calculated
     from the displayed preview/committed coordinates;
   - run structure relaxation, switch between its operation-specific movie
     frames, and require the distribution source/frame metadata and curve to
     follow that relaxation timeline rather than the loaded source frame;
   - calculate active, selected-active-bond, all, and no-partial modes; change
     the selection to a different active label pair and verify a debounced
     refresh, then select another bond of the same label pair and verify no
     duplicate RDF request; verify the
     concentration-weighted partial RDF relation reconstructs the total;
   - on a finite no-PBC cluster, require `analysisKind="pair-distribution"`,
     title `Pair-distribution function`, full-range probability integral one,
     shorter-cutoff integral equal to the included unordered-pair fraction,
     and matching label-pair CSV columns; continue to reject partial PBC;
   - generate the README amorphous pairwise example and require total, Cu-Cu,
     Cu-Zr, and Zr-Zr curves even when first-seen label order is nonlexical;
   - reject partial PBC, retain an explicit long triclinic cutoff, verify the
     returned image extent/span, render the Plotly drawer, and export matching
     CSV columns and row count.
   - require a selected movable component for the planar translation map, scan
     both short-contact and bond-strain metrics, and verify the live marker
     follows unwrapped plane-lattice coordinates while `G` remains constrained
     to the requested `(hkl)` plane;
   - verify both registry metrics are reported as geometry scores rather than
     energies and that the registry CSV matches every plotted grid point;
   - verify RDF, commensurate, and registry graphs each expose one adjacent
     icon-only CSV action with an accessible label; use real pointer clicks to
     download CSV and close the drawer, confirming the viewport canvas does not
     intercept either action.
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
   - on macOS, generate a real Quick Look thumbnail for project-embedded HTML,
     require a nonblank structure poster, then open the same file from
     `file://`, rotate it, and recover the embedded project through v_ase;
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
    - require exact equality among live schema operation/export keys,
      `capabilities()` names, browser operation/export dispatchers, and the
      canonical Skill; an extra or missing name is a release blocker;
    - run selection, Edit-mode atom motion, camera, axes/cell/grid, render, and
      export through separate `v_ase api` subprocesses, then inspect the same
      GUI controls and semantic revision rather than relying on page-injected
      API calls;
    - regenerate `readme_ai_edit.gif` with external CLI subprocesses and verify
      the final GUI structure against its ASE reference coordinates/elements;
    - add and sweep the README volumetric plane through external CLI
      operations and verify every offset in
      `describe().analysis.volumetricPlanes` before capturing a frame.
12. **Settings and resets**
    - save and reload display supercell and visual translation;
    - verify Reset Coordinates preserves both;
    - verify full Reset returns translation to zero;
    - verify pairwise rows expose enabled/max only and retain a resized label
      column.
13. **Interface theme and personal defaults**
    - verify System follows `prefers-color-scheme` and explicit Light/Dark
      choices update the workspace shell and every document frame;
    - save a current 2D/flat-bond/radius setup as the personal default, open a
      new document, and verify it inherits the reusable values without the
      previous camera or per-atom overrides;
    - verify canceling the GUI warning preserves the preference;
    - verify the agent restore operation fails without `confirm:true`, then
      succeeds after explicit approval and returns the built-in visual values;
    - verify another open tab receives the configured/unconfigured status.
14. **README scientific examples**
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
    - inspect the commensurate cells-only image and require complete host and
      guest primitive grids surrounding the proposal plus readable square-root
      notation; inspect its 3D candidate plot from an oblique camera;
    - inspect the planar translation images and require one full physical
      periodic cell, current and optimum markers, a readable metric, a visible
      unit cell, and a separate no-colorscale optimizer-trial path;
    - select the ethane H-C-C-H order and verify the media visibly transitions
      through distance, angle, and torsion;
    - inspect the separate displacement image for nonzero vectors and readable
      frame/reference statistics;
    - play the semantic graphene edit and verify one center vacancy, three
      `N_pyridinic` neighbors, one `Li_site` 2.15 A above the vacancy, the
      documented source/intermediate/final CIF files, and a nonblank oblique
      render;
    - inspect the collaboration figure and animation with no accompanying text;
      require a first-time reviewer to identify You, the external AI Agent, and
      one live v_ase structure; the bidirectional Natural language, CLI, and GUI
      channels; the N3/Li request; structured Agent operations; live GUI edits;
      human GUI refinement; revision re-synchronization; and the final
      natural-language completion. Reject detached endpoints, unreadable
      microcopy, or a channel whose payload cannot be inferred;
    - compare three identical Cu13 clusters and verify Standard, Metal, and
      Rubber remain visibly distinct without changing ASE element, radius, or
      color;
    - play the 96-Cu plus moving-O colorscale trajectory with one locked global
      range and verify all 97 atoms are mapped, every visible force arrow
      changes with and exactly follows the active frame's stored Cartesian
      vector, the arrow and colorscale use that same array, and the stored net
      force is zero in every frame;
    - play the isovalue GIF and require continuous mesh changes at fixed camera
      and background; play the plane GIF and require continuous slice changes
      with fixed `vmin`/`vmax`, atoms, cell, camera, and background;
    - inspect the pairwise RDF image and require all three Cu/Zr partial curves
      plus total RDF and the `g(r)=1` reference;
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
- a resolved commensurate common-cell preview shows complete host and guest primitive
  lattices extending at least one primitive cell beyond the highlighted common
  cell, readable grid dimensions and paper-style notation, plus opaque atoms,
  a one-cell halo, and boundary-crossing bonds when atom preview is enabled;
- an unmatched direct commensurate angle shows no green common cell and keeps
  the black host and orange guest parent lattices visually dominant;
- the commensurate candidate graph reads as a 3D coordinate system with angle
  horizontal, area ratio in depth, strain vertical, a gridded floor projection,
  discrete candidate points, and a moving current-angle plane rather than
  stems or disconnected 2D linework;
- live View checkboxes hide and restore world axes and the unit cell without
  affecting the orientation gizmo;
- Hookean spring has X and Z span around its axis and wire radius smaller than
  its coil radius, adds no numeric annotation, and appears only beyond the ASE
  `rt` cutoff;
- signed volumetric surfaces have distinct positive/negative coverage, repeat
  with the displayed supercell, move by the same visual translation as atoms,
  appear automatically for a newly loaded grid, and update opacity live;
- raw and absolute volumetric histograms each have 256 bins, preserve the
  source voxel count, and drive single/signed slider ranges without mesh work;
- multiple hkl planes remain individually selectable, expose mixed values
  without inventing a common value, accept atomic multi-plane edits, clip to
  skew unit cells and supercells, use periodic interpolation, and replace the
  low-resolution `G/R` preview with the configured settled resolution;
- View mode can create and edit plane hkl and signed grid-origin distance
  without changing ASE coordinates; Edit-mode numeric and pointer `G/R`
  transforms update the corresponding distance slider and hkl fields live;
- editing one selected plane requests and replaces only that plane raster,
  and a high-resolution section through a representative skew structure stays
  within the documented timing and temporary-memory budget;
- semantic add/update/remove plane commands round-trip through `describe()`,
  reject stale IDs and invalid hkl/ranges atomically, and survive `.vase`
  project save/load;
- FP64 volumetric import remains FP64 through combination and `.vase`
  round-trip while the browser receives only compact mesh geometry;
- the RDF drawer is nonblank, labeled in Angstrom and `g(r)`, and exposes the
  retained cutoff, `g(r) = 1` bulk reference, and required periodic-image span
  without clipping; the amorphous regression reaches a flat long-range
  plateau;
- stored-force arrows preserve exact Cartesian direction and configured scale
  in both 2D and 3D, follow displayed replicas, and remain absent without
  stored force data;
- a narrow viewport keeps every top-bar command reachable through one stable
  horizontal scroll track without overlap or wrapping;
- the native file picker confirms one file with Enter and does not immediately
  reopen from a trailing key event;
- the Render Area gray mask, eye marker, border, pointer projection, live
  lighting, and exported image decode to the same composition and camera;
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
