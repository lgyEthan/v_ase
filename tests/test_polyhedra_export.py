import json
from pathlib import Path
import zipfile

import numpy as np
import pytest
from ase import Atoms

from v_ase.export import _blender_script, _cad_scene_data, export_obj_response, export_3dm_response, export_html_response
from v_ase.session import EditorSession


def atoms():
    return Atoms('SrTiO3',scaled_positions=[[0,0,0],[.5,.5,.5],[.5,.5,0],[.5,0,.5],[0,.5,.5]],cell=[3.905]*3,pbc=True)


def display():
    return {'showPolyhedra':True,'polyhedraRules':[{'id':'Ti','centers':{'elements':['Ti']},
        'ligands':{'elements':['O']},'maxDistance':2.2,'color':'#1266bb','opacity':.35}],
        'polyhedraAtomMode':'none','supercell':[2,1,1],'translation':[1.,2.,3.]}


def session():
    a=atoms()
    return EditorSession(session_id="poly-export",original_atoms=a.copy(),working_atoms=a)


def test_cad_geometry_preserves_faces_color_opacity_and_periodic_replication():
    s=session();scene=_cad_scene_data(s,{'display':display()})
    assert len(scene['polyhedra'])==2 and not scene['atoms'] and not scene['bonds']
    for poly in scene['polyhedra']:
        assert poly['color']=='#1266bb' and poly['opacity']==.35
        assert len(poly['edges'])==12 and len(poly['triangles'])==8
    a,b=[np.asarray(p['vertices']) for p in scene['polyhedra']]
    assert np.linalg.norm((b-a)[0])==pytest.approx(3.905)


def test_obj_contains_polyhedron_geometry_and_transparent_material(tmp_path):
    result=export_obj_response(session(),{'display':display()})
    with zipfile.ZipFile(result.path) as archive:
        source=archive.read('v_ase_scene.obj').decode()
        material=archive.read('v_ase_scene.mtl').decode()
        data=json.loads(archive.read('v_ase_scene.json'))
    assert 'o polyhedron_' in source and 'd 0.350000' in material
    assert len(data['polyhedra'])==2
    Path(result.path).unlink(missing_ok=True)


def test_rhino_contains_polyhedron_meshes_and_edges():
    rhino=pytest.importorskip('rhino3dm')
    result=export_3dm_response(session(),{'display':display()})
    model=rhino.File3dm.Read(result.path)
    meshes=[o for o in model.Objects if isinstance(o.Geometry,rhino.Mesh)]
    assert len(meshes)==2 and all(len(o.Geometry.Faces)==8 for o in meshes)
    assert any(abs(m.Transparency-.65)<1e-8 for m in model.Materials)
    Path(result.path).unlink(missing_ok=True)


def test_project_retains_rules_and_independent_colors_opacity(tmp_path):
    from v_ase.project import write_project_archive,read_project_archive
    path=tmp_path/'coordination.vase'
    write_project_archive(path,session(),{'display':display()})
    project=read_project_archive(path)
    assert project.settings['display']['polyhedraRules']==display()['polyhedraRules']
    assert project.settings['display']['polyhedraAtomMode']=='none'


def test_style_changes_reuse_cached_scientific_geometry(monkeypatch):
    import v_ase.polyhedra as module
    from v_ase.server import _calculate_session_polyhedra
    from copy import deepcopy
    s=session();payload={'rules':display()['polyhedraRules']}
    first=_calculate_session_polyhedra(s,payload)
    modified=deepcopy(payload);modified['rules'][0].update(color='#ff8833',opacity=.72)
    def forbidden(*args,**kwargs):raise AssertionError('Style change recomputed scientific geometry.')
    monkeypatch.setattr(module,'calculate_polyhedra',forbidden)
    second=_calculate_session_polyhedra(s,modified)
    assert first['fingerprint']==second['fingerprint']
    assert first['polyhedra'][0]['style']['opacity']==.35
    assert second['polyhedra'][0]['style']['opacity']==.72
    assert second['polyhedra'][0]['style']['color']=='#ff8833'


def test_identical_trajectory_geometry_reports_the_requested_frame():
    from v_ase.server import _calculate_session_polyhedra
    s=session();s.trajectory_frames=[s.working_atoms.copy(),s.working_atoms.copy()]
    payload={'rules':display()['polyhedraRules'],'frame_index':0}
    first=_calculate_session_polyhedra(s,payload)
    second=_calculate_session_polyhedra(s,{**payload,'frame_index':1})
    assert first['fingerprint']==second['fingerprint']
    assert first['frame']==0 and second['frame']==1


def test_default_label_selection_invalidates_cache_when_labels_change():
    from v_ase.server import _calculate_session_polyhedra
    from v_ase.io import set_atom_labels
    s=session();rules=display()['polyhedraRules'];rules[0]['centers']={'labels':['Ti']}
    first=_calculate_session_polyhedra(s,{'rules':rules})
    set_atom_labels(s.working_atoms,['Sr','Ti_other','O','O','O'])
    second=_calculate_session_polyhedra(s,{'rules':rules})
    assert first['polyhedronCount']==1 and second['polyhedronCount']==0
    assert first['fingerprint']!=second['fingerprint']
