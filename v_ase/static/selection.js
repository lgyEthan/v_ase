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
            .filter(hit => hit.object.userData.index !== undefined && !hit.object.userData.lockMarker);
        if (intersects.length > 0) {
            return intersects[0].object.userData.index;
        }
        return null;
    }

    boxSelect(rect, atomGroup, camera) {
        const selected = new Set();
        
        atomGroup.children.forEach(mesh => {
            if (mesh.userData.index === undefined || mesh.userData.lockMarker) return;
            const pos = new THREE.Vector3();
            mesh.getWorldPosition(pos);
            
            // Project to screen space
            const screenPos = pos.project(camera);
            
            // Check if behind camera
            if (screenPos.z > 1 || screenPos.z < -1) return;
            
            // Convert to CSS pixels
            const x = (screenPos.x + 1) / 2 * window.innerWidth;
            const y = -(screenPos.y - 1) / 2 * window.innerHeight;

            if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                selected.add(mesh.userData.index);
            }
        });

        return selected;
    }
}
