# Agent Setup

## Contents

1. Required Context
2. Native Skill Loaders
3. Any Other AI Agent
4. Starting A Live Session
5. Browser And HTTP Access
6. Human Handoff
7. Privacy And Failure Boundaries

## Required Context

Prefer giving the agent the complete
`visualizing-atomic-structures-with-v-ase/` directory. It contains one
canonical `SKILL.md` and one-level references. Do not provide an outdated copy
of the instructions from another project.

If the client accepts only individual files, always provide:

1. `SKILL.md`;
2. `references/agent-setup.md`;
3. the reference files needed for the task.

Choose task references as follows:

- live state, selection, edits, camera, materials, render, or export:
  `references/semantic-api.md`;
- tested multi-step scientific operations:
  `references/workflows-and-examples.md`;
- installation, CLI, WSL, remote servers, or lifecycle:
  `references/cli-and-environments.md`;
- deletion, identity changes, constraints, relaxation, output, or errors:
  `references/safety-and-errors.md`;
- v_ase development, testing, or release work:
  `references/evaluation.md`.

Do not load every reference into context when only one is relevant.

## Native Skill Loaders

For Codex:

```bash
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase \
  "$CODEX_HOME/skills/"
```

For Claude Code in a project:

```bash
mkdir -p .claude/skills
cp -R v_ase/skills/visualizing-atomic-structures-with-v-ase \
  .claude/skills/
```

For another client with a `SKILL.md` loader, copy the complete directory to
that client's documented local skill directory. Do not invent a vendor
directory name when the client does not document one.

## Any Other AI Agent

ChatGPT desktop agents, Gemini-based agents, agentic IDEs, and other local
models can use the same contract without native skill installation:

1. attach or expose `SKILL.md` and the relevant references;
2. ensure the agent can run a local command or control the local browser;
3. give it the bootstrap instruction below;
4. give it the startup JSON from `--for-ai`.

Bootstrap instruction:

```text
Read SKILL.md and agent-setup.md first. Load only the reference files needed
for this task. Start v_ase with --for-ai. Inspect capabilities() and
describe() before editing. Apply semantic changes one at a time, verify state
after every physical change, inspect the decoded final render, and return
human_url for manual takeover. Never infer coordinates from screenshots when
semantic state is available.
```

A hosted model with neither local shell access nor local browser control
cannot operate the session directly. It can still propose a verified command
plan, but a local agent must execute it.

## Starting A Live Session

Install and launch:

```bash
python -m pip install v_ase-gui
v_ase gui STRUCTURE --for-ai
```

Read the first stdout line as JSON. It includes:

- `human_url`: normal interactive GUI;
- `state_url`: read-only semantic state;
- `schema_url`: current command schema;
- `skill_url`: canonical installed skill;
- `skill_path`: local canonical `SKILL.md`;
- `browser_api`: `window.v_aseAI`.

Keep the CLI process running while the agent works. Parse the JSON instead of
copying individual URL fragments by hand.

## Browser And HTTP Access

An agent with browser automation should open `human_url` and use:

```javascript
const ai = window.v_aseAI;
await ai.ready();
await ai.capabilities();
await ai.describe({includePositions: true});
```

Use `apply()`, `render()`, and `export()` only after reading the semantic API
reference. The state and schema URLs are useful for read-only inspection and
capability discovery. Physical edits use the live browser API so that the AI
and human operate the same document.

For a remote server, keep the structure and v_ase process on the server. Use
the automatic SSH tunnel command documented in `cli-and-environments.md`; the
browser receives rendered/session data, not the original structure file.

## Human Handoff

After semantic and rendered verification:

1. report the final atom count, labels/elements, cell/PBC, camera, and output;
2. return `human_url`;
3. leave the process running if the user wants manual refinement;
4. close the session when the user is done.

The user can continue in the same document. Do not create a second copy unless
the requested workflow requires one.

## Privacy And Failure Boundaries

- Treat local paths, session identifiers, and `human_url` as private.
- Do not paste private structures into a hosted model unless the user approves.
- Never claim a successful edit from a screenshot alone.
- Never reuse atom indices after deletion, insertion, frame changes, or
  materialized supercells without calling `describe()` again.
- Do not silently replace unavailable semantic operations with mouse clicks.
- If the live schema and this skill disagree, stop, inspect the implementation,
  update the skill, add a regression test, and only then continue.
