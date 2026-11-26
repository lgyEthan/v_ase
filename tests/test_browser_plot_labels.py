"""Read actual graph output in the editor and offline viewer."""
import base64
import gzip
from io import BytesIO
import re

import pytest
from ase import Atoms
from PIL import Image
from playwright.sync_api import expect, sync_playwright
from v_ase.analysis import calculate_rdf
from v_ase.session import sessions
from v_ase.viewer import view,find_free_port
from tests.ui_navigation import open_editor_route


@pytest.mark.parametrize('periodic',[True,[True,True,False],False],ids=['rdf','slab-pairs','finite-pairs'])
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


def test_partial_pbc_plot_can_float_restyle_and_dock_with_registry_using_the_same_controls():
    atoms = Atoms('CuO', positions=[[.2, .3, 0], [7.6, .3, 0]], cell=[8, 8, 25], pbc=[True, True, False])
    editor = view(atoms, notebook=True, open_browser=False, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1540, 'height': 940})
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            open_editor_route(page, 'rdf')
            assert page.locator('#btn-rdf-float').count() == 0
            pbc = page.locator('#rdf-use-pbc')
            assert pbc.is_checked()
            page.locator('#btn-rdf-calculate').click()
            axis = page.locator('#analysis-drawer #rdf-plot .ytitle')
            axis.wait_for()
            assert axis.text_content() == 'Neighbors per atom / Å'
            toolbar_rows = [page.locator(f'#btn-analysis-{name}').bounding_box()['y']
                            for name in ('float', 'export', 'drawer-close')]
            assert max(toolbar_rows) - min(toolbar_rows) <= 1

            page.locator('#btn-analysis-float').click()
            graph = page.locator('#analysis-floating')
            moved_plot = graph.locator('#rdf-plot')
            moved_plot.locator('.xtitle').wait_for()
            assert page.locator('#analysis-drawer').is_hidden()
            original = graph.bounding_box()
            page.locator('#analysis-floating-title').press('Shift+ArrowLeft')
            page.locator('#analysis-floating-resize').press('Shift+ArrowDown')
            changed = graph.bounding_box()
            assert changed['x'] < original['x'] and changed['height'] > original['height']

            page.locator('#btn-analysis-appearance').click()
            page.locator('#energy-background-mode').select_option('transparent')
            page.locator('#energy-grid').uncheck()
            page.locator('#energy-data-mode').select_option('markers')
            axis_controls = page.locator('#energy-graph-axes')
            axis_controls.locator('xpath=..').locator('summary').click()
            x_minimum = axis_controls.get_by_role('spinbutton', name='X minimum', exact=True)
            x_minimum.fill('1.5')
            # A single limit must change the rendered axis while the field still has focus.
            page.wait_for_function("""() => {
                const axis = document.getElementById('rdf-plot')._fullLayout.xaxis;
                return axis.range[0] === 1.5 && axis.range[1] > 1.5;
            }""")
            assert x_minimum.evaluate('input => input === document.activeElement')
            assert axis_controls.get_by_role('spinbutton', name='X maximum', exact=True).input_value() == ''
            x_minimum.fill('9')
            page.wait_for_function("""() => {
                const [min, max] = document.getElementById('rdf-plot')._fullLayout.xaxis.range;
                return min === 9 && max > min;
            }""")
            x_minimum.fill('')
            page.wait_for_function("""() => {
                const axis = document.getElementById('rdf-plot')._fullLayout.xaxis;
                return axis.autorange === true && axis.range[0] < 1.5;
            }""")
            for name, value in [('X minimum', '0.4'), ('X maximum', '1.8'),
                                ('Y minimum', '0'), ('Y maximum', '3')]:
                axis_controls.get_by_role('spinbutton', name=name, exact=True).fill(value)
            page.wait_for_function("""() => {
                const plot = document.getElementById('rdf-plot');
                return String(plot._fullLayout.xaxis.range) === '0.4,1.8'
                    && String(plot._fullLayout.yaxis.range) === '0,3';
            }""")
            x_minimum.fill('2')
            assert axis_controls.get_by_role('status').is_visible()
            assert axis_controls.get_by_role('button', name='Apply limits', exact=True).count() == 0
            assert moved_plot.evaluate('plot => plot._fullLayout.xaxis.range') == [.4, 1.8]
            x_minimum.fill('0.4')
            page.evaluate("""() => Plotly.relayout(document.getElementById('rdf-plot'),
                {'xaxis.range':[0.7,1.4]})""")
            x_minimum.press('Enter')
            page.wait_for_function("""String(document.getElementById('rdf-plot')._fullLayout.xaxis.range) === '0.4,1.8'""")
            page.wait_for_function("""() => {
                const plot = document.getElementById('rdf-plot');
                return plot.data[0].mode === 'markers' && !plot._fullLayout.xaxis.showgrid
                    && getComputedStyle(document.getElementById('analysis-floating')).backgroundColor === 'rgba(0, 0, 0, 0)';
            }""")
            pbc.uncheck()
            page.wait_for_function("window.__ASE_APP__.state.rdfResult.analysis_kind === 'pair-distribution'")
            assert moved_plot.locator('.ytitle').text_content() == 'Pair probability / Å⁻¹'
            assert page.evaluate('window.__ASE_APP__.state.atoms.pbc') == [True, True, False]

            page.locator('#btn-analysis-dock').click()
            page.locator('#analysis-drawer #rdf-plot .xtitle').wait_for()
            assert graph.is_hidden()
            page.evaluate("""async () => window.v_aseAI.apply({display: {rdfUsePbc: true,
                analysisPlots: {rdf: {placement: 'viewport', style: {
                    series: {total: {dataMode: 'line-markers'}}}}}}})""")
            page.wait_for_function("""() => {
                const plot = document.querySelector('#analysis-floating #rdf-plot');
                return plot?.data?.[0].mode === 'lines+markers'
                    && plot.querySelector('.ytitle')?.textContent === 'Neighbors per atom / Å';
            }""")
            page.locator('#btn-analysis-dock').click()
            page.locator('#btn-analysis-drawer-close').click()
            page.locator('#btn-rdf-calculate').click()
            page.locator('#btn-analysis-float').click()
            graph.locator('#rdf-plot').wait_for()
            page.locator('#btn-analysis-floating-close').click()

            page.evaluate('''async () => window.__ASE_APP__.calculateRegistryMap({
                selectedIndices: [0], skipHiddenWarning: true})''')
            page.locator('#analysis-drawer #registry-plot').wait_for()
            page.locator('#btn-analysis-float').click()
            graph.locator('#registry-plot').wait_for()
            page.locator('#btn-analysis-appearance').click()
            dialog = page.get_by_role('dialog', name='Axis limits')
            for name, value in [('X minimum', '-1'), ('X maximum', '3'),
                                ('Y minimum', '-2'), ('Y maximum', '2')]:
                dialog.get_by_role('spinbutton', name=name, exact=True).fill(value)
            page.locator('#apply-graph-axes').click()
            page.wait_for_function("""() => {
                const plot = document.getElementById('registry-plot');
                return String(plot._fullLayout.xaxis.range) === '-1,3'
                    && String(plot._fullLayout.yaxis.range) === '-2,2';
            }""")
            page.locator('#btn-analysis-dock').click()
            page.locator('#analysis-drawer #registry-plot').wait_for()
            assert graph.is_hidden()
            browser.close()
    finally:
        editor.close()


def test_floating_distribution_is_rendered_and_embedded_in_html(tmp_path):
    atoms = Atoms('Cu2O', positions=[[.2, .3, 0], [1.8, .3, 0], [2.8, .5, 0]],
                  cell=[8, 8, 25], pbc=[True, True, False])
    moved = atoms.copy()
    moved.positions[2] += [.7, .3, 0]
    editor = view([atoms, moved], notebook=True, open_browser=False, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1540, 'height': 940}, accept_downloads=True)
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady')
            open_editor_route(page, 'rdf')
            page.locator('#rdf-pair-mode').select_option('all')
            page.locator('#btn-rdf-calculate').click()
            page.locator('#btn-analysis-float').click()
            page.locator('#analysis-floating-title').click()
            settings = page.locator('#graph-settings')
            expect(settings).to_be_visible()
            page.locator('#graph-series').select_option('Cu|O')
            page.locator('#graph-series-name').fill('Cu–O distances')
            page.locator('#energy-data-mode').select_option('markers')
            page.locator('#energy-marker-color').fill('#b03a8c')
            page.locator('#energy-background-mode').select_option('color')
            page.locator('#energy-background-color').fill('#254568')
            settings.get_by_text('Font & tick labels', exact=True).click()
            page.locator('#graph-font-family').select_option('Georgia')
            page.locator('#graph-font-size').fill('14')
            page.locator('#graph-y-tick-labels').uncheck()
            page.locator('#graph-tick-format').select_option('fixed')
            page.locator('#graph-tick-precision').fill('3')
            axes = page.locator('#energy-graph-axes')
            axes.locator('xpath=..').locator('summary').click()
            axes.get_by_role('spinbutton', name='X minimum', exact=True).fill('1.5')
            page.wait_for_function("document.getElementById('rdf-plot')._fullLayout.xaxis.range[0] === 1.5")
            source_plot = page.locator('#analysis-floating #rdf-plot')
            assert source_plot.evaluate("plot => plot.data[0].mode") == 'lines'
            assert source_plot.evaluate("plot => plot.data.find(trace => trace.name === 'Cu–O distances').mode") == 'markers'
            assert source_plot.evaluate("""plot => plot.querySelector('.legend').getBoundingClientRect().bottom
                <= plot.getBoundingClientRect().top + plot._fullLayout._size.t + 1""")
            source_plot.evaluate("""async plot => {
                await Plotly.restyle(plot, {visible: 'legendonly'}, [0]);
                await Plotly.relayout(plot, {'yaxis.range': [0, 2], 'yaxis.autorange': false});
            }""")

            open_editor_route(page, 'render-html')
            page.locator('#btn-export-html').click()
            include = page.locator('#html-include-graph')
            expect(include).to_be_checked()
            preview = page.locator('#html-export-preview')
            expect(preview).to_have_attribute('data-includes-graph', 'true')
            def background_pixels(data_url):
                with Image.open(BytesIO(base64.b64decode(data_url.split(',')[1]))) as image:
                    return sum(pixel == (37, 69, 104) for pixel in image.convert('RGB').getdata())
            assert background_pixels(preview.get_attribute('src')) > 1000
            include.uncheck()
            expect(preview).to_have_attribute('data-includes-graph', 'false')
            assert background_pixels(preview.get_attribute('src')) == 0
            include.check()
            expect(preview).to_have_attribute('data-includes-graph', 'true')
            page.locator('#html-embed-project').check()

            with page.expect_download() as event:
                page.locator('#html-export-confirm').click()
            output = tmp_path / 'distribution.html'
            event.value.save_as(output)
            html = output.read_bytes()

            def compressed_tag(name):
                data = re.search(rb'<script id="v-ase-' + name + rb'"[^>]*>([^<]+)</script>', html).group(1)
                return base64.b64decode(data, validate=True)

            for name in (b'three-source', b'renderer-source', b'plotly-source', b'rdf-frames'):
                payload = compressed_tag(name)
                assert len(payload) < len(gzip.decompress(payload))
            offline = browser.new_page(viewport={'width': 1280, 'height': 820})
            network = []
            offline.on('request', lambda request: network.append(request.url) if request.url.startswith('http') else None)
            offline.goto(output.as_uri())
            expect(offline.locator('#viewer-frame')).to_have_attribute('data-rdf-in-poster', 'true')
            chart = offline.locator('.standalone-rdf-plot')
            expect(chart.get_by_text('Cu–O distances', exact=True)).to_be_visible()
            assert chart.evaluate('plot => plot._fullLayout.xaxis.range[0]') == 1.5
            assert chart.evaluate('plot => plot._fullLayout.yaxis.range') == [0, 2]
            assert chart.evaluate('plot => plot.data[0].visible') == 'legendonly'
            assert chart.evaluate('plot => plot._fullLayout.xaxis.tickformat') == '.3f'
            assert chart.evaluate('plot => plot._fullLayout.yaxis.showticklabels') is False
            assert chart.evaluate('plot => plot._fullLayout.font.family') == 'Georgia'
            assert chart.evaluate("plot => plot.data.find(trace => trace.name === 'Cu–O distances').marker.color") == '#b03a8c'
            assert background_pixels(offline.locator('#standalone-poster').get_attribute('src')) > 1000
            assert offline.locator('.trajectory-energy-overlay').count() == 0
            initial = chart.evaluate("""plot => ({
                x: plot._fullLayout.xaxis.range.slice(), y: plot._fullLayout.yaxis.range.slice(),
                curve: plot.data.find(trace => trace.name === 'Cu–O distances').y.slice()
            })""")
            chart.evaluate("""async plot => {
                await Plotly.relayout(plot, {'xaxis.range': [0.6, 2], 'yaxis.range': [0.3, 1.3], dragmode: 'pan'});
                await Plotly.restyle(plot, {visible: true}, [0]);
            }""")
            offline.locator('#reset-view').focus()
            offline.locator('#next-frame').click()
            expect(offline.locator('.standalone-rdf-overlay')).to_have_attribute('data-frame', '1')
            frame_curve = chart.evaluate("plot => plot.data.find(trace => trace.name === 'Cu–O distances').y")
            assert frame_curve != initial['curve']
            assert frame_curve == pytest.approx(calculate_rdf(moved, pair_mode='all').partial['Cu|O'])
            assert chart.evaluate('plot => plot._fullLayout.xaxis.range') == [0.6, 2]
            assert chart.evaluate('plot => plot._fullLayout.yaxis.range') == [0.3, 1.3]
            assert chart.evaluate('plot => plot.data[0].visible') is True
            offline.locator('#reset-view').click()
            offline.wait_for_function("""() => {
                const plot = document.querySelector('.standalone-rdf-plot');
                return plot._fullLayout.xaxis.range[0] === 1.5
                    && plot._fullLayout.yaxis.range[0] === 0 && plot.data[0].visible === 'legendonly';
            }""")
            assert chart.evaluate('plot => plot._fullLayout.xaxis.range') == initial['x']
            assert chart.evaluate('plot => plot._fullLayout.yaxis.range') == initial['y']
            assert chart.evaluate("plot => plot.data.find(trace => trace.name === 'Cu–O distances').y") == frame_curve
            assert offline.evaluate('() => window.v_aseStandalone.frameIndex') == 1
            offline.locator('#previous-frame').click()
            expect(offline.locator('.standalone-rdf-overlay')).to_have_attribute('data-frame', '0')
            assert chart.evaluate("plot => plot.data.find(trace => trace.name === 'Cu–O distances').y") == initial['curve']
            assert not network

            fallback = browser.new_page()
            fallback.add_init_script("window.DecompressionStream = undefined;")
            fallback.goto(output.as_uri())
            expect(fallback.locator('.standalone-rdf-overlay')).to_have_attribute('data-frame', '0')
            fallback.evaluate('() => window.v_aseStandalone.setFrame(1)')
            expect(fallback.locator('.standalone-rdf-overlay')).to_have_attribute('data-frame', '1')
            assert fallback.locator('.standalone-rdf-plot').evaluate(
                "plot => plot.data.find(trace => trace.name === 'Cu–O distances').y"
            ) == frame_curve
            assert fallback.evaluate('() => window.v_aseStandalone.projectBytes().length') > 0

            # Damage only the optional graph's gzip checksum. A readable
            # trajectory and its embedded project must still open.
            frames = compressed_tag(b'rdf-frames')
            corrupt = bytearray(frames)
            corrupt[-8] ^= 1
            damaged = tmp_path / 'damaged-chart.html'
            damaged.write_bytes(html.replace(base64.b64encode(frames), base64.b64encode(corrupt), 1))
            degraded = browser.new_page()
            degraded.goto(damaged.as_uri())
            expect(degraded.locator('html')).to_have_attribute('data-v-ase-ready', 'true')
            expect(degraded.locator('#boot-error')).to_have_text('The saved distribution could not be loaded.')
            degraded.evaluate('() => window.v_aseStandalone.setFrame(1)')
            expect(degraded.locator('#frame-label')).to_have_text('2 / 2')
            assert degraded.evaluate('() => window.v_aseStandalone.projectBytes().length') > 0

            def assert_restored(document):
                restored = document.locator('#analysis-floating #rdf-plot')
                expect(restored.get_by_text('Cu–O distances', exact=True)).to_be_visible()
                assert restored.evaluate('plot => plot._fullLayout.xaxis.range[0]') == 1.5
                assert restored.evaluate('plot => plot._fullLayout.yaxis.range') == [0, 2]
                assert restored.evaluate('plot => plot.data[0].visible') == 'legendonly'
                assert restored.evaluate('plot => plot._fullLayout.font.family') == 'Georgia'
                assert document.evaluate('window.__ASE_APP__.state.rdfAutoRefresh') is True

            calls = []
            page.on('request', lambda request: calls.append(request.url) if '/api/analysis/rdf/' in request.url else None)
            sessions[editor.session_id].config['launch_directory'] = str(tmp_path)
            assert page.evaluate("""() => window.__ASE_APP__.loadStructureFile({name: 'distribution.html'}, '', ':', null,
                {path: 'distribution.html', confirmedIntent: true, throwErrors: true})""") is not False
            assert_restored(page)
            assert not calls

            reopened = view(str(output), notebook=True, open_browser=False, block=False,
                            port=find_free_port(), close_on_disconnect=False)
            try:
                document = browser.new_page(viewport={'width': 1540, 'height': 940})
                document.on('request', lambda request: calls.append(request.url) if '/api/analysis/rdf/' in request.url else None)
                document.goto(reopened.url)
                document.wait_for_function('window.__ASE_APP__?.collaborationReady')
                assert_restored(document)
                assert not calls
            finally:
                reopened.close()
            browser.close()
    finally:
        editor.close()
