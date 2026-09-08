"""Personal ChatGPT connection through OpenAI's official Secure MCP Tunnel.

This module can also be copied into a plugin as a standalone bridge script.
It uses the existing v_ase MCP transport and never implements its own tunnel.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import getpass
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
import zipfile

SCHEMA = "v_ase.chatgpt-local.v1"
PLUGIN_NAME = "v-ase-local"
TUNNEL_SETTINGS = "https://platform.openai.com/settings/organization/tunnels"
CHATGPT_PLUGINS = "https://chatgpt.com/#settings/Connectors"
KEY_VARIABLE = "CONTROL_PLANE_API_KEY"
DEFAULT_DIRECTORY = Path.home() / ".local" / "share" / "v_ase" / "chatgpt"


def _identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_-]{8,128}", value):
        raise ValueError(f"Use the actual {prefix}... identifier shown by OpenAI.")
    return value


def _private_directory(directory):
    directory = Path(directory).expanduser()
    if directory.is_symlink():
        raise ValueError("The ChatGPT runtime directory must not be a symbolic link.")
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    # Refuse an arbitrary existing parent such as HOME or a source checkout.
    owned = (directory / "connection.json").is_file() or (directory / ".vase-runtime.json").is_file()
    if any(directory.iterdir()) and not owned:
        raise ValueError("Choose an empty directory or an existing v_ase ChatGPT runtime directory.")
    directory.chmod(0o700)
    return directory


def _write_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".vase-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(directory):
    path = Path(directory).expanduser() / "connection.json"
    if path.is_symlink():
        raise ValueError("The connection file must not be a symbolic link.")
    data = json.loads(path.read_text())
    allowed = {"schema", "tunnel_id", "app_id", "port", "file", "connect", "interactive", "working_directory"}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or set(data) - allowed:
        raise ValueError("This is not a v_ase ChatGPT connection configuration.")
    for name in ("file", "connect", "tunnel_id", "app_id"):
        if data.get(name) is not None and not isinstance(data[name], str):
            raise ValueError(f"The connection setting {name} must be a string or null.")
    if not isinstance(data.get("interactive"), bool):
        raise ValueError("The interactive setting must be a Boolean.")
    if not isinstance(data.get("working_directory"), str) or not Path(data["working_directory"]).is_absolute():
        raise ValueError("The working directory must be an absolute local path.")
    if isinstance(data.get("port"), bool) or not isinstance(data.get("port"), int) or not 1024 <= data["port"] <= 65535:
        raise ValueError("The local MCP port must be an integer between 1024 and 65535.")
    if data.get("tunnel_id"):
        _identifier(data["tunnel_id"], "tunnel_")
    if data.get("app_id"):
        _identifier(data["app_id"], "plugin_asdk_app")
    if data.get("connect") and (data.get("file") or data.get("interactive")):
        raise ValueError("An existing GUI connection cannot also open another file or change its mode.")
    return data


def _binary(value=None):
    path = value or shutil.which("tunnel-client")
    if not path or not Path(path).is_file() or not os.access(path, os.X_OK):
        raise ValueError("Install the official client first: brew install openai/tools/tunnel-client (macOS).")
    return str(Path(path).resolve())


def _environment(*, runtime_key=None):
    env = os.environ.copy()
    # Configuration is explicit. Do not inherit another tunnel/profile or pass
    # control-plane/admin/model credentials to the local GUI and MCP children.
    for name in list(env):
        if name.startswith(("CONTROL_PLANE_", "TUNNEL_CLIENT_", "MCP_SERVER_", "MCP_COMMAND", "HEALTH_", "CLOUDFLARED_", "HARPOON_")):
            env.pop(name)
    for name in ("OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
        env.pop(name, None)
    env["NO_PROXY"] = ",".join(filter(None, [env.get("NO_PROXY"), "localhost", "127.0.0.1", "::1"]))
    if runtime_key is not None:
        env[KEY_VARIABLE] = runtime_key
    return env


def _profile(directory, config, binary):
    if not config.get("tunnel_id"):
        raise ValueError(f"Create a tunnel at {TUNNEL_SETTINGS}, then configure its tunnel_id.")
    profiles = directory / "profiles"
    profiles.mkdir(exist_ok=True)
    command = [binary, "init", "--sample", "sample_mcp_remote_no_auth", "--profile", PLUGIN_NAME,
               "--profile-dir", str(profiles), "--tunnel-id", config["tunnel_id"],
               "--mcp-server-url", f"http://127.0.0.1:{config['port']}/mcp",
               "--health-listen-addr", "127.0.0.1:0", "--control-plane-api-key-ref", f"env:{KEY_VARIABLE}"]
    target = profiles / f"{PLUGIN_NAME}.yaml"
    if target.exists():
        if target.is_symlink():
            raise ValueError("The generated tunnel profile must not be a symbolic link.")
        command.append("--force")
    result = subprocess.run(command, env=_environment(), capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise ValueError("tunnel-client could not create the profile: " + result.stderr[-2000:])
    target.chmod(0o600)
    return target


def configure(args):
    if args.connect and args.interactive:
        raise ValueError("Change an existing GUI's mode in the GUI, not its connection configuration.")
    directory = _private_directory(args.data_dir)
    target = directory / "connection.json"
    old = _load(directory) if target.exists() else {"schema": SCHEMA, "port": 8766,
        "tunnel_id": None, "app_id": None, "file": None, "connect": None,
        "interactive": False, "working_directory": str(Path.cwd().resolve())}
    if args.tunnel_id is not None:
        old["tunnel_id"] = _identifier(args.tunnel_id, "tunnel_")
    if args.app_id is not None:
        old["app_id"] = _identifier(args.app_id, "plugin_asdk_app")
    if args.port is not None:
        if not 1024 <= args.port <= 65535:
            raise ValueError("Use a local MCP port between 1024 and 65535.")
        old["port"] = args.port
    workspace = getattr(args, "workspace", None)
    if workspace is not None:
        workspace = Path(workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise ValueError("The structure workspace must be an existing directory.")
        old["working_directory"] = str(workspace)
    if args.connect:
        from v_ase.ai_tools import FunctionTools
        with FunctionTools(args.connect, artifact_dir=directory / "artifacts"):
            pass  # Validate the same loopback/document URL contract as native MCP.
        old.update(connect=args.connect, file=None, interactive=False)
    elif args.file is not None:
        file = Path(args.file).expanduser().resolve()
        if not file.is_file():
            raise ValueError("The structure/project file does not exist.")
        old.update(file=str(file), connect=None, interactive=bool(args.interactive))
    elif args.interactive:
        if old.get("connect"):
            raise ValueError("Change an existing GUI's mode in the GUI, not its connection configuration.")
        old["interactive"] = True
    _write_json(target, old)
    if old.get("tunnel_id") and shutil.which("tunnel-client"):
        _profile(directory, old, _binary())
    return {"status": "configured" if old.get("tunnel_id") else "awaiting_tunnel_id",
            "directory": str(directory), "tunnel_id": old.get("tunnel_id"),
            "api_key_stored": False, "next": "start" if old.get("tunnel_id") else TUNNEL_SETTINGS}


async def probe_mcp(url):
    import mcp
    from v_ase.ai_tools import FunctionTools
    async with mcp.Client(url) as client:
        listing = await client.list_tools()
        names = {tool.name for tool in listing.tools}
        required = {"vase_scene_snapshot", "vase_render", "vase_inspect_image", "vase_search_tools"}
        if not required <= names:
            raise ValueError("The local endpoint is not the expected v_ase MCP server.")
        connection = await client.read_resource("vase://connection")
        target = json.loads(connection.contents[0].text)["command_url"]
        with FunctionTools(target) as bridge:
            # tools/list is served by the adapter even after its GUI has died.
            # Check the actual backend contract without requiring an open render tab.
            await asyncio.to_thread(bridge._verify_contract)
        return {"tool_count": len(names), "required_tools_present": True, "gui_backend_ready": True}


def _health(directory, endpoint="readyz"):
    file = directory / "tunnel-health.url"
    if not file.is_file() or file.is_symlink():
        return None
    url = file.read_text().strip()
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Invalid local tunnel health URL.")
    with build_opener(ProxyHandler({})).open(url.rstrip("/") + "/" + endpoint, timeout=2) as response:
        return {"ready": response.status == 200, "ui_url": url.rstrip("/") + "/ui"}


def doctor(args):
    from importlib.metadata import version
    directory = Path(args.data_dir).expanduser().resolve()
    config = _load(directory)
    checks = {"configuration": True, "tunnel_id": bool(config.get("tunnel_id")),
              "runtime_key_in_environment": bool(os.environ.get(KEY_VARIABLE)),
              "registered_chatgpt_app": bool(config.get("app_id"))}
    versions = {}
    for name in ("v-ase-gui", "mcp", "ase", "numpy", "scipy"):
        try:
            versions[name] = version(name)
        except Exception:
            checks[name] = False
    binary = shutil.which("tunnel-client")
    checks["tunnel_client"] = bool(binary)
    report = {"checks": checks, "versions": versions, "directory": str(directory),
              "note": "A configured local server is not evidence of a connected ChatGPT tunnel."}
    if binary:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
        report["tunnel_client_version"] = result.stdout.strip()
    try:
        report["tunnel"] = _health(directory)
    except (OSError, ValueError):
        report["tunnel"] = None
    try:
        report["local"] = {"ready": True, **asyncio.run(asyncio.wait_for(
            probe_mcp(f"http://127.0.0.1:{config['port']}/mcp"), timeout=5))}
    except Exception:
        report["local"] = {"ready": False}
    tunnel_ready = report["tunnel"] and report["tunnel"]["ready"]
    report["status"] = ("tunnel_ready" if tunnel_ready and report["local"]["ready"]
                        else "gui_unavailable" if tunnel_ready
                        else "local_ready" if report["local"]["ready"]
                        else "configured" if checks["tunnel_id"] else "awaiting_tunnel_id")
    if args.online:
        key = os.environ.get(KEY_VARIABLE)
        if not key:
            raise ValueError(f"Set {KEY_VARIABLE} locally for --online; never paste the key into chat.")
        profile = _profile(directory, config, _binary())
        result = subprocess.run([_binary(), "doctor", "--profile-file", str(profile), "--explain"],
                                env=_environment(runtime_key=key), capture_output=True, text=True, timeout=60)
        report["online"] = {"passed": result.returncode == 0,
                            "details": (result.stdout + result.stderr).replace(key, "[REDACTED]")[-6000:]}
    return report


@contextmanager
def _termination_signals():
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    def stop(signum, frame):
        raise KeyboardInterrupt
    previous = {}
    try:
        for sig in (signal.SIGTERM, getattr(signal, "SIGHUP", signal.SIGTERM)):
            if sig not in previous:
                previous[sig] = signal.signal(sig, stop)
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@contextmanager
def _run_lock(directory):
    if os.name != "posix":
        raise ValueError("The integrated foreground launcher currently supports macOS and Linux.")
    import fcntl
    with open(directory / "run.lock", "a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("This v_ase ChatGPT runtime is already running.") from exc
        yield


def _stop(process):
    if process is None:
        return
    # Each child starts its own session; this also closes an owned GUI spawned
    # by the MCP adapter, while an explicitly connected existing GUI survives.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def start(args):
    directory = Path(args.data_dir).expanduser().resolve()
    config = _load(directory)
    if not math.isfinite(args.startup_timeout) or not 1 <= args.startup_timeout <= 600:
        raise ValueError("Startup timeout must be between 1 and 600 seconds.")
    key = None
    binary = None
    if not args.local_only:
        binary = _binary()
        if not config.get("tunnel_id"):
            raise ValueError(f"Configure the tunnel_id from {TUNNEL_SETTINGS} first.")
        key = os.environ.get(KEY_VARIABLE)
        if not key:
            if not sys.stdin.isatty():
                raise ValueError("Run start in a local terminal for hidden API-key input, or set CONTROL_PLANE_API_KEY locally.")
            key = getpass.getpass("OpenAI tunnel runtime API key (hidden; not saved): ").strip()
        if not key:
            raise ValueError("A tunnel runtime API key is required.")
    with _termination_signals(), _run_lock(directory):
        with socket.socket() as reservation:
            try:
                reservation.bind(("127.0.0.1", config["port"]))
            except OSError as exc:
                raise ValueError("The configured MCP port is occupied. Choose another port with configure --port.") from exc
        state_path = directory / "state.json"
        mcp_url = f"http://127.0.0.1:{config['port']}/mcp"
        # Scientific files may live beside another checkout or a file named
        # v_ase.py. Run the installed package, never Python code from that folder.
        command = [sys.executable, "-I", "-m", "v_ase.cli", "mcp", "--transport", "streamable-http",
                   "--port", str(config["port"]), "--discovery", "all", "--artifact-dir", str(directory / "artifacts")]
        if config.get("connect"):
            command += ["--connect", config["connect"]]
        if config.get("file"):
            command += ["--file", config["file"]]
        if config.get("interactive"):
            command += ["--interactive"]
        if args.no_browser:
            command += ["--no-browser"]
        status = {"status": "starting", "mcp_url": mcp_url, "tunnel_id": config.get("tunnel_id"),
                  "local_only": args.local_only}
        _write_json(state_path, status)
        mcp_process = tunnel_process = None
        try:
            with open(directory / "mcp.log", "w", encoding="utf-8") as mcp_log, open(directory / "tunnel.log", "w", encoding="utf-8") as tunnel_log:
                mcp_process = subprocess.Popen(command, cwd=config["working_directory"], env=_environment(),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
                gui_urls = []
                def drain():
                    for line in mcp_process.stdout:
                        try:
                            mcp_log.write(line); mcp_log.flush()
                        except ValueError:
                            return  # The owner is shutting down this log and child.
                        if line.startswith("v_ase human GUI: "):
                            gui_urls.append(line.split(": ", 1)[1].strip())
                            print(line.rstrip(), flush=True)
                reader = threading.Thread(target=drain, daemon=True); reader.start()
                deadline = time.monotonic() + args.startup_timeout
                while True:
                    if mcp_process.poll() is not None:
                        raise ValueError(f"Local MCP exited during startup. See {directory / 'mcp.log'}.")
                    try:
                        result = asyncio.run(asyncio.wait_for(probe_mcp(mcp_url), timeout=3))
                        break
                    except Exception as exc:
                        if time.monotonic() >= deadline:
                            raise ValueError(f"Local MCP did not become ready. See {directory / 'mcp.log'}.") from exc
                        time.sleep(.1)
                status.update(status="local_ready", **result)
                if gui_urls:
                    status["human_url"] = gui_urls[-1]
                _write_json(state_path, status)
                print(json.dumps(status), flush=True)
                if not args.local_only:
                    profile = _profile(directory, config, binary)
                    health_file = directory / "tunnel-health.url"
                    health_file.unlink(missing_ok=True)
                    tunnel_process = subprocess.Popen([binary, "run", "--profile-file", str(profile),
                        "--health.listen-addr", "127.0.0.1:0", "--health.url-file", str(health_file)],
                        env=_environment(runtime_key=key), stdout=tunnel_log, stderr=subprocess.STDOUT,
                        start_new_session=True)
                    deadline = time.monotonic() + args.startup_timeout
                    while True:
                        if tunnel_process.poll() is not None:
                            raise ValueError(f"Tunnel client exited. Check runtime-key permissions in {directory / 'tunnel.log'}.")
                        try:
                            health = _health(directory)
                            if health and health["ready"]:
                                status.update(status="tunnel_ready", **health)
                                _write_json(state_path, status)
                                print(json.dumps(status), flush=True)
                                break
                        except OSError:
                            pass
                        if time.monotonic() >= deadline:
                            raise ValueError(f"Tunnel did not become ready. Check {directory / 'tunnel.log'}; local readiness alone is insufficient.")
                        time.sleep(.25)
                print("Keep this terminal and the local GUI open. Ctrl-C stops this runtime.", flush=True)
                while mcp_process.poll() is None and (tunnel_process is None or tunnel_process.poll() is None):
                    time.sleep(.25)
                raise ValueError("A runtime process stopped. See the local runtime logs.")
        except KeyboardInterrupt:
            status["status"] = "stopped"
        except Exception as exc:
            status.update(status="failed", error=str(exc))
            raise
        finally:
            _stop(tunnel_process); _stop(mcp_process)
            _write_json(state_path, status)
    return status


def package_plugin(args):
    from v_ase.ai import ai_skill_path
    directory = Path(args.data_dir).expanduser().resolve()
    config = _load(directory)
    app_id = args.app_id or config.get("app_id")
    if not app_id:
        raise ValueError("First register the running tunnel in ChatGPT, then pass its plugin_asdk_app... technical ID with --app-id.")
    _identifier(app_id, "plugin_asdk_app")
    target = Path(args.output or Path.home() / "plugins" / PLUGIN_NAME).expanduser()
    if target.name != PLUGIN_NAME or target.is_symlink():
        raise ValueError(f"The plugin output must be a real directory named {PLUGIN_NAME}.")
    if target.exists() and any(target.iterdir()):
        raise ValueError("The plugin output already contains files; choose a fresh output directory.")
    archive = target.parent / f"{PLUGIN_NAME}.zip"
    if archive.exists():
        raise ValueError("The output ZIP already exists; choose a fresh output parent.")
    bootstrap = Path(__file__).with_name("chatgpt_bootstrap.py")
    if not bootstrap.is_file():
        bootstrap = Path(__file__).with_name("install_local.py")
    if not bootstrap.is_file():
        raise ValueError("The local installer is missing from this bridge distribution.")
    target.mkdir(parents=True, exist_ok=True)
    (target / ".codex-plugin").mkdir()
    (target / "scripts").mkdir()
    skill = Path(ai_skill_path()).parent
    shutil.copytree(skill, target / "skills" / skill.name)
    shutil.copy2(__file__, target / "scripts" / "chatgpt_bridge.py")
    shutil.copy2(bootstrap, target / "scripts" / "install_local.py")
    manifest = {"name": PLUGIN_NAME, "version": "0.1.0", "description": "Atomic visualization through your private local v_ase MCP tunnel.",
        "author": {"name": "v_ase contributors"}, "license": "AGPL-3.0-or-later",
        "homepage": "https://github.com/lgyEthan/v_ase", "skills": "./skills/", "apps": "./.app.json",
        "interface": {"displayName": "v_ase Local", "shortDescription": "Atomic figures in your local v_ase GUI.",
            "longDescription": "Use a personal Secure MCP Tunnel to inspect, edit, analyze and render your local atomic structures. Requires a separately prepared local Python runtime.",
            "developerName": "v_ase contributors", "category": "Productivity", "capabilities": ["Read", "Write"],
            "defaultPrompt": ["Inspect my current atomic structure and render a figure.", "Plot the RDF of the loaded structure."]}}
    _write_json(target / ".codex-plugin" / "plugin.json", manifest)
    _write_json(target / ".app.json", {"apps": {"v_ase": {"id": app_id}}})
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(target.rglob("*")):
            if file.is_file() and not file.is_symlink() and "__pycache__" not in file.parts:
                bundle.write(file, str(Path(PLUGIN_NAME) / file.relative_to(target)))
    config["app_id"] = app_id
    _write_json(directory / "connection.json", config)
    return {"plugin_directory": str(target.resolve()), "zip": str(archive.resolve()),
            "app_id": app_id, "runtime_or_keys_included": False, "public_directory_eligible": False}


def add_parser(subparsers):
    parser = subparsers.add_parser("chatgpt", help="prepare a personal ChatGPT plugin and Secure MCP Tunnel")
    commands = parser.add_subparsers(dest="chatgpt_command", required=True)
    for name, function in (("configure", configure), ("doctor", doctor), ("start", start), ("plugin", package_plugin)):
        command = commands.add_parser(name)
        command.add_argument("--data-dir", type=Path, default=DEFAULT_DIRECTORY)
        command.set_defaults(func=run_command, chatgpt_function=function)
        if name == "configure":
            command.add_argument("--tunnel-id")
            command.add_argument("--app-id")
            command.add_argument("--port", type=int)
            command.add_argument("--workspace", type=Path, help="local directory available to file discovery and loading")
            inputs = command.add_mutually_exclusive_group()
            inputs.add_argument("--connect")
            inputs.add_argument("--file")
            command.add_argument("--interactive", action="store_true")
        elif name == "doctor":
            command.add_argument("--online", action="store_true")
        elif name == "start":
            command.add_argument("--local-only", action="store_true", help="test local MCP without starting a tunnel")
            command.add_argument("--no-browser", action="store_true")
            command.add_argument("--startup-timeout", type=float, default=90)
        elif name == "plugin":
            command.add_argument("--app-id")
            command.add_argument("--output", type=Path)
    return parser


def run_command(args):
    try:
        result = args.chatgpt_function(args)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"v_ase chatgpt: {exc}") from exc
    return 0


if __name__ == "__main__":
    root = argparse.ArgumentParser(description=__doc__)
    add_parser(root.add_subparsers(dest="command", required=True))
    arguments = root.parse_args(["chatgpt", *sys.argv[1:]])
    raise SystemExit(run_command(arguments))
