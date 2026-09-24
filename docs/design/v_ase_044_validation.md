# v_ase 0.4.4 validation record

## Scope and implementation

This candidate addresses the seven follow-up requests concerning colorscale
scope, variable-count trajectories, atom-property readouts, property discovery,
Render hierarchy, independent physical output cameras, and navigation shortcuts.

| Requirement | Implementation | Regression evidence |
| --- | --- | --- |
| Clear color targets | `main.js` colorscale scope handler and `syncAtomColorScaleControls`; Selected atoms, label snapshots and Use current selection | Label targets capture base indices, live selection is independent, manual bounds survive retargeting |
| Variable topology | `setAtomsData` distinguishes frame navigation from explicit topology edits; `reconcileDesignDisplay` preserves absent indices; server trajectory-range scan | 3→1→3 and 4→2→4 atom-count/element changes; short-frame coordinate edits preserve absent indices; project settings and all-frame bounds |
| Offline target parity | `export.py::_html_atom_color_scale_frames` uses saved colorscale indices, with legacy selection fallback only when absent | HTML targets differ from live selection and retain the intended scope |
| Visible atom data | `singleSelectionPropertyLines` and `updateSelectionMeasureUI`; scrollable bottom readout, custom arrays first | Existence is visible for one selected atom; Shift-click passes through the readout for deliberate measurements |
| Fast field discovery | `ensureAtomScalarCatalog` preloads metadata separately from Matplotlib palettes; option-node memoization | Choices exist before enabling mapping and unchanged catalogs preserve option nodes |
| Render hierarchy | `index.html` and `editor.css`; Output frame & scale first, nested Output camera, separate Lighting/Quality/Overlays | Desktop and narrow screenshots; input/unit containment and route visibility checks |
| Independent camera | `viewOutputCamera`, fixed/follow state, projected output plane and editor-only wheel zoom | Orthographic and perspective fitting, axis views, unchanged exact exported PNG and physical output settings |
| Video camera parity | `exportTrajectoryVideo` uses `aiEffectiveRenderSnapshot` and reports its camera | Decoded default GIF matches saved-camera PNG within palette quantization; independent evaluator default/explicit GIF hashes identical |
| Shortcut recovery | `commitInputValue` restores invalid drafts for route changes; strict Save/commit guards remain | Command+Shift+P/A with negative output scale, unchanged saved value, invalid Save rejected |

Primary new regressions are in
`tests/test_browser_camera_property_persistence.py`. Existing scientific,
trajectory, deliberate measurement, native-file, project, HTML, notebook,
MCP/CLI, renderer and layout tests remain required.

## Fresh-context canonical Skill evaluation

The release-checklist evaluator used only the canonical Skill/references,
discovered public schemas, MCP/HTTP/CLI and normal GUI actions in its own session.
It verified variable count/element scopes, physical edits and constraints, exact
PNGs, camera separation, project contents, human events, stale-revision rejection
and actual GIF frames. Its GIF mismatch exposed a default-camera export defect;
the corrected default and explicitly specified camera GIFs then had identical
SHA-256 `684739508ac8f6d5c3bb2c03e1309c7c7e377101151881cdb14bf94dd7639cec`.
It also found GUI scope changes resetting manual color bounds. This was fixed
and verified with a real-browser label/retarget regression after the evaluation.

Recorded calls: 64 (55 MCP, 8 HTTP, 1 CLI); serialized response bytes: 688,609;
summed application-call duration: 17.1181 seconds; elapsed evaluation: about
884 seconds. Provider token counts were unavailable, not estimated. Two typed
errors were an initial installed-runtime contract mismatch and intentional stale
revision rejection. Paired checkout GUI/MCP runtimes resolved the first.

This bounded evaluator did not exercise every analysis or external renderer;
the complete repository suite remains necessary. Browser Use blocked its HTML
file URL and prohibited workarounds; none was attempted. That evaluator's HTML
visual acceptance is unverified. Independent repository HTML browser regressions
are a separate release gate, not evidence that the policy restriction vanished.
Raw local evidence is `/tmp/vase-044-skill-evaluation/`; it is not a public asset.
The evaluator ran before the version bump and correctly reported the checkout
as 0.4.3 rather than claiming to test a published 0.4.4 wheel.

## Completed local gates and remaining release prerequisites

- Focused regressions and the evaluator's corrected GIF checks passed.
- An intermediate full run had 1,051 passes and one intermittent marquee-test
  timeout. Event/hit-target tracing showed the test began while the startup
  busy overlay still covered the canvas. The test now waits for the overlay to
  disappear. The final full run passed **1,052 tests**, with **no failures or
  skips**, in 561.89 seconds. The 279 warnings are upstream deprecations.
  Log: `/tmp/vase-044-final-verification.log`.
- All README media were regenerated and GitHub copies synchronized. Logo,
  constraint, measurement, field and colorscale images, and representative
  ribbon/colorscale animation frames were inspected visually. Groups captured
  before the metadata bump were recaptured to make their visible headers 0.4.4;
  the interactive logo was also rebuilt with final version metadata. Post-capture
  asset/document checks passed: 25 static/build checks plus one recording-browser
  check rerun with Chromium launch permission (26 total).
- Strict Sphinx HTML passed. Eight pages at 1440/390 px had no horizontal
  overflow; search and interactive logo controls passed. Linkcheck completed
  with exactly five expected 404s for the unreleased 0.4.4 release/download URLs;
  all other links resolved after GitHub rate-limit backoff. Recheck those five
  URLs after publication; linkcheck is not yet a passing release gate.
- Desktop Node tests: **9 passed**. Canonical Skill checks: **28 passed**.
- Isolated wheel/sdist build and `twine check` passed; distribution content
  matches source and excludes unrelated untracked work. The initial build
  without isolation used an older shared setuptools and failed on the existing
  license metadata; isolation used the repository-required build dependencies.
- On 2026-09-24, after unlock, the complete native Apple-silicon development
  smoke passed: all ten document/settings commands, invalid-field navigation,
  Ctrl+A numeric selection, cutoff Tab order, native Save/Save As, HTML profile,
  drop/open, detached-window transfer and rollback, independent close, Quit
  cancellation, 800×600 nonblank rendering and 69 route/width geometry checks.
  Actual workspace and render screenshots were inspected. Evidence:
  `/tmp/vase-044-native-final/`. The earlier interrupted run remains excluded.
- A fresh temporary environment installed the local candidate wheel and all
  declared dependencies: `pip check` and `v_ase --version` passed. Its installed
  GUI/CLI verified variable-count saved scopes, exact 640×480 PNG, 320×240
  five-frame play-once GIF, served canonical Skill parity and stale-revision
  rejection. Actual PNG output was visually inspected. Evidence remains in
  `/tmp/vase-044-wheel-verification/`; the disposable environment was removed
  after verification to recover disk space. This is not a published-wheel check.
- The tested Python distributions were published on 2026-09-24. GitHub and
  PyPI expose identical wheel/sdist hashes. A clean environment installed the
  actual published wheel and repeated the GUI/CLI property, PNG/GIF, served
  Skill and stale-revision checks successfully; see the release validation
  archive's `published-wheel/` evidence.
- All three native and packaged desktop CI targets passed at
  `c46ec4acb0c84c3dd3ec479ce6ee97ee62bced35`: Apple silicon, physical Intel Mac
  and Windows x64. Each run passed all ten document/settings commands and 69
  panel/width checks. Windows installation/uninstallation also preserved
  existing structure-file defaults. Actual packaged screenshots were inspected.
- Read the Docs `latest` and `v0.4.4` builds passed at the release commit. Public
  installation/property/render pages, search indexes, PDF and EPUB downloads
  were verified. The `stable` channel remains inactive.
- The maintainer installed the notarized Apple-silicon DMG through Finder.
  The installed `/Applications/v_ase.app` reports 0.4.4, passes strict deep
  signature verification and Gatekeeper's Notarized Developer ID assessment,
  and contains all 100 scientific/GUI package files byte-for-byte identical
  to the published wheel. An earlier agent-initiated bundle replacement was
  denied by macOS and temporarily left the old installation incomplete; the
  user completed the normal DMG replacement and the repaired installation was
  verified before the temporary recovery backup was removed.

## Release promotion

The initial lock-screen blocker was resolved; the final development smoke
passed on 2026-09-24. The tested core is published and all three packaged CI
jobs passed. Mac signing/notarization and final public-desktop verification
follow `desktop/README.md`; those remaining gates are recorded below only
after completion. Unrelated untracked research and evaluation work is preserved.

- [GitHub release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.4)
- [PyPI package](https://pypi.org/project/v-ase-gui/0.4.4/)
- [Cross-platform desktop CI](https://github.com/lgyEthan/v_ase/actions/runs/35939857270)
- [Versioned installation guide](https://v-ase.readthedocs.io/en/v0.4.4/desktop.html)
