# v_ase viewer — iOS and Android developer handoff

**Audience:** mobile product designers, iOS/Android engineers, rendering engineers and QA engineers who have not developed v_ase.

**Date:** 28 September 2026. **Status:** requirements and implementation contract; the mobile app has not been built.

**Product name:** `v_ase viewer`. **Interface language:** English. **Platforms:** iPhone, iPad, Android phones and Android tablets, including Samsung Galaxy Tab.

This document is intended to be handed directly to a mobile team. It explains the product, the owner's requirements and repeated quality concerns, the scientific behavior that must survive the port, and how to determine whether an implementation is acceptable. It is not permission to simplify the product into a rotating-molecule demo.

The companion [feasibility assessment](v_ase_mobile_viewer_feasibility.md) provides the dependency investigation and platform sources. This handoff is self-contained for product behavior. Source paths below are relative to the repository root; names marked **proposed** are not existing modules.

## Contents

1. [How to read this contract](#1-how-to-read-this-contract)
2. [What v_ase is](#2-what-v_ase-is)
3. [What the owner has repeatedly emphasized](#3-what-the-owner-has-repeatedly-emphasized)
4. [Product scope and capability coverage](#4-product-scope-and-capability-coverage)
5. [Scientific data and appearance rules](#5-scientific-data-and-appearance-rules)
6. [Touch, gizmo and input behavior](#6-touch-gizmo-and-input-behavior)
7. [Layout, navigation and control quality](#7-layout-navigation-and-control-quality)
8. [Camera and Render Area contract](#8-camera-and-render-area-contract)
9. [Files, document lifecycle and saving](#9-files-document-lifecycle-and-saving)
10. [Architecture and integration boundaries](#10-architecture-and-integration-boundaries)
11. [Performance, interruption and error handling](#11-performance-interruption-and-error-handling)
12. [Developer delivery stages](#12-developer-delivery-stages)
13. [Acceptance scenarios and test evidence](#13-acceptance-scenarios-and-test-evidence)
14. [Distribution and handover checklist](#14-distribution-and-handover-checklist)

## 1. How to read this contract

Use these distinctions during planning and review:

- **Owner requirement:** explicitly requested behavior, including the most recent clarification. Do not remove it to reduce development effort without a scope decision from the owner.
- **Existing reference behavior:** behavior found in the current v_ase source. It is useful for compatibility, but is not proof that every implementation detail is already correct.
- **Proposed mobile design:** a concrete recommendation where the owner specified an outcome rather than an exact mechanism. It may be refined through prototype review while retaining the requirement.
- **Release gate:** something that must be demonstrated or cleared before a production claim, such as file fidelity, device performance or distribution rights.

Earlier discussions include desktop editing, desktop installation and several superseded camera/UI designs. **Do not implement every historical sentence literally.** Later requirements take precedence: for example, the camera uses a visibility icon plus an optional **Lock camera to viewport** toggle, not a permanent World/Viewport radio group and a separate Hide render area button.

The mobile scope is View-only. Physical atom editing and relaxation requested for the desktop product are not mobile requirements. The quality principles learned during that desktop work do apply to mobile.

Historical failures listed here are regression examples reported by the owner. They are not an assertion that all remain in the current desktop working tree. The local reference is version 0.4.7 plus pending fixes, based on commit `b0640038aadde01628e1ac42c337a03d3e6cf9c9`. Pin the exact shared-code revision used by the mobile build; do not assume that a release number alone identifies the reference behavior.

**Current assessment evidence:** four existing offline HTML tests passed in desktop Chromium during the feasibility investigation. This is not a physical iOS/Android certification or a complete audit of all desktop functionality. Application code is not modified by this handoff.

## 2. What v_ase is

v_ase is a scientific editor/viewer for atomic structures, trajectories and scalar fields. Scientists use it to inspect geometry and stored results, select meaningful atom groups, make visual distinctions, and prepare accurate images or animations. The atomic structure is the main content; panels support the work.

The desktop product uses Python/ASE for scientific data and operations, JavaScript/Three.js for interactive rendering, and Electron for the native desktop shell. It can also run through a browser/Jupyter workflow. A standalone HTML export already displays a saved scene without Python, but does not contain the complete desktop View interface.

The mobile product should be an offline-capable, native-installed scientific viewer. Users must not need a terminal, Python installation, ASE installation, account, cloud conversion or an always-on desktop computer merely to open their supported documents.

### 2.1 Vocabulary for non-atomistic developers

| Term | Meaning and implementation consequence |
|---|---|
| Atom | One scientific record with a position and chemical identity; the sphere drawn for it is only a visual glyph. Hiding the sphere does not remove the atom. |
| Element / TYPE | Chemical identity such as H, C, O or Cu. It is scientific data. View-only must not change it. |
| Label / LABEL | A visual group such as `Cu_surface` or `O_2`. Multiple labels can describe atoms of the same element. A label must never be parsed as a request to change chemistry. |
| Base index | The atom's index in a source frame. Existing property-target behavior follows indices across frames, including frames with different atom counts/elements. |
| Trajectory / frame | An ordered sequence of structures. The next frame can have different coordinates, cell, elements, properties or even atom count. It is not necessarily a fixed-topology mesh animation. |
| Å / angstrom | A unit of length, equal to 10⁻¹⁰ m. Use the document's units. Do not confuse an Å value with screen pixels or an arbitrary slider unit. |
| Cell | The three lattice vectors and their origin describing the structure's simulation cell. It can be skew, not merely an axis-aligned box. |
| PBC | Periodic boundary conditions, independently enabled along each cell direction. Some structures are periodic in only one or two directions. |
| Display supercell / replica | A repeated visual image of the source cell. Select it by base index **and cell offset**; selecting one image is not always the same as selecting every copy. |
| MIC | Minimum-image convention: a periodic geometric distance/direction can differ from the directly drawn separation. Preserve the scientific distinction in measurement and analysis. |
| Bond | A visual connection generated by configured rules or explicit atom pairs. Bond cutoff is a distance threshold; bond thickness is an appearance value. Neither is an atom radius. |
| Scalar property | One numeric value per atom, such as charge, existence/occupancy, or force magnitude. The source, units, component and frame matter. |
| Vector property | Several components per atom, such as a force. Display a chosen component or norm explicitly rather than silently treating the vector as a scalar. |
| Constraint / FixAtoms | Scientific restrictions on physical editing. The viewer can show/hide their marks, but a GUI selection or a saved colorscale target is not a constraint. |
| Volumetric field | Values sampled on a 3D grid, such as density; an isosurface/plane is a visualization derived from those values. |
| Editing view / viewport camera | The viewpoint used to inspect the scene, even in View-only mode. The word “editing” here does not grant atom-edit permission. |
| Output camera / Render Area | The saved camera and rectangle defining an exported image/movie. It must remain independent of ordinary inspection unless explicitly locked to the viewport. |
| View-only | No physical structure mutation. It still permits selection, measurement, visual styling, viewing data, supported analyses, camera adjustment, and saving/exporting the resulting view. |

### 2.2 The four kinds of state

Keep these distinct in the code and UI:

1. **Scientific source:** coordinates, elements, cell/PBC/origin, source labels, constraints, stored properties, fields, frame order. Immutable in mobile View-only.
2. **Document presentation:** visual label overrides, appearance, captured mapping targets, selected frame, object visibility, output camera, render/export settings and view history. Editable and saveable.
3. **Transient interaction:** touch contacts, selection rectangle, transform preview, pending numeric text, open menu, busy state. Never serialize as if it were a confirmed scientific result.
4. **App preferences:** system/light/dark choice, gizmo location/size, handedness, tool density and recent files. Do not overwrite these merely by opening another person's project.

## 3. What the owner has repeatedly emphasized

These are central product priorities, not optional finishing touches.

| Owner emphasis | Required implementation behavior | Previously observed failure to prevent |
|---|---|---|
| A professional scientific canvas, not a dashboard | Structure remains visually dominant. Use restrained chrome, precise typography and familiar editing/viewing affordances. | Panels appeared to become the main product; excessive text made controls difficult to recognize. |
| Organize complexity; do not hide capabilities in drawers | Frequent controls are visible or directly reachable; hierarchy explains what each setting affects. | Redesigns put more functions into containers without improving discoverability. |
| Consistency with the actual v_ase identity | Use the established wordmark and approved icon assets. | The top-left logo was replaced without approval. |
| Tool hierarchy must match purpose | Selection and measurement are interaction modes; Move/Rotate/Scale act on a valid selected object; orbit is navigation. | A row of unrelated English tool names behaved as if all were interchangeable toggles. |
| Controls need robust exclusive/independent state | Use one state model; changing mutually exclusive tools clears/cancels the old preview. Independent visibility settings remain independent. | Multiple tools appeared active, or a camera-view action silently changed the camera-lock mode. |
| A panel must not shove the scene sideways | Overlay panels and preserve camera state. Fit only on explicit actions or initial load. | Opening the right panel repeatedly displaced the ribbon/structure. |
| Immediate, truthful feedback | Valid appearance edits update the scene immediately; longer work shows progress or loading. | Colors/material/opacity did not update, and property dropdowns initially looked empty. |
| No flicker, clipping or occlusion artifacts | Selection changes and camera adjustments must not blank the canvas or rebuild unrelated surfaces unnecessarily. | Deselection flashed the screen; atoms were masked white or reduced to outlines; grid disappeared. |
| Clear settings hierarchy | Navigation/bookmarks appear before the active section title; sections and subsections are visually distinct. | “Atoms” appeared above the navigation for the whole workspace; unrelated settings looked like peers. |
| Purposeful icon use | Icons identify navigation and familiar actions; scientific controls retain labels/units. Distinct actions use distinct, understandable icons. | Reused icons for Transform and Cell matrix; a Relax icon did not communicate its action; icons were inserted indiscriminately. |
| Compact tables for repeated scientific entities | One logical row per label/pair, pinned identifying column, horizontal scroll when needed. | One label occupied three or four lines, making ten labels unreadable. |
| Fine layout details count as defects | Headers flush to table top; no clipped units, overlapping controls, miscentered selection markers or inconsistent fonts. | Rows showed above a displaced sticky header; units escaped the input layout. |
| Fast numeric workflows | Select-all replaces the entire value; Tab/Next goes to the next related value; shortcut-focused numbers are selected. | Ctrl+A changed only one digit; Tab stopped at an unrelated checkbox; entering 2 changed 1 to 12. |
| Visual targets remain stable | Captured colorscale/radius indices must not track later GUI selection or disappear on short frames. | Changing the selection changed colors; the final shorter frame cleared mappings. |
| Camera behavior must be understandable | Separate camera visibility, viewport lock, camera selection, viewing the camera and changing its pose. | Several similarly named buttons had unclear side effects; enabling follow changed the carefully set framing. |
| Exported result must match the configured result | Image, movie and HTML use the same Render Area and effective atom appearance. | Video failed with mismatched PNG dimensions; some paths ignored property radii. |
| File associations must be conservative | Own `.vase` only. HTML remains a browser file; JSON is not a structure association. | Settings/generic extensions were made to look like v_ase documents. |
| Preserve work and file identity | Save reuses supported targets/format/profile; Save As is separate; failed writes/cancel do not lose work. | Save could behave like a new export and change format/settings unexpectedly. |
| Commercial-app interaction details matter | Menus, search, dismissal, focus, selection, resizing and loading are coherent as a system. | Opening File left Search open; moving to another desktop menu did not switch the menu. |
| Show evidence, not “it should work” | Visually inspect outputs and exercise actual native inputs on real devices. | Successful API/test responses were mistaken for a finished user experience. |

The phrase “no overlaps/no flicker” means these are acceptance failures in supported scenarios. It does not justify promising unlimited data sizes or that the OS can never terminate the app.

## 4. Product scope and capability coverage

### 4.1 Launch and basic scope

- Open `.vase` and v_ase-exported `.html`/`.htm`. Do not silently add raw `.xyz`, `.extxyz`, `.vasp`, `.cif`, arbitrary JSON or a general browser as mobile input types. The desktop can read more formats; that is a separate product capability.
- Register `.vase` as the owned document type. Explicit in-app HTML import must work without claiming the system HTML association.
- Open into View-only automatically. No “Open in View or Edit?” question.
- An empty app offers **Open file**, recent documents and an optional bundled example. It must not ask to “Replace this tab” when there is no current work.
- When a document is already open, a newly opened project becomes another internal document by default. Keep its complete settings and source identity. A mobile document switcher may replace a crowded desktop tab strip.
- Work offline after installation for all supported local viewer functions. No mandatory remote upload/conversion service.
- Preserve desktop browser, native desktop and Jupyter workflows when modifying shared modules.

### 4.2 Functional coverage ledger

The full mobile target retains all applicable desktop View capabilities. Heavy features can be delivered in stages, but they cannot be silently removed from the final scope or represented by nonfunctional controls.

| Area | Must remain usable in View | Not part of mobile physical editing |
|---|---|---|
| Selection and inspection | Atom/replica/object picking; rectangle/add/remove/invert/select-all; visible selection; stored properties and deliberate geometry measurement | Atom deletion or coordinate editing |
| Appearance | Global size; label table; live selected appearance; labels and merge; material/opacity/color; property colors/radii; visual undo/redo | Changing a chemical element |
| Bonds | Pair specifications, suggested reset, manual pair definitions, appearance and periodic bridges | Modifying a force model by changing visual bonds |
| Cell and guides | Cell/PBC inspection, displayed replication, visible cell/grid/axes/constraints, visual translation where supported | Cell-matrix mutation, physical supercell materialization or wrapping source coordinates |
| Trajectories | Play/pause, seek, frame ranges, interpolation where valid, stable mappings and frame-specific metadata | Running a molecular dynamics/relaxation calculator |
| Analysis | Stored forces, displacements, distributions, polyhedra, embedded fields/planes/isosurfaces, read-only registry and match previews | Physical optimization, applying matched cells, constraint editing |
| Camera and rendering | World camera, viewport-lock option, Render Area, flat/3D, materials/lighting where meaningful, object-specific camera transforms | Atom G/R/S masquerading as viewing |
| Output | Save view/project copies; interactive HTML; exact images; trajectory movies/GIF and existing View-accessible data/geometry exports under an explicit parity plan | Converting a viewing change into an unannounced structure mutation |
| Documents | Open, switch, close, dirty-state handling, recents, external-open delivery, sharing and view reset | Desktop OS process/window behavior copied blindly onto iOS |

Read-only analysis is not always cheap or already implemented in JavaScript. Local ports of those kernels and of several export paths are part of the engineering plan. “Can display a previously computed surface” is not the same as “can change its isovalue and recompute it.”

**Data availability exception:** a lightweight HTML can omit arbitrary arrays, raw grids and recoverable project content. Features requiring absent data must say **Not included in this file**. They must not invent values or claim full `.vase` parity. Full project/embedded HTML provides the intended complete data path.

### 4.3 Reset and desktop-specific history

Provide **Reset view** to return to the document's saved presentation, distinct from resetting personal app defaults. It must not reset physical coordinates in a View-only product. Explain what changes before a reset that discards unsaved presentation changes; retain undo where possible.

The owner's earlier desktop request for “Reset coordinates / Reset everything,” dragging tabs into new desktop windows, quitting the last desktop window with Command+W, and opening broad ASE file formats describes desktop scope. Mobile adaptation should preserve safe document management and supported tablet windows without force-quitting the process or adding editing permissions. Do not create fake mobile equivalents that change data.

## 5. Scientific data and appearance rules

### 5.1 Immutable source and identities

- Preserve source precision. Keep validated float64 data when the source requires it; use explicitly derived float32 buffers for the GPU. A screenshot matching the source is not proof of a lossless save.
- Index zero is an atom, not a falsy/missing value. Empty selection is not “all atoms.” Unknown/NaN property values are not numerical zero.
- Preserve source labels separately from chemical elements and visual label overrides. Never infer the element of a source atom from an arbitrary user-entered label.
- A periodic image reference includes `(base index, cell offset [a,b,c])`. Measurement/hide/selection of a replica must use its displayed position and exact identity.
- Scope conversion must be explicit: scalar arrays belong to base atoms, so a selected replica maps to its base index for scalar targeting; hiding that visual instance need not hide every image.
- Existing colorscale/radius scopes follow **base indices**, even when a later frame changes element or atom count. Do not substitute chemical-name matching or invent an identity-matching algorithm. An imported scientific ID can be preserved, but changing targeting semantics requires a separate product decision.

### 5.2 Live selected appearance

Owner-required sequence:

1. Selecting atoms exposes their editable **visual** appearance. There is no **Apply selected appearance** button.
2. Committing a new label splits those selected atoms into that visual group immediately. Text commits on Enter/Done or valid focus exit; Escape cancels a draft. Do not create a succession of labels on every partially typed character.
3. If the user changes color, material, opacity or relative radius before naming a label, create a free label beginning at `[Element]_2`. Use `_3`, `_4`, etc. if needed. Mixed elements/existing visual styles must not be flattened into an inappropriate single group.
4. The first split and first completed appearance gesture form one undo transaction. Later adjustments are normal undo steps. During a color picker drag, do not create a new label and undo entry for every pointer event.
5. Committing an existing label asks whether to merge. On confirmation, inherit the destination label's complete visualization settings, including radius, color, opacity, material, visibility and linked bond appearance. Cancel leaves the old group intact.
6. If only some members of a shared label are subsequently styled, separate that subset again; do not change unselected members unintentionally.
7. Selected controls, label table and canvas update together. No hidden second appearance state that makes the table disagree with the selected atoms.

**Radius example:** if a selected group has a label radius of `1.20 Å` and the user applies a `1.5` relative size adjustment, its new label row should contain `1.80 Å`. The relative adjustment is folded into the new label radius once. The independent global size and property factor remain separate; they must not be multiplied twice.

The current reference `SelectedAppearanceEditor` performs optimistic visual updates and transactional rollback. Mobile can implement a different state framework, but must preserve those outcomes. No network/backend round-trip should be required for an ordinary local color adjustment.

### 5.3 Property color and radius mappings

Display controls in a readable sequence: **Property → Apply to → Range → Mapping appearance**. Show the source and unit of the property. Keep color mapping and radius mapping independent.

**Color target UI:**

- **Apply to:** `All atoms`, `Selected atoms`, and available labels.
- Under `Selected atoms`, show an explicit **Use current selection** button plus a captured-target count. Changing the current GUI selection does not automatically retarget the map.
- Selecting a label captures its current base indices; it does not dynamically redirect as labels/elements change later.
- Do not call the target “Fixed atom selection.” That wording can be confused with `FixAtoms` constraints. Internal descriptions may say “captured indices,” but the UI must remain understandable.
- An empty captured set colors no atoms. Do not fall back to the whole structure.

**Range semantics:**

- **Fit current frame** calculates limits once and locks them.
- **Fit trajectory** calculates one finite range across the relevant frames and locks it.
- **Manual** uses explicit finite limits.
- Playback does not normalize each frame independently. The same value should retain the same color/size interpretation.
- Changing a scope does not silently replace a manually chosen range. An explicit Fit action refits it.
- Custom colormap stops, reverse and gamma must survive save/load and export. Reusing sampled color values is insufficient if the user later changes the property/range.

**Effective radius:**

```text
drawn radius = base/label radius
             × global atom-size multiplier
             × any retained legacy/manual per-atom multiplier
             × property radius factor
```

An appearance split folds the selected manual multiplier into its label radius and clears the obsolete per-index adjustment. Property mapping stays independent. For the standard mapped factor:

```text
t = clamp((transformedValue - minimum) / (maximum - minimum), 0, 1)
factor = outputMinimum + (outputMaximum - outputMinimum) × t^exponent
```

Use the existing normalization/validation semantics, including degenerate ranges, rather than a new formula hidden behind the same controls. Identity and absolute-value transforms are explicit choices. A fractional-existence preset uses the actual available property; never assume that an absent property equals 1 or that a charge property is occupancy.

Missing/nonfinite radius values and indices outside its scope use the reference neutral factor `1`; report data availability. Factor `0` hides the atom glyph without deleting its scientific record or arbitrarily changing bonding policy. Missing color data remains explicitly unavailable and follows the reference unmapped-appearance behavior, never a fabricated zero-valued color.

**Loading behavior:** preload/cache the catalog, retain dropdown options while opened, load values on demand, and show a truthful loading/error state. Never leave an apparently empty dropdown that populates only after the user has dismissed it.

### 5.4 Trajectory consistency

At frame commit, update positions, topology, labels, color factors, radius factors, constraints and relevant property values as a coherent transaction. Rendering base radii first and applying mapped radii a moment later is an acceptance failure.

Example required behavior:

```text
Captured indices: [1, 7, 9]
Frame A: 10 atoms → map indices 1, 7, 9
Frame B:  6 atoms → map index 1; retain 7 and 9 in saved configuration
Frame C: 12 atoms → map indices 1, 7, 9 again
```

Changing the element at index 7 does not delete index 7 from the mapping. Opening an unrelated document must not inherit those indices. Saving on Frame B must preserve the full captured set.

Keep frame requests generation-tagged and coalesced. A result for an old frame/document/property must not overwrite a newer request. Rapid scrubbing must not produce the previously reported **per-atom property catalog became stale** failure during normal navigation.

Interpolate compatible frames according to shared scientific rules. Continuous raw scalars are interpolated before applying the locked color/radius mapping. Discrete labels/elements/topology are not averaged. When topology is incompatible, use the documented discrete transition/reference fallback rather than inventing atoms or morphing unrelated indices. The play/seek/export paths must agree.

### 5.5 Selection, measurement and inspection

- Distinguish **ordered picks for measurement** from **bulk/box selection** in state. A box containing exactly three or four atoms must not accidentally display an angle or torsion.
- Preserve the desktop's deliberate individual-pick measurement workflow when using a mouse/keyboard. On touch, explicit Measure provides an unambiguous ordered-pick path. Do not suppress all two-to-four-atom metrics merely to fix the bulk-selection case.
- Measure is an explicit tool. Ordered taps identify points `a1`…`a4`; two points give distance, three an angle at the middle point, four signed torsion. Show direct/MIC values where applicable. Offer clear/restart/undo-last-point without a keyboard.
- If Measure is activated on an existing eligible selection, show its ordering and permit correction; never let arbitrary Set iteration define an unexplained physical measurement.
- For a single selected atom, the compact readout contains current **label**, Cartesian X/Y/Z and actual stored properties, including existence and force when available. Do not replace it with a permanent large note over the canvas.
- Element, mass and fractional coordinates need not occupy the default bottom readout. Preserve them in underlying data/advanced inspection if required by APIs. Do not delete scientific attributes to simplify the UI.
- Long readouts scroll/expand and can be copied. Readout overlays must not swallow intended picks of nearby atoms. Touch uses explicit expansion; no Shift-only escape from an obstructing overlay.

### 5.6 Bonds, constraints and flat rendering

- **Style → Bonds** opens Pair specifications by default. Label-pair enable and cutoff are distinct controls.
- Keep **Reset to suggested cutoffs**. Do not reintroduce a redundant Automatic radii mode in the visible UI. Suggested defaults may be derived from element radii internally.
- Rendered bond cutoffs and repulsive-calculator distances are different concepts. The mobile viewer does not run the relaxation calculator; do not merge its settings into the bond table.
- Preserve manual pairs, periodic bridges, bond thickness and endpoint appearance where present in the source.
- Show/hide constraint marks through **Objects → Constraints**, and use the same visibility in exported images/movies. This never edits the saved constraints.
- **2D flat** and **3D spheres** are display styles, distinct from orthographic/perspective projection. Offer the same style setting in the viewport controls and Renderer route; both edit one state value.
- Flat mode disables 3D material and lighting controls while retaining their saved values for return to 3D. It does not disable meaningful output dimensions, crop, colors, opacity or export settings. Fixed-atom crosses must remain sharp, without smeared ends.

## 6. Touch, gizmo and input behavior

### 6.1 Owner-specified mapping

| Input | Required result |
|---|---|
| Tap atom/object outside gizmo | Select and show appropriate information/context |
| One-finger drag beginning on empty canvas | Rectangular atom selection, not orbit |
| Drag beginning in floating gizmo | Orbit continuously even after the finger leaves its visible bounds |
| Tap an X/Y/Z gizmo target | Align like the corresponding desktop axis key |
| Drag across an X/Y/Z target | Continue the drag; never align accidentally |
| Two-finger same-direction movement on canvas | Orbit, as an alternative to the gizmo |
| Pinch / differential two-finger motion | Smooth zoom; provide a clearly defined pan workflow as below |
| Gesture beginning in a settings panel | Scroll or edit that panel, not manipulate the 3D scene |

**Unresolved ambiguity and proposed resolution:** the owner requested both pan/zoom and same-direction two-finger orbit. Equal same-direction motion is also the conventional pan gesture. Opposite-direction motion alone has no centroid translation from which to infer pan. The proposed design is an explicit **Pan** toggle: default two-finger translation orbits; with Pan active it pans, while pinch still zooms. This recommendation has been explained, but must not be represented to contractors as an explicitly approved exact gesture implementation. Validate it in the interaction prototype; do not silently replace the owner's default same-direction orbit.

### 6.2 Floating gizmo

- Use the existing rotating XYZ concept, relocated to a mobile thumb-reachable floating control. A fixed desktop upper-right widget alone is not sufficient.
- Default position is designed for a landscape phone; proposed anchor is lower-left of the usable canvas, clear of safe-area edges and timeline. Portrait has a separately stored usable position.
- Settings supports left/right presets, sensitivity, size, and deliberate **Reposition gizmo** mode. Normal drag orbits; repositioning the control is a different explicit mode.
- During orbit, a thumb circle follows the contact, with a base/tether so direction is visible like a joystick. The scene and all axis markers update from the same camera orientation every draw. Avoid a decorative static axis icon while the scene rotates.
- Proposed drag behavior uses relative displacement and stops when the finger stops/releases. Do not add perpetual spin by default. If velocity-based joystick orbit is proposed, validate precision and explicit stopping before adopting it.
- Capture the pointer at gesture start. Leaving the region does not end it. End on up/cancel/background; reset visual thumb state.
- Tap/drag classification is sticky. A proposed starting threshold is 8 CSS px and 300 ms for a one-contact tap, to be tuned on devices. Crossing that threshold permanently cancels axis-tap eligibility for the current gesture.
- Axis hit regions must be usable at touch size. When projection makes axes overlap, use depth-aware disambiguation and an accessible axis alternative; do not invisibly overlap six large buttons and snap unpredictably.
- All controls have accessible names and a non-drag axis/alignment alternative for assistive input.

### 6.3 Pointer state machine

Suggested controller states, independent of UI framework:

```text
Idle
  ├─ GizmoPending → GizmoOrbit → Idle
  ├─ AtomTapPending → Selection / MeasurePoint → Idle
  ├─ EmptyPending → BoxPreview → CommitSelection → Idle
  ├─ TwoTouchPending → Orbit OR Pan/Pinch → AwaitAllReleased → Idle
  └─ PanelOwned → NativeScroll / InputEdit → Idle

Any state → Cancelled on pointercancel, view replacement or app suspension
```

Rules that prevent the usual mobile defects:

1. Resolve the owner of a contact at pointer-down. A panel contact never migrates to canvas control. A captured gizmo drag never becomes selection because it crossed the canvas.
2. Do not simultaneously attach competing navigation and selection controllers to the same touch stream. The existing renderer's controls track one active pointer; that is not a complete mobile recognizer.
3. Box selection remains a preview until release. If a second finger arrives, cancel the box preview and switch to navigation without committing a selection.
4. A second finger arriving during an atom tap cancels the tap. Allow navigation without requiring both fingertips to land in tiny empty gaps in a dense structure; confirm this proposed accessibility extension in the prototype.
5. Classify two-touch translation versus pinch using common/differential motion and hysteresis. Hold the classification through the gesture. An asymmetric pinch must not oscillate into orbit every other event.
6. When one finger of a two-finger gesture lifts, do not reinterpret the remaining contact as a new atom tap or selection box. Wait for all contacts to end.
7. Suppress the synthesized click after a completed drag. Dragging past an axis, menu or atom must not activate it at release.
8. Leave panel scrolling, text selection, OS edge gestures and accessibility functional. Use `touch-action: none` on the interactive canvas/gizmo only, not indiscriminately on the entire app.
9. Selection provides Replace/Add/Subtract, Select all, Clear and Invert without Shift. Active state is obvious and consistent. Measurement is a distinct mode and bulk selection does not inherit measurement intent.
10. Drag beginning on an atom must not move scientific coordinates. A selected camera/field visual object can have explicit move/rotate/scale handles; object-edit mode must be deliberate and mutually exclusive with selection/navigation.

### 6.4 Hardware keyboard, mouse and pen

Detect capabilities per event, not once from “mobile” user-agent or screen width. A tablet can use a mouse and touch concurrently. Pencil/pen picking must not accidentally invoke physical atom editing; provide palm/secondary-pointer handling appropriate to the platform.

Mouse+keyboard users should retain desktop-like precision, Shift selection, orbit/pan/wheel behavior and tooltips. Touch-sized controls may remain available; offer density preferences rather than abruptly replacing the whole UI when a mouse moves.

| Apple keyboard | Android keyboard | View-only action |
|---|---|---|
| Command+Shift+B | Ctrl+Shift+B | Open display Supercell controls; select the first value |
| Command+Shift+P | Ctrl+Shift+P | Open Atoms/property color and radius controls |
| Command+B | Ctrl+B | Open bonding configuration |
| Command+Shift+A | Ctrl+Shift+A | Open Renderer, including scale and flat/3D setting |
| Command+E | Ctrl+E | Show read-only cell information/unsupported physical-transform explanation; never enable Edit |
| Command+O | Ctrl+O | Native Open picker |
| Command+S | Ctrl+S | Save using valid retained project target/format, otherwise save UI |
| Command+Shift+S | Ctrl+Shift+S | Save As/copy to a new target |
| Command+W | Ctrl+W | Close current internal document safely |
| Command+N | Ctrl+N | Create an empty viewer document/Open destination |
| Command+A | Ctrl+A | Select all scene atoms when viewport owns focus; select field text in an input |
| Command+Z / Shift+Z | Ctrl+Z / Shift+Z | Undo/redo visual transactions |
| X/Y/Z | X/Y/Z | Axis alignment, or axis constraint during an allowed visual-object transform |
| F | F | Fit view when viewport owns focus |
| Space | Space | Play/pause current trajectory |
| Arrows | Arrows | Step camera orientation; leave arrows native in input fields |
| Option+Left/Right | Alt+Left/Right | Previous/next source frame |
| Shift+A / Option+A | Shift+A / Alt+A | Invert / clear selection outside inputs |
| Delete/Backspace | Delete/Backspace | Hide selected visual instances; never delete source atoms |
| G/R/S, Enter, Escape | G/R/S, Enter, Escape | Transform a supported selected visual object, then commit/cancel; atom transforms stay disabled |
| Tab / Escape | Tab / Escape | With viewport focus, reveal the inspector; inside it Tab navigates fields. Escape cancels the active gesture/modal/tool first, then follows inspector dismissal behavior |

Native key callbacks and DOM key events must not execute the same command twice. Respect IME composition and text focus. Modified letters must not fall through to plain-axis/transform shortcuts. Preserve Command+A and the owner's additional Ctrl+A select-all behavior in numeric fields on Apple keyboards where the event is available.

Retain visual Sun-direction manipulation where lighting is available: selecting its source and using G translates source/target together; selecting the target and using G aims the light; R rotates its direction. Axis constraints, numeric entry and cancel apply to supported visual transforms. These controls never move atoms and are disabled where flat rendering makes lighting ineffective.

OS-reserved commands cannot be promised universally. Native fullscreen is not a guarantee that every system shortcut reaches the app. Provide visible alternatives and record actual tested delivery. Closing the last mobile document returns to the library/empty screen; do not call an exit API to imitate desktop process termination.

## 7. Layout, navigation and control quality

### 7.1 Proposed adaptive workspace

```text
Landscape phone/tablet
┌ Document / Open / document switcher / preferences ───────────────────┐
│ Objects       axis/view controls     [overlay inspector when open]  │
│                                    ┌ Inspect Style Analyze Render ┐│
│             SCIENTIFIC CANVAS      │ section navigation           ││
│                                    │ active section title         ││
│  floating XYZ gizmo + Pan           │ controls / table / plot      ││
│ selection/property strip           └──────────────────────────────┘│
│ trajectory strip, when present                                      │
└─────────────────────────────────────────────────────────────────────┘

Portrait
┌ Document / Open / document switcher / preferences ┐
│ Objects                        axis/view controls│
│                 SCIENTIFIC CANVAS                │
│  floating gizmo + Pan                            │
│ trajectory strip, when present                   │
├ bottom sheet handle + selection summary          ┤
│ Inspect / Style / Analyze / Render               │
│ section navigation → title → controls            │
└──────────────────────────────────────────────────┘
```

This is hierarchy/placement, not a demand to render box borders like the diagram. Reuse the current visual language. A narrow/short landscape window may need a compact panel; choose based on usable dimensions, not a device model.

- Landscape properties appear on the right; portrait properties use a bottom sheet. Use collapsed, medium and expanded sheet states with an explicit handle.
- Panels overlay a stable canvas surface. Opening a panel, editing an input or changing selection must not refit/recenter the structure. If a genuine window resize requires projection updates, preserve the intended camera/framing rather than resetting it.
- Initial fit and explicit camera recall account for the usual properties area. On landscape, this normally means a work center left of full-window center; on portrait, above the medium sheet. User panning after that must remain respected.
- Keep Objects and selected-atom information close to the canvas. Keep appearance/analysis/render configuration in the properties area. Do not put every command in a single overflow menu.
- English labels remain concise. Use original v_ase branding, restrained surfaces, consistent text sizes, clear focus rings and aligned active markers. Avoid nested cards, decorative gradients and gratuitous pill controls.

### 7.2 Information hierarchy

Use this repeated structure:

```text
Workspace: Style
Section navigation: Atoms | Bonds | Cell | Polyhedra | View & guides
Active title: Atoms
  Global size
  Property radius
  Property color
  Per-label appearance (table)
  Selected atoms (contextual controls)
```

The desktop owner's icon-bookmark preference applies to **section navigation**, not every field. Fine-pointer layouts can use icon-only bookmarks with hover/focus labels. Touch has no hover; selected section text, accessible labels and press-and-hold descriptions must keep icons understandable. The row of section navigation comes **before** the active title, never underneath “Atoms” as if it belonged to Atoms.

Surface material is already a per-label/selected-appearance setting. Do not reintroduce a duplicate global Surface material section outside the table. Some older prose in `docs/appearance.md` still lists that older grouping; the latest owner instruction takes precedence.

Frequently used axis controls and rotation steps stay visible when there is room. Only collapse them when space requires it; use a meaningful animated chevron, not an unexplained `...`. Animation must not animate/reflow the scientific canvas or ignore reduced-motion settings.

### 7.3 Controls and tables

- Repeated labels/pairs use real tabular alignment. Keep one row per entity, a sticky identifying column, horizontal scroll and a consistent header. Do not make each label an independently stacked card.
- A unit suffix and input share a layout container with sufficient minimum width. Decimal alignment and tabular numerals improve scanning. Scientific labels can wrap; numbers and units must not collide.
- Table headers stick to the **table's own scroll container** with no gap above. A body row must never appear above the header, including during nested-panel scroll.
- Use roughly 44 pt Apple / 48 dp Android interactive target intent; confirm actual rendered size. Small glyphs can sit inside larger hit targets. Do not make large target rectangles overlap and then choose arbitrarily.
- In bond cutoff editing, Tab/Shift+Tab and virtual-keyboard Next move directly between cutoff values. Pair enable checkboxes remain accessible by touch and an appropriate keyboard path; optimized numeric navigation must not make them unreachable.
- The first Supercell field selected by its shortcut must select the entire current number. `Primary+Shift+B`, `2`, Tab, `2` should yield a displayed 2 × 2 repeat, not 12 × 12.
- Maintain a last-valid value while the user types `-`, `1e`, an empty draft, etc. Invalid drafts need local feedback and cancellation; they must not lock unrelated panel shortcuts with a global “Finish the invalid field before leaving this control” error. Save/export must still reject or resolve invalid data before serialization.
- When the software keyboard appears, scroll the focused field into its panel's visible area. Do not cover it, bounce focus, refit the structure or switch the panel from portrait to landscape because the available height shrank.
- Slider drags preview smoothly; commit a sensible undo action at gesture end. Async work uses debouncing/cancellation without hiding the control's current intended value.

### 7.4 Popovers and modal behavior

Use one interaction-layer coordinator. Opening File/Open or another primary menu closes Search and other mutually exclusive popovers. Tap outside dismisses when appropriate; Escape/Back dismisses the topmost layer before changing the document. Restore focus to the invoking control.

With a mouse and an already-open desktop-style menu, moving over another menu trigger switches menus. Do not transplant hover-only behavior to touch. A confirmation for destructive/reset/merge behavior is distinct from a transient properties popover and must retain the correct focus scope.

Do not steal focus or switch the current workbench route just because an atom is selected. Show selection information contextually while respecting the user's active configuration task.

### 7.5 Theme and orientation

Theme defaults to **System**, with persistent Light/Dark overrides and live response to OS changes. Theme changes affect chrome; they must not recolor the saved scientific figure or change its white/transparent export background.

The owner clarified the intended orientation behavior using YouTube:

1. Normal presentation follows the OS orientation policy, including sensor auto-rotation lock.
2. A visible **landscape/fullscreen** button explicitly enters the wide viewing presentation and requests landscape through native APIs.
3. Exiting restores the prior presentation and system-following policy.
4. Scene state, current frame, selection and output camera survive the transition.

Do not interpret “rotation lock” as a blanket reason to omit this button. A user's explicit app-level orientation request is different from sensor-driven auto-rotation or changing the global device setting. Apple offers [`requestGeometryUpdate`](https://developer.apple.com/documentation/uikit/uiwindowscene/requestgeometryupdate(_:errorhandler:)); Android offers [`setRequestedOrientation`](https://developer.android.com/develop/adaptive-apps/cookbook/orientation-restriction).

Tablet split windows, newer adaptive Android behavior and browser-hosted HTML have separate restrictions. If orientation cannot change, fullscreen/expanded presentation should still use the available window and explain the limitation. Preserve tablet multitasking. Test with rotation lock both on and off; do not certify this based on a simulator or CSS rotation of the WebView alone. See [Android adaptive orientation](https://developer.android.com/develop/adaptive-apps/guides/app-orientation-aspect-ratio-resizability) and [Apple iPad window/orientation guidance](https://developer.apple.com/documentation/technotes/tn3192-migrating-your-app-from-the-deprecated-uirequiresfullscreen-key).

## 8. Camera and Render Area contract

This area received repeated owner corrections. Implement the state model first, then bind controls to it. Do not build several vaguely named buttons that each modify a different collection of booleans.

### 8.1 Separate concepts

| Concept | Meaning | Does it change saved output? |
|---|---|---|
| Camera visibility | Whether the Render Area guide and off-axis camera representation are displayed | No change to pose, dimensions or scale merely from hiding/showing |
| Camera selected | The camera is the active visual object for its transforms | Selection alone does not change output |
| Look/view through saved camera | Navigate the inspection view to the output camera | No output-pose replacement |
| Lock camera to viewport | Optional mode where subsequent navigation changes output composition while the on-screen guide stays stable | Subsequent navigation does change composition; toggling on/off alone preserves the established composition |
| Align camera to current view | Explicitly replace output camera pose using the current inspection view | Yes; it is a deliberate camera edit |
| Physical output scale | Pixels per Å in output, independently from preview zoom and atom-radius multiplier | Yes, when explicitly edited or changed by a camera scale transform |

**Terminology:** consistently use **Render Area** for the output guide. Do not alternate between output frame, render view, render area and preview window. “2D flat” is not synonymous with orthographic camera.

### 8.2 Visibility and lock transition table

The camera icon exists in both the viewport controls and **Render → Renderer → Render Area & scale**. Both reflect the same camera visibility as **Objects → Camera / render area**. Do not omit the right-panel icon.

| Action | Required result |
|---|---|
| Activate camera icon while hidden | Show camera/Render Area and enter saved camera view; fit it into the normal usable workspace, accounting for the properties panel |
| Deactivate camera icon | Hide guide and wire camera; clear camera selection; deactivate Lock camera to viewport; preserve saved output pose/scale/dimensions |
| Disable camera through Objects | Same deactivation behavior; all matching controls synchronize immediately |
| Enable Lock camera to viewport | Show camera if necessary, enter saved view if needed, preserve the existing composition; make lock state unmistakable |
| Disable Lock camera to viewport | Camera remains fixed at its current world-space pose; no framing jump |
| Recall saved view while lock is already active | Idempotent; do not turn the lock off or switch to a different navigation mode |
| Align camera to current view | Replace camera pose deliberately, update preview/export state and commit one visual transaction |

The latest desktop convention uses camera icons as visibility toggles; returning to the saved view can be done by turning it off and on. Do not silently reinterpret the same icon as three unrelated actions depending on hidden state. If the mobile team proposes a separate recall shortcut, keep it clearly distinct from alignment and review it as a UX proposal.

There is **no separate Hide render area text button** and no permanent “World versus Viewport” chooser. World-fixed is the default; **Lock camera to viewport** is the optional toggle. “Navigate: camera/scene” and “Camera follows editing view” are superseded wording.

### 8.3 Navigation and visual transforms

With viewport lock off:

- Orbit, pan, zoom and X/Y/Z adjust the inspection view without altering output composition.
- Camera-view preview zoom can make the guide smaller/larger on screen without changing its output dimensions/physical scale.
- View-camera alignment indication can remain for pan/zoom but changes when the inspection angle leaves the camera direction; it is not permission to rewrite output-camera state.

With viewport lock on:

- The guide stays stable in the viewport; navigation changes what the output camera sees.
- X/Y/Z updates camera, axes and guide in the **same visible frame**. Never hide the guide until the next wheel or touch event.
- Camera G/R/S changes output composition while the surrounding rendered structure/cell moves relative to the stable guide. This is camera manipulation, not writing changed atom coordinates.

Camera transforms must also be operable without a keyboard through explicit selected-camera controls. `G` translates camera and target together; `R` rotates around the output center with optional world-axis constraints; `S` uniformly scales framing and updates physical px/Å inversely where applicable. Commit applies a coherent camera/scale state; Cancel restores both, including the on-screen preview. Selecting the camera clears incompatible object-transform selections but must not mutate atom data.

### 8.4 Off-axis camera representation and composition

- Use a recognizable camera outline/body, viewing-angle arc and oriented output-plane outline. The old floating eye alone did not show facing direction or framing and is not acceptable.
- Avoid an opaque plane covering atoms. The camera/grid/guide layers must not write depth or mask scientific geometry incorrectly.
- The frame's camera badge/outline must visibly look selectable; show press/selected/focus state. Do not make a purely decorative-looking symbol the only way to select it.
- Objects provides camera, cell, grid, axes, constraints and other available scientific-layer visibility. Camera gizmos and editor UI are not included as scientific export content.
- The grid behaves like an adaptive work plane with a fading horizon, not a visibly finite square rotating out of view. Camera clipping must accommodate structure bounds without corrupting saved camera optics.
- Opening or resizing a panel does not refit. Explicit camera recall initially centers within the usual work area, even if the panel is currently collapsed; later user positioning stays respected.

### 8.5 Render/export parity

Image, movie/GIF and interactive HTML use the same stored camera/Render Area dimensions and compatible object-visibility choices. The renderer must not capture the phone screen/UI and call that the configured scientific export.

- Width/height are exact output pixels, not device pixels multiplied by current display DPR. A 1920 × 1080 job produces every encoded input frame at precisely that size.
- Output px/Å, viewport zoom and sphere-size multiplier are separate values. Display units and labels accordingly.
- Export the actual property-derived radii, colors, label styles, bonds, constraints, cell and vectors for each frame. Do not update appearance after the frame is captured.
- Video includes source **From frame / To frame**, FPS, interpolation options, duration estimate and repeat choice where supported. Specify UI numbering clearly; recommended UI is 1-based inclusive, converted once to internal 0-based indices.
- GIF supports **Loop forever** and **Play once**; validate actual encoded loop metadata in a decoder/player.
- Flat mode preserves crisp glyphs and disables ineffective material/lighting controls. Both viewport and Renderer mode controls remain synchronized.
- Export dialogs use the document's retained profile. Canceling a one-off export does not replace that profile or turn an HTML project into `.vase`.
- Stream/capture/encode one bounded set of frames at a time. Progress and cancel are mandatory; report an actual output path/share result, not merely a successful internal callback.

## 9. Files, document lifecycle and saving

### 9.1 Supported file types

| Input | How it opens | What data is available |
|---|---|---|
| `.vase` | Native document association or in-app Open | Full saved project members, subject to schema/size validation |
| v_ase HTML with embedded project | Explicit in-app Open; browser can also display it | Full embedded project plus saved HTML scene/export composition |
| Lightweight v_ase HTML | Explicit in-app Open; browser display | Only included scene/frame data, saved mappings and optional precomputed results |
| Arbitrary HTML | External browser option / explain unsupported scientific document | Do not execute it inside the privileged app |
| Raw structure files or JSON | Unsupported mobile input in this scope | Explain supported formats; do not steal their association |

On iOS, declare the shared `.vase` UTType/MIME coherently and integrate Files/cloud-provider access. On Android, use content URIs/Storage Access Framework; do not assume a filesystem pathname is available. Read/open permissions can disappear and providers can deliver data lazily. `.vase` eligibility does not permit forcing users' default-app choices.

For providers that label a `.vase` as generic ZIP/octet-stream, offer an explicit picker fallback then validate content. Do not register the app as the global default handler for ZIP or all files. HTML has no owned/default association in this product.

### 9.2 Safe native HTML import

The existing export contains base64 scientific data **and executable JS modules**. Import only validated scene/project data into trusted packaged renderer code. Do not navigate a bridge-enabled WebView to arbitrary imported HTML or evaluate its module scripts.

Validate schema, sizes, references and strings; do not use `eval` for data parsing or allow unknown fields to become file paths, script sources or bridge commands. Imported HTML must not cause network requests merely because its title/body was parsed. Use no-resource-loading extraction and native/file origin restrictions.

This is a security requirement specific to importing executable HTML into a native shell, not a reason to remove the owner's in-app HTML load feature.

### 9.3 Document and save state

Maintain explicit states such as Loading, Ready/Clean, Ready/Dirty, Saving, Save failed and Closing decision. A recoverable local view session is not automatically a saved external file.

- A new document does not become active until validation/basic scene construction succeeds. On failure, leave current work intact and explain the file issue.
- Read `.vase` without an Edit/View chooser; the mobile host remains View-only. Preserve the stored desktop `documentMode` as source metadata when producing a lossless view copy, rather than silently changing a future desktop reopen to View.
- Restore saved camera, current frame, label/display state, mapping scopes, object visibility and render/export configuration. Fit its composition to the device; do not promise identical desktop pixels on a different aspect ratio.
- Save waits for a coherent committed frame and pending visual transactions. Invalid scientific settings must not be serialized, but unrelated navigation must remain escapable.
- **Save** reuses a retained writable document target where supported, with the same format and profile. Without durable write access, show an explicit destination/copy flow. Do not claim an external file was overwritten when only an app-cache copy changed.
- **Save As** creates a new target. Only a successful write updates the retained target. Cancel/failure keeps the original target and dirty state.
- A restorable HTML remains restorable HTML on Save, including its archive, poster/scene and export configuration. Lightweight HTML stays a viewing export unless a full project actually exists; never synthesize missing arrays.
- Never overwrite source coordinates/cell/constraints/elements while saving visual edits. Preserve unknown archive members and unsupported-but-retained metadata when round-tripping.
- Before overwriting, detect external modification where the provider allows it. Offer a conflict/copy path instead of silently winning a race. Be explicit where the provider cannot guarantee atomic compare-and-swap.
- Closing dirty work offers Save, Discard and Cancel. Canceling the native picker cancels the close. Android Back first cancels/dismisses the current interaction; it must not suddenly discard a document.
- App termination can happen without a prompt. Persist recoverable view state incrementally and restore it on the next launch, while distinguishing recovered changes from saved source data.

### 9.4 File drop, share-open and multiple documents

Native Open, incoming share/open intents, Files handoff and supported drag/drop should call the same validated import pipeline. Do not have a shortcut-only loader that loses metadata.

Existing document open defaults to another internal document. A frame append is a different operation that must explicitly explain that it takes frames into the current trajectory and does not replace its entire style. Empty-state opening skips nonsensical destination questions. On devices with native multiple-window support, windows may be a separate supported target; do not imitate desktop tab tear-off through fragile touch-distance heuristics on phones.

Only the active document normally owns an active renderer. Preserve inactive state and suspend its GPU/workers; reopening a tab must not reload a different frame or forget scalar targets.

## 10. Architecture and integration boundaries

### 10.1 Recommended baseline

Use a packaged shared web rendering/viewer core with a native mobile shell, for example Capacitor + WKWebView on iOS and Android WebView. This is a recommendation, not a requirement to adopt Ionic UI components. The interface must retain v_ase's design rather than default framework styling.

Python/ASE is not required merely to draw atoms, inspect included arrays or process touch input. It is currently used to decode/prepare scientific data and compute many analyses. Replacing it requires actual implementations of those services; setting `vizOnly: true` does not remove them.

Proposed architecture:

```text
Native host (Swift/Kotlin)
  File grants / open intents / share / orientation / keyboard / lifecycle
                         ↕ typed, capability-limited bridge
Mobile UI → shared viewer state + semantic commands → Three.js renderer
                         ↕ provider interfaces
Document reader / frame store / property store / analysis workers / exporters
                         ↕ bounded local files and buffers
Original project data + view session + optional derived caches
```

Avoid bundling the desktop Python runtime, a localhost Uvicorn server and all scientific packages as the default answer. Embedded Python is possible in principle, but native wheels, scientific extensions, storage, performance and licensing need their own proof. Do not assume Pyodide can install every desktop dependency.

### 10.2 Interfaces to agree before UI work

These are **proposed interfaces**, not existing API guarantees:

| Boundary | Minimum responsibilities |
|---|---|
| `DocumentSource` | Validated metadata/schema, original members, capabilities/availability, retained source identity and grants |
| `FrameSource` | Frame count/current frame; lazy typed data; topology signature; explicit cancellation and progress |
| `PropertySource` | Field descriptors with source/unit/component; per-frame values and availability; bounded range scans; stable missing-data semantics |
| `AnalysisService` | Deterministic read-only computations, progress/cancel, source-generation tags and numerical reference tests |
| `ViewerStore` | View state/selection/object state/undo; immutable source boundary; coherent scene-frame commit |
| `ExportService` | Exact dimensions/camera/appearance snapshot; bounded encoding; formats and capability reporting; no silent substitution |
| `HostServices` | Open/read/write/share, file grants, lifecycle, orientation requests, native keyboard delivery and safe local-resource access |

Every asynchronous response includes document identity, data generation and requested frame/operation identity. Reject obsolete results before applying them. UI actions should call shared semantic commands rather than manipulate unrelated DOM fields in an order-dependent way.

### 10.3 Existing source map

| Need | Starting point | What the mobile team should preserve/extract |
|---|---|---|
| Project format | `v_ase/project.py`: `write_project_archive`, `read_project_archive`, `normalize_visual_settings` | Schema/members, settings migrations, safe data types, labels, per-frame origins, constraints and unknown-content retention |
| Saved file target | `v_ase/project_files.py`; `v_ase/static/project_provenance.js` | Format/profile/source binding and conflict principles; replace desktop/browser handles with native provider semantics |
| Offline HTML | `v_ase/export.py:export_html_response`; `v_ase/static/standalone.html`, `v_ase/static/standalone.js` | Trusted data schema, embedded-vs-lightweight distinction, saved composition and frame-specific display factors |
| Renderer | `v_ase/static/renderer.js`: `ASERenderer`, `BlenderTumbleControls`, `requestRender`, capture methods | Rendering, instancing, camera math, draw-on-change; replace single-pointer assumptions for touch |
| Selection | `v_ase/static/selection.js`: `ASESelection`; selection/reference/measurement methods in `v_ase/static/main.js` | Exact replica identity, bulk intent, ordered metrics, picking and visibility |
| Appearance | `v_ase/static/selected_appearance.js`: `SelectedAppearanceEditor`; `v_ase/static/main.js:atomColorScaleSelection` | Transactions, split/merge, frozen targets and table synchronization |
| Scalar infrastructure | `v_ase/atom_scalars.py`; `v_ase/static/atom_properties.js:AtomScalarStore`; `v_ase/static/radius_mapping.js` | Catalog/source/reduction semantics, cache generations, neutral values and radius formula |
| Trajectory | `v_ase/static/trajectory.js`; frame loading/playback in `v_ase/static/main.js`; `v_ase/static/api.js` | Interpolation and coherent commits; provide local adapters for server calls |
| Scientific serialization | `v_ase/serialization.py:atoms_to_json` | Renderer payload fields; note that this payload omits arbitrary array catalogs and raw volumes |
| Scientific kernels | `v_ase/analysis.py`, `v_ase/neighbors.py`, `v_ase/registry.py`, `v_ase/commensurate.py`, `v_ase/polyhedra.py`, `v_ase/volumetric.py` | Numerical reference for offline worker/native/WASM ports |
| Camera | `v_ase/static/main.js`: `setRenderAreaVisible`, `setRenderCameraNavigation`, `viewOutputCamera`, `captureRenderAreaCamera`, `followRenderAreaNavigation` | Visibility/lock/recall/alignment distinction, no-jump transitions and profile synchronization |
| Axis gizmo | `v_ase/static/main.js`: `alignViewToAxis`, `ensureOrientationWidget`, `updateOrientationWidget` | Canonical +/- poses and axes derived from inverse camera quaternion |
| Commands | `v_ase/static/editor_commands.js`, `v_ase/static/editor_interactions.js`, `v_ase/static/ui_activity.js` | Shared command IDs, interaction-layer behavior and activity feedback |
| Workbench | `v_ase/static/main.js:EDITOR_ROUTES`; `v_ase/static/editor_ui.js:WORKBENCH_ROUTES`; `v_ase/static/index.html`, `v_ase/static/editor.css` | Feature inventory/design language; do not reuse the whole desktop DOM uncritically |
| Export | `v_ase/export.py`; image/video/HTML actions in `v_ase/static/main.js` | Formats, exact frame contract, per-frame appearance, stored profiles and encoding needs |
| Desktop-only host | `desktop/main.cjs`, `desktop/package.json`, workspace scripts | Useful lifecycle references, not portable iOS/Android runtime code |

### 10.4 `.vase` reader requirements for the mobile team

`.vase` is a ZIP, not a single JSON scene:

```text
manifest.json
structure.traj                  # ASE ULM binary trajectory
labels.json
frame_info.json
atom_arrays.npz                 # ZIP of NPY arrays
calculator_results.npz          # stored results, not executable calculators
volumetric/....npz              # optional
commensurate_guest.traj         # optional
commensurate_guest_labels.json  # optional
```

ULM frames use binary offsets and can inherit headers from the first frame. NPY arrays have dtype, shape, byte order and storage ordering. The current writer permits numeric/boolean/complex/byte-string/Unicode forms, while safe object-like values can be converted to strings. Do not parse these using unchecked JavaScript Number conversion, especially 64-bit integer IDs. Never execute pickle, constraints or calculator objects.

Validate nested expanded sizes, member count, duplicate paths, traversal, shapes, offsets and supported versions **before allocation**. The desktop's multi-gigabyte limits are not a phone admission policy. Stream a compressed trajectory member into bounded app-cache storage when random ULM reads require it; whole-archive expansion into JS strings is not acceptable.

A future chunked viewer payload can speed new projects, but existing files must work without a forced desktop re-export. Verify source fingerprints and retain authoritative original members; never render a stale derived cache in preference to changed data.

### 10.5 Who supplies what

- **Mobile team:** native hosts, adaptive UI, touch/input, file-provider integration, lifecycle/recovery, local data adapters, performance instrumentation and native packaging.
- **Shared-core/scientific work:** viewer state extraction, file-format conformance, scientific kernels, renderer parity and serialization. Assign named ownership within the implementation project; do not leave this implicitly to a designer or a generic mobile UI contractor.
- **Product owner:** confirms interaction prototype, especially the pan/orbit resolution; supplies/clears brand assets; decides any explicitly proposed scope exception and distribution/licensing choices.
- **QA:** golden files and Python-generated numerical oracles, shared browser tests, physical-device interaction/energy tests, and visual export review.

The team may overlap these roles. A contractor delivering only the native wrapper has not delivered full View parity.

## 11. Performance, interruption and error handling

### 11.1 Required implementation properties

- Draw on change. The existing renderer already coalesces `requestAnimationFrame`; do not replace it with an unconditional 60 fps loop while idle.
- Keep an active frame/ring buffer and bounded property/mesh caches. Share/reuse buffers where safe. Count decoded CPU bytes, GPU buffers/textures, archive extraction and encoder buffers, not just compressed file size.
- Use instanced geometry and spatial acceleration for bonds/picking/selection. Dense-scene touch picking needs explicit testing; a nearest-projected-atom fallback that stops after a threshold cannot be the sole touch usability strategy.
- Keep UI interaction on the main thread light; put decoding and expensive analysis in cancellable workers/native tasks. Bound concurrent jobs.
- Adaptive preview quality may reduce pixel ratio/mesh detail during interaction, heat or low-power conditions. It must not silently change scientific values, requested export dimensions or precision.
- Preflight replication count, atom/bond instances, field resolution, isosurface triangles and output dimensions. Offer a smaller preview or a clear capacity message before allocating unsafe work. Do not omit atoms invisibly.
- Export uses bounded frame queues and frees each completed buffer. Never hold a movie's full set of high-resolution PNGs in memory.
- Suspend inactive documents; pause playback and continuous work when backgrounded/locked. Preserve state and manage approved foreground export behavior explicitly. Do not keep a hidden scientific server alive indefinitely.
- Handle memory warnings, WebGL context loss and WebView content-process death. Persist enough to reopen the original file and recover the last committed view; release/recreate resources cleanly.
- No keep-awake behavior by default. A deliberate presentation/playback option can be considered if clearly scoped and restored on exit.

### 11.2 Loading and errors

Operations that may take noticeable time need immediate acknowledgment, then progress where measurable. Use “Loading properties…”, “Reading frame 12…”, “Computing distribution…” and “Rendering frame 8 of 40…”, not a silent disabled interface. Keep the last valid scene visible while replacement data is prepared.

Distinguish cancellation/supersession, unsupported file feature, corrupt input, absent property, resource limit, permission loss and export failure. Superseded frame requests are normal and should not toast as failures. An unavailable datum is not a zero. A failed write keeps the document dirty and recoverable.

### 11.3 Proposed benchmark envelope

These are validation fixtures/targets, **not existing performance claims**:

| Workload | What must be measured |
|---|---|
| 1,000 atoms with bonds | Input latency, p95 frame time, smooth orbit/selection; target 60 fps on supported reference hardware, allow explicit low-power 30 fps |
| 10,000 atoms with bonds and property mapping | Adaptive rendering, selection/picking latency and memory stability |
| 100,000 atoms or a large field | Correct admission control/degraded preview/refusal; no promise of full-detail interactivity on all devices |
| 100 frames, changing topology and scalar data | Rapid scrub coherence, bounded memory, property persistence and cancellation |
| 15–30 minute playback/analysis | Energy/battery trace, temperature/thermal response, frame times and background behavior |
| 50 document open/close cycles | Resources return to a stable plateau after cache eviction; no accumulating GPU contexts/blob URLs |

Agree minimum supported hardware/OS versions after these measurements and current toolchain review. Report device model, OS/WebView version, scene size, display mode and quality. No universal CPU percentage or memory ceiling proves safety on every phone.

## 12. Developer delivery stages

Each stage must include runnable evidence and identified gaps. Prototype milestones do not permit marketing a subset as the completed app.

| Stage | Required deliverable | Completion evidence |
|---|---|---|
| A. Reference and scope | Pinned source revision; owner-requirement ledger; license/provenance review; prototype plan | Every feature has an owner and status; ambiguous pan mapping visibly flagged |
| B. Native file/view spike | iOS and Android packages opening legacy `.vase`, embedded HTML and lightweight HTML offline | Real-device opening, property fidelity checks and no unexpected network use |
| C. Interaction prototype | Gizmo, tap/box/multi-touch, Pan proposal, orientation button, portrait/right panel, external inputs | Owner can exercise it; all gesture transitions and rotation-lock cases demonstrated |
| D. Shared state and appearance | Selection, label transactions, mappings, trajectories, camera and visual undo | Golden scenarios below pass without stale data or flashes |
| E. Scientific and output parity | Worker kernels, fields/analysis, lossless view-save and required encoders/exporters | Python-reference comparisons, exact exported dimensions/crops and format recovery |
| F. Product polish | Focus, menus, table scrolling, unit layout, theme, accessibility and interruption recovery | Physical-device QA evidence, all repeated owner defects covered |
| G. Optimization and release | Measured support envelope, notices/privacy, signing, docs, beta/store submission | No known release-blocking data loss/scientific mismatch; current store gates cleared |

Do not start with an elaborate new UI before proving legacy-file reading and coherent per-frame property rendering. Do not spend the final week discovering that the chosen shell cannot perform the file, orientation or keyboard workflow.

## 13. Acceptance scenarios and test evidence

### 13.1 Fixture package to prepare

The following are **required future test fixtures**, not files newly delivered with this document. Generate them from the canonical Python implementation and store expected data/screenshots with provenance.

| Fixture | Contents |
|---|---|
| F01 Small periodic molecule | Nonzero cell origin, skew cell, partial PBC, constraints, known direct/MIC metrics |
| F02 Label appearance | Several labels sharing an element, at least 10 label rows, materials/opacities/radii, linked bonds |
| F03 Scalar trajectory | Existence, signed charge, stored force vector, custom scalar, known locked ranges, selected-index scope |
| F04 Variable topology | Frames of 10, 6 and 12 atoms with element changes and missing property values; save also on the short frame |
| F05 Field project | Raw grid, isosurface, plane, units, precision and expected numerical samples |
| F06 Render camera | Nondefault world camera, physical px/Å, visible cell/constraints, non-screen output aspect |
| F07 HTML variants | Full embedded project and lightweight view of the same scene, with missing-data expectations |
| F08 Failure inputs | Truncated/oversized archives, duplicate members, invalid offsets, bad dimensions, malicious HTML script/URL payload |
| F09 Capacity inputs | Medium/large structure, replicated scene, long trajectory and large field with documented decoded sizes |

Include legacy `.vase` versions and files produced by the actual public desktop release, not only files produced by the new mobile writer. An app that can read only its own output has not demonstrated compatibility.

### 13.2 Concrete owner-regression acceptance cases

All cases are required where their source data/capability exists.

| ID | Steps | Pass condition |
|---|---|---|
| SEL-01 | Drag a box around exactly three atoms, then exactly four | Counts/selection appear; no accidental angle/torsion |
| SEL-02 | Activate Measure; tap known atoms in order; clear/undo one pick | Correct ordered direct/MIC values; no hidden reordering |
| SEL-03 | Select a single atom containing `existence` and stored force | Compact readout shows current label, XYZ and those real properties; no obstructive note |
| SEL-04 | Select/deselect repeatedly with panel open and closed | No blank frame, layout shift or camera reset |
| APP-01 | Change color on selected atoms without first naming a label | Free `Element_2`/next label is created once; canvas/table agree immediately |
| APP-02 | Undo the first adjustment from APP-01 | Original group membership and complete appearance restored together |
| APP-03 | Merge selection into an existing styled label; test Yes and Cancel | Yes inherits all destination settings; Cancel changes nothing |
| APP-04 | Apply 1.5× to a 1.20 Å selected label radius | New row is 1.80 Å; global/property factors remain independent; no double multiplier |
| MAP-01 | Capture selected indices for color; select different atoms | Color targets do not change until Use current selection |
| MAP-02 | Choose label scope, change labels/elements/frame topology | Captured indices remain as specified; no silent retargeting |
| MAP-03 | Play F04 through short frame, loop, save on short frame, reopen | Missing indices resume on later frames; scope/range/property preserved |
| MAP-04 | Scrub rapidly while color and radius mapping are active | Latest coherent frame wins; no base-radius flash or stale-catalog toast |
| MAP-05 | Open Property dropdown immediately after load and during playback | Known options/loading state visible; no empty-then-late rebuild closing selection |
| INP-01 | Click/tap cutoff; Command+A and Ctrl+A on Apple hardware; type 2 | Whole value becomes 2 when those chords are delivered, not one digit replaced |
| INP-02 | Edit one cutoff; Tab/Next, Shift+Tab/Previous | Moves between adjacent cutoff values in one action |
| INP-03 | Primary+Shift+B, then 2, Tab, 2 | 2 × 2 displayed supercell; no 12; no source-cell mutation |
| INP-04 | Leave an incomplete numeric draft via Renderer/Atoms shortcut | App handles draft locally/restores last valid value; navigation not globally trapped |
| GST-01 | Start on gizmo, drag outside it and across XYZ targets | Orbit continues; thumb feedback follows; no selection or axis snap |
| GST-02 | Tap each axis, then repeat from exact aligned pose | Desktop canonical alignment/opposite-side behavior; correct axis/up orientation |
| GST-03 | Begin box drag, add second finger, lift fingers in either order | Box canceled; navigation takes over; no trailing selection/tap |
| GST-04 | Orbit, pinch asymmetrically, use proposed Pan toggle, cross a panel | Stable gesture ownership/classification; no unintended mixed operation |
| GST-05 | Cancel via OS gesture/background while dragging | No stuck tool/capture/thumb indicator; next gesture works |
| UI-01 | Open/right-panel resize, portrait sheet detents, select/deselect | Scene/camera unchanged except deliberate navigation or true viewport projection adjustment |
| UI-02 | Scroll label/bond table vertically/horizontally with 10+ labels | Header flush at top, pinned identity visible, no rows above header or wrapped four-line entities |
| UI-03 | Narrow window, large text, keyboard open, long units/property names | No overlap/clipping; focused control and Done/Next reachable |
| UI-04 | Open Search, then another menu; mouse-hover between open menu triggers | Correct exclusive popover/menu and focus behavior |
| UI-05 | System theme changes, then manual theme override | Chrome follows intended preference; scientific/export colors remain unchanged |
| CAM-01 | Toggle camera through viewport, Renderer and Objects | All visibility/active states agree; off clears lock/selection without erasing camera |
| CAM-02 | Enable viewport lock after careful framing, then disable | No framing/px-per-Å jump from the toggle itself |
| CAM-03 | Under lock, press XYZ or tap axis | Render Area visible and correct in the immediate resulting frame |
| CAM-04 | Select camera; G/R/S or touch equivalents; cancel each | Correct full-scene composition including cell; Cancel restores pose and scale |
| CAM-05 | World-fixed mode: orbit/pan/zoom; recall camera | Output camera unchanged; recall fits usual usable work area |
| CAM-06 | View camera off-axis through dense geometry and grid | Camera orientation understandable; no white masking, missing atoms or finite grid edge |
| OUT-01 | Render same camera to image and movie/GIF frames | Exact dimensions, same crop, colors/radii/object visibility; no PNG-size mismatch |
| OUT-02 | Export selected frame range and GIF once/forever | Correct first/last frame/count/order/FPS and verified loop metadata |
| OUT-03 | Flat mode with fixed atoms; turn Constraints off; export | Sharp crosses when on, absent when off; ineffective material/light controls disabled |
| FILE-01 | Open project on empty app, then with another document open | No nonsensical Replace prompt; new document preserves saved presentation |
| FILE-02 | Save HTML, cancel an unrelated image export, Save again | Remains HTML with its profile and recovery content; no target reset |
| FILE-03 | Save As cancel/fail; close dirty document and cancel picker | Existing target/work intact, document remains open and dirty |
| FILE-04 | Native provider grant lost or source externally changed | Clear recoverable error/conflict; no hidden write to a different path |
| FILE-05 | Install app; inspect `.vase`, HTML, JSON, ZIP associations | Only `.vase` is owned; explicit HTML import still works |
| ROT-01 | Portrait lock on/off; enter landscape fullscreen and exit on phone | Native request works on supported configuration; prior state/policy restored |
| ROT-02 | iPad/Android split-screen, resize/fold/unfold; open keyboard | Valid adaptive UI; no data reset or fake forced window rotation |
| LIFE-01 | Airplane mode, suspend/resume, kill WebView/context, reopen | Supported local operations work; recoverable view/session restored |
| PERF-01 | Run workload/long-playback/open-close matrix | Measured stable memory, bounded work, no silent data reduction and documented capacity behavior |

### 13.3 Scientific equivalence and test tooling

Use the canonical Python reader/kernels to produce reference values; do not compare two implementations sharing the same mistaken test formula. Cover skew/partial PBC, direct/MIC metrics, cell origins, labels/elements, arbitrary properties, radius factors, distributions, fields and unsupported-data handling.

Source bytes/typed data should round-trip exactly where the format promises it. For numerical ports, define per-operation tolerances from input precision and algorithm; do not declare an arbitrary screenshot tolerance sufficient for scientific correctness. Screen/GPU precision is not source-data precision.

Existing starting points include `tests/test_html_export.py`, `tests/test_project_consistency.py`, `tests/test_analysis_field_audit.py`, `tests/test_rdf_analysis.py`, `tests/test_registry_analysis.py`, and camera/property-frame browser regressions. Reuse them as references and add local-provider coverage; do not silently mark unavailable mobile paths skipped and call the suite green.

Use:

- unit tests for document parsing, reducers, commands, scope/undo state and worker cancellation;
- pytest reference fixtures for numerical and format equivalence;
- browser automation for shared renderer/UI/layout tests;
- native iOS/Android tests for file delivery, grants, rotation, lifecycle and keyboard routing;
- physical-device manual/automated multi-touch, GPU, visual and energy checks.

Device matrix must include a supported older/smaller iPhone, a current iPhone, iPad in full/split windows, a midrange Android phone, a current Android phone, and a Samsung Galaxy Tab or equivalent Android tablet. Include current/minimum supported OS, dark/light, portrait/landscape, software keyboard and external keyboard/mouse. Emulation alone is insufficient.

For each acceptance case record build revision, device/OS, fixture hash, steps, expected/actual result and screenshot/video or numeric evidence. Inspect actual exported files in a decoder/viewer. A successful HTTP/bridge response or a green uninspected screenshot capture is not a pass.

## 14. Distribution and handover checklist

### 14.1 Rights and store gates

The repository is AGPL-3.0-or-later; removing Python does not remove the license from reused JS. Determine rights to reuse/distribute the mobile core and whether an additional license/permission is required for the intended App Store channel. Do not relabel third-party/contributor code without authority. The [FSF's historical App Store licensing discussion](https://www.fsf.org/blogs/licensing/more-about-the-app-store-gpl-enforcement) identifies a compatibility issue to review against current agreements, not a complete current legal conclusion.

Audit notices/rights for Three.js, file readers, scientific libraries/tables, colormaps, codecs, icons/fonts and examples. The owner wants the castle to remain central in the app icon, with the red base removable and the small character secondary; use the approved asset/provenance rather than inventing a new identity. App and document icons should be distinguishable, and all artwork must have appropriate distribution rights. An AI edit or user attachment does not automatically establish those rights.

Apple Distribution/provisioning, App Store Connect and TestFlight are separate from the existing macOS Developer ID/notarization process. Android needs its own package/signing/Play workflow. Bundle trusted executable code and treat imported documents as data. Review current [Apple review guidelines](https://developer.apple.com/app-store/review/guidelines/) and current Google Play requirements before submission.

Default to local processing without analytics, accounts or automatic uploads. Declare actual data/SDK behavior accurately, provide privacy policy/support information, and meet territory/trader/age-rating requirements. Do not promise approval in every country simply because distribution is set to worldwide.

### 14.2 What a completed handover must contain

- [ ] Source revision and reproducible iOS/Android build instructions, dependency lockfiles and third-party notices.
- [ ] A checked capability ledger: complete, data-unavailable by design, or an explicitly approved exception. No vague “mostly works” rows.
- [ ] Approved touch prototype decisions and final gesture/state diagrams, including Pan/orbit resolution.
- [ ] File-format reader/writer conformance tests and golden fixture package.
- [ ] Visual-state/undo/camera invariants with automated regressions for the owner's repeated defects.
- [ ] Real-device test report and exported output samples, including energy/memory observations.
- [ ] File association, HTML import isolation, native grants and recovery verification.
- [ ] English in-app help: opening supported files, gizmo gestures, selection/Measure, Pan, landscape fullscreen, save vs copy, missing-data messages and hardware shortcuts.
- [ ] Concise user documentation and meaningful examples. The owner explicitly disliked long Save/Share prose and decorative demos with no scientific purpose; put detailed engineering instructions in developer docs, not the everyday user flow.
- [ ] App Store/Play metadata, screenshots, privacy/support links, rights clearance, beta results and signing/release notes.
- [ ] If shared desktop behavior changes, updated README/canonical skill/references, required regenerated examples and full release checks under `AGENTS.md` and `docs/release_checklist.md`; desktop/Jupyter regression evidence.

No public mobile release should claim completion while data fidelity, normal gesture behavior, exact rendering or safe document saving remains unverified. The owner's quality expectation is a coherent scientific application with polished everyday interactions—not a collection of individually callable functions.
