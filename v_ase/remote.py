"""One-command SSH launcher for remote v_ase sessions."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .viewer import announce_viewer_url, find_free_port, open_browser_url


_REMOTE_TARGET = re.compile(
    r"^(?P<host>(?:[^@\s/:]+@)?(?:\[[^\]]+\]|[^/:\s]+)):(?P<path>.*)$"
)
_LOOPBACK_URL = re.compile(
    r"https?://(?:127\.0\.0\.1|localhost):\d+(?:/[^\s]*)?"
)
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True)
class RemoteTarget:
    """An scp-style SSH host and remote path."""

    host: str
    path: str


class RemoteLaunchError(RuntimeError):
    """Raised when an automatic SSH viewer session cannot be established."""


_REMOTE_CONFIG_SCHEMA = "v_ase.remote-runtimes.v1"


def remote_runtime_config_path() -> Path:
    """Return the local per-user remote runtime configuration path."""
    override = os.environ.get("V_ASE_REMOTE_CONFIG")
    if override:
        return Path(override).expanduser()
    if os.name == "nt" and os.environ.get("APPDATA"):
        root = Path(os.environ["APPDATA"])
    elif os.environ.get("XDG_CONFIG_HOME"):
        root = Path(os.environ["XDG_CONFIG_HOME"]).expanduser()
    else:
        root = Path.home() / ".config"
    return root / "v_ase" / "remote-runtimes.json"


def _validated_remote_python(value: str) -> str:
    path = str(value or "").strip()
    if not path:
        raise ValueError("The remote Python path cannot be empty.")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise ValueError("The remote Python path contains an invalid character.")
    if not path.startswith("/"):
        raise ValueError(
            "Use an absolute remote Python path, for example "
            "/home/user/miniconda3/envs/vase/bin/python."
        )
    return path


def load_remote_runtime_config(path: Path | None = None) -> dict[str, str]:
    """Read saved host-to-Python mappings without executing remote shell setup."""
    config_path = path or remote_runtime_config_path()
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteLaunchError(
            f"could not read remote runtime settings at {config_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != _REMOTE_CONFIG_SCHEMA:
        raise RemoteLaunchError(
            f"remote runtime settings at {config_path} use an unsupported format"
        )
    hosts = payload.get("hosts")
    if not isinstance(hosts, dict):
        raise RemoteLaunchError(
            f"remote runtime settings at {config_path} do not contain a host map"
        )
    result: dict[str, str] = {}
    for host, entry in hosts.items():
        if not isinstance(host, str) or not isinstance(entry, dict):
            continue
        try:
            result[host] = _validated_remote_python(entry.get("python", ""))
        except ValueError:
            continue
    return result


def save_remote_runtime_config(
    hosts: dict[str, str],
    path: Path | None = None,
) -> Path:
    """Atomically save validated host runtime mappings."""
    config_path = path or remote_runtime_config_path()
    normalized = {
        str(host).strip(): {"python": _validated_remote_python(python)}
        for host, python in hosts.items()
        if str(host).strip()
    }
    payload = {
        "schema": _REMOTE_CONFIG_SCHEMA,
        "hosts": dict(sorted(normalized.items())),
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_path.parent,
            prefix=f".{config_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            temporary_path = Path(handle.name)
        temporary_path.chmod(0o600)
        temporary_path.replace(config_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return config_path


def configure_remote_runtime(host: str, python: str) -> Path:
    """Persist one SSH host's exact Python executable."""
    normalized_host = str(host or "").strip()
    if not normalized_host or normalized_host.startswith("-") or any(
        character.isspace() for character in normalized_host
    ):
        raise ValueError("Enter one valid SSH host or user@host value.")
    hosts = load_remote_runtime_config()
    hosts[normalized_host] = _validated_remote_python(python)
    return save_remote_runtime_config(hosts)


def remove_remote_runtime(host: str) -> tuple[Path, bool]:
    """Remove one saved SSH host runtime mapping."""
    normalized_host = str(host or "").strip()
    hosts = load_remote_runtime_config()
    removed = hosts.pop(normalized_host, None) is not None
    return save_remote_runtime_config(hosts), removed


def remote_command_prefix(
    args: argparse.Namespace,
    target: RemoteTarget,
) -> list[str]:
    """Resolve transient, saved, then PATH-based remote CLI execution."""
    explicit = getattr(args, "remote_python", None)
    configured = load_remote_runtime_config().get(target.host)
    selected = explicit or configured
    python = _validated_remote_python(selected) if selected else None
    if python:
        return [python, "-m", "v_ase.cli"]
    return ["v_ase"]


def parse_remote_target(value: str | None) -> RemoteTarget | None:
    """Parse ``HOST:/path`` without misclassifying normal local paths."""
    if not value or _WINDOWS_DRIVE.match(value):
        return None

    local_candidate = Path(value).expanduser()
    if local_candidate.exists():
        return None

    match = _REMOTE_TARGET.fullmatch(value)
    if match is None:
        return None

    host = match.group("host")
    path = match.group("path")
    destination = host.rsplit("@", 1)[-1]
    if not path or host.startswith("-") or destination.startswith("-"):
        return None
    return RemoteTarget(host=host, path=path)


def _remote_gui_argv(
    args: argparse.Namespace,
    target: RemoteTarget,
    *,
    no_browser: bool,
    stream_frames: bool,
    modern_bond_defaults: bool,
    remote_port: int | None = None,
    command_prefix: list[str] | None = None,
) -> list[str]:
    command = [
        *(command_prefix or remote_command_prefix(args, target)),
        "gui",
        "--index",
        str(args.index),
    ]
    if no_browser:
        command.append("--no-browser")
    if stream_frames:
        command.append("--stream-frames")
    if remote_port is not None:
        command.extend(["--port", str(remote_port)])
    if args.format:
        command.extend(["--format", str(args.format)])
    if getattr(args, "volumetric_precision", "fp32") != "fp32":
        command.extend([
            "--volumetric-precision",
            str(args.volumetric_precision),
        ])
    if args.output:
        command.extend(["--output", str(args.output)])
    if args.output_format:
        command.extend(["--output-format", str(args.output_format)])
    if args.show_bonds and not modern_bond_defaults:
        command.append("--show-bonds")
    elif not args.show_bonds and modern_bond_defaults:
        command.append("--hide-bonds")
    if args.hide_cell:
        command.append("--hide-cell")
    if args.hide_axes:
        command.append("--hide-axes")
    if args.interactive:
        command.append("--interactive")
    if args.cli_mode:
        # The local process owns the machine-readable handshake/event stream.
        # The remote process only needs to keep the tunneled server alive.
        command.append("--no-block")
    command.extend(["--", target.path])
    return command


def build_remote_gui_command(
    args: argparse.Namespace,
    target: RemoteTarget,
    remote_port: int | None = None,
    command_prefix: list[str] | None = None,
) -> str:
    """Build the command used by a current remote v_ase installation."""
    command = _remote_gui_argv(
        args,
        target,
        no_browser=True,
        stream_frames=True,
        modern_bond_defaults=True,
        remote_port=remote_port,
        command_prefix=command_prefix,
    )
    return shlex.join(command)


def build_remote_gui_launcher(
    args: argparse.Namespace,
    target: RemoteTarget,
    remote_port: int | None = None,
) -> str:
    """Build one SSH command that negotiates remote CLI capabilities.

    The remote shell inspects its own help text and selects a compatible
    invocation without a second SSH login. For the oldest CLI,
    BROWSER=/bin/echo exposes the loopback URL while preserving the normal
    blocking lifecycle.
    """
    command_prefix = remote_command_prefix(args, target)
    current_command = build_remote_gui_command(
        args,
        target,
        remote_port,
        command_prefix=command_prefix,
    )
    current_bonds_without_stream = shlex.join(
        _remote_gui_argv(
            args,
            target,
            no_browser=True,
            stream_frames=False,
            modern_bond_defaults=True,
            remote_port=remote_port,
            command_prefix=command_prefix,
        )
    )
    legacy_bonds_with_stream = shlex.join(
        _remote_gui_argv(
            args,
            target,
            no_browser=True,
            stream_frames=True,
            modern_bond_defaults=False,
            remote_port=remote_port,
            command_prefix=command_prefix,
        )
    )
    legacy_bonds_without_stream = shlex.join(
        _remote_gui_argv(
            args,
            target,
            no_browser=True,
            stream_frames=False,
            modern_bond_defaults=False,
            remote_port=remote_port,
            command_prefix=command_prefix,
        )
    )
    oldest_command = shlex.join(
        _remote_gui_argv(
            args,
            target,
            no_browser=False,
            stream_frames=False,
            modern_bond_defaults=False,
            remote_port=remote_port,
            command_prefix=command_prefix,
        )
    )

    if command_prefix[0] == "v_ase":
        runtime_instruction = (
            "Install it with `python -m pip install --upgrade v_ase-gui`, "
            "or select its environment with --remote-python /absolute/path/to/python."
        )
    else:
        runtime_instruction = (
            f"Verify that {command_prefix[0]} exists and contains v_ase-gui, "
            "or choose another --remote-python path."
        )
    unavailable_message = shlex.quote(
        f"v_ase: could not inspect the selected v_ase runtime on {target.host}. "
        f"{runtime_instruction}"
    )
    compatibility_message = shlex.quote(
        f"v_ase: {target.host} uses an older remote CLI; continuing in "
        "compatibility mode without on-demand frame streaming. Upgrade with "
        "`python -m pip install --upgrade v_ase-gui` for large trajectories."
    )
    precision_message = shlex.quote(
        f"v_ase: {target.host} does not support --volumetric-precision. "
        "Upgrade it with `python -m pip install --upgrade v_ase-gui`."
    )
    port_message = shlex.quote(
        f"v_ase: {target.host} does not support the managed SSH tunnel port. "
        "Upgrade it with `python -m pip install --upgrade v_ase-gui`."
    )

    lines = [
        f"_vase_help=$({shlex.join([*command_prefix, 'gui', '--help'])} 2>&1)",
        "_vase_help_status=$?",
        'if [ "$_vase_help_status" -ne 0 ]; then',
        '  printf \'%s\\n\' "$_vase_help" >&2',
        f"  printf '%s\\n' {unavailable_message} >&2",
        '  exit "$_vase_help_status"',
        "fi",
    ]
    if remote_port is not None:
        lines.extend([
            'case "$_vase_help" in',
            "  *--port*) ;;",
            f"  *) printf '%s\\n' {port_message} >&2; exit 64 ;;",
            "esac",
        ])
    if getattr(args, "volumetric_precision", "fp32") != "fp32":
        lines.extend([
            'case "$_vase_help" in',
            "  *--volumetric-precision*) ;;",
            f"  *) printf '%s\\n' {precision_message} >&2; exit 64 ;;",
            "esac",
        ])
    lines.extend([
        'case "$_vase_help" in',
        "  *--no-browser*)",
        '    case "$_vase_help" in',
        "      *--stream-frames*)",
        '        case "$_vase_help" in',
        f"          *--hide-bonds*) exec {current_command} ;;",
        f"          *) exec {legacy_bonds_with_stream} ;;",
        "        esac",
        "        ;;",
        "      *)",
        f"        printf '%s\\n' {compatibility_message} >&2",
        '        case "$_vase_help" in',
        f"          *--hide-bonds*) exec {current_bonds_without_stream} ;;",
        f"          *) exec {legacy_bonds_without_stream} ;;",
        "        esac",
        "        ;;",
        "    esac",
        "    ;;",
        "  *)",
        f"    printf '%s\\n' {compatibility_message} >&2",
        f"    BROWSER=/bin/echo exec {oldest_command}",
        "    ;;",
        "esac",
    ])
    return "\n".join(lines)


def localize_remote_url(remote_url: str, local_port: int) -> str:
    """Keep the remote session path while replacing its loopback endpoint."""
    parsed = urlsplit(remote_url)
    return urlunsplit(
        (
            parsed.scheme,
            f"127.0.0.1:{local_port}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def _terminate_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _read_remote_url(
    process: subprocess.Popen[str],
    target: RemoteTarget,
) -> str:
    if process.stdout is None:
        raise RemoteLaunchError("could not read the remote v_ase startup output")

    startup_messages: list[str] = []
    while True:
        line = process.stdout.readline()
        if not line:
            return_code = process.poll()
            if return_code is None:
                time.sleep(0.02)
                continue
            detail = "\n".join(startup_messages[-8:]).strip()
            suffix = f"\n{detail}" if detail else ""
            raise RemoteLaunchError(
                f"v_ase did not start on {target.host} (SSH exit {return_code})."
                f"{suffix}"
            )

        match = _LOOPBACK_URL.search(line)
        if match is not None:
            return match.group(0)

        message = line.strip()
        if message and message != "Open this URL in your browser:":
            startup_messages.append(message)
            print(message, file=sys.stderr, flush=True)


def _drain_remote_output(process: subprocess.Popen[str]) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        if _LOOPBACK_URL.search(line) or line.strip() == "Open this URL in your browser:":
            continue
        print(line, end="", file=sys.stderr, flush=True)


def _wait_for_forwarded_http(
    process: subprocess.Popen[str],
    local_url: str,
    timeout: float = 10.0,
) -> None:
    parsed = urlsplit(local_url)
    local_port = parsed.port
    if local_port is None:
        raise RemoteLaunchError("remote v_ase returned an invalid local URL")
    request_target = parsed.path or "/"
    if parsed.query:
        request_target = f"{request_target}?{parsed.query}"

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RemoteLaunchError(
                "remote v_ase exited before the tunnel became ready"
            )
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            local_port,
            timeout=0.5,
        )
        try:
            connection.request("GET", request_target)
            response = connection.getresponse()
            response.read(1)
            if 200 <= response.status < 400:
                return
            last_error = RemoteLaunchError(
                f"forwarded viewer returned HTTP {response.status}"
            )
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
        finally:
            connection.close()
        time.sleep(0.05)
    detail = f": {last_error}" if last_error is not None else ""
    raise RemoteLaunchError(f"SSH tunnel did not reach the remote viewer{detail}")


def launch_remote_gui(args: argparse.Namespace, target: RemoteTarget) -> int:
    """Open a remote structure through an automatically managed SSH tunnel."""
    if args.no_block:
        raise RemoteLaunchError(
            "--no-block is not supported for remote targets; "
            "the managed command already remains open until the browser closes"
        )

    ssh_executable = shutil.which("ssh")
    if ssh_executable is None:
        raise RemoteLaunchError(
            "OpenSSH is required for HOST:/path targets, but `ssh` was not found"
        )

    remote_process: subprocess.Popen[str] | None = None
    drain_thread: threading.Thread | None = None
    event_stream = None
    print(
        f"Opening {target.host}:{target.path}...",
        file=sys.stderr,
        flush=True,
    )
    try:
        local_port = args.port if args.port is not None else find_free_port()
        remote_port = find_free_port()
        remote_process = subprocess.Popen(
            [
                ssh_executable,
                "-T",
                "-o",
                "ExitOnForwardFailure=yes",
                "-L",
                f"127.0.0.1:{local_port}:127.0.0.1:{remote_port}",
                target.host,
                build_remote_gui_launcher(args, target, remote_port),
            ],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        remote_url = _read_remote_url(remote_process, target)
        reported_remote_port = urlsplit(remote_url).port
        if reported_remote_port is None:
            raise RemoteLaunchError("remote v_ase returned an invalid viewer URL")
        if reported_remote_port != remote_port:
            raise RemoteLaunchError(
                "remote v_ase did not honor the requested tunnel port; "
                "upgrade the remote installation"
            )
        local_url = localize_remote_url(remote_url, local_port)
        drain_thread = threading.Thread(
            target=_drain_remote_output,
            args=(remote_process,),
            daemon=True,
            name="v_ase-remote-output",
        )
        drain_thread.start()
        _wait_for_forwarded_http(remote_process, local_url)

        if args.cli_mode:
            from .ai import ai_handshake, start_collaboration_event_stream

            handshake = ai_handshake(local_url)
            print(json.dumps(handshake, separators=(",", ":")), flush=True)
            event_stream = start_collaboration_event_stream(handshake)
            print(
                "The structure remains on the remote host. Open the reported "
                "human_url for the same live GUI. Committed GUI and agent changes "
                "are emitted here as NDJSON.",
                file=sys.stderr,
                flush=True,
            )
        else:
            announce_viewer_url(local_url)
            if args.no_browser:
                print(
                    "Automatic browser launch is disabled; use the URL above.",
                    file=sys.stderr,
                    flush=True,
                )
            elif not open_browser_url(local_url):
                print(
                    "v_ase could not open a browser automatically; "
                    "use the URL above.",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    "Browser launch requested. If no tab appeared, use the URL above.",
                    file=sys.stderr,
                    flush=True,
                )

        while True:
            remote_return_code = remote_process.poll()
            if remote_return_code is not None:
                if remote_return_code != 0:
                    raise RemoteLaunchError(
                        f"remote v_ase exited with status {remote_return_code}"
                    )
                return 0
            time.sleep(0.1)
    except KeyboardInterrupt:
        return 130
    finally:
        if event_stream is not None:
            stop_event, event_thread = event_stream
            stop_event.set()
            event_thread.join(timeout=1.5)
        _terminate_process(remote_process)
        if drain_thread is not None:
            drain_thread.join(timeout=0.5)
