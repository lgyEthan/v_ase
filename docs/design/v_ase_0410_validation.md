# v_ase 0.4.10 implementation validation

## Accepted visualization

The user chose the expanding-ring comparison. Unselected FixedPlane annuli use
inner/outer radii 1.00/1.48 times the live atom radius; selected annuli use
1.18/1.66. Face width, edge thickness and face opacity (0.30) are unchanged.
Hover reveals the dashed normal and X endpoints without expanding the ring.
Depth testing preserves front/back relationships with atoms and yellow selection
shells in 3D and flat 2D. Hidden-selection publication capture uses the ordinary
ring, while interactive scenes retain selection expansion. Atom radius and
position interpolation update marks without generating new geometry per atom.

## Source checks

- Full Python/browser/transport/notebook suite: **1,158 passed**, 697.45 seconds; no failures or skips.
- Six focused FixedPlane browser regressions pass. Checks include actual pixels,
  arbitrary plane normals, annulus face/rims, selection/hover/deselection,
  publication export, moving atoms, scalar radii, zero-radius hiding and cached
  geometry for 256 constrained atoms.
- Electron Node lifecycle/file authority tests: 13 passed.
- Native Mac source smoke passed 75 layout routes and ten native commands,
  selection/constraint pixels in 2D and 3D, native Control+A and Tab, native saves,
  dirty closure, detached document transfer, cancellation and rollback.
- Windows source CI: [36543437735](https://github.com/lgyEthan/v_ase/actions/runs/36543437735),
  implementation commit `84911daf6a7b2cd0e93c34e4371f87d529863f8b`, passed.
- Strict Sphinx HTML and 16 desktop/narrow page-width checks passed, including
  navigation, search, examples, and Edit-on-GitHub targets. Prepublication
  linkcheck found only the five not-yet-published 0.4.10 release/download links;
  final linkcheck is required after asset publication.
- README images and animations were regenerated with the canonical capture
  script and synchronized into docs/assets/github. Water animation/poster
  capture is now part of that script; the poster is animation frame 12.
- Exact scientific package files in the final wheel match the source. Wheel and
  sdist pass twine check; the sdist contains documentation sources, selected
  figures, and the canonical Skill while excluding internal design records.
- A clean installed-wheel CLI/browser workflow passed constrained edits and
  Undo, three-frame properties/forces/radii, exact 480x360 PNG, five-frame GIF,
  project roundtrip, stale-revision rejection and canonical Skill serving.

## Defects found by release validation

- The Orbit toolbar button had not started a controls gesture on primary drag.
  It now rotates, with Shift-drag for pan; a real pointer-drag regression covers it.
- The commensurate-rotation focused/native axis schema incorrectly advertised
  a vector. It now advertises the actual global-Z string contract, with valid
  Z/z and invalid vector/X/Y/ALL regression cases.
- Explicit commensurate guest indices did not synchronize the selection. A
  later style/camera patch could dismiss the proposal. Explicit indices now
  select the guest, and the exact combined display/camera fit has an HTTP test.
- A short rigid translation optimization could expose a mixed status/running
  snapshot across HTTP and worker threads. Summary reads now share the existing
  optimizer lock. A deterministic concurrent-reader regression proves that
  half-completed updates cannot escape; browser lifecycle coverage also passes.

Early full-suite attempts caught an in-progress asset capture, a schema edit
made while tests were running, and the actual optimizer snapshot race above.
The final full suite ran after source and captured assets were frozen.

## Fresh canonical-Skill evaluation

A fresh evaluator used only the canonical Skill, focused public schemas, native
MCP, CLI and HTTP contracts, plus visible same-document human GUI refinement.
All 70 operation names and 13 export types executed successfully, and 24/24
independent scientific assertions passed. Both the axis-schema and explicit
commensurate guest defects were independently retested after correction.

The evaluation recorded 447 instrumented calls, 9,178,364 serialized response
bytes and 64.900 cumulative call seconds (not full evaluation wall time).
Provider input/cached-input/output/reasoning/total token counts were unavailable
and recorded as null. Coverage means at least one valid route per operation and
export, not every option combination or long-tail performance scenario.

The independent agent could not execute offline file:// HTML because its UI
policy blocked that navigation. It checked the embedded archive statically and
recovered it through the public loader. Separate repository browser tests cover
offline navigation/playback, zero network, JavaScript-disabled posters and frame
bounds. Exported Blender Python was syntax-checked in this evaluation; a fresh
Blender engine run is not claimed. Some independent exact-size images clipped
outer repeats because their aspect differed from the viewport; those images
establish restored visibility, not a fully framed publication composition.

## Distribution gates

Source validation is not a claim that platform publication has completed.
The final process additionally requires the published-wheel clean-environment
check, Read the Docs latest/tag/PDF/ePub verification, all three packaged desktop
CI targets, both Mac architectures signed and notarized with app and DMG tickets,
repeated final packaged GUI checks, Windows install/uninstall association checks,
and re-download verification of the public assets.

Exact platform/source provenance and final results accompany the release in
`desktop-validation.zip`, `desktop-signing-validation.zip`,
`mac-notarization.json` and `desktop-SHA256SUMS.txt`. Windows CI uses software
rendering; these tests cannot establish behavior on every physical GPU/driver.
Windows publisher signing remains disabled, separately from Mac notarization.
The user's installed application is not replaced by this release procedure.
