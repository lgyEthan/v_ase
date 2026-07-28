# v_ase Release Contract

Keep implementation, user documentation, agent control documentation, and
rendered examples synchronized in every release.

- Update `README.md` for every user-visible change.
- Update `v_ase/skills_v_ase.md` whenever a workflow, semantic command,
  display setting, analysis feature, or export changes.
- When rendering or constraint visuals change, regenerate every README image
  and animation with `scripts/capture_readme_screenshots.py`, then synchronize
  `docs/assets/` and `docs/assets/github/`.
- Run the full test suite, build wheel and sdist, and run `twine check`.
- Publish the same tested version to the GitHub `main` branch and PyPI.
- Verify the published wheel in a clean environment.

The complete sequence is in `docs/release_checklist.md`.
