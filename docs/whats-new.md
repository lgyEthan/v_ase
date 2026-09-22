# What is new

## 0.4.1 — redesigned scientific workspace

This release introduces a wide viewport, an optional Objects drawer,
a single Style/Build/Analyze/Render workbench with responsive stacking,
exact editor shortcuts, explicit Measure mode, property-based atom radius,
independent output px/Å, and retained project Save/Save As with safe document
closure. Mac commands use Command, while Windows/Linux use Ctrl; fullscreen
Keyboard Lock is offered with explicit support/denial feedback rather than a
universal interception promise. Child-tab reloads now preserve both unsaved
commits and clean saved appearance. The new [workspace](workspace.md), [radius](property-radius.md),
[rendering](render-images.md), and [project](save-projects.md) guides describe
these workflows. Scientific tools are visible in each workbench, while
contextual object settings and analysis results stay beside the structure.

```bash
python -m pip install --upgrade "v_ase-gui[mcp]==0.4.1"
```

Restart running GUI/MCP servers after upgrading. Existing tunnel IDs and keys remain
usable; refresh the ChatGPT connection's discovered tools if needed.


## 0.3.8

**Rendering menu fix.** Render Lighting controls remain clickable outside the scrolling toolbar.

[Lighting controls](render-images.md#render-lighting) · [MCP tools](ai-tools-reference.md) ·
[Complete changelog](https://github.com/lgyEthan/v_ase/blob/main/CHANGELOG.md)
