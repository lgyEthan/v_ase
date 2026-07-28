# v_ase Agent Interface

Use this interface when an AI agent must inspect an atomic structure, choose a
camera, configure the scientific view, and produce a final render without
repeated screenshot interpretation.

## Start

```bash
v_ase gui STRUCTURE --for-ai
```

The first stdout line is a JSON handshake. Keep that process running. The
handshake contains:

- `human_url`: the normal v_ase GUI for immediate human takeover;
- `state_url`: current-frame structure, labels, cell, constraints, forces, and
  calculator metadata as JSON;
- `schema_url`: the machine-readable control contract;
- `skill_url`: this guide;
- `browser_api`: `window.v_aseAI`.

The structure file remains where v_ase is running. For `HOST:/path` inputs, the
server reads and processes the trajectory remotely; only the active frame and
rendered browser data cross the SSH tunnel.

## Semantic Browser API

Open `human_url` in a browser automation context. The workspace and editor
frame expose the same async API:

```javascript
const ai = window.v_aseAI;
await ai.ready();
const state = await ai.describe();
```

`describe()` returns positions in Angstrom, labels, ASE chemical elements,
cell, PBC, constraints, current frame, frame count, selection, visual settings,
and the exact camera. Use this data instead of reading pixels.

Apply a deterministic view:

```javascript
await ai.apply({
  frame: 0,
  display: {
    showBonds: true,
    showCell: true,
    showGrid: false,
    viewportBackground: "white",
    atomDisplayMode: "3d",
    lightingMode: "studio-shadow",
    sunIntensity: 2.2
  },
  camera: {
    axis: "+Z",
    fit: "structure"
  }
});
```

Valid axis views are `+X`, `-X`, `+Y`, `-Y`, `+Z`, and `-Z`. For an arbitrary
camera, provide finite `position`, `target`, and `up` vectors. A
screen-relative orbit accepts `left`, `right`, `up`, `down`, `roll-cw`, or
`roll-ccw` plus an angle in degrees.

Select unit-cell atoms by zero-based index:

```javascript
await ai.apply({selection: {clear: true, indices: [0, 4, 9]}});
```

In View mode, a periodic replica can be selected with
`{index: 4, cellOffset: [1, 0, 0]}` in `selection.references`.

Render with the exact v_ase export pipeline:

```javascript
const result = await ai.render({
  width: 1920,
  height: 1080,
  options: {
    transparentBackground: false,
    backgroundColor: "#ffffff",
    includeGrid: false,
    includeAxes: false,
    includeCell: true,
    renderMode: "studio-shadow",
    sphereQuality: "high",
    sphereQualityScale: 1.0
  }
});
```

The result contains a PNG `dataUrl`, dimensions, camera, and applied options.
Decode the data URL to save the final image. This is the same capture path used
by Export Image, so a screenshot crop is unnecessary.

## Human Takeover

Open `human_url` at any time. It is not a separate AI renderer: the human sees
the same live document, frame, camera, selection, and visual settings. The top
bar can switch between View and Edit without restarting the session.
