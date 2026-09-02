# What is new in 0.2.36

Version 0.2.36 makes external AI control more reliable and substantially more
context-efficient without removing the complete compatibility API.

## Progressive CLI discovery

`v_ase api ... schema` now returns a compact operation/export index by default.
An agent can request one exact contract with `--operation-schema`,
`--export-schema`, or `--schema-method`, while `--full-schema` remains available
for integration audits.

Semantic state is divided into `summary`, `structure`, `appearance`, `bonding`,
`render`, `analysis`, and `full` profiles. Positions, complete per-atom arrays,
and per-index visual overrides are opt-in. On the 236-atom ReSe2/graphene
regression scene, summary state serializes to 1,876 bytes versus 58,659 bytes
for full state with positions. Focused state is generated directly rather than
building the complete payload first.

## Verifiable mutations

CLI apply calls return compact summary state by default together with the exact
changed paths, before/current revisions, and state fingerprints. Agents can
request a different focused result with `--response-profile`. Browser callers
without a profile retain the complete response for compatibility.

Exact `configure-bonds.indexPairs` edits now preserve every independent
label-pair cutoff, range, and appearance setting. A label-pair allow-list and
an exact edge list are separate operations, preventing a local highlighted
chain from resetting unrelated display policy.

## Deterministic render authority

The render profile identifies whether output pixels use an explicit request,
the active Render Area, a retained image-export profile, or the working
viewport. Render requests can choose that source explicitly and return the
exact effective camera used.

Visualization-only role labels, atom styling, bond policy, and `compose-view`
can now express centered periodic repetition, motif anchoring,
crystallographic view direction, structural screen-up references, bounded
framing, and flat 2D versus shaded 3D composition without editing ASE
coordinates. Flat atoms use a crisp illustration outline, and displayed-cell
camera fitting includes the complete centered replication window.

The bundled vendor-neutral Skill includes a focused deterministic-rendering
workflow for turning natural-language or reference-figure requirements into
periodic composition, role-based styling, exact bonds, camera orientation,
bounded draft inspection, and final output without repeatedly loading full
state or Base64 pixels into an agent context.

For changes from earlier versions, read the
[complete changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md).
