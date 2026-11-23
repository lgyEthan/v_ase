"""Actual category scope, shared field geometry, popup collision and grid pixels."""
import base64
import io

import numpy as np
import pytest
from PIL import Image

from tests.test_browser_ui_revision import revision_workspace
from tests.test_browser_desktop_design import desktop_design_page
from tests.ui_navigation import open_editor_route

GROUPS={
 'Style':['appearance','bonding','cell-replication','polyhedra','water','isosurfaces','forces','view'],
 'Build':['add-atoms','transform','cell-transform','constraints','build-match','scientific-tools','build-rigid'],
 'Analyze':['selection','rdf','displacement','volumetric','registry-map'],
 'Render':['export','render-image','render-video','render-html','render-geometry']}


def test_inspector_menu_is_category_scoped_and_keyboard_does_not_commit_early(revision_workspace):
    p,f,_,_=revision_workspace
    for group,routes in GROUPS.items():
        f.get_by_role('tab',name=group,exact=True).click()
        before=f.evaluate('window.__ASE_APP__.editorRoute')
        f.locator('#inspector-tool-trigger').click()
        f.evaluate('''async()=>{window.__ASE_APP__.updateUI();await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}''')
        menu=f.locator('#inspector-tool-menu')
        assert menu.is_visible() and menu.get_attribute('aria-label')==f'{group} tools'
        assert f.locator('#editor-navigator').is_hidden()
        visible=menu.locator('[data-editor-route]:visible')
        assert visible.evaluate_all('es=>es.map(e=>e.dataset.editorRoute)')==routes
        p.keyboard.press('End')
        assert f.evaluate('window.__ASE_APP__.editorRoute')==before
        assert visible.last.evaluate('e=>e===document.activeElement')
        p.keyboard.press('Enter')
        assert f.evaluate('window.__ASE_APP__.editorRoute')==routes[-1]
        assert menu.is_hidden()
        f.locator('#inspector-tool-trigger').click();p.keyboard.press('Escape')
        assert menu.is_hidden()
        assert f.locator('#inspector-tool-trigger').evaluate('e=>e===document.activeElement')
    f.locator('#inspector-tool-trigger').click()
    p.keyboard.press('Meta+f')
    assert f.locator('#inspector-tool-menu').is_hidden()
    f.locator('#editor-command-search').fill('radius')
    assert f.locator('#editor-navigator [data-editor-route="appearance"]').is_visible()


def test_desktop_toolbar_connects_modes_to_stage_and_categories_to_inspector(revision_workspace):
    p,f,_,_=revision_workspace
    for width,height in [(1600,1000),(1280,800),(1024,768),(1024,460)]:
        p.set_viewport_size({'width':width,'height':height})
        if f.locator('#editor-sidebar-toggle').get_attribute('aria-expanded')!='true':
            f.locator('#editor-sidebar-toggle').click()
        f.locator('#workbench-tabs [data-workbench="render"]').click()
        bounds=f.evaluate('''()=>Object.fromEntries(['runtime-mode-switch','editor-search-toggle','workbench-tabs','editor-quick-actions','editor-inspector-toggle','inspector','top-bar'].map(id=>[id,document.getElementById(id).getBoundingClientRect().toJSON()]))''')
        mode,search,tabs,actions,toggle,panel,bar=[bounds[k] for k in ['runtime-mode-switch','editor-search-toggle','workbench-tabs','editor-quick-actions','editor-inspector-toggle','inspector','top-bar']]
        assert mode['right']<=search['left']
        assert actions['right']<=tabs['left']
        assert tabs['right']<=toggle['left']
        assert toggle['right']<=bar['right']
        assert tabs['right']>panel['left'] and tabs['left']<panel['right']
        assert f.locator('#top-bar').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
        assert f.locator('#runtime-mode-switch').evaluate('e=>Boolean(e.compareDocumentPosition(document.getElementById("workbench-tabs")) & Node.DOCUMENT_POSITION_FOLLOWING)')


def test_renderer_fields_have_one_track_height_and_regular_vertical_spacing(desktop_design_page):
    p=desktop_design_page
    open_editor_route(p,'export')
    for width in [320,400,460]:
        p.evaluate('(w)=>window.__ASE_APP__.setInspectorWidth(w)',width)
        p.locator('#inspector-content').evaluate('e=>e.scrollTop=0')
        boxes=p.locator('#renderer-frame-settings').evaluate('''e=>['image-width','image-height','renderer-framing-mode','renderer-pixels-per-angstrom'].map(id=>{const input=document.getElementById(id),el=input.closest('.unit-input')||input;return el.getBoundingClientRect().toJSON();})''')
        for key in ['left','right','width','height']:
            assert max(b[key] for b in boxes)-min(b[key] for b in boxes)<1,(key,boxes)
        assert boxes[0]['height']==28
        assert [round(boxes[i+1]['top']-boxes[i]['bottom']) for i in range(3)]==[8,8,8]
        vector=p.locator('.renderer-vector-row').first
        vector.scroll_into_view_if_needed()
        assert not vector.evaluate('e=>e.scrollWidth>e.clientWidth+1')


def test_camera_popup_never_intersects_fixed_axis_target_even_during_motion(desktop_design_page):
    p=desktop_design_page
    for width,height,inspector in [(1600,1000,320),(1024,768,460),(1024,460,460),(800,600,320),(640,300,320)]:
        p.set_viewport_size({'width':width,'height':height})
        # The browser dispatches resize asynchronously; its normal handler may
        # restore the saved width. Finish that event before setting this case's
        # inspector width, then measure only the camera disclosure motion.
        p.evaluate('async()=>{await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}')
        p.evaluate('(w)=>window.__ASE_APP__.setInspectorWidth(w)',inspector)
        result=p.evaluate('''async()=>{
          const a=window.__ASE_APP__,g=document.getElementById('orientation-widget'),popup=document.getElementById('camera-more-content'),trigger=document.getElementById('camera-rotation-toggle');
            const before=g.getBoundingClientRect().toJSON(),camera=JSON.stringify(a.cameraSettingsSnapshot()),samples=[];
          trigger.click();const start=performance.now();
            do{const r=popup.getBoundingClientRect(),b=g.getBoundingClientRect(),t=trigger.getBoundingClientRect(),rail=document.getElementById('viewport-tools').getBoundingClientRect(),stage=a.renderer.container.getBoundingClientRect();
              samples.push({overlap:Math.min(r.right,b.right)>Math.max(r.left,b.left)&&Math.min(r.bottom,b.bottom)>Math.max(r.top,b.top),railOverlap:Math.min(rail.right,b.right)>Math.max(rail.left,b.left)&&Math.min(rail.bottom,b.bottom)>Math.max(rail.top,b.top),triggerOverlap:Math.min(r.right,t.right)>Math.max(r.left,t.left)&&Math.min(r.bottom,t.bottom)>Math.max(r.top,t.top),contained:r.left>=stage.left&&r.right<=stage.right&&r.top>=stage.top&&r.bottom<=stage.bottom,gizmo:b.toJSON()});
            await new Promise(requestAnimationFrame);
          }while(performance.now()-start<190);
          trigger.click();return {samples,before,cameraUnchanged:camera===JSON.stringify(a.cameraSettingsSnapshot())};
        }''')
        assert result['cameraUnchanged']
        assert all(not s['overlap'] and not s['railOverlap'] and not s['triggerOverlap'] and s['contained'] for s in result['samples']),result
        assert all(s['gizmo']==result['before'] for s in result['samples']),{'size':[width,height,inspector],**result}


def test_empty_stage_welcome_is_centered_and_cannot_cover_camera_controls():
    from ase import Atoms
    from v_ase.viewer import view,find_free_port
    from playwright.sync_api import sync_playwright
    editor=view(Atoms(),notebook=True,open_browser=False,block=False,port=find_free_port(),close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);p=browser.new_page(viewport={'width':1024,'height':460})
            p.goto(editor.url);p.wait_for_function('window.__ASE_APP__?.collaborationReady')
            result=p.evaluate('''async()=>{
              const stage=document.getElementById('app-viewport').getBoundingClientRect(),welcome=document.getElementById('empty-workspace').getBoundingClientRect();
              document.getElementById('camera-rotation-toggle').click();await new Promise(requestAnimationFrame);
              const popup=document.getElementById('camera-more-content');
              const blocked=[...popup.querySelectorAll('button,input')].filter(e=>{const b=e.getBoundingClientRect();return b.width&&b.height&&!e.disabled&&!e.contains(document.elementFromPoint(b.left+b.width/2,b.top+b.height/2));}).map(e=>e.id||e.textContent);
              return {offset:(welcome.left+welcome.width/2)-(stage.left+stage.width/2),blocked};
            }''')
            assert abs(result['offset'])<1
            assert not result['blocked'],result
            browser.close()
    finally:editor.close()


@pytest.mark.parametrize('projection',['orthographic','perspective'])
def test_grid_pixels_do_not_fragment_when_far_clip_changes(desktop_design_page,projection):
    p=desktop_design_page
    encoded=p.evaluate('''projection=>{
      const r=window.__ASE_APP__.renderer;r.setProjectionMode(projection);
      r.camera.position.set(16,-19,22);r.controls.target.set(0,0,0);r.camera.lookAt(0,0,0);
      r.gridGroup.visible=true;r.axesHelper.visible=false;r.atomMeshes.visible=false;r.bondGroup.visible=false;r.cellGroup.visible=false;
      const images=[];const allocations=r.renderer.info.memory.geometries;
      for(const far of [100,10000,1e7,1e9]){r.camera.far=far;r.camera.updateProjectionMatrix();r.renderNow();images.push(r.domElement.toDataURL());}
      return {images,allocations,after:r.renderer.info.memory.geometries};
    }''',projection)
    assert encoded['allocations']==encoded['after']
    arrays=[np.array(Image.open(io.BytesIO(base64.b64decode(x.split(',')[1]))).convert('RGB')).astype(float) for x in encoded['images']]
    assert np.count_nonzero(np.min(arrays[0],axis=2)<250)>1000
    for image in arrays[1:]:
        # Ignore subpixel AA rounding; a broken/missing grid changes broad regions.
        assert np.mean(np.abs(image-arrays[0]))<.08
