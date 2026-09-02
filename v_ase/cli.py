"""Command line interface for v_ase."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit

from v_ase._version import __version__

# Kept as an injectable seam for the CLI regression suite while the actual
# viewer import remains lazy for normal command startup.
view = None


def _scientific_stack_error(error: Exception) -> str:
    detail = str(error).strip() or error.__class__.__name__
    lowered = detail.lower()
    binary_markers = (
        "numpy.dtype size changed",
        "numpy.core.multiarray failed to import",
        "_array_api not found",
        "compiled using numpy 1.x",
    )
    if any(marker in lowered for marker in binary_markers):
        return (
            "v_ase: NumPy and SciPy/matscipy are binary-incompatible in this "
            "Python environment. The structure file has not been read yet. "
            "Upgrade v_ase in the same interpreter with "
            "`python -m pip install --upgrade --force-reinstall v_ase-gui`; "
            "if this is a shared Conda base environment, a clean environment "
            "is recommended. Original import error: "
            f"{detail}"
        )
    return f"v_ase: could not load the scientific Python stack: {detail}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v_ase",
        description="Local browser viewer and editor for ASE structures and trajectories.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    gui = subparsers.add_parser(
        "gui",
        help="open the v_ase GUI, optionally with a structure, trajectory, or project",
        description="Open an empty v_ase workspace or load a file like ASE's `ase gui FILE`.",
    )
    gui.add_argument(
        "file",
        nargs="?",
        help=(
            "optional local structure, trajectory, .vase project, or v_ase HTML project; "
            "use HOST:/path for a file that must remain on a remote server"
        ),
    )
    gui.add_argument(
        "-i",
        "--index",
        default=":",
        help="ASE read index. Use ':' for all frames, '-1' for last frame, or an integer frame index. Default: :",
    )
    gui.add_argument("-o", "--output", help="write the edited structure to this file when the session is finalized")
    gui.add_argument(
        "--format",
        "--input-format",
        dest="format",
        metavar="FORMAT",
        help=(
            "force the input file format when the filename is ambiguous. "
            "Common aliases: POSCAR, XDATCAR, vasprun.xml, lammpstrj, traj, xyz, "
            "extxyz, data, CHG, CHGCAR, LOCPOT, PARCHG, ELFCAR, cube, xsf, "
            "vase, html. "
            "Raw ASE format names such as vasp-xml and lammps-data also work."
        ),
    )
    gui.add_argument(
        "--volumetric-precision",
        choices=("fp32", "fp64"),
        default="fp32",
        help=(
            "scalar-grid precision used when reading CHGCAR, LOCPOT, PARCHG, "
            "Cube, or XSF data. FP32 is faster and uses half the memory; FP64 "
            "preserves double precision. Default: fp32"
        ),
    )
    gui.add_argument("--output-format", help="ASE output format override")
    gui.add_argument(
        "--port",
        type=int,
        help="local browser server port; a free loopback port is selected automatically when omitted",
    )
    gui.add_argument(
        "--no-browser",
        action="store_true",
        help="do not launch a browser automatically; print the URL for SSH tunnels or headless servers",
    )
    gui.add_argument(
        "--remote-python",
        metavar="ABSOLUTE_PATH",
        help=(
            "for a HOST:/path input, run the remote backend with this exact "
            "Python executable instead of the remote shell PATH; the value "
            "overrides any saved host setting for this launch"
        ),
    )
    gui.add_argument(
        "--no-block",
        action="store_true",
        help="open without waiting for session finalization; keep the local server alive until Ctrl+C",
    )
    gui.add_argument(
        "--stream-frames",
        action="store_true",
        help="transfer trajectory coordinates one frame at a time instead of preloading a browser cache",
    )
    bonds = gui.add_mutually_exclusive_group()
    bonds.add_argument(
        "--show-bonds",
        dest="show_bonds",
        action="store_true",
        help="show inferred bonds on startup (default)",
    )
    bonds.add_argument(
        "--hide-bonds",
        dest="show_bonds",
        action="store_false",
        help="start with inferred bonds hidden",
    )
    gui.add_argument("--hide-cell", action="store_true", help="hide the unit cell on startup")
    gui.add_argument("--hide-axes", action="store_true", help="hide axes on startup")
    gui.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "enable atom editing, deletion, constraints editing, relaxation, "
            "undo, copy, and paste. By default v_ase opens in lightweight "
            "visualization mode."
        ),
    )
    gui.add_argument(
        "--cli",
        dest="cli_mode",
        action="store_true",
        help=(
            "start a terminal-oriented machine-readable session, print a JSON "
            "API handshake followed by revisioned change events, and suppress "
            "automatic browser launch; this mode does not accept natural "
            "language or commands from stdin"
        ),
    )
    gui.set_defaults(func=run_gui, show_bonds=True)

    remote = subparsers.add_parser(
        "remote",
        help="configure exact Python runtimes for SSH hosts",
        description=(
            "Save or inspect the Python executable used for HOST:/path launches. "
            "No shell activation or .bashrc sourcing is required."
        ),
    )
    remote_subparsers = remote.add_subparsers(dest="remote_command", required=True)
    remote_configure = remote_subparsers.add_parser(
        "configure",
        help="save the Python executable for one SSH host",
    )
    remote_configure.add_argument("host", help="SSH host or user@host, matching HOST:/path")
    remote_configure.add_argument(
        "--python",
        required=True,
        dest="remote_python_path",
        metavar="ABSOLUTE_PATH",
        help="absolute Python executable containing the v_ase installation",
    )
    remote_configure.set_defaults(func=run_remote_configure)
    remote_show = remote_subparsers.add_parser(
        "show",
        help="show saved remote Python runtimes",
    )
    remote_show.add_argument("host", nargs="?", help="optional single SSH host")
    remote_show.set_defaults(func=run_remote_show)
    remote_remove = remote_subparsers.add_parser(
        "remove",
        help="remove one saved remote Python runtime",
    )
    remote_remove.add_argument("host", help="SSH host or user@host")
    remote_remove.set_defaults(func=run_remote_remove)

    api = subparsers.add_parser(
        "api",
        help="send one structured command to a live v_ase CLI session",
        description=(
            "Send a JSON command to command_url from the first line printed by "
            "`v_ase gui STRUCTURE --cli`. This interface is intended for "
            "external AI agents and automation; it does not parse natural language. "
            "Schema and state queries are focused by default so an agent does not "
            "re-read the complete scene after every action."
        ),
        epilog=(
            "Typical sequence: `schema --operation-schema compose-view`; "
            "`describe --profile render`; `apply --params-file command.json`; "
            "`render --params '{\"width\":800,\"height\":600}' --save draft.png`. "
            "Use `schema --full-schema` or `describe --profile full` only when needed."
        ),
    )
    api.add_argument("command_url", help="loopback command_url from the CLI handshake")
    api.add_argument(
        "method",
        choices=[
            "ready",
            "schema",
            "describe",
            "capabilities",
            "documents",
            "activate",
            "newDocument",
            "apply",
            "render",
            "export",
        ],
        help="semantic API method",
    )
    params = api.add_mutually_exclusive_group()
    params.add_argument(
        "--params",
        default="{}",
        help="JSON object/value passed to the method (default: {})",
    )
    params.add_argument(
        "--params-file",
        type=Path,
        help="read method parameters from a UTF-8 JSON file",
    )
    api.add_argument(
        "--profile",
        choices=(
            "summary", "structure", "appearance", "bonding",
            "render", "analysis", "full",
        ),
        help=(
            "describe profile. The CLI defaults to summary when no explicit params "
            "are supplied"
        ),
    )
    api.add_argument(
        "--include-positions",
        action="store_true",
        help="include Cartesian positions in a focused structure or bonding description",
    )
    api.add_argument(
        "--include-properties",
        action="store_true",
        help="include complete per-atom arrays in a structure description",
    )
    api.add_argument(
        "--include-overrides",
        action="store_true",
        help="include complete per-index appearance or bond endpoint overrides",
    )
    api.add_argument(
        "--operation-schema",
        metavar="NAME",
        action="append",
        help=(
            "with schema, return an exact semantic-operation contract; repeat the "
            "flag to request up to 16 related operations in one response"
        ),
    )
    api.add_argument(
        "--export-schema",
        metavar="FORMAT",
        help="with schema, return only one export contract",
    )
    api.add_argument(
        "--schema-method",
        choices=("apply", "describe", "render"),
        help="with schema, return only the selected method contract",
    )
    api.add_argument(
        "--full-schema",
        action="store_true",
        help="with schema, return the complete compatibility schema instead of the compact index",
    )
    api.add_argument(
        "--response-profile",
        choices=(
            "summary", "structure", "appearance", "bonding",
            "render", "analysis", "full",
        ),
        help="state profile returned after apply (CLI default: summary)",
    )
    api.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="browser command timeout in seconds (default: 300; maximum: 1800)",
    )
    api.add_argument(
        "--save",
        type=Path,
        help="decode a render/export dataUrl directly to this output file",
    )
    api.add_argument(
        "--force",
        action="store_true",
        help="allow --save to replace an existing file",
    )
    api.add_argument(
        "--print-data-url",
        action="store_true",
        help=(
            "print render/export dataUrl payloads instead of the compact metadata-only "
            "default; normally use --save to avoid sending Base64 through an AI context"
        ),
    )
    api.set_defaults(func=run_api_command)

    return parser


def normalize_argv(argv: list[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"gui", "api", "remote", "-h", "--help", "--version"} and not args[0].startswith("-"):
        return ["gui", *args]
    return args


def _load_api_params(args: argparse.Namespace):
    source = (
        args.params_file.read_text(encoding="utf-8")
        if args.params_file is not None
        else args.params
    )
    try:
        return json.loads(source)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"v_ase api: invalid JSON parameters at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def _resolved_api_params(args: argparse.Namespace):
    """Merge token-efficient method shortcuts into one JSON parameter object."""
    params = _load_api_params(args)
    if args.method in {"schema", "describe", "apply", "render", "export", "activate"} \
            and not isinstance(params, dict):
        raise SystemExit(f"v_ase api: {args.method} parameters must be a JSON object.")
    shortcut_values = (
        args.profile,
        args.include_positions,
        args.include_properties,
        args.include_overrides,
        args.operation_schema,
        args.export_schema,
        args.schema_method,
        args.full_schema,
        args.response_profile,
    )
    if any(shortcut_values) and not isinstance(params, dict):
        raise SystemExit("v_ase api: method shortcut flags require JSON object parameters.")
    explicit_params = args.params_file is not None or args.params != "{}"
    if args.method == "schema":
        invalid = args.profile or args.include_positions or args.include_properties \
            or args.include_overrides or args.response_profile
        if invalid:
            raise SystemExit("v_ase api: describe/apply profile flags cannot be used with schema.")
        selectors = [
            bool(args.operation_schema), bool(args.export_schema),
            bool(args.schema_method), bool(args.full_schema),
        ]
        if sum(selectors) > 1:
            raise SystemExit(
                "v_ase api: choose only one of --operation-schema, --export-schema, "
                "--schema-method, or --full-schema."
            )
        if args.operation_schema:
            if len(args.operation_schema) == 1:
                params["operation"] = args.operation_schema[0]
            else:
                params["operations"] = args.operation_schema
        elif args.export_schema:
            params["export"] = args.export_schema
        elif args.schema_method:
            params["method"] = args.schema_method
        elif not args.full_schema and not explicit_params:
            params["scope"] = "summary"
    elif args.method == "describe":
        invalid = args.operation_schema or args.export_schema or args.schema_method \
            or args.full_schema or args.response_profile
        if invalid:
            raise SystemExit("v_ase api: schema/apply shortcut flags cannot be used with describe.")
        if args.profile:
            params["profile"] = args.profile
        elif not explicit_params:
            params["profile"] = "summary"
        if args.include_positions:
            params["includePositions"] = True
        if args.include_properties:
            params["includeProperties"] = True
        if args.include_overrides:
            params["includeOverrides"] = True
    elif args.method == "apply":
        invalid = args.profile or args.include_positions or args.include_properties \
            or args.include_overrides or args.operation_schema or args.export_schema \
            or args.schema_method or args.full_schema
        if invalid:
            raise SystemExit("v_ase api: schema/describe shortcut flags cannot be used with apply.")
        params.setdefault("responseProfile", args.response_profile or "summary")
    elif args.method == "capabilities":
        if any(shortcut_values):
            raise SystemExit(
                "v_ase api: schema/describe/apply shortcut flags cannot be used with capabilities."
            )
        if not explicit_params:
            params["profile"] = "summary"
    elif any(shortcut_values):
        raise SystemExit(
            f"v_ase api: profile and schema shortcut flags do not apply to {args.method}."
        )
    return params


def _decode_data_url(data_url: str) -> bytes:
    if not isinstance(data_url, str) or not data_url.startswith("data:"):
        raise ValueError("The command result does not contain a valid data URL.")
    header, separator, payload = data_url.partition(",")
    if not separator:
        raise ValueError("The command result contains a malformed data URL.")
    if header.endswith(";base64"):
        return base64.b64decode(payload, validate=True)
    return unquote_to_bytes(payload)


def run_api_command(args: argparse.Namespace) -> int:
    parsed = urlsplit(args.command_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise SystemExit(
            "v_ase api: command_url must be a loopback HTTP(S) URL from a "
            "live v_ase CLI handshake."
        )
    if not args.timeout or args.timeout <= 0:
        raise SystemExit("v_ase api: --timeout must be a positive number.")
    output_path = args.save.expanduser() if args.save is not None else None
    if output_path is not None and output_path.exists() and not args.force:
        raise SystemExit(
            f"v_ase api: refusing to replace existing file: {output_path}. "
            "Choose another path or pass --force after explicit approval."
        )

    import requests

    try:
        response = requests.post(
            args.command_url,
            json={
                "method": args.method,
                "params": _resolved_api_params(args),
                "timeout_seconds": min(float(args.timeout), 1800.0),
            },
            timeout=min(float(args.timeout), 1800.0) + 5.0,
        )
    except requests.RequestException as exc:
        raise SystemExit(f"v_ase api: command request failed: {exc}") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise SystemExit(
            f"v_ase api: command failed ({response.status_code}): "
            f"{detail or response.text or response.reason}"
        )
    payload = response.json()
    result = payload.get("result")
    if output_path is not None:
        if not isinstance(result, dict):
            raise SystemExit("v_ase api: this command result cannot be saved as a file.")
        try:
            encoded = _decode_data_url(result.get("dataUrl"))
        except (ValueError, TypeError, base64.binascii.Error) as exc:
            raise SystemExit(f"v_ase api: could not decode command output: {exc}") from exc
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(encoded)
        result = dict(result)
        result.pop("dataUrl", None)
        result["saved_to"] = str(output_path.resolve())
        result["saved_bytes"] = len(encoded)
        payload["result"] = result
    elif (
        isinstance(result, dict)
        and isinstance(result.get("dataUrl"), str)
        and not args.print_data_url
    ):
        data_url = result["dataUrl"]
        result = dict(result)
        result.pop("dataUrl", None)
        result["data_url_omitted"] = True
        result["data_url_characters"] = len(data_url)
        result["save_hint"] = "Repeat this command with --save OUTPUT to decode the artifact."
        payload["result"] = result
    print(json.dumps(payload, separators=(",", ":")), flush=True)
    return 0


def run_remote_configure(args: argparse.Namespace) -> int:
    from v_ase.remote import RemoteLaunchError, configure_remote_runtime

    try:
        path = configure_remote_runtime(args.host, args.remote_python_path)
    except (OSError, ValueError, RemoteLaunchError) as exc:
        raise SystemExit(f"v_ase remote configure: {exc}") from exc
    print(f"Configured {args.host} to use {args.remote_python_path}")
    print(f"Saved in {path}")
    return 0


def run_remote_show(args: argparse.Namespace) -> int:
    from v_ase.remote import (
        RemoteLaunchError,
        load_remote_runtime_config,
        remote_runtime_config_path,
    )

    try:
        hosts = load_remote_runtime_config()
    except (OSError, ValueError, RemoteLaunchError) as exc:
        raise SystemExit(f"v_ase remote show: {exc}") from exc
    if args.host:
        python = hosts.get(args.host)
        if python is None:
            raise SystemExit(f"v_ase remote show: no runtime is configured for {args.host}")
        print(f"{args.host}\t{python}")
        return 0
    if not hosts:
        print(f"No remote runtimes configured ({remote_runtime_config_path()})")
        return 0
    for host, python in sorted(hosts.items()):
        print(f"{host}\t{python}")
    return 0


def run_remote_remove(args: argparse.Namespace) -> int:
    from v_ase.remote import RemoteLaunchError, remove_remote_runtime

    try:
        path, removed = remove_remote_runtime(args.host)
    except (OSError, ValueError, RemoteLaunchError) as exc:
        raise SystemExit(f"v_ase remote remove: {exc}") from exc
    if not removed:
        raise SystemExit(f"v_ase remote remove: no runtime is configured for {args.host}")
    print(f"Removed the saved runtime for {args.host} from {path}")
    return 0


def run_gui(args: argparse.Namespace) -> int:
    if args.file:
        from v_ase.remote import (
            RemoteLaunchError,
            launch_remote_gui,
            parse_remote_target,
        )

        remote_target = parse_remote_target(args.file)
        if remote_target is not None:
            try:
                return launch_remote_gui(args, remote_target)
            except RemoteLaunchError as exc:
                raise SystemExit(f"v_ase: {exc}") from exc

    if args.remote_python:
        raise SystemExit(
            "v_ase: --remote-python is only valid with a HOST:/path input"
        )

    try:
        from ase import Atoms
        from ase.io import write

        from v_ase.io import (
            infer_input_format,
            read_fast_lammps_dump,
            read_indexed_trajectory,
            read_structure_frames,
        )
        from v_ase.viewer import view as imported_view
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        raise SystemExit(_scientific_stack_error(exc)) from exc

    path = Path(args.file).expanduser() if args.file else None
    if path is not None and not path.exists():
        raise SystemExit(f"v_ase: file not found: {path}")

    resolved_format = infer_input_format(path, args.format)
    suffix = path.suffix.lower() if path is not None else ""
    trajectory_source = None
    initial_frame = 0
    initial_design_settings = None
    volumetric_datasets = None
    is_vase_project = suffix == ".vase" or resolved_format == "vase-project"
    is_html_project = (
        suffix in {".html", ".htm"}
        or resolved_format == "vase-html-project"
    )
    is_lammps_dump = resolved_format == "lammps-dump-text" or (
        args.format is None and suffix in {".lammpstrj", ".dump"}
    )
    # A filename-free launch is a scratch workspace.  Start it in Edit mode so
    # the user can define a cell and build atoms without an extra mode switch.
    viz_only = False if path is None else not args.interactive
    if path is None:
        frames = [Atoms()]
    elif is_vase_project or is_html_project:
        from v_ase.project import read_project_archive, read_project_html

        try:
            project = (
                read_project_html(path)
                if is_html_project
                else read_project_archive(path)
            )
        except ValueError as exc:
            raise SystemExit(f"v_ase: could not open project: {exc}") from exc
        frames = project.frames
        volumetric_datasets = project.volumetric_datasets
        initial_frame = project.current_frame
        initial_design_settings = project.settings
    elif path is not None:
        from v_ase.volumetric import (
            read_volumetric_file,
            resolve_volumetric_format,
            volumetric_structure,
        )

        volumetric_format = resolve_volumetric_format(
            path,
            args.format or resolved_format,
        )
        if volumetric_format:
            try:
                volumetric_datasets = read_volumetric_file(
                    path,
                    volumetric_format,
                    precision=args.volumetric_precision,
                )
            except (OSError, TypeError, ValueError) as exc:
                raise SystemExit(
                    f"v_ase: could not open volumetric data: {exc}"
                ) from exc
            frames = [volumetric_structure(volumetric_datasets)]
            first_dataset = volumetric_datasets[0]
            minimum = float(first_dataset.minimum)
            maximum = float(first_dataset.maximum)
            has_surface_range = maximum > minimum
            if has_surface_range and minimum < 0.0 < maximum:
                volumetric_level = max(abs(minimum), abs(maximum)) * 0.18
                volumetric_surface_mode = "signed"
            elif has_surface_range:
                volumetric_level = minimum + (maximum - minimum) * 0.22
                volumetric_surface_mode = "single"
            else:
                volumetric_level = None
                volumetric_surface_mode = "single"
            initial_design_settings = {
                "display": {
                    "showVolumetric": has_surface_range,
                    "volumetricPrecision": (
                        "float64"
                        if args.volumetric_precision == "fp64"
                        else "float32"
                    ),
                    "volumetricDatasetId": first_dataset.dataset_id,
                    "volumetricLevel": volumetric_level,
                    "volumetricSurfaceMode": volumetric_surface_mode,
                    "volumetricSmearingSigma": 0.0,
                    "volumetricSmoothingIterations": 4,
                }
            }
        elif viz_only and is_lammps_dump:
            try:
                fast = read_fast_lammps_dump(path, args.index)
                frames = [fast.atoms]
                trajectory_source = fast.trajectory
                initial_frame = fast.initial_frame
            except ValueError as exc:
                print(
                    f"v_ase: fast LAMMPS loader unavailable ({exc}); "
                    "falling back to the compatible loader.",
                    file=sys.stderr,
                )
                frames = read_structure_frames(path, args.index, args.format)
        elif viz_only and args.stream_frames:
            try:
                indexed = read_indexed_trajectory(path, args.index, args.format)
            except ValueError as exc:
                print(
                    f"v_ase: indexed trajectory loader unavailable ({exc}); "
                    "falling back to the compatible loader.",
                    file=sys.stderr,
                )
                indexed = None
            if indexed is None:
                frames = read_structure_frames(path, args.index, args.format)
            else:
                frames = [indexed.atoms]
                trajectory_source = indexed.trajectory
                initial_frame = indexed.initial_frame
        else:
            frames = read_structure_frames(path, args.index, args.format)
    if not frames:
        raise SystemExit(f"v_ase: no frames found in {path}")

    keep_alive = bool(args.no_block or args.cli_mode)
    runtime_view = view or imported_view
    result = runtime_view(
        frames,
        block=not keep_alive,
        port=args.port,
        show_cell=not args.hide_cell,
        show_axes=not args.hide_axes,
        show_bonds=args.show_bonds,
        viz_only=viz_only,
        trajectory_source=trajectory_source,
        initial_frame=initial_frame,
        initial_design_settings=initial_design_settings,
        document_name=path.name if path is not None else "Untitled",
        open_browser=not args.no_browser and not args.cli_mode,
        stream_trajectory=args.stream_frames,
        volumetric_datasets=volumetric_datasets,
    )

    if keep_alive:
        event_stream = None
        if args.cli_mode:
            from v_ase.ai import ai_handshake, start_collaboration_event_stream

            handshake = ai_handshake(result.url)
            print(json.dumps(handshake, separators=(",", ":")), flush=True)
            event_stream = start_collaboration_event_stream(handshake)
            print(
                "v_ase CLI API session is running. Open human_url to watch or "
                "edit the same live document. Committed GUI and agent changes "
                "are emitted as NDJSON; press Ctrl+C here to stop it.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"Viewer URL: {result.url}")
            print("Server is kept alive for manual testing. Press Ctrl+C here to stop it.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            if event_stream is not None:
                stop_event, thread = event_stream
                stop_event.set()
                thread.join(timeout=1.5)
            result.close()
        finally:
            if event_stream is not None:
                stop_event, thread = event_stream
                stop_event.set()
                thread.join(timeout=0.3)
        return 0

    if args.output and result is not None:
        write_kwargs = {}
        if args.output_format:
            write_kwargs["format"] = args.output_format
        write(args.output, result, **write_kwargs)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
