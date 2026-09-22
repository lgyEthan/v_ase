"""Numerical and project-persistence baselines for property radius mapping."""

import math
import ast
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from v_ase.atom_radius import (
    atom_radius_factors,
    atom_radius_factors_for_atoms,
    fit_atom_radius_range,
    normalize_atom_radius_mapping,
)
from v_ase.project import normalize_visual_settings
from v_ase.export import export_blender_response
from v_ase.session import EditorSession
from v_ase.server import _enrich_commensurate_preview_visuals


def mapping(**changes):
    return normalize_atom_radius_mapping({
        "enabled": True,
        "field": "array::fraction::scalar",
        "rangeMode": "manual",
        "min": 0,
        "max": 1,
        "minMultiplier": 0,
        "maxMultiplier": 1,
        **changes,
    }, strict=True)


def test_fractional_and_volume_proportional_radii():
    values = [0, 0.125, 0.5, 1]
    np.testing.assert_allclose(atom_radius_factors(values, mapping()), values)
    np.testing.assert_allclose(
        atom_radius_factors(values, mapping(exponent=1 / 3)),
        [0, 0.5, math.cbrt(0.5), 1],
    )


def test_charge_magnitude_and_manual_radius_precedence():
    factors = atom_radius_factors(
        [-2, -1, 0, 1, 2],
        mapping(
            valueTransform="absolute", max=2,
            minMultiplier=0.25, maxMultiplier=1.5,
        ),
    )
    np.testing.assert_allclose(factors, [1.5, 0.875, 0.25, 0.875, 1.5])
    assert 1.2 * 0.6 * 1.5 * 0.5 == pytest.approx(0.54)


def test_missing_constant_scope_and_disabled_behavior():
    fitted = fit_atom_radius_range([2, 2, float("nan")], mapping())
    assert fitted["minimum"] < 2 < fitted["maximum"]
    factors = atom_radius_factors(
        [0, float("nan"), 1, 1],
        mapping(scope="indices", indices=[0, 1, 2]),
    )
    np.testing.assert_allclose(factors, [0, 1, 1, 1])
    np.testing.assert_allclose(
        atom_radius_factors([0, 1], mapping(enabled=False)),
        [1, 1],
    )


def test_stored_ase_field_and_backward_compatible_project():
    atoms = Atoms("H4", positions=np.zeros((4, 3)))
    atoms.set_array("fraction", np.array([0, 0.125, 0.5, 1], dtype=np.float64))
    np.testing.assert_allclose(atom_radius_factors_for_atoms(atoms, mapping()), atoms.arrays["fraction"])
    normalized = normalize_visual_settings({"display": {"atomRadiusMapping": mapping()}})
    assert normalized["display"]["atomRadiusMapping"] == mapping()
    older = normalize_visual_settings({"display": {"atomRadiusScale": 0.6}})
    assert "atomRadiusMapping" not in older["display"]


def test_blender_export_carries_actual_scalar_factors_for_each_trajectory_frame():
    first = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    second = first.copy()
    first.new_array("fraction", np.array([0.0, 1.0]))
    second.new_array("fraction", np.array([0.5, 0.25]))
    session = EditorSession(
        "mapped-blender", first.copy(), first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )
    response = export_blender_response(session, {
        "positions": first.positions.tolist(),
        "display": {"atomRadiusMapping": mapping()},
    })
    script = Path(response.path).read_text(encoding="utf-8")
    data_line = next(line for line in script.splitlines() if line.startswith("DATA = "))
    data = ast.literal_eval(data_line.removeprefix("DATA = "))
    assert data["atom_radius_factors"] == pytest.approx([0, 1])
    assert data["frames"][0]["atom_radius_factors"] == pytest.approx([0, 1])
    assert data["frames"][1]["atom_radius_factors"] == pytest.approx([0.5, 0.25])


def test_matching_preview_uses_source_specific_and_transformed_position_radii():
    host = Atoms("H2", positions=[[0, 0, 0], [2, 0, 0]])
    guest = Atoms("H2", positions=[[0, 0, 0], [1, 0, 0]])
    host.new_array("fraction", np.array([0.0, 1.0]))
    guest.new_array("fraction", np.array([0.5, 0.25]))
    geometry = {
        "positions": [[0, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]],
        "atom_indices": [0, 1, 0, 1],
        "components": ["host", "host", "guest", "guest"],
    }
    property_preview = _enrich_commensurate_preview_visuals(
        geometry, host, guest, mapping()
    )
    assert property_preview["radius_factors"] == pytest.approx([0, 1, 0.5, 0.25])
    position_preview = _enrich_commensurate_preview_visuals(
        geometry, host, guest, mapping(field="position:x", max=4)
    )
    assert position_preview["radius_factors"] == pytest.approx([0, 0.5, 0.75, 1])
    scoped_preview = _enrich_commensurate_preview_visuals(
        geometry, host, guest, mapping(scope="indices", indices=[0])
    )
    assert scoped_preview["radius_factors"] == pytest.approx([0, 1, 1, 1])


@pytest.mark.parametrize("changes", [
    {"min": 1, "max": 1},
    {"minMultiplier": -1},
    {"maxMultiplier": 5},
    {"minMultiplier": 2, "maxMultiplier": 1},
    {"exponent": 0},
    {"enabled": True, "field": ""},
    {"min": float("nan")},
    {"max": float("inf")},
    {"indices": [-1]},
])
def test_invalid_mapping_is_rejected(changes):
    with pytest.raises(ValueError):
        mapping(**changes)
