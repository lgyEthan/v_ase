# MCP and native function tools

v_ase 0.3.2 provides typed tools for the shared human GUI. The tools use the
same scientific operations and revision stream as the CLI and JavaScript
interface. v_ase does not run a model or require a model API key.

```{contents} On this page
:local:
:depth: 1
```

## Install and connect an MCP client

Install the optional official MCP SDK adapter in the environment containing
v_ase:

```bash
python -m pip install "v_ase-gui[mcp]==0.3.2"
```

Add this stdio server to your MCP host's configuration. Use the absolute path
to `v_ase` if the host does not inherit your terminal's environment:

```json
{
  "mcpServers": {
    "v_ase": {
      "command": "v_ase",
      "args": ["mcp", "--discovery", "progressive"]
    }
  }
}
```

The MCP process opens an empty editable GUI. Its stderr reports the human URL;
stdout contains only MCP messages. Keep the MCP connection open while using its
GUI. Stopping an owned MCP server stops that GUI process; exported files remain.
Add `--file STRUCTURE` to open a file, and `--interactive` to open it in Edit.
Use `--no-browser` when a browser is opened separately by the agent or user.

An existing GUI can instead be shared with the MCP host:

```bash
v_ase gui STRUCTURE --cli
v_ase mcp --connect COMMAND_URL --discovery progressive
```

Replace `COMMAND_URL` with the first process's JSON handshake value, and open
its `human_url`. The first process stays running. Closing the connected MCP
adapter does not close the existing GUI. Workspace-only actions are advertised
only for workspace connections; a document endpoint controls that document.
The GUI and adapter must have the
same tool contract; a mismatch is rejected before an edit.

## Discover only the tools needed

By default, `v_ase mcp` advertises the complete catalog for hosts that expect
an unchanging tool list. `--discovery progressive` starts with connection,
document, state, event, and search tools. Call `vase_search_tools` with a feature
or exact tool name. Matching tools become available through `tools/list`; the
server sends a list-change notification. A host must support refreshing tools
for this mode. Use the default mode if it does not.

For example, search for `configure_bonds`, read its schema, then call
`vase_configure_bonds` with `index_pairs` or label `pairs`. Neither a shell
command nor an operation-name JSON wrapper is needed. Tool inputs use
`snake_case`; GUI state and the compatibility HTTP/JavaScript API retain their
existing `camelCase` field names. User-defined atom labels and map keys are
preserved exactly.

[Tools by feature](ai-tools-reference.md) maps scientific workflows to the
catalog. A missing tool is not permission to call a hidden browser function.

## Read, edit, verify

Read `vase_describe(profile="summary")` first. The result includes `documentId`
and `collaboration.revision`. Pass these as `expected_document_id` and
`expected_revision` to editing tools. Use `structure`, `appearance`, `bonding`,
`render`, or `analysis` for a focused follow-up. Coordinates and property arrays
are opt-in.

Each edit returns `mutation.changedPaths`, the resulting revision, and a state
fingerprint. GUI edits and agent edits appear in the same document. Consume
`vase_events(after=CURSOR, timeout=0)` between decisions. When the event buffer
reports a gap, read current state instead of replaying guessed edits.

Keep one browser connection per document/workspace. Duplicate windows are
rejected before semantic dispatch so one edit cannot run twice.

A tab switch is rejected even if the new tab happens to have the same revision
number. Concurrent agent edits are serialized in the GUI before revision
validation. After a conflict, describe again, review the human's change, and
re-plan. Never remove a revision guard to force an ordinary edit through.

Stopping playback or optimization is an interruption: these controls require
the document ID but allow the revision to be omitted because the running
process keeps advancing it. Use `vase_pause_playback` before analyzing a movie.
This exception does not allow a stale coordinate or appearance edit.

A timeout reports an unknown outcome. An operation can complete after a client
stops waiting. Inspect the document before retrying an edit.

## Reuse files and visual settings

`vase_files` lists paths relative to the GUI launch directory.
`vase_load_structure` replaces a tab from a structure or project;
`vase_append_structure` adds frames or scalar grids.
`vase_load_settings` restores a saved visual-settings JSON file (up to 64 MiB)
without replacing atomic coordinates. Absolute and escaping paths are rejected.

## Render and export resources

`vase_render(width=1600, height=1250)` and every `vase_export_*` tool save a
unique file under `v_ase-artifacts` by default. Choose an output directory with
`--artifact-dir PATH`. Existing files are never replaced.

The result contains the artifact's URI, absolute path, MIME type, size and
SHA-256 digest. MCP also returns a resource link; read it through the host's
resource interface when needed. Only artifacts produced by this connection
can be read. Binary image bytes are not placed in ordinary tool text.

Inspect a draft image, refine its semantic settings, then check one final
image's dimensions, framing and appearance. A successful HTTP or MCP response
alone does not prove visual quality. Projects, standalone HTML, scientific
CSV, CAD files and trajectory movies need the same content checks as GUI
exports.

## Use local Streamable HTTP

A host that uses HTTP can connect to a separate loopback MCP endpoint:

```bash
v_ase mcp --connect COMMAND_URL --transport streamable-http --port 8766
```

Connect the MCP host to `http://127.0.0.1:8766/mcp`. This server binds to loopback
and uses the SDK's Host/Origin checks. It is a local desktop interface, without
public deployment authentication. A cloud model service cannot reach the
computer's loopback address directly; use a local function runner or an
appropriately authenticated deployment integration. Do not change the GUI's
binding to expose private structures to the internet.

## Use native function calling

The native adapter needs the normal v_ase installation and no MCP or model SDK:

```python
from v_ase.ai_tools import FunctionTools

with FunctionTools(command_url, artifact_dir="figures") as vase:
    # Supply only these definitions to your model's function-calling API.
    tools = vase.function_tools(["vase_describe", "vase_configure_bonds", "vase_render"])

    # A provider returns the tool name and JSON arguments as structured fields.
    result = vase.call_function(tool_call.name, tool_call.arguments)
```

`function_tools()` returns Responses-style function definitions with
`strict=True`. Your application runs the model loop and returns `result` as the
corresponding function output. v_ase never handles the model's credentials.
Other providers can reuse `definitions()` and `call(name, arguments)`.

Strict providers require every declared field. An optional non-null parameter
uses `null` to mean omission. An optional nullable field uses `null` to omit it,
or `{"value": null}` to explicitly clear it. Dynamic label/index maps use
arrays of `{"key": ..., "value": ...}` entries, with unique keys. The dispatcher
restores the canonical dictionary and validates all original conditions before
execution. This preserves the distinction between no change and an explicit
scientific null.

Use `function_tools(strict=False)` with `call_function(..., strict=False)` for
providers that accept the complete JSON Schema directly. Both modes perform
local validation. Unknown fields, wrong vector lengths, non-finite numbers,
missing parameters and invalid cross-field combinations fail before dispatch.

## Scientific interpretation

Typed arguments prevent syntax and type mistakes; they do not establish a
physical model's validity. Check PBC, coordinate basis, units, constraints and
frame identity. Repulsion removes overlaps but does not establish equilibrium.
Commensurate matching is a bounded geometric search; a common cell is not an
energy minimum. RDF normalization and scalar-grid integration retain the
assumptions explained in their feature guides.

`rotate-selection(pivot="com")` and physical scaling now use the mass-weighted
center of mass, including for mixed elements. The existing explicit `origin`,
`cell`, `active`, and Cartesian pivot choices remain available.

## Evidence and limitations

The release checks cover protocol transports, schema coverage, invalid-call
rejection, revision and document conflicts, scientific coordinate results,
resource contents and browser rendering. These tests establish implementation
correctness within the exercised cases. They do not establish superiority over
every agent interface.

A controlled model comparison should hold the structure, task, model, seed or
sampling settings, and success criteria fixed across Skill+CLI, Skill+native
tools, and native tools without Skill. Record provider token counts, invalid
calls, schema reads, latency and semantic/visual success separately. Transport
byte counts and local timings are not model token counts.

### Local transport measurements

A 108-atom Cu document was read 20 times per adapter on macOS arm64 with
Python 3.13.5. The order rotated between adapters and all semantic results
matched. The GUI and persistent connections were already warm.

| Path | Median read latency | Median serialized result size |
| --- | ---: | ---: |
| CLI subprocess | 348.48 ms | 1,003 bytes |
| Native strict function | 2.17 ms | 894 bytes |
| MCP stdio | 2.72 ms | 2,100 bytes |

The CLI row includes starting Python for each call. MCP returns both text and
structured representations, explaining its larger serialized result. The
complete MCP catalog was 157,226 bytes at measurement time; progressive startup
was 2,908 bytes, and one native describe definition was 718 bytes. Catalog sizes
change when features are added. These measurements isolate adapter overhead;
they are not renderer speedups or model token/success measurements.

Reproduce against the checked-out version with:

```bash
python scripts/benchmark_ai_transports.py --iterations 20 --output /tmp/vase-benchmark.json
```

{download}`Recorded samples and scope <benchmark-results/ai-transports-0.3.2.json>`
include the environment and explicit limitations. Use a fixed model study to
assess the three agent conditions described above.

The design follows the official [MCP tool contract](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
[official Python SDK](https://py.sdk.modelcontextprotocol.io/), and
[OpenAI function-calling contract](https://developers.openai.com/api/docs/guides/function-calling).
