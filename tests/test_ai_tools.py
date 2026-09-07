"""Typed adapter validation, parity, artifact safety, and real MCP transports."""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import threading

import pytest
from jsonschema import Draft202012Validator

from v_ase.ai_schema import AI_OPERATION_PARAMETERS, AI_CONTROL_SCHEMA, AI_EXPORT_PARAMETERS, AI_QUERY_SCHEMAS, _ai_operation_schema
from v_ase.ai_tools import FunctionTools, ToolError, tool_catalog, _flatten, INTERRUPT_OPERATIONS

URL = 'http://127.0.0.1:9/api/ai/command/session/test'


def test_catalog_covers_every_operation_control_and_export_with_typed_parameters():
    catalog = tool_catalog()
    for name, contract in AI_OPERATION_PARAMETERS.items():
        spec = catalog['vase_' + name.replace('-', '_')]
        properties = _flatten(_ai_operation_schema(name))['properties']
        assert set(contract['optional']) <= properties.keys(), name
        assert 'expected_document_id' in spec.input_schema['required']
        if name not in INTERRUPT_OPERATIONS:
            assert 'expected_revision' in spec.input_schema['required']
        assert spec.operation == name
    assert {s.export_format for s in catalog.values() if s.export_format} == set(AI_EXPORT_PARAMETERS)
    assert {s.field for s in catalog.values() if s.field} == set(AI_CONTROL_SCHEMA['properties']) - {'operation', 'expectedRevision', 'expectedDocumentId', 'responseProfile', 'requestId'}
    for spec in catalog.values():
        Draft202012Validator.check_schema(spec.input_schema)


@pytest.mark.parametrize('url', [
    'https://example.com/api/ai/command/session/test',
    'http://127.0.0.1:9/private', 'http://user:pass@localhost/api/ai/command/session/x',
    URL+'?redirect=elsewhere', URL+'#x',
])
def test_client_rejects_nonlocal_or_ambiguous_targets(url):
    with pytest.raises(ValueError):
        FunctionTools(url)


def test_invalid_arguments_fail_before_http_and_nested_keys_are_typed(tmp_path):
    with FunctionTools(URL, artifact_dir=tmp_path) as client:
        for args in ({}, {'position': [0,0,0], 'element':'H'},
                     {'position': [float('nan'),0,0], 'element':'H', 'expected_revision':0, 'expected_document_id':'test'}):
            with pytest.raises(ToolError) as exc:
                client.call('vase_add_atom', args)
            assert exc.value.outcome == 'not_applied'
        with pytest.raises(ToolError):
            client.call('vase_configure_bonds', {'expected_revision':0, 'expected_document_id':'test', 'index_pairs': [[0, '1']]})


def test_artifacts_are_unique_bounded_to_produced_resources_and_not_inline(tmp_path):
    with FunctionTools(URL, artifact_dir=tmp_path) as client:
        source={'filename':'../../sample.png','mimeType':'image/png','dataUrl':'data:image/png;base64,'+base64.b64encode(b'content').decode()}
        a,b=client._save_artifact(source),client._save_artifact(source)
        assert 'dataUrl' not in a
        assert a['artifact']['uri'] != b['artifact']['uri']
        assert Path(a['artifact']['path']).parent == tmp_path
        assert client.read_artifact(a['artifact']['uri'])[1] == b'content'
        with pytest.raises(ToolError): client.read_artifact(Path(__file__).as_uri())
        Path(a['artifact']['path']).write_bytes(b'changed')
        with pytest.raises(ToolError): client.read_artifact(a['artifact']['uri'])


@pytest.mark.parametrize('transport', ['memory', 'legacy', 'stdio', 'http'])
def test_mcp_controls_same_gui_and_preserves_revision_guards(tmp_path, transport):
    mcp=pytest.importorskip('mcp')
    from ase import Atoms
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import numpy as np
    import uvicorn
    from v_ase.viewer import view, find_free_port
    from v_ase.ai import ai_handshake
    from v_ase.mcp_server import create_mcp_server

    editor=view(Atoms('Cu2',positions=[[0,0,0],[2,0,0]],cell=[8,8,8],pbc=True), block=False, open_browser=False, close_on_disconnect=False, port=find_free_port())
    handshake=ai_handshake(editor.url)
    adapter=FunctionTools(handshake['command_url'], artifact_dir=tmp_path)
    server=create_mcp_server(adapter, discovery='all')
    http_server=None
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page()
            page.goto(handshake['human_url'])
            page.wait_for_function('window.v_aseAI')
            if transport in {'memory','legacy'}: target=server
            elif transport=='stdio':
                from mcp import StdioServerParameters
                target=StdioServerParameters(command=sys.executable, args=['-m','v_ase.cli','mcp','--connect',handshake['command_url'],'--discovery','all','--artifact-dir',str(tmp_path)],env={'PYTHONPATH':os.environ.get('PYTHONPATH','')})
            else:
                port=find_free_port()
                http_server=uvicorn.Server(uvicorn.Config(server.streamable_http_app(json_response=True),host='127.0.0.1',port=port,log_level='error'))
                thread=threading.Thread(target=http_server.run,daemon=True);thread.start()
                import time
                deadline=time.monotonic()+5
                while not http_server.started and time.monotonic()<deadline:time.sleep(.02)
                assert http_server.started
                target=f'http://127.0.0.1:{port}/mcp'
            async def exercise():
                async with mcp.Client(target, mode='legacy' if transport=='legacy' else 'auto') as client:
                    listing=await client.list_tools()
                    assert len(listing.tools)==len(adapter.catalog)
                    initial=(await client.call_tool('vase_describe',{'profile':'summary'})).structured_content
                    assert initial['documentId']
                    guard={'expected_revision': initial['collaboration']['revision'],'expected_document_id':initial['documentId']}
                    changed=await client.call_tool('vase_set_camera',{'camera':{'axis':'+Z','fit':'structure'},**guard})
                    assert not changed.is_error,changed
                    assert changed.structured_content['mutation']['changedPaths']
                    stale=await client.call_tool('vase_set_mode',{'mode':'edit',**guard})
                    assert stale.is_error
                    assert stale.structured_content['error']['code']=='conflict'
                    current=(await client.call_tool('vase_describe',{})).structured_content
                    wrong=await client.call_tool('vase_set_mode',{'mode':'edit','expected_revision':current['collaboration']['revision'],'expected_document_id':'wrong-document'})
                    assert wrong.is_error and wrong.structured_content['error']['code']=='conflict'
                    artifact=await client.call_tool('vase_render',{'width':320,'height':240})
                    assert not artifact.is_error,artifact
                    meta=artifact.structured_content['artifact']
                    assert 'dataUrl' not in json.dumps(artifact.structured_content)
                    img=Image.open(meta['path']);assert img.size==(320,240)
                    assert np.asarray(img.convert('RGB')).std()>5
                    resource=await client.read_resource(meta['uri'])
                    assert base64.b64decode(resource.contents[0].blob)==Path(meta['path']).read_bytes()
                    resources=await client.list_resources();assert len(resources.resources)>=3
                    assert any(str(r.uri)=='vase://skill/references/native-tools.md' for r in resources.resources)
                    events=await client.call_tool('vase_events',{'after':1000000});assert not events.is_error
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(lambda: asyncio.run(exercise())).result(timeout=90)
            browser.close()
    finally:
        if http_server: http_server.should_exit=True;thread.join(5)
        adapter.close();editor.close()


def test_strict_function_schemas_cover_all_tools_and_preserve_nullable_omission():
    from v_ase.function_schema import strict_schema, decode_strict
    with FunctionTools(URL) as client:
        definitions=client.function_tools()
        assert len(definitions)==len(client.catalog)
        for tool in definitions:
            assert tool['strict'] is True
            Draft202012Validator.check_schema(tool['parameters'])
        rdf=client.catalog['vase_calculate_rdf'].input_schema
        props={k:None for k in rdf['properties']}
        props.update(expected_revision=0,expected_document_id='test')
        assert 'cutoff' not in decode_strict(props,rdf)
        props['cutoff']={'value':None}
        assert decode_strict(props,rdf)['cutoff'] is None
        props['cutoff']={'value':4.5}
        assert decode_strict(props,rdf)['cutoff']==4.5
        schema={'type':'object','properties':{'ranges':{'type':'object','additionalProperties':{'type':'number'}}},'required':['ranges']}
        wire={'ranges':[{'key':'Cu_surface|O_ads','value':2.8}]}
        assert Draft202012Validator(strict_schema(schema)).is_valid(wire)
        assert decode_strict(wire,schema)=={'ranges':{'Cu_surface|O_ads':2.8}}
        with pytest.raises(ValueError):decode_strict({'ranges':wire['ranges']*2},schema)


def test_default_mcp_registers_advanced_tools_before_a_client_freezes_bindings():
    mcp = pytest.importorskip('mcp')
    from v_ase.mcp_server import create_mcp_server
    from v_ase.cli import build_parser
    assert build_parser().parse_args(['mcp']).discovery == 'all'
    async def exercise():
        with FunctionTools(URL) as adapter:
            async with mcp.Client(create_mcp_server(adapter)) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert names == set(adapter.catalog)
                assert {'vase_configure_bonds', 'vase_apply_scene', 'vase_scene_snapshot'} <= names
                bad = await client.call_tool('vase_configure_bonds', {})
                assert bad.structured_content['error']['code'] == 'invalid_arguments'
    asyncio.run(exercise())


def test_progressive_mcp_discovers_then_calls_loaded_tools():
    mcp=pytest.importorskip('mcp')
    from v_ase.mcp_server import create_mcp_server, CORE_TOOLS
    async def exercise():
        with FunctionTools(URL) as adapter:
            async with mcp.Client(create_mcp_server(adapter,discovery='progressive')) as client:
                assert len((await client.list_tools()).tools)==len(CORE_TOOLS.intersection(adapter.catalog))
                found=await client.call_tool('vase_search_tools',{'query':'configure_bonds','limit':1})
                assert not found.is_error
                assert found.structured_content['tools'][0]['name']=='vase_configure_bonds'
                assert len((await client.list_tools()).tools)==len(CORE_TOOLS.intersection(adapter.catalog))+1
                bad=await client.call_tool('vase_configure_bonds',{})
                assert bad.is_error and bad.structured_content['error']['code']=='invalid_arguments'
    asyncio.run(exercise())


def test_native_scientific_edits_queries_and_quoted_file_paths(tmp_path):
    from ase import Atoms
    from ase.io import write
    from playwright.sync_api import sync_playwright
    import numpy as np
    from v_ase.viewer import view, find_free_port
    from v_ase.ai import ai_handshake
    atoms=Atoms('CH',positions=[[0,0,0],[2,0,0]],cell=[8,8,8],pbc=True)
    # The path is data throughout; it must not pass through shell parsing.
    source=tmp_path / 'a "quoted" $sample `file`.extxyz'
    write(source,atoms)
    editor=view(atoms,block=False,open_browser=False,close_on_disconnect=False,port=find_free_port(),viz_only=False)
    handshake=ai_handshake(editor.url)
    from v_ase.session import sessions
    session=sessions[handshake['session_id']]
    session.config['launch_directory']=str(tmp_path)
    try:
        with sync_playwright() as pw, FunctionTools(handshake['command_url'],artifact_dir=tmp_path/'artifacts') as tools:
            browser=pw.chromium.launch(headless=True);page=browser.new_page();page.goto(editor.url);page.wait_for_function('window.v_aseAI')
            def apply(name, args):
                state=tools.call('vase_describe',{})
                return tools.call(name,{**args,'expected_document_id':state['documentId'],'expected_revision':state['collaboration']['revision']})
            result=apply('vase_rotate_selection',{'indices':[0,1],'angle_deg':180,'axis':[0,0,1],'pivot':'com','response_profile':'structure'})
            expected=atoms.positions.copy();center=np.average(expected,axis=0,weights=atoms.get_masses());expected[:,:2]=2*center[:2]-expected[:,:2]
            np.testing.assert_allclose(result['positions'],expected,atol=1e-8)
            duplicated=apply('vase_duplicate_selection',{'indices':[1]});assert duplicated['atomCount']==3
            apply('vase_undo',{})
            loaded=apply('vase_load_structure',{'path':source.name,'confirm_replace':True,'runtime_mode':'edit'})
            assert loaded['atomCount']==2
            appended=apply('vase_append_structure',{'path':source.name})
            assert appended['frameCount']==2
            capabilities=tools.call('vase_capabilities',{})
            assert set(capabilities['queries'])==set(AI_QUERY_SCHEMAS)
            catalog=tools.call('vase_atom_scalar_catalog',{})
            assert catalog['query']=='atom-scalar-catalog'
            properties=tools.call('vase_atom_properties',{'index':1})
            assert properties['result']['atom_index']==1
            preview=tools.call('vase_bulk_preview',{'formula':'Cu','cell_mode':'cubic'})
            assert preview['query']=='bulk-preview'
            strict=tools.function_tools(['vase_set_camera'])[0]['parameters']
            args={k:None for k in strict['properties']}
            # Optional camera fields omitted by strict nulls; only the axis changes.
            camera_schema=tools.catalog['vase_set_camera'].input_schema['properties']['camera']
            args['camera']={k:None for k in camera_schema['properties']};args['camera']['axis']='+X'
            state=tools.call('vase_describe',{});args.update(expected_revision=state['collaboration']['revision'],expected_document_id=state['documentId'])
            output=tools.call_function('vase_set_camera',json.dumps(args))
            assert output['mutation']['applied']
            exported=tools.call('vase_export_project',{});assert Path(exported['artifact']['path']).stat().st_size>100
            assert tools.metrics['calls']>10
            browser.close()
    finally:editor.close()


def test_generated_tool_reference_is_current():
    import runpy
    generator=runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/generate_ai_tool_reference.py'))
    assert (Path(__file__).resolve().parents[1]/'docs/ai-tools-reference.md').read_text()==generator['render']()


def test_two_agents_cannot_apply_the_same_revision_twice_or_broadcast_edits(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from ase import Atoms
    from playwright.sync_api import sync_playwright
    from v_ase.viewer import view, find_free_port
    from v_ase.ai import ai_handshake
    from v_ase.session import sessions
    atoms=Atoms('H',positions=[[0,0,0]],cell=[8,8,8],pbc=True)
    editor=view(atoms,block=False,open_browser=False,close_on_disconnect=False,port=find_free_port(),viz_only=False)
    h=ai_handshake(editor.url)
    try:
        with sync_playwright() as pw, FunctionTools(h['command_url']) as a, FunctionTools(h['command_url']) as b:
            browser=pw.chromium.launch(headless=True);page=browser.new_page();page.goto(editor.url);page.wait_for_function('window.v_aseAI')
            state=a.call('vase_describe',{})
            args={'element':'H','position':[2,0,0],'expected_document_id':state['documentId'],'expected_revision':state['collaboration']['revision']}
            def add(client):
                try:return client.call('vase_add_atom',args)
                except ToolError as exc:return exc
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(add,c) for c in [a,b]]
                results=[f.result() for f in futures]
            assert sum(isinstance(r,dict) for r in results)==1
            assert [r.code for r in results if isinstance(r,ToolError)]==['conflict']
            assert len(sessions[h['session_id']].working_atoms)==2
            other=browser.new_page();other.goto(editor.url);other.wait_for_function('window.v_aseAI')
            with pytest.raises(ToolError) as error:a.call('vase_add_atom',args)
            assert error.value.code=='ambiguous_browser'
            assert error.value.outcome=='not_applied'
            assert len(sessions[h['session_id']].working_atoms)==2
            browser.close()
    finally:editor.close()


def test_progressive_mcp_modern_subscription_delivers_tool_change():
    mcp=pytest.importorskip('mcp')
    from v_ase.mcp_server import create_mcp_server
    from mcp.client.subscriptions import ToolsListChanged
    async def exercise():
        with FunctionTools(URL) as adapter:
            async with mcp.Client(create_mcp_server(adapter,discovery='progressive')) as client:
                assert client.server_capabilities.tools.list_changed
                async with client.listen(tools_list_changed=True) as changes:
                    await client.call_tool('vase_search_tools',{'query':'configure_bonds','limit':1})
                    event=await asyncio.wait_for(anext(changes.__aiter__()),timeout=3)
                    assert isinstance(event,ToolsListChanged)
    asyncio.run(exercise())


def test_typed_display_roundtrip_volume_and_settings_restore(tmp_path):
    from ase import Atoms
    from ase.io import write
    import numpy as np
    from playwright.sync_api import sync_playwright
    from v_ase.viewer import view,find_free_port
    from v_ase.ai import ai_handshake
    from v_ase.session import sessions
    from v_ase.volumetric import VolumetricData
    from v_ase.ai_tools import _snake
    atoms=Atoms('CuO',positions=[[1,1,1],[3,1,1]],cell=[8,8,8],pbc=True)
    fields=[VolumetricData('one',np.arange(64,dtype=float).reshape(4,4,4),atoms.cell.array)]
    editor=view(atoms,block=False,open_browser=False,close_on_disconnect=False,port=find_free_port(),volumetric_datasets=fields)
    h=ai_handshake(editor.url);sessions[h['session_id']].config['launch_directory']=str(tmp_path)
    def snake_values(value,schema):
        if isinstance(value,dict):
            props=schema.get('properties',{});extra=schema.get('additionalProperties',{})
            return {_snake(k) if k in props else k:snake_values(v,props.get(k,extra if isinstance(extra,dict) else {})) for k,v in value.items()}
        if isinstance(value,list):return [snake_values(v,schema.get('items',{})) for v in value]
        return value
    try:
        with sync_playwright() as pw,FunctionTools(h['command_url'],artifact_dir=tmp_path) as tools:
            browser=pw.chromium.launch(headless=True);page=browser.new_page();page.goto(editor.url);page.wait_for_function('window.v_aseAI')
            def apply(name,args):
                state=tools.call('vase_describe',{})
                return tools.call(name,{**args,'expected_document_id':state['documentId'],'expected_revision':state['collaboration']['revision']})
            state=tools.call('vase_describe',{'profile':'analysis'})
            dataset=state['analysis']['volumetricDatasets'][0]['id']
            apply('vase_add_volumetric_plane',{'dataset_id':dataset,'hkl':[0,0,1],'resolution':128})
            full=tools.call('vase_describe',{'profile':'full'})
            schema=AI_CONTROL_SCHEMA['properties']['display']
            display={k:v for k,v in full['display'].items() if k in schema['properties']}
            apply('vase_set_display',{'display':snake_values(display,schema)})
            saved=tools.call('vase_export_settings',{})
            apply('vase_set_display',{'display':{'show_cell':False}})
            apply('vase_load_settings',{'path':Path(saved['artifact']['path']).name})
            restored=tools.call('vase_describe',{'profile':'full'})
            np.testing.assert_allclose(restored['positions'],full['positions'])
            assert restored['display']['showCell']==full['display']['showCell']
            assert len(restored['display']['volumetricPlanes'])==1
            wrong=tmp_path/'not-a-grid.extxyz';write(wrong,atoms)
            count=restored['frameCount']
            with pytest.raises(ToolError):apply('vase_load_volumetric',{'path':wrong.name})
            assert tools.call('vase_describe',{})['frameCount']==count
            browser.close()
    finally:editor.close()


def test_progressive_legacy_initialize_advertises_list_changes_and_scope():
    mcp=pytest.importorskip('mcp')
    from v_ase.mcp_server import create_mcp_server
    async def exercise():
        with FunctionTools(URL) as adapter:
            assert 'vase_documents' not in adapter.catalog
            async with mcp.Client(create_mcp_server(adapter,discovery='progressive'),mode='legacy') as client:
                assert client.server_capabilities.tools.list_changed
    asyncio.run(exercise())
    with FunctionTools(URL.replace('/session/','/workspace/')) as adapter:
        assert 'vase_documents' in adapter.catalog


def test_poscar_reports_directional_constraint_limit_without_changing_atoms():
    from ase import Atoms
    from ase.constraints import FixedPlane
    from v_ase.session import EditorSession
    from v_ase.export import export_poscar_response
    import numpy as np
    atoms=Atoms('H',positions=[[1,2,3]],cell=[[10,0,0],[1,9,0],[.5,.8,8]],pbc=True)
    atoms.set_constraint(FixedPlane([0],[0,0,1]))
    session=EditorSession("poscar-constraint-test",atoms.copy(),atoms.copy())
    before=session.working_atoms.copy()
    with pytest.raises(ValueError,match='No constraints were discarded'):
        export_poscar_response(session,{'positions':atoms.positions.tolist()})
    np.testing.assert_array_equal(session.working_atoms.positions,before.positions)
    np.testing.assert_array_equal(session.working_atoms.constraints[0].dir,[0,0,1])


def test_tool_annotations_distinguish_visual_changes_artifacts_and_physical_edits():
    catalog=tool_catalog()
    assert catalog['vase_describe'].definition()['annotations']['readOnlyHint']
    assert not catalog['vase_set_camera'].definition()['annotations']['destructiveHint']
    assert not catalog['vase_render'].definition()['annotations']['readOnlyHint']
    assert not catalog['vase_render'].definition()['annotations']['destructiveHint']
    assert catalog['vase_delete_selection'].definition()['annotations']['destructiveHint']
