import json
import shutil
import subprocess
from itertools import product
from pathlib import Path

import numpy as np
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


def test_moving_box_origin_is_preserved_during_affine_mic_interpolation():
    result = run_trajectory_module("""
        const first = {positions:[[11,0,0]],cell:[[2,0,0],[0,2,0],[0,0,2]],
                       cell_origin:[10,0,0],pbc:[true,true,true]};
        const second = {positions:[[22,0,0]],cell:[[4,0,0],[0,4,0],[0,0,4]],
                        cell_origin:[20,0,0],pbc:first.pbc};
        console.log(JSON.stringify([0,.5,1].map(t => {
            const frame=interpolateTrajectoryFrames(first,second,t,{useMic:true});
            return {position:[...frame.positions],origin:frame.cell_origin};
        })));
    """)
    assert result == [
        {"position": [11, 0, 0], "origin": [10, 0, 0]},
        {"position": [16.5, 0, 0], "origin": [15, 0, 0]},
        {"position": [22, 0, 0], "origin": [20, 0, 0]},
    ]


def _closest_periodic_shift(displacement, cell, pbc):
    """Exhaust all integers bounded by a valid trial image and the dual basis."""
    basis = np.asarray(cell)[pbc]
    dual = np.linalg.pinv(basis)
    coefficients = displacement @ dual
    trial = np.rint(coefficients)
    upper_distance = np.linalg.norm(displacement - trial @ basis)
    bounds = upper_distance * np.linalg.norm(dual, axis=0)
    ranges = [range(int(np.ceil(c - b - 1e-10)), int(np.floor(c + b + 1e-10)) + 1) for c, b in zip(coefficients, bounds)]
    candidates = np.array(list(product(*ranges)))
    distances = np.linalg.norm(displacement - candidates @ basis, axis=1)
    shift = np.zeros(3)
    shift[pbc] = candidates[np.argmin(distances)]
    return shift


def _sample_frames(first, second, amounts, use_mic=True):
    data = json.dumps({"first": first, "second": second, "amounts": amounts, "useMic": use_mic})
    return run_trajectory_module(
        f"const data = {data};"
        "console.log(JSON.stringify(data.amounts.map(t => {"
        "const result = interpolateTrajectoryFrames(data.first, data.second, t, {useMic: data.useMic});"
        "return {...result, positions: [...result.positions]};"
        "})));"
    )


@pytest.mark.parametrize("cell, pbc, delta", [
    ([[1., 0., 0.], [8.9, .2, 0.], [2.3, .12, 1.4]], [True, True, True], [.49, .49, .12]),
    ([[1., 0., 0.], [.2, 1., 0.], [10., 11., 1.]], [True, True, False], [.1, .1, .49]),
    ([[1., 0., 0.], [100., 1., 0.], [0., 0., 1.]], [True, False, False], [.2, .49, 0.]),
    ([[1., .4, 0.], [0., 2., .5], [1.7, .6, 3.]], [False, True, True], [.49, .49, -.4]),
])
def test_skew_and_partial_pbc_interpolation_matches_exhaustive_cartesian_images(cell, pbc, delta):
    cell = np.asarray(cell)
    pbc = np.asarray(pbc)
    first_fractional = np.array([.07, .15, .11])
    delta = np.asarray(delta)
    first = {"positions": [(first_fractional @ cell).tolist()], "cell": cell.tolist(), "pbc": pbc.tolist()}
    second = {**first, "positions": [((first_fractional + delta) @ cell).tolist()]}
    amounts = [0., .19, .5, .83, 1.]
    samples = _sample_frames(first, second, amounts)
    shift = _closest_periodic_shift(delta @ cell, cell, pbc)
    for amount, sample in zip(amounts, samples):
        expected_fractional = first_fractional + amount * (delta - shift)
        expected_fractional[pbc] %= 1
        np.testing.assert_allclose(sample["positions"], expected_fractional @ cell, atol=2e-11)
        assert sample["micApplied"] is True
    if cell[1, 0] in (8.9, 100.):
        assert np.max(np.abs(shift)) > 1  # A fixed 27-image neighborhood is insufficient.


def test_random_unreduced_triclinic_paths_match_independent_image_oracle():
    rng = np.random.default_rng(2109)
    cell = np.array([[1., 0., 0.], [8.9, .2, 0.], [2.3, .12, 1.4]])
    first_fractional = rng.random((24, 3))
    deltas = rng.uniform(-.49, .49, (24, 3))
    first = {"positions": (first_fractional @ cell).tolist(), "cell": cell.tolist(), "pbc": [True]*3}
    second = {**first, "positions": ((first_fractional + deltas) @ cell).tolist()}
    sample = _sample_frames(first, second, [.37])[0]
    expected = []
    for origin, delta in zip(first_fractional, deltas):
        shift = _closest_periodic_shift(delta @ cell, cell, np.array([True]*3))
        expected.append(((origin + .37 * (delta - shift)) % 1) @ cell)
    np.testing.assert_allclose(np.reshape(sample["positions"], (-1, 3)), expected, atol=3e-11)


def test_changing_cells_use_one_midpoint_metric_for_every_intermediate_amount():
    first_cell = np.array([[2., 0., 0.], [.2, 1., 0.], [0., 0., 3.]])
    second_cell = np.array([[2., 0., 0.], [1.8, 1., 0.], [0., 0., 3.]])
    delta = np.array([.49, .3, 0.])
    first = {"positions": [[0., 0., 0.]], "cell": first_cell.tolist(), "pbc": [True, True, False]}
    second = {**first, "positions": [(delta @ second_cell).tolist()], "cell": second_cell.tolist()}
    midpoint_cell = (first_cell + second_cell) / 2
    pbc = np.array(first["pbc"])
    midpoint_shift = _closest_periodic_shift(delta @ midpoint_cell, midpoint_cell, pbc)
    early_cell = .9 * first_cell + .1 * second_cell
    assert not np.array_equal(midpoint_shift, _closest_periodic_shift(delta @ early_cell, early_cell, pbc))
    amounts = [.1, .25, .5, .75, .9]
    for amount, sample in zip(amounts, _sample_frames(first, second, amounts)):
        fraction = amount * (delta - midpoint_shift)
        fraction[pbc] %= 1
        expected_cell = (1 - amount) * first_cell + amount * second_cell
        np.testing.assert_allclose(sample["positions"], fraction @ expected_cell, atol=2e-12)
        np.testing.assert_allclose(sample["cell"], expected_cell)


def test_singular_endpoint_cell_keeps_explicit_cartesian_fallback():
    first = {"positions": [[3., 2., 1.]], "cell": [[2., 0., 0.], [.4, 3., 0.], [0., 0., 0.]], "pbc": [True, True, False]}
    second = {"positions": [[-2., 4., 3.]], "cell": [[3., 0., 0.], [.8, 4., 0.], [0., 0., 5.]], "pbc": first["pbc"]}
    sample = _sample_frames(first, second, [.4])[0]
    assert sample["micApplied"] is False
    np.testing.assert_allclose(sample["positions"], [1., 2.8, 1.8])
    np.testing.assert_allclose(sample["cell"], .6*np.array(first["cell"]) + .4*np.array(second["cell"]))


def test_only_axes_periodic_in_both_frames_may_change_image():
    first = {"positions": [[9.5, 9.5, 0.]], "cell": np.diag([10., 10., 10.]).tolist(), "pbc": [True, True, True]}
    second = {**first, "positions": [[.5, .5, 0.]], "pbc": [True, False, True]}
    sample = _sample_frames(first, second, [.5])[0]
    assert sample["pbc"] == [True, False, True]
    np.testing.assert_allclose(sample["positions"], [0., 5., 0.])


@pytest.mark.parametrize("expression", ["NaN", "Infinity", "-Infinity", "null"])
def test_nonfinite_coordinates_are_rejected_instead_of_fabricated_as_zero(expression):
    result = run_trajectory_module(
        "const frame = {positions: [[0,0,0]], cell: [[1,0,0],[0,1,0],[0,0,1]], pbc: [true,true,true]};"
        f"const invalid = {{...frame, positions: [[{expression},0,0]]}};"
        "const errors = [false,true].map(useMic => {try {interpolateTrajectoryFrames(frame,invalid,.5,{useMic});return null;}catch(error){return error.message;}});"
        "console.log(JSON.stringify(errors));"
    )
    assert all("finite XYZ positions" in error for error in result)


@pytest.mark.parametrize("target, expression", [("amount", "NaN"), ("amount", "Infinity"), ("cell", "NaN")])
def test_nonfinite_amount_or_cell_reports_clear_error(target, expression):
    result = run_trajectory_module(
        "const frame = {positions: [[0,0,0]], cell: [[1,0,0],[0,1,0],[0,0,1]], pbc: [true,true,true]};"
        + (f"frame.cell[0][0] = {expression};" if target == "cell" else "")
        + f"try {{interpolateTrajectoryFrames(frame,frame,{expression if target == 'amount' else '.5'},{{useMic:true}});console.log(JSON.stringify(null));}}"
        + "catch(error){console.log(JSON.stringify(error.message));}"
    )
    assert "finite" in result


def test_typed_positions_retain_values_and_incomplete_xyz_triples_are_rejected():
    result = run_trajectory_module(
        "const first = {positions: new Float64Array([1,2,3]), cell: null, pbc: []};"
        "const second = {...first, positions: new Float64Array([3,4,5])};"
        "const position = [...interpolateTrajectoryFrames(first,second,.25).positions];"
        "let error=null;try{interpolateTrajectoryFrames({...first,positions:new Float64Array([1,2,3,4])},second,.5);}catch(e){error=e.message;}"
        "console.log(JSON.stringify({position,error}));"
    )
    assert result["position"] == [1.5, 2.5, 3.5]
    assert result["error"]


def test_degenerate_midpoint_periodic_basis_fails_clearly():
    result = run_trajectory_module(
        "const first = {positions: [[0,0,0]],cell:[[1,0,0],[0,1,0],[0,0,1]],pbc:[true,true,true]};"
        "const second = {...first,cell:[[-1,0,0],[0,-1,0],[0,0,-1]]};"
        "try{interpolateTrajectoryFrames(first,second,.25,{useMic:true});console.log(JSON.stringify(null));}"
        "catch(error){console.log(JSON.stringify(error.message));}"
    )
    assert "independent periodic vectors in the midpoint cell" in result


def test_extreme_unreduced_basis_hits_explicit_search_bound_without_approximating():
    result = run_trajectory_module(
        "const first = {positions:[[0,0,0]],cell:[[1,0,0],[.5,1e-8,0],[0,0,1]],pbc:[true,true,true]};"
        "const second = {...first,positions:[[.25,0,0]]};"
        "try{interpolateTrajectoryFrames(first,second,.5,{useMic:true});console.log(JSON.stringify(null));}"
        "catch(error){console.log(JSON.stringify(error.message));}"
    )
    assert "safety limit" in result
    assert "10000 candidates per atom" in result
