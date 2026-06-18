from pathlib import Path
import asyncio
import tomllib

from ase.build import molecule
from fastapi import HTTPException
import pytest

from v_ase.server import (
    apply_positions,
    delete_atoms,
    get_atoms,
    reset,
    session_atoms_to_json,
    trajectory_position_array,
    undo,
    update_calculator,
    update_constraints,
    update_atom_types,
    value_error_handler,
)
import v_ase.server as server_module
from v_ase.export import export_blender_response, export_pickle_response, export_poscar_response
from v_ase.session import EditorSession, sessions


ROOT = Path(__file__).resolve().parents[1]


def test_static_version_strings_match_package_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    index_html = (ROOT / "v_ase/static/index.html").read_text(encoding="utf-8")

    assert f'style.css?v={version}' in index_html
    assert f'three.module.js?v={version}' in index_html
    assert f'main.js?v={version}' in index_html
    assert f'<span class="version">{version}</span>' in index_html
    assert "0.0.28" not in index_html


def test_ui_button_api_endpoints_respond_without_network_server():
    atoms = molecule("H2O")
    session = EditorSession("ui-api-test", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session

    positions = atoms.positions.tolist()
    assert asyncio.run(get_atoms(session.session_id))["metadata"]["natoms"] == 3
    assert asyncio.run(get_atoms(session.session_id))["metadata"]["calculator"] == "Repulsion"
    assert asyncio.run(apply_positions(session.session_id, {"positions": positions}))["metadata"]["natoms"] == 3
    assert asyncio.run(delete_atoms(session.session_id, {"indices": [2]}))["metadata"]["natoms"] == 2
    assert asyncio.run(undo(session.session_id))["metadata"]["natoms"] == 3
    renamed = asyncio.run(update_atom_types(session.session_id, {"indices": [0], "label": "O_surface"}))
    assert renamed["symbols"][0] == "O_surface"
    assert renamed["chemical_symbols"][0] == "O"
    unknown = asyncio.run(update_atom_types(session.session_id, {"indices": [0], "label": "surface_site"}))
    assert unknown["symbols"][0] == "surface_site"
    assert unknown["chemical_symbols"][0] == "O"
    typed = asyncio.run(update_atom_types(session.session_id, {"indices": [1], "label": "Si", "base_symbol": "Si"}))
    assert typed["symbols"][1] == "Si"
    assert typed["chemical_symbols"][1] == "Si"
    numeric = asyncio.run(update_atom_types(session.session_id, {"indices": [1], "label": "2"}))
    assert numeric["symbols"][1] == "2"
    assert numeric["chemical_symbols"][1] == "Si"
    constrained = asyncio.run(update_constraints(session.session_id, {
        "indices": [1, 2],
        "fix_atoms": True,
        "directional_kind": "fixed_plane",
        "vector": [0, 0, 1],
    }))
    assert sorted(constrained["constraints"]["fixed_indices"]) == [1, 2]
    assert constrained["constraints"]["fixed_plane"]["1"] == [0.0, 0.0, 1.0]
    assert constrained["constraints"]["fixed_plane"]["2"] == [0.0, 0.0, 1.0]
    assert asyncio.run(reset(session.session_id))["metadata"]["natoms"] == 3
    assert export_poscar_response(session, {"positions": positions}).filename == "POSCAR"
    assert export_pickle_response(session, {
        "positions": positions,
        "include_calculator": False,
    }).filename == "atoms.pkl"


def test_viz_only_session_blocks_atom_editing_api_calls():
    atoms = molecule("H2O")
    session = EditorSession("viz-only-api-test", atoms.copy(), atoms.copy(), config={"viz_only": True})
    sessions[session.session_id] = session

    assert session.working_atoms.calc is None
    assert asyncio.run(get_atoms(session.session_id))["metadata"]["calculator"] is None

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(apply_positions(session.session_id, {"positions": atoms.positions.tolist()}))

    assert excinfo.value.status_code == 403
    assert "default visualization mode" in excinfo.value.detail
    assert "--interactive" in excinfo.value.detail

    with pytest.raises(HTTPException) as calc_excinfo:
        asyncio.run(update_calculator(session.session_id, {"device": "cpu"}))

    assert calc_excinfo.value.status_code == 403


def test_missing_session_is_reported_as_404_json():
    response = asyncio.run(value_error_handler(None, ValueError("Session missing-session not found")))

    assert response.status_code == 404
    assert response.body == b'{"detail":"Session missing-session not found"}'


def test_trajectory_position_cache_is_only_sent_for_same_topology_frames():
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.25, 0.0, 0.0]
    session = EditorSession(
        "trajectory-cache",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )

    data = session_atoms_to_json(session)

    assert data["metadata"]["trajectory_positions_cached"] is True
    assert len(data["trajectory_positions"]) == 2
    assert data["trajectory_positions"][1][0][0] == first.positions[0, 0] + 0.25

    different_topology = molecule("CO")
    session.trajectory_frames[1] = different_topology
    data = session_atoms_to_json(session)

    assert data["metadata"]["trajectory_positions_cached"] is False
    assert "trajectory_positions" not in data


def test_large_trajectory_uses_binary_position_cache_metadata(monkeypatch):
    monkeypatch.setattr(server_module, "MAX_INLINE_TRAJECTORY_CACHE_VALUES", 9)
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.25, 0.0, 0.0]
    session = EditorSession(
        "trajectory-binary-cache",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )

    data = session_atoms_to_json(session)
    array = trajectory_position_array(session)

    assert data["metadata"]["trajectory_positions_cached"] is False
    assert data["metadata"]["trajectory_positions_binary"] is True
    assert "trajectory_positions" not in data
    assert array.shape == (2, len(first), 3)
    assert array.dtype.name == "float32"

    session.trajectory_frames[1] = second.copy()
    session.trajectory_frames[1].set_cell([5, 5, 6])
    data = session_atoms_to_json(session)

    assert data["metadata"]["trajectory_positions_cached"] is False
    assert "trajectory_positions" not in data


def test_frontend_uses_physical_keys_for_layout_independent_shortcuts():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    for code in ["KeyA", "KeyC", "KeyG", "KeyR", "KeyV", "KeyX", "KeyY", "KeyZ"]:
        assert code in main_js
    assert "isPhysicalKey" in main_js
    assert "e.key === 'g'" not in main_js
    assert "e.key === 'r'" not in main_js


def test_image_export_is_option_modal_with_transparency_and_grid_controls():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert "showExportImageModal" in main_js
    assert "export-transparent" in main_js
    assert "export-grid" in main_js
    assert "export-axes" in main_js
    assert "this.renderer.exportPNG(exportWidth, exportHeight" in main_js
    assert "modalContainer?.addEventListener('pointerdown'" in main_js
    assert "e.stopPropagation()" in main_js
    assert "transparentBackground" in renderer_js
    assert "includeAxes" in renderer_js
    assert "this.scene.background = null" in renderer_js
    assert "this.gridGroup.visible = includeGrid" in renderer_js
    assert "alpha: true" in renderer_js


def test_viewer_uses_packaged_three_and_initial_camera_fit():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert "https://unpkg.com" not in index_html
    assert "three.module.js" in index_html
    assert (ROOT / "v_ase/static/vendor/three.module.js").exists()
    assert (ROOT / "v_ase/static/vendor/THREE_LICENSE").exists()
    assert "needsInitialCameraFit" in renderer_js
    assert "fitCameraToStructure" in renderer_js
    assert "structureBounds" in renderer_js
    assert "OrthographicCamera" in renderer_js
    assert "setProjectionMode" in renderer_js
    assert "updateCameraProjection" in renderer_js
    assert "this.camera = this.orthographicCamera" in renderer_js
    assert "projectionMode = 'orthographic'" in renderer_js
    assert "this.cameraFillLight = new THREE.PointLight" in renderer_js
    assert "this.cameraFillDirectionalLight = new THREE.DirectionalLight" in renderer_js
    assert "this.cameraFillDirectionalLight.position.copy(this.camera.position)" in renderer_js
    assert "new THREE.AmbientLight(0xffffff, 0.68)" in renderer_js
    assert "updateViewLighting()" in renderer_js


def test_frontend_handles_missing_calculator_forces_without_aborting_refresh():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "validForces" in main_js
    assert "Array.isArray(f)" in main_js
    assert "f.slice(0, 3).every" in main_js
    assert "this.state.atoms.forces.map(f => Math.sqrt(f[0]" not in main_js


def test_rotate_preview_uses_stable_view_axis_and_rejects_nonfinite_positions():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "camera.getWorldDirection(viewAxis).normalize()" in main_js
    assert "if (!Number.isFinite(angle)) angle = 0" in main_js
    assert "orig.some(v => !Number.isFinite(v))" in main_js
    assert "every(Number.isFinite)" in main_js
    assert "rotatedTarget.sub(origVec)" in main_js
    assert "this.constrainedMoveDelta(idx, rotatedTarget.sub(origVec))" in main_js
    assert "this.transform.mode === 'MOVE'" in main_js
    assert "this.api.getConstrainedPositions" in main_js
    assert "this.transform.rotationAngle -= delta" in main_js
    assert "snapRotationAngle" in main_js
    assert "snapMoveDelta" in main_js


def test_selection_marquee_transform_increment_and_view_axis_shortcuts_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert 'id="marquee"' in index_html
    assert "showMarquee(left, top, width, height)" in main_js
    assert "marquee.classList.remove('hidden')" in main_js
    assert "marquee.classList.add('hidden')" in main_js
    assert "#marquee" in style_css
    assert "position: fixed;" in style_css
    assert 'id="move-increment"' in index_html
    assert 'id="rotate-increment"' in index_html
    assert 'type="number" id="move-increment"' in index_html
    assert 'type="number" id="rotate-increment"' in index_html
    assert "readTransformSettings" in main_js
    assert "state.transformReadout" in main_js
    assert "formatMoveReadout" in main_js
    assert "formatRotateReadout" in main_js
    assert "alignViewToAxis" in main_js
    assert "axisFromKey" in main_js
    assert "Align view in select mode" in index_html
    assert "Lock transform axis in G/R mode" in index_html


def test_frontend_renders_constraint_guides_and_blender_export_button():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    selection_js = (ROOT / "v_ase/static/selection.js").read_text()

    assert "constrainedMoveDelta" in main_js
    assert "fixed_line" in main_js
    assert "fixed_plane" in main_js
    assert "chk-constraints" in index_html
    assert "chk-overlays" in index_html
    assert "Show Overlays" in index_html
    assert "Apply constraints" in index_html
    assert "apply_constraint</label>" not in index_html
    assert "btn-done" not in index_html
    assert "btn-cancel" not in index_html
    assert 'id="btn-apply"' not in index_html
    assert "apply_constraint" in main_js
    assert "state.applyConstraints" in main_js
    assert "showOverlays" in main_js
    assert "applySupercell" in api_js
    assert "btn-set-supercell" in index_html
    assert "Set Supercell as Cell" in index_html
    assert "btn-wrap" in index_html
    assert "Wrap Atoms Into Cell" in index_html
    assert "btn-delete-selection" in index_html
    assert "calc-device" in index_html
    assert "calc-cpus" in index_html
    assert "constraint-kind" in index_html
    assert "constraint-fixatoms" in index_html
    assert "btn-apply-constraint" in index_html
    assert "updateConstraints" in api_js
    assert "selectedFixAtomsState" in main_js
    assert "applySelectedDirectionalConstraint" in main_js
    assert "hover-readout" in index_html
    assert "move-increment" in index_html
    assert "rotate-increment" in index_html
    assert "sphere-quality" in index_html
    assert "chk-antialias" in index_html
    assert "element-bond-list" in index_html
    assert "Element cutoffs" in index_html
    assert "deleteSelection" in main_js
    assert "api.deleteAtoms" in main_js
    assert "updateCalculatorConfig" in api_js
    assert "currentCalculatorPayload" in main_js
    assert "e.code === 'Delete'" in main_js
    assert "renderElementBondControls" in main_js
    assert "parseElementBondCutoffs" in main_js
    assert "atomHoverText" in main_js
    assert "setHoveredAtom" in main_js
    assert "elementCovalentRadius" in main_js
    assert "rebuildConstraintGuides" in renderer_js
    assert "applyOverlayVisibility" in renderer_js
    assert "atomMaterialSpec" in renderer_js
    assert "fixedAdjustedColor" in renderer_js
    assert "lineFade" in renderer_js
    assert "planeSoft" in renderer_js
    assert "rebuildPersistentConstraintMarks" not in renderer_js
    assert "addFixedAtomHatch" not in renderer_js
    assert "addFixedPlaneMark" not in renderer_js
    assert "fixedHatch" not in renderer_js
    assert "planeGrid" not in renderer_js
    assert "planeVeil" not in renderer_js
    assert "planeTrail" not in renderer_js
    assert "lockMarker" not in renderer_js
    assert "lockMarker" not in selection_js
    assert "ConeGeometry" not in renderer_js
    assert "constraintMarkGroup" in renderer_js
    assert "addFixedLineGuide" in renderer_js
    assert "addFixedPlaneGuide" in renderer_js
    assert "rebuildHookeanConstraints" in renderer_js
    assert "makeSpringPoints" in renderer_js
    assert "makeFlatSpringPoints" in renderer_js
    assert "hookeanState" in renderer_js
    assert "hookeanDistance" in renderer_js
    assert "hookeanThreshold" in renderer_js
    assert "hookeanExtension" in renderer_js
    assert "thresholdY" in renderer_js
    assert "hookeanInactive" in renderer_js
    assert "hookeanGuide" in renderer_js
    assert "gapLine" in renderer_js
    assert "lockPin" in renderer_js
    assert "addSupercellCellPreview" in renderer_js
    assert "sphereQualitySegments" in renderer_js
    assert "elementBondCutoff" in renderer_js
    assert "springLine.visible = state !== 'inactive'" in renderer_js
    assert "hookeanBondExclusions" in renderer_js
    assert "minimumImageDelta" in renderer_js
    assert "cartToFrac" in renderer_js
    assert "atomVisualRadius" in renderer_js
    assert "atomVisualColor" in renderer_js
    assert "exportBlender" in api_js
    assert "btn-export-blender" in index_html
    assert "selected-measure" in index_html
    assert "getSelectionMeasureText" in main_js
    assert "selectionAngle" in main_js
    assert "currentCameraForExport" in main_js
    assert "camera) body.camera = camera" in api_js
    assert "display) body.display = display" in api_js
    assert "bondPairs) body.bond_pairs = bondPairs" in api_js
    assert "threshold: 4.80" in api_js


def test_frontend_has_radius_controls_loading_overlay_and_modern_panel_styles():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "busy-overlay" in index_html
    assert "withBusy" in main_js
    assert "Applying ${reps.join(' x ')} supercell" in main_js
    assert "Wrapping ${frameCount} frame" in main_js
    assert "atom-radius-scale" in index_html
    assert "element-radius-list" in index_html
    assert "renderElementRadiusControls" in main_js
    assert "return this.reconcileTypeOrder(this.state.atoms?.symbols || []);" in main_js
    assert "previewDetectedBase" in main_js
    assert "typeSelect.value = inferredBase" in main_js
    assert "nameInput.value = typeSelect.value" in main_js
    assert "nameInput.addEventListener('change', () => commitRename())" in main_js
    assert "nameInput.addEventListener('change', commitRename)" not in main_js
    assert "detectedElementForLabel" in main_js
    assert "setElementBaseDefaults" in main_js
    assert "appearance: preserveAppearance" in main_js
    assert "element_radii" in main_js
    assert "element_colors" in main_js
    assert "parseElementRadii" in main_js
    assert "parseElementVisibility" in main_js
    assert "element-color-input" in main_js
    assert "element-visible-checkbox" in main_js
    assert "element-select-checkbox" in main_js
    assert "indeterminate" in main_js
    assert "renameElementType" in main_js
    assert "renameElementTypeForVisualization" in main_js
    assert "nameInput.disabled = this.state.vizOnly" not in main_js
    assert "canViewportSelectAtoms()" in main_js
    assert "this.canViewportSelectAtoms() && this.transform.mode === 'IDLE'" in main_js
    assert "this.renderer.renameAtomType(oldSymbol, label, indices, this.state.display, base)" in main_js
    assert "applySelectedTypeForVisualization" in main_js
    assert "selectElement(symbol)" in main_js
    assert "toggleElementSelection" in main_js
    assert "elementVisible" in renderer_js
    assert "atomTypeVisible" in renderer_js
    assert "renameAtomType(oldSymbol, label, indices = [], displayOptions = null, baseSymbol = null)" in renderer_js
    assert "refreshAtomAppearance(indices)" in renderer_js
    assert "rebuildInstancedAtoms" in renderer_js
    assert "inferBondPairsCellList" in renderer_js
    assert "0.6 * (vi + vj)" in renderer_js
    assert "fixedAtomDisplayEnabled()" in renderer_js
    assert "return this.displayOptions.showOverlays !== false" in renderer_js
    assert "fixedAtomSegments(segmentCount)" in renderer_js
    assert "flatShading: true" in renderer_js
    assert "v-ase-fixed-micro-etched-faceted-v2" in renderer_js
    assert "const supercellChanged" in renderer_js
    assert "if (supercellChanged) this.rebuildSupercell()" in renderer_js
    assert "elementVisible: { ...(options.elementVisible" in renderer_js
    assert "mesh.visible === false" in (ROOT / "v_ase/static/selection.js").read_text()
    assert "btn-apply-selected-type" not in index_html
    assert "selection-textbox" in index_html
    assert "data-copy-target=\"selected-indices\"" in index_html
    assert "Center (unwrapped)" in index_html
    assert "orientation-widget" in index_html
    assert "Repulsion Calc" in index_html
    assert "Repulsion calculator settings only" in index_html
    assert 'id="calc-controls" class="calc-control-group" title="Repulsion calculator settings only" data-edit-only' in index_html
    assert "updateAtomTypes" in (ROOT / "v_ase/static/api.js").read_text()
    assert 'id="projection-mode"' in index_html
    assert '<option value="orthographic" selected>Orthographic</option>' in index_html
    assert 'id="inspector-resizer"' in index_html
    assert 'data-edit-only' in index_html
    assert "--interactive" in (ROOT / "v_ase/cli.py").read_text()
    assert "updateEditingAvailability" in main_js
    assert "wrapVisibleAtomsIntoCell" in main_js
    assert "updateOrientationWidget" in main_js
    assert "setupInspectorResizer" in main_js
    assert "atomRadiusScale" in renderer_js
    assert "elementRadii" in renderer_js
    assert "elementColors" in renderer_js
    assert "const materialKey = `supercell:viz:${geometryKey}:${color}`" in renderer_js
    assert "color: group.color" in renderer_js
    assert "previous.atomRadiusScale" in renderer_js
    assert "reconcileTypeOrder" in main_js
    assert "replaceTypeOrder(oldSymbol, label)" in main_js
    assert "#inspector .panel-section" in style_css
    assert ".element-radius-panel" in style_css
    assert "overflow-x: auto" in style_css
    assert ".element-check:indeterminate" in style_css
    assert ".element-appearance-row" in style_css
    assert "--inspector-width" in style_css
    assert "body.inspector-wide #inspector .element-appearance-row" in style_css
    assert 'body[data-viz-only="true"] [data-edit-only]' in style_css
    assert ".busy-spinner" in style_css
    assert ".orientation-widget" in style_css
    assert ".calc-control-title" in style_css


def test_frontend_reset_video_and_visual_settings_controls_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "btn-reset-coords" in index_html
    assert "confirmFullReset" in main_js
    assert "confirmCoordinateReset" in main_js
    assert "resetCoordinates" in api_js
    assert "Resetting coordinates and original unit cell" in main_js
    assert "Visual settings were kept" in main_js
    assert "btn-export-video" in index_html
    assert '<section class="panel-section export-section"' in index_html
    assert '<section class="panel-section utility-section"' in index_html
    assert "Scientific Tools" not in index_html
    assert "Relaxation" in index_html
    assert "Export Video is available for trajectory files only" in main_js
    assert "exportTrajectoryVideo" in main_js
    assert "canvas.captureStream" in main_js
    assert "MediaRecorder" in main_js
    assert "btn-save-settings" in index_html
    assert "btn-load-settings" in index_html
    assert "settings-file" in index_html
    assert "saveVisualSettings" in api_js
    assert "loadVisualSettings" in api_js
    assert "v_ase_visual_settings.pkl" in main_js
    assert ".confirm-list" in style_css
    assert "#inspector .btn-block:disabled" in style_css


def test_trajectory_controls_update_live_and_space_toggles_playback():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "queueFrameLoad" in main_js
    assert "flushFrameLoadQueue" in main_js
    assert '<div id="trajectory-panel" class="trajectory-strip"' in index_html
    assert 'frame-label">1 / 1' in index_html
    assert "panel.classList.remove('hidden')" in main_js
    assert "slider.disabled = count <= 1" in main_js
    assert "frame-slider').oninput" in main_js
    assert "movie-fps').oninput" in main_js
    assert 'label for="movie-skip">Skip' in index_html
    assert "movie-skip" in main_js
    assert "restartPlayback" in main_js
    assert "currentPlaybackFps" in main_js
    assert "currentPlaybackSkip" in main_js
    assert "currentPlaybackStep" in main_js
    assert "this.stepFrame(this.currentPlaybackStep())" in main_js
    assert "setTimeout(tick, 1000 / this.currentPlaybackFps())" in main_js
    assert "e.code === 'Space'" in main_js
    assert "Play or pause trajectory" in main_js
    assert "setupNumberSteppers" in main_js
    assert "bindNumberStepperButton" in main_js
    assert "pointerInsideButton" in main_js
    assert "button.addEventListener('pointerleave', stop)" in main_js
    assert "window.addEventListener('blur', stop, true)" in main_js
    assert "number-stepper-up" in main_js
    assert "input[type=\"number\"]::-webkit-inner-spin-button" in style_css
    assert ".trajectory-strip .number-stepper-btn" in style_css
    assert ".trajectory-strip" in style_css
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    assert "refreshBondsForCurrentPositions" in renderer_js
    assert "const nextPairs = this.inferBondPairs()" in renderer_js
    assert "this.refreshBondsForCurrentPositions()" in renderer_js


def test_export_downloads_use_save_picker_and_fallback_anchor():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "saveBlobFromAction" in main_js
    assert "showSaveFilePicker" in main_js
    assert "document.body.appendChild(a)" in main_js
    assert "Preparing POSCAR export" in main_js
    assert "Preparing Pickle export" in main_js
    assert "Preparing Blender export" in main_js


def test_blender_export_includes_bonds_unit_cell_smooth_atoms_and_camera_projection():
    atoms = molecule("H2")
    atoms.set_cell([6, 6, 6])
    atoms.set_pbc([True, True, True])
    session = EditorSession("blender-export-regression", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session

    response = export_blender_response(session, {
        "positions": atoms.positions.tolist(),
        "display": {
            "showBonds": True,
            "bondMode": "manual",
            "manualBondPairs": [[0, 1]],
        },
        "bond_pairs": [[0, 1]],
        "camera": {
            "position": [5, -6, 4],
            "target": [0, 0, 0],
            "projection": "orthographic",
            "ortho_scale": 8,
        },
    })
    script = Path(response.path).read_text(encoding="utf-8")

    assert "BONDS = DATA.get(\"bonds\", [])" in script
    assert "MAT_BOND" in script
    assert "add_unit_cell(CELL)" in script
    assert "ATOM_MESHES" in script
    assert "bpy.data.objects.new" in script
    assert "polygon.use_smooth = True" in script
    assert "obj.data.type = \"ORTHO\"" in script
    assert "bond_{bond.get('i', 0)}" in script


def test_control_panel_uses_collapsible_default_hierarchy():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert '<details class="panel-section" open data-panel="structure-info">' in index_html
    assert '<details class="panel-section" open data-panel="selection">' in index_html
    assert '<details class="panel-section" open data-panel="view">' in index_html
    assert '<details class="panel-section" data-panel="transform" data-edit-only>' in index_html
    assert '<details class="panel-section" data-panel="appearance">' in index_html
    assert '<details class="panel-section" data-panel="cell-transform" data-edit-only>' in index_html
    assert '<details class="panel-section" data-panel="scientific-tools">' in index_html
    assert "details:not([open]) > summary.section-header" in style_css
    assert "summary.section-header::after" in style_css


def test_grid_guides_scale_to_large_unit_cells():
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert "desiredGuideSize" in renderer_js
    assert "replaceViewportGuides" in renderer_js
    assert "refreshViewportGuidesForStructure" in renderer_js
    assert "new THREE.GridHelper(guideSize, divisions" in renderer_js
    assert "[0, 0, -half], [0, 0, half]" in renderer_js


def test_rotate_pivot_and_unit_cell_aware_validation_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()
    docs = (ROOT / "docs/unit_cell_aware_rotate.md").read_text()

    assert "rotate-pivot" in index_html
    assert "Global origin" in index_html
    assert "Unit-cell center" in index_html
    assert "chk-unit-aware-rotate" in index_html
    assert "Bond-strain guard" in index_html
    assert "rotate-strain-cutoff" in index_html
    assert "make-supercell-matrix" in index_html
    assert "Apply make_supercell Matrix" in index_html
    assert "applyMakeSupercellMatrix" in main_js
    assert "parseSupercellMatrix" in main_js
    assert "applySupercellMatrix" in (ROOT / "v_ase/static/api.js").read_text()
    assert "rotationPivotPosition" in main_js
    assert "prepareRotationValidation" in main_js
    assert "validateRotationStrain" in main_js
    assert "minimumImageDeltaFromPositions" in main_js
    assert "Rotate blocked:" in main_js
    assert "data-rotate-invalid" in style_css
    assert "strainViolationGroup" in renderer_js
    assert "setStrainViolations" in renderer_js
    assert "clearStrainViolations" in renderer_js
    assert "H' = P H" in docs
    assert "ase.build.make_supercell" in docs
    assert "Minimum Image Convention" in docs
    assert "epsilon_ij" in docs
    assert "10.1080/08927028908031386" in docs
    assert "10.3390/solids7010005" in docs
