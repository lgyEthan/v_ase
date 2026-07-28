---
name: visualizing-atomic-structures-with-v-ase
description: Controls v_ase to inspect, edit, analyze, style, animate, and export ASE-compatible atomic structures and trajectories through its CLI and semantic browser API. Use when a user needs atomistic visualization, structure measurement, periodic-cell operations, constraints, trajectory movies, publication rendering, scientific or CAD export, or a human-editable GUI, even when v_ase is not explicitly named.
---

# Visualizing Atomic Structures With v_ase

Use semantic structure data and deterministic commands. Do not infer scientific
state from screenshots when `describe()` provides it.

All lengths are Angstrom and all angles are degrees unless stated otherwise.

## Quick Start

Install the tested release:

```bash
python -m pip install "v_ase-gui==0.0.104"
```

Start an agent-ready live session:

```bash
v_ase gui STRUCTURE --for-ai
```

Read the first stdout line as JSON. Keep the process running. The handshake
contains:

- `human_url`: the regular GUI for browser control or human takeover;
- `state_url`: read-only current semantic state;
- `schema_url`: JSON Schema for `apply()`;
- `skill_url`: this canonical skill;
- `browser_api`: `window.v_aseAI`;
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

## Required Workflow

Use this sequence for every task:

1. **Plan**: inspect `capabilities()` and `describe()`; identify the document,
   frame, atom indices, labels, elements, cell, PBC, constraints, and camera.
2. **Validate**: confirm atom count and topology before reusing indices. Confirm
   Edit mode before physical changes.
3. **Execute**: apply one semantic change at a time.
4. **Verify**: call `describe()` after every structure, trajectory, constraint,
   selection, or camera change.
5. **Render**: call `render()` at the requested dimensions. Inspect the returned
   dimensions, options, byte count, and decoded image.
6. **Export**: call `export()` only after state and camera verification.
7. **Handoff**: provide `human_url` when the user wants manual refinement.

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

## Minimal End-To-End Example

This example reads state, creates a deterministic orthographic view, measures
two atoms, renders the exact export frame, and exports it without a screenshot
crop:

```javascript
await ai.ready();
const state = await ai.describe({includePositions: true});
if (state.atomCount < 2) throw new Error("At least two atoms are required.");

await ai.apply({
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

For physical editing, trajectory analysis, video, CAD export, and failure
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

## Validation Before Completion

For any nontrivial task, verify all applicable items:

- structure: count, labels, elements, positions, cell, PBC, constraints;
- trajectory: frame count, active frame, stable selection, analysis reference;
- appearance: visibility, radii, colors, materials, bonds, cell, background;
- camera: projection, position, target, up vector, framing, expected direction;
- manipulation overlays: rotation axis, fixed start reference, moving current
  reference, and separate commensurate candidates when a human is editing;
- constraints: persistent per-atom FixedLine/FixedPlane markers and one
  original-position FixedPlane motion guide per selected atom during `G`;
- render: exact dimensions, format, options, nonblank decoded pixels;
- export: MIME type, filename, byte count, and reopenability where supported;
- video: exact decoded frame count and `frames / FPS` duration, with visible
  displacement vectors present in the captured frames when enabled.

If an instruction in this skill prevents a correct result, inspect the live
schema and implementation, correct the skill and add a regression test. Do not
work around a stale skill silently.

## References

Read only the references needed for the current task:

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
