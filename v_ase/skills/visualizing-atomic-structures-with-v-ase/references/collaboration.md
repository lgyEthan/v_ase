# Live Human-Agent Collaboration

## Contents

1. Shared-Document Model
2. CLI Stream Contract
3. Event Fields
4. Required Agent Loop
5. Revision Safety
6. Multiple Documents
7. Worked Example
8. Failure And Recovery

## Shared-Document Model

The external agent and researcher operate the same live document in a cycle
centered on v_ase:

```text
researcher --natural language--> external agent
external agent --structured command--> v_ase
v_ase --live 3D document--> researcher GUI
researcher GUI --committed edit--> same v_ase document
v_ase --exact state + revision--> external agent
```

This is a visible feedback cycle: the researcher watches Agent operations in
the live GUI, can refine the same document directly, and the Agent receives
that committed GUI edit as a new revision before continuing. A one-way
request-to-render pipeline does not satisfy this collaboration contract.

v_ase is the scientific application in this cycle, not the AI. It owns and
validates the atomistic document, applies structured Agent commands and human
GUI edits, renders the GUI, and emits machine-readable state and revisions.
`human_url` is not a rendered copy or separate editor. It opens the same
workspace controlled through the handshake's `command_url`. Human GUI edits
are authoritative and must be reviewed before the agent continues.

Do not validate this contract with page-only JavaScript. Send at least one
selection plus physical or visual change from a separate `v_ase api` process,
confirm the corresponding controls/readouts change in the normal GUI, make at
least two separate GUI-originated edits, and then confirm both human events,
`describe().collaboration.revision`, and semantic state agree.

When live human collaboration is requested, automate the visible `human_url`
page itself so the researcher observes and edits that browser view between
agent commands. Do not create an unnecessary hidden rendering copy.

The event stream reports committed state changes, not raw pointer motion.
Camera drags, sliders, selection changes, and related rapid input are coalesced
into compact events so the agent is not flooded.

## CLI Stream Contract

Start:

```bash
v_ase gui STRUCTURE --cli
```

Stdout is line-delimited JSON:

1. the first line is the `v_ase.ai.v1` startup handshake;
2. each later line is one `v_ase.collaboration.v1` event.

Stderr contains human-readable lifecycle and reconnect status. Do not combine
stderr with the JSON parser.

Relevant handshake fields:

```json
{
  "human_url": "http://127.0.0.1:50000/workspace?...",
  "command_url": "http://127.0.0.1:50000/api/ai/command/workspace/...",
  "state_url": "http://127.0.0.1:50000/api/ai/state/...",
  "events_url": "http://127.0.0.1:50000/api/ai/workspace-events/...",
  "event_protocol": "v_ase.collaboration.v1",
  "event_delivery": "ndjson-after-handshake",
  "event_scope": "workspace",
  "command_transport": "http-json-bridge"
}
```

The CLI performs long polling and reconnects automatically. It accepts no
commands on stdin. Send structured commands with
`v_ase api "$COMMAND_URL" METHOD`.

## Event Fields

A typical workspace event is:

```json
{
  "protocol": "v_ase.collaboration.v1",
  "type": "state.changed",
  "revision": 9,
  "document_revision": 4,
  "timestamp": "2026-07-30T12:00:00+00:00",
  "source": "human",
  "categories": ["display"],
  "changed_paths": ["display.atomRadiusScale"],
  "summary": "Human changed atom radius.",
  "workspace_id": "...",
  "session_id": "...",
  "document": "graphene.cif",
  "frame": 0,
  "atom_count": 72,
  "selection_count": 0,
  "state_url": "http://127.0.0.1:50000/api/ai/state/..."
}
```

- `revision` is the monotonically increasing event-stream revision. In a
  workspace stream it spans all tabs.
- `document_revision` is the affected document's optimistic-concurrency
  revision. A document-only stream uses `revision` for that value.
- `source` is `human`, `agent`, or `system`.
- `categories` may include `analysis`, `camera`, `constraints`, `display`,
  `document`, `export`, `frame`, `mode`, `selection`, `state`, `structure`, or
  `trajectory`.
- `changed_paths` identifies likely semantic fields but is not a state patch.
- `state_url` points to current backend state for the affected document.

Events deliberately omit positions and other large arrays. Use the `describe`
method as the authoritative live state after receiving an event.

## Required Agent Loop

1. Parse the first stdout line and open `human_url`.
2. Call `ready`, `capabilities`, and `describe` through `v_ase api`.
3. Record `state.collaboration.revision`.
4. Send that value as `expectedRevision` with every `apply` call.
5. Keep reading later stdout lines while working.
6. On a human event, stop issuing mutations.
7. If its `session_id` is not active, call `documents` and `activate`.
8. Call `describe` and inspect the changed semantic fields.
9. Update the plan, use the new document revision, and continue only if the
   user's request still applies.
10. Verify final semantic state and rendered pixels before completion.

Do not acknowledge an event by guessing from `summary`. The summary is for
orientation; `describe` is authoritative.

## Revision Safety

Use optimistic concurrency and treat stale-revision rejection as a required
safety boundary:

```bash
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'
v_ase api "$COMMAND_URL" apply --params \
  '{"expectedRevision":CURRENT_REVISION,"display":{"atomRadiusScale":0.72}}'
```

If the human changes the GUI between `describe()` and `apply()`, v_ase rejects
the command:

```text
Collaboration revision conflict: expected 6, current 7.
Call describe() and review the human change before retrying.
```

Never remove `expectedRevision` merely to bypass a conflict. Re-read state,
review the human change, then construct a new command from the new revision.

## Multiple Documents

A workspace-scoped stream reports changes from every v_ase tab. Use the event's
`session_id` and `document_revision`, not only the active tab:

```bash
v_ase api "$COMMAND_URL" documents
v_ase api "$COMMAND_URL" activate \
  --params '{"sessionId":"EVENT_SESSION_ID"}'
v_ase api "$COMMAND_URL" describe \
  --params '{"includePositions":true}'
```

Each tab keeps independent structure, trajectory, camera, selection, history,
settings, calculator, and `.vase` output. A workspace `revision` orders events
across tabs; each tab's `collaboration.revision` guards its own mutations.

## Worked Example

Researcher request:

```text
Starting from a pristine 6 x 6 graphene sheet, create a pyridinic N3
vacancy, place Li 2.15 A above it, and prepare a clear rendered view.
```

Agent sequence:

1. inspect the graphene cell and identify the central carbon;
2. delete it and re-read indices;
3. change the three nearest neighbors to element N with label
   `N_pyridinic`;
4. add element Li with label `Li_site`;
5. set bonds, camera, lighting, and output framing;
6. verify atom count, labels, elements, coordinates, cell, and render.

While the agent is working, the researcher may orbit the camera or adjust atom
radius in `human_url`. The CLI emits `camera` or `display` events. The agent
then re-describes the same document and preserves those refinements in later
commands and exports.

## Failure And Recovery

- `state.resync-required`: buffered older events expired. Ignore cached
  revisions. For a workspace stream, call `documents()` and inspect every
  relevant tab; for a document stream, activate that session and call
  `describe()`.
- event HTTP reconnect message on stderr: keep the process alive; the CLI
  retries automatically.
- revision conflict: re-describe and review; do not force the stale command.
- unknown `session_id`: call `documents()`. If absent, the tab was closed; do
  not recreate it without user intent.
- event summary and semantic state disagree: trust semantic state and report
  the discrepancy.
- HTTP 409 or browser disconnected: keep the CLI alive, open or reconnect
  `human_url`, wait for the viewport, then retry. Do not substitute
  screenshot-derived coordinates.
