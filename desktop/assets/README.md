# Desktop icon source

`icon.png` is the transparent master for the Mac and Windows application icon.
It derives from the maintainer's original `v2.png` atomic-bead castle render.
The built-in image generation editor isolated the full castle on 23 September
2026. The castle is the main subject; Pinocchio remains a small central detail.
The broad flat red foundation board and original background were removed.
This desktop illustration does not replace the canonical `v_ase-logo.png`
used in the editor header and GitHub README.

Final edit prompt:

> Preserve the full red, white and black atomic-bead castle, its towers, roofs,
> entrance and flags. Keep Pinocchio at his original small relative size.
> Remove only the projecting flat red rectangular foundation board and the
> gray background/floor shadows. Use transparent alpha, a tight balanced square
> composition, original bead material and colors. No text, badge, border or
> background tile.

A second editor pass retained the full castle and added transparent breathing
room around every flag and tower so the application icon does not touch its
square boundary.

Re-encode platform sizes after replacing the approved master:

```sh
python desktop/scripts/build_icons.py
```

This encoding step needs Pillow. The ICO contains 16–256 px images; the ICNS
contains the Mac sizes up to 1024 px. Keep the alpha channel.
