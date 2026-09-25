# v_ase 0.4.7 validation and release record

Date: 2026-09-25. This release implements the live appearance, footer,
Supercell-entry, camera-lock, render-area, object-visibility, flat-rendering and
activity-feedback follow-up. Unrelated local scientific-study files are excluded
from the release.

## Implemented behavior

| Request | Implementation and regression evidence |
| --- | --- |
| Remove redundant material section | `index.html` retains material in the per-label table and selected appearance; `main.js` binds those controls. |
| Live selected appearance | `selected_appearance.js` owns immediate label assignment and shared table styles. First appearance edit allocates the next unused chemical-element suffix. Explicit label commit separates immediately. Existing-label merge confirms and inherits resolved color/radius/material/opacity/visibility and label bond settings. Numeric label radii absorb per-index multipliers. The first split and input gesture share one Undo entry. |
| Preserve scientific identity | `server.py` validates and commits batched label assignments with one history snapshot. Across trajectories, only indices present in each frame change. Mode snapshots update only changed labels/elements, preserving other frames' chemistry. View-only identity continues its existing frame-scoped override semantics. |
| Single-atom footer | Current label, displayed Cartesian XYZ, custom properties and stored forces appear in the status strip. No floating single-atom note, element/mass/fractional boilerplate or duplicate selection banner. The complete atom-properties API remains available. |
| Supercell entry | Command/Ctrl+Shift+B selects all text in the first field synchronously; actual key-input tests enter `2 Tab 2` without appending to `1`. |
| Camera lock and camera view | World and Viewport are mutually exclusive. The camera-view icon sits beside axis views and preserves the lock. World orbit deactivates it; pan/zoom retain alignment. Align camera to current view is a separate deliberate operation. |
| Stable render area | Viewport-locked camera G/R/S keeps the frame stationary while the surrounding scene moves. Orthographic and perspective tests verify all three operations, cancellation, immediate X/Y/Z updates, stored-camera output and exact project reopening. |
| Clear camera object | Oriented wire camera and angle arc replace the eye. The outlined render plane never covers atoms with an opaque fill. The bordered Camera badge is selectable and stays reachable when a crop extends outside the canvas. Objects can hide the camera/area. |
| Initial composition | New scenes account for the inspector width once. Toggling/resizing the inspector does not change the camera. Saved/user-adjusted viewpoints retain their physical magnification and composition. |
| Flat rendering | Fixed-atom X uses crisp signed-distance rectangles with antialiased edges and square ends. Material and lighting controls are disabled in 2D, including image/video dialogs, while stored 3D settings are preserved. |
| Shared object visibility | Constraints has an independent visual toggle; physical enforcement is unchanged. Grid/axes/cell/bonds/constraints visibility applies to image and animation. Committed GUI export guide choices synchronize with Objects; native per-export omission stays scoped to that export. |
| Loading feedback | Per-section activity counters cover scalar catalogs, radius/colorscale fitting and mapping, analyses, forces and volumetric generation without blocking focus/navigation. |

## Additional regressions found during validation

- Existing-label merge must resolve target defaults before inserting a different
  element. Otherwise the lowest-index new member changes the original members'
  fallback color/radius. Explicit inherited settings now freeze those defaults.
- Undo baselines omit unnecessary default material entries, avoiding a spurious
  dirty/history difference after a complete undo.
- Force display restored by `applyDesignSettings` now loads the current frame.
  The independent native evaluator reproduced scene-patch timeout/rollback and
  verified the fix for both force-only and frame/selection/force transactions.
  `test_scene_force_visibility_loads_and_settles_current_frame` uses real stored
  SinglePointCalculator forces and checks readiness, frame, values and arrows.
- Saved image guide choices no longer revert to previous Objects values.
  Capture/profile/preview equality remains an exact regression assertion.
- Logo capture explicitly records its publication camera after aligning +Z;
  the new editor's initial left offset must not enter the standalone logo.

## Verification evidence

- Focused new browser regressions: live labels/appearance/merge/Undo in View and
  Edit; mixed-element/collision/variable-frame labels; camera G/R/S and all axis
  keys; footer properties; delayed loading; flat controls; PNG/GIF visibility.
- Mac arm64 Electron smoke: ten commands, native key input, Control+A in numeric
  fields, vertical cutoff Tab, native Save/Save As, HTML/project profiles, OS
  dropped-file grants, detach/save/rollback, independent windows, dirty-close
  cancellation and last-window exit. All 69 layout checks at 1440/1024/390 px
  pass. The final smoke was repeated after the force/export fixes and passed. An earlier run was interrupted by inspection input and is excluded.
- Desktop Node authority/lifecycle tests: 13 passed.
- All README media regenerated and GitHub copies synchronized. Logo,
  constraints, scalar mapping, volumetric output and representative twist/plane/line/colorscale animation frames visually inspected.
- Strict Sphinx HTML build passed. Home, quick start, appearance, API,
  troubleshooting, development and desktop pages checked at desktop and
  390 px: no page-width overflow. Code-copy buttons, version, navigation,
  Edit-on-GitHub targets and interactive +Z logo checked.
- Fresh canonical-Skill-only evaluator: all 70 focused operation contracts
  audited and all 13 export families invoked. Scientific edits, constraints,
  camera invariants, exact PNG/GIF, frame-specific properties, project roundtrip,
  same-document human events and stale-revision rejection passed. Supplementary
  native/MCP/HTTP regression subset: 59 passed; final Skill subset: 28 passed.
  Metrics: 138 native calls / 286,644 response bytes / 49.63 summed seconds;
  58 CLI calls / 521,595 bytes / 41.70 summed seconds. Provider token counts were
  unavailable and are not estimated from bytes.
- Independent evaluation limits: not every operation lifecycle or desktop,
  notebook and remote scenario was manually replayed. CUA policy prevented that
  evaluator's `file://` HTML inspection; offline HTML coverage comes separately
  from the repository browser regressions. No claim of exhaustive manual QA.

- Final independent 0.4.7 follow-up: World and Viewport native camera edits,
  exact same-size rollback, smaller-viewport Undo/Redo, actual GUI S=1.5,
  `.vase` reopen and sixteen nonblank 512×384 renders passed. Saved render
  cameras and corresponding output pixels were identical. Measured scale
  agreed within 0.001 px/Å. Canonical parity: 28 passed. Final scenarios:
  92 native calls / 341,320 response bytes / 6.732 summed seconds; provider
  tokens unavailable. This was Chrome resize/project replay; native Windows
  detach remains a separate desktop CI gate.
- The final local wheel passed an isolated GUI/CLI workflow with real stored
  forces, constraints, scalar color/radius, exact PNG and animated GIF, native
  project reopening, stale guards and served Skill.

## Patch release rationale

The initial Windows desktop CI for 0.4.6 detected a real magnification change
when the operating system constrained the detached window height. The extra
history camera restore overwrote the physical scale already restored from the
document. No desktop 0.4.6 installer was promoted. The Python distributions are
immutable, so the correction is delivered as 0.4.7, with new regressions for both
camera locks and scale Undo/Redo after resizing. The history restore now guards
camera-follow callbacks for its entire transaction. A supplementary native-tool
audit also found the same resize assumption in the independent AI scene runtime
restore. It now stores viewport dimensions and measured scale, preserves exact
same-size rollback, and adapts the working camera at a different size without
altering the saved render camera. A native Undo/Redo regression covers this path.

## Release gates

- [x] Final full regression suite: 1,094 passed (1,075 behavioral tests in 615.36 s plus 19 synchronized asset/version tests).
- [x] Patched-source wheel/sdist build, `twine check`, and package-content equality (103 package files).
- [ ] Same tested version published to PyPI and GitHub main/tag.
- [ ] Clean published-wheel GUI/CLI workflow and served canonical Skill.
- [ ] All three native/packaged desktop CI targets.
- [ ] Both Mac architectures Developer ID signed, notarized and stapled;
      packaged smoke, all native-component verification and Gatekeeper checks.
- [ ] Public installers, ZIPs, source, signing evidence and final checksums;
      re-download verification. Windows unsigned status remains explicit.
- [ ] Published Read the Docs version/latest and final strict linkcheck.

Final public artifact evidence belongs to the
[0.4.7 release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.7).
