"""Run integration tests against the installed-layout bundle, outside the source tree."""
from pathlib import Path
import argparse
import os
import platform
import json
import plistlib
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--app", type=Path, help="Explicit .app bundle or Windows .exe, including a signed release candidate")
args = parser.parse_args()
if args.app:
    app = args.app.resolve(strict=True)
    candidates = [app / "Contents/MacOS/v_ase" if platform.system() == "Darwin" else app]
else:
    pattern = "*/v_ase.app/Contents/MacOS/v_ase" if platform.system() == "Darwin" else "win-unpacked/v_ase.exe"
    candidates = list((root / "dist").glob(pattern))
if len(candidates) != 1:
    raise SystemExit(f"Expected one packaged application, got {candidates}")
if platform.system() == "Darwin":
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(candidates[0].parents[2])], check=True)
    contents = candidates[0].parents[1]
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    types = info['CFBundleDocumentTypes']
    project = next(item for item in types if 'vase' in item.get('CFBundleTypeExtensions', []))
    structures = next(item for item in types if 'extxyz' in item.get('CFBundleTypeExtensions', []))
    assert project['LSHandlerRank'] == 'Owner'
    assert structures['LSHandlerRank'] == 'Alternate'
    expected = json.loads((root / 'file-formats.json').read_text())['structureExtensions']
    assert set(structures['CFBundleTypeExtensions']) == set(expected)
    icons = [info['CFBundleIconFile'], project['CFBundleTypeIconFile'], structures['CFBundleTypeIconFile']]
    assert len(set(icons)) == 3, icons
    for icon in icons:
        assert (contents / 'Resources' / icon).is_file(), icon
output = Path(os.environ.get("V_ASE_SMOKE_DIR", root / "smoke-output" / "packaged")).resolve()
output.mkdir(parents=True, exist_ok=True)
(output / "result.json").unlink(missing_ok=True)
environment = {**os.environ, "V_ASE_SMOKE_DIR": str(output)}
timeout = 600 if environment.get("V_ASE_SOFTWARE_GL") == "1" else 240
with tempfile.TemporaryDirectory(prefix="vase-packaged-") as directory:
    result = subprocess.run([str(candidates[0]), "--smoke-test"], cwd=directory,
                            env=environment, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    print(result.stdout)
    print(result.stderr)
    (output / "application.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
if not (output / "result.json").is_file():
    raise SystemExit("The application exited without completing its checks")
if platform.system() == "Darwin":
    # Import caches or other runtime writes must not break the sealed bundle.
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(candidates[0].parents[2])], check=True)
