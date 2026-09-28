// Rendering-only curved-edge interpolation. Original mesh vertices, scalar
// samples and scientific atom coordinates are never moved. Open edges remain
// straight so periodic cuts / volume boundaries stay on their original plane.
export const MAX_REFINED_TRIANGLES = 2000000;
export function* refineSurface(source, iterations = 0) {
    let positions = source.positions, normals = source.normals, indices = source.indices;
    const passes = Math.max(0, Math.min(2, Math.round(Number(iterations) || 0)));
    if (indices.length / 3 * 4 ** passes > MAX_REFINED_TRIANGLES) {
        throw new Error('Surface interpolation exceeds 2,000,000 triangles. Lower interpolation or use a coarser source grid.');
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
            if(i%12288===0)yield {pass,progress:i/indices.length*.3};
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
            if(++processed%4096===0)yield {pass,progress:.3+.4*processed/edges.size};
        }
        const nextIndices=new Uint32Array(indices.length*4);
        for(let i=0;i<indices.length;i+=3) {
            const [a,b,c]=indices.subarray(i,i+3);
            const ab=edges.get(edgeKey(a,b)).vertex,bc=edges.get(edgeKey(b,c)).vertex,ca=edges.get(edgeKey(c,a)).vertex;
            nextIndices.set([a,ab,ca,ab,b,bc,ca,bc,c,ab,bc,ca],i*4);
            if(i%12288===0)yield {pass,progress:.7+.3*i/indices.length};
        }
        positions=nextPositions;normals=nextNormals;indices=nextIndices;
    }
    return {positions,normals,indices};
}

export async function refineSurfaceAsync(source, iterations, signal, onProgress = ()=>{}) {
    const iterator=refineSurface(source,iterations);
    let start=performance.now();
    for(;;) {
        if(signal?.aborted)throw new DOMException('Surface interpolation cancelled.','AbortError');
        const step=iterator.next();if(step.done)return step.value;
        if(performance.now()-start>=6) {
            onProgress((step.value.pass+step.value.progress)/Math.max(1,iterations));
            await new Promise(resolve=>setTimeout(resolve,0));start=performance.now();
        }
    }
}
