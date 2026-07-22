import tomllib
from pathlib import Path

from ase.build import molecule
from ase.io import write

from v_ase.cli import _read_frames, build_parser, normalize_argv, resolve_input_format, run_gui
from v_ase.io import atom_type_labels
from v_ase.serialization import atoms_to_json

ROOT = Path(__file__).resolve().parents[1]


def test_v_ase_gui_parser_accepts_ase_gui_style_file_argument():
    parser = build_parser()
    args = parser.parse_args(["gui", "XXXX.vasp"])

    assert args.command == "gui"
    assert args.file == "XXXX.vasp"
    assert args.index == ":"


def test_v_ase_gui_parser_accepts_an_empty_workspace():
    parser = build_parser()
    args = parser.parse_args(["gui"])

    assert args.command == "gui"
    assert args.file is None
    assert args.interactive is False


def test_v_ase_gui_without_file_launches_an_empty_visualization_session(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["gui"])
    captured = {}

    def fake_view(frames, **kwargs):
        captured["frames"] = frames
        captured["kwargs"] = kwargs
        return frames[0]

    monkeypatch.setattr("v_ase.cli.view", fake_view)

    assert run_gui(args) == 0
    assert len(captured["frames"]) == 1
    assert len(captured["frames"][0]) == 0
    assert captured["kwargs"]["viz_only"] is True


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
    assert resolve_input_format("vase") == "vase-project"
    assert resolve_input_format("espresso-in") == "espresso-in"


def test_v_ase_gui_parser_accepts_input_format_alias():
    parser = build_parser()
    args = parser.parse_args(["gui", "ABCD", "--format", "vasprun.xml"])

    assert args.file == "ABCD"
    assert args.format == "vasprun.xml"


def test_v_ase_gui_parser_defaults_to_visualization_mode_and_accepts_interactive_mode():
    parser = build_parser()
    args = parser.parse_args(["gui", "movie.extxyz"])

    assert args.file == "movie.extxyz"
    assert args.interactive is False

    interactive = parser.parse_args(["gui", "movie.extxyz", "--interactive"])
    assert interactive.interactive is True


def test_v_ase_visualize_import_path_exposes_view():
    from v_ase.visualize import view

    assert callable(view)


def test_pyproject_exposes_v_ase_console_script():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert config["project"]["scripts"]["v_ase"] == "v_ase.cli:main"
    assert config["project"]["name"] == "v_ase-gui"


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
    assert data["visual"]["colors"] == data["visual"]["base_colors"]
    assert data["visual"]["colors"][0] == data["visual"]["colors"][1]
    assert data["visual"]["colors"][2] == data["visual"]["element_colors"]["O"]


def test_read_frames_keeps_integer_atom_types_as_raw_labels_when_mass_is_missing(tmp_path):
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
    assert atom_type_labels(frames[0]) == ["1", "2", "3"]
    assert data["symbols"] == ["1", "2", "3"]
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
    assert atom_type_labels(frames[0]) == ["1", "2"]


def test_lammpstrj_integer_types_are_raw_labels_and_valid_atomic_numbers(tmp_path):
    path = tmp_path / "water.lammpstrj"
    path.write_text(
        "\n".join([
            "ITEM: TIMESTEP",
            "0",
            "ITEM: NUMBER OF ATOMS",
            "3",
            "ITEM: BOX BOUNDS pp pp pp",
            "0 10",
            "0 10",
            "0 10",
            "ITEM: ATOMS id type x y z",
            "1 8 0.0 0.0 0.0",
            "2 1 0.9 0.0 0.0",
            "3 1 -0.3 0.8 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_type_labels(frames[0]) == ["8", "1", "1"]


def test_lammpstrj_mass_column_guesses_integer_type_base_symbol(tmp_path):
    path = tmp_path / "water_mass.lammpstrj"
    path.write_text(
        "\n".join([
            "ITEM: TIMESTEP",
            "0",
            "ITEM: NUMBER OF ATOMS",
            "3",
            "ITEM: BOX BOUNDS pp pp pp",
            "0 10",
            "0 10",
            "0 10",
            "ITEM: ATOMS id type mass x y z",
            "1 8 15.999 0.0 0.0 0.0",
            "2 1 1.008 0.9 0.0 0.0",
            "3 1 1.008 -0.3 0.8 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_type_labels(frames[0]) == ["8", "1", "1"]


def test_lammps_data_reads_type_labels_and_mass_guessed_symbols(tmp_path):
    path = tmp_path / "water.data"
    path.write_text(
        "\n".join([
            "LAMMPS data file",
            "",
            "3 atoms",
            "2 atom types",
            "",
            "0.0 10.0 xlo xhi",
            "0.0 10.0 ylo yhi",
            "0.0 10.0 zlo zhi",
            "",
            "Masses",
            "",
            "1 15.999",
            "2 1.008",
            "",
            "Atoms # full",
            "",
            "1 1 1 -0.8 0.0 0.0 0.0",
            "2 1 2 0.4 0.9 0.0 0.0",
            "3 1 2 0.4 -0.3 0.8 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_type_labels(frames[0]) == ["1", "2", "2"]
    assert frames[0].get_initial_charges().tolist() == [-0.8, 0.4, 0.4]


def test_lammps_data_without_masses_uses_valid_type_ids_as_atomic_numbers(tmp_path):
    path = tmp_path / "bare_types.data"
    path.write_text(
        "\n".join([
            "LAMMPS data file",
            "",
            "2 atoms",
            "8 atom types",
            "",
            "0.0 10.0 xlo xhi",
            "0.0 10.0 ylo yhi",
            "0.0 10.0 zlo zhi",
            "",
            "Atoms # atomic",
            "",
            "1 8 0.0 0.0 0.0",
            "2 1 1.0 0.0 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H"]
    assert atom_type_labels(frames[0]) == ["8", "1"]


def test_lammps_data_arbitrary_type_ids_fall_back_to_raw_labels(tmp_path):
    path = tmp_path / "large_type_id.data"
    path.write_text(
        "\n".join([
            "LAMMPS data file",
            "",
            "2 atoms",
            "999 atom types",
            "",
            "0.0 10.0 xlo xhi",
            "0.0 10.0 ylo yhi",
            "0.0 10.0 zlo zhi",
            "",
            "Atoms # atomic",
            "",
            "1 999 0.0 0.0 0.0",
            "2 119 1.0 0.0 0.0",
            "",
        ])
    )

    frames = _read_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["H", "H"]
    assert atom_type_labels(frames[0]) == ["999", "119"]
