import asyncio

import numpy as np
import pytest
from ase import Atoms
from fastapi import HTTPException
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.builders import (
    BULK_STRUCTURE_SPECS,
    BulkBuildError,
    build_bulk_atoms,
    bulk_builder_catalog,
    bulk_preview_payload,
)
from v_ase.server import (
    apply_ase_bulk,
    ase_bulk_catalog,
    preview_ase_bulk,
    undo,
)
from v_ase.session import EditorSession, sessions
from v_ase.viewer import find_free_port, view


PROTOTYPE_REQUESTS = {
    "sc": {"formula": "H", "crystalstructure": "sc", "a": 3.0},
    "fcc": {"formula": "Cu", "crystalstructure": "fcc"},
    "bcc": {"formula": "Fe", "crystalstructure": "bcc"},
    "bct": {"formula": "In", "crystalstructure": "bct"},
    "hcp": {"formula": "Mg", "crystalstructure": "hcp"},
    "rhombohedral": {"formula": "As", "crystalstructure": "rhombohedral"},
    "orthorhombic": {"formula": "U", "crystalstructure": "orthorhombic"},
    "diamond": {"formula": "C", "crystalstructure": "diamond"},
    "zincblende": {
        "formula": "GaAs", "crystalstructure": "zincblende", "a": 5.65,
    },
    "rocksalt": {
        "formula": "NaCl", "crystalstructure": "rocksalt", "a": 5.64,
    },
    "cesiumchloride": {
        "formula": "CsCl", "crystalstructure": "cesiumchloride", "a": 4.12,
    },
    "fluorite": {
        "formula": "CaF2", "crystalstructure": "fluorite", "a": 5.46,
    },
    "wurtzite": {
        "formula": "ZnO", "crystalstructure": "wurtzite", "a": 3.25,
    },
}


def test_bulk_catalog_is_cached_and_describes_only_working_ase_paths():
    catalog = bulk_builder_catalog()

    assert bulk_builder_catalog() is catalog
    assert catalog["generator"] == "ase.build.bulk"
    assert {item["id"] for item in catalog["structures"]} == set(
        BULK_STRUCTURE_SPECS
    )
    assert "tetragonal" not in BULK_STRUCTURE_SPECS
    assert "mcl" not in BULK_STRUCTURE_SPECS

    references = {item["formula"]: item for item in catalog["reference_materials"]}
    assert "cubic" in references["Cu"]["compatible_cell_modes"]
    assert "cubic" not in references["Be"]["compatible_cell_modes"]
    assert references["Cu"]["atom_counts"]["cubic"] == 4


@pytest.mark.parametrize(
    ("structure", "cell_mode"),
    [
        (structure, cell_mode)
        for structure, spec in BULK_STRUCTURE_SPECS.items()
        for cell_mode in spec["cell_modes"]
    ],
)
def test_every_advertised_bulk_prototype_and_cell_mode_builds(
    structure,
    cell_mode,
):
    atoms, normalized = build_bulk_atoms({
        **PROTOTYPE_REQUESTS[structure],
        "cell_mode": cell_mode,
    })

    assert len(atoms) > 0
    assert atoms.pbc.all()
    assert atoms.get_volume() > 0
    assert np.isfinite(atoms.cell.array).all()
    assert normalized["effective_crystalstructure"] == structure
    assert normalized["cell_mode"] == cell_mode


def test_reference_copper_cubic_matches_ase_bulk_contract():
    preview = bulk_preview_payload({"formula": "Cu", "cell_mode": "cubic"})

    assert preview["valid"] is True
    assert preview["crystalstructure"] == "fcc"
    assert preview["atom_count"] == 4
    np.testing.assert_allclose(
        preview["cell_parameters"]["a"],
        preview["cell_parameters"]["b"],
    )
    np.testing.assert_allclose(
        preview["cell_parameters"]["a"],
        preview["cell_parameters"]["c"],
    )
    np.testing.assert_allclose(
        [
            preview["cell_parameters"]["alpha"],
            preview["cell_parameters"]["beta"],
            preview["cell_parameters"]["gamma"],
        ],
        [90.0, 90.0, 90.0],
    )


def test_custom_cuo_reports_exact_missing_arguments_then_builds():
    with pytest.raises(BulkBuildError) as missing_all:
        build_bulk_atoms({"formula": "CuO", "cell_mode": "cubic"})
    assert missing_all.value.missing_fields == ("crystalstructure", "a")

    with pytest.raises(BulkBuildError) as missing_a:
        build_bulk_atoms({
            "formula": "CuO",
            "crystalstructure": "rocksalt",
            "cell_mode": "cubic",
        })
    assert missing_a.value.missing_fields == ("a",)

    atoms, _ = build_bulk_atoms({
        "formula": "CuO",
        "crystalstructure": "rocksalt",
        "cell_mode": "cubic",
        "a": 4.27,
    })
    assert len(atoms) == 8
    assert atoms.get_chemical_formula() == "Cu4O4"


def test_incompatible_cubic_reference_and_conflicting_c_parameters_are_rejected():
    with pytest.raises(BulkBuildError, match="cannot construct a cubic cell"):
        build_bulk_atoms({"formula": "Be", "cell_mode": "cubic"})

    with pytest.raises(BulkBuildError, match="either c or c/a"):
        build_bulk_atoms({
            "formula": "ZnO",
            "crystalstructure": "wurtzite",
            "cell_mode": "primitive",
            "a": 3.25,
            "c": 5.2,
            "covera": 1.6,
        })


def test_custom_rhombohedral_requires_and_accepts_angle_and_basis():
    with pytest.raises(BulkBuildError) as incomplete:
        build_bulk_atoms({
            "formula": "B",
            "crystalstructure": "rhombohedral",
            "a": 3.0,
        })
    assert incomplete.value.missing_fields == ("alpha", "basis")

    atoms, _ = build_bulk_atoms({
        "formula": "B",
        "crystalstructure": "rhombohedral",
        "a": 3.0,
        "alpha": 58.0,
        "basis": [[0.0, 0.0, 0.0]],
    })
    assert len(atoms) == 1


def test_bulk_api_preview_apply_and_undo_restore_complete_trajectory():
    first = Atoms("H", positions=[[0, 0, 0]], cell=[6, 6, 6], pbc=True)
    second = first.copy()
    second.positions[0, 0] = 0.75
    session = EditorSession(
        "ase-bulk-api",
        first.copy(),
        second.copy(),
        original_frames=[first.copy(), first.copy()],
        trajectory_frames=[first.copy(), second.copy()],
        current_frame=1,
        config={
            "viz_only": False,
            "initial_design_settings": {"display": {"atomRadiusScale": 1.4}},
        },
    )
    sessions[session.session_id] = session
    try:
        catalog = asyncio.run(ase_bulk_catalog(session.session_id))
        assert catalog["generator"] == "ase.build.bulk"

        invalid = asyncio.run(preview_ase_bulk(session.session_id, {
            "formula": "CuO",
            "cell_mode": "cubic",
        }))
        assert invalid["valid"] is False
        assert invalid["missing_fields"] == ["crystalstructure", "a"]

        with pytest.raises(HTTPException) as confirmation:
            asyncio.run(apply_ase_bulk(session.session_id, {
                "formula": "Cu",
                "cell_mode": "cubic",
            }))
        assert confirmation.value.status_code == 409

        built = asyncio.run(apply_ase_bulk(session.session_id, {
            "formula": "Cu",
            "cell_mode": "cubic",
            "replace_existing": True,
        }))
        assert built["metadata"]["natoms"] == 4
        assert built["metadata"]["frame_count"] == 1
        assert built["generated_structure"] == {
            "generator": "ase.build.bulk",
            "formula": "Cu",
            "crystalstructure": "fcc",
            "cell_mode": "cubic",
        }
        assert session.config["initial_design_settings"]["display"]["atomRadiusScale"] == 1.4

        restored = asyncio.run(undo(session.session_id))
        assert restored["metadata"]["natoms"] == 1
        assert restored["metadata"]["frame_count"] == 2
        assert session.current_frame == 1
        np.testing.assert_allclose(session.trajectory_frames[0].positions, first.positions)
        np.testing.assert_allclose(session.trajectory_frames[1].positions, second.positions)
        np.testing.assert_allclose(session.original_atoms.positions, first.positions)
    finally:
        sessions.pop(session.session_id, None)


def test_bulk_apply_is_edit_only_and_blank_scratch_needs_no_replace_confirmation():
    view_session = EditorSession(
        "ase-bulk-view-only",
        Atoms(),
        Atoms(),
        config={"viz_only": True, "empty_workspace": True},
    )
    edit_session = EditorSession(
        "ase-bulk-empty-edit",
        Atoms(),
        Atoms(),
        config={"viz_only": False, "empty_workspace": True},
    )
    sessions[view_session.session_id] = view_session
    sessions[edit_session.session_id] = edit_session
    try:
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(apply_ase_bulk(view_session.session_id, {
                "formula": "Cu",
                "cell_mode": "cubic",
            }))
        assert blocked.value.status_code == 403

        built = asyncio.run(apply_ase_bulk(edit_session.session_id, {
            "formula": "Cu",
            "cell_mode": "cubic",
        }))
        assert built["metadata"]["natoms"] == 4
    finally:
        sessions.pop(view_session.session_id, None)
        sessions.pop(edit_session.session_id, None)


def test_browser_ase_bulk_builder_validates_builds_replaces_and_undoes():
    port = find_free_port()
    editor = view(
        Atoms(),
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
            page = browser.new_page(viewport={"width": 1440, "height": 920})
            try:
                page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
                page.wait_for_function(
                    "window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 0"
                )
                page.click("#btn-create-atom-toggle")
                page.click("#add-atoms-tab-build")
                page.wait_for_selector("#add-atoms-pane-build:not(.hidden)")
                page.wait_for_function(
                    "document.getElementById('ase-bulk-preview')?.dataset.state === 'valid'"
                )
                assert "4 atoms" in page.locator("#ase-bulk-preview-title").inner_text()
                assert "fcc" in page.locator("#ase-bulk-preview-title").inner_text()
                assert page.locator("#btn-ase-bulk-build").is_enabled()

                page.click("#btn-ase-bulk-build")
                page.wait_for_function(
                    "window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 4"
                )
                page.wait_for_function(
                    "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4"
                )

                page.fill("#ase-bulk-formula", "CuO")
                page.wait_for_function(
                    "document.getElementById('ase-bulk-preview')?.dataset.state === 'invalid'"
                )
                detail = page.locator("#ase-bulk-preview-detail").inner_text()
                assert "crystal structure" in detail
                assert "lattice parameter a" in detail
                assert page.locator("#ase-bulk-structure").evaluate(
                    "element => element.classList.contains('is-required')"
                )

                page.select_option("#ase-bulk-structure", "rocksalt")
                page.wait_for_function(
                    "document.getElementById('ase-bulk-preview-detail')?.textContent.includes('lattice parameter a')"
                )
                assert page.locator('[data-bulk-parameter="a"]').evaluate(
                    "element => element.classList.contains('is-required')"
                )
                page.fill("#ase-bulk-a", "4.27")
                page.wait_for_function(
                    "document.getElementById('ase-bulk-preview')?.dataset.state === 'valid'"
                )
                assert "8 atoms" in page.locator("#ase-bulk-preview-title").inner_text()

                page.click("#btn-ase-bulk-build")
                page.wait_for_selector("#modal-confirm-action")
                assert "Replace with this ASE crystal?" in page.locator(
                    "#modal-content"
                ).inner_text()
                page.click("#modal-confirm-action")
                page.wait_for_function(
                    "window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 8"
                )
                page.wait_for_function(
                    "window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 8"
                )
                symbols = page.evaluate(
                    "window.__ASE_APP__.state.atoms.chemical_symbols"
                )
                assert symbols.count("Cu") == 4
                assert symbols.count("O") == 4

                page.locator("#app-viewport canvas").focus()
                page.keyboard.press("Control+z")
                page.wait_for_function(
                    "window.__ASE_APP__?.state?.atoms?.metadata?.natoms === 4"
                )
                assert page.evaluate(
                    "window.__ASE_APP__.state.atoms.chemical_symbols"
                ) == ["Cu"] * 4

                capabilities = page.evaluate(
                    "async () => await window.v_aseAI.capabilities()"
                )
                assert capabilities["bulkBuilder"]["generator"] == "ase.build.bulk"
                assert capabilities["bulkBuilder"]["catalogUrl"].endswith(
                    f"/api/build/bulk/catalog/{editor.session_id}"
                )
                blocked = page.evaluate("""async () => {
                    try {
                        await window.v_aseAI.apply({operation: {
                            name: 'build-bulk',
                            formula: 'CuO',
                            crystalStructure: 'rocksalt',
                            cellMode: 'cubic',
                            a: 4.27
                        }});
                        return '';
                    } catch (error) {
                        return error.message;
                    }
                }""")
                assert "Obtain human approval" in blocked

                semantic = page.evaluate("""async () => await window.v_aseAI.apply({
                    operation: {
                        name: 'build-bulk',
                        formula: 'CuO',
                        crystalStructure: 'rocksalt',
                        cellMode: 'cubic',
                        a: 4.27,
                        confirmReplace: true
                    }
                })""")
                assert semantic["atomCount"] == 8
                assert semantic["frameCount"] == 1
                assert semantic["chemicalSymbols"].count("Cu") == 4
                assert semantic["chemicalSymbols"].count("O") == 4
            finally:
                browser.close()
    finally:
        editor.close()
