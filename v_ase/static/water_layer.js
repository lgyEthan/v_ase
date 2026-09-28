import * as THREE from 'three';
import { normalizeWater, detectWater, buildWaterGeometry } from './water_geometry.js';

// One coalesced build at the draw boundary keeps trajectory atoms and surface
// coherent. The exact same boundary is used by PNG/video/offline-HTML rendering.
export function installWaterRenderer(Renderer) {
    const p=Renderer.prototype;
    p.ensureWaterLayer=function(){
        if(this.waterLayer)return this.waterLayer;
        const group=new THREE.Group();group.name='v_ase_water_surface';this.scene.add(group);
        return this.waterLayer={group,dirty:true,hidden:new Set(),mesh:null,key:null,report:{molecules:0}};
    };
    p.refreshWaterSurface=function(){
        const w=this.ensureWaterLayer();
        if(!w.dirty)return;
        w.dirty=false;
        const before=[...w.hidden].join(',');
        try {
            const cfg=normalizeWater(this.displayOptions.waterSurface);
            if(!cfg.enabled||!this.atomsData){
                w.group.visible=false;w.hidden.clear();w.key=null;
                w.mesh?.geometry.dispose();w.mesh?.material.dispose();w.group.clear();w.mesh=null;w.materialKey=null;
                w.report={molecules:0,triangles:0};
            } else {
                const start=performance.now();
                const detected=detectWater(this.atomsData,cfg);
                const reps=(this.displayOptions.supercell||[1,1,1]).map(n=>Math.max(1,Math.round(n)));
                if(detected.molecules.length*reps.reduce((a,b)=>a*b,1)>20000)throw new Error('Water preview exceeds 20,000 displayed molecules. Reduce repetitions or scope.');
                const centers=[], visible=[];
                const cell=this.atomsData.cell;
                for(const m of detected.molecules){
                    // Visibility is tested without the water replacement mask.
                    if(!this.waterSourceVisible(m.oxygen))continue;
                    visible.push(m);
                    for(let a=0;a<reps[0];a++)for(let b=0;b<reps[1];b++)for(let c=0;c<reps[2];c++){
                        if(!this.waterSourceVisible(m.oxygen,[a,b,c]))continue;
                        centers.push(m.position.map((v,k)=>v+(cell?.[0]?.[k]||0)*a+(cell?.[1]?.[k]||0)*b+(cell?.[2]?.[k]||0)*c));
                    }
                }
                const key=JSON.stringify([centers,cfg.smoothing,cfg.level,cfg.spacing]);
                if(key!==w.key){
                    const result=buildWaterGeometry(centers,cfg);
                    const geometry=new THREE.BufferGeometry();
                    geometry.setAttribute('position',new THREE.BufferAttribute(result.positions,3));
                    geometry.setAttribute('normal',new THREE.BufferAttribute(result.normals,3));
                    geometry.computeBoundingSphere();
                    if(!w.mesh){w.mesh=new THREE.Mesh();w.mesh.name='Water density envelope';w.mesh.renderOrder=4;w.group.add(w.mesh);}
                    w.mesh.geometry.dispose();w.mesh.geometry=geometry;w.key=key;
                    w.gridPoints=result.gridPoints;w.spacing=result.spacing;
                }
                const lit=cfg.lighting&&this.atomDisplayMode()!=='2d';
                const materialKey=JSON.stringify([lit,cfg.color,cfg.opacity,cfg.roughness]);
                if(w.mesh&&w.materialKey!==materialKey){
                    w.mesh.material.dispose();
                    const common={color:cfg.color,opacity:cfg.opacity,transparent:cfg.opacity<1,depthWrite:cfg.opacity===1,side:THREE.DoubleSide};
                    w.mesh.material=lit?new THREE.MeshPhysicalMaterial({...common,roughness:cfg.roughness,metalness:0,clearcoat:1,clearcoatRoughness:cfg.roughness,ior:1.333,specularIntensity:1,envMap:this.ensureMetalEnvironmentMap(),envMapIntensity:0.45}):new THREE.MeshBasicMaterial({...common,toneMapped:false});
                    w.materialKey=materialKey;
                }
                w.group.visible=centers.length>0;
                w.group.position.copy(this.visualTranslationVector());
                w.hidden=new Set(cfg.hideMolecules&&w.mesh?.geometry.attributes.position.count?visible.flatMap(m=>[m.oxygen,...m.hydrogens]):[]);
                w.report={molecules:visible.length,displayedMolecules:centers.length,triangles:(w.mesh?.geometry.attributes.position.count||0)/3,gridPoints:w.gridPoints,spacing:w.spacing,buildMs:performance.now()-start,excludedOxygens:detected.excludedOxygens};
            }
        } catch(error){
            w.group.visible=false;w.hidden.clear();w.report={error:error.message};
        }
        if(before!==[...w.hidden].join(','))this.applyAtomVisibility();
        this.domElement.dataset.waterMolecules=String(w.report.molecules||0);
        this.domElement.dataset.waterTriangles=String(w.report.triangles||0);
        this.onWaterSurfaceChange?.(w.report);
    };
    const reference=p.atomReferenceVisible;
    p.waterSourceVisible=function(...args){return reference.apply(this,args);};
    p.atomReferenceVisible=function(index,...args){
        return !this.waterLayer?.hidden.has(index)&&reference.call(this,index,...args);
    };
    for(const name of ['rebuildAtoms','updatePositions','updatePositionsFlat','setDisplayOptions']){
        const original=p[name];
        p[name]=function(...args){
            const w=this.ensureWaterLayer();w.dirty=true;
            if(name==='rebuildAtoms')w.hidden.clear();
            return original.apply(this,args);
        };
    }
    const draw=p.renderScientificScene;
    p.renderScientificScene=function(...args){this.refreshWaterSurface();return draw.apply(this,args);};
    const lightBounds=p.lightingStructureBounds;
    p.lightingStructureBounds=function(...args){
        const box=lightBounds.apply(this,args), group=this.waterLayer?.group;
        if(group?.visible&&this.waterLayer.mesh){group.updateMatrixWorld(true);box.union(new THREE.Box3().setFromObject(group));}
        return box;
    };
    const bounds=p.structureBounds;
    p.structureBounds=function(...args){
        let box=bounds.apply(this,args);
        const group=this.waterLayer?.group;
        if(group?.visible&&this.waterLayer.mesh){
            group.updateMatrixWorld(true);
            const extra=new THREE.Box3().setFromObject(group);
            if(!extra.isEmpty())box=box?box.union(extra):extra;
        }
        return box;
    };
}
