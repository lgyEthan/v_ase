# macOS and Windows desktop apps

The desktop app runs the same v_ase scientific editor with its own Python
backend. You do not need to install Python, Node.js or a browser. Native menus
provide document shortcuts without browser conflicts or fullscreen mode.

## Choose a download

Open the [v0.4.1 GitHub release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.1)
and expand **Assets**, or use a direct installer link below. GitHub's **Source
code** archives and the Python `.whl`/`.tar.gz` files are not desktop installers.

| Computer | Requirement | Installer |
| --- | --- | --- |
| Apple silicon Mac (M-series) | macOS 15 or newer | [Download Apple silicon DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.1/v_ase-0.4.1-mac-arm64.dmg) |
| Intel Mac | macOS 15 or newer | [Download Intel DMG](https://github.com/lgyEthan/v_ase/releases/download/v0.4.1/v_ase-0.4.1-mac-x64.dmg) |
| Windows PC, Intel/AMD x64 | Windows 10 or 11, 64-bit | [Download Windows EXE](https://github.com/lgyEthan/v_ase/releases/download/v0.4.1/v_ase-0.4.1-win-x64.exe) |

On a Mac, **Apple menu → About This Mac** shows either an Apple **Chip** or an
Intel **Processor**. On Windows, **Settings → System → About → System type**
identifies the processor and OS architecture. Windows ARM and 32-bit Windows
do not have native builds in this release. The Mac minimum includes the
bundled scientific/Rhino dependencies; older Macs can use a compatible Python
environment and the browser GUI instead.

## Install on macOS

1. Download the matching `.dmg` above and open it in Finder.
2. Drag **v_ase.app** into **Applications**. Wait for the copy to finish.
3. Eject the v_ase disk image. Open **Applications → v_ase**; run the installed
   copy, not the copy inside the mounted disk image.
4. The first launch starts the bundled Python backend. Wait for the editor
   window, then use **File → Open** or **Command+O** to select a project or
   structure. No `pip`, Conda, Node.js or terminal setup is necessary.

The Mac DMGs and apps are **signed with Developer ID Application: Giyeok Lee
(B89YQRGQ6C) and notarized by Apple**. Both carry stapled notarization tickets;
the portable ZIP also contains the app with its ticket. macOS may show the
normal confirmation that the app was downloaded from the internet: choose
**Open** after checking the source. The current downloads do not require an
**Open Anyway** exception or disabling Gatekeeper.

The Mac files were refreshed on 22 September 2026 to replace the initial
ad-hoc-signed downloads while retaining v_ase 0.4.1. If an older copy reports
an unidentified developer, quit it and download the current matching DMG
again; compare its checksum and replace the Applications copy. If a current,
checksum-matching copy is blocked, keep the exact error and consult your
administrator on a managed Mac. Do not remove quarantine attributes or
disable Gatekeeper as an installation step. See
[Apple's explanation of Developer ID distribution](https://developer.apple.com/developer-id/).

The release's `mac-notarization.json` records the public signing identity,
Apple submission results and final hashes. `desktop-SHA256SUMS.txt` covers
the final downloads. No Apple developer account is needed to install the app.

## Install on Windows

1. Download **v_ase-0.4.1-win-x64.exe** and open it from File Explorer.
2. The current build is **not publisher-signed**. If SmartScreen displays
   **Windows protected your PC**, verify the source and checksum, then use
   **More info → Run anyway** if offered. Do not disable SmartScreen or
   antivirus protection. A managed PC may require administrator approval.
3. Follow the installer, choose the destination when offered, and complete
   installation. The default installation is for your Windows user and does
   not require administrator access.
4. Launch **v_ase** from the Start menu or the installed shortcut. Wait for the
   bundled backend to start, then use **File → Open** or **Ctrl+O**.

Install the EXE when you want normal Start-menu integration and `.vase` file
registration. The default per-user application directory is
`%LOCALAPPDATA%\Programs\v_ase\`; a custom installation directory takes
precedence. The executable for **Open with** is the installed `v_ase.exe`,
not the downloaded installer and not the bundled `python.exe`.

## ZIP downloads and checksums

ZIPs are alternatives to the installers. Extract the **entire** archive to a
permanent location first. On Mac, move the extracted **v_ase.app** into
Applications. On Windows, open **v_ase.exe** in the extracted directory and
keep all adjacent files and resource folders with it. Opening an EXE from
inside a ZIP, or copying only the EXE, cannot provide its bundled runtime.
The Windows ZIP does not run the installer or register file associations;
choose the executable manually when configuring **Open with**. Moving it
later invalidates that saved association.

Download [desktop-SHA256SUMS.txt](https://github.com/lgyEthan/v_ase/releases/download/v0.4.1/desktop-SHA256SUMS.txt)
from the same release. In the download directory, compute the relevant hash:

```sh
# macOS Terminal; substitute mac-x64 for an Intel download.
shasum -a 256 v_ase-0.4.1-mac-arm64.dmg
```

```powershell
# Windows PowerShell.
Get-FileHash .\v_ase-0.4.1-win-x64.exe -Algorithm SHA256
```

Compare it with the line for that exact filename in the checksum file.
Matching hashes verify download integrity, not the publisher's identity.
For Mac downloads, Developer ID signatures and Apple's notarization checks
provide the separate OS-level publisher and distribution checks.

## Open .vase by default

**Yes: `.vase` can open in the desktop app when double-clicked.** The Mac app
and Windows installer declare it as a v_ase project type. Registration makes
the app available; the OS or a previously chosen default may still require
you to select it. v_ase does not override the user's existing default by force.

### macOS file association

1. Install v_ase in Applications and launch it once.
2. In Finder, select a `.vase` file and choose **File → Get Info** (Command+I).
3. Expand **Open with**, select **v_ase**, and click **Change All…** to apply
   it to `.vase` files. Confirm the change.
4. If v_ase is missing, select **Other…**, enable **All Applications** if
   needed, and choose `/Applications/v_ase.app`.

To open one file without changing its default, use **Open With → v_ase** from
the file's context menu. These are the standard
[macOS file association controls](https://support.apple.com/en-mo/guide/mac-help/mh35597/mac).

### Windows file association

1. Right-click a `.vase` file in File Explorer and choose **Open with → Choose
   another app**.
2. Select **v_ase**. If it is missing, use **Choose an app on your PC** or
   **More apps → Look for another app on this PC** (wording varies by Windows
   version) and select the installed `v_ase.exe`.
3. On Windows 11 choose **Always**. On Windows 10 enable **Always use this app
   to open .vase files**, then confirm. Choose **Just once**, when offered,
   for a single file instead.

Alternatively, use **Settings → Apps → Default apps** and select the default
for `.vase`; Windows 10 exposes **Choose default apps by file type**. See
[Microsoft's default-app instructions](https://support.microsoft.com/en-us/windows/apps/change-default-apps-in-windows).

Double-clicking a file hands it to the existing v_ase window, or starts the app
if needed. It opens the usual **Open File** dialog: choose **View** or **Edit**,
then **Replace**, or **Open in new tab → Open New Tab** when another document
is present. It is not a silent replacement of unsaved work. **Replace** and
**Open in new tab** restore a project's appearance; **Add to trajectory**
imports its structures only.

## Open .vasp and other structure files

**This is already supported; a future version is not required.** Repeat the
association steps above using a `.vasp` file. Unlike `.vase`, `.vasp` is not
predeclared by the 0.4.1 installer, so you may need to browse to v_ase manually.
You can choose it just once or make it the default for `.vasp`. The same method
works for other [supported formats](formats.md), such as `.xyz` and `.cif`.
An OS association only selects the application; it does not add a new reader
or turn an unsupported file into a supported structure.

For `.vasp`, **Auto detect** normally selects the VASP reader. If the name is
ambiguous, select **Reader → POSCAR / CONTCAR** in the Open File dialog.
Extensionless `POSCAR` and `CONTCAR` have no `.vasp` extension to associate;
open them with **File → Open** and select **All files** in the native chooser
if necessary. Avoid changing the default for all extensionless files.

Opening a `.vasp` structure does not make it a v_ase project. Save the editor's
complete state as `.vase` or project HTML; use the existing POSCAR export when
you need VASP-compatible structural output. Merely associating or opening a
file does not convert or overwrite it. Leave `.html` associated with a browser
unless you intentionally want a different system-wide default; open embedded
v_ase HTML projects through **File → Open**.

## Update or uninstall

There is no automatic update service. Quit v_ase, download a newer matching
installer, and install it explicitly. On Mac, replace the Applications copy;
on Windows, run the new installer. Keep projects outside the application and
ZIP extraction directories.

To uninstall, quit v_ase and move the Mac app to Trash, or use Windows
**Settings → Apps → Installed apps** (Windows 11) / **Apps & features**
(Windows 10). For a Windows ZIP, remove its extracted directory after saving
projects elsewhere. Choose another default app if an association still points
to the removed executable. Removing the app does not require uninstalling
your independent Python/Jupyter environment.

## Work with documents

File → Open (Command+O / Ctrl+O) selects a structure or project anywhere on your
computer. The existing Reader, Frames, View/Edit and Replace/Add to trajectory/
Open in new tab choices remain available. Project appearance and scientific
content are restored by the same reader as the browser GUI.

Save writes to the approved current project file. Save As chooses a new file.
`.vase` stays `.vase`; project HTML stays HTML and retains its output profile.
Saving detects external changes and refuses to silently overwrite them. Use
Save As or reopen the externally modified file. A cancelled or failed save
leaves the prior file and dirty document intact.

| Action | macOS | Windows |
| --- | --- | --- |
| New internal document | Command+N | Ctrl+N |
| Close internal document | Command+W | Ctrl+W |
| Save / Save As | Command+S / Command+Shift+S | Ctrl+S / Ctrl+Shift+S |
| Atom color and radius properties | Command+Shift+P | Ctrl+Shift+P |
| Bonds | Command+B | Ctrl+B |
| Supercell | Command+Shift+B | Ctrl+Shift+B |
| Renderer and output px/Å | Command+Shift+A | Ctrl+Shift+A |
| Cell transformation | Command+E | Ctrl+E |

The [existing viewport, selection and G/R/S shortcuts](shortcuts.md) are
unchanged. Typing into a field retains normal text editing. Close document
keeps the app open, including when the last document becomes a blank tab.
Quit (Command+Q on macOS, Alt+F4 on Windows) checks every document for unsaved
changes and active jobs before stopping the app and its Python server.

## Python, Jupyter and agents

The private desktop runtime does not replace your Python environments.
`pip install v_ase-gui`, `v_ase gui`, Python `view(...)`, and `%v_ase inline`,
`%v_ase browser` and `%v_ase auto` continue to work. Use your Python environment
for custom calculators and project-specific dependencies; the desktop app does
not import packages from Conda or Jupyter. Transfer editable scenes using
`.vase` projects.

The bundled runtime includes the normal scientific dependencies, video support,
MCP support and optional Rhino export. Blender export produces the same script
as the web GUI; running that script still requires Blender, as before.

To let an agent refine the **same desktop document**, choose native
Help → Copy agent connection URL. Use that loopback URL with the existing
[CLI/HTTP interface](ai-cli.md):

```bash
v_ase api 'COPIED_CONNECTION_URL' describe --profile structure
```

Keep the desktop app open. Its URL changes when the app restarts and is not a
cloud connection. Use the normal MCP/tunnel setup for a remote agent.

## Diagnostics

The app starts a loopback Python server and stops it on Quit. It does not
modify system Python, install a background service, or upload structures.
Backend diagnostics are in `backend.log` under:

- macOS: `~/Library/Application Support/v_ase/`
- Windows: `%APPDATA%\v_ase\`

Include the desktop version, OS and relevant error text when reporting a
problem. Inspect logs for private paths before sharing them. Source and build
instructions are in [desktop/README.md](https://github.com/lgyEthan/v_ase/blob/main/desktop/README.md).
