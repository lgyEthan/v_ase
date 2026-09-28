"""Pixel regressions for selection/constraints and classic Windows scrollbars."""
import io
import numpy as np
import pytest
from PIL import Image
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine, FixedPlane
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port
from tests.ui_navigation import open_editor_route

@pytest.fixture
def page():
    atoms=Atoms('C3',positions=[[-2,0,0],[0,0,0],[2,0,0]],cell=[10]*3)
    atoms.set_constraint([FixAtoms(indices=[0]),FixedLine(1,[0,1,0]),FixedPlane(2,[0,0,1])])
    editor=view(atoms,notebook=True,block=False,port=find_free_port(),viz_only=False,close_on_disconnect=False)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--disable-features=OverlayScrollbar,FluentOverlayScrollbar'])
            page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1.25)
            page.add_init_script("Object.defineProperty(navigator,'userAgentData',{value:{platform:'Windows'},configurable:true})")
            page.goto(editor.url);page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            page.locator('#busy-overlay').wait_for(state='hidden')
            page.evaluate('''()=>{const a=window.__ASE_APP__;
              a.applyDesignSettings({display:{showCell:false,showAxes:false,showGrid:false,showOverlays:false,showConstraints:true}});
              a.applyCameraSettings({position:[0,0,12],target:[0,0,0],up:[0,1,0],projection:'orthographic',ortho_scale:7});}''')
            yield page
            browser.close()
    finally:editor.close()


def canvas_pixels(page):
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    return np.array(Image.open(io.BytesIO(page.locator('#app-viewport canvas').first.screenshot())).convert('RGB'),dtype=int)

@pytest.mark.parametrize('mode',['2d','3d'])
@pytest.mark.parametrize('background',['white','dark'])
def test_drag_and_panel_selection_and_constraints_draw_pixels(page,mode,background):
    page.evaluate('(p)=>window.__ASE_APP__.applyDesignSettings({display:{atomDisplayMode:p.mode,viewportBackground:p.background}})',{'mode':mode,'background':background})
    before=canvas_pixels(page)
    # Drag through the actual pointer selection handler, with scientific overlays off.
    bounds=page.evaluate('''()=>{const r=window.__ASE_APP__.renderer;
      const p=[...r.atomMeshByIndex.values()].map(a=>r.projectWorldToClient(a.position));
      return {x1:Math.min(...p.map(p=>p.x))-35,y1:Math.min(...p.map(p=>p.y))-35,
              x2:Math.max(...p.map(p=>p.x))+35,y2:Math.max(...p.map(p=>p.y))+35};}''')
    page.mouse.move(bounds['x1'],bounds['y1']);page.mouse.down()
    page.mouse.move(bounds['x2'],bounds['y2'],steps=8);page.mouse.up()
    page.wait_for_function('window.__ASE_APP__.state.selected.size===3')
    selected=canvas_pixels(page)
    yellow=lambda a:(a[:,:,0]>160)&(a[:,:,1]>100)&(a[:,:,2]<90)&((a[:,:,0]-a[:,:,2])>90)
    assert yellow(selected).sum()>yellow(before).sum()+150
    # Deselect and reselect through the label table, not a direct renderer call.
    open_editor_route(page,'appearance')
    box=page.locator('[data-appearance-field="select"][data-atom-label="C"]')
    box.uncheck();page.wait_for_function('window.__ASE_APP__.state.selected.size===0')
    unselected=canvas_pixels(page)
    box.check();page.wait_for_function('window.__ASE_APP__.state.selected.size===3')
    assert yellow(canvas_pixels(page)).sum()>yellow(unselected).sum()+150
    box.uncheck()
    # Each constraint type must change real pixels; physical constraints stay intact.
    visible=canvas_pixels(page)
    page.click('#btn-objects');page.get_by_role('checkbox',name='Show Constraints',exact=True).uncheck();page.click('#btn-objects')
    hidden=canvas_pixels(page)
    difference=np.abs(visible-hidden).sum(axis=2)
    assert (difference>20).sum()>150
    assert page.evaluate('window.__ASE_APP__.state.atoms.constraints.fixed_indices')==[0]
    Image.fromarray(visible.astype('uint8')).save(f'/tmp/vase049-constraints-{mode}-{background}.png')
    Image.fromarray(selected.astype('uint8')).save(f'/tmp/vase049-selection-{mode}-{background}.png')

@pytest.mark.parametrize('width,height,zoom',[(1280,720,1),(1024,600,1.25),(1024,768,1.5),(390,844,1)])
def test_placement_has_one_vertical_scroll_and_reachable_actions(page,width,height,zoom):
    page.set_viewport_size({'width':width,'height':height})
    # Browser zoom applies layout pressure; native Electron also tests OS-style zoom.
    page.evaluate('(z)=>document.documentElement.style.zoom=z',zoom)
    open_editor_route(page,'add-atoms')
    page.click('#add-atoms-tab-batch');page.click('#add-atoms-content-molecules')
    button=page.locator('#btn-add-atoms-scatter')
    button.scroll_into_view_if_needed()
    data=button.evaluate('''el=>{const scroll=[];for(let p=el.parentElement;p;p=p.parentElement){
      if(/auto|scroll/.test(getComputedStyle(p).overflowY)&&p.scrollHeight>p.clientHeight+1)scroll.push(p.id||p.className);}
      const r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
      return {scroll,reachable:hit===el||el.contains(hit)};}''')
    assert data['scroll']==['inspector-content'],data
    assert data['reachable'],data
    assert page.locator('#add-atoms-relax-host #btn-relax').count()==1
    assert page.locator('#btn-relax').is_disabled()


def test_inline_placement_relaxation_restores_start_without_removing_added_atoms(page):
    page.evaluate('''async()=>{const a=window.__ASE_APP__;
      await a.aiApply({operation:{name:'scatter-atoms',entries:[{element:'H',label:'H_added',count:2}],
        regions:[{id:'test-allow',name:'Test',role:'allow',bounds:[.1,.5,.1,.5,.1,.5]}],seed:42,freezeExisting:true}});
      window.placementStart=a.state.atoms.positions.map(p=>[...p]);}''')
    open_editor_route(page,'add-atoms');page.click('#add-atoms-tab-batch')
    start=page.locator('#add-atoms-relax-host #btn-relax')
    assert start.is_enabled()
    page.fill('#relax-steps','3');page.fill('#relax-fmax','0.001')
    start.click()
    page.wait_for_function('window.__ASE_APP__.state.relaxTrajectory.frames.length>1 && !window.__ASE_APP__.state.isRelaxing',timeout=30000)
    page.locator('#btn-clear-relax-trajectory').click()
    page.locator('#relax-clear-initial').click()
    page.wait_for_function('window.__ASE_APP__.state.relaxTrajectory.frames.length===0')
    result=page.evaluate('''()=>({positions:window.__ASE_APP__.state.atoms.positions,start:window.placementStart,
        active:window.__ASE_APP__.addAtomsUI.active,kind:document.body.dataset.currentEditorRoute})''')
    np.testing.assert_allclose(result['positions'],result['start'],atol=1e-12)
    assert len(result['positions'])==5 and result['active'] and result['kind']=='add-atoms'
    page.locator('#btn-add-atoms-cancel').click()
    page.wait_for_function('window.__ASE_APP__.state.atoms.positions.length===3')
