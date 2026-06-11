from ase.build import molecule
from ase.io import write

from v_ase.cli import _read_frames, build_parser, normalize_argv, resolve_input_format
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


def test_format_aliases_resolve_to_ase_format_names():
    assert resolve_input_format("POSCAR") == "vasp"
    assert resolve_input_format("CONTCAR") == "vasp"
    assert resolve_input_format("XDATCAR") == "vasp-xdatcar"
    assert resolve_input_format("vasprun.xml") == "vasp-xml"
    assert resolve_input_format("lammpstrj") == "lammps-dump-text"
    assert resolve_input_format("traj") == "traj"
    assert resolve_input_format("xyz") == "xyz"
    assert resolve_input_format("data") == "lammps-data"
    assert resolve_input_format("espresso-in") == "espresso-in"


def test_v_ase_gui_parser_accepts_input_format_alias():
    parser = build_parser()
    args = parser.parse_args(["gui", "ABCD", "--format", "vasprun.xml"])

    assert args.file == "ABCD"
    assert args.format == "vasprun.xml"


def test_v_ase_gui_parser_accepts_viz_only_mode():
    parser = build_parser()
    args = parser.parse_args(["gui", "movie.extxyz", "--viz-only"])

    assert args.file == "movie.extxyz"
    assert args.viz_only is True


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


def test_read_frames_uses_format_alias_for_extensionless_poscar(tmp_path):
    path = tmp_path / "ABCD"
    atoms = molecule("H2O")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc([True, True, True])
    write(path, atoms, format="vasp")

    frames = _read_frames(path, "-1", "POSCAR")

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


def test_read_frames_maps_integer_atom_types_to_h_labels_when_mass_is_missing(tmp_path):
    path = tmp_path / "typed_integer.extxyz"
    path.write_text(
        "\n".join([
            "3",
            "Properties=atom_type:I:1:pos:R:3",
            "1 0.0 0.0 0.0",
            "2 1.0 0.0 0.0",
            "3 0.0 1.0 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)
    data = atoms_to_json(frames[0])

    assert frames[0].get_chemical_symbols() == ["H", "H", "H"]
    assert atom_type_labels(frames[0]) == ["H_1", "H_2", "H_3"]
    assert data["symbols"] == ["H_1", "H_2", "H_3"]
    assert data["chemical_symbols"] == ["H", "H", "H"]


def test_read_frames_uses_mass_to_guess_integer_atom_type_base_symbol(tmp_path):
    path = tmp_path / "typed_integer_mass.extxyz"
    path.write_text(
        "\n".join([
            "2",
            "Properties=atom_type:I:1:mass:R:1:pos:R:3",
            "1 15.999 0.0 0.0 0.0",
            "2 28.085 1.0 0.0 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "Si"]
    assert atom_type_labels(frames[0]) == ["O_1", "Si_2"]
