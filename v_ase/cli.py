"""Command line interface for v_ase."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

from ase.io import read, write

from v_ase.io import read_custom_extxyz, read_custom_lammps_dump
from v_ase.viewer import view


INPUT_FORMAT_ALIASES = {
    "poscar": "vasp",
    "contcar": "vasp",
    "vasp": "vasp",
    "xdatcar": "vasp-xdatcar",
    "vasp-xdatcar": "vasp-xdatcar",
    "vasp_xdatcar": "vasp-xdatcar",
    "vasprun": "vasp-xml",
    "vasprun.xml": "vasp-xml",
    "vasp-xml": "vasp-xml",
    "vasp_xml": "vasp-xml",
    "lammpstrj": "lammps-dump-text",
    "lammpsdump": "lammps-dump-text",
    "lammps-dump": "lammps-dump-text",
    "lammps_dump": "lammps-dump-text",
    "lammps-dump-text": "lammps-dump-text",
    "lammps_dump_text": "lammps-dump-text",
    "traj": "traj",
    "trajectory": "traj",
    "xyz": "xyz",
    "extxyz": "extxyz",
    "extendedxyz": "extxyz",
    "data": "lammps-data",
    "lammps-data": "lammps-data",
    "lammps_data": "lammps-data",
}


def package_version() -> str:
    try:
        return version("v_ase-gui")
    except PackageNotFoundError:
        return "0.0.16"


def resolve_input_format(fmt: str | None) -> str | None:
    if not fmt:
        return None
    key = fmt.strip().lower()
    return INPUT_FORMAT_ALIASES.get(key, fmt)


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
    gui.add_argument(
        "--format",
        "--input-format",
        dest="format",
        metavar="FORMAT",
        help=(
            "force the input file format when the filename is ambiguous. "
            "Common aliases: POSCAR, XDATCAR, vasprun.xml, lammpstrj, traj, xyz, extxyz, data. "
            "Raw ASE format names such as vasp-xml and lammps-data also work."
        ),
    )
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
    gui.add_argument(
        "--viz-only",
        action="store_true",
        help="open a lighter OVITO-style visualization mode; atom coordinate editing, deletion, and relaxation are disabled, while visual labels and display settings remain editable",
    )
    gui.set_defaults(func=run_gui)

    return parser


def _read_frames(path: Path, index: str, fmt: str | None):
    read_kwargs = {"index": index}
    resolved_format = resolve_input_format(fmt)
    if resolved_format:
        read_kwargs["format"] = resolved_format

    suffix = path.suffix.lower()
    if resolved_format == "lammps-dump-text" or (fmt is None and suffix in {".lammpstrj", ".dump"}):
        return read_custom_lammps_dump(path, index)

    def should_use_custom_extxyz(frames):
        if fmt not in {None, "extxyz", "xyz"} or suffix not in {".xyz", ".extxyz"}:
            return False
        for atoms in frames:
            if "atom_type" in atoms.arrays and any(symbol == "X" for symbol in atoms.get_chemical_symbols()):
                return True
        return False

    try:
        loaded = read(path, **read_kwargs)
    except (KeyError, TypeError, ValueError):
        if fmt not in {None, "extxyz", "xyz"} or path.suffix.lower() not in {".xyz", ".extxyz"}:
            raise
        loaded = read_custom_extxyz(path, index)
    frames = loaded if isinstance(loaded, list) else [loaded]
    if should_use_custom_extxyz(frames):
        return read_custom_extxyz(path, index)
    return frames


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
        viz_only=args.viz_only,
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
