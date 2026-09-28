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
    try{{const huge=refineSurface({{...mesh,indices:new Uint32Array(6000000)}},2);huge.next();throw Error('Missing limit');}}catch(e){{if(!e.message.includes('8,000,000'))throw e;}}
    console.log('ok');
    """
    assert subprocess.run([shutil.which('node') or '/Users/glee0366/.local/bin/node','--input-type=module','-e',source],capture_output=True,text=True,check=True).stdout.strip()=='ok'


def test_quality_settings_survive_project_archive(tmp_path):
    from ase import Atoms
    from v_ase.project import read_project_archive, write_project_archive
    from v_ase.session import EditorSession

    atoms = Atoms('OH2', positions=[[0, 0, 0], [.95, 0, 0], [-.24, .93, 0]])
    session = EditorSession('quality-project', atoms.copy(), atoms.copy(), config={'viz_only': True})
    display = {'atomSmoothness': 96, 'isosurfaceInterpolation': 4, 'waterInterpolation': 3,
               'isosurfaceMeshSmoothing': 12, 'waterMeshSmoothing': 25,
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
        assert all(validator.is_valid(value) for value in (0, 1, 2, 3, 5, 8))
        assert all(not validator.is_valid(value) for value in (-1, 9, .5))

    for name in ('isosurfaceMeshSmoothing', 'waterMeshSmoothing'):
        validator = Draft202012Validator(DISPLAY_PROPERTIES[name])
        assert all(validator.is_valid(value) for value in (0, 1, 20, 100))
        assert all(not validator.is_valid(value) for value in (-1, 101, .5))


def test_surface_fairing_reduces_ripples_preserves_source_and_pinned_edges():
    module=(Path(__file__).parents[1]/'v_ase/static/surface_refinement.js').as_uri()
    source="""
    import {refineSurfaceAsync} from 'MODULE';
    const n=49,positions=new Float32Array(n*n*3),normals=new Float32Array(n*n*3),faces=[];
    for(let y=0;y<n;y++)for(let x=0;x<n;x++){
        const k=(y*n+x)*3;positions[k]=x;positions[k+1]=y;
        positions[k+2]=(x&&y&&x<n-1&&y<n-1)? .3*Math.sin(x*2.1)*Math.sin(y*1.9):0;
        normals[k+2]=1;
        if(x<n-1&&y<n-1){const i=y*n+x;faces.push(i,i+1,i+n,i+1,i+n+1,i+n);}
    }
    const mesh={positions,normals,indices:new Uint32Array(faces)};
    const originals=JSON.stringify([Array.from(positions),Array.from(normals),faces]);
    const result=await refineSurfaceAsync(mesh,0,undefined,undefined,{smoothing:20});
    let before=0,after=0;
    for(let i=0;i<n*n;i++){
        const x=i%n,y=Math.floor(i/n),k=i*3;
        if(!x||!y||x===n-1||y===n-1){for(let j=0;j<3;j++)if(result.positions[k+j]!==positions[k+j])throw Error('Boundary moved');}
        else {before+=positions[k+2]**2;after+=result.positions[k+2]**2;}
        if(Math.abs(Math.hypot(...result.normals.subarray(k,k+3))-1)>1e-5)throw Error('Normal not unit');
    }
    if(after>=before*.1)throw Error('Ripple not smoothed');
    if(result.indices!==mesh.indices)throw Error('Fairing added triangles');
    if(originals!==JSON.stringify([Array.from(positions),Array.from(normals),Array.from(mesh.indices)]))throw Error('Source modified');
    const tiny={positions:new Float32Array([0,0,0,1,0,0,0,1,0]),normals:new Float32Array([0,0,1,0,0,1,0,0,1]),indices:new Uint32Array([0,1,2])};
    const high=await refineSurfaceAsync(tiny,5);if(high.indices.length!==3*4**5)throw Error('Level above 2 ignored');
    const controller=new AbortController();let yielded=false;
    try{await refineSurfaceAsync(mesh,1,controller.signal,()=>{yielded=true;controller.abort();},{smoothing:100});throw Error('Did not cancel fairing');}
    catch(e){if(e.name!=='AbortError'||!yielded)throw e;}
    console.log('ok');
    """.replace('MODULE',module)
    result=subprocess.run([shutil.which('node') or '/Users/glee0366/.local/bin/node','--input-type=module','-e',source],capture_output=True,text=True,check=True)
    assert result.stdout.strip()=='ok'
