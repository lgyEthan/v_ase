# Recovery from typed tool errors

## Before a mutation

`invalid_arguments` rejects the request before dispatch. Use the exact loaded
schema; fix the named field without reloading every tool. `unknown_tool` or a
not-loaded tool needs a bounded search/exact schema request. `guide_error` needs
a valid topic/heading/page, not an arbitrary filesystem path.

`contract_mismatch` means the GUI and adapter are from different source contracts.
Restart them together. `ambiguous_browser` requires selecting one live controlling
browser. `conflict` requires a fresh scene/document revision and review of human
changes. Do not bypass guards. A modified retry payload needs a new request ID.

## Scene application

`scene_not_ready` reports active playback/relaxation, pending rendering or failed
requested overlays. Use `vase_scene_readiness` and resolve that cause. Do not
silently hide a requested field or change the camera to mask a readiness issue.
If an existing failed overlay prevents a transaction from starting, use its
dedicated tool (for example `show-volumetric` with a valid field/isovalue, or
`set-atom-colorscale` with a discovered field) to repair that feature first.
Use `vase_set_display` to hide it only when the user's requested result allows it.
These dedicated recovery edits keep guards but are not scene transactions.
A transaction failure with `outcome="rolled_back"` means prior visual/frame state
was restored. With `rollback_failed` or `outcome="unknown"`, inspect the live
scene before any further edit; do not retry blindly or claim success.

`idempotency_conflict` means a request ID was reused with different arguments.
Only identical uncertain retries may reuse a key. Receipts are scoped to a bounded
live-document cache. A repeated failed key reports its saved failure, not a fresh
attempt. Inspection and a new plan need a new key.

`scene_too_large` concerns bounded geometry inspection. Filter atoms/labels/elements
or reduce display repetitions; use summary state when coordinates are unnecessary.
A stale `expected_scene_fingerprint` requires restarting pagination at zero.
Truncated receipts/guides explicitly say so; read only the missing relevant part.

## Scientific scope and files

Keep physical data, source units, constraints and provenance unless the task
requests their change. A visualization task does not enter Edit, attach a
calculator, start optimization, materialize cells or replace scientific fields.
Never delete atoms without task intent. Existing explicit authorization is
sufficient; do not repeatedly ask for approval of the same authorized action.
Transient selection and publication appearance are separate from scientific data.
Only produced artifact URIs are readable; changed content is rejected. Use a new
export name unless replacement was intended. A local export does not authorize
publishing private data. Existing explicit task authorization remains in force.

After an error, make one evidence-based correction and inspect the affected
result. Repeated identical failures require a different diagnosis, not unbounded
permutations of field IDs, camera angles or hidden state.
Do not suppress an error; do not report completion from transport success alone.
