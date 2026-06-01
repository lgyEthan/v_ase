v_ase manual showcase checklist
===============================

Launch:
  conda run -n python311 python tests/manual_showcase.py

Scene:
  Structure : 2 x 2 x 1 cubic NaCl solid-state supercell.
  Atom 0    : FixAtoms, should not move when apply_constraint is on.
  Atom 1    : FixedLine([1, 0, 0]), can move only along X when constraints are on.
  Atom 2    : FixedPlane([0, 0, 1]), can move only in XY when constraints are on.
  Atoms 1-2: Hookean(rt=4.80 A, k=5.0).
  Atoms 3-4: Boundary pair across periodic X; auto bond should appear by minimum image.
  Atom 5    : Starts outside the unit cell so Wrap Atoms Into Cell is visibly testable.

Manual checks:
  1. Selection feedback
     - Click atoms. Selected atoms should have clear yellow outlines.
     - Select atom 1: FixedLine guide should appear.
     - Select atom 2: FixedPlane guide should appear.

  2. apply_constraint=True transform behavior
     - Keep apply_constraint checked.
     - Press A, then R, then Z, type 90, press Enter.
     - Atom 0 must stay fixed.
     - Atom 1 should only slide along the FixedLine X direction.
     - Atom 2 should stay in the FixedPlane, so Z must not change.

  3. apply_constraint=False free Blender-like editing
     - Uncheck apply_constraint in the right panel.
     - Press A, then R, then Z, type 90, press Enter.
     - Fixed atom and constrained atoms should now move freely.
     - Re-check apply_constraint for the remaining checks.

  4. Hookean visual state
     - Use trajectory controls at the bottom/right panel.
     - Frame 1: Hookean should be inactive with an open latch and blue slack gap.
     - Frame 2: Hookean should be near threshold.
     - Frame 3: Hookean should be active with a closed green latch and continuous spring.
     - The spring must not visually break when atom 2 is far from atom 1.

  5. PBC bond
     - Ensure Show Bonds is checked and Mode is Auto cutoff.
     - Atoms 3 and 4 sit on opposite sides of the periodic X boundary.
     - They should still be bonded through the periodic boundary.
     - Switch Mode to Element cutoffs.
     - Confirm Na-Na, Na-Cl, and Cl-Cl rcut rows appear and changing Na-Cl updates bonds.

  6. Supercell
     - Set Supercell to 2 x 1 x 1.
     - First it appears as translucent preview atoms plus repeated unit-cell lines.
     - Click Set Supercell as Cell.
     - The scene should become a larger real editable solid-state cell.

  7. Delete and wrap
     - Select any non-critical atom and press Delete or Backspace.
     - The selected atom should disappear and indices/constraints should update.
     - Click Wrap Atoms Into Cell.
     - Atom 5 should be brought back inside the displayed unit cell.

  8. Export
     - Click Export POSCAR.
     - Click Export Pickle.
     - Click Export Blender.
     - Blender export should download v_ase_blender_scene.py.
     - The script should contain Hookean threshold/gap/marker objects.

  9. Camera
     - Middle mouse drag should rotate without polar angle limits.
     - Shift + middle mouse drag should pan.
     - Mouse wheel should zoom.

  10. Visual quality and modal layering
     - Change Atom smoothness from Auto to Ultra.
     - Toggle Anti-aliasing and confirm viewport quality updates without losing selection.
     - Open Export Image and drag inside the modal; atoms behind it should not be selected.
