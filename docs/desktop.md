# macOS and Windows desktop apps

The desktop app runs the same v_ase scientific editor with its own Python
backend. You do not need to install Python, Node.js or a browser. Native menus
provide document shortcuts without browser conflicts or fullscreen mode.

## Install

Download from the [v0.4.1 GitHub release](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.1):

| Computer | Download | Installation |
| --- | --- | --- |
| Apple silicon Mac | `v_ase-0.4.1-mac-arm64.dmg` | Open the disk image and drag v_ase to Applications. |
| Intel Mac | `v_ase-0.4.1-mac-x64.dmg` | Open the disk image and drag v_ase to Applications. |
| Windows, 64-bit Intel/AMD | `v_ase-0.4.1-win-x64.exe` | Run the per-user installer; administrator access is not required. |

ZIP archives are also provided. Extract the entire archive before opening the
app; keep its Python resources beside it. macOS 12 or newer and Windows 10 or
newer are required. Windows on ARM is not a native build target in this release.

These initial desktop builds are **not Apple-notarized or publisher-signed**.
macOS may require System Settings → Privacy & Security → Open Anyway after
attempting to open the app. Windows may display a SmartScreen notice; check the
download source and file hash before choosing More info → Run anyway. The
release includes `desktop-SHA256SUMS.txt`. Do not disable Gatekeeper,
SmartScreen, or antivirus protection system-wide.

There is no automatic update service. Install a newer release explicitly;
saved projects remain ordinary files outside the application bundle.

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
