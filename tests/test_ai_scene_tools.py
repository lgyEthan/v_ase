"""Scene/MCP regressions authored for the deferred validation stage.

Do not infer that these tests have passed from their presence in this change.
"""
import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest

from v_ase.ai_tools import FunctionTools, ToolError
from v_ase.ai_schema import ai_schema_payload

URL = 'http://127.0.0.1:9/api/ai/command/session/test'


def test_cli_query_discovery_can_fetch_one_contract_without_the_whole_catalog():
    summary = ai_schema_payload({'scope':'summary'})
    assert 'properties' not in summary['queries']['scene-snapshot']
    query = ai_schema_payload({'query':'atom-scalar-catalog'})
    assert query['schema']['properties']['name'] == {'const':'atom-scalar-catalog'}
    assert query['schema']['additionalProperties'] is False
    assert 'queries' not in query


def test_mcp_image_inspection_emits_image_content_not_base64_text(tmp_path):
    import base64
    from io import BytesIO
    from PIL import Image
    mcp = pytest.importorskip('mcp')
    from v_ase.mcp_server import create_mcp_server

    buffer = BytesIO()
    Image.new('RGB', (16,16), '#89d9cc').save(buffer, format='PNG')
    data = buffer.getvalue()

    async def exercise():
        with FunctionTools(URL, artifact_dir=tmp_path) as adapter:
            artifact = adapter._save_artifact({'filename':'scene.png', 'mimeType':'image/png',
                'dataUrl':'data:image/png;base64,' + base64.b64encode(data).decode('ascii')})['artifact']
            async with mcp.Client(create_mcp_server(adapter)) as client:
                result = await client.call_tool('vase_inspect_image', {'uri':artifact['uri']})
                assert not result.is_error
                assert [item.type for item in result.content] == ['image']
                assert base64.b64decode(result.content[0].data) == data
                assert result.structured_content['artifact']['sha256'] == artifact['sha256']
    asyncio.run(exercise())


def test_discovery_is_bounded_and_exact_names_do_not_dump_schemas(tmp_path):
    with FunctionTools(URL, artifact_dir=tmp_path) as client:
        found = client.call('vase_search_tools', {'query': 'vase_apply_scene', 'limit': 1})
        assert found['tools'][0]['name'] == 'vase_apply_scene'
        assert 'inputSchema' not in found['tools'][0]
        assert len(client.call('vase_search_tools', {'query': 'render display'} )['tools']) <= 4
        with pytest.raises(ToolError):
            client.call('vase_search_tools', {'query': 'scene', 'limit': 9})
        definitions = client.deferred_function_tools(strict=False)
        native = [tool for group in definitions
                  for tool in (group['tools'] if group['type'] == 'namespace' else [group])]
        assert all(len(group['tools']) <= 8 for group in definitions if group['type'] == 'namespace')
        assert next(d for d in native if d['name'] == 'vase_style_scene')['defer_loading'] is False
        assert next(d for d in native if d['name'] == 'vase_apply_scene')['defer_loading'] is True
        assert next(d for d in native if d['name'] == 'vase_scatter_atoms')['defer_loading'] is True


def test_guides_are_bounded_and_the_no_bond_recipe_preserves_policies(tmp_path):
    with FunctionTools(URL, artifact_dir=tmp_path) as client:
        guide = client.call('vase_read_guide', {'topic': 'rendering', 'section': 'Minimal display edits', 'max_characters': 512})
        assert len(guide['text']) <= 512
        assert 'show_bonds=false' in guide['text']
        assert 'disableUnspecified' not in guide['text']
        with pytest.raises(ToolError):
            client.call('vase_read_guide', {'topic': 'rendering', 'expected_sha256': '0'*64})


def test_scene_patch_rejects_unknown_settings_and_scientific_mutations_before_http(tmp_path):
    guard = {'expected_document_id': 'test', 'expected_revision': 0}
    with FunctionTools(URL, artifact_dir=tmp_path) as client:
        for patch in [{'positions': [[0,0,0]]}, {'mode': 'edit'}, {'display': {'showBondss': False}}]:
            with pytest.raises(ToolError) as error:
                client.call('vase_apply_scene', {**guard, 'patch': patch})
            assert error.value.outcome == 'not_applied'
        with pytest.raises(ToolError):
            client.call('vase_style_scene', guard)


@contextmanager
def live_scene(tmp_path, *, volume=False):
    from ase import Atoms
    import numpy as np
    from playwright.sync_api import sync_playwright
    from v_ase.ai import ai_handshake
    from v_ase.viewer import view, find_free_port
    from v_ase.volumetric import VolumetricData

    atoms = Atoms('CuO', positions=[[2,3,4],[4,3,4]], cell=[8,8,8], pbc=True)
    fields = []
    if volume:
        grid = np.indices((12,12,12), dtype=float)
        values = np.exp(-sum((axis-5.5)**2 for axis in grid)/12).astype('float32')
        fields.append(VolumetricData(name='Scene test field', values=values, cell=np.diag([8.,8.,8.]), dataset_id='scene-test-field'))
    editor = view(atoms, block=False, open_browser=False, close_on_disconnect=False,
                  port=find_free_port(), volumetric_datasets=fields)
    handshake = ai_handshake(editor.url)
    try:
        with sync_playwright() as pw, FunctionTools(handshake['command_url'], artifact_dir=tmp_path) as client:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(editor.url)
            page.wait_for_function('window.v_aseAI')
            app_frame = next((frame for frame in page.frames if 'session_id=' in frame.url
                              and '/workspace' not in frame.url), page.main_frame)
            app_frame.wait_for_function('window.__V_ASE_APP__')
            def apply(name, **params):
                state = client.call('vase_describe', {'profile':'summary'})
                return client.call(name, {'expected_document_id':state['documentId'],
                    'expected_revision':state['collaboration']['revision'], **params})
            yield client, app_frame, apply
            browser.close()
    finally:
        editor.close()


def test_minimal_scene_style_preserves_science_pair_policies_camera_and_retry(tmp_path):
    with live_scene(tmp_path) as (client, page, apply):
        apply('vase_configure_bonds', pairs=[{'labels':['Cu','O'], 'maximum_angstrom':3.2}])
        before = client.call('vase_describe', {'profile':'full'})
        args = {'expected_document_id':before['documentId'], 'expected_revision':before['collaboration']['revision'],
                'request_id':'minimal-style', 'atom_display_mode':'2d', 'show_bonds':False}
        first = client.call('vase_style_scene', args)
        second = client.call('vase_style_scene', args)
        assert second['retry']['replayed']
        assert first['mutation']['revision'] == second['mutation']['revision']
        after = client.call('vase_describe', {'profile':'full'})
        for key in ['positions','chemicalSymbols','atomicNumbers','cell','pbc','constraints','camera']:
            assert after[key] == before[key]
        for key in ['pairwiseBondCutoffs','pairwiseBondRanges','pairwiseBondStyles']:
            assert after['display'][key] == before['display'][key]
        assert after['display']['atomDisplayMode'] == '2d'
        assert after['display']['showBonds'] is False
        with pytest.raises(ToolError) as error:
            client.call('vase_style_scene', {**args, 'show_bonds':True})
        assert error.value.code == 'idempotency_conflict'


def test_scene_map_merge_and_mid_application_rollback(tmp_path):
    with live_scene(tmp_path) as (client, page, apply):
        apply('vase_apply_scene', patch={'display': {'label_colors': {'Cu':'#aa0000','O':'#0000aa'}}})
        apply('vase_apply_scene', patch={'display': {'label_colors': {'Cu':'#00aa00'}}})
        before = client.call('vase_describe', {'profile':'full'})
        assert before['display']['labelColors']['O'] == '#0000aa'
        page.evaluate('''() => {
            const app=window.__V_ASE_APP__, original=app.aiApply;
            app.aiApply=async function(command){
                if(command.camera){this.aiApply=original;throw new Error('Injected scene failure');}
                return await original.call(this,command);
            };
        }''')
        with pytest.raises(ToolError) as error:
            apply('vase_apply_scene', patch={'display': {'label_colors': {'Cu':'#ffffff'}}, 'camera': {'axis':'+Z'}})
        assert error.value.outcome == 'rolled_back'
        after = client.call('vase_describe', {'profile':'full'})
        assert after['display'] == before['display']
        assert after['camera'] == before['camera']
        assert after['positions'] == before['positions']


def test_effective_bond_style_ignores_inactive_fallback(tmp_path):
    with live_scene(tmp_path) as (client, page, apply):
        apply('vase_configure_bonds', index_pairs=[[0,1]], pairs=[{'labels':['Cu','O'],
            'style':'flat','material':'unlit','color_mode':'custom','color':'#d7191c'}])
        apply('vase_set_display', display={'bond_style':'cylinder'})
        first = client.call('vase_scene_snapshot', {'sections':['bonds'], 'visible_only':False})
        apply('vase_set_display', display={'bond_style':'flat'})
        second = client.call('vase_scene_snapshot', {'sections':['bonds'], 'visible_only':False})
        assert first['bonds']['items'][0]['segments'] == second['bonds']['items'][0]['segments']
        assert second['bonds']['items'][0]['segments'][0]['style'] == 'flat'


def test_scene_and_render_use_the_same_stored_image_options(tmp_path):
    with live_scene(tmp_path) as (client, page, apply):
        page.evaluate('''() => {
            const app = window.__V_ASE_APP__;
            const profile = app.currentImageExportProfile();
            app.state.imageExportProfile = {...profile, width:480, height:360,
                options:{...profile.options, backgroundColor:'#123456',
                    transparentBackground:false, includeCell:false,
                    scaleMode:'physical',pixelsPerAngstrom:32}};
        }''')
        before = client.call('vase_scene_snapshot', {})
        apply('vase_style_scene', show_bonds=False)
        after = client.call('vase_scene_snapshot', {})
        rendered = client.call('vase_render', {})
        assert rendered['width'] == after['render']['width'] == 480
        assert rendered['height'] == after['render']['height'] == 360
        for key, value in before['render']['options'].items():
            if key == 'camera':
                for field, expected in value.items():
                    assert rendered['options']['camera'][field] == expected == after['render']['options']['camera'][field], field
            else:
                assert rendered['options'][key] == value == after['render']['options'][key], key
        assert rendered['effectiveRender']['outputCamera'] == after['render']['outputCamera']


def test_publication_plane_render_preserves_selection_and_interactive_mode_differs(tmp_path):
    with live_scene(tmp_path, volume=True) as (client, page, apply):
        apply('vase_add_volumetric_plane', dataset_id='scene-test-field', hkl=[0,0,1],
              offset_angstrom=4, resolution=128, colormap='coolwarm')
        selected = client.call('vase_scene_snapshot', {'sections':['planes']})
        ids = selected['interaction']['planeIds']
        assert ids
        a = client.call('vase_render', {'width':480,'height':360})
        assert client.call('vase_scene_snapshot', {})['interaction']['planeIds'] == ids
        interactive = client.call('vase_render', {'width':480,'height':360,
            'options': {'selection_appearance':'interactive'}})
        apply('vase_select_volumetric_planes', plane_ids=[])
        b = client.call('vase_render', {'width':480,'height':360})
        assert Path(a['artifact']['path']).read_bytes() == Path(b['artifact']['path']).read_bytes()
        assert Path(a['artifact']['path']).read_bytes() != Path(interactive['artifact']['path']).read_bytes()
        assert client.call('vase_inspect_image', {'uri':b['artifact']['uri']})['delivery'] == 'image'
