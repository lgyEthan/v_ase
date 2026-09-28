"""Scientific and file-format regressions for the experimental water envelope."""
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np
from ase import Atoms
from v_ase.project import write_project_archive, read_project_archive
from v_ase.session import EditorSession

ROOT = Path(__file__).resolve().parents[1]


def node_check(source):
    node=shutil.which('node')
    assert node, 'Node is required to check the water geometry module.'
    result=subprocess.run([node,'--input-type=module','-'],input="import assert from 'node:assert/strict';\nimport {detectWater,buildWaterGeometry,normalizeWater} from './v_ase/static/water_geometry.js';\n"+source,
                          cwd=ROOT,text=True,capture_output=True,timeout=45)
    assert result.returncode==0,result.stderr
    return result.stdout


def test_water_detection_uses_elements_and_periodic_chemical_neighbours():
    node_check("""
const a={chemical_symbols:['O','H','H','O','H','Na'],symbols:['oxide','proton','proton','O_2','H','ion'],
 positions:[[.2,0,0],[9.24,0,0],[.44,.93,0],[5,0,0],[5.96,0,0],[2,2,2]],
 cell:[[10,0,0],[2,10,0],[0,0,10]],pbc:[true,true,true]};
const before=JSON.stringify(a), water=detectWater(a);
assert.equal(water.molecules.length,1);assert.equal(water.molecules[0].oxygen,0);
assert.deepEqual(water.molecules[0].hydrogens,[1,2]);assert.equal(JSON.stringify(a),before);
assert.equal(detectWater(a,{source:'selected',indices:[]}).molecules.length,0);
assert.equal(detectWater(a,{source:'selected',indices:[0,999]}).molecules.length,1);
assert.equal(detectWater({...a,pbc:[false,false,false]}).molecules.length,0);
""")


def test_water_rejects_three_hydrogen_sites_and_tracks_changed_topology():
    node_check("""
const a={symbols:['O','H','H'],positions:[[0,0,0],[.96,0,0],[-.24,.93,0]]};
assert.equal(detectWater(a).molecules.length,1);
a.symbols.push('H');a.positions.push([0,0,.96]);assert.equal(detectWater(a).molecules.length,0);
a.symbols[0]='C';assert.equal(detectWater(a).molecules.length,0);
assert.deepEqual(normalizeWater({source:'selected',indices:[0,7,0]}).indices,[0,7]);
assert.throws(()=>normalizeWater({spacing:0}));assert.throws(()=>normalizeWater({opacity:NaN}));
""")


def test_water_isosurface_has_physical_extent_finite_outward_normals():
    node_check("""
const origin=[3,4,5], result=buildWaterGeometry([origin],{spacing:.3});
assert.ok(result.positions.length>500);assert.equal(result.indices.length%3,0);
assert.ok(result.positions.length<result.indices.length*3);
assert.ok(Array.from(result.indices).every(i=>i<result.positions.length/3));
const expected=2*Math.sqrt(-2*Math.log(.63));
assert.ok(expected>1.9 && expected<1.95);
for(let i=0;i<result.positions.length;i+=3){
 const p=[0,1,2].map(d=>result.positions[i+d]-origin[d]),n=Array.from(result.normals.slice(i,i+3));
 const r=Math.hypot(...p);assert.ok(Math.abs(r-expected)<.07);
 assert.ok(Math.abs(Math.hypot(...n)-1)<1e-5);
 assert.ok(p.reduce((s,x,d)=>s+x*n[d],0)/r>.98);
}
assert.equal(buildWaterGeometry([]).positions.length,0);
assert.throws(()=>buildWaterGeometry([[NaN,0,0]]));
assert.throws(()=>buildWaterGeometry(Array(500001).fill([0,0,0])));
""")


def test_water_mapping_and_source_precision_survive_project_archive(tmp_path):
    atoms=Atoms('OH2',positions=[[.123456789012345,0,0],[1.08,0,0],[-.12,.93,0]])
    settings={'display':{'waterSurface':{'enabled':True,'source':'selected','indices':[0,7],
                                       'color':'#123456','lighting':False,'smoothing':1.8}}}
    path=tmp_path/'water.vase'
    session=EditorSession('water-test',atoms.copy(),atoms.copy(),config={'viz_only':True})
    write_project_archive(path,session,settings=settings)
    loaded=read_project_archive(path)
    assert loaded.settings['display']['waterSurface']==settings['display']['waterSurface']
    np.testing.assert_array_equal(loaded.frames[0].positions,atoms.positions)


def test_geometry_exports_do_not_silently_omit_water():
    import pytest
    from v_ase.export import export_3dm_response, export_obj_response
    for export in (export_3dm_response, export_obj_response):
        with pytest.raises(ValueError, match='water surface is not supported'):
            export(None, {'display': {'waterSurface': {'enabled': True}}})


def test_explicit_molecules_prevent_neighbour_hydrogen_theft_and_serialize():
    from v_ase.serialization import atoms_to_json
    atoms=Atoms('OH2OH2', positions=[[0,0,0],[1,0,0],[0,1,0], [.5,.5,0],[1.5,.5,0],[.5,1.5,0]])
    atoms.new_array('mol',np.array([1,1,1,2,2,2]))
    data=atoms_to_json(atoms)
    assert data['molecule_ids']==[1,1,1,2,2,2]
    assert data['molecule_id_source']=='mol'
    node_check('const a='+json.dumps(data)+"; const d=detectWater(a);assert.equal(d.molecules.length,2);assert.equal(d.topologyMolecules,2);")


def test_large_indexed_boundary_is_closed_and_repeatable():
    node_check("""
const centers=[];for(let x=0;x<24;x++)for(let y=0;y<24;y++)for(let z=0;z<24;z++)centers.push([x*2.8,y*2.8,z*2.8]);
const g=buildWaterGeometry(centers),h=buildWaterGeometry(centers);
assert.equal(g.positions.length,h.positions.length);assert.deepEqual(g.indices,h.indices);
assert.ok(g.indices.length>0);assert.ok(g.gridPoints<=1200000);
assert.ok(g.positions.length/3<centers.length*6);
// A closed density boundary has exactly two incident faces on every mesh edge.
const edges=new Map();for(let i=0;i<g.indices.length;i+=3)for(let k=0;k<3;k++){
 const a=g.indices[i+k],b=g.indices[i+(k+1)%3],key=Math.min(a,b)+','+Math.max(a,b);
 edges.set(key,(edges.get(key)||0)+1);
}
assert.ok([...edges.values()].every(n=>n===2));
""")


def test_changed_molecule_ids_disable_coordinate_only_trajectory_cache():
    from v_ase.server import trajectory_layout_compatible
    a=Atoms('OH2OH2', positions=np.zeros((6,3)));a.new_array('mol',np.array([1,1,1,2,2,2]))
    b=a.copy();b.arrays['mol'][:]=1
    session=EditorSession('water-changing-topology',a.copy(),a.copy(),trajectory_frames=[a,b])
    assert trajectory_layout_compatible(session) is False


def test_dense_low_threshold_envelope_has_no_clipped_boundary():
    node_check("""
const g=buildWaterGeometry(Array.from({length:100},()=>[0,0,0]),{level:.1});
const edges=new Map();for(let i=0;i<g.indices.length;i+=3)for(let k=0;k<3;k++){
 const a=g.indices[i+k],b=g.indices[i+(k+1)%3],key=Math.min(a,b)+','+Math.max(a,b);
 edges.set(key,(edges.get(key)||0)+1);
}
assert.ok(edges.size>0);assert.ok([...edges.values()].every(n=>n===2));
""")


def test_unreduced_periodic_basis_finds_water_beyond_adjacent_images():
    node_check("""
const a={symbols:['O','H','H'],positions:[[0,0,0],[.957,0,0],[-.24,.93,0]],
 cell:[[10,0,0],[31,2,0],[0,0,10]],pbc:[true,true,true]};
// Wrapped second H requires the O image at +2*a, not just +/- one cell.
assert.equal(detectWater(a).molecules.length,1);
assert.equal(detectWater({...a,molecule_ids:[1,1,1]}).molecules.length,1);
""")
