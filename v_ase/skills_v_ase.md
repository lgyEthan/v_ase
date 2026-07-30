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
The canonical skill also documents standalone `html` export in lightweight
view-only and project-embedded modes. Lightweight view-only is the ordinary
export default; the human HTML Project action embeds `.vase` by default.
Embedded HTML can be reopened with `v_ase gui FILE.html`; lightweight HTML
cannot restore editable state. Both begin with the exact Preview Area frame
without application chrome and cross-fade to an adaptive live WebGL canvas
without changing frame bounds. It also documents `%v_ase inline`,
`%v_ase browser`, and `%v_ase auto` for Jupyter Notebook/Lab, plus per-call
`notebook=` overrides and ordinary-Python browser behavior. This release
documents specific-atom rotation through the human
**Active atom (last selected)** pivot and semantic `pivot: "active"` mode.
The compatibility file remains available so existing links do not fail.
