import asyncio
import time

import numpy as np
import pytest
from ase import Atoms
from ase.build import molecule
from ase.io import write

from v_ase.io import set_atom_labels
from v_ase.server import (
    cancel_workspace_autoclose,
    close_workspace_document,
    create_workspace_document,
    schedule_workspace_autoclose,
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
from v_ase.websocket_manager import ws_manager


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
            "launch_directory": "/tmp/v_ase-workspace-launch",
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
        assert child_b.config["launch_directory"] == "/tmp/v_ase-workspace-launch"
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


def test_workspace_browser_close_ignores_its_stale_socket():
    host, workspace = _workspace_host()
    stale_socket = object()
    ws_manager.active_connections[stale_socket] = (
        f"workspace:{workspace.workspace_id}:closing-client"
    )
    try:
        schedule_workspace_autoclose(
            workspace.workspace_id,
            delay=0.01,
            closing_client_id="closing-client",
        )

        assert host.done_event.wait(timeout=1.0)
        assert workspace.workspace_id not in workspaces
    finally:
        ws_manager.active_connections.pop(stale_socket, None)
        finalize_workspace(workspace.workspace_id)
        sessions.pop(host.session_id, None)


def test_workspace_browser_close_keeps_another_browser_connected():
    host, workspace = _workspace_host()
    closing_socket = object()
    active_socket = object()
    ws_manager.active_connections[closing_socket] = (
        f"workspace:{workspace.workspace_id}:closing-client"
    )
    ws_manager.active_connections[active_socket] = (
        f"workspace:{workspace.workspace_id}:active-client"
    )
    try:
        schedule_workspace_autoclose(
            workspace.workspace_id,
            delay=0.01,
            closing_client_id="closing-client",
        )
        time.sleep(0.08)

        assert not host.done_event.is_set()
        assert workspace.workspace_id in workspaces
    finally:
        cancel_workspace_autoclose(workspace.workspace_id)
        ws_manager.active_connections.pop(closing_socket, None)
        ws_manager.active_connections.pop(active_socket, None)
        finalize_workspace(workspace.workspace_id)
        sessions.pop(host.session_id, None)


def test_workspace_browser_close_respects_disabled_autoclose():
    host, workspace = _workspace_host()
    host.config["workspace_auto_close_on_disconnect"] = False
    try:
        schedule_workspace_autoclose(
            workspace.workspace_id,
            delay=0.01,
            closing_client_id="closing-client",
        )
        time.sleep(0.08)

        assert not host.done_event.is_set()
        assert workspace.workspace_id in workspaces
    finally:
        cancel_workspace_autoclose(workspace.workspace_id)
        finalize_workspace(workspace.workspace_id)
        sessions.pop(host.session_id, None)


def test_workspace_browser_tabs_suspend_inactive_renderers_and_keep_settings_separate(tmp_path):
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
    imported = Atoms(
        "CO",
        positions=[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
        cell=[9.0, 9.0, 9.0],
        pbc=True,
    )
    set_atom_labels(imported, ["C_bulk", "O_ads"])
    imported_file = tmp_path / "independent.extxyz"
    write(imported_file, imported, format="extxyz")

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
            tab_layout = page.evaluate("""() => {
                const tabs = [...document.querySelectorAll('.document-tab')];
                const add = document.getElementById('new-document');
                const last = tabs[tabs.length - 1].getBoundingClientRect();
                const plus = add.getBoundingClientRect();
                return {
                    parent: add.parentElement.id,
                    followsLastTab: tabs[tabs.length - 1].nextElementSibling === add,
                    gap: plus.left - last.right,
                    widths: tabs.map(tab => tab.getBoundingClientRect().width)
                };
            }""")
            assert tab_layout["parent"] == "document-tabs"
            assert tab_layout["followsLastTab"] is True
            assert 0 <= tab_layout["gap"] <= 12
            assert all(96 <= width <= 232 for width in tab_layout["widths"])

            child_frame = page.frame_locator(
                f'iframe[data-session-id="{child_id}"]'
            )
            child_frame.locator("#structure-file").set_input_files(str(imported_file))
            child_frame.locator('input[name="open-file-mode"][value="new-tab"]').check()
            assert child_frame.locator("#open-file-confirm").inner_text() == "Open New Tab"
            child_frame.locator("#open-file-confirm").click()
            page.wait_for_function(
                "document.querySelectorAll('.document-tab').length === 3"
            )
            imported_id = page.locator(".document-tab").nth(2).get_attribute("data-session-id")
            assert imported_id
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    const app = frame?.contentWindow?.__ASE_APP__;
                    return app?.state?.atoms?.symbols?.join(',') === 'C_bulk,O_ads';
                }""",
                arg=imported_id,
            )
            assert page.locator(".document-tab").nth(2).locator(".document-title").inner_text() == imported_file.name
            assert sessions[child_id].config["empty_workspace"] is True
            assert len(sessions[child_id].working_atoms) == 0
            assert sessions[imported_id].config["document_name"] == imported_file.name

            status = page.evaluate(
                """([hostId, childId, importedId]) => {
                    const app = id => document.querySelector(
                        `iframe[data-session-id="${id}"]`
                    ).contentWindow.__ASE_APP__;
                    app(childId).state.display.atomRadiusScale = 1.8;
                    return {
                        hostSuspended: app(hostId).renderer.suspended,
                        childSuspended: app(childId).renderer.suspended,
                        importedSuspended: app(importedId).renderer.suspended,
                        hostScale: app(hostId).state.display.atomRadiusScale,
                        childScale: app(childId).state.display.atomRadiusScale,
                        hostProject: app(hostId).projectFilename(),
                        childProject: app(childId).projectFilename(),
                    };
                }""",
                [host.session_id, child_id, imported_id],
            )
            assert status == {
                "hostSuspended": True,
                "childSuspended": True,
                "importedSuspended": False,
                "hostScale": 0.6,
                "childScale": 1.8,
                "hostProject": "water.vase",
                "childProject": "Untitled.vase",
            }

            page.locator(".document-tab").nth(0).locator(".document-select").click()
            page.wait_for_function(
                """([hostId, childId, importedId]) => {
                    const frame = id => document.querySelector(
                        `iframe[data-session-id="${id}"]`
                    ).contentWindow.__ASE_APP__;
                    return !frame(hostId).renderer.suspended
                        && frame(childId).renderer.suspended
                        && frame(importedId).renderer.suspended;
                }""",
                arg=[host.session_id, child_id, imported_id],
            )
            page.close()
            assert host.done_event.wait(timeout=4.0)
            assert workspace.workspace_id not in workspaces
            browser.close()
    finally:
        finalize_workspace(workspace.workspace_id)
        editor.close()
