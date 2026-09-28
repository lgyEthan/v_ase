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
    const assigned=new Set(),explicit=[],ids=atoms?.molecule_ids;
    const close=(a,b)=>{
        const delta=sub(a,b);
        if(!basis)return dot(delta,delta)<cfg.ohCutoff**2;
        const f=basis.reciprocal.map(v=>dot(delta,v));
        // Reciprocal-vector norms bound every lattice image inside the cutoff,
        // including skew cells; do not assume +/- one image is sufficient.
        const nearest=f.map((v,d)=>basis.pbc[d]?Math.round(v):0);
        const candidate=delta.map((v,k)=>v-nearest.reduce((sum,n,d)=>sum+n*basis.cell[d][k],0));
        if(dot(candidate,candidate)<cfg.ohCutoff**2)return true;
        const ranges=f.map((v,d)=>{
            if(!basis.pbc[d])return [0,0];
            const margin=cfg.ohCutoff*Math.hypot(...basis.reciprocal[d])+1e-9;
            return [Math.ceil(v-margin),Math.floor(v+margin)];
        });
        if(ranges.reduce((n,[lo,hi])=>n*Math.max(0,hi-lo+1),1)>4096)throw new Error('Periodic cell is too skew or too small for bounded water neighbour validation. Reduce the cell basis first.');
        for(let a=ranges[0][0];a<=ranges[0][1];a++)for(let b=ranges[1][0];b<=ranges[1][1];b++)for(let c=ranges[2][0];c<=ranges[2][1];c++){
            const q=delta.map((v,k)=>v-a*basis.cell[0][k]-b*basis.cell[1][k]-c*basis.cell[2][k]);
            if(dot(q,q)<cfg.ohCutoff**2)return true;
        }
        return false;
    };
    if(Array.isArray(ids)&&ids.length===elements.length){
        const groups=new Map();
        for(let i=0;i<ids.length;i++)if(Number.isSafeInteger(ids[i])&&ids[i]>0){
            if(!groups.has(ids[i]))groups.set(ids[i],[]);groups.get(ids[i]).push(i);
        }
        for(const group of groups.values()){
            // A declared molecule is authoritative. Never borrow a neighbouring
            // molecule's H or mistake surface hydroxyls for water.
            group.forEach(i=>assigned.add(i));
            if(group.length!==3)continue;
            const os=group.filter(i=>elements[i]==='O'),hs=group.filter(i=>elements[i]==='H');
            if(os.length===1&&hs.length===2&&group.every(i=>pos[i]?.length===3&&pos[i].every(Number.isFinite))
                &&hs.every(h=>close(pos[os[0]],pos[h])))explicit.push({oxygen:os[0],hydrogens:hs,position:[...pos[os[0]]]});
        }
    }
    const oxygens=[], hydrogens=[];
    for(let i=0;i<elements.length;i++){
        if(assigned.has(i)||pos[i]?.length!==3||!pos[i].every(Number.isFinite))continue;
        if(elements[i]==='O')oxygens.push(i);
        if(elements[i]==='H')hydrogens.push(i);
    }
    const step=cfg.ohCutoff, bins=new Map();
    const key=p=>p.map(x=>Math.floor(x/step)).join(',');
    // Wrapped fractional differences lie in (-1, 1). Reciprocal norms bound
    // all image shifts that could be within the cutoff, even for unreduced cells.
    const reach=[0,1,2].map(d=>basis?.pbc[d]?Math.max(1,Math.ceil(step*Math.hypot(...basis.reciprocal[d]))):0);
    const imageCount=reach.reduce((n,r)=>n*(2*r+1),1);
    if(oxygens.length && (imageCount>4096 || imageCount*oxygens.length>2000000)) {
        throw new Error('Periodic water neighbour search exceeds its image budget. Reduce the cell basis or provide molecule IDs.');
    }
    const shifts=[[]];
    if(oxygens.length)for(let d=0;d<3;d++) {
        const prior=shifts.splice(0);
        for(const s of prior)for(let n=-reach[d];n<=reach[d];n++)shifts.push([...s,n]);
    }
    for(const i of oxygens){
        const p=wrap(pos[i],basis);
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
    const scope=new Set(cfg.indices), molecules=explicit.filter(m=>cfg.source==='auto'||scope.has(m.oxygen));
    for(const o of oxygens){
        const hs=attached.get(o);
        if(hs.length===2&&(cfg.source==='auto'||scope.has(o)))molecules.push({oxygen:o,hydrogens:hs,position:[...pos[o]]});
    }
    return {molecules, indices:molecules.flatMap(m=>[m.oxygen,...m.hydrogens]),
        oxygenCount:elements.filter(s=>s==='O').length, excludedOxygens:elements.filter(s=>s==='O').length-molecules.length, topologyMolecules:explicit.length, method:assigned.size?'molecule IDs + unassigned geometry':'geometry'};
}

// Surface nets: one shared vertex per boundary voxel, two indexed triangles
// per crossing grid edge. Interior voxels never create geometry.
const CORNERS=[[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
const scratch={};
function buffer(name,Type,length){
    if(!scratch[name]||scratch[name].length<length)scratch[name]=new Type(length);
    return scratch[name].subarray(0,length);
}
const EDGES=[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
export function buildWaterGeometry(centers, options={}) {
    const cfg=normalizeWater(options), empty=()=>({positions:new Float32Array(),normals:new Float32Array(),indices:new Uint32Array(),gridPoints:0,spacing:cfg.spacing});
    if(!centers.length)return empty();
    if(centers.length>500000)throw new Error('Water surface exceeds 500,000 displayed molecules. Reduce repetitions or source scope.');
    const pad=3*cfg.smoothing,lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
    for(const p of centers)for(let d=0;d<3;d++){
        if(!Number.isFinite(p[d]))throw new Error('Invalid water position.');
        lo[d]=Math.min(lo[d],p[d]-pad);hi[d]=Math.max(hi[d],p[d]+pad);
    }
    let step=cfg.spacing,dims,origin;
    // The world-anchored lattice and deterministic budget keep repeated samples stable.
    for(let retry=0;retry<60;retry++){
        // Keep a zero-valued guard band around truncated kernels, including
        // low thresholds/high local density; no boundary face can be clipped.
        origin=lo.map(x=>(Math.floor(x/step)-3)*step);
        dims=hi.map((x,d)=>Math.ceil((x-origin[d])/step)+4);
        if(dims.every(n=>n<=512)&&dims.reduce((a,b)=>a*b,1)<=1200000
            &&centers.length*(2*Math.ceil(pad/step)+1)**3<=120000000)break;
        step*=1.15;
    }
    if(step>cfg.smoothing*2)throw new Error('Water extent is too large for a resolved surface. Reduce repetitions or source scope.');
    const [nx,ny,nz]=dims,plane=nx*ny,size=plane*nz;
    if(!Number.isFinite(size)||size>1200000)throw new Error('Water surface grid exceeds the memory budget.');
    const field=buffer('field',Float32Array,size);field.fill(0);
    const r=Math.ceil(pad/step),inv=1/(2*cfg.smoothing**2);
    const ex=new Float32Array(nx),ey=new Float32Array(ny),ez=new Float32Array(nz);
    for(const p of centers){
        const qx=(p[0]-origin[0])/step,qy=(p[1]-origin[1])/step,qz=(p[2]-origin[2])/step;
        const x0=Math.max(0,Math.round(qx)-r),x1=Math.min(nx-1,Math.round(qx)+r);
        const y0=Math.max(0,Math.round(qy)-r),y1=Math.min(ny-1,Math.round(qy)+r);
        const z0=Math.max(0,Math.round(qz)-r),z1=Math.min(nz-1,Math.round(qz)+r);
        for(let x=x0;x<=x1;x++)ex[x]=Math.exp(-(((x-qx)*step)**2)*inv);
        for(let y=y0;y<=y1;y++)ey[y]=Math.exp(-(((y-qy)*step)**2)*inv);
        for(let z=z0;z<=z1;z++)ez[z]=Math.exp(-(((z-qz)*step)**2)*inv);
        for(let z=z0;z<=z1;z++)for(let y=y0;y<=y1;y++){
            const yz=ey[y]*ez[z],offset=nx*y+plane*z;
            for(let x=x0;x<=x1;x++)field[offset+x]+=ex[x]*yz;
        }
    }
    const cells=buffer('cells',Int32Array,size);cells.fill(-1);
    // Bounds derive from grid allocation, not molecule count. No per-vertex JS objects.
    const positions=buffer('positions',Float32Array,size*3),normals=buffer('normals',Float32Array,size*3);
    const offsets=[0,1,nx+1,nx,plane,plane+1,plane+nx+1,plane+nx],values=new Float32Array(8);
    const iso=cfg.level;let vertices=0;
    for(let z=1;z<nz-2;z++)for(let y=1;y<ny-2;y++)for(let x=1;x<nx-2;x++){
        const base=x+nx*y+plane*z;let mask=0;
        for(let i=0;i<8;i++){values[i]=field[base+offsets[i]];if(values[i]>=iso)mask|=1<<i;}
        if(mask===0||mask===255)continue;
        let px=0,py=0,pz=0,gx=0,gy=0,gz=0,crossings=0;
        for(const [a,b] of EDGES){
            if((values[a]>=iso)===(values[b]>=iso))continue;
            const t=(iso-values[a])/(values[b]-values[a]),ca=CORNERS[a],cb=CORNERS[b];
            px+=ca[0]+(cb[0]-ca[0])*t;py+=ca[1]+(cb[1]-ca[1])*t;pz+=ca[2]+(cb[2]-ca[2])*t;
            const ia=base+offsets[a],ib=base+offsets[b];
            gx+=(field[ia-1]-field[ia+1])*(1-t)+(field[ib-1]-field[ib+1])*t;
            gy+=(field[ia-nx]-field[ia+nx])*(1-t)+(field[ib-nx]-field[ib+nx])*t;
            gz+=(field[ia-plane]-field[ia+plane])*(1-t)+(field[ib-plane]-field[ib+plane])*t;
            crossings++;
        }
        const id=vertices++,o=id*3,length=Math.hypot(gx,gy,gz)||1;cells[base]=id;
        positions[o]=origin[0]+(x+px/crossings)*step;
        positions[o+1]=origin[1]+(y+py/crossings)*step;
        positions[o+2]=origin[2]+(z+pz/crossings)*step;
        normals[o]=gx/length;normals[o+1]=gy/length;normals[o+2]=gz/length;
    }
    const indices=buffer('indices',Uint32Array,vertices*18);let used=0;
    const quad=(a,b,c,d)=>{
        if(a<0||b<0||c<0||d<0)return;
        const ao=a*3,bo=b*3,co=c*3;
        const ux=positions[bo]-positions[ao],uy=positions[bo+1]-positions[ao+1],uz=positions[bo+2]-positions[ao+2];
        const vx=positions[co]-positions[ao],vy=positions[co+1]-positions[ao+1],vz=positions[co+2]-positions[ao+2];
        if((uy*vz-uz*vy)*normals[ao]+(uz*vx-ux*vz)*normals[ao+1]+(ux*vy-uy*vx)*normals[ao+2]<0)[b,d]=[d,b];
        indices[used++]=a;indices[used++]=b;indices[used++]=c;
        indices[used++]=a;indices[used++]=c;indices[used++]=d;
    };
    for(let z=1;z<nz-2;z++)for(let y=1;y<ny-2;y++)for(let x=1;x<nx-2;x++){
        const i=x+nx*y+plane*z,inside=field[i]>=iso;
        if(inside!==(field[i+1]>=iso))quad(cells[i],cells[i-nx],cells[i-nx-plane],cells[i-plane]);
        if(inside!==(field[i+nx]>=iso))quad(cells[i],cells[i-plane],cells[i-plane-1],cells[i-1]);
        if(inside!==(field[i+plane]>=iso))quad(cells[i],cells[i-1],cells[i-1-nx],cells[i-nx]);
    }
    return {positions:positions.slice(0,vertices*3),normals:normals.slice(0,vertices*3),indices:indices.slice(0,used),gridPoints:size,spacing:step};
}
