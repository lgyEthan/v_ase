# v_ase 0.4.5 validation and release record

Date: 2026-09-24. This record concerns the eight follow-up requirements for
file associations, camera interaction, viewport rendering, desktop closure and
saved-project restoration. It supersedes neither historical 0.4.4 evidence nor
the independent scientific-study files elsewhere in this checkout.

## Desktop promotion follow-up

The first three-platform CI run eventually returned success, but inspection
of its Intel packaged evidence found an empty `result.json`. That candidate
set must not be promoted. Closing the final window requested `app.quit()`
both directly and from `window-all-closed`, bypassing the smoke harness's
single cancelled `will-quit` event while its asynchronous report was written.
Final-window closure now delegates the quit request to `window-all-closed`;
explicit Quit owns its single request after releasing all windows. Four Node
regressions execute the production handlers, including cancellation and
multi-window preservation. The desktop Node suite now contains 13 tests.
Packaged validation must parse the entire report and require every completion
flag, so process exit zero or an empty file can no longer pass the gate.

This is a desktop-only follow-up: the already published 0.4.5 Python package,
scientific files, version tag and distributions remain unchanged. Require a
fresh three-platform CI run for the desktop commit. Record that commit
separately from the Python release commit in `mac-notarization.json` and use
it for the downloadable desktop source archive.

## Implemented behavior

| Requirement | Implementation and verification |
| --- | --- |
| Only `.vase` automatic file handling | `desktop/file-formats.json`, package associations and the generated NSIS include exclude generic suffixes such as JSON. Mac scientific types use rank `None`; explicit opening remains possible. Windows only adds specific scientific Open With candidates, and removes its own obsolete generic registrations. Tests preserve other application defaults. |
| Clear camera states | Renderer has mutually exclusive **Navigate: Scene / Camera**, plus **Look through camera** and **Align camera to view**. Navigation-target switches preserve the complete output profile. Scene navigation leaves the output camera fixed; Camera navigation applies subsequent relative view changes. |
| Oriented camera guide | The renderer draws a compact wire camera and oriented output-plane outline, replacing the opaque eye sprite. The guide writes no depth, uses scene occlusion, and is omitted from exports. |
| Camera G/R/S | A selected output camera supports translation, rotation about its output center, and uniform frame scaling in either View or Edit. Escape restores pose and scale. These compose atoms, bonds, cell and fields together without modifying scientific coordinates. |
| Find 2D/3D | The existing complete-scene 2D/3D style is available in Renderer (Command/Ctrl+Shift+A) and Viewport, with synchronized controls. |
| Atom/grid visibility | Scientific drawing limits follow geometry while saved camera optics remain unchanged. An analytic, adaptive XY work plane replaces finite grid tiles. It renders behind scientific geometry with correct alpha blending and cannot cut holes into atoms. |
| Close last desktop tab/window | Command/Ctrl+W invokes the host's guarded close when a window has one document, including an empty document. Other windows remain open; closing the final window quits. Cancel preserves the window. The browser retains its blank internal document behavior. |
| Restore `.vase` without prompts | Saves record authoritative runtime mode, current frame, scientific data, visual mappings, both cameras, output-frame visibility, selection/measurement intent and inspector presentation. A project opens without reader/mode prompts, reuses an empty startup tab, and otherwise creates a tab. Same-tab semantic loads also adopt saved mode. Older archives use their stored display mode, or Edit if no mode exists. |

## Additional regressions found by independent evaluation

- Native project/HTML saves previously used a smaller display-only snapshot.
  They now use the same complete project snapshot as GUI Save, retaining
  selection and presentation.
- Empty selected colorscale targets now map no atoms without blocking explicit
  native requests, trajectory range handling, GIF, MOV or AVI export.
- Animation capture restores selection and measurement intent across topology
  changes, and does not report its temporary frame visits as human edits.
- Partial appearance changes retain the image export profile.
- The documentation runtime bundles every renderer module, including the new
  grid. A regression checks local import coverage so a successful Sphinx build
  cannot hide a broken interactive logo.
- Following-camera orientation uses an orthogonal camera basis, preserving
  exact axis-view metadata as well as the rendered direction.
- Grid lines fade at grazing angles rather than producing dense stripes.
- Concurrent collaboration flushes serialize behind in-flight publications;
  a deterministic regression holds an HTTP publication open and verifies that
  the second flush cannot return an obsolete revision.

## Evidence

The work uses actual Chromium/Electron renders, numerical project round trips,
native keyboard injection and isolated backend sessions. It does not rely only
on static source assertions. Local output lives under `/tmp/vase-045-*`;
sanitized final desktop evidence is attached to the GitHub release.

- `tests/test_browser_camera_project_reopen.py`: both saved modes, immediate
  new-tab opening, same-tab semantic restoration, saved selection, color/radius
  pixel comparison, orthographic/perspective camera transforms and cancellation,
  clipping, grid visibility/occlusion, complete-scene style switch, idle redraw
  count, empty color targets, animation selection and collaboration revisions.
- `tests/test_project_file_binding.py`: backend-authored mode and typed legacy
  fallback, in addition to original writable-file binding tests.
- Desktop smoke: real Command/Ctrl+A, consecutive cutoff Tab, native Save and
  Save As, new-tab/project opening, detach/transfer rollback, independent windows,
  dirty close cancellation, last-tab window close and empty-last-window Quit.
- Documentation QA: eight representative pages at 1440 and 390 px, no horizontal
  overflow, navigation/edit links, search results and the interactive logo.
- Fresh canonical-Skill-only evaluation: independent MCP and CLI/HTTP execution,
  artifact inspection and retests of reported failures. Coverage and unavailable
  provider token metrics must be stated explicitly in its final report.

## Release gates

The source record distinguishes local checks from subsequent published-artifact
checks. Final distribution, CI, signing and download evidence is recorded with
the [0.4.5 release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.5),
including `desktop-validation.zip` and `mac-notarization.json`.

- [x] Final suite after the desktop lifecycle follow-up: **1,072 passed** in
      578.64 seconds, including the five packaged-evidence regressions. All
      13 repository consistency checks also passed.
- [x] **13 desktop Node tests**; final native Mac smoke passed all ten commands,
      69 layout checks, save/transfer/cancel and last-window close checks.
- [x] Complete README media regenerated; GitHub assets synchronized. Logo,
      constraints, measurements, scalar maps, volumes and animation frames
      visually inspected. Edge-on grid and atom occlusion inspected at full size.
- [x] Strict Sphinx HTML build and 16 desktop/narrow page checks, search and
      interactive logo. Strict Sphinx linkcheck passed after publication,
      including all three installer links and the final checksum file.
- [x] Typed canonical Skill/schema reference check and independent evaluator.
      Initial/final evaluation: 129 calls, 894,158 serialized bytes; bounded
      publication-barrier retest: 16 MCP calls, 70,195 bytes, no errors. Provider
      token counts were unavailable. The evaluator did not cover real human
      gestures or all advanced scientific workflows; repository browser/native
      regressions cover those separately. No exhaustive independent audit of
      every nested schema field is claimed.
- [x] Tracked-only wheel/sdist build and `twine check`; all 101 package files
      match tested source. Clean isolated wheel GUI/CLI workflow passed PNG,
      GIF, index-scoped mapping, served Skill and stale-revision checks.
      Sdist documentation/selected assets/Skill inclusion and exclusion of
      unrelated local research files were verified.
- [x] Python tag `v0.4.5` and PyPI distributions are commit
      `15635d7e998b80a8b0c19d8bece470b7e018f89d`. The downloaded GitHub
      wheel/sdist match PyPI; a clean published-wheel scientific workflow passed.
      Desktop-only follow-up `8fe0ace99b8606813f8ff8364dd3dbb3e4decb01`
      is published on main and does not replace the original Python tag.
- [x] Apple silicon, Intel Mac and Windows native/packaged checks passed in
      [CI run 35957840573](https://github.com/lgyEthan/v_ase/actions/runs/35957840573)
      at the desktop follow-up commit. All six complete reports were parsed;
      Windows installation/uninstallation preserved existing file defaults.
- [x] Both Mac architectures Developer ID signed, Apple Accepted app/DMG,
      stapled, Gatekeeper verified and tested after signing. All 273 native
      components per app passed verification. Both public DMGs and ZIPs were
      downloaded again; the public Intel ZIP also completed the entire
      packaged smoke in a fresh path. Interrupted local runs with confirmed
      manual input were rejected and repeated without changing application bytes.
- [x] All **11** public desktop assets were downloaded again and checked
      against GitHub digests, local final bytes and post-stapling checksums.
      The matching desktop source, cross-platform evidence, signed-app evidence
      and `mac-notarization.json` are attached to the release. Windows remains
      explicitly publisher-unsigned; the bundled 101 package files were checked
      against PyPI (canonical agent documentation permits CRLF-only differences).

The installed user application is not patched in place. Installing the release
uses the documented DMG/Applications or Windows installer workflow.
