import * as THREE from 'three';
import {refineSurface, refineSurfaceAsync, normalizeSubdivision, normalizeSmoothing} from './surface_refinement.js';

export const normalizeSegments = value => Math.max(8,Math.min(128,Math.round((Number(value)||32)/2)*2));
const levels=[8,12,16,24,32,48,64,96,128];
// A screen-space error bound, never an atom-count quality cap. Tight close-ups
// automatically reach the requested maximum; tiny distant glyphs cost less.
export function projectedSegments(radiusPixels, maximum) {
    const needed=Math.ceil(Math.PI/Math.acos(Math.max(-1,1-.2/Math.max(.2,radiusPixels))));
    return Math.min(maximum,levels.find(n=>n>=needed)||128);
}
export function installRenderQuality(Renderer) {
    const p=Renderer.prototype;
    p.qualityGeometry=function(kind,segments){
        const key=`quality:${kind}:${segments}`;
        if(!this.geometryCache.has(key))this.geometryCache.set(key,kind==='sphere'
            ?new THREE.SphereGeometry(1,segments,Math.max(8,Math.floor(segments*.65)))
            :new THREE.CylinderGeometry(.5,.5,1,segments));
        return this.geometryCache.get(key);
    };
    p.applyLiveGeometryQuality=function(){
        const segments=this.sphereQualitySegments(this.atomsData?.symbols?.length||0);
        const updateSphere=mesh=>{
            if(mesh.geometry?.type!=='SphereGeometry')return;
            const previous=mesh.geometry;mesh.geometry=this.qualityGeometry('sphere',segments);
            if(!mesh.userData.sharedGeometry&&previous!==mesh.geometry)previous.dispose();
            mesh.userData.sharedGeometry=true;
        };
        for(const mesh of this.atomMeshes?.children||[])updateSphere(mesh);
        for(const group of [this.supercellGroup,this.polyhedraGroup])for(const mesh of group?.children||[])updateSphere(mesh);
        const old=this.bondCylinderGeometry;
        this.bondCylinderGeometry=this.qualityGeometry('bond',segments);
        for(const group of [this.bondGroup,this.supercellGroup,this.polyhedraGroup])for(const mesh of group?.children||[])
            if(mesh.geometry===old||(mesh.userData?.polyhedraBondSegments && mesh.geometry?.type==='CylinderGeometry'))mesh.geometry=this.bondCylinderGeometry;
        // The initial constructor geometry is not in the shared cache.
        if(old&&!Array.from(this.geometryCache.values()).includes(old))old.dispose();
        this.requestRender();
    };
    p.reportQualityLimit=function(message){
        this.qualityLimitMessage=message;this.domElement.dataset.qualityWarning=message;
        this.onQualityLimit?.(message);
    };
    p.prepareQualityDraw=function(camera){
        if(!this.displayOptions.atomSmoothness||this.atomDisplayMode()==='2d')return ()=>{};
        this.scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
        const frustum=new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse));
        const size=this.renderer.getDrawingBufferSize(new THREE.Vector2());
        const center=new THREE.Vector3(),view=new THREE.Vector3(),sphere=new THREE.Sphere();
        const assignments=[];let drawn=0,culled=0,maxSegments=0,triangles=0;
        // These temporary draw buffers do not change scientific instance IDs,
        // water packing, picking, selection, radii or the next trajectory write.
        for(const group of [this.atomMeshes,this.supercellGroup,this.polyhedraGroup,this.bondGroup]) {
            if(!group?.visible)continue;
            for(const mesh of group.children) {
                const kind=mesh.geometry?.type==='SphereGeometry'?'sphere':mesh.geometry===this.bondCylinderGeometry?'bond':null;
                if(!kind||!mesh.visible)continue;
                const maximum=kind==='sphere'?mesh.geometry.parameters.widthSegments:mesh.geometry.parameters.radialSegments;
                const count=mesh.isInstancedMesh?mesh.count:1, matrix=mesh.instanceMatrix?.array;
                let maxRadius=0,live=0;
                let scratch=mesh.userData.qualityScratch;
                if(mesh.isInstancedMesh&&(!scratch||scratch.capacity<count)) {
                    if(scratch){const originalMatrix=mesh.instanceMatrix,originalColor=mesh.instanceColor;mesh.instanceMatrix=scratch.matrix;mesh.instanceColor=scratch.color;mesh.dispose();mesh.instanceMatrix=originalMatrix;mesh.instanceColor=originalColor;}
                    scratch={capacity:count,matrix:new THREE.InstancedBufferAttribute(new Float32Array(count*16),16),
                        color:mesh.instanceColor?new THREE.InstancedBufferAttribute(new Float32Array(count*3),3):null,
                        originalMatrix:mesh.instanceMatrix,originalColor:mesh.instanceColor};
                    mesh.userData.qualityScratch=scratch;
                }
                for(let i=0;i<count;i++) {
                    const k=i*16;
                    let radius;
                    if(matrix) {
                        center.set(matrix[k+12],matrix[k+13],matrix[k+14]).applyMatrix4(mesh.matrixWorld);
                        radius=kind==='sphere'?Math.hypot(matrix[k],matrix[k+1],matrix[k+2]):.5*Math.max(Math.hypot(matrix[k],matrix[k+1],matrix[k+2]),Math.hypot(matrix[k+8],matrix[k+9],matrix[k+10]));
                    } else {center.setFromMatrixPosition(mesh.matrixWorld);radius=Math.abs(mesh.scale.x);}
                    const boundsRadius=kind==='bond'&&matrix?Math.hypot(radius,.5*Math.hypot(matrix[k+4],matrix[k+5],matrix[k+6])):radius;
                    sphere.center.copy(center);sphere.radius=boundsRadius;
                    if(radius<=0||(!this.shadowModeActive&&!frustum.intersectsSphere(sphere))){culled++;continue;}
                    view.copy(center).applyMatrix4(camera.matrixWorldInverse);
                    const pixels=radius*size.y*.5*Math.abs(camera.projectionMatrix.elements[5])/(camera.isPerspectiveCamera?Math.max(.001,-view.z-boundsRadius):1);
                    maxRadius=Math.max(maxRadius,pixels);
                    if(matrix){scratch.matrix.array.set(matrix.subarray(k,k+16),live*16);if(scratch.color)scratch.color.array.set(mesh.instanceColor.array.subarray(i*3,i*3+3),live*3);}
                    live++;
                }
                const segments=projectedSegments(maxRadius,maximum);maxSegments=Math.max(maxSegments,segments);drawn+=live;
                assignments.push([mesh,mesh.geometry,mesh.instanceMatrix,mesh.instanceColor,mesh.count,mesh.visible,mesh.frustumCulled]);
                mesh.geometry=this.qualityGeometry(kind,segments);mesh.visible=live>0;
                // Do not let Three cache a bounding sphere from compacted IDs.
                mesh.frustumCulled=false;
                triangles+=mesh.geometry.index.count/3*live;
                if(matrix){mesh.instanceMatrix=scratch.matrix;mesh.instanceColor=scratch.color;mesh.count=live;scratch.matrix.needsUpdate=true;if(scratch.color)scratch.color.needsUpdate=true;}
            }
        }
        this.domElement.dataset.qualityDrawn=String(drawn);this.domElement.dataset.qualityCulled=String(culled);this.domElement.dataset.qualitySegments=String(maxSegments);
        const restore=()=>{for(const [mesh,geometry,matrix,color,count,visible,frustumCulled] of assignments){mesh.geometry=geometry;mesh.instanceMatrix=matrix;mesh.instanceColor=color;mesh.count=count;mesh.visible=visible;mesh.frustumCulled=frustumCulled;}};
        // Reject before a pathological GPU submission. A JavaScript Cancel
        // button cannot interrupt a draw already submitted to the driver.
        if(triangles>20000000 && !this.exportCaptureActive){
            restore();
            if(this.displayOptions.atomSmoothness<=12){
                const skip=()=>{};skip.skip=true;
                this.reportQualityLimit('This view still exceeds the interactive triangle budget. Hide objects or reduce repetitions. The last completed view is retained.');
                return skip;
            }
            this.displayOptions.atomSmoothness=12;this.applyLiveGeometryQuality();
            this.reportQualityLimit('The requested view exceeds 20 million atom/bond triangles. Switched to 12 segments; hide objects or reduce repetitions before raising quality.');
            return this.prepareQualityDraw(camera);
        }
        return restore;
    };

    p.surfaceQualityRecords=function(){
        const records=[];
        if(this.waterLayer?.mesh?.geometry.index?.count>0&&this.waterLayer.group.visible)records.push({target:this.waterLayer.mesh,kind:'water'});
        if(this.volumetricGroup?.visible)for(const target of this.volumetricSurfaces||[])
            if(target.geometry.index?.count>0)records.push({target,kind:'isosurface'});
        return records;
    };
    p.notifySurfaceQuality=function(){
        const jobs=Array.from(this.surfaceQualityJobs?.values()||[]);
        this.surfaceQualityError=this.surfaceQualityCapacityError
            ||this.surfaceQualityRecords().map(({target})=>target._surfaceQuality?.error).find(Boolean)||null;
        this.surfaceQualityFailed=Boolean(this.surfaceQualityError);
        this.domElement.dataset.surfaceQualityBusy=String(jobs.length>0);
        if(this.waterLayer){const triangles=this.waterLayer.group.visible?(this.waterLayer.mesh?.geometry.index?.count/3||0):0;this.domElement.dataset.waterRenderedTriangles=String(triangles);this.waterLayer.report.renderedTriangles=triangles;}
        const records=this.surfaceQualityRecords();
        const available={water:records.some(r=>r.kind==='water'),isosurface:records.some(r=>r.kind==='isosurface')};
        const status={busy:jobs.length>0,progress:jobs.length?Math.min(...jobs.map(j=>j.progress||0)):1,error:this.surfaceQualityError||null,available};
        const signature=JSON.stringify([status.busy,Math.round(status.progress*100),status.error,this.qualityLimitMessage,available.water,available.isosurface]);
        if(signature!==this.surfaceQualityStatusSignature||this.surfaceQualityListener!==this.onSurfaceQualityChange){
            this.surfaceQualityStatusSignature=signature;this.surfaceQualityListener=this.onSurfaceQualityChange;
            this.onSurfaceQualityChange?.(status);
        }
    };
    p.cancelSurfaceQuality=function(){
        for(const job of this.surfaceQualityJobs?.values()||[])job.controller.abort();
        this.surfaceQualityJobs?.clear();this.notifySurfaceQuality();
    };
    p.releaseSurfaceQuality=function(target){
        if(!target)return;
        this.surfaceQualityJobs?.get(target)?.controller.abort();this.surfaceQualityJobs?.delete(target);
        const q=target._surfaceQuality;
        if(q&&q.base!==target.geometry)q.base.dispose();
        target._surfacePendingBase?.dispose();delete target._surfacePendingBase;delete target._surfaceQuality;
    };
    p.replaceWaterQualitySource=function(mesh,geometry){
        const previous=mesh._surfaceQuality;
        if(geometry.index?.count>0&&previous&&previous.applied!==previous.base&&(this.displayOptions.waterInterpolation>0||this.displayOptions.waterMeshSmoothing>0)){
            this.surfaceQualityJobs?.get(mesh)?.controller.abort();this.surfaceQualityJobs?.delete(mesh);
            mesh._surfacePendingBase?.dispose();mesh._surfacePendingBase=geometry;
        } else {this.releaseSurfaceQuality(mesh);mesh.geometry.dispose();mesh.geometry=geometry;}
    };
    p.refreshSurfaceQuality=function({synchronous=false}={}){
        this.surfaceQualityJobs??=new Map();
        const records=this.surfaceQualityRecords(),active=new Set(records.map(r=>r.target));
        const refinedTriangles=records.reduce((sum,{target,kind})=>{
            const level=normalizeSubdivision(this.displayOptions[`${kind}Interpolation`]);
            const base=target._surfacePendingBase||target._surfaceQuality?.base||target.geometry;
            const smoothing=normalizeSmoothing(this.displayOptions[`${kind}MeshSmoothing`]);
            return sum+(level||smoothing ? (base.index?.count||0)/3*4**level : 0);
        },0);
        if(refinedTriangles>12000000){
            this.surfaceQualityCapacityError='Combined surface interpolation exceeds 12,000,000 triangles. Lower subdivision or remove unused surfaces.';
            this.cancelSurfaceQuality();
            if(synchronous)throw new Error(this.surfaceQualityError);
            return;
        }
        this.surfaceQualityCapacityError=null;
        for(const [target,job] of this.surfaceQualityJobs)if(!active.has(target)){job.controller.abort();this.surfaceQualityJobs.delete(target);}
        for(const {target,kind} of records) {
            const level=normalizeSubdivision(this.displayOptions[`${kind}Interpolation`]);
            const smoothing=normalizeSmoothing(this.displayOptions[`${kind}MeshSmoothing`]);
            const key=`${level}:${smoothing}`;
            let record=target._surfaceQuality;
            if(target._surfacePendingBase){
                if(record&&record.base!==record.applied)record.base.dispose();
                record={base:target._surfacePendingBase,applied:target.geometry,level:-1,key:''};
                delete target._surfacePendingBase;target._surfaceQuality=record;
            }
            if(!record||target.geometry!==record.applied){
                this.surfaceQualityJobs.get(target)?.controller.abort();this.surfaceQualityJobs.delete(target);
                if(record&&record.base!==record.applied)record.base.dispose();
                record={base:target.geometry,applied:target.geometry,level:0,key:'0:0'};target._surfaceQuality=record;
            }
            const oldJob=this.surfaceQualityJobs.get(target);
            if(oldJob?.key!==key){oldJob?.controller.abort();this.surfaceQualityJobs.delete(target);}
            if(record.key===key)continue;
            record.error=null;
            if(oldJob?.key===key&&!synchronous)continue;
            oldJob?.controller.abort();this.surfaceQualityJobs.delete(target);
            const setGeometry=geometry=>{
                const old=record.applied;record.applied=geometry;record.level=level;record.key=key;target.geometry=geometry;
                if(old!==record.base)old.dispose();
                if(kind==='isosurface')this.rebuildVolumetricSurfaces();
                this.requestRender();
            };
            if(!level&&!smoothing){setGeometry(record.base);continue;}
            const base=record.base;
            const source={positions:base.attributes.position.array,normals:base.attributes.normal.array,indices:base.index.array};
            const accept=result=>{
                const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(result.positions,3));
                geometry.setAttribute('normal',new THREE.BufferAttribute(result.normals,3));geometry.setIndex(new THREE.BufferAttribute(result.indices,1));geometry.computeBoundingSphere();setGeometry(geometry);
            };
            if(synchronous){const iterator=refineSurface(source,level,{smoothing});let step;do{step=iterator.next();}while(!step.done);accept(step.value);continue;}
            const controller=new AbortController(),job={controller,level,key,progress:0};
            this.surfaceQualityJobs.set(target,job);this.surfaceQualityError=null;
            job.promise=refineSurfaceAsync(source,level,controller.signal,value=>{job.progress=value;this.notifySurfaceQuality();},{smoothing})
                .then(result=>{if(!controller.signal.aborted&&target.geometry===record.applied)accept(result);})
                .catch(error=>{if(!controller.signal.aborted&&this.surfaceQualityJobs.get(target)===job&&error.name!=='AbortError'){record.error=error.message;record.level=level;record.key=key;}})
                .finally(()=>{if(this.surfaceQualityJobs.get(target)===job)this.surfaceQualityJobs.delete(target);this.notifySurfaceQuality();});
        }
        this.notifySurfaceQuality();
    };
    p.prepareSurfaceCapture=async function(){
        for(;;){
            this.refreshWaterSurface?.();this.refreshSurfaceQuality();
            const jobs=Array.from(this.surfaceQualityJobs?.values()||[],job=>job.promise);
            if(!jobs.length)break;
            await Promise.all(jobs);
            if(this.surfaceQualityFailed)break;
        }
        if(this.surfaceQualityFailed)throw new Error(this.surfaceQualityError||'Surface quality could not be prepared. Lower interpolation.');
    };
    const options=p.setDisplayOptions;
    p.setDisplayOptions=function(value,...args){
        const before=this.displayOptions.atomSmoothness;
        const changed=['waterInterpolation','isosurfaceInterpolation','waterMeshSmoothing','isosurfaceMeshSmoothing'].some(k=>this.displayOptions[k]!==value[k]&&k in value);
        const result=options.call(this,value,...args);
        if(before!==this.displayOptions.atomSmoothness){this.qualityLimitMessage=null;delete this.domElement.dataset.qualityWarning;this.applyLiveGeometryQuality();}
        if(changed){this.surfaceQualityFailed=false;this.surfaceQualityError=null;this.refreshSurfaceQuality();}
        return result;
    };
    const draw=p.renderScientificScene;
    p.renderScientificScene=function(...args){this.refreshSurfaceQuality({synchronous:Boolean(this._qualitySynchronousCapture)});return draw.apply(this,args);};
    const blob=p.exportPNGBlob;
    p.exportPNGBlob=async function(...args){await this.prepareSurfaceCapture();return blob.apply(this,args);};
    const png=p.exportPNG;
    p.exportPNG=function(...args){this._qualitySynchronousCapture=true;try{return png.apply(this,args);}finally{this._qualitySynchronousCapture=false;}};
    const disposeObject=p.disposeObject;
    p.disposeObject=function(object){
        object.traverse?.(mesh=>{
            const scratch=mesh.userData?.qualityScratch;
            if(scratch){const matrix=mesh.instanceMatrix,color=mesh.instanceColor;mesh.instanceMatrix=scratch.matrix;mesh.instanceColor=scratch.color;mesh.dispose();mesh.instanceMatrix=matrix;mesh.instanceColor=color;delete mesh.userData.qualityScratch;}
            if(mesh.isInstancedMesh)mesh.dispose();
        });
        return disposeObject.call(this,object);
    };
    const clearVolumes=p.clearVolumetricSurfaces;
    p.clearVolumetricSurfaces=function(...args){
        for(const target of this.volumetricSurfaces||[])this.releaseSurfaceQuality(target);
        return clearVolumes.apply(this,args);
    };
    const dispose=p.dispose;
    p.dispose=function(...args){this.cancelSurfaceQuality();for(const target of [this.waterLayer?.mesh,...(this.volumetricSurfaces||[])])this.releaseSurfaceQuality(target);return dispose.apply(this,args);};
}
