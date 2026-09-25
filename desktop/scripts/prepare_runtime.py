"""Build a relocatable Python runtime; no user Python installation is required."""
from __future__ import annotations

import hashlib
import json
import os
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
    options = ["--only-binary=:all:"]
    environment = dict(os.environ)
    if key == ("Darwin", "x86_64"):
        # Current cryptography no longer publishes Intel Mac wheels. Build the
        # current patched release with static OpenSSL, never downgrade it.
        openssl = subprocess.check_output(["brew", "--prefix", "openssl@3"], text=True).strip()
        if not (Path(openssl) / "lib/libcrypto.a").is_file():
            raise SystemExit("Intel Mac build requires Homebrew openssl@3, Rust and Xcode tools")
        environment.update(OPENSSL_STATIC="1", OPENSSL_DIR=openssl)
        options += ["--no-binary=cryptography"]
    subprocess.run([str(interpreter), "-I", "-m", "pip", "install", *options,
                    "--disable-pip-version-check", "-r", str(ROOT / "requirements-runtime.txt")],
                   check=True, env=environment)
    subprocess.run([str(interpreter), "-I", "-m", "pip", "check"], check=True)
    subprocess.run([str(interpreter), "-I", "-c",
                    "from v_ase._version import __version__; assert __version__ == '0.4.6'; "
                    "import ase, matscipy, skimage, rhino3dm, mcp; print('Runtime verified:', __version__)"], check=True)
    if key == ("Darwin", "x86_64"):
        extension = next((runtime / "python").glob("lib/python3.11/site-packages/cryptography/hazmat/bindings/_rust*.so"))
        links = subprocess.check_output(["otool", "-L", str(extension)], text=True)
        if "libcrypto" in links or "libssl" in links or "/usr/local/" in links or "/opt/homebrew/" in links:
            raise SystemExit(f"Cryptography must not require the build machine's libraries:\n{links}")
        print("Intel cryptography has no external OpenSSL dependency", flush=True)
    # The scientific package is the published wheel. Ship the synchronized
    # agent documentation with the additional desktop connection instructions.
    package = Path(subprocess.check_output([str(interpreter), "-I", "-X", "utf8", "-c",
        "import pathlib,v_ase; print(pathlib.Path(v_ase.__file__).parent)"], text=True).strip())
    skill = "visualizing-atomic-structures-with-v-ase"
    shutil.copytree(ROOT.parent / "v_ase/skills" / skill, package / "skills" / skill, dirs_exist_ok=True)
    (runtime / "python" / "v_ase-desktop-runtime.json").write_text(json.dumps({
        "v_ase": "0.4.6", "python": PYTHON, "source": name, "sha256": expected,
        "platform": target,
        "agent_documentation": "Canonical repository Skill with desktop connection guidance",
    }, indent=2) + "\n")
    shutil.copy2(ROOT.parent / "LICENSE", ROOT / "LICENSE")


if __name__ == "__main__":
    main()
