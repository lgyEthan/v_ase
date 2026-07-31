"""One-command SSH launcher for remote v_ase sessions."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .viewer import find_free_port, open_browser_url


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


def build_remote_gui_command(
    args: argparse.Namespace,
    target: RemoteTarget,
) -> str:
    """Build a shell-safe command for the remote SSH session."""
    command = [
        "v_ase",
        "gui",
        "--index",
        str(args.index),
        "--no-browser",
        "--stream-frames",
    ]
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
    if not args.show_bonds:
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
    return shlex.join(command)


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


def _wait_for_tunnel(
    process: subprocess.Popen[str],
    local_port: int,
    timeout: float = 8.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = process.stderr.read().strip() if process.stderr else ""
            suffix = f": {detail}" if detail else ""
            raise RemoteLaunchError(f"SSH tunnel could not be opened{suffix}")
        try:
            with socket.create_connection(("127.0.0.1", local_port), timeout=0.15):
                return
        except OSError:
            time.sleep(0.03)
    raise RemoteLaunchError("SSH tunnel did not become ready")


def _start_tunnel(
    ssh_executable: str,
    target: RemoteTarget,
    remote_port: int,
    requested_local_port: int | None = None,
) -> tuple[subprocess.Popen[str], int]:
    last_error: RemoteLaunchError | None = None
    attempts = 1 if requested_local_port is not None else 5
    for _ in range(attempts):
        local_port = (
            requested_local_port
            if requested_local_port is not None
            else find_free_port()
        )
        process = subprocess.Popen(
            [
                ssh_executable,
                "-T",
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-L",
                f"127.0.0.1:{local_port}:127.0.0.1:{remote_port}",
                target.host,
            ],
            stdin=None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _wait_for_tunnel(process, local_port)
            return process, local_port
        except RemoteLaunchError as exc:
            last_error = exc
            _terminate_process(process)
    raise last_error or RemoteLaunchError("SSH tunnel could not be opened")


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
    tunnel_process: subprocess.Popen[str] | None = None
    drain_thread: threading.Thread | None = None
    event_stream = None
    print(
        f"Opening {target.host}:{target.path}...",
        file=sys.stderr,
        flush=True,
    )
    try:
        remote_process = subprocess.Popen(
            [
                ssh_executable,
                "-T",
                target.host,
                build_remote_gui_command(args, target),
            ],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        remote_url = _read_remote_url(remote_process, target)
        remote_port = urlsplit(remote_url).port
        if remote_port is None:
            raise RemoteLaunchError("remote v_ase returned an invalid viewer URL")

        tunnel_process, local_port = _start_tunnel(
            ssh_executable,
            target,
            remote_port,
            requested_local_port=args.port,
        )
        local_url = localize_remote_url(remote_url, local_port)
        drain_thread = threading.Thread(
            target=_drain_remote_output,
            args=(remote_process,),
            daemon=True,
            name="v_ase-remote-output",
        )
        drain_thread.start()

        if args.cli_mode:
            from .ai import ai_handshake, start_collaboration_event_stream

            handshake = ai_handshake(local_url)
            print(json.dumps(handshake, separators=(",", ":")), flush=True)
            event_stream = start_collaboration_event_stream(handshake)
            print(
                "The structure remains on the remote host. Open the reported "
                "human_url for the normal GUI. Committed GUI and agent changes "
                "are emitted here as NDJSON.",
                file=sys.stderr,
                flush=True,
            )
        elif args.no_browser or not open_browser_url(local_url):
            print(
                "Open this URL in your browser:\n"
                f"{local_url}",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(
                "Connected. The remote structure is open in your browser.",
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
            if tunnel_process.poll() is not None:
                detail = (
                    tunnel_process.stderr.read().strip()
                    if tunnel_process.stderr
                    else ""
                )
                suffix = f": {detail}" if detail else ""
                raise RemoteLaunchError(f"SSH tunnel closed unexpectedly{suffix}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        return 130
    finally:
        if event_stream is not None:
            stop_event, event_thread = event_stream
            stop_event.set()
            event_thread.join(timeout=1.5)
        _terminate_process(tunnel_process)
        _terminate_process(remote_process)
        if drain_thread is not None:
            drain_thread.join(timeout=0.5)
