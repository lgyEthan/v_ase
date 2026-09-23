"""Rasterize the code-native document symbol; leave the castle artwork unchanged.

Build dependency: Playwright Chromium and Pillow (not shipped at runtime).
"""
from pathlib import Path
import base64
from PIL import Image
from playwright.sync_api import sync_playwright

assets = Path(__file__).resolve().parents[1] / 'assets'
svg = (assets / 'document.svg').read_text()
# A self-contained SVG avoids any network or local-file renderer permissions.
svg = svg.replace('icon.png', 'data:image/png;base64,' + base64.b64encode((assets / 'icon.png').read_bytes()).decode())
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1024, 'height': 1024}, device_scale_factor=1)
    for stem, label, color in [('document', 'VASE', '#176b6b'), ('structure-document', 'ATOM', '#445b75')]:
        content = svg.replace('>VASE<', f'>{label}<').replace('#176b6b', color)
        page.set_content('<style>html,body{margin:0;background:transparent}</style>' + content)
        page.screenshot(path=str(assets / f'{stem}.png'), omit_background=True)
        with Image.open(assets / f'{stem}.png') as icon:
            icon.save(assets / f'{stem}.ico', sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
            icon.save(assets / f'{stem}.icns')
    browser.close()
