# Host/Guest Commensurate Validation

This deterministic graphene/Cu(111) pair validates matching two structures
that have different primitive cells.

1. Start from the repository root:

   ```bash
   v_ase gui examples/commensurate_host_guest/graphene_host.extxyz
   ```

2. Open **Structure > Transform** and enable **Commensurate atoms**. With no
   selected guest layer, only the black host cell and primitive vectors appear.
3. Select **Load or Replace Guest Structure** and open
   `examples/commensurate_host_guest/cu111_guest.extxyz`.
4. Keep **Interlayer gap: 3 Å**, **Apply residual strain to: Guest**,
   **Maximum strain: 1.0%**, and **Maximum area ratio: 16**.

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
