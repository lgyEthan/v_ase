import base64
import io
import math
import hashlib
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from ase.constraints import FixAtoms, FixedLine, FixedPlane, FixScaled
from ase.io import write
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from examples.readme_scenes import make_ai_pyridinic_graphene_scene
from v_ase.io import set_atom_labels
from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


def _expand_inspector(page):
    if page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')"):
        page.click('#btn-inspector-collapse')
        page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
        page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")


def _open_panel(page, panel):
    details = page.locator(f'[data-panel="{panel}"]')
    if not details.evaluate("element => element.open"):
        details.locator('summary').click()


def _select_structure_section(page, section):
    page.click('[data-inspector-group="structure"]')
    page.select_option("#structure-section-select", section)
    page.wait_for_function(
        """section => {
            const panel = document.querySelector(`[data-panel="${section}"]`);
            if (!panel) return false;
            const inspector = document.getElementById('inspector');
            const inspectorRect = inspector.getBoundingClientRect();
            const panelRect = panel.getBoundingClientRect();
            return panel.open
                && panelRect.bottom >= inspectorRect.top
                && panelRect.top <= inspectorRect.bottom;
        }""",
        arg=section,
    )


def test_exact_selection_rotation_panel_commits_and_undoes_backend_coordinates():
    atoms = Atoms(
        "P3",
        positions=[
            [1.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
        ],
        cell=[10.0, 10.0, 10.0],
        pbc=False,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.addSelectionReference(0);
                app.addSelectionReference(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")

            _expand_inspector(page)
            _select_structure_section(page, "transform")
            page.select_option("#rotate-pivot", "selection")
            page.select_option("#selection-rotate-axis", "Z")
            page.fill("#selection-rotate-angle", "90")
            page.click("#btn-rotate-selection-exact")
            page.wait_for_function("""() => {
                const positions = window.__ASE_APP__.state.atoms.positions;
                return Math.abs(positions[0][0] - 2) < 1e-6
                    && Math.abs(positions[0][1] + 1) < 1e-6
                    && Math.abs(positions[1][0] - 2) < 1e-6
                    && Math.abs(positions[1][1] - 1) < 1e-6;
            }""")
            rotated = page.evaluate("window.__ASE_APP__.state.atoms.positions")
            assert np.asarray(rotated) == pytest.approx(
                np.asarray([[2.0, -1.0, 0.0], [2.0, 1.0, 0.0], [0.0, 5.0, 0.0]]),
                abs=1e-6,
            )

            page.locator("#app-viewport canvas").focus()
            page.keyboard.press("Control+z")
            page.wait_for_function("""() => {
                const positions = window.__ASE_APP__.state.atoms.positions;
                return Math.abs(positions[0][0] - 1) < 1e-6
                    && Math.abs(positions[0][1]) < 1e-6
                    && Math.abs(positions[1][0] - 3) < 1e-6
                    && Math.abs(positions[1][1]) < 1e-6;
            }""")

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.addSelectionReference(0);
                app.addSelectionReference(1);
                app.addSelectionReference(2);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.select_option("#rotate-pivot", "active")
            pivot = page.evaluate(
                "window.__ASE_APP__.rotationPivotPosition([0, 1, 2]).toArray()"
            )
            assert pivot == pytest.approx([0.0, 5.0, 0.0])

            page.fill("#selection-rotate-angle", "90")
            page.click("#btn-rotate-selection-exact")
            page.wait_for_function("""() => {
                const positions = window.__ASE_APP__.state.atoms.positions;
                return Math.abs(positions[0][0] - 5) < 1e-6
                    && Math.abs(positions[0][1] - 6) < 1e-6
                    && Math.abs(positions[1][0] - 5) < 1e-6
                    && Math.abs(positions[1][1] - 8) < 1e-6
                    && Math.abs(positions[2][0]) < 1e-6
                    && Math.abs(positions[2][1] - 5) < 1e-6;
            }""")
            browser.close()
    finally:
        editor.close()


def test_fixed_plane_move_restores_per_atom_motion_plane_guide():
    atoms = Atoms(
        "LiOH",
        positions=[
            [0.0, 0.0, 0.0],
            [2.2, 0.0, 0.0],
            [2.8, 0.7, 0.0],
        ],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    atoms.set_constraint(FixedPlane(0, [0, 0, 1]))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")

            state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.selected = new Set([0]);
                app.updateSelectionVisuals();
                app.enterTransformMode('MOVE');
                app.transform.setAxis('X', app.renderer.camera);
                app.transform.buffer = '1.25';
                app.applyTransformPreview();
                const guide = app.renderer.constraintMotionGuideGroup.children[0];
                return {
                    atom: app.renderer.atomMeshByIndex.get(0).position.toArray(),
                    persistent: app.renderer.constraintGuideGroup.children.length,
                    motionVisible: app.renderer.constraintMotionGuideGroup.visible,
                    motionCount: app.renderer.constraintMotionGuideGroup.children.length,
                    motionKind: guide?.userData?.kind,
                    motionIndex: guide?.userData?.atomIndex,
                    motionAnchor: guide?.userData?.anchor,
                    surfaces: guide?.children.filter(
                        child => child.userData?.fixedPlaneMotionSurface
                    ).length,
                    surfaceVisible: guide?.children.find(
                        child => child.userData?.fixedPlaneMotionSurface
                    )?.visible,
                    perimeters: guide?.children.filter(
                        child => child.userData?.fixedPlaneMotionPerimeter
                    ).length,
                    axes: guide?.children.filter(
                        child => child.userData?.fixedPlaneMotionAxis
                    ).length
                };
            }""")
            assert state["atom"] == pytest.approx([1.25, 0.0, 0.0])
            assert state["persistent"] == 1
            assert state["motionVisible"] is True
            assert state["motionCount"] == 1
            assert state["motionKind"] == "fixed_plane_motion"
            assert state["motionIndex"] == 0
            assert state["motionAnchor"] == pytest.approx([0.0, 0.0, 0.0])
            assert state["surfaces"] == 1
            assert state["surfaceVisible"] is True
            assert state["perimeters"] == 1
            assert state["axes"] == 2

            page.evaluate("window.__ASE_APP__.cancelTransform()")
            assert page.evaluate(
                "window.__ASE_APP__.renderer.constraintMotionGuideGroup.children.length"
            ) == 0
            browser.close()
    finally:
        editor.close()


def test_line_constraints_use_one_center_axis_and_move_guide_while_only_planes_use_rings():
    atoms = Atoms(
        "Li4",
        positions=[
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [4.0, 0.0, 0.0],
            [6.0, 0.0, 0.0],
        ],
        cell=[[8.0, 0.0, 0.0], [0.8, 7.0, 0.0], [0.4, 0.6, 6.0]],
        pbc=True,
    )
    atoms.set_constraint([
        FixedLine(0, [0, 0, 1]),
        FixedPlane(1, [0, 0, 1]),
        FixScaled(2, [True, True, False]),
        FixScaled(3, [True, False, False]),
    ])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.constraintGuideGroup?.children?.length === 4"
            )

            guides = page.evaluate("""() => (
                window.__ASE_APP__.renderer.constraintGuideGroup.children
                    .map(group => ({
                        index: group.userData.constraintGuideFor,
                        kind: group.userData.kind,
                        rings: group.children.filter(
                            child => child.geometry?.type === 'RingGeometry'
                        ).length,
                        axes: group.children.filter(
                            child => child.userData?.fixedLineAxis
                        ).length
                    }))
                    .sort((left, right) => left.index - right.index)
            )""")
            assert guides == [
                {"index": 0, "kind": "fixed_line", "rings": 0, "axes": 1},
                {"index": 1, "kind": "fixed_plane", "rings": 1, "axes": 0},
                {"index": 2, "kind": "fixed_line", "rings": 0, "axes": 1},
                {"index": 3, "kind": "fixed_plane", "rings": 1, "axes": 0},
            ]

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.selected = new Set([0]);
                app.updateSelectionVisuals();
            }""")
            selection_geometry = page.evaluate("""() => (
                window.__ASE_APP__.renderer.selectionOutlines.children.map(
                    child => child.geometry?.type || ''
                )
            )""")
            assert selection_geometry == ["SphereGeometry"]

            motion = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.enterTransformMode('MOVE');
                const guide = app.renderer.constraintMotionGuideGroup.children[0];
                return {
                    count: app.renderer.constraintMotionGuideGroup.children.length,
                    kind: guide?.userData?.kind,
                    index: guide?.userData?.atomIndex,
                    anchor: guide?.userData?.anchor,
                    direction: guide?.userData?.direction,
                    axes: guide?.children.filter(
                        child => child.userData?.fixedLineMotionAxis
                    ).length
                };
            }""")
            assert motion == {
                "count": 1,
                "kind": "fixed_line_motion",
                "index": 0,
                "anchor": [0.0, 0.0, 0.0],
                "direction": [0.0, 0.0, 1.0],
                "axes": 1,
            }
            page.evaluate("window.__ASE_APP__.cancelTransform()")
            browser.close()
    finally:
        editor.close()


def test_axis_shortcuts_restore_canonical_roll_before_opposite_view():
    atoms = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.75, 0.0, 0.0]],
        cell=[6.0, 6.0, 6.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            canvas = page.locator("#app-viewport canvas")

            for axis, canonical_direction, canonical_up in (
                ("x", [1, 0, 0], [0, 0, 1]),
                ("y", [0, 1, 0], [0, 0, 1]),
                ("z", [0, 0, 1], [0, 1, 0]),
            ):
                page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const camera = app.renderer.camera;
                    const target = app.renderer.controls.target;
                    const distance = Math.max(camera.position.distanceTo(target), 4);
                    camera.position.copy(target).add(
                        new camera.position.constructor(0.41, -0.63, 0.66)
                            .normalize()
                            .multiplyScalar(distance)
                    );
                    camera.up.set(0.2, 0.9, 0.35).normalize();
                    app.completeCameraViewChange('test-noncanonical-view');
                }""")
                canvas.focus()
                page.keyboard.press(axis)
                canonical = page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const basis = app.cameraViewBasis();
                    return {
                        direction: basis.offset.clone().normalize().toArray(),
                        up: basis.up.toArray()
                    };
                }""")
                assert canonical["direction"] == pytest.approx(canonical_direction, abs=1e-8)
                assert canonical["up"] == pytest.approx(canonical_up, abs=1e-8)

                page.evaluate("window.__ASE_APP__.rotateCameraView('roll-cw', 37)")
                rolled = page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const basis = app.cameraViewBasis();
                    return {
                        direction: basis.offset.clone().normalize().toArray(),
                        up: basis.up.toArray()
                    };
                }""")
                assert rolled["direction"] == pytest.approx(canonical_direction, abs=1e-8)
                assert rolled["up"] != pytest.approx(canonical_up, abs=1e-4)

                canvas.focus()
                page.keyboard.press(axis)
                restored = page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const basis = app.cameraViewBasis();
                    return {
                        direction: basis.offset.clone().normalize().toArray(),
                        up: basis.up.toArray()
                    };
                }""")
                assert restored["direction"] == pytest.approx(canonical_direction, abs=1e-8)
                assert restored["up"] == pytest.approx(canonical_up, abs=1e-8)

                page.keyboard.press(axis)
                opposite = page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const basis = app.cameraViewBasis();
                    return {
                        direction: basis.offset.clone().normalize().toArray(),
                        up: basis.up.toArray()
                    };
                }""")
                assert opposite["direction"] == pytest.approx(
                    [-value for value in canonical_direction],
                    abs=1e-8,
                )
                assert opposite["up"] == pytest.approx(canonical_up, abs=1e-8)
            browser.close()
    finally:
        editor.close()


def test_ai_semantic_graphene_defect_edit_matches_documented_cif():
    source, expected, metadata = make_ai_pyridinic_graphene_scene()
    port = find_free_port()
    editor = view(
        source,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(editor.url)
            page.wait_for_function("window.v_aseAI")

            final = page.evaluate(
                """async ({vacancy, neighbors, liPosition}) => {
                    const ai = window.v_aseAI;
                    await ai.ready();
                    await ai.apply({
                        mode: 'edit',
                        selection: {clear: true, indices: [vacancy]},
                        operation: {
                            name: 'delete-selection',
                            indices: [vacancy]
                        }
                    });
                    await ai.apply({
                        selection: {clear: true, indices: neighbors},
                        operation: {
                            name: 'set-identity',
                            indices: neighbors,
                            label: 'N_pyridinic',
                            element: 'N'
                        }
                    });
                    await ai.apply({
                        operation: {
                            name: 'add-atom',
                            label: 'Li_site',
                            element: 'Li',
                            position: liPosition
                        }
                    });
                    await ai.apply({
                        display: {
                            showBonds: true,
                            showGrid: false,
                            showAxes: false,
                            viewportBackground: 'white',
                            lightingMode: 'studio-shadow',
                            labelColors: {
                                C: '#686d73',
                                N_pyridinic: '#3157d5',
                                Li_site: '#8f4fd6'
                            },
                            labelMaterials: {
                                C: 'standard',
                                N_pyridinic: 'metal',
                                Li_site: 'metal'
                            }
                        },
                        quality: {
                            antiAliasing: true,
                            sphereQuality: 'ultra'
                        },
                        camera: {axis: '+Z', fit: 'structure'}
                    });
                    return await ai.describe({includePositions: true});
                }""",
                {
                    "vacancy": metadata["vacancy_index"],
                    "neighbors": metadata["neighbors_after"],
                    "liPosition": metadata["li_position"],
                },
            )
            assert final["atomCount"] == len(expected) == 72
            assert np.allclose(
                np.asarray(final["positions"], dtype=float),
                expected.positions,
                atol=1e-8,
                rtol=0,
            )
            assert final["chemicalSymbols"] == expected.get_chemical_symbols()
            assert final["labels"].count("N_pyridinic") == 3
            assert final["labels"].count("Li_site") == 1
            assert final["chemicalSymbols"].count("N") == 3
            assert final["chemicalSymbols"].count("Li") == 1
            assert [item["index"] for item in final["selection"]] == metadata[
                "neighbors_after"
            ]

            rendered = page.evaluate("""async () => {
                const image = await window.v_aseAI.render({
                    format: 'png',
                    width: 420,
                    height: 420,
                    options: {
                        includeGrid: false,
                        includeAxes: false,
                        includeCell: true,
                        backgroundColor: '#ffffff',
                        renderMode: 'studio-shadow',
                        sphereQuality: 'ultra'
                    }
                });
                return {
                    width: image.width,
                    height: image.height,
                    bytes: image.bytes,
                    dataUrl: image.dataUrl
                };
            }""")
            assert rendered["width"] == 420
            assert rendered["height"] == 420
            assert rendered["bytes"] > 0
            image_bytes = base64.b64decode(rendered["dataUrl"].split(",", 1)[1])
            with Image.open(io.BytesIO(image_bytes)) as image:
                assert image.size == (420, 420)
                pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
            assert float(pixels.std()) > 12.0
            browser.close()
    finally:
        editor.close()


def test_human_gui_changes_stream_to_agent_and_revision_guard_prevents_overwrite():
    atoms = Atoms(
        "H2",
        positions=[[0, 0, 0], [0.74, 0, 0]],
        cell=[8, 8, 8],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(editor.url)
            page.wait_for_function("window.v_aseAI")
            initial = page.evaluate(
                "async () => { await window.v_aseAI.ready(); return await window.v_aseAI.describe(); }"
            )
            initial_revision = initial["collaboration"]["revision"]
            assert initial_revision >= 1

            agent_state = page.evaluate(
                """async revision => await window.v_aseAI.apply({
                    expectedRevision: revision,
                    selection: {clear: true, indices: [0]},
                    display: {showGrid: false}
                })""",
                initial_revision,
            )
            agent_revision = agent_state["collaboration"]["revision"]
            assert agent_revision > initial_revision

            editor_page = next(
                frame for frame in page.frames
                if "workspace_child=1" in frame.url
            )
            editor_page.evaluate("""() => {
                const input = document.getElementById('viewport-background');
                input.value = 'dark';
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            editor_page.wait_for_function(
                "revision => window.__ASE_APP__.collaborationRevision > revision",
                arg=agent_revision,
            )
            human_revision = editor_page.evaluate(
                "() => window.__ASE_APP__.collaborationRevision"
            )
            events = page.evaluate(
                """async ({sessionId, after}) => {
                    const response = await fetch(
                        `/api/ai/events/${encodeURIComponent(sessionId)}?after=${after}&timeout=0`
                    );
                    return await response.json();
                }""",
                {"sessionId": editor.session_id, "after": agent_revision},
            )
            human_events = [
                event for event in events["events"]
                if event["source"] == "human"
            ]
            assert human_events
            assert human_events[-1]["revision"] == human_revision
            assert "display" in human_events[-1]["categories"]
            assert "display.viewportBackground" in human_events[-1]["changed_paths"]

            conflict = page.evaluate(
                """async revision => {
                    try {
                        await window.v_aseAI.apply({
                            expectedRevision: revision,
                            camera: {axis: '+Z'}
                        });
                        return null;
                    } catch (error) {
                        return error.message;
                    }
                }""",
                agent_revision,
            )
            assert "Collaboration revision conflict" in conflict

            latest = page.evaluate(
                "async () => await window.v_aseAI.describe({includePositions: false})"
            )
            recovered = page.evaluate(
                """async revision => await window.v_aseAI.apply({
                    expectedRevision: revision,
                    camera: {axis: '+Z'}
                })""",
                latest["collaboration"]["revision"],
            )
            assert recovered["collaboration"]["revision"] > human_revision
            browser.close()
    finally:
        editor.close()


def test_real_cli_stdout_stream_reports_human_gui_change(tmp_path):
    structure = tmp_path / "collaboration.xyz"
    write(
        structure,
        Atoms(
            "H2",
            positions=[[0, 0, 0], [0.74, 0, 0]],
            cell=[8, 8, 8],
            pbc=True,
        ),
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-m",
            "v_ase.cli",
            "gui",
            str(structure),
            "--cli",
            "--interactive",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_lines: queue.Queue[str] = queue.Queue()

    def read_stdout():
        assert process.stdout is not None
        for line in process.stdout:
            stdout_lines.put(line)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    try:
        handshake = json.loads(stdout_lines.get(timeout=20))
        assert handshake["protocol"] == "v_ase.ai.v1"
        assert handshake["event_delivery"] == "ndjson-after-handshake"

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            page.evaluate("async () => await window.v_aseAI.ready()")
            editor_page = next(
                frame for frame in page.frames
                if "workspace_child=1" in frame.url
            )
            editor_page.evaluate("""() => {
                const input = document.getElementById('viewport-background');
                input.value = 'dark';
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")

            human_event = None
            seen_events = []
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    event = json.loads(
                        stdout_lines.get(timeout=max(0.1, deadline - time.monotonic()))
                    )
                except queue.Empty:
                    break
                seen_events.append(event)
                if event.get("source") == "human" and "display" in event.get("categories", []):
                    human_event = event
                    break
            browser.close()

        assert human_event is not None, seen_events
        assert human_event["protocol"] == "v_ase.collaboration.v1"
        assert human_event["session_id"] == handshake["session_id"]
        assert "display.viewportBackground" in human_event["changed_paths"]
        assert human_event["state_url"].endswith(
            f"/api/ai/state/{handshake['session_id']}"
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_ai_bridge_screen_relative_camera_and_constraint_vector_workflow():
    lattice = 2.46
    atoms = Atoms(
        "BN",
        scaled_positions=[[0, 0, 0.5], [1 / 3, 2 / 3, 0.5]],
        cell=[
            [lattice, 0, 0],
            [0.5 * lattice, math.sqrt(3) * lattice * 0.5, 0],
            [0, 0, 14],
        ],
        pbc=[True, True, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(editor.url)
            page.wait_for_function("window.v_aseAI")

            ready = page.evaluate("async () => await window.v_aseAI.ready()")
            assert ready["protocol"] == "v_ase.ai.v1"
            assert ready["ready"] is True
            editor_page = next(
                frame for frame in page.frames
                if "workspace_child=1" in frame.url
            )
            defaults = editor_page.evaluate("""() => ({
                bonds: document.getElementById('chk-bonds').checked,
                guide: document.getElementById('chk-commensurate-guide').checked,
                snap: document.getElementById('chk-commensurate-snap').checked
            })""")
            assert defaults == {"bonds": True, "guide": True, "snap": False}
            helix = editor_page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const points = renderer.makeHelicalSpringPoints(0, 3, 0.2, 7, 98);
                const xs = points.map(point => point.x);
                const zs = points.map(point => point.z);
                return {
                    points: points.length,
                    xSpan: Math.max(...xs) - Math.min(...xs),
                    zSpan: Math.max(...zs) - Math.min(...zs),
                    materialType: renderer.constraintMaterials.hookean.type,
                    wireRadius: renderer.hookeanSpringWireRadius()
                };
            }""")
            assert helix["points"] >= 100
            assert helix["xSpan"] > 0.38
            assert helix["zSpan"] > 0.38
            assert helix["materialType"] == "MeshStandardMaterial"
            assert helix["wireRadius"] == pytest.approx(0.022)

            result = page.evaluate("""async () => await window.v_aseAI.apply({
                display: {
                    showBonds: true,
                    showGrid: false,
                    viewportBackground: 'white',
                    atomDisplayMode: '2d'
                },
                quality: {antiAliasing: false, sphereQuality: 'low'},
                camera: {axis: '+Z', fit: 'structure'},
                selection: {clear: true, indices: [0]}
            })""")
            assert result["atomCount"] == 2
            assert result["selection"][0]["index"] == 0
            assert result["camera"]["projection"] == "orthographic"
            assert result["display"]["showBonds"] is True
            assert result["display"]["antiAliasing"] is False
            assert result["display"]["sphereQuality"] == "low"
            assert editor_page.evaluate("""() => ({
                antiAliasing: window.__ASE_APP__.renderer.displayOptions.antiAliasing,
                sphereQuality: window.__ASE_APP__.renderer.displayOptions.sphereQuality
            })""") == {"antiAliasing": False, "sphereQuality": "low"}

            axis_views = page.evaluate("""async () => {
                const snapshots = {};
                for (const axis of ['+X', '-X', '+Y', '-Y', '+Z', '-Z']) {
                    snapshots[axis] = (
                        await window.v_aseAI.apply({
                            camera: {axis, fit: 'structure'}
                        })
                    ).camera;
                }
                await window.v_aseAI.apply({
                    camera: {axis: '+Z', fit: 'structure'}
                });
                return snapshots;
            }""")
            expected_axes = {
                "+X": [1, 0, 0],
                "-X": [-1, 0, 0],
                "+Y": [0, 1, 0],
                "-Y": [0, -1, 0],
                "+Z": [0, 0, 1],
                "-Z": [0, 0, -1],
            }
            for axis, expected in expected_axes.items():
                position = np.asarray(axis_views[axis]["position"], dtype=float)
                target = np.asarray(axis_views[axis]["target"], dtype=float)
                direction = position - target
                direction /= np.linalg.norm(direction)
                assert direction.tolist() == pytest.approx(expected, abs=1e-8)

            rendered = page.evaluate("""async () => {
                const image = await window.v_aseAI.render({
                    format: 'png',
                    width: 320,
                    height: 240,
                    options: {
                        includeGrid: false,
                        includeAxes: false,
                        includeCell: true,
                        backgroundColor: '#ffffff'
                    }
                });
                const loaded = await new Promise((resolve, reject) => {
                    const element = new Image();
                    element.onload = () => resolve([element.naturalWidth, element.naturalHeight]);
                    element.onerror = reject;
                    element.src = image.dataUrl;
                });
                return {
                    protocol: image.protocol,
                    mimeType: image.mimeType,
                    filename: image.filename,
                    bytes: image.bytes,
                    dimensions: loaded,
                    prefix: image.dataUrl.slice(0, 22)
                };
            }""")
            assert rendered["protocol"] == "v_ase.ai.v1"
            assert rendered["mimeType"] == "image/png"
            assert rendered["filename"] == "v_ase-render.png"
            assert rendered["bytes"] > 0
            assert rendered["dimensions"] == [320, 240]
            assert rendered["prefix"] == "data:image/png;base64,"

            compact_rendered = page.evaluate("""async () => {
                const image = await window.v_aseAI.render({
                    width: 320,
                    height: 240,
                    format: 'webp',
                    options: {
                        includeGrid: false,
                        includeAxes: false,
                        includeCell: true,
                        backgroundColor: '#ffffff'
                    }
                });
                const loaded = await new Promise((resolve, reject) => {
                    const element = new Image();
                    element.onload = () => resolve([element.naturalWidth, element.naturalHeight]);
                    element.onerror = reject;
                    element.src = image.dataUrl;
                });
                return {
                    format: image.format,
                    mimeType: image.mimeType,
                    bytes: image.bytes,
                    dimensions: loaded,
                    prefix: image.dataUrl.slice(0, 23)
                };
            }""")
            assert compact_rendered["format"] == "webp"
            assert compact_rendered["mimeType"] == "image/webp"
            assert compact_rendered["bytes"] > 0
            assert compact_rendered["bytes"] < rendered["bytes"]
            assert compact_rendered["dimensions"] == [320, 240]
            assert compact_rendered["prefix"] == "data:image/webp;base64,"

            image_export = page.evaluate("""async () => {
                const image = await window.v_aseAI.export({
                    format: 'image',
                    imageFormat: 'png',
                    width: 256,
                    height: 256,
                    options: {includeGrid: false, includeAxes: false}
                });
                return {
                    exportFormat: image.exportFormat,
                    format: image.format,
                    filename: image.filename,
                    bytes: image.bytes,
                    prefix: image.dataUrl.slice(0, 22)
                };
            }""")
            assert image_export["exportFormat"] == "image"
            assert image_export["format"] == "png"
            assert image_export["filename"] == "v_ase-render.png"
            assert image_export["bytes"] > 0
            assert image_export["prefix"] == "data:image/png;base64,"

            capabilities = page.evaluate("async () => await window.v_aseAI.capabilities()")
            assert set(
                [
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
                    "undo",
                    "redo",
                    "reset-coordinates",
                    "start-relaxation",
                    "stop-relaxation",
                    "refresh-displacements",
                ]
            ).issubset(capabilities["operations"])
            assert {"image", "video", "poscar", "pickle", "blender", "3dm", "obj", "html", "project", "settings"}.issubset(
                capabilities["exports"]
            )

            moved = page.evaluate("""async () => {
                await window.v_aseAI.apply({mode: 'edit'});
                await window.v_aseAI.apply({
                    selection: {clear: true, indices: [1]},
                    operation: {
                        name: 'move-selection',
                        vector: [0.1, 0.2, 0.0],
                        applyConstraints: true
                    }
                });
                return await window.v_aseAI.describe();
            }""")
            assert moved["positions"][1] == pytest.approx(
                (atoms.positions[1] + np.array([0.1, 0.2, 0.0])).tolist(),
                abs=1e-8,
            )
            page.evaluate("async () => await window.v_aseAI.apply({operation: 'undo'})")
            restored_position = page.evaluate(
                "async () => (await window.v_aseAI.describe()).positions[1]"
            )
            assert restored_position == pytest.approx(atoms.positions[1].tolist(), abs=1e-8)

            active_rotated = page.evaluate("""async () => {
                await window.v_aseAI.apply({
                    operation: {
                        name: 'rotate-selection',
                        indices: [1, 0],
                        axis: [0, 0, 1],
                        angleDeg: 90,
                        pivot: 'active',
                        applyConstraints: true
                    }
                });
                return await window.v_aseAI.describe({includePositions: true});
            }""")
            pivot = atoms.positions[0]
            relative = atoms.positions[1] - pivot
            expected_active = pivot + np.array([-relative[1], relative[0], relative[2]])
            assert active_rotated["positions"][0] == pytest.approx(pivot.tolist(), abs=1e-8)
            assert active_rotated["positions"][1] == pytest.approx(expected_active.tolist(), abs=1e-8)
            page.evaluate("async () => await window.v_aseAI.apply({operation: 'undo'})")

            page.evaluate(
                "async () => await window.v_aseAI.apply({selection: {clear: true, indices: [0]}})"
            )

            exported = page.evaluate("""async () => {
                const result = await window.v_aseAI.export({format: 'poscar'});
                return {
                    format: result.format,
                    filename: result.filename,
                    mimeType: result.mimeType,
                    bytes: result.bytes,
                    prefix: result.dataUrl.slice(0, 37)
                };
            }""")
            assert exported["format"] == "poscar"
            assert exported["filename"] == "POSCAR"
            assert exported["bytes"] > 0
            assert exported["prefix"].startswith("data:application/octet-stream;base64,")

            obj_export = page.evaluate("""async () => {
                const result = await window.v_aseAI.export({
                    format: 'obj',
                    includeCell: true
                });
                return {
                    format: result.format,
                    filename: result.filename,
                    mimeType: result.mimeType,
                    bytes: result.bytes,
                    prefix: result.dataUrl.slice(0, 28)
                };
            }""")
            assert obj_export["format"] == "obj"
            assert obj_export["filename"] == "v_ase_obj_scene.zip"
            assert obj_export["mimeType"] == "application/zip"
            assert obj_export["bytes"] > 0
            assert obj_export["prefix"].startswith("data:application/zip;base64,")

            _expand_inspector(editor_page)
            _select_structure_section(editor_page, "constraints")
            editor_page.select_option("#constraint-kind", "fixed_line")
            x_input = editor_page.locator("#constraint-x")
            x_input.fill("0")
            x_input.press("Tab")
            assert editor_page.locator("#constraint-y").is_enabled()
            editor_page.locator("#constraint-y").fill("0")
            editor_page.locator("#constraint-y").press("Tab")
            assert editor_page.locator("#constraint-z").is_enabled()
            editor_page.locator("#constraint-z").fill("1")
            editor_page.locator("#constraint-z").press("Tab")
            draft = editor_page.evaluate("""() => ({
                kind: document.getElementById('constraint-kind').value,
                values: ['constraint-x', 'constraint-y', 'constraint-z'].map(
                    id => document.getElementById(id).value
                ),
                disabled: ['constraint-x', 'constraint-y', 'constraint-z'].map(
                    id => document.getElementById(id).disabled
                )
            })""")
            assert draft == {
                "kind": "fixed_line",
                "values": ["0", "0", "1"],
                "disabled": [False, False, False],
            }
            editor_page.click("#btn-apply-constraint")
            editor_page.wait_for_function("""() => {
                const line = window.__ASE_APP__.state.atoms.constraints.fixed_line?.['0'];
                return Array.isArray(line) && line.join(',') === '0,0,1';
            }""")

            baseline = editor_page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                const target = app.renderer.controls.target;
                const distance = Math.max(camera.position.distanceTo(target), 4);
                camera.position.copy(target).add(
                    new camera.position.constructor(0.38, -0.71, 0.59)
                        .normalize().multiplyScalar(distance)
                );
                camera.up.set(0.61, 0.45, 0.65).normalize();
                camera.lookAt(target);
                app.rotateCameraView('roll-cw', 31);
                app.completeCameraViewChange('arbitrary-screen-basis');
                return app.cameraSettingsSnapshot();
            }""")
            editor_page.evaluate("window.__ASE_APP__.rotateCameraView('up', 23)")
            editor_page.evaluate("window.__ASE_APP__.rotateCameraView('down', 23)")
            restored = editor_page.evaluate("window.__ASE_APP__.cameraSettingsSnapshot()")
            assert restored["position"] == pytest.approx(baseline["position"], abs=1e-7)
            assert restored["up"] == pytest.approx(baseline["up"], abs=1e-7)
            assert restored["target"] == pytest.approx(baseline["target"], abs=1e-7)
            browser.close()
    finally:
        editor.close()


def test_empty_workspace_opens_a_complete_trajectory_from_the_browser(tmp_path):
    first = molecule("H2O")
    first.set_cell([8.0, 8.0, 8.0])
    first.set_pbc(True)
    second = first.copy()
    second.positions += [0.4, 0.0, 0.0]
    source = tmp_path / "browser_movie.extxyz"
    write(source, [first, second], format="extxyz")
    replacement = Atoms(
        "OC",
        positions=[[0.0, 0.0, 0.0], [1.25, 0.0, 0.0]],
        cell=[9.0, 9.0, 9.0],
        pbc=True,
    )
    replacement_source = tmp_path / "replacement.extxyz"
    write(replacement_source, replacement, format="extxyz")

    port = find_free_port()
    editor = view(
        Atoms(),
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 0")

            assert page.locator('#empty-workspace').is_visible()
            assert page.locator('#btn-empty-open').is_visible()
            assert page.locator('#btn-export-pickle').is_disabled()
            empty_workspace_styles = page.locator('#empty-workspace').evaluate(
                """element => {
                    const heading = element.querySelector('h1');
                    const supporting = element.querySelector(':scope > span');
                    const button = element.querySelector('#btn-empty-open');
                    const rect = button.getBoundingClientRect();
                    return {
                        heading: getComputedStyle(heading).color,
                        supporting: getComputedStyle(supporting).color,
                        buttonBackground: getComputedStyle(button).backgroundColor,
                        buttonColor: getComputedStyle(button).color,
                        buttonWidth: rect.width,
                        buttonHeight: rect.height,
                    };
                }"""
            )
            assert empty_workspace_styles == {
                "heading": "rgb(20, 33, 30)",
                "supporting": "rgb(75, 92, 86)",
                "buttonBackground": "rgb(20, 122, 105)",
                "buttonColor": "rgb(255, 255, 255)",
                "buttonWidth": 154,
                "buttonHeight": 42,
            }

            with page.expect_file_chooser() as chooser_info:
                page.click('#btn-empty-open')
            chooser_info.value.set_files(str(source))
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 3")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2")
            page.wait_for_function("document.getElementById('busy-overlay').classList.contains('hidden')")
            assert page.locator('#modal-container').is_hidden()
            assert not page.locator('#empty-workspace').is_visible()
            assert not page.locator('#btn-export-pickle').is_disabled()
            assert page.locator('#frame-label').inner_text() == '1 / 2'

            inherited_before = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const current = app.designSettingsSnapshot();
                app.applyDesignSettings({
                    ...current,
                    antiAliasing: false,
                    sphereQuality: 'high',
                    moveIncrement: 0.15,
                    rotateIncrementDeg: 7.5,
                    display: {
                        ...current.display,
                        showBonds: true,
                        showGrid: false,
                        bondMode: 'pairwise',
                        atomRadiusScale: 1.35,
                        labelColors: {H: '#d9d9d9', O: '#2a6fdf'},
                        labelRadii: {H: 0.31, O: 0.77},
                        labelVisible: {H: false, O: true},
                        pairwiseBondCutoffs: {'H-H': 0.8, 'H-O': 1.4, 'O-O': 1.8},
                        supercell: [2, 1, 1],
                        projectionMode: 'orthographic',
                        viewportBackground: 'white',
                        atomDisplayMode: '2d',
                        viewRotationStepDeg: 22.5,
                        lightingMode: 'rendered',
                        sunIntensity: 4.25,
                        sunPosition: [12, -5, 15],
                        sunTarget: [1, 2, 3],
                        atomicScalePixelsPerAngstrom: 36
                    },
                    camera: {
                        projection: 'orthographic',
                        position: [9, -11, 7],
                        target: [1, 2, 0.5],
                        up: [0, 0, 1],
                        near: 0.01,
                        far: 5000,
                        ortho_scale: 10,
                        zoom: 1
                    }
                });
                return app.designSettingsSnapshot();
            }""")

            page.set_input_files('#structure-file', str(replacement_source))
            assert page.locator('#open-file-name').inner_text() == replacement_source.name
            page.click('#open-file-confirm')
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app?.state?.atoms?.metadata?.natoms === 2
                    && app.state.atoms.symbols.join(',') === 'O,C'
                    && document.getElementById('busy-overlay').classList.contains('hidden');
            }""")
            inherited_after = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                return {
                    snapshot,
                    oColor: app.renderer.atomVisualColor(0).toLowerCase(),
                    cColor: app.renderer.atomVisualColor(1).toLowerCase()
                };
            }""")
            after = inherited_after["snapshot"]
            assert after["display"]["showBonds"] is True
            assert after["display"]["showGrid"] is False
            assert after["display"]["bondMode"] == "pairwise"
            assert after["display"]["atomRadiusScale"] == pytest.approx(1.35)
            assert after["display"]["supercell"] == [2, 1, 1]
            assert after["display"]["viewportBackground"] == "white"
            assert after["display"]["atomDisplayMode"] == "2d"
            assert after["display"]["viewRotationStepDeg"] == pytest.approx(22.5)
            assert after["display"]["lightingMode"] == "rendered"
            assert after["display"]["sunIntensity"] == pytest.approx(4.25)
            assert after["display"]["sunPosition"] == [12, -5, 15]
            assert after["display"]["sunTarget"] == [1, 2, 3]
            assert after["display"]["labelColors"] == {"O": "#2a6fdf"}
            assert after["display"]["labelRadii"]["O"] == pytest.approx(0.77)
            assert "H" not in after["display"]["labelRadii"]
            assert after["display"]["labelVisible"] == {"O": True, "C": True}
            assert after["display"]["pairwiseBondCutoffs"]["O-O"] == pytest.approx(1.8)
            assert "H-O" not in after["display"]["pairwiseBondCutoffs"]
            assert set(after["display"]["pairwiseBondCutoffs"]) == {"C-C", "C-O", "O-O"}
            assert inherited_after["oColor"] == "#2a6fdf"
            assert inherited_after["cColor"] != "#2a6fdf"
            assert after["antiAliasing"] is False
            assert after["sphereQuality"] == "high"
            assert after["moveIncrement"] == pytest.approx(0.15)
            assert after["rotateIncrementDeg"] == pytest.approx(7.5)
            assert after["camera"]["projection"] == inherited_before["camera"]["projection"]
            assert after["camera"]["position"] == pytest.approx(inherited_before["camera"]["position"])
            assert after["camera"]["target"] == pytest.approx(inherited_before["camera"]["target"])
            assert after["display"]["atomicScalePixelsPerAngstrom"] == pytest.approx(
                inherited_before["display"]["atomicScalePixelsPerAngstrom"]
            )
            browser.close()
    finally:
        editor.close()


def test_open_file_can_append_frames_with_new_labels_to_the_current_movie(tmp_path):
    initial = Atoms("H", positions=[[0.25, 0.0, 0.0]], cell=[8, 8, 8], pbc=True)
    set_atom_labels(initial, ["H_host"])
    carbon = Atoms("C", positions=[[1.0, 0.0, 0.0]], cell=[9, 9, 9], pbc=True)
    oxygen = Atoms("OO", positions=[[0, 0, 0], [1.2, 0, 0]], cell=[9, 9, 9], pbc=True)
    set_atom_labels(carbon, ["C_bulk"])
    set_atom_labels(oxygen, ["O_ads", "O_bridge"])
    source = tmp_path / "append_movie.extxyz"
    write(source, [carbon, oxygen], format="extxyz")

    port = find_free_port()
    editor = view(
        initial,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
        document_name="host.xyz",
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            console_errors = []
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error" else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.symbols?.[0] === 'H_host'")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const settings = app.designSettingsSnapshot();
                app.applyDesignSettings({
                    ...settings,
                    display: {
                        ...settings.display,
                        showBonds: true,
                        bondMode: 'pairwise',
                        atomRadiusScale: 1.25,
                        labelColors: {H_host: '#88aaff'},
                        pairwiseBondCutoffs: {'H_host-H_host': 0.7}
                    }
                });
            }""")

            page.set_input_files("#structure-file", str(source))
            page.check('input[name="open-file-mode"][value="append"]')
            assert page.locator("#open-file-confirm").inner_text() == "Add Frames"
            page.click("#open-file-confirm")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app?.state?.atoms?.metadata?.frame_count === 3
                    && document.getElementById('busy-overlay').classList.contains('hidden');
            }""")

            state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    labels: app.uniqueAtomLabels(),
                    pairs: [...document.querySelectorAll('.pairwise-bond-max')]
                        .map(input => input.dataset.pairKey),
                    frame: app.state.atoms.metadata.current_frame,
                    position: app.state.atoms.positions[0],
                    scale: app.state.display.atomRadiusScale,
                    title: app.workspaceDocumentTitle()
                };
            }""")
            assert state["labels"] == ["H_host", "C_bulk", "O_ads", "O_bridge"]
            assert set(state["pairs"]) == {
                "H_host-H_host",
                "C_bulk-H_host",
                "H_host-O_ads",
                "H_host-O_bridge",
                "C_bulk-C_bulk",
                "C_bulk-O_ads",
                "C_bulk-O_bridge",
                "O_ads-O_ads",
                "O_ads-O_bridge",
                "O_bridge-O_bridge",
            }
            assert state["frame"] == 0
            assert state["position"] == pytest.approx([0.25, 0.0, 0.0])
            assert state["scale"] == pytest.approx(1.25)
            assert state["title"] == "host.xyz"

            page.locator("#frame-slider").evaluate("""slider => {
                slider.value = '1';
                slider.dispatchEvent(new Event('input', {bubbles: true}));
            }""")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.symbols?.join(',') === 'C_bulk'")
            page.locator("#frame-slider").evaluate("""slider => {
                slider.value = '2';
                slider.dispatchEvent(new Event('input', {bubbles: true}));
            }""")
            page.wait_for_function(
                "window.__ASE_APP__?.state?.atoms?.symbols?.join(',') === 'O_ads,O_bridge'"
            )
            assert page.evaluate("window.__ASE_APP__.state.display.atomRadiusScale") == pytest.approx(1.25)
            assert not console_errors
            browser.close()
    finally:
        editor.close()


def test_arrow_keys_step_only_the_selected_loaded_or_relaxation_timeline():
    frames = []
    for x in (0.0, 1.0, 2.0):
        frames.append(
            Atoms("H", positions=[[x, 0.0, 0.0]], cell=[8, 8, 8], pbc=True)
        )
    port = find_free_port()
    editor = view(
        frames,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 3")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.atoms.metadata.calculator = 'Repulsion';
                app.state.relaxTrajectory = {
                    frames: [
                        [[10, 0, 0]],
                        [[11, 0, 0]],
                        [[12, 0, 0]]
                    ],
                    frame: 0,
                    sourceFrame: 0,
                    active: false,
                    finished: true
                };
                app.state.timelineSource = 'loaded';
                app.updateTrajectoryUI();
            }""")

            assert page.locator("#timeline-source-select option").all_text_contents() == [
                "Source frames",
                "Relaxation · Repulsion",
            ]
            assert page.locator("#timeline-source-select").input_value() == "loaded"
            assert page.locator("#secondary-trajectory-row").get_attribute("data-source") == "relax"
            assert "RELAX" in page.locator("#secondary-timeline-source-label").inner_text()

            page.evaluate("document.activeElement?.blur()")
            page.keyboard.press("ArrowRight")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 1")
            assert page.locator("#frame-label").inner_text() == "2 / 3"
            assert page.evaluate("window.__ASE_APP__.state.relaxTrajectory.frame") == 0

            page.select_option("#timeline-source-select", "relax")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.timelineSource === 'relax'
                    && app.state.atoms.positions[0][0] === 10;
            }""")
            assert page.locator("#secondary-trajectory-row").get_attribute("data-source") == "loaded"
            assert page.locator("#secondary-timeline-source-label").inner_text() == "SOURCE"

            page.evaluate("document.activeElement?.blur()")
            page.keyboard.press("ArrowRight")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.relaxTrajectory.frame === 1
                    && app.state.atoms.positions[0][0] === 11;
            }""")
            assert page.evaluate("window.__ASE_APP__.state.atoms.metadata.current_frame") == 1

            page.locator("#movie-fps").focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(100)
            assert page.evaluate("window.__ASE_APP__.state.relaxTrajectory.frame") == 1
            assert page.locator("#frame-label").inner_text() == "2 / 3"
            browser.close()
    finally:
        editor.close()


def test_trajectory_selection_persists_and_displacement_vectors_render():
    first = Atoms(
        "H3",
        positions=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    second = Atoms(
        "H3",
        positions=[[0.2, 0.0, 0.0], [1.4, 0.0, 0.0], [2.8, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        [first, second],
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1360, "height": 820})
            console_errors = []
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2"
            )
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.addSelectionReference(0);
                app.addSelectionReference(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 2")
            assert "1.0000 A" in page.locator("#selected-measure").inner_text()

            page.locator("#app-viewport canvas").focus()
            page.keyboard.press("ArrowRight")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.atoms.metadata.current_frame === 1
                    && app.selectionCount() === 2
                    && app.state.selected.has(0)
                    && app.state.selected.has(1);
            }""")
            assert "1.2000 A" in page.locator("#selected-measure").inner_text()

            _expand_inspector(page)
            page.click('[data-inspector-group="analysis"]')
            page.check("#chk-displacement")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.renderer.domElement.dataset.displacementCount === '3'
                    && document.getElementById('displacement-status').dataset.state === 'ready';
            }""")
            displacement = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const group = app.renderer.displacementGroup;
                return {
                    childCount: group.children.length,
                    vectorCount: group.userData.entries.length,
                    shaftCount: group.userData.shaft.count,
                    headCount: group.userData.head.count,
                    flat: group.userData.flat,
                    stats: document.getElementById('displacement-mapped').innerText,
                    selected: [...app.state.selected],
                    selectionOrder: [...app.state.selectionOrder]
                };
            }""")
            assert displacement == {
                "childCount": 2,
                "vectorCount": 3,
                "shaftCount": 3,
                "headCount": 3,
                "flat": False,
                "stats": "3 atoms (index)",
                "selected": [0, 1],
                "selectionOrder": ["atom:0", "atom:1"],
            }

            page.click('[data-inspector-group="structure"]')
            _open_panel(page, "cell-replication")
            page.fill("#super-x", "2")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.displacementCount === '6'"
            )
            page.fill("#translate-x", "1.0")
            page.fill("#translate-y", "-0.5")
            page.fill("#translate-z", "0.25")
            page.click("#btn-apply-translation")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.visualTranslation === '1.000000,-0.500000,0.250000'"
            )
            repeated = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const entries = app.renderer.displacementGroup.userData.entries;
                const preview = app.renderer.supercellGroup.children.find(
                    child => child.userData?.supercellCellPreview
                );
                return {
                    vizOnly: app.state.vizOnly,
                    physicalPositions: app.state.atoms.positions.map(position => [...position]),
                    translation: [...app.state.display.translation],
                    supercell: [...app.state.display.supercell],
                    atomGroup: app.renderer.atomMeshes.position.toArray(),
                    vectorGroup: app.renderer.displacementGroup.position.toArray(),
                    previewPosition: preview?.position.toArray(),
                    starts: entries.map(entry => entry.start),
                    offsets: entries.map(entry => entry.cellOffset),
                    vectors: entries.map(entry => entry.vector),
                    saved: app.designSettingsSnapshot().display,
                    inputs: ['translate-x', 'translate-y', 'translate-z'].map(
                        id => Number(document.getElementById(id).value)
                    )
                };
            }""")
            assert repeated["vizOnly"] is True
            np.testing.assert_allclose(repeated["physicalPositions"], second.positions)
            assert repeated["translation"] == pytest.approx([1.0, -0.5, 0.25])
            assert repeated["supercell"] == [2, 1, 1]
            assert repeated["atomGroup"] == pytest.approx([1.0, -0.5, 0.25])
            assert repeated["vectorGroup"] == pytest.approx([1.0, -0.5, 0.25])
            assert repeated["previewPosition"] == pytest.approx([0.0, 0.0, 0.0])
            np.testing.assert_allclose(repeated["starts"], [
                [0.2, 0.0, 0.0],
                [10.2, 0.0, 0.0],
                [1.4, 0.0, 0.0],
                [11.4, 0.0, 0.0],
                [2.8, 0.0, 0.0],
                [12.8, 0.0, 0.0],
            ])
            assert repeated["offsets"] == [
                [0, 0, 0], [1, 0, 0],
                [0, 0, 0], [1, 0, 0],
                [0, 0, 0], [1, 0, 0],
            ]
            np.testing.assert_allclose(repeated["vectors"], [
                [0.2, 0.0, 0.0], [0.2, 0.0, 0.0],
                [0.4, 0.0, 0.0], [0.4, 0.0, 0.0],
                [0.8, 0.0, 0.0], [0.8, 0.0, 0.0],
            ])
            assert repeated["saved"]["translation"] == pytest.approx([1.0, -0.5, 0.25])
            assert repeated["saved"]["translationMode"] == "cartesian"
            assert repeated["saved"]["supercell"] == [2, 1, 1]
            assert repeated["inputs"] == [1.0, -0.5, 0.25]

            page.click('[data-inspector-group="analysis"]')
            page.select_option("#displacement-style", "2d")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.displacementGroup.userData.flat === true"
            )
            assert not console_errors
            browser.close()
    finally:
        editor.close()


def test_coordinate_reset_preserves_visual_translation_and_display_supercell():
    atoms = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.75, 0.0, 0.0]],
        cell=[6.0, 7.0, 8.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            _open_panel(page, "cell-replication")
            page.fill("#super-x", "2")
            page.fill("#super-y", "2")
            page.fill("#translate-x", "0.4")
            page.fill("#translate-y", "-0.2")
            page.fill("#translate-z", "0.1")
            page.click("#btn-apply-translation")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.visualTranslation === '0.400000,-0.200000,0.100000'"
            )

            page.click("#btn-reset-coords")
            page.wait_for_selector("#modal-confirm-action")
            assert "displayed replication" in page.locator("#modal-content").inner_text()
            assert "visual translation" in page.locator("#modal-content").inner_text()
            page.click("#modal-confirm-action")
            page.wait_for_function(
                "document.getElementById('busy-overlay').classList.contains('hidden')"
            )
            preserved = page.evaluate("""() => ({
                positions: window.__ASE_APP__.state.atoms.positions,
                supercell: window.__ASE_APP__.state.display.supercell,
                translation: window.__ASE_APP__.state.display.translation,
                atomGroup: window.__ASE_APP__.renderer.atomMeshes.position.toArray(),
                inputs: ['translate-x', 'translate-y', 'translate-z'].map(
                    id => Number(document.getElementById(id).value)
                ),
                superInputs: ['super-x', 'super-y', 'super-z'].map(
                    id => Number(document.getElementById(id).value)
                )
            })""")
            np.testing.assert_allclose(preserved["positions"], atoms.positions)
            assert preserved["supercell"] == [2, 2, 1]
            assert preserved["translation"] == pytest.approx([0.4, -0.2, 0.1])
            assert preserved["atomGroup"] == pytest.approx([0.4, -0.2, 0.1])
            assert preserved["inputs"] == [0.4, -0.2, 0.1]
            assert preserved["superInputs"] == [2, 2, 1]

            page.click("#btn-reset")
            page.wait_for_selector("#modal-confirm-action")
            page.click("#modal-confirm-action")
            page.wait_for_function(
                "document.getElementById('busy-overlay').classList.contains('hidden')"
            )
            reset = page.evaluate("""() => ({
                supercell: window.__ASE_APP__.state.display.supercell,
                translation: window.__ASE_APP__.state.display.translation,
                translationMode: window.__ASE_APP__.state.display.translationMode,
                inputs: ['translate-x', 'translate-y', 'translate-z'].map(
                    id => Number(document.getElementById(id).value)
                )
            })""")
            assert reset == {
                "supercell": [1, 1, 1],
                "translation": [0, 0, 0],
                "translationMode": "cartesian",
                "inputs": [0, 0, 0],
            }
            browser.close()
    finally:
        editor.close()


def test_rotate_direction_commensurate_snap_and_panel_focus_workflow():
    lattice = 2.46
    atoms = Atoms(
        "C4",
        scaled_positions=[
            [0.0, 0.0, 0.25],
            [1 / 3, 2 / 3, 0.25],
            [0.0, 0.0, 0.75],
            [2 / 3, 1 / 3, 0.75],
        ],
        cell=[
            [lattice, 0.0, 0.0],
            [0.5 * lattice, 0.5 * 3 ** 0.5 * lattice, 0.0],
            [0.0, 0.0, 18.0],
        ],
        pbc=[True, True, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")

            canvas = page.locator('#app-viewport canvas')
            canvas.focus()
            page.keyboard.press('Control+a')
            page.wait_for_function("window.__ASE_APP__.state.selected.size === 4")

            # Tab and Escape both open a collapsed panel. Once open, Tab
            # remains available for native form navigation; Escape commits,
            # closes, and returns keyboard focus to the viewport.
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            page.click('[data-inspector-group="structure"]')
            page.fill('#rotate-increment', '5')
            page.keyboard.press('Tab')
            assert not page.locator('body').evaluate(
                "element => element.classList.contains('inspector-collapsed')"
            )
            page.keyboard.press('Escape')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            assert page.evaluate("document.activeElement?.tagName") == 'CANVAS'
            assert page.evaluate("window.__ASE_APP__.state.selected.size") == 4
            page.keyboard.press('Escape')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            assert page.evaluate("window.__ASE_APP__.state.selected.size") == 4
            page.keyboard.press('Escape')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            assert page.evaluate("document.activeElement?.tagName") == 'CANVAS'
            aligned_reference = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const savedPositions = app.state.originalPositions;
                const savedPivot = app.transform.pivot.clone();
                app.state.originalPositions = [
                    [-4, -1, 0], [-4, 1, 0], [4, -1, 0], [4, 1, 0]
                ];
                app.transform.pivot.set(0, 0, 0);
                const result = app.rotationReferenceForSelection(
                    [0, 1, 2, 3],
                    new app.transform.pivot.constructor(0, 0, 1)
                );
                app.state.originalPositions = savedPositions;
                app.transform.pivot.copy(savedPivot);
                return result.reference.toArray();
            }""")
            assert abs(aligned_reference[0]) == pytest.approx(1.0, abs=1e-7)
            assert aligned_reference[1] == pytest.approx(0.0, abs=1e-7)
            assert aligned_reference[2] == pytest.approx(0.0, abs=1e-7)
            page.keyboard.press('r')
            assert page.evaluate("window.__ASE_APP__.transform.mode") == 'ROTATE'
            rotation_guide = page.evaluate("""() => {
                const guide = window.__ASE_APP__.transform.rotationGuideGroup;
                return {
                    visible: guide.visible,
                    roles: guide.children
                        .filter(child => child.visible)
                        .map(child => child.userData.rotationGuideRole)
                        .sort(),
                    angle: window.__ASE_APP__.transform.rotationGuide?.angle
                };
            }""")
            assert rotation_guide["visible"] is True
            assert rotation_guide["roles"] == ["axis", "current", "start"]
            assert rotation_guide["angle"] == pytest.approx(0.0)
            page.keyboard.press('Escape')

            # From +Z, free R and R+Z must apply the same visible clockwise
            # motion for the same clockwise pointer path.
            rotation = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                document.getElementById('rotate-increment').value = '0';
                app.readTransformSettings();
                app.alignViewToAxis('Z');
                const run = (axis) => {
                    app.enterTransformMode('ROTATE');
                    if (axis) app.transform.setAxis(axis, app.renderer.camera);
                    const pivot = app.state.rotationScreenPivot;
                    app.updateRotationFromPointer(pivot.x + 100, pivot.y);
                    app.updateRotationFromPointer(pivot.x, pivot.y + 100);
                    app.applyTransformPreview();
                    const positions = app.currentPositionsFromScene();
                    const angle = app.transform.rotationAngle;
                    const guideAngle = app.transform.rotationGuide?.angle;
                    app.cancelTransform();
                    return { positions, angle, guideAngle };
                };
                return { free: run(null), locked: run('Z') };
            }""")
            assert rotation["free"]["angle"] == pytest.approx(-math.pi / 2, abs=1e-5)
            assert rotation["locked"]["angle"] == pytest.approx(-math.pi / 2, abs=1e-5)
            assert rotation["free"]["guideAngle"] == pytest.approx(math.pi / 2, abs=1e-5)
            assert rotation["locked"]["guideAngle"] == pytest.approx(-math.pi / 2, abs=1e-5)
            assert np.asarray(rotation["free"]["positions"]) == pytest.approx(
                np.asarray(rotation["locked"]["positions"]), abs=1e-5
            )

            # Enable the cell-boundary search through the actual panel, then
            # run R+Z and wait for the backend result and rendered guide.
            canvas.focus()
            page.keyboard.press('Tab')
            page.click('[data-inspector-group="structure"]')
            page.check('#chk-commensurate-guide')
            page.check('#chk-commensurate-snap')
            page.keyboard.press('Escape')
            page.keyboard.press('r')
            page.keyboard.press('z')
            page.wait_for_function("window.__ASE_APP__.state.commensurateCandidates.length >= 60")
            page.wait_for_function("window.__ASE_APP__.renderer.commensurateGuideGroup.children.length > 0")
            page.wait_for_function("""window.__ASE_APP__.renderer.commensurateGuideGroup.children
                .some(object => object.isSprite)""")
            labels = page.evaluate("""() => window.__ASE_APP__.renderer.commensurateGuideGroup.children
                .filter(object => object.isSprite)
                .map(object => object.material.map.image.getContext('2d') ? object.userData : null)
                .length""")
            assert labels > 0
            candidate_status = page.locator('#commensurate-status').inner_text()
            assert 'boundary strain' in candidate_status
            assert 'N=' in candidate_status

            snapped = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.transform.buffer = '21.2';
                app.transform.rotationAngle = app.renderer.THREE
                    ? app.renderer.THREE.MathUtils.degToRad(21.2)
                    : 21.2 * Math.PI / 180;
                app.applyTransformPreview();
                return {
                    candidate: app.state.commensurateSnappedCandidate,
                    readout: app.state.transformReadout,
                    sprites: app.renderer.commensurateGuideGroup.children.filter(object => object.isSprite).length,
                    rotationGuideAngle: app.transform.rotationGuide?.angle,
                    rotationGuideRoles: app.transform.rotationGuideGroup.children
                        .filter(child => child.visible)
                        .map(child => child.userData.rotationGuideRole)
                        .sort(),
                    candidateRays: app.renderer.commensurateGuideGroup.children
                        .filter(object => object.userData?.commensurateCandidate).length,
                    baselineRays: app.renderer.commensurateGuideGroup.children
                        .filter(object => (
                            object.isLine && !object.userData?.commensurateCandidate
                        )).length
                };
            }""")
            assert snapped["candidate"]["targetAngleDeg"] == pytest.approx(21.7867893, abs=1e-5)
            assert "MATCH" in snapped["readout"]
            assert snapped["sprites"] > 0
            assert snapped["rotationGuideAngle"] == pytest.approx(
                math.radians(21.7867893), abs=1e-5
            )
            assert snapped["rotationGuideRoles"] == ["axis", "current", "start"]
            assert snapped["candidateRays"] > 0
            assert snapped["baselineRays"] == 0
            assert '21.79 deg' in page.locator('#cmd-val').inner_text()
            assert page.locator('#commensurate-candidates-readout').is_visible()
            assert page.locator('#commensurate-candidates-values .commensurate-candidate-chip').count() >= 3
            assert '21.79 deg' in page.locator(
                '#commensurate-candidates-values .commensurate-candidate-chip.active'
            ).inner_text()
            assert page.locator('#commensurate-status').inner_text().startswith('Snapped: 21.786789 deg')

            unsnapped = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.commensurateSnap = false;
                app.transform.buffer = '21.2';
                app.transform.rotationAngle = 21.2 * Math.PI / 180;
                app.applyTransformPreview();
                return {
                    candidate: app.state.commensurateSnappedCandidate,
                    readout: app.state.transformReadout
                };
            }""")
            assert unsnapped["candidate"] is None
            assert unsnapped["readout"].startswith('21.20 deg')
            page.keyboard.press('Escape')

            # The toolbar icon follows the supplied matte-sphere / lit-sphere
            # visual states rather than the former flashlight glyph.
            assert page.locator('#btn-lighting-toggle .render-sphere-off').count() == 1
            assert page.locator('#btn-lighting-toggle .render-sphere-on').count() == 1
            palette = page.evaluate("""() => {
                const sample = document.createElement('div');
                sample.style.background = 'var(--field)';
                document.body.appendChild(sample);
                const result = {
                    field: getComputedStyle(sample).backgroundColor,
                    calculator: getComputedStyle(document.getElementById('calc-device')).backgroundColor,
                    offHighlight: getComputedStyle(document.querySelector('.render-stop-off-highlight')).stopColor,
                    onLight: getComputedStyle(document.querySelector('.render-stop-on-light')).stopColor,
                    onHighlight: getComputedStyle(document.querySelector('.render-stop-on-highlight')).stopColor
                };
                sample.remove();
                return result;
            }""")
            assert palette["calculator"] == palette["field"]
            assert palette["offHighlight"] == "rgb(195, 204, 200)"
            assert palette["onLight"] == "rgb(138, 229, 211)"
            assert palette["onHighlight"] == "rgb(255, 240, 196)"
            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'studio-shadow')
            page.wait_for_function("document.getElementById('lighting-widget').dataset.mode === 'studio-shadow'")
            assert page.locator('.render-sphere-on').evaluate("element => getComputedStyle(element).display") == 'block'
            assert page.locator('.render-sphere-shadow').evaluate("element => getComputedStyle(element).display") == 'block'
            browser.close()
    finally:
        editor.close()


def test_export_preview_is_screen_fixed_and_matches_the_png_render():
    atoms = molecule("H2O")
    atoms.set_cell([12.0, 10.0, 8.0])
    atoms.center()
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            _expand_inspector(page)
            page.click('[data-inspector-group="export"]')
            page.fill('#image-width', '1600')
            page.fill('#image-height', '800')
            page.click('#btn-preview-image')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === 1600")

            initial = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                const inspector = document.getElementById('inspector').getBoundingClientRect();
                const topBar = document.getElementById('top-bar').getBoundingClientRect();
                const commandBar = document.getElementById('command-bar').getBoundingClientRect();
                const preview = app.renderer.lastExportPreview;
                const direct = app.renderer.exportCameraSetup(1600, 800, app.imagePreviewOptions());
                return {
                    pressed: document.getElementById('btn-preview-image').getAttribute('aria-pressed'),
                    hidden: document.getElementById('export-preview-frame').classList.contains('hidden'),
                    frame: [frame.left, frame.top, frame.width, frame.height],
                    safeBounds: [topBar.bottom, inspector.left, commandBar.top],
                    frameAspect: frame.width / frame.height,
                    output: preview.outputSize,
                    render: preview.renderSize,
                    offset: preview.offset,
                    content: [
                        preview.contentRect.left,
                        preview.contentRect.bottom,
                        preview.contentRect.width,
                        preview.contentRect.height
                    ],
                    previewProjection: preview.cameraProjection,
                    directProjection: direct.camera.projectionMatrix.elements.slice(),
                    previewCount: app.renderer.previewRenderCount
                };
            }""")
            assert initial["pressed"] == "true"
            assert initial["hidden"] is False
            assert initial["frameAspect"] == pytest.approx(2.0, abs=0.004)
            assert initial["output"] == [1600, 800]
            assert initial["frame"][1] >= initial["safeBounds"][0]
            assert initial["frame"][0] + initial["frame"][2] <= initial["safeBounds"][1]
            assert initial["frame"][1] + initial["frame"][3] <= initial["safeBounds"][2]
            assert initial["previewProjection"] == pytest.approx(initial["directProjection"])
            assert initial["render"] == [1600, 800]
            assert initial["offset"] == [0, 0]
            assert initial["content"][2:] == pytest.approx(initial["frame"][2:], abs=1.0)

            page.fill('#image-width', '800')
            page.fill('#image-height', '1600')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[1] === 1600")
            portrait = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                const preview = app.renderer.lastExportPreview;
                return {
                    aspect: frame.width / frame.height,
                    render: preview.renderSize,
                    offset: preview.offset,
                    content: [preview.contentRect.width, preview.contentRect.height],
                    frame: [frame.width, frame.height]
                };
            }""")
            assert portrait["aspect"] == pytest.approx(0.5, abs=0.004)
            assert portrait["render"] == [800, 1600]
            assert portrait["offset"] == [0, 0]
            assert portrait["content"] == pytest.approx(portrait["frame"], abs=1.0)

            # A square output changes the cloned camera gate instead of
            # letterboxing the live viewport inside the preview frame.
            page.fill('#image-width', '1920')
            page.fill('#image-height', '1920')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '1920,1920'"
            )
            square = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const preview = app.renderer.lastExportPreview;
                const setup = app.renderer.exportCameraSetup(1920, 1920, app.imagePreviewOptions());
                const camera = setup.camera;
                return {
                    render: preview.renderSize,
                    offset: preview.offset,
                    cameraAspect: camera.isPerspectiveCamera
                        ? camera.aspect
                        : Math.abs((camera.right - camera.left) / (camera.top - camera.bottom)),
                    content: [preview.contentRect.width, preview.contentRect.height],
                    frame: [preview.frameRect.width, preview.frameRect.height]
                };
            }""")
            assert square["render"] == [1920, 1920]
            assert square["offset"] == [0, 0]
            assert square["cameraAspect"] == pytest.approx(1.0)
            assert square["content"] == pytest.approx(square["frame"], abs=1.0)

            page.fill('#image-width', '1600')
            page.fill('#image-height', '800')
            page.wait_for_function("window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === 1600")

            # Zoom affects the export camera and atoms inside the frame, but
            # the preview rectangle itself stays fixed in screen coordinates.
            zoomed = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                camera.zoom *= 0.62;
                camera.updateProjectionMatrix();
                app.renderer.requestRender();
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const frame = document.getElementById('export-preview-frame').getBoundingClientRect();
                return {
                    frame: [frame.left, frame.top, frame.width, frame.height],
                    projection: app.renderer.lastExportPreview.cameraProjection,
                    previewCount: app.renderer.previewRenderCount
                };
            }""")
            assert zoomed["frame"] == pytest.approx(initial["frame"], abs=0.01)
            assert zoomed["projection"] != pytest.approx(initial["previewProjection"])
            assert zoomed["previewCount"] > initial["previewCount"]

            page.click('[data-inspector-group="view"]')
            page.fill('#atomic-scale', '40')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 40) < 0.02")
            scale_40 = page.evaluate("""() => ({
                zoom: window.__ASE_APP__.renderer.camera.zoom,
                scale: window.__ASE_APP__.renderer.currentPixelsPerAngstrom()
            })""")
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            scale_80 = page.evaluate("""() => ({
                zoom: window.__ASE_APP__.renderer.camera.zoom,
                scale: window.__ASE_APP__.renderer.currentPixelsPerAngstrom(),
                input: Number(document.getElementById('atomic-scale').value),
                span: document.getElementById('atomic-scale-span').textContent
            })""")
            assert scale_40["scale"] == pytest.approx(40, abs=0.02)
            assert scale_80["scale"] == pytest.approx(80, abs=0.02)
            assert scale_80["zoom"] == pytest.approx(scale_40["zoom"] * 2, rel=2e-3)
            assert scale_80["input"] == pytest.approx(80, abs=0.02)
            assert "Viewport span:" in scale_80["span"]

            page.locator('#atomic-scale').press('Tab')
            wheel_sync = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.controls.doZoom(-120);
                return {
                    scale: app.renderer.currentPixelsPerAngstrom(),
                    input: Number(document.getElementById('atomic-scale').value)
                };
            }""")
            assert wheel_sync["scale"] > 80
            assert wheel_sync["input"] == pytest.approx(wheel_sync["scale"], rel=2e-3)
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")

            persisted = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const snapshot = app.designSettingsSnapshot();
                app.renderer.setPixelsPerAngstrom(35);
                app.applyDesignSettings(snapshot);
                return {
                    scale: app.renderer.currentPixelsPerAngstrom(),
                    saved: snapshot.display.atomicScalePixelsPerAngstrom,
                    framing: snapshot.display.imageFramingMode,
                    hasLegacyScale: Object.hasOwn(snapshot.display, 'imagePixelsPerAngstrom')
                };
            }""")
            assert persisted["scale"] == pytest.approx(80, abs=0.02)
            assert persisted["saved"] == pytest.approx(80, abs=0.02)
            assert persisted["framing"] == "viewport"
            assert persisted["hasLegacyScale"] is False

            page.select_option('#projection-mode', 'perspective')
            page.wait_for_function("window.__ASE_APP__.renderer.camera.isPerspectiveCamera")
            page.fill('#atomic-scale', '50')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 50) < 0.02")
            perspective_50 = page.evaluate(
                "window.__ASE_APP__.renderer.camera.position.distanceTo(window.__ASE_APP__.renderer.controls.target)"
            )
            page.fill('#atomic-scale', '100')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 100) < 0.02")
            perspective_100 = page.evaluate(
                "window.__ASE_APP__.renderer.camera.position.distanceTo(window.__ASE_APP__.renderer.controls.target)"
            )
            assert perspective_100 == pytest.approx(perspective_50 * 0.5, rel=2e-3)
            page.select_option('#projection-mode', 'orthographic')
            page.wait_for_function("window.__ASE_APP__.renderer.camera.isOrthographicCamera")
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            page.click('[data-inspector-group="export"]')

            physical = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const profile = app.currentImageExportProfile();
                app.setImageExportProfile({
                    ...profile,
                    options: {
                        ...profile.options,
                        scaleMode: 'physical',
                        pixelsPerAngstrom: 80
                    }
                });
                app.renderer.renderNow();
                const setup = app.renderer.exportCameraSetup(1600, 800, app.imagePreviewOptions());
                const camera = setup.camera;
                const result = {
                    mode: app.renderer.lastExportPreview.scaleMode,
                    pixelsPerAngstrom: app.renderer.lastExportPreview.pixelsPerAngstrom,
                    span: [
                        (camera.right - camera.left) / camera.zoom,
                        (camera.top - camera.bottom) / camera.zoom
                    ],
                    projection: app.renderer.lastExportPreview.cameraProjection,
                    directProjection: camera.projectionMatrix.elements.slice()
                };
                app.setImageExportProfile({
                    ...profile,
                    options: { ...profile.options, scaleMode: 'viewport' }
                });
                app.renderer.renderNow();
                return result;
            }""")
            assert physical["mode"] == "physical"
            assert physical["pixelsPerAngstrom"] == pytest.approx(80)
            assert physical["span"] == pytest.approx([20.0, 10.0])
            assert physical["projection"] == pytest.approx(physical["directProjection"])

            # Use the actual CSS frame dimensions as output pixels, then compare
            # the rendered inset and PNG. Both must share camera and scene state.
            frame_width = round(zoomed["frame"][2])
            frame_height = round(zoomed["frame"][3])
            page.fill('#image-width', str(frame_width))
            page.fill('#image-height', str(frame_height))
            page.wait_for_function(
                "([w, h]) => window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[0] === w && "
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.[1] === h",
                arg=[frame_width, frame_height],
            )
            comparison = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.showGrid = false;
                app.state.display.showAxes = false;
                app.renderer.setDisplayOptions(app.state.display, { rebuild: false });
                app.syncImageExportPreview();
                app.renderer.renderNow();

                const renderer = app.renderer;
                const rect = renderer.lastExportPreview.frameRect;
                const width = renderer.lastExportPreview.outputSize[0];
                const height = renderer.lastExportPreview.outputSize[1];
                const sourceUrl = renderer.domElement.toDataURL('image/png');
                const loadImage = url => new Promise((resolve, reject) => {
                    const image = new Image();
                    image.onload = () => resolve(image);
                    image.onerror = reject;
                    image.src = url;
                });
                const source = await loadImage(sourceUrl);
                const ratioX = source.naturalWidth / renderer.domElement.clientWidth;
                const ratioY = source.naturalHeight / renderer.domElement.clientHeight;
                const previewCanvas = document.createElement('canvas');
                previewCanvas.width = width;
                previewCanvas.height = height;
                const previewContext = previewCanvas.getContext('2d', { willReadFrequently: true });
                previewContext.drawImage(
                    source,
                    rect.left * ratioX,
                    rect.top * ratioY,
                    rect.width * ratioX,
                    rect.height * ratioY,
                    0,
                    0,
                    width,
                    height
                );

                const options = app.imagePreviewOptions();
                const exportedUrl = renderer.exportPNG(width, height, options);
                const exported = await loadImage(exportedUrl);
                const exportCanvas = document.createElement('canvas');
                exportCanvas.width = width;
                exportCanvas.height = height;
                const exportContext = exportCanvas.getContext('2d', { willReadFrequently: true });
                exportContext.drawImage(exported, 0, 0);
                const previewPixels = previewContext.getImageData(0, 0, width, height).data;
                const exportPixels = exportContext.getImageData(0, 0, width, height).data;
                let total = 0;
                let maximum = 0;
                for (let index = 0; index < previewPixels.length; index += 1) {
                    const difference = Math.abs(previewPixels[index] - exportPixels[index]);
                    total += difference;
                    maximum = Math.max(maximum, difference);
                }
                return {
                    meanAbsoluteDifference: total / previewPixels.length,
                    maximumDifference: maximum,
                    size: [width, height],
                    frame: [rect.left, rect.top, rect.width, rect.height],
                    outputAspect: width / height,
                    frameAspect: rect.width / rect.height
                };
            }""")
            assert comparison["size"] == [frame_width, frame_height]
            assert comparison["frameAspect"] == pytest.approx(comparison["outputAspect"], abs=0.004)
            assert comparison["meanAbsoluteDifference"] < 1.0

            # The preview uses the existing demand renderer and must not create
            # a hidden animation loop while the scene is idle.
            idle_start = page.evaluate("window.__ASE_APP__.renderer.previewRenderCount")
            time.sleep(0.3)
            idle_end = page.evaluate("window.__ASE_APP__.renderer.previewRenderCount")
            assert idle_end == idle_start

            page.click('#btn-preview-image')
            page.wait_for_function("window.__ASE_APP__.renderer.domElement.dataset.exportPreview === 'false'")
            assert page.locator('#export-preview-frame').is_hidden()
            browser.close()
    finally:
        editor.close()


def test_image_export_modal_is_the_authoritative_retina_preview(tmp_path):
    atoms = molecule("C6H6")
    atoms.set_cell([12.0, 12.0, 8.0])
    atoms.center()
    atoms.set_pbc(True)
    atoms = atoms.repeat((2, 2, 1))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        show_bonds=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                accept_downloads=True,
            )
            page = context.new_page()
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 48")
            export_preflight = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                const originalChoose = app.chooseSaveDestination.bind(app);
                const originalSave = app.savePreparedBlob.bind(app);
                const order = [];
                let actionCount = 0;
                app.chooseSaveDestination = async () => {
                    order.push('choose');
                    return null;
                };
                const cancelled = await app.saveBlobFromAction(async () => {
                    actionCount += 1;
                    order.push('generate');
                    return new Blob(['cancelled']);
                }, 'cancelled.txt', 'text/plain');

                app.chooseSaveDestination = async () => {
                    order.push('choose-success');
                    return { handle: null, browserDownload: true };
                };
                app.savePreparedBlob = async (_blob, _name, _type, destination) => {
                    order.push(destination?.browserDownload ? 'save-success' : 'save-missing');
                    return true;
                };
                const saved = await app.saveBlobFromAction(async () => {
                    actionCount += 1;
                    order.push('generate-success');
                    return new Blob(['saved']);
                }, 'saved.txt', 'text/plain');
                app.chooseSaveDestination = originalChoose;
                app.savePreparedBlob = originalSave;
                return { cancelled, saved, actionCount, order };
            }""")
            assert export_preflight == {
                "cancelled": False,
                "saved": True,
                "actionCount": 1,
                "order": [
                    "choose",
                    "choose-success",
                    "generate-success",
                    "save-success",
                ],
            }
            _expand_inspector(page)
            page.click('[data-inspector-group="export"]')
            page.fill('#image-width', '1280')
            page.fill('#image-height', '720')
            page.uncheck('#export-include-cell')
            page.wait_for_function(
                "window.__ASE_APP__.state.imageExportProfile?.options?.includeCell === false"
            )
            page.click('#btn-preview-image')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '1280,720'"
            )

            page.click('#btn-export-image')
            assert page.locator('#export-image-format').input_value() == 'png'
            assert set(page.locator('#export-image-format option').evaluate_all(
                "options => options.map(option => option.value)"
            )) == {'png', 'jpg', 'pdf', 'webp'}
            page.select_option('#export-image-format', 'jpg')
            assert page.locator('#export-transparent').is_disabled()
            assert page.locator('#export-transparent').is_checked() is False
            page.select_option('#export-image-format', 'pdf')
            assert page.locator('#export-transparent').is_disabled()
            page.select_option('#export-image-format', 'png')
            assert not page.locator('#export-transparent').is_disabled()
            assert page.locator('#export-cell').is_checked() is False
            page.fill('#export-width', '640')
            page.fill('#export-height', '640')
            page.uncheck('#export-grid')
            page.uncheck('#export-axes')
            page.select_option('#export-sphere-quality', 'medium')
            page.fill('#export-smoothness-scale', '1.30')
            page.select_option('#export-render-mode', 'studio-shadow')
            page.fill('#export-sun-intensity', '3.75')
            page.fill('#export-sun-position-0', '11.5')
            page.fill('#export-sun-position-1', '-7.25')
            page.fill('#export-sun-position-2', '16.0')
            page.fill('#export-sun-target-0', '1.25')
            page.fill('#export-sun-target-1', '0.50')
            page.fill('#export-sun-target-2', '-0.75')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.exportPreview?.width === 640 && "
                "window.__ASE_APP__.renderer.exportPreview?.height === 640 && "
                "window.__ASE_APP__.renderer.exportPreview?.options?.renderMode === 'studio-shadow'"
            )

            live = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const cellVisibleBefore = app.renderer.cellGroup.visible;
                const sceneState = app.renderer.beginExportScene(app.state.imageExportProfile.options);
                const cellVisibleDuring = app.renderer.cellGroup.visible;
                sceneState.restore();
                app.renderer.renderNow();
                return {
                    panelSize: [
                        Number(document.getElementById('image-width').value),
                        Number(document.getElementById('image-height').value)
                    ],
                    frameSize: [
                        Number(document.getElementById('export-preview-frame').dataset.outputWidth),
                        Number(document.getElementById('export-preview-frame').dataset.outputHeight)
                    ],
                    profile: app.state.imageExportProfile,
                    preview: app.renderer.exportPreview,
                    previewProjection: app.renderer.lastExportPreview.cameraProjection,
                    directProjection: app.renderer.exportCameraSetup(
                        640,
                        640,
                        app.state.imageExportProfile.options
                    ).camera.projectionMatrix.elements.slice(),
                    cellVisibility: [
                        cellVisibleBefore,
                        cellVisibleDuring,
                        app.renderer.cellGroup.visible
                    ]
                };
            }""")
            assert live["panelSize"] == [640, 640]
            assert live["frameSize"] == [640, 640]
            assert live["profile"]["width"] == 640
            assert live["profile"]["height"] == 640
            assert live["profile"]["options"] == live["preview"]["options"]
            assert live["profile"]["options"]["includeGrid"] is False
            assert live["profile"]["options"]["includeAxes"] is False
            assert live["profile"]["options"]["includeCell"] is False
            assert live["cellVisibility"] == [True, False, True]
            assert live["profile"]["options"]["sphereQuality"] == "medium"
            assert live["profile"]["options"]["sphereQualityScale"] == pytest.approx(1.3)
            assert live["profile"]["options"]["renderModeSelection"] == "studio-shadow"
            assert live["profile"]["options"]["sunIntensity"] == pytest.approx(3.75)
            assert live["profile"]["options"]["sunPosition"] == pytest.approx([11.5, -7.25, 16.0])
            assert live["profile"]["options"]["sunTarget"] == pytest.approx([1.25, 0.5, -0.75])
            assert live["previewProjection"] == pytest.approx(live["directProjection"])

            page.evaluate("""() => {
                window.__imageExportProgress = [];
                const progress = document.getElementById('busy-progress');
                new MutationObserver(() => {
                    const value = Number(progress.getAttribute('aria-valuenow'));
                    if (Number.isFinite(value)) {
                        window.__imageExportProgress.push({
                            value,
                            eta: document.getElementById('busy-progress-eta')?.textContent || '',
                            message: document.getElementById('busy-message')?.textContent || ''
                        });
                    }
                }).observe(progress, {
                    attributes: true,
                    attributeFilter: ['aria-valuenow']
                });
            }""")
            with page.expect_download(timeout=60_000) as download_info:
                page.click('#modal-export-image')
            download = download_info.value
            output = tmp_path / download.suggested_filename
            download.save_as(output)
            page.wait_for_function(
                "document.getElementById('modal-container').classList.contains('hidden') && "
                "window.__ASE_APP__.renderer.lastExportPreview?.outputSize?.join(',') === '640,640'"
            )
            image_progress = page.evaluate("window.__imageExportProgress")
            progress_values = [entry["value"] for entry in image_progress]
            assert progress_values
            assert progress_values == sorted(progress_values)
            assert progress_values[-1] == 100
            assert progress_values.count(100) == 1
            assert any(
                entry["eta"] and entry["eta"] != "Complete"
                for entry in image_progress
                if entry["value"] < 100
            )

            exported = Image.open(output).convert('RGBA')
            assert exported.size == (640, 640)
            contract = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.renderNow();
                return {
                    profile: app.state.imageExportProfile,
                    preview: app.renderer.lastExportPreview,
                    capture: app.renderer.lastExportCapture
                };
            }""")
            assert contract["capture"]["outputSize"] == [640, 640]
            assert contract["capture"]["options"] == contract["profile"]["options"]
            assert contract["preview"]["options"] == contract["profile"]["options"]
            assert contract["capture"]["cameraProjection"] == pytest.approx(
                contract["preview"]["cameraProjection"]
            )
            assert contract["capture"]["cameraPosition"] == pytest.approx(
                contract["preview"]["cameraPosition"]
            )
            assert contract["capture"]["cameraQuaternion"] == pytest.approx(
                contract["preview"]["cameraQuaternion"]
            )

            preview_url = page.evaluate("""async () => {
                const renderer = window.__ASE_APP__.renderer;
                renderer.renderNow();
                const rect = renderer.lastExportPreview.frameRect;
                const sourceUrl = renderer.domElement.toDataURL('image/png');
                const source = await new Promise((resolve, reject) => {
                    const image = new Image();
                    image.onload = () => resolve(image);
                    image.onerror = reject;
                    image.src = sourceUrl;
                });
                const ratioX = source.naturalWidth / renderer.domElement.clientWidth;
                const ratioY = source.naturalHeight / renderer.domElement.clientHeight;
                const canvas = document.createElement('canvas');
                canvas.width = 640;
                canvas.height = 640;
                const context = canvas.getContext('2d');
                context.drawImage(
                    source,
                    rect.left * ratioX,
                    rect.top * ratioY,
                    rect.width * ratioX,
                    rect.height * ratioY,
                    0,
                    0,
                    640,
                    640
                );
                return canvas.toDataURL('image/png');
            }""")
            preview_bytes = base64.b64decode(preview_url.split(',', 1)[1])
            preview = Image.open(io.BytesIO(preview_bytes)).convert('RGBA')
            preview_pixels = np.asarray(preview, dtype=np.int16)
            export_pixels = np.asarray(exported, dtype=np.int16)
            absolute_difference = np.abs(preview_pixels - export_pixels)
            assert absolute_difference.mean() < 3.0
            assert np.quantile(absolute_difference, 0.99) < 24

            page.click('#btn-export-image')
            page.fill('#export-width', '768')
            page.fill('#export-height', '432')
            page.check('#export-transparent')
            page.select_option('#export-render-mode', 'modeling')
            page.wait_for_function(
                "window.__ASE_APP__.renderer.exportPreview?.width === 768 && "
                "window.__ASE_APP__.renderer.exportPreview?.height === 432 && "
                "window.__ASE_APP__.renderer.exportPreview?.options?.transparentBackground === true"
            )
            with page.expect_download(timeout=60_000) as transparent_download_info:
                page.click('#modal-export-image')
            transparent_download = transparent_download_info.value
            transparent_output = tmp_path / f"transparent-{transparent_download.suggested_filename}"
            transparent_download.save_as(transparent_output)
            transparent_image = Image.open(transparent_output).convert('RGBA')
            assert transparent_image.size == (768, 432)
            transparent_pixels = np.asarray(transparent_image)
            assert transparent_pixels[0, 0, 3] == 0
            transparent_contract = page.evaluate("""() => ({
                profile: window.__ASE_APP__.state.imageExportProfile,
                preview: window.__ASE_APP__.renderer.lastExportPreview,
                capture: window.__ASE_APP__.renderer.lastExportCapture
            })""")
            assert transparent_contract["profile"]["options"]["transparentBackground"] is True
            assert transparent_contract["capture"]["options"] == transparent_contract["profile"]["options"]
            assert transparent_contract["preview"]["options"] == transparent_contract["profile"]["options"]
            assert transparent_contract["capture"]["cameraProjection"] == pytest.approx(
                transparent_contract["preview"]["cameraProjection"]
            )

            context.close()
            browser.close()
    finally:
        editor.close()


def test_export_video_modal_keeps_actions_visible_in_a_short_viewport():
    first = molecule("H2O")
    second = first.copy()
    second.positions[:, 0] += 0.2
    port = find_free_port()
    editor = view(
        [first, second],
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1040, "height": 620})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2"
            )
            page.evaluate("window.__ASE_APP__.showExportVideoModal()")
            page.wait_for_function(
                "!document.getElementById('modal-container').classList.contains('hidden')"
            )
            layout = page.evaluate("""() => {
                const modal = document.querySelector('#modal-container .modal');
                const content = document.getElementById('modal-content');
                const actions = modal.querySelector('.modal-actions');
                const cancel = document.getElementById('modal-close');
                const submit = document.getElementById('modal-export-video');
                const modalRect = modal.getBoundingClientRect();
                const actionsRect = actions.getBoundingClientRect();
                const visible = element => {
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return style.visibility !== 'hidden'
                        && style.display !== 'none'
                        && rect.width > 0
                        && rect.height > 0
                        && rect.top >= 0
                        && rect.bottom <= window.innerHeight;
                };
                return {
                    modalTop: modalRect.top,
                    modalBottom: modalRect.bottom,
                    viewportHeight: window.innerHeight,
                    contentScrollable: content.scrollHeight > content.clientHeight,
                    actionsBottom: actionsRect.bottom,
                    cancelVisible: visible(cancel),
                    submitVisible: visible(submit)
                };
            }""")
            assert layout["modalTop"] >= 0
            assert layout["modalBottom"] <= layout["viewportHeight"]
            assert layout["contentScrollable"] is True
            assert layout["actionsBottom"] <= layout["viewportHeight"]
            assert layout["cancelVisible"] is True
            assert layout["submitVisible"] is True
            browser.close()
    finally:
        editor.close()


def test_trajectory_video_export_downloads_preview_matched_mov(tmp_path):
    first = molecule("H2O")
    first.set_cell([10.0, 10.0, 10.0])
    first.center()
    frames = [first]
    for shift in (0.35, 0.70):
        frame = first.copy()
        frame.positions[1:, 0] += shift
        frames.append(frame)

    port = find_free_port()
    editor = view(
        frames,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800}, accept_downloads=True)
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 3")
            page.evaluate("""() => {
                const toggle = document.getElementById('chk-displacement');
                toggle.checked = true;
                toggle.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                window.__videoCaptureRecords = [];
                window.__videoProgress = [];
                const originalCapture = app.renderer.renderExportCaptureFrame.bind(app.renderer);
                app.renderer.renderExportCaptureFrame = capture => {
                    window.__videoCaptureRecords.push({
                        frame: app.state.atoms.metadata.current_frame,
                        count: Number(app.renderer.domElement.dataset.displacementCount || 0),
                        visible: app.renderer.displacementGroup.visible
                    });
                    return originalCapture(capture);
                };
                const progress = document.getElementById('busy-progress');
                const recordProgress = () => {
                    window.__videoProgress.push({
                        value: Number(progress.getAttribute('aria-valuenow') || 0),
                        eta: document.getElementById('busy-progress-eta')?.textContent || ''
                    });
                };
                new MutationObserver(recordProgress).observe(progress, {
                    attributes: true,
                    attributeFilter: ['aria-valuenow']
                });
            }""")

            options = {
                "width": 320,
                "height": 256,
                "fps": 6,
                "format": "mov",
                "interpolationMultiplier": 2,
                "interpolationMic": True,
                "transparentBackground": False,
                "backgroundColor": "#ffffff",
                "includeGrid": False,
                "includeAxes": False,
                "scaleMode": "viewport",
                "pixelsPerAngstrom": 70,
                "sphereQuality": "medium",
                "sphereQualityScale": 1,
                "renderMode": "modeling",
                "sunIntensity": 2.2,
                "sunPosition": [8, -10, 14],
                "sunTarget": [0, 0, 0],
            }
            with page.expect_download(timeout=60_000) as download_info:
                page.evaluate("options => window.__ASE_APP__.exportTrajectoryVideo(options)", options)
            download = download_info.value
            output = tmp_path / download.suggested_filename
            download.save_as(output)

            assert output.suffix == ".mov"
            assert output.stat().st_size > 1000
            state = page.evaluate("""() => ({
                frame: window.__ASE_APP__.state.atoms.metadata.current_frame,
                captureActive: window.__ASE_APP__.renderer.exportCaptureActive,
                canvasWidth: window.__ASE_APP__.renderer.domElement.width,
                canvasHeight: window.__ASE_APP__.renderer.domElement.height
            })""")
            assert state["frame"] == 0
            assert state["captureActive"] is False
            assert state["canvasWidth"] > 320
            assert state["canvasHeight"] > 240

            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            probe = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            assert "h264" in probe.stderr.lower()
            assert "320x256" in probe.stderr

            decoded = imageio_ffmpeg.read_frames(str(output), pix_fmt="rgb24")
            metadata = next(decoded)
            decoded_frames = list(decoded)
            assert metadata["size"] == (320, 256)
            assert len(decoded_frames) == 5
            assert len({hashlib.sha1(frame).hexdigest() for frame in decoded_frames}) == 5
            export_contract = page.evaluate("""() => ({
                captures: window.__videoCaptureRecords,
                progress: window.__videoProgress
            })""")
            assert len(export_contract["captures"]) == 5
            assert any(
                capture["frame"] > 0
                and capture["count"] > 0
                and capture["visible"]
                for capture in export_contract["captures"]
            )
            progress_values = [
                entry["value"] for entry in export_contract["progress"]
            ]
            assert progress_values
            assert progress_values == sorted(progress_values)
            assert progress_values[-1] == 100
            assert progress_values.count(100) == 1
            assert any(
                "remaining" in entry["eta"].lower()
                for entry in export_contract["progress"]
            )

            first_frame = tmp_path / "video-first-frame.png"
            subprocess.run(
                [
                    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(output), "-frames:v", "1", str(first_frame),
                ],
                check=True,
                capture_output=True,
            )
            from PIL import Image

            with Image.open(first_frame).convert("RGB") as image:
                assert image.size == (320, 256)
                corner = image.getpixel((2, 2))
            assert min(corner) >= 245
            browser.close()
    finally:
        editor.close()


def test_trajectory_video_export_preserves_all_72_frames_at_30_fps(tmp_path):
    frames = []
    for index in range(72):
        angle = 2 * math.pi * index / 72
        frames.append(Atoms(
            "LiH",
            positions=[
                [4.0, 4.0, 4.0],
                [4.0 + 2.2 * math.cos(angle), 4.0 + 2.2 * math.sin(angle), 4.0],
            ],
            cell=[8.0, 8.0, 8.0],
            pbc=True,
        ))

    port = find_free_port()
    editor = view(
        frames,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 960, "height": 700}, accept_downloads=True)
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 72"
            )
            options = {
                "width": 320,
                "height": 256,
                "fps": 30,
                "format": "mov",
                "interpolationMultiplier": 1,
                "interpolationMic": True,
                "transparentBackground": False,
                "backgroundColor": "#ffffff",
                "includeGrid": False,
                "includeAxes": False,
                "includeCell": False,
                "scaleMode": "viewport",
                "pixelsPerAngstrom": 70,
                "sphereQuality": "medium",
                "sphereQualityScale": 1,
                "renderMode": "modeling",
                "sunIntensity": 2.2,
                "sunPosition": [8, -10, 14],
                "sunTarget": [0, 0, 0],
            }
            with page.expect_download(timeout=120_000) as download_info:
                page.evaluate(
                    "options => window.__ASE_APP__.exportTrajectoryVideo(options)",
                    options,
                )
            download = download_info.value
            output = tmp_path / download.suggested_filename
            download.save_as(output)

            import imageio_ffmpeg

            decoded = imageio_ffmpeg.read_frames(str(output), pix_fmt="rgb24")
            metadata = next(decoded)
            decoded_frames = list(decoded)
            assert metadata["size"] == (320, 256)
            assert metadata["fps"] == pytest.approx(30.0, abs=0.05)
            assert len(decoded_frames) == 72
            assert metadata["duration"] == pytest.approx(72 / 30, abs=0.05)
            assert len({
                hashlib.sha1(frame).hexdigest()
                for frame in decoded_frames
            }) >= 68
            browser.close()
    finally:
        editor.close()


def test_sidebar_sun_renderer_export_and_periodic_bond_contract():
    atoms = Atoms(
        "OO",
        positions=[[0.35, 0.0, 0.0], [9.65, 0.0, 0.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            initial = page.evaluate("""() => ({
                periodic: window.__ASE_APP__.state.display.showPeriodicBonds,
                bonds: window.__ASE_APP__.renderer.bondPairs.length,
                lighting: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadows: window.__ASE_APP__.renderer.renderer.shadowMap.enabled
            })""")
            assert initial == {
                "periodic": False,
                "bonds": 0,
                "lighting": "modeling",
                "shadows": False,
            }

            assert page.locator('body').evaluate("element => element.classList.contains('inspector-collapsed')")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'false'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Expand control panel'
            assert page.locator('#btn-inspector-collapse .inspector-edge-chevron').count() == 1
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            assert page.locator('#inspector').evaluate("element => Math.round(element.getBoundingClientRect().width)") == 0

            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 336")
            assert page.locator('#btn-inspector-collapse').get_attribute('aria-expanded') == 'true'
            assert page.locator('#btn-inspector-collapse').get_attribute('title') == 'Collapse control panel'
            edge_geometry = page.evaluate("""() => {
                const button = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    buttonRight: button.right,
                    panelLeft: panel.left,
                    verticalCenterDelta: Math.abs(
                        (button.top + button.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert edge_geometry['buttonRight'] == pytest.approx(edge_geometry['panelLeft'], abs=1.5)
            assert edge_geometry['verticalCenterDelta'] <= 1.5

            page.click('[data-inspector-group="view"]')
            assert page.locator('[data-panel="view"]').is_visible()
            assert not page.locator('[data-panel="structure-info"]').is_visible()
            assert not page.locator('[data-panel="appearance"]').is_visible()
            assert not page.locator('[data-panel="bonding"]').is_visible()
            page.click('[data-inspector-group="structure"]')
            assert page.locator('[data-panel="appearance"]').is_visible()
            page.select_option('#structure-section-select', 'bonding')
            assert page.locator('[data-panel="bonding"]').is_visible()
            page.click('[data-inspector-group="analysis"]')
            assert page.locator('[data-panel="displacement"]').is_visible()
            page.click('[data-inspector-group="export"]')
            assert page.locator('[data-panel="project"]').is_visible()
            assert page.locator('[data-panel="settings"]').is_visible()
            assert 'complete working structure' in page.locator('[data-panel="project"] .panel-note').inner_text()
            assert 'coordinates' in page.locator('[data-panel="settings"] .panel-note').inner_text()
            page.click('[data-inspector-group="view"]')
            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Escape')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            page.keyboard.press('Tab')
            page.wait_for_function("!document.body.classList.contains('inspector-collapsed')")

            page.click('[data-inspector-group="structure"]')
            _open_panel(page, 'bonding')
            page.check('#chk-periodic-bonds')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")
            assert page.locator('#app-viewport canvas').get_attribute('data-periodic-bonds') == 'true'

            lighting_icon = page.locator('#btn-lighting-toggle .render-light-icon')
            assert lighting_icon.is_visible()
            icon_box = lighting_icon.bounding_box()
            assert icon_box is not None
            assert icon_box['width'] == pytest.approx(31, abs=1)
            assert icon_box['height'] == pytest.approx(29, abs=1)
            viewport_tools = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                const calculator = document.getElementById('calc-controls').getBoundingClientRect();
                const scientificPanel = document.querySelector(
                    '[data-panel="scientific-tools"]'
                ).getBoundingClientRect();
                return {
                    triggerLeft: trigger.left,
                    contained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    ),
                    calculatorInTopBar: calculator.top < document.getElementById(
                        'top-bar'
                    ).getBoundingClientRect().bottom,
                    calculatorInsideRelaxation:
                        calculator.top >= scientificPanel.top
                        && calculator.bottom <= scientificPanel.bottom
                };
            }""")
            assert viewport_tools['contained'] is True
            assert viewport_tools['headerCenterDelta'] <= 2
            assert viewport_tools['calculatorInTopBar'] is False
            assert viewport_tools['calculatorInsideRelaxation'] is True
            page.click('#btn-lighting-toggle')
            lighting_panel_geometry = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const card = document.getElementById('lighting-card').getBoundingClientRect();
                const header = document.getElementById('top-bar').getBoundingClientRect();
                return {
                    triggerRight: trigger.right,
                    cardRight: card.right,
                    cardTop: card.top,
                    headerBottom: header.bottom
                };
            }""")
            assert lighting_panel_geometry['cardRight'] == pytest.approx(lighting_panel_geometry['triggerRight'], abs=1.5)
            assert lighting_panel_geometry['cardTop'] >= lighting_panel_geometry['headerBottom'] + 5
            page.select_option('#lighting-mode', 'studio-shadow')
            page.check('#chk-sun-gizmo')
            page.fill('#sun-position-x', '3')
            page.fill('#sun-position-y', '-3')
            page.fill('#sun-position-z', '4')
            page.wait_for_function("window.__ASE_APP__.renderer.sunGizmoGroup.visible")
            shadow_state = page.evaluate("""() => ({
                mode: window.__ASE_APP__.renderer.lightingOptions.lightingMode,
                shadowMap: window.__ASE_APP__.renderer.renderer.shadowMap.enabled,
                sunShadow: window.__ASE_APP__.renderer.studioSunLight.castShadow,
                modelingLights: window.__ASE_APP__.renderer.modelingLightGroup.visible,
                studioLights: window.__ASE_APP__.renderer.studioLightGroup.visible
            })""")
            assert shadow_state == {
                "mode": "studio-shadow",
                "shadowMap": True,
                "sunShadow": True,
                "modelingLights": False,
                "studioLights": True,
            }
            page.click('#btn-lighting-close')

            handle = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const point = app.renderer.sunGizmoGroup.userData.positionHandle.position.clone();
                point.project(app.renderer.camera);
                const rect = app.renderer.domElement.getBoundingClientRect();
                return {
                    x: rect.left + (point.x + 1) * rect.width / 2,
                    y: rect.top + (-point.y + 1) * rect.height / 2
                };
            }""")
            before_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            page.mouse.move(handle["x"], handle["y"])
            page.mouse.down()
            page.mouse.move(handle["x"] + 44, handle["y"] - 28, steps=6)
            page.mouse.up()
            after_direct_drag = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert after_direct_drag["position"] == pytest.approx(before_drag["position"])
            assert after_direct_drag["target"] == pytest.approx(before_drag["target"])
            assert after_direct_drag["selected"] == "source"
            assert after_direct_drag["rendererSelected"] == "source"

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('2')
            page.keyboard.press('Enter')
            after_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice(),
                mode: window.__ASE_APP__.transform.mode
            })""")
            assert after_move["position"] == pytest.approx([
                before_drag["position"][0] + 2,
                before_drag["position"][1],
                before_drag["position"][2],
            ])
            assert after_move["target"] == pytest.approx([
                before_drag["target"][0] + 2,
                before_drag["target"][1],
                before_drag["target"][2],
            ])
            assert after_move["mode"] == 'IDLE'

            direction_before_rotate = [
                after_move["target"][axis] - after_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_rotate = [
                after_rotate["target"][axis] - after_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_rotate["position"] == pytest.approx(after_move["position"])
            assert direction_after_rotate == pytest.approx([
                -direction_before_rotate[1],
                direction_before_rotate[0],
                direction_before_rotate[2],
            ])

            page.keyboard.press('r')
            page.keyboard.press('z')
            mouse_rotation = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const before = app.renderer.lightingOptions.sunTarget.map(
                    (value, axis) => value - app.renderer.lightingOptions.sunPosition[axis]
                );
                const pivot = app.state.rotationScreenPivot;
                app.updateRotationFromPointer(pivot.x + 90, pivot.y);
                app.updateRotationFromPointer(pivot.x, pivot.y + 90);
                app.applyTransformPreview();
                const after = app.renderer.lightingOptions.sunTarget.map(
                    (value, axis) => value - app.renderer.lightingOptions.sunPosition[axis]
                );
                return {
                    before,
                    after,
                    pointerAngle: app.transform.rotationAngle,
                    sunAngle: app.sunTransformRotation().angle,
                };
            }""")
            assert mouse_rotation["pointerAngle"] == pytest.approx(-1.57079632679, abs=1e-5)
            assert mouse_rotation["sunAngle"] == pytest.approx(1.57079632679, abs=1e-5)
            assert mouse_rotation["after"] == pytest.approx([
                -mouse_rotation["before"][1],
                mouse_rotation["before"][0],
                mouse_rotation["before"][2],
            ])
            page.keyboard.press('Escape')

            page.evaluate("window.__ASE_APP__.setSunSelected('target')")
            target_selection = page.evaluate("""() => ({
                selected: window.__ASE_APP__.state.sunSelected,
                rendererSelected: window.__ASE_APP__.renderer.sunGizmoSelected
            })""")
            assert target_selection == {"selected": "target", "rendererSelected": "target"}

            page.keyboard.press('g')
            page.keyboard.press('y')
            page.keyboard.type('3')
            page.keyboard.press('Enter')
            after_target_move = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            assert after_target_move["position"] == pytest.approx(after_rotate["position"])
            assert after_target_move["target"] == pytest.approx([
                after_rotate["target"][0],
                after_rotate["target"][1] + 3,
                after_rotate["target"][2],
            ])

            direction_before_target_rotate = [
                after_target_move["target"][axis] - after_target_move["position"][axis]
                for axis in range(3)
            ]
            page.keyboard.press('r')
            target_rotate_pivot = page.evaluate("window.__ASE_APP__.transform.pivot.toArray()")
            assert target_rotate_pivot == pytest.approx(after_target_move["position"])
            page.keyboard.press('z')
            page.keyboard.type('90')
            page.keyboard.press('Enter')
            after_target_rotate = page.evaluate("""() => ({
                position: window.__ASE_APP__.renderer.lightingOptions.sunPosition.slice(),
                target: window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()
            })""")
            direction_after_target_rotate = [
                after_target_rotate["target"][axis] - after_target_rotate["position"][axis]
                for axis in range(3)
            ]
            assert after_target_rotate["position"] == pytest.approx(after_target_move["position"])
            assert direction_after_target_rotate == pytest.approx([
                -direction_before_target_rotate[1],
                direction_before_target_rotate[0],
                direction_before_target_rotate[2],
            ])

            page.keyboard.press('g')
            page.keyboard.press('z')
            page.keyboard.type('2')
            page.keyboard.press('Escape')
            after_cancel = page.evaluate("window.__ASE_APP__.renderer.lightingOptions.sunTarget.slice()")
            assert after_cancel == pytest.approx(after_target_rotate["target"])

            directional_shadow = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const originalPositions = window.__ASE_APP__.state.atoms.positions.map(position => position.slice());
                const shiftedPositions = originalPositions.map(([x, y, z]) => [x + 120, y - 80, z + 45]);
                renderer.updatePositions(shiftedPositions);
                renderer.fitSunShadowCamera();
                const bounds = renderer.lightingStructureBounds();
                const center = bounds.getCenter(renderer.studioSunTarget.position.clone());
                const semanticDirection = renderer.studioSunTarget.position.clone()
                    .fromArray(renderer.lightingOptions.sunTarget)
                    .sub(renderer.studioSunLight.position.clone().fromArray(renderer.lightingOptions.sunPosition))
                    .normalize();
                const effectiveDirection = renderer.studioSunTarget.position.clone()
                    .sub(renderer.studioSunLight.position).normalize();
                const camera = renderer.studioSunLight.shadow.camera;
                camera.updateMatrixWorld(true);
                const inside = renderer.boxCorners(bounds).every(corner => {
                    const point = corner.clone().applyMatrix4(camera.matrixWorldInverse);
                    return point.x >= camera.left && point.x <= camera.right &&
                        point.y >= camera.bottom && point.y <= camera.top &&
                        -point.z >= camera.near && -point.z <= camera.far;
                });
                const result = {
                    directional: renderer.studioSunLight.isDirectionalLight,
                    center: center.toArray(),
                    effectiveTarget: renderer.studioSunTarget.position.toArray(),
                    semanticDirection: semanticDirection.toArray(),
                    effectiveDirection: effectiveDirection.toArray(),
                    inside
                };
                renderer.updatePositions(originalPositions);
                return result;
            }""")
            assert directional_shadow["directional"] is True
            assert max(abs(value) for value in directional_shadow["center"]) > 40
            assert directional_shadow["effectiveTarget"] == pytest.approx(directional_shadow["center"])
            assert directional_shadow["effectiveDirection"] == pytest.approx(
                directional_shadow["semanticDirection"]
            )
            assert directional_shadow["inside"] is True
            lighting_export = page.evaluate("window.__ASE_APP__.currentLightingForExport()")
            assert lighting_export["mode"] == "studio-shadow"
            assert lighting_export["intensity"] == pytest.approx(2.2)
            assert lighting_export["position"] == pytest.approx(after_target_rotate["position"])
            assert lighting_export["target"] == pytest.approx(after_target_rotate["target"])
            assert lighting_export["color"] == pytest.approx([1.0, 0.960784, 0.87451])

            export_contract = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const liveCamera = renderer.camera;
                const before = {
                    position: liveCamera.position.toArray(),
                    projection: liveCamera.projectionMatrix.elements.slice()
                };
                const viewport = renderer.exportCameraSetup(640, 640, { scaleMode: 'viewport' });
                const physical = renderer.exportCameraSetup(1000, 500, {
                    scaleMode: 'physical',
                    pixelsPerAngstrom: 100
                });
                const originalGeometry = renderer.atomMeshes.children[0].geometry;
                const dataUrl = renderer.exportPNG(640, 360, {
                    renderMode: 'studio-shadow',
                    sunIntensity: 2.6,
                    sunPosition: [4, -5, 7],
                    sunTarget: [0, 0, 0],
                    includeGrid: false,
                    includeAxes: false,
                    scaleMode: 'viewport',
                    sphereQuality: 'ultra',
                    sphereQualityScale: 1.5
                });
                return {
                    prefix: dataUrl.slice(0, 22),
                    dataUrl,
                    cloned: viewport.camera !== liveCamera,
                    viewportAspect: viewport.camera.isPerspectiveCamera
                        ? viewport.camera.aspect
                        : Math.abs(
                            (viewport.camera.right - viewport.camera.left) /
                            (viewport.camera.top - viewport.camera.bottom)
                        ),
                    viewportRender: [viewport.renderWidth, viewport.renderHeight],
                    viewportOffset: [viewport.offsetX, viewport.offsetY],
                    physicalSpan: [
                        (physical.camera.right - physical.camera.left) / physical.camera.zoom,
                        (physical.camera.top - physical.camera.bottom) / physical.camera.zoom
                    ],
                    geometryRestored: renderer.atomMeshes.children[0].geometry === originalGeometry,
                    after: {
                        position: liveCamera.position.toArray(),
                        projection: liveCamera.projectionMatrix.elements.slice()
                    },
                    before
                };
            }""")
            assert export_contract["prefix"] == "data:image/png;base64,"
            assert export_contract["cloned"] is True
            assert export_contract["viewportAspect"] == pytest.approx(1.0)
            assert export_contract["viewportRender"] == [640, 640]
            assert export_contract["viewportOffset"] == [0, 0]
            assert export_contract["physicalSpan"] == pytest.approx([10.0, 5.0])
            assert export_contract["geometryRestored"] is True
            assert export_contract["after"]["position"] == pytest.approx(
                export_contract["before"]["position"]
            )
            assert export_contract["after"]["projection"] == pytest.approx(
                export_contract["before"]["projection"]
            )
            exported_size = page.evaluate("""async dataUrl => {
                const image = new Image();
                const loaded = new Promise((resolve, reject) => {
                    image.onload = resolve;
                    image.onerror = reject;
                });
                image.src = dataUrl;
                await loaded;
                return [image.naturalWidth, image.naturalHeight];
            }""", export_contract["dataUrl"])
            assert exported_size == [640, 360]

            page.click('[data-inspector-group="view"]')
            page.fill('#atomic-scale', '80')
            page.wait_for_function("Math.abs(window.__ASE_APP__.renderer.currentPixelsPerAngstrom() - 80) < 0.02")
            page.click('[data-inspector-group="export"]')
            page.click('#btn-export-image')
            assert page.locator('#export-framing-mode').is_visible()
            assert page.locator('#export-pixels-per-angstrom').count() == 0
            page.select_option('#export-framing-mode', 'physical')
            page.fill('#export-width', '1600')
            page.fill('#export-height', '800')
            assert 'View > Atomic scale (80.00 px/Å)' in page.locator('#export-scale-note').inner_text()
            assert '20.00 Å × 10.00 Å' in page.locator('#export-scale-note').inner_text()
            page.select_option('#export-sphere-quality', 'auto')
            page.fill('#export-smoothness-scale', '1.5')
            assert '48 sphere segments' in page.locator('#export-smoothness-note').inner_text()
            page.click('#modal-close')

            page.click('#btn-lighting-toggle')
            page.select_option('#lighting-mode', 'modeling')
            page.wait_for_function("!window.__ASE_APP__.renderer.renderer.shadowMap.enabled")
            page.wait_for_timeout(100)
            start = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            time.sleep(0.35)
            end = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            assert end == start

            page.click('#btn-lighting-close')
            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.body.classList.contains('inspector-collapsed')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width <= 1")
            mobile_collapsed = page.evaluate("""() => {
                const trigger = document.getElementById('btn-lighting-toggle').getBoundingClientRect();
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                const actionGroup = document.querySelector('.action-group').getBoundingClientRect();
                return {
                    panelWidth: panel.width,
                    handleRight: handle.right,
                    viewportWidth: window.innerWidth,
                    triggerRight: trigger.right,
                    handleLeft: handle.left,
                    handleOverlap: !(
                        trigger.right <= handle.left ||
                        trigger.left >= handle.right ||
                        trigger.bottom <= handle.top ||
                        trigger.top >= handle.bottom
                    ),
                    triggerContained: trigger.left >= actionGroup.left && trigger.right <= actionGroup.right,
                    headerCenterDelta: Math.abs(
                        (trigger.top + trigger.height / 2) -
                        (actionGroup.top + actionGroup.height / 2)
                    ),
                    handleVerticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_collapsed['panelWidth'] == pytest.approx(0, abs=1)
            assert mobile_collapsed['handleRight'] == pytest.approx(mobile_collapsed['viewportWidth'], abs=1)
            assert mobile_collapsed['handleOverlap'] is False
            assert mobile_collapsed['triggerContained'] is True
            assert mobile_collapsed['headerCenterDelta'] <= 2
            assert mobile_collapsed['handleVerticalCenterDelta'] <= 1.5

            page.click('#btn-inspector-collapse')
            page.wait_for_function("document.getElementById('inspector').getBoundingClientRect().width >= 345.5")
            mobile_expanded = page.evaluate("""() => {
                const handle = document.getElementById('btn-inspector-collapse').getBoundingClientRect();
                const panel = document.getElementById('inspector').getBoundingClientRect();
                return {
                    handleRight: handle.right,
                    panelLeft: panel.left,
                    panelWidth: panel.width,
                    verticalCenterDelta: Math.abs(
                        (handle.top + handle.height / 2) -
                        (panel.top + panel.height / 2)
                    )
                };
            }""")
            assert mobile_expanded['panelWidth'] == pytest.approx(346, abs=1)
            assert mobile_expanded['handleRight'] == pytest.approx(mobile_expanded['panelLeft'], abs=1)
            assert mobile_expanded['verticalCenterDelta'] <= 1.5

            browser.close()
    finally:
        editor.close()


def test_grid_button_and_ordered_distance_angle_torsion_measurements():
    positions = np.array([
        [-3.0, -1.0, 0.0],
        [-1.0, -1.0, 0.0],
        [0.5, 0.5, 0.0],
        [2.5, 0.5, 1.2],
        [4.5, 3.5, 0.0],
    ])
    atoms = Atoms("H5", positions=positions, cell=[14.0, 12.0, 10.0], pbc=False)
    set_atom_labels(atoms, ["H", "H", "H_alt", "H_alt", "H_alt"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 5")

            grid_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const button = document.getElementById('btn-grid-toggle');
                const rect = button.getBoundingClientRect();
                return {
                    state: app.state.display.showGrid,
                    visible: app.renderer.gridGroup.visible,
                    checked: document.getElementById('chk-grid').checked,
                    pressed: button.getAttribute('aria-pressed'),
                    buttonVisible: rect.width > 0 && rect.height > 0 &&
                        rect.left >= 0 && rect.right <= window.innerWidth
                };
            }""")
            assert grid_state == {
                "state": True,
                "visible": True,
                "checked": True,
                "pressed": "true",
                "buttonVisible": True,
            }
            page.click("#btn-grid-toggle")
            page.wait_for_function("window.__ASE_APP__.renderer.gridGroup.visible === false")
            assert page.evaluate("""() => ({
                state: window.__ASE_APP__.state.display.showGrid,
                checked: document.getElementById('chk-grid').checked,
                pressed: document.getElementById('btn-grid-toggle').getAttribute('aria-pressed'),
                label: document.getElementById('btn-grid-toggle').getAttribute('aria-label')
            })""") == {
                "state": False,
                "checked": False,
                "pressed": "false",
                "label": "Show viewport grid",
            }
            page.click("#btn-grid-toggle")
            page.wait_for_function("window.__ASE_APP__.renderer.gridGroup.visible === true")

            points = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const target = renderer.controls.target;
                target.set(0.5, 0.5, 0);
                renderer.camera.position.set(0.5, 0.5, 22);
                renderer.camera.up.set(0, 1, 0);
                renderer.camera.lookAt(target);
                renderer.camera.updateMatrixWorld(true);
                app.completeCameraViewChange('ordered-measurement-test');
                const rect = renderer.domElement.getBoundingClientRect();
                return app.state.atoms.positions.map((values, index) => {
                    const position = renderer.getAtomPosition(index).clone().project(renderer.camera);
                    return {
                        x: rect.left + (position.x + 1) * rect.width / 2,
                        y: rect.top + (1 - position.y) * rect.height / 2
                    };
                });
            }""")

            def click_atom(index, additive=False):
                if additive:
                    page.keyboard.down("Shift")
                page.mouse.click(points[index]["x"], points[index]["y"])
                if additive:
                    page.keyboard.up("Shift")
                page.wait_for_function(
                    f"window.__ASE_APP__.selectionCount() === {index + 1}"
                )

            def measurement_state():
                return page.evaluate("""() => {
                    const overlay = document.getElementById('measurement-overlay');
                    const badges = [...overlay.querySelectorAll('.measure-atom-badge')];
                    const boxes = badges.map(badge => {
                        const rect = badge.getBoundingClientRect();
                        return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom};
                    });
                    const overlaps = boxes.some((a, index) => boxes.slice(index + 1).some(b =>
                        Math.min(a.right, b.right) > Math.max(a.left, b.left) &&
                        Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top)
                    ));
                    return {
                        order: [...window.__ASE_APP__.state.selectionOrder],
                        kind: overlay.dataset.measureKind,
                        hidden: overlay.classList.contains('hidden'),
                        labels: badges.map(badge => badge.textContent),
                        references: badges.map(badge => badge.dataset.reference),
                        connectors: overlay.querySelectorAll('.measure-connector').length,
                        torsionAxes: overlay.querySelectorAll('.measure-torsion-axis').length,
                        angleArcs: overlay.querySelectorAll('.measure-angle-arc').length,
                        values: [...overlay.querySelectorAll('.measure-value-badge text')]
                            .map(value => value.textContent),
                        detail: document.getElementById('selected-measure').innerText,
                        summary: document.getElementById('selection-measure-value').innerText,
                        overlaps
                    };
                }""")

            click_atom(0)
            one = measurement_state()
            assert one["order"] == ["atom:0"]
            assert one["kind"] == "point"
            assert one["labels"] == ["a1"]
            assert one["references"] == ["0"]
            assert one["connectors"] == 0
            assert one["detail"] == "a1=#0 H"

            click_atom(1, additive=True)
            two = measurement_state()
            assert two["order"] == ["atom:0", "atom:1"]
            assert two["kind"] == "distance"
            assert two["labels"] == ["a1", "a2"]
            assert two["connectors"] == 1
            assert "Direct: d(a1-a2) = 2.0000 A" in two["detail"]
            assert "MIC: d(a1-a2) = 2.0000 A" in two["detail"]
            assert two["summary"] == (
                "Distance a1-a2 | Direct 2.0000 A | MIC 2.0000 A"
            )
            assert two["values"] == ["Direct 2.000 | MIC 2.000 A"]
            assert two["overlaps"] is False

            click_atom(2, additive=True)
            three = measurement_state()
            assert three["order"] == ["atom:0", "atom:1", "atom:2"]
            assert three["kind"] == "angle"
            assert three["labels"] == ["a1", "a2", "a3"]
            assert three["connectors"] == 2
            assert three["angleArcs"] == 1
            assert three["torsionAxes"] == 0
            assert "Direct: d(a1-a2) = 2.0000 A" in three["detail"]
            assert "MIC:" not in three["detail"]
            assert "angle(a1-a2-a3) = 135.00 deg" in three["detail"]
            assert three["summary"] == (
                "Angle a1-a2-a3 | Direct 135.00 deg"
            )
            assert three["values"] == ["Direct 135.0 deg"]
            assert three["overlaps"] is False

            click_atom(3, additive=True)
            four = measurement_state()
            first = positions[1] - positions[0]
            middle = positions[2] - positions[1]
            last = positions[3] - positions[2]
            first_normal = np.cross(first, middle)
            second_normal = np.cross(middle, last)
            first_normal /= np.linalg.norm(first_normal)
            second_normal /= np.linalg.norm(second_normal)
            expected_torsion = math.degrees(math.atan2(
                np.dot(
                    np.cross(first_normal, second_normal),
                    middle / np.linalg.norm(middle),
                ),
                np.dot(first_normal, second_normal),
            ))
            ase_torsion = atoms.get_dihedral(0, 1, 2, 3, mic=False)
            ase_signed_torsion = (
                ase_torsion - 360.0 if ase_torsion > 180.0 else ase_torsion
            )
            assert expected_torsion == pytest.approx(ase_signed_torsion, abs=1e-8)
            browser_torsion = page.evaluate(
                "() => window.__ASE_APP__.selectionTorsion(...window.__ASE_APP__.selectionEntries())"
            )
            assert browser_torsion == pytest.approx(expected_torsion, abs=1e-8)
            assert four["order"] == ["atom:0", "atom:1", "atom:2", "atom:3"]
            assert four["kind"] == "torsion"
            assert four["labels"] == ["a1", "a2", "a3", "a4"]
            assert four["connectors"] == 3
            assert four["torsionAxes"] == 1
            assert four["angleArcs"] == 0
            assert "torsion(a1-a2-a3-a4)" in four["detail"]
            assert "MIC:" not in four["detail"]
            assert four["summary"].startswith("Torsion a1-a2-a3-a4")
            assert four["summary"] == (
                f"Torsion a1-a2-a3-a4 | Direct {expected_torsion:.2f} deg"
            )
            assert four["values"] == [f"Direct {expected_torsion:.1f} deg"]
            assert four["overlaps"] is False

            click_atom(4, additive=True)
            five = measurement_state()
            assert five["kind"] == "none"
            assert five["hidden"] is True
            assert five["labels"] == []
            assert five["connectors"] == 0
            assert five["detail"] == "5 atoms selected | H: 2, H_alt: 3"
            assert five["summary"] == "5 atoms selected | H: 2, H_alt: 3"

            page.locator("#app-viewport canvas").focus()
            page.keyboard.press("Alt+a")
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 0")
            box_points = points[:3]
            left = min(point["x"] for point in box_points) - 10
            right = max(point["x"] for point in box_points) + 10
            top = min(point["y"] for point in box_points) - 10
            bottom = max(point["y"] for point in box_points) + 10
            page.mouse.move(left, top)
            page.mouse.down()
            page.mouse.move(right, bottom, steps=8)
            page.mouse.up()
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 3")
            boxed = measurement_state()
            assert boxed["order"] == ["atom:0", "atom:1", "atom:2"]
            assert boxed["kind"] == "angle"
            assert boxed["labels"] == ["a1", "a2", "a3"]
            assert boxed["references"] == ["0", "1", "2"]
            assert boxed["connectors"] == 2
            assert boxed["angleArcs"] == 1
            assert boxed["summary"] == (
                "Angle a1-a2-a3 | Direct 135.00 deg"
            )
            assert boxed["overlaps"] is False
            browser.close()
    finally:
        editor.close()


def test_live_view_axes_and_unit_cell_toggles_control_viewport_guides():
    atoms = Atoms(
        "Si2",
        positions=[[1.0, 1.0, 1.0], [3.0, 3.0, 3.0]],
        cell=[6.0, 7.0, 8.0],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
        show_axes=True,
        show_cell=True,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1360, "height": 820})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.cellGroup?.children?.length > 0"
            )
            _expand_inspector(page)
            page.click('[data-inspector-group="view"]')

            assert page.locator("#chk-axes").is_checked()
            assert page.locator("#chk-cell").is_checked()
            assert page.evaluate("""() => ({
                axes: window.__ASE_APP__.renderer.axesHelper.visible,
                cell: window.__ASE_APP__.renderer.cellGroup.visible
            })""") == {"axes": True, "cell": True}

            page.uncheck("#chk-axes")
            page.uncheck("#chk-cell")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.display.showAxes === false
                    && app.state.display.showCell === false
                    && app.renderer.axesHelper.visible === false
                    && app.renderer.cellGroup.visible === false;
            }""")

            page.check("#chk-axes")
            page.check("#chk-cell")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.display.showAxes === true
                    && app.state.display.showCell === true
                    && app.renderer.axesHelper.visible === true
                    && app.renderer.cellGroup.visible === true;
            }""")
            browser.close()
    finally:
        editor.close()


def test_periodic_measurement_reports_direct_and_mic_values():
    atoms = Atoms(
        "HH",
        positions=[[0.5, 0.0, 0.0], [9.5, 0.0, 0.0]],
        cell=[10.0, 8.0, 8.0],
        pbc=[True, False, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2"
            )
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.addSelectionReference(0);
                app.addSelectionReference(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.wait_for_function(
                "document.getElementById('selected-measure').innerText.includes('Direct:')"
            )
            measured = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    direct: app.selectionDistance(0, 1, {mic: false}),
                    mic: app.selectionDistance(0, 1, {mic: true}),
                    detail: document.getElementById('selected-measure').innerText,
                    summary: document.getElementById('selection-measure-value').innerText,
                    overlayValues: [...document.querySelectorAll(
                        '.measure-value-badge text'
                    )].map(value => value.textContent),
                    background: `#${app.renderer.scene.background.getHexString()}`,
                    backgroundMode: app.state.display.viewportBackground,
                };
            }""")
            assert measured["direct"] == pytest.approx(9.0)
            assert measured["mic"] == pytest.approx(1.0)
            assert "Direct: d(a1-a2) = 9.0000 A" in measured["detail"]
            assert "MIC: d(a1-a2) = 1.0000 A" in measured["detail"]
            assert measured["summary"] == (
                "Distance a1-a2 | Direct 9.0000 A | MIC 1.0000 A"
            )
            assert measured["overlayValues"] == [
                "Direct 9.000 | MIC 1.000 A"
            ]
            assert measured["background"] == "#ffffff"
            assert measured["backgroundMode"] == "white"
            browser.close()
    finally:
        editor.close()


def test_auto_bond_defaults_keep_metal_pairs_clean_and_metal_ligands_visible():
    atoms = Atoms(
        "Cu2O",
        positions=[
            [0.0, 0.0, 0.0],
            [2.8, 0.0, 0.0],
            [0.0, 2.47, 0.0],
        ],
        cell=[12.0, 12.0, 12.0],
        pbc=False,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3"
            )
            page.wait_for_function(
                "JSON.stringify(window.__ASE_APP__.renderer.bondPairs) === '[[0,2]]'"
            )
            defaults = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    cuCu: renderer.bondCutoffForPair(0, 1),
                    cuO: renderer.bondCutoffForPair(0, 2),
                    pairs: renderer.bondPairs
                };
            }""")
            assert defaults["cuCu"] == pytest.approx(0.0)
            assert defaults["cuO"] == pytest.approx(2.48)
            assert defaults["pairs"] == [[0, 2]]

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.bondMode = 'pairwise';
                app.state.display.pairwiseBondCutoffs = {'Cu-Cu': 3.0};
                app.renderer.setDisplayOptions(app.state.display);
            }""")
            page.wait_for_function(
                "JSON.stringify(window.__ASE_APP__.renderer.bondPairs) === '[[0,1]]'"
            )
            browser.close()
    finally:
        editor.close()


def test_cell_local_bonds_clip_at_the_displayed_supercell_boundary():
    atoms = Atoms(
        "CCCC",
        scaled_positions=[
            [0.95, 0.20, 0.25],
            [0.05, 0.20, 0.25],
            [0.70, 0.95, 0.75],
            [0.70, 0.05, 0.75],
        ],
        cell=[[4.0, 0.0, 0.0], [1.2, 3.6, 0.0], [0.0, 0.0, 8.0]],
        pbc=[True, True, False],
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4")

            # The two nearest C-C images lie across +a and +b. A single
            # displayed cell correctly clips both at its outer boundary.
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 0")
            assert page.locator('#app-viewport canvas').get_attribute(
                'data-supercell-bridge-bond-count'
            ) == '0'

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            page.fill('#super-x', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[0] === 2")
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '1'"
            )
            doubled = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    basePairs: renderer.bondPairs.length,
                    records: renderer.supercellBridgeBondRecords.map(record => ({
                        i: record.i,
                        j: record.j,
                        imageOffset: record.imageOffset
                    })),
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert doubled == {
                "basePairs": 0,
                "records": [{"i": 0, "j": 1, "imageOffset": [1, 0, 0]}],
                "bridgeSegments": 2,
                "totalSegments": 2,
            }

            # Three cells contain two internal boundaries. There is no third
            # bond through the outer edge of the displayed supercell.
            page.fill('#super-x', '3')
            page.keyboard.press('Tab')
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '2'"
            )
            tripled = page.evaluate("""() => {
                const meshes = window.__ASE_APP__.renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert tripled == {"bridgeSegments": 4, "totalSegments": 4}

            # A 2x2x1 display contains two internal a-boundary bonds (one per
            # b row) and two internal b-boundary bonds (one per a column).
            page.fill('#super-x', '2')
            page.fill('#super-y', '2')
            page.keyboard.press('Tab')
            page.wait_for_function(
                "document.querySelector('#app-viewport canvas').dataset.supercellBridgeBondCount === '4'"
            )
            doubled_xy = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.supercellGroup.children.filter(
                    child => child.userData.supercellBonds
                );
                return {
                    records: renderer.supercellBridgeBondRecords.map(record => ({
                        i: record.i,
                        j: record.j,
                        imageOffset: record.imageOffset
                    })),
                    bridgeSegments: meshes.reduce((sum, mesh) => sum +
                        mesh.userData.bondInstances.filter(instance => instance.bridge).length, 0),
                    totalSegments: meshes.reduce((sum, mesh) => sum + mesh.count, 0)
                };
            }""")
            assert doubled_xy == {
                "records": [
                    {"i": 0, "j": 1, "imageOffset": [1, 0, 0]},
                    {"i": 2, "j": 3, "imageOffset": [0, 1, 0]},
                ],
                "bridgeSegments": 8,
                "totalSegments": 8,
            }
            browser.close()
    finally:
        editor.close()


def test_interactive_bonds_reinfer_live_and_cutoffs_survive_structure_updates():
    atoms = Atoms(
        "CC",
        positions=[[0.0, 0.0, 0.0], [0.7, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=False,
    )
    set_atom_labels(atoms, ["C_left", "C_right"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'pairwise')
            cutoff = page.locator('.pairwise-bond-max[data-pair-key="C_left-C_right"]')
            assert cutoff.count() == 1
            cutoff.fill('0.90')
            page.wait_for_function(
                "Math.abs(window.__ASE_APP__.state.display.pairwiseBondCutoffs['C_left-C_right'] - 0.9) < 1e-9"
            )
            cutoff.fill('0')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.pairwiseBondCutoffs['C_left-C_right'] === 0 && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )
            cutoff.fill('0.90')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")
            assert page.locator('.pairwise-bond-min').count() == 0
            initial_width = page.evaluate(
                "window.__ASE_APP__.state.display.pairwiseLabelColumnWidth"
            )
            resizer = page.locator("#pairwise-label-column-resizer")
            resizer_box = resizer.bounding_box()
            assert resizer_box is not None
            page.mouse.move(
                resizer_box["x"] + resizer_box["width"] / 2,
                resizer_box["y"] + resizer_box["height"] / 2,
            )
            page.mouse.down()
            page.mouse.move(
                resizer_box["x"] + resizer_box["width"] / 2 + 48,
                resizer_box["y"] + resizer_box["height"] / 2,
            )
            page.mouse.up()
            page.wait_for_function(
                "before => window.__ASE_APP__.state.display.pairwiseLabelColumnWidth > before + 35",
                arg=initial_width,
            )
            resized = page.evaluate("""() => ({
                state: window.__ASE_APP__.state.display.pairwiseLabelColumnWidth,
                snapshot: window.__ASE_APP__.designSettingsSnapshot().display.pairwiseLabelColumnWidth,
                css: getComputedStyle(document.getElementById('pairwise-bond-panel'))
                    .getPropertyValue('--pair-label-width').trim()
            })""")
            assert resized["state"] == resized["snapshot"]
            assert resized["css"] == f'{resized["state"]}px'

            page.evaluate("""() => {
                document.activeElement?.blur();
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                mode: window.__ASE_APP__.state.display.bondMode,
                cutoff: window.__ASE_APP__.state.display.pairwiseBondCutoffs['C_left-C_right'],
                input: Number(document.querySelector('.pairwise-bond-max[data-pair-key="C_left-C_right"]').value),
                bonds: window.__ASE_APP__.renderer.bondPairs.length
            })""")
            assert persisted == {
                "mode": "pairwise",
                "cutoff": 0.9,
                "input": 0.9,
                "bonds": 0,
            }

            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('-1.0')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'MOVE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 1"
            )
            page.keyboard.press('Escape')
            page.wait_for_function(
                "window.__ASE_APP__.transform.mode === 'IDLE' && "
                "window.__ASE_APP__.renderer.bondPairs.length === 0"
            )

            relabeled = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.pairwiseBondCutoffs['C_left-C_right'] = 1.23;
                app.state.display.pairwiseBondRanges['C_left-C_right'] = {
                    enabled: true,
                    min: 0,
                    max: 1.23
                };
                app.renameAtomLabelForVisualization('C_left', 'C_custom', [0], 'C', {preserveAppearance: true});
                return {
                    labels: [...app.state.atoms.symbols],
                    order: [...app.state.labelOrder],
                    cutoff: app.state.display.pairwiseBondCutoffs['C_custom-C_right'],
                    rendererCutoff: app.renderer.bondCutoffForPair(0, 1),
                    input: Number(document.querySelector('.pairwise-bond-max[data-pair-key="C_custom-C_right"]')?.value),
                };
            }""")
            assert relabeled == {
                "labels": ["C_custom", "C_right"],
                "order": ["C_custom", "C_right"],
                "cutoff": 1.23,
                "rendererCutoff": 1.23,
                "input": 1.23,
            }
            browser.close()
    finally:
        editor.close()


def test_large_scene_neighbor_cache_keeps_live_bond_topology_exact():
    positions = [[0.0, 0.0, 0.0], [1.1, 0.0, 0.0]]
    positions.extend(
        [10.0 + (index % 20) * 3.0, 10.0 + (index // 20) * 3.0, 0.0]
        for index in range(398)
    )
    atoms = Atoms(
        "H400",
        positions=positions,
        cell=[80.0, 80.0, 10.0],
        pbc=False,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 400"
            )
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.bondMode = 'pairwise';
                app.state.display.pairwiseBondCutoffs = {'H-H': 1.0};
                app.renderer.setDisplayOptions(app.state.display);
            }""")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.bondPairs.length === 0 && "
                "window.__ASE_APP__.renderer.bondNeighborCache !== null"
            )
            initial_cache = page.evaluate("""() => {
                const cache = window.__ASE_APP__.renderer.bondNeighborCache;
                return {
                    referenceX: cache.referencePositions[3],
                    hasPair: cache.candidatePairs.some(
                        (value, offset) => offset % 2 === 0
                            && value === 0
                            && cache.candidatePairs[offset + 1] === 1
                    )
                };
            }""")
            assert initial_cache["referenceX"] == pytest.approx(1.1, abs=1e-5)
            assert initial_cache["hasPair"] is True

            within_skin = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const positions = renderer.currentPositions();
                positions[1] = [0.95, 0, 0];
                renderer.updatePositions(positions);
                return {
                    bonds: renderer.bondPairs,
                    referenceX: renderer.bondNeighborCache.referencePositions[3]
                };
            }""")
            assert within_skin["bonds"] == [[0, 1]]
            assert within_skin["referenceX"] == pytest.approx(1.1, abs=1e-5)

            beyond_skin = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const positions = renderer.currentPositions();
                positions[1] = [1.6, 0, 0];
                renderer.updatePositions(positions);
                return {
                    bonds: renderer.bondPairs,
                    referenceX: renderer.bondNeighborCache.referencePositions[3]
                };
            }""")
            assert beyond_skin["bonds"] == []
            assert beyond_skin["referenceX"] == pytest.approx(1.6, abs=1e-5)
            browser.close()
    finally:
        editor.close()


def test_15000_atom_view_keeps_material_presets_instanced_and_renders_under_five_seconds():
    shape = (25, 25, 24)
    positions = np.indices(shape).reshape(3, -1).T.astype(float) * 1.8
    atoms = Atoms(
        numbers=np.full(len(positions), 6, dtype=int),
        positions=positions,
        cell=np.asarray(shape, dtype=float) * 1.8,
        pbc=True,
    )
    set_atom_labels(atoms, ["C_bulk"] * len(atoms))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            started = time.perf_counter()
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 15000",
                timeout=15_000,
            )
            first_render_seconds = time.perf_counter() - started
            print(f"V_ASE_15000_ATOM_FIRST_RENDER_SECONDS={first_render_seconds:.3f}")
            initial = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    groups: renderer.atomMeshes.children.length,
                    instances: renderer.atomMeshes.children.reduce(
                        (total, mesh) => total + (mesh.isInstancedMesh ? mesh.count : 1),
                        0
                    ),
                    pixelRatio: renderer.renderer.getPixelRatio(),
                };
            }""")
            assert first_render_seconds < 5.0
            assert initial["groups"] == 1
            assert initial["instances"] == 15_000
            assert initial["pixelRatio"] <= 1

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.labelMaterials.C_bulk = 'metal';
                app.renderer.setDisplayOptions(app.state.display);
            }""")
            page.wait_for_function("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return renderer.atomMeshes.children.length === 1
                    && renderer.atomMeshes.children[0].count === 15000
                    && Math.abs(renderer.atomMeshes.children[0].material.metalness - 0.90) < 1e-6;
            }""")
            metal_state = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const material = renderer.atomMeshes.children[0].material;
                return {
                    groups: renderer.atomMeshes.children.length,
                    metalness: material.metalness,
                    roughness: material.roughness,
                    envMapIntensity: material.envMapIntensity,
                    environmentName: material.envMap?.name || '',
                    environmentShared: material.envMap === renderer.metalEnvironmentMap
                };
            }""")
            assert metal_state == {
                "groups": 1,
                "metalness": pytest.approx(0.90),
                "roughness": pytest.approx(0.18),
                "envMapIntensity": pytest.approx(2.15),
                "environmentName": "v_ase_metal_studio_environment",
                "environmentShared": True,
            }
            browser.close()
    finally:
        editor.close()


def test_metal_material_has_visible_studio_reflections(tmp_path):
    atoms = Atoms("Cu", positions=[[0.0, 0.0, 0.0]])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 960, "height": 720})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1"
            )
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                Object.assign(app.state.display, {
                    showGrid: false,
                    showAxes: false,
                    showCell: false,
                    atomRadiusScale: 1.4,
                    labelMaterials: {Cu: 'standard'}
                });
                app.renderer.setDisplayOptions(app.state.display);
                app.renderer.fitCameraToStructure();
            }""")
            page.wait_for_timeout(150)
            standard_path = tmp_path / "standard-cu.png"
            page.locator("#app-viewport canvas").screenshot(path=str(standard_path))

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.display.labelMaterials.Cu = 'metal';
                app.renderer.setDisplayOptions(app.state.display);
            }""")
            page.wait_for_function("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const material = renderer.atomMeshByIndex.get(0)?.material;
                return material?.metalness > 0.85
                    && material?.envMap?.name === 'v_ase_metal_studio_environment';
            }""")
            page.wait_for_timeout(150)
            metal_path = tmp_path / "metal-cu.png"
            page.locator("#app-viewport canvas").screenshot(path=str(metal_path))

            def surface_luminance(path):
                pixels = np.asarray(Image.open(path).convert("RGB"), dtype=float)
                height, width, _ = pixels.shape
                pixels = pixels[
                    int(height * 0.24):int(height * 0.72),
                    int(width * 0.28):int(width * 0.72),
                ]
                mask = np.min(pixels, axis=2) < 220
                values = (
                    0.2126 * pixels[:, :, 0]
                    + 0.7152 * pixels[:, :, 1]
                    + 0.0722 * pixels[:, :, 2]
                )[mask]
                assert values.size > 3_000
                return {
                    "p05": float(np.percentile(values, 5)),
                    "p50": float(np.percentile(values, 50)),
                    "p95": float(np.percentile(values, 95)),
                    "spread": float(np.percentile(values, 95) - np.percentile(values, 5)),
                }

            standard = surface_luminance(standard_path)
            metal = surface_luminance(metal_path)
            print(
                "V_ASE_METAL_VISUAL_QA "
                f"standard={standard} metal={metal} "
                f"standard_path={standard_path} metal_path={metal_path}"
            )
            assert metal["spread"] > standard["spread"] * 1.10
            assert metal["p05"] < standard["p05"] - 20
            browser.close()
    finally:
        editor.close()


def test_bond_style_thickness_and_color_modes_render_and_persist():
    atoms = Atoms(
        "HO",
        positions=[[0.0, 0.0, 0.0], [2.4, 0.0, 0.0]],
        cell=[[8.0, 0.0, 0.0], [1.2, 8.0, 0.0], [0.3, 0.5, 8.0]],
        pbc=True,
    )
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            _open_panel(page, 'bonding')
            page.select_option('#bond-mode', 'manual')
            page.fill('#bond-pairs', '0-1')
            page.wait_for_function("window.__ASE_APP__.renderer.bondPairs.length === 1")

            default_bond = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const meshes = renderer.bondGroup.children;
                return {
                    styles: meshes.map(mesh => mesh.geometry.type),
                    segments: meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0),
                    colors: meshes.map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert default_bond["styles"] == ["CylinderGeometry", "CylinderGeometry"]
            assert default_bond["segments"] == 2
            assert default_bond["colors"] == default_bond["expected"]

            page.select_option('#bond-style', 'flat')
            page.select_option('#bond-color-mode', 'custom')
            page.fill('#bond-thickness', '0.24')
            page.fill('#bond-custom-color', '#18a7d8')
            page.locator('#bond-pairs').click()
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                return app.state.display.bondStyle === 'flat'
                    && app.state.display.bondColorMode === 'custom'
                    && Math.abs(app.state.display.bondThickness - 0.24) < 1e-9
                    && app.state.display.bondCustomColor === '#18a7d8'
                    && mesh.geometry.type === 'PlaneGeometry'
                    && mesh.userData.bondSegments.length === 1
                    && mesh.userData.bondColor === '#18a7d8'
                    && mesh.material.color.getHexString() === '18a7d8';
            }""")
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const mesh = app.renderer.bondGroup.children[0];
                const matrix = Array.from(mesh.instanceMatrix.array.slice(0, 16));
                return {
                    thickness: Math.hypot(matrix[0], matrix[1], matrix[2]),
                    output: document.getElementById('bond-thickness-value').innerText,
                    customVisible: !document.getElementById('bond-custom-color-row').classList.contains('hidden'),
                    color: `#${mesh.material.color.getHexString()}`,
                    matrix
                };
            }""")
            assert flat_state["thickness"] == pytest.approx(0.24, abs=1e-5)
            assert flat_state["output"] == "0.24 A"
            assert flat_state["customVisible"] is True
            assert flat_state["color"] == "#18a7d8"

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.controls.rotate(42, -27);
                app.renderer.renderNow();
            }""")
            rotated_matrix = page.evaluate(
                "Array.from(window.__ASE_APP__.renderer.bondGroup.children[0].instanceMatrix.array.slice(0, 16))"
            )
            assert rotated_matrix != flat_state["matrix"]

            page.select_option('#bond-color-mode', 'split')
            page.wait_for_function("""() => {
                const meshes = window.__ASE_APP__.renderer.bondGroup.children;
                return meshes.length === 2
                    && meshes.reduce((sum, mesh) => sum + mesh.userData.bondSegments.length, 0) === 2;
            }""")
            split_colors = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    actual: renderer.bondGroup.children
                        .map(mesh => `#${mesh.material.color.getHexString()}`).sort(),
                    expected: [renderer.atomVisualColor(0), renderer.atomVisualColor(1)]
                        .map(color => color.toLowerCase()).sort()
                };
            }""")
            assert split_colors["actual"] == split_colors["expected"]

            page.click('[data-inspector-group="structure"]')
            page.fill('#super-x', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[0] === 2")
            page.fill('#super-y', '2')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[1] === 2")
            page.fill('#super-z', '2')
            page.keyboard.press('Tab')
            page.wait_for_function("window.__ASE_APP__.state.display.supercell[2] === 2")
            assert page.evaluate("window.__ASE_APP__.state.display.supercell") == [2, 2, 2]
            repeated = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const children = renderer.supercellGroup.children;
                const atoms = children.filter(child => child.userData.supercellInstanced);
                const bonds = children.filter(child => child.userData.supercellBonds);
                return {
                    atomInstances: atoms.reduce((sum, mesh) => sum + mesh.count, 0),
                    bondInstances: bonds.reduce((sum, mesh) => sum + mesh.count, 0),
                    atomMeshes: atoms.length,
                    bondMeshes: bonds.length,
                    atomTransparent: atoms.some(mesh => mesh.material.transparent),
                    atomOpacity: atoms.map(mesh => mesh.material.opacity),
                    selectableChildren: window.__ASE_APP__.renderer.atomMeshes.children.length,
                    exactBaseMaterials: atoms.every(mesh => mesh.userData.atomIndices.every(index =>
                        mesh.material === renderer.atomMeshByIndex.get(index).material
                    )),
                };
            }""")
            assert repeated["atomInstances"] == 14
            assert repeated["bondInstances"] == 14
            assert repeated["atomMeshes"] >= 1
            assert repeated["bondMeshes"] == 2
            assert repeated["atomTransparent"] is False
            assert all(opacity == 1 for opacity in repeated["atomOpacity"])
            assert repeated["exactBaseMaterials"] is True
            assert repeated["selectableChildren"] == 2
            repeated_hover = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const Vector3 = renderer.camera.position.constructor;
                const target = new Vector3(8, 0, 0);
                renderer.camera.position.set(13, -20, 7);
                renderer.camera.up.set(0, 0, 1);
                renderer.controls.target.copy(target);
                renderer.camera.lookAt(target);
                renderer.camera.updateMatrixWorld(true);
                renderer.scene.updateMatrixWorld(true);
                const screen = target.clone().project(renderer.camera);
                const pointer = {
                    clientX: (screen.x + 1) * 0.5 * window.innerWidth,
                    clientY: (1 - screen.y) * 0.5 * window.innerHeight,
                };
                return {
                    hover: app.selection.pickHover(pointer, renderer.atomMeshes, renderer.supercellGroup),
                    selectable: app.selection.pick(pointer, renderer.atomMeshes),
                    clientX: pointer.clientX,
                    clientY: pointer.clientY,
                };
            }""")
            assert repeated_hover["hover"] == {
                "kind": "replica",
                "index": 0,
                "cellOffset": [1, 0, 0],
                "key": "replica:0:1,0,0",
            }
            assert repeated_hover["selectable"] is None
            page.mouse.move(repeated_hover["clientX"], repeated_hover["clientY"])
            page.wait_for_function("window.__ASE_APP__.state.hoveredIndex === 0")
            assert "#0@[1,0,0] H" in page.locator('#hover-readout').inner_text()
            for control in ('#super-x', '#super-y', '#super-z'):
                page.fill(control, '1')
                page.keyboard.press('Tab')
            page.wait_for_function(
                "window.__ASE_APP__.state.display.supercell.every(value => value === 1)"
            )

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.selected.clear();
                app.state.selected.add(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.keyboard.press('g')
            page.keyboard.press('x')
            page.keyboard.type('0.1')
            page.keyboard.press('Enter')
            page.wait_for_function("window.__ASE_APP__.transform.mode === 'IDLE'")
            page.evaluate("async () => { await window.__ASE_APP__.pendingApply; }")
            persisted = page.evaluate("""() => ({
                style: window.__ASE_APP__.state.display.bondStyle,
                thickness: window.__ASE_APP__.state.display.bondThickness,
                colorMode: window.__ASE_APP__.state.display.bondColorMode,
                customColor: window.__ASE_APP__.state.display.bondCustomColor,
                styleControl: document.getElementById('bond-style').value,
                thicknessControl: Number(document.getElementById('bond-thickness').value),
                colorControl: document.getElementById('bond-color-mode').value
            })""")
            assert persisted == {
                "style": "flat",
                "thickness": 0.24,
                "colorMode": "split",
                "customColor": "#18a7d8",
                "styleControl": "flat",
                "thicknessControl": 0.24,
                "colorControl": "split",
            }
            browser.close()
    finally:
        editor.close()


def test_viz_only_replica_selection_measurements_and_atomic_label_commit():
    atoms = Atoms(
        "Cu2",
        positions=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    set_atom_labels(atoms, ["Cu", "Cu2"])
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 820})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")

            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            _open_panel(page, 'appearance')
            type_palette = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const labels = ['Cu', 'Cu2'];
                return {
                    types: labels.map(label => document.querySelector(`.chemical-type-select[data-atom-label="${label}"]`).value),
                    controls: labels.map(label => document.querySelector(`.label-color-input[data-atom-label="${label}"]`).value.toLowerCase()),
                    rendered: [0, 1].map(index => app.renderer.atomVisualColor(index).toLowerCase())
                };
            }""")
            assert type_palette["types"] == ["Cu", "Cu"]
            assert type_palette["controls"][0] == type_palette["controls"][1]
            assert type_palette["rendered"][0] == type_palette["rendered"][1]
            assert type_palette["controls"] == type_palette["rendered"]

            label_input = page.locator('.atom-label-input[data-atom-label="Cu2"]')
            label_input.fill('Cu')
            label_input.press('Enter')
            page.wait_for_function("""() => {
                const labels = window.__ASE_APP__.state.atoms.symbols;
                return labels[0] === 'Cu' && labels[1] === 'Cu';
            }""")
            toasts = page.locator('#toast-container .toast').all_inner_texts()
            assert all('already exists' not in text for text in toasts)
            assert sum('Merged Cu2 into label Cu' in text for text in toasts) == 1
            assert all('atoms found' not in text for text in toasts)

            page.click('[data-inspector-group="structure"]')
            for control, value in (('#super-x', '2'), ('#super-y', '2'), ('#super-z', '1')):
                page.fill(control, value)
                page.keyboard.press('Tab')
            page.wait_for_function("""() =>
                window.__ASE_APP__.state.display.supercell.join(',') === '2,2,1' &&
                window.__ASE_APP__.renderer.supercellSelectionReferences().length === 6
            """)
            replica_material = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                const base = renderer.atomMeshByIndex.get(0);
                const replica = renderer.supercellGroup.children.find(mesh =>
                    mesh.userData.supercellInstanced && mesh.userData.atomIndices.includes(0)
                );
                return {
                    useInstancedAtoms: renderer.useInstancedAtoms,
                    sameMaterial: base.material === replica.material,
                    baseColor: base.material.color.getHexString(),
                    replicaColor: replica.material.color.getHexString(),
                    baseEmissive: base.material.emissive.getHexString(),
                    replicaEmissive: replica.material.emissive.getHexString(),
                    baseRoughness: base.material.roughness,
                    replicaRoughness: replica.material.roughness,
                    hasInstanceColor: Boolean(replica.instanceColor)
                };
            }""")
            assert replica_material["useInstancedAtoms"] is False
            assert replica_material["sameMaterial"] is True
            assert replica_material["replicaColor"] == replica_material["baseColor"]
            assert replica_material["replicaEmissive"] == replica_material["baseEmissive"]
            assert replica_material["replicaRoughness"] == replica_material["baseRoughness"]
            assert replica_material["hasInstanceColor"] is False

            points = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const Vector3 = renderer.camera.position.constructor;
                renderer.camera.position.set(2, 2, 20);
                renderer.camera.up.set(0, 1, 0);
                renderer.controls.target.set(2, 2, 0);
                renderer.camera.lookAt(renderer.controls.target);
                renderer.camera.updateMatrixWorld(true);
                renderer.scene.updateMatrixWorld(true);
                const rect = renderer.domElement.getBoundingClientRect();
                const project = values => {
                    const point = new Vector3(...values).project(renderer.camera);
                    return {
                        x: rect.left + (point.x + 1) * rect.width / 2,
                        y: rect.top + (1 - point.y) * rect.height / 2,
                    };
                };
                return {
                    xReplica: project([4, 0, 0]),
                    base: project([0, 0, 0]),
                    yReplica: project([0, 4, 0]),
                };
            }""")
            page.mouse.click(points['xReplica']['x'], points['xReplica']['y'])
            page.keyboard.down('Shift')
            page.mouse.click(points['base']['x'], points['base']['y'])
            page.keyboard.up('Shift')
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 2")
            replica_distance = page.evaluate("""() => ({
                detail: document.getElementById('selected-measure').innerText,
                summary: document.getElementById('selection-measure-value').innerText,
                overlay: [...document.querySelectorAll('.measure-value-badge text')]
                    .map(label => label.textContent),
                direct: window.__ASE_APP__.selectionDistance(
                    ...window.__ASE_APP__.selectionEntries(),
                    {mic: false}
                ),
                mic: window.__ASE_APP__.selectionDistance(
                    ...window.__ASE_APP__.selectionEntries(),
                    {mic: true}
                ),
                unitCell: window.__ASE_APP__.selectionUnitCellDistance(
                    ...window.__ASE_APP__.selectionEntries()
                )
            })""")
            assert replica_distance["direct"] == pytest.approx(4.0)
            assert replica_distance["mic"] == pytest.approx(0.0)
            assert replica_distance["unitCell"] == pytest.approx(0.0)
            assert "Direct: d(a1-a2) = 4.0000 A" in replica_distance["detail"]
            assert "MIC: d(a1-a2) = 0.0000 A" in replica_distance["detail"]
            assert "Unit cell: d(a1-a2) = 0.0000 A" in replica_distance["detail"]
            assert replica_distance["summary"] == (
                "Distance a1-a2 | Direct 4.0000 A | MIC 0.0000 A | "
                "Unit cell 0.0000 A"
            )
            assert replica_distance["overlay"] == [
                "Direct 4.000 | MIC 0.000 | Cell 0.000 A"
            ]

            page.keyboard.down('Shift')
            page.mouse.click(points['yReplica']['x'], points['yReplica']['y'])
            page.keyboard.up('Shift')
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 3")
            page.click('[data-inspector-group="inspect"]')
            _open_panel(page, 'selection')

            selected = page.evaluate("""() => ({
                count: window.__ASE_APP__.selectionCount(),
                indices: document.getElementById('selected-indices').innerText,
                centerLines: [...document.getElementById('selected-center').children]
                    .map(line => line.textContent),
                centerLineDelta: (() => {
                    const lines = [...document.getElementById('selected-center').children];
                    return lines.length === 2
                        ? lines[1].getBoundingClientRect().top - lines[0].getBoundingClientRect().top
                        : 0;
                })(),
                measure: document.getElementById('selected-measure').innerText,
                measureSummary: document.getElementById('selection-measure-value').innerText,
                measureVisible: !document.getElementById('selection-measure-readout').classList.contains('hidden'),
                replicaOutlines: window.__ASE_APP__.renderer.replicaSelectionOutlines.children
                    .reduce((sum, mesh) => sum + mesh.count, 0),
                overlayKind: document.getElementById('measurement-overlay').dataset.measureKind,
                overlayLabels: [...document.querySelectorAll('.measure-atom-badge text')]
                    .map(label => label.textContent),
                overlayReferences: [...document.querySelectorAll('.measure-atom-badge')]
                    .map(label => label.dataset.reference),
                connectorCount: document.querySelectorAll('.measure-connector').length,
                angleArcCount: document.querySelectorAll('.measure-angle-arc').length,
            })""")
            assert selected['count'] == 3
            assert selected['indices'] == '0@[1,0,0], 0, 0@[0,1,0]'
            assert selected['centerLines'] == [
                '1.333, 1.333, 0.000 A',
                '(frac 0.3333, 0.3333, 0.0000)',
            ]
            assert selected['centerLineDelta'] > 5
            assert 'a1=#0@[1,0,0] Cu' in selected['measure']
            assert 'a2=#0 Cu' in selected['measure']
            assert 'a3=#0@[0,1,0] Cu' in selected['measure']
            assert 'Direct: d(a1-a2) = 4.0000 A' in selected['measure']
            assert 'MIC:' not in selected['measure']
            assert 'angle(a1-a2-a3) = 90.00 deg' in selected['measure']
            assert selected['measureSummary'] == (
                'Angle a1-a2-a3 | Direct 90.00 deg'
            )
            assert selected['measureVisible'] is True
            assert selected['replicaOutlines'] == 2
            assert selected['overlayKind'] == 'angle'
            assert selected['overlayLabels'] == ['a1', 'a2', 'a3']
            assert selected['overlayReferences'] == ['0@[1,0,0]', '0', '0@[0,1,0]']
            assert selected['connectorCount'] == 2
            assert selected['angleArcCount'] == 1

            page.mouse.move(points['yReplica']['x'], points['yReplica']['y'])
            page.wait_for_function("window.__ASE_APP__.state.hoveredReference?.key === 'replica:0:0,1,0'")
            hover_text = page.locator('#hover-readout').inner_text()
            assert '#0@[0,1,0] Cu' in hover_text
            assert 'measure=' not in hover_text
            assert page.locator('#selection-measure-value').inner_text() == selected['measureSummary']

            page.locator('#app-viewport canvas').focus()
            page.keyboard.press('Control+a')
            page.wait_for_function("window.__ASE_APP__.selectionCount() === 8")
            assert page.locator('#prop-selected').inner_text() == '8'
            assert page.locator('#measurement-overlay').get_attribute('data-measure-kind') == 'none'
            assert page.locator('.measure-atom-badge').count() == 0
            assert page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const selected = app.selection.boxSelect(
                    {left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight},
                    app.renderer.atomMeshes,
                    app.renderer.camera,
                    app.renderer.supercellGroup,
                    true
                );
                return [...selected].filter(value => value?.kind === 'replica').length;
            }""") == 6
            browser.close()
    finally:
        editor.close()


def test_runtime_mode_switch_merges_labels_and_splits_only_material_variants():
    atoms = Atoms(
        "C3",
        positions=[[0.0, 0.0, 0.0], [1.6, 0.0, 0.0], [3.2, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    set_atom_labels(atoms, ["C_a", "C_b", "C_b"])
    original_positions = atoms.positions.tolist()
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            console_errors = []
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error" else None,
            )
            page.on(
                "pageerror",
                lambda error: console_errors.append(
                    f"pageerror: {error}\n{getattr(error, 'stack', '')}"
                ),
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            try:
                page.wait_for_function(
                    "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3",
                    timeout=8_000,
                )
            except PlaywrightError as exc:
                pytest.fail(f"v_ase did not initialize: {console_errors!r}; {exc}")

            assert page.locator('[data-runtime-mode="view"]').get_attribute("aria-pressed") == "true"
            _expand_inspector(page)
            page.click('[data-inspector-group="structure"]')
            _open_panel(page, "appearance")
            page.select_option(
                '.appearance-material-select[data-atom-label="C_b"]',
                "metal",
            )
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.display.labelMaterials.C_b === 'metal'
                    && Math.abs(app.renderer.atomMeshByIndex.get(1).material.metalness - 0.90) < 1e-6;
            }""")

            page.click('[data-runtime-mode="edit"]')
            page.wait_for_function("""() =>
                window.__ASE_APP__.state.vizOnly === false
                && document.querySelector('[data-runtime-mode="edit"]').getAttribute('aria-pressed') === 'true'
            """)
            assert page.locator("#selected-appearance").is_visible()

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.state.selected.add(0);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.fill("#selected-atom-label", "C_b")
            page.click("#btn-apply-selected-label")
            page.wait_for_function("""() =>
                window.__ASE_APP__.state.atoms.symbols.every(label => label === 'C_b')
            """)
            assert page.locator("#toast-container").inner_text().count(
                "Merged selected atoms into label C_b"
            ) == 1

            page.select_option("#selected-atom-material", "rubber")
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                const material = app.renderer.atomMeshByIndex.get(0).material;
                return app.state.display.atomMaterials['0'] === 'rubber'
                    && Math.abs(material.roughness - 0.88) < 1e-6
                    && Math.abs(material.metalness) < 1e-6;
            }""")

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.state.atoms.positions[2][1] = 0.35;
                app.renderer.updatePositions(app.state.atoms.positions);
            }""")
            page.click('[data-runtime-mode="view"]')
            page.wait_for_function("""() => {
                const app = window.__ASE_APP__;
                return app.state.vizOnly === true
                    && app.state.atoms.symbols.join(',') === 'C_b_2,C_b,C_b'
                    && Object.keys(app.state.display.atomMaterials).length === 0
                    && app.state.display.labelMaterials.C_b === 'metal'
                    && app.state.display.labelMaterials.C_b_2 === 'rubber';
            }""")
            switched = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    positions: app.state.atoms.positions,
                    selected: [...app.state.selected],
                    materials: [0, 1, 2].map(index => ({
                        roughness: app.renderer.atomMeshByIndex.get(index).material.roughness,
                        metalness: app.renderer.atomMeshByIndex.get(index).material.metalness,
                    })),
                };
            }""")
            expected_positions = np.asarray(original_positions, dtype=float)
            expected_positions[2, 1] = 0.35
            assert np.allclose(switched["positions"], expected_positions)
            assert switched["selected"] == [0]
            assert switched["materials"][0]["roughness"] == pytest.approx(0.88)
            assert switched["materials"][1]["metalness"] == pytest.approx(0.90)
            assert switched["materials"][2]["metalness"] == pytest.approx(0.90)

            page.click('[data-runtime-mode="edit"]')
            page.wait_for_function("""() =>
                window.__ASE_APP__.state.vizOnly === false
                && window.__ASE_APP__.state.atoms.symbols.join(',') === 'C_b_2,C_b,C_b'
            """)
            assert not [message for message in console_errors if "favicon" not in message]
            browser.close()
    finally:
        editor.close()


def test_camera_toolbar_white_background_and_flat_2d_display():
    atoms = molecule("H2O")
    atoms.set_cell([8.0, 8.0, 8.0])
    atoms.set_pbc(True)
    atoms.set_constraint(FixAtoms(indices=[0]))
    port = find_free_port()
    editor = view(
        atoms,
        notebook=True,
        block=False,
        port=port,
        show_bonds=True,
        viz_only=False,
        close_on_disconnect=False,
    )

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            console_errors = []
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")
            page.wait_for_function("window.__ASE_APP__?.renderer?.bondPairs?.length === 2")
            assert page.evaluate("""() => ({
                state: window.__ASE_APP__.state.display.viewportBackground,
                background: `#${window.__ASE_APP__.renderer.scene.background.getHexString()}`,
                control: document.getElementById('viewport-background').value,
                atomRadiusScale: window.__ASE_APP__.state.display.atomRadiusScale,
                bondThickness: window.__ASE_APP__.state.display.bondThickness,
                radiusControl: Number(document.getElementById('atom-radius-scale').value),
                thicknessControl: Number(document.getElementById('bond-thickness').value),
                radiusOutput: document.getElementById('atom-radius-scale-value').innerText,
                thicknessOutput: document.getElementById('bond-thickness-value').innerText
            })""") == {
                "state": "white",
                "background": "#ffffff",
                "control": "white",
                "atomRadiusScale": pytest.approx(0.6),
                "bondThickness": pytest.approx(0.25),
                "radiusControl": pytest.approx(0.6),
                "thicknessControl": pytest.approx(0.25),
                "radiusOutput": "0.60x",
                "thicknessOutput": "0.25 A",
            }

            toolbar_geometry = page.evaluate("""() => {
                const header = document.getElementById('top-bar').getBoundingClientRect();
                const toolbar = document.getElementById('view-toolbar').getBoundingClientRect();
                const arrows = [...document.querySelectorAll('[data-view-rotate]')];
                return {
                    headerCenterY: header.top + header.height / 2,
                    toolbarCenterY: toolbar.top + toolbar.height / 2,
                    toolbarVisible: toolbar.width > 0 && toolbar.height > 0,
                    toolbarLeft: toolbar.left,
                    toolbarRight: toolbar.right,
                    viewportWidth: window.innerWidth,
                    arrowCount: arrows.length,
                    arrowText: arrows.map(button => button.textContent.trim()),
                    arrowDirections: arrows.map(button => button.dataset.viewRotate),
                    arrowGeometry: arrows.map(button => {
                            const icon = button.querySelector('.view-orbit-icon');
                            const bounds = icon.getBBox();
                        return {
                            width: bounds.width,
                            height: bounds.height,
                            faceCount: button.querySelectorAll(
                                '.view-arrow-front-surface, .view-arrow-orbit-surface'
                            ).length,
                            depthCount: button.querySelectorAll(
                                '.view-arrow-front-depth, .view-arrow-orbit-depth'
                            ).length,
                            rimCount: button.querySelectorAll(
                                '.view-arrow-front-rim, .view-arrow-orbit-rim'
                            ).length,
                            orbitCount: button.querySelectorAll('.view-arrow-orbit-surface').length,
                            seamCount: button.querySelectorAll('.view-arrow-orbit-seam').length,
                            specularCount: button.querySelectorAll('.view-arrow-orbit-highlight').length,
                            volumeTransform: button.querySelector('.view-orbit-volume')
                                ?.getAttribute('transform') || '',
                            filter: getComputedStyle(button.querySelector('.view-orbit-icon')).filter
                        };
                    }),
                    popupExists: Boolean(
                        document.getElementById('btn-view-toggle')
                        || document.getElementById('view-card')
                    )
                };
            }""")
            assert toolbar_geometry["toolbarVisible"] is True
            assert toolbar_geometry["toolbarCenterY"] == pytest.approx(
                toolbar_geometry["headerCenterY"], abs=1
            )
            assert toolbar_geometry["toolbarLeft"] >= 0
            assert toolbar_geometry["toolbarRight"] <= toolbar_geometry["viewportWidth"]
            assert toolbar_geometry["arrowCount"] == 6
            assert toolbar_geometry["arrowText"] == [""] * 6
            assert toolbar_geometry["arrowDirections"] == [
                "up",
                "down",
                "left",
                "right",
                "roll-ccw",
                "roll-cw",
            ]
            assert all(
                min(arrow["width"], arrow["height"]) >= 18
                and max(arrow["width"], arrow["height"]) >= 22
                and arrow["faceCount"] == 1
                and arrow["depthCount"] == 1
                and arrow["rimCount"] == 1
                and arrow["filter"] != "none"
                for arrow in toolbar_geometry["arrowGeometry"]
            )
            assert [
                (
                    arrow["orbitCount"],
                    arrow["seamCount"],
                    arrow["specularCount"],
                    arrow["volumeTransform"],
                )
                for arrow in toolbar_geometry["arrowGeometry"]
            ] == [
                (1, 1, 1, ""),
                (1, 1, 1, "translate(0 48) scale(1 -1)"),
                (1, 1, 1, "matrix(0 1 1 0 0 0)"),
                (1, 1, 1, "matrix(0 1 -1 0 48 0)"),
                (0, 0, 0, ""),
                (0, 0, 0, ""),
            ]
            assert toolbar_geometry["popupExists"] is False

            _expand_inspector(page)
            page.click('[data-inspector-group="view"]')
            page.select_option("#viewport-background", "white")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'white'"
            )
            white_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const grid = app.renderer.gridGroup.children[0];
                return {
                    background: `#${app.renderer.scene.background.getHexString()}`,
                    clear: `#${app.renderer.renderer.getClearColor(
                        new app.renderer.scene.background.constructor()
                    ).getHexString()}`,
                    dataset: app.renderer.domElement.dataset.viewportBackground,
                    sidebar: document.getElementById('viewport-background').value,
                    gridOpacity: grid.material.opacity
                };
            }""")
            assert white_state == {
                "background": "#ffffff",
                "clear": "#ffffff",
                "dataset": "white",
                "sidebar": "white",
                "gridOpacity": pytest.approx(0.48),
            }

            page.select_option("#atom-display-mode", "2d")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.atomDisplayMode === '2d'"
            )
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.bondStyle === 'flat'"
            )
            flat_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    mode: app.state.display.atomDisplayMode,
                    requestedBondStyle: app.state.display.bondStyle,
                    effectiveBondStyle: app.renderer.effectiveBondStyle(),
                    atomMaterials: app.renderer.atomMeshes.children.map(
                        mesh => mesh.material.type
                    ),
                    fixedFlatMaterialCount: app.renderer.atomMeshes.children.filter(
                        mesh => mesh.userData.fixed
                            && mesh.material.userData.fixedEtchedFlatApplied === true
                    ).length,
                    outlineMaterialCount: app.renderer.atomMeshes.children.filter(
                        mesh => mesh.material.userData.flatOutlineEnabled === true
                    ).length,
                    atomMeshCount: app.renderer.atomMeshes.children.length,
                    bondGeometry: app.renderer.bondGroup.children.map(
                        mesh => mesh.geometry.type
                    ),
                    sidebar: document.getElementById('atom-display-mode').value
                };
            }""")
            assert flat_state["mode"] == "2d"
            assert flat_state["requestedBondStyle"] == "cylinder"
            assert flat_state["effectiveBondStyle"] == "flat"
            assert set(flat_state["atomMaterials"]) == {"MeshBasicMaterial"}
            assert flat_state["fixedFlatMaterialCount"] == 1
            assert flat_state["outlineMaterialCount"] == flat_state["atomMeshCount"]
            assert set(flat_state["bondGeometry"]) == {"PlaneGeometry"}
            assert flat_state["sidebar"] == "2d"
            page.wait_for_timeout(150)
            assert not [
                message
                for message in console_errors
                if "Shader Error" in message or "WebGLProgram" in message
            ]

            page.select_option("#viewport-background", "dark")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'dark'"
            )
            assert page.evaluate("""() => window.__ASE_APP__.renderer.atomMeshes.children.every(
                mesh => mesh.material.userData.flatOutlineEnabled === true
            )""") is True

            page.select_option("#viewport-background", "white")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.viewportBackground === 'white'"
            )
            page.select_option("#atom-display-mode", "3d")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.atomDisplayMode === '3d'"
            )
            solid_state = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                return {
                    atomMaterials: app.renderer.atomMeshes.children.map(
                        mesh => mesh.material.type
                    ),
                    bondGeometry: app.renderer.bondGroup.children.map(
                        mesh => mesh.geometry.type
                    )
                };
            }""")
            assert set(solid_state["atomMaterials"]) == {"MeshPhysicalMaterial"}
            assert set(solid_state["bondGeometry"]) == {"CylinderGeometry"}

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                const target = app.renderer.controls.target;
                const distance = Math.max(camera.position.distanceTo(target), 4);
                camera.position.set(target.x, target.y, target.z + distance);
                camera.up.set(0, 1, 0);
                app.completeCameraViewChange('test-top-view');
            }""")
            page.fill("#view-rotate-step", "45")
            before_rotation = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const target = renderer.controls.target.clone();
                const point = target.clone().add({x: 1, y: 0, z: 0});
                const projected = point.project(renderer.camera);
                return {
                    positions: JSON.stringify(app.state.atoms.positions),
                    cameraPosition: renderer.camera.position.toArray(),
                    target: target.toArray(),
                    projected: [
                        projected.x * renderer.domElement.clientWidth,
                        projected.y * renderer.domElement.clientHeight
                    ]
                };
            }""")
            assert math.degrees(math.atan2(
                before_rotation["projected"][1],
                before_rotation["projected"][0],
            )) == pytest.approx(0, abs=1e-5)

            page.click('[data-view-rotate="roll-ccw"]')
            rotated = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const renderer = app.renderer;
                const target = renderer.controls.target.clone();
                const point = target.clone().add({x: 1, y: 0, z: 0});
                const projected = point.project(renderer.camera);
                return {
                    positions: JSON.stringify(app.state.atoms.positions),
                    cameraPosition: renderer.camera.position.toArray(),
                    cameraUp: renderer.camera.up.toArray(),
                    projected: [
                        projected.x * renderer.domElement.clientWidth,
                        projected.y * renderer.domElement.clientHeight
                    ],
                    step: app.state.display.viewRotationStepDeg,
                    saved: app.designSettingsSnapshot().display
                };
            }""")
            assert rotated["positions"] == before_rotation["positions"]
            assert rotated["cameraPosition"] == pytest.approx(
                before_rotation["cameraPosition"], abs=1e-8
            )
            assert rotated["cameraUp"] == pytest.approx(
                [math.sqrt(0.5), math.sqrt(0.5), 0], abs=1e-7
            )
            assert math.degrees(math.atan2(
                rotated["projected"][1],
                rotated["projected"][0],
            )) == pytest.approx(45, abs=1e-5)
            assert rotated["step"] == pytest.approx(45)
            assert rotated["saved"]["viewportBackground"] == "white"
            assert rotated["saved"]["atomDisplayMode"] == "3d"
            assert rotated["saved"]["viewRotationStepDeg"] == pytest.approx(45)

            page.click('[data-view-rotate="roll-cw"]')
            camera_after_roll_pair = page.evaluate("""() => {
                const renderer = window.__ASE_APP__.renderer;
                return {
                    position: renderer.camera.position.toArray(),
                    up: renderer.camera.up.toArray()
                };
            }""")
            assert camera_after_roll_pair["position"] == pytest.approx(
                before_rotation["cameraPosition"], abs=1e-8
            )
            assert camera_after_roll_pair["up"] == pytest.approx([0, 1, 0], abs=1e-8)

            for first, inverse, component, expected_sign, screen_component, screen_sign in (
                ("left", "right", 0, 1, 0, -1),
                ("right", "left", 0, -1, 0, 1),
                ("up", "down", 1, 1, 1, -1),
                ("down", "up", 1, -1, 1, 1),
            ):
                page.evaluate("""() => {
                    const app = window.__ASE_APP__;
                    const camera = app.renderer.camera;
                    const target = app.renderer.controls.target;
                    const distance = Math.max(camera.position.distanceTo(target), 4);
                    camera.position.set(target.x, target.y, target.z + distance);
                    camera.up.set(0, 1, 0);
                    app.completeCameraViewChange('test-top-view');
                }""")
                camera_before_pair = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return {
                        position: renderer.camera.position.toArray(),
                        up: renderer.camera.up.toArray()
                    };
                }""")
                probe_before = page.evaluate("""direction => {
                    const renderer = window.__ASE_APP__.renderer;
                    const target = renderer.controls.target.clone();
                        const offsets = {
                            left: [1, 0, 0],
                            right: [-1, 0, 0],
                            up: [0, 1, 0],
                            down: [0, -1, 0]
                    };
                    const point = target.clone().add({
                        x: offsets[direction][0],
                        y: offsets[direction][1],
                        z: offsets[direction][2]
                    });
                    renderer.camera.updateMatrixWorld(true);
                    const projected = point.clone().project(renderer.camera);
                    return {
                        projected: [projected.x, projected.y],
                        distance: point.distanceTo(renderer.camera.position)
                    };
                }""", first)
                page.click(f'[data-view-rotate="{first}"]')
                moved_direction = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return renderer.camera.position.clone()
                        .sub(renderer.controls.target).normalize().toArray();
                }""")
                assert moved_direction[component] * expected_sign > 0.6
                probe_after = page.evaluate("""direction => {
                    const renderer = window.__ASE_APP__.renderer;
                    const target = renderer.controls.target.clone();
                        const offsets = {
                            left: [1, 0, 0],
                            right: [-1, 0, 0],
                            up: [0, 1, 0],
                            down: [0, -1, 0]
                    };
                    const point = target.clone().add({
                        x: offsets[direction][0],
                        y: offsets[direction][1],
                        z: offsets[direction][2]
                    });
                    renderer.camera.updateMatrixWorld(true);
                    const projected = point.clone().project(renderer.camera);
                    return {
                        projected: [projected.x, projected.y],
                        distance: point.distanceTo(renderer.camera.position)
                    };
                }""", first)
                assert (
                    probe_after["projected"][screen_component]
                    - probe_before["projected"][screen_component]
                ) * screen_sign > 1e-4
                assert probe_after["distance"] < probe_before["distance"]
                page.click(f'[data-view-rotate="{inverse}"]')
                camera_after_pair = page.evaluate("""() => {
                    const renderer = window.__ASE_APP__.renderer;
                    return {
                        position: renderer.camera.position.toArray(),
                        up: renderer.camera.up.toArray()
                    };
                }""")
                assert camera_after_pair["position"] == pytest.approx(
                    camera_before_pair["position"], abs=1e-8
                )
                assert camera_after_pair["up"] == pytest.approx(
                    camera_before_pair["up"], abs=1e-8
                )

            undo_baseline = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                const target = app.renderer.controls.target;
                const distance = Math.max(camera.position.distanceTo(target), 4);
                camera.position.set(target.x, target.y, target.z + distance);
                camera.up.set(0, 1, 0);
                app.completeCameraViewChange('test-undo-baseline');
                app.resetHistoryTimeline();
                document.querySelector('#app-viewport canvas').focus();
                return app.cameraSettingsSnapshot();
            }""")
            page.click('[data-view-rotate="up"]')
            undo_moved = page.evaluate("""() => ({
                camera: window.__ASE_APP__.cameraSettingsSnapshot(),
                undoKinds: window.__ASE_APP__.undoTimeline.map(action => action.kind),
                redoCount: window.__ASE_APP__.redoTimeline.length
            })""")
            assert undo_moved["undoKinds"] == []
            assert undo_moved["redoCount"] == 0
            assert undo_moved["camera"]["position"] != pytest.approx(
                undo_baseline["position"], abs=1e-8
            )

            visual_baseline = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.resetHistoryTimeline();
                return {
                    color: app.state.display.labelColors.O || null,
                    rendered: app.labelVisualColor('O')
                };
            }""")
            page.evaluate("""() => {
                const input = document.querySelector('.label-color-input[data-atom-label="O"]');
                input.value = '#12a4d9';
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function(
                "window.__ASE_APP__.undoTimeline.length === 1"
                " && window.__ASE_APP__.undoTimeline[0].kind === 'visual'"
            )
            assert page.evaluate(
                "window.__ASE_APP__.state.display.labelColors.O"
            ) == "#12a4d9"

            page.locator("#app-viewport canvas").focus()
            page.keyboard.press("Control+z")
            page.wait_for_function(
                "window.__ASE_APP__.undoTimeline.length === 0"
                " && window.__ASE_APP__.redoTimeline.length === 1"
            )
            visual_undone = page.evaluate("""() => ({
                color: window.__ASE_APP__.state.display.labelColors.O || null,
                rendered: window.__ASE_APP__.labelVisualColor('O'),
                camera: window.__ASE_APP__.cameraSettingsSnapshot()
            })""")
            assert visual_undone["color"] == visual_baseline["color"]
            assert visual_undone["rendered"] == visual_baseline["rendered"]
            assert visual_undone["camera"]["position"] == pytest.approx(
                undo_moved["camera"]["position"], abs=1e-8
            )
            assert visual_undone["camera"]["up"] == pytest.approx(
                undo_moved["camera"]["up"], abs=1e-8
            )

            page.keyboard.press("Control+Shift+z")
            page.wait_for_function(
                "window.__ASE_APP__.undoTimeline.length === 1"
                " && window.__ASE_APP__.redoTimeline.length === 0"
            )
            assert page.evaluate("""() => ({
                color: window.__ASE_APP__.state.display.labelColors.O,
                rendered: window.__ASE_APP__.labelVisualColor('O')
            })""") == {
                "color": "#12a4d9",
                "rendered": "#12a4d9",
            }

            appearance_baseline = page.evaluate("""() => ({
                radius: window.__ASE_APP__.state.display.labelRadii.O,
                material: window.__ASE_APP__.state.display.labelMaterials.O || 'standard'
            })""")
            changed_radius = appearance_baseline["radius"] + 0.17
            page.evaluate("""value => {
                const input = document.querySelector(
                    '.label-radius-input[data-atom-label="O"]'
                );
                input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""", f"{changed_radius:.4f}")
            page.wait_for_function("window.__ASE_APP__.undoTimeline.length === 2")
            page.evaluate("""() => {
                const select = document.querySelector(
                    '.appearance-material-select[data-atom-label="O"]'
                );
                select.value = 'metal';
                select.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function("window.__ASE_APP__.undoTimeline.length === 3")

            page.locator("#app-viewport canvas").focus()
            page.keyboard.press("Control+z")
            page.wait_for_function("window.__ASE_APP__.undoTimeline.length === 2")
            material_undone = page.evaluate("""() => ({
                radius: window.__ASE_APP__.state.display.labelRadii.O,
                material: window.__ASE_APP__.state.display.labelMaterials.O || 'standard'
            })""")
            assert material_undone["radius"] == pytest.approx(changed_radius)
            assert material_undone["material"] == appearance_baseline["material"]

            page.keyboard.press("Control+z")
            page.wait_for_function("window.__ASE_APP__.undoTimeline.length === 1")
            appearance_undone = page.evaluate("""() => ({
                color: window.__ASE_APP__.state.display.labelColors.O,
                radius: window.__ASE_APP__.state.display.labelRadii.O,
                material: window.__ASE_APP__.state.display.labelMaterials.O || 'standard'
            })""")
            assert appearance_undone == {
                "color": "#12a4d9",
                "radius": appearance_baseline["radius"],
                "material": appearance_baseline["material"],
            }

            orbit_baseline = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const camera = app.renderer.camera;
                const target = app.renderer.controls.target;
                const distance = Math.max(camera.position.distanceTo(target), 4);
                camera.position.set(target.x, target.y, target.z + distance);
                camera.up.set(0, 1, 0);
                app.completeCameraViewChange('test-orbit-undo-baseline');
                app.resetHistoryTimeline();
                return app.cameraSettingsSnapshot();
            }""")
            canvas_box = page.locator("#app-viewport canvas").bounding_box()
            assert canvas_box is not None
            orbit_x = canvas_box["x"] + canvas_box["width"] * 0.35
            orbit_y = canvas_box["y"] + canvas_box["height"] * 0.35
            page.mouse.move(orbit_x, orbit_y)
            page.mouse.down(button="middle")
            page.mouse.move(orbit_x + 90, orbit_y + 55, steps=8)
            page.mouse.up(button="middle")
            page.wait_for_timeout(120)
            orbit_moved = page.evaluate("window.__ASE_APP__.cameraSettingsSnapshot()")
            assert orbit_moved["position"] != pytest.approx(
                orbit_baseline["position"], abs=1e-8
            )
            assert page.evaluate("window.__ASE_APP__.undoTimeline.length") == 0

            translation_baseline = page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.resetHistoryTimeline();
                return {
                    positions: app.state.atoms.positions.map(position => [...position]),
                    cell: app.state.atoms.cell.map(vector => [...vector])
                };
            }""")
            _expand_inspector(page)
            _select_structure_section(page, "cell-replication")
            page.wait_for_timeout(450)
            page.fill("#translate-x", "1.25")
            page.fill("#translate-y", "-0.5")
            page.fill("#translate-z", "0.75")
            page.click("#btn-apply-translation")
            page.wait_for_function(
                """() => {
                    const app = window.__ASE_APP__;
                    const expected = [1.25, -0.5, 0.75];
                    return app.state.display.translation.every(
                        (value, index) => Math.abs(value - expected[index]) < 1e-8
                    ) && app.renderer.domElement.dataset.visualTranslation === '1.250000,-0.500000,0.750000';
                }"""
            )
            translated_ui = page.evaluate("""() => ({
                positions: window.__ASE_APP__.state.atoms.positions,
                cell: window.__ASE_APP__.state.atoms.cell,
                undoKinds: window.__ASE_APP__.undoTimeline.map(action => action.kind),
                translation: window.__ASE_APP__.state.display.translation,
                atomGroup: window.__ASE_APP__.renderer.atomMeshes.position.toArray(),
                cellGroup: window.__ASE_APP__.renderer.cellGroup.position.toArray(),
                inputs: ['translate-x', 'translate-y', 'translate-z'].map(
                    id => Number(document.getElementById(id).value)
                )
            })""")
            assert translated_ui["undoKinds"] == []
            assert translated_ui["inputs"] == [1.25, -0.5, 0.75]
            assert translated_ui["translation"] == pytest.approx([1.25, -0.5, 0.75])
            assert translated_ui["atomGroup"] == pytest.approx([1.25, -0.5, 0.75])
            assert translated_ui["cellGroup"] == pytest.approx([0, 0, 0])
            np.testing.assert_allclose(
                translated_ui["cell"],
                translation_baseline["cell"],
            )
            for current_position, original_position in zip(
                translated_ui["positions"],
                translation_baseline["positions"],
            ):
                assert current_position == pytest.approx(original_position)

            page.fill("#translate-x", "0")
            page.fill("#translate-y", "0")
            page.fill("#translate-z", "0")
            page.click("#btn-apply-translation")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.domElement.dataset.visualTranslation === '0.000000,0.000000,0.000000'"
            )
            translation_reset = page.evaluate("""() => ({
                positions: window.__ASE_APP__.state.atoms.positions,
                cell: window.__ASE_APP__.state.atoms.cell,
                translation: window.__ASE_APP__.state.display.translation,
                inputs: ['translate-x', 'translate-y', 'translate-z'].map(
                    id => Number(document.getElementById(id).value)
                )
            })""")
            np.testing.assert_allclose(
                translation_reset["positions"],
                translation_baseline["positions"],
            )
            np.testing.assert_allclose(
                translation_reset["cell"],
                translation_baseline["cell"],
            )
            assert translation_reset["translation"] == [0, 0, 0]
            assert translation_reset["inputs"] == [0, 0, 0]

            assert page.evaluate(
                "JSON.stringify(window.__ASE_APP__.state.atoms.positions)"
            ) == before_rotation["positions"]
            browser.close()
    finally:
        editor.close()
