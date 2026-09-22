"""Run integration tests against the installed-layout bundle, outside the source tree."""
from pathlib import Path
import os
import platform
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
pattern = "*/v_ase.app/Contents/MacOS/v_ase" if platform.system() == "Darwin" else "win-unpacked/v_ase.exe"
candidates = list((root / "dist").glob(pattern))
if len(candidates) != 1:
    raise SystemExit(f"Expected one packaged application, got {candidates}")
if platform.system() == "Darwin":
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(candidates[0].parents[2])], check=True)
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
