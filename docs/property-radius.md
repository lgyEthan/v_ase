# Size atoms from a numeric property

Open **Style → Atoms → Property radius mapping**. This controls the
drawn sphere size; it does not change coordinates, chemistry, bonds, or the
cell. It can be used alongside the independent property colorscale.

1. Open the mapping section and choose an available numeric field. The field
   list distinguishes coordinates, stored ASE arrays, and calculator results
   already present in the document. An unavailable field cannot be enabled.
2. Choose **All atoms** or freeze the current selected base-atom indices. A
   frozen scope does not follow later selection changes. Deleting, duplicating
   or materializing an editable supercell remaps that scope by atom provenance.
3. Choose identity or absolute-value transform. **Fit current frame** scans
   the displayed frame; **Fit trajectory** scans the loaded compatible frames
   without requiring a full trajectory cube in browser memory. Missing values
   are reported. Either fit locks its limits until you fit again. Alternatively,
   enter manual limits.
4. Set minimum and maximum multipliers and the exponent, then enable the
   mapping. Invalid or incomplete entries stay as visible drafts without
   changing the last valid rendering.

For a transformed value :math:`x`, limits :math:`x_{\min},x_{\max}`, and exponent :math:`p`, the
normalized fraction is

```{math}
t=\operatorname{clamp}\!\left(\frac{x-x_{\min}}{x_{\max}-x_{\min}},0,1\right),
\qquad
f=f_{\min}+(f_{\max}-f_{\min})t^p.
```

The effective sphere radius is the existing label/per-atom radius times the
global-size multiplier times :math:`f`. Missing or non-finite values and atoms
outside the frozen scope use :math:`f=1`. A zero factor hides the sphere glyph but
does not delete the atom or its bonds. A positive final-radius request for
such an atom is rejected until its mapping is changed or disabled.

The occupancy preset uses a manual :math:`[0,1]` domain. Custom and charge presets
fit the finite values of the selected field and scope, including signed values
when the identity transform is used. Absolute-value fitting applies the
transform to the actual values before finding extrema.

When an optimizer frame is displayed, coordinate fields come from those
displayed positions. A per-atom property not recorded for that optimizer frame
uses neutral factor 1; v_ase does not borrow values from an unrelated loaded
trajectory frame.

The mapping is part of a `.vase` project. Frame-specific mapped sizes are
also used by image/video rendering, offline HTML, and supported geometry
exports. Before publishing a scientific figure, inspect its rendered image or
animation rather than relying on an export-success message alone.

[Atom appearance](appearance.md) · [Scalar colors](scalar-colors.md) ·
[Save projects](save-projects.md) · [Render images](render-images.md)
