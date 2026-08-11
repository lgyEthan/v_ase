"""Scientific and state-integrity tests for random atom insertion."""

from __future__ import annotations

import asyncio
import threading
import time

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixAtoms, FixedLine
from fastapi import HTTPException
from playwright._impl._errors import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from v_ase.add_atoms import (
    AdditionRepulsionCalculator,
    cancel_atom_addition,
    cell_cartesian_bounds,
    finish_atom_addition,
    sample_cartesian_box_positions,
    sample_unit_cell_positions,
    start_atom_addition,
    start_atom_addition_relaxation,
)
from v_ase.io import atom_labels, set_atom_labels
from v_ase.session import EditorSession
from v_ase.session import sessions
from v_ase.server import (
    apply_positions,
    atom_addition_pair_cutoffs,
    cancel_random_atom_addition,
    finish_random_atom_addition,
    start_random_atom_addition,
)
from v_ase.viewer import find_free_port, view


TRICLINIC_CELL = np.asarray([
    [7.4, 0.0, 0.0],
    [2.1, 6.3, 0.0],
    [-0.8, 1.4, 5.7],
])


def make_host() -> Atoms:
    atoms = Atoms(
        "CuON",
        positions=[
            [1.2, 1.4, 1.8],
            [4.8, 2.1, 2.7],
            [3.1, 4.2, 4.5],
        ],
        cell=TRICLINIC_CELL,
        pbc=True,
    )
    set_atom_labels(atoms, ["Cu_surface", "O_bridge", "N_anchor"])
    atoms.set_tags([8, 4, 2])
    atoms.set_initial_charges([0.2, -0.4, 0.1])
    atoms.new_array("mlip_uncertainty", np.asarray([0.03, 0.08, 0.05]))
    atoms.set_constraint([
        FixAtoms(indices=[0]),
        FixedLine(2, [0.0, 0.0, 1.0]),
    ])
    return atoms


def assert_host_unchanged(reference: Atoms, candidate: Atoms) -> None:
    count = len(reference)
    np.testing.assert_array_equal(candidate.positions[:count], reference.positions)
    np.testing.assert_array_equal(candidate.cell.array, reference.cell.array)
    np.testing.assert_array_equal(candidate.pbc, reference.pbc)
    assert atom_labels(candidate)[:count] == atom_labels(reference)
    assert set(candidate.arrays) >= set(reference.arrays)
    for name, values in reference.arrays.items():
        np.testing.assert_array_equal(candidate.arrays[name][:count], values)
    assert [repr(item) for item in candidate.constraints] == [
        repr(item) for item in reference.constraints
    ]


def test_triclinic_unit_cell_sampling_is_volume_uniform_and_reproducible():
    first = sample_unit_cell_positions(TRICLINIC_CELL, 80_000, seed=1847)
    second = sample_unit_cell_positions(TRICLINIC_CELL, 80_000, seed=1847)
    np.testing.assert_array_equal(first, second)

    fractional = first @ np.linalg.inv(TRICLINIC_CELL)
    assert np.all(fractional >= 0.0)
    assert np.all(fractional < 1.0)
    np.testing.assert_allclose(fractional.mean(axis=0), 0.5, atol=0.004)
    np.testing.assert_allclose(fractional.var(axis=0), 1.0 / 12.0, atol=0.002)

    occupancy, _ = np.histogramdd(
        fractional,
        bins=(4, 4, 4),
        range=((0, 1), (0, 1), (0, 1)),
    )
    expected = len(first) / occupancy.size
    # A generous six-sigma multinomial bound catches spatial bias without
    # making the deterministic statistical test fragile.
    sigma = np.sqrt(expected * (1.0 - 1.0 / occupancy.size))
    assert float(np.max(np.abs(occupancy - expected))) < 6.0 * sigma


def test_cartesian_box_sampling_uses_only_one_periodic_representation():
    bounds = cell_cartesian_bounds(TRICLINIC_CELL)
    positions, diagnostics = sample_cartesian_box_positions(
        TRICLINIC_CELL,
        [True, True, True],
        bounds,
        20_000,
        seed=29,
    )
    fractional = positions @ np.linalg.inv(TRICLINIC_CELL)
    assert np.all(fractional >= 0.0)
    assert np.all(fractional < 1.0)
    for axis in range(3):
        assert np.all(positions[:, axis] >= bounds[2 * axis])
        assert np.all(positions[:, axis] <= bounds[2 * axis + 1])
    assert diagnostics["attempted"] > diagnostics["accepted"]
    assert 0.0 < diagnostics["acceptance_fraction"] < 1.0


def test_random_addition_cancel_restores_every_host_property_and_history():
    host = make_host()
    session = EditorSession("add-cancel", host.copy(), host.copy())
    redo_marker = session._history_state()
    session.redo_stack.append(redo_marker)

    result = start_atom_addition(session, {
        "entries": [
            {"element": "Li", "label": "Li_mobile", "count": 12},
            {"element": "H", "label": "H_probe", "count": 5},
        ],
        "region_mode": "cell",
        "seed": 11,
        "freeze_existing": True,
    })

    assert result["new_count"] == 17
    assert len(session.working_atoms) == len(host) + 17
    assert result["temporary_fixed_indices"] == list(range(len(host)))
    cancel_atom_addition(session)

    assert session.atom_addition is None
    assert len(session.working_atoms) == len(host)
    assert_host_unchanged(host, session.working_atoms)
    assert session.redo_stack == [redo_marker]
    assert not session.history


def test_random_addition_rejects_trajectory_topology_changes():
    first = make_host()
    second = make_host()
    second.positions += [0.1, -0.2, 0.3]
    session = EditorSession(
        "add-trajectory",
        first.copy(),
        first.copy(),
        original_frames=[first.copy(), second.copy()],
        trajectory_frames=[first.copy(), second.copy()],
    )

    with pytest.raises(ValueError, match="requires a single structure"):
        start_atom_addition(session, {
            "element": "Li",
            "label": "Li_new",
            "count": 4,
            "region_mode": "cell",
            "seed": 5,
        })

    assert session.atom_addition is None
    assert len(session.trajectory_frames) == 2
    assert_host_unchanged(first, session.working_atoms)


def test_random_addition_finish_reconstructs_host_from_immutable_baseline():
    host = make_host()
    session = EditorSession("add-finish", host.copy(), host.copy())
    start_atom_addition(session, {
        "element": "Li",
        "label": "Li_inserted",
        "count": 8,
        "region_mode": "box",
        "bounds": cell_cartesian_bounds(TRICLINIC_CELL),
        "seed": 9,
    })

    # Simulate temporary host motion from an unfrozen optimizer. Finish must
    # discard it while retaining the inserted coordinates.
    session.working_atoms.positions[: len(host)] += 0.314
    inserted_before = session.working_atoms.positions[len(host) :].copy()
    result = finish_atom_addition(session)

    assert result["added"] == 8
    assert_host_unchanged(host, session.working_atoms)
    np.testing.assert_allclose(session.working_atoms.positions[len(host) :], inserted_before)
    assert atom_labels(session.working_atoms)[len(host) :] == ["Li_inserted"] * 8
    assert session.atom_addition is None


def test_addition_repulsion_uses_mic_and_moves_only_tag_three_atoms():
    atoms = Atoms(
        "CuH",
        positions=[[0.10, 5.0, 5.0], [9.85, 5.0, 5.0]],
        cell=[10.0, 10.0, 10.0],
        pbc=True,
    )
    atoms.set_tags([1, 3])
    atoms.calc = AdditionRepulsionCalculator(
        min_bondinfo={"Cu-H": 1.0},
        cutoff_scale=1.0,
        k_repulsion=2.0,
        mic=True,
        work_on_relax_atoms_too=False,
    )
    forces = atoms.get_forces()

    np.testing.assert_array_equal(forces[0], np.zeros(3))
    assert np.linalg.norm(forces[1]) > 0.0

    without_mic = atoms.copy()
    without_mic.set_tags([1, 3])
    without_mic.calc = AdditionRepulsionCalculator(
        min_bondinfo={"Cu-H": 1.0},
        cutoff_scale=1.0,
        k_repulsion=2.0,
        mic=False,
        work_on_relax_atoms_too=False,
    )
    np.testing.assert_array_equal(without_mic.get_forces(), np.zeros((2, 3)))


def test_repulsive_placement_keeps_host_exact_after_finish(monkeypatch):
    host = make_host()
    session = EditorSession("add-relax", host.copy(), host.copy())
    monkeypatch.setattr("v_ase.add_atoms.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    start_atom_addition(session, {
        "element": "H",
        "label": "H_new",
        "count": 6,
        "region_mode": "cell",
        "seed": 71,
        "freeze_existing": True,
    })
    response = start_atom_addition_relaxation(session, {
        "steps": 12,
        "fmax": 0.1,
        "k_repulsion": 2.0,
        "pair_cutoffs": {
            "Cu-H": 2.1,
            "H-H": 1.2,
            "H-N": 1.6,
            "H-O": 1.5,
        },
    })
    assert response["is_relaxing"] is True
    deadline = time.monotonic() + 10.0
    while session.atom_addition.is_relaxing and time.monotonic() < deadline:
        time.sleep(0.02)
    assert session.atom_addition.is_relaxing is False

    finish_atom_addition(session)
    assert_host_unchanged(host, session.working_atoms)
    assert len(session.working_atoms) == len(host) + 6


def test_cancel_waits_for_an_inflight_optimizer_commit_then_restores_host(monkeypatch):
    host = make_host()
    session = EditorSession("add-cancel-race", host.copy(), host.copy())
    monkeypatch.setattr("v_ase.add_atoms.ws_manager.broadcast_sync", lambda *_args, **_kwargs: None)
    start_atom_addition(session, {
        "element": "H",
        "label": "H_mobile",
        "count": 16,
        "region_mode": "cell",
        "seed": 33,
        "freeze_existing": True,
    })

    working = session.working_atoms
    original_set_positions = working.set_positions
    commit_entered = threading.Event()
    release_commit = threading.Event()

    def blocked_set_positions(*args, **kwargs):
        commit_entered.set()
        if not release_commit.wait(timeout=5.0):
            raise TimeoutError("Test did not release the optimizer commit.")
        return original_set_positions(*args, **kwargs)

    monkeypatch.setattr(working, "set_positions", blocked_set_positions)
    start_atom_addition_relaxation(session, {
        "steps": 20,
        "fmax": 0.01,
        "k_repulsion": 2.0,
        "pair_cutoffs": {
            "Cu-H": 3.0,
            "H-H": 2.0,
            "H-N": 2.5,
            "H-O": 2.5,
        },
    })
    assert commit_entered.wait(timeout=5.0)

    cancelled = threading.Event()

    def cancel():
        cancel_atom_addition(session)
        cancelled.set()

    cancel_thread = threading.Thread(target=cancel)
    cancel_thread.start()
    try:
        time.sleep(0.05)
        assert not cancelled.is_set()
    finally:
        release_commit.set()
        cancel_thread.join(timeout=5.0)

    assert cancelled.is_set()
    assert session.atom_addition is None
    assert_host_unchanged(host, session.working_atoms)


def test_add_atoms_api_exposes_temporary_fixing_without_mutating_constraints():
    host = make_host()
    session = EditorSession("add-api", host.copy(), host.copy(), config={"viz_only": False})
    sessions[session.session_id] = session

    pairs = asyncio.run(atom_addition_pair_cutoffs(session.session_id, {
        "elements": ["Li", "H"],
        "basis": "covalent",
        "scale": 0.7,
    }))
    assert {"Cu-Li", "H-Li", "H-H"} <= set(pairs["pair_cutoffs"])

    data = asyncio.run(start_random_atom_addition(session.session_id, {
        "entries": [
            {"element": "Li", "label": "Li_mobile", "count": 4},
            {"element": "H", "label": "H_probe", "count": 3},
        ],
        "region_mode": "cell",
        "seed": 410,
        "freeze_existing": True,
        "cutoff_basis": "pairwise",
        "pair_cutoffs": pairs["pair_cutoffs"],
    }))
    addition = data["metadata"]["atom_addition"]
    assert addition["active"] is True
    assert addition["new_count"] == 7
    assert addition["sampling"]["acceptance_fraction"] == 1.0
    assert set(range(len(host))) <= set(data["constraints"]["fixed_indices"])
    assert [repr(item) for item in session.atom_addition.baseline_atoms.constraints] == [
        repr(item) for item in host.constraints
    ]
    # Only index zero is truly constrained in the working ASE object. The rest
    # of the host is fixed only on the isolated optimizer copy and in display metadata.
    assert [repr(item) for item in session.working_atoms.constraints] == [
        repr(item) for item in host.constraints
    ]

    with pytest.raises(HTTPException, match="Finish or cancel Add Atoms") as exc_info:
        asyncio.run(apply_positions(session.session_id, {
            "positions": session.working_atoms.positions.tolist(),
        }))
    assert exc_info.value.status_code == 409

    cancelled = asyncio.run(cancel_random_atom_addition(session.session_id))
    assert cancelled["metadata"]["atom_addition"] is None
    assert_host_unchanged(host, session.working_atoms)


def test_add_atoms_api_finish_commits_only_inserted_atoms():
    host = make_host()
    session = EditorSession("add-api-finish", host.copy(), host.copy(), config={"viz_only": False})
    sessions[session.session_id] = session
    asyncio.run(start_random_atom_addition(session.session_id, {
        "element": "Ne",
        "label": "Ne_void",
        "count": 5,
        "region_mode": "box",
        "bounds": cell_cartesian_bounds(TRICLINIC_CELL),
        "seed": 17,
    }))
    inserted = session.working_atoms.positions[len(host):].copy()
    session.working_atoms.positions[:len(host)] += 1.0

    data = asyncio.run(finish_random_atom_addition(session.session_id))
    assert data["metadata"]["atom_addition"] is None
    assert data["metadata"]["atom_addition_result"]["added"] == 5
    assert_host_unchanged(host, session.working_atoms)
    np.testing.assert_allclose(session.working_atoms.positions[len(host):], inserted)


def test_browser_random_add_atoms_mode_scatter_relax_and_finish():
    host = make_host()
    port = find_free_port()
    editor = view(
        host,
        notebook=True,
        block=False,
        port=port,
        viz_only=False,
        close_on_disconnect=False,
    )
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as exc:
                pytest.skip(f"Playwright Chromium is not installed: {exc}")
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(f"http://127.0.0.1:{port}/?session_id={editor.session_id}")
            page.wait_for_function("window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 3")

            page.click("#btn-create-atom-toggle")
            page.click("#add-atoms-tab-batch")
            page.wait_for_function(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.visible === true"
            )
            assert page.evaluate(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.children.length"
            ) >= 2

            first = page.locator("#add-atoms-entries .add-atoms-entry-row").first
            first.locator(".add-atoms-entry-type").select_option("Li")
            first.locator(".add-atoms-entry-label").fill("Li_mobile")
            first.locator(".add-atoms-entry-count").fill("8")
            page.click("#btn-add-atoms-entry")
            second = page.locator("#add-atoms-entries .add-atoms-entry-row").nth(1)
            second.locator(".add-atoms-entry-type").select_option("H")
            second.locator(".add-atoms-entry-label").fill("H_probe")
            second.locator(".add-atoms-entry-count").fill("5")
            page.fill("#add-atoms-seed", "2021")
            page.wait_for_function(
                "document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').length > 0"
            )
            page.click("#btn-add-atoms-scatter")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.positions.length === 16"
            )
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.new_count === 13"
            )
            assert page.locator("#add-atoms-mode-badge").is_visible()
            assert page.locator("#btn-add-atoms-finish").is_enabled()
            assert page.evaluate(
                "window.__ASE_APP__.state.selected.size"
            ) == 13

            backend = sessions[editor.session_id]
            assert [repr(item) for item in backend.working_atoms.constraints] == [
                repr(item) for item in host.constraints
            ]
            assert_host_unchanged(host, backend.atom_addition.baseline_atoms)

            page.fill("#add-atoms-steps", "20")
            page.click("#btn-add-atoms-relax")
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === true"
            )
            page.wait_for_function(
                "window.__ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
                timeout=20_000,
            )
            assert_host_unchanged(host, backend.atom_addition.baseline_atoms)

            page.click("#btn-add-atoms-finish")
            page.wait_for_function(
                "window.__ASE_APP__.state.atoms.metadata.atom_addition === null"
            )
            assert page.evaluate(
                "window.__ASE_APP__.renderer.addAtomsRegionGroup.visible"
            ) is False
            assert_host_unchanged(host, backend.working_atoms)
            assert len(backend.working_atoms) == len(host) + 13
            assert atom_labels(backend.working_atoms)[-13:] == ["Li_mobile"] * 8 + ["H_probe"] * 5
            browser.close()
    finally:
        editor.close()
