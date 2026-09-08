# Tools by feature

This reference describes the v_ase 0.3.3 tool catalog.
See [scene workflows](ai-scene.md) for compact inspection and visual edits.

The catalog below is generated from the same schemas used by MCP and native
function tools. Inputs use snake_case. Scientific units are Angstrom and
degrees; atom and frame indices are zero-based. Tool discovery provides
complete nested types, bounds and conditions.

```{contents} On this page
:local:
:depth: 1
```

Ordinary editing tools also require `expected_document_id` and
`expected_revision`; these guards, optional `request_id` and `response_profile` are
omitted from the tables for readability. Interrupt controls may omit the
revision. See [connection and recovery](ai-tools.md#read-edit-verify).

## Discovery, guides and image inspection

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_search_tools`
  - Find a bounded set of tools by feature or exact name. Returns short matches, not the full catalog or duplicate schemas.
* - `vase_tool_schema`
  - Read the exact typed schemas for at most four named tools. Use only when the host has not already supplied them.
* - `vase_read_guide`
  - Read one short scientific workflow or an exact section, with bounded paging. Parameter schemas come from tools.
* - `vase_inspect_image`
  - Inspect an image artifact produced by this connection. MCP returns image content directly; native hosts embed the validated artifact bytes as an image, never as text.
```

## Rendered scene and visual transactions

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_style_scene`
  - Change common figure settings in one visual transaction. For flat atoms and hidden bonds set atom_display_mode='2d' and show_bonds=false. Preserves camera, pair policies and every unmentioned setting. No geometry lookup is needed for…
* - `vase_scene_snapshot`
  - Inspect the actual rendered scene: camera/crop, interaction state and readiness. Add bounded geometry sections for renderer-resolved atom positions, periodic references and per-edge appearance. Start with the default summary for…
* - `vase_scene_readiness`
  - Wait for frame, surface, plane, scalar-color and vector rendering to settle; reports pending work and errors without images.
* - `vase_apply_scene`
  - Apply one visual/frame transaction without changing stored scientific data. Requires document and revision guards. Unmentioned fields survive; background rendering settles before success. On failure restore the previous visual/frame…
* - `vase_select_volumetric_planes`
  - Select the exact plane IDs, or [] to clear plane selection. Optional clearAtoms/clearGizmos clear the other selection types. This changes interaction state only, never plane geometry or scientific arrays.
```

## Connection and collaboration

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_describe`
  - Read the live GUI document. Start with summary; use a focused profile only when needed. Lengths are Angstrom, angles degrees, indices zero-based.
* - `vase_ready`
  - Check that the shared human GUI is connected.
* - `vase_documents`
  - List document tabs in the connected workspace.
* - `vase_new_document`
  - Create and activate an empty editable document tab in the shared workspace.
* - `vase_activate`
  - Activate the requested human GUI tab. Describe again before any edit.
* - `vase_capabilities`
  - Read the compact live feature catalog, including installed scientific capabilities.
* - `vase_events`
  - Poll human/agent collaboration events. Keep the returned cursor; after an event or gap, describe the live document before editing.
```

## Trajectory playback

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_set_frame`
  - Set frame in the same live document.  Review changedPaths in the result.
* - `vase_set_playback`
  - Start or stop the selected trajectory timeline. Pause before scientific reads or edits; playback advances revisions and frames.
* - `vase_pause_playback`
  - Pause the active movie and synchronize its displayed frame. Requires document identity; revision is optional because playback keeps advancing it.
```

## Structure editing and construction

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_set_mode`
  - Set mode in the same live document.  Review changedPaths in the result.
* - `vase_set_selection`
  - Set selection in the same live document.  Review changedPaths in the result.
* - `vase_bulk_catalog`
  - Installed ASE bulk materials and supported crystal/cell choices.
* - `vase_bulk_preview`
  - Preview ASE bulk geometry, cell and atom count without replacing the live structure.
* - `vase_wrap`
  - Requires a usable cell. View mode wraps the displayed atoms only; Edit mode wraps ASE positions with the requested constraint handling.
* - `vase_translate_all`
  - coordinateMode is cartesian or fractional.
* - `vase_set_unit_cell`
  - Defines the 3 x 3 ASE cell without scaling atom coordinates. pbc defaults to [true,true,true]. This also creates a usable scratch document when no atoms have been loaded.
* - `vase_build_bulk`
  - Builds a periodic crystal with ase.build.bulk. Query /api/build/bulk/catalog/{session_id} for installed-ASE reference materials and compatible cell shapes, then preview through /api/build/bulk/preview/{session_id}. Custom compounds…
* - `vase_set_supercell`
  - reps contains three integers from 1 through 64.
* - `vase_make_supercell`
  - matrix is a 3 x 3 integer transformation matrix.
* - `vase_add_atom`
  - Prerequisites: label-or-element.
* - `vase_delete_selection`
  - View mode hides the exact selected visual instances without changing ASE atoms. Edit mode deletes the corresponding base atom indices from the physical structure. Prerequisites: selection-or-indices.
* - `vase_set_identity`
  - Prerequisites: selection-or-indices.
* - `vase_move_selection`
  - Prerequisites: selection-or-indices.
* - `vase_rotate_selection`
  - axis defaults to [0,0,1]. pivot is com, active, origin, cell, or an explicit three-number position. Prerequisites: selection-or-indices.
* - `vase_scale_selection`
  - Scales physical Cartesian atom coordinates about the pivot without changing atom or bond radii. axis is X, Y, Z, or ALL and defaults to ALL. pivot is com, active, origin, cell, or an explicit three-number position. Prerequisites:…
* - `vase_center_selection_at_origin`
  - Sets visual translation so the selected atom, or the mass-weighted center of mass of multiple selected atoms, lies at Cartesian origin. ASE positions and the unit cell are unchanged. Prerequisites: selection-or-indices.
* - `vase_undo`
  - Undoes the latest available visual or physical edit in the shared GUI history. Describe afterward to verify the affected state.
* - `vase_redo`
  - Reapplies the latest undone visual or physical edit in the shared GUI history. Describe afterward to verify the affected state.
* - `vase_reset_coordinates`
  - Restores all frames from the document's stored reset baseline as one undoable physical edit.
* - `vase_load_settings`
  - Load saved visual settings from a relative JSON path below the GUI launch directory. Restores appearance, camera and render profile without replacing atom coordinates.
* - `vase_duplicate_selection`
  - Duplicate selected base atoms in Edit mode, preserving per-atom arrays, constraints, and appearance. Newly inserted atoms become selected.
* - `vase_configure_polyhedra`
  - Configure coordination hulls without changing atoms or bonds. Rules explicitly select centers and ligands with cutoff distances or exact periodic vertex references. Read scene-snapshot section polyhedra to verify membership and…
```

## Constraints and relaxation

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_set_apply_constraints`
  - Set applyConstraints in the same live document.  Review changedPaths in the result.
* - `vase_set_constraints`
  - kind is fixed_line or fixed_plane; vector has three components. Prerequisites: selection-or-indices.
* - `vase_start_relaxation`
  - When Add Atoms is active, this common operation routes the same calculator, cutoff, device, fmax, and step contract through placement relaxation while preserving the immutable pre-session host. Otherwise an ASE calculator must be…
* - `vase_stop_relaxation`
  - Stops the active ordinary or Add Atoms placement optimizer.
* - `vase_clear_relaxation_trajectory`
  - Removes the dedicated optimization movie while leaving its mode active. retain is final by default or displayed to keep the frame currently shown. Prerequisites: available-relaxation-trajectory.
* - `vase_exit_relaxation_mode`
  - Stops an active optimizer if needed, closes the dedicated movie timeline, and either keeps current coordinates (default) or restores the exact pre-relaxation structure when keep=false.
* - `vase_configure_calculator`
  - Configure the attached default repulsion calculator without starting optimization. Visual bond cutoffs are independent. Requires Edit mode.
```

## Camera and framing

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_set_quality`
  - Set quality in the same live document.  Review changedPaths in the result.
* - `vase_set_camera`
  - Set camera in the same live document. Use axis for a deterministic +/-X, +/-Y, or +/-Z view; use position/target/up for an explicit camera; fit='structure' frames the complete structure; orbit applies screen-relative…
* - `vase_set_render_area`
  - Set renderArea in the same live document. Persistent image, video, and HTML framing. Enable it to show the render gate, follow the viewport while composing, or set an independent camera that remains fixed while the scene changes.…
* - `vase_compose_view`
  - Creates a reproducible periodic composition without changing ASE coordinates. displaySupercell is visual replication, not set-supercell. centerMotif translates the periodic motif to targetFractional along chosen a/b/c axes using atom…
```

## Appearance and bonds

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_set_display`
  - Set display in the same live document. Partial visual settings. Common keys include showBonds, showCell, showAxes, showGrid, viewportBackground, atomDisplayMode, atomRadiusScale, labelRadii, labelColors, labelOpacities,…
* - `vase_set_visual_label`
  - Assigns a visualization-only label to exact zero-based atom indices while preserving ASE elements, coordinates, order, cell, PBC, and constraints. A topology-compatible trajectory receives the same index mapping in every frame;…
* - `vase_style_atoms`
  - Applies deterministic visualization overrides to the union of exact indices, visual labels, and ASE elements. radiusAngstrom is the final rendered radius in Angstrom after the global atom scale; radiusScale is an explicit per-index…
* - `vase_configure_bonds`
  - Configures visual bonds by unordered visual-label pair. Each pair may set enabled, maximumAngstrom, style, material, thicknessAngstrom, colorMode, color, and opacity. disableUnspecified=true makes the supplied enabled pairs an…
* - `vase_set_atom_colorscale`
  - Colors atoms by x/y/z, force norm, or a discovered numeric per-atom ASE array/calculator result. scope is all or selected. rangeMode is current, trajectory, or manual; every trajectory frame uses the same resolved minimum and maximum.…
* - `vase_set_interface_theme`
  - theme is system, light, or dark. system follows the browser/OS color-scheme preference and is the built-in default.
* - `vase_set_personal_visual_default`
  - Persists the current reusable visual settings for this OS user. Coordinates, trajectory data, absolute camera placement, and per-atom appearance overrides are excluded.
* - `vase_restore_app_visual_defaults`
  - Destructively deletes the saved personal visual default and applies the built-in v_ase visual settings to the active tab. confirm must be true and an agent must obtain human approval first.
* - `vase_style_polyhedra`
  - Change only face color/opacity or edge appearance of existing coordination rule IDs. Preserves centers, ligands, distances and every other rule; uses cached geometry. Set color=null to inherit center atom colors.
```

## File input

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_files`
  - List files below the GUI launch directory. Use returned relative paths for load/append/guest/volumetric operations; absolute and escaping paths are rejected.
* - `vase_load_structure`
  - Open a structure, trajectory, volumetric file, .vase project, or project HTML using a relative path below the GUI launch directory. Use the files query to discover paths. Replaces this tab; a nonempty document requires…
* - `vase_append_structure`
  - Append structures as trajectory frames or scalar grids as fields, using a relative path below the GUI launch directory. Project visual settings are ignored when appending.
```

## Atomic and molecular distributions

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_molecule_catalog`
  - Installed ASE molecule names, formulas, and native geometries.
* - `vase_insertion_pair_cutoffs`
  - Preview default repulsion onset distances independently of visual bonds.
* - `vase_insertion_domain`
  - Preview exact accessible insertion volume and optional realized molecular density without adding atoms.
* - `vase_scatter_atoms`
  - Starts an Add Atoms session or appends one or more element/label populations to the active session after placement relaxation is inactive. The first pre-session structure remains the immutable host across every placement.…
* - `vase_scatter_molecules`
  - Starts an Add Molecules session or appends molecules to the active Add session from the installed ASE G2 molecule catalog. Query /api/add-session/molecules/{session_id} before choosing a name. Molecule coordinates are placed and…
* - `vase_update_add_atoms_region`
  - Replaces all active Allow/Reject regions, or updates one stable regionId, without moving staged atoms. Regions can translate as a group but cannot be rotated. Prerequisites: active-cartesian-add-atoms-session.
* - `vase_relax_added_atoms`
  - Compatibility alias for the same shared placement-relaxation path used by start-relaxation. It starts asynchronous FIRE with one AdditionRepulsionCalculator attached to the complete staged structure. device selects CPU or CUDA and…
* - `vase_stop_added_atoms`
  - Prerequisites: active-add-atoms-relaxation.
* - `vase_finish_add_atoms`
  - Commits only inserted atoms; every host coordinate, constraint, and array is restored exactly. Prerequisites: inactive-add-atoms-relaxation.
* - `vase_cancel_add_atoms`
  - Restores the complete pre-session structure and history state. Prerequisites: active-add-atoms-session.
* - `vase_scale_add_atoms_regions`
  - Scales Cartesian insertion-region bounds about their shared center, or an explicit three-number pivot. axis is X, Y, Z, or ALL. Prerequisites: active-add-atoms-session.
```

## Analysis and stored properties

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_atom_scalar_catalog`
  - Discover available scalar field IDs for the requested frame.
* - `vase_atom_properties`
  - Read stored arrays and calculator properties for one base atom without evaluating its calculator.
* - `vase_frame_properties`
  - Read stored frame properties without evaluating the calculator. includeArrays can be large.
* - `vase_atom_scalar_values`
  - Read a discovered scalar field. allFrames returns trajectory data and may be large.
* - `vase_atom_scalar_range`
  - Find finite scalar bounds in the current frame or trajectory, optionally restricted to indices.
* - `vase_force_vectors`
  - Read stored Cartesian forces for a frame or trajectory. No force calculation is triggered.
* - `vase_colormap_catalog`
  - Discover installed Matplotlib colormaps.
* - `vase_colormap_lut`
  - Sample a discovered colormap for visual verification.
* - `vase_refresh_displacements`
  - Optionally updates display settings, then recomputes displacement analysis for the current frame and configured reference/mapping.
* - `vase_calculate_rdf`
  - pairMode is active, selected, all, or none. selected filters partial curves to active bonds whose endpoints are both selected in the GUI; activePairs can provide the same label-pair filter explicitly. Fully periodic 3D cells use bulk…
```

## Periodic interfaces

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_rotate_to_commensurate`
  - Finds the nearest validated periodic 2D lattice match, rotates the selected layer to that exact angle, and opens the common-cell proposal. The default is cells-only; showAtoms=true adds the opaque core and muted one-primitive-cell…
* - `vase_load_commensurate_guest`
  - Loads a separate guest structure from inside the GUI launch directory. gap is guest minimum z minus host maximum z in angstrom and defaults to 3. Absolute paths and parent-directory traversal are rejected.
* - `vase_remove_commensurate_guest`
  - Removes the separately loaded guest and clears its search/proposal, returning the workspace to same-lattice matching.
* - `vase_calculate_commensurate`
  - Searches bounded integer common cells about global Z. Same-lattice mode requires a selected rotating layer before atom preview or materialization; host-guest mode requires a loaded guest. Cells-only preview is the default.…
* - `vase_apply_commensurate_cell`
  - Materializes the active validated proposal as the ASE unit cell. Prerequisites: active-commensurate-proposal.
* - `vase_dismiss_commensurate_cell`
  - Closes the active proposal and restores the pre-preview camera.
* - `vase_calculate_registry_map`
  - Scans one primitive periodic translation cell in the requested (hkl) plane. metric is short-contact or bond-strain; both are geometry scores, not energies. Prerequisites: selection-or-indices.
* - `vase_start_registry_relaxation`
  - Activates rigid translation for a selected component. space=plane (default) uses two coordinates in the periodic (hkl) plane; space=cartesian uses one common x/y/z translation in Angstrom with maxDisplacement as the bound for each…
* - `vase_set_registry_translation`
  - Sets two unwrapped plane-lattice coefficients in plane mode or three Cartesian Angstrom components in 3D mode, without moving the cell or changing selected internal coordinates. Prerequisites: active-registry-relaxation.
* - `vase_run_registry_relaxation`
  - Optimizes the active two-coordinate plane or three-coordinate Cartesian rigid translation with the attached calculator or the default pairwise repulsion calculator. Consume registry_relax_step events until is_relaxing is false.…
* - `vase_stop_registry_relaxation`
  - Prerequisites: active-registry-relaxation.
* - `vase_finish_registry_relaxation`
  - Commits the rigid translation as one undoable structure edit and exits the mode. Prerequisites: inactive-registry-relaxation.
* - `vase_cancel_registry_relaxation`
  - Restores the exact pre-mode coordinates and exits without a history entry. Prerequisites: active-registry-relaxation.
```

## Volumetric fields

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_load_volumetric`
  - path is resolved inside the GUI launch directory. Supported formats include CHGCAR, LOCPOT, PARCHG, ELFCAR, Cube, and XSF. precision is fp32/float32 or fp64/float64 and is applied while reading.
* - `vase_show_volumetric`
  - surfaceMode is single or signed; stepSize is 1, 2, or 4. Signed mode renders +abs(level) and -abs(level), requires a non-zero level, and may return only the sign that still crosses the displayed field range after smearing. opacity is…
* - `vase_add_volumetric_plane`
  - Creates one cell-clipped scalar-field plane. hkl is a non-zero three-number reciprocal-space normal; offsetAngstrom is the signed distance from the origin along its Cartesian unit normal. If the offset is omitted, the plane is…
* - `vase_update_volumetric_planes`
  - Applies every supplied field to all planeIds as one visual edit. resolution is 128, 256, 512, or 1024. vmin/vmax are used when autoRange is false. Invalid IDs or values reject the whole edit.
* - `vase_remove_volumetric_planes`
  - Removes all requested planar sections as one visual edit.
* - `vase_combine_volumetric`
  - All grids must have matching dimensions, cell, origin, PBC, and units and endpoint conventions. resultName names the output; name is reserved for the operation. Accumulation uses float64 slabs; output precision defaults to the highest…
* - `vase_remove_volumetric`
  - Deletes the specified scalar dataset from the document and clears the active surface when it used that dataset. Source files are unchanged.
```

## Render and export

```{list-table}
:header-rows: 1
:widths: 45 55

* - Tool
  - Purpose
* - `vase_render`
  - Render the shared GUI to a unique local artifact. Returns a resource URI and exact camera/dimensions, never inline Base64. Inspect the image for final visual quality.
* - `vase_export_image`
  - Export image from the shared GUI to a unique local artifact. imageFormat is png, jpeg, webp, or pdf.
* - `vase_export_video`
  - Export video from the shared GUI to a unique local artifact. container is mov or avi and requires a loaded trajectory. Indexed PNG frames preserve every source/interpolated frame without wall-clock sampling. Native dimensions must be…
* - `vase_export_poscar`
  - Export poscar from the shared GUI to a unique local artifact. ASE rejects Cartesian directional constraints that cannot be represented as POSCAR selective dynamics for the current cell. Constraints are never silently removed; use…
* - `vase_export_pickle`
  - Export pickle from the shared GUI to a unique local artifact.
* - `vase_export_blender`
  - Export blender from the shared GUI to a unique local artifact.
* - `vase_export_3dm`
  - Export 3dm from the shared GUI to a unique local artifact. Requires the optional rhino3dm dependency.
* - `vase_export_obj`
  - Export obj from the shared GUI to a unique local artifact.
* - `vase_export_html`
  - Export html from the shared GUI to a unique local artifact. embedProject defaults to false for a lightweight view-only file. HTML dimensions are integers in 256..8192 and the rendered background is opaque.
* - `vase_export_project`
  - Export project from the shared GUI to a unique local artifact.
* - `vase_export_settings`
  - Export settings from the shared GUI to a unique local artifact.
* - `vase_export_rdf_csv`
  - Export rdf-csv from the shared GUI to a unique local artifact. Exports the total RDF and currently requested partial curves. pairMode accepts active, selected, all, or none; selected requires the browser-derived selected active label…
* - `vase_export_commensurate_csv`
  - Export commensurate-csv from the shared GUI to a unique local artifact. Exports angle, host/guest integer matrices, area ratios, residual strains, and the scientific references used by the bounded search.
* - `vase_export_registry_csv`
  - Export registry-csv from the shared GUI to a unique local artifact. Exports the complete periodic (hkl) translation grid, its exact lattice basis, Cartesian vectors, and geometry metric values.
```
