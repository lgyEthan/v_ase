from pathlib import Path
import ast
import asyncio
import re
import tomllib
from urllib.parse import quote

from ase import Atoms
from ase.build import molecule
from fastapi import HTTPException
import numpy as np
import pytest

from v_ase.server import (
    add_atoms,
    apply_positions,
    delete_atoms,
    get_atoms,
    reset,
    session_atoms_to_json,
    trajectory_identity_compatible,
    trajectory_position_array,
    undo,
    update_calculator,
    update_constraints,
    update_atom_identity,
    update_session_mode,
    value_error_handler,
)
import v_ase.server as server_module
from v_ase.export import (
    _display_bonds,
    export_blender_response,
    export_obj_response,
    export_pickle_response,
    export_poscar_response,
)
from v_ase.io import set_atom_labels
from v_ase.session import EditorSession, sessions


ROOT = Path(__file__).resolve().parents[1]


def test_static_version_strings_match_package_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    url_version = quote(version, safe=".")
    index_html = (ROOT / "v_ase/static/index.html").read_text(encoding="utf-8")

    assert f'style.css?v={url_version}' in index_html
    assert f'three.module.js?v={url_version}' in index_html
    assert f'main.js?v={url_version}' in index_html
    assert f'<span class="version">{version}</span>' in index_html
    assert "0.0.28" not in index_html


def test_theme_and_personal_default_controls_are_wired_end_to_end():
    index_html = (ROOT / "v_ase/static/index.html").read_text(encoding="utf-8")
    workspace_html = (ROOT / "v_ase/static/workspace.html").read_text(encoding="utf-8")
    main_js = (ROOT / "v_ase/static/main.js").read_text(encoding="utf-8")
    workspace_js = (ROOT / "v_ase/static/workspace.js").read_text(encoding="utf-8")
    style_css = (ROOT / "v_ase/static/style.css").read_text(encoding="utf-8")
    api_js = (ROOT / "v_ase/static/api.js").read_text(encoding="utf-8")

    assert 'id="ui-theme"' in index_html
    assert '<option value="system" selected>System</option>' in index_html
    assert 'id="btn-set-visual-default"' in index_html
    assert 'id="btn-restore-visual-default"' in index_html
    assert 'id="visual-default-status"' in index_html
    assert "prefers-color-scheme: dark" in index_html
    assert "prefers-color-scheme: dark" in workspace_html
    assert 'html[data-ui-theme="light"]' in style_css
    assert "setupThemeControls()" in main_js
    assert "loadUserVisualDefaults()" in main_js
    assert "includeCamera: false" in main_js
    assert "Saved personal visualization defaults will be deleted." in main_js
    assert "v_ase:document-theme" in main_js
    assert "v_ase:workspace-theme" in workspace_js
    assert "fetchUserVisualDefaults" in api_js
    assert "/api/preferences/visual-defaults/{session_id}" in api_js
    assert "'preferences', 'collaboration'" in main_js
    assert "'set-interface-theme', 'set-personal-visual-default'" in main_js
    assert "restore-app-visual-defaults permanently deletes" in main_js


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
    renamed = asyncio.run(update_atom_identity(session.session_id, {"indices": [0], "label": "O_surface"}))
    assert renamed["symbols"][0] == "O_surface"
    assert renamed["chemical_symbols"][0] == "O"
    unknown = asyncio.run(update_atom_identity(session.session_id, {"indices": [0], "label": "surface_site"}))
    assert unknown["symbols"][0] == "surface_site"
    assert unknown["chemical_symbols"][0] == "O"
    typed = asyncio.run(update_atom_identity(session.session_id, {"indices": [1], "label": "Si", "base_symbol": "Si"}))
    assert typed["symbols"][1] == "Si"
    assert typed["chemical_symbols"][1] == "Si"
    numeric = asyncio.run(update_atom_identity(session.session_id, {"indices": [1], "label": "2"}))
    assert numeric["symbols"][1] == "2"
    assert numeric["chemical_symbols"][1] == "Si"
    duplicate = asyncio.run(update_atom_identity(session.session_id, {"indices": [2], "label": "surface_site", "base_symbol": "H"}))
    assert duplicate["symbols"][0] == duplicate["symbols"][2] == "surface_site"
    assert duplicate["chemical_symbols"][2] == "H"
    added = asyncio.run(add_atoms(session.session_id, {
        "symbol": "adsorbate_site",
        "base_symbol": "O",
        "position": [1.5, 1.5, 1.5],
    }))
    assert added["symbols"][-1] == "adsorbate_site"
    assert added["chemical_symbols"][-1] == "O"
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
    obj_response = export_obj_response(session, {
        "positions": positions,
        "display": {"showBonds": True, "showCell": False},
        "bond_pairs": [[0, 1], [0, 2]],
    })
    try:
        assert obj_response.filename == "v_ase_obj_scene.zip"
    finally:
        Path(obj_response.path).unlink(missing_ok=True)


def test_viz_only_session_blocks_atom_editing_api_calls():
    atoms = molecule("H2O")
    session = EditorSession("viz-only-api-test", atoms.copy(), atoms.copy(), config={"viz_only": True})
    sessions[session.session_id] = session

    assert session.working_atoms.calc is None
    assert asyncio.run(get_atoms(session.session_id))["metadata"]["calculator"] is None

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(apply_positions(session.session_id, {"positions": atoms.positions.tolist()}))

    assert excinfo.value.status_code == 403
    assert "View mode" in excinfo.value.detail
    assert "top-bar mode to Edit" in excinfo.value.detail

    with pytest.raises(HTTPException) as calc_excinfo:
        asyncio.run(update_calculator(session.session_id, {"device": "cpu"}))

    assert calc_excinfo.value.status_code == 403


def test_runtime_mode_switch_preserves_exact_identity_positions_and_editability():
    atoms = molecule("H2O")
    session = EditorSession(
        "runtime-mode-test",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": True},
    )
    sessions[session.session_id] = session
    positions = (atoms.positions + [0.25, -0.1, 0.2]).tolist()

    edited = asyncio.run(update_session_mode(session.session_id, {
        "viz_only": False,
        "labels": ["O_site", "H_site", "H_site"],
        "chemical_symbols": ["O", "H", "H"],
        "positions": positions,
    }))

    assert session.config["viz_only"] is False
    assert edited["symbols"] == ["O_site", "H_site", "H_site"]
    assert np.allclose(edited["positions"], positions)
    assert edited["metadata"]["has_calculator"] is True
    assert asyncio.run(apply_positions(session.session_id, {"positions": positions}))["metadata"]["natoms"] == 3

    viewed = asyncio.run(update_session_mode(session.session_id, {
        "viz_only": True,
        "labels": ["O_site", "H_site", "H_site"],
        "chemical_symbols": ["O", "H", "H"],
        "positions": positions,
    }))
    assert session.config["viz_only"] is True
    assert viewed["symbols"] == ["O_site", "H_site", "H_site"]
    with pytest.raises(HTTPException):
        asyncio.run(apply_positions(session.session_id, {"positions": positions}))


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
    session.invalidate_trajectory_layout()
    data = session_atoms_to_json(session)

    assert data["metadata"]["trajectory_positions_cached"] is False
    assert "trajectory_positions" not in data


def test_trajectory_view_identity_scope_requires_stable_count_and_element_sequence():
    first = molecule("H2O")
    second = molecule("H2O")
    set_atom_labels(second, ["O_next", "H_next", "H_next"])
    session = EditorSession(
        "trajectory-view-identity",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        config={"viz_only": True},
    )

    assert trajectory_identity_compatible(session) is True
    assert session_atoms_to_json(session)["metadata"]["trajectory_identity_compatible"] is True

    reordered = Atoms("HHO", positions=second.positions.copy())
    session.trajectory_frames[1] = reordered
    session.invalidate_trajectory_layout()
    assert trajectory_identity_compatible(session) is False
    assert session_atoms_to_json(session)["metadata"]["trajectory_identity_compatible"] is False

    session.trajectory_frames[1] = Atoms("HO", positions=second.positions[:2].copy())
    session.invalidate_trajectory_layout()
    assert trajectory_identity_compatible(session) is False


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


def test_streamed_trajectory_never_builds_inline_or_binary_browser_cache():
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [0.25, 0.0, 0.0]
    session = EditorSession(
        "trajectory-frame-stream",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        config={"stream_trajectory": True},
    )

    data = session_atoms_to_json(session)

    assert data["metadata"]["trajectory_streaming"] is True
    assert data["metadata"]["trajectory_positions_cached"] is False
    assert data["metadata"]["trajectory_positions_binary"] is False
    assert "trajectory_positions" not in data
    assert trajectory_position_array(session) is None


def test_frontend_uses_physical_keys_for_layout_independent_shortcuts():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    for code in ["KeyA", "KeyC", "KeyG", "KeyR", "KeyV", "KeyX", "KeyY", "KeyZ"]:
        assert code in main_js
    assert "isPhysicalKey" in main_js
    assert "e.key === 'g'" not in main_js
    assert "e.key === 'r'" not in main_js


def test_image_export_has_exact_preview_and_option_modal_controls():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert 'id="export-preview-frame"' in index_html
    assert 'id="btn-preview-image"' in index_html
    assert "syncImageExportPreview" in main_js
    assert "setExportPreview" in renderer_js
    assert "renderExportPreview" in renderer_js
    assert "const exportView = this.exportCameraSetup(width, height, options)" in renderer_js
    assert "this.renderExportPreview()" in renderer_js
    assert "showExportImageModal" in main_js
    assert "export-transparent" in main_js
    assert "export-grid" in main_js
    assert "export-axes" in main_js
    assert 'id="atomic-scale"' in index_html
    assert 'id="atomic-scale-span"' in index_html
    assert "setPixelsPerAngstrom" in renderer_js
    assert "syncAtomicScaleFromCamera" in main_js
    assert "export-framing-mode" in main_js
    assert "export-pixels-per-angstrom" not in main_js
    assert "export-sphere-quality" in main_js
    assert "export-smoothness-scale" in main_js
    assert "normalizedImageExportProfile" in main_js
    assert "setImageExportProfile(readImageProfile())" in main_js
    assert "const profile = this.state.exportPreviewProfile || this.currentImageExportProfile()" in main_js
    assert "options: profile.options" in main_js
    assert "this.renderer.exportPNGBlob(width, height, options)" in main_js
    assert "this.api.encodeImage(source, format, onProgress)" in main_js
    assert "xhr.upload.addEventListener('progress'" in (
        ROOT / "v_ase/static/api.js"
    ).read_text()
    assert "modalContainer?.addEventListener('pointerdown'" in main_js
    assert "e.stopPropagation()" in main_js
    assert "transparentBackground" in renderer_js
    assert "includeAxes" in renderer_js
    assert "this.scene.background = null" in renderer_js
    assert "options.includeGrid !== false" in renderer_js
    assert "exportCameraSetup" in renderer_js
    assert "cameraFromSettings(settings, aspect = 1)" in renderer_js
    assert "const configured = this.cameraFromSettings(options.camera, outputAspect)" in renderer_js
    assert "interactionProjectionContext(clientX, clientY)" in renderer_js
    assert 'id="render-area-follow-view"' in index_html
    assert 'id="render-area-eye"' in index_html
    assert "camera.aspect = outputAspect" in renderer_js
    assert "const halfWidth = halfHeight * outputAspect" in renderer_js
    assert "offsetX = Math.floor" not in renderer_js
    assert "offsetY = Math.floor" not in renderer_js
    assert "applyExportSphereQuality" in renderer_js
    assert "this.updateCameraProjection(width / height)" not in renderer_js
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
    assert "this.cameraFillDirectionalLight.position.copy(camera.position)" in renderer_js
    assert "new THREE.AmbientLight(0xffffff, 0.30)" in renderer_js
    assert "new THREE.DirectionalLight(0xffffff, 0.88)" in renderer_js
    assert "new THREE.HemisphereLight(0xffffff, 0xd6dcda, 0.38)" in renderer_js
    assert "new THREE.MeshPhysicalMaterial" in renderer_js
    assert "updateViewLighting()" in renderer_js


def test_frontend_handles_missing_calculator_forces_without_aborting_refresh():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "computeFmax(forces = [])" in main_js
    assert "this.state.cachedFmax = this.computeFmax" in main_js
    assert "Array.isArray(force)" in main_js
    assert "[x, y, z].every(Number.isFinite)" in main_js
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
    assert "Restore canonical +axis view" in index_html
    assert "const canonicalUp = axis === 'Z'" in main_js
    assert "const canonicalUpAligned = basis.up.dot(canonicalUp) > poseTolerance;" in main_js
    assert "positiveDirectionAligned && canonicalUpAligned ? -1 : 1" in main_js
    assert "Lock the global Cartesian axis in G/R/S mode" in index_html
    assert "this.isPhysicalKey(e, 'KeyS', ['s'])" in main_js


def test_frontend_renders_constraint_guides_and_blender_export_button():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    selection_js = (ROOT / "v_ase/static/selection.js").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

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
    assert "pairwise-bond-list" in index_html
    assert "Pair specifications" in index_html
    assert "Manual index pairs" in index_html
    assert "deleteSelection" in main_js
    assert "api.deleteAtoms" in main_js
    assert "updateCalculatorConfig" in api_js
    assert "currentCalculatorPayload" in main_js
    assert "e.code === 'Delete'" in main_js
    assert "renderPairwiseBondControls" in main_js
    assert "parsePairwiseBondRanges" in main_js
    assert "this.setInspectorCollapsed(!document.body.classList.contains('inspector-collapsed'))" in main_js
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
    assert "constraintConeGeometry" not in renderer_js
    assert "displacementConeGeometry" in renderer_js
    assert "constraintMarkGroup" in renderer_js
    assert "addFixedLineGuide" in renderer_js
    assert "addFixedPlaneGuide" in renderer_js
    assert "rebuildHookeanConstraints" in renderer_js
    assert "makeSpringPoints" in renderer_js
    assert "makeHelicalSpringPoints" in renderer_js
    assert "makeFlatSpringPoints" not in renderer_js
    assert "hookean: new THREE.MeshStandardMaterial" in renderer_js
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
    assert "rebuildSupercellBonds" in renderer_js
    assert "inferSupercellBridgeBondRecords" in renderer_js
    assert "supercellBridgeStartOffsets" in renderer_js
    assert "supercellBridgeBondCount" in renderer_js
    assert "supercellBonds" in renderer_js
    assert "rebuildSupercellAtoms" in renderer_js
    assert "pickHover" in selection_js
    assert "sphereQualitySegments" in renderer_js
    assert "pairwiseBondCutoff" in renderer_js
    assert "springLine.visible = state !== 'inactive'" in renderer_js
    assert "hookeanBondExclusions" in renderer_js
    assert "minimumImageDelta" in renderer_js
    assert "cartToFrac" in renderer_js
    assert "atomVisualRadius" in renderer_js
    assert "atomVisualColor" in renderer_js
    assert "exportBlender" in api_js
    assert "btn-export-blender" in index_html
    assert "export3dm" in api_js
    assert "exportObj" in api_js
    assert "exportHtml" in api_js
    assert "btn-export-3dm" in index_html
    assert "btn-export-obj" in index_html
    assert "btn-export-html" in index_html
    assert "htmlViewFilename" in main_js
    assert "showHtmlExportModal" in main_js
    assert "Embed editable .vase project" in main_js
    assert "Interactive view-only HTML saved without project data." in main_js
    assert "renderHtmlCompositionPreview" in main_js
    assert "exportCompositionSnapshot" in renderer_js
    assert 'id="html-include-grid"' in main_js
    assert 'id="html-include-axes"' in main_js
    assert 'id="html-include-cell"' in main_js
    assert "embedProject === true" in main_js
    assert "btn-save-project-html" not in index_html
    assert "project-include-interactive-viewer" in main_js
    assert "Include interactive rendered view" in main_js
    assert "output format changes to HTML" in main_js
    assert "Interactive HTML project" in main_js
    assert "Output format: HTML" in main_js
    assert 'data-inspector-group="export"' in index_html
    assert "renderer.supercellBridgeBondRecords" in main_js
    assert "selected-measure" in index_html
    assert "getSelectionMeasureText" in main_js
    assert 'id="selection-measure-readout"' in index_html
    assert 'id="selection-measure-value"' in index_html
    assert "getSelectionMeasureSummary" in main_js
    assert "fetchAtomProperties" in api_js
    assert "/api/analysis/atom-properties/" in api_js
    assert "ensureSingleSelectionProperties" in main_js
    assert "singleSelectionPropertyLines" in main_js
    assert "single-atom-properties" in style_css
    assert "single-atom-measure-grid" in main_js
    assert ".single-atom-measure-grid .selection-measure-panel-label" in style_css
    assert "measure=${measure}" not in main_js
    assert "selectionAngle" in main_js
    assert "selectionTorsion" in main_js
    assert "selectionDelta(first, second, { mic = true } = {})" in main_js
    assert "Direct: d(a1-a2)" in main_js
    assert "MIC: d(a1-a2)" in main_js
    assert "selectionMeasurementMap" in main_js
    assert "updateSelectionMeasurementOverlay" in main_js
    assert 'id="measurement-overlay"' in index_html
    assert 'id="btn-grid-toggle"' in index_html
    assert "setViewportGridVisible" in main_js
    assert "currentCameraForExport" in main_js
    assert "camera) body.camera = camera" in api_js
    assert "display) body.display = display" in api_js
    assert "bondPairs) body.bond_pairs = bondPairs" in api_js
    assert "threshold: 4.80" in api_js
    for panel in (
        "structure-info", "selection", "constraints", "view", "transform",
        "appearance", "cell-transform", "bonding", "scientific-tools",
    ):
        assert f'<details class="panel-section" open data-panel="{panel}"' in index_html


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
    assert "appearance-table-body" in index_html
    assert "renderAppearanceRows" in main_js
    assert "return this.reconcileLabelOrder(this.state.atoms?.symbols || []);" in main_js
    assert "naturalTypeCompare" in main_js
    assert ".sort((a, b) => this.naturalTypeCompare(a, b))" in main_js
    assert "previewDetectedBase" in main_js
    assert "typeSelect.value = inferredBase" in main_js
    assert "nameInput.value = this.labelForBaseTypeChange(symbol, typeSelect.value)" not in main_js
    assert "uniqueTypeLabel" not in main_js
    assert "Merged ${oldSymbol} into label ${label}" in main_js
    assert "pendingLabelRenames" in main_js
    assert "expectedIndices" in main_js
    assert "No ${oldSymbol} atoms found" not in main_js
    assert "nameInput.addEventListener('change', () => commitRename())" in main_js
    assert "nameInput.addEventListener('change', commitRename)" not in main_js
    assert "detectedElementForLabel" in main_js
    assert "setElementBaseDefaults" in main_js
    assert "appearance: preserveAppearance" in main_js
    assert "element_radii" in main_js
    assert "element_colors" in main_js
    assert "parseLabelRadii" in main_js
    assert "parseLabelVisibility" in main_js
    assert "label-color-input" in main_js
    assert "label-visible-checkbox" in main_js
    assert "label-select-checkbox" in main_js
    assert "indeterminate" in main_js
    assert "renameAtomLabel" in main_js
    assert "renameAtomLabelForVisualization" in main_js
    assert "applySelectedLabelForVisualization" in main_js
    assert "trajectory_identity_compatible" in main_js
    assert "Label changed on this frame only" in main_js
    assert "viewIdentityOverridesSnapshot" in main_js
    assert "restoreViewIdentityOverrides" in main_js
    assert "includeIdentityOverrides: true" in main_js
    assert "nameInput.disabled = this.state.vizOnly" not in main_js
    assert '<div id="selected-appearance" class="selected-appearance">' in index_html
    assert "canViewportSelectAtoms()" in main_js
    assert "this.canViewportSelectAtoms() && this.transform.mode === 'IDLE'" in main_js
    assert "this.renderer.renameAtomLabel(oldSymbol, label, indices, this.state.display, null)" in main_js
    assert "this.renderer.renameAtomLabel(null, label, indices, this.state.display, null)" in main_js
    assert "applySelectedLabelEdit" in main_js
    assert "setupRuntimeModeControls" in main_js
    assert "viewModeIdentityPlan" in main_js
    assert "labelMaterials" in main_js
    assert "labelOpacities" in main_js
    assert "atomMaterials" in main_js
    assert "atomRadiusScales" in main_js
    assert "atomColors" in main_js
    assert "atomOpacities" in main_js
    assert "atomBondStyles" in main_js
    assert 'data-runtime-mode="view"' in index_html
    assert 'id="selected-atom-material"' in index_html
    assert 'id="selected-atom-color"' in index_html
    assert 'id="selected-atom-opacity"' in index_html
    assert 'id="selected-atom-radius-scale"' in index_html
    assert 'id="selected-atom-update-bonds"' in index_html
    assert "appearance-material-select" in main_js
    assert "label-opacity-input" in main_js
    assert "selectLabel(symbol)" in main_js
    assert "toggleLabelSelection" in main_js
    assert "labelVisible" in renderer_js
    assert "atomLabelVisible" in renderer_js
    assert "handleLostPointerCapture(event)" in renderer_js
    assert "Chrome/Safari can drop pointer capture during middle-button drags" in renderer_js
    assert "window.addEventListener('pointermove', this.onPointerMove, true)" in renderer_js
    assert "window.addEventListener('mouseup', this.onMouseUp, true)" in renderer_js
    assert "window.addEventListener('blur', this.onWindowBlur, true)" in renderer_js
    assert "this.onLostPointerCapture = (event) => this.handleLostPointerCapture(event)" in renderer_js
    assert "this.onLostPointerCapture = (event) => this.endGesture(event)" not in renderer_js
    assert "renameAtomLabel(oldSymbol, label, indices = [], displayOptions = null, baseSymbol = null)" in renderer_js
    assert "refreshAtomAppearance(indices)" in renderer_js
    assert "rebuildInstancedAtoms" in renderer_js
    assert "inferBondPairsCellList" in renderer_js
    assert "AUTO_BOND_HYDROGEN_SLACK" in renderer_js
    assert "AUTO_BOND_COVALENT_SLACK" in renderer_js
    assert "AUTO_BOND_METAL_LIGAND_SLACK" in renderer_js
    assert "METALLIC_ELEMENT_SYMBOLS" in renderer_js
    assert "autoBondBaseCutoffFromValues" in renderer_js
    assert "firstClass === AUTO_BOND_CLASS_METAL && secondClass === AUTO_BOND_CLASS_METAL" in renderer_js
    assert "fixedAtomDisplayEnabled()" in renderer_js
    assert "return this.displayOptions.showOverlays !== false" in renderer_js
    assert "fixedAtomSegments(segmentCount)" in renderer_js
    fixed_segments = renderer_js.index("\n    fixedAtomSegments(segmentCount) {")
    assert "return segmentCount;" in renderer_js[fixed_segments:fixed_segments + 500]
    assert "const baseSelectionVisible = visible && !this.commensurateSupercellPreview" in renderer_js
    assert "canvas.width = 760" in renderer_js
    assert "let fontSize = 42" in renderer_js
    assert "flatShading: isFixed" in renderer_js
    assert "v-ase-fixed-micro-etched-faceted-v3" in renderer_js
    assert "const supercellChanged" in renderer_js
    assert "if (supercellChanged) this.rebuildSupercell()" in renderer_js
    assert "labelVisible: { ...(options.labelVisible" in renderer_js
    assert "mesh.visible === false" in (ROOT / "v_ase/static/selection.js").read_text()
    assert "btn-apply-selected-type" not in index_html
    assert "selection-textbox" in index_html
    assert "data-copy-target=\"selected-indices\"" in index_html
    assert "align-items: start" in style_css
    assert "max-height: 28px" in style_css
    assert "align-self: start" in style_css
    assert "Center (unwrapped)" in index_html
    assert "orientation-widget" in index_html
    assert "create-atom-widget" in index_html
    assert "btn-create-atom-toggle" in index_html
    assert "create-atom-card" in index_html
    assert "setupCreateAtomWidget" in main_js
    assert "createAtomFromWidget" in main_js
    assert "makeCreateAtomWidgetDraggable" in main_js
    assert "top: calc(var(--header-height) + 16px)" in style_css
    assert "bottom: auto" in style_css
    assert "widget.style.removeProperty('top')" in main_js
    assert "widget.style.removeProperty('bottom')" in main_js
    assert "this.api.addAtom(symbol, position, baseSymbol)" in main_js
    assert "async addAtom(symbol, position, baseSymbol = null)" in (ROOT / "v_ase/static/api.js").read_text()
    assert ".create-atom-widget" in style_css
    assert "body.dragging-create-atom" in style_css
    assert "Repulsion calculator" in index_html
    assert "These resources apply only to the built-in Repulsion calculator" in index_html
    assert 'id="calc-controls" class="repulsion-settings"' in index_html
    assert "updateAtomIdentity" in (ROOT / "v_ase/static/api.js").read_text()
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
    assert "labelRadii" in renderer_js
    assert "labelColors" in renderer_js
    assert "new THREE.SphereGeometry(1, group.atomSegments" in renderer_js
    assert "mesh.setColorAt(" in renderer_js
    assert "mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)" in renderer_js
    assert "previous.atomRadiusScale" in renderer_js
    assert "reconcileLabelOrder" in main_js
    assert "replaceLabelOrder(oldSymbol, label)" in main_js
    assert "#inspector .panel-section" in style_css
    assert ".appearance-table" in style_css
    assert "overflow-x: auto" in style_css
    assert ".label-check:indeterminate" in style_css
    assert ".appearance-row" in style_css
    assert "--inspector-width" in style_css
    assert "min-width: 820px" in style_css
    assert "#inspector .appearance-row > :first-child" in style_css
    assert "position: sticky" in style_css
    assert 'body[data-viz-only="true"] [data-edit-only]' in style_css
    assert ".busy-spinner" in style_css
    assert ".orientation-widget" in style_css
    assert ".create-atom-card" in style_css
    assert ".calc-control-title" in style_css


def test_frontend_renderer_uses_demand_rendering_and_large_scene_instancing():
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "preserveDrawingBuffer: false" in renderer_js
    assert "requestRender()" in renderer_js
    assert "renderFrame()" in renderer_js
    assert "this.controls.onChange = () =>" in renderer_js
    assert "this.onCameraChange?.(" in renderer_js
    assert "requestAnimationFrame(() => this.animate())" not in renderer_js
    assert "rebuildInstancedAtoms" in renderer_js
    assert "new THREE.InstancedMesh" in renderer_js
    assert "this.atomIndicesByLabel = new Map()" in renderer_js
    assert "applyAtomVisibility(changedSymbols = null)" in renderer_js
    assert "updateRenderQuality()" in renderer_js
    assert "if (atomCount >= 15000) cap = 1" in renderer_js
    assert "orientationSignature" in main_js


def test_camera_view_background_and_2d_display_controls_are_wired():
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert 'id="view-toolbar"' in index_html
    assert 'id="view-rotate-step"' in index_html
    for direction in ("left", "right", "up", "down", "roll-ccw", "roll-cw"):
        assert f'data-view-rotate="{direction}"' in index_html
    arrow_positions = [
        index_html.index(f'data-view-rotate="{direction}"')
        for direction in ("up", "down", "left", "right", "roll-ccw", "roll-cw")
    ]
    assert arrow_positions == sorted(arrow_positions)
    assert 'data-view-rotate-axis=' not in index_html
    assert 'data-view-align-axis=' not in index_html
    assert 'id="btn-view-toggle"' not in index_html
    assert 'id="viewport-background"' in index_html
    assert 'id="atom-display-mode"' in index_html
    viewport_start = index_html.index('data-panel="view"')
    appearance_start = index_html.index('data-panel="appearance"')
    anti_aliasing = index_html.index('id="chk-antialias"')
    atom_smoothness = index_html.index('id="sphere-quality"')
    atom_radius = index_html.index('id="atom-radius-scale"')
    assert viewport_start < anti_aliasing < appearance_start
    assert viewport_start < atom_smoothness < appearance_start
    assert appearance_start < atom_radius
    assert "setupViewControls()" in main_js
    assert "cameraViewBasis()" in main_js
    assert "rotateCameraView(direction, stepDegrees" in main_js
    assert "'roll-ccw': { axis: basis.forward, sign: 1 }" in main_js
    assert "'roll-cw': { axis: basis.forward, sign: -1 }" in main_js
    assert "left: { axis: basis.up, sign: 1 }" in main_js
    assert "right: { axis: basis.up, sign: -1 }" in main_js
    assert "up: { axis: basis.right, sign: 1 }" in main_js
    assert "down: { axis: basis.right, sign: -1 }" in main_js
    assert 'id="view-arrow-orbit-shape"' in index_html
    assert 'id="view-arrow-orbit-highlight"' in index_html
    assert 'id="view-arrow-orbit-seam"' in index_html
    assert index_html.count('class="view-arrow-orbit-surface"') == 4
    assert index_html.count('class="view-arrow-orbit-highlight"') == 4
    assert index_html.count('class="view-arrow-orbit-seam"') == 4
    assert index_html.count('class="view-arrow-orbit-rim"') == 4
    assert 'transform="matrix(0 1 1 0 0 0)"' in index_html
    assert 'transform="translate(0 48) scale(1 -1)"' in index_html
    assert 'transform="matrix(0 1 -1 0 48 0)"' in index_html
    assert 'id="view-arrow-roll-ccw-shape"' in index_html
    assert index_html.count('class="view-arrow-front-surface"') == 2
    assert index_html.count('class="view-arrow-front-depth"') == 2
    assert "selectionCountText(selectedReferences" in main_js
    assert "bondThickness: 0.25" in main_js
    assert "atomRadiusScale: 0.6" in main_js
    assert 'id="bond-thickness" value="0.25"' in index_html
    assert 'id="atom-radius-scale" value="0.6"' in index_html
    assert "viewportBackground: 'white'" in main_js
    assert '<option value="white" selected>White</option>' in index_html
    assert 'data-viewport-background="white"' in index_html
    assert "atomDisplayMode: '3d'" in main_js
    assert "setViewportBackground(mode" in renderer_js
    assert "new THREE.HemisphereLight(0xffffff, 0xd6dcda, 0.38)" in renderer_js
    assert "new THREE.AmbientLight(0xffffff, 0.30)" in renderer_js
    assert "new THREE.DirectionalLight(0xffffff, 0.88)" in renderer_js
    assert "lightViewport ? '#e3e8e5'" in renderer_js
    assert "lightViewport ? 0.48 : 0.58" in renderer_js
    assert "effectiveBondStyle()" in renderer_js
    assert "this.atomDisplayMode() === '2d'" in renderer_js
    assert "new THREE.MeshBasicMaterial" in renderer_js
    assert "applyFlatAtomShader(material, isFixed)" in renderer_js
    assert "material.userData.flatOutlineEnabled = outline" in renderer_js
    assert "applyFlatBondShader(material)" in renderer_js
    assert "flatBondOutlineApplied" in renderer_js
    assert "vec3(0.012)" in renderer_js
    assert ".view-toolbar" in style_css
    assert ".view-arrow-btn" in style_css


def test_native_file_picker_suppresses_the_trailing_enter_activation():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "performance.now() < this.filePickerSuppressUntil" in main_js
    assert "this.filePickerSuppressUntil = performance.now() + 750" in main_js


def test_new_scientific_defaults_and_ai_control_contract_are_wired():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    workspace_js = (ROOT / "v_ase/static/workspace.js").read_text()
    cli_py = (ROOT / "v_ase/cli.py").read_text()
    server_py = (ROOT / "v_ase/server.py").read_text()
    skill_root = (
        ROOT
        / "v_ase"
        / "skills"
        / "visualizing-atomic-structures-with-v-ase"
    )
    skill = "\n".join([
        (skill_root / "SKILL.md").read_text(),
        *[
            path.read_text()
            for path in sorted((skill_root / "references").glob("*.md"))
        ],
    ])

    assert 'id="chk-bonds" checked' in index_html
    assert 'id="chk-commensurate-guide">' in index_html
    assert 'id="chk-commensurate-guide" checked' not in index_html
    assert 'id="commensurate-max-area" value="16"' in index_html
    assert 'id="commensurate-max-area" value="16" min="1" max="128"' in index_html
    assert 'id="commensurate-supercell-proposal"' in index_html
    assert 'id="chk-commensurate-snap">' in index_html
    assert 'id="calc-cutoff-scale" value="1.00"' in index_html
    assert 'id="calc-cutoff-mode"' in index_html
    assert 'id="calc-cutoff-distance" value="2.00"' in index_html
    assert 'id="calc-strength" value="1.0"' in index_html
    assert "showBonds: true" in main_js
    assert "commensurateGuide: false" in main_js
    assert "commensurateMaxAreaRatio: 16" in main_js
    assert "prepareCommensurateSupercellProposal" in main_js
    assert "applyCommensurateSupercellProposal" in main_js
    assert "commensurateSnap: false" in main_js
    assert "camera.getWorldQuaternion" in main_js
    assert "kindSelect.dataset.draftKind" in main_js
    assert "window.v_aseAI" in main_js
    assert "window.v_aseAI" in workspace_js
    assert "--cli" in cli_py
    assert '@app.get("/api/ai/state/{session_id}")' in server_py
    assert "ai.render" in skill
    for operation in (
        "wrap",
        "translate-all",
        "set-supercell",
        "make-supercell",
        "add-atom",
        "delete-selection",
        "set-identity",
        "set-constraints",
        "move-selection",
        "rotate-selection",
        "rotate-to-commensurate",
        "apply-commensurate-cell",
        "dismiss-commensurate-cell",
        "undo",
        "redo",
        "reset-coordinates",
        "start-relaxation",
        "stop-relaxation",
        "clear-relaxation-trajectory",
        "refresh-displacements",
    ):
        assert f"'{operation}'" in main_js
        assert f"`{operation}`" in skill
    for export_format in (
        "image",
        "video",
        "poscar",
        "pickle",
        "blender",
        "3dm",
        "obj",
        "project",
        "settings",
    ):
        assert f"`{export_format}`" in skill
    assert '"white"` or `"dark"`' in skill
    assert '"unlit"`, `"standard"`, or `"metal"`' in skill
    assert "quality.sphereQuality must be auto" in main_js
    matrix_operation = main_js[
        main_js.index("if (name === 'make-supercell')"):
        main_js.index("if (name === 'add-atom')")
    ]
    assert "this.finalizeMaterializedSupercellDisplay()" in matrix_operation
    finalize_start = main_js.index("finalizeMaterializedSupercellDisplay() {")
    finalize_end = main_js.index(
        "normalizedTranslationVector(",
        finalize_start,
    )
    finalize_helper = main_js[finalize_start:finalize_end]
    assert "this.state.display.supercell = [1, 1, 1]" in finalize_helper
    assert "this.resetVisualHistoryBaseline()" in finalize_helper


def test_open_file_uses_the_native_system_picker_immediately():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "chooseStructureFile() {\n        this.chooseSystemStructureFile();\n    }" in main_js
    assert "chooseSystemStructureFile" in main_js
    assert "showLaunchDirectoryBrowser" not in main_js
    assert "browseStructureFiles(directory" not in api_js
    assert "loadStructurePath(path" not in api_js
    # Agent-only path loading remains restricted to the terminal launch
    # directory; the human Open workflow must still invoke the native picker.
    assert "appendStructurePath(" in api_js
    assert "appendStructurePath" not in main_js[
        main_js.index("chooseStructureFile()"):
        main_js.index("chooseSystemStructureFile", main_js.index("chooseStructureFile()") + 1)
    ]
    assert ".launch-file-list" not in style_css


def test_api_browser_close_and_python_view_autoclose_contract_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    viewer_py = (ROOT / "v_ase/viewer.py").read_text()
    server_py = (ROOT / "v_ase/server.py").read_text()
    workspace_js = (ROOT / "v_ase/static/workspace.js").read_text()

    assert "close_on_disconnect: bool = True" in viewer_py
    assert '"auto_close_on_disconnect": bool(close_on_disconnect and not notebook)' in viewer_py
    assert "this.ws = ws" in main_js
    assert "window.addEventListener('pagehide', this.handlePageTeardown" in main_js
    assert "this.closeSocket?.();" in main_js
    assert "window.addEventListener('beforeunload', this.handlePageTeardown" in main_js
    assert "this.ws.close(1000, 'page closing')" in main_js
    assert "schedule_session_autoclose(session_id)" in server_py
    assert "finalize_session_from_browser_close(session_id)" in server_py
    assert "this.browserClientId" in workspace_js
    assert "navigator.sendBeacon(closeUrl" in workspace_js
    assert "/browser-close/" in workspace_js
    assert "client_id: this.browserClientId" in workspace_js
    assert "closing_client_id=normalized" in server_py


def test_frontend_reset_video_and_visual_settings_controls_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "btn-reset-coords" in index_html
    assert "confirmFullReset" in main_js
    assert "confirmCoordinateReset" in main_js
    assert "resetCoordinates" in api_js
    assert "Resetting physical coordinates and original unit cell" in main_js
    assert "Display replication and visual translation were kept" in main_js
    assert "btn-export-video" in index_html
    assert '<section class="panel-section export-section"' in index_html
    assert '<section class="panel-section utility-section"' in index_html
    assert "Scientific Tools" not in index_html
    assert "Relaxation" in index_html
    assert "Export Video is available for loaded trajectory files only" in main_js
    assert "exportTrajectoryVideo" in main_js
    assert "canvas.captureStream" in main_js
    assert "MediaRecorder" in main_js
    assert "MOV (H.264)" in main_js
    assert "AVI (MPEG-4)" in main_js
    assert "video/mp4;codecs=avc1.42E01E" in main_js
    assert "backgroundColor: '#ffffff'" in main_js
    assert 'id="video-interpolation-multiplier"' in main_js
    assert 'id="video-interpolation-mic"' in main_js
    assert "interpolateTrajectoryFrames" in main_js
    assert "interpolatedFrameCount" in main_js
    assert "Higher values take longer to render." in main_js
    assert "beginExportCapture" in renderer_js
    assert "renderExportCaptureFrame" in renderer_js
    assert "transcodeVideo" in api_js
    assert "btn-save-settings" in index_html
    assert "btn-load-settings" in index_html
    assert "settings-file" in index_html
    assert "saveVisualSettings" in api_js
    assert "loadVisualSettings" in api_js
    assert "v_ase_visual_settings.json" in main_js
    assert "btn-save-project" in index_html
    assert index_html.count('id="btn-save-project"') == 1
    assert ">Save Project</button>" in index_html
    assert "btn-load-project" in index_html
    assert "project-file" in index_html
    assert "projectFilename()" in main_js
    assert "this.projectFilename()" in main_js
    assert "saveProject" in main_js
    assert "loadProject" in api_js
    assert "btn-open-file" in index_html
    assert "btn-empty-open" in index_html
    assert "structure-file" in index_html
    assert "loadStructureFile" in main_js
    assert "loadStructureFile" in api_js
    assert "const hadLoadedAtoms = this.hasLoadedAtoms();" in main_js
    assert "const settings = isProject ? projectSettings : inheritedSettings;" in main_js
    assert "this.renderer.needsInitialCameraFit = !settings?.camera;" in main_js
    assert "this.renderPairwiseBondControls({ capture: false });" in main_js
    assert "ASE Pickle" in index_html
    assert "SinglePointCalculator" in index_html
    assert "save-format-guide" in index_html
    assert ".confirm-list" in style_css
    assert "#inspector .btn-block:disabled" in style_css
    assert "--viewport-light-ink: #14211e" in style_css
    assert "--viewport-light-action: #147a69" in style_css


def test_trajectory_controls_update_live_and_space_toggles_playback():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert "queueFrameLoad" in main_js
    assert "flushFrameLoadQueue" in main_js
    assert '<div id="trajectory-panel" class="trajectory-strip"' in index_html
    assert 'frame-label">1 / 1' in index_html
    assert "timeline-source-select" in index_html
    assert "secondary-trajectory-row" in index_html
    assert "secondary-frame-slider" in index_html
    assert "primaryTimelineSource" in main_js
    assert "secondaryTimelineSource" in main_js
    assert "setTimelineSource" in main_js
    assert "timelineSourceName" in main_js
    assert "timelineFrameCount(source)" in main_js
    assert "startRelaxTrajectory" in main_js
    assert "appendRelaxFrame" in main_js
    assert "loadRelaxFrame" in main_js
    assert "relaxOverridePositions" in main_js
    assert "panel.classList.toggle('hidden', loadedCount <= 1 && relaxCount <= 1)" in main_js
    assert "slider.disabled = count <= 1" in main_js
    assert "frame-slider').oninput" in main_js
    assert "secondary-frame-slider')?.addEventListener('input'" in main_js
    assert "movie-fps').oninput" in main_js
    assert 'label for="movie-skip">Skip' in index_html
    assert "movie-skip" in main_js
    assert "restartPlayback" in main_js
    assert "currentPlaybackFps" in main_js
    assert "currentPlaybackSkip" in main_js
    assert "currentPlaybackStep" in main_js
    assert "playbackTask = this.stepFrame(" in main_js
    assert "this.currentPlaybackStep()," in main_js
    assert "this.state.trajectoryPlaybackSource || source" in main_js
    assert "this.state.trajectoryPlaybackTask = playbackTask" in main_js
    assert "setTimeout(tick, 1000 / this.currentPlaybackFps())" in main_js
    assert "e.code === 'Space'" in main_js
    assert "e.key === 'ArrowLeft' || e.key === 'ArrowRight'" in main_js
    assert "this.requestFrameStep(delta)" in main_js
    assert "Play or pause the selected timeline" in main_js
    assert "setupNumberInputHoldGuards" in main_js
    assert "bindNumberInputHoldGuard" in main_js
    assert "data-hold-guarded" in main_js
    assert "nativeNumberSpinDirection" in main_js
    assert "stepNumberInputOnce" in main_js
    assert "event.preventDefault()" in main_js
    assert "event.stopImmediatePropagation()" in main_js
    assert "input.dispatchEvent(new Event('change', { bubbles: true }))" in main_js
    assert "window.addEventListener('blur', stop, true)" in main_js
    assert "number-stepper" not in main_js
    assert "number-stepper" not in style_css
    assert "input[type=\"number\"]::-webkit-inner-spin-button" not in style_css
    assert ".trajectory-strip" in style_css
    assert ".secondary-trajectory-row" in style_css
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    assert "canonicalVectorKey" in renderer_js
    assert "...Object.keys(fixedLine).map(Number)" in renderer_js
    assert "...Object.keys(fixedPlane).map(Number)" in renderer_js
    assert "!selectedIndices.size" not in renderer_js
    assert "constraintGuideMetrics(index)" in renderer_js
    assert "new THREE.CircleGeometry(metrics.outerRadius, 48)" in renderer_js
    assert "Math.max(0.01, half - metrics.strokeWidth)" in renderer_js
    assert "constraintGuideIndices" in renderer_js
    assert "planeAggregate" in renderer_js
    assert "refreshBondsForCurrentPositions" in renderer_js
    assert "inferCurrentBondTopology" in renderer_js
    assert "const periodicPairs = this.inferBondPairs(true)" in renderer_js
    assert "bridgeRecords: this.inferSupercellBridgeBondRecords(repeats, periodicPairs)" in renderer_js
    assert "this.refreshBondsForCurrentPositions()" in renderer_js


def test_persistent_constraint_guides_and_cell_style_controls_are_wired():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()

    assert 'id="cell-color"' in index_html
    assert 'id="cell-thickness"' in index_html
    assert 'id="cell-material"' in index_html
    assert "cellThickness: 0.04" in main_js
    assert "cellColor: '#d6bd67'" in main_js
    assert "cellMaterial: 'unlit'" in main_js
    assert "normalizedCellThickness()" in renderer_js
    assert "createCellMaterial()" in renderer_js
    assert "new THREE.InstancedMesh(" in renderer_js
    assert "addUniqueSegment" in renderer_js
    assert "originKeys" in renderer_js
    assert "signature === this.constraintGuideSignature" in renderer_js
    assert "lineHalfLength" in renderer_js
    assert "fixedLineAxis" in renderer_js
    assert "fixedLineMotionAxis" in renderer_js
    assert "fixedLineRail" not in renderer_js
    assert "fixedLineCollar" not in renderer_js
    assert "new THREE.RingGeometry" not in renderer_js[
        renderer_js.index("addFixedLineGuide("):
        renderer_js.index("addFixedPlaneGuide(")
    ]
    assert ".chemical-type-select" in style_css
    assert ".cell-translation .panel-note" in style_css


def test_export_downloads_use_save_picker_and_fallback_anchor():
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert "saveBlobFromAction" in main_js
    assert "showSaveFilePicker" in main_js
    assert "document.body.appendChild(a)" in main_js
    assert "Preparing POSCAR export" in main_js
    assert "Preparing ASE Pickle export" in main_js
    assert "Preparing Blender export" in main_js
    blob_helper = main_js[
        main_js.index("async saveBlobFromAction("):
        main_js.index("\n    closeModal()", main_js.index("async saveBlobFromAction("))
    ]
    assert blob_helper.index("await this.chooseSaveDestination") < blob_helper.index(
        "await this.withBusy"
    )
    image_handler = main_js[
        main_js.index("document.getElementById('modal-export-image')"):
        main_js.index("\n    showExportVideoModal()", main_js.index("document.getElementById('modal-export-image')"))
    ]
    assert image_handler.index("await this.chooseSaveDestination") < image_handler.index(
        "this.renderOptimizedImage"
    )
    assert "export-image-format" in main_js
    assert "WebP (lossless, compact)" in main_js
    video_handler = main_js[
        main_js.index("document.getElementById('modal-export-video')"):
        main_js.index("\n    async exportTrajectoryVideo", main_js.index("document.getElementById('modal-export-video')"))
    ]
    assert video_handler.index("await this.chooseSaveDestination") < video_handler.index(
        "await this.exportTrajectoryVideo"
    )


def test_structure_translation_controls_and_api_are_explicit():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert 'class="cell-translation" data-edit-only' not in index_html
    assert 'class="cell-translation"' in index_html
    assert 'data-translation-mode="cartesian"' in index_html
    assert 'data-translation-mode="fractional"' in index_html
    assert 'id="translate-x"' in index_html
    assert 'id="translate-y"' in index_html
    assert 'id="translate-z"' in index_html
    assert 'id="btn-apply-translation"' in index_html
    assert "Offsets displayed atoms after cell replication." in index_html
    assert "ASE coordinates and the unit cell remain unchanged." in index_html
    assert "translationVectorFromControls" in main_js
    assert "applyAtomTranslation" in main_js
    assert "this.state.display.translation = [...vector]" in main_js
    assert "visualTranslationVector" in renderer_js
    assert "applyVisualTranslation" in renderer_js
    assert "/api/translate/{session_id}" in api_js


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
            "bondStyle": "flat",
            "bondThickness": 0.24,
            "bondColorMode": "split",
            "pairwiseBondStyles": {
                "H-H": {
                    "style": "flat",
                    "material": "metal",
                    "thickness": 0.18,
                    "colorMode": "split",
                    "color": "#c8ccd0",
                    "opacity": 0.75,
                }
            },
            "translation": [1.0, -0.5, 0.25],
            "translationMode": "cartesian",
            "labelMaterials": {"H": "metal"},
            "labelOpacities": {"H": 0.4},
            "atomRadiusScales": {"1": 1.25},
            "atomColors": {"1": "#33aa77"},
            "atomOpacities": {"1": 0.65},
            "atomMaterials": {"1": "rubber"},
            "atomBondStyles": {"1": {"material": "rubber", "opacity": 0.65}},
        },
        "bond_pairs": [[0, 1]],
        "camera": {
            "position": [5, -6, 4],
            "target": [0, 0, 0],
            "projection": "orthographic",
            "ortho_scale": 8,
        },
        "lighting": {
            "mode": "studio-shadow",
            "intensity": 3.4,
            "position": [7, -9, 12],
            "target": [1, 2, 3],
            "color": [1.0, 0.9, 0.8],
        },
    })
    script = Path(response.path).read_text(encoding="utf-8")
    exported_data = ast.literal_eval(
        script.split("DATA = ", 1)[1].splitlines()[0]
    )

    assert "BONDS = DATA.get(\"bonds\", [])" in script
    assert "MAT_BOND" in script
    assert 'BOND_STYLE = DISPLAY.get("bondStyle", "cylinder")' in script
    assert 'BOND_COLOR_MODE = DISPLAY.get("bondColorMode", "split")' in script
    assert "BOND_THICKNESS" in script
    assert "add_flat_between" in script
    assert "def get_bond_appearance(i, j, endpoint=None):" in script
    assert "def bond_pieces(i, j, start, end):" in script
    assert 'DISPLAY_PAIR_BOND_STYLES = DISPLAY.get("pairwiseBondStyles", {})' in script
    assert 'DISPLAY_ATOM_BOND_STYLES = DISPLAY.get("atomBondStyles", {})' in script
    assert "add_unit_cell(CELL)" in script
    assert "ATOM_MESHES" in script
    assert "bpy.data.objects.new" in script
    assert "polygon.use_smooth = True" in script
    assert "obj.data.type = \"ORTHO\"" in script
    assert 'name = f"bond_{i}_{j}_{bond_index:04d}"' in script
    assert 'LIGHTING = DATA.get("lighting", {})' in script
    assert "'mode': 'studio-shadow'" in script
    assert "'intensity': 3.4" in script
    assert "'position': [7, -9, 12]" in script
    assert "'target': [1, 2, 3]" in script
    assert 'bpy.data.lights.new("v_ase_studio_sun_data", type="SUN")' in script
    assert 'obj.data.energy = intensity' in script
    assert 'direction.to_track_quat("-Z", "Y")' in script
    assert 'obj = bpy.data.objects.new("v_ase_studio_sun", light_data)' in script
    assert 'source = bpy.data.objects.new("v_ase_sun_source", None)' in script
    assert 'target_handle = bpy.data.objects.new("v_ase_sun_target", None)' in script
    assert 'track.track_axis = "TRACK_NEGATIVE_Z"' in script
    assert 'BLENDER_OBJECT_MODE = DISPLAY.get("blenderExportMode", "instanced")' in script
    assert 'GeometryNodeInstanceOnPoints' in script
    assert 'atom_index = mesh.attributes.new("atom_index", "INT", "POINT")' in script
    assert 'add_bond_groups(BONDS)' in script
    assert 'mat.use_nodes = True' in script
    assert 'bsdf.inputs.get("Base Color")' in script
    assert 'base_color.default_value = rgba' in script
    assert 'DISPLAY_LABEL_MATERIALS = DISPLAY.get("labelMaterials", {})' in script
    assert 'DISPLAY_LABEL_OPACITIES = DISPLAY.get("labelOpacities", {})' in script
    assert 'DISPLAY_ATOM_RADIUS_SCALES = DISPLAY.get("atomRadiusScales", {})' in script
    assert 'DISPLAY_ATOM_COLORS = DISPLAY.get("atomColors", {})' in script
    assert 'DISPLAY_ATOM_OPACITIES = DISPLAY.get("atomOpacities", {})' in script
    assert 'DISPLAY_ATOM_MATERIALS = DISPLAY.get("atomMaterials", {})' in script
    assert '"rubber": {"roughness": 0.88' in script
    assert 'metallic.default_value = surface["metalness"]' in script
    assert "'labelMaterials': {'H': 'metal'}" in script
    assert "'labelOpacities': {'H': 0.4}" in script
    assert "'atomRadiusScales': {'1': 1.25}" in script
    assert "'atomColors': {'1': '#33aa77'}" in script
    assert "'atomOpacities': {'1': 0.65}" in script
    assert "'atomMaterials': {'1': 'rubber'}" in script
    assert "'thickness': 0.18" in script
    assert "'atomBondStyles': {'1': {'material': 'rubber', 'opacity': 0.65}}" in script
    assert exported_data["visual_translation"] == pytest.approx([1.0, -0.5, 0.25])
    np.testing.assert_allclose(
        exported_data["positions"],
        atoms.positions + np.asarray([1.0, -0.5, 0.25]),
    )
    np.testing.assert_allclose(exported_data["cell"], atoms.cell.array)
    assert 'scene.render.engine = render_engine' in script
    assert 'INCLUDE_CELL = bool(DATA.get("include_cell", True))' in script
    assert 'if INCLUDE_CELL:\n    add_unit_cell(CELL)' in script
    compile(script, "v_ase_blender_scene.py", "exec")


def test_export_unit_cell_option_is_shared_across_geometry_and_render_outputs():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert 'id="export-include-cell"' in index_html
    assert 'id="export-cell"' in main_js
    assert 'id="video-cell"' in main_js
    assert "includeCell: source.includeCell ?? fallback.includeCell" in main_js
    assert "body.include_cell = includeCell !== false" in api_js
    assert "const includeCell = options.includeCell !== false" in renderer_js
    assert "child.userData?.supercellCellPreview" in renderer_js


def test_bond_appearance_controls_and_instanced_renderer_contract():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()

    assert 'id="bond-style"' in index_html
    assert '<option value="cylinder">Cylinder</option>' in index_html
    assert '<option value="flat">Flat ribbon</option>' in index_html
    assert 'id="bond-thickness"' in index_html
    assert 'id="bond-color-mode"' in index_html
    assert '<option value="split">Split atom colors</option>' in index_html
    assert '<option value="custom">Custom color</option>' in index_html
    assert 'id="bond-custom-color"' in index_html
    assert 'id="btn-bond-apply"' not in index_html
    assert "enabled.className = 'pairwise-bond-enabled'" in main_js
    assert 'className = `pairwise-bond-${field}`' in main_js
    assert "makeDistanceInput('max'" in main_js
    assert "makeDistanceInput('min'" not in main_js
    assert 'id="pairwise-label-column-resizer"' in index_html
    assert "setupPairwiseLabelColumnResizer" in main_js
    assert "pairwiseBondRanges" in main_js
    assert "pairwiseBondRanges" in renderer_js
    assert "bondStyle: 'cylinder'" in main_js
    assert "bondColorMode: 'split'" in main_js
    assert "captureBondSettingsFromControls" in main_js
    assert "bondCylinderGeometry" in renderer_js
    assert "bondFlatGeometry" in renderer_js
    assert "bondSegments" in renderer_js
    assert "segmentsByColor" in renderer_js
    assert "bondMaterial(flat ? 'flat' : 'cylinder', color)" in renderer_js
    assert "orientFlatBond" in renderer_js
    assert "setupInputCommitBehavior" in main_js
    assert "commitInputValue" in main_js


def test_pairwise_cutoff_export_is_label_keyed_and_zero_disables_the_pair():
    atoms = molecule("H2")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc(False)
    set_atom_labels(atoms, ["H_left", "H_right"])
    session = EditorSession("label-pair-export", atoms.copy(), atoms.copy())
    data = session_atoms_to_json(session)

    enabled = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondCutoffs": {"H_left-H_right": 1.0},
    })
    disabled = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondCutoffs": {"H_left-H_right": 0.0},
    })
    chemical_key_is_not_used = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondCutoffs": {"H-H": 1.0},
    })
    legacy_minimum_is_ignored = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondRanges": {
            "H_left-H_right": {"enabled": True, "min": 0.8, "max": 1.0}
        },
    })
    second_legacy_minimum_is_ignored = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "pairwise",
        "pairwiseBondRanges": {
            "H_left-H_right": {"enabled": True, "min": 0.6, "max": 1.0}
        },
    })

    assert len(enabled) == 1
    assert disabled == []
    assert chemical_key_is_not_used == []
    assert len(legacy_minimum_is_ignored) == 1
    assert len(second_legacy_minimum_is_ignored) == 1


def test_automatic_bond_export_matches_viewport_pair_class_rules():
    def exported_bonds(symbols, distance):
        atoms = Atoms(
            symbols=symbols,
            positions=[[0.0, 0.0, 0.0], [distance, 0.0, 0.0]],
            cell=[12.0, 12.0, 12.0],
            pbc=False,
        )
        session = EditorSession("automatic-bond-export", atoms.copy(), atoms.copy())
        return _display_bonds(
            session_atoms_to_json(session),
            {"showBonds": True, "bondMode": "auto"},
        )

    assert exported_bonds("H2", 0.74) == []
    assert exported_bonds("Cu2", 2.35) == []
    assert len(exported_bonds(["Cu", "O"], 2.20)) == 1


def test_legacy_pairwise_cutoff_map_replaces_stale_range_keys_during_export():
    atoms = Atoms(
        "H3",
        positions=[
            [0.0, 0.0, 0.0],
            [0.7, 0.0, 0.0],
            [0.0, 0.7, 0.0],
        ],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    set_atom_labels(atoms, ["H_a", "H_b", "H_c"])
    session = EditorSession("legacy-pair-map-export", atoms.copy(), atoms.copy())
    bonds = _display_bonds(
        session_atoms_to_json(session),
        {
            "showBonds": True,
            "bondMode": "pairwise",
            "pairwiseBondCutoffs": {"H_a-H_b": 0.8},
            "pairwiseBondRanges": {
                "H_a-H_b": {"enabled": False, "min": 0.0, "max": 0.0},
                "H_a-H_c": {"enabled": True, "min": 0.0, "max": 0.8},
            },
        },
    )

    assert [(bond["i"], bond["j"]) for bond in bonds] == [(0, 1)]


def test_bond_export_defaults_to_visible_cell_and_periodic_images_are_opt_in():
    atoms = molecule("H2")
    atoms.set_cell([10, 10, 10])
    atoms.set_pbc(True)
    atoms.positions[0] = [0.6, 0.0, 0.0]
    atoms.positions[1] = [9.4, 0.0, 0.0]
    session = EditorSession("bond-boundary-export", atoms.copy(), atoms.copy())
    data = session_atoms_to_json(session)

    direct = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "manual",
        "manualBondPairs": [[0, 1]],
        "showPeriodicBonds": False,
    })
    periodic = _display_bonds(data, {
        "showBonds": True,
        "bondMode": "manual",
        "manualBondPairs": [[0, 1]],
        "showPeriodicBonds": True,
    })

    assert direct[0]["length"] == pytest.approx(8.8)
    assert periodic[0]["length"] == pytest.approx(1.2)


def test_control_panel_uses_collapsible_default_hierarchy():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()

    assert 'id="btn-inspector-collapse"' in index_html
    assert '<body class="inspector-collapsed" data-viewport-background="white">' in index_html
    assert 'class="inspector-edge-chevron"' in index_html
    assert 'viewBox="0 0 14 20"' in index_html
    assert 'd="M1.6 4 12 10 1.6 16"' in index_html
    assert 'inspector-collapse-glyph' not in index_html
    assert '<strong>Workspace</strong>' not in index_html
    assert 'data-inspector-group="inspect"' in index_html
    assert 'data-inspector-group="structure"' in index_html
    assert 'data-inspector-group="analysis"' in index_html
    assert 'data-inspector-group="view"' in index_html
    assert 'data-inspector-group="export"' in index_html
    assert 'id="structure-section-select"' in index_html
    assert '<option value="appearance">Atoms &amp; Appearance</option>' in index_html
    assert '<option value="bonding">Bonding</option>' in index_html
    assert 'class="structure-section-nav"' not in index_html
    assert 'data-panel="structure-info" data-panel-group="inspect"' in index_html
    assert 'data-panel="selection" data-panel-group="inspect"' in index_html
    assert 'data-panel="view" data-panel-group="view"' in index_html
    assert 'data-panel="cell-replication" data-panel-group="structure"' in index_html
    assert 'data-panel="transform" data-panel-group="structure">' in index_html
    assert '<option value="transform">Transform &amp; Cell Match</option>' in index_html
    assert '<div class="prop-row" data-edit-only>' in index_html
    assert 'id="chk-commensurate-guide"' in index_html
    assert 'data-panel="appearance" data-panel-group="structure"' in index_html
    assert 'data-panel="bonding" data-panel-group="structure"' in index_html
    assert 'data-panel="export" data-panel-group="export"' in index_html
    assert 'data-panel="cell-transform" data-panel-group="structure" data-edit-only' in index_html
    assert 'data-panel="scientific-tools" data-panel-group="structure" data-edit-only' in index_html
    assert "setupInspectorNavigation" in main_js
    assert "setupStructureSectionNavigation" in main_js
    assert "let collapsed = true" in main_js
    assert "savedCollapsed === null ? true" in main_js
    assert "button.setAttribute('aria-label'" in main_js
    assert "glyph.textContent" not in main_js
    assert "body.inspector-collapsed" in style_css
    assert ".inspector-edge-toggle" in style_css
    assert "--inspector-width: 0px" in style_css
    assert "#inspector .group-hidden" in style_css
    assert "details:not([open]) > summary.section-header" in style_css
    assert "summary.section-header::after" in style_css


def test_studio_sun_and_periodic_bond_controls_are_opt_in_and_exportable():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()

    assert 'id="lighting-widget"' in index_html
    assert 'class="render-light-icon"' in index_html
    assert 'class="render-sphere-off"' in index_html
    assert 'class="render-sphere-on"' in index_html
    assert 'class="render-sphere-highlight"' in index_html
    assert 'class="render-sphere-shadow"' in index_html
    assert 'class="render-sphere-rim"' in index_html
    assert 'class="render-stop-off-highlight"' in index_html
    assert 'class="render-stop-on-light"' in index_html
    assert 'stop-color="#' not in index_html
    assert 'render-spot-' not in index_html
    assert 'render-light-cone' not in index_html
    assert 'render-light-beam' not in index_html
    assert 'class="sun-icon"' not in index_html
    assert index_html.index('id="calc-controls"') > index_html.index('data-panel="scientific-tools"')
    assert index_html.index('id="calc-controls"') > index_html.index('id="lighting-widget"')
    assert index_html.index('id="lighting-widget"') < index_html.index('id="btn-reset"')
    assert '<option value="modeling">Modeling</option>' in index_html
    assert '<option value="studio">Studio Sun</option>' in index_html
    assert '<option value="studio-shadow">Sun + Soft Shadow</option>' in index_html
    assert 'id="chk-sun-gizmo"' in index_html
    assert '<span>Direction source</span>' in index_html
    assert '<span>Direction target</span>' in index_html
    assert '<span>Direction handles</span>' in index_html
    assert 'id="chk-periodic-bonds"' in index_html
    assert "showPeriodicBonds: false" in main_js
    assert "lightingMode: 'modeling'" in main_js
    assert "setupLightingControls" in main_js
    assert "enterSunTransformMode" in main_js
    assert "applySunTransformPreview" in main_js
    assert "? -this.snapRotationAngle(this.transform.rotationAngle)" in main_js
    assert "currentLightingForExport" in main_js
    assert "startSunHandleDrag" not in renderer_js
    assert "export-render-mode" in main_js
    assert "sunPosition" in main_js
    assert "this.setSunSelected(sunHandle)" in main_js
    assert "if (handle === 'target') target.add(delta)" in main_js
    assert "position.add(delta);\n                target.add(delta);" in main_js
    assert "target.copy(position).add(targetOffset)" in main_js
    assert "position.copy(target).add(sourceOffset)" not in main_js
    assert "mode === 'ROTATE' || handle === 'source' ? position : target" in main_js
    assert "buildSunGizmo" in renderer_js
    assert "pickSunHandle" in renderer_js
    assert "updateSunTransform" in renderer_js
    assert "lightingStructureBounds" in renderer_js
    assert "semanticSunDirection" in renderer_js
    assert "applyStudioSunDirection" in renderer_js
    assert "sunHandle = 'source'" in renderer_js
    assert "sunHandle = 'target'" in renderer_js
    assert "this.studioSunLight.shadow.mapSize.set(2048, 2048)" in renderer_js
    assert "updateSunHandleDrag" not in renderer_js
    assert "if (lighting) body.lighting = lighting" in api_js
    assert "THREE.PCFSoftShadowMap" in renderer_js
    assert "this.renderer.shadowMap.enabled = false" in renderer_js
    assert "replicaSelectionOutlines" in renderer_js
    assert "replicaSelectionMutedMaterial" in renderer_js
    assert "equivalentReplicaSelectionReferences" in renderer_js
    assert "{ muted: true }" in main_js
    assert "supercellAtomReference" in renderer_js
    assert "selectionCount()" in main_js
    assert '<span>Tab / Esc</span><label>Open the control panel while it is collapsed</label>' in index_html
    assert '<span>Tab / Esc</span><label>Open the control panel while it is collapsed</label>' in main_js
    assert 'close the open control panel and return focus to the viewport' in index_html
    assert 'close the open control panel and return focus to the viewport' in main_js
    assert "this.setInspectorCollapsed(false);" in main_js
    assert '<span>Sun source + G</span><label>Move source and target together</label>' in main_js
    assert "bondDelta(i, j" in renderer_js
    assert "this.displayOptions.showPeriodicBonds" in renderer_js
    assert "data-periodic-bonds" not in index_html


def test_application_chrome_uses_one_role_based_palette():
    style_css = (ROOT / "v_ase/static/style.css").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    transform_js = (ROOT / "v_ase/static/transform.js").read_text()

    required_tokens = (
        "--neutral-900:",
        "--surface-hover:",
        "--teal-border:",
        "--amber-border:",
        "--red-border:",
        "--renderer-off-mid:",
        "--renderer-on-light:",
        "--renderer-specular:",
    )
    for token in required_tokens:
        assert token in style_css

    # Color literals belong to the dark and light palette declarations only.
    # Components consume semantic roles so new panels cannot drift into one-off
    # grey families.
    component_css = style_css.split("\n}\n", 1)[1]
    component_css = re.sub(
        r'html\[data-ui-theme="light"\]\s*\{.*?\}\s*',
        "",
        component_css,
        count=1,
        flags=re.DOTALL,
    )
    assert re.search(r"#[0-9A-Fa-f]{3,8}(?![0-9A-Za-z_-])", component_css) is None
    assert "rgba(" not in component_css
    assert ".repulsion-settings" in style_css
    assert "background: var(--field);" in style_css

    # Canvas, transform guides, and the orientation widget share the same axis
    # and neutral properties instead of maintaining separate color constants.
    assert "cssColor('--viewport-dark-bg', '#2d3333')" in renderer_js
    assert "cssColor('--viewport-light-bg', '#ffffff')" in renderer_js
    assert "cssColor('--axis-x', '#f05b55')" in renderer_js
    assert "['--axis-x', '#f05b55']" in transform_js
    assert "color: cssColor('--amber', '#f3be57')" in transform_js


def test_grid_guides_scale_to_large_unit_cells():
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert "desiredGuideSize" in renderer_js
    assert "replaceViewportGuides" in renderer_js
    assert "refreshViewportGuidesForStructure" in renderer_js
    assert "new THREE.GridHelper(guideSize, divisions" in renderer_js
    assert "[0, 0, -half], [0, 0, half]" in renderer_js


def test_rotate_pivot_and_commensurate_cell_matching_are_wired():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    transform_js = (ROOT / "v_ase/static/transform.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()
    server_py = (ROOT / "v_ase/server.py").read_text()
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    style_css = (ROOT / "v_ase/static/style.css").read_text()
    docs = (ROOT / "docs/unit_cell_aware_rotate.md").read_text()

    assert "rotate-pivot" in index_html
    assert "Active atom (last selected)" in index_html
    assert "Global origin" in index_html
    assert "Unit-cell center" in index_html
    assert "chk-commensurate-guide" in index_html
    assert "Magnetic angle snap" in index_html
    assert "commensurate-strain" in index_html
    assert "commensurate-max-index" in index_html
    assert "commensurate-snap-range" in index_html
    assert "make-supercell-matrix" in index_html
    assert "Apply make_supercell Matrix" in index_html
    assert "applyMakeSupercellMatrix" in main_js
    assert "parseSupercellMatrix" in main_js
    assert "applySupercellMatrix" in api_js
    assert "rotationPivotPosition" in main_js
    assert "activeRotationPivotIndex" in main_js
    assert "operation.pivot === 'active'" in main_js
    assert "prepareCommensurateRotation" in main_js
    assert "nearestCommensurateCandidate" in main_js
    assert "snapCommensurateAngle" in main_js
    assert "configureRotationReference" in main_js
    assert "updateRotationReferenceGuide" in main_js
    assert "v_ase_rotation_axis" in transform_js
    assert "v_ase_rotation_start_reference" in transform_js
    assert "v_ase_rotation_current_reference" in transform_js
    assert "setCommensurateGuides" in renderer_js
    assert "clearCommensurateGuides" in renderer_js
    assert "commensurateAngles" in api_js
    assert 'POST /api/commensurate' not in server_py
    assert '@app.post("/api/commensurate/{session_id}")' in server_py
    assert "Bond-strain guard" not in index_html
    assert "Rotate blocked:" not in main_js
    assert "data-rotate-invalid" not in style_css
    assert "H' = P H" in docs
    assert "ase.build.make_supercell" in docs
    assert "Q* = argmin" in docs
    assert "epsilon_guest" in docs
    assert "epsilon_host" in docs
    assert "10.1016/j.cpc.2015.08.038" in docs
    assert "10.1021/acs.jpcc.6b01496" in docs
    assert "10.1073/pnas.1108174108" in docs


def test_fixed_plane_motion_guide_is_per_atom_and_transform_scoped():
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()

    assert "setConstraintMotionGuides" in main_js
    assert "clearConstraintMotionGuides" in main_js
    assert "v_ase_constraint_motion_guides" in renderer_js
    assert "fixed_plane_motion" in renderer_js
    assert "fixedPlaneMotionSurface" in renderer_js
    assert "fixedPlaneMotionPerimeter" in renderer_js
    assert "fixedPlaneMotionAxis" in renderer_js


def test_displacement_analysis_uses_instancing_and_frame_scoped_requests():
    index_html = (ROOT / "v_ase/static/index.html").read_text()
    main_js = (ROOT / "v_ase/static/main.js").read_text()
    renderer_js = (ROOT / "v_ase/static/renderer.js").read_text()
    api_js = (ROOT / "v_ase/static/api.js").read_text()

    assert 'data-inspector-group="analysis"' in index_html
    assert 'data-panel="displacement" data-panel-group="analysis"' in index_html
    assert 'id="chk-displacement-mic"' in index_html
    assert 'id="displacement-reference-mode"' in index_html
    assert '<option value="previous">Previous frame</option>' in index_html
    assert '<option value="frame">Specific frame</option>' in index_html
    assert '<option value="2d">2D flat arrow</option>' in index_html
    assert "scheduleDisplacementAnalysisRefresh" in main_js
    assert "fetchDisplacements" in api_js
    assert "frame_index: this.currentFrameIndex()" in api_js
    assert "new THREE.InstancedMesh(" in renderer_js
    assert "displacementGroup" in renderer_js
    assert "updateDisplacementVectorMatrices" in renderer_js
    assert "displacementCameraSignature" in renderer_js
    assert "this.supercellTranslations(cell, repetitions)" in renderer_js
    assert "const visibleStart = this.atomMeshByIndex.get(index)?.position" in renderer_js


def test_transform_panel_can_apply_an_exact_selection_rotation():
    index_html = (ROOT / "v_ase" / "static" / "index.html").read_text()
    main_js = (ROOT / "v_ase" / "static" / "main.js").read_text()

    assert 'id="selection-rotate-axis"' in index_html
    assert 'id="selection-rotate-angle"' in index_html
    assert 'id="btn-rotate-selection-exact"' in index_html
    assert "async rotateSelectionFromPanel()" in main_js
    assert "this.enterTransformMode('ROTATE')" in main_js
    assert "this.transform.buffer = String(angleDegrees)" in main_js
    assert "await this.commitTransform()" in main_js


def test_live_commensurate_candidate_selection_avoids_array_sorting():
    main_js = (ROOT / "v_ase" / "static" / "main.js").read_text()
    angle_selector = main_js.split(
        "commensurateCandidateAtAngle(angleDeg = 0)", 1
    )[1].split("commensurateSmallestCandidate()", 1)[0]
    smallest_selector = main_js.split(
        "commensurateSmallestCandidate()", 1
    )[1].split("useCommensurateSuggestedAngle", 1)[0]

    assert ".sort(" not in angle_selector
    assert ".sort(" not in smallest_selector
    assert "for (const candidate of this.state.commensurateCandidates || [])" in angle_selector
    assert "for (const candidate of this.state.commensurateCandidates || [])" in smallest_selector


def test_add_atoms_uses_the_shared_relaxation_controls_only():
    main_js = (ROOT / "v_ase" / "static" / "main.js").read_text(encoding="utf-8")
    index_html = (ROOT / "v_ase" / "static" / "index.html").read_text(encoding="utf-8")

    assert 'id="btn-add-atoms-open-relaxation"' in index_html
    assert 'id="btn-relax"' in index_html
    assert 'id="calc-device"' in index_html
    assert 'id="add-atoms-device"' not in index_html
    assert 'id="add-atoms-pair-table"' not in index_html
    assert "this.calculatorPayloadWithOverrides(calculatorOverrides)" in main_js
    assert "document.getElementById('relax-fmax')?.value" in main_js
    assert "document.getElementById('relax-steps')?.value" in main_js
    assert "refreshAddAtomsPairCutoffs" not in main_js
