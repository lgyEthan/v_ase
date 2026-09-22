# Desktop icon source

`icon.png` is the transparent master for the Mac and Windows application icon.
It derives from the maintainer's original `v2.png` atomic-bead castle render.
The built-in image generation editor isolated and enlarged its central
Pinocchio figure and circular red, black and white turret on 23 September 2026.
This desktop illustration does not replace the canonical `v_ase-logo.png`
used in the editor header and GitHub README.

Final edit prompt:

> Isolate only the brown Pinocchio bead figure together with the short circular
> red/black/white crenellated turret on which he stands. Remove the surrounding
> castle towers, flags, walls and gray background. Enlarge the central group
> on a square transparent canvas, preserving spherical beads and original
> colors. No text, background plate or added elements.

Re-encode platform sizes after replacing the approved master:

```sh
python desktop/scripts/build_icons.py
```

This encoding step needs Pillow. The ICO contains 16–256 px images; the ICNS
contains the Mac sizes up to 1024 px. Keep the alpha channel.
