# MCP and native setup

## Current source and connection

Install `v_ase-gui[mcp]==0.3.3` for the scene transaction and discovery tools.
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
