import threading
import traceback

import numpy as np
from ase.optimize import QuasiNewton

from .repulsion import ensure_default_calculator, is_vase_repulsion_calculator
from .session import copy_atoms_with_calc
from .websocket_manager import ws_manager


_STOP_SIGNAL = "OPTIMIZATION_STOPPED"


def _set_payload_positions(session, payload):
    if "positions" not in payload:
        return
    session.working_atoms.set_positions(
        np.array(payload["positions"]),
        apply_constraint=bool(payload.get("apply_constraint", True)),
    )
    session.sync_current_frame()


def _configure_default_calculator(session, payload):
    settings = payload.get("calculator") or {}
    calc = session.working_atoms.calc
    if not is_vase_repulsion_calculator(calc):
        return
    calc.configure(
        device=settings.get("device"),
        cpu_threads=settings.get("cpu_threads"),
    )
    for frame in session.trajectory_frames:
        if is_vase_repulsion_calculator(frame.calc):
            frame.calc.configure(
                device=settings.get("device"),
                cpu_threads=settings.get("cpu_threads"),
            )


def _launch_relax_thread(session, fmax, steps, run_id):
    thread = threading.Thread(
        target=run_opt_thread,
        args=(session, fmax, steps, run_id),
        daemon=True,
        name=f"v_ase-relax-{session.session_id[:8]}",
    )
    thread.start()
    return thread


async def start_relaxation(session, payload, background_tasks=None):
    ensure_default_calculator(session.working_atoms)
    _set_payload_positions(session, payload)
    _configure_default_calculator(session, payload)

    if not session.working_atoms.calc:
        return {"status": "error", "message": "No calculator attached"}

    fmax = float(payload.get("fmax", 0.05))
    steps = int(payload.get("steps", 200))
    session.relax_params = {
        "fmax": fmax,
        "steps": steps,
        "apply_constraint": bool(payload.get("apply_constraint", True)),
    }

    if session.is_relaxing:
        request_relax_restart(session)
        return {"status": "restarting"}

    session.is_relaxing = True
    session.stop_relax = False
    session.relax_restart_requested = False
    session.relax_run_id += 1
    _launch_relax_thread(session, fmax, steps, session.relax_run_id)
    return {"status": "started"}


def request_relax_restart(session):
    if not session.is_relaxing:
        return False
    session.relax_restart_requested = True
    session.stop_relax = True
    return True


def _publish_current_step(session, atoms, dyn):
    forces = atoms.get_forces()
    energy = atoms.get_potential_energy()
    current_fmax = float(np.sqrt((forces**2).sum(axis=1).max())) if len(forces) else 0.0
    session.working_atoms = copy_atoms_with_calc(atoms)
    session.sync_current_frame()
    ws_manager.broadcast_sync(
        {
            "type": "relax_step",
            "session_id": session.session_id,
            "step": dyn.nsteps,
            "energy": float(energy),
            "fmax": current_fmax,
            "positions": atoms.get_positions().tolist(),
        },
        session.session_id,
    )


def _restart_if_requested(session):
    if not session.relax_restart_requested:
        return False
    params = session.relax_params or {}
    fmax = float(params.get("fmax", 0.05))
    steps = int(params.get("steps", 200))
    session.relax_restart_requested = False
    session.stop_relax = False
    session.is_relaxing = True
    session.relax_run_id += 1
    _launch_relax_thread(session, fmax, steps, session.relax_run_id)
    return True


def run_opt_thread(session, fmax, steps, run_id):
    stopped_for_restart = False
    try:
        atoms = copy_atoms_with_calc(session.working_atoms)
        ensure_default_calculator(atoms)
        dyn = QuasiNewton(atoms, logfile=None)

        def callback():
            if session.stop_relax or run_id != session.relax_run_id:
                raise RuntimeError(_STOP_SIGNAL)
            _publish_current_step(session, atoms, dyn)

        dyn.attach(callback, interval=1)
        dyn.run(fmax=fmax, steps=steps)
        if run_id == session.relax_run_id:
            session.working_atoms = copy_atoms_with_calc(atoms)
            session.sync_current_frame()
            ws_manager.broadcast_sync(
                {"type": "relax_finished", "status": "converged"},
                session.session_id,
            )

    except Exception as exc:
        stopped_for_restart = str(exc) == _STOP_SIGNAL and session.relax_restart_requested
        if str(exc) == _STOP_SIGNAL:
            if not stopped_for_restart:
                ws_manager.broadcast_sync(
                    {"type": "relax_finished", "status": "stopped"},
                    session.session_id,
                )
        else:
            error_msg = f"Calculator Failure: {exc}"
            ws_manager.broadcast_sync(
                {"type": "relax_finished", "status": "error", "message": error_msg},
                session.session_id,
            )
            print(traceback.format_exc())
    finally:
        if stopped_for_restart and _restart_if_requested(session):
            return
        if run_id == session.relax_run_id:
            session.is_relaxing = False
            session.stop_relax = False


async def stop_relaxation(session):
    session.relax_restart_requested = False
    session.stop_relax = True
    return {"status": "stopping"}
