"""Physical mesh parity and real Blender water export, including changing topology."""
import json
from pathlib import Path
import subprocess
import numpy as np
import pytest
from ase import Atoms
from scipy.spatial import cKDTree
from v_ase.water_export import normalize_water, build_water_geometry, refine_water_geometry, detect_water
from v_ase.export import export_blender_response
from v_ase.session import EditorSession
from v_ase.serialization import atoms_to_json
from tests.test_water_surface import node_check
from tests.test_blender_runtime import BLENDER

@pytest.mark.parametrize('subdivision,smoothing', [(0,0),(1,0),(2,4),(1,20)])
def test_export_geometry_matches_viewport(subdivision,smoothing):
    centers=[[.2,.3,.4],[2.7,1.1,0],[3.4,-.5,1.2]]
    raw=json.loads(node_check('''import {refineSurface} from './v_ase/static/surface_refinement.js';
const g=buildWaterGeometry('''+json.dumps(centers)+''');
const it=refineSurface(g,'''+str(subdivision)+''',{smoothing:'''+str(smoothing)+'''});let r;do{r=it.next()}while(!r.done);
console.log(JSON.stringify({positions:Array.from(r.value.positions),normals:Array.from(r.value.normals),indices:Array.from(r.value.indices)}));'''))
    p,n,f=refine_water_geometry(build_water_geometry(centers,normalize_water({})),subdivision,smoothing)
    expected=np.array(raw['positions']).reshape(-1,3)
    assert len(p)==len(expected)
    assert len(f)==len(raw['indices'])//3
    distance,index=cKDTree(expected).query(p)
    assert distance.max()<2e-5
    np.testing.assert_allclose(n,np.array(raw['normals']).reshape(-1,3)[index],atol=1e-4)
    # A closed surface must not grow holes in export.
    edges=np.sort(f[:,[0,1,1,2,2,0]].reshape(-1,2),axis=1)
    assert (np.unique(edges,axis=0,return_counts=True)[1]==2).all()


def test_detection_matches_periodic_source_and_authoritative_ids():
    a=Atoms('OH2OH2',positions=[[.2,0,0],[9.24,0,0],[.44,.93,0],[5,0,0],[5.96,0,0],[4.76,.93,0]],cell=[10]*3,pbc=True)
    for explicit in (False,True):
        if explicit:a.new_array('mol',np.array([1,1,1,2,2,2]))
        d=atoms_to_json(a); cfg=normalize_water({'source':'selected','indices':[0]})
        expected=json.loads(node_check('console.log(JSON.stringify(detectWater('+json.dumps(d)+','+json.dumps(cfg)+').molecules.map(m=>[m.oxygen,...m.hydrogens])));'))
        assert detect_water(d,cfg)==[tuple(m) for m in expected]

@pytest.mark.skipif(BLENDER is None,reason='Blender executable unavailable')
def test_water_scene_runs_and_renders_in_blender(tmp_path):
    a=Atoms('OH2Na',positions=[[0,0,0],[.96,0,0],[-.24,.93,0],[3,0,0]],cell=[8]*3,pbc=True)
    b=a.copy();b.positions[0:3,1]+=1
    c=Atoms('Na',positions=[[3,0,0]],cell=[8]*3,pbc=True)
    session=EditorSession('water-export',a.copy(),a.copy(),trajectory_frames=[a,b,c])
    response=export_blender_response(session,{'display':{'waterSurface':{'enabled':True},'waterInterpolation':1,'waterMeshSmoothing':3,'showBonds':True},'camera':{'position':[6,-10,7],'target':[1,0,0],'ortho_scale':9,'projection':'orthographic'}})
    source=Path(response.path).read_text();Path(response.path).unlink()
    image=tmp_path/'water.png'
    source = source + '\nexec(' + repr(source) + ')\nassert len([h for h in bpy.app.handlers.frame_change_post if getattr(h, \"_v_ase_export\", False)]) == 2\n'
    source+='''
water=bpy.data.objects['v_ase_water_surface']
assert len(water.data.vertices)>100
assert water['v_ase_water_molecules']==1
assert all(p.use_smooth for p in water.data.polygons)
start=[tuple(v.co) for v in water.data.vertices]
scene=bpy.context.scene
scene.frame_set(2)
assert [tuple(v.co) for v in water.data.vertices]!=start
scene.frame_set(3)
assert len(water.data.vertices)==0
scene.frame_set(1)
assert len(water.data.vertices)==len(start)
assert len([m for m in bpy.data.meshes if m.name.startswith('v_ase_water_surface')])==1
scene.render.resolution_x=320;scene.render.resolution_y=240;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath='''+repr(str(image))+'''
bpy.ops.render.render(write_still=True)
'''
    script=tmp_path/'water.py';script.write_text(source)
    proc=subprocess.run([BLENDER,'-b','--factory-startup','--python',str(script)],capture_output=True,text=True,timeout=120)
    assert proc.returncode==0 and 'Traceback' not in proc.stdout+proc.stderr,proc.stdout+proc.stderr
    assert image.exists()
    from PIL import Image
    pixels=np.array(Image.open(image).convert('RGB'),dtype=int)
    assert ((pixels[:,:,2]-pixels[:,:,0])>25).sum()>500
    Image.open(image).save('/tmp/vase049-blender-water.png')


def test_water_scope_follows_reference_visibility_not_atom_glyph_radius():
    from v_ase.export import _cad_scene_data
    from v_ase.water_export import water_scene
    a=Atoms('OH2Na',positions=[[0,0,0],[.96,0,0],[-.24,.93,0],[3,0,0]],cell=[8]*3,pbc=True)
    session=EditorSession('water-visibility',a.copy(),a.copy())
    display={'waterSurface':{'enabled':True},'waterInterpolation':0,'waterMeshSmoothing':0,
             'supercell':[2,1,1],'hiddenAtomReferences':['atom:0']}
    scene=_cad_scene_data(session,{'display':display})
    result=water_scene(a,display,scene)
    assert result['molecules']==1
    assert np.array(result['vertices'])[:,0].min()>5
    assert all(s['index']==3 or s['cell_offset']==[0,0,0] for s in scene['atoms'])
    # Radius/property zero hides spheres, not the independently configured surface.
    display['hiddenAtomReferences']=[]
    display['atomRadiusMapping']={'enabled':True,'field':'array::occupancy::scalar','rangeMode':'manual','min':0,'max':1,'minMultiplier':0,'maxMultiplier':1}
    a.new_array('occupancy',np.zeros(4));session.working_atoms=a
    scene=_cad_scene_data(session,{'display':display})
    assert not scene['atoms']
    assert water_scene(a,display,scene)['molecules']==2
