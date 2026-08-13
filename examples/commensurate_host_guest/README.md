# Host/Guest Commensurate Validation

The visual example uses graphene's hexagonal primitive cell and a rectangular
MoS2 conventional cell so the two independent parent lattices are immediately
distinguishable. The smaller graphene/Cu(111) pair remains as a separate
numerical regression in `expected.json`.

1. Start from the repository root:

   ```bash
   v_ase gui examples/commensurate_host_guest/graphene_host.extxyz
   ```

2. Open **Structure > Transform** and enable **Commensurate atoms**. With no
   selected guest layer, only the black host cell and primitive vectors appear.
3. Select **Load or Replace Guest Structure** and open
   `examples/commensurate_host_guest/mos2_guest.extxyz`.
4. Keep **Interlayer gap: 3 Å**, **Apply residual strain to: Guest**,
   **Maximum strain: 2.5%**, and **Maximum area ratio: 16**.

The illustrated bounded match is a rectangular graphene
`(√7 × √21) R±19.11°` area-`14` host cell against four rectangular
MoS2 conventional cells (`2 × 2`) at `|19.10660535|°`. The parent graphene
and MoS2 grids remain fixed in extent and share the same origin while only the
orange guest grid rotates. A teal common-cell guide appears only when the
current angle reaches an accepted match. Atom visibility is an independent
user setting and remains off by default.

For the strict numerical fixture, load `cu111_guest.extxyz` instead and use
1% strain with maximum area ratio 16.

The smallest admissible result is a graphene `√13` host cell matched to a
Cu(111) `√12` guest cell. The symmetry-equivalent rotations are
`±16.10211375°`; the guest maximum principal strain is `0.166582%` and the
paper-style mean absolute strain is `0.111055%`. The materialized common cell
contains 26 graphene atoms and 12 Cu atoms. `expected.json` contains the exact
matrices and regression values.

The default preview shows black host cells, orange guest cells, and the teal
common-cell boundary. **Show preview atoms** adds all enabled bonds and one
primitive-cell halo. The graph provides:

- **Angle × cell size × strain**: angle on the horizontal axis, area-ratio
  layers in depth, and maximum principal strain vertically;
- **Paper strain projection**: mean absolute strain versus the actual number
  of atoms in the common cell.

Both graphs use the same accepted candidate set. The save icon exports that set
and its method citations as CSV. The fixture validates geometry and rendering;
it is not a relaxed interface or an energetic optimum.
