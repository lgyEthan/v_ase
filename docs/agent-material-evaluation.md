# GUI or SKILL+MCP? A visual comparison

**Primary study: 3 materials · 60 runs. Separate Cu₈O₄ extension: 20 runs. Luna / max · 15-minute limit.**

[Targets & tokens](#targets-and-token-use) · [Success criteria](#what-counts-as-success) ·
[Cu₈O₄ extension](#cu8-extension) · [Timing](#time-and-image-use) ·
[Detailed methods](agent-material-evaluation-methods.md)

## Targets and token use

Both interfaces received the **same project, camera, atom indices and references**.
The task was visual reproduction; group identities were supplied.

The three cards below show **fixed targets**, not selected participant outputs.
Original crops are preserved. Click to enlarge.

**Bars: median total tokens of strict successes only. Timeouts are excluded.**

::::::{container} eval-comparison-grid

:::::{container} eval-case

### Cu₅O₄/Cu(111)

```{figure} assets/agent-evaluation/cu5o4-target.png
:alt: Fixed Cu5O4/Cu(111) target: flat copper and red oxygen circles, with the supplied tight crop.
:class: eval-target
:width: 420px

**Flat view, no bonds.** Preserve all other styling. 41 source atoms.
```

```{figure} assets/agent-evaluation/cu5o4-tokens.png
:alt: Cu successful-run median total tokens: GUI 327,244 from 10 runs; MCP 177,289.5 from 10 runs.
:class: eval-token-chart
:width: 520px

**45.8% lower median** with MCP. Strict success: **10/10 vs 10/10**.
```

:::::

:::::{container} eval-case

### ReSe₂/graphene

```{figure} assets/agent-evaluation/rese2-target.png
:alt: Fixed ReSe2/graphene top-view target: differently colored atom groups and a red Re-Re bond motif in the supplied crop.
:class: eval-target
:width: 420px

**Nine specified Re–Re bonds.** Preserve atom colors and top view. 236 source atoms.
```

```{figure} assets/agent-evaluation/rese2-tokens.png
:alt: ReSe2 successful-run median total tokens: GUI 1,277,757.5 from 8 runs; MCP 385,335 from 10 runs.
:class: eval-token-chart
:width: 520px

**69.8% lower median** with MCP. Strict success: **GUI 8/10 · MCP 10/10**.
```

:::::

:::::{container} eval-case

### Pt₃O₄/CeO₂

```{figure} assets/agent-evaluation/pt3o4-target.png
:alt: Fixed Pt3O4/CeO2 target: gray Pt and red cluster oxygen over beige Ce and dark-red support oxygen.
:class: eval-target
:width: 420px

**Four preassigned color/radius groups.** Distinguish cluster and support. 55 source atoms; display repetition only.
```

```{figure} assets/agent-evaluation/pt3o4-tokens.png
:alt: Pt3O4 successful-run median total tokens: GUI 1,428,543.5 from 6 runs; MCP 447,886.5 from 10 runs.
:class: eval-token-chart
:width: 520px

**68.6% lower median** with MCP. Strict success: **GUI 6/10 · MCP 10/10**.
```

:::::

::::::

(cu8-extension)=
## Cu₈O₄ prepared-scene extension

This separate v_ase 0.3.8 phase used a 44-atom Cu₈O₄/Cu(111) scene with 24
fixed atoms. Both arms received the exact 987 × 882 target PNG and the same
prepared project. The requested edit was only **3D → flat 2D** and **bonds on →
off**; camera, crop, cell, coordinates, colors, radii, labels, replication and
visual translation had to remain unchanged.

::::::{container} eval-comparison-grid

:::::{container} eval-case

### Starting scene

```{figure} assets/agent-evaluation/cu8o4-start.png
:alt: Cu8O4 starting scene with three-dimensional shaded atoms and visible black bonds.
:class: eval-target
:width: 420px

The shared baseline: 3D atom shading and visible bonds.
```

:::::

:::::{container} eval-case

### Fixed target

```{figure} assets/agent-evaluation/cu8o4-target.png
:alt: Cu8O4 target with flat solid atom fills, dark outlines and no bonds.
:class: eval-target
:width: 420px

The accepted target: uniform 2D fills and no bonds.
```

:::::

::::::

```{figure} assets/agent-evaluation/cu8o4-tokens.png
:alt: Cu8O4 total-token distribution: GUI median 1,589,856.5 and MCP median 145,256, with ten strict successes in each arm.
:class: eval-token-chart
:width: 760px

Every dot is one fresh strict success. Bars show median and Q1–Q3.
```

| Result | GUI-only | SKILL+MCP |
| --- | ---: | ---: |
| Strict success | **10/10** | **10/10** |
| Median total tokens (Q1–Q3) | 1,589,856.5 (996,207.75–2,670,396.5) | 145,256 (133,082.5–184,405.5) |
| Median first-acceptance time (Q1–Q3) | 500.8 s (350.8–657.1) | 85.5 s (73.3–100.2) |
| Tool-result images | 103 | 10 |
| Tool calls / invalid calls | 695 / 6 | 40 / 0 |

MCP lowered the median total-token count by **90.9%** and median time by
**82.9%**. It used fewer tokens and less time in all ten paired blocks. Each MCP
participant loaded the frozen Skill before its first scientific MCP call and
received one final render image; GUI participants received 3–18 screenshots.

The examples below follow the predeclared rule: the lowest-repetition strict
success with complete accounting, rather than the best-looking run. Both are
pixel-identical to the fixed target.

::::::{container} eval-comparison-grid

:::::{container} eval-case

```{figure} assets/agent-evaluation/cu8o4-gui-example.png
:alt: Predeclared representative GUI-only Cu8O4 output, pixel-identical to the target.
:width: 420px

GUI-only · `cu8o4-gui-b05-r01`
```

:::::

:::::{container} eval-case

```{figure} assets/agent-evaluation/cu8o4-mcp-example.png
:alt: Predeclared representative Skill plus MCP Cu8O4 output, pixel-identical to the target.
:width: 420px

SKILL+MCP · `cu8o4-mcp-b05-r01`
```

:::::

::::::

This extension is not pooled with the earlier Cu₅O₄ result: it used a different
date, v_ase version, resolution and reference disclosure. One GUI and one MCP
engineering pilot were excluded before freezing the phase after they exposed a
duplicate MCP image counter; all 20 reported runs were then collected fresh.
The task is a prepared-scene refinement and the Skill contains a similar
flat/no-bonds recipe, so it does not establish a transport-only or universal
SOTA claim. {ref}`Exact protocol and audit <cu8-extension-methods>`
· {download}`Cu₈O₄ aggregate data <benchmark-results/cu8-gui-mcp-20260921.json>`

:::{admonition} Read the bars with the success counts
:class: important
The charts show **median total tokens for strict successes with complete
accounting**. All charts use a zero baseline. In the primary 60-run study, the
six GUI timeouts are excluded because their usage is incomplete; the Cu₈O₄
extension has complete accounting for all 20 runs. `n` is the number of included
successes. MCP means **SKILL+MCP** throughout.
:::

## What counts as success?

The aggregate table below is the primary three-material study; Cu₈O₄ is kept
separate in the extension section above.

| Check | GUI | SKILL+MCP |
| --- | ---: | ---: |
| **Strict completion** — requested picture **and** full declared state preservation | **24/30** | **30/30** |
| **Matching picture** — exploratory audit of image + physical data | **28/30** | **30/30** |

**Why 24 and 28 differ:** four more GUI runs produced a matching picture but
failed the stricter state checks. Those checks also preserve internal atom-label
representation, document mode and unrequested settings. A label mismatch does
**not** mean atomic coordinates or chemical species were damaged.

The matching-picture audit was added **post hoc**. It allows internal label-array
representation differences and does not replace the primary endpoint.
[Exact definitions](agent-material-evaluation-methods.md#success-and-accounting)

## Time and image use

| Material | GUI median time | MCP median time |
| --- | ---: | ---: |
| Cu₅O₄/Cu(111) | 130 s | 74 s |
| ReSe₂/graphene | 222 s | 105 s |
| Pt₃O₄/CeO₂ | 323 s | 129 s |

Times include **strict successes only**, using first acceptance. Timeouts remain
censored at 900 seconds.

| Images delivered to the model | GUI | MCP |
| --- | ---: | ---: |
| Tool-result images | 344 | 30 |
| Initial reference attachments | 40 | 40 |

MCP used one final inspection image per run. Image counts alone do not establish
what caused the token difference.

## What this comparison supports

- **Observed:** lower MCP medians in these three prepared-scene tasks.
- **Exception:** GUI used fewer tokens in **2 of 10 Cu blocks**.
- **Scope:** Skill guidance and interface are evaluated together; this is not
  transport-only evidence or a universal SOTA ranking.
- **Familiarity:** Cu and Re were used during development. This is not a held-out
  benchmark, and the starting cameras were already prepared.

[Task specifications, variability and audit details](agent-material-evaluation-methods.md) ·
{download}`Aggregate data <benchmark-results/material-gui-mcp-20260908.json>`

```{toctree}
:maxdepth: 1
:hidden:

agent-material-evaluation-methods
```
