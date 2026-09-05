# AI-agent integration

v_ase 0.3.2 gives an external AI agent typed access to the same document that a
researcher sees and edits. MCP is the primary integration for tool-capable
hosts. Native function tools serve application developers. The CLI, HTTP JSON
bridge and JavaScript interface remain supported adapters.

```{contents} On this page
:local:
:depth: 1
```

## Choose a connection

| Agent environment | Interface | Start here |
| --- | --- | --- |
| An MCP desktop or coding host | stdio MCP, optionally progressive discovery | [MCP setup](ai-tools.md#install-and-connect-an-mcp-client) |
| A local model application | strict native function schemas and dispatcher | [Native functions](ai-tools.md#use-native-function-calling) |
| An HTTP MCP host on the same machine | loopback Streamable HTTP | [HTTP transport](ai-tools.md#use-local-streamable-http) |
| Shell automation, HPC, or a host without MCP | Skill + CLI/HTTP | [CLI collaboration](ai-cli.md) |

v_ase runs no LLM and requires no model API key. Natural language belongs
between the human and the external agent; v_ase executes structured requests.

## Share one document

```text
Human <-------------- natural language -------------> AI agent
  |                                                       |
  | live GUI                                      typed tools
  |                                                       |
  +---------------- v_ase live document <------------------+
                            |
                 CLI / HTTP / JavaScript adapters
```

The human and AI work in the **same live GUI**. The raw API uses
`expectedRevision` and `expectedDocumentId` for guarded edits.

State profiles expose only the structure, appearance, bonds, camera or analysis
needed for the next decision. Editing tools require the inspected document ID
and revision. They return exact changed paths; a later human edit becomes a
new revision that the agent must review. Rendering is for final visual checks,
while scientific state is read semantically.

The [bundled workflow Skill](https://github.com/lgyEthan/v_ase/tree/main/v_ase/skills/visualizing-atomic-structures-with-v-ase)
explains scientific interpretation, validation and recovery. Tool schemas
supply the actual parameters. This separates scientific workflow knowledge
from transport syntax.

## Find a scientific workflow

Use [tools by feature](ai-tools-reference.md) to find the relevant operation.
For interpretation, follow the dedicated [distribution](atomic-distributions.md),
[constraint](constraints-relaxation.md), [trajectory](trajectories-analysis.md),
[RDF](rdf.md), [volumetric](volumetric-guide.md),
[interface matching](periodic-interfaces.md), or
[render/export](projects-export.md) guide.

## Verify the result

Read the relevant state after each edit. Confirm unchanged structure for
visualization-only work, and check ASE positions and constraints after a
physical edit. Pause a running movie before a frame-dependent read. Inspect a
saved image and reopen exported projects or standalone HTML when applicable.

MCP removes shell quoting from agent calls; it does not prove that an agent's
scientific choices are correct or establish a universal SOTA ranking. The
[implementation and evaluation notes](ai-tools.md#evidence-and-limitations)
state the scope of the evidence.

```{toctree}
:maxdepth: 1

ai-tools
ai-tools-reference
ai-cli
```
