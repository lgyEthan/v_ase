# Interface design and interaction contract

The desktop has a top document strip, a Scene sidebar, a scientific stage and a
contextual inspector. A dedicated GPT-6 Astra xhigh reviewer assessed the desktop
captures, transient surfaces and measured rendering work. The
[reference catalog](interface-references.md) records observations and evidence
for twelve applications. Styling, icons and motion are original.

## Composition

| Surface | Purpose and geometry |
| --- | --- |
| Document strip | 40 px across the top; the v_ase logo, filename tabs, dirty/save state, close buttons and New document. Tabs remain available when Scene is hidden. Long names truncate; the tab list scrolls without losing the New button. |
| Toolbar | 48 px; Scene toggle and access mode at stage left, global Find tools, Save/Export, then Style/Build/Analyze/Render directly above the inspector with its toggle. DOM focus order follows the visible order. |
| Scene sidebar | 216 px; actual scene objects, guides and optional overlays. It controls the active document, never a stale document generation. |
| Scientific stage | 8 px shell gutter and 10 px outside corners; occupies the actual unobstructed area. Camera, atomic graphics, background and exact output are scientific settings. |
| Inspector | 320 px default; named tool, purpose, 16 px inset and aligned values/units. Its title opens only the current category's tool list. |
| Timeline | Distinct tray for multi-frame documents, with transport, scrubber, frame position and playback settings. |
| Analysis | Separate results tray with title, export, close and independently resizable boundary. |

The Scene sidebar collapses by default at 1100 px or below; an explicit user
choice persists. Narrow portrait windows stack the inspector below the canvas.
Short landscape windows retain side-by-side editing with scrollable forms.
Direct/notebook editors retain their original app, camera and file handles when
additional documents are opened.

**View only** (lock) and **Edit structure** (pencil) form one mutually exclusive
segment. These describe access to physical edits. **Camera** labels viewport
navigation; **Display & guides** names interface/background/guide settings.
Native desktop menus live in the OS menu bar; the desktop has no redundant
in-app ellipsis menu. Browser/notebook hosts have one bounded, opaque command
menu, with subgroups expanding inside its surface.

**Find tools…** searches every category and command, regardless of the current
workspace. Command+F on Mac and Ctrl+F elsewhere focus it. Opening search does
not change modes or routes. Results show their category. Enter opens a result;
Up/Down navigate, Escape restores the actual opener, and outside interaction
closes it without taking focus from the clicked control. The popup is anchored
to the toolbar launcher and clamped to the window.

The inspector title is a separate, category-scoped chooser with no second search
field. Arrow/Home/End move focus; Enter activates, Escape returns to the title.
Switching categories updates this list; global Find remains independent.

## Appearance and controls

Graphite is the neutral default. Slate is cool blue, Stone warm neutral and Moss
the optional green palette. Each supplies the complete shell, sidebar, inspector,
fields, hover/pressed states, separators, selection, accent and focus ring.
System/Light/Dark is an independent preference. Parent workspace and editor
frames update synchronously. Both preferences persist in the local profile;
offline HTML exports retain their selected interface appearance.

| Role, Graphite | Light | Dark |
| --- | --- | --- |
| Shell | `#f1f2f4` | `#202226` |
| Scene sidebar | `#e9ebee` | `#24272b` |
| Inspector | `#fafafb` | `#292c31` |
| Field | `#ffffff` | `#34383f` |
| Action | `#3267cf` | `#91b8ff` |

Appearance changes never set the scientific background, atom colors, lighting,
camera or image export profile. Existing saved scientific backgrounds remain
intact. Set the viewport background explicitly in Display & guides.

System typography uses 13 px property labels, 12 px supporting text and 18 px
tool names. Values use tabular numerals; coordinates may use monospace. Fields
and unit wrappers are 28 px high, with one shared label/control track and 8 px
vertical gaps. Matrices, colors, checkboxes and vector subfields retain their
appropriate geometry. Small non-disabled text
has at least 4.5:1 contrast on its intended surface; focus rings target 3:1.
Controls share normal, hover, pressed, focused, disabled and invalid states.
Native selects reserve arrow space and preserve keyboard selection; forced
colors restores the system arrow. Open custom lists stay within the window.

Atom appearance uses expandable label groups. Selection and visibility remain
independent of disclosure. Expansion and unfinished labels/carets survive a
refresh only while their atom binding and stored value remain unchanged.
Delete/Backspace on these controls never deletes scientific atoms. XYZ entry
has explicit Å units. Constraints show one selection scope and relevant controls.
Image output exposes exact dimensions, framing, scale, background and format;
its completed thumbnail uses exported bytes, and Save a copy reuses those bytes.

## Interaction and motion

Motion acknowledges state changes and can be interrupted. Workspace selection
has one traveling indicator; deliberate route changes use a brief 120 ms entry,
while rapid switches skip replay. Panels travel for about 140 ms with a short
opacity change. These are v_ase choices, not measurements copied from references.
Reduced motion removes travel. Scientific values are never eased.

Panel toggles commit stage geometry once. Only the panel surface animates;
the canvas is never stretched or scaled to hide rendering work. Each toggle
allocates/repaints the WebGL canvas at most once. Repeated same-size resize
notifications do not redraw it. Closing leaves no panel strip. Opening never
invokes Fit. Width-only orthographic resizes preserve vertical frustum, zoom,
coordinates, direction, target and pixels per Å. Semantic/export orthographic
zoom is 1 because `ortho_scale` includes the effective world height.

Sliders, scrubbing, object gestures and resize handles follow input directly.
During a pointer resize, Escape/cancellation/focus loss restores the start;
release persists it. Arrow keys commit steps, Shift increases the step,
Home/End selects bounds and double-click resets. Escape after a committed key
step keeps it. Native document drags reorder horizontally by tab midpoint or
show a new-window destination below the strip; cancellation commits neither.
Panel toggle icons have distinct open/closed geometry, Show/Hide labels and
matching pressed/expanded state.

Menus dismiss outside; Escape returns to their launcher. Camera and lighting
popups retain full geometry while revealing; their background contains every
visible control throughout. Closing lighting returns focus to its Camera button.
Camera disclosure leaves the axis gizmo fixed. Actual stage, popup and gizmo
bounds choose a separate popup column, with a bounded scrollable fallback when
space is limited; a fixed translation offset is insufficient.
Lighting may use the free inspector-side region in very short windows; its
compact form stacks fields while keeping the renderer selector and Close
reachable. Internal scrolling never recalculates the card's own position.
Dialogs take focus and isolate background controls before their first frame,
then restore a visible launcher. Busy work blocks conflicting keyboard, pointer
and parent-document actions immediately, even during the 180 ms deferred
progress surface. Each overlapping task owns its cleanup. Workspace readiness
follows release of initial input isolation. Scene actions validate session and
child generation; child dialogs/busy work isolate both tabs and Scene.

## Review and verification

Use fresh headless browsers while the researcher uses the host. Never attach
to an existing browser, move foreground windows or send OS input. Native OS
checks need an idle/dedicated test host. Headless tests load the actual desktop
adapter with a controlled bridge; this does not establish native OS frame rate.

Review 1440×900, 1280×800 and 1024×768; both appearances and all four palettes;
real multiple documents and dirty/long names; both modes; expanded, empty and
invalid forms; all transient menus; analysis and export completion. Check opening,
settled, closing, interrupted and reduced-motion states, not just end images.

The warmed before/after panel benchmark covers 64 atoms and 1728 bonded Si atoms,
requested DPR 1/2, twelve toggles per context. Record allocations, scientific
draws, handler/JS/layout work, rAF distributions and camera/coordinate invariance.
Report effective renderer pixel ratio separately from requested DPR. Headless
software timings establish reduced redundant work, not guaranteed native FPS.

`tests/test_browser_ui_revision.py` covers both browser and native adapter,
global search placement/lifecycle, top tabs/logo, exclusive modes, atomic themes,
opaque menus, one-resize toggles and exact image-byte preservation.
`tests/test_ui_palette_contract.py` checks contrast. Existing scientific,
collaboration, file/export, stale-revision and native drag checks remain required.
`tests/test_browser_ui_refinement.py` checks category scope, desktop toolbar
association, measured input tracks, popup/gizmo collisions during motion and
grid pixel invariance under large far-clip changes. The grid constructs rays
from the camera basis without subtracting far-plane world positions; it still
uses one quad, no depth writes and no per-line geometry.

Mode completion updates the persistent segment and one accessible live-region
announcement. It does not stack success toasts for mutually exclusive states.
Warnings and failed changes remain visible. A captured native tab drag accepts
Escape from the parent or a focused editor iframe; losing window focus cancels it.

The global index is generated from all openable editor routes, including Water,
Isosurfaces, project/default settings and the format guide. Utility render routes
keep Render selected. Search height is clamped below its actual launcher. In
short windows the analysis surface begins below the actual toolbar boundary,
including the document strip, so navigation and its Back action remain usable.

Analysis plots use explicit title objects for axis and colorbar labels, matching
[the Plotly title contract](https://plotly.com/javascript/guides/migrating-to-v3/).
Regression checks read actual SVG quantity/unit text and bounds, rather than
accepting a title string in a layout object that the renderer silently ignores.
