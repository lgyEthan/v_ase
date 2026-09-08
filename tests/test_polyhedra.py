"""Independent geometry, site/image and degeneracy checks for coordination hulls."""
import itertools

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.calculator import Calculator
from ase.spacegroup import crystal

from v_ase.polyhedra import calculate_polyhedra


def rule(**updates):
    return {'id':'coordination','centers':{'indices':[0]},'ligands':{'elements':['O']},
            'maxDistance':3., **updates}


def structure(vertices):
    return Atoms('Ti'+'O'*len(vertices),positions=[[0,0,0],*vertices])


@pytest.mark.parametrize('vertices,faces,edges,volume',[
    (list(itertools.product([-1,1],repeat=3)),6,12,8.),
    ([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],8,12,4/3),
    ([[1,1,1],[-1,-1,1],[1,-1,-1],[-1,1,-1]],4,6,8/3),
])
def test_known_hulls_outward_faces_and_no_triangulation_diagonals(vertices,faces,edges,volume):
    atoms=structure(vertices);before=atoms.positions.copy()
    p=calculate_polyhedra(atoms,[rule()])['polyhedra'][0]
    assert len(p['faces'])==faces and len(p['edges'])==edges
    assert p['volume']==pytest.approx(volume,rel=1e-12)
    assert p['centerInside']
    pts=np.array([v['position'] for v in p['vertices']])
    for face in p['triangles']:
        a,b,c=pts[face];assert np.dot(np.cross(b-a,c-a),(a+b+c)/3)>0
    np.testing.assert_array_equal(atoms.positions,before)


def test_primitive_perovskite_uses_six_images_of_three_oxygen_basis_atoms():
    a=3.905
    atoms=Atoms('SrTiO3',scaled_positions=[[0,0,0],[.5,.5,.5],[.5,.5,0],[.5,0,.5],[0,.5,.5]],cell=[a]*3,pbc=True)
    p=calculate_polyhedra(atoms,[rule(centers={'elements':['Ti']},maxDistance=2.2)])['polyhedra'][0]
    assert p['neighborCount']==6
    assert len({v['index'] for v in p['vertices']})==3
    assert len({(v['index'],tuple(v['cellOffset'])) for v in p['vertices']})==6
    assert p['volume']==pytest.approx(a**3/6)


def test_rutile_iridium_oxide_has_distorted_octahedra():
    atoms=crystal(['Ir','O'],basis=[(0,0,0),(.305,.305,0)],spacegroup=136,
                  cellpar=[4.505,4.505,3.159,90,90,90])
    result=calculate_polyhedra(atoms,[rule(centers={'elements':['Ir']},maxDistance=2.4)])
    assert result['polyhedronCount']==2
    for p in result['polyhedra']:
        assert p['neighborCount']==6 and len(p['faces'])==8 and len(p['edges'])==12
        distances=np.array([v['distance'] for v in p['vertices']])
        assert np.ptp(distances)>.01  # Do not impose a regular octahedron.


@pytest.mark.parametrize('pbc',[[True,True,True],[True,False,True],[False,False,False]])
def test_skew_and_unwrapped_geometry_agrees_with_explicit_integer_image_search(pbc):
    rng=np.random.default_rng(3)
    cell=np.array([[5.,0,0],[3.5,4.,0],[1.,.8,4.5]])
    atoms=Atoms('Ti'+'O'*24,scaled_positions=rng.random((25,3)),cell=cell,pbc=pbc)
    atoms.positions[0]+=2*cell[0]
    r=rule(maxDistance=2.7,maxCoordination=512,minCoordination=3)
    result=calculate_polyhedra(atoms,[r])
    expected=set()
    for j in range(1,len(atoms)):
        for shift in itertools.product(*[range(-4,5) if periodic else [0] for periodic in pbc]):
            d=np.linalg.norm(atoms.positions[j]+np.array(shift)@cell-atoms.positions[0])
            if 1e-10<d<=2.7+1e-10:expected.add((j,shift))
    actual=set()
    for poly in result['polyhedra']:
        actual.update((v['index'],tuple(v['cellOffset'])) for v in poly['vertices'])
    if len(expected)>=3:assert actual==expected
    else:assert not result['polyhedra']


def test_rank_two_is_a_polygon_and_collinear_is_reported_without_joggling():
    atoms=structure([[1,1,0],[1,-1,0],[-1,-1,0],[-1,1,0]])
    p=calculate_polyhedra(atoms,[rule()])['polyhedra'][0]
    assert p['rank']==2 and p['volume']==0 and p['area']==pytest.approx(4)
    assert len(p['faces'])==1 and len(p['edges'])==4
    assert calculate_polyhedra(atoms,[rule(planar=False)])['diagnostics'][0]['status']=='planar-disabled'
    atoms=structure([[1,0,0],[2,0,0],[-1,0,0]])
    result=calculate_polyhedra(atoms,[rule()])
    assert not result['polyhedra']
    assert result['diagnostics'][0]['status']=='collinear-or-coincident'


def test_mixed_ligands_labels_and_explicit_images_are_not_bond_inference():
    atoms=structure([[1,0,0],[-1,0,0],[0,1,0],[0,0,1]])
    atoms[1].symbol='F';atoms.calc=Calculator()
    # Empty selectors mean all; fields on one selector combine by intersection.
    labels=['site','axial','axial','equatorial','equatorial']
    p=calculate_polyhedra(atoms,[rule(ligands={'elements':['O','F']})],labels=labels)['polyhedra'][0]
    assert p['neighborCount']==4
    r=rule(maxDistance=.1,explicit=[{'center':0,'vertices':[{'index':i} for i in range(1,5)]}])
    r['ligands']={}
    assert calculate_polyhedra(atoms,[r])['polyhedra'][0]['neighborCount']==4
    with pytest.raises(ValueError,match='periodicity'):
        r['explicit'][0]['vertices'][0]['cellOffset']=[1,0,0]
        calculate_polyhedra(atoms,[r])


def test_duplicates_cutoff_endpoints_and_disabled_rules():
    atoms=structure([[1,0,0],[-1,0,0],[0,1,0],[0,0,1],[0,0,1]])
    p=calculate_polyhedra(atoms,[rule(minDistance=.999999999,maxDistance=1.)])['polyhedra'][0]
    assert p['neighborCount']==4 and p['duplicateVertexCount']==1
    assert calculate_polyhedra(atoms,[rule(enabled=False)])['polyhedronCount']==0
    with pytest.raises(ValueError,match='smaller'):
        calculate_polyhedra(atoms,[rule(minDistance=3)])
    with pytest.raises(ValueError,match='outside'):
        calculate_polyhedra(atoms,[rule(centers={'indices':[300]})])


def test_tiny_cell_large_cutoff_is_bounded_before_image_allocation():
    atoms=Atoms('TiO',scaled_positions=[[0,0,0],[.5,.5,.5]],cell=[.01]*3,pbc=True)
    with pytest.raises(ValueError,match='work budget'):
        calculate_polyhedra(atoms,[rule(maxDistance=100.)])


def test_downloaded_iridium_example_keeps_its_documented_visual_labels():
    from pathlib import Path
    from ase.io import read
    from v_ase.io import atom_labels
    root=Path(__file__).resolve().parents[1]
    atoms=read(root/'docs/assets/examples/IrO2_polyhedra.extxyz')
    labels=atom_labels(atoms)
    assert labels.count('Ir_A')==labels.count('Ir_B')==12
    assert labels.count('O')==48
    for label in ('Ir_A','Ir_B'):
        result=calculate_polyhedra(atoms,[rule(centers={'labels':[label]},maxDistance=2.4)])
        assert result['polyhedronCount']==12
        assert all(p['neighborCount']==6 for p in result['polyhedra'])
