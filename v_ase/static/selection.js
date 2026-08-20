import * as THREE from 'three';

export class ASESelection {
    constructor(renderer) {
        this.renderer = renderer;
        this.raycaster = new THREE.Raycaster();
        this.isSelecting = false;
        this.startPoint = new THREE.Vector2();
    }

    projectionContext(e) {
        return this.renderer.interactionProjectionContext(e.clientX, e.clientY);
    }

    getMouse(e, context = null) {
        return this.renderer.pointerNdc(e, context || this.projectionContext(e));
    }

    pick(e, atomGroup, supercellGroup = null, includeReplicas = false) {
        const context = this.projectionContext(e);
        const mouse = this.getMouse(e, context);
        this.raycaster.setFromCamera(mouse, context.camera);

        const repeatedAtoms = includeReplicas
            ? (supercellGroup?.children || [])
                .filter(object => object.userData?.supercellInstanced && object.visible !== false)
            : [];
        const intersects = this.raycaster.intersectObjects([...atomGroup.children, ...repeatedAtoms])
            .filter(hit => hit.object.visible !== false);
        if (intersects.length > 0) {
            for (const hit of intersects) {
                if (hit.object.userData.instancedAtoms) {
                    return hit.object.userData.atomIndices?.[hit.instanceId] ?? null;
                }
                if (hit.object.userData.supercellInstanced) {
                    const reference = this.renderer.supercellAtomReference(hit.object, hit.instanceId);
                    if (reference) return reference;
                }
                if (hit.object.userData.index !== undefined) return hit.object.userData.index;
            }
        }
        if ((this.renderer.atomMeshByIndex?.size || 0) > 2000) return null;
        return this.nearestProjectedAtom(e, atomGroup, context);
    }

    pickHover(e, atomGroup, supercellGroup) {
        const context = this.projectionContext(e);
        const mouse = this.getMouse(e, context);
        this.raycaster.setFromCamera(mouse, context.camera);
        const repeatedAtoms = (supercellGroup?.children || [])
            .filter(object => object.userData?.supercellInstanced && object.visible !== false);
        const candidates = [...atomGroup.children, ...repeatedAtoms];
        const intersects = this.raycaster.intersectObjects(candidates)
            .filter(hit => hit.object.visible !== false);
        for (const hit of intersects) {
            if (hit.object.userData.instancedAtoms) {
                return hit.object.userData.atomIndices?.[hit.instanceId] ?? null;
            }
            if (hit.object.userData.supercellInstanced) {
                const reference = this.renderer.supercellAtomReference(hit.object, hit.instanceId);
                if (reference) return reference;
            }
            if (hit.object.userData.index !== undefined) return hit.object.userData.index;
        }
        if ((this.renderer.atomMeshByIndex?.size || 0) > 2000) return null;
        return this.nearestProjectedAtom(e, atomGroup, context);
    }

    nearestProjectedAtom(e, atomGroup, context = this.projectionContext(e)) {
        let best = null;
        const tolerance = 24;
        const pos = new THREE.Vector3();
        this.renderer.forEachAtomProxy((mesh, index) => {
            if (
                mesh.visible === false
                || !this.renderer.atomReferenceVisible(index)
            ) return;
            pos.copy(mesh.position);
            const screenPos = this.renderer.projectWorldToClient(pos, context);
            if (screenPos.z > 1 || screenPos.z < -1) return;
            const dist = Math.hypot(e.clientX - screenPos.x, e.clientY - screenPos.y);
            if (dist <= tolerance && (!best || dist < best.dist)) {
                best = { index, dist };
            }
        });
        if (best) return best.index;
        return null;
    }

    boxSelect(rect, atomGroup, camera, supercellGroup = null, includeReplicas = false) {
        const selected = new Set();
        const pos = new THREE.Vector3();
        const context = this.renderer.interactionProjectionContext(
            (rect.left + rect.right) * 0.5,
            (rect.top + rect.bottom) * 0.5
        );
        
        this.renderer.forEachAtomProxy((mesh, index) => {
            if (
                mesh.visible === false
                || !this.renderer.atomReferenceVisible(index)
            ) return;
            pos.copy(mesh.position);
            const screenPos = this.renderer.projectWorldToClient(pos, context);
            if (screenPos.z > 1 || screenPos.z < -1) return;

            if (
                screenPos.x >= rect.left && screenPos.x <= rect.right
                && screenPos.y >= rect.top && screenPos.y <= rect.bottom
            ) {
                selected.add(index);
            }
        });

        if (includeReplicas) {
            const matrix = new THREE.Matrix4();
            (supercellGroup?.children || []).forEach(mesh => {
                if (!mesh.userData?.supercellInstanced || mesh.visible === false) return;
                mesh.updateMatrixWorld(true);
                for (let instanceId = 0; instanceId < mesh.count; instanceId++) {
                    const reference = this.renderer.supercellAtomReference(mesh, instanceId);
                    if (
                        !reference
                        || !this.renderer.atomReferenceVisible(reference.index, reference.cellOffset)
                    ) continue;
                    mesh.getMatrixAt(instanceId, matrix);
                    pos.setFromMatrixPosition(matrix).applyMatrix4(mesh.matrixWorld);
                    const screenPos = this.renderer.projectWorldToClient(pos, context);
                    if (screenPos.z > 1 || screenPos.z < -1) continue;
                    if (
                        screenPos.x >= rect.left && screenPos.x <= rect.right
                        && screenPos.y >= rect.top && screenPos.y <= rect.bottom
                    ) {
                        selected.add(reference);
                    }
                }
            });
        }

        return selected;
    }
}
