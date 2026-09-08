"""Personal tunnel setup must preserve locality, secrets and process ownership."""
from argparse import Namespace
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import zipfile

import pytest

from v_ase import chatgpt
from v_ase.cli import build_parser, normalize_argv


def configure(directory, **changes):
    values = dict(data_dir=directory, tunnel_id=None, app_id=None, port=None,
                  connect=None, file=None, interactive=False)
    values.update(changes)
    return chatgpt.configure(Namespace(**values))


def test_chatgpt_command_does_not_become_a_structure_filename():
    assert normalize_argv(["chatgpt", "doctor"]) == ["chatgpt", "doctor"]
    args = build_parser().parse_args(["chatgpt", "start", "--local-only"])
    assert args.chatgpt_function is chatgpt.start
    assert args.local_only


def test_prepare_without_credentials_is_explicitly_not_connected(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROL_PLANE_API_KEY", "test-secret-never-write")
    result = configure(tmp_path)
    assert result["status"] == "awaiting_tunnel_id"
    config = (tmp_path / "connection.json").read_text()
    assert "test-secret-never-write" not in config
    assert "api_key" not in config
    if os.name == "posix":
        assert (tmp_path / "connection.json").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("identifier", ["fake", "tunnel_", "tunnel_../../secret", "tunnel_12345678\nextra"])
def test_invalid_tunnel_identifiers_fail_without_a_profile(tmp_path, identifier):
    with pytest.raises(ValueError, match="actual tunnel_"):
        configure(tmp_path, tunnel_id=identifier)
    assert not (tmp_path / "profiles").exists()


def test_configuration_does_not_overwrite_an_unrelated_directory(tmp_path):
    keep = tmp_path / "important.txt";keep.write_text("preserve")
    with pytest.raises(ValueError, match="empty directory"):
        configure(tmp_path)
    assert keep.read_text() == "preserve"


def test_connect_and_interactive_fail_before_touching_the_existing_gui(tmp_path):
    with pytest.raises(ValueError, match="existing GUI's mode"):
        configure(tmp_path, connect="http://127.0.0.1:9999/command", interactive=True)
    assert not (tmp_path / "connection.json").exists()


def test_file_workspace_is_distinct_from_private_runtime_and_survives_reconfigure(tmp_path):
    workspace = tmp_path / "structures"; workspace.mkdir()
    runtime = tmp_path / "runtime"
    configure(runtime, workspace=workspace)
    configure(runtime, port=8767)
    assert chatgpt._load(runtime)["working_directory"] == str(workspace)


@pytest.mark.parametrize("value", [[], {"schema": chatgpt.SCHEMA, "port": 8766, "file": ["bad"]}])
def test_malformed_configuration_is_a_readable_error(tmp_path, value):
    (tmp_path / "connection.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        chatgpt._load(tmp_path)


def test_bootstrap_rejects_an_existing_environment_with_system_packages(tmp_path):
    from v_ase.chatgpt_bootstrap import install
    (tmp_path / ".vase-runtime.json").write_text(json.dumps({"schema": chatgpt.SCHEMA}))
    runtime = tmp_path / "runtime"; runtime.mkdir()
    (runtime / "pyvenv.cfg").write_text("include-system-site-packages = true\n")
    with pytest.raises(ValueError, match="includes system packages"):
        install(Namespace(data_dir=tmp_path))


def test_tunnel_key_and_overrides_are_not_inherited_by_gui_children(monkeypatch):
    for key in ("CONTROL_PLANE_API_KEY", "OPENAI_API_KEY", "OPENAI_ADMIN_KEY"):
        monkeypatch.setenv(key, "test-secret")
    monkeypatch.setenv("CONTROL_PLANE_BASE_URL", "https://wrong.example")
    monkeypatch.setenv("TUNNEL_CLIENT_PROFILE", "unrelated")
    env = chatgpt._environment()
    assert all(key not in env for key in ("CONTROL_PLANE_API_KEY", "OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "CONTROL_PLANE_BASE_URL", "TUNNEL_CLIENT_PROFILE"))
    tunnel = chatgpt._environment(runtime_key="runtime-only")
    assert tunnel["CONTROL_PLANE_API_KEY"] == "runtime-only"
    assert "OPENAI_ADMIN_KEY" not in tunnel


def test_plugin_requires_a_real_registration_and_never_packages_runtime_data(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime";configure(runtime)
    (runtime / "private.log").write_text("PRIVATE")
    (runtime / "artifacts").mkdir();(runtime / "artifacts" / "private.vase").write_text("PRIVATE")
    args = Namespace(data_dir=runtime, app_id=None, output=tmp_path / "bundle" / "v-ase-local")
    with pytest.raises(ValueError, match="register the running tunnel"):
        chatgpt.package_plugin(args)
    assert not args.output.exists()
    # Registration identity is a fixture, never presented as a live connection.
    args.app_id = "plugin_asdk_app_0123456789abcdef0123456789abcdef"
    result = chatgpt.package_plugin(args)
    manifest = json.loads((args.output / ".codex-plugin/plugin.json").read_text())
    assert manifest["apps"] == "./.app.json"
    mapping = json.loads((args.output / ".app.json").read_text())
    assert mapping == {"apps": {"v_ase": {"id": args.app_id}}}
    assert not (args.output / ".mcp.json").exists()  # ChatGPT must not call cloud localhost.
    with zipfile.ZipFile(result["zip"]) as archive:
        names = archive.namelist()
        assert any(n.endswith("scripts/install_local.py") for n in names)
        assert any(n.endswith("scripts/chatgpt_bridge.py") for n in names)
        assert not any("private" in n or "connection.json" in n or "profiles/" in n for n in names)


def test_existing_zip_rejection_does_not_change_the_registration(tmp_path):
    runtime = tmp_path / "runtime";configure(runtime)
    old = (runtime / "connection.json").read_bytes()
    destination = tmp_path / "v-ase-local"
    (tmp_path / "v-ase-local.zip").write_bytes(b"preserve")
    with pytest.raises(ValueError, match="ZIP already exists"):
        chatgpt.package_plugin(Namespace(data_dir=runtime, app_id="plugin_asdk_app_0123456789abcdef", output=destination))
    assert not destination.exists()
    assert (runtime / "connection.json").read_bytes() == old


def test_health_probe_rejects_nonlocal_urls_before_a_request(tmp_path):
    (tmp_path / "tunnel-health.url").write_text("https://remote.example")
    with pytest.raises(ValueError, match="Invalid local"):
        chatgpt._health(tmp_path)


def test_run_lock_prevents_duplicate_servers(tmp_path):
    with chatgpt._run_lock(tmp_path):
        with pytest.raises(ValueError, match="already running"):
            with chatgpt._run_lock(tmp_path):
                pytest.fail("second runtime acquired the same lock")


def test_real_tunnel_client_generates_an_environment_reference_profile(tmp_path):
    import shutil
    binary = shutil.which("tunnel-client")
    if not binary:
        pytest.skip("Official tunnel-client is a separately installed optional runtime")
    configure(tmp_path, tunnel_id="tunnel_0123456789abcdef0123456789abcdef")
    text = (tmp_path / "profiles/v-ase-local.yaml").read_text()
    assert "env:CONTROL_PLANE_API_KEY" in text
    assert "http://127.0.0.1:8766/mcp" in text
    assert "127.0.0.1:0" in text


def test_local_launcher_is_real_mcp_and_sigterm_stops_its_owned_servers(tmp_path):
    from v_ase.viewer import find_free_port
    import shutil
    import venv
    # Install the current package copy without changing the developer's global
    # environment. Dependency sharing keeps this subprocess regression small;
    # the production bootstrap is separately checked for full isolation.
    env_dir = tmp_path.parent / (tmp_path.name + "-python")
    venv.EnvBuilder(system_site_packages=True, with_pip=False).create(env_dir)
    site_packages = env_dir / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    shutil.copytree(Path(chatgpt.__file__).parent, site_packages / "v_ase", ignore=shutil.ignore_patterns("__pycache__"))
    python = env_dir / "bin/python"
    port = find_free_port()
    workspace = tmp_path.parent / (tmp_path.name + "-structures"); workspace.mkdir()
    # Both MCP and its nested GUI must use installed code, even when the
    # structure workspace happens to contain a same-named Python module.
    (workspace / "v_ase.py").write_text("raise RuntimeError('Do not import code from the structure workspace')\n")
    configure(tmp_path, port=port, workspace=workspace)
    env = os.environ.copy()
    env.pop("CONTROL_PLANE_API_KEY", None)
    process = subprocess.Popen([str(python), "-I", "-m", "v_ase.cli", "chatgpt", "start", "--local-only",
        "--no-browser", "--data-dir", str(tmp_path), "--startup-timeout", "35"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    state_path = tmp_path / "state.json"
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(process.stdout.read())
            if state_path.exists():
                state = json.loads(state_path.read_text())
                if state.get("status") == "local_ready":
                    break
            time.sleep(.1)
        else:
            pytest.fail("Local MCP did not become ready")
        assert state["tool_count"] >= 100
        assert state["gui_backend_ready"]
        assert not (tmp_path / "profiles").exists()
        # A browser tab closing must not stop a foreground CLI/MCP-owned GUI.
        import requests
        from urllib.parse import urlsplit, parse_qs
        url = urlsplit(state["human_url"])
        workspace_id = parse_qs(url.query)["workspace_id"][0]
        http = requests.Session(); http.trust_env = False
        response = http.post(f"{url.scheme}://{url.netloc}/api/workspace/{workspace_id}/browser-close/test-browser", timeout=5)
        assert response.ok
        time.sleep(1.5)  # Beyond the browser-disconnect grace period (1.2 s).
        import asyncio
        assert asyncio.run(chatgpt.probe_mcp(state["mcp_url"]))["gui_backend_ready"]
        http.close()
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=12)
        assert json.loads(state_path.read_text())["status"] == "stopped"
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0
        if state.get("human_url"):
            from urllib.parse import urlsplit
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", urlsplit(state["human_url"]).port)) != 0
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=12)
