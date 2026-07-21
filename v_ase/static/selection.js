import * as THREE from 'three';

export class ASESelection {
    constructor(renderer) {
        this.renderer = renderer;
        this.raycaster = new THREE.Raycaster();
        this.isSelecting = false;
        this.startPoint = new THREE.Vector2();
    }

    getMouse(e) {
        return new THREE.Vector2(
            (e.clientX / window.innerWidth) * 2 - 1,
            -(e.clientY / window.innerHeight) * 2 + 1
        );
    }

    pick(e, atomGroup) {
        const mouse = this.getMouse(e);
        this.raycaster.setFromCamera(mouse, this.renderer.camera);
        
        const intersects = this.raycaster.intersectObjects(atomGroup.children)
            .filter(hit => hit.object.visible !== false);
        if (intersects.length > 0) {
            const hit = intersects[0];
            if (hit.object.userData.instancedAtoms) {
                return hit.object.userData.atomIndices?.[hit.instanceId] ?? null;
            }
            return hit.object.userData.index;
        }
        if ((this.renderer.atomMeshByIndex?.size || 0) > 2000) return null;
        return this.nearestProjectedAtom(e, atomGroup);
    }

    pickHover(e, atomGroup, supercellGroup) {
        const mouse = this.getMouse(e);
        this.raycaster.setFromCamera(mouse, this.renderer.camera);
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
                const indices = hit.object.userData.atomIndices || [];
                if (!indices.length || hit.instanceId === undefined || hit.instanceId === null) continue;
                return indices[hit.instanceId % indices.length] ?? null;
            }
            if (hit.object.userData.index !== undefined) return hit.object.userData.index;
        }
        if ((this.renderer.atomMeshByIndex?.size || 0) > 2000) return null;
        return this.nearestProjectedAtom(e, atomGroup);
    }

    nearestProjectedAtom(e, atomGroup) {
        let best = null;
        const tolerance = 24;
        const pos = new THREE.Vector3();
        this.renderer.forEachAtomProxy((mesh, index) => {
            if (mesh.visible === false || !this.renderer.atomTypeVisible(index)) return;
            pos.copy(mesh.position);
            const screenPos = pos.project(this.renderer.camera);
            if (screenPos.z > 1 || screenPos.z < -1) return;
            const x = (screenPos.x + 1) / 2 * window.innerWidth;
            const y = -(screenPos.y - 1) / 2 * window.innerHeight;
            const dist = Math.hypot(e.clientX - x, e.clientY - y);
            if (dist <= tolerance && (!best || dist < best.dist)) {
                best = { index, dist };
            }
        });
        if (best) return best.index;
        return null;
    }

    boxSelect(rect, atomGroup, camera) {
        const selected = new Set();
        const pos = new THREE.Vector3();
        
        this.renderer.forEachAtomProxy((mesh, index) => {
            if (mesh.visible === false || !this.renderer.atomTypeVisible(index)) return;
            pos.copy(mesh.position);
            
            // Project to screen space
            const screenPos = pos.project(camera);
            
            // Check if behind camera
            if (screenPos.z > 1 || screenPos.z < -1) return;
            
            // Convert to CSS pixels
            const x = (screenPos.x + 1) / 2 * window.innerWidth;
            const y = -(screenPos.y - 1) / 2 * window.innerHeight;

            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                selected.add(index);
            }
        });

        return selected;
    }
}
