# Contributing documentation

The v_ase documentation is part of the release contract, not a separate
after-release artifact. User documentation, implementation behavior, the
canonical agent control contract, rendered examples, package metadata, and
the published Read the Docs version must describe the same tested release.

## Documentation stack

The site uses:

- Sphinx for document structure, cross-references, search and output;
- MyST-Parser for Markdown sources;
- the Read the Docs Sphinx theme; and
- `.readthedocs.yaml` for the hosted Python and build configuration.

The pinned documentation dependencies live in `docs/requirements.txt`.
`docs/conf.py` reads the application release from `v_ase/_version.py`, so the
site title follows the tested package version without importing the scientific
runtime.

## Build locally

From the repository root, create or activate a Python 3.12+ environment and
install only the documentation toolchain:

```bash
python -m pip install -r docs/requirements.txt
make -C docs html
```

The generated site is under `docs/_build/html`. The Makefile enables warnings
as errors and continues far enough to report all warnings in one run. A
successful build must therefore finish with no missing documents, orphaned
pages, unresolved references, duplicate targets, invalid MyST, or missing
images.

Run the external-link builder separately:

```bash
make -C docs linkcheck
```

Transient publisher rate limits can be retried, but a repeatable 404 must be
fixed. Prefer DOI landing pages over fragile publisher-specific supplementary
file paths.

Clean generated output with:

```bash
make -C docs clean
```

`docs/_build/` is generated and must not be committed.

## Add or reorganize a page

1. Put user and maintainer Markdown under `docs/` with a descriptive,
   lower-case filename.
2. Give the page exactly one level-one heading.
3. Add it to the appropriate MyST `toctree` in `docs/index.md`. A page omitted
   from every toctree produces a strict-build warning unless it is
   deliberately marked orphaned.
4. Use relative links between documentation pages, including the `.md`
   suffix in source.
5. Build HTML with warnings as errors and inspect the rendered page, sidebar,
   tables, code blocks and narrow-screen layout.

Do not link to `../README.md`, `../examples`, or another file outside the
Sphinx source tree as though it will automatically become a documentation
page. Either create an internal documentation page, use a stable external
source link, or include the content deliberately and verify rewritten links.

## MyST conventions

Use ordinary CommonMark where it is sufficient. MyST directives are available
for structured content:

````markdown
:::{note}
This renders consistently in HTML and non-HTML Sphinx builders.
:::

```{toctree}
:maxdepth: 2

child-page
```
````

Follow these rules:

- use fenced code blocks with a language such as `bash`, `python`, `json`, or
  `text`;
- give links meaningful text instead of "here";
- provide accurate alt text for every meaningful image;
- keep tables narrow enough for the Read the Docs content column;
- use headings or MyST admonitions instead of raw HTML `<details>` blocks when
  content must also work in PDF/ePub; and
- avoid hard-coded section-fragment links when a normal page link or Sphinx
  cross-reference is clearer.

The strict build is the final authority for parser and reference behavior;
GitHub's Markdown preview is not equivalent to Sphinx/MyST.

## Images and animations

Reference local, versioned assets rather than
`raw.githubusercontent.com/.../main/...` URLs. A `main` URL makes an older
tagged manual display a newer image and can force a documentation build or
reader to download a large animation remotely.

Use a static PNG or other optimized still when motion is not essential. Keep
large GIFs only for workflows where the sequence communicates behavior that a
still cannot. Never add the complete `docs/assets/` tree to Sphinx's
`html_static_path`; Sphinx should copy only assets actually referenced by
pages.

When application rendering or constraint visuals change, run the canonical
capture script:

```bash
python scripts/capture_readme_screenshots.py
```

Synchronize the generated files in `docs/assets/` and
`docs/assets/github/`, then inspect the real image and animation frames. An
HTTP success or file-existence check is not visual validation.

The source distribution intentionally excludes the full duplicated media
tree. Any asset required to build the Sphinx site from an sdist must be listed
by the documentation asset rules in `MANIFEST.in` without pulling all large
README animations into the distribution.

## Keep all documentation surfaces synchronized

For every user-visible behavior change:

- update the relevant user-guide or reference page;
- update `README.md` as required by the repository release contract;
- update `CHANGELOG.md` for the release;
- update examples or troubleshooting when commands, dependencies, output, or
  errors change; and
- update package metadata when the public documentation or release URL
  changes.

When a workflow, semantic operation, display setting, analysis feature,
export, dependency, safety rule, or error changes, also update the canonical
agent Skill and the necessary one-level references under
`v_ase/skills/visualizing-atomic-structures-with-v-ase/`. Compare those files
with the live semantic schema and capabilities. Add or update a regression if
an agent could otherwise fail because the written contract is ambiguous or
stale.

Do not copy a long canonical contract into two independently edited pages when
a concise user explanation plus a clear reference can avoid divergence.

## Validate links and documentation contracts

Run the repository consistency and agent documentation tests while editing:

```bash
python -m pytest tests/test_project_consistency.py tests/test_agent_skill.py
```

New nested documentation directories must be included in recursive Markdown
link checks. Validate both the target file and any section anchor. External
link checking complements these repository tests; it does not replace them.

When version text changes, verify at minimum:

- `pyproject.toml`;
- `v_ase/_version.py`;
- application shell and cache-busted frontend imports;
- `CHANGELOG.md`;
- `CITATION.cff` and its artifact URL/date;
- version-pinned Skill installation commands; and
- the Sphinx site title and current-release callout.

## Verify the source distribution

The documentation build configuration and required source assets are included
in the sdist through `MANIFEST.in`. After changing those rules, build and
inspect the release artifacts:

```bash
python -m build
python -m twine check dist/*
tar -tf dist/v_ase_gui-*.tar.gz
```

Extract the new sdist into a clean temporary directory, install
`docs/requirements.txt`, and run the same strict Sphinx HTML build there. This
catches a missing configuration, CSS file, page, or required image that a
checkout build would hide.

## Read the Docs and release validation

Read the Docs builds from `.readthedocs.yaml` using the pinned requirements.
Pull-request builds should pass before merge. After a release tag is published:

1. confirm the tag-specific documentation build succeeds;
2. confirm the `stable` and `latest` selectors point to the intended releases;
3. inspect the deployed navigation, search and representative images;
4. confirm source/edit links point to the version being read rather than
   always to `main`; and
5. verify the public Documentation URL from README and package metadata.

The complete package, browser, semantic-agent, media, GitHub and PyPI sequence
remains mandatory. See [Release checklist](release_checklist.md).

## Documentation pull-request checklist

- [ ] The page is in the correct toctree and has one clear audience.
- [ ] Commands were checked against v_ase 0.2.35 or the version being released.
- [ ] Local links, anchors and image paths resolve.
- [ ] HTML builds with warnings as errors.
- [ ] Linkcheck has no repeatable broken URL.
- [ ] Rendered HTML was inspected, not only the Markdown source.
- [ ] README, Skill, changelog, metadata and tests were updated where required.
- [ ] Required Sphinx sources/assets are present in the sdist.
