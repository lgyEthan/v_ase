# MCP and native setup

## Contents

- [Current source and connection](#current-source-and-connection)
- [Personal ChatGPT tunnel](#personal-chatgpt-tunnel)
- [Bounded discovery and guides](#bounded-discovery-and-guides)
- [Native function integration](#native-function-integration)
- [Scientific and collaboration guarantees](#scientific-and-collaboration-guarantees)

## Current source and connection

Install `v_ase-gui[mcp]==0.3.7` for the scene transaction and discovery tools.
Restart the GUI and adapter together after upgrading; their contracts must match.
No model or model API key is required by v_ase itself.

A local MCP host runs `v_ase mcp`. All callable tools are registered by default. Add
`--file FILE`, `--connect COMMAND_URL`, `--artifact-dir DIRECTORY` or `--no-browser`
as needed. An owned GUI closes when its MCP process stops; a connected existing
GUI remains owned by the original launcher. `--transport streamable-http` exposes
the local server; remote model services cannot directly reach loopback without
an appropriately configured host/tunnel. Keep stdout for MCP protocol messages.

Use bounded search and exact-schema reads instead of printing the catalog.
`--discovery progressive` is opt-in: the host must rebuild callable bindings
after notifications during an active turn. Codex 0.153.4 did not do this in
the observed code-host path; use the default `all` mode there. Initialization or
a successful search alone does not establish late-tool usability. Schemas and
GUI must share the same contract; restart both after changing source.

## Personal ChatGPT tunnel

The current source includes `v_ase chatgpt configure|start|doctor|plugin` and
`python v_ase/chatgpt_bootstrap.py`. The bootstrap creates an isolated local
Python environment and a foreground launcher; plugin installation alone cannot
provision dependencies or start a process on the person's computer. The helper
is included in v_ase 0.3.4 and newer. A packaged plugin carries a standalone copy.
The local `configure --workspace DIRECTORY` setting determines the root for file
discovery/loading. Restart after changing it. Do not work around a rejected path;
have the person select the intended local structure workspace during setup.

Use OpenAI's official Secure MCP Tunnel with the registered ChatGPT connection.
Do not point a cloud host at its own localhost or substitute a public tunnel.
The person supplies the actual `tunnel_...` ID and associates the intended
ChatGPT workspace. Runtime access requires Tunnels Read/Use. The runtime key is
entered locally through a hidden prompt or `CONTROL_PLANE_API_KEY`; never request
it in chat, tool arguments, files or plugin metadata. No model API key is needed
by the scientific backend.

`start --local-only` verifies local MCP without starting a tunnel. `local_ready`
does not mean connected to OpenAI. `tunnel_ready` requires the official client's
`/readyz` check; only a successful ChatGPT tool call verifies ChatGPT registration.
Startup also checks the actual GUI backend contract. `doctor` reports
`gui_unavailable` when tunnel transport works but the backend does not.
Closing the browser tab preserves a CLI/MCP-owned server; reopen its human URL.
An open browser is still required for renderer-backed scene operations.
Keep the foreground terminal, local GUI and computer awake for the session.
Ctrl-C stops owned processes; a GUI explicitly attached with `--connect` survives.
Inspect local `mcp.log` or `tunnel.log` for the failing stage, without copying keys.

After ChatGPT registration, `plugin --app-id` packages the canonical Skill with
the real technical ID beginning `plugin_asdk_app`. This is not the tunnel ID.
The bundle excludes runtime files, structures and credentials. Secure tunnels
support private development, not public plugin-directory submission. Public
distribution requires its own supported HTTPS service and authentication.
The generated plugin ZIP is personalized: its `.app.json` contains the owner's
registered app ID. Distribute generic v_ase packages and setup instructions;
each account configures its own connection. Never publish a personalized ZIP as
a generic starter or embed a person's key or connection IDs in common software.
For conversational control, the user can use ordinary Chat with the MCP plugin.
Do not conflate ordinary Chat with ChatGPT Work: the documented shared allowance
applies to Work and Codex. Tokens, product limits and API invoices are distinct.
See the [official tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
and [plugin packaging](https://developers.openai.com/plugins/build/plugins).

## Bounded discovery and guides

Scene inspection, search/schema/guide access, rendering, document state and
scientific operations are callable from startup. `vase_search_tools` returns
default 4 matches, maximum 8; the host can defer detailed schema disclosure.
It searches names and individual descriptions, not duplicated namespace boilerplate.
Results are short and do not repeat full schemas. `vase_tool_schema` reads at most
four exact definitions when the host has not already supplied them.

`vase_read_guide` returns a topic or exact heading section with at most 5,000
characters by default. Follow `nextOffset` only if the excerpt is incomplete and
needed. Keep `expected_sha256` when paging. Do not read every guide at startup.
All original structure, insertion, constraints, interface, analysis and export
tools remain available through the same catalog.

## Native function integration

`FunctionTools.initial_definitions()` supplies the small starting catalog.
When a host manages discovery explicitly, install returned `vase_tool_schema`
definitions before the next model call. `deferred_function_tools()` instead
returns the core functions plus feature namespaces of at most eight deferred
functions each. The host must add its `tool_search` capability; namespace
descriptions are short and specific to their feature. `definitions()` and `function_tools()`
remain complete-catalog compatibility methods; pass names to restrict them.

`call(name, arguments)` accepts canonical schemas. `call_function(..., strict=True)`
uses the provider codec: null omits optional fields, dynamic maps become typed
key/value entries, and nullable optional values can use {value:null}. The codec
restores canonical dictionaries and applies their validation. Do not mix strict
encoded arguments with the canonical MCP call.

MCP image inspection returns an image content block. A native-function host must
recognize `delivery="image"`, read the validated artifact bytes and embed image
input using its model API. Never serialize those bytes/Base64 as text. Consume
structuredContent or its text fallback once, not both as duplicate context.

## Scientific and collaboration guarantees

Use exact discovered IDs, document/revision guards and explicit units. Visual
scene transactions do not edit stored scientific arrays. Physical operations
remain dedicated typed tools. Retry receipts are bounded to the live document,
not durable across restarts. Follow the scene and recovery guides for rollback,
readiness and idempotency outcomes. Do not infer tested performance from the
presence of an MCP transport; runtime and scientific regressions are separate.

### Reusing a personal connection

Installing tunnel-client does not create an API key, tunnel or ChatGPT
registration. The same user can configure existing authorized IDs on another
computer after installing its local runtime. Stop the old client before a
single-tunnel handoff. Another account needs its own authorized resources.
Install v_ase 0.3.4 or newer for the complete tunnel lifecycle. Use `--source`
with a matching checkout or wheel only when intentionally overriding PyPI.
Never include personal IDs, keys or actual local directory paths in public
instructions. Ordinary Chat, Work/Codex usage and model API billing are distinct;
the local launcher calls no model API, and no tunnel-pricing guarantee follows.
