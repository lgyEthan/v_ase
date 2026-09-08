"""One-time local Python environment installer for the v_ase ChatGPT plugin.

This script uses only the standard library and can be copied into a plugin.
Installing a ChatGPT plugin does not execute it automatically.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def choose_python(explicit=None):
    candidates = [explicit] if explicit else [sys.executable, *[
        shutil.which(name) for name in ("python3.13", "python3.12", "python3.11", "python3.10", "python")]]
    for value in candidates:
        if not value:
            continue
        value = shutil.which(value) or value
        try:
            result = subprocess.run([value, "-c", "import sys; print('.'.join(map(str,sys.version_info[:2])))"],
                                    capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            continue
        try:
            major, minor = map(int, result.stdout.strip().split("."))
        except ValueError:
            continue
        if result.returncode == 0 and major == 3 and minor >= 10:
            return str(Path(value).resolve())
    raise ValueError("Install Python 3.10 or newer, then rerun this local installer. A plugin cannot install Python into ChatGPT.")


def install(args):
    directory = Path(args.data_dir).expanduser()
    if directory.is_symlink():
        raise ValueError("Choose a real private runtime directory, not a symbolic link.")
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    marker = directory / ".vase-runtime.json"
    if any(directory.iterdir()) and not marker.is_file() and not (directory / "connection.json").is_file():
        raise ValueError("Choose an empty directory or an existing v_ase ChatGPT runtime.")
    directory.chmod(0o700)
    marker.write_text(json.dumps({"schema": "v_ase.chatgpt-local.v1"}) + "\n")
    marker.chmod(0o600)
    runtime = directory / "runtime"
    if runtime.is_symlink():
        raise ValueError("The isolated Python runtime must not be a symbolic link.")
    python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if runtime.exists() and not (runtime / "pyvenv.cfg").is_file():
        raise ValueError("The runtime directory exists and is not a Python virtual environment.")
    if (runtime / "pyvenv.cfg").is_file():
        settings = dict(line.strip().split("=", 1) for line in (runtime / "pyvenv.cfg").read_text().splitlines() if "=" in line)
        if any(key.strip() == "include-system-site-packages" and value.strip().lower() == "true" for key, value in settings.items()):
            raise ValueError("The existing runtime includes system packages. Choose a new directory for an isolated environment.")
    if not python.exists():
        subprocess.run([choose_python(args.python), "-m", "venv", str(runtime)], check=True)
    source_root = Path(__file__).resolve().parents[1]
    source = args.source
    if source is None and (source_root / "v_ase" / "chatgpt.py").is_file() and (source_root / "pyproject.toml").is_file():
        source = source_root
    if source is not None:
        source = Path(source).expanduser().resolve()
        if not source.exists():
            raise ValueError("The requested source directory or wheel does not exist.")
        package = str(source) + "[mcp]"
    else:
        package = "v_ase-gui[mcp]>=0.3.5"
    # Run outside the source checkout: local egg-info must not make pip skip the
    # actual wheel installation. Child argv is a list, never a shell string.
    env = os.environ.copy()
    for name in ("CONTROL_PLANE_API_KEY", "OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
        env.pop(name, None)
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "--no-cache-dir", package],
                   cwd=directory, env=env, check=True)
    bridge = Path(__file__).with_name("chatgpt.py")
    if not bridge.is_file():
        bridge = Path(__file__).with_name("chatgpt_bridge.py")
    if not bridge.is_file():
        raise ValueError("The plugin installer is incomplete: chatgpt_bridge.py is missing.")
    destination = directory / "chatgpt_bridge.py"
    if bridge.resolve() != destination:
        shutil.copy2(bridge, destination)
    installer = directory / "install_local.py"
    if Path(__file__).resolve() != installer:
        shutil.copy2(__file__, installer)
    configure = [str(python), str(destination), "configure", "--data-dir", str(directory)]
    for option in ("tunnel_id", "app_id", "file", "port", "workspace"):
        value = getattr(args, option, None)
        if value is not None:
            if option in ("file", "workspace"):
                value = Path(value).expanduser().resolve()
            configure.extend(["--" + option.replace("_", "-"), str(value)])
    if args.interactive:
        configure.append("--interactive")
    # The scientific file workspace is the caller's folder, not the private
    # environment directory used for installation. Existing settings survive.
    subprocess.run(configure, cwd=Path.cwd(), env=env, check=True)
    launch = [str(python), str(destination), "start", "--data-dir", str(directory)]
    launcher = None
    if os.name == "posix":
        launcher = directory / "start-vase-chatgpt.command"
        launcher.write_text("#!/bin/sh\nexec " + shlex.join(launch) + ' "$@"\n')
        launcher.chmod(0o700)
    print(json.dumps({"python": str(python), "bridge": str(destination),
        "start_command": shlex.join(launch), "launcher": str(launcher) if launcher else None,
        "tunnel_client_installed": bool(shutil.which("tunnel-client")),
        "next": "Install tunnel-client if needed, configure your tunnel_id, then run the launcher in a terminal."}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".local/share/v_ase/chatgpt")
    parser.add_argument("--source", type=Path, help="optional local v_ase checkout or wheel; otherwise use PyPI")
    parser.add_argument("--python", help="Python executable for the isolated environment")
    parser.add_argument("--tunnel-id")
    parser.add_argument("--app-id")
    parser.add_argument("--file")
    parser.add_argument("--port", type=int)
    parser.add_argument("--workspace", type=Path, help="local directory available to file discovery and loading")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    try:
        install(args)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"v_ase local setup: {exc}") from exc


if __name__ == "__main__":
    main()
