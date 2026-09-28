"""Synthetic moving water reservoirs for checking surface visualization, not MD.

Run from the source checkout: python examples/water_surface.py
The membrane/ions remain atomistic; water is drawn as a continuous envelope.
"""
from pathlib import Path
import argparse
import sys
import threading
import numpy as np
from ase import Atoms
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v_ase.viewer import view, find_free_port


def make_water_frames(count=24):
    rng = np.random.default_rng(17)
    centers = np.array([[x, y, z] for x in [-9, -6.2, -3.4, 3.4, 6.2, 9]
                        for y in np.arange(-5.6, 5.7, 2.8)
                        for z in np.arange(-5.6, 5.7, 2.8)])
    centers += rng.uniform(-.12, .12, centers.shape)
    phases = rng.uniform(0, 2*np.pi, (len(centers), 3))
    membrane = [[0, y, z] for y in np.arange(-7, 7.1, 1.4)
                for z in np.arange(-7, 7.1, 1.4) if y*y+z*z > 3]
    frames = []
    for frame in range(count):
        t = frame/count*2*np.pi
        positions, symbols = [], []
        for i, center in enumerate(centers):
            p = center+.22*np.sin(t+phases[i])
            angle = .4*np.sin(t+phases[i, 0])
            rotation = np.array([[np.cos(angle), -np.sin(angle), 0],
                                 [np.sin(angle), np.cos(angle), 0], [0,0,1]])
            positions.extend([p, p+rotation@np.array([.9572,0,0]),
                              p+rotation@np.array([-.23999,.92663,0])])
            symbols.extend(['O','H','H'])
        positions.extend(membrane); symbols.extend(['C']*len(membrane))
        positions.extend([[-6, -2, .8], [-4, 3, -3], [-7, 2, 3]])
        symbols.extend(['Na','Cl','Na'])
        atoms = Atoms(symbols, positions=positions, cell=[24,18,18], pbc=False)
        atoms.info['comment'] = 'Synthetic illustration; not an MD trajectory or desalination result.'
        frames.append(atoms)
    return frames


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port', type=int, default=0)
    args=parser.parse_args();port=args.port or find_free_port()
    editor=view(make_water_frames(), notebook=True, block=False, port=port,
                viz_only=True, close_on_disconnect=False, document_name="Water surface — synthetic demo",
                initial_design_settings={'display':{'waterSurface':{'enabled':True},
                    'atomSmoothness':64,'waterInterpolation':1,'waterMeshSmoothing':20,
                    'showGrid':False,'showAxes':False,'showCell':False}})
    print(f'WATER_DEMO_URL=http://127.0.0.1:{port}/?session_id={editor.session_id}',flush=True)
    threading.Event().wait()
