# v_ase Symmetry Isolation Contract

This repository is the standalone experimental symmetry build.

- Perform every source, test, build, and Git operation inside
  `/Users/glee0366/Dropbox/CMT_USYD/Projects/side_project/interactive_visualizer_symm`.
- Never read from, write to, run commands in, or use Git metadata from the
  sibling `interactive_visualizer` repository.
- Work only on the `symmetry` branch unless the user explicitly creates
  another branch inside this standalone repository.
- Keep versions independent from the main package using
  `MAIN_BASEaSYMMETRY_ITERATION+symmetry`, for example
  `0.0.120a3+symmetry`. The first three fields identify the main release whose
  viewer state was forked; the alpha number advances only on this branch.
- Never merge or push changes to the original GitHub `main` branch.
- Never upload this experimental build to PyPI.
- Local wheel and sdist builds plus `twine check` are allowed for validation.

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
- Do not publish this branch to GitHub `main` or PyPI. Push a symmetry-specific
  remote branch only when the user explicitly requests it.
- Verify the locally built wheel in a clean environment.

The complete sequence is in `docs/release_checklist.md`.
