import asyncio
import base64
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
from v_ase.project import write_project_archive
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
        assert child_b.config["viz_only"] is False
        assert child_b.working_atoms.calc is not None
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


def test_workspace_finalize_releases_streaming_and_large_session_resources():
    class ClosingTrajectory:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    host, workspace = _workspace_host()
    source = ClosingTrajectory()
    host.trajectory_source = source
    host.history.append(host._history_state(include_trajectory=True))
    host.redo_stack.append(host._history_state())
    host.volumetric_datasets.append(object())
    host.original_volumetric_datasets.append(object())

    finalize_workspace(workspace.workspace_id)

    assert source.closed is True
    assert host.done_event.is_set()
    assert host.result_atoms is not None
    assert len(host.result_atoms) == 3
    assert host.trajectory_source is None
    assert host.trajectory_frames == []
    assert host.original_frames == []
    assert host.history == []
    assert host.redo_stack == []
    assert host.volumetric_datasets == []
    assert host.original_volumetric_datasets == []
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
            page.locator(".document-tab").nth(0).locator(".document-select").click()
            page.wait_for_function(
                """sessionId => {
                    const frame = document.querySelector(
                        `iframe[data-session-id="${sessionId}"]`
                    );
                    return frame && !frame.hidden;
                }""",
                arg=host.session_id,
            )
            first_frame.locator("#structure-file").set_input_files(str(imported_file))
            first_frame.locator('input[name="open-file-mode"][value="new-tab"]').check()
            assert first_frame.locator("#open-file-confirm").inner_text() == "Open New Tab"
            first_frame.locator("#open-file-confirm").click()
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


def test_regular_workspace_new_project_tab_keeps_browser_handle_and_format(tmp_path):
    sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
    atoms = Atoms('H', positions=[[0, 0, 0]])
    source = tmp_path / 'new-project.vase'
    seed = EditorSession('regular-project-seed', atoms.copy(), atoms.copy(), config={'viz_only': True})
    write_project_archive(source, seed, {'display': {'showGrid': False}})
    encoded = base64.b64encode(source.read_bytes()).decode('ascii')
    editor = view(atoms, notebook=True, block=False, port=find_free_port(), close_on_disconnect=False)
    host = sessions[editor.session_id]
    workspace = create_workspace(host)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.on('dialog', lambda dialog: dialog.dismiss())
            page.set_default_timeout(10000)
            page.goto(f'http://127.0.0.1:{editor.port}/workspace'
                      f'?workspace_id={workspace.workspace_id}&session_id={host.session_id}')
            page.wait_for_function('''() => document.querySelector('iframe')
                ?.contentWindow?.__ASE_APP__?.collaborationReady''')
            opened = page.evaluate('''async encoded => {
                const bytes=Uint8Array.from(atob(encoded),char=>char.charCodeAt(0));
                const host= document.querySelector('iframe').contentWindow;
                const root=await host.navigator.storage.getDirectory();
                const handle=await root.getFileHandle('new-project.vase',{create:true});
                const writer=await handle.createWritable();
                await writer.write(bytes);
                await writer.close();
                window.__newProjectHandle=handle;
                await host.__ASE_APP__
                    .openStructureFileInNewTab(await handle.getFile(),'',':','view',{handle});
                return {tabs:window.__V_ASE_WORKSPACE__.tabs.size,
                    active:window.__V_ASE_WORKSPACE__.activeSessionId,
                    hostToast:host.document.getElementById('toast-container')?.innerText,
                    error:document.getElementById('workspace-error-message')?.innerText};
            }''', encoded)
            assert opened['tabs'] == 2, opened
            page.wait_for_function('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                return workspace?.tabs?.size===2
                    && workspace.tabs.get(workspace.activeSessionId)?.pane?.contentWindow
                        ?.__ASE_APP__?.projectFile?.format==='vase';
            }''')
            assert page.evaluate('''async () => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const app=workspace.tabs.get(workspace.activeSessionId).pane.contentWindow.__ASE_APP__;
                return await app.projectFile.handle?.isSameEntry(window.__newProjectHandle);
            }''') is True
            assert page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const entry=workspace.tabs.get(workspace.activeSessionId);
                const child=entry.pane.contentWindow.__ASE_APP__;
                entry.dirty=false;
                child.pendingApplyInFlight=true;
                const event=new Event('beforeunload',{cancelable:true});
                window.dispatchEvent(event);
                child.pendingApplyInFlight=false;
                return event.defaultPrevented;
            }''') is True
            page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const pane=workspace.tabs.get(workspace.activeSessionId).pane;
                window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                pane.contentWindow.location.reload();
            }''')
            page.wait_for_function('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const child=workspace.tabs.get(workspace.activeSessionId)?.pane
                    ?.contentWindow?.__ASE_APP__;
                return child && child!==window.__oldProjectChild
                    && child.collaborationReady && child.projectFile.format==='vase';
            }''')
            assert page.evaluate('''async () => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const app=workspace.tabs.get(workspace.activeSessionId).pane.contentWindow.__ASE_APP__;
                return await app.projectFile.handle?.isSameEntry(window.__newProjectHandle);
            }''') is True
            page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                workspace.tabs.get(workspace.activeSessionId).pane.contentWindow.__ASE_APP__
                    .openEditorRoute('appearance');
            }''')
            active_frame = page.frame_locator('iframe.document-pane:not([hidden])')
            active_frame.locator('#atom-radius-scale-number').fill('0.85')
            active_frame.locator('#atom-radius-scale-number').press('Tab')
            page.wait_for_function('''() => window.__V_ASE_WORKSPACE__.tabs
                .get(window.__V_ASE_WORKSPACE__.activeSessionId).dirty''')
            for value in ('0.90', '0.95'):
                active_frame.locator('#atom-radius-scale-number').fill(value)
                active_frame.locator('#atom-radius-scale-number').press('Tab')
            page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const pane=workspace.tabs.get(workspace.activeSessionId).pane;
                window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                pane.contentWindow.location.reload();
            }''')
            page.wait_for_function('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const entry=workspace.tabs.get(workspace.activeSessionId);
                const child=entry?.pane?.contentWindow?.__ASE_APP__;
                return child && child!==window.__oldProjectChild
                    && entry.appInstance===child && child.projectFile.format==='vase';
            }''')
            page.wait_for_timeout(350)  # A late activation must not reset restored saved state.
            assert page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const entry=workspace.tabs.get(workspace.activeSessionId);
                const child=entry.pane.contentWindow.__ASE_APP__;
                return entry.dirty && child.projectFile.dirty
                    && child.state.display.atomRadiusScale===0.95;
            }''') is True
            assert page.evaluate('''async () => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const pane=workspace.tabs.get(workspace.activeSessionId).pane;
                const child=pane.contentWindow.__ASE_APP__;
                const root=await pane.contentWindow.navigator.storage.getDirectory();
                const handle=await root.getFileHandle('new-project-copy.vase',{create:true});
                window.__savedAsHandle=handle;
                child.filePickerAdapter={showSaveFilePicker:async()=>handle};
                return await child.saveCompactProject({saveAs:true});
            }''') is True
            page.wait_for_function('''() => window.__V_ASE_WORKSPACE__.tabs
                .get(window.__V_ASE_WORKSPACE__.activeSessionId)
                ?.provenance?.filename==='new-project-copy.vase' ''')
            page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const pane=workspace.tabs.get(workspace.activeSessionId).pane;
                window.__oldProjectChild=pane.contentWindow.__ASE_APP__;
                pane.contentWindow.location.reload();
            }''')
            page.wait_for_function('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const entry=workspace.tabs.get(workspace.activeSessionId);
                const child=entry?.pane?.contentWindow?.__ASE_APP__;
                return child && child!==window.__oldProjectChild
                    && entry.appInstance===child
                    && child.projectFile.filename==='new-project-copy.vase';
            }''')
            assert page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const app=workspace.tabs.get(workspace.activeSessionId).pane.contentWindow.__ASE_APP__;
                return app.state.display.atomRadiusScale===0.95
                    && app.projectFile.dirty===false
                    && app.projectFile.handle?.name==='new-project-copy.vase';
            }''') is True
            browser.close()
    finally:
        finalize_workspace(workspace.workspace_id)
        editor.close()


def test_regular_workspace_mac_parent_shortcut_targets_active_child_once():
    sync_playwright = pytest.importorskip('playwright.sync_api').sync_playwright
    editor = view(Atoms('H'), notebook=True, block=False, port=find_free_port(),
                  close_on_disconnect=False)
    host = sessions[editor.session_id]
    workspace = create_workspace(host)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.add_init_script("""Object.defineProperty(navigator, 'userAgentData', {
                configurable:true, value:{platform:'macOS'}});
                Object.defineProperty(navigator, 'platform', {
                    configurable:true, value:'MacIntel'});""")
            page.goto(f'http://127.0.0.1:{editor.port}/workspace'
                      f'?workspace_id={workspace.workspace_id}&session_id={host.session_id}')
            assert page.locator('#new-document').get_attribute('aria-keyshortcuts') == 'Meta+N'
            page.wait_for_function('''() => document.querySelector('iframe')
                ?.contentWindow?.__ASE_APP__?.collaborationReady''')
            page.click('#new-document')
            page.wait_for_function('''() => document.querySelectorAll('.document-tab').length===2
                && document.querySelector('.document-pane:not([hidden])')
                    ?.contentWindow?.__ASE_APP__?.collaborationReady''')
            page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                const child=workspace.tabs.get(workspace.activeSessionId).pane.contentWindow.__ASE_APP__;
                window.__saveTargets=[];
                child.saveDocument=async()=>window.__saveTargets.push('child');
                document.querySelector('iframe').contentWindow.__ASE_APP__.saveDocument=
                    async()=>window.__saveTargets.push('host');
            }''')
            page.locator('.document-tab.active .document-select').click()
            before_camera = page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                return workspace.tabs.get(workspace.activeSessionId).pane.contentWindow
                    .__ASE_APP__.cameraSettingsSnapshot().position;
            }''')
            page.keyboard.press('ArrowUp')
            after_camera = page.evaluate('''() => {
                const workspace=window.__V_ASE_WORKSPACE__;
                return workspace.tabs.get(workspace.activeSessionId).pane.contentWindow
                    .__ASE_APP__.cameraSettingsSnapshot().position;
            }''')
            assert after_camera != pytest.approx(before_camera, abs=1e-8)
            page.keyboard.press('Meta+s')
            assert page.evaluate('window.__saveTargets') == ['child']
            page.keyboard.press('Control+s')
            assert page.evaluate('window.__saveTargets') == ['child']
            page.keyboard.press('Meta+n')
            page.wait_for_function("document.querySelectorAll('.document-tab').length===3")
            page.wait_for_function('''() => document.querySelector('.document-pane:not([hidden])')
                ?.contentWindow?.__ASE_APP__?.workspaceRecoveryAcknowledged''')
            page.locator('.document-tab.active .document-select').click()
            page.keyboard.press('Meta+w')
            page.wait_for_function("document.querySelectorAll('.document-tab').length===2")
            assert page.is_closed() is False
            browser.close()
    finally:
        finalize_workspace(workspace.workspace_id)
        editor.close()


def test_last_workspace_tab_cancel_then_discard_keeps_workspace_alive():
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    playwright_error = pytest.importorskip("playwright._impl._errors").Error
    editor = view(Atoms("H", positions=[[0, 0, 0]]), notebook=True,
                  block=False, port=find_free_port(), viz_only=False,
                  close_on_disconnect=False)
    host = sessions[editor.session_id]
    workspace = create_workspace(host)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except playwright_error as error:
                pytest.skip(f"Playwright Chromium unavailable: {error}")
            page = browser.new_page()
            page.goto(
                f"http://127.0.0.1:{editor.port}/workspace"
                f"?workspace_id={workspace.workspace_id}&session_id={host.session_id}"
            )
            page.wait_for_function("document.querySelectorAll('.document-tab').length === 1")
            frame = page.frame_locator(f'iframe[data-session-id="{host.session_id}"]')
            frame.locator('#app-viewport').wait_for()
            page.wait_for_function("""id => {
                const app = document.querySelector(`iframe[data-session-id="${id}"]`)
                    ?.contentWindow?.__ASE_APP__;
                return app?.visualHistoryReady === true;
            }""", arg=host.session_id)
            page.evaluate("""id => {
                const app = document.querySelector(`iframe[data-session-id="${id}"]`)
                    .contentWindow.__ASE_APP__;
                app.state.display.atomRadiusScale = 0.85;
                app.scheduleVisualHistoryCommit('test-dirty');
                app.flushVisualHistoryCommit();
            }""", host.session_id)
            page.wait_for_function("document.querySelector('.document-tab')?.classList.contains('dirty')")
            page.locator('.document-tab .document-close').click()
            frame.locator('#modal-keep-editing').click()
            assert page.locator('.document-tab').count() == 1
            assert host.session_id in sessions
            page.evaluate("""id => {
                const app = document.querySelector(`iframe[data-session-id="${id}"]`)
                    .contentWindow.__ASE_APP__;
                app.chooseSaveDestination = async () => null;
            }""", host.session_id)
            page.locator('.document-tab .document-close').click()
            frame.locator('#modal-save-document').click()
            page.wait_for_function("document.querySelector('.document-tab .document-close')?.disabled === false")
            assert page.locator('.document-tab').count() == 1
            page.locator('.document-tab .document-close').click()
            frame.locator('#modal-discard-document').click()
            page.wait_for_function("""id => {
                const tab = document.querySelector('.document-tab');
                return document.querySelectorAll('.document-tab').length === 1
                    && tab?.dataset.sessionId !== id;
            }""", arg=host.session_id)
            assert host.session_id in sessions
            assert workspace.workspace_id in workspaces
            browser.close()
    finally:
        finalize_workspace(workspace.workspace_id)
        editor.close()


def test_detach_moves_live_document_and_old_window_cannot_destroy_it():
    from v_ase.session import move_workspace_session, create_workspace_session
    host, original = _workspace_host()
    host.push_history()
    host.working_atoms.positions[0, 0] += 1
    host.project_file_binding = {'id': 'opaque', 'format': 'html', 'filename': 'sample.html'}
    history = host.history
    frames = host.trajectory_frames
    target = move_workspace_session(original, host.session_id)
    try:
        assert original.host_session_id != host.session_id
        assert len(original.session_ids) == 1
        assert target.session_ids == [host.session_id]
        assert target.host_session is host
        assert host.history is history and host.trajectory_frames is frames
        assert host.project_file_binding['format'] == 'html'
        assert host.config['workspace_id'] == target.workspace_id
        finalize_workspace(original.workspace_id)
        assert sessions[host.session_id] is host
        assert not host.done_event.is_set()
        assert len(host.working_atoms) == 3
        # Transfer back into another existing window is the failure rollback path.
        fresh_host = create_workspace_session(target)
        fresh = create_workspace(fresh_host)
        target.session_ids.remove(fresh_host.session_id)
        move_workspace_session(target, host.session_id, fresh)
        assert host.config['workspace_id'] == fresh.workspace_id
        assert host.session_id in fresh.session_ids
        assert host.session_id not in target.session_ids
        finalize_workspace(target.workspace_id)
        assert sessions[host.session_id] is host
        finalize_workspace(fresh.workspace_id)
    finally:
        for ws in (original, target):
            finalize_workspace(ws.workspace_id)


def test_native_window_close_releases_only_its_documents_without_stopping_host():
    from v_ase.server import close_workspace_window
    from v_ase.session import move_workspace_session
    host, original = _workspace_host()
    target = move_workspace_session(original, host.session_id)
    try:
        asyncio.run(close_workspace_window(target.workspace_id))
        assert target.workspace_id not in workspaces
        assert host.session_id not in sessions
        assert not host.done_event.is_set()  # The desktop owns process lifetime.
        assert original.workspace_id in workspaces
        assert original.host_session_id in sessions
        child = asyncio.run(create_workspace_document(original.workspace_id))
        assert child['session_id'] in sessions
    finally:
        finalize_workspace(original.workspace_id)
