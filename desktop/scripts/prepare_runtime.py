"""Build a relocatable Python runtime; no user Python installation is required."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "20260901"
PYTHON = "3.11.16"
RUNTIMES = {
    ("Darwin", "arm64"): ("aarch64-apple-darwin", "50424fa409e8ae84b82a3052522f64695b47dff2158b70bb7358e0ebd6c085c9"),
    ("Darwin", "x86_64"): ("x86_64-apple-darwin", "167cc15cf4eeb72944a67bbd2f7120c45fded17d5043d5db64b3144d7adc30ae"),
    ("Windows", "AMD64"): ("x86_64-pc-windows-msvc", "6be524fa6752af802146a4adc7d098565425b0b1c166e19a5a7a4c8cccb86bf6"),
}


def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Run this build helper with Python 3.12 or newer (the bundled runtime is Python 3.11).')
    key = (platform.system(), platform.machine())
    if key not in RUNTIMES:
        raise SystemExit(f"Build on the target OS and architecture: {key!r} is unsupported")
    target, expected = RUNTIMES[key]
    name = f"cpython-{PYTHON}+{RELEASE}-{target}-install_only.tar.gz"
    archive = ROOT / ".cache" / name
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists():
        url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{RELEASE}/{name}"
        print(f"Downloading official Python runtime: {name}", flush=True)
        with urlopen(url, timeout=120) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise SystemExit("Python archive digest mismatch; remove the cached archive and investigate")
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    interpreter = runtime / "python" / ("python.exe" if key[0] == "Windows" else "bin/python3")
    if not interpreter.exists():
        with tarfile.open(archive) as source:
            source.extractall(runtime, filter="data")
    subprocess.run([str(interpreter), "-I", "-m", "pip", "install", "--only-binary=:all:",
                    "--disable-pip-version-check", "-r", str(ROOT / "requirements-runtime.txt")], check=True)
    subprocess.run([str(interpreter), "-I", "-m", "pip", "check"], check=True)
    subprocess.run([str(interpreter), "-I", "-c",
                    "from v_ase._version import __version__; assert __version__ == '0.4.1'; "
                    "import ase, matscipy, skimage, rhino3dm, mcp; print('Runtime verified:', __version__)"], check=True)
    (runtime / "python" / "v_ase-desktop-runtime.json").write_text(json.dumps({
        "v_ase": "0.4.1", "python": PYTHON, "source": name, "sha256": expected,
        "platform": target,
    }, indent=2) + "\n")
    shutil.copy2(ROOT.parent / "LICENSE", ROOT / "LICENSE")


if __name__ == "__main__":
    main()
