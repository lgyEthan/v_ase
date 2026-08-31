# Release Checklist

Every v_ase release must keep the package, user documentation, agent contract,
and rendered examples in sync.

1. Update the version in `pyproject.toml`, `v_ase/_version.py`, the application
   shell, cache-busted JavaScript imports, and `CHANGELOG.md`.
2. Synchronize `CITATION.cff`, the version notice in `docs/index.md`, and any
   version-specific documentation with that exact release and artifact URL.
3. Update `README.md` and the versioned Read the Docs user guide for every
   user-visible behavior change. Keep the navigation, file-format tables,
   troubleshooting, examples, and public Python/CLI signatures current.
4. Update the canonical
   `v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md` and its
   one-level references for every semantic API, workflow, display, analysis,
   export, dependency, safety rule, or error-handling change.
5. Validate skill frontmatter, trigger/no-trigger cases, reference links, and
   capability parity against `v_ase api "$COMMAND_URL" capabilities`, the
   optional `window.v_aseAI.capabilities()` mirror, and the live schema. If an
   AI failed because the skill was incomplete, update both the skill and a
   regression test before release.
6. Build the documentation with the pinned dependencies and treat every Sphinx
   warning as a release failure:

   ```bash
   python -m pip install -r docs/requirements.txt
   make -C docs html
   make -C docs linkcheck
   ```

   Open the generated home, quick start, one long workflow page, API/CLI
   reference, troubleshooting, and developer navigation at desktop and narrow
   widths. Confirm search, code blocks, tables, images, previous/next links,
   version label, and Edit-on-GitHub target. Verify that every toctree entry and
   internal link resolves and that excluded `docs/design/` artifacts are not
   published.
7. When rendering or constraint visuals change, run
   `scripts/capture_readme_screenshots.py` and replace every README image and
   animation in both `docs/assets/` and `docs/assets/github/`.
   Open the logo, constraint images, and animation frames to verify actual
   geometry, camera, lighting, clipping, and visibility.
8. Run the complete browser AI workflows listed in the skill evaluation
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
9. Run the complete test suite, build wheel and source distribution, and run
   `twine check`. Inspect the sdist to confirm the Sphinx configuration,
   Markdown sources, selected documentation assets, and canonical Skill are
   present.
10. Push the release commit to GitHub and upload the same version to PyPI.
11. Wait for Read the Docs to finish the tag build. Verify the release version,
    `stable`, and `latest` aliases resolve to the intended commits, the search
    index is current, and downloadable PDF/ePub artifacts build when enabled.
12. Install the published wheel in a clean environment and verify
   `v_ase --version`, `v_ase gui`, canonical skill serving, and the documented
   end-to-end semantic workflow.
