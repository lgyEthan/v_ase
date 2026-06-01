from ase.build import molecule
from ase.io import write

from v_ase.cli import _read_frames, build_parser, normalize_argv
from v_ase.io import atom_type_labels
from v_ase.serialization import atoms_to_json


def test_v_ase_gui_parser_accepts_ase_gui_style_file_argument():
    parser = build_parser()
    args = parser.parse_args(["gui", "XXXX.vasp"])

    assert args.command == "gui"
    assert args.file == "XXXX.vasp"
    assert args.index == ":"


def test_v_ase_accepts_direct_file_argument_as_gui_alias():
    assert normalize_argv(["POSCAR"]) == ["gui", "POSCAR"]


def test_v_ase_visualize_import_path_exposes_view():
    from v_ase.visualize import view

    assert callable(view)


def test_read_frames_supports_single_structure_files(tmp_path):
    path = tmp_path / "POSCAR"
    atoms = molecule("H2O")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc([True, True, True])
    write(path, atoms, format="vasp")

    frames = _read_frames(path, "-1", None)

    assert len(frames) == 1
    assert frames[0].get_chemical_formula() == "H2O"


def test_read_frames_supports_multi_frame_files(tmp_path):
    path = tmp_path / "movie.extxyz"
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [1.0, 0.0, 0.0]
    write(path, [first, second])

    frames = _read_frames(path, ":", None)

    assert len(frames) == 2


def test_read_frames_preserves_custom_extxyz_atom_types(tmp_path):
    path = tmp_path / "typed.extxyz"
    path.write_text(
        "\n".join([
            "3",
            'Lattice="10 0 0 0 11 0 0 0 12" Properties=species:S:1:pos:R:3 info="typed"',
            "H_type5 0.0 0.0 0.0",
            "H_type7 1.0 0.0 0.0",
            "O_type2 0.0 1.0 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)
    data = atoms_to_json(frames[0])

    assert frames[0].get_chemical_symbols() == ["H", "H", "O"]
    assert atom_type_labels(frames[0]) == ["H_type5", "H_type7", "O_type2"]
    assert data["symbols"] == ["H_type5", "H_type7", "O_type2"]
    assert data["chemical_symbols"] == ["H", "H", "O"]
    assert data["visual"]["colors"][0] != data["visual"]["colors"][1]
