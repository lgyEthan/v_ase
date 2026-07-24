import asyncio

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule

from v_ase.server import (
    close_workspace_document,
    create_workspace_document,
    workspace_state,
)
from v_ase.session import (
    EditorSession,
    create_workspace,
    finalize_workspace,
    sessions,
    workspaces,
)
from v_ase.viewer import find_free_port, view


def _workspace_host(name: str = "water.xyz"):
    atoms = molecule("H2O")
    atoms.set_cell([8.0, 8.0, 8.0])
    atoms.set_pbc(True)
    session = EditorSession(
        "workspace-host",
        atoms.copy(),
        atoms.copy(),
        original_frames=[atoms.copy()],
        trajectory_frames=[atoms.copy()],
        config={
            "viz_only": True,
            "show_cell": True,
            "show_axes": True,
            "document_name": name,
        },
    )
    sessions[session.session_id] = session
    return session, create_workspace(session)


def test_workspace_documents_have_independent_structure_and_configuration():
    host, workspace = _workspace_host()
    try:
        first_child = asyncio.run(
            create_workspace_document(workspace.workspace_id, {"source_session_id": host.session_id})
        )
        second_child = asyncio.run(
            create_workspace_document(workspace.workspace_id, {"source_session_id": host.session_id})
        )
        child_a = sessions[first_child["session_id"]]
        child_b = sessions[second_child["session_id"]]

        child_a.working_atoms = Atoms("He", positions=[[1.0, 2.0, 3.0]])
        child_a.config["document_name"] = "helium.xyz"
        child_a.config["initial_design_settings"] = {"display": {"atomRadiusScale": 1.7}}

        assert len(host.working_atoms) == 3
        assert len(child_b.working_atoms) == 0
        assert child_b.config["document_name"] == "Untitled"
        assert child_b.config["initial_design_settings"] is None
        assert child_a.working_atoms is not host.working_atoms
        assert child_a.config is not host.config
        assert not np.shares_memory(
            child_a.working_atoms.positions,
            host.working_atoms.positions,
        )

        state = asyncio.run(workspace_state(workspace.workspace_id))
        assert [document["session_id"] for document in state["documents"]] == [
            host.session_id,
            child_a.session_id,
            child_b.session_id,
        ]
        assert [document["title"] for document in state["documents"]] == [
            "water.xyz",
            "helium.xyz",
            "Untitled",
        ]

        asyncio.run(close_workspace_document(workspace.workspace_id, child_a.session_id))
        assert child_a.session_id not in sessions
        assert host.session_id in sessions
        assert child_b.session_id in sessions
    finally:
        finalize_workspace(workspace.workspace_id)
        sessions.pop(host.session_id, None)


def test_workspace_finalize_releases_children_and_unblocks_host():
    host, workspace = _workspace_host()
    child_payload = asyncio.run(create_workspace_document(workspace.workspace_id, {}))
    child_id = child_payload["session_id"]

    finalize_workspace(workspace.workspace_id)

    assert workspace.workspace_id not in workspaces
    assert child_id not in sessions
    assert host.done_event.is_set()
    assert host.session_id in sessions
    sessions.pop(host.session_id, None)


def test_workspace_browser_tabs_suspend_inactive_renderers_and_keep_settings_separate():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    playwright_error = pytest.importorskip("playwright._impl._errors").Error

    port = find_free_port()
    editor = view(
        molecule("H2O"),
        notebook=True,
        block=False,
        port=port,
        viz_only=True,
        close_on_disconnect=False,
        document_name="water.xyz",
    )
    host = sessions[editor.session_id]
    workspace = create_workspace(host)

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except playwright_error as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(
                f"http://127.0.0.1:{port}/workspace"
                f"?workspace_id={workspace.workspace_id}&session_id={host.session_id}"
            )
            page.wait_for_function(
                "document.querySelectorAll('.document-tab').length === 1"
            )
            first_frame = page.frame_locator(
                f'iframe[data-session-id="{host.session_id}"]'
            )
            first_frame.locator("#app-viewport").wait_for()
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    return frame?.contentWindow?.__ASE_APP__?.state?.atoms?.metadata?.natoms === 3;
                }""",
                arg=host.session_id,
            )

            page.click("#new-document")
            page.wait_for_function(
                "document.querySelectorAll('.document-tab').length === 2"
            )
            child_id = page.locator(".document-tab").nth(1).get_attribute("data-session-id")
            assert child_id
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    return frame?.contentWindow?.__ASE_APP__?.state?.atoms?.metadata?.natoms === 0;
                }""",
                arg=child_id,
            )

            status = page.evaluate(
                """([hostId, childId]) => {
                    const app = id => document.querySelector(
                        `iframe[data-session-id="${id}"]`
                    ).contentWindow.__ASE_APP__;
                    app(childId).state.display.atomRadiusScale = 1.8;
                    return {
                        hostSuspended: app(hostId).renderer.suspended,
                        childSuspended: app(childId).renderer.suspended,
                        hostScale: app(hostId).state.display.atomRadiusScale,
                        childScale: app(childId).state.display.atomRadiusScale,
                        hostProject: app(hostId).projectFilename(),
                        childProject: app(childId).projectFilename(),
                    };
                }""",
                [host.session_id, child_id],
            )
            assert status == {
                "hostSuspended": True,
                "childSuspended": False,
                "hostScale": 1,
                "childScale": 1.8,
                "hostProject": "water.vase",
                "childProject": "Untitled.vase",
            }

            page.locator(".document-tab").nth(0).locator(".document-select").click()
            page.wait_for_function(
                """([hostId, childId]) => {
                    const frame = id => document.querySelector(
                        `iframe[data-session-id="${id}"]`
                    ).contentWindow.__ASE_APP__;
                    return !frame(hostId).renderer.suspended && frame(childId).renderer.suspended;
                }""",
                arg=[host.session_id, child_id],
            )
            browser.close()
            assert host.done_event.wait(timeout=4.0)
            assert workspace.workspace_id not in workspaces
    finally:
        finalize_workspace(workspace.workspace_id)
        editor.close()
