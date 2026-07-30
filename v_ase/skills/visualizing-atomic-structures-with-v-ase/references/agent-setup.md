# Agent Setup

## Contents

1. Required Context
2. Native Skill Loaders
3. Any Other AI Agent
4. Starting A Live Session
5. Browser And HTTP Access
6. Live Human Collaboration
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
- a human watching or modifying the same GUI while the agent works:
  `references/collaboration.md`;
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
2. ensure the agent can run local shell commands and can open a loopback URL;
3. give it the bootstrap instruction below;
4. let the agent start and parse the CLI/API session itself.

Bootstrap instruction:

```text
Read SKILL.md and agent-setup.md first. Load only the reference files needed
for this task, including collaboration.md when the user may refine the GUI.
Start v_ase with --cli. Parse the first JSON line and keep consuming later
NDJSON events. Open human_url and wait for the viewport. Use `v_ase api`
with command_url to call capabilities and describe before editing. Apply
semantic changes one at a time with expectedRevision, re-synchronize after
human events, verify state after every physical change, inspect the decoded
final render, and return human_url. Never infer coordinates from screenshots
when semantic state is available.
```

A hosted model with neither local shell access nor local browser control
cannot operate the session directly. It can still propose a verified command
plan, but a local agent must execute it.

## Starting A Live Session

The user installs v_ase once:

```bash
python -m pip install v_ase-gui
```

The agent then launches the machine-readable session itself:

```bash
v_ase gui STRUCTURE --cli
```

`--cli` is a terminal-oriented API mode. It does not contain an LLM. Read the
first stdout line as JSON; it includes:

- `human_url`: normal interactive GUI;
- `state_url`: read-only semantic state;
- `events_url`: collaboration event stream;
- `event_protocol`: `v_ase.collaboration.v1`;
- `event_delivery`: `ndjson-after-handshake`;
- `event_scope`: workspace or document;
- `schema_url`: current command schema;
- `skill_url`: canonical installed skill;
- `skill_path`: local canonical `SKILL.md`;
- `command_url`: live HTTP JSON command endpoint;
- `command_methods`: supported semantic methods;
- `command_transport`: `http-json-bridge`;
- `browser_api`: optional in-page fallback, `window.v_aseAI`;
- `accepts_natural_language`: `false`;
- `stdin_commands`: `false`.

`v_ase gui ... --cli` is intentionally long-running. Start it through the
agent runtime's persistent-process facility, read its first stdout line as
soon as the runner yields, then issue `v_ase api` calls from separate commands.
Do not wait for the launcher to exit. Keep its process/session handle for
polling later events and stop it only after final verification. Parse the JSON
directly instead of asking the user to copy individual URL fragments by hand.

There is no natural-language endpoint and no command loop on stdin. The user
speaks to the external agent. The Skill tells that agent how to turn the
request into structured semantic commands after it opens `human_url`. v_ase
writes the handshake as the first stdout line, committed workspace changes as
later NDJSON lines, and lifecycle status to stderr.

## Browser And HTTP Access

Open `human_url` first. The visible browser owns the WebGL renderer and executes
commands against the exact document the human sees. The agent itself does not
need page-main-world JavaScript access. Use the separate terminal client:

```bash
v_ase api "$COMMAND_URL" ready
v_ase api "$COMMAND_URL" schema
v_ase api "$COMMAND_URL" capabilities
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'
v_ase api "$COMMAND_URL" apply --params '{
  "expectedRevision":CURRENT_REVISION,
  "camera":{"axis":"+Z","fit":"structure"}
}'
```

`COMMAND_URL` is the literal `command_url` value from the handshake. Quote it.
The command returns one JSON object. Its semantic value is under `result`.
Call `schema` before planning a broad workflow; it exposes exact operation and
export parameter maps as `operation_parameters` and `export_parameters`, even
before a document command is sent to the browser.
For a complex request, write the parameters to a JSON file and use
`--params-file`. For render/export results, use `--save OUTPUT`; this decodes
the returned data URL without printing it. Existing files are protected unless
the agent uses `--force` after explicit approval.

Use `apply`, `render`, and `export` only after reading the semantic API
reference. `state_url` is backend/bootstrap state, not a complete snapshot of
the live camera and visual settings. The `describe` command is authoritative.
Prefer `{"includePositions":false}` for initial metadata inspection of large
structures, then request positions only for coordinate-dependent work.

If no live browser is connected, commands fail with HTTP 409 and tell the
agent to open `human_url`. If the browser controller cannot evaluate
`window.v_aseAI`, do not treat that as a blocker; `v_ase api` is the
vendor-neutral control path.

For a remote server, keep the structure and v_ase process on the server. Use
the automatic SSH tunnel command documented in `cli-and-environments.md`; the
browser receives rendered/session data, not the original structure file.

## Live Human Collaboration

Return `human_url` as soon as the document is ready. The user can watch every
agent operation and edit the same GUI without waiting for a final handoff.

Keep reading stdout after the handshake. Each later line is a compact
`v_ase.collaboration.v1` event. When `source` is `human`:

1. pause new mutations;
2. activate the event's `session_id` when it is in another tab;
3. call `describe()` for authoritative current state;
4. review `categories` and `changed_paths`;
5. continue using the new document `collaboration.revision`.

Always send that revision as `expectedRevision`. A stale command must fail
rather than overwrite a human's newer edit. See `references/collaboration.md`
for event fields, workspace revisions, examples, and recovery.

After semantic and rendered verification, report the final atom count,
labels/elements, cell/PBC, camera, and output. Leave the process running while
the user wants to continue refining the document.

## Privacy And Failure Boundaries

- Treat local paths, session identifiers, and `human_url` as private.
- Do not paste private structures into a hosted model unless the user approves.
- Never claim a successful edit from a screenshot alone.
- Never ignore a human event or bypass an `expectedRevision` conflict.
- Never reuse atom indices after deletion, insertion, frame changes, or
  materialized supercells without calling `describe()` again.
- Do not silently replace unavailable semantic operations with mouse clicks.
- If the live schema and this skill disagree, stop, inspect the implementation,
  update the skill, add a regression test, and only then continue.
