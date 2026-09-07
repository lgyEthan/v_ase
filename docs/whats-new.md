# What is new in 0.3.3

## Focused MCP scene workflows

Scene snapshots expose the current effective camera, appearance and rendering
readiness without loading an image. Common style edits and complete visual/frame
transactions use document/revision guards, verification and rollback. Scientific
editing, analysis and exports remain available through focused tools.
[Follow the scene workflow](ai-scene.md).

## Discovery and focused guidance

MCP registers all callable tools by default so hosts can keep stable bindings.
Bounded search, exact schemas and focused guides reduce unnecessary context.
Progressive registration remains opt-in for hosts that support live tool-list
changes. The canonical Skill covers workflow and verification; tool schemas
supply parameters. [Connect MCP or native tools](ai-tools.md).

## Publication images and recovery

Publication rendering neutralizes selection outlines and selected plane-border
appearance without clearing live selection. Image inspection returns image
content, while ordinary responses carry artifact paths and metadata. Retained
request receipts support retries after an uncertain response; inspect the live
revision before starting a different mutation.

## Material evaluation

Sixty fresh Luna/max participants compared GUI-only and SKILL+MCP across three
prepared material scenes. Strict success was 24/30 and 30/30, respectively.
Successful-run median total tokens decreased by 46–70% with MCP; an exploratory
matching-picture audit found 28/30 and 30/30. These are workflow-specific results,
not a universal interface ranking. [Methods and detailed results](agent-material-evaluation.md).

## Upgrade

```bash
python -m pip install --upgrade "v_ase-gui[mcp]==0.3.3"
```

Restart the GUI and adapter together. CLI, HTTP and JavaScript compatibility
remain available; no model API key is required by v_ase itself. See the
[changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md) for earlier
releases and the [scientific validation guide](scientific-validation.md).
