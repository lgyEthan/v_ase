// Visualization only: an oxygen-density envelope, never a fluid dynamics solver.
export const WATER_DEFAULTS = Object.freeze({enabled:false, source:'auto', indices:[],
    color:'#65aaca', opacity:0.48, lighting:true, roughness:0.18,
    hideMolecules:true, smoothing:1.45, level:0.65, spacing:0.65, ohCutoff:1.25});
export function normalizeWater(value={}) {
    const v={...WATER_DEFAULTS,...value};
    const number=(key,min,max)=>{
        const n=Number(v[key]);
        if(!Number.isFinite(n)||n<min||n>max)throw new Error(`Water ${key} must be between ${min} and ${max}.`);
        v[key]=n;
    };
    for(const [key,a,b] of [['opacity',0,1],['roughness',0.02,1],['smoothing',0.5,3],['level',0.1,3],['spacing',0.3,1.5],['ohCutoff',0.8,1.6]])number(key,a,b);
    if(!/^#[\da-f]{6}$/i.test(v.color))throw new Error('Water color must be a six-digit hex color.');
    if(!['auto','selected'].includes(v.source))throw new Error('Water source must be auto or selected.');
    if(!Array.isArray(v.indices)||v.indices.some(i=>!Number.isSafeInteger(i)||i<0))throw new Error('Water indices must be nonnegative integers.');
    v.indices=[...new Set(v.indices)];
    for(const key of ['enabled','lighting','hideMolecules'])v[key]=v[key]===true;
    return v;
}
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
export function periodicBasis(cell,pbc) {
    if(!cell?.every(row=>row?.length===3&&row.every(Number.isFinite)))return null;
    const det=dot(cell[0],cross(cell[1],cell[2]));
    if(Math.abs(det)<1e-10)return null;
    return {cell, reciprocal:[cross(cell[1],cell[2]),cross(cell[2],cell[0]),cross(cell[0],cell[1])].map(v=>v.map(x=>x/det)),pbc:pbc||[false,false,false]};
}
function wrap(p,basis) {
    if(!basis)return [...p];
    const f=basis.reciprocal.map(v=>dot(p,v));
    basis.pbc.forEach((yes,i)=>{if(yes)f[i]-=Math.floor(f[i]);});
    return [0,1,2].map(k=>f.reduce((s,x,i)=>s+x*basis.cell[i][k],0));
}
// Spatial bins and periodic images avoid quadratic all-O/all-H searches.
// A H belongs to its nearest O inside the independent chemical cutoff; only
// exactly-two-H oxygen sites are accepted. Display labels/bond cutoffs are irrelevant.
export function detectWater(atoms, options={}) {
    const cfg=normalizeWater(options), pos=atoms?.positions||[];
    const elements=atoms?.chemical_symbols || atoms?.symbols || [];
    const basis=periodicBasis(atoms?.cell,atoms?.pbc);
    const oxygens=[], hydrogens=[];
    for(let i=0;i<elements.length;i++){
        if(pos[i]?.length!==3||!pos[i].every(Number.isFinite))continue;
        if(elements[i]==='O')oxygens.push(i);
        if(elements[i]==='H')hydrogens.push(i);
    }
    const step=cfg.ohCutoff, bins=new Map(), wrapped=new Map();
    const key=p=>p.map(x=>Math.floor(x/step)).join(',');
    const shifts=[[]];
    for(let d=0;d<3;d++) {
        const prior=shifts.splice(0);
        for(const s of prior)for(const n of basis?.pbc[d]?[-1,0,1]:[0])shifts.push([...s,n]);
    }
    for(const i of oxygens){
        const p=wrap(pos[i],basis);wrapped.set(i,p);
        for(const shift of shifts){
            const q=p.map((v,k)=>v+(basis?shift.reduce((s,x,d)=>s+x*basis.cell[d][k],0):0));
            const k=key(q);if(!bins.has(k))bins.set(k,[]);bins.get(k).push([i,q]);
        }
    }
    const attached=new Map(oxygens.map(i=>[i,[]]));
    for(const h of hydrogens){
        const p=wrap(pos[h],basis), c=p.map(x=>Math.floor(x/step));
        let best=-1, distance=step*step;
        for(let x=-1;x<=1;x++)for(let y=-1;y<=1;y++)for(let z=-1;z<=1;z++){
            for(const [o,q] of bins.get([c[0]+x,c[1]+y,c[2]+z].join(','))||[]){
                const d=dot(sub(p,q),sub(p,q));
                if(d<distance){distance=d;best=o;}
            }
        }
        if(best>=0)attached.get(best).push(h);
    }
    const scope=new Set(cfg.indices), molecules=[];
    for(const o of oxygens){
        const hs=attached.get(o);
        if(hs.length===2&&(cfg.source==='auto'||scope.has(o)))molecules.push({oxygen:o,hydrogens:hs,position:[...pos[o]]});
    }
    return {molecules, indices:molecules.flatMap(m=>[m.oxygen,...m.hydrogens]),
        oxygenCount:oxygens.length, excludedOxygens:oxygens.length-molecules.length};
}

// Reuse bounded scratch storage across synchronous builds; returned buffers are owned copies.
let geometryScratch=null;
const TETS=[[0,5,1,6],[0,1,2,6],[0,2,3,6],[0,3,7,6],[0,7,4,6],[0,4,5,6]];
const CORNERS=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
export function buildWaterGeometry(centers, options={}) {
    const cfg=normalizeWater(options);
    if(!centers.length)return {positions:new Float32Array(),normals:new Float32Array(),gridPoints:0,spacing:cfg.spacing};
    if(centers.length>20000)throw new Error('Water preview supports up to 20,000 displayed molecules. Reduce the scope or repetitions.');
    const pad=3*cfg.smoothing;
    const lo=[Infinity,Infinity,Infinity], hi=[-Infinity,-Infinity,-Infinity];
    for(const p of centers)for(let d=0;d<3;d++){if(!Number.isFinite(p[d]))throw new Error('Invalid water position.');lo[d]=Math.min(lo[d],p[d]-pad);hi[d]=Math.max(hi[d],p[d]+pad);}
    let step=cfg.spacing, dims, origin;
    // Keep the lattice world-anchored; moving the cloud must not move every voxel.
    for(let retry=0;retry<40;retry++){
        origin=lo.map(x=>Math.floor(x/step)*step);
        dims=hi.map((x,d)=>Math.ceil((x-origin[d])/step)+2);
        if(dims.every(n=>n<=128)&&dims.reduce((a,b)=>a*b,1)<=300000
            && centers.length*(2*Math.ceil(pad/step)+1)**3<=20000000)break;
        step*=1.15;
    }
    if(step>cfg.smoothing*1.25)throw new Error('Water extent/density is too large for a resolved preview. Reduce source scope or repetitions.');
    const [nx,ny,nz]=dims, size=nx*ny*nz;
    if(!Number.isFinite(size)||size>300000)throw new Error('Water surface grid exceeds the preview budget.');
    const field=new Float32Array(size), idx=(x,y,z)=>x+nx*(y+ny*z), r=Math.ceil(pad/step);
    const inv=1/(2*cfg.smoothing*cfg.smoothing);
    for(const p of centers){
        const q=p.map((v,d)=>(v-origin[d])/step), c=q.map(Math.round);
        const start=c.map(v=>Math.max(0,v-r)), end=c.map((v,d)=>Math.min(dims[d]-1,v+r));
        const ex=[],ey=[],ez=[];
        for(let x=start[0];x<=end[0];x++)ex[x]=Math.exp(-(((x-q[0])*step)**2)*inv);
        for(let y=start[1];y<=end[1];y++)ey[y]=Math.exp(-(((y-q[1])*step)**2)*inv);
        for(let z=start[2];z<=end[2];z++)ez[z]=Math.exp(-(((z-q[2])*step)**2)*inv);
        for(let z=start[2];z<=end[2];z++)for(let y=start[1];y<=end[1];y++){
            const yz=ey[y]*ez[z], offset=idx(0,y,z);
            for(let x=start[0];x<=end[0];x++)field[offset+x]+=ex[x]*yz;
        }
    }
    const scratch=geometryScratch ||= {positions:new Float32Array(1800000),normals:new Float32Array(1800000)};
    const {positions,normals}=scratch, iso=cfg.level, gradient=new Map();
    let used=0;
    const grad=(id,x,y,z)=>{
        if(gradient.has(id))return gradient.get(id);
        const at=(a,b,c)=>field[idx(Math.max(0,Math.min(nx-1,a)),Math.max(0,Math.min(ny-1,b)),Math.max(0,Math.min(nz-1,c)))];
        const g=[at(x-1,y,z)-at(x+1,y,z),at(x,y-1,z)-at(x,y+1,z),at(x,y,z-1)-at(x,y,z+1)];
        gradient.set(id,g);return g;
    };
    const triangle=(a,b,c)=>{
        if(dot(cross(sub(b.p,a.p),sub(c.p,a.p)),a.n)<0)[b,c]=[c,b];
        if(used+9>positions.length)throw new Error('Water surface exceeds 200,000 triangles. Increase grid spacing.');
        for(const v of [a,b,c])for(let d=0;d<3;d++){positions[used]=v.p[d];normals[used++]=v.n[d];}
    };
    for(let z=0;z<nz-1;z++)for(let y=0;y<ny-1;y++)for(let x=0;x<nx-1;x++){
        const base=idx(x,y,z), plane=nx*ny;
        const v0=field[base],v1=field[base+1],v2=field[base+nx+1],v3=field[base+nx],
            v4=field[base+plane],v5=field[base+plane+1],v6=field[base+plane+nx+1],v7=field[base+plane+nx];
        const mask=(v0>=iso?1:0)|(v1>=iso?2:0)|(v2>=iso?4:0)|(v3>=iso?8:0)|(v4>=iso?16:0)|(v5>=iso?32:0)|(v6>=iso?64:0)|(v7>=iso?128:0);
        if(mask===0||mask===255)continue;
        const ids=[base,base+1,base+nx+1,base+nx,base+plane,base+plane+1,base+plane+nx+1,base+plane+nx];
        const values=[v0,v1,v2,v3,v4,v5,v6,v7];
        const edges=new Map();
        const vertex=(a,b)=>{
            const key=a<b?a*8+b:b*8+a;if(edges.has(key))return edges.get(key);
            const t=(iso-values[a])/(values[b]-values[a]);
            const ca=CORNERS[a], cb=CORNERS[b];
            const ga=grad(ids[a],x+ca[0],y+ca[1],z+ca[2]), gb=grad(ids[b],x+cb[0],y+cb[1],z+cb[2]);
            const n=ga.map((v,d)=>v+(gb[d]-v)*t), length=Math.hypot(...n)||1;
            const v={p:ca.map((v,d)=>origin[d]+([x,y,z][d]+v+(cb[d]-v)*t)*step),n:n.map(v=>v/length)};
            edges.set(key,v);return v;
        };
        for(const tet of TETS){
            const inside=tet.filter(i=>values[i]>=iso), outside=tet.filter(i=>values[i]<iso);
            if(inside.length===1||inside.length===3){
                const one=inside.length===1?inside:outside, many=inside.length===1?outside:inside;
                triangle(...many.map(i=>vertex(one[0],i)));
            } else if(inside.length===2){
                const [a,b]=inside,[c,d]=outside;
                const ac=vertex(a,c),ad=vertex(a,d),bd=vertex(b,d),bc=vertex(b,c);
                triangle(ac,ad,bd);triangle(ac,bd,bc);
            }
        }
    }
    return {positions:positions.slice(0,used),normals:normals.slice(0,used),gridPoints:size,spacing:step};
}
