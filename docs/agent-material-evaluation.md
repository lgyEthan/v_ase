# GUI and SKILL+MCP material evaluation

In a 60-run comparison, SKILL+MCP reached the strict target in 30/30 runs,
compared with 24/30 for GUI-only. Among successful runs with complete usage
accounting, MCP reduced median total tokens by 46–70% across the three tasks.
These are descriptive results for this workflow and model, not a universal
ranking of interfaces.

```{contents} On this page
:local:
:depth: 1
```

## Tasks and starting structures

Each participant received an existing structure project, a reference image,
the same written target, and predetermined atom indices. Participants styled
the structure; they did not generate structures or classify chemical roles.

| Material | Scientific atoms | Requested visualization |
| --- | ---: | --- |
| Cu₅O₄/Cu(111) | 41 | Switch the prepared view to flat 2D and hide bonds, preserving other settings; 534 × 417 pixels. |
| ReSe₂/graphene | 236 | Keep the prepared top view and atom styles; apply flat red bonds to nine supplied Re–Re index pairs, with thickness 0.12 and opacity 1; 1600 × 1250 pixels. |
| Pt₃O₄/CeO₂ | 55 | Style four supplied groups independently: support Ce, support O, cluster Pt and cluster O. Preserve the prepared top camera and 3 × 3 × 1 display repetition; 1000 × 1000 pixels. |

The Re–Re pairs were `[2,20]`, `[2,29]`, `[11,20]`, `[11,29]`, `[5,11]`,
`[5,23]`, `[5,32]`, `[14,23]`, and `[14,32]` (zero-based). Their target color
was `#d7191c`.

For Pt₃O₄/CeO₂, support Ce/O colors were `#ded6bc` / `#4a1410`, and cluster
Pt/O colors were `#96969d` / `#d4372d`. Their respective scale settings were
1.70, 2.45, 1.85, and 2.50. The scene used standard materials, high sphere
quality, a white background and no bonds, cell, axes, grid or overlays.
These labels were visualization groups, not changes to chemical species or
physical constraints. The published Pt structure has no fixed-layer constraints.

The Pt source is frame 0 of `pt3o4_DFT_10_most_stable.extxyz` from
[Zenodo record 16809151](https://zenodo.org/records/16809151), accompanying
[Dominguez et al., J. Chem. Phys. 165, 034115 (2026)](https://doi.org/10.1063/5.0302876).
It corresponds to the Pt₃O₄ composition illustrated in Fig. 5(c), middle column,
lower top view. The target is our own v_ase rendering of the supplied structure,
not a pixel-identical reproduction of the paper's renderer. Display repetition
does not turn the 55-atom source into a different scientific structure.

## Experimental conditions

The study ran on 8 September 2026 against the frozen scene-interface source
preceding the 0.3.3 release. All 60 participants were fresh independent
`gpt-5.6-luna` threads with reasoning effort `max`; there were no model fallbacks
or inherited conversation histories. Each of the six material/interface cells
had ten runs. Ten randomized blocks each contained all six cells and ran
serially. Schedule seed 20260908 controls ordering, not provider sampling.
Each run had a fixed 900-second horizon.

- **GUI-only:** editing through a frozen Playwright screenshot/accessibility
  helper, using unique accessible names/roles or screen coordinates. No
  semantic API, CLI, raw DOM editing or indexed accessibility-node selector.
- **SKILL+MCP:** the frozen canonical Skill, read before the first MCP operation,
  and actual stdio MCP calls through the official SDK. All tools were registered
  at initialization; bounded schema discovery was handled by the host.
- **Common capture:** both arms used evaluator helpers for image inspection
  and submission. Consequently this compares editing workflows, not the cost
  of navigating native export dialogs.

The source, starting projects, target images and instructions were fixed within
the primary phase. Four earlier diagnostic participants were excluded before
the final 60-run phase: their validators had incorrectly rejected explicitly
requested stored image quality or equivalent Render Area UI state. The final
validator checks effective camera/crop geometry and requested PNG dimensions.
Those diagnostic outcomes are not pooled into the following results.

## Strict success and token usage

Strict acceptance required the requested style, camera and output dimensions,
visual inspection, preservation of scientific arrays and other declared state,
and acceptance within 900 seconds. Preservation included the application's
`v_ase_atom_type` label-array representation and unrequested settings.

**Token medians below include only strict successes with complete provider
accounting.** All 54 successful runs had complete accounting. The six GUI
timeouts have incomplete observed usage, which is a lower bound and is not
reported as tokens needed to obtain a matching image.

| Material | GUI successes | MCP successes | GUI median tokens | MCP median tokens | Median reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cu₅O₄/Cu(111) | 10/10 | 10/10 | 327,244 | 177,289.5 | 45.8% |
| ReSe₂/graphene | 8/10 | 10/10 | 1,277,757.5 | 385,335 | 69.8% |
| Pt₃O₄/CeO₂ | 6/10 | 10/10 | 1,428,543.5 | 447,886.5 | 68.6% |

| Material | GUI token Q1–Q3 | MCP token Q1–Q3 | GUI median uncached input | MCP median uncached input |
| --- | ---: | ---: | ---: | ---: |
| Cu₅O₄/Cu(111) | 228,784.5–418,877.5 | 146,852–252,354 | 43,445.5 | 33,142 |
| ReSe₂/graphene | 970,509.75–3,308,052.25 | 274,407.5–428,912.25 | 99,980.5 | 62,217 |
| Pt₃O₄/CeO₂ | 861,398–1,879,129.25 | 406,537–497,407.5 | 94,554 | 64,494.5 |

Total tokens are provider-reported input plus output, accumulated over the run.
Input already includes cached input; output already includes reasoning tokens.
These subsets are not added a second time. Total tokens are neither a price
estimate nor a count of unique words: repeated context contributes repeatedly.
Terminal cumulative usage was reconciled with per-response accounting and can
include the final assistant reply. It is not an isolated measure of transport
overhead or exact token usage at the first visually matching image.

## Time to acceptance

Times use the first accepted submission, not the final assistant message.
The following medians and interquartile ranges are also conditional on strict
success. They should be read alongside the success counts above.

| Material | GUI median seconds (Q1–Q3) | MCP median seconds (Q1–Q3) |
| --- | ---: | ---: |
| Cu₅O₄/Cu(111) | 130.4 (106.9–202.6) | 74.0 (63.6–86.7) |
| ReSe₂/graphene | 221.6 (210.8–449.1) | 105.1 (92.6–122.7) |
| Pt₃O₄/CeO₂ | 322.8 (225.0–348.3) | 128.5 (121.6–148.8) |

An accounting grace period after acceptance, and the interrupt/drain after a
timeout, were excluded from task time. Unsuccessful runs remain censored at
900 seconds rather than being assigned an invented completion time.

## Matching pictures versus exact project preservation

A separate **post hoc, exploratory** audit retained render/style/camera,
dimensions, inspection and physical-data checks, but allowed a different
representation of the internal `v_ase_atom_type` annotation array. It found:

| Material | GUI matching submitted figures | MCP matching submitted figures |
| --- | ---: | ---: |
| Cu₅O₄/Cu(111) | 10/10 | 10/10 |
| ReSe₂/graphene | 9/10 | 10/10 |
| Pt₃O₄/CeO₂ | 9/10 | 10/10 |
| Total | 28/30 | 30/30 |

Four GUI strict failures therefore still produced a matching picture while
preserving the physical structure. A label-array mismatch is not evidence of
damaged coordinates or changed chemical species. This exploratory endpoint
does not replace the primary results. Its first-match timing was reconstructed
from tool-event timestamps; token snapshots at dispatch are lower bounds, so
terminal retry costs must not be called necessary tokens-to-picture-success.

## Image use and audit checks

Raw provider outputs contained 344 tool-result image blocks for GUI and 30
for MCP: one final image per MCP run. Initial reference attachments were equal
at 40 per arm (the Re task supplied two references). The MCP workflow therefore
used semantic scene information for editing and a final image for visual QA in
these runs. Image counts alone do not establish the cause of the token gap.

All 60 thread identities and requested model settings were verified. Input
hashes were unchanged, no cells were missing or duplicated, and all 54 accepted
projects were independently reopened to check scientific preservation. The
host's convenience MCP-call counter missed code-mode calls; secondary call
counts were corrected from actual MCP JSON-RPC wire logs. Provider token
accounting and primary outcomes were unaffected.

## Interpretation and limits

The observed medians favor SKILL+MCP in all three tasks, but **GUI used fewer
total tokens in two of the ten Cu blocks** where both runs succeeded. A simple
two-setting task can make discovery and workflow overhead comparatively large.
Blocks do not represent identical provider random seeds.

This comparison includes the Skill's guidance, not just MCP transport. Cu and
Re tasks had been used during development, and the Skill includes a generic
flat-view/hide-bonds example similar to the Cu task. This is not a held-out
benchmark, a transport-only causal experiment or proof of universal SOTA.
Ten runs per cell and success-conditioned medians cannot establish general
performance on other materials, models, GUI hosts or unconstrained composition
tasks. The prepared cameras also make this an existing-view reproduction task,
not free-form figure design.

This page publishes aggregate results and methods. Private participant logs,
structure bundles and the internal research protocol are not distributed with
the software. See [MCP setup](ai-tools.md) and [scene workflows](ai-scene.md)
for the released interface used to perform this class of task.
