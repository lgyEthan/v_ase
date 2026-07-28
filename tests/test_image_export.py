import io

import numpy as np
from PIL import Image
import pytest

import v_ase.export as export_module
from v_ase.export import encode_export_image, optimize_png_bytes


def _source_png(width=720, height=480):
    y, x = np.indices((height, width), dtype=np.uint16)
    pixels = np.empty((height, width, 4), dtype=np.uint8)
    pixels[..., 0] = (x * 255 // max(1, width - 1)).astype(np.uint8)
    pixels[..., 1] = (y * 255 // max(1, height - 1)).astype(np.uint8)
    pixels[..., 2] = ((x + y) % 256).astype(np.uint8)
    pixels[..., 3] = np.where((x // 24 + y // 24) % 2, 255, 180).astype(np.uint8)
    image = Image.fromarray(pixels, mode="RGBA")
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=1)
    return output.getvalue(), pixels


def _decode_rgba(payload):
    with Image.open(io.BytesIO(payload)) as image:
        return np.asarray(image.convert("RGBA"))


def test_png_optimizer_preserves_every_pixel_and_never_increases_size():
    source, expected = _source_png()
    optimized = optimize_png_bytes(source)

    assert len(optimized) <= len(source)
    np.testing.assert_array_equal(_decode_rgba(optimized), expected)


def test_lossless_webp_preserves_resolution_pixels_and_reduces_smooth_scene():
    source, expected = _source_png()
    encoded, media_type = encode_export_image(source, "webp")

    assert media_type == "image/webp"
    assert len(encoded) < len(source) * 0.75
    np.testing.assert_array_equal(_decode_rgba(encoded), expected)


def test_image_export_rejects_unknown_format():
    source, _ = _source_png(64, 64)
    try:
        encode_export_image(source, "jpeg")
    except ValueError as exc:
        assert "png" in str(exc).lower()
        assert "webp" in str(exc).lower()
    else:
        raise AssertionError("Unknown image export format was accepted.")


def test_png_optimizer_bounds_decompressed_memory(monkeypatch):
    source, _ = _source_png(64, 64)
    monkeypatch.setattr(export_module, "MAX_PNG_DECOMPRESSED_BYTES", 128)

    with pytest.raises(ValueError, match="too large"):
        optimize_png_bytes(source)
