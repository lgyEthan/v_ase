"""Navigate the real editor workbench in browser tests."""

ROUTE_GROUPS = {
    'style': ('appearance', 'bonding', 'cell-replication', 'polyhedra', 'water', 'isosurfaces', 'forces', 'view'),
    'build': ('add-atoms', 'transform', 'cell-transform', 'constraints',
              'build-match', 'scientific-tools', 'build-rigid'),
    'analyze': ('selection', 'rdf', 'displacement', 'volumetric', 'registry-map'),
    'render': ('export', 'render-image', 'render-video', 'render-html', 'render-geometry'),
}


def open_editor_route(page, route, *, expand_appearance=True):
    """Click the public workbench/search controls, never private app routing."""
    handle = page.locator('#editor-inspector-toggle')
    if handle.get_attribute('aria-expanded') == 'false':
        handle.click()
    trigger=page.locator('#editor-search-toggle')
    if trigger.get_attribute('aria-expanded') != 'true':
        trigger.click()
    page.locator('#editor-command-search').fill(route)
    page.locator(f'#editor-navigator [data-editor-route="{route}"]').click()
    # Workflow assertions measure committed geometry. The 120 ms route entry
    # can otherwise be sampled at its 8 px starting offset; motion tests inspect
    # those intermediate frames separately. Await completion, never a fixed sleep.
    page.locator('#inspector-content > .editor-route-current').evaluate('''async e=>{
        const nodes=[e,document.querySelector('#inspector .inspector-head'),document.getElementById('inspector')];
        await Promise.all(nodes.flatMap(n=>n?.getAnimations() || []).map(a=>a.finished.catch(()=>{})));
    }''')
    if route == 'appearance' and expand_appearance:
        expand_appearance_rows(page)


def expand_appearance_rows(page):
    """Use each real disclosure to expose fields needed by scientific tests."""
    for row in page.locator('#appearance-table details.appearance-row').all():
        if row.get_attribute('open') is None:
            summary = row.locator(':scope > summary')
            summary.focus()
            summary.press('Enter')


def click_view_control(page, selector):
    """Reach a canvas setting through its actual Camera popover."""
    trigger = page.locator('#camera-rotation-toggle')
    if trigger.get_attribute('aria-expanded') != 'true':
        trigger.click()
    page.locator(selector).click()


def open_document_menu(page, name='File'):
    trigger = page.locator('#editor-menu-toggle')
    if trigger.get_attribute('aria-expanded') != 'true':
        trigger.click()
    page.locator('#editor-menu-bar > details > summary').filter(has_text=name).first.click()


def set_scene_navigator_open(page, opened=True):
    trigger = page.locator('#editor-sidebar-toggle')
    if (trigger.get_attribute('aria-pressed') == 'true') != opened:
        trigger.click()
