"""Geometry quality is reversible, bounded and consistent across capture paths."""
import shutil
import subprocess
from pathlib import Path


def test_curved_surface_refinement_preserves_cuts_and_cancels():
    module=(Path(__file__).parents[1]/'v_ase/static/surface_refinement.js').as_uri()
    source=f"""
    import {{refineSurface,refineSurfaceAsync}} from '{module}';
    const mesh={{positions:new Float32Array([0,0,0,1,0,0,1,1,0,0,1,0]),
      normals:new Float32Array([0,0,1,0,0,1,0,0,1,0,0,1]),indices:new Uint32Array([0,1,2,0,2,3])}};
    const iterator=refineSurface(mesh,2);let step;do{{step=iterator.next();}}while(!step.done);
    const r=step.value,edges=new Map();
    for(let i=0;i<r.indices.length;i+=3)for(let j=0;j<3;j++){{let a=r.indices[i+j],b=r.indices[i+(j+1)%3];const key=[Math.min(a,b),Math.max(a,b)].join(':');edges.set(key,(edges.get(key)||0)+1);}}
    if(r.indices.length!==96||r.positions.some((x,i)=>i%3===2&&x!==0))throw Error('Cut plane moved');
    if([...edges.values()].some(n=>n>2)||[...edges.values()].filter(n=>n===1).length!==16)throw Error('Non-manifold subdivision');
    if(!mesh.positions.every((x,i)=>r.positions[i]===x))throw Error('Original vertices moved');
    const vertices=new Float32Array([1,0,0,-1,0,0,0,1,0,0,-1,0,0,0,1,0,0,-1]);
    const closed={{positions:vertices,normals:vertices.slice(),indices:new Uint32Array([0,2,4,2,1,4,1,3,4,3,0,4,2,0,5,1,2,5,3,1,5,0,3,5])}};
    const curve=await refineSurfaceAsync(closed,1);
    for(let i=vertices.length;i<curve.positions.length;i+=3){{
      const radius=Math.hypot(...curve.positions.subarray(i,i+3));
      if(radius<.88||radius>.89)throw Error('Curved edges were not interpolated');
      if(Math.abs(Math.hypot(...curve.normals.subarray(i,i+3))-1)>1e-6)throw Error('Invalid refined normal');
    }}
    const abort=new AbortController();abort.abort();
    try{{await refineSurfaceAsync(mesh,1,abort.signal);throw Error('Not cancelled');}}catch(e){{if(e.name!=='AbortError')throw e;}}
    try{{const huge=refineSurface({{...mesh,indices:new Uint32Array(6000000)}},2);huge.next();throw Error('Missing limit');}}catch(e){{if(!e.message.includes('2,000,000'))throw e;}}
    console.log('ok');
    """
    assert subprocess.run([shutil.which('node') or '/Users/glee0366/.local/bin/node','--input-type=module','-e',source],capture_output=True,text=True,check=True).stdout.strip()=='ok'


def test_quality_settings_survive_project_archive(tmp_path):
    from ase import Atoms
    from v_ase.project import read_project_archive, write_project_archive
    from v_ase.session import EditorSession

    atoms = Atoms('OH2', positions=[[0, 0, 0], [.95, 0, 0], [-.24, .93, 0]])
    session = EditorSession('quality-project', atoms.copy(), atoms.copy(), config={'viz_only': True})
    display = {'atomSmoothness': 96, 'isosurfaceInterpolation': 2, 'waterInterpolation': 1,
               'waterSurface': {'enabled': True}, 'imageSphereQuality': 'viewport', 'imageSmoothnessScale': 1}
    path = write_project_archive(tmp_path / 'quality.vase', session, {'display': display})
    project = read_project_archive(path)
    assert all(project.settings['display'][key] == value for key, value in display.items())
    assert project.settings['documentMode'] == 'view'
    assert (project.frames[0].positions == atoms.positions).all()


def test_quality_ai_schema_bounds():
    from jsonschema import Draft202012Validator
    from v_ase.ai_display_schema import DISPLAY_PROPERTIES

    segments = Draft202012Validator(DISPLAY_PROPERTIES['atomSmoothness'])
    assert all(segments.is_valid(value) for value in (0, 8, 64, 96, 128))
    assert all(not segments.is_valid(value) for value in (-1, 7, 63, 129, 2.5, '64'))
    for name in ('isosurfaceInterpolation', 'waterInterpolation'):
        validator = Draft202012Validator(DISPLAY_PROPERTIES[name])
        assert all(validator.is_valid(value) for value in (0, 1, 2))
        assert all(not validator.is_valid(value) for value in (-1, 3, .5))
