"""Command line interface for v_ase."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ase import Atoms
from ase.io import write

from v_ase._version import __version__
from v_ase.io import (
    read_fast_lammps_dump,
    read_structure_frames,
    resolve_input_format,
)
from v_ase.viewer import view


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
            "extxyz, data, vase, html. "
            "Raw ASE format names such as vasp-xml and lammps-data also work."
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
        "--for-ai",
        action="store_true",
        help=(
            "start a machine-readable agent session, print a JSON handshake, "
            "and leave the same URL available for normal human use"
        ),
    )
    gui.set_defaults(func=run_gui, show_bonds=True)

    return parser


def normalize_argv(argv: list[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"gui", "-h", "--help", "--version"} and not args[0].startswith("-"):
        return ["gui", *args]
    return args


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

    path = Path(args.file).expanduser() if args.file else None
    if path is not None and not path.exists():
        raise SystemExit(f"v_ase: file not found: {path}")

    resolved_format = resolve_input_format(args.format)
    suffix = path.suffix.lower() if path is not None else ""
    trajectory_source = None
    initial_frame = 0
    initial_design_settings = None
    is_vase_project = suffix == ".vase" or resolved_format == "vase-project"
    is_html_project = (
        suffix in {".html", ".htm"}
        or resolved_format == "vase-html-project"
    )
    is_lammps_dump = resolved_format == "lammps-dump-text" or (
        args.format is None and suffix in {".lammpstrj", ".dump"}
    )
    viz_only = not args.interactive
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
        initial_frame = project.current_frame
        initial_design_settings = project.settings
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
    else:
        frames = read_structure_frames(path, args.index, args.format)
    if not frames:
        raise SystemExit(f"v_ase: no frames found in {path}")

    keep_alive = bool(args.no_block or args.for_ai)
    result = view(
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
        open_browser=not args.no_browser and not args.for_ai,
        stream_trajectory=args.stream_frames,
    )

    if keep_alive:
        if args.for_ai:
            from v_ase.ai import ai_handshake

            print(json.dumps(ai_handshake(result.url), separators=(",", ":")), flush=True)
            print(
                "v_ase AI session is running. Open the reported human_url for "
                "the normal GUI; press Ctrl+C here to stop it.",
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
            result.close()
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
