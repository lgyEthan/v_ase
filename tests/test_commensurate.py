import asyncio
import math

import numpy as np
import pytest
from ase import Atoms

from v_ase.commensurate import find_commensurate_angles
from v_ase.server import commensurate_rotation_candidates
from v_ase.session import EditorSession, sessions


def graphene_cell():
    lattice = 2.46
    return np.array([
        [lattice, 0.0, 0.0],
        [0.5 * lattice, 0.5 * math.sqrt(3.0) * lattice, 0.0],
        [0.0, 0.0, 20.0],
    ])


def candidate_near(result, angle, tolerance=1e-5):
    return next(
        candidate
        for candidate in result["candidates"]
        if abs(candidate["angle_deg"] - angle) <= tolerance
    )


def test_hexagonal_commensurate_series_reaches_the_tbg_reference_angle():
    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-6,
        chemical_symbols=["C", "C", "C", "C"],
    )

    assert result["lattice_family"] == "hexagonal"
    assert result["periodic_axes"] == [0, 1]
    assert result["axis_alignment"] == pytest.approx(1.0)

    first = candidate_near(result, 21.7867893)
    second = candidate_near(result, 13.1735511)
    magic = candidate_near(result, 1.05012088)
    assert (first["area"], second["area"], magic["area"]) == (7, 19, 2977)
    assert first["strain"] == pytest.approx(0.0, abs=1e-10)
    assert second["strain"] == pytest.approx(0.0, abs=1e-10)
    assert magic["strain"] == pytest.approx(0.0, abs=1e-10)
    assert magic["magic_reference"] is True


def test_magic_reference_is_not_claimed_for_non_carbon_hexagonal_cells():
    result = find_commensurate_angles(
        graphene_cell(),
        [True, True, False],
        "Z",
        max_index=32,
        strain_tolerance=1e-6,
        chemical_symbols=["B", "N"],
    )

    assert candidate_near(result, 1.05012088)["magic_reference"] is False


def test_commensurate_search_requires_two_projected_periodic_boundaries():
    with pytest.raises(ValueError, match="two independent periodic cell vectors"):
        find_commensurate_angles(
            np.diag([4.0, 5.0, 6.0]),
            [True, False, False],
            "Z",
        )


def test_commensurate_api_uses_current_session_cell():
    atoms = Atoms(
        "C4",
        scaled_positions=[
            [0.0, 0.0, 0.25],
            [1 / 3, 2 / 3, 0.25],
            [0.0, 0.0, 0.75],
            [2 / 3, 1 / 3, 0.75],
        ],
        cell=graphene_cell(),
        pbc=[True, True, False],
    )
    session = EditorSession("commensurate-api", atoms.copy(), atoms.copy())
    sessions[session.session_id] = session

    result = asyncio.run(commensurate_rotation_candidates(session.session_id, {
        "axis": "Z",
        "max_index": 32,
        "strain_tolerance": 0.001,
    }))

    assert result["axis"] == "Z"
    assert candidate_near(result, 1.05012088)["magic_reference"] is True
