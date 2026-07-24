"""Command line interface for v_ase."""

from __future__ import annotations

import argparse
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
        help="optional structure, trajectory, or .vase project, e.g. POSCAR, .vasp, .traj, .extxyz, .vase",
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
            "Common aliases: POSCAR, XDATCAR, vasprun.xml, lammpstrj, traj, xyz, extxyz, data, vase. "
            "Raw ASE format names such as vasp-xml and lammps-data also work."
        ),
    )
    gui.add_argument("--output-format", help="ASE output format override")
    gui.add_argument("--port", type=int, help="local browser server port")
    gui.add_argument(
        "--no-block",
        action="store_true",
        help="open without waiting for session finalization; keep the local server alive until Ctrl+C",
    )
    gui.add_argument("--show-bonds", action="store_true", help="show inferred bonds on startup")
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
    gui.set_defaults(func=run_gui)

    return parser


def normalize_argv(argv: list[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"gui", "-h", "--help", "--version"} and not args[0].startswith("-"):
        return ["gui", *args]
    return args


def run_gui(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser() if args.file else None
    if path is not None and not path.exists():
        raise SystemExit(f"v_ase: file not found: {path}")

    resolved_format = resolve_input_format(args.format)
    suffix = path.suffix.lower() if path is not None else ""
    trajectory_source = None
    initial_frame = 0
    initial_design_settings = None
    is_vase_project = suffix == ".vase" or resolved_format == "vase-project"
    is_lammps_dump = resolved_format == "lammps-dump-text" or (
        args.format is None and suffix in {".lammpstrj", ".dump"}
    )
    viz_only = not args.interactive
    if path is None:
        frames = [Atoms()]
    elif is_vase_project:
        from v_ase.project import read_project_archive

        project = read_project_archive(path)
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

    result = view(
        frames,
        block=not args.no_block,
        port=args.port,
        show_cell=not args.hide_cell,
        show_axes=not args.hide_axes,
        show_bonds=args.show_bonds,
        viz_only=viz_only,
        trajectory_source=trajectory_source,
        initial_frame=initial_frame,
        initial_design_settings=initial_design_settings,
        document_name=path.name if path is not None else "Untitled",
    )

    if args.no_block:
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
