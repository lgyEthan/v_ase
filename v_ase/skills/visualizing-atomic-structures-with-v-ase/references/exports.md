# Exports

## Image and scene artifacts

`vase_render` and image export return exact camera, options, dimensions and a
connection-owned artifact URI. Omitted dimensions use the stored image profile.
Publication mode neutralizes transient selection appearance while keeping the
live selection; interactive mode preserves selected outlines. Borders can be
omitted explicitly. Check scene readiness first when a prior operation failed.

Use `vase_inspect_image` for actual final image content. A URI or successful call
is not a visual inspection. Native hosts embed `read_artifact(uri)` bytes as image
input; MCP performs that conversion itself. Never dump Base64 into text.

## Editable data and geometry

Use project export for the human-editable scientific document.
`.vase` retains shared or per-frame cell origins in its
manifest because ASE `.traj` alone drops `celldisp`. Use a project when the cell
guide's displacement matters on reopening. Settings store
reusable appearance without atom data. Portable HTML can be a lightweight view
or explicitly embed the project. Geometry exports (Blender, OBJ, 3DM) are scene
representations, not a replacement for complete scientific arrays/constraints.
3DM requires its optional dependency. POSCAR and pickle follow their scientific
format limitations; unsupported constraints must remain explicit errors.

## Movies and tables

Video uses loaded trajectory frames and requested interpolation/FPS; interpolated
frames are not new physical simulation samples. Choose supported even dimensions
and opaque background. RDF, commensurate and registry CSV exports retain scientific
parameters and conventions. Read the focused export schema for exact options.

Produced artifact paths are unique. Only artifacts created by this connection
can be read through it, with content integrity checks. Preserve the user's
original files unless replacement was requested. No publication/upload follows
from an ordinary local export request.

## Coordination polyhedra

Polyhedra rules are retained in projects and presets. Exact image/video output
waits for current hull geometry, including interpolated positions and cells.
Offline HTML embeds per-frame hulls. OBJ and 3DM export real faces and edge
geometry with color/opacity; Blender carries per-frame geometry with a frame
handler. Atom-only formats do not carry coordination display settings.
