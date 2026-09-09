"""Pixel-level checks of compositing, not just successful HTTP/image exports."""
import base64
import io
import json
import subprocess
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view,find_free_port

ROOT=Path(__file__).resolve().parents[1]


def test_bsp_splits_crossing_faces_without_changing_area_or_insertion_order():
    node=shutil.which('node')
    if node is None:pytest.skip('Node.js is needed for the pure geometry ordering check.')
    source='''
        import {PolyhedraBSP} from './v_ase/static/polyhedra_bsp.js';
        const p=[{key:'red',points:[[-1,-1,-1],[1,-1,1],[1,1,1],[-1,1,-1]]},
                 {key:'blue',points:[[-1,-1,1],[1,-1,-1],[1,1,-1],[-1,1,1]]}];
        const area=points=>{let n=0;for(let i=1;i<points.length-1;i++){
            const a=points[i].map((v,k)=>v-points[0][k]),b=points[i+1].map((v,k)=>v-points[0][k]);
            n+=Math.hypot(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])/2;
        }return n;};
        const tree=new PolyhedraBSP(p),fragments=tree.ordered([0,0,10]);
        const reverse=new PolyhedraBSP([...p].reverse()).ordered([0,0,10]);
        console.log(JSON.stringify({initial:p.reduce((a,p)=>a+area(p.points),0),
            final:fragments.reduce((a,p)=>a+area(p.points),0),fragments:fragments.length,
            deterministic:JSON.stringify(fragments.map(p=>[p.key,p.points]))===JSON.stringify(reverse.map(p=>[p.key,p.points]))}));
    '''
    result=subprocess.run([node,'--input-type=module','-e',source],cwd=ROOT,check=True,capture_output=True,text=True)
    data=json.loads(result.stdout)
    assert data['fragments']>2 and data['deterministic']
    assert data['final']==pytest.approx(data['initial'],abs=1e-12)


@pytest.mark.parametrize('projection',['orthographic','perspective'])
@pytest.mark.parametrize('mode',['2d','3d'])
def test_crossing_transparent_faces_sort_per_pixel_and_respect_opaque_depth(tmp_path,mode,projection):
    editor=view(Atoms('He',positions=[[0,0,0]]),port=find_free_port(),notebook=True,block=False,viz_only=True,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':600,'height':600})
            page.goto(f'http://127.0.0.1:{editor.port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__V_ASE_APP__?.renderer?.atomsData')
            images=page.evaluate('''async ({mode,projection})=>{
                const T=await import('three'),a=window.__V_ASE_APP__,r=a.renderer;
                a.setInspectorCollapsed(true,false);
                Object.assign(a.state.display,{atomDisplayMode:mode,showBonds:false,showCell:false,showAxes:false,showGrid:false});
                r.setDisplayOptions(a.state.display);
                // Isolate two intersecting faces; each pixel has a known depth order.
                r.scene.traverse(o=>{if(o.isMesh||o.isLine||o.isLineSegments||o.isSprite)o.visible=false;});
                r.displayOptions.showPolyhedra=true;
                r.polyhedraGroup=new T.Group();r.scene.add(r.polyhedraGroup);
                r.camera=r.orthographicCamera;r.camera.left=-1.5;r.camera.right=1.5;r.camera.top=1.5;r.camera.bottom=-1.5;
                r.camera.zoom=1;
                if(projection==='perspective'){r.camera=r.perspectiveCamera;r.camera.fov=2*Math.atan(1.5/10)*180/Math.PI;r.camera.aspect=1;}
                r.camera.position.set(0,0,10);r.camera.up.set(0,1,0);r.camera.lookAt(0,0,0);r.camera.updateProjectionMatrix();
                r.controls.camera=r.camera;r.controls.target.set(0,0,0);
                const polygons=[{key:'red',points:[[-1,-1,-1],[1,-1,1],[1,1,1],[-1,1,-1]],rgba:[1,0,0,.5],reference:{index:0}},
                    {key:'blue',points:[[-1,-1,1],[1,-1,-1],[1,1,-1],[-1,1,1]],rgba:[0,0,1,.5],reference:{index:0}}];
                const capture=()=>{r.preparePolyhedraView(r.camera);r.updateViewLighting();r.renderer.render(r.scene,r.camera);return r.domElement.toDataURL('image/png');};
                let mesh=r.createPolyhedraFaceMesh(polygons,true);r.polyhedraGroup.add(mesh);const first=capture();
                r.clearGroup(r.polyhedraGroup);mesh=r.createPolyhedraFaceMesh([...polygons].reverse(),true);r.polyhedraGroup.add(mesh);const reversed=capture();
                const marker=new T.Mesh(new T.SphereGeometry(.12,32,24),new T.MeshBasicMaterial({color:'#808080',toneMapped:false}));
                marker.position.set(.6,0,0);r.scene.add(marker);const between=capture();
                marker.position.z=2;const front=capture();
                const ndc=marker.position.clone().project(r.camera);const frontPoint=[Math.round((1-ndc.y)*300),Math.round((ndc.x+1)*300)];
                marker.position.z=-2;const behind=capture();
                r.scene.remove(marker);r.camera.position.z=-10;r.camera.up.set(0,-1,0);r.camera.lookAt(0,0,0);const opposite=capture();
                return {first,reversed,between,front,behind,opposite,frontPoint};
            }''',{'mode':mode,'projection':projection})
            front_point=tuple(images.pop('frontPoint'))
            pixels={}
            for name,encoded in images.items():
                raw=base64.b64decode(encoded.split(',',1)[1]);(tmp_path/f'{mode}-{name}.png').write_bytes(raw)
                pixels[name]=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
            np.testing.assert_array_equal(pixels['first'],pixels['reversed'])
            if mode=='2d' and projection=='orthographic':
                # Normal alpha blending: near red(.5) over far blue(.5) over white.
                np.testing.assert_allclose(pixels['first'][300,420],[191,64,128],atol=2)
                np.testing.assert_allclose(pixels['first'][300,180],[128,64,191],atol=2)
                np.testing.assert_allclose(pixels['between'][300,420],[192,64,64],atol=2)
                np.testing.assert_allclose(pixels['front'][front_point],[128,128,128],atol=2)
                np.testing.assert_allclose(pixels['behind'][300,420],[160,32,96],atol=2)
            else:
                np.testing.assert_allclose(pixels['front'][front_point],[128,128,128],atol=2)
                assert not np.array_equal(pixels['between'][300,420],pixels['behind'][300,420])
            assert not np.array_equal(pixels['first'],pixels['opposite'])
            browser.close()
    finally:editor.close()
