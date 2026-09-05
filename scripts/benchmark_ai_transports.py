"""Measure local adapter overhead without making model/SOTA or token claims.

Creates its own GUI. Compares identical summary reads using subprocess CLI,
persistent native functions, and a real MCP stdio client. Needs [dev,mcp].
"""
from __future__ import annotations
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(iterations, output):
    from ase.build import bulk
    from playwright.sync_api import sync_playwright
    from mcp import Client, StdioServerParameters
    from v_ase import __version__
    from v_ase.ai import ai_handshake
    from v_ase.ai_tools import FunctionTools
    from v_ase.viewer import view, find_free_port
    from v_ase.mcp_server import create_mcp_server
    editor=view(bulk('Cu',cubic=True).repeat((3,3,3)), block=False, open_browser=False,
                close_on_disconnect=False,port=find_free_port())
    h=ai_handshake(editor.url)
    rows=[]
    baseline=None
    def record(label, started, result, text_bytes):
        nonlocal baseline
        duration=time.perf_counter()-started
        invariant={k: result[k] for k in ['documentId','frame','atomCount','cell','pbc','labelCounts','stateFingerprint']}
        if baseline is None: baseline=invariant
        assert invariant==baseline, f'{label} returned different semantic state'
        rows.append({'transport':label,'seconds':duration,'result_json_bytes':text_bytes})
    try:
        with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix='vase-benchmark-') as artifacts:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page();page.goto(h['human_url']);page.wait_for_function('window.v_aseAI')
            with FunctionTools(h['command_url'],artifact_dir=artifacts) as native:
                native.call('vase_describe',{})  # Verify/warm the shared contract separately.
                command=[sys.executable,'-m','v_ase.cli','api',h['command_url'],'describe','--profile','summary']
                subprocess.run(command,check=True,capture_output=True)
                strict_args={'profile':'summary','include_positions':None,'include_properties':None,'include_overrides':None}
                async def runs():
                    params=StdioServerParameters(command=sys.executable,args=['-m','v_ase.cli','mcp','--connect',h['command_url'],'--artifact-dir',artifacts],env={'PYTHONPATH':os.environ.get('PYTHONPATH','')})
                    async with Client(params) as mcp:
                        await mcp.call_tool('vase_describe',{})
                        for i in range(iterations):
                            # Rotate order to reduce monotonic warmup/thermal bias.
                            labels=['cli','native_function','mcp_stdio']
                            labels=labels[i%3:]+labels[:i%3]
                            for label in labels:
                                started=time.perf_counter()
                                if label=='cli':
                                    completed=await asyncio.to_thread(subprocess.run,command,check=True,capture_output=True,text=True)
                                    envelope=json.loads(completed.stdout);result=envelope['result'];size=len(completed.stdout.encode())
                                elif label=='native_function':
                                    result=await asyncio.to_thread(native.call_function,'vase_describe',strict_args)
                                    size=len(json.dumps(result,separators=(',',':')).encode())
                                else:
                                    reply=await mcp.call_tool('vase_describe',{})
                                    assert not reply.is_error
                                    result=reply.structured_content
                                    size=len(reply.model_dump_json(by_alias=True,exclude_none=True).encode())
                                record(label,started,result,size)
                        full=await mcp.list_tools()
                    async with Client(create_mcp_server(native,discovery='progressive')) as compact:
                        minimal=await compact.list_tools()
                    return {'mcp_all_tools':len(full.model_dump_json(by_alias=True,exclude_none=True).encode()),
                            'mcp_progressive_initial':len(minimal.model_dump_json(by_alias=True,exclude_none=True).encode()),
                            'native_one_function':len(json.dumps(native.function_tools(['vase_describe']),separators=(',',':')).encode())}
                with ThreadPoolExecutor(max_workers=1) as pool:
                    schemas=pool.submit(lambda:asyncio.run(runs())).result(timeout=180)
                preview=native.call('vase_render',{'width':640,'height':480})
                image_path=Path(output).with_suffix('.png')
                image_path.write_bytes(Path(preview['artifact']['path']).read_bytes())
            browser.close()
        summary={}
        for label in ['cli','native_function','mcp_stdio']:
            values=[row['seconds'] for row in rows if row['transport']==label]
            summary[label]={'median_ms':statistics.median(values)*1000,
                            'p95_ms':sorted(values)[math.ceil(len(values)*.95)-1]*1000,
                            'median_result_json_bytes':statistics.median(row['result_json_bytes'] for row in rows if row['transport']==label)}
        result={'environment':{'python':platform.python_version(),'platform':platform.platform()},'version':__version__,'iterations_per_transport':iterations,'atoms':baseline['atomCount'],
                'scope':'Warm local adapter/CLI process overhead for identical summary reads; no model calls.',
                'provider_tokens':None,'model_success_rate':None,'semantic_results_equal':True,
                'schema_json_bytes':schemas,'summary':summary,'samples':rows,
                'byte_metric':'Serialized result/envelope JSON, excluding HTTP headers and protocol framing. MCP includes its text and structured representations.',
                'limitations':'Not an agent comparison. Startup/discovery is excluded from warm latency. No token, SOTA, or whole-application speed claim.'}
        Path(output).write_text(json.dumps(result,indent=2)+'\n')
        return result
    finally:editor.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=20)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.iterations<3:parser.error('--iterations must be at least 3')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result=measure(args.iterations,args.output)
    print(json.dumps(result['summary'],indent=2))
