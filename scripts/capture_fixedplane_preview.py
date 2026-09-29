"""Capture the local FixedPlane proposal without replacing release showcase media.

Run: python scripts/capture_fixedplane_preview.py --output /path/to/preview
All pictures come from the real renderer; the gallery adds only captions.
"""
import argparse
import base64
import html
import io
import math
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ase import Atoms
from ase.build import fcc111
from PIL import Image
from ase.constraints import FixedPlane
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port
from capture_readme_screenshots import (
    set_display, set_camera, set_atomic_scale, set_selection,
    collapse_inspector, set_readme_lighting,
)



def capture_depth_study(browser, out, errors):
    """An isolated atom makes true front/back ordering easy to inspect."""
    atoms = Atoms('Cu', positions=[[0,0,0]])
    atoms.set_constraint(FixedPlane(0, [0,0,1]))
    port = find_free_port()
    editor = view(atoms, notebook=True, block=False, port=port, open_browser=False,
                  close_on_disconnect=False, viz_only=False, theme='dark',
                  document_name='FixedPlane depth study', show_bonds=False)
    try:
        page = browser.new_page(viewport={'width':960,'height':760}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
        page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 1')
        set_display(page, {'showGrid':False,'showCell':False,'showAxes':False,'showBonds':False,
                          'viewportBackground':'dark','atomRadiusScale':1,'labelRadii':{'Cu':1.04},
                          'labelColors':{'Cu':'#8f7748'},'labelMaterials':{'Cu':'standard'},
                          'atomSmoothness':64})
        collapse_inspector(page)
        set_selection(page,[0])
        set_atomic_scale(page,110)
        set_readme_lighting(page,[0,0,0],intensity=2.3,position_offset=[-10,-12,16])
        def capture(elevation, mode='3d'):
            angle=math.radians(elevation)
            set_camera(page,target=[0,0,0],position=[0,-24*math.cos(angle),24*math.sin(angle)],up=[0,0,1],wait_ms=0)
            image=page.evaluate("""mode=>window.__ASE_APP__.renderer.exportPNG(960,680,{
                selectionAppearance:'interactive',backgroundColor:mode==='3d'?'#202c33':'#ffffff',
                includeGrid:false,includeAxes:false,includeCell:false,scaleMode:'viewport'})""",mode)
            return base64.b64decode(image.split(',')[1])
        for mode in ['3d','2d']:
            set_display(page,{'atomDisplayMode':mode,'viewportBackground':'dark' if mode=='3d' else 'white'})
            for name,elevation in [('oblique',28),('below',-28),('edge',0),('top',80)]:
                (out/f'depth-{mode}-{name}.png').write_bytes(capture(elevation,mode))
            set_selection(page,[])
            (out/f'depth-{mode}-unselected.png').write_bytes(capture(68,mode))
            idle = capture(28,mode)
            (out/f'depth-{mode}-unselected-oblique.png').write_bytes(idle)
            set_selection(page,[0])
            selected = capture(28,mode)
            toggles = [Image.open(io.BytesIO(data)).convert('RGB') for data in [idle, selected]]
            toggles[0].save(out/f'selection-toggle-{mode}.gif',save_all=True,
                           append_images=toggles[1:],duration=1200,loop=0,disposal=2)
        set_display(page,{'atomDisplayMode':'3d','viewportBackground':'dark'})
        frames=[]
        for frame in range(64):
            elevation=30+42*math.sin(2*math.pi*frame/64)
            frames.append(Image.open(io.BytesIO(capture(elevation))).convert('RGB'))
        frames[0].save(out/'depth-orbit.gif',save_all=True,append_images=frames[1:],
                       duration=85,loop=0,optimize=True,disposal=2)
        frames=[]
        for frame in range(48):
            phase=2*math.pi*frame/48
            page.evaluate('''({factor,x})=>{const r=window.__ASE_APP__.renderer;
                r.updatePositions([[x,0,0]]);r.setAtomRadiusFactors([factor]);r.renderNow();}''',
                {'factor':.65+.3*math.sin(phase),'x':1.2*math.cos(phase)})
            frames.append(Image.open(io.BytesIO(capture(48))).convert('RGB'))
        frames[0].save(out/'radius-motion.gif',save_all=True,append_images=frames[1:],
                       duration=85,loop=0,optimize=True,disposal=2)
        page.evaluate('''()=>{const r=window.__ASE_APP__.renderer;
            r.updatePositions([[0,0,0]]);r.setAtomRadiusFactors(null);r.renderNow();}''')
        capture(28)
        result=page.evaluate("""async ()=>{const a=window.__ASE_APP__;
            a.captureRenderAreaCamera({syncPreview:false});
            return a.aiExport({format:'html',width:960,height:680,embedProject:true,options:{
                selectionAppearance:'interactive',backgroundColor:'#202c33',
                includeGrid:false,includeAxes:false,includeCell:false,scaleMode:'viewport'}});
        }""")
        (out/'fixedplane-depth.html').write_bytes(base64.b64decode(result['dataUrl'].split(',')[1]))
        page.close()
    finally:
        editor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    atoms = fcc111('Cu', size=(7, 5, 2), vacuum=4)
    atoms.positions -= atoms.positions.mean(axis=0)
    atoms.pbc = False
    indices = [36, 39, 44, 47, 51, 54, 58, 61, 65, 67]
    normals = [[0,0,1],[0,0,1],[1,0,1],[0,1,1],[0,0,1],
               [1,1,1],[1,0,0],[0,0,1],[0,1,0],[0,0,1]]
    atoms.set_constraint([FixedPlane(i, n) for i, n in zip(indices, normals)])
    port = find_free_port()
    editor = view(atoms, notebook=True, block=False, port=port, open_browser=False,
                  close_on_disconnect=False, viz_only=False, theme='dark',
                  document_name='FixedPlane preview', show_bonds=False)
    errors = []
    panels = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 70')
            set_display(page, {'showGrid':False, 'showCell':False, 'showAxes':False,
                              'showBonds':False, 'atomRadiusScale':1, 'labelRadii':{'Cu':1.04},
                              'labelColors':{'Cu':'#8f7748'}, 'labelMaterials':{'Cu':'standard'},
                              'atomSmoothness':64})
            collapse_inspector(page)
            set_camera(page, target=[0,0,.5], position=[5,-24,16], up=[0,0,1])
            set_atomic_scale(page, 51)
            set_readme_lighting(page, [0,0,0], intensity=2.3, position_offset=[-10,-12,16])
            variants = [('idle','Overview · no selection',[],None),
                        ('single','Single atom · yellow selection',[51],None),
                        ('same-plane','Multiple atoms · same plane',[36,51,67],None),
                        ('selected','Multiple atoms · different planes',[39,54,65],None),
                        ('hover','Hover · selection stays empty',[],51)]
            for mode in ['3d','2d']:
                set_display(page, {'atomDisplayMode':mode,'viewportBackground':'dark' if mode=='3d' else 'white'})
                for key,title,selected,hover in variants:
                    closeup = key in ['single','hover']
                    target = atoms.positions[51].tolist() if closeup else [0,0,.5]
                    set_camera(page, target=target,
                               position=[target[0]+5,target[1]-24,target[2]+16], up=[0,0,1], wait_ms=0)
                    set_atomic_scale(page, 78 if closeup else 51)
                    set_selection(page, selected)
                    page.evaluate('(index)=>window.__ASE_APP__.setHoveredAtom(index)', hover)
                    options = {'selectionAppearance':'interactive','backgroundColor':'#202c33' if mode=='3d' else '#ffffff',
                               'includeGrid':False,'includeAxes':False,'includeCell':False,'scaleMode':'viewport'}
                    image = page.evaluate('(options)=>window.__ASE_APP__.renderer.exportPNG(1440,1000,options)', options)
                    filename = f'{mode}-{key}.png'
                    (out / filename).write_bytes(base64.b64decode(image.split(',')[1]))
                    panels.append({'mode':mode,'title':title,'file':filename})
            set_display(page, {'atomDisplayMode':'3d','viewportBackground':'dark'})
            set_camera(page,target=[0,0,.5],position=[5,-24,16],up=[0,0,1])
            set_atomic_scale(page,51)
            set_selection(page, [39,54,65])
            page.evaluate('window.__ASE_APP__.setHoveredAtom(null)')
            # Store an editable local example and an offline rotating viewer.
            for format, filename in [('project','fixedplane.vase'),('html','fixedplane-interactive.html')]:
                result = page.evaluate("""async format => {
                    const a=window.__ASE_APP__;
                    a.captureRenderAreaCamera({syncPreview:false});
                    return a.aiExport({format,width:1440,height:1000,embedProject:true,options:{
                        selectionAppearance:'interactive',backgroundColor:'#202c33',
                        includeGrid:false,includeAxes:false,includeCell:false,scaleMode:'viewport'}});
                }""", format)
                (out / filename).write_bytes(base64.b64decode(result['dataUrl'].split(',')[1]))
            page.screenshot(path=str(out / 'editor.png'))
            capture_depth_study(browser, out, errors)
            browser.close()
    finally:
        editor.close()
    if errors:
        raise RuntimeError(errors)
    rows = []
    for _, title, _, _ in variants:
        pair = [p for p in panels if p['title']==title]
        rows.append('<section><h2>'+html.escape(title)+'</h2><div class="pair">'+''.join(
            f'<figure><img src="{p["file"]}" alt="{html.escape(title)} in {p["mode"]}"><figcaption>{"3D" if p["mode"]=="3d" else "2D flat"}</figcaption></figure>'
            for p in pair)+'</div></section>')
    (out / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FixedPlane · local preview</title>
<style>*{box-sizing:border-box}body{margin:0;background:#eef2f4;color:#172b35;font:16px/1.5 system-ui,sans-serif}main{max-width:1460px;margin:auto;padding:32px}h1{font-size:27px;margin:0 0 8px}h2{font-size:18px;margin:28px 0 10px}p{max-width:1000px;margin:8px 0}a{color:#006d7d}nav{display:flex;gap:24px;margin:18px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;border:1px solid #c8d3d8;border-radius:6px;overflow:hidden;background:white}img{display:block;width:100%}figcaption{padding:9px 14px;font-weight:600}small{display:block;color:#586b76;margin-top:25px}@media(max-width:760px){main{padding:18px}.pair{grid-template-columns:1fr}}</style>
<main><h1>FixedPlane constraint · selection expands the ring</h1>
<p>A translucent pale cyan face fills the space between the atom and the outer ring. Narrow, darker inner and outer rims clearly frame the face. Selection expands the inner and outer edges equally around the yellow outline, preserving the face width and thickness. All parts use real 3D depth. Selection and hover reveal dashed normals with X ends.</p>
<p>The face, rim, and normal follow the atom’s current position and rendered radius, including property-based animation. Zero-radius atoms hide their constraint marks. Flat 2D and exports use the same geometry. All examples below come from the actual renderer.</p>
<nav><a href="fixedplane-depth.html">Rotate one atom</a><a href="fixedplane-interactive.html">Rotate the dense structure</a><a href="fixedplane.vase" download>Download .vase example</a></nav>
<section><h2>Selection · equal-width expanded ring</h2><p>Same camera and atom size. The selected ring expands around the yellow outline without losing face width. The face remains 70% transparent.</p><div class="pair"><figure><img src="depth-3d-unselected-oblique.png" alt="Unselected atom with the unselected ring"><figcaption>Not selected</figcaption></figure><figure><img src="depth-3d-oblique.png" alt="Yellow selection overlapping the unselected ring"><figcaption>Selected · ring expanded</figcaption></figure></div></section>
<section><h2>Selection toggle · the ring expands and returns</h2><div class="pair"><figure><img src="selection-toggle-3d.gif" alt="3D selection toggling while the ring expands"><figcaption>3D</figcaption></figure><figure><img src="selection-toggle-2d.gif" alt="Flat selection toggling while the ring expands"><figcaption>2D flat</figcaption></figure></div></section>
<section><h2>Pale face · darker, raised rim</h2><div class="pair"><figure><img src="depth-3d-unselected.png" alt="Cyan face fully filled between atom and rim"><figcaption>3D · face and edge have separate colors</figcaption></figure><figure><img src="depth-2d-unselected.png" alt="Filled plane in flat 2D"><figcaption>2D flat · same distinct face and rim</figcaption></figure></div></section>
<section><h2>Moves and changes size with the atom</h2><figure style="max-width:960px"><img src="radius-motion.gif" alt="Atom, filled constraint plane, and yellow selection changing size and position together"><figcaption>Actual position and property-radius updates · geometry is reused</figcaption></figure></section>
<section><h2>Depth study · rotate above and below the ring</h2><p>The rear band disappears behind the atom and its yellow selection outline. The front band passes in front. The face is 30% opaque on both sides; its narrow, darker rims stay opaque.</p><figure style="max-width:960px"><img src="depth-orbit.gif" alt="Real renderer animation showing front and rear ring occlusion"><figcaption>Actual 3D camera rotation</figcaption></figure></section>
<section><h2>Oblique view · 3D and flat 2D</h2><div class="pair"><figure><img src="depth-3d-oblique.png" alt="3D annular ring with correct occlusion"><figcaption>3D</figcaption></figure><figure><img src="depth-2d-oblique.png" alt="Flat annular ring with correct occlusion"><figcaption>2D flat</figcaption></figure></div></section>
<section><h2>Raised edge · filled face</h2><div class="pair"><figure><img src="depth-3d-edge.png" alt="Edge-on physical ring"><figcaption>Edge-on · finite thickness</figcaption></figure><figure><img src="depth-3d-top.png" alt="Face-on physical ring"><figcaption>Near top · the face keeps its width around the yellow outline</figcaption></figure></div></section>
'''+''.join(rows)+'''<small>Local design review for the planned 0.4.10 update. Not published. The .vase example requires this preview source to show the new glyphs; an older installed app uses its own renderer.</small></main></html>''')
    (out / 'capture.json').write_text(json.dumps({'panels':panels,'console_errors':errors},indent=2))
    print(out / 'index.html')


if __name__ == '__main__':
    main()
