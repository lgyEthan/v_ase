# What is new in 0.3.2

Version 0.3.2 adds typed MCP and native function interfaces to the shared
scientific GUI. The existing CLI, HTTP JSON bridge and JavaScript interface
remain available.

## MCP setup and discovery

Install `v_ase-gui[mcp]==0.3.2` and configure a host to run `v_ase mcp`.
The server can open a GUI or connect to one already running. stdio and local
Streamable HTTP are supported. Progressive discovery loads feature tools on
request and supplies change notifications; default discovery advertises all
tools for compatibility. [Connect an MCP host](ai-tools.md).

## Native functions and complete schemas

`FunctionTools` supplies strict function definitions and a local dispatcher
without a model SDK. Arguments never pass through a shell string. The canonical
schemas now include previously missing movement, constraint, RDF and field
parameters, plus the GUI display settings. Dynamic maps and explicit nulls
survive strict-provider conversion. [Read the function guide](ai-tools.md#use-native-function-calling).

## More GUI features available to agents

Tools cover file opening and trajectory appending, exact atom duplication,
repulsion configuration without starting relaxation, movie control, input file
browsing, bulk/molecule catalogs and previews, stored atomic properties,
scalar/force arrays and colormaps. [Browse tools by feature](ai-tools-reference.md).

## Collaboration and scientific correctness

Ordinary edits check both document ID and revision; different tabs cannot be
confused because their revision numbers happen to match. Concurrent agent
commands are serialized. Duplicate GUI connections are rejected before an
operation could be broadcast and executed twice. Stop controls can interrupt a
running movie or optimizer whose revision keeps advancing.

The semantic `com` pivot for rotation and scaling now uses atomic masses,
correcting mixed-element behavior. Other physical models and their interpretation
follow the [scientific validation guide](scientific-validation.md).

## Exact trajectory movies

Video export now sends indexed PNG frames directly to the encoder. This fixes
an observed eight-frame movie that previously contained seven frames and a
320×240 request that became 320×256. Even dimensions are preserved exactly and
both interpolation endpoints are retained. The pipeline holds one raster at a
time, applies encoder backpressure and restores the original GUI frame.

## Artifacts and readable guidance

MCP/native render and export tools write unique files and return resource links
with MIME type, size and SHA-256. The Skill focuses on scientific workflows and
recovery, while tool schemas supply parameters. AI documentation is split into
connection setup, feature sections, and CLI compatibility.

## Upgrade

```bash
python -m pip install --upgrade "v_ase-gui[mcp]==0.3.2"
```

Restart the GUI and adapter together; mismatched tool contracts are rejected.
For core-only use, install `v_ase-gui==0.3.2`. Existing CLI scripts remain valid;
new typed tool arguments use snake_case while raw HTTP/JavaScript retains
camelCase. No model API key is required by v_ase.

The previous scientific audit is preserved in the
[validation record](scientific-validation.md) and [changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md).
