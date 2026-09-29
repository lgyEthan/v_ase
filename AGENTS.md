# v_ase Release Contract

Keep implementation, user documentation, agent control documentation, and
rendered examples synchronized in every release.

- Update `README.md` for every user-visible change.
- Update the canonical
  `v_ase/skills/visualizing-atomic-structures-with-v-ase/SKILL.md` and its
  one-level `references/` whenever a workflow, semantic command, display
  setting, analysis feature, export, error, or dependency changes.
- Compare the canonical skill against `window.v_aseAI.capabilities()` and the
  live schema. Add or update a regression whenever an AI could not complete a
  user request because the skill was ambiguous or stale.
- Run the documented AI end-to-end scenarios, including semantic state,
  physical edits, constraints, trajectories, camera directions, exact image
  rendering, exports, same-document human refinement, CLI collaboration events,
  and stale-revision rejection. Inspect rendered output visually; an HTTP
  success response is not sufficient.
- When rendering or constraint visuals change, regenerate every README image
  and animation with `scripts/capture_readme_screenshots.py`, then synchronize
  `docs/assets/` and `docs/assets/github/`.
- Run the full test suite, build wheel and sdist, and run `twine check`.
- Publish the same tested version to the GitHub `main` branch and PyPI.
- Verify the published wheel in a clean environment.

The complete sequence is in `docs/release_checklist.md`.

## Public naming and local integration files

- Use descriptive `fix/`, `feature/`, `release/`, or `maintenance/` branches.
  Do not use an automated coding assistant's product name in branch names,
  authored identifiers, comments, file paths, UI copy, or public artifacts.
- Keep private agent/plugin configuration local. Never commit personal plugin
  manifests, host-specific installation folders, environment settings, account
  bindings, or generated private bundles. Ignore them and exclude them from
  source distributions and release archives.
- Before publishing, inspect tracked paths and text, generated package contents,
  public documentation, and release metadata. Do not claim a naming check has
  passed unless it was actually performed; do not disguise forbidden names by
  splitting or encoding string literals.
- Before deleting a work branch, verify its commits are included in `main`.
  Preserve unmerged work and local changes, and do not rename a checkout used
  by another active task. Keep the working release checkout on `main` afterward.
