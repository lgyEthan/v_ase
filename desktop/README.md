# v_ase Desktop

Native macOS and Windows windows around the published v_ase 0.4.1 GUI. Scientific
editing, rendering, serialization and Python/Jupyter APIs stay in the Python
distribution. The host adds OS file dialogs, guarded native file handles,
document shortcuts, single-instance file opening and safe Quit.

## Build on the target platform

Use Node.js 22, npm, Python 3.12+ **for the build helper**, and Git. The app bundles
CPython 3.11.16. Targets are macOS arm64/x64 and Windows x64.
Mac builds require Xcode command-line tools and CMake 3.22.1+.
The finished Mac app requires macOS 15+ because of its bundled scientific and
Rhino wheels. Intel builds also require Xcode tools, Rust and Homebrew
`openssl@3` to compile current `cryptography` with static OpenSSL; that project
no longer publishes Intel Mac wheels. The build checks its linkage and never
downgrades to an older cryptography release to obtain a wheel.

```sh
cd desktop
python scripts/prepare_runtime.py
npm ci
python scripts/prepare_macos_graphics.py
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
The Mac graphics helper builds digest-pinned Khronos Vulkan Loader 1.4.357.0
sources. Electron 44 omits this library although Chromium 151+ dynamically
requires it for SwiftShader. `after_pack.cjs` puts it in the framework before
signing, including its licenses and source provenance in Resources. The app
does not depend on Homebrew or a system Vulkan installation. Software graphics
is explicitly enabled only for the fixed CI smoke fixture; normal windows use
the platform GPU. See the [upstream report](https://github.com/chromiumembedded/cef/issues/4230).
The canonical agent Skill and its references are then synchronized into the
bundle, including desktop connection guidance. Scientific Python/JavaScript
and package metadata remain those of the published wheel.

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
The desktop smoke also checks all 23 workbench routes at 1440, 1024 and 390
pixel widths for clipped controls and unit overlap, and counts oxygen-colored
pixels in the export to reject a blank WebGL image. Windows starts isolated
Python with explicit UTF-8 mode so Unicode GUI source does not depend on the
system ANSI code page.

`.github/workflows/desktop.yml` tests Apple silicon, Intel Mac and Windows
independently, then repeats tests against each packaged app. Only after **all
three** pass does it attach installers, ZIPs, a corresponding source archive
and checksums to the existing `v0.4.1` release. The PyPI wheel and release tag
are not replaced. Notes identify the exact desktop commit. One failing target
blocks all desktop uploads.
`desktop-validation.zip` on the release contains each platform's result JSON,
workspace screenshots and rendered fixture, excluding browser profiles/logs.

Initial builds are not publisher-signed/notarized. Configure real credentials
before advertising signed builds. Never describe ad-hoc signing as Apple
notarization, or require users to disable OS protection.
Mac bundles use a valid ad-hoc signature with electron-builder's standard
Electron entitlements and hardened runtime. Packaged tests check the entire
bundle before and after execution with `codesign --verify --deep --strict`; this catches broken resource
signatures that a direct executable launch alone can miss. Ad-hoc signing
does not identify a publisher or replace Apple notarization.
The private Python process runs with `-B` so imports cannot add bytecode caches
inside the signed application, including after repeated launches.

For updates, revise Electron/runtime pins, desktop version, bundled PyPI
version and documentation together; rerun native and packaged checks on every
target. Core updates must first complete the PyPI/GitHub release checklist.
Do not silently rebuild against an untested local Python checkout.
