import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_trajectory_module(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the standalone trajectory module test")
    command = (
        "import {interpolateTrajectoryFrames, interpolatedFrameCount} "
        "from './v_ase/static/trajectory.js';"
        + script
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_video_interpolation_multiplier_and_periodic_mic_path():
    result = run_trajectory_module(
        """
        const first = {
            positions: [[9.5, 0, 0]],
            cell: [[10, 0, 0], [0, 10, 0], [0, 0, 10]],
            pbc: [true, true, true]
        };
        const second = {
            positions: [[0.5, 0, 0]],
            cell: first.cell,
            pbc: first.pbc
        };
        const direct = interpolateTrajectoryFrames(first, second, 0.5, {useMic: false});
        const mic = interpolateTrajectoryFrames(first, second, 0.5, {useMic: true});
        console.log(JSON.stringify({
            frames: interpolatedFrameCount(3, 2),
            direct: [...direct.positions],
            mic: [...mic.positions],
            micApplied: mic.micApplied
        }));
        """
    )

    assert result == {
        "frames": 5,
        "direct": [5, 0, 0],
        "mic": [0, 0, 0],
        "micApplied": True,
    }


def test_video_mic_interpolation_uses_each_frames_cell():
    result = run_trajectory_module(
        """
        const first = {
            positions: [[9, 0, 0]],
            cell: [[10, 0, 0], [2, 8, 0], [0, 0, 10]],
            pbc: [true, true, false]
        };
        const second = {
            positions: [[2.4, 0, 0]],
            cell: [[12, 0, 0], [3, 9, 0], [0, 0, 10]],
            pbc: [true, true, false]
        };
        const midpoint = interpolateTrajectoryFrames(first, second, 0.5, {useMic: true});
        console.log(JSON.stringify({
            position: [...midpoint.positions],
            cell: midpoint.cell,
            micApplied: midpoint.micApplied
        }));
        """
    )

    assert result["micApplied"] is True
    assert result["cell"] == [[11, 0, 0], [2.5, 8.5, 0], [0, 0, 10]]
    assert result["position"] == pytest.approx([0.55, 0, 0])
