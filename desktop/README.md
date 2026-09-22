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
independently, then repeats tests against each packaged app. It retains build
candidates and evidence as workflow artifacts. It deliberately does **not**
publish those ad-hoc Mac builds: an automatic `--clobber` must never replace a
notarized public app. After **all three** targets pass at the same commit, a
maintainer signs/notarizes the Mac candidates and promotes the verified set
as described below. The PyPI wheel and release tag are not replaced. Release
notes identify the exact desktop build commit and signing record.
`desktop-validation.zip` on the release contains each platform's result JSON,
workspace screenshots and rendered fixture, excluding browser profiles/logs.

Local/CI Mac builds use an ad-hoc signature with electron-builder's standard
Electron entitlements and hardened runtime. Public Mac releases require the
Developer ID and notarization procedure below. Windows publisher signing is a
separate process; an Apple certificate does not sign the Windows installer.
Never describe ad-hoc signing as Apple notarization or disable OS protection.
Packaged tests check the entire
bundle before and after execution with `codesign --verify --deep --strict`; this catches broken resource
signatures that a direct executable launch alone can miss. Ad-hoc signing
does not identify a publisher or replace Apple notarization.
The private Python process runs with `-B` so imports cannot add bytecode caches
inside the signed application, including after repeated launches.

For updates, revise Electron/runtime pins, desktop version, bundled PyPI
version and documentation together; rerun native and packaged checks on every
target. Core updates must first complete the PyPI/GitHub release checklist.
Do not silently rebuild against an untested local Python checkout.

## Sign and notarize macOS

Use a Mac with Command Line Tools, a valid **Developer ID Application** identity
(certificate **and matching private key** in the login keychain), and the Apple
Developer ID G2 intermediate when required by the certificate. Keep trust at
system defaults. Do not export the private key or store an Apple password in
the repository, CI logs, release assets, or command arguments.

Store notarization credentials once through Apple's interactive prompt:

```sh
xcrun notarytool store-credentials vase-notary --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID
security find-identity -v -p codesigning
```

`store-credentials` asks for an app-specific password and saves it in Keychain.
These credentials authorize notarization; the Developer ID private key signs
the app. A successful credentials check is not yet app notarization.

Download both tested CI Mac ZIPs and verify their recorded digests. Extract
each to its own disposable directory with `ditto -x -k`; preserve symlinks.
Do not sign an installed/running app. Run the following from `desktop/` for
**each** architecture; set absolute paths and select `arm64` or `x64`:

```sh
VASE_APP=/absolute/staging/mac-arm64/v_ase.app
VASE_ARCH=arm64
VASE_OUTPUT=/absolute/staging/release
VASE_IDENTITY='Developer ID Application: YOUR_NAME (YOUR_TEAM_ID)'
mkdir -p "$VASE_OUTPUT"
node scripts/sign_macos.cjs "$VASE_APP" "$VASE_IDENTITY"
V_ASE_SMOKE_DIR="$VASE_OUTPUT/checks-$VASE_ARCH" python scripts/test_packaged.py --app "$VASE_APP"
ditto -c -k --sequesterRsrc --keepParent "$VASE_APP" "$VASE_OUTPUT/submission-$VASE_ARCH.zip"
xcrun notarytool submit "$VASE_OUTPUT/submission-$VASE_ARCH.zip" --keychain-profile vase-notary --wait --output-format json
```

The helper signs nested Mach-O executables/libraries, Electron helpers and
frameworks **inside out**, then the outer app, with secure timestamps and
hardened runtime. It preserves the tested Electron entitlements, including
JIT. `--deep` is used for verification, never for signing. This includes
private Python, extension modules, FFmpeg and the bundled Vulkan loader.
Approve the normal `codesign` Keychain prompt locally if shown.

Require **Accepted**; save the returned submission ID and obtain its log with
`xcrun notarytool log SUBMISSION_ID --keychain-profile vase-notary LOG.json`.
If processing is pending, query `notarytool info SUBMISSION_ID` with the same
profile; do not repeatedly resubmit identical bytes. An invalid submission
must be repaired and tested before continuing. Once accepted:

```sh
xcrun stapler staple "$VASE_APP"
xcrun stapler validate "$VASE_APP"
spctl --assess --type execute --verbose=2 "$VASE_APP"
ditto -c -k --sequesterRsrc --keepParent "$VASE_APP" "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.zip"
npx --no-install electron-builder --prepackaged "$VASE_APP" --mac dmg --"$VASE_ARCH" --publish never --config.directories.output="$VASE_OUTPUT" --config.dmg.writeUpdateInfo=false
codesign --force --timestamp --sign "$VASE_IDENTITY" "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.dmg"
xcrun notarytool submit "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.dmg" --keychain-profile vase-notary --wait --output-format json
```

The pinned builder's `--prepackaged` path creates the familiar DMG layout
without rebuilding or re-signing the app. After the **DMG** submission is
Accepted, retain that ID/log as well, then run:

```sh
xcrun stapler staple "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.dmg"
xcrun stapler validate "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.dmg"
codesign --verify --deep --strict "$VASE_APP"
python scripts/verify_macos.py "$VASE_APP" --team-id YOUR_TEAM_ID --notarized
spctl --assess --type open --context context:primary-signature --verbose=2 "$VASE_OUTPUT/v_ase-0.4.1-mac-$VASE_ARCH.dmg"
```

ZIPs cannot themselves receive a staple: their enclosed `.app` must already
have one. The DMG and its enclosed app both carry tickets. Run packaged smoke
again after final stapling; inspect workspace/render images and confirm no
`.pyc` files were created inside the sealed app. Test Intel natively in CI;
on an Apple-silicon signing Mac with Rosetta, repeat its packaged smoke with
`V_ASE_SOFTWARE_GL=1` and record that additional test as **Rosetta**, not a
second physical Intel test.

## Promote verified desktop downloads

1. Require successful native and packaged checks on **all three CI targets**
   at one recorded source commit, plus the final Mac signing checks above.
   Scientific package files must still match the released PyPI wheel.
2. Stage only final Mac DMGs/ZIPs, the same tested Windows EXE/ZIP, the
   corresponding `git archive` desktop source, and sanitized validation
   artifacts. Do not upload submission ZIPs, credentials, browser profiles,
   local logs or builder blockmaps. There is no auto-update feed.
3. Add `mac-notarization.json` with public certificate identity/team, build
   commit, input digests, Apple Accepted submission IDs, final artifact digests,
   ticket/Gatekeeper verification and packaged-check results. Preserve the
   original cross-platform `desktop-validation.zip`; include additional signed
   Mac result JSON/screenshots in a separate validation archive.
4. Compute `desktop-SHA256SUMS.txt` **after stapling**, covering every desktop
   download, source archive and evidence file. Preserve hashes for unchanged
   Windows assets. Sign-only promotion does not modify the Python tag, wheel,
   sdist or package version.
5. Use authenticated `gh release upload v0.4.1 --repo lgyEthan/v_ase --clobber`
   with the explicit changed asset paths. Upload the checksum file last. Use
   `gh release edit ... --notes-file ...` to preserve core release notes and
   update desktop install links, source provenance, Mac signed/notarized status
   and the distinct unsigned Windows status. Never include credentials.
6. Download the public assets again, compare local hashes with GitHub's digest
   and the checksum file, extract the Mac ZIPs, verify signatures/tickets and
   Gatekeeper assessment, and inspect the DMG's Applications shortcut. Confirm
   the source/evidence links and the online installation guide match delivery.
