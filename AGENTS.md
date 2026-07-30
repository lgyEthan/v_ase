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
