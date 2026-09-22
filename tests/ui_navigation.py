"""Navigate the real editor workbench in browser tests."""

ROUTE_GROUPS = {
    'style': ('appearance', 'bonding', 'cell-replication', 'polyhedra', 'view'),
    'build': ('add-atoms', 'transform', 'cell-transform', 'constraints',
              'build-match', 'scientific-tools', 'build-rigid'),
    'analyze': ('selection', 'rdf', 'displacement', 'forces', 'volumetric', 'registry-map'),
    'render': ('export', 'render-image', 'render-video', 'render-html', 'render-geometry'),
}


def open_editor_route(page, route):
    """Click the public workbench/search controls, never private app routing."""
    handle = page.locator('#btn-inspector-collapse')
    if handle.is_visible() and handle.get_attribute('aria-expanded') == 'false':
        handle.click()
    for group, routes in ROUTE_GROUPS.items():
        if route in routes:
            page.locator(f'#workbench-tabs [data-workbench="{group}"]').click()
            page.locator(f'#workbench-tools [data-editor-route="{route}"]').click()
            return
    page.locator('#editor-search-toggle').click()
    page.locator('#editor-command-search').fill(route)
    page.locator(f'#editor-navigator [data-editor-route="{route}"]').click()
