# v_ase viewer: mobile feasibility and recommended architecture

Assessment date: 28 September 2026.

For a mobile team unfamiliar with v_ase, start with the companion [iOS and Android developer handoff](v_ase_viewer_mobile_developer_handoff.md). It specifies product behavior, the owner's quality priorities, interaction rules and concrete acceptance scenarios; this assessment supplies the feasibility and dependency investigation.

This is an investigation and design recommendation, not an implemented mobile app. It examines the local 0.4.7 working tree, including its pending desktop fixes, at base commit `b0640038aadde01628e1ac42c337a03d3e6cf9c9`. Existing uncommitted application work is outside this document's changes. Platform references were checked on the assessment date; store requirements must be checked again before submission.

## 1. Decision

**A useful, offline iPhone/iPad/Android phone/tablet application named `v_ase viewer` is feasible. The recommended implementation does not require users to install Python, ASE, a terminal, or a companion computer.** Reuse the JavaScript scientific renderer, put a dedicated adaptive viewer UI around it, and package that UI in an iOS/Android native shell.

However, three different things must not be confused:

1. The current **desktop View mode** still calls the Python backend for loading, properties, analysis, persistence and exports.
2. The current **exported HTML viewer** already displays structures and trajectories without Python, but has substantially fewer controls than desktop View mode.
3. The requested **mobile viewer with all desktop View capabilities** needs a shared client-side document/data layer, mobile interaction design, and ports of remaining scientific operations. It is a product development project, not a CSS change or an Electron repackaging task.

The principal feasibility conditions are:

- Read existing `.vase` archives locally, including ASE ULM trajectories and NumPy sidecars. A mobile app that accepts only newly re-exported files would not satisfy the request.
- Preserve all relevant View operations, including selections, property mapping and scientific inspection. Precomputed colors alone do not provide an editable colorscale interface.
- Resolve the two-finger pan/orbit ambiguity described in section 6.
- Treat manual orientation as a platform request, with a truthful fallback where the OS cannot honor it.
- Resolve distribution rights before an App Store release. The repository currently declares **AGPL-3.0-or-later**; removing Python does not remove that license from reused JavaScript.
- Validate performance on physical mobile devices. No source audit can guarantee crash-free operation for arbitrarily large scientific files.

## 2. What the source actually supports today

Paths below are relative to the repository root. Function names are the durable navigation references; line numbers will move during ongoing desktop work.

| Source | Observed implementation | Mobile consequence |
|---|---|---|
| `pyproject.toml` | Python >=3.10; ASE, matscipy, NumPy, SciPy, scikit-image, FastAPI/Uvicorn, matplotlib, Plotly, Pillow and imageio-ffmpeg; optional rhino3dm | The desktop dependency set is much larger than ASE alone. It should not be copied wholesale into a viewer. |
| `desktop/package.json`, `desktop/main.cjs` | Electron desktop wrapper and bundled `runtime/python` | Keep this for desktop. Build a separate mobile host; the desktop bundle is not an iOS/Android package. |
| `v_ase/static/main.js`: `canEditAtoms`, `canTransformSelectedAtoms`, `updateEditingAvailability`, `switchRuntimeMode` | `state.vizOnly` disables physical atom editing, while changing mode invokes `api.updateSessionMode` | View is a permission/workflow mode, not a switch that removes backend dependencies. |
| `v_ase/server.py`: `require_editable`, `save_project`, scalar/force/analysis/field endpoints | Physical edits are gated; many read-only operations still execute Python | Inventory and port these operations rather than substituting mocked API responses. |
| `v_ase/project.py`: `write_project_archive`, `read_project_archive` | `.vase` is ZIP; `v_ase.project.v1`; `manifest.json`, `structure.traj`, labels, metadata, NPZ arrays/results, optional volumes and guest structure | A ZIP/JSON reader alone is insufficient. Existing scientific data is not all browser-ready. |
| `v_ase/export.py`: `export_html_response` | Generates `v_ase.html-view.v1` with scene JSON, frame data, settings, camera/export composition, optional embedded `.vase`, poster and inline renderer modules | There is already a working Python-free rendering format and a compatibility fixture source. |
| `v_ase/static/standalone.html` | Self-contained base64 data/modules, CSP with `connect-src 'none'` | Browser display needs no backend. Native import must extract data, not execute imported modules with bridge privileges. |
| `v_ase/static/standalone.js`: `startStandaloneViewer`, `installViewOnlyPointerControls` | Camera interaction, reset saved view, playback, metadata, optional project extraction; left pointer drag rotates, Shift pans | Does not implement the requested touch mapping, editable settings, atom inspection or full selection/measurement UI. |
| `v_ase/serialization.py`: `atoms_to_json` | Positions, labels, elements, cell/PBC/origin, standard attributes, supported constraint visuals, ASE-derived radii/colors and stored forces | Useful renderer boundary; does **not** include every arbitrary `Atoms.arrays` property or volumetric grid. |
| `v_ase/export.py`: `_html_atom_color_scale_frames`, radius-factor generation | Exports mapped colors and radius factors per frame; also precomputes displacement/polyhedra when enabled | Preserves a saved appearance, but not a complete catalog of data for selecting another scalar later. |
| `v_ase/atom_scalars.py`: `atom_property_snapshot`, `atom_scalar_catalog`, `atom_scalar_values` | Reads arbitrary per-atom arrays and stored calculator results; inspection deliberately does not run a calculator | These semantics can be reproduced locally without a Python calculator, if the data is retained. |
| `v_ase/static/atom_properties.js`: `AtomScalarStore` | Deduplicates requests, guards generations, maintains a 32 MiB scalar cache, but calls `api.fetchAtomScalar*` | Reuse the cache contract with a local data provider. Do not retain HTTP as the only provider. |
| `v_ase/static/radius_mapping.js`, `trajectory.js` | Client-side radius mapping and trajectory interpolation, including periodic geometry handling | Share rather than reimplement inconsistently. |
| `v_ase/static/selection.js`: `ASESelection.pick`, `boxSelect` | Picking and rectangular selection, with periodic-image references | Good foundations for touch; supply touch arbitration and a deliberate selection mode. |
| `v_ase/static/selected_appearance.js`: `SelectedAppearanceEditor` | Selected appearance owns label settings; label splitting and initial adjustment form a transaction | Preserve visual edits, merge behavior and undo in View mode without physical relabeling of the underlying structure. |
| `v_ase/static/renderer.js`: `ASERenderer`, `BlenderTumbleControls` | Three.js rendering, pointer capture for a **single** active navigation pointer, on-demand `requestRender`, instancing, export capture | Reusable rendering core; current controls are not a multi-touch gesture recognizer. |
| `main.js`: `ensureOrientationWidget`, `updateOrientationWidget`, axis-view handling | SVG axes are projected using the inverse camera quaternion | Reuse this orientation math for the moving mobile gizmo. |
| `main.js`: `EDITOR_ROUTES`; `editor_ui.js`: `WORKBENCH_ROUTES` | Style, Build, Analyze, Render routing and contextual sections | Reuse semantic commands, not the whole desktop panel DOM. |
| `editor_commands.js`, `shortcut_capture.js` | Shared platform-aware command registry and desktop/browser shortcut handling | Share command definitions; native mobile key routing and OS-reserved shortcuts still require testing. |
| `main.js`: `applyThemePreference` | Existing system/light/dark UI preference | Preserve semantics. UI theme must not change scientific colors or a saved render background. |

### Evidence and limits of this assessment

The existing `tests/test_html_export.py` includes a browser test that opens an exported file using a `file:` URL, rejects external HTTP(S) requests, checks trajectory interaction and checks a 390 × 844 layout. Other tests cover embedded project recovery, lightweight HTML and per-frame radius factors. These are relevant desktop-browser proofs, **not iOS/Android certification**.

The assessment's targeted test result is recorded in section 12. No mobile implementation, physical-device touch test, store submission or mobile benchmark was performed for this report.

## 3. Python and ASE: what View-only does and does not remove

The mobile runtime should be:

```text
iOS app (WKWebView) / Android app (WebView)
  ├─ packaged v_ase viewer UI + Three.js renderer
  ├─ shared document, selection, appearance and camera state
  ├─ local ZIP / ULM / NPY readers and bounded worker jobs
  └─ native file picker, document handoff, sharing, lifecycle and orientation

Desktop Python/ASE remains responsible for desktop editing and normal exports.
The mobile app does not need a localhost Python server or a terminal process.
```

The WebView uses the device CPU/GPU and native host services. Background work means bounded worker/native jobs inside the application, not a terminal kept open behind it. Pause rendering/playback on suspension; do not run an indefinite background scientific server.

**Python on mobile is technically possible.** CPython documents embedded deployment on [iOS](https://docs.python.org/3.14/using/ios.html) and [Android](https://docs.python.org/3/using/android.html). That does not mean existing desktop wheels work there. Native scientific extensions and codecs need compatible builds, packaging and license review. ASE itself is [LGPL-2.1-or-later](https://docs.ase-lib.org/about.html).

| Approach | Feasibility | Recommendation |
|---|---|---|
| Packaged web viewer + native shell | Reuses renderer, provides offline access and native file integration | **Preferred.** Use Capacitor with small Swift/Kotlin plugins where required; [Capacitor documents this native/web architecture](https://capacitorjs.com/docs). |
| Browser/PWA alone | Useful companion and preview; shares most viewer code | Keep compatible, but it does not guarantee native file associations, orientation control or every keyboard shortcut. |
| Embedded CPython + scientific dependencies | Possible in principle; large platform-specific engineering and licensing surface | Not the baseline for View-only. Evaluate only if a scientifically essential operation cannot reasonably be ported. |
| Pyodide/WASM Python | Possible for compatible packages; introduces runtime/package and memory overhead | Not an automatic escape hatch. [Compiled extensions need WASM-compatible wheels](https://micropip.pyodide.org/en/latest/project/usage.html); do not assume matscipy or all desktop dependencies work. |
| Remote desktop/Python server | Can retain server computations | Optional future integration only; cannot satisfy a standalone offline viewer and introduces privacy/connectivity requirements. |

The major win of View-only is eliminating calculators, relaxation, structural mutation and broad ASE file import from the mandatory mobile runtime. **Selection, appearance, read-only analysis and file decoding still require implementation.**

## 4. File compatibility and persistence

### 4.1 Existing `.vase` files

Implement a validated local reader for the format already written by `project.py`:

- Inspect ZIP directory before extraction; reject duplicate names, traversal, encryption, corrupt/oversized members and nested decompression bombs. Desktop limits include 16 GiB expanded archives and 8 GiB sidecars: these are **not suitable mobile memory budgets**.
- Parse `manifest.json`, `labels.json`, `frame_info.json`, current frame, settings, camera state, `documentMode`, cell origins and frame-specific metadata.
- Read `structure.traj` as **ASE ULM data**, without importing Python objects or executing calculators. The installed ASE reader confirms a binary header, 64-bit frame offsets, JSON records and typed array offsets. Frames can inherit atomic numbers, PBC, masses and constraints from the trajectory header; ignoring this inheritance will corrupt apparently valid trajectories.
- Read `atom_arrays.npz` and `calculator_results.npz`; support the numeric, boolean, complex, byte-string and Unicode array forms the current writer permits. Honor dtype, shape, endianness and NPY memory ordering. Never load pickled objects. Complex values need explicit component/magnitude semantics, not silent conversion to real numbers.
- Read `volumetric/*.npz` with values/cell/origin/PBC and manifest quantities. Decode supported constraints as data; unknown constraints should be retained for round-trip and explicitly identified as unvisualized.
- Preserve optional `commensurate_guest.traj`, its labels, and unused archive members when saving a view copy. No execution of stored calculator configurations.
- Validate bounds before allocation. Handle Int64 identities without silently rounding values beyond JavaScript's safe integer range.
- Large DEFLATE members cannot simply be randomly accessed as uncompressed trajectories. Stream selected members to bounded app-cache files, then read ULM offsets; do not expand the whole archive into JS memory. Browser-only mode needs its own bounded storage strategy and capability checks.

Create conformance fixtures using the **current Python reader as the reference**, not a second implementation of assumptions. Include files from released formats and variable-topology trajectories. Copying ASE reader code versus independently implementing the format has different licensing implications; resolve that before choosing an implementation source.

### 4.2 Future fast viewer payload, without breaking old files

Add an optional, versioned viewer index and chunked typed-array payload to `.vase` **after the legacy reader works**. Keep the existing authoritative archive data and desktop reader compatibility. A proposed namespace is `viewer/manifest.json`, with `v_ase.viewer.v1` metadata and independently compressed frame/property/field chunks.

The viewer payload must include the property catalog and units, topology per frame, label/element distinction, cached vectors, constraint visuals, source precision and scene settings. A JPEG or precolored mesh alone is insufficient. Include source fingerprints so an outdated viewer cache cannot override edited authoritative data. On mismatch, rebuild from original members. Never delete original scientific data to make a file smaller without a separately named export action.

This payload is an optimization, **not a requirement to re-save old projects**. Do not claim that current `.vase` archives already contain it.

### 4.3 HTML behavior

- Continue producing standalone HTML that can display in a capable browser without Python. Hosted HTTPS delivery and local-file delivery need separate mobile tests: a Files/Downloads preview is not necessarily a browser that executes scripts.
- The app's **Open** accepts `.html`/`.htm` explicitly. It extracts the inert `v-ase-scene-data` payload and, if present, `v-ase-project-data`. Validate schemas and bounds; render using the app's trusted, packaged code.
- Never execute the imported `v-ase-*-source` modules, inline scripts, event handlers or remote URLs in a bridge-enabled WebView. Do not inject imported HTML into the app DOM. Use a bounded data extractor that causes no resource fetches.
- With embedded `.vase`, the archive supplies the full scientific property data; the scene/export profile preserves the HTML's saved composition. Keep these purposes distinct.
- With lightweight HTML, show all available scene data and frozen mappings. Missing arbitrary scalar arrays, volumes or derived results **cannot be recovered**. Explain unavailable operations with `Not included in this file`; do not invent zero values or promise identical capabilities to an embedded full project.
- Arbitrary non-v_ase HTML is not a scientific document. Offer to open it externally, rather than executing it inside the app or pretending to recognize it.

### 4.4 OS registration

Register **only `.vase` as the app's owned document type**, using the existing MIME `application/vnd.v-ase.project+zip`. Do not register HTML, JSON, generic ZIP or `*/*` as globally owned/default types.

On Apple platforms use a stable exported UTType, document declaration with Viewer role, and Files/document-picker integration. Apple's [type declaration guidance](https://developer.apple.com/documentation/uniformtypeidentifiers/defining-file-and-data-types-for-your-app) explains how the type becomes visible to Files. Reuse the project's type identifier if already defined; do not create incompatible identifiers independently in mobile and desktop.

On Android use precise document intents and the [Storage Access Framework](https://developer.android.com/training/data-storage/shared/documents-files). A provider can mislabel a custom extension as generic ZIP/octet-stream; explicit in-app Open may need an “All files” fallback with validation **after user selection**. That is not permission to register as the handler of all ZIPs. Test cold/warm launches, cloud-backed files and persistable URI permission loss.

Registration makes the app eligible; it does **not** guarantee that every OS/file provider silently sets it as the default. Respect system chooser and user decisions. Opening HTML in the app must leave the browser's HTML association unchanged.

### 4.5 View-only save contract

Allow saving visual changes: selection snapshots, labels used for display, colors, radius mapping, camera, object visibility and analysis presentation. Keep structural coordinates, elements, cells, constraints and stored results unchanged. Default to a **Save view copy** through the system document picker; only overwrite with explicit user intent and a writable file-provider handle.

For legacy `.vase`, preserve original archive members and patch supported visual metadata; avoid a lossy full rewrite. Preserve the source `documentMode` so a mobile visit does not unexpectedly change a desktop Edit document to View. Mobile itself always opens in View, without an Edit/View question. Save mobile UI preferences separately from document scientific state.

Keep a local, content-fingerprinted viewing session for recents and crash recovery. A fresh import starts from saved camera/frame/settings; a deliberate resume may restore the mobile session. A phone aspect ratio cannot reproduce desktop pixels literally: fit the saved render composition without changing its physical camera/scale. Leave unknown settings intact for round-trip.

## 5. Capability inventory: View-only is more than orbiting a structure

The following is the required parity ledger, not a list of features to silently discard. A staged preview may be narrower, but must say so; the final “all View functions” claim requires closing every applicable row.

| Capability | Source and current dependency | Mobile disposition |
|---|---|---|
| Orbit, pan, zoom, fit, XYZ alignment, orthographic/perspective, flat/3D display | `renderer.js`, camera methods in `main.js` | Reuse math/rendering; replace gesture ownership and adapt controls. |
| Atom/object picking; rectangle/add/remove selection; periodic images | `selection.js`; selected/reference state in `main.js` | Local. Preserve `{index, cellOffset}` references, not just base indices. |
| Intentional distance/angle/torsion | `measurementIntent`, ordered selection and metric methods in `main.js` | Explicit Measure mode with ordered taps. Bulk selection must not accidentally show angle/torsion values. |
| Single-atom label, XYZ, arbitrary stored properties, force values | `atom_property_snapshot`, `AtomScalarStore` | Local property provider; compact selected-atom strip plus expandable properties. No calculator invocation. |
| Per-label/selected color, radius, material, opacity; split/merge; undo | `SelectedAppearanceEditor`, display/view-identity state | Preserve live preview, stable label ownership, inherited settings and atomic undo. No physical element mutation. |
| Scalar colors and property-dependent radius | `atom_scalars.py`, `radius_mapping.js`, color methods in `main.js` | Port catalog/reductions/range/LUT provider. Keep label scopes and captured selected-index scopes independent of later selection. |
| Bonds: label-pair rules, cutoff, appearance, periodic bridges | Renderer bond methods; export bond generation | Shared local computation with spatial indexing. Pair table remains the default; no reintroduced automatic-radii UI. |
| Display supercell, visibility, cell/axes/grid/constraints | Renderer and `state.display` | Local display copies, bounded by instance budget. Physical supercell materialization remains outside View. |
| Trajectory playback, scrubbing, interpolation, range selection | `trajectory.js`; backend frame/scalar access | Local paged provider; frame positions/colors/radii commit together. Missing indices/properties do not reset the mapping configuration. |
| Forces and displacement vectors | Stored forces; `server.py:calculate_displacements`; `trajectory.js` geometry | Local stored data and worker computation; preserve source/reference and PBC rules. |
| Coordination polyhedra | `polyhedra.py:calculate_polyhedra`, JS mesh/display modules | Saved meshes are useful initially; changing rules requires a real local hull/neighbour computation. |
| Pair/bond/angular distributions and CSV | `analysis.py:calculate_rdf`, `neighbors.py`, matplotlib/Plotly display path | Port scientific kernels to workers/WASM and ship local plotting resources. Match partial/skew PBC and normalization against Python. |
| Volumetric fields, planes, isosurfaces, differences, smoothing | `volumetric.py:generate_isosurface`, `generate_volumetric_plane`, `combine_volumetric_datasets` | Grid data plus bounded local kernels needed. Saved surface-only display is not full field parity. Keep units, precision and sampling semantics. |
| Registry maps and periodic-cell-match preview | `registry.py:calculate_registry_map`, `commensurate.py`; read-only endpoints | Real worker ports needed for offline recomputation. Physical apply/relax operations remain excluded. An existing embedded guest can be used; the input restriction excludes opening arbitrary new structure formats. |
| Render Area, camera object, world/viewport lock, light settings | Camera state/methods in `main.js`, `renderer.js` capture | Reuse separate editing-view and output-camera semantics; touch panels must not redefine the camera on opening. |
| PNG/JPEG/WebP/PDF, trajectory GIF/MOV/AVI, selected frame range | GPU capture; `export.py` Pillow/FFmpeg encoding, video frame endpoints | PNG/JPEG feasible locally; other formats need verified encoders/plugins. Native video encoding does not automatically reproduce current MOV/AVI/GIF output. Bounded frame pipeline, progress and cancellation are mandatory. |
| Interactive HTML/share and `.vase` view copies | `export_html_response`, project writer | New trusted client serializer/exporter and native share sheet. Preserve export configuration and optional project recovery. |
| Blender/OBJ/Rhino, POSCAR and other desktop save formats | `export.py`, ASE/rhino3dm | Input-only restriction does not automatically remove these existing View-accessible outputs. Literal parity requires separate serializer/codec work and dependency review; desktop handoff may be offered but must not be called offline parity. |
| Documents, recents, preferences, command search | Workspace/direct-workspace scripts and persistence | Mobile document switcher with suspended inactive renderers. No desktop Electron window/process assumptions. |
| Physical atom G/R/S, insertion, deletion, cell mutation, constraints editing, relaxation | `require_editable`, `canEditAtoms`, Build routes | Intentionally excluded by View-only. Hide the Build editing workflow; retain inspection/display counterparts. |

Do not use the mock `ASEApi.createMockState` as a production mobile backend. Introduce explicit interfaces: `DocumentSource`, `FrameSource`, `PropertySource`, `AnalysisService`, `ExportService`, `HostServices`. Provide existing-server and local-worker adapters. Keep immutable source data separate from view overrides and temporary gesture state.

## 6. Touch specification and the pan/orbit conflict

### The conflict to resolve explicitly

For two contacts `p1`, `p2`, centroid `c = (p1 + p2) / 2` describes translation; distance `d = |p2 - p1|` describes pinch. Two fingers moving equally in opposite directions change distance but produce **no pan vector**. Two fingers moving together normally pan, but the requested default assigns that movement to orbit.

Therefore it is impossible to distinguish pan from orbit using that same unconstrained movement alone. **Recommended resolution: keep the requested default same-direction orbit and provide a visible Pan toggle.** In Pan mode, centroid translation pans and distance change still zooms. This is an explicit additional design decision, not a claim that the original wording has no ambiguity.

### Gesture routing

| Start and action | Result |
|---|---|
| Gizmo tap on X/Y/Z | Run the same axis-alignment command as a keyboard press, including its existing opposite-side behavior on repeat. |
| Gizmo drag | Orbit with captured pointer; continue outside gizmo bounds; show the moving thumb ring. Never select atoms or snap an axis midway. |
| Atom tap | Select the atom/reference and show label, XYZ and stored properties. In Add/Subtract selection modes, apply that operation. |
| Object tap | Select the visible object and its contextual viewer controls. Objects list provides a precise alternative for overlapping geometry. |
| Empty-space tap | Clear selection, unless an explicit additive workflow says otherwise. |
| Empty-space one-finger drag | Box selection. Selection is visual; it never translates physical coordinates. |
| Two-finger translation, default Orbit mode | Orbit after gesture classification and dead zone. |
| Two-finger pinch | Zoom about the gesture anchor. Differential motion owns zoom; do not add unintended orbit from asymmetric pinch drift. |
| Two-finger translation, Pan toggle active | Pan; pinch can zoom simultaneously. Pan has a clear active state and one-tap return to Orbit. |
| Panel drag | Native panel scrolling, not camera input. Horizontal table scrolling stays within its table. |
| Measure mode ordered taps | Add ordered references and deliberate metrics. Provide undo-last-point and clear. |

Use one input controller with explicit states: idle, tap candidate, box-select, gizmo-orbit, two-touch-pending, two-touch-orbit, two-touch-pan/pinch, panel interaction, cancelled. Do not let `BlenderTumbleControls`, selection handlers and the mobile controller all consume the same gesture.

Implementation decisions:

1. Use Pointer Events, an active-pointer map and capture from gesture start. [Pointer Events defines capture and `touch-action` behavior](https://www.w3.org/TR/pointerevents/). Set `touch-action: none` only on canvas/gizmo surfaces; preserve panel scrolling and text selection.
2. Initial tap threshold: at most 8 CSS px displacement and 300 ms, one pointer only. Treat these as tuning constants to test on devices. Once a drag or second pointer occurs, suppress its later synthesized click/axis snap.
3. Delay committing box selection until release. If a second finger arrives, cancel the rectangle preview and transition to two-touch navigation without modifying selection.
4. Determine common versus differential motion over a short stable sample window with hysteresis. Lock orbit versus pan/pinch classification until lift; never oscillate between them on each event. Opposing angular motion should not unexpectedly roll the camera; expose roll separately if needed.
5. When two fingers become one, require all fingers to lift before starting another selection. No trailing single-finger rectangle.
6. On pointer cancellation, app backgrounding, view replacement or OS edge gesture, clear captures/previews/velocity. Never leave a virtual button held down.
7. A contact beginning in the gizmo belongs to it until release, even if crossing panels. A contact beginning in a panel must never enter the canvas controller. Gesture ownership is decided at start.
8. During a gizmo drag, render the thumb ring at the finger location with a tether/clamped base indication. Base and axes stay anchored; axes use the same camera quaternion as the scene. Use drag displacement, not an endless autonomous spin after the finger stops. This gives joystick feedback without sacrificing scientific framing precision.
9. Default gizmo center: lower-left of the usable landscape canvas, clear of safe-area edges, timeline and selection controls. Initial diameter about 120 CSS px; enlarge axis hit regions without making them overlap ambiguously. Store user placement as normalized usable-canvas coordinates **separately for portrait and landscape**. Settings offers left/right presets, size, sensitivity and an explicit “Reposition gizmo” mode so repositioning cannot accidentally orbit.
10. Add a visible Replace/Add/Subtract selection control, Select all, Clear and Invert. A keyboard is not required for any selection workflow. Large-scene picking needs spatial acceleration; the current fallback projected-atom picking skips groups above 2,000 atoms and must not leave touch users unable to pick small glyphs.

## 7. Mobile information architecture and visual behavior

Keep the v_ase wordmark, colors and restrained controls. Do not squeeze the desktop inspector, menu bar and every tab into a phone.

**Persistent chrome:** compact document title/Open, document switcher, settings, Objects, camera/Render Area state, selection count and a collapsible trajectory strip. Floating gizmo and Pan toggle remain reachable without covering the selected structure. Use text for scientific settings; icons are for navigation and well-established actions, with accessible names and press-and-hold explanations.

**Properties navigation:** `Inspect`, `Style`, `Analyze`, `Render`. The read-only Cell/replication controls belong under Style. Build does not appear as a disabled wall of controls. Match preview remains discoverable under Analyze when source data exists.

- **Inspect:** selected atom information, ordered measurement, selected appearance, selection operations. Show compact label/XYZ/properties, not a permanent large note over the canvas.
- **Style:** Atoms, Bonds, Cell, Polyhedra, View & guides. Under Atoms use distinct blocks for global size, property radius, property color, per-label table, selected-label appearance. Keep the property source/range/target/colormap hierarchy explicit. Per-label rows remain rows with horizontal scrolling, not four lines per label.
- **Analyze:** Distributions, displacement, stored forces, fields, registry, match preview. Each expensive operation has loading/progress/cancel and a source/frame indicator.
- **Render:** renderer, Render Area/camera, image, video/GIF, HTML/share, additional outputs. Camera visibility and viewport-lock toggles retain their desktop meaning. Disabling the camera object releases viewport lock. No deprecated “hide render area” text button reappears.

Landscape uses a right-side overlay inspector, roughly 320–400 CSS px subject to remaining canvas width. Portrait uses a bottom sheet with collapsed handle/selection summary, medium and expanded detents. On a short landscape phone, use a compact sheet or narrower inspector instead of leaving an unusable canvas. Actual window dimensions, not a device name, select the layout.

Opening/collapsing panels must not reset the camera, resize the WebGL drawing surface gratuitously, shift scientific coordinates, or change output framing. Use safe content bounds for first fit/camera recall. Do not repeatedly recenter a user's existing pan. Orientation changes update layout and projection coherently while preserving world camera state, selected frame and rendered composition.

Detail requirements:

- Minimum 44 pt Apple / 48 dp Android hit-target intent; verify actual native/WebView scaling. Selected state uses aligned shape, contrast and accessible state, not color alone.
- Clear section title above its controls; subsection boundaries and table headers remain attached to their data. Sticky headers sit at the actual scroll-container top, without a blank strip or a row showing above them.
- A property value and its unit form one layout component. Long names wrap/truncate predictably; values never collide with units or sliders. Numeric editors use suitable decimal input modes, validation and Done/Next actions; allow negatives/scientific notation where scientifically valid.
- Keep the focused field visible when the software keyboard appears. Use native keyboard insets/visual viewport dimensions; do not interpret keyboard resize as an orientation change or refit the structure.
- Scroll panels independently; do not globally call `preventDefault()` on all touch movement. Bottom-sheet movement starts on the handle, not while editing a number or scrolling a table.
- Menus, search, sheets and popovers have one consistent dismissal/focus policy. Escape/Back dismisses the topmost transient interaction first. Respect reduced-motion and screen-reader settings; provide accessible button alternatives to gesture-only functions.
- Theme preference defaults to **System** and follows live OS changes. Light/Dark overrides persist at app level. Scientific element colors, field colormaps and saved output background remain document settings.

## 8. Orientation, tablets and external input

### Orientation

Default: allow both orientations and follow the window orientation supplied by the OS. Do not force landscape on launch; “landscape default” applies to control placement/design, not overriding a user's rotation lock.

Clarification following the user's YouTube example: **a user-initiated landscape/fullscreen button is feasible and is the intended phone interaction.** System sensor-based auto-rotation lock, an app's explicit interface-orientation request, and fullscreen presentation are distinct. The earlier warning must not be read as “portrait rotation lock always prevents an app from entering landscape.” The app does not need to change the device's global rotation-lock setting to request a landscape interface.

Provide a `Landscape fullscreen` action and an exit action. On entry, expand the viewer and request landscape through the native host; preserve the scene, camera, selection and frame. On exit, restore the previous presentation and system-following orientation policy. Apple provides [`UIWindowScene.requestGeometryUpdate`](https://developer.apple.com/documentation/uikit/uiwindowscene/requestgeometryupdate(_:errorhandler:)); Android provides [`Activity.setRequestedOrientation`](https://developer.android.com/develop/adaptive-apps/cookbook/orientation-restriction). Supported orientation declarations and the active native controller/window must be configured coherently. Test this action with phone rotation lock both enabled and disabled. This is a custom scientific canvas, so video-player fullscreen behavior cannot simply be assumed to carry over without native integration.

If the current window/platform cannot honor the landscape request, fullscreen presentation should still work within the available window, with a concise explanation of the orientation limitation. Do not silently rotate the entire WebView with CSS and pretend native pickers, keyboard, accessibility and touch coordinates also rotated correctly.

The exceptions concern platform/window constraints, not a blanket ban caused by a phone's auto-rotation toggle. The [Capacitor orientation documentation](https://capacitorjs.com/docs/apis/screen-orientation) notes iPad multitasking restrictions and Android large-screen behavior. On newer iPadOS, also consult Apple's [migration guidance for orientation/window behavior](https://developer.apple.com/documentation/technotes/tn3192-migrating-your-app-from-the-deprecated-uirequiresfullscreen-key); do not assume an older plugin's fullscreen guidance covers every current mode. [Android's adaptive-app guidance](https://developer.android.com/develop/adaptive-apps/guides/app-orientation-aspect-ratio-resizability) describes ignored orientation restrictions on large screens; Android 17 removes the earlier temporary opt-out for targeted apps. Preserve tablet multitasking and adapt to its window. Browser HTML has separate fullscreen/orientation capabilities and must not inherit the native-app guarantee.

### Tablets, foldables and mouse/keyboard

- Support iPad split-window/Stage Manager and Android split-screen/foldable window changes; do not assume physical device orientation equals usable window aspect ratio.
- Use event `pointerType`, actual window size and hover/fine-pointer capabilities. A tablet can receive touch, pencil, mouse and keyboard in the same session. Do not choose interaction mode once from user-agent text.
- Mouse behavior reuses desktop selection, Shift-addition and middle/right-button navigation. Touch behavior retains the mobile mapping. A connected mouse should not make touch controls unusable; provide a compact-tools preference if desired.
- Route the same semantic commands from DOM and native keyboard hooks, with a guard against double execution. Apple hardware keyboards use Command; Android uses Control. X/Y/Z alignment, arrows, fit, selection, ordered measurement and available panel navigation must work.
- Reuse `editor_commands.js` mappings: Primary+Shift+B (supercell), Primary+Shift+P (atoms), Primary+B (bonds), Primary+Shift+A (renderer), Primary+O (open), Primary+S/Shift+S (save/save copy), Primary+W (close document), Primary+N (new empty viewer document). Primary+E must show the read-only cell information/explanation rather than invoke a physical edit.
- Keep atom G/R/S editing disabled in View. If a camera/field visual object supports G/R/S in the desktop viewer, preserve that object-specific command and provide equivalent touch controls. Keyboard support does not turn the mobile product into an editor.
- Text fields own select-all, arrows, Tab, copy/paste and IME composition. Unmodified X/Y/Z must never fire while typing. Primary+A and the user's Control+A numeric-field expectation should select the whole field where applicable, not the scene.
- OS-reserved combinations such as application switching cannot all be intercepted. Document and test exact delivered combinations; do not promise that fullscreen or a native shell makes every desktop shortcut available. iOS lifecycle does not require force-quitting the process when the final document closes: return to the library/empty screen.

## 9. Performance and reliability design

Retain the renderer's on-demand scheduling. `ASERenderer.requestRender()` already coalesces animation frames; `animate()` is not itself a perpetual animation loop. Preserve this advantage. `standalone.js` currently uses whole-frame JSON and `setInterval` playback; that is not the final mobile streaming architecture.

Required controls:

1. Render only for input, animation or changed data. Pause playback/worker jobs on backgrounding and screen lock; cancel queued frames. Never keep the device awake indefinitely by default.
2. Decode frames/properties in workers with a latest-request-wins token. Batch position, topology, labels, colors, radii and vectors into **one** committed frame. A stale request must not flash base radii or clear a mapping at the last frame.
3. Keep a small frame ring buffer and bounded LRU property/mesh caches. Preserve float64 scientific values when required; derive float32 GPU buffers explicitly. Do not duplicate the full trajectory in base64, a string, arrays and GPU memory at once.
4. Use instanced atoms/bonds, geometry/material reuse, spatially indexed picking/neighbours and bounded mesh complexity. Reuse renderer buffers when topology is unchanged. Dispose geometries, textures and object URLs on eviction/document close.
5. Start interactive DPR at 1, with adaptive quality; increase only after measurement. Reduce quality during dragging/thermal pressure, restore on idle. Saved scientific data and requested export dimensions must not change with preview quality.
6. Preflight atom × replication count, bonds, grid cells, isosurface triangles, output pixels and estimated decoded bytes. Show a capacity message **before** allocating an unsafe request. Offer fewer replicas, a field resolution preview or selected-frame playback; do not silently discard atoms or lower analytical precision.
7. Bounded image/video export pipeline: capture → encode → release frame; no array of all full-resolution PNGs. Progress/cancel, correct frame range, GIF loop choice and exact Render Area dimensions remain required.
8. Recover from WebGL context loss and native WebView content-process termination using a persisted document/session reference. Recovery cannot prevent every OS kill; it must avoid data loss and restore a usable scene.
9. Suspend inactive documents; do not allocate one active GPU context per hidden tab. Limit parallel analysis workers to avoid saturating all cores during interaction.
10. Busy indication should appear quickly for an operation that does not finish immediately; retain previous valid scene until replacement is ready. Cancellation is a normal outcome, not an alarming “frame failed” toast.

Proposed validation targets, **not measured guarantees**:

| Scenario | Initial acceptance target |
|---|---|
| Small scene, 1,000 atoms | Smooth interactive orbit on the minimum supported physical phone; aim for 60 fps, with 30 fps as the low-power fallback |
| Medium scene, 10,000 atoms with bonds | Sustained responsive input at adaptive quality; measure p95 frame times and pick latency |
| 100,000-atom / large-volume stress case | Preflight, degraded preview or clear refusal before dangerous allocation; no unconditional promise of full quality |
| Idle open document | No continuous rendering/playback/analysis work; inspect energy traces rather than an arbitrary CPU-percent assertion |
| Rapid 100-frame scrubbing and variable atom counts | Latest frame wins; no stale-catalog errors, radius flashes, mapping resets or unbounded memory growth |
| Repeated open/close/background cycle | Stable memory after warmup and cache eviction; successful session recovery after simulated context/process loss |
| 15–30 minute playback/analysis session | Record thermals, memory, battery/energy and frame times on physical iOS and Android devices |

Memory admission limits must come from measured device classes, not a fabricated universal iOS limit. A provisional internal cache budget can be conservative, but an OS may still terminate a process under system-wide pressure.

## 10. Licenses, copyright and store distribution

### A release gate, not an automatic prohibition

`pyproject.toml`, `desktop/package.json` and `LICENSE` declare AGPL-3.0-or-later. The reused renderer/controller code remains covered even if Python is removed. The FSF documents an [App Store/GPL additional-restrictions conflict](https://www.fsf.org/blogs/licensing/more-about-the-app-store-gpl-enforcement); that account is historical, so it is a warning to review **current agreements**, not a substitute for a current legal conclusion. Apple's [current Developer Program agreement](https://developer.apple.com/support/terms/apple-developer-program-license-agreement/) must be part of that review.

Before committing to worldwide App Store distribution:

- Establish who holds rights to all reused code. If all necessary rights are held, evaluate a separate App Store-compatible license/additional permission for the mobile distribution while retaining the open-source desktop license. Do not simply relabel contributor or dependency code.
- Audit ASE-derived readers, numeric tables, colormaps, scientific kernels, codecs and any WASM library independently. Three.js has an existing MIT notice at `v_ase/static/vendor/THREE_LICENSE`; include it. A data-format implementation is not the same thing as shipping ASE, and code copied from ASE still needs its own compliance decision.
- Record provenance and rights for the wordmark, castle icon, fonts, SVG icons, screenshots and bundled scientific examples. A user-supplied image or AI edit is not by itself proof of worldwide distribution rights; avoid protected character adaptations/trademarks without clearance. The castle/Pinocchio artwork needs an actual provenance record rather than an assumption based on its filename.
- Follow design principles from Blender, video apps and professional editors; do not copy their artwork, branded icons or proprietary assets.
- Ship third-party notices and corresponding source/offers wherever required. Review export codecs before bundling; desktop FFmpeg packaging is not automatically the right mobile licensing choice.

This audit cannot certify worldwide copyright/legal compliance. Rights verification and, where necessary, legal review are explicit prerequisites, not an assertion that release is impossible.

### Store packaging and privacy

The proposed app is an offline scientific document viewer with native file access and substantial interaction, not a website shortcut. Bundle the executable viewer code and use imported files as validated data. Apple's [review guidelines](https://developer.apple.com/app-store/review/guidelines/) require meaningful app utility, appropriate code/data handling, accurate metadata and rights to distributed content; approval is not guaranteed by using a particular framework.

Use a separate mobile bundle/package identity. Existing macOS Developer ID signing/notarization does not produce an iOS App Store build. Use Apple Distribution/provisioning and App Store Connect/TestFlight for iOS, and a signed Android App Bundle/Play signing workflow for Google Play. Preserve desktop, PyPI and Jupyter distribution independently.

Start without accounts, ads, analytics or automatic document uploads. User files stay local unless the user invokes a share action. Provide a privacy policy and accurate store declarations based on the actual SDK behavior; local-only design is not permission to skip declarations. Native picker/share operations should request only the access they need. Prepare support contact, age rating, licensing notices and sample files for review.

Worldwide availability is a distribution choice, not a guarantee. Apple documents [country/region availability constraints](https://developer.apple.com/help/app-store-connect/manage-your-apps-availability/manage-availability-for-your-app-on-the-app-store) and [EU trader-status requirements](https://developer.apple.com/help/app-store-connect/manage-compliance-information/manage-european-union-digital-services-act-trader-requirements). Check current Apple/Google requirements and applicable territories before submission rather than promising every country in advance.

## 11. Recommended implementation sequence

These stages are recommendations for a future implementation request; this report does not start them.

| Stage | Concrete work | Exit condition |
|---|---|---|
| 0. Scope and rights | Close licensing/provenance questions; approve the explicit Pan-mode resolution and orientation fallback; freeze the View parity ledger | No hidden assumption that analysis/exports can disappear or that AGPL is automatically store-cleared |
| 1. Shared viewer core | Extract document/view state and rendering/selection/camera commands from `main.js`; add provider interfaces; retain desktop adapters | Desktop behavior and saved projects pass existing regressions; mobile has no accidental `ASEApi`/WebSocket dependency |
| 2. Local document readers | Implement ZIP/ULM/NPY + bounded extraction and trusted HTML data import; preserve legacy content | Old `.vase`, embedded HTML and lightweight HTML fixtures open without Python/network; malformed files fail safely |
| 3. Native shell spike | Capacitor iOS/Android projects, Files/SAF/share, lifecycle, context recovery, orientation request, hardware input | Real iPhone/iPad/Android phone/tablet load the same fixture offline; only `.vase` is registered |
| 4. Mobile interaction/UI | Pointer state machine, floating axes/joystick, explicit selection/Pan/Measure, portrait sheet/landscape inspector, keyboard insets/theme | Gesture ownership and cancellation matrix passes; no overlap, involuntary camera shift or drag-axis snap |
| 5. Local View functions | Properties/radius/colors/bonds/vectors/trajectory providers, scientific worker ports, analysis/volume/parity work | Every applicable section 5 row has an implementation and numerical/browser regression; frozen-only previews are not mislabeled |
| 6. Persistence and output | Lossless view-copy save, native sharing, exact image/video/GIF output, required serializer/codec work | Round-trip preserves underlying structure and saved appearance; no silent format loss |
| 7. Optimization and device QA | Admission control, adaptive rendering, cache eviction, thermal/battery/large-file tests and accessibility | Published device/workload support envelope, successful interruption/recovery testing |
| 8. Distribution | Complete notices/privacy/docs, TestFlight and Play testing, release notes, signing and review | Store-ready evidence; desktop regression gates and repository release contract met for any shared-code release |

An early HTML-based prototype can prove the touch design quickly, but it must be called a prototype. The hardest work is legacy scientific file compatibility, complete offline View parity and mobile performance—not creating the app icon or WebView shell. Do not estimate a fixed release date from this audit alone; stages 2, 3 and scientific-kernel benchmarks determine the credible schedule.

Suggested future code boundaries (new modules, not files that already exist): `viewer_core/`, `viewer_io/`, `viewer_workers/`, `mobile/`. Existing `renderer.js`, `selection.js`, `radius_mapping.js`, `trajectory.js`, `editor_commands.js` and selected-appearance semantics should remain shared where practical. Avoid another 30,000-line mobile copy of `main.js`.

## 12. Validation plan and current evidence

### Checks run for this assessment

Four existing tests were selected from `tests/test_html_export.py`:

```sh
.venv/bin/python -m pytest -q -rs tests/test_html_export.py \
  -k 'self_contained_and_embeds_lossless or exported_html_opens_offline_as_view_only_interactive_trajectory or lightweight_html_opens_offline_without_project_download or offline_html_uses_frame_specific_radius_factors'
```

**Result: 4 passed, 8 deselected in 8.83 seconds.** This confirms the current self-contained export/recovery path, desktop Chromium offline interaction, lightweight HTML and per-frame radius behavior covered by these tests.

Initial sandbox execution produced one pass and three skips because Chromium's macOS process registration was denied. The test's skip message labels all launch failures as “not installed”; the log actually showed `bootstrap_check_in ... Permission denied`. The four-pass result above is from rerunning the same targeted checks outside that launch restriction. It is not a physical-mobile result, and no new screenshot inspection was performed in this assessment.

### Required mobile acceptance matrix

- **File fidelity:** released `.vase` versions, inherited ULM headers, fp32/fp64, endianness, custom arrays, Unicode labels, complex/vector properties, constraints, origin, partial/skew PBC, volumes, guest structure, changing atom counts/elements, nonzero saved frame and both saved desktop modes. Compare to Python reference output. Do not instantiate calculators to inspect results.
- **HTML:** embedded and nonembedded exports; saved export aspect; poster/interactive transition; browser offline test; native safe import; script/URL injection attempts; oversized base64; missing-data explanations. A lightweight export must not falsely expose absent properties.
- **Gestures:** gizmo starts/ends outside bounds; dragged-over axes never snap; short tap snaps; second finger cancels selection; lift-order permutations; gesture crossing panel boundary; OS edge/cancel; empty-space rectangle; add/remove/invert; overlapping objects; measurements after bulk selection.
- **Appearance/trajectory:** selected scope remains fixed after selection changes; label split/merge/undo; per-label table agrees with selected appearance; immediate material/color/opacity/radius updates; no frame flash; missing indices ignored per frame without clearing configuration; rapid scrub/reverse playback; topology-change interpolation policy matches desktop.
- **Camera/render:** preserve saved view and Render Area; independent world camera and viewport lock; camera hide releases lock; XYZ snapping updates frame in the same draw; constraints/object visibility obeyed; output camera G/R/S where supported; image/video share identical crop and dimensions.
- **UI:** smallest supported phone in both orientations; notches/home indicator; virtual keyboard; expanded labels/large text; portrait/landscape switch while typing; right/bottom panel transitions; table scrolling/sticky headers; no blank header strips, clipped units, hidden controls or canvas recenter flicker.
- **Input:** touch, Apple Pencil/stylus, mouse, trackpad, hardware keyboard, combinations/hot-plug; X/Y/Z, selection shortcuts, panel shortcuts, native file commands; Control/Command+A in numeric fields; Tab/Shift+Tab; IME; Escape/Android Back; no duplicate native/DOM command.
- **Runtime:** airplane mode after installation, background/foreground, rotation, split-window, interrupted cloud-file download, permission revoked, low storage, low memory, context loss, OS process recreation, 50 repeated document opens/closes, oversized archive rejection and cancelled export cleanup.
- **Scientific parity:** RDF/BDF/ADF, exact minimum-image semantics, vectors, field planes/isosurfaces/differences, polyhedra and read-only registry/match functions compared numerically with existing Python tests; worker cancellation cannot publish a stale result.
- **Distribution:** `.vase` association only; HTML still opens in browser; generic JSON/ZIP untouched; signed app works without development tools/Python; bundled notices and sample files; no unexpected network requests or document uploads.

Reuse pytest scientific reference fixtures (`test_html_export.py`, `test_project_consistency.py`, `test_analysis_field_audit.py`, `test_rdf_analysis.py`, `test_registry_analysis.py`, property/frame and camera browser tests). Add pure JS/worker tests and Playwright tests for the shared viewer. Playwright mobile emulation is useful for layout and event sequences but does not replace physical WebKit/Android WebView, multi-touch, orientation, keyboard and power tests. Use native UI automation plus manual real-device checks for those gaps.

For eventual shared-code releases, follow `AGENTS.md` and `docs/release_checklist.md`: synchronize README, canonical skill/references and rendered examples as applicable; run documented AI workflows and full tests; build/check Python artifacts; preserve desktop/Jupyter behavior. Add a separate mobile release checklist and native CI jobs. A mobile-only package is not published to PyPI as if it were the Python desktop product.

## 13. Final feasibility classification

| Request | Assessment |
|---|---|
| Mobile viewer without user-installed Python/ASE | **Yes**, with a local viewer/data architecture |
| Open existing `.vase` offline | **Yes, substantial new reader work**; current HTML viewer does not already do it |
| Browser HTML and explicit in-app HTML open | **Yes**, with v_ase data extraction; generic HTML stays external |
| Full current desktop View functionality | **Technically achievable in principle, not currently present**; scientific ports/exports and data availability are the main cost |
| Floating joystick gizmo, axis tap, bulk selection | **Yes**, with explicit gesture ownership |
| Same-direction two-finger orbit plus pan | **Yes with a disambiguating Pan control**; indistinguishable gestures cannot do both simultaneously by inference |
| Portrait/landscape/tablet adaptive panels | **Yes** |
| YouTube-style landscape/fullscreen button on native phones | **Yes**, through explicit native presentation/orientation control; verify with auto-rotation lock on and off |
| Identical forced orientation in every tablet/window/browser mode | **Not universally guaranteeable**; retain fullscreen/adaptive layout when orientation cannot change |
| System theme and hardware keyboard/mouse | **Yes**, except OS-reserved commands; View restrictions still apply |
| All View functionality from every lightweight HTML | **No if the file omits the necessary data**; expose what exists or use an embedded full project |
| Worldwide App Store/Play release | **Conditional** on rights, current policies, region requirements and review |
| Unlimited structures with guaranteed no crash/overuse | **No**; bounded capacity, measured performance and recovery are required |

Recommended next action after this assessment: authorize a shared-viewer/native-file proof of concept with one legacy `.vase`, one embedded HTML, one lightweight HTML and one variable-topology property trajectory. That validates the highest-risk architecture before committing the complete mobile UI and scientific parity implementation.
