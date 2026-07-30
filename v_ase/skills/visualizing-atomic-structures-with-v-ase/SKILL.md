---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible atomic structures and trajectories through its CLI and semantic browser API. Use when a user needs atomistic visualization, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, reusable 3D export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic commands. Do not infer scientific
state from screenshots when `describe()` provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install the tested release:

```bash
python -m pip install "v_ase-gui==0.0.118"
```

Start the terminal-oriented API session yourself:

```bash
v_ase gui STRUCTURE --cli
```

The user gives natural-language instructions to the external agent, not to
v_ase. `--cli` does not contain an LLM, parse natural language, or accept
commands from stdin. It launches the normal local v_ase application without
opening a browser and exposes a structured browser API.

Read the first stdout line as JSON. Keep the process running and continue
reading stdout as NDJSON. The handshake contains:

- `human_url`: the same regular GUI for human watching and refinement;
- `state_url`: read-only current semantic state;
- `events_url`: long-polled human/agent change stream;
- `event_protocol`: `v_ase.collaboration.v1`;
- `event_delivery`: `ndjson-after-handshake`;
- `event_scope`: `workspace` or `document`;
- `schema_url`: JSON Schema for `apply()`;
- `skill_url`: this canonical skill;
- `browser_api`: `window.v_aseAI`;
- `command_transport`: `browser-javascript`;
- `accepts_natural_language`: `false`;
- `stdin_commands`: `false`;
- `skill_path`: the installed canonical `SKILL.md`.

Open `human_url`, then connect:

```javascript
const ai = window.v_aseAI;
await ai.ready();
const capabilities = await ai.capabilities();
const before = await ai.describe({includePositions: true});
```

No API key or external service is required. The loopback URL contains a session
identifier; do not publish it while a private structure is open.

The control path is:

```text
user request -> external agent + this Skill -> CLI handshake/event stream
-> window.v_aseAI structured commands -> same live human GUI
-> human GUI edit -> NDJSON event -> agent re-describes and continues
```

Use `describe({includePositions: false})` for compact metadata inspection and
request full positions only when coordinate-dependent work requires them.
This avoids repeated screenshot interpretation and can reduce context/token
use. Rendered pixels remain the final authority for visual-quality checks.

## Required Workflow

Use this sequence for every task:

1. **Connect**: parse the handshake, keep consuming later NDJSON events, and
   open `human_url` so the human and agent share one live document.
2. **Plan**: inspect `capabilities()` and `describe()`; identify the document,
   frame, atom indices, labels, elements, cell, PBC, constraints, and camera.
3. **Validate**: confirm atom count and topology before reusing indices. Confirm
   Edit mode before physical changes.
4. **Execute**: apply one semantic change at a time with the latest
   `collaboration.revision` as `expectedRevision`.
5. **Synchronize**: on a human event, pause mutations, activate its document,
   call `describe()`, and preserve the newer human change.
6. **Verify**: call `describe()` after every structure, trajectory, constraint,
   selection, or camera change.
7. **Render**: call `render()` at the requested dimensions. Inspect the returned
   dimensions, options, byte count, and decoded image.
8. **Export**: call `export()` only after state and camera verification.
9. **Collaborate**: keep `human_url` and the event stream active while the user
   wants to watch or refine the result.

Do not report completion when only an HTTP response succeeded. Verify the
resulting semantic state and rendered output.

## Degrees Of Freedom

- **Low freedom**: deletion, identity/element changes, constraint edits,
  materialized supercells, relaxation, overwrite-prone exports, and release
  publishing. Use exact documented commands and verify afterward.
- **Medium freedom**: camera placement, bond cutoffs, materials, lighting,
  displacement analysis, interpolation, and rendering quality. Start with the
  documented templates, then tune against the requested result.
- **High freedom**: choosing a visually clear viewpoint, palette, or
  composition when the user has not specified one. Preserve scientific
  identity and disclose aesthetic choices.

## Core Semantic Commands

The browser API has six methods:

```javascript
await ai.ready();
await ai.capabilities();
await ai.describe({includePositions: true});
await ai.apply(command);
await ai.render(renderRequest);
await ai.export(exportRequest);
```

Workspace pages additionally support:

```javascript
await ai.documents();
await ai.activate(sessionId);
await ai.newDocument();
```

`apply()` accepts `frame`, `mode`, `display`, `quality`, `applyConstraints`,
`camera`, `selection`, and `operation`. Query `capabilities()` instead of
assuming that a command exists.
For a rotation around one atom, pass that atom last in the explicit `indices`
array and set `pivot: "active"`; verify that its coordinate is unchanged.

## Minimal End-To-End Example

This example reads state, creates a deterministic orthographic view, measures
two atoms, renders the exact export frame, and exports it without a screenshot
crop:

```javascript
await ai.ready();
const state = await ai.describe({includePositions: true});
if (state.atomCount < 2) throw new Error("At least two atoms are required.");

await ai.apply({
  expectedRevision: state.collaboration.revision,
  display: {
    viewportBackground: "white",
    showBonds: true,
    showGrid: false,
    showAxes: false,
    showCell: true,
    lightingMode: "studio-shadow"
  },
  quality: {antiAliasing: true, sphereQuality: "ultra"},
  camera: {axis: "+Z", fit: "structure"},
  selection: {clear: true, indices: [0, 1]}
});

const verified = await ai.describe({includePositions: true});
if (verified.selection.length !== 2 || !verified.measurement) {
  throw new Error("Selection or measurement verification failed.");
}

const preview = await ai.render({
  format: "webp",
  width: 3840,
  height: 2160,
  options: {
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    transparentBackground: false,
    backgroundColor: "#ffffff",
    scaleMode: "viewport",
    sphereQuality: "ultra",
    renderMode: "studio-shadow"
  }
});

if (preview.width !== 3840 || preview.height !== 2160 || preview.bytes <= 0) {
  throw new Error("Render verification failed.");
}
```

For physical editing, trajectory analysis, video, 3D scene export, and failure
handling, use the references below rather than improvising field names.

## Safety Boundaries

- Never delete atoms, overwrite a project, materialize a supercell, change
  chemical elements, start relaxation, or publish files without explicit user
  intent.
- Never treat a visual label as an ASE element. Verify `chemicalSymbols`.
- Never infer a periodic replica from screen position. Use `cellOffset`.
- Never reuse indices after topology or frame changes without `describe()`.
- Keep `applyConstraints: true` unless the user explicitly requests free
  editing.
- Treat ASE backend positions returned after an edit as authoritative.
- Prefer a new output filename. Browser save pickers and human approval are
  required when an existing path may be replaced.
- Do not expose local paths, session URLs, tokens, or private structure data in
  public output.
- Treat a newer human collaboration revision as authoritative. Never remove
  `expectedRevision` merely to force a stale command through.

## Validation Before Completion

For any nontrivial task, verify all applicable items:

- structure: count, labels, elements, positions, cell, PBC, constraints;
- trajectory: frame count, active frame, stable selection, analysis reference;
- appearance: visibility, radii, colors, materials, bonds, cell, background;
- camera: projection, position, target, up vector, framing, expected direction;
- manipulation overlays: rotation axis, fixed start reference, moving current
  reference, and separate commensurate candidates when a human is editing;
- constraints: persistent per-atom FixedLine/FixedPlane markers, one long
  original-position FixedLine direction guide during `G`, and one
  original-position FixedPlane motion guide per selected atom during `G`;
  FixedLine uses one center axis, while rings and discs are plane-only;
- render: exact dimensions, format, options, nonblank decoded pixels;
- export: MIME type, filename, byte count, and reopenability where supported;
- standalone HTML: both lightweight and project-embedded modes load from
  `file://` with saved camera/trajectory, view-only controls, and zero network requests;
  embedded mode must also restore through `v_ase gui FILE.html`;
- video: exact decoded frame count and `frames / FPS` duration, with visible
  displacement vectors present in the captured frames when enabled.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.

## References

Read only the references needed for the current task:

- [Agent setup](references/agent-setup.md): exact files to give Codex, Claude
  Code, ChatGPT desktop agents, Gemini-based agents, agentic IDEs, and clients
  without native skill loaders.
- [Live collaboration](references/collaboration.md): same-document human/agent
  workflow, NDJSON events, optimistic revisions, multi-tab routing, and
  recovery.
- [CLI and environments](references/cli-and-environments.md): installation,
  input formats, local/remote/server use, dependencies, and process lifecycle.
- [Semantic API](references/semantic-api.md): complete state, command, display,
  analysis, render, and export fields.
- [Workflows and examples](references/workflows-and-examples.md): tested
  structure editing, trajectory, rendering, and multi-document recipes.
- [Safety and errors](references/safety-and-errors.md): destructive actions,
  common errors, fallbacks, and verification requirements.
- [Evaluation](references/evaluation.md): trigger tests, capability audit, and
  release-time end-to-end scenarios.
