"""Release payload identity must detect changed code despite equal versions."""
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest


def payload_fixture(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "desktop/scripts/verify_scientific_payload.py"
    spec = importlib.util.spec_from_file_location("desktop_payload_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = tmp_path / "v_ase.app"
    package = app / "Contents/Resources/python/lib/python3.11/site-packages/v_ase"
    package.mkdir(parents=True)
    files = {"_version.py": b'__version__ = "0.4.14"\n', "static/main.js": b"current scientific UI"}
    buffer = BytesIO()
    with ZipFile(buffer, "w") as wheel:
        for name, data in files.items():
            target = package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            wheel.writestr("v_ase/" + name, data)
    blob = buffer.getvalue()
    metadata = {"urls": [{"filename": "v_ase_gui-0.4.14-py3-none-any.whl",
                          "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/test.whl",
                          "digests": {"sha256": hashlib.sha256(blob).hexdigest()}}]}
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: BytesIO(
        json.dumps(metadata).encode() if url.endswith("/json") else blob))
    return module, app, package


def test_desktop_payload_accepts_the_complete_matching_wheel(tmp_path, monkeypatch):
    module, app, _ = payload_fixture(tmp_path, monkeypatch)
    assert module.verify(app, "0.4.14")["scientificFilesMatched"] == 2


@pytest.mark.parametrize("change", ["modified", "extra", "missing"])
def test_desktop_payload_rejects_drift_with_an_unchanged_version(tmp_path, monkeypatch, change):
    module, app, package = payload_fixture(tmp_path, monkeypatch)
    target = package / "static/main.js"
    if change == "modified":
        target.write_bytes(b"old scientific UI")
    elif change == "extra":
        (package / "unexpected.py").write_text("unexpected = True")
    else:
        target.unlink()
    with pytest.raises(ValueError, match="differs from PyPI"):
        module.verify(app, "0.4.14")
