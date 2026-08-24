import asyncio
import subprocess
import sys

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.atom_scalars import (
    atom_force_vectors,
    atom_property_snapshot,
    atom_scalar_catalog,
    atom_scalar_values,
)
from v_ase.colormaps import (
    colormap_catalog,
    colormap_lut,
    custom_colormap_lut,
    normalize_custom_colormap,
)
from v_ase.export import _cad_scene_data
from v_ase.server import (
    per_atom_force_vectors,
    per_atom_properties,
    per_atom_scalar_catalog,
    per_atom_scalar_range,
    per_atom_scalar_values,
)
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
    assert np.allclose(atom_force_vectors(atoms), [[3.0, 4.0, 0.0], [0.0, 0.0, 2.0]])
    assert np.allclose(atom_scalar_values(atoms, uncertainty["id"]), [0.2, 0.7])
    assert np.allclose(atom_scalar_values(atoms, descriptor_norm["id"]), [5.0, 2.0])
    assert np.allclose(atom_scalar_values(atoms, descriptor_y["id"]), [4.0, 0.0])
    assert np.allclose(atom_scalar_values(atoms, charges["id"]), [-0.3, 0.3])


def test_atom_property_snapshot_includes_standard_arrays_strings_and_stored_results():
    atoms = Atoms("HO", positions=[[0, 0, 0], [1, 2, 3]])
    atoms.set_tags([2, 5])
    atoms.set_masses([1.2, 16.5])
    atoms.set_initial_charges([-0.1, 0.2])
    atoms.set_initial_magnetic_moments([0.5, 1.5])
    atoms.new_array("site_name", np.array(["donor", "acceptor"]))
    atoms.new_array("descriptor", np.array([[1.0, 2.0], [3.0, 4.0]]))
    atoms.calc = SinglePointCalculator(
        atoms,
        forces=np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
        charges=np.array([-0.3, 0.3]),
        energies=np.array([-1.2, -1.1]),
    )

    properties = atom_property_snapshot(atoms, 1)
    by_key = {(item["source"], item["name"]): item for item in properties}

    assert by_key[("ase", "atomic_number")]["value"] == 8
    assert by_key[("ase", "mass")]["value"] == pytest.approx(16.5)
    assert by_key[("ase", "tag")]["value"] == 5
    assert by_key[("ase", "initial_charge")]["value"] == pytest.approx(0.2)
    assert by_key[("ase", "initial_magmom")]["value"] == pytest.approx(1.5)
    assert by_key[("array", "site_name")]["value"] == "acceptor"
    assert by_key[("array", "descriptor")]["value"] == [3.0, 4.0]
    assert by_key[("calculator", "forces")]["value"] == [0.4, 0.5, 0.6]
    assert by_key[("calculator", "forces")]["unit"] == "eV/A"
    assert by_key[("calculator", "charges")]["value"] == pytest.approx(0.3)
    assert by_key[("calculator", "energies")]["value"] == pytest.approx(-1.1)


def test_atom_property_api_uses_the_requested_trajectory_frame():
    first = Atoms("H", positions=[[0, 0, 0]])
    second = Atoms("H", positions=[[1, 2, 3]])
    first.new_array("score", np.array([1.25]))
    second.new_array("score", np.array([9.75]))
    session = EditorSession(
        "atom-property-frame-api",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session
    try:
        result = asyncio.run(per_atom_properties(session.session_id, 0, frame_index=1))
    finally:
        sessions.pop(session.session_id, None)

    score = next(item for item in result["properties"] if item["name"] == "score")
    assert result["frame_index"] == 1
    assert result["atom_index"] == 0
    assert score["source"] == "array"
    assert score["value"] == pytest.approx(9.75)


def test_single_atom_measure_lists_current_frame_properties_lazily():
    first = Atoms("HO", positions=[[0, 0, 0], [1, 2, 3]], cell=[8, 8, 8], pbc=True)
    first.set_tags([2, 5])
    first.set_initial_charges([-0.1, 0.2])
    first.set_initial_magnetic_moments([0.5, 1.5])
    first.new_array("score", np.array([1.25, 2.5]))
    first.new_array("descriptor", np.array([[1.0, 2.0], [3.0, 4.0]]))
    first.new_array("site_name", np.array(["donor", "acceptor"]))
    first.calc = SinglePointCalculator(
        first,
        forces=np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]),
        charges=np.array([-0.3, 0.3]),
        energies=np.array([-1.2, -1.1]),
    )
    second = first.copy()
    second.positions[1] = [4, 5, 6]
    second.arrays["score"][:] = [8.5, 9.75]
    second.arrays["descriptor"][1] = [7.0, 8.0]
    second.calc = SinglePointCalculator(
        second,
        forces=np.array([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]]),
        charges=np.array([-0.4, 0.4]),
        energies=np.array([-1.0, -0.9]),
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
            page = browser.new_page(viewport={"width": 1360, "height": 860})
            property_requests = []
            page.on(
                "request",
                lambda request: property_requests.append(request.url)
                if "/api/analysis/atom-properties/" in request.url else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.addSelectionReference(1);
                app.updateSelectionVisuals();
                app.updateUI();
            }""")
            page.wait_for_function("""() => (
                document.getElementById('selected-measure').innerText.includes(
                    'Per-atom properties (11):'
                )
            )""")
            first_measure = page.locator("#selected-measure").inner_text()
            assert "a1=#1 O" in first_measure
            assert "Element: O" in first_measure
            assert "Position (Cartesian): (1.000000, 2.000000, 3.000000) A" in first_measure
            assert "Position (fractional): (0.125000, 0.250000, 0.375000)" in first_measure
            assert "[ASE] atomic_number = 8" in first_measure
            assert "[ASE] tag = 5" in first_measure
            assert "[ASE] initial_charge = 0.2 e" in first_measure
            assert "[ASE array] descriptor = [3, 4]" in first_measure
            assert "[ASE array] site_name = acceptor" in first_measure
            assert "[Calculator] charges = 0.3 e" in first_measure
            assert "[Calculator] energies = -1.1 eV" in first_measure
            assert "11 properties" in page.locator("#selection-measure-value").inner_text()
            assert len(property_requests) == 1

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.updateUI();
                app.updateUI();
            }""")
            page.wait_for_timeout(50)
            assert len(property_requests) == 1

            page.evaluate("() => window.__ASE_APP__.loadFrame(1)")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 1")
            page.wait_for_function("""() => (
                document.getElementById('selected-measure').innerText.includes(
                    '[ASE array] score = 9.75'
                )
            )""")
            second_measure = page.locator("#selected-measure").inner_text()
            assert "Position (Cartesian): (4.000000, 5.000000, 6.000000) A" in second_measure
            assert "[ASE array] descriptor = [7, 8]" in second_measure
            assert len(property_requests) == 2
            browser.close()
    finally:
        editor.close()


def test_force_vector_api_returns_frame_specific_cartesian_vectors():
    first = Atoms("H2", positions=[[0, 0, 0], [0, 0, 1]])
    second = first.copy()
    first.new_array("forces", np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]))
    second.new_array("forces", np.array([[0.0, 2.0, 0.0], [0.0, -2.0, 0.0]]))
    session = EditorSession(
        "force-vector-api",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session

    response = asyncio.run(
        per_atom_force_vectors(
            session.session_id,
            {"frame_index": 0, "all_frames": True},
        )
    )
    vectors = np.frombuffer(response.body, dtype=np.float32).reshape(2, 2, 3)
    assert response.headers["x-v-ase-cache"] == "trajectory"
    np.testing.assert_allclose(vectors[0], [[1, 0, 0], [-1, 0, 0]])
    np.testing.assert_allclose(vectors[1], [[0, 2, 0], [0, -2, 0]])


def test_colormap_registry_exposes_all_registered_maps_and_stable_luts():
    catalog = colormap_catalog()
    names = {entry["name"] for entry in catalog["maps"]}
    assert catalog["provider"] == "Matplotlib"
    assert catalog["preview_samples"] == 24
    assert {"viridis", "coolwarm", "tab20", "viridis_r"}.issubset(names)
    viridis = next(entry for entry in catalog["maps"] if entry["name"] == "viridis")
    assert len(viridis["preview"]) == catalog["preview_samples"]
    assert viridis["preview"][0] == colormap_lut("viridis", samples=24)["colors"][0]
    assert viridis["preview"][-1] == colormap_lut("viridis", samples=24)["colors"][-1]

    forward = colormap_lut("viridis", samples=64)
    reverse = colormap_lut("viridis", samples=64, reverse=True)
    assert len(forward["colors"]) == 64
    assert forward["colors"][0] == reverse["colors"][-1]
    assert forward["colors"][-1] == reverse["colors"][0]


def test_custom_colormap_supports_continuous_discrete_and_reverse_sampling():
    specification = {
        "mode": "continuous",
        "stops": [
            {"position": 0, "color": "#FF0000"},
            {"position": 0.5, "color": "#00FF00"},
            {"position": 1, "color": "#0000FF"},
        ],
    }
    normalized = normalize_custom_colormap(specification)
    assert normalized == specification

    continuous = custom_colormap_lut(specification, samples=16)
    reverse = custom_colormap_lut(specification, samples=16, reverse=True)
    assert continuous["provider"] == "Custom"
    assert continuous["colors"][0] == "#FF0000"
    assert continuous["colors"][-1] == "#0000FF"
    assert continuous["colors"] == list(reversed(reverse["colors"]))

    discrete = custom_colormap_lut(
        {**specification, "mode": "discrete"},
        samples=16,
    )
    assert discrete["colors"][0] == "#FF0000"
    assert discrete["colors"][7] == "#FF0000"
    assert discrete["colors"][8] == "#00FF00"
    assert discrete["colors"][-1] == "#0000FF"

    with pytest.raises(ValueError, match="at least two"):
        normalize_custom_colormap({"mode": "continuous", "stops": []})
    with pytest.raises(ValueError, match="unique"):
        normalize_custom_colormap({
            "mode": "continuous",
            "stops": [
                {"position": 0.5, "color": "#000000"},
                {"position": 0.5, "color": "#FFFFFF"},
            ],
        })


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

    missing_response = asyncio.run(
        per_atom_scalar_values(
            session.session_id,
            {"field_id": field_id, "frame_index": 1, "all_frames": False},
        )
    )
    missing_values = np.frombuffer(missing_response.body, dtype=np.float32)
    assert missing_response.headers["x-v-ase-cache"] == "frame"
    assert missing_response.headers["x-v-ase-start-frame"] == "1"
    assert missing_values.shape == (1,)
    assert np.isnan(missing_values[0])


def test_scalar_range_api_scans_trajectory_without_materializing_value_cube():
    first = Atoms("H2", positions=[[0, 0, 0], [0, 0, 1]])
    second = first.copy()
    first.new_array("score", np.array([1.0, 2.0]))
    second.new_array("score", np.array([3.0, 4.0]))
    session = EditorSession(
        "atom-colorscale-range",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    sessions[session.session_id] = session
    field_id = _field(
        atom_scalar_catalog(first),
        source="array",
        name="score",
        reduction="scalar",
    )["id"]

    current = asyncio.run(per_atom_scalar_range(
        session.session_id,
        {"field_id": field_id, "frame_index": 0, "all_frames": False},
    ))
    trajectory = asyncio.run(per_atom_scalar_range(
        session.session_id,
        {"field_id": field_id, "frame_index": 0, "all_frames": True},
    ))
    selected = asyncio.run(per_atom_scalar_range(
        session.session_id,
        {
            "field_id": field_id,
            "frame_index": 0,
            "all_frames": True,
            "indices": [1],
        },
    ))

    assert (current["minimum"], current["maximum"]) == (1.0, 2.0)
    assert (trajectory["minimum"], trajectory["maximum"]) == (1.0, 4.0)
    assert trajectory["frames_scanned"] == 2
    assert trajectory["finite_values"] == 4
    assert (selected["minimum"], selected["maximum"]) == (2.0, 4.0)
    assert selected["scope"] == "selected"


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
    third = Atoms("H3", positions=first.positions + [0, 0, 4], cell=first.cell, pbc=True)
    port = find_free_port()
    editor = view(
        [first, second, third],
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
            scalar_value_payloads = []

            def track_request(request):
                requests.append(request.url)
                if "/api/analysis/atom-scalars/values/" in request.url:
                    scalar_value_payloads.append(request.post_data_json)

            page.on("request", track_request)
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

            page.click("#atom-colormap-trigger")
            page.wait_for_selector("#atom-colormap-menu:not(.hidden)")
            assert page.locator("#atom-colormap-menu .atom-colormap-option").count() > 100
            preview_styles = page.locator(
                "#atom-colormap-menu .atom-colormap-option:not([data-map='custom']) .atom-colormap-swatch"
            ).evaluate_all("elements => elements.slice(0, 8).map(element => element.style.backgroundImage)")
            assert preview_styles
            assert all("linear-gradient" in value for value in preview_styles)

            page.click(".atom-colormap-option[data-map='custom']")
            page.wait_for_selector("#modal-container .custom-colormap-modal")
            assert page.locator(".custom-colormap-stop").count() == 3
            page.click("#btn-add-custom-colormap-stop")
            assert page.locator(".custom-colormap-stop").count() == 4
            page.locator(".custom-colormap-stop-hex").first.fill("#001122")
            page.locator("[data-custom-colormap-mode='discrete']").click()
            custom_preview = page.locator("#custom-colormap-preview").evaluate(
                "element => element.style.backgroundImage"
            )
            assert "linear-gradient" in custom_preview
            assert "rgb(0, 17, 34)" in custom_preview
            page.click("#modal-apply-custom-colormap")
            page.wait_for_function("""() => (
                window.__ASE_APP__.state.display.atomColorScaleMap === 'custom'
                && window.__ASE_APP__.renderer.atomColorScaleColors?.length === 3
            )""")
            custom_state = page.evaluate("window.__ASE_APP__.state.display.atomColorScaleCustomMap")
            assert custom_state["mode"] == "discrete"
            assert len(custom_state["stops"]) == 4
            assert custom_state["stops"][0]["color"] == "#001122"
            assert page.locator("#atom-colormap-trigger-name").inner_text() == "Custom"
            assert page.evaluate("""() => (
                window.__ASE_APP__.designSettingsSnapshot().display.atomColorScaleCustomMap
            )""") == custom_state

            custom_colors = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )
            custom_preview_before_reverse = page.locator(
                "#atom-colormap-trigger-preview"
            ).evaluate("element => element.style.backgroundImage")
            page.evaluate("""() => {
                const reverse = document.getElementById('chk-atom-colorscale-reverse');
                reverse.checked = true;
                reverse.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.atomColorScaleReverse === true"
            )
            page.wait_for_timeout(50)
            assert page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            ) != custom_colors
            assert page.locator("#atom-colormap-trigger-preview").evaluate(
                "element => element.style.backgroundImage"
            ) != custom_preview_before_reverse

            page.select_option("#atom-colorscale-map", "viridis")
            page.locator("#atom-colorscale-map").dispatch_event("change")
            page.evaluate("""() => {
                const reverse = document.getElementById('chk-atom-colorscale-reverse');
                reverse.checked = false;
                reverse.dispatchEvent(new Event('change', {bubbles: true}));
            }""")
            page.wait_for_function(
                """() => (
                    window.__ASE_APP__.state.display.atomColorScaleMap === 'viridis'
                    && window.__ASE_APP__.state.display.atomColorScaleReverse === false
                )"""
            )

            page.select_option("#atom-colorscale-field", "array::mlip_uncertainty::scalar")
            page.wait_for_function("""() => (
                window.__ASE_APP__.state.display.atomColorScaleRangeMode === 'current'
                && window.__ASE_APP__.state.display.atomColorScaleMin === 0
                && window.__ASE_APP__.state.display.atomColorScaleMax === 2
            )""")
            current_range = page.evaluate("""() => [
                window.__ASE_APP__.state.display.atomColorScaleMin,
                window.__ASE_APP__.state.display.atomColorScaleMax
            ]""")
            assert current_range == [0, 2]
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
            assert page.evaluate("""() => [
                window.__ASE_APP__.state.display.atomColorScaleMin,
                window.__ASE_APP__.state.display.atomColorScaleMax
            ]""") == [0, 2]

            page.click("#btn-atom-colorscale-fit-trajectory")
            page.wait_for_function("""() => (
                window.__ASE_APP__.state.display.atomColorScaleRangeMode === 'trajectory'
                && window.__ASE_APP__.state.display.atomColorScaleMin === 0
                && window.__ASE_APP__.state.display.atomColorScaleMax === 10
            )""")
            assert page.locator("#atom-colorscale-range-source").inner_text() == "FULL TRAJECTORY"
            assert scalar_value_payloads
            assert all(payload["all_frames"] is False for payload in scalar_value_payloads)

            page.evaluate("window.__ASE_APP__.loadFrame(2)")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 2")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors?.length === 3")
            assert page.evaluate(
                "window.__ASE_APP__.state.display.atomColorScaleField"
            ) == "array::mlip_uncertainty::scalar"
            assert page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            ) == [None, None, None]
            assert page.evaluate("""() => [
                window.__ASE_APP__.state.display.atomColorScaleMin,
                window.__ASE_APP__.state.display.atomColorScaleMax
            ]""") == [0, 10]

            page.evaluate("window.__ASE_APP__.loadFrame(1)")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 1")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.atomColorScaleColors?.some(Boolean)"
            )

            colors_before_gamma = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )
            page.fill("#atom-colorscale-gamma", "2")
            page.locator("#atom-colorscale-gamma").dispatch_event("input")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.atomColorScaleGamma === 2"
            )
            page.wait_for_timeout(50)
            colors_after_gamma = page.evaluate(
                "window.__ASE_APP__.renderer.atomColorScaleColors"
            )
            assert colors_after_gamma != colors_before_gamma

            page.fill("#atom-colorscale-min", "-1")
            page.locator("#atom-colorscale-min").press("Tab")
            page.fill("#atom-colorscale-max", "12")
            page.locator("#atom-colorscale-max").press("Tab")
            page.wait_for_function(
                "window.__ASE_APP__.state.display.atomColorScaleRangeMode === 'manual'"
            )
            assert page.evaluate("""() => [
                window.__ASE_APP__.state.display.atomColorScaleMin,
                window.__ASE_APP__.state.display.atomColorScaleMax
            ]""") == [-1, 12]

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

            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.__testSelectionRebuilds = 0;
                app.__testOriginalSetSelection = app.renderer.setSelection.bind(app.renderer);
                app.renderer.setSelection = (...args) => {
                    app.__testSelectionRebuilds += 1;
                    return app.__testOriginalSetSelection(...args);
                };
            }""")
            page.evaluate("window.__ASE_APP__.loadFrame(0)")
            page.wait_for_function("window.__ASE_APP__.state.atoms.metadata.current_frame === 0")
            assert page.evaluate("window.__ASE_APP__.state.selected.has(1)") is True
            assert page.evaluate("window.__ASE_APP__.__testSelectionRebuilds") == 0
            page.evaluate("""() => {
                const app = window.__ASE_APP__;
                app.renderer.setSelection = app.__testOriginalSetSelection;
                delete app.__testOriginalSetSelection;
                delete app.__testSelectionRebuilds;
            }""")

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
            assert capabilities["atomColorScale"]["providers"] == ["Matplotlib", "Custom"]
            assert capabilities["atomColorScale"]["customMap"]["minimumStops"] == 2
            assert capabilities["atomColorScale"]["scalarCatalogUrl"]
            assert capabilities["atomColorScale"]["colormapCatalogUrl"]
            assert capabilities["atomColorScale"]["rangeUrl"]
            assert capabilities["atomColorScale"]["rangeModes"] == [
                "current", "trajectory", "manual"
            ]
            assert "set-atom-colorscale" in capabilities["operations"]
            page.evaluate("""async () => await window.v_aseAI.apply({
                operation: {
                    name: 'set-atom-colorscale',
                    enabled: true,
                    field: 'position:z',
                    map: 'plasma',
                    scope: 'all',
                    rangeMode: 'trajectory',
                    gamma: 1.5
                }
            })""")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.atomColorScaleColors?.every(Boolean)"
            )
            assert page.evaluate(
                "window.__ASE_APP__.state.display.atomColorScaleRangeMode"
            ) == "trajectory"
            assert page.evaluate(
                "window.__ASE_APP__.state.display.atomColorScaleGamma"
            ) == 1.5
            page.evaluate("""async () => await window.v_aseAI.apply({
                operation: {
                    name: 'set-atom-colorscale',
                    enabled: true,
                    field: 'position:z',
                    customMap: {
                        mode: 'continuous',
                        stops: [
                            {position: 0, color: '#112233'},
                            {position: 0.4, color: '#44AA88'},
                            {position: 1, color: '#FFDD55'}
                        ]
                    },
                    rangeMode: 'current'
                }
            })""")
            page.wait_for_function("""() => (
                window.__ASE_APP__.state.display.atomColorScaleMap === 'custom'
                && window.__ASE_APP__.renderer.atomColorScaleColors?.every(Boolean)
            )""")
            assert page.evaluate(
                "window.__ASE_APP__.state.display.atomColorScaleCustomMap.stops.length"
            ) == 3
            page.evaluate("""async () => await window.v_aseAI.apply({
                operation: {name: 'set-atom-colorscale', enabled: false}
            })""")
            page.wait_for_function("window.__ASE_APP__.renderer.atomColorScaleColors === null")
            browser.close()
    finally:
        editor.close()


def test_large_browser_trajectory_scans_and_caches_colorscale_values_once():
    atom_count = 5_000
    positions = np.zeros((atom_count, 3), dtype=float)
    positions[:, 0] = np.arange(atom_count) % 100
    positions[:, 1] = np.arange(atom_count) // 100
    first = Atoms(["H"] * atom_count, positions=positions, cell=[120, 60, 8], pbc=True)
    second = first.copy()
    first.new_array("score", np.linspace(-2.0, 3.0, atom_count))
    second.new_array("score", np.linspace(4.0, 9.0, atom_count))
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
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            value_payloads = []
            range_requests = []

            def track_request(request):
                if "/api/analysis/atom-scalars/values/" in request.url:
                    value_payloads.append(request.post_data_json)
                if "/api/analysis/atom-scalars/range/" in request.url:
                    range_requests.append(request.post_data_json)

            page.on("request", track_request)
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function(
                f"window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === {atom_count}"
            )
            page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.atomColorScaleEnabled = true;
                app.state.display.atomColorScaleField = 'array::score::scalar';
                app.state.display.atomColorScaleRangeMode = 'current';
                await app.updateAtomColorScale({quiet: true, refreshCatalog: true});
            }""")
            value_payloads.clear()
            range_requests.clear()

            page.evaluate("window.__ASE_APP__.fitAtomColorScaleRange('trajectory')")
            page.wait_for_function("""() => (
                window.__ASE_APP__.state.display.atomColorScaleRangeMode === 'trajectory'
                && window.__ASE_APP__.state.display.atomColorScaleMin === -2
                && window.__ASE_APP__.state.display.atomColorScaleMax === 9
            )""")

            assert value_payloads == [{
                "field_id": "array::score::scalar",
                "frame_index": 0,
                "all_frames": True,
            }]
            assert range_requests == []
            assert page.evaluate("""() => {
                const cache = window.__ASE_APP__.atomColorScaleRuntime.valueCaches.get(
                    'array::score::scalar'
                );
                return cache.frames === 2 && cache.atoms === 5000 && cache.values.length === 10000;
            }""") is True
            browser.close()
    finally:
        editor.close()


def test_browser_force_arrows_follow_each_trajectory_frame():
    first = Atoms("H2", positions=[[0, 0, 0], [0, 0, 1.2]], cell=[5, 5, 5], pbc=True)
    second = first.copy()
    second.positions[:, 0] += 0.2
    first.new_array("forces", np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]))
    second.new_array("forces", np.array([[0.0, 2.0, 0.0], [0.0, -2.0, 0.0]]))
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
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            force_requests = []
            page.on(
                "request",
                lambda request: force_requests.append(request.post_data_json)
                if "/api/analysis/force-vectors/" in request.url
                else None,
            )
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 2")
            first_vectors = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                app.state.display.showForceVectors = true;
                app.renderer.setDisplayOptions(app.state.display);
                await app.updateForceVectorsForCurrentFrame();
                return app.renderer.forceVectorGroup.userData.entries.map(entry => entry.vector);
            }""")
            second_vectors = page.evaluate("""async () => {
                const app = window.__ASE_APP__;
                await app.loadFrame(1);
                return app.renderer.forceVectorGroup.userData.entries.map(entry => entry.vector);
            }""")
            assert first_vectors == [[1, 0, 0], [-1, 0, 0]]
            assert second_vectors == [[0, 2, 0], [0, -2, 0]]
            assert first_vectors != second_vectors
            assert force_requests == [{"frame_index": 0, "all_frames": True}]
            browser.close()
    finally:
        editor.close()
