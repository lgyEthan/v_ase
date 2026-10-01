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
try:
    report = json.loads((output / "result.json").read_text())
except (OSError, ValueError) as error:
    raise SystemExit("The application exited without complete JSON test evidence") from error
expected_version = json.loads((root / "package.json").read_text())["version"]
required = ("nativeControlA", "verticalCutoffTab", "droppedFileGrant", "detachedWindow",
            "detachedSave", "transferRollback", "openNewWindow", "independentWindowClose",
            "nativeKeyInput", "nativeSave", "scientificProject", "openNewTab",
            "quitCancellation", "nodeIsolation", "lastDocumentClosesWindow",
            "emptyLastWindowRequestsQuit", "multiFileOpen", "osOpenBatch", "cellAxisShortcuts")
if (report.get("version") != expected_version or report.get("geometryRoutes") != 75
        or report.get("commands") != 10 or report.get("oxygenPixels", 0) <= 100
        or any(report.get(key) is not True for key in required)):
    raise SystemExit("The packaged application did not complete every required regression check")
parity = report.get("visualParity", {})
axes = parity.get("axisChecks", [])
if (set(p.get("mode") for p in axes) != {"2d", "3d"}
        or any(p.get("bluePixels", 0) < 3 or not p.get("cameraPreserved") for p in axes)):
    raise SystemExit("The packaged application did not show the canvas Z shaft while preserving the camera")
pixels, layouts = parity.get("pixelChecks", []), parity.get("layoutChecks", [])
if (set(p.get("mode") for p in pixels) != {"2d", "3d"}
        or any(p.get("outlinePixels", 0) <= 100 or p.get("constraintPixels", 0) <= 100 for p in pixels)
        or set(p.get("zoom") for p in layouts) != {1, 1.25, 1.5}
        or any(p.get("scroll") != ["inspector-content"] or not p.get("reachable") or not p.get("relaxHost") for p in layouts)):
    raise SystemExit("The packaged application did not pass native selection/constraint pixels and panel layout checks")
if platform.system() == "Darwin":
    # Import caches or other runtime writes must not break the sealed bundle.
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(candidates[0].parents[2])], check=True)
