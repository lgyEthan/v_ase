# Scene inspection and MCP workflows

The scene interface is included in v_ase 0.3.3. Install `v_ase-gui[mcp]==0.3.3`
and use the same version for the GUI and adapter.

```{contents} On this page
:local:
:depth: 1
```

## Start with the current figure

`vase_scene_snapshot()` returns a compact description of the document being
rendered: document ID and revision, frame, image dimensions, effective camera
source, display mode, bond visibility, selection and rendering readiness. It
does not return coordinates, large pair-policy maps or field arrays by default.

For a small display change, use the initially available `vase_style_scene`:

```json
{
  "expected_document_id": "DOCUMENT_ID_FROM_SNAPSHOT",
  "expected_revision": 12,
  "atom_display_mode": "2d",
  "show_bonds": false
}
```

The revision above is illustrative. Use the value actually inspected.
This changes two settings in one transaction while preserving the camera,
cutoffs, ranges, pair styles and scientific data. Hiding a bond is different
from disabling a bonding policy. Advanced changes use `vase_apply_scene`.

## Identify atoms and connections on screen

Add geometry only when the task needs identities or composition:

```json
{
  "sections": ["atoms", "bonds"],
  "elements": ["Re"],
  "width": 1600,
  "height": 1250,
  "limit": 64
}
```

Rows include base indices, periodic `cellOffset`, world coordinates including
visual translation, output-pixel coordinates and renderer-resolved appearance.
Bond segments resolve the actual global/pair/endpoint style precedence. Periodic
display bridge bonds are identified separately. The fallback style is not
necessarily the style used for a drawn edge.
`render.outputCamera` records the camera projection after physical-scale and
output-aspect adjustments; `render.camera` records the source configuration.

`visible_only` defaults to true and tests enabled geometry against the output
camera frustum. It does not claim that an object is unoccluded or visible through
transparent surfaces. Use `visible_only=false` to inspect configured manual
edges outside the crop. Exact graph requirements and final pixels are separate
checks; identical pixels can hide a different off-crop graph.

Each section returns `total`, `offset`, `limit` and `nextOffset`. Continue with
`atom_offset`, `bond_offset` or `plane_offset`, and carry the original
`sceneFingerprint` as `expected_scene_fingerprint`. If the scene changes,
restart pagination. Geometry scans are limited to 200,000 references; filters
or fewer display repetitions reduce the request. Output pages are at most 256
rows. Frustum intersection remains a conservative geometry test.

## Inspect commensurate previews

`sections=["preview"]` returns bounded host/guest proposal rows and rendered
preview bonds, with `preview_offset` and `preview_bond_offset` for pagination.
Use `components` to restrict host, guest or lattice rows. Preview references
explicitly contain a proposal row and source index; they are not physical base
atom IDs. Proposal cells and a `materialized:false` marker remain explicit.
The normal atom/bond sections reflect whether the base scene is currently hidden.

## Apply a complete visual transaction

Discover `vase_apply_scene` for a coordinated `patch` containing any of:

| Field | Scope |
| --- | --- |
| `display` | Typed appearance, bond, field, vector and display-repetition settings |
| `frame` | A loaded trajectory frame; does not modify source frames |
| `camera`, `render_area` | Camera and framing controls |
| `quality` | Sphere quality and antialiasing |
| `selection` | Base/periodic atom selection |
| `plane_selection` | Plane IDs plus optional atom/gizmo clearing |
| `clear_selections` | Clear all selection types without deleting objects |

Every ordinary mutation requires the inspected document/revision. Inputs use
snake_case; responses and raw CLI/HTTP/JavaScript fields use camelCase. User
labels and dynamic map keys retain their spelling.

Unmentioned fields survive. Override maps merge by default, including fields
within existing pair styles. Arrays are explicit replacements. Set
`map_mode="replace"` to replace only supplied maps, including clearing them with
an empty object. Existing dataset and plane IDs are validated. The transaction
does not accept physical coordinate, species, cell or constraint edits; their
dedicated MCP tools remain available.

The transaction validates before mutation, rechecks the revision after
preparation, holds interactive input during application, waits for rendering
work, and records one undo step. A failed application restores the preceding
visual/frame snapshot. Errors distinguish `rolled_back` from `unknown` when
restoration itself cannot complete. The result returns requested applied values,
changed paths and readiness instead of repeating the complete scene. Oversized
receipt values and change lists are explicitly marked as truncated.

## Readiness instead of blind retries

`vase_scene_readiness` reports pending frame, surface, plane, scalar-color and
vector work, stale rendered data and errors. Set `wait=false` for a progress
snapshot. The default wait is bounded to 15 seconds and can be set up to 30
seconds. It does not start an interatomic calculator.
`nonBlockingWork` reports independent or hidden analysis work; an RDF-panel
failure does not by itself prevent capture of a ready 3D figure.

Pause playback and relaxation before exact figure capture. A render waits for
the mutation queue and tracked work; it reports `scene_not_ready` rather than
quietly capturing stale requested overlays. Inspect the failing task instead
of guessing field IDs or changing unrelated camera settings.

## Selection and publication rendering

Atom selection and plane selection are independent. Use
`vase_select_volumetric_planes(plane_ids=[])` to deselect planes explicitly, or
a scene patch with `clear_selections=true` to clear atoms, replicas, planes,
light handles and render-area selection.
Selecting nonempty plane IDs follows the GUI's exclusive selection rules: it
clears atom selection and the light handle. A patch rejects an atom selection
combined with nonempty plane selection instead of silently discarding one.

Image export defaults to `options.selection_appearance="publication"`. It hides
atom-selection outlines and renders neutral plane borders while preserving live
selection. Scientific constraint markings remain. Set
`selection_appearance="interactive"` for selected appearance, or
`include_plane_borders=false` to omit just plane perimeters. The interactive
choice is a rendered scene, not a screenshot of GUI panels.

The artifact records the actual camera, options and dimensions. Omitted image
dimensions use the current image profile. Stored profile options are respected
before explicit request overrides. `vase_inspect_image(uri=...)` returns an image
content block on MCP; only artifacts produced by the connection can be inspected.
Native function hosts embed validated artifact bytes as image input. Never print
Base64 as text or treat a resource link alone as visual inspection.

## Bounded discovery and scientific guides

All callable tools are registered by default for client compatibility. Search
returns at most eight short matches (four by default), using individual tool
descriptions rather than a repeated namespace prefix. Hosts can defer model-facing
schema disclosure; `vase_tool_schema` reads at most four exact names per request.
Use `--discovery progressive` only after verifying that the host creates new
callable bindings during an active turn, not merely that it receives notifications.

`vase_read_guide` reads one topic or exact Markdown section. Topics separately
cover scene workflow, rendering, structures, trajectories, volumetric data, RDF,
interfaces, insertion, constraints, exports, collaboration, setup and recovery.
Excerpts are 5,000 characters by default and explicitly paginated. The Skill no
longer requires reading a large CLI manual before a simple figure edit.

For native hosts, `initial_definitions()` supplies the small core;
`deferred_function_tools()` supplies core functions and feature namespaces of at
most eight deferred functions each. Such hosts must add the corresponding tool-search
capability and implement its discovery/loading
flow. Existing complete-catalog methods remain available for compatibility.

## Retry receipts and human changes

Ordinary mutations accept an optional `request_id`. An identical retry returns
the saved receipt while it is retained, without applying the mutation again.
Changed arguments or a changed revision require a new ID. Reusing an ID with
different arguments reports `idempotency_conflict`.

Receipts are bounded to this live document: up to 128 entries within 8 MiB.
Reload/restart/eviction ends retention. This is not a durable exactly-once
guarantee. Large responses may be compacted on replay. A receipt's recorded
revision can be older than a new human edit; inspect current state before the
next mutation. Physical operations retain their dedicated scientific semantics
and do not become a general multi-operation physical transaction.

## Implementation and verification

The implementation shares schemas between MCP, native functions and the
CLI/HTTP bridge. Browser scene inspection uses the renderer's projection,
appearance and periodic-image rules. The new short workflow guides replace
mandatory loading of the legacy reference manuals.

Regression cases cover discovery bounds, minimal display changes, map
preservation, rollback, retry conflicts, selected-plane exports and effective
styles. The [release checklist](release_checklist.md) requires the full suite,
live MCP transports, regenerated rendering examples and package verification.
The [material evaluation](agent-material-evaluation.md) reports actual agent
results separately from implementation tests and explains their scope.
