"""Compare an app's complete v_ase payload with the published release wheel."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import platform
from pathlib import Path
import re
from urllib.request import urlopen
from zipfile import ZipFile


def verify(app: Path, version: str) -> dict:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Expected a release version")
    runtime = (app / "Contents/Resources/python" if app.suffix == ".app"
               else app.parent / "resources/python").resolve(strict=True)
    packages = [*runtime.glob("lib/python*/site-packages/v_ase"),
                *runtime.glob("Lib/site-packages/v_ase")]
    if len(packages) != 1:
        raise ValueError("Expected one bundled scientific package")
    package = packages[0]
    with urlopen(f"https://pypi.org/pypi/v-ase-gui/{version}/json", timeout=60) as response:
        metadata = json.load(response)
    filename = f"v_ase_gui-{version}-py3-none-any.whl"
    wheels = [item for item in metadata["urls"] if item["filename"] == filename
              and item["packagetype"] == "bdist_wheel" and not item.get("yanked")]
    if len(wheels) != 1 or not wheels[0]["url"].startswith("https://files.pythonhosted.org/"):
        raise ValueError("Expected the unique published wheel")
    with urlopen(wheels[0]["url"], timeout=120) as response:
        payload = response.read()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != wheels[0]["digests"]["sha256"]:
        raise ValueError("Published wheel digest mismatch")
    matched = 0
    with ZipFile(BytesIO(payload)) as wheel:
        expected = {name.removeprefix("v_ase/"): wheel.read(name)
                    for name in wheel.namelist()
                    if name.startswith("v_ase/") and not name.endswith("/")}
        actual = {path.relative_to(package).as_posix() for path in package.rglob("*")
                  if path.is_file()}
        if actual != set(expected):
            raise ValueError("Bundled scientific file list differs from PyPI")
        for name, data in expected.items():
            path = package / name
            if not path.resolve().is_relative_to(runtime) or path.read_bytes() != data:
                raise ValueError(f"Bundled scientific file differs from PyPI: {name}")
            matched += 1
    if not matched or "_version.py" not in expected:
        raise ValueError("Incomplete scientific payload")
    return {"version": version, "wheel": filename, "wheelSha256": digest,
            "scientificFilesMatched": matched, "payload": "identical to PyPI"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("app", type=Path, nargs="?")
    parser.add_argument("--version", default=json.loads((root / "package.json").read_text())["version"])
    args = parser.parse_args()
    if args.app is None:
        pattern = "*/v_ase.app" if platform.system() == "Darwin" else "win-unpacked/v_ase.exe"
        candidates = list((root / "dist").glob(pattern))
        if len(candidates) != 1:
            raise SystemExit("Expected one packaged application")
        args.app = candidates[0]
    print(json.dumps(verify(args.app, args.version), indent=2))
