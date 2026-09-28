import * as THREE from 'three';
import { normalizeWater, detectWater, buildWaterGeometry } from './water_geometry.js';

// Non-atom instance buffers retain their scientific slot order between writes.
// Packing is only for drawing: zero-sized atoms/bonds are NOT sent to the GPU.
function restoreInstances(mesh) {
    const order=mesh.userData.waterInstanceOrder;
    if(!order)return;
    for(const attribute of [mesh.instanceMatrix,mesh.instanceColor])if(attribute){
        const src=attribute.array.slice(),size=attribute.itemSize;
        for(let i=0;i<order.length;i++)attribute.array.set(src.subarray(i*size,(i+1)*size),order[i]*size);
        attribute.needsUpdate=true;
    }
    mesh.count=order.length;delete mesh.userData.waterInstanceOrder;
}
function packInstances(mesh) {
    if(mesh.userData.waterInstanceOrder)return;
    const matrix=mesh.instanceMatrix.array,n=mesh.count,live=[],dead=[];
    for(let i=0;i<n;i++){
        const k=i*16;
        ((matrix[k]||matrix[k+1]||matrix[k+2])&&(matrix[k+4]||matrix[k+5]||matrix[k+6])?live:dead).push(i);
    }
    if(!dead.length)return;
    const order=live.concat(dead);
    for(const attribute of [mesh.instanceMatrix,mesh.instanceColor])if(attribute){
        const src=attribute.array.slice(),size=attribute.itemSize;
        for(let i=0;i<n;i++)attribute.array.set(src.subarray(order[i]*size,(order[i]+1)*size),i*size);
        attribute.needsUpdate=true;
    }
    mesh.userData.waterInstanceOrder=order;mesh.count=live.length;
}
export function installWaterRenderer(Renderer) {
    const p=Renderer.prototype;
    p.ensureWaterLayer=function(){
        if(this.waterLayer)return this.waterLayer;
        const group=new THREE.Group();group.name='v_ase_water_surface';this.scene.add(group);
        return this.waterLayer={group,dirty:true,revision:0,builds:0,hidden:new Set(),hiddenReferences:new Set(),mesh:null,key:null,report:{molecules:0}};
    };
    p.waterReplacementActive=function(){return this.waterLayer?.hiddenReferences.size>0;};
    p.packWaterInstances=function(){
        const w=this.waterLayer;if(!w)return;
        const enabled=this.waterReplacementActive();
        // Atom references always track their packed slots, including colors,
        // picking IDs, selection outlines and in-place trajectory updates.
        if(w.packAtoms){
            w.packAtoms=false;
            for(const mesh of this.atomInstanceMeshes||[]){
                const ids=mesh.userData.atomIndices,live=[],dead=[];
                for(const i of ids)(!enabled||this.atomGlyphVisible(i)?live:dead).push(i);
                const packed=live.concat(dead),colors=mesh.instanceColor?.array.slice();
                for(let slot=0;slot<packed.length;slot++){
                    const index=packed[slot],ref=this.atomInstanceRefs.get(index),old=ref.instanceId;
                    if(colors)mesh.instanceColor.array.set(colors.subarray(old*3,old*3+3),slot*3);
                    ref.instanceId=slot;ref.matrixOffset=slot*16;ref.colorOffset=slot*3;
                    this.updateAtomInstanceMatrix(index);
                }
                mesh.userData.atomIndices=packed;mesh.count=live.length;
                mesh.instanceMatrix.needsUpdate=true;if(mesh.instanceColor)mesh.instanceColor.needsUpdate=true;
            }
        }
        for(const group of [this.bondGroup,this.supercellGroup])for(const mesh of group?.children||[]){
            if(!mesh.isInstancedMesh||!(mesh.userData.supercellInstanced||mesh.userData.supercellBonds||mesh.userData.bondSegments))continue;
            if(enabled)packInstances(mesh);else restoreInstances(mesh);
        }
    };
    p.refreshWaterSurface=function(){
        const w=this.ensureWaterLayer();
        if(!w.dirty)return;
        w.dirty=false;
        const before=w.hiddenReferences;
        try {
            const cfg=normalizeWater(this.displayOptions.waterSurface);
            if(!cfg.enabled||!this.atomsData){
                w.group.visible=false;w.hidden=new Set();w.hiddenReferences=new Set();w.key=null;
                w.mesh?.geometry.dispose();w.mesh?.material.dispose();w.group.clear();w.mesh=null;w.materialKey=null;
                w.report={molecules:0,triangles:0,builds:w.builds};
            } else {
                const start=performance.now(),d=this.displayOptions;
                const reps=this.hasValidCell()?(d.supercell||[1,1,1]):[1,1,1];
                const key=JSON.stringify([w.revision,cfg.source,cfg.indices,cfg.ohCutoff,cfg.smoothing,cfg.level,cfg.spacing,
                    reps,d.labelVisible,d.hiddenAtomReferences,d.showPolyhedra,d.polyhedraAtomMode]);
                if(key!==w.key){
                    const detected=detectWater(this.atomsData,cfg),cell=this.atomsData.cell;
                    const offsets=reps.map(n=>this.supercellAxisOffsets(n)),centers=[],references=new Set(),base=new Set(),seen=new Set();
                    const instanceCount=offsets.reduce((n,values)=>n*values.length,1);
                    if(detected.molecules.length*instanceCount>500000)throw new Error('Water surface exceeds 500,000 displayed molecules. Reduce repetitions or source scope.');
                    for(const m of detected.molecules){
                        for(const a of offsets[0])for(const b of offsets[1])for(const c of offsets[2]){
                            const offset=(a||b||c)?[a,b,c]:null;
                            if(!this.waterSourceVisible(m.oxygen,offset))continue;
                            centers.push(m.position.map((v,k)=>v+(cell?.[0]?.[k]||0)*a+(cell?.[1]?.[k]||0)*b+(cell?.[2]?.[k]||0)*c));
                            seen.add(m.oxygen);
                            for(const i of [m.oxygen,...m.hydrogens]){references.add(this.atomReferenceKey(i,offset));if(!offset)base.add(i);}
                        }
                    }
                    const result=buildWaterGeometry(centers,cfg),geometry=new THREE.BufferGeometry();
                    geometry.setAttribute('position',new THREE.BufferAttribute(result.positions,3));
                    geometry.setAttribute('normal',new THREE.BufferAttribute(result.normals,3));
                    geometry.setIndex(new THREE.BufferAttribute(result.indices,1));geometry.computeBoundingSphere();
                    if(!w.mesh){w.mesh=new THREE.Mesh();w.mesh.name='Water density envelope';w.mesh.renderOrder=4;w.group.add(w.mesh);}
                    w.mesh.geometry.dispose();w.mesh.geometry=geometry;w.key=key;w.builds++;
                    w.base=base;w.references=references;
                    w.report={molecules:seen.size,displayedMolecules:centers.length,triangles:result.indices.length/3,
                        vertices:result.positions.length/3,gridPoints:result.gridPoints,spacing:result.spacing,buildMs:performance.now()-start,
                        excludedOxygens:detected.excludedOxygens,topologyMolecules:detected.topologyMolecules,method:detected.method,builds:w.builds};
                }
                const lit=cfg.lighting&&this.atomDisplayMode()!=='2d';
                const materialKey=JSON.stringify([lit,cfg.color,cfg.opacity,cfg.roughness]);
                if(w.mesh&&w.materialKey!==materialKey){
                    w.mesh.material.dispose();
                    const common={color:cfg.color,opacity:cfg.opacity,transparent:cfg.opacity<1,depthWrite:cfg.opacity===1,side:THREE.DoubleSide};
                    w.mesh.material=lit?new THREE.MeshPhysicalMaterial({...common,roughness:cfg.roughness,metalness:0,clearcoat:1,clearcoatRoughness:cfg.roughness,ior:1.333,specularIntensity:1,envMap:this.ensureMetalEnvironmentMap(),envMapIntensity:0.45}):new THREE.MeshBasicMaterial({...common,toneMapped:false});
                    w.materialKey=materialKey;
                }
                w.group.visible=w.report.triangles>0;w.group.position.copy(this.visualTranslationVector());
                w.hidden=cfg.hideMolecules&&w.group.visible?w.base:new Set();
                w.hiddenReferences=cfg.hideMolecules&&w.group.visible?w.references:new Set();
            }
        } catch(error){
            w.group.visible=false;w.hidden=new Set();w.hiddenReferences=new Set();w.key=null;w.report={error:error.message,builds:w.builds};
        }
        if(before.size!==w.hiddenReferences.size||[...before].some(key=>!w.hiddenReferences.has(key))){
            w.packAtoms=true;this.applyAtomVisibility();
        }
        this.domElement.dataset.waterMolecules=String(w.report.molecules||0);
        this.domElement.dataset.waterTriangles=String(w.report.triangles||0);
        this.onWaterSurfaceChange?.(w.report);
    };
    const reference=p.atomReferenceVisible;
    p.waterSourceVisible=function(...args){return reference.apply(this,args);};
    p.atomReferenceVisible=function(index,offset=null){
        const normalized=offset?.some(Boolean)?offset:null;
        return !this.waterLayer?.hiddenReferences.has(this.atomReferenceKey(index,normalized))&&reference.call(this,index,offset);
    };
    for(const name of ['rebuildAtoms','updatePositions','updatePositionsFlat','setDisplayOptions']){
        const original=p[name];
        p[name]=function(...args){
            const w=this.ensureWaterLayer();w.dirty=true;
            if(name!=='setDisplayOptions')w.revision++;
            if(name==='rebuildAtoms'){w.hidden=new Set();w.hiddenReferences=new Set();w.packAtoms=true;}
            return original.apply(this,args);
        };
    }
    const visibility=p.applyAtomVisibility;
    p.applyAtomVisibility=function(...args){const result=visibility.apply(this,args);if(this.waterLayer)this.waterLayer.packAtoms=true;return result;};
    // Restore canonical buffer slots only when something writes those slots.
    // Orbiting/zooming renders already packed GPU buffers with no per-atom work.
    for(const name of ['positionBondInstance','setSupercellInstanceMatrix']){
        const original=p[name];p[name]=function(mesh,...args){restoreInstances(mesh);return original.call(this,mesh,...args);};
    }
    for(const name of ['updateSupercellPositions','refreshSupercellAtomColors']){
        const original=p[name];p[name]=function(...args){
            for(const mesh of this.supercellGroup?.children||[])if(mesh.isInstancedMesh)restoreInstances(mesh);
            return original.apply(this,args);
        };
    }
    const replica=p.supercellAtomReference;
    p.supercellAtomReference=function(mesh,instanceId){return replica.call(this,mesh,mesh?.userData.waterInstanceOrder?.[instanceId]??instanceId);};
    const draw=p.renderScientificScene;
    p.renderScientificScene=function(...args){this.refreshWaterSurface();this.packWaterInstances();return draw.apply(this,args);};
    for(const name of ['lightingStructureBounds','structureBounds']){
        const original=p[name];p[name]=function(...args){
            let box=original.apply(this,args);const w=this.waterLayer;
            if(w?.group.visible&&w.mesh){w.group.updateMatrixWorld(true);const extra=new THREE.Box3().setFromObject(w.group);if(!extra.isEmpty())box=box?box.union(extra):extra;}
            return box;
        };
    }
}
