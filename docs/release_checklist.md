# Release Checklist

Every v_ase release must keep the package, user documentation, agent contract,
and rendered examples in sync.

> **Symmetry repository override:** run this checklist only inside
> `interactive_visualizer_symm` on the `symmetry` branch. Never access the
> sibling `interactive_visualizer` repository, never merge or push to GitHub
> `main`, and never upload this experimental package to PyPI.

1. Advance `MAIN_BASEaSYMMETRY_ITERATION+symmetry` and update it in
   `pyproject.toml`, `v_ase/_version.py`, the application shell, cache-busted
   JavaScript imports, and `CHANGELOG.md`. Keep `MAIN_BASE` at the main release
   from which this standalone repository was forked unless a deliberate new
   fork is created.
2. Update `README.md` for every user-visible behavior change.
3. Update the canonical
   `v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md` and its
   one-level references for every semantic API, workflow, display, analysis,
   export, dependency, safety rule, or error-handling change.
4. Validate skill frontmatter, trigger/no-trigger cases, reference links, and
   capability parity against `v_ase api "$COMMAND_URL" capabilities`, the
   optional `window.v_aseAI.capabilities()` mirror, and the live schema. If an
   AI failed because the skill was incomplete, update both the skill and a
   regression test before release.
5. When rendering or constraint visuals change, run
   `scripts/capture_readme_screenshots.py` and replace every README image and
   animation in both `docs/assets/` and `docs/assets/github/`.
   Open the logo, constraint images, and animation frames to verify actual
   geometry, camera, lighting, clipping, and visibility.
   When symmetry or phonon examples change, also run
   `scripts/capture_symmetry_readme_assets.py`; verify its CIF/EXTXYZ/YAML
   manifest and inspect all four actual Analysis-panel PNGs.
6. Run the complete browser AI workflows listed in the skill evaluation
   reference. Verify state, selection, edits, constraints, trajectory, camera
   directions, nonblank exact-size renders, exports, GUI-to-CLI collaboration
   events, multi-tab routing, and stale-revision rejection.
   For standalone HTML, reopen the GUI-downloaded file from `file://`, verify
   view-only navigation and playback at desktop/mobile sizes, extract its
   `.vase`, and assert that it makes no HTTP/HTTPS request. Also reopen it with
   JavaScript disabled and verify that the poster alone fills the exact export
   frame with no logo, header, border, or margin. Compare that poster to the
   first WebGL frame, trigger the cross-fade, and assert that frame bounds do
   not move. Exercise `%v_ase inline`, `%v_ase browser`, and `%v_ase auto` in a
   real notebook kernel.
   Run a fresh zero-context agent with only the canonical Skill and require it
   to use the HTTP JSON bridge rather than page-main-world evaluation. Require
   it to call `schema`, inspect calculator state, exercise every operation and
   export, verify output contents, and run alone in its own document session.
7. Run the complete test suite, build wheel and source distribution, and run
   `twine check`.
8. Keep the tested release local unless the user explicitly requests a push
   to a symmetry-specific remote branch. Do not upload to PyPI.
9. Install the locally built wheel in a clean environment and verify
   `v_ase --version`, `v_ase gui`, canonical skill serving, and the documented
   end-to-end semantic workflow.
