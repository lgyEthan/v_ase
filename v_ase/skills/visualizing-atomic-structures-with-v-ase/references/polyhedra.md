# Coordination polyhedra

Use `configure-polyhedra` / `vase_configure_polyhedra` in View or Edit. This is
presentation and geometric analysis: do not enable a calculator or edit atoms.
Supply center and ligand selectors by elements, visual labels or known atom
indices. Fields within a selector intersect; values in one list are alternatives.
An empty selector object means all atoms; an empty values list selects none.
Do not infer a step, oxidation state, coordination shell or active site for the
user. Ask for or use supplied labels/indices and a scientifically intended cutoff.

`rules` replaces the full rule list. Omit it when only toggling the feature.
Each rule has a unique `id`, `centers` and `max_distance` in Å. Optional ligands,
minimum distance, periodicity and minimum/maximum coordination select its sites.
The hull uses all qualifying images, including several images of one basis atom;
never reduce the vertices to unique base atom indices. `explicit` groups instead
specify a center and exact vertex index/cell_offset records; those override the
distance search, but must obey the ligand selector and allowed PBC directions.

Example: `centers={"elements":["Ti"]}`, `ligands={"elements":["O"]}`,
`max_distance=2.2` produces TiO6 hulls for the provided cubic SrTiO3 fixture.
This cutoff is an example, not an automatic universal Ti–O bond rule.

For a color-only request, use `style-polyhedra` / `vase_style_polyhedra` with
`rule_ids`, `color` and/or `opacity`. It preserves all selectors and other rules;
do not retrieve and resend the complete rule list. Omitted style fields survive.

Face `color` is a hexadecimal string or null to inherit the resolved center
color. `opacity` is 0–1. `show_faces`, `show_edges`, `edge_color`, `edge_radius`
(Å) are independent. Color/opacity edits preserve scientific geometry and use
cached results. `atom_mode` is `all`, `coordination` (centers + ligands), `centers`, `ligands`,
or `none`. Original atom visibility settings remain stored. Use `coordination`
for a complete octahedron without unrelated atoms. `complete_ligands=true`
(default) adds the required image spheres outside displayed cells; these are
unique base-index/cell-offset sites, not new physical atoms. Keep it enabled for
complete periodic cages. `show_center_bonds=true` adds optional center–ligand
connectors independently of ordinary bonds, using bond color/width styles.
They remain visible with `atom_mode=none` if explicitly enabled. In 2D connectors
are unlit; 3D material settings remain stored. `respect_visibility` follows hidden-center labels/references.

Read `vase_scene_snapshot(sections=["polyhedra"], limit=4)` after the update.
It reports resolved appearance, base/image identities, world and screen positions,
faces, true edges, areas and volumes. Page using `polyhedron_offset` and the same
scene fingerprint. Each page returns at most 512 vertices, keeping whole hulls
together; do not request every vertex for a color-only change.
Include `atoms` and `bonds` only when checking displayed sites/connectors. Their
`source` values `polyhedra-ligand-image` and `polyhedra-coordination-connector`
distinguish them from regular displayed atoms/bonds. Summary includes supplemental
site/connector counts, readiness and transparency ordering. Physical atom count
never includes the supplemental images. Click, rectangle and native selection retain image offsets in View mode;
Edit maps image selections to editable base atoms. Native `vase_set_selection`
accepts the returned `index` and `cell_offset` directly; no internal `kind` is
required. A zero offset selects the base atom.

Verify a complete cage's ligand count and styles semantically, then inspect the
final image in the requested 2D/3D style. Flat 2D is a shading style, not a planar
hull or a request to modify coordinates. Transparent polyhedron faces are split
and depth ordered across rules for the active projection/camera. Independent
translucent objects such as an annotation plane intersecting these faces still
use object ordering; do not promise universal order-independent transparency.
For exact face/atom depth, keep atom and connector opacity at 1. Render only after pending geometry
settles; image/video capture waits for each source or interpolated frame's hulls.
For a movie, inspect decoded source and midpoint frames, not only export success.

Planar neighbors may form a polygon with zero volume. Collinear/degenerate
neighborhoods and coordination filters are reported, not turned into artificial
solids. Coplanar triangulation diagonals are not visible edges. Duplicate vertex
positions are collapsed for geometry and reported; this is not an occupancy model.
Inspect both neighbor count and hull vertex count when inner sites are present.
The center need not lie inside a hull; read `center_inside`/`centerInside`.

No atom or cell is changed, and no energy/bond inference follows from the hull.
A convex hull cannot represent a concave cavity. The numeric rank tolerance and
bounded resource limits are part of the response/error contract. Reduce centers,
cutoff or display repetitions after a resource error; never silently omit sites.
