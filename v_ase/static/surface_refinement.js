// Display-only mesh fairing and curved-edge subdivision. Source mesh buffers,
// scalar samples and scientific atom coordinates are never modified. Optional
// fairing moves displayed interior vertices; open boundaries remain pinned.
export const MAX_REFINED_TRIANGLES = 8000000;
export const MAX_SUBDIVISION_LEVEL = 8;
export const MAX_SMOOTHING_PASSES = 100;
export const normalizeSubdivision = value => Math.max(0,Math.min(MAX_SUBDIVISION_LEVEL,Math.round(Number(value)||0)));
export const normalizeSmoothing = value => Math.max(0,Math.min(MAX_SMOOTHING_PASSES,Math.round(Number(value)||0)));

// Display-only Taubin fairing before subdivision. Work stays proportional to
// the original mesh, not the exponentially larger tessellation. Boundary and
// non-manifold vertices are pinned; source positions/normals are never written.
function* fairSurface(source, passes) {
    const indices=source.indices, count=source.positions.length/3;
    let positions=source.positions.slice(), scratch=new Float32Array(positions.length);
    const degree=new Uint32Array(count),edges=new Map(),pinned=new Uint8Array(count);
    for(let i=0;i<indices.length;i+=3) {
        const a=indices[i],b=indices[i+1],c=indices[i+2];
        degree[a]+=2;degree[b]+=2;degree[c]+=2;
        for(const [u,v] of [[a,b],[b,c],[c,a]]) {const key=Math.min(u,v)*count+Math.max(u,v);edges.set(key,(edges.get(key)||0)+1);}
        if(i%12288===0)yield {progress:.08*i/indices.length};
    }
    const offsets=new Uint32Array(count+1);
    for(let i=0;i<count;i++) {offsets[i+1]=offsets[i]+degree[i];if(i%4096===0)yield {progress:.08+.02*i/count};}
    const neighbours=new Uint32Array(offsets[count]),cursor=offsets.slice();
    for(let i=0;i<indices.length;i+=3) {
        const a=indices[i],b=indices[i+1],c=indices[i+2];
        neighbours[cursor[a]++]=b;neighbours[cursor[a]++]=c;
        neighbours[cursor[b]++]=a;neighbours[cursor[b]++]=c;
        neighbours[cursor[c]++]=a;neighbours[cursor[c]++]=b;
        if(i%12288===0)yield {progress:.1+.05*i/indices.length};
    }
    let visited=0;
    for(const [key,uses] of edges) {
        if(uses!==2){pinned[Math.floor(key/count)]=1;pinned[key%count]=1;}
        if(++visited%4096===0)yield {progress:.15+.05*visited/edges.size};
    }
    edges.clear();
    for(let pass=0;pass<passes;pass++)for(let phase=0;phase<2;phase++) {
        const factor=phase===0?.5:-.53;
        for(let i=0;i<count;i++) {
            const k=i*3;
            let x=0,y=0,z=0;
            if(!pinned[i]&&degree[i]) {
                for(let j=offsets[i];j<offsets[i+1];j++){const n=neighbours[j]*3;x+=positions[n];y+=positions[n+1];z+=positions[n+2];}
                scratch[k]=positions[k]+factor*(x/degree[i]-positions[k]);
                scratch[k+1]=positions[k+1]+factor*(y/degree[i]-positions[k+1]);
                scratch[k+2]=positions[k+2]+factor*(z/degree[i]-positions[k+2]);
            } else {scratch[k]=positions[k];scratch[k+1]=positions[k+1];scratch[k+2]=positions[k+2];}
            if(i%4096===0)yield {progress:.2+.7*(pass+(phase+i/count)/2)/passes};
        }
        [positions,scratch]=[scratch,positions];
    }
    const normals=new Float32Array(positions.length);
    for(let i=0;i<indices.length;i+=3){
        const a=indices[i]*3,b=indices[i+1]*3,c=indices[i+2]*3;
        const ux=positions[b]-positions[a],uy=positions[b+1]-positions[a+1],uz=positions[b+2]-positions[a+2];
        const vx=positions[c]-positions[a],vy=positions[c+1]-positions[a+1],vz=positions[c+2]-positions[a+2];
        const x=uy*vz-uz*vy,y=uz*vx-ux*vz,z=ux*vy-uy*vx;
        for(const k of [a,b,c]){normals[k]+=x;normals[k+1]+=y;normals[k+2]+=z;}
        if(i%12288===0)yield {progress:.9+.07*i/indices.length};
    }
    for(let i=0;i<normals.length;i+=3){
        const length=Math.hypot(normals[i],normals[i+1],normals[i+2]);
        for(let axis=0;axis<3;axis++)normals[i+axis]=length?normals[i+axis]/length:source.normals[i+axis];
        if(i%12288===0)yield {progress:.97+.03*i/normals.length};
    }
    return {positions,normals,indices};
}
export function* refineSurface(source, iterations = 0, {smoothing = 0} = {}) {
    let positions = source.positions, normals = source.normals, indices = source.indices;
    const passes = normalizeSubdivision(iterations), fairing=normalizeSmoothing(smoothing), offset=fairing?1:0;
    if (indices.length / 3 * 4 ** passes > MAX_REFINED_TRIANGLES) {
        throw new Error('Surface interpolation exceeds 8,000,000 triangles. Lower subdivision, or smooth the original mesh without adding triangles.');
    }
    if(fairing){
        const iterator=fairSurface(source,fairing);let result;
        for(;;){result=iterator.next();if(result.done)break;yield {pass:0,...result.value};}
        ({positions,normals}=result.value);
    }
    for (let pass = 0; pass < passes; pass++) {
        const vertexCount = positions.length / 3, edges = new Map();
        const edgeKey = (a,b) => Math.min(a,b) * vertexCount + Math.max(a,b);
        for (let i=0;i<indices.length;i+=3) {
            const tri=indices.subarray(i,i+3);
            for(let j=0;j<3;j++) {
                const a=tri[j],b=tri[(j+1)%3],key=edgeKey(a,b),edge=edges.get(key);
                if(edge)edge.count++;else edges.set(key,{a,b,count:1});
            }
            if(i%12288===0)yield {pass:pass+offset,progress:i/indices.length*.3};
        }
        const nextPositions=new Float32Array((vertexCount+edges.size)*3);
        const nextNormals=new Float32Array(nextPositions.length);
        nextPositions.set(positions);nextNormals.set(normals);
        let vertex=vertexCount,processed=0;
        for(const edge of edges.values()) {
            const a=edge.a*3,b=edge.b*3,k=vertex*3;
            let da=0,db=0;
            for(let axis=0;axis<3;axis++) {
                const delta=positions[b+axis]-positions[a+axis];
                da+=delta*normals[a+axis];db-=delta*normals[b+axis];
            }
            let length=0;
            for(let axis=0;axis<3;axis++) {
                nextPositions[k+axis]=(positions[a+axis]+positions[b+axis])*.5
                    -(edge.count===2 ? (da*normals[a+axis]+db*normals[b+axis])*.125 : 0);
                nextNormals[k+axis]=normals[a+axis]+normals[b+axis];
                length+=nextNormals[k+axis]**2;
            }
            length=Math.sqrt(length)||1;
            for(let axis=0;axis<3;axis++)nextNormals[k+axis]/=length;
            edge.vertex=vertex++;
            if(++processed%4096===0)yield {pass:pass+offset,progress:.3+.4*processed/edges.size};
        }
        const nextIndices=new Uint32Array(indices.length*4);
        for(let i=0;i<indices.length;i+=3) {
            const [a,b,c]=indices.subarray(i,i+3);
            const ab=edges.get(edgeKey(a,b)).vertex,bc=edges.get(edgeKey(b,c)).vertex,ca=edges.get(edgeKey(c,a)).vertex;
            nextIndices.set([a,ab,ca,ab,b,bc,ca,bc,c,ab,bc,ca],i*4);
            if(i%12288===0)yield {pass:pass+offset,progress:.7+.3*i/indices.length};
        }
        positions=nextPositions;normals=nextNormals;indices=nextIndices;
    }
    return {positions,normals,indices};
}

export async function refineSurfaceAsync(source, iterations, signal, onProgress = ()=>{}, options = {}) {
    const iterator=refineSurface(source,iterations,options);
    const stages=normalizeSubdivision(iterations)+(normalizeSmoothing(options.smoothing)?1:0);
    let start=performance.now();
    for(;;) {
        if(signal?.aborted)throw new DOMException('Surface interpolation cancelled.','AbortError');
        const step=iterator.next();if(step.done)return step.value;
        if(performance.now()-start>=6) {
            onProgress((step.value.pass+step.value.progress)/Math.max(1,stages));
            await new Promise(resolve=>setTimeout(resolve,0));start=performance.now();
        }
    }
}
