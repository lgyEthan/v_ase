"""Command line interface for v_ase."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

from ase.io import read, write

from v_ase.io import read_custom_extxyz
from v_ase.viewer import view


def package_version() -> str:
    try:
        return version("v_ase-gui")
    except PackageNotFoundError:
        return "0.0.5"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v_ase",
        description="Blender-style browser GUI for ASE structures and trajectories.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    subparsers = parser.add_subparsers(dest="command")

    gui = subparsers.add_parser(
        "gui",
        help="open a structure or trajectory file in the v_ase GUI",
        description="Open a file like ASE's `ase gui FILE`, but in the v_ase browser editor.",
    )
    gui.add_argument("file", help="structure or trajectory file readable by ASE, e.g. POSCAR, .vasp, .traj, .extxyz")
    gui.add_argument(
        "-i",
        "--index",
        default=":",
        help="ASE read index. Use ':' for all frames, '-1' for last frame, or an integer frame index. Default: :",
    )
    gui.add_argument("-o", "--output", help="write the edited structure to this file after Done")
    gui.add_argument("--format", help="ASE input format override")
    gui.add_argument("--output-format", help="ASE output format override")
    gui.add_argument("--port", type=int, help="local browser server port")
    gui.add_argument(
        "--no-block",
        action="store_true",
        help="open without waiting for Done/Cancel; keep the local server alive until Ctrl+C",
    )
    gui.add_argument("--show-bonds", action="store_true", help="show inferred bonds on startup")
    gui.add_argument("--hide-cell", action="store_true", help="hide the unit cell on startup")
    gui.add_argument("--hide-axes", action="store_true", help="hide axes on startup")
    gui.set_defaults(func=run_gui)

    return parser


def _read_frames(path: Path, index: str, fmt: str | None):
    read_kwargs = {"index": index}
    if fmt:
        read_kwargs["format"] = fmt
    try:
        loaded = read(path, **read_kwargs)
    except KeyError as exc:
        if fmt not in {None, "extxyz", "xyz"} or path.suffix.lower() not in {".xyz", ".extxyz"}:
            raise
        loaded = read_custom_extxyz(path, index)
    return loaded if isinstance(loaded, list) else [loaded]


def normalize_argv(argv: list[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] not in {"gui", "-h", "--help", "--version"} and not args[0].startswith("-"):
        return ["gui", *args]
    return args


def run_gui(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser()
    if not path.exists():
        raise SystemExit(f"v_ase: file not found: {path}")

    frames = _read_frames(path, args.index, args.format)
    if not frames:
        raise SystemExit(f"v_ase: no frames found in {path}")

    result = view(
        frames,
        block=not args.no_block,
        port=args.port,
        show_cell=not args.hide_cell,
        show_axes=not args.hide_axes,
        show_bonds=args.show_bonds,
    )

    if args.no_block:
        print(f"Viewer URL: http://127.0.0.1:{result.port}/?session_id={result.session_id}")
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
