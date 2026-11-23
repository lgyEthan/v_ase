# Materials-model outputs as editable figures

This self-contained example uses three preserved CrystaLLM AuO2 outputs and
three ALM Edit Li4Fe5CoO12 outputs. These are six samples from two material
systems. They demonstrate v_ase's composition, saved appearance and editable
project workflow. They do not evaluate model success rates or stability, and
are not the exact published figure samples.

The source CIFs, raw CrystaLLM text, generation identifiers, source hashes,
integer lattice-basis transformations and periodic image mappings are supplied
here. The manifest records the previously selected successful examples; no
model inference, reference-coordinate substitution or relaxation is performed.
The example's pinned renderer is v_ase 0.4.13. An intentional version change
requires `--expected-version VERSION` and a fresh validation run.

## Reproduce from a checkout or source distribution

Use a separate environment to keep an older editable installation from
shadowing the intended package. No model weights or GPU workstation are needed
for this rendering example. On macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install 'v_ase-gui==0.4.13'
.venv/bin/python -I examples/model_output_figures/prepare.py \
  --output-dir output/model_output_figures
.venv/bin/python -I -c 'from v_ase.cli import main; main()' gui --cli --no-browser
```

On Windows use `.venv\Scripts\python.exe` for the same Python commands.
Open `human_url` from the launcher's first JSON line and keep it open. Set
`COMMAND_URL` to that line's workspace `command_url`. From the same workspace
directory, in another terminal:

```bash
.venv/bin/python -I examples/model_output_figures/render.py \
  --command-url "$COMMAND_URL" --workspace-root . \
  --output-dir output/model_output_figures
.venv/bin/python -I examples/model_output_figures/render.py \
  --output-dir output/model_output_figures --verify-only
```

Rendering creates its own workspace tab, preserving the person's existing
document. It checks the connected GUI's JavaScript assets against the imported
package and always renders all samples again. It does not trust an old success
manifest as a reason to skip work. The example directory can be copied to a
different location; `--data-dir` selects that copy. Keep the output directory
inside the connected GUI's workspace file root.

## What is verified

- Original source and raw-output hashes, composition, finite coordinates,
  positive cell volume and short-contact screening.
- An integer unimodular basis change that preserves the cell metric and volume.
  Every displayed site is reconstructed from a source index and an integer
  image offset; ALM contains each of the 22 source atoms exactly once.
- Coordinates read back from the saved ASE trajectory, using its full floating
  point precision. Periodic pair distances are checked after the equivalent
  presentation transform. Finite display scenes have PBC off; source CIFs
  retain their scientific periodic boundary conditions.
- The actual structure inside every exported `.vase`, its bond visibility,
  the output dimensions and pixel equality after reopening with no one-off
  render arguments. Same-document style Undo and stale-revision rejection
  are also checked.

Exact pixel comparison concerns the same browser and renderer in that run.
It does not promise identical pixels across different drivers or browsers.
Numerical and image-boundary checks do not replace visual inspection. A report
must disclose its actual runtime, date and inspection status.

## Drawing conventions and sources

AuO2 follows CrystaLLM Figure 3d: 3D atoms and split-color Au-O cylinders with
a 2.5 Å visual cutoff. Its six-atom source cell supplies a finite 49-site
presentation containing nine periodic Au centers and complete O neighbors.
Li4Fe5CoO12 follows ALM Figure 26: the full 22-atom cell, flat atoms and a cell
outline with no bonds or polyhedra. Visual connections do not establish
chemical bonding, and short-contact screening does not establish stability.

- Antunes, Butler and Grau-Crespo, *Crystal structure generation with
  autoregressive large language modeling*, Nature Communications 15, 10570
  (2024), [paper](https://doi.org/10.1038/s41467-024-54639-7).
- Edamadaka et al., *Atomistic Language Models Understand and Generate
  Materials*, arXiv:2606.21395v1 (2026),
  [paper](https://arxiv.org/abs/2606.21395v1).

The ALM thumbnail prints O2, while the released input and generated output
contain O12. The actual released/generated structure is preserved. Original
paper panels are not included in this public example. A separate comparison
report can use locally supplied, attributed references with a suitable rights
basis. The publication figure contains only the new v_ase renderings.
