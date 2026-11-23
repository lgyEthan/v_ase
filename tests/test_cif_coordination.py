"""The user's nonstandard H-M CIF and independent layer-coordination oracle."""
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from v_ase.io import infer_input_format, read_structure_frames
from v_ase.polyhedra import automatic_rules, calculate_polyhedra

FIXTURE = Path(__file__).parent / 'fixtures/vermiculite.cif'


def test_explicit_cif_symmetry_keeps_cell_sites_and_original_labels():
    atoms = read_structure_frames(FIXTURE)[0]
    assert infer_input_format('VERMICULITE.CIF') == 'cif'
    assert Counter(atoms.get_chemical_symbols()) == {'Mg':12, 'Si':16, 'O':48}
    np.testing.assert_allclose(atoms.cell.cellpar(), [5.31,9.20,28.46,90,97.14,90], atol=1e-10)
    assert atoms.pbc.all()
    assert atoms.info['cif_spacegroup_symbol'] == 'C 1 c 1'
    assert 'spacegroup' not in atoms.info  # Never mislabel the construction seed as P1.
    labels = atoms.arrays['cif_site_label']
    assert sum(str(x).startswith('O-H') for x in labels) == 8
    # Independently expand the four supplied operations, not ASE's group lookup.
    basis = [[0,0,0],[0,1/3,0],[0,2/3,0],[.397,0,.094],[.897,.16667,.094]]
    for site in basis:
        x,y,z=site
        for target in [[x,y,z],[x+.5,y+.5,z],[x,-y,z+.5],[x+.5,-y+.5,z+.5]]:
            delta=atoms.get_scaled_positions()-np.mod(target,1)
            delta-=np.rint(delta)
            assert np.min(np.linalg.norm(delta,axis=1)) < 1e-5


def test_cif_unknown_group_without_operations_is_not_silently_treated_as_p1(tmp_path):
    text=FIXTURE.read_text()
    start=text.index('loop_\n_space_group_symop_operation_xyz')
    end=text.index('loop_\n_atom_site_label',start)
    source=tmp_path/'unknown.cif';source.write_text(text[:start]+text[end:])
    with pytest.raises(Exception, match='spacegroup'):
        read_structure_frames(source)


def test_vermiculite_tetrahedral_and_octahedral_layers_from_actual_sites():
    atoms=read_structure_frames(FIXTURE)[0]
    original=atoms.positions.copy()
    rules=[{'id':'T','centers':{'elements':['Si']},'ligands':{'elements':['O']},'maxDistance':2.0},
           {'id':'O','centers':{'elements':['Mg']},'ligands':{'elements':['O']},'maxDistance':2.5}]
    result=calculate_polyhedra(atoms,rules)
    assert Counter((p['centerLabel'],p['neighborCount']) for p in result['polyhedra']) == {('Si',4):16,('Mg',6):12}
    assert result['vertexCount']==136 and not result['diagnostics']
    assert all(p['rank']==3 and p['centerInside'] for p in result['polyhedra'])
    assert any(any(v['cellOffset']) for p in result['polyhedra'] for v in p['vertices'])
    np.testing.assert_array_equal(atoms.positions,original)
    auto=calculate_polyhedra(atoms,automatic_rules(atoms))
    assert Counter(p['neighborCount'] for p in auto['polyhedra'])=={4:16,6:12}
    assert auto['polyhedronCount']==28


def test_bond_filter_is_opt_in_image_aware_and_independent_of_drawn_bonds():
    atoms=Atoms('SrTiO3',scaled_positions=[[0,0,0],[.5,.5,.5],[.5,.5,0],[.5,0,.5],[0,.5,.5]],cell=[3.905]*3,pbc=True)
    rules=[{'id':'TiO','centers':{'elements':['Ti']},'ligands':{'elements':['O']},'maxDistance':2.2}]
    settings={'bondMode':'pairwise','showBonds':False,'pairwiseBondRanges':{'O-Ti':{'max':2.1,'enabled':True}}}
    result=calculate_polyhedra(atoms,rules,bond_settings=settings)
    assert result['polyhedra'][0]['neighborCount']==6
    assert len({(v['index'],tuple(v['cellOffset'])) for v in result['polyhedra'][0]['vertices']})==6
    settings['pairwiseBondRanges']['O-Ti']['max']=1.5
    rejected=calculate_polyhedra(atoms,rules,bond_settings=settings)
    assert rejected['polyhedronCount']==0
    assert rejected['diagnostics'][0]['status']=='bonded-neighbors-outside-range'
    assert rejected['diagnostics'][0]['unfilteredNeighborCount']==6
    assert calculate_polyhedra(atoms,rules)['polyhedronCount']==1


def test_automatic_unsupported_elements_produce_empty_rules_not_an_invented_shape():
    assert automatic_rules(Atoms('C4',positions=[[0,0,0],[1,0,0],[0,1,0],[0,0,1]])) == []


def test_agent_can_discover_automatic_and_bond_filter_without_full_schema():
    from v_ase.ai_tools import tool_catalog
    from v_ase.ai_schema import ai_schema_payload
    schema=tool_catalog()['vase_configure_polyhedra'].input_schema
    assert schema['properties']['automatic']['type']=='boolean'
    assert schema['properties']['bonded_only']['type']=='boolean'
    display=ai_schema_payload({'method':'apply'})['schema']['properties']['display']['properties']
    assert display['polyhedraBondedOnly']['type']=='boolean'


def test_filtered_geometry_uses_bond_floor_and_invalidates_hookean_cache():
    from ase.constraints import Hookean
    from v_ase.session import EditorSession
    from v_ase.server import _calculate_session_polyhedra
    atoms=Atoms('TiO4',positions=[[0,0,0],[1,1,1],[-1,-1,1],[-1,1,-1],[1,-1,-1]])
    rule={'id':'T','centers':{'elements':['Ti']},'ligands':{'elements':['O']},'maxDistance':2.5,'minCoordination':4}
    settings={'bondMode':'auto','showBonds':False}
    session=EditorSession(session_id='bond-filter',original_atoms=atoms.copy(),working_atoms=atoms)
    payload={'rules':[rule],'bondedOnly':True,'bondSettings':settings}
    first=_calculate_session_polyhedra(session,payload)
    assert first['polyhedronCount']==1
    atoms.set_constraint(Hookean(0,1,k=2,rt=1))
    second=_calculate_session_polyhedra(session,payload)
    assert first['fingerprint']!=second['fingerprint']
    assert second['polyhedronCount']==0 and second['diagnostics'][0]['neighborCount']==3
    assert calculate_polyhedra(atoms,[rule])['polyhedronCount']==1
    atoms.set_constraint();atoms.positions*=.05
    assert calculate_polyhedra(atoms,[rule],bond_settings=settings)['polyhedronCount']==0
    assert calculate_polyhedra(atoms,[rule])['polyhedronCount']==1


def test_mesh_export_obeys_opt_in_filter_without_requiring_bond_lines():
    from v_ase.export import _polyhedral_scene_meshes
    atoms=read_structure_frames(FIXTURE)[0]
    display={'showPolyhedra':True,'polyhedraRules':automatic_rules(atoms),
             'polyhedraBondedOnly':True,'showBonds':False,'bondMode':'pairwise',
             'pairwiseBondRanges':{'Mg-O':{'max':2.5},'O-Si':{'max':2.0}}}
    assert len(_polyhedral_scene_meshes(atoms,display))==28
    display['pairwiseBondRanges']={}
    assert not _polyhedral_scene_meshes(atoms,display)
    display['polyhedraBondedOnly']=False
    assert len(_polyhedral_scene_meshes(atoms,display))==28
