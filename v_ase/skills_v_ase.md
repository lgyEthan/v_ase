# v_ase Agent Skill Compatibility Link

Give an AI the complete canonical skill directory whenever possible:

[visualizing-atomic-structures-with-v-ase/SKILL.md](skills/visualizing-atomic-structures-with-v-ase/SKILL.md)

Start with:

- [agent setup](skills/visualizing-atomic-structures-with-v-ase/references/agent-setup.md)
- [semantic API](skills/visualizing-atomic-structures-with-v-ase/references/semantic-api.md)
- [verified workflows](skills/visualizing-atomic-structures-with-v-ase/references/workflows-and-examples.md)
- [safety and errors](skills/visualizing-atomic-structures-with-v-ase/references/safety-and-errors.md)

Codex and Claude Code can install the directory as a native skill. ChatGPT
desktop agents, Gemini-based agents, agentic IDEs, and other local models can
attach `SKILL.md`, `agent-setup.md`, and the task-specific references, then
control the same vendor-neutral `window.v_aseAI` semantic API.

Launch with:

```bash
v_ase gui STRUCTURE --for-ai
```

Give the AI the first JSON line printed by the command. It identifies the
human GUI, state, schema, skill, and browser API for the same live document.
This compatibility file remains available so existing links do not fail.
