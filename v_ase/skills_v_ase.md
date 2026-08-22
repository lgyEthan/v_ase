# v_ase Agent Skill Compatibility Link

Give an AI the complete canonical skill directory whenever possible:

[visualizing-atomic-structures-with-v-ase/SKILL.md](skills/visualizing-atomic-structures-with-v-ase/SKILL.md)

Start with:

- [agent setup](skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md)
- [live collaboration](skills/visualizing-atomic-structures-with-v-ase/references/collaboration.md)
- [semantic API](skills/visualizing-atomic-structures-with-v-ase/references/semantic-api.md)
- [verified workflows](skills/visualizing-atomic-structures-with-v-ase/references/workflows-and-examples.md)
- [safety and errors](skills/visualizing-atomic-structures-with-v-ase/references/safety-and-errors.md)

Codex and Claude Code can install the directory as a native skill. ChatGPT
desktop agents, Gemini-based agents, agentic IDEs, and other local models can
attach `SKILL.md`, `agent-setup.md`, and the task-specific references, then
control the same vendor-neutral HTTP JSON semantic API.

The controlling agent launches:

```bash
v_ase gui STRUCTURE --cli
```

`--cli` is a terminal-oriented API mode, not an embedded LLM. The agent parses
the first JSON line itself; it identifies the human GUI, state, schema, skill,
browser API, and collaboration event stream for the same live document. Later
stdout lines report committed human/agent changes as revisioned NDJSON. v_ase
does not accept natural language or command messages from stdin. A user gives
natural language to the external agent, which translates it into structured
`v_ase api "$COMMAND_URL" ...` calls, listens for human GUI refinements, and
verifies the returned semantic state and rendered output without maintaining
a separate copy. The browser must have `human_url` open, but the agent does not
need page-main-world JavaScript access.
The agent calls `v_ase api "$COMMAND_URL" schema` before a broad workflow to
discover exact operation and export parameters, then uses `capabilities` and
`describe` for the live document and attached calculator state.
It must require exact equality between schema parameter-map keys and the
operation/export names returned by `capabilities`; a mismatch indicates an
out-of-sync installation. External-agent verification uses separate
`v_ase api` processes and confirms each command in the same live GUI, not
only through page-injected JavaScript.
The same semantic contract includes VASP/Cube/XSF volumetric grids, signed
isosurfaces, compatible-grid density differences, total and label-pair RDF,
interactive hkl scalar-field planes, and RDF CSV export. Agents use
`describe().analysis` for dataset and plane IDs,
effective cutoffs, warnings, and curve names instead of reading plots or
surfaces from screenshots.
The canonical skill also documents standalone `html` export in lightweight
view-only and project-embedded modes. Lightweight view-only is the ordinary
export default; the human HTML Project action embeds `.vase` by default.
Embedded HTML can be reopened with `v_ase gui FILE.html`; lightweight HTML
cannot restore editable state. Both begin with the exact Preview Area frame
without application chrome and cross-fade to an adaptive live WebGL canvas
without changing frame bounds. Their optimized static poster is directly
previewable through macOS Finder/Quick Look without installing v_ase; embedded
mode remains a complete recoverable save file. It also documents `%v_ase inline`,
`%v_ase browser`, and `%v_ase auto` for Jupyter Notebook/Lab; `auto` restores
active-kernel detection. Per-call `notebook=` values override that preference.
Agent capability discovery explicitly includes the `expectedRevision`
concurrency guard used to protect newer human GUI edits. This release
documents specific-atom rotation through the human
**Active atom (last selected)** pivot and semantic `pivot: "active"` mode.
Trajectory property coloring and force-vector overlays are frame-aware: an
agent must describe or fetch the active frame after changing frames and must
never treat one frame's stored force buffer as trajectory-wide data. Rigid
translation either accepts any PBC-compatible integer `(h k l)` plane or uses
three Cartesian Angstrom coordinates with independent per-axis bounds. Both
keep the cell and unselected host fixed and move every selected atom by one
shared vector. The sampled plane map is optional; an agent may activate either
mode, inspect its trial timeline, then apply or cancel. Visual
`center-selection-at-origin` separately aligns one atom or a mass-weighted COM
without modifying ASE coordinates.
The compatibility file remains available so existing links do not fail.
