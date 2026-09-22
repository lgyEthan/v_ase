# v_ase 0.4.1 implementation and validation record

Date: 22 September 2026. This is a delivery record, not a future implementation
plan. The superseded remaining-implementation instructions have been removed.
The editable `v_ase_ui_toy_model.html` and its two reference images are retained
as design history; production behavior is implemented in `v_ase/static/`.

## Delivered workspace

The atomic viewport occupies the main workspace. A single right workbench
contains four persistent primary tabs and visible, labelled tool buttons:

| Area | Directly available tools |
| --- | --- |
| Style | Atoms, Bonds, Cell, Polyhedra, View & guides |
| Build | Add atoms, Transform, Cell matrix, Constraints, Match cells, Relax, Rigid translation |
| Analyze | Measure, Distributions, Displacements, Forces, Fields, Registry |
| Render | Renderer, Image, Video, Interactive HTML, Geometry |

Objects uses a contextual viewport drawer. Analysis results occupy a dock below
the viewport. File, Edit, View, Preferences and Help retain project, history,
presets and guidance workflows. All seven viewport tools are visible: Select,
Move, Orbit, Rotate, Scale, Measure and Add atoms. Camera presets, grid and
lighting remain beside the viewport. Tools requiring Edit explain that state
and provide an explicit switch. View-only cell matching previews remain usable.

At narrow widths the workbench stacks below the viewport. Numeric fields use
bounded layouts; suffixes share the input's container. Atom-type appearance uses
labelled vertical forms instead of a horizontally scrolling table. The color
legend, orientation widget, camera controls and viewport toolbar occupy separate
regions. Collapsing the workbench also disables hit targets in its hidden body.

Primary ownership: `static/editor_ui.js`, `static/editor.css`, `static/index.html`
and `static/main.js`. Scientific state and existing backend operations remain
authoritative; navigation does not create a second document model.

## Functional requirements

- Bulk/box selection records its intent and does not accidentally create an
  ordered distance, angle or torsion. Individual ordered picks and explicit
  measurement retain those workflows.
- Global, type and selected atom size coexist with scalar-property radius
  mapping. Mapping supports fitted/fixed ranges, frozen selection scope,
  trajectory properties, missing values and persistence. Browser rendering,
  image/video, standalone HTML, Blender and CAD exports share the effective
  radius representation. See `docs/property-radius.md`.
- Rendering scale is px/Å, independent of atom radius and viewport zoom.
- Save reuses a writable destination, original HTML/VASE format and stored
  output profile. Save As chooses a new destination. Browser limitations use an
  explicit fallback instead of pretending a download overwrites its source.
- Internal documents have independent dirty state, close decisions and reload
  recovery. Direct and notebook editors can adopt internal tabs in place.
- Scientific coordinates use double-precision trajectory transport. GPU display
  buffers may use floats, but visiting a frame cannot reduce precision in saved
  ASE Pickle or VASE data. Optical camera settings apply after fit and can be
  changed without supplying a new camera pose.

## Required commands

Use Command on macOS and Ctrl on Windows/Linux. The registry in
`static/editor_commands.js` is shared by menus, shortcut labels, search and
execution. Modifier aliases are not silently substituted.

| Command | macOS | Windows/Linux |
| --- | --- | --- |
| Supercell | Command+Shift+B | Ctrl+Shift+B |
| Atom properties | Command+Shift+P | Ctrl+Shift+P |
| Bonds | Command+B | Ctrl+B |
| Renderer | Command+Shift+A | Ctrl+Shift+A |
| Cell matrix | Command+E | Ctrl+E |
| Close internal document | Command+W | Ctrl+W |
| Save | Command+S | Ctrl+S |
| Save As | Command+Shift+S | Ctrl+Shift+S |
| New internal document | Command+N | Ctrl+N |

The browser application intercepts events it receives. Browser/OS-reserved
accelerators are not universally delivered to a web page. App fullscreen
Keyboard Lock is capability- and permission-dependent and reports its state;
ordinary browser fullscreen does not guarantee capture. Menus always provide
the same operations. See `docs/shortcuts.md` for input focus, Escape, G/R/S,
camera arrows and Option/Alt+trajectory navigation. Native application keyboard
capture is provided by the separately packaged desktop host described below.

## Verification

- Full Python/Chromium suite: **1,019 passed, 2 skipped**, 508.66 seconds.
  The two optional-environment cases were then executed with the installed
  Sphinx/Jupyter runtime: **2 passed**. These cover shared HTML/LaTeX image
  fallback and a real kernel exercising `%v_ase inline`, `browser` and `auto`.
- `tests/test_browser_ui_geometry.py` checks all 23 tools at 1440, 1024 and
  390 px widths, long atom labels, expanded property mapping, bulk molecular
  fields and legend/control separation. Image/video dialogs are also checked
  at 640×360. Roving tool keyboard navigation preserves the camera.
- Browser regressions cover structure editing, ordered versus bulk selection,
  appearance, bonds, cells, constraints, relaxation, trajectories, fields,
  analysis, project formats, save conflicts, dirty close, tabs, reload and
  platform command dispatch. Blender/runtime and optional Rhino dependencies
  were available in the full-suite environment.
- Scientific identity regressions compare coordinates exactly across cached
  and streamed trajectories, including 260 atoms, edits and project/export
  round trips. No tolerance hides float32 truncation.
- A fresh agent using only the canonical Skill independently exercised guarded
  physical edits, constraints, properties, trajectory changes, axis cameras,
  exact-sized images, scientific exports, GUI/CLI collaboration and stale
  revision rejection. Its fresh-session recheck confirmed all three exported
  frames exactly, with maximum coordinate error 0 Å; camera scales 4 and 3.5
  were confirmed in state and visually inspected images. The bounded recheck
  made 17 successful semantic CLI calls. Provider token usage was unavailable.
- Typed tool reference generation, first-party JavaScript syntax and whitespace
  checks pass. Strict Sphinx HTML builds pass. Documentation was inspected at
  desktop and narrow widths, including the live logo, workflow, API/CLI,
  troubleshooting and developer navigation.
- All README image/animation capture groups were regenerated, synchronized to
  `docs/assets/github/`, and representative geometry/constraint frames inspected.

The full suite is the regression evidence; the independent agent check is
intentionally narrower. Native OS shortcut delivery was not falsely inferred
from synthetic browser events. PyPI/GitHub publication and clean published-wheel
verification follow `docs/release_checklist.md`; their external records identify
the actual released commit and artifacts.

## Published Python release

The [GitHub v0.4.1 release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.1)
and [PyPI 0.4.1](https://pypi.org/project/v-ase-gui/0.4.1/) contain the same tested
wheel and source distribution from `e647dfdc53213a9499adc09a2c13953ce5452084`.
The source archive was built from tracked release files, excluding unrelated
local research work. Both distributions passed `twine check`.

| Artifact | SHA-256 |
| --- | --- |
| `v_ase_gui-0.4.1-py3-none-any.whl` | `7c6c7c8301f3d537f8696338627ceeea0ac429b56b6efcaae772e41d61b7f2ba` |
| `v_ase_gui-0.4.1.tar.gz` | `c1b5ed1af1c26de0de517058e9f1501b3406f05e2fedf50e9f4950c92855f9df` |

A fresh environment installed the downloaded published wheel, verified its
digest and version, started the GUI, served the canonical Skill, exercised the
semantic API, rendered an 800×600 atomic image, exported VASE and routed two
documents. The published wheel was not replaced by an editable checkout.

The versioned Read the Docs build
[34692878](https://app.readthedocs.org/projects/v-ase/builds/34692878/) succeeded
at that exact tag, generating HTML, a 237-page PDF and ePub. The `stable` channel
remains inactive. The PDF build log still reports a missing Command-symbol
glyph and several overfull table cells; successful generation does not imply
that every page of that offline manual was visually validated. The strict HTML
and ePub builders reported success.

## Desktop architecture and checks

The desktop host is in `desktop/`. It packages the exact PyPI scientific editor
with a private CPython 3.11.16 runtime; browser and Jupyter entry points remain
independent. The canonical agent documentation is copied into the bundle with
the desktop connection instructions. It does not fork scientific JavaScript,
Python operations, serialization, or the editor command registry.
All 77 scientific/frontend package files in the local final Mac bundle were
compared byte-for-byte with the published wheel and matched; the intentionally
synchronized agent documentation was excluded from that comparison.

- `main.cjs` owns the loopback backend, native menus, key dispatch, OS file-open
  events and safe Quit. Both GUI documents and native menus use the existing
  nine-command registry. Native Command/Ctrl+N and +W affect internal documents.
- `host-adapter.js` reuses published save, open, document and close handlers.
  Native Save retains format and output profile. Help copies the command URL
  for an agent to refine the same document through the existing API.
- `file-vault.cjs` owns path access behind opaque, sender-bound capabilities.
  Save detects external changes, reserves the destination against concurrent
  writes, fsyncs a temporary sibling, then replaces the target atomically.
  Cancellation and failed writes preserve the original file.
- The renderer has Node disabled, context isolation and sandboxing enabled.
  File IPC is restricted to the trusted top workspace. The backend remains on
  loopback; quitting stops it. Scientific files are not uploaded to a service.
- The initial Mac bundles had valid ad-hoc integrity signatures and hardened
  runtime. They were not yet publisher-signed or Apple-notarized; the signing
  refresh below records their replacement. Packaged checks run
  `codesign --verify --deep --strict` both before and after running the GUI.
  Python uses `-B`: importing packages must not create bytecode caches inside
  the signed application. A post-run check confirmed zero `.pyc` files and
  an unchanged valid resource signature.
- Intel Mac cryptography is built from the current pinned source with static
  OpenSSL; linkage checks reject dependencies on the build machine's libraries.
  The Mac Vulkan loader is built from checksum-pinned Khronos sources because
  Electron omits a library needed by Chromium's software graphics path. Both
  Python and graphics libraries are inside the application bundle.

`desktop/smoke.cjs` checks all nine native input commands, menu navigation,
structure opening, native file IPC, dirty Save, Save As preserving the original,
Open in new tab with a retained handle, HTML format/profile retention at
720×480, cancelled Quit, internal New/Close, and context isolation. It exports
an 800×600 PNG and counts colored atom pixels to reject blank rendering.
It also checks all 23 workbench routes at 1440, 1024 and 390 pixels for horizontal
clipping and input-unit overlap: **69 route/width combinations per run**.
Five Node tests independently cover file authority and interrupted/conflicting
saves. `scripts/test_packaged.py` repeats the GUI checks outside the checkout
and clears stale result files before launch.

Local Apple-silicon validation passed with both the normal GPU and the explicit
CI software graphics path. The fully packaged, signed bundle passed outside
the checkout, including all 69 layout checks. Desktop OS/architecture delivery
was initially gated by `.github/workflows/desktop.yml`: Apple silicon, Intel
Mac and Windows each passed both development-host and packaged-app checks
before installers were attached. The signing refresh now separates tested CI
candidates from public promotion, preventing unsigned automatic overwrites.

In addition to Electron's native-input regression, the actual Mac application
was opened through Launch Services and driven with OS keyboard input. All nine
required Command combinations were observed: the five settings commands
selected the expected tools and focused their controls, New/Close changed only
internal document tabs, and Save/Save As opened the project save UI. The native
Command+O file chooser also handed the disposable XYZ fixture to the existing
Reader/Frames/View/Edit import dialog. Automated integration tests provide the
file-write and round-trip assertions; physical keyboard checks were performed
on macOS, not on a physical Windows machine.

All three final desktop builds passed on commit
`dc0146981640eb2a554c3a65b2fa09e5c6ef2f2f` in
[workflow 35717604992](https://github.com/lgyEthan/v_ase/actions/runs/35717604992).

| Platform | Native host and packaged-app checks |
| --- | --- |
| macOS 15, Apple silicon | [Passed](https://github.com/lgyEthan/v_ase/actions/runs/35717604992/job/106712805294) |
| macOS 15, Intel | [Passed](https://github.com/lgyEthan/v_ase/actions/runs/35717604992/job/106712805202) |
| Windows x64 | [Passed](https://github.com/lgyEthan/v_ase/actions/runs/35717604992/job/106712804911) |

Each target produces an installer and a portable ZIP. The attached
`v_ase-desktop-0.4.1-source.tar.gz` identifies the corresponding desktop source;
the original Python release tag and distributions remain unchanged.
`desktop-validation.zip` contains six result sets (development and packaged
app for each platform) and their rendered images/workspace screenshots.
`desktop-SHA256SUMS.txt` covers the desktop downloads and evidence archive.

## Initial public desktop download verification

After publication, the release API listed all nine desktop artifacts alongside
the unchanged Python wheel and source distribution. Every desktop artifact's
server-reported SHA-256 matched `desktop-SHA256SUMS.txt`. The Apple-silicon ZIP
and validation archive were independently downloaded; their locally computed
digests matched, and both archives passed ZIP integrity checks.

| Published installer | SHA-256 |
| --- | --- |
| `v_ase-0.4.1-mac-arm64.dmg` | `3c55082072e44a07f922a306bb6466dd92bbccf6c513f27de84349657cffb06b` |
| `v_ase-0.4.1-mac-x64.dmg` | `a00b015bf7de4f2d908a34cfef249aa006f7e8b6d07982a7742c532bd95bb700` |
| `v_ase-0.4.1-win-x64.exe` | `4e2d6f780dec5b41be1b4e77efa3524b7cc5c06db6a7563c4f9e9c40b24211ca` |

The downloaded Apple-silicon application was extracted outside the repository.
Its private Python imported v_ase 0.4.1, ASE, matscipy and rhino3dm successfully
without using the checkout or an installed system Python. All 77 scientific
and frontend package files again matched the published wheel byte-for-byte.
The application passed `codesign --verify --deep --strict` before and after
those imports, with zero generated `.pyc` files.

The public validation archive contains six successful result files: development
and packaged runs for all three platforms. Each records all nine commands,
native Save, scientific project round trips, HTML profile retention, new-tab
opening, Quit cancellation, isolated renderer privileges, all 69 layout checks,
and a nonblank 800×600 render. Published Windows and Intel Mac workspace
screenshots and the Intel rendered image were also inspected visually. This
verifies the shipped artifacts and their recorded CI checks; it does not imply
physical Windows keyboard testing or compatibility with untested OS versions.


## Developer ID and notarization refresh — 22 September 2026

The initial ad-hoc Mac downloads described above are replaced by Developer ID
signed and Apple-notarized DMGs and ZIPs. This is a desktop packaging refresh
of **0.4.1**, not a replacement Python release. The PyPI wheel, sdist and tag
remain unchanged.

- Identity: **Developer ID Application: Giyeok Lee (B89YQRGQ6C)**.
- Certificate SHA-1: `290155F7F6CF0A9AA22E93F9928B2CEA210C272D`.
- The tested original CI apps were signed inside out, including **273 unique
  Mach-O binaries per architecture**, with secure timestamps and hardened
  runtime. The existing Electron entitlements were retained. Private keys and
  notarization credentials stayed in the maintainer's local Keychain.
- The two changed canonical agent guidance files were synchronized into each
  Mac candidate before signing; scientific Python/static files still match
  the published wheel. The host ASAR is identical in the two input apps and
  was not modified by signing.
- Every native binary passed strict signature, Developer ID authority, team,
  timestamp and hardened-runtime checks. Both apps and both DMGs passed
  ticket validation and Gatekeeper assessment as **Notarized Developer ID**.
- Each final DMG was mounted read-only: its Applications link points to
  `/Applications`, and its enclosed app retains a valid signature and stapled
  ticket. ZIPs contain the already-stapled app; ZIPs themselves cannot carry
  a stapled ticket.
- Packaged GUI checks passed before and after app stapling: nine native-input
  commands, native Save/Save As, `.vase` and HTML round trips, 720×480 HTML
  profile retention, internal New/Close, cancelled Quit, renderer isolation,
  all 69 layout combinations, and nonblank 800×600 rendering. Final renders
  contain 75,582 oxygen-colored pixels on ARM and 75,668 on Intel. Screenshots
  were inspected. The additional local Intel runs used **Rosetta/software
  graphics**; they are not misreported as physical Intel-machine tests.
- Strict signatures remain valid after launch and there are zero `.pyc` files
  inside either bundle. Node file-safety tests: **5 passed**. Canonical agent
  guide regressions: **28 passed**. Strict Sphinx HTML builds passed.
- `2fd0cba57375cd4ef98c67abc88bd2f4390f5fe9` adds signing/verification helpers,
  an explicit app-path packaged test, current agent guidance, and release
  protection. CI retains ad-hoc candidates and evidence; it cannot overwrite
  notarized public files. Public promotion requires the documented checks.
- Refreshed [workflow 35731690584](https://github.com/lgyEthan/v_ase/actions/runs/35731690584)
  passed all three platforms at that signing/documentation commit, including
  native-host and packaged-app tests on Intel and ARM GitHub runners
  and Windows x64.
- Windows retains the same scientific/GUI implementation and remains
  **not publisher-signed**. Its refreshed CI packages synchronize the bundled
  agent guidance so it does not incorrectly report the old Mac signing status.

| Apple submission | ID | Result |
| --- | --- | --- |
| arm64 APP | `e1b54868-4024-4c7e-8419-f54e9fe8f426` | Accepted; no reported issues |
| arm64 DMG | `866bf6c0-6a61-45fe-87d6-4f92a9d372dd` | Accepted; no reported issues |
| x64 APP | `5ed0d897-0d36-4ea1-9f2c-e4a372cecc16` | Accepted; no reported issues |
| x64 DMG | `5902ed43-ab35-4328-b25f-49a6a89a9eae` | Accepted; no reported issues |

| Final Mac asset | SHA-256 after stapling |
| --- | --- |
| `v_ase-0.4.1-mac-arm64.dmg` | `c646a70230fa4628cf1bcb5a672aa22698c5766941dad83a4f1c1caed92c9692` |
| `v_ase-0.4.1-mac-arm64.zip` | `f0a2b03e7a26a26a79cea9b939366cf5fe2245d9f7c1572d6331561c2753c2fb` |
| `v_ase-0.4.1-mac-x64.dmg` | `019be3594e26e41abb5845e49a9b1a85bba3e69d6e9f6bb2476d24c273ac4213` |
| `v_ase-0.4.1-mac-x64.zip` | `4a41482b35a4a05f3b94c2faa4c227ec1b87b475c39a114446d166f6f4ed4e5b` |

The release's `mac-notarization.json` records input/output provenance and
Apple submission results. `desktop-signing-validation.zip` carries sanitized
signed-app checks, Apple's logs and refreshed CI evidence, excluding browser
profiles and application logs. `desktop-validation.zip` preserves the earlier
cross-platform evidence. The desktop source archive includes signing tools
and current documentation; `desktop-SHA256SUMS.txt` covers the delivered
artifacts. Public download verification is performed after upload.
