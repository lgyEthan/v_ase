# Release Checklist

Every v_ase release must keep the package, user documentation, agent contract,
and rendered examples in sync.

1. Update the version in `pyproject.toml`, `v_ase/_version.py`, the application
   shell, cache-busted JavaScript imports, and `CHANGELOG.md`.
2. Update `README.md` for every user-visible behavior change.
3. Update the canonical
   `v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md` and its
   one-level references for every semantic API, workflow, display, analysis,
   export, dependency, safety rule, or error-handling change.
4. Validate skill frontmatter, trigger/no-trigger cases, reference links, and
   capability parity against `window.v_aseAI.capabilities()` and the live
   schema. If an AI failed because the skill was incomplete, update both the
   skill and a regression test before release.
5. When rendering or constraint visuals change, run
   `scripts/capture_readme_screenshots.py` and replace every README image and
   animation in both `docs/assets/` and `docs/assets/github/`.
   Open the logo, constraint images, and animation frames to verify actual
   geometry, camera, lighting, clipping, and visibility.
6. Run the complete browser AI workflows listed in the skill evaluation
   reference. Verify state, selection, edits, constraints, trajectory, camera
   directions, nonblank exact-size renders, exports, GUI-to-CLI collaboration
   events, multi-tab routing, and stale-revision rejection.
   For standalone HTML, reopen the GUI-downloaded file from `file://`, verify
   view-only navigation and playback at desktop/mobile sizes, extract its
   `.vase`, and assert that it makes no HTTP/HTTPS request.
7. Run the complete test suite, build wheel and source distribution, and run
   `twine check`.
8. Push the release commit to GitHub and upload the same version to PyPI.
9. Install the published wheel in a clean environment and verify
   `v_ase --version`, `v_ase gui`, canonical skill serving, and the documented
   end-to-end semantic workflow.
