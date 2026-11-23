"""Verify real project-scoped npx installation without modifying user clients."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "visualizing-atomic-structures-with-v-ase"
SKILLS_CLI_VERSION = "1.9.0"
# Codex and Cursor share the universal project directory in this CLI version.
CLIENT_DIRECTORIES = {"claude-code": ".claude", "codex": ".agents", "cursor": ".agents"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ROOT), help="Local checkout or GitHub source to install")
    parser.add_argument("--output", type=Path, help="Optional verification JSON")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "skills.sh.json").read_text())
    containers = [(ROOT / path).resolve() for path in manifest["paths"]]
    assert all(path.is_relative_to(ROOT) for path in containers), "Discovery paths must stay in this repository"
    canonical = ROOT / "v_ase" / "skills" / SKILL_NAME
    assert any(canonical.is_relative_to(path) for path in containers), "Canonical Skill is not discoverable"
    expected = {
        path.relative_to(canonical).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in canonical.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    assert "SKILL.md" in expected and "references/native-tools.md" in expected
    npx = shutil.which("npx")
    assert shutil.which("node") and npx, "Node.js 22.20+ and npx are required"
    with tempfile.TemporaryDirectory(prefix="vase-skill-install-") as directory:
        sandbox = Path(directory)
        environment = dict(os.environ)
        environment.update(
            DO_NOT_TRACK="1",
            npm_config_cache=str(sandbox / "npm-cache"),
            NODE_COMPILE_CACHE=str(sandbox / "node-cache"),
            XDG_CACHE_HOME=str(sandbox / "cache"),
        )
        command = [
            npx, "--yes", f"skills@{SKILLS_CLI_VERSION}", "add", args.source,
            "--skill", SKILL_NAME, "-a", "claude-code", "codex", "cursor", "--copy", "-y",
        ]
        result = subprocess.run(command, cwd=sandbox, env=environment, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        installed = []
        for client, base in CLIENT_DIRECTORIES.items():
            destination = sandbox / base / "skills" / SKILL_NAME
            assert destination.is_dir(), f"Missing project installation: {base}"
            for name, digest in expected.items():
                path = destination / name
                assert path.is_file(), f"Missing installed resource: {base}/{name}"
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"Changed resource: {base}/{name}"
            installed.append({"client": client, "project_directory": base, "files_matched": len(expected)})
        assert (sandbox / "skills-lock.json").is_file(), "Installer did not record its project lock"
        record = {
            "cli_version": SKILLS_CLI_VERSION,
            "source": args.source,
            "skill": SKILL_NAME,
            "installations": installed,
            "project_scope_only": True,
            "temporary_directory_removed_after_check": True,
            "mcp_configuration_modified": False,
        }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
