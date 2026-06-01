import numpy as np
from ase.optimize import QuasiNewton
from .websocket_manager import ws_manager
import traceback

async def start_relaxation(session, payload, background_tasks):
    if session.is_relaxing:
        return {"status": "error", "message": "Relaxation already in progress"}
    
    if not session.working_atoms.calc:
        return {"status": "error", "message": "No calculator attached"}

    if "positions" in payload:
        session.working_atoms.set_positions(
            np.array(payload["positions"]),
            apply_constraint=bool(payload.get("apply_constraint", True)),
        )

    fmax = payload.get("fmax", 0.05)
    steps = payload.get("steps", 200)
    
    session.is_relaxing = True
    session.stop_relax = False
    
    background_tasks.add_task(run_opt_thread, session, fmax, steps)
    return {"status": "started"}

def run_opt_thread(session, fmax, steps):
    try:
        atoms = session.working_atoms
        # Optimization loop
        dyn = QuasiNewton(atoms, logfile=None)
        
        def callback():
            if session.stop_relax:
                raise Exception("OPTIMIZATION_STOPPED")
            
            # Authoritative force and energy fetch
            forces = atoms.get_forces()
            energy = atoms.get_potential_energy()
            current_fmax = np.sqrt((forces**2).sum(axis=1).max())
            
            msg = {
                "type": "relax_step",
                "session_id": session.session_id,
                "step": dyn.nsteps,
                "energy": float(energy),
                "fmax": float(current_fmax),
                "positions": atoms.get_positions().tolist()
            }
            ws_manager.broadcast_sync(msg, session.session_id)

        dyn.attach(callback, interval=1)
        dyn.run(fmax=fmax, steps=steps)
        session.working_atoms = atoms
        ws_manager.broadcast_sync({"type": "relax_finished", "status": "converged"}, session.session_id)
        
    except Exception as e:
        if str(e) == "OPTIMIZATION_STOPPED":
            ws_manager.broadcast_sync({"type": "relax_finished", "status": "stopped"}, session.session_id)
        else:
            error_msg = f"Calculator Failure: {str(e)}"
            ws_manager.broadcast_sync({"type": "relax_finished", "status": "error", "message": error_msg}, session.session_id)
            print(traceback.format_exc())
    finally:
        session.is_relaxing = False

async def stop_relaxation(session):
    session.stop_relax = True
    return {"status": "stopping"}
