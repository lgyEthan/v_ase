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

The external agent and researcher operate one live v_ase document:

```text
researcher request -> external agent -> semantic v_ase command
                                      -> same live GUI
researcher GUI edit -> CLI NDJSON event -> agent re-reads semantic state
```

`human_url` is not a rendered copy or separate editor. It opens the same
workspace controlled through `window.v_aseAI`. Human GUI edits are
authoritative and must be reviewed before the agent continues.

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
  "state_url": "http://127.0.0.1:50000/api/ai/state/...",
  "events_url": "http://127.0.0.1:50000/api/ai/workspace-events/...",
  "event_protocol": "v_ase.collaboration.v1",
  "event_delivery": "ndjson-after-handshake",
  "event_scope": "workspace",
  "browser_api": "window.v_aseAI"
}
```

The CLI performs long polling and reconnects automatically. It accepts no
commands on stdin. Commands remain structured browser-JavaScript calls.

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

Events deliberately omit positions and other large arrays. Use `describe()` as
the authoritative browser state after receiving an event.

## Required Agent Loop

1. Parse the first stdout line and open `human_url`.
2. Call `ready()`, `capabilities()`, and `describe()`.
3. Record `state.collaboration.revision`.
4. Send that value as `expectedRevision` with every `apply()` call.
5. Keep reading later stdout lines while working.
6. On a human event, stop issuing mutations.
7. If its `session_id` is not active, call `documents()` and
   `activate(session_id)`.
8. Call `describe()` and inspect the changed semantic fields.
9. Update the plan, use the new document revision, and continue only if the
   user's request still applies.
10. Verify final semantic state and rendered pixels before completion.

Do not acknowledge an event by guessing from `summary`. The summary is for
orientation; `describe()` is authoritative.

## Revision Safety

Use optimistic concurrency and treat stale-revision rejection as a required
safety boundary:

```javascript
const before = await ai.describe({includePositions: true});

const after = await ai.apply({
  expectedRevision: before.collaboration.revision,
  display: {atomRadiusScale: 0.72}
});
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

```javascript
const documents = await ai.documents();
if (documents.activeSessionId !== event.session_id) {
  await ai.activate(event.session_id);
}
const current = await ai.describe({includePositions: true});
```

Each tab keeps independent structure, trajectory, camera, selection, history,
settings, calculator, and `.vase` output. A workspace `revision` orders events
across tabs; each tab's `collaboration.revision` guards its own mutations.

## Worked Example

Researcher request:

```text
Create a pyridinic N3 vacancy, place Li 2.15 A above it, preserve PBC,
and prepare a clear rendered view.
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
- browser control is unavailable: keep the CLI alive and reconnect to
  `human_url`; do not substitute screenshot-derived coordinates.
