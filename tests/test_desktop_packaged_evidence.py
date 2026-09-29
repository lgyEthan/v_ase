"""A successful process exit cannot substitute for completed desktop checks."""
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("evidence", ["", "{", "{}", "wrong-version", "missing-pixels", "clipped-action", "complete"])
def test_packaged_runner_requires_complete_evidence(tmp_path, monkeypatch, evidence):
    root = Path(__file__).resolve().parents[1] / "desktop"
    executable = tmp_path / "v_ase.exe"
    executable.touch()
    output = tmp_path / "evidence"
    report = {
        "version": json.loads((root / "package.json").read_text())["version"],
        "commands": 10, "geometryRoutes": 75, "oxygenPixels": 120,
        **dict.fromkeys(("nativeControlA", "verticalCutoffTab", "droppedFileGrant",
                        "detachedWindow", "detachedSave", "transferRollback",
                        "openNewWindow", "independentWindowClose", "nativeKeyInput",
                        "nativeSave", "scientificProject", "openNewTab",
                        "quitCancellation", "nodeIsolation", "lastDocumentClosesWindow",
                        "emptyLastWindowRequestsQuit", "multiFileOpen", "osOpenBatch", "cellAxisShortcuts"), True),
    }
    report["visualParity"] = {
        "pixelChecks": [{"mode": mode, "outlinePixels": 250, "constraintPixels": 300}
                        for mode in ("2d", "3d")],
        "layoutChecks": [{"zoom": zoom, "scroll": ["inspector-content"],
                          "reachable": True, "relaxHost": True}
                         for zoom in (1, 1.25, 1.5)],
    }
    if evidence == "missing-pixels":
        report["visualParity"]["pixelChecks"][1]["constraintPixels"] = 0
    if evidence == "clipped-action":
        report["visualParity"]["layoutChecks"][2]["reachable"] = False
    if evidence == "wrong-version":
        report["version"] = "0.0.0"
    contents = json.dumps(report) if evidence in {"wrong-version", "missing-pixels", "clipped-action", "complete"} else evidence

    def process_exit_zero(*_args, **_kwargs):
        # Model the exact observed failure: exit zero, but an empty result file.
        (output / "result.json").write_text(contents)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setenv("V_ASE_SMOKE_DIR", str(output))
    monkeypatch.setattr("sys.argv", ["test_packaged.py", "--app", str(executable)])
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("subprocess.run", process_exit_zero)
    if evidence == "complete":
        runpy.run_path(str(root / "scripts/test_packaged.py"), run_name="__main__")
    else:
        with pytest.raises(SystemExit, match="evidence|required regression check|native selection/constraint"):
            runpy.run_path(str(root / "scripts/test_packaged.py"), run_name="__main__")
