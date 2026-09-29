# Install the desktop app

Use v_ase on macOS or Windows without installing Python. The desktop app includes
the scientific tools and uses your system's file dialogs and keyboard shortcuts.

## Choose a download

| Your computer | Download |
| --- | --- |
| Apple silicon Mac (M-series), macOS 15+ | [Apple silicon installer](https://github.com/lgyEthan/v_ase/releases/download/v0.4.10/v_ase-0.4.10-mac-arm64.dmg) |
| Intel Mac, macOS 15+ | [Intel installer](https://github.com/lgyEthan/v_ase/releases/download/v0.4.10/v_ase-0.4.10-mac-x64.dmg) |
| Windows 10/11, Intel or AMD 64-bit | [Windows installer](https://github.com/lgyEthan/v_ase/releases/download/v0.4.10/v_ase-0.4.10-win-x64.exe) |

On a Mac, **Apple menu → About This Mac** shows your chip or processor.
Windows users can check **Settings → System → About → System type**.
There is no native Windows ARM or 32-bit build. For Linux, or a compatible
Python environment on another system, use [Python installation](installation.md#python-installation).

## Install on macOS

1. Download and open the matching `.dmg` file.
2. Drag **v_ase** into **Applications** and wait for the copy to finish.
3. Eject the disk image, then open **v_ase** from **Applications**.
4. Choose **File → Open** (`Command+O`) to open your structure or project.

The Mac app is signed and notarized. A first-launch confirmation that the app
was downloaded from the internet is normal; choose **Open** if you downloaded
it from the release linked above.

## Install on Windows

1. Download and run **v_ase-0.4.10-win-x64.exe**.
2. Follow the installer to choose where to install the app.
3. Open **v_ase** from the Start menu.
4. Choose **File → Open** (`Ctrl+O`) to open your structure or project.

The Windows installer is currently unsigned, so SmartScreen may show
**Windows protected your PC**. If you downloaded it from the release above,
**More info → Run anyway** may be available. If your organisation blocks it,
ask your administrator; do not disable Windows protection.

## Open your files

Use **File → Open**, or drag a file into the editor. v_ase reads structures such
as `.xyz`, `.extxyz`, `.vasp`, `.cif` and `.traj`, as well as its own `.vase`
projects. [Supported formats](formats.md).

A `.vase` project restores its saved view, appearance, frame and Edit/View mode.
It opens in a new tab when you are already working on another document.
For structure files, you can choose a new tab, replace the current structure,
or add frames to its trajectory. An empty document needs no destination choice.

Use **Save** (`Command/Ctrl+S`) to save a project and **Save As**
(`Command/Ctrl+Shift+S`) to make a separate copy. [Saving and sharing](save-projects.md).

## Open .vase by default

If double-clicking a `.vase` file does not open v_ase, choose the app once in
your operating system:

### macOS file association

1. In Finder, select a `.vase` file and press `Command+I` for **Get Info**.
2. Under **Open with**, choose **v_ase**. If needed, choose **Other…** and
   select it from Applications.
3. Click **Change All…** to use v_ase for other `.vase` files.

### Windows file association

1. Right-click a `.vase` file and choose **Open with → Choose another app**.
2. Select **v_ase**, or browse to the installed `v_ase.exe` if it is not listed.
3. Choose **Always**, or **Always use this app** on Windows 10.

Choose the installed application, not the downloaded installer.

## Open .vasp and other structure files

Other structure types keep their existing default application. To change one,
use the same **Open with** steps on a file of that type. You can also use
**Open with** just once without changing its default.

For extensionless `POSCAR` or `CONTCAR`, use **File → Open**. If the reader is
not recognised, choose **POSCAR / CONTCAR** in the import dialog.
Keep ordinary HTML files associated with your browser; use v_ase's **File → Open**
for an editable v_ase HTML project.

## Work with documents

Use the **+** button to create a tab. Drag a tab below the tab bar to move it to
its own window, or choose **File → Move tab to new window**.

`Command+W` on Mac or `Ctrl+W` on Windows closes the active tab. The last tab
closes its window; the last window closes the app. Unsaved changes always offer
**Save**, **Discard** or **Cancel**. [Workspace](workspace.md) · [All shortcuts](shortcuts.md).

## Update or uninstall

To update, quit v_ase and download the newer installer from
[GitHub Releases](https://github.com/lgyEthan/v_ase/releases).
On Mac, replace the copy in Applications. On Windows, run the new installer.
Keep your projects outside the application folder. There are no automatic updates.

To uninstall, quit the app and move it to Trash on Mac, or remove it through
**Settings → Apps** on Windows. Your separate Python or Jupyter installation is unaffected.

## ZIP downloads and checksums

The [release page](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.10) also
provides ZIP downloads. Extract the entire ZIP first. On Mac, move **v_ase.app**
to Applications; on Windows, run **v_ase.exe** and keep its adjacent files together.
The Windows ZIP does not create Start-menu entries or file associations.

If a download appears incomplete, download it again. You can check its integrity
against [desktop-SHA256SUMS.txt](https://github.com/lgyEthan/v_ase/releases/download/v0.4.10/desktop-SHA256SUMS.txt):

```bash
# macOS; use mac-x64 for an Intel download
shasum -a 256 v_ase-0.4.10-mac-arm64.dmg
```

```powershell
# Windows
Get-FileHash .\v_ase-0.4.10-win-x64.exe -Algorithm SHA256
```

## Python, Jupyter and agents

Use a separate [Python installation](installation.md#python-installation) for
Jupyter or custom calculators. Exchange complete documents with the desktop app
using `.vase` files. Python and ASE are already included in the desktop app;
Blender is only needed if you want to run a [Blender export](export-structures.md#blender).

To connect an agent to your open desktop document, use
**Help → Copy agent connection URL** and follow the [connection guide](ai-cli.md).

## Diagnostics

If the app does not open, check that the download matches your computer.
On Mac, launch the Applications copy after ejecting the DMG. On Windows,
reinstall or extract the whole ZIP rather than copying only the executable.

For other problems, include **Help → About this runtime**, your OS version and
the error message in a [bug report](https://github.com/lgyEthan/v_ase/issues).
If a log is requested, `backend.log` is in:

- Mac: `~/Library/Application Support/v_ase/`
- Windows: `%APPDATA%\v_ase\`

Check logs for private paths before sharing them.
