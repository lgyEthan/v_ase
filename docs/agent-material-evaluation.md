# GUI or SKILL+MCP? A visual comparison

**3 materials · 2 interfaces · 10 fresh runs each · Luna / max · 15-minute limit**

[Targets & tokens](#targets-and-token-use) · [Success criteria](#what-counts-as-success) ·
[Timing](#time-and-image-use) · [Detailed methods](agent-material-evaluation-methods.md)

## Targets and token use

Both interfaces received the **same project, camera, atom indices and references**.
The task was visual reproduction; group identities were supplied.

Images are **fixed targets**, not selected participant outputs. Original crops
are preserved. Click to enlarge.

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

:::{admonition} Read the bars with the success counts
:class: important
The charts show **median total tokens for strict successes with complete
accounting**. All charts use the same zero-based scale. The six GUI timeouts are
excluded; their recorded usage is incomplete, not a cost to successful completion.
`n` is the number of included successes. MCP means **SKILL+MCP** throughout.
:::

## What counts as success?

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
