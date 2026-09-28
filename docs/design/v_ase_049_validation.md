# v_ase 0.4.9 implementation validation

## Scope

The release fixes live selection/constraint visibility, Windows panel scrolling
and compact/high-DPI layout, placement-to-relaxation flow, and restoration of the
starting optimization structure. It adds Blender water-surface geometry export.
Windows publisher signing is documented but remains disabled.

## Completed source checks

- Full Python/browser/transport/notebook suite: **1,150 passed**, 774.36 seconds.
  Warnings were dependency deprecations; no skipped or failed tests.
- Focused final browser/packaged-evidence regressions: **79 passed**.
- Electron Node lifecycle/file-authority tests: **13 passed**.
- Source Windows runner: [36426023011](https://github.com/lgyEthan/v_ase/actions/runs/36426023011),
  source application commit `c4e527b57643962caebb427d19dbe0cabf33f3c7`.
- Actual Electron mouse drag and per-label checkbox selection produced yellow
  outline pixels in both 2D and 3D with scientific overlays disabled. Constraint
  toggles changed rendered pixels without modifying the physical constraints.
- Windows and Mac native checks passed 75 route/layout combinations, ten native
  commands, editing/select-all/tab traversal, native Save/Save As, dirty closure,
  multi-window transfer/rollback, file grants, HTML/project recovery and isolation.
- At 100%, 125% and 150% native zoom, Place Molecules has exactly one vertical
  scroll ancestor and passes a real element hit test. Route navigation's deferred
  scroll is allowed to finish before scrolling to the action.
- Windows CI uses software graphics. These checks do not establish compatibility
  with every physical Windows GPU/driver or every OS accessibility setting.
- Strict Sphinx HTML build and desktop/narrow inspection passed across 18 page/
  width combinations, including API/CLI reference, navigation and search.
- README images/animations were regenerated with the repository capture script.
  The collaboration capture explicitly requests browser mode because it requires
  a workspace child frame, independently of notebook autodetection.

## Independent canonical-Skill evaluation

A fresh evaluator used only the canonical Skill, public schema/capabilities,
MCP/native functions, HTTP JSON commands and CLI; it did not edit implementation.
All **70 operations**, **13 exports** and **seven state profiles** passed their
recorded smoke/content checks. The run made 593 application calls (499 native,
86 HTTP, eight CLI), totaling 1,799,680 serialized response bytes in 32m 35.7s.
Provider token fields were unavailable and recorded as null. This is operation
coverage, not exhaustive validation of every option combination.

The evaluator found and independently verified corrections for:

1. Clear-to-initial in an active Add Atoms session being rejected by the mutation
   allow-list. Both general relaxation and placement now retain the intended
   mode, exact initial coordinates, atom count and constraints.
2. Semantic isosurface enablement not synchronizing renderer visibility, leaving
   capture readiness false. Combined signed Cube surfaces and section planes
   now produce the expected nonblank, exact-size image.
3. A refined water mesh surviving an empty source. Empty frames now have zero
   rendered triangles and restore the appropriate atom representation.
4. Placement-region guides leaking after relaxation → clear-to-initial → region
   edit/scale → Finish → project replacement. The corrected reproduction renders
   pixel-identically to a clean session (zero changed pixels). Guides are also
   excluded from image/movie capture and restored in the active editing view.

Forty-two exported artifacts passed SHA-256 verification. Real Blender 5.0.1
executed the generated script, rendered the water mesh and played through
changing topology/no-water frames. Repeated script execution leaves one current
water mesh and one handler per feature. Separate automated tests compare Python
and JavaScript physical mesh vertices/normals and periodic scope. Modeling-light
appearance is renderer-dependent; no photometric identity is claimed.

Offline HTML was reopened with JavaScript both disabled and enabled, at mobile
and desktop dimensions, with zero external network requests. The poster/first
WebGL frame, view navigation, playback, project recovery, stale-revision guards,
wrong-document guards and human-to-agent collaboration were checked.

## Distribution evidence

The release process must additionally require wheel/sdist `twine check`, clean
installed-wheel verification, all three packaged desktop jobs, signed/notarized
Mac arm64 and x64 re-tests, Windows install/uninstall association checks, public
asset re-download verification, and successful versioned Read the Docs builds.
Those final results and their exact build commit are recorded in the release's
`desktop-validation.zip`, `desktop-signing-validation.zip`,
`mac-notarization.json` and `desktop-SHA256SUMS.txt`; source checks alone must not
be presented as completed distribution verification.
