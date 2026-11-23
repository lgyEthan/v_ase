"""Read actual SVG quantity/unit labels, including short analysis workspaces."""
import pytest
from ase import Atoms
from playwright.sync_api import sync_playwright
from v_ase.viewer import view,find_free_port
from tests.ui_navigation import open_editor_route


@pytest.mark.parametrize('periodic',[True,False],ids=['rdf','finite-pairs'])
def test_analysis_quantity_and_unit_labels_remain_visible(periodic):
    editor=view(Atoms('CuO',positions=[[0,0,0],[1.8,0,0]],cell=[7]*3,pbc=periodic),
                notebook=True,open_browser=False,block=False,port=find_free_port(),viz_only=False,close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True);p=b.new_page(viewport={'width':1440,'height':900})
            p.goto(editor.url);p.wait_for_function('window.__ASE_APP__?.collaborationReady')
            open_editor_route(p,'rdf');p.locator('#btn-rdf-calculate').click()
            p.wait_for_function('Boolean(window.__ASE_APP__.state.rdfResult) && !document.body.dataset.busy')
            expected=p.evaluate("window.__ASE_APP__.state.rdfResult.y_label || (window.__ASE_APP__.state.rdfResult.analysis_kind==='pair-distribution'?'Pair probability / Å⁻¹':'g(r)')")
            for width,height,theme in [(1440,900,'light'),(1024,460,'light'),(1024,460,'dark')]:
                p.set_viewport_size({'width':width,'height':height})
                p.evaluate('async theme=>{const a=window.__ASE_APP__;a.applyThemePreference(theme);await a.plotRdf(a.state.rdfResult);await Plotly.Plots.resize(document.getElementById("rdf-plot"));}',theme)
                x=p.locator('#rdf-plot .xtitle');y=p.locator('#rdf-plot .ytitle')
                assert x.text_content()=='r / Å'
                assert y.text_content()==expected
                for label in [x,y]:
                    assert label.is_visible()
                    bounds=label.bounding_box();panel=p.locator('#analysis-drawer').bounding_box()
                    assert bounds['x']>=panel['x'] and bounds['y']>=panel['y']
                    assert bounds['x']+bounds['width']<=panel['x']+panel['width']+1
                    assert bounds['y']+bounds['height']<=panel['y']+panel['height']+1
            b.close()
    finally:editor.close()
