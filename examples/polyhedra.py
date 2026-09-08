"""Idealized, unrelaxed structures for coordination-polyhedra examples.

Parameters are explicit illustrative model inputs, not claims of a particular
experimental refinement. Labels distinguish supplied sites, not oxidation states.
"""
from pathlib import Path
from ase import Atoms
from ase.spacegroup import crystal
from ase.io import write
from v_ase.io import set_atom_labels


def srtio3(repeat=(3,3,2)):
    atoms=Atoms('SrTiO3',scaled_positions=[[0,0,0],[.5,.5,.5],[.5,.5,0],[.5,0,.5],[0,.5,.5]],
                cell=[3.905]*3,pbc=True).repeat(repeat)
    atoms.info['model']='Ideal cubic SrTiO3, a=3.905 A; unrelaxed illustrative geometry.'
    return atoms


def iridium_oxide(repeat=(2,2,3)):
    atoms=crystal(['Ir','O'],basis=[(0,0,0),(.305,.305,0)],spacegroup=136,
                  cellpar=[4.505,4.505,3.159,90,90,90])
    set_atom_labels(atoms,['Ir_A','Ir_B',*['O']*4])
    atoms.info['spacegroup']=136
    atoms.info['model']='Idealized rutile IrO2, a=4.505 A, c=3.159 A, u=0.305; unrelaxed.'
    atoms.info['label_definition']='Ir_A and Ir_B label the two symmetry-related Ir basis sites for visualization; no charge assignment.'
    return atoms.repeat(repeat)


def write_examples(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    write(directory/'SrTiO3_polyhedra.traj',srtio3())
    write(directory/'SrTiO3_primitive.traj',srtio3((1,1,1)))
    write(directory/'IrO2_polyhedra.extxyz',iridium_oxide())


if __name__=='__main__':
    write_examples(Path(__file__).parent/'readme_scene_assets')
