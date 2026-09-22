# v_ase Desktop

Native macOS and Windows windows around the published v_ase 0.4.1 GUI. Scientific
editing, rendering, serialization and Python/Jupyter APIs stay in the Python
distribution. The host adds OS file dialogs, guarded native file handles,
document shortcuts, single-instance file opening and safe Quit.

## Build on the target platform

Use Node.js 22, npm, Python 3.12+ **for the build helper**, and Git. The app bundles
CPython 3.11.16. Targets are macOS arm64/x64 and Windows x64.

```sh
cd desktop
python scripts/prepare_runtime.py
npm ci
npm test
npm run smoke
npm run dist
python scripts/test_packaged.py
```

The helper verifies a pinned official python-build-standalone archive against
its SHA-256, installs published `v_ase-gui[mcp,rhino]==0.4.1` and locked binary
dependencies, runs `pip check`, and checks scientific imports. The full
relocatable Python preserves dynamic ASE readers and package resources. It
never installs into the user's Python environment.

`npm start` runs the development host; `npm run pack` builds an unpacked app.
Output goes to `dist/`; test reports, screenshots and PNGs go to `smoke-output/`.
The packaged test launches outside the repository to catch dependencies on the
developer's checkout or Python installation. The icon is a code-drawn v-shaped
atomic chain and v_ase wordmark, in PNG/ICNS/ICO forms under `assets/`.

## Host contract

- `main.cjs` owns Python lifecycle, the exact GUI command registry, native menus,
  single-instance file events and approved external help links. Application
  content and network requests stay on the spawned loopback origin.
- `preload.cjs` exposes narrow IPC only to the trusted top-level workspace.
  Node integration is off; sandbox and context isolation are on. Every file
  operation checks its sender frame and origin.
- `host-adapter.js` installs environment adapters on the existing app. It calls
  published `executeEditorCommand`, `showOpenFileModal`, `openDocumentFromFile`,
  save-picker and `confirmDocumentClose` contracts. Native handles stay in
  parent-owned runtime provenance, never project archives.
- `file-vault.cjs` accepts paths only from main-process file dialogs or OS file
  events. Renderer code uses opaque tokens. Reads/writes are chunked; Save
  checks external-change fingerprints, fsyncs a sibling temporary file, then
  atomically replaces the target. Cancelling never truncates the original.
- Files use the existing upload/reader API. Desktop integration does not relax
  the Python server's launch-directory boundary.

The host does not fork `v_ase/static/`, scientific code, schemas or serialization.
Browser and notebook entry points remain available. Custom calculator packages
and Blender installations are not incorporated into the private runtime.

## Verification and delivery

Node tests cover file authority, external changes, interrupted saves, duplicate
writes, read bounds and ownership. Electron tests use the bundled backend and
renderer, native menus and keyboard input, project opening, dirty Save, Save As,
selection, exact PNG rendering, internal New/Close and Node isolation. Inspect
screenshots as well as `result.json`. Core regressions are recorded in
`docs/design/v_ase_041_validation.md`.

`.github/workflows/desktop.yml` tests Apple silicon, Intel Mac and Windows
independently, then repeats tests against each packaged app. Only after **all
three** pass does it attach installers, ZIPs, a corresponding source archive
and checksums to the existing `v0.4.1` release. The PyPI wheel and release tag
are not replaced. Notes identify the exact desktop commit. One failing target
blocks all desktop uploads.

Initial builds are not publisher-signed/notarized. Configure real credentials
before advertising signed builds. Never describe ad-hoc signing as Apple
notarization, or require users to disable OS protection.

For updates, revise Electron/runtime pins, desktop version, bundled PyPI
version and documentation together; rerun native and packaged checks on every
target. Core updates must first complete the PyPI/GitHub release checklist.
Do not silently rebuild against an untested local Python checkout.
