import asyncio
import subprocess
import sys

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.atom_scalars import atom_scalar_catalog, atom_scalar_values
from v_ase.colormaps import colormap_catalog, colormap_lut
from v_ase.export import _cad_scene_data
from v_ase.server import per_atom_scalar_catalog, per_atom_scalar_values
from v_ase.session import EditorSession, sessions
from v_ase.viewer import find_free_port, view


def _field(catalog, *, source, name, reduction, component=None):
    return next(
        item
        for item in catalog
        if item["source"] == source
        and item["name"] == name
        and item["reduction"] == reduction
        and item["component"] == component
    )


def test_catalog_discovers_coordinates_forces_arrays_and_calculator_results():
    atoms = Atoms("H2", positions=[[0, 1, 2], [3, 4, 5]])
    atoms.new_array("mlip_uncertainty", np.array([0.2, 0.7]))
    atoms.new_array("local_descriptor", np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 2.0]]))
    atoms.new_array("non_numeric_labels", np.array(["left", "right"]))
    atoms.calc = SinglePointCalculator(
        atoms,
        forces=np.array([[3.0, 4.0, 0.0], [0.0, 0.0, 2.0]]),
        charges=np.array([-0.3, 0.3]),
        energies=np.array([-1.2, -1.1]),
    )

    catalog = atom_scalar_catalog(atoms)
    assert [entry["id"] for entry in catalog[:3]] == ["position:x", "position:y", "position:z"]
    assert any(entry["id"] == "force:norm" for entry in catalog)
    assert not any(entry["name"] == "non_numeric_labels" for entry in catalog)

    uncertainty = _field(catalog, source="array", name="mlip_uncertainty", reduction="scalar")
    descriptor_norm = _field(catalog, source="array", name="local_descriptor", reduction="norm")
    descriptor_y = _field(
        catalog,
        source="array",
        name="local_descriptor",
        reduction="component",
        component=1,
    )
    charges = _field(catalog, source="result", name="charges", reduction="scalar")

    assert np.allclose(atom_scalar_values(atoms, "position:z"), [2.0, 5.0])
    assert np.allclose(atom_scalar_values(atoms, "force:norm"), [5.0, 2.0])
    assert np.allclose(atom_scalar_values(atoms, uncertainty["id"]), [0.2, 0.7])
    assert np.allclose(atom_scalar_values(atoms, descriptor_norm["id"]), [5.0, 2.0])
    assert np.allclose(atom_scalar_values(atoms, descriptor_y["id"]), [4.0, 0.0])
    assert np.allclose(atom_scalar_values(atoms, charges["id"]), [-0.3, 0.3])


def test_colormap_registry_exposes_all_registered_maps_and_stable_luts():
    catalog = colormap_catalog()
    names = {entry["name"] for entry in catalog["maps"]}
    assert catalog["provider"] == "Matplotlib"
    assert {"viridis", "coolwarm", "tab20", "viridis_r"}.issubset(names)

    forward = colormap_lut("viridis", samples=64)
    reverse = colormap_lut("viridis", samples=64, reverse=True)
    assert len(forward["colors"]) == 64
    assert forward["colors"][0] == reverse["colors"][-1]
    assert forward["colors"][-1] == reverse["colors"][0]


def test_normal_server_import_does_not_load_matplotlib():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import v_ase.server; print('matplotlib' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False"


def test_scalar_api_returns_one_compact_trajectory_cache_when_layout_matches():
    first = Atoms("H2", positions=[[0, 0, 0], [0, 0, 1]])
    second = first.copy()
    second.positions[:, 2] = [2, 3]
    first.new_array("score", np.array([1.0, 2.0]))
    second.new_array("score", np.array([3.0, 4.0]))
    session = EditorSession(
        "atom-colorscale-api",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session

    discovered = asyncio.run(per_atom_scalar_catalog(session.session_id, frame_index=0))
    score = _field(discovered["fields"], source="array", name="score", reduction="scalar")
    response = asyncio.run(
        per_atom_scalar_values(
            session.session_id,
            {"field_id": score["id"], "frame_index": 0, "all_frames": True},
        )
    )
    values = np.frombuffer(response.body, dtype=np.float32).reshape(2, 2)
    assert response.headers["x-v-ase-cache"] == "trajectory"
    assert np.allclose(values, [[1.0, 2.0], [3.0, 4.0]])


def test_scalar_api_marks_missing_frame_arrays_as_nan_instead_of_reusing_values():
    first = Atoms("H", positions=[[0, 0, 0]])
    second = first.copy()
    first.new_array("optional_score", np.array([5.0]))
    session = EditorSession(
        "atom-colorscale-missing-frame",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session
    field_id = _field(
        atom_scalar_catalog(first),
        source="array",
        name="optional_score",
        reduction="scalar",
    )["id"]

    response = asyncio.run(
        per_atom_scalar_values(
            session.session_id,
            {"field_id": field_id, "frame_index": 0, "all_frames": True},
        )
    )
    values = np.frombuffer(response.body, dtype=np.float32)
    assert values[0] == 5.0
    assert np.isnan(values[1])


def test_cad_scene_uses_current_colorscale_without_overwriting_uncolored_atoms():
    atoms = Atoms("H2", positions=[[0, 0, 0], [0, 0, 1]], cell=[4, 4, 4], pbc=True)
    session = EditorSession("atom-colorscale-cad", atoms.copy(), atoms.copy())
    scene = _cad_scene_data(
        session,
        {
            "display": {
                "showBonds": False,
                "labelColors": {"H": "#112233"},
                "atomColorScaleEnabled": True,
                "atomColorScaleColors": ["#abcdef", None],
                "supercell": [2, 1, 1],
            }
        },
    )
    first_colors = [atom["color"] for atom in scene["atoms"] if atom["index"] == 0]
    second_colors = [atom["color"] for atom in scene["atoms"] if atom["index"] == 1]
    assert first_colors == ["#abcdef", "#abcdef"]
    assert second_colors == ["#112233", "#112233"]


def test_browser_colorscale_is_lazy_selection_scoped_frame_aware_and_reversible():
    first = Atoms(
        "H3",
        positions=[[0, 0, 0], [0, 0, 1], [0, 0, 2]],
        cell=[8, 8, 8],
        pbc=True,
    )
    first.new_array("mlip_uncertainty", np.array([0.0, 1.0, 2.0]))
    first.new_array("forces", np.array([[1.0, 0, 0], [0, 2.0, 0], [0, 0, 3.0]]))
    first.set_initial_charges([-0.2, 0.0, 0.2])
    second = first.copy()
    second.arrays["mlip_uncertainty"][:] = [8.0, 9.0, 10.0]
    second.arrays["forces"][:] = [[4.0, 0, 0], [0, 5.0, 0], [0, 0, 6.0]]
    second.set_initial_charges([-0.4, 0.0, 0.4])
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
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")

            assert not [
                url for url in requests
                if "/api/analysis/atom-scalars/" in url or "/api/analysis/colormaps/" in url
            ]
            base_colors = page.evaluate("""() => [0, 1, 2].map(index => (
                window.__ASE_APP__.renderer.atomVisualColor(index)
            ))""")

            if page.locator("body").evaluate(
                "element => element.classList.contains('inspector-collapsed')"
            ):
                page.click("#btn-inspector-collapse")
            page.click('[data-inspector-group="structure"]')
            page.select_option("#structure-section-select", "appearance")
            page.wait_for_function(
                "document.querySelector('[data-panel=\"appearance\"]')?.open === true"
            )

            page.evaluate("""() => {
                const input = document.getElementById('chk-atom-colorscale');
                input.checked = true;
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function("window.__ASE_APP__.atomColorScaleRuntime.catalog?.fields?.length > 3")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors?.length === 3")
            catalog = page.evaluate("window.__ASE_APP__.atomColorScaleRuntime.catalog.fields")
            assert any(item["id"] == "force:norm" for item in catalog)
            assert any(item["name"] == "initial_charges" for item in catalog)
            assert any(item["name"] == "mlip_uncertainty" for item in catalog)
            assert page.locator("#atom-colorscale-map option").count() > 100

            page.select_option("#atom-colorscale-field", "array::mlip_uncertainty::scalar")
            page.evaluate("""() => {
                const input = document.getElementById('chk-atom-colorscale-auto-range');
                input.checked = false;
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.fill("#atom-colorscale-min", "0")
            page.fill("#atom-colorscale-max", "10")
            page.locator("#atom-colorscale-max").press("Tab")
            page.evaluate("window.__ASE_APP__.updateAtomColorScale({quiet:true})")
            first_frame_colors = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )

            page.evaluate("window.__ASE_APP__.loadFrame(1)")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 1")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors?.length === 3")
            second_frame_colors = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )
            assert second_frame_colors != first_frame_colors

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.addSelectionReference(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.select_option("#atom-colorscale-scope", "selected")
            page.evaluate("window.__ASE_APP__.updateAtomColorScale({quiet:true})")
            selected_colors = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )
            assert selected_colors[0] is None
            assert selected_colors[1].startswith("#")
            assert selected_colors[2] is None
            assert page.locator("#atom-colorscale-legend").is_visible()

            request_count = len([
                url for url in requests
                if "/api/analysis/atom-scalars/" in url or "/api/analysis/colormaps/" in url
            ])
            page.evaluate("""() => {
                const input = document.getElementById('chk-atom-colorscale');
                input.checked = false;
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors === null")
            restored = page.evaluate("""() => [0, 1, 2].map(index => (
                window.__ASE_APP__.renderer.atomVisualColor(index)
            ))""")
            assert restored == base_colors
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.clearAtomSelection();
                app.addSelectionReference(0);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.wait_for_timeout(100)
            assert len([
                url for url in requests
                if "/api/analysis/atom-scalars/" in url or "/api/analysis/colormaps/" in url
            ]) == request_count

            capabilities = page.evaluate("window.v_aseAI.capabilities()")
            assert capabilities["atomColorScale"]["provider"] == "Matplotlib"
            assert capabilities["atomColorScale"]["scalarCatalogUrl"]
            assert capabilities["atomColorScale"]["colormapCatalogUrl"]
            assert "set-atom-colorscale" in capabilities["operations"]
            page.evaluate("""async () => await window.v_aseAI.apply({
                operation: {
                    name: 'set-atom-colorscale',
                    enabled: true,
                    field: 'position:z',
                    map: 'plasma',
                    scope: 'all',
                    autoRange: true
                }
            })""")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.atomColorScaleColors?.every(Boolean)"
            )
            page.evaluate("""async () => await window.v_aseAI.apply({
                operation: {name: 'set-atom-colorscale', enabled: false}
            })""")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors === null")
            browser.close()
    finally:
        editor.close()
