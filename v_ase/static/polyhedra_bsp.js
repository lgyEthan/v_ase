// Painter ordering for intersecting convex faces. Splitting changes only the
// drawing tessellation; scientific ligand identities/faces remain untouched.
const dot = (a,b) => a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const sub = (a,b) => a.map((v,i)=>v-b[i]);
const EPS = 1e-7;

function planeOf(points) {
    const a=sub(points[1],points[0]),b=sub(points[2],points[0]);
    const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    const length=Math.hypot(...n);
    if(length<EPS*EPS)return null;
    const normal=n.map(v=>v/length);
    return {normal,offset:dot(normal,points[0])};
}

function classify(points,plane) {
    let front=false,back=false;
    for(const p of points){const d=dot(plane.normal,p)-plane.offset;front ||= d>EPS;back ||= d< -EPS;}
    return front ? (back ? 2 : 1) : (back ? -1 : 0);
}

function split(polygon,plane) {
    const front=[],back=[],points=polygon.points;
    for(let i=0;i<points.length;i++) {
        const a=points[i],b=points[(i+1)%points.length];
        const da=dot(plane.normal,a)-plane.offset,db=dot(plane.normal,b)-plane.offset;
        if(da>=-EPS)front.push(a);
        if(da<=EPS)back.push(a);
        if((da>EPS && db< -EPS)||(da< -EPS && db>EPS)) {
            const t=da/(da-db),p=a.map((v,k)=>v+(b[k]-v)*t);
            front.push(p);back.push(p);
        }
    }
    return [front,back].map(points=>({...polygon,points}));
}

export class PolyhedraBSP {
    constructor(polygons,{maxPolygons=120000,maxDepth=128}={}) {
        this.fragmentCount=polygons.length;
        // Geometry ordering, never rule insertion order, chooses partitions.
        const ordered=polygons.map((p,i)=>({...p,plane:planeOf(p.points),key:p.key??String(i)}))
            .filter(p=>p.plane).sort((a,b)=>{
                for(let k=0;k<3;k++) {
                    const delta=a.points.reduce((n,p)=>n+p[k],0)/a.points.length-b.points.reduce((n,p)=>n+p[k],0)/b.points.length;
                    if(Math.abs(delta)>EPS)return delta;
                }
                return a.key<b.key?-1:a.key>b.key?1:0;
            });
        const build=(items,depth)=>{
            if(!items.length)return null;
            if(depth>maxDepth || this.fragmentCount>maxPolygons)
                throw new Error('Transparent polyhedra exceed the face-ordering budget. Reduce centers/repetitions or use opaque faces.');
            let best=null,score=Infinity;
            const count=Math.min(11,items.length);
            for(let c=0;c<count;c++) {
                const plane=items[Math.floor(c*items.length/count)].plane;
                let front=0,back=0,cross=0;
                for(const item of items){const side=classify(item.points,plane);if(side===1)front++;else if(side===-1)back++;else if(side===2)cross++;}
                const value=cross*4+Math.abs(front-back);
                if(value<score){score=value;best=plane;}
            }
            const front=[],back=[],coplanar=[];
            for(const item of items) {
                const side=classify(item.points,best);
                if(side===0)coplanar.push(item);
                else if(side===1)front.push(item);
                else if(side===-1)back.push(item);
                else {const parts=split(item,best);front.push(parts[0]);back.push(parts[1]);this.fragmentCount++;}
            }
            coplanar.sort((a,b)=>a.key<b.key?-1:a.key>b.key?1:0);
            return {plane:best,polygons:coplanar,front:build(front,depth+1),back:build(back,depth+1)};
        };
        this.root=build(ordered,0);
    }

    ordered(eye,backward=null) {
        const result=[];
        const visit=node=>{
            if(!node)return;
            let side=backward ? dot(node.plane.normal,backward) : 0;
            if(!backward || Math.abs(side)<1e-12)side=dot(node.plane.normal,eye)-node.plane.offset;
            visit(side>=0?node.back:node.front);
            for(const polygon of node.polygons)result.push(polygon);
            visit(side>=0?node.front:node.back);
        };
        visit(this.root);return result;
    }
}
