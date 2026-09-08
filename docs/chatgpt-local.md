# Connect ChatGPT to your local v_ase

Control the v_ase document on your computer from a **ChatGPT Chat conversation**.
You can inspect the scene, change a figure and render an image while the same
GUI stays available for your own edits.

**Personal connection · macOS/Linux**

```{figure} assets/chatgpt-local.*
:alt: ChatGPT connects through a private tunnel to the local v_ase MCP adapter and shared GUI.
```

[Install](#1-install-a-private-local-runtime) · [Account setup](#3-create-and-associate-your-tunnel) · [Daily use](#daily-use-one-launcher) · [Another computer](#a-second-computer-or-another-person)

## What you need

| On your computer | In your own account |
| --- | --- |
| Python 3.10+ and v_ase with MCP dependencies | Access to ChatGPT Developer mode |
| OpenAI's `tunnel-client` program | A tunnel associated with your ChatGPT workspace |
| An open v_ase GUI and running terminal | An authorized tunnel runtime API key |

Installing the tunnel client **does not create the tunnel, key or ChatGPT
connection**. Installing a plugin **does not install Python**. Complete the
computer setup and account setup below once; later sessions use just the launcher.

All paths below are generic defaults. `YOUR_TUNNEL_ID` and `YOUR_REGISTERED_APP_ID`
are placeholders to replace with your own values. No author's connection is
included. Each command block has its own **Copy** button.

## 1. Install a private local runtime

Open a terminal in a new setup folder. Check that Python 3.10 or newer is available:

```bash
python3 --version
```

Create a folder for structures you want the connection to access:

```bash
mkdir -p "$HOME/vase-workspace"
```

Download the two small installer files from this release. These files use
Python's standard library; the installer obtains v_ase and its dependencies from PyPI.

```bash
curl -fL https://raw.githubusercontent.com/lgyEthan/v_ase/v0.3.5/v_ase/chatgpt_bootstrap.py -o chatgpt_bootstrap.py
```

```bash
curl -fL https://raw.githubusercontent.com/lgyEthan/v_ase/v0.3.5/v_ase/chatgpt.py -o chatgpt.py
```

Install v_ase and MCP into a dedicated environment:

```bash
python3 chatgpt_bootstrap.py --workspace "$HOME/vase-workspace"
```

**Expected result:** an isolated runtime and launcher are created under
`~/.local/share/v_ase/chatgpt/`. Your existing conda/DFT environment is unchanged.
The setup may report `awaiting_tunnel_id` at this stage; step 3 supplies it.
Copy a structure into `vase-workspace` before asking ChatGPT to discover it.

## 2. Install the tunnel client

On **macOS**, install the official client using Homebrew:

```bash
brew install openai/tools/tunnel-client
```

Verify that it is available:

```bash
tunnel-client --version
```

On **Linux**, use the appropriate client installation from the
[official Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
The integrated v_ase foreground launcher currently supports macOS/Linux;
these commands are not a native Windows setup.

## 3. Create and associate your tunnel

1. Sign in to [Platform → Tunnels](https://platform.openai.com/settings/organization/tunnels).
2. Click **Create tunnel** and fill in the fields below.
3. Create it, then copy its generated `tunnel_…` ID.

| Field | Example or selection |
| --- | --- |
| Name | `v_ase-local` |
| Description | `Private MCP connection to my local visualizer` |
| Organizations | Your intended Platform organization |
| ChatGPT workspaces | The workspace in which you will use this connection |

A **ChatGPT workspace** is the ChatGPT account/workspace context that receives
access. It is separate from the Platform organization. A Platform organization
called “Personal” does not automatically identify the right ChatGPT workspace.
The picker may display an ID rather than a friendly name; do not guess or copy
someone else's ID. Use the intended account and verify its workspace access if
the correct choice is missing.

Save your tunnel ID locally, replacing the placeholder:

```bash
"$HOME/.local/share/v_ase/chatgpt/runtime/bin/python" \
  "$HOME/.local/share/v_ase/chatgpt/chatgpt_bridge.py" configure \
  --tunnel-id YOUR_TUNNEL_ID
```

**Expected result:** local connection settings contain your tunnel ID.
No API key is saved by this command.

## 4. Create a key for tunnel access

1. Open [Platform → API keys](https://platform.openai.com/settings/organization/api-keys).
2. Create a secret key in the project authorized to use your tunnel.
3. Choose **Restricted** permissions. Enable the tunnel runtime permissions;
   leave unrelated model, file and training permissions disabled.
4. Save the secret privately so you can enter it again when starting the launcher.

The official permission names are **Tunnels: Read + Use** for runtime access and
**Read + Manage** for creating/managing tunnels. The key used to run v_ase does
not need model-generation permissions. Follow the exact choices exposed by the
current key editor and the [official permissions description](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
If the editor does not expose the required tunnel scope, check project access
instead of enabling unrelated permissions.

The secret is normally shown only when created. An existing valid, authorized
key can be reused; a new key is not required for every launch. Enter it only at
the launcher's hidden terminal prompt, never into this guide, a chat or a repository.

## 5. Start v_ase and the tunnel

Run:

```bash
"$HOME/.local/share/v_ase/chatgpt/start-vase-chatgpt.command"
```

Enter the runtime key at the hidden prompt and press Enter. Nothing is echoed
while you type. The launcher starts the local MCP adapter and GUI, then the
outbound tunnel. It does not persist the key.

| What you see | Meaning |
| --- | --- |
| `local_ready` | MCP and the matching GUI backend are reachable |
| `tunnel_ready` | The official tunnel client's readiness check passed |
| A v_ase browser tab | Keep this open for scene operations and rendering |

**Leave the terminal running and the computer awake.** `Ctrl+C` stops the
processes owned by this launcher. Closing its GUI tab leaves the backend alive;
reopen the reported human URL to reconnect the browser renderer. A ready tunnel
alone is not proof that a scene can render.

## 6. Add the connection in ChatGPT

1. In ChatGPT, open **Settings > Security and login > Developer mode**.
2. Open [ChatGPT Plugins](https://chatgpt.com/plugins) and choose the plus button.
3. Enter a name such as `v_ase Local` and a short description.
4. Under **Connection**, select **Tunnel**, then choose or enter your tunnel ID.
5. Create the connection and inspect its discovered tools.

Use the same ChatGPT workspace associated in step 3. Developer mode availability
can depend on account/workspace policy. The authoritative current screen labels
are in [OpenAI's connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## 7. Try a real structure

Download the {download}`ferrocene example <assets/examples/ferrocene.traj>` into
`vase-workspace`, then open it in the local GUI. Start a new ChatGPT **Chat**
conversation and enable the v_ase connection. Send:

```text
Inspect the current v_ase scene. Report its atom count and revision.
Keep the coordinates unchanged. Use a white background, show bonds,
and render a 1000 × 800 image. Inspect the rendered result.
```

**Expected result:** the ferrocene input has **21 atoms**. ChatGPT reads structured
scene state and produces a render from your live GUI. Check that the image has
the requested dimensions and that your GUI shows the same appearance.

For physical editing, explicitly ask for an edit and use the
[rotation example](rotate.md). A tool receipt or saved path alone does not prove
that the rendered image was inspected. See [MCP scene control](ai-scene.md).

## Daily use: one launcher

After the one-time setup, run the same launcher, enter your existing key, open
the GUI and enable the connection in ChatGPT. You do **not** need to create a new
tunnel or register another plugin on each use.

```bash
"$HOME/.local/share/v_ase/chatgpt/start-vase-chatgpt.command"
```

The dedicated environment runs v_ase even when your terminal has a different
conda environment active. Your simulation environment is needed only if the
GUI must use a calculator installed there.

## A second computer or another person

| Item | You, on a second computer | Another person starting fresh |
| --- | --- | --- |
| v_ase runtime and tunnel client | Install locally | Install locally |
| Tunnel ID | Reuse your authorized tunnel for a handoff | Create their own authorized tunnel |
| Runtime key | Reuse a valid authorized key, or issue one for the device | Use their own authorized key |
| ChatGPT connection | Reuse the existing connection in your same workspace | Register in their own workspace |
| Local configuration | Configure the ID and that computer's structure folder | Configure their own values |

For a handoff, **stop the old computer's launcher first**. This guide uses one
active computer per tunnel so calls reach one known live document. To control
both computers independently, give each a separate tunnel and ChatGPT connection.

On the new computer, complete steps 1–2, configure the existing ID using step 3,
and run step 5. Existing local files and Python environments are not transferred
by the tunnel or plugin installation.

## Optional: use an existing scientific environment

Use this only when an existing GUI must run with that environment's ASE
calculator. Install a compatible v_ase build there first. From the directory
containing your structure, start the GUI in that environment:

```bash
v_ase gui ferrocene.traj --cli --interactive
```

Keep that process running and open its reported `human_url`. Stop the previous
tunnel launcher. In a second terminal, connect the helper to the reported
`command_url`, replacing the placeholder:

```bash
"$HOME/.local/share/v_ase/chatgpt/runtime/bin/python" \
  "$HOME/.local/share/v_ase/chatgpt/chatgpt_bridge.py" configure \
  --connect YOUR_GUI_COMMAND_URL
```

Restart the launcher. The API key and tunnel registration are unchanged.
The GUI and MCP adapter must have compatible tool contracts. File discovery
follows the connected GUI's workspace.

## Optional: package a personal Skill bundle

The registered MCP connection supplies tools. A personal bundle can also carry
the scientific Skill and installer. This packaging command does not itself
install a Skill into ChatGPT web.

Copy the technical app ID beginning with `plugin_asdk_app…` from your registered
connection, then replace the placeholder below:

```bash
"$HOME/.local/share/v_ase/chatgpt/runtime/bin/python" \
  "$HOME/.local/share/v_ase/chatgpt/chatgpt_bridge.py" plugin \
  --app-id YOUR_REGISTERED_APP_ID
```

The output under `~/plugins/` contains your registered app ID in `.app.json`.
It excludes API keys and Python environments, but **is still personalized**.
Follow the supported [plugin packaging/install flow](https://developers.openai.com/plugins/build/plugins)
for the intended host. Do not publish that ZIP as a universal connection.
The copied installer uses v_ase 0.3.4 or newer. Use `--source` only when you
intend to install a particular local checkout or wheel.

## Troubleshooting

Run a local diagnostic:

```bash
"$HOME/.local/share/v_ase/chatgpt/runtime/bin/python" \
  "$HOME/.local/share/v_ase/chatgpt/chatgpt_bridge.py" doctor
```

| Symptom | Check |
| --- | --- |
| `awaiting_tunnel_id` | Complete step 3; installation alone creates no tunnel |
| Tunnel missing in ChatGPT | Account/workspace association and tunnel access |
| `local_ready` without `tunnel_ready` | Runtime key permissions, network and `tunnel.log` |
| `gui_unavailable` | Restart or reconnect the correct GUI backend |
| Tools connect but scene operations fail | Open the GUI browser and let it finish loading |
| File cannot be discovered | Put it inside the configured workspace |
| Runtime already running | Use its terminal or stop it before starting another |
| Key no longer available | Issue a replacement; do not search for it in chat history |

Logs live under the local runtime directory; review them locally before sharing.
`doctor --online` additionally checks the official client when a runtime key is
already supplied in the environment. The decisive check is a successful tool
call from ChatGPT against the intended document.

## Privacy, distribution and usage

| Shareable software | Keep personal |
| --- | --- |
| Generic v_ase source, wheel and installer | Secret API key |
| These instructions and example inputs | `connection.json`, tunnel settings and local paths |
| A generic Skill without account bindings | A generated bundle containing your registered app ID |

The runtime key authenticates the tunnel. **The launcher does not call a model
API.** ChatGPT still processes prompts, tool results and images as model context;
“uses tokens” does not mean “charges a separate API bill” or automatically mean
“uses the Codex weekly allowance.” Ordinary **Chat** is distinct from **Work**;
OpenAI documents shared usage specifically for Work and Codex. See
[Chat/Work modes](https://learn.chatgpt.com/docs/use-chatgpt) and
[usage information](https://learn.chatgpt.com/docs/pricing). This guide does not
make a separate tunnel-pricing guarantee where none is established publicly.

The tunnel is outbound-only. Your MCP server remains on loopback, but tool
results, requested coordinates and rendered images can be sent to ChatGPT.
The connection can perform authorized edits and exports, not just read data.

Secure MCP Tunnels support private development connections, not public
plugin-directory distribution. Share the generic installer so each person can
configure their own account; a public plugin needs an appropriate publicly
reachable HTTPS MCP service. [Official tunnel scope](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).

## Upgrading tools

After upgrading v_ase, restart the local GUI/MCP process and refresh the
connection's discovered tools in ChatGPT if new tools are not listed.
Coordination polyhedra require v_ase 0.3.5 or newer; the tunnel ID and key need
not change for an ordinary software update.
