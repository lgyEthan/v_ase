# Native MCP and function tools

After trajectory scrubbing, verify `analysis.frameSynchronization` before an
export. Frame-specific fields are rebuilt when their previous meshes were
invalidated, including a rapid visit to another frame and return.

## Connection and discovery

Install `v_ase-gui[mcp]==0.3.2` for the optional official MCP SDK. An MCP host
launches `v_ase mcp --discovery progressive`; the server opens a scratch GUI.
Use `--file FILE` and optionally `--interactive` to start with a structure.
`--connect COMMAND_URL` shares an existing GUI. `--transport streamable-http`
serves loopback `http://127.0.0.1:8766/mcp`; the default is stdio.

Default discovery advertises all tools. Progressive discovery starts with
connection/state/event tools and `vase_search_tools`; search enables matching
tools and emits a list-change notification. Hosts that cannot refresh tool
lists should use the default. Prefer feature tools over broad display patches.

v_ase does not call a model. No API key is required by this adapter. Cloud
model services cannot directly reach a local loopback URL; use a local native
function runner or a separately authenticated integration.

## Scientific control

Every existing operation is a named `vase_` tool with hyphens changed to
underscores. Declared input fields use snake_case; returned state retains
camelCase. The catalog also covers each display/control field, all exports,
file discovery, bulk/molecule catalogs and previews, stored properties, scalar
and force arrays, and colormap lookup.

New shared operations are `load-structure`, `append-structure`,
`duplicate-selection`, `configure-calculator`, `set-playback`, and `load-settings`.
`load-settings` restores a saved visual JSON file without replacing coordinates
and accepts files up to 64 MiB.
Use `vase_files` to discover paths relative to the GUI launch directory.
Absolute paths and path escapes are rejected. Replacing a populated tab needs
user intent and `confirm_replace=true`; projects restore their visual settings.
Appending a project contributes frames without its visual settings.
`duplicate-selection` preserves the same data and appearance as GUI copy/paste.
`configure-calculator` changes default repulsion settings without starting it.

`pivot="com"` uses atomic masses for physical rotation and scaling. Explicit
Cartesian, cell, origin and active-atom pivots remain available.

Editing tools require the latest `expected_revision` and
`expected_document_id` from `describe`. The latter is the returned `documentId`,
not the human-readable `document` title. Preserve both guards after a tab switch.
Stop controls require document identity but allow revision omission to interrupt
an evolving trajectory or optimizer. Use `vase_pause_playback` before reads.

## Native functions

`v_ase.ai_tools.FunctionTools(command_url)` exposes `function_tools(names)` and
`call_function(name, arguments)` without an MCP or model SDK. Supply the selected
definitions to a local model runner and pass its structured function arguments
to the dispatcher. `strict=True` is the default. Optional non-null fields use
null for omission; nullable optional fields use null for omission or
`{value:null}` to explicitly clear. Dynamic maps use typed key/value entries.
The dispatcher restores dictionaries and applies the full semantic validation.
`strict=False` preserves the complete original schemas and still validates locally.

## Resources and recovery

Render/export tools save unique artifacts in `v_ase-artifacts` (override with
`--artifact-dir`). Results include URI, path, MIME type, byte size and SHA-256.
MCP returns resource links; only produced artifacts are readable. Inspect one
final image, and reopen scientific/project exports when relevant.

`invalid_arguments` means nothing was dispatched. `conflict` means the revision
or active document no longer matches. `contract_mismatch` means the adapter and
GUI need the same installed version. `transport_error` and other bridge errors
can have unknown outcomes: inspect state before retrying a mutation.

The server owns a GUI it launched; keep it alive for human refinement. A
`--connect` adapter does not own or close its existing GUI. Export files persist.
