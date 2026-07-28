# Release Checklist

Every v_ase release must keep the package, user documentation, agent contract,
and rendered examples in sync.

1. Update the version in `pyproject.toml`, `v_ase/_version.py`, the application
   shell, cache-busted JavaScript imports, and `CHANGELOG.md`.
2. Update `README.md` for every user-visible behavior change.
3. Update `v_ase/skills_v_ase.md` for every semantic API, workflow, display,
   analysis, or export change.
4. When rendering or constraint visuals change, run
   `scripts/capture_readme_screenshots.py` and replace every README image and
   animation in both `docs/assets/` and `docs/assets/github/`.
5. Run the complete test suite, build wheel and source distribution, and run
   `twine check`.
6. Push the release commit to GitHub and upload the same version to PyPI.
7. Install the published wheel in a clean environment and verify
   `v_ase --version`, `v_ase gui`, and the packaged agent skill.
