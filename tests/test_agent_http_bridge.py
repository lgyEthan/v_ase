"""End-to-end checks for the vendor-neutral HTTP command bridge."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import time

import numpy as np
import pytest
import requests
from ase import Atoms
from ase.constraints import FixAtoms
from PIL import Image
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.ai import ai_handshake
from v_ase.add_atoms import MOLECULE_GROUP_ARRAY
from v_ase.io import atom_labels, set_atom_labels
from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


def _post_command(url: str, method: str, params=None, *, expected_status: int = 200):
    response = requests.post(
        url,
        json={"method": method, "params": {} if params is None else params},
        timeout=30,
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def _run_cli_command(url: str, method: str, params=None):
    if method == "capabilities" and params is None:
        params = {"profile": "full"}
    if method == "apply" and isinstance(params, dict) and "responseProfile" not in params:
        # Most bridge regressions predate focused responses and inspect complete
        # state. Token-efficient CLI defaults are covered separately.
        params = {**params, "responseProfile": "full"}
    command = [
        sys.executable,
        "-m",
        "v_ase.cli",
        "api",
        url,
        method,
    ]
    if params is not None:
        command.extend(["--params", json.dumps(params, separators=(",", ":"))])
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)["result"]


def _stable_description(url: str, *, timeout: float = 5.0):
    """Wait until asynchronous GUI events stop advancing collaboration state."""
    deadline = time.monotonic() + timeout
    previous_revision = None
    latest = None
    while time.monotonic() < deadline:
        latest = _run_cli_command(url, "describe", {"includePositions": False})
        revision = latest["collaboration"]["revision"]
        if revision == previous_revision:
            return latest
        previous_revision = revision
        time.sleep(0.1)
    return latest


def test_cli_combines_fields_with_a_result_name_and_preserves_source_values():
    from v_ase.volumetric import VolumetricData
    cell = np.eye(3) * 5
    atoms = Atoms("He", cell=cell, pbc=True)
    datasets = [VolumetricData(str(value), np.full((3, 3, 3), value), cell) for value in (1e8, 1, 1e8)]
    editor = view(atoms, block=False, open_browser=False, close_on_disconnect=False,
                  volumetric_datasets=datasets, port=find_free_port())
    handshake = ai_handshake(editor.url)
    url = handshake["command_url"]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            schema = _run_cli_command(url, "schema", {"profile": "full"})
            assert "resultName" in schema["operation_parameters"]["combine-volumetric"]["optional"]
            state = _run_cli_command(url, "describe", {"profile": "analysis"})
            ids = [grid["id"] for grid in state["analysis"]["volumetricDatasets"]]
            result = _run_cli_command(url, "apply", {
                "expectedRevision": state["collaboration"]["revision"],
                "operation": {"name": "combine-volumetric", "datasetIds": ids,
                              "coefficients": [1, 1, -1], "resultName": "Cancellation audit"},
            })
            grids = result["analysis"]["volumetricDatasets"]
            assert grids[-1]["name"] == "Cancellation audit"
            assert grids[-1]["integral"] == pytest.approx(125)
            assert len(grids) == 4
            assert [grid["mean"] for grid in grids[:3]] == [1e8, 1, 1e8]
            browser.close()
    finally:
        editor.close()


def test_cli_reads_exact_stored_trajectory_properties_with_force_arrows_hidden():
    from ase.calculators.singlepoint import SinglePointCalculator
    frames = []
    for index in range(3):
        atoms = Atoms("HHe", positions=[[index * 0.1, 0, 0], [1, 1, 1]], cell=[5]*3, pbc=True)
        atoms.set_tags([index, index + 1])
        atoms.set_initial_charges([index * 0.25, -index * 0.25])
        atoms.calc = SinglePointCalculator(atoms, forces=np.full((2, 3), index * 0.123456789012345))
        frames.append(atoms)
    editor = view(frames, block=False, open_browser=False, close_on_disconnect=False, port=find_free_port())
    handshake = ai_handshake(f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}")
    url = handshake["command_url"]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            initial = _stable_description(url)
            _run_cli_command(url, "apply", {"expectedRevision": initial["collaboration"]["revision"], "frame": 2})
            state = _run_cli_command(url, "describe", {"profile": "structure", "includeProperties": True})
            assert state["frame"] == 2
            np.testing.assert_allclose(state["forces"], frames[2].calc.results["forces"], rtol=0, atol=1e-15)
            assert state["tags"] == [2, 3]
            assert state["charges"] == [0.5, -0.5]
            assert state["propertyCounts"]["forces"] == 2
            assert page.evaluate("window.__ASE_APP__.state.display.showForceVectors") is False
            # The vector/scalar analysis path must also retain a stored calculator.
            payload = requests.post(f"http://127.0.0.1:{editor.port}/api/analysis/force-vectors/{editor.session_id}",
                                    json={"frame_index": 2, "all_frames": True}, timeout=30)
            assert payload.status_code == 200
            assert np.isfinite(np.frombuffer(payload.content, dtype=np.float32)).all()
            browser.close()
    finally:
        editor.close()


def test_saved_project_renders_its_visible_volumetric_plane_on_initial_load(tmp_path):
    from v_ase.volumetric import VolumetricData
    cell = np.eye(3) * 8
    values = np.broadcast_to(np.linspace(0, 1, 8)[:, None, None], (8, 8, 8)).copy()
    dataset = VolumetricData("Plane reference", values, cell)
    editor = view(Atoms("He", positions=[[4, 4, 4]], cell=cell, pbc=True),
                  volumetric_datasets=[dataset], block=False, open_browser=False,
                  close_on_disconnect=False, port=find_free_port())
    restored = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            handshake = ai_handshake(f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}")
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            initial = _stable_description(handshake["command_url"])
            state = _run_cli_command(handshake["command_url"], "apply", {
                "expectedRevision": initial["collaboration"]["revision"],
                "operation": {"name": "add-volumetric-plane", "datasetId": dataset.dataset_id,
                              "hkl": [0, 0, 1], "offsetAngstrom": 4, "resolution": 128},
            })
            saved = _post_command(handshake["command_url"], "export", {"format": "project"})["result"]
            path = tmp_path / "plane.vase"
            path.write_bytes(base64.b64decode(saved["dataUrl"].split(",", 1)[1]))
            restored = view(str(path), block=False, open_browser=False, close_on_disconnect=False, port=find_free_port())
            reopened = browser.new_page()
            second = ai_handshake(f"http://127.0.0.1:{restored.port}/?session_id={restored.session_id}")
            reopened.goto(second["human_url"])
            reopened.wait_for_function("window.v_aseAI")
            _run_cli_command(second["command_url"], "ready")
            assert reopened.evaluate("window.__ASE_APP__.renderer.volumetricPlanes.size") == 1
            assert reopened.evaluate("[...window.__ASE_APP__.renderer.volumetricPlanes.values()][0].group.visible") is True
            render = _post_command(second["command_url"], "render", {"width": 640, "height": 480})["result"]
            pixels = Image.open(io.BytesIO(base64.b64decode(render["dataUrl"].split(",", 1)[1]))).convert("RGB")
            rgb = np.asarray(pixels)
            assert np.count_nonzero((rgb[:, :, 1] > rgb[:, :, 0] + 20) & (rgb[:, :, 1] > rgb[:, :, 2])) > 500
            browser.close()
    finally:
        if restored is not None:
            restored.close()
        editor.close()


def test_commensurate_cli_reports_the_proposal_angle_and_can_fit_its_preview():
    cell = [[2.46, 0, 0], [1.23, 2.46 * np.sqrt(3) / 2, 0], [0, 0, 12]]
    atoms = Atoms("C4", scaled_positions=[[0, 0, .2], [1/3, 1/3, .2], [0, 0, .5], [1/3, 1/3, .5]],
                  cell=cell, pbc=[True, True, False])
    editor = view(atoms, viz_only=False, block=False, open_browser=False,
                  close_on_disconnect=False, port=find_free_port())
    handshake = ai_handshake(f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}")
    url = handshake["command_url"]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1000, "height": 800})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            state = _stable_description(url)
            rotated = _run_cli_command(url, "apply", {
                "expectedRevision": state["collaboration"]["revision"],
                "selection": {"indices": [2, 3]},
                "operation": {"name": "rotate-to-commensurate", "indices": [2, 3],
                              "angleDeg": 21.2, "maxAreaRatio": 16, "showAtoms": True},
            })
            assert rotated["analysis"]["commensurate"]["currentAngleDeg"] == pytest.approx(21.7867893, abs=1e-6), page.evaluate("JSON.stringify(window.__ASE_APP__.state.commensurateProposal?.context)")
            settled = _stable_description(url)
            analysis = _run_cli_command(url, "describe", {"profile": "analysis"})
            assert analysis["analysis"]["commensurate"]["currentAngleDeg"] == pytest.approx(21.7867893, abs=1e-6), page.evaluate("JSON.stringify(window.__ASE_APP__.state.commensurateProposal?.context)")
            assert page.evaluate("window.__ASE_APP__.state.commensurateProposal.context.positionsIncludeDisplayRotation") is True
            _run_cli_command(url, "apply", {
                "expectedRevision": settled["collaboration"]["revision"],
                "camera": {"fit": "commensurate"},
            })
            assert page.evaluate("""() => {
                const app = window.__ASE_APP__;
                const box = app.renderer.commensuratePreviewBounds(app.state.commensurateProposal.data.preview);
                return app.renderer.boxCorners(box).every(point => {
                    point.project(app.renderer.camera);
                    return Math.abs(point.x) <= 1.001 && Math.abs(point.y) <= 1.001;
                });
            }""")
            browser.close()
    finally:
        editor.close()


def test_external_cli_composes_a_periodic_reference_view_without_structure_edits():
    atoms = Atoms(
        "Cu4O2",
        positions=[
            [0.4, 0.5, 1.0], [2.4, 0.5, 1.0],
            [1.4, 2.5, 1.0], [3.4, 2.5, 1.0],
            [0.7, 1.2, 2.0], [2.7, 1.2, 2.0],
        ],
        cell=[[4.0, 0.0, 0.0], [1.0, 4.0, 0.0], [0.0, 0.0, 10.0]],
        pbc=True,
    )
    baseline = atoms.copy()
    port = find_free_port()
    editor = view(
        atoms,
        notebook=False,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1100, "height": 760})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")

            initial = _run_cli_command(command_url, "describe", {"includePositions": True})
            labelled = _run_cli_command(command_url, "apply", {
                "expectedRevision": initial["collaboration"]["revision"],
                "operation": {
                    "name": "set-visual-label",
                    "indices": [0, 1],
                    "label": "Cu_substrate",
                },
            })
            styled = _run_cli_command(command_url, "apply", {
                "expectedRevision": labelled["collaboration"]["revision"],
                "operation": {
                    "name": "style-atoms",
                    "labels": ["Cu_substrate"],
                    "color": "#f5f5f2",
                    "radiusAngstrom": 1.1,
                    "material": "unlit",
                    "affectBonds": True,
                },
            })
            bonded = _run_cli_command(command_url, "apply", {
                "expectedRevision": styled["collaboration"]["revision"],
                "operation": {
                    "name": "configure-bonds",
                    "disableUnspecified": True,
                    "clearEndpointOverrides": True,
                    "indexPairs": [[0, 4], [1, 5]],
                    "pairs": [{
                        "labels": ["Cu_substrate", "O"],
                        "maximumAngstrom": 3.0,
                    }],
                },
            })
            composed = _run_cli_command(command_url, "apply", {
                "expectedRevision": bonded["collaboration"]["revision"],
                "operation": {
                    "name": "compose-view",
                    "displaySupercell": [3, 3, 1],
                    "centerMotif": {
                        "indices": [4, 5],
                        "targetFractional": [0.5, 0.5, 0.5],
                        "axes": ["a", "b"],
                    },
                    "viewFromCellAxis": "+c",
                    "verticalReferences": [
                        {"index": 4, "cellOffset": [0, 0, 0]},
                        {"index": 5, "cellOffset": [0, 0, 0]},
                    ],
                    "targetIndices": [4, 5],
                    "atomDisplayMode": "2d",
                    "fit": "references",
                    "fitReferences": [
                        {"index": 4, "cellOffset": [0, 0, 0]},
                        {"index": 5, "cellOffset": [0, 0, 0]},
                    ],
                    "padding": 0.08,
                },
            })

            assert composed["labels"][:2] == ["Cu_substrate", "Cu_substrate"]
            assert composed["chemicalSymbols"] == baseline.get_chemical_symbols()
            assert np.asarray(composed["positions"]) == pytest.approx(baseline.positions)
            assert np.asarray(composed["cell"]) == pytest.approx(baseline.cell.array)
            assert composed["pbc"] == baseline.pbc.tolist()
            assert composed["display"]["supercell"] == [3, 3, 1]
            assert composed["display"]["atomDisplayMode"] == "2d"
            assert composed["display"]["atomBondStyles"] == {}
            assert composed["display"]["bondMode"] == "manual"
            assert composed["display"]["manualBondPairs"] == [[0, 4], [1, 5]]
            assert np.linalg.norm(composed["display"]["translation"][:2]) > 0.1
            assert {
                key for key, value in composed["display"]["pairwiseBondCutoffs"].items()
                if float(value) > 0
            } == {"Cu_substrate-O"}

            accepted_direction = np.asarray(composed["camera"]["position"]) - np.asarray(
                composed["camera"]["target"]
            )
            accepted_direction /= np.linalg.norm(accepted_direction)
            accepted_up = np.asarray(composed["camera"]["up"])
            refined = _run_cli_command(command_url, "apply", {
                "expectedRevision": composed["collaboration"]["revision"],
                "operation": {
                    "name": "compose-view",
                    "preserveOrientation": True,
                    "targetIndices": [4, 5],
                    "fit": "references",
                    "fitIndices": [4, 5],
                    "padding": 0.04,
                },
            })
            refined_direction = np.asarray(refined["camera"]["position"]) - np.asarray(
                refined["camera"]["target"]
            )
            refined_direction /= np.linalg.norm(refined_direction)
            assert refined_direction == pytest.approx(accepted_direction, abs=1e-10)
            assert np.asarray(refined["camera"]["up"]) == pytest.approx(accepted_up, abs=1e-10)
            browser.close()
    finally:
        editor.close()


def test_external_cli_agent_repeats_shared_relaxation_and_commits_staged_content():
    host = Atoms(
        "Cu4O2",
        positions=[
            [0.8, 0.9, 1.1], [4.9, 1.2, 1.6], [2.3, 4.4, 2.2],
            [6.1, 4.9, 3.1], [2.8, 2.5, 4.8], [5.5, 3.0, 5.1],
        ],
        cell=[[7.6, 0.0, 0.0], [1.7, 6.5, 0.0], [-0.6, 1.1, 6.2]],
        pbc=True,
    )
    set_atom_labels(host, ["Cu_host"] * 4 + ["O_host"] * 2)
    host.set_tags([9, 8, 7, 6, 5, 4])
    host.new_array("site_weight", np.asarray([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]))
    host.set_constraint(FixAtoms(indices=[0]))
    baseline_positions = host.positions.copy()
    baseline_arrays = {name: values.copy() for name, values in host.arrays.items()}
    baseline_constraints = [repr(item) for item in host.constraints]

    port = find_free_port()
    editor = view(
        host,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    return Boolean(frame?.contentWindow?.__ASE_APP__);
                }""",
                arg=editor.session_id,
            )
            child = next(
                frame for frame in page.frames if "workspace_child=1" in frame.url
            )

            capabilities = _run_cli_command(command_url, "capabilities")
            assert {
                "scatter-atoms", "scatter-molecules",
                "relax-added-atoms", "stop-added-atoms",
                "start-relaxation", "stop-relaxation",
                "finish-add-atoms", "cancel-add-atoms",
            } <= set(capabilities["operations"])

            initial = _run_cli_command(
                command_url,
                "describe",
                {"includePositions": True},
            )
            scattered = _run_cli_command(command_url, "apply", {
                "expectedRevision": initial["collaboration"]["revision"],
                "mode": "edit",
                "operation": {
                    "name": "scatter-atoms",
                    "entries": [
                        {"element": "Li", "label": "Li_mobile", "count": 7},
                        {"element": "H", "label": "H_probe", "count": 3},
                    ],
                    "regions": [{
                        "id": "allow-main",
                        "name": "Allow main",
                        "role": "allow",
                        "bounds": [0.0, 7.6, 0.0, 6.5, 0.0, 6.2],
                    }],
                    "seed": 2021,
                    "freezeExisting": True,
                    "cutoffBasis": "covalent",
                    "cutoffScale": 0.7,
                },
            })
            assert scattered["addAtoms"]["new_count"] == 10
            assert scattered["atomCount"] == len(host) + 10
            child.wait_for_function(
                "window.__ASE_APP__?.renderer?.addAtomsRegionGroup?.visible === true"
            )
            child.wait_for_function(
                f"window.__ASE_APP__?.state?.atoms?.positions?.length === {len(host) + 10}"
            )

            scaled_regions = _run_cli_command(command_url, "apply", {
                "expectedRevision": scattered["collaboration"]["revision"],
                "operation": {
                    "name": "scale-add-atoms-regions",
                    "regionIds": ["allow-main"],
                    "factor": 0.5,
                    "axis": "X",
                    "pivot": [3.8, 3.25, 3.1],
                },
            })
            assert scaled_regions["addAtoms"]["regions"][0]["id"] == "allow-main"
            assert scaled_regions["addAtoms"]["regions"][0]["bounds"] == pytest.approx(
                [1.9, 5.7, 0.0, 6.5, 0.0, 6.2]
            )
            child.wait_for_function(
                "() => window.__ASE_APP__?.addAtomsUI?.active?.regions?.[0]?.bounds?.[0] === 1.9"
            )

            running = _run_cli_command(command_url, "apply", {
                "expectedRevision": scaled_regions["collaboration"]["revision"],
                "operation": {
                    "name": "start-relaxation",
                    "fmax": 0.1,
                    "steps": 20,
                    "calculator": {
                        "device": "cpu",
                        "cpu_threads": 1,
                        "cutoff_mode": "scaled",
                        "cutoff_scale": 0.7,
                        "pair_cutoffs": scattered["addAtoms"]["pair_cutoffs"],
                        "k_repulsion": 2.0,
                    },
                },
            })
            # A short optimizer run can finish through the WebSocket before
            # the apply response is serialized. Both states are valid.
            assert running["addAtoms"]["status"] in {
                "relaxing", "converged", "steps", "stopped", "relaxed",
            }

            deadline = time.monotonic() + 20.0
            placed = running
            while placed["addAtoms"]["is_relaxing"] and time.monotonic() < deadline:
                time.sleep(0.1)
                placed = _run_cli_command(
                    command_url,
                    "describe",
                    {"includePositions": False},
                )
            assert placed["addAtoms"]["is_relaxing"] is False
            assert placed["addAtoms"]["status"] != "error"

            placement_state = _run_cli_command(command_url, "describe", {"profile": "structure"})
            assert placement_state["calculator"]["detailsScope"] == "document"
            assert placement_state["calculator"]["placementDetailsPath"] == "addAtoms"
            assert placement_state["addAtoms"]["cpu_threads"] == 1
            assert placement_state["addAtoms"]["cutoff_mode"] == "scaled"
            assert placement_state["addAtoms"]["cutoff_scale"] == pytest.approx(0.7)
            assert placement_state["addAtoms"]["k_repulsion"] == pytest.approx(2.0)

            placed = _stable_description(command_url)
            appended = _run_cli_command(command_url, "apply", {
                "expectedRevision": placed["collaboration"]["revision"],
                "operation": {
                    "name": "scatter-molecules",
                    "molecules": [{"name": "H2O", "label": "water", "count": 1}],
                    "regions": [{
                        "id": "allow-main",
                        "name": "Allow main revised",
                        "role": "allow",
                        "bounds": [1.9, 6.2, 0.0, 6.5, 0.0, 6.2],
                    }],
                    "placementMode": "homogeneous",
                    "coordinateBasis": "cartesian",
                    "randomOrientation": True,
                    "rigidMolecules": True,
                    "seed": 2022,
                    "freezeExisting": True,
                },
            })
            assert appended["addAtoms"]["placement_count"] == 2
            assert appended["addAtoms"]["last_batch_new_count"] == 3
            assert appended["addAtoms"]["new_count"] == 13
            assert appended["atomCount"] == len(host) + 13
            # Initial placement, region scaling, relaxation, and the second
            # placement are distinct user actions while Add Atoms stays open.
            assert len(sessions[editor.session_id].history) == 4
            np.testing.assert_array_equal(
                sessions[editor.session_id].atom_addition.baseline_atoms.positions,
                baseline_positions,
            )

            appended = _stable_description(command_url)
            committed = _run_cli_command(command_url, "apply", {
                "expectedRevision": appended["collaboration"]["revision"],
                "operation": "finish-add-atoms",
            })
            assert committed["addAtoms"] is None
            assert committed["atomCount"] == len(host) + 13
            assert committed["labels"][-13:] == (
                ["Li_mobile"] * 7
                + ["H_probe"] * 3
                + ["O_water", "H_water", "H_water"]
            )
            child.wait_for_function(
                "window.__ASE_APP__?.renderer?.addAtomsRegionGroup?.visible === false"
            )

            backend = sessions[editor.session_id].working_atoms
            np.testing.assert_array_equal(backend.positions[: len(host)], baseline_positions)
            for name, values in baseline_arrays.items():
                np.testing.assert_array_equal(backend.arrays[name][: len(host)], values)
            assert [repr(item) for item in backend.constraints] == baseline_constraints
            assert atom_labels(backend)[-13:] == (
                ["Li_mobile"] * 7
                + ["H_probe"] * 3
                + ["O_water", "H_water", "H_water"]
            )
            browser.close()
    finally:
        editor.close()


def test_external_cli_agent_places_and_rigidly_relaxes_molecules():
    host = Atoms(
        "Si2",
        positions=[[2.0, 2.0, 2.0], [8.0, 8.0, 8.0]],
        cell=[12.0, 12.0, 12.0],
        pbc=True,
    )
    set_atom_labels(host, ["Si_host", "Si_host"])
    baseline = host.positions.copy()
    port = find_free_port()
    editor = view(
        host,
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")
            capabilities = _run_cli_command(command_url, "capabilities")
            assert capabilities["addAtoms"]["moleculeCatalogUrl"].endswith(
                f"/api/add-session/molecules/{editor.session_id}"
            )
            assert capabilities["addAtoms"]["insertionDomainPreviewUrl"].endswith(
                f"/api/add-session/domain/{editor.session_id}"
            )
            assert capabilities["addAtoms"]["regionRoles"] == ["allow", "reject"]
            assert capabilities["addAtoms"]["maxRegions"] == 32
            assert capabilities["addAtoms"]["densityUnit"] == "g/cm3"
            molecule_names = {
                item["name"] for item in capabilities["addAtoms"]["moleculeCatalog"]
            }
            assert {"H2O", "CO2", "NH3", "C6H6"} <= molecule_names
            assert capabilities["addAtoms"]["defaults"] == {
                "placementMode": "random",
                "coordinateBasis": "cartesian",
                "pbcAware": True,
                "regionMic": True,
                "quantityMode": "count",
                "randomOrientation": True,
                    "rigidMolecules": True,
                    "freezeExisting": True,
                    "constrainToDomain": False,
                    "allowEscape": True,
                }
            initial = _run_cli_command(
                command_url,
                "describe",
                {"includePositions": True},
            )
            scattered = _run_cli_command(command_url, "apply", {
                "expectedRevision": initial["collaboration"]["revision"],
                "mode": "edit",
                "operation": {
                    "name": "scatter-molecules",
                    "molecules": [{"name": "H2O", "label": "water", "count": 1}],
                    "quantityMode": "density",
                    "targetDensityGcm3": 0.06,
                    "placementMode": "homogeneous",
                    "coordinateBasis": "cartesian",
                    "pbcAware": True,
                    "regionMic": False,
                    "randomOrientation": True,
                    "rigidMolecules": True,
                    "regions": [
                        {
                            "id": "left-reservoir",
                            "name": "Left reservoir",
                            "role": "allow",
                            "bounds": [0, 8, 0, 12, 0, 12],
                        },
                        {
                            "id": "right-reservoir",
                            "name": "Right reservoir",
                            "role": "allow",
                            "bounds": [4, 12, 0, 12, 0, 12],
                        },
                        {
                            "id": "central-obstacle",
                            "name": "Central obstacle",
                            "role": "reject",
                            "bounds": [5, 7, 5, 7, 0, 12],
                        },
                    ],
                    "seed": 808,
                },
            })
            assert scattered["addAtoms"]["content_kind"] == "molecules"
            assert scattered["addAtoms"]["molecule_count"] == 3
            assert scattered["addAtoms"]["new_count"] == 9
            assert scattered["addAtoms"]["placement_mode"] == "homogeneous"
            assert scattered["addAtoms"]["coordinate_basis"] == "cartesian"
            assert [region["id"] for region in scattered["addAtoms"]["regions"]] == [
                "left-reservoir", "right-reservoir", "central-obstacle"
            ]
            assert scattered["addAtoms"]["domain"]["volume_angstrom3"] == pytest.approx(
                1680.0,
                abs=1e-9,
            )
            assert scattered["addAtoms"]["density"]["target_g_cm3"] == pytest.approx(0.06)
            assert scattered["addAtoms"]["density"]["actual_g_cm3"] == pytest.approx(
                3 * 18.015 / (6.02214076e23 * 1680e-24),
                rel=5e-5,
            )
            assert [item["index"] for item in scattered["selection"]] == list(
                range(len(host), len(host) + 9)
            )

            staged_positions = sessions[editor.session_id].working_atoms.positions.copy()
            updated = _run_cli_command(command_url, "apply", {
                "expectedRevision": scattered["collaboration"]["revision"],
                "operation": {
                    "name": "update-add-atoms-region",
                    "regionId": "central-obstacle",
                    "regionName": "Shifted obstacle",
                    "bounds": [5.5, 7.5, 5, 7, 0, 12],
                    "regionMic": True,
                },
            })
            assert [region["id"] for region in updated["addAtoms"]["regions"]] == [
                "left-reservoir", "right-reservoir", "central-obstacle"
            ]
            assert updated["addAtoms"]["regions"][2]["name"] == "Shifted obstacle"
            assert updated["addAtoms"]["domain"]["pbc_aware"] is True
            np.testing.assert_array_equal(
                sessions[editor.session_id].working_atoms.positions,
                staged_positions,
            )

            backend_session = sessions[editor.session_id]
            addition = backend_session.atom_addition
            references = [
                np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=2)
                for reference in addition.molecule_references
            ]
            rotated = _run_cli_command(command_url, "apply", {
                "expectedRevision": updated["collaboration"]["revision"],
                "operation": {
                    "name": "rotate-selection",
                    "axis": [0.0, 0.0, 1.0],
                    "angleDeg": 25.0,
                    "pivot": "center",
                },
            })
            moved = _run_cli_command(command_url, "apply", {
                "expectedRevision": rotated["collaboration"]["revision"],
                "operation": {
                    "name": "move-selection",
                    "vector": [0.3, -0.1, 0.2],
                },
            })
            np.testing.assert_array_equal(backend_session.working_atoms.positions[:len(host)], baseline)

            running = _run_cli_command(command_url, "apply", {
                "expectedRevision": moved["collaboration"]["revision"],
                "operation": {
                    "name": "relax-added-atoms",
                    "freezeExisting": True,
                    "strength": 2.0,
                    "fmax": 0.1,
                    "steps": 12,
                    "mic": True,
                },
            })
            deadline = time.monotonic() + 20.0
            placed = running
            while placed["addAtoms"]["is_relaxing"] and time.monotonic() < deadline:
                time.sleep(0.1)
                placed = _run_cli_command(
                    command_url,
                    "describe",
                    {"includePositions": False},
                )
            assert placed["addAtoms"]["is_relaxing"] is False
            assert placed["addAtoms"]["status"] != "error"
            for group, expected in zip(addition.molecule_groups, references):
                current = backend_session.working_atoms.positions[group]
                distances = np.linalg.norm(current[:, None, :] - current[None, :, :], axis=2)
                np.testing.assert_allclose(distances, expected, atol=2e-8)

            placed = _stable_description(command_url)
            committed = _run_cli_command(command_url, "apply", {
                "expectedRevision": placed["collaboration"]["revision"],
                "operation": "finish-add-atoms",
            })
            assert committed["addAtoms"] is None
            np.testing.assert_array_equal(backend_session.working_atoms.positions[:len(host)], baseline)
            groups = backend_session.working_atoms.arrays[MOLECULE_GROUP_ARRAY]
            assert set(groups[:len(host)]) == {-1}
            assert sorted(set(groups[len(host):])) == [0, 1, 2]
            browser.close()
    finally:
        editor.close()


def test_http_bridge_controls_the_same_live_workspace_without_page_evaluation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("V_ASE_CONFIG_DIR", str(tmp_path / "preferences"))
    first = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]],
        cell=[8.0, 8.0, 8.0],
        pbc=True,
    )
    second = first.copy()
    second.positions[1, 1] = 0.15
    port = find_free_port()
    editor = view(
        [first, second],
        notebook=False,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
        open_browser=False,
    )
    handshake = ai_handshake(editor.url)
    command_url = str(handshake["command_url"])

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(handshake["human_url"])
            page.wait_for_function("window.v_aseAI")

            ready = _post_command(command_url, "ready")["result"]
            assert ready["ready"] is True
            assert ready["sessionId"] == editor.session_id

            cli_ready = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "v_ase.cli",
                    "api",
                    command_url,
                    "ready",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert json.loads(cli_ready.stdout)["result"]["sessionId"] == editor.session_id

            capabilities = _run_cli_command(command_url, "capabilities")
            assert capabilities["schemaUrl"].endswith("/api/ai/schema")
            assert "expectedRevision" in capabilities["apply"]
            assert "vector" in capabilities["operationParameters"]["move-selection"]["required"]
            assert "embedProject" in capabilities["exportParameters"]["html"]["optional"]
            assert {
                "wrap",
                "set-unit-cell",
                "move-selection",
                "rotate-selection",
                "scale-selection",
                "set-constraints",
                "refresh-displacements",
                "load-commensurate-guest",
                "remove-commensurate-guest",
                "calculate-commensurate",
                "calculate-registry-map",
                "set-registry-translation",
                "set-interface-theme",
                "set-personal-visual-default",
                "restore-app-visual-defaults",
                "clear-relaxation-trajectory",
            }.issubset(capabilities["operations"])
            assert capabilities["repulsion"]["defaultMode"] == "absolute"
            assert capabilities["bondAppearance"]["pairDisplayKey"] == "pairwiseBondStyles"
            assert "thickness" in capabilities["bondAppearance"]["pairFields"]
            assert {
                "atomRadiusScales",
                "atomColors",
                "atomOpacities",
                "atomMaterials",
                "atomBondStyles",
            }.issubset(capabilities["bondAppearance"]["atomDisplayKeys"])
            assert "preferences" in capabilities["state"]
            assert {
                "image",
                "html",
                "project",
                "settings",
                "commensurate-csv",
                "registry-csv",
            }.issubset(
                capabilities["exports"]
            )

            compact_capabilities = _post_command(
                command_url,
                "capabilities",
                {"profile": "summary"},
            )["result"]
            assert compact_capabilities["profile"] == "summary"
            assert "operationParameters" not in compact_capabilities
            assert "exportParameters" not in compact_capabilities
            assert "bulkBuilder" in compact_capabilities["catalogs"]

            initial = _post_command(
                command_url,
                "describe",
                {"includePositions": True},
            )["result"]
            assert initial["atomCount"] == 2
            assert initial["frameCount"] == 2
            assert initial["calculator"]["attached"] is True
            assert initial["calculator"]["name"] == "Repulsion"
            assert initial["calculator"]["details"]["cutoff_mode"] == "absolute"
            assert initial["calculator"]["details"]["cutoff_scale"] == pytest.approx(1.0)
            assert initial["preferences"]["interfaceTheme"]["preference"] == "system"
            assert initial["preferences"]["personalVisualDefaults"] is False

            schema = _post_command(command_url, "schema")["result"]
            assert set(capabilities["operations"]) == set(
                schema["operation_parameters"]
            )
            assert set(capabilities["exports"]) == set(schema["export_parameters"])
            assert set(capabilities["operationParameters"]) == set(
                schema["operation_parameters"]
            )
            assert set(capabilities["exportParameters"]) == set(
                schema["export_parameters"]
            )
            assert schema["control_schema"]["title"] == "v_ase live semantic control"
            assert schema["operation_parameters"]["rotate-selection"]["mode"] == "edit"
            assert schema["operation_parameters"]["set-unit-cell"]["required"] == ["cell"]
            assert schema["operation_parameters"]["scale-add-atoms-regions"]["required"] == [
                "regionIds",
                "factor",
                "active-add-atoms-session",
            ]
            assert schema["operation_parameters"]["start-relaxation"]["required"] == [
                "attached-calculator-or-active-add-atoms-session"
            ]
            assert schema["operation_parameters"]["clear-relaxation-trajectory"][
                "optional"
            ] == ["retain"]
            assert "same calculator" in (
                schema["operation_parameters"]["start-relaxation"]["notes"]
            )
            assert "includeCell" in schema["export_parameters"]["blender"]["optional"]
            assert schema["operation_parameters"]["load-commensurate-guest"]["required"] == [
                "path"
            ]
            assert "maxAreaRatio" in (
                schema["operation_parameters"]["calculate-commensurate"]["optional"]
            )
            assert schema["operation_parameters"]["calculate-registry-map"]["required"] == [
                "selection-or-indices"
            ]
            assert "hkl" in schema["operation_parameters"]["calculate-registry-map"]["optional"]
            assert "hkl" in schema["operation_parameters"]["start-registry-relaxation"]["optional"]
            calculator_schema = next(
                branch["then"]["properties"]["calculator"]
                for branch in schema["control_schema"]["properties"]["operation"]["oneOf"][1]["allOf"]
                if "calculator" in branch.get("then", {}).get("properties", {})
            )
            assert calculator_schema["additionalProperties"] is False
            assert calculator_schema["properties"]["cutoff_mode"]["enum"] == [
                "absolute",
                "scaled",
            ]
            assert calculator_schema["properties"]["pair_cutoffs"]["additionalProperties"][
                "minimum"
            ] == 0
            assert calculator_schema["properties"]["cutoff_distance"]["minimum"] == 0.01
            assert "Absolute mode" in (
                schema["operation_parameters"]["start-relaxation"]["notes"]
            )
            assert schema["operation_parameters"]["set-registry-translation"]["required"] == [
                "active-registry-relaxation",
                "coordinates",
            ]
            assert "maxAreaRatio" in (
                schema["export_parameters"]["commensurate-csv"]["optional"]
            )
            assert "gridX" in schema["export_parameters"]["registry-csv"]["optional"]
            assert "hkl" in schema["export_parameters"]["registry-csv"]["optional"]
            assert schema["operation_parameters"]["set-interface-theme"]["required"] == [
                "theme"
            ]
            assert schema["operation_parameters"]["restore-app-visual-defaults"][
                "required"
            ] == ["confirm"]
            assert schema["operation_parameters"]["add-volumetric-plane"]["required"] == [
                "datasetId",
                "hkl",
            ]
            assert schema["operation_parameters"]["update-volumetric-planes"][
                "required"
            ] == ["planeIds"]

            compact_schema = _post_command(
                command_url,
                "schema",
                {"scope": "summary"},
            )["result"]
            assert compact_schema["scope"] == "summary"
            assert "control_schema" not in compact_schema
            focused_bonds = _post_command(
                command_url,
                "schema",
                {"operation": "configure-bonds"},
            )["result"]
            assert focused_bonds["scope"] == "operation"
            assert focused_bonds["name"] == "configure-bonds"
            assert focused_bonds["schema"]["properties"]["name"] == {
                "const": "configure-bonds"
            }
            browser_schema = page.evaluate(
                "window.v_aseAI.schema({method: 'render'})"
            )
            assert browser_schema["scope"] == "method"
            assert browser_schema["name"] == "render"

            compact_state = _post_command(
                command_url,
                "describe",
                {"profile": "summary"},
            )["result"]
            assert compact_state["profile"] == "summary"
            assert compact_state["atomCount"] == 2
            assert "display" not in compact_state
            assert len(json.dumps(compact_state)) < 10000

            obsolete_apply = _post_command(
                command_url,
                "apply",
                {"name": "wrap", "parameters": {}},
                expected_status=422,
            )
            assert "unsupported top-level field(s)" in obsolete_apply["detail"]

            nested_parameters = _post_command(
                command_url,
                "apply",
                {"operation": {"name": "wrap", "parameters": {}}},
                expected_status=422,
            )
            assert "directly beside operation.name" in nested_parameters["detail"]

            themed = _post_command(
                command_url,
                "apply",
                {"operation": {"name": "set-interface-theme", "theme": "dark"}},
            )["result"]
            assert themed["preferences"]["interfaceTheme"]["preference"] == "dark"

            focused_change = _post_command(
                command_url,
                "apply",
                {
                    "expectedRevision": themed["collaboration"]["revision"],
                    "display": {"showGrid": False},
                    "responseProfile": "summary",
                },
            )["result"]
            assert focused_change["profile"] == "summary"
            assert focused_change["mutation"]["applied"] is True
            assert "display.showGrid" in focused_change["mutation"]["changedPaths"]
            assert "display" not in focused_change

            personalized = _post_command(
                command_url,
                "apply",
                {
                    "display": {
                        "atomRadiusScale": 0.83,
                        "atomDisplayMode": "2d",
                        "bondStyle": "flat",
                    },
                    "operation": {"name": "set-personal-visual-default"},
                },
            )["result"]
            assert personalized["preferences"]["personalVisualDefaults"] is True

            rejected_restore = _post_command(
                command_url,
                "apply",
                {
                    "operation": {
                        "name": "restore-app-visual-defaults",
                        "confirm": False,
                    }
                },
                expected_status=422,
            )
            assert "confirm" in rejected_restore["detail"]

            restored = _post_command(
                command_url,
                "apply",
                {
                    "operation": {
                        "name": "restore-app-visual-defaults",
                        "confirm": True,
                    }
                },
            )["result"]
            assert restored["preferences"]["personalVisualDefaults"] is False
            assert restored["display"]["atomRadiusScale"] == pytest.approx(0.6)
            assert restored["display"]["atomDisplayMode"] == "3d"

            explicit_cell = [[9.0, 0.0, 0.0], [1.2, 8.5, 0.0], [0.4, 0.7, 7.5]]
            cell_updated = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": restored["collaboration"]["revision"],
                    "mode": "edit",
                    "operation": {
                        "name": "set-unit-cell",
                        "cell": explicit_cell,
                        "pbc": [True, True, True],
                    },
                },
            )
            assert cell_updated["cell"] == explicit_cell
            assert cell_updated["pbc"] == [True, True, True]

            changed = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": cell_updated["collaboration"]["revision"],
                    "mode": "edit",
                    "display": {
                        "showGrid": False,
                        "showAxes": True,
                        "showCell": True,
                        "viewportBackground": "white",
                    },
                    "camera": {"axis": "+Z", "fit": "structure"},
                    "selection": {"clear": True, "indices": [1]},
                    "operation": {
                        "name": "move-selection",
                        "vector": [0.1, 0.2, 0.0],
                        "applyConstraints": True,
                    },
                },
            )
            assert changed["positions"][1] == pytest.approx(
                [0.84, 0.2, 0.0],
                abs=1e-8,
            )
            assert changed["selection"][0]["index"] == 1

            scaled = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": changed["collaboration"]["revision"],
                    "selection": {"clear": True, "indices": [0, 1]},
                    "operation": {
                        "name": "scale-selection",
                        "factor": 2.0,
                        "axis": "X",
                        "pivot": "origin",
                    },
                },
            )
            assert scaled["positions"][0] == pytest.approx([0.0, 0.0, 0.0])
            assert scaled["positions"][1] == pytest.approx([1.68, 0.2, 0.0])
            assert scaled["cell"] == explicit_cell

            child = next(
                frame for frame in page.frames if "workspace_child=1" in frame.url
            )
            child.wait_for_function(
                "() => document.getElementById('prop-selected')?.textContent === '2'"
            )
            assert child.locator('[data-runtime-mode="edit"]').get_attribute(
                "aria-pressed"
            ) == "true"
            assert child.locator("#chk-axes").is_checked()
            assert child.locator("#chk-cell").is_checked()
            assert not child.locator("#chk-grid").is_checked()
            assert child.locator("#selected-indices").inner_text().strip() == "0, 1"

            started_relaxation = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": scaled["collaboration"]["revision"],
                    "operation": {
                        "name": "start-relaxation",
                        "fmax": 0.001,
                        "steps": 4,
                        "calculator": {
                            "cutoff_mode": "absolute",
                            "pair_cutoffs": {"H|H": 2.0},
                            "k_repulsion": 1.0,
                        },
                    },
                },
            )
            assert started_relaxation["relaxation"]["active"] is True
            deadline = time.monotonic() + 10
            relaxed = started_relaxation
            while relaxed["relaxation"]["running"] and time.monotonic() < deadline:
                time.sleep(0.05)
                relaxed = _stable_description(command_url)
            assert relaxed["relaxation"]["running"] is False
            assert relaxed["relaxation"]["frameCount"] >= 1

            cleared_relaxation = _run_cli_command(
                command_url,
                "apply",
                {
                    "expectedRevision": relaxed["collaboration"]["revision"],
                    "operation": {
                        "name": "clear-relaxation-trajectory",
                        "retain": "displayed",
                    },
                },
            )
            assert cleared_relaxation["relaxation"]["active"] is True
            assert cleared_relaxation["relaxation"]["running"] is False
            assert cleared_relaxation["relaxation"]["frameCount"] == 0

            stale = _post_command(
                command_url,
                "apply",
                {
                    "expectedRevision": initial["collaboration"]["revision"],
                    "camera": {"axis": "-Z"},
                },
                expected_status=422,
            )
            assert "Collaboration revision conflict" in stale["detail"]

            rendered = _post_command(
                command_url,
                "render",
                {
                    "format": "png",
                    "width": 320,
                    "height": 240,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": True,
                        "includeCell": True,
                        "backgroundColor": "#ffffff",
                    },
                },
            )["result"]
            assert rendered["width"] == 320
            assert rendered["height"] == 240
            image_bytes = base64.b64decode(rendered["dataUrl"].split(",", 1)[1])
            with Image.open(io.BytesIO(image_bytes)) as image:
                assert image.size == (320, 240)
                pixels = np.asarray(image.convert("RGB"), dtype=np.float32)
            assert float(pixels.std()) > 2.0

            cli_image_path = tmp_path / "agent-http-render.png"
            try:
                cli_render = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "v_ase.cli",
                        "api",
                        command_url,
                        "render",
                        "--params",
                        json.dumps({
                            "format": "png",
                            "width": 160,
                            "height": 120,
                            "options": {
                                "includeGrid": False,
                                "includeAxes": True,
                                "includeCell": True,
                            },
                        }),
                        "--save",
                        str(cli_image_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                cli_payload = json.loads(cli_render.stdout)["result"]
                assert cli_payload["saved_bytes"] == cli_image_path.stat().st_size
                with Image.open(cli_image_path) as cli_image:
                    assert cli_image.size == (160, 120)
            finally:
                cli_image_path.unlink(missing_ok=True)

            html_export = _post_command(
                command_url,
                "export",
                {
                    "format": "html",
                    "width": 320,
                    "height": 240,
                    "embedProject": False,
                    "options": {
                        "includeGrid": False,
                        "includeAxes": True,
                        "includeCell": True,
                    },
                },
            )["result"]
            assert html_export["filename"].endswith(".html")
            assert html_export["mimeType"].startswith("text/html")
            html_bytes = base64.b64decode(html_export["dataUrl"].split(",", 1)[1])
            assert b"v_ase" in html_bytes

            documents = _post_command(command_url, "documents")["result"]
            assert documents["activeSessionId"] == editor.session_id
            assert len(documents["documents"]) == 1

            created = _post_command(command_url, "newDocument")["result"]
            assert created["sessionId"] != editor.session_id
            documents = _post_command(command_url, "documents")["result"]
            assert len(documents["documents"]) == 2
            assert documents["activeSessionId"] == created["sessionId"]

            activated = _post_command(
                command_url,
                "activate",
                {"sessionId": editor.session_id},
            )["result"]
            assert activated["sessionId"] == editor.session_id

            document_command_url = (
                f"http://127.0.0.1:{port}/api/ai/command/session/{editor.session_id}"
            )
            direct = _post_command(
                document_command_url,
                "describe",
                {"includePositions": False},
            )["result"]
            assert direct["document"] == initial["document"]
            assert "positions" not in direct
            browser.close()
    finally:
        editor.close()
