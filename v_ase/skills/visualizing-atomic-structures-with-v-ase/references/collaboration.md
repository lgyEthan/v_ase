# Human and agent collaboration

## One document and two actors

The shared GUI and semantic tools edit one document. `documentId` is stable
identity, not the displayed title. `vase_documents` and `vase_activate` select
workspace tabs. A document endpoint is scoped to its own tab. Keep one controlling
browser per session/workspace to avoid ambiguous command dispatch.

Scene snapshots expose `revision`; legacy describe exposes
`collaboration.revision`. Supply the observed revision and document ID to each
ordinary mutation. Review a human event before editing. Do not force stale
arguments by dropping guards. A scene patch checks again after preparation,
briefly holds interactive input while applying, and produces one undo step.
Queries/captures wait for the mutation queue, while readiness can report progress.

## Events and continuation

Consume `vase_events` with its cursor while sharing work. A gap means events were
lost: read current state rather than guessing a replay. Polling unchanged state
is unnecessary in a short isolated edit. Keep the session alive only while the
user needs collaboration; closing an owned MCP server closes its owned GUI.
Human changes to data or frame invalidate cached atom references when topology
or identity changes. Read the requested focused state to rebuild that mapping.

Events use `v_ase.collaboration.v1`. The CLI stream is
`ndjson-after-handshake`; MCP's `vase_events` exposes the same records. Read
`source`, `changed_paths` and `document_revision`. A `state.resync-required`
record means the cursor is too old: re-describe the affected document. When a
workspace event concerns another tab, discover/activate its session first. The
raw activation shape is `{"sessionId":"EVENT_SESSION_ID"}`. Return `human_url`
for the researcher to refine the same live document. Raw API guards retain the
name `expectedRevision`; MCP uses `expected_revision` for stale-revision rejection.

## Uncertain replies

An optional `request_id` prevents re-executing an identical keyed mutation while
its receipt remains in this live document. Reuse identical arguments, including
guards. A revised plan gets a new key. The cache retains up to 128 receipts within
8 MiB and is lost on reload/restart; it is not persistent exactly-once delivery.
A large replay can return a compact receipt instead of the original full state.
Its recorded revision can differ from the current human-edited revision.

Read current state before new work after a replay, timeout, conflict or unknown
outcome. Stop controls intentionally allow an omitted advancing revision but
still require identity. All other edits keep guards. Existing user permission
for the task remains valid; do not ask again for an already authorized action.
