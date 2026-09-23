# v_ase 0.4.3 validation record

## Scope

This release addresses the requested document/app icon distinction, Open With
registration, property controls and frozen color targets, atomic trajectory
updates, first-open behavior, compact label tables and panel hierarchy, an
editable output-frame guide, exact Retina video dimensions, inclusive video
ranges, and animated GIF playback. It also fixes the reported inset Relaxation
table header and applies flush, opaque, locally sticky headers to the label and
bond tables.

## Implementation and regressions

| Area | Implementation | Verification |
| --- | --- | --- |
| Desktop file types | `desktop/file-formats.json`, `package.json`, generated NSIS registration, distinct document assets | Node association tests; packaged Mac plist/resource checks; Windows CI install/uninstall checks preserve existing structure defaults |
| Property UI | `static/index.html`, `editor.css`, `main.js` appearance rows and scalar controls | Compact one-row geometry; horizontal scroll; all routes at desktop/narrow/mobile widths |
| Frozen colors | Explicit selection snapshots and provenance remapping | Selection changes do not recolor different atoms; explicit reapply changes targets; saved settings retain indices |
| Frame presentation | Serialized `loadFrame` commits and renderer frame transactions; bounded shared scalar caches | Delayed scalar requests and rapid scrubbing never present unmapped radii or stale colors |
| Frame edit persistence | Position-cache generation invalidation on committed edits/refresh | Warm and late pre-edit caches; physical move, frame roundtrip, animation export, decoded `.vase` coordinates |
| Output frame | Existing canvas projection and picking; DOM crop guide | One scene render per viewport frame, stable gate with floating inspector, saved-camera alignment |
| Video | Fixed capture framebuffer, range validation and interpolated scalars | Actual Retina 1920×1080 PNG uploads and decoded MOV; GIF/AVI exact dimensions/frame counts/endpoints |
| GIF | FFmpeg per-frame palette, loop=0 or no loop extension | Decode both modes, verify durations and frame counts; selected source range interpolation |
| Project settings | Persist confirmed video profile; reopen replaces canceled draft | Real `.vase` save/load restores GIF, FPS, inclusive source interval and loop choice |
| Table headers | No inner table padding; opaque sticky headers at top:0 | 1440/390 px, scroll offsets 0/75/150, geometric edge alignment and top-pixel hit testing; inspected screenshots |
| Native workflow | Shared browser UI inside Electron | Native Mac key input, Ctrl+A numeric selection, cutoff Tab order, safe Save, tab/window transfer, Quit cancellation, exact nonblank PNG and 69 route/width checks |

Focused tests are in `test_browser_property_frames.py`,
`test_browser_ui_geometry.py`, `test_video_export.py`, `test_agent_skill.py`, and
`desktop/test/file-associations.test.cjs`. Existing scientific, project, notebook,
HTML, MCP, CLI, selection and renderer regressions remain required.

## Fresh-context canonical skill audit

The evaluator used only the canonical Skill/references, focused discovery and
CLI/HTTP bridge in a separate six-frame document. It verified selected scalar
styles, constraints, camera direction, exact PNG, human GUI revision events,
stale revision rejection, GIF once/repeat, seven-frame AVI/GIF subsets, and
project/HTML contents. It exposed the physical frame-cache regression and stale
schema wording; both were corrected with regressions before release.

Recorded API/CLI calls: 71; response bytes: 493,632; request time: 31.115 seconds;
elapsed evaluation time: 844.69 seconds. Provider token fields were unavailable.
The evaluator's exported HTML could not be opened because its browser tool
blocked file URLs. Static HTML/project/poster inspection succeeded; independent
repository HTML browser regressions remain the execution gate. Later human
interaction with that evaluator's GUI was preserved and excluded from its clean
initial evaluation. Its session was not closed automatically.

Raw local evidence is under `/tmp/vase-043-skill-evaluation/`; these paths are
maintainer-local, not release assets. The final desktop release carries public
platform validation and signing evidence as specified in `desktop/README.md`.

## Release gates

- Core suite: **1,030 passed** in 621.03 seconds. The 273 warnings are upstream
  deprecation warnings. Asset consistency ran after the final capture, with
  **13 passed**: **1,043 tests passed** in total, no failures or skips.
- Desktop Node tests: **9 passed**. Native Apple-silicon development smoke passed
  all commands, file handling, window transfer, numeric input and 69 layout checks.
- Regenerated all README example groups and synchronized GitHub assets; visually
  inspected the logo, ribbon, constraints, measurements, scalar colors and fields.
- Strict Sphinx HTML build passed. Eight manual pages at 1440 and 390 px had no
  horizontal overflow; interactive logo controls and search passed.
- Wheel and sdist build and `twine check` passed. The sdist contains documentation,
  selected rendered assets and the canonical Skill; unrelated untracked work is
  excluded from the clean source snapshot.
- Published-wheel verification, cross-platform packaged CI, Mac signing and
  notarization, and public download checks are separate promotion gates. Their
  results are recorded in the release's public validation and signing artifacts.
