# Human and agent collaboration

## Contents

- [One document and two actors](#one-document-and-two-actors)
- [Events and continuation](#events-and-continuation)
- [Human interface refinement](#human-interface-refinement)
- [Uncertain replies](#uncertain-replies)

## One document and two actors

The shared GUI and semantic tools edit one document. `documentId` is stable
identity, not the displayed title. `vase_documents` and `vase_activate` select
workspace tabs. A document endpoint is scoped to its own tab. Keep one controlling
browser per session/workspace to avoid ambiguous command dispatch.

The ordinary and in-place-adopted notebook workspaces expose the same
`documents`, `activate`, `newDocument`, `describe`, guarded `apply`, `render`
and `export` browser/HTTP operations. Commands target the active document;
after closing the original notebook tab, use the surviving child document ID.
If an active child is still loading, wait for readiness before Save or another
gesture-dependent command rather than assuming the original host is active.
If a controlled browser leaves an agent-created child at `about:blank` and
`newDocument` reports a readiness timeout, preserve the existing documents.
Activate the last ready document, use the visible New (+) control, then call
`ready` and rediscover the active document ID before continuing through the API.
This fallback was required in an extension-controlled Chrome profile; the same
external command passed in a clean Chrome profile and the in-app browser.
Do not change browser security settings or repeatedly create empty tabs.
After a child reload, its `ready()` response waits for the parent to restore
the current visual state and saved baseline; do not mutate it before readiness.
The browser uses Command on macOS and Ctrl on Windows/Linux for document
shortcuts; these are UI conveniences, not semantic-agent API calls. Browser-
reserved keys may require top-level application fullscreen and Keyboard Lock,
and File actions remain the fallback. An embedded notebook editor links to the
same session in a full editor rather than owning Keyboard Lock inside its frame.

Scene snapshots expose `revision`; legacy describe exposes
`collaboration.revision`. Supply the observed revision and document ID to each
ordinary mutation. Review a human event before editing. Do not force stale
arguments by dropping guards. A scene patch checks again after preparation,
briefly holds interactive input while applying, and produces one undo step.
Queries/captures wait for the mutation queue, while readiness can report progress.
Revision snapshots also await collaboration events already being published,
including debounce callbacks, so a completed flush is a publication barrier.

Desktop documents can move into independent windows without changing their
scientific session ID. Workspace membership changes; rediscover it after a human
moves a tab. Help → Copy agent connection URL targets the focused window.
Window transfer waits for pending edits and blocks while transforms, jobs or
saves are active. A native file grant is reissued only to the destination window;
the original format/profile and external-change checks remain in force.

## Events and continuation

Consume `vase_events` with its cursor while sharing work. A gap means events were
lost: read current state rather than guessing a replay. Polling unchanged state
is unnecessary in a short isolated edit. Keep the session alive only while the
user needs collaboration; closing an owned MCP server closes its owned GUI.
Video export temporarily visits source frames and restores the original frame,
selection and measurement intent. Those internal visits do not publish human
frame/selection edits or advance the collaboration revision.

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

## Human interface refinement

The editor, browser/notebook tabs and standalone HTML controls share the same
interface system. `vase_set_interface_theme(theme="system", palette="graphite")`
changes chrome: appearance is System/Light/Dark and the optional palette is
Graphite (default), Slate, Stone or Moss. Parent and editor frames update together.
These preferences never change scientific backgrounds, atomic appearance,
coordinates, lighting, camera or image export. Existing saved scientific
backgrounds remain intact. Offline HTML retains its selected interface palette.
A deliberate task change may briefly animate its controls; frame updates and semantic state synchronization do not replay it.
Reduced-motion preferences disable presentation transitions. Do not wait an
arbitrary animation duration before a semantic command: use readiness and the
committed state as usual.

Humans can resize the inspector, analysis results and bond-label column with
pointer/touch or the keyboard. Arrow keys move the edge; Shift increases the
step, Home/End selects bounds, and double-click restores the default. Keyboard
steps commit immediately. During a pointer/touch drag, Escape, pointer
cancellation and focus loss restore the starting size; only pointer release
persists that drag. After a committed keyboard step, Escape keeps its size and
uses the normal action to close the inspector. These controls do not move
atoms, change camera direction or pixels per Å, or add a coordinate Undo entry.
The canvas occupies the actual visible stage. Orthographic semantic/export zoom
is 1 because `ortho_scale` already contains the effective world height; width-only
resizes keep the vertical frustum and internal zoom exact.

The toolbar selects Style/Build/Analyze/Render. Find tools (Command+F/Ctrl+F)
and the inspector title open one global search across all categories/commands,
including Water, Isosurfaces and project/default settings.
Horizontal document tabs and the v_ase logo sit at the top; hiding the Scene-only
sidebar leaves them available. View only and Edit structure are exclusive access
modes. Camera navigation and Display & guides have separate labels. Native
desktop menus replace the in-app ellipsis menu; browsers retain one opaque,
bounded command surface. The sidebar has actual objects, guides and overlays.
Scene actions target only the active document generation. Child dialogs and blocking
work make parent navigation inert. Busy operations own their progress and
cleanup independently; overlapping work stays isolated until every task finishes.
Deferred progress visibility never defers input isolation. Each tool has its own icon, title and short purpose. Keyboard focus reveals its
tooltip immediately; pointer hover is delayed. Sliders have a 28 px interaction
area. Custom tooltips retain updated titles without a second native bubble.
Sliders keep their original exact numeric companion and step constraints. Dialogs
take keyboard focus immediately, even before their first animation frame, and
trap focus and isolate background controls until closing, then restore focus to
their opener. Compact dropdown values use an ellipsis before a reserved arrow
area; open the native list to read complete option text. Expandable titles wrap
beside their arrow and retain Enter/Space activation. Use native tools for agent operations; the GUI remains available
for human refinement of that same document.

On narrow windows the grouped viewport tools use a horizontal strip below the
structure, with Fit view above. Overflow scrolls from the first control to the
last; touch targets expand to 44 px.
Expanded camera rotation controls stay inside the viewport; closed controls
remain inert. Command search accepts Up/Down from the
query into visible results, Home/End within results, Enter to open and Escape
to close and return focus. Up from the first result returns to the query.
The Add atoms form uses the inspector heading when inactive; an active
insertion session retains its status badge and exit controls.

When a researcher is using the host computer, run UI verification in a fresh
headless browser with browser-scoped input. Do not attach to their browser,
bring native windows forward or consume their keyboard/mouse input. Native
OS-input smoke checks belong on an idle or dedicated test host. Save screenshots
and motion recordings without opening them automatically on the researcher's desktop.

Selection and visibility checkboxes keep keyboard focus in the appearance form,
even when activated programmatically. Delete/Backspace at those controls never
delete scientific atoms. Background appearance refreshes retain an unfinished
label and its text selection only when both its atom binding and stored value
are unchanged. Enter/Tab commit the retained draft normally. A semantic rename,
atom membership change or explicit settings restoration supersedes the old
draft; replacing a row must not commit its discarded input. Agents should read
semantic state to distinguish committed labels from a human's unfinished draft.

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

Atom-label groups retain expansion and unchanged drafts/carets during refresh.
Their summary exposes swatch, label, count, visibility and selection; expand for
element, radius, opacity and material. Image dimensions/framing/background are
directly editable under Render → Image; Advanced render settings holds shared
quality and lighting. Fast operations defer the visible blocker while rejecting
conflicting input immediately. No OS-input automation is needed for verification.

Command/Ctrl+F opens command search across all workspaces. Escape returns to
the actual search opener.
