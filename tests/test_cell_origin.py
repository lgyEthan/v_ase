"""Nonzero simulation-box origins stay consistent across data and rendering."""
import numpy as np
import pytest
from ase import Atoms

from v_ase.export import _cad_scene_data
from v_ase.serialization import atoms_to_json
from v_ase.session import EditorSession


def source_atoms():
    return Atoms("CuO", positions=[[10.5, 2.5, 1.5], [11.5, 3.5, 2.5]],
                 cell=[3, 4, 5], pbc=True, celldisp=[10, 2, 1])


def test_json_and_cad_cell_edges_preserve_source_origin():
    atoms = source_atoms()
    assert atoms_to_json(atoms)["cell_origin"] == [10, 2, 1]
    session = EditorSession("cell-origin-cad", atoms.copy(), atoms.copy())
    scene = _cad_scene_data(session, {})
    endpoints = np.array([edge[key] for edge in scene["cell_edges"] for key in ("start", "end")])
    np.testing.assert_allclose(endpoints.min(axis=0), [10, 2, 1])
    np.testing.assert_allclose(endpoints.max(axis=0), [13, 6, 6])


@pytest.mark.parametrize("moving", [False, True])
def test_project_roundtrip_preserves_cell_origins_beyond_ase_trajectory(tmp_path, moving):
    from v_ase.project import write_project_archive, read_project_archive
    first = source_atoms()
    second = first.copy()
    if moving:
        second.set_celldisp([11, 2, 1])
    session = EditorSession("origin-project", first.copy(), first.copy(),
                            trajectory_frames=[first, second])
    path = write_project_archive(tmp_path / "origin.vase", session, {})
    restored = read_project_archive(path)
    for actual, expected in zip(restored.frames, [first, second]):
        np.testing.assert_allclose(actual.get_celldisp(), expected.get_celldisp())
        np.testing.assert_array_equal(actual.positions, expected.positions)


def test_live_cell_origin_matches_semantic_state_after_a_frame_change(tmp_path):
    from playwright.sync_api import sync_playwright
    from v_ase.ai import ai_handshake
    from v_ase.ai_tools import FunctionTools
    from v_ase.viewer import view, find_free_port

    first = source_atoms()
    second = first.copy()
    second.positions[:, 0] += .25
    second.set_celldisp([10.25, 2, 1])
    editor = view([first, second], open_browser=False, block=False, close_on_disconnect=False,
                  port=find_free_port(), viz_only=True)
    try:
        with sync_playwright() as pw, FunctionTools(ai_handshake(editor.url)["command_url"], artifact_dir=tmp_path) as client:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1100, "height": 760})
            page.goto(editor.url)
            page.wait_for_function("window.v_aseAI")
            app = next((frame for frame in page.frames if "session_id=" in frame.url
                        and "/workspace" not in frame.url), page.main_frame)
            app.wait_for_function("window.__V_ASE_APP__?.renderer?.cellGroup?.children.length")
            for index, origin in [(0, [10, 2, 1]), (1, [10.25, 2, 1])]:
                app.evaluate("index => window.__V_ASE_APP__.loadFrame(index)", index)
                state = client.call("vase_describe", {"profile": "structure"})
                np.testing.assert_allclose(state["cellOrigin"], origin)
                endpoints = app.evaluate("""() => window.__V_ASE_APP__.renderer.cellGroup.children
                    .flatMap(mesh => mesh.userData.cellEdgeSegments || [])
                    .flatMap(pair => pair.map(point => point.toArray()))""")
                np.testing.assert_allclose(np.min(endpoints, axis=0), origin)
                np.testing.assert_allclose(np.max(endpoints, axis=0), np.array(origin) + [3, 4, 5])
            page.screenshot(path=str(tmp_path / "cell-origin.png"))
            browser.close()
    finally:
        editor.close()
