"""Capture every real editor route for visual review; never changes input files.

Run from the repository's dev environment. The gallery is local and unpublished.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from ase.io import read
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v_ase.viewer import find_free_port, view


def capture(destination: Path, source: Path, *, expanded: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    frames = read(source, index=':')
    editor = view(frames, notebook=True, block=False, port=find_free_port(),
                  viz_only=False, close_on_disconnect=False, open_browser=False)
    records, errors = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 960}, device_scale_factor=1)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.collaborationReady && document.documentElement.dataset.interfaceReady')
            page.emulate_media(reduced_motion='reduce')
            routes = page.locator('#editor-navigator [data-editor-route], #workbench-tools [data-editor-route], [data-editor-menu-route]').evaluate_all('(nodes)=>[...new Set(nodes.map(n=>n.dataset.editorRoute || n.dataset.editorMenuRoute))]')

            def capture_expanded(route, theme, width, height):
                if not expanded:
                    return
                details = page.evaluate('''()=>{window.__galleryDetails=[...document.querySelectorAll('#inspector-content .editor-route-current details')].map(d=>[d,d.open]);
                    for(const [d] of window.__galleryDetails)d.open=true;
                    return window.__galleryDetails.length;}''')
                if route == 'appearance':
                    page.locator('#chk-atom-radius-mapping').check()
                    page.locator('#chk-atom-colorscale').check()
                inspector = page.locator('#inspector-content')
                dimensions = inspector.evaluate('e=>({height:e.clientHeight,max:e.scrollHeight-e.clientHeight})')
                step = max(160, dimensions['height'] - 60)
                offsets = sorted({0, dimensions['max'], *range(0, dimensions['max'], step)})
                for index, offset in enumerate(offsets):
                    inspector.evaluate('(e,y)=>e.scrollTop=y', offset)
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    filename = f'{theme}-{route}-{width}x{height}-expanded-{index + 1}.png'
                    page.locator('#inspector').screenshot(path=str(destination / filename))
                    records.append({'theme': theme, 'route': route, 'file': filename,
                                    'width': width, 'height': height, 'state': 'expanded',
                                    'crop': 'inspector', 'scroll_top': offset, 'expanded_sections': details})
                page.evaluate('''()=>{for(const [d,open] of window.__galleryDetails)d.open=open;
                    delete window.__galleryDetails;}''')
                if route == 'appearance':
                    page.locator('#chk-atom-radius-mapping').uncheck()
                    page.locator('#chk-atom-colorscale').uncheck()
                inspector.evaluate('e=>e.scrollTop=0')
            for theme in ('light', 'dark'):
                page.evaluate('(theme)=>window.v_aseTheme.apply(theme)', theme)
                for route in routes:
                    page.evaluate('(route)=>window.__ASE_APP__.openEditorRoute(route)', route)
                    page.wait_for_function('(route)=>document.body.dataset.currentEditorRoute===route', arg=route)
                    # Two rendered frames let ResizeObserver and the layout settle.
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    filename = f'{theme}-{route}.png'
                    page.screenshot(path=str(destination / filename))
                    records.append({'theme': theme, 'route': route, 'file': filename, 'width': 1440, 'height': 960})
                    capture_expanded(route, theme, 1440, 960)
            for width, height in ((1024, 768), (390, 844), (800, 420)):
                page.set_viewport_size({'width': width, 'height': height})
                page.evaluate("window.v_aseTheme.apply('light')")
                for route in ('appearance', 'add-atoms', 'rdf', 'render-image'):
                    page.evaluate('(route)=>window.__ASE_APP__.openEditorRoute(route)', route)
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    filename = f'light-{route}-{width}x{height}.png'
                    page.screenshot(path=str(destination / filename))
                    records.append({'theme': 'light', 'route': route, 'file': filename, 'width': width, 'height': height})
                    capture_expanded(route, 'light', width, height)
            browser.close()
    finally:
        editor.close()
    receipt = {'source': str(source), 'routes': routes, 'screenshots': records, 'expanded_review': expanded, 'page_errors': errors}
    (destination / 'gallery.json').write_text(json.dumps(receipt, indent=2) + '\n')
    cards = ''.join(f'<figure><a href="{r["file"]}"><img loading="lazy" src="{r["file"]}" alt="{html.escape(r["route"])}"></a>'
                    f'<figcaption>{html.escape(r["route"])} · {r["theme"]} · {r["width"]} × {r["height"]}'
                    f'{" · expanded, scroll " + str(r["scroll_top"]) if r.get("state") == "expanded" else ""}</figcaption></figure>' for r in records)
    (destination / 'index.html').write_text('<!doctype html><meta charset="utf-8"><title>v_ase interface review</title>'
        '<style>body{margin:32px;background:#f4f4f3;color:#252627;font:14px system-ui}h1{font-size:26px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:24px}figure{margin:0}img{width:100%;border:1px solid #ddd;border-radius:8px}figcaption{padding:8px 0;color:#666}</style>'
        f'<h1>v_ase interface review</h1><p>{len(routes)} routes · {len(records)} screenshots. Original application UI; no third-party artwork.</p><main>{cards}</main>')
    for theme in ('light', 'dark'):
        entries = [r for r in records if r['theme'] == theme and r['width'] == 1440 and r.get('state') != 'expanded']
        for start in range(0, len(entries), 12):
            batch = entries[start:start + 12]
            board = Image.new('RGB', (1440, 1100), '#f4f4f3')
            draw = ImageDraw.Draw(board)
            for index, entry in enumerate(batch):
                x, y = (index % 3) * 480, (index // 3) * 275
                with Image.open(destination / entry['file']) as screenshot:
                    screenshot.thumbnail((468, 246))
                    board.paste(screenshot.convert('RGB'), (x + 6, y + 22))
                draw.text((x + 8, y + 4), entry['route'], fill='#252627')
            board.save(destination / f'contact-{theme}-{start // 12 + 1}.jpg', quality=90)
    if errors:
        raise RuntimeError(f'Gallery reported JavaScript errors: {errors}')
    print(f'{len(routes)} routes; {len(records)} screenshots; no page errors. {destination / "index.html"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/ui_redesign/gallery')
    parser.add_argument('--structure', type=Path, default=ROOT / 'docs/assets/examples/SrTiO3_primitive.traj')
    parser.add_argument('--expanded', action='store_true', help='Also capture nested sections, appearance mappings and every inspector scroll position.')
    args = parser.parse_args()
    capture(args.output.absolute(), args.structure.absolute(), expanded=args.expanded)
