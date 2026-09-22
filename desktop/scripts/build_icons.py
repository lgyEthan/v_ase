"""Encode platform icon containers from the approved transparent PNG master."""
from pathlib import Path
from PIL import Image

assets = Path(__file__).resolve().parents[1] / 'assets'
with Image.open(assets / 'icon.png') as source:
    icon = source.convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS)
    icon.save(assets / 'icon.ico', sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(assets / 'icon.icns')
