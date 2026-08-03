# Host/Guest Commensurate Validation

This deterministic pair exercises independent host and guest cells rather than
the same-lattice twist shortcut.

1. Start from the repository root:

   ```bash
   v_ase gui examples/commensurate_host_guest/graphene_host.extxyz
   ```

2. Open **Structure > Transform**, enable **Commensurate atoms**, and choose
   **Host / guest interface**.
3. Select **Load Guest Structure** and open
   `examples/commensurate_host_guest/cu111_guest.extxyz`.
4. Keep **Apply residual strain to: Guest**, **Maximum strain: 1.0%**, and
   **Maximum area ratio: 16**.

The smallest admissible result is a graphene `sqrt(13)` host cell matched to a
Cu(111) `sqrt(12)` guest cell. The two symmetry-equivalent rotations are
`+/-16.10211375 deg`; the guest maximum principal strain is `0.166582%` and the
paper-style mean absolute strain is `0.111055%`. The materialized common cell
contains 26 graphene atoms and 12 Cu atoms. `expected.json` contains the
machine-readable matrices and regression values.

The fixture is for validating lattice matching and visualization. It is not a
relaxed interface or a recommended input for an electronic-structure
calculation.

Use the graph selector in the lower analysis drawer to compare:

- **3D overview**: rotation angle, maximum host/guest area ratio, and maximum
  principal strain used by the cutoff;
- **Paper strain projection**: mean absolute strain versus the actual number
  of atoms in the common cell.

The two graph views describe the same candidate set. Changing the graph never
changes the strain cutoff or the proposed common cell.
