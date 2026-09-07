# Material comparison: methods and exact results

[← Visual results](agent-material-evaluation.md)

```{contents} On this page
:local:
:depth: 1
```

## Study setup

| Item | Fixed condition |
| --- | --- |
| Date / source | 8 September 2026; frozen scene-interface source preceding 0.3.3 |
| Participants | 60 independent `gpt-5.6-luna` threads, reasoning `max`; no inherited conversations or model fallback |
| Repetitions | 10 per material/interface cell; 3 materials × 2 interfaces |
| Order | 10 randomized blocks of 6 cells, executed serially |
| Ordering seed | 20260908; **not** a provider sampling seed |
| Horizon | 900 seconds per run |
| Shared inputs | Same prepared project, target images, instructions and preassigned indices within each material |
| GUI editing | Frozen Playwright screenshot/accessibility helper; unique accessible names/roles or screen coordinates |
| GUI exclusions | No semantic API, CLI, raw DOM editing or indexed accessibility-node selector |
| MCP editing | Frozen canonical Skill read before first MCP operation; official SDK stdio transport; all tools registered, bounded host discovery |
| Shared capture | Evaluator image inspection and submission helpers in both arms |

**Interpretation:** the GUI arm tests editing through GUI controls, not complete
navigation of native export dialogs. The MCP arm includes the Skill's guidance.

## Target specifications

The [visual results page](agent-material-evaluation.md#targets-and-token-use)
shows the actual target PNGs, with their original crops and no redrawn atoms.
Their SHA-256 values are in the downloadable aggregate data.

### Cu₅O₄/Cu(111)

| Source | Required change | Preserve | Output |
| --- | --- | --- | --- |
| 41 atoms: 37 Cu + 4 O | Flat 2D; hide bonds | Prepared camera and all other settings | 534 × 417 PNG |

### ReSe₂/graphene

| Source | Required change | Preserve | Output |
| --- | --- | --- | --- |
| 236 atoms: 36 Re + 72 Se + 128 C | Nine exact Re–Re pairs; red `#d7191c`, flat/unlit, thickness 0.12, opacity 1 | Top camera, atom styles and graphene visibility | 1600 × 1250 PNG |

Zero-based index pairs:

```text
[2,20]  [2,29]  [11,20]  [11,29]  [5,11]
[5,23]  [5,32]  [14,23]  [14,32]
```

The task supplied two reference images; acceptance used the main top-view target.

### Pt₃O₄/CeO₂

**55 scientific atoms; 3 × 3 × 1 display repetition.** The supplied top camera
and crop were preserved. Output: 1000 × 1000 PNG, high sphere quality, standard
materials, modeling lighting and white background; no bonds/cell/axes/grid/overlays.

| Supplied visualization group | Atoms | Color | Scale setting |
| --- | ---: | --- | ---: |
| Support Ce | 16 | Beige `#ded6bc` | 1.70 |
| Support O | 32 | Dark red `#4a1410` | 2.45 |
| Cluster Pt | 3 | Gray `#96969d` | 1.85 |
| Cluster O | 4 | Red `#d4372d` | 2.50 |

These are display labels, not changed chemical species. The original structure
has **no fixed-layer constraints**; repetition changes the view, not source atoms.

**Source:** frame 0 of `pt3o4_DFT_10_most_stable.extxyz` in
[Zenodo 16809151](https://zenodo.org/records/16809151), accompanying
[Dominguez et al., J. Chem. Phys. 165, 034115 (2026)](https://doi.org/10.1063/5.0302876).
The composition appears in Fig. 5(c), middle column, lower top view. Our target
is a v_ase rendering of that structure, not the paper's original renderer.

## Success and accounting

| Quantity | Definition | Do not interpret it as |
| --- | --- | --- |
| **Strict success** | Accepted within 900 s; required style, camera, dimensions, visual inspection, scientific arrays and declared state preserved—including `v_ase_atom_type`, document mode and unrequested settings | A picture-only score |
| **Matching picture** | Post hoc: render/style/camera/dimensions/inspection pass within 900 s; scientific record preserved except internal `v_ase_atom_type` representation | A replacement for strict success or proof of full GUI-state preservation |
| **Total tokens** | Provider input + output, reconciled against cumulative accounting; all 54 strict successes have complete usage | Unique words, price, or isolated MCP transport cost |
| **Cached / reasoning tokens** | Cached input is already inside input; reasoning is already inside output | Extra terms to add again |
| **Timeout usage** | Incomplete observed lower bound for six GUI runs | Tokens required to produce a matching picture |
| **Task time** | First accepted submission; final reply/accounting grace and timeout drain excluded | Final assistant message time |
| **First picture-match timing** | Reconstructed from tool-event timestamps + callback duration | The primary monotonic timing endpoint |

The experiment continued after a picture-only match if strict checks still
failed. Terminal retry costs therefore cannot be called the necessary cost of
the first matching image. Token snapshots at submission dispatch are lower bounds.

## Exact token results

**Population: strict successes with complete usage.** Q1–Q3 is the interquartile
range, not a confidence interval. Different success counts make these
success-conditioned comparisons; always read them with the success table.

| Material / interface | n | Median total tokens | Q1–Q3 | Median uncached input |
| --- | ---: | ---: | ---: | ---: |
| Cu · GUI | 10 | 327,244 | 228,784.5–418,877.5 | 43,445.5 |
| Cu · MCP | 10 | 177,289.5 | 146,852–252,354 | 33,142 |
| Re · GUI | 8 | 1,277,757.5 | 970,509.75–3,308,052.25 | 99,980.5 |
| Re · MCP | 10 | 385,335 | 274,407.5–428,912.25 | 62,217 |
| Pt · GUI | 6 | 1,428,543.5 | 861,398–1,879,129.25 | 94,554 |
| Pt · MCP | 10 | 447,886.5 | 406,537–497,407.5 | 64,494.5 |

Median reduction = `100 × (1 − MCP median / GUI median)`.
It is not the median of per-block percentage changes.

## Exact success and time results

| Material / interface | Strict success | Picture match¹ | Median seconds (Q1–Q3)² |
| --- | ---: | ---: | ---: |
| Cu · GUI | 10/10 | 10/10 | 130.4 (106.9–202.6) |
| Cu · MCP | 10/10 | 10/10 | 74.0 (63.6–86.7) |
| Re · GUI | 8/10 | 9/10 | 221.6 (210.8–449.1) |
| Re · MCP | 10/10 | 10/10 | 105.1 (92.6–122.7) |
| Pt · GUI | 6/10 | 9/10 | 322.8 (225.0–348.3) |
| Pt · MCP | 10/10 | 10/10 | 128.5 (121.6–148.8) |

¹ Post hoc exploratory audit. ² Strict successes only; nonaccepted runs remain
censored at 900 s, with no invented completion time.

## Calibration and audit trail

| Check | Outcome |
| --- | --- |
| Four earlier diagnostic participants | Excluded before the fresh 60-run phase; original records retained |
| Validator calibration | Removed false rejection of explicitly requested stored image quality and equivalent Render Area UI state; final checks use effective camera/crop and requested PNG size |
| Frozen inputs | Source, starting projects, target images and instructions fixed during the primary phase |
| Participant identity | All 60 fresh threads and requested model settings verified; no missing/duplicate cells |
| Accepted projects | All 54 independently reopened to check scientific preservation |
| MCP call accounting | Host convenience counter missed code-mode calls; secondary counts corrected from actual JSON-RPC wire logs. Provider token totals and primary outcomes unchanged |
| Images delivered | GUI 344 vs MCP 30 tool-result image blocks; 40 initial reference attachments per arm |

## Limits of the comparison

| Limitation | Consequence |
| --- | --- |
| Cu and Re used during development; Skill includes a similar flat/no-bonds recipe | Not a held-out benchmark |
| Skill and MCP change together | Cannot isolate the transport's causal effect |
| Ten runs per cell; success-conditioned summaries | No general ranking for other models, materials or hosts |
| Prepared cameras and group indices | Tests refinement/reproduction, not unrestricted figure design or site recognition |
| GUI cheaper in 2/10 Cu blocks | MCP is not always the lowest-token route; blocks are not identical provider random seeds |

## Published assets

{download}`Aggregate results <benchmark-results/material-gui-mcp-20260908.json>`
contain the chart inputs, sample sizes, variability and target-image hashes.
Recreate the charts from the repository with:

```bash
python scripts/plot_public_material_evaluation.py
```

Only the target renders and aggregate results are public here. Raw participant
logs, structure bundles and the internal protocol remain outside the release.
