import shlex
import json
import tomllib
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import molecule
from ase.io import write
import pytest

import v_ase.remote as remote
from v_ase.cli import build_parser, normalize_argv, run_api_command, run_gui
from v_ase.export import export_html_response
from v_ase.io import read_structure_frames, resolve_input_format
from v_ase.io import atom_labels
from v_ase.serialization import atoms_to_json
from v_ase.session import EditorSession
from v_ase.remote import (
    RemoteTarget,
    build_remote_gui_command,
    localize_remote_url,
    parse_remote_target,
)

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
    assert args.no_browser is False
    assert args.port is None
    assert args.show_bonds is True
    assert args.cli_mode is False
    assert args.volumetric_precision == "fp32"


def test_v_ase_gui_parser_accepts_headless_server_mode():
    parser = build_parser()
    args = parser.parse_args(["gui", "movie.extxyz", "--no-browser", "--port", "58039"])

    assert args.no_browser is True
    assert args.port == 58039


def test_v_ase_gui_parser_uses_cli_for_machine_readable_sessions():
    parser = build_parser()
    args = parser.parse_args(["gui", "movie.extxyz", "--cli"])

    assert args.cli_mode is True
    with pytest.raises(SystemExit):
        parser.parse_args(["gui", "movie.extxyz", "--for-ai"])


def test_v_ase_api_parser_accepts_structured_live_commands(tmp_path):
    parser = build_parser()
    params = tmp_path / "params.json"
    params.write_text('{"includePositions":false}', encoding="utf-8")
    args = parser.parse_args([
        "api",
        "http://127.0.0.1:49152/api/ai/command/workspace/workspace",
        "describe",
        "--params-file",
        str(params),
    ])

    assert args.command == "api"
    assert args.method == "describe"
    assert args.params_file == params
    assert normalize_argv(["api", "http://127.0.0.1/x", "ready"])[0] == "api"

    schema_args = parser.parse_args([
        "api",
        "http://127.0.0.1:49152/api/ai/command/workspace/workspace",
        "schema",
    ])
    assert schema_args.method == "schema"


def test_v_ase_api_saves_binary_data_urls(monkeypatch, tmp_path, capsys):
    parser = build_parser()
    output = tmp_path / "render.png"
    args = parser.parse_args([
        "api",
        "http://127.0.0.1:49152/api/ai/command/session/session",
        "render",
        "--params",
        '{"width":64,"height":64}',
        "--save",
        str(output),
    ])
    captured = {}

    class Response:
        ok = True

        @staticmethod
        def json():
            return {
                "protocol": "v_ase.ai.v1",
                "result": {
                    "filename": "render.png",
                    "dataUrl": "data:image/png;base64,iVBORw0KGgo=",
                },
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("requests.post", fake_post)

    assert run_api_command(args) == 0
    assert output.read_bytes() == b"\x89PNG\r\n\x1a\n"
    result = json.loads(capsys.readouterr().out)["result"]
    assert "dataUrl" not in result
    assert result["saved_to"] == str(output.resolve())
    assert captured["json"]["method"] == "render"
    assert captured["json"]["params"] == {"width": 64, "height": 64}


def test_scp_style_remote_target_is_detected_without_a_port_argument():
    target = parse_remote_target("physics:/data/trajectory.extxyz")

    assert target == RemoteTarget(
        host="physics",
        path="/data/trajectory.extxyz",
    )


def test_remote_target_supports_user_host_and_spaces():
    target = parse_remote_target("researcher@cluster:~/runs/final structure.vase")

    assert target == RemoteTarget(
        host="researcher@cluster",
        path="~/runs/final structure.vase",
    )


def test_windows_drive_and_existing_colon_paths_remain_local(tmp_path, monkeypatch):
    assert parse_remote_target(r"C:\data\POSCAR") is None

    local_file = tmp_path / "sample:frame.xyz"
    local_file.write_text("0\n\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert parse_remote_target(local_file.name) is None


def test_remote_gui_command_preserves_user_options_and_quotes_the_path():
    parser = build_parser()
    args = parser.parse_args(
        [
            "gui",
            "physics:/data/final structure.extxyz",
            "--index",
            "-1",
            "--format",
            "extxyz",
            "--show-bonds",
            "--interactive",
            "--cli",
            "--port",
            "49152",
        ]
    )
    target = parse_remote_target(args.file)

    assert target is not None
    command = shlex.split(build_remote_gui_command(args, target))
    assert command == [
        "v_ase",
        "gui",
        "--index",
        "-1",
        "--no-browser",
        "--stream-frames",
        "--format",
        "extxyz",
        "--interactive",
        "--no-block",
        "--",
        "/data/final structure.extxyz",
    ]


def test_remote_url_is_rewritten_to_the_automatically_selected_local_endpoint():
    remote_url = (
        "http://127.0.0.1:55363/workspace"
        "?workspace_id=workspace&session_id=session"
    )

    assert localize_remote_url(remote_url, 49152) == (
        "http://127.0.0.1:49152/workspace"
        "?workspace_id=workspace&session_id=session"
    )


def test_cli_mode_prints_one_machine_readable_handshake_and_keeps_session_alive(
    monkeypatch,
    capsys,
):
    parser = build_parser()
    args = parser.parse_args(["gui", "--cli"])
    captured = {}

    class FakeEditor:
        url = (
            "http://127.0.0.1:49152/workspace"
            "?workspace_id=workspace&session_id=session"
        )

        def close(self):
            captured["closed"] = True

    def fake_view(frames, **kwargs):
        captured["frames"] = frames
        captured["kwargs"] = kwargs
        return FakeEditor()

    monkeypatch.setattr("v_ase.cli.view", fake_view)
    monkeypatch.setattr("v_ase.cli.time.sleep", lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    class FakeStop:
        def set(self):
            captured["event_stream_stopped"] = True

    class FakeThread:
        def join(self, timeout=None):
            captured["event_stream_join_timeout"] = timeout

    def fake_start_event_stream(handshake):
        captured["stream_handshake"] = handshake
        return FakeStop(), FakeThread()

    monkeypatch.setattr(
        "v_ase.ai.start_collaboration_event_stream",
        fake_start_event_stream,
    )

    assert run_gui(args) == 0
    stdout = capsys.readouterr().out.strip()
    handshake = json.loads(stdout)
    assert handshake["protocol"] == "v_ase.ai.v1"
    assert handshake["status"] == "ready"
    assert handshake["session_id"] == "session"
    assert handshake["browser_api"] == "window.v_aseAI"
    assert handshake["command_transport"] == "http-json-bridge"
    assert handshake["command_url"].endswith("/api/ai/command/workspace/workspace")
    assert {"schema", "describe", "apply", "render", "export"}.issubset(
        handshake["command_methods"]
    )
    assert handshake["accepts_natural_language"] is False
    assert handshake["stdin_commands"] is False
    assert handshake["state_url"].endswith("/api/ai/state/session")
    assert handshake["events_url"].endswith("/api/ai/workspace-events/workspace")
    assert handshake["event_protocol"] == "v_ase.collaboration.v1"
    assert handshake["event_delivery"] == "ndjson-after-handshake"
    assert handshake["event_scope"] == "workspace"
    assert handshake["skill_path"].endswith(
        "/skills/visualizing-atomic-structures-with-v-ase/SKILL.md"
    )
    assert captured["kwargs"]["block"] is False
    assert captured["kwargs"]["open_browser"] is False
    assert captured["kwargs"]["show_bonds"] is True
    assert captured["closed"] is True
    assert captured["stream_handshake"] == handshake
    assert captured["event_stream_stopped"] is True
    assert captured["event_stream_join_timeout"] == pytest.approx(0.3)


def test_run_gui_delegates_remote_targets_before_local_file_validation(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["gui", "physics:/data/POSCAR"])
    captured = {}

    def fake_launch_remote_gui(received_args, target):
        captured["args"] = received_args
        captured["target"] = target
        return 0

    monkeypatch.setattr("v_ase.remote.launch_remote_gui", fake_launch_remote_gui)

    assert run_gui(args) == 0
    assert captured["target"] == RemoteTarget("physics", "/data/POSCAR")


def test_remote_launch_uses_explicit_port_only_for_the_local_endpoint(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(
        ["gui", "physics:/data/POSCAR", "--port", "49152", "--no-browser"]
    )
    target = RemoteTarget("physics", "/data/POSCAR")
    captured = {}

    class FakeProcess:
        def __init__(self, return_code):
            self.return_code = return_code
            self.stdout = None
            self.stderr = None
            self.terminated = False

        def poll(self):
            return self.return_code

        def terminate(self):
            self.terminated = True
            self.return_code = 0

        def wait(self, timeout=None):
            return self.return_code

    remote_process = FakeProcess(0)
    tunnel_process = FakeProcess(None)

    monkeypatch.setattr(remote.shutil, "which", lambda name: "/usr/bin/ssh")
    monkeypatch.setattr(
        remote.subprocess,
        "Popen",
        lambda *popen_args, **popen_kwargs: remote_process,
    )
    monkeypatch.setattr(
        remote,
        "_read_remote_url",
        lambda process, remote_target: (
            "http://127.0.0.1:55363/workspace?session_id=remote"
        ),
    )

    def fake_start_tunnel(
        ssh_executable,
        remote_target,
        remote_port,
        requested_local_port=None,
    ):
        captured["remote_port"] = remote_port
        captured["requested_local_port"] = requested_local_port
        return tunnel_process, requested_local_port

    monkeypatch.setattr(remote, "_start_tunnel", fake_start_tunnel)

    assert remote.launch_remote_gui(args, target) == 0
    assert captured == {
        "remote_port": 55363,
        "requested_local_port": 49152,
    }
    assert tunnel_process.terminated is True


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
    assert captured["kwargs"]["open_browser"] is True


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
    assert resolve_input_format("html") == "vase-html-project"
    assert resolve_input_format("CHGCAR") == "vasp-density"
    assert resolve_input_format("LOCPOT") == "vasp-potential"
    assert resolve_input_format("PARCHG") == "vasp-partial-density"
    assert resolve_input_format("cube") == "cube"
    assert resolve_input_format("xsf") == "xsf"
    assert resolve_input_format("espresso-in") == "espresso-in"


def test_v_ase_gui_opens_volumetric_input_with_grid_attached(tmp_path, monkeypatch):
    atoms = Atoms(
        "NaCl",
        positions=[[1.0, 1.0, 1.0], [3.0, 3.0, 3.0]],
        cell=[5.0, 5.0, 5.0],
        pbc=True,
    )
    values = np.linspace(-0.5, 0.8, 8 * 9 * 10).reshape(8, 9, 10)
    cube_path = tmp_path / "density.cube"
    write(cube_path, atoms, data=values, format="cube")
    captured = {}

    def fake_view(frames, **kwargs):
        captured["frames"] = frames
        captured["kwargs"] = kwargs
        return frames[0]

    monkeypatch.setattr("v_ase.cli.view", fake_view)

    args = build_parser().parse_args([
        "gui",
        str(cube_path),
        "--volumetric-precision",
        "fp64",
    ])
    assert run_gui(args) == 0
    assert len(captured["frames"]) == 1
    assert captured["frames"][0].get_chemical_symbols() == ["Na", "Cl"]
    datasets = captured["kwargs"]["volumetric_datasets"]
    assert len(datasets) == 1
    assert datasets[0].values.shape == values.shape
    assert datasets[0].values.dtype == np.float64
    assert captured["kwargs"]["initial_design_settings"]["display"][
        "volumetricPrecision"
    ] == "float64"
    display = captured["kwargs"]["initial_design_settings"]["display"]
    assert display["showVolumetric"] is True
    assert display["volumetricDatasetId"] == datasets[0].dataset_id
    assert display["volumetricLevel"] > 0
    assert display["volumetricSurfaceMode"] == "signed"


def test_v_ase_gui_keeps_constant_volumetric_input_hidden(tmp_path, monkeypatch):
    atoms = molecule("H2")
    atoms.set_cell([6.0, 6.0, 6.0])
    atoms.center()
    atoms.pbc = True
    values = np.full((8, 8, 8), 0.25, dtype=np.float32)
    cube_path = tmp_path / "constant.cube"
    write(cube_path, atoms, data=values, format="cube")
    captured = {}

    def fake_view(frames, **kwargs):
        captured["kwargs"] = kwargs
        return frames[0]

    monkeypatch.setattr("v_ase.cli.view", fake_view)
    args = build_parser().parse_args(["gui", str(cube_path)])

    assert run_gui(args) == 0
    display = captured["kwargs"]["initial_design_settings"]["display"]
    assert display["showVolumetric"] is False
    assert display["volumetricLevel"] is None
    assert display["volumetricSurfaceMode"] == "single"


def test_v_ase_gui_reopens_project_embedded_html(tmp_path, monkeypatch):
    atoms = molecule("H2O")
    session = EditorSession(
        "html-cli-source",
        atoms.copy(),
        atoms.copy(),
        config={"viz_only": True},
    )
    settings = {
        "display": {
            "showBonds": True,
            "supercell": [2, 1, 1],
            "viewportBackground": "white",
        }
    }
    response = export_html_response(
        session,
        {
            "positions": atoms.positions.tolist(),
            "settings": settings,
            "document_name": "water.vasp",
            "embed_project": True,
        },
    )
    html_path = tmp_path / "water_project.html"
    html_path.write_bytes(response.body)

    captured = {}

    def fake_view(frames, **kwargs):
        captured["frames"] = frames
        captured["kwargs"] = kwargs
        return frames[0]

    monkeypatch.setattr("v_ase.cli.view", fake_view)
    args = build_parser().parse_args(["gui", str(html_path)])

    assert run_gui(args) == 0
    assert len(captured["frames"]) == 1
    assert captured["frames"][0].get_chemical_formula() == "H2O"
    assert captured["kwargs"]["initial_design_settings"]["display"]["supercell"] == [2, 1, 1]

    lightweight = export_html_response(
        session,
        {
            "positions": atoms.positions.tolist(),
            "settings": settings,
            "document_name": "water.vasp",
            "embed_project": False,
        },
    )
    lightweight_path = tmp_path / "water_view_only.html"
    lightweight_path.write_bytes(lightweight.body)
    lightweight_args = build_parser().parse_args(["gui", str(lightweight_path)])
    with pytest.raises(SystemExit, match="no embedded .vase project"):
        run_gui(lightweight_args)


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
    assert args.show_bonds is True

    interactive = parser.parse_args(["gui", "movie.extxyz", "--interactive"])
    assert interactive.interactive is True

    hidden = parser.parse_args(["gui", "movie.extxyz", "--hide-bonds"])
    assert hidden.show_bonds is False

    agent = parser.parse_args(["gui", "movie.extxyz", "--cli"])
    assert agent.cli_mode is True


def test_v_ase_visualize_import_path_exposes_view():
    from v_ase.visualize import view

    assert callable(view)


def test_pyproject_exposes_v_ase_console_script():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert config["project"]["scripts"]["v_ase"] == "v_ase.cli:main"
    assert config["project"]["name"] == "v_ase-gui"
    package_data = config["tool"]["setuptools"]["package-data"]["v_ase"]
    assert "skills_v_ase.md" in package_data
    assert "skills/visualizing-atomic-structures-with-v-ase/SKILL.md" in package_data
    assert "skills/visualizing-atomic-structures-with-v-ase/references/*.md" in package_data


def test_read_structure_frames_supports_single_structure_files(tmp_path):
    path = tmp_path / "POSCAR"
    atoms = molecule("H2O")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc([True, True, True])
    write(path, atoms, format="vasp")

    frames = read_structure_frames(path, "-1", None)

    assert len(frames) == 1
    assert frames[0].get_chemical_formula() == "H2O"


def test_read_structure_frames_uses_format_alias_for_extensionless_poscar(tmp_path):
    path = tmp_path / "ABCD"
    atoms = molecule("H2O")
    atoms.set_cell([8, 8, 8])
    atoms.set_pbc([True, True, True])
    write(path, atoms, format="vasp")

    frames = read_structure_frames(path, "-1", "POSCAR")

    assert len(frames) == 1
    assert frames[0].get_chemical_formula() == "H2O"


def test_repeated_poscar_species_blocks_become_distinct_labels(tmp_path):
    path = tmp_path / "POSCAR"
    path.write_text(
        """Repeated oxygen blocks
1.0
8.0 0.0 0.0
0.0 8.0 0.0
0.0 0.0 8.0
O Cu O
1 2 3
Direct
0.00 0.00 0.00
0.15 0.00 0.00
0.30 0.00 0.00
0.45 0.00 0.00
0.60 0.00 0.00
0.75 0.00 0.00
"""
    )

    frames = read_structure_frames(path, "-1", None)

    assert frames[0].get_chemical_symbols() == ["O", "Cu", "Cu", "O", "O", "O"]
    assert atom_labels(frames[0]) == ["O1", "Cu", "Cu", "O2", "O2", "O2"]
    payload = atoms_to_json(frames[0])
    assert payload["labels"] == ["O1", "Cu", "Cu", "O2", "O2", "O2"]
    assert payload["chemical_symbols"] == ["O", "Cu", "Cu", "O", "O", "O"]


def test_repeated_vasp_species_labels_follow_every_original_block(tmp_path):
    path = tmp_path / "material.input"
    path.write_text(
        """Multiple repeated species
1.0
9.0 0.0 0.0
0.0 9.0 0.0
0.0 0.0 9.0
O Cu O Cu O
1 1 2 1 1
Selective dynamics
Direct
0.00 0.00 0.00 T T T
0.15 0.00 0.00 T T T
0.30 0.00 0.00 T T T
0.45 0.00 0.00 T T T
0.60 0.00 0.00 T T T
0.75 0.00 0.00 T T T
"""
    )

    frames = read_structure_frames(path, "-1", "CONTCAR")

    assert frames[0].get_chemical_symbols() == ["O", "Cu", "O", "O", "Cu", "O"]
    assert atom_labels(frames[0]) == ["O1", "Cu1", "O2", "O2", "Cu2", "O3"]


def test_read_structure_frames_supports_multi_frame_files(tmp_path):
    path = tmp_path / "movie.extxyz"
    first = molecule("H2O")
    second = molecule("H2O")
    second.positions += [1.0, 0.0, 0.0]
    write(path, [first, second])

    frames = read_structure_frames(path, ":", None)

    assert len(frames) == 2


def test_read_structure_frames_preserves_custom_extxyz_atom_types(tmp_path):
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

    frames = read_structure_frames(path, ":", None)
    data = atoms_to_json(frames[0])

    assert frames[0].get_chemical_symbols() == ["H", "H", "O"]
    assert atom_labels(frames[0]) == ["H_type5", "H_type7", "O_type2"]
    assert data["symbols"] == ["H_type5", "H_type7", "O_type2"]
    assert data["chemical_symbols"] == ["H", "H", "O"]
    assert data["visual"]["colors"] == data["visual"]["base_colors"]
    assert data["visual"]["colors"][0] == data["visual"]["colors"][1]
    assert data["visual"]["colors"][2] == data["visual"]["element_colors"]["O"]


def test_read_structure_frames_keeps_integer_atom_types_as_raw_labels_when_mass_is_missing(tmp_path):
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

    frames = read_structure_frames(path, ":", None)
    data = atoms_to_json(frames[0])

    assert frames[0].get_chemical_symbols() == ["H", "H", "H"]
    assert atom_labels(frames[0]) == ["1", "2", "3"]
    assert data["symbols"] == ["1", "2", "3"]
    assert data["chemical_symbols"] == ["H", "H", "H"]


def test_read_structure_frames_uses_mass_to_guess_integer_atom_type_base_symbol(tmp_path):
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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "Si"]
    assert atom_labels(frames[0]) == ["1", "2"]


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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_labels(frames[0]) == ["8", "1", "1"]


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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_labels(frames[0]) == ["8", "1", "1"]


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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H", "H"]
    assert atom_labels(frames[0]) == ["1", "2", "2"]
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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["O", "H"]
    assert atom_labels(frames[0]) == ["8", "1"]


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

    frames = read_structure_frames(path, ":", None)

    assert frames[0].get_chemical_symbols() == ["H", "H"]
    assert atom_labels(frames[0]) == ["999", "119"]
