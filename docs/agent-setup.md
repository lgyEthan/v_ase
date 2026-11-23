# Install the Skill and connect an agent

Install the scientific Skill so your agent knows how to use v_ase, then connect
MCP so it can call the live tools. The Skill installer does not install the
scientific Python runtime or register an MCP server.

This `main` guide includes source changes after published **0.4.13**. Existing
desktop downloads and PyPI remain the published release. Match the Skill and
runtime channel below; a shared version number alone does not identify a local
source build.

## Choose a matching runtime and Skill

| Your runtime | Skill source |
| --- | --- |
| Current Python source, or a development host explicitly using that source runtime | `lgyEthan/v_ase` |
| Published desktop app or PyPI **0.4.13** | `lgyEthan/v_ase@v0.4.13` |
| A specific source commit or release tag | The same commit or tag in `owner/repo@REF` |

The commands below target current GitHub source. For published 0.4.13, replace
the Skill source as shown above and install `v_ase-gui[mcp]==0.4.13` instead of
the source package. The [release page](https://github.com/lgyEthan/v_ase/releases/tag/v0.4.13)
contains the published desktop downloads.

## Install the Skill with npx

The optional installer needs Node.js **22.20 or newer**. v_ase itself runs
without Node.js. Choose the coding clients you use; this example targets all
three and makes the Skill available across projects:

```bash
npx skills@latest add lgyEthan/v_ase \
  --skill visualizing-atomic-structures-with-v-ase \
  -a claude-code codex cursor -g -y
```

Remove agents you do not use. Omit `-g` to install for the current project;
omit `-y` to review the installer choices. To inspect without installing:

```bash
npx skills@latest add lgyEthan/v_ase --list
```

The repository's `skills.sh.json` points to the canonical
`v_ase/skills/visualizing-atomic-structures-with-v-ase/` directory. The installer
includes `SKILL.md`, its `references/` and agent metadata together. There is no
second, independently edited copy of the scientific guide.

To install the current local checkout instead:

```bash
npx skills@latest add ./v_ase/skills \
  --skill visualizing-atomic-structures-with-v-ase \
  -a claude-code codex cursor -g -y
```

Update tracked global installations with `npx skills@latest update -g -y`.
The installer’s [source formats, scopes and client options](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
also cover version-pinned repositories. These commands target local coding
clients; ChatGPT web/app uses the [connected MCP/plugin workflow](chatgpt-local.md).

## Install a matching runtime

For current GitHub source, use a fresh Python environment with Python 3.10 or newer:

```bash
python -m pip install "v_ase-gui[mcp] @ git+https://github.com/lgyEthan/v_ase.git@main"
v_ase --version
```

An existing source checkout can instead use `python -m pip install '.[mcp]'`.
When replacing an already installed 0.4.13 snapshot in an existing environment,
add `--force-reinstall`: the source version string has not yet been advanced for
a new public release. Verify the imported source and tool contract, not only
`v_ase --version`.
The optional `rhino` extra adds Rhino export. A desktop app already contains
its Python runtime and MCP adapter; it does not add `v_ase` to your terminal PATH.
Use the bundled Python as explained below rather than modifying a separate
Conda/Jupyter environment just to connect to the desktop app.
The normal desktop packaging helper uses the published wheel; building the host
from `main` does not by itself change its scientific runtime. For source
development, set `VASE_DEV_PYTHON` to the Python environment installed from that
source. [Desktop development](https://github.com/lgyEthan/v_ase/blob/main/desktop/README.md).

## Register MCP

Add a server in your coding client's MCP settings. Keep unrelated servers.
With the Python CLI installed, a stdio definition is:

```json
{
  "mcpServers": {
    "v_ase": {
      "command": "v_ase",
      "args": ["mcp", "--discovery", "all"]
    }
  }
}
```

This is the common JSON form; clients with another configuration format use
the same executable and argument list. Use the absolute executable path if the
client does not inherit your terminal PATH. This starts an owned GUI; its stderr
reports the human URL. Keep the GUI connected and keep the MCP process running.

### Share the document already open

Copy **Help → Copy agent connection URL** from the desktop app, or the
`command_url` printed by `v_ase gui STRUCTURE --cli`. Use that complete URL as
one argument:

```json
{
  "mcpServers": {
    "v_ase": {
      "command": "v_ase",
      "args": ["mcp", "--connect", "COMMAND_URL", "--discovery", "all"]
    }
  }
}
```

Replace `COMMAND_URL` with the actual value. The adapter attaches to that live
document/workspace; it does not replace its structure. The URL changes after an
app restart. Closing this attached adapter leaves the existing GUI running.

For a **desktop-only installation**, use the app's bundled Python executable
as `command` and put `-m`, `v_ase.cli` before `mcp` in the argument list:

```json
{
  "mcpServers": {
    "v_ase": {
      "command": "/Applications/v_ase.app/Contents/Resources/python/bin/python3",
      "args": ["-I", "-B", "-m", "v_ase.cli", "mcp", "--connect", "COMMAND_URL", "--discovery", "all"]
    }
  }
}
```

On macOS, replace the app location if installed in your user Applications
folder. On Windows, use `resources\python\python.exe` inside the installed
application directory and the same argument list. Avoid shell quoting inside
the JSON argument strings. The app's private dependencies and source channel
stay together. [MCP lifecycle and transports](ai-tools.md).

## Verify the connection

1. Open the reported human URL, or keep the existing GUI open.
2. Confirm the client lists callable `vase_…` tools. A reachable endpoint alone
   does not prove the GUI is ready.
3. Have the agent read the installed Skill and a compact scene snapshot. If the
   client has not loaded the Skill, `vase_read_guide(topic="skill")` provides the
   runtime's own copy.
4. For a test figure, inspect state, make a guarded display change and inspect
   the rendered image. Keep the inspected document ID and revision on edits.

If the adapter reports a tool-contract mismatch, update the runtime and adapter
together rather than weakening the checks. For cloud ChatGPT, use the documented
tunnel/plugin connection; cloud localhost cannot address your desktop app.

For an agent-readable starting point, use
[`llms.txt`](https://raw.githubusercontent.com/lgyEthan/v_ase/main/llms.txt).
