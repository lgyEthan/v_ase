import * as THREE from 'three';

const AXIS_COLORS = {
    X: 0xff3b30,
    Y: 0x34c759,
    Z: 0x0a84ff
};

const AXIS_VECTORS = {
    X: new THREE.Vector3(1, 0, 0),
    Y: new THREE.Vector3(0, 1, 0),
    Z: new THREE.Vector3(0, 0, 1)
};

export class ASETransform {
    constructor(scene) {
        this.scene = scene;
        this.mode = 'IDLE'; // IDLE, MOVE, ROTATE
        this.axis = null; // X, Y, Z
        this.buffer = "";
        this.pointerDelta = new THREE.Vector2(0, 0);
        this.rotationAngle = 0;
        this.pivot = new THREE.Vector3();

        this.setupGuides();
    }

    setupGuides() {
        this.guideRoot = new THREE.Group();
        this.guideRoot.visible = false;
        this.scene.add(this.guideRoot);

        this.axisGuides = {};
        this.axisRotateRings = {};
        Object.entries(AXIS_COLORS).forEach(([axis, color]) => {
            const group = new THREE.Group();
            const mat = new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity: 0.92,
                depthTest: false,
                depthWrite: false
            });
            const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, 80, 16), mat);
            const coneA = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.42, 24), mat);
            const coneB = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.42, 24), mat);

            shaft.position.set(0, 0, 0);
            coneA.position.set(0, 40.25, 0);
            coneB.position.set(0, -40.25, 0);
            coneB.rotation.x = Math.PI;

            group.add(shaft, coneA, coneB);
            if (axis === 'X') group.rotation.z = -Math.PI / 2;
            if (axis === 'Z') group.rotation.x = Math.PI / 2;
            group.visible = false;
            group.renderOrder = 40;
            this.guideRoot.add(group);
            this.axisGuides[axis] = group;

            const ringMat = new THREE.MeshBasicMaterial({
                color,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.72,
                depthTest: false,
                depthWrite: false
            });
            const ring = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.026, 12, 128), ringMat);
            ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), AXIS_VECTORS[axis]);
            ring.visible = false;
            ring.renderOrder = 41;
            this.guideRoot.add(ring);
            this.axisRotateRings[axis] = ring;
        });

        const pivotMat = new THREE.MeshBasicMaterial({
            color: 0xffc400,
            transparent: true,
            opacity: 0.95,
            depthTest: false,
            depthWrite: false
        });
        this.pivotMarker = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 12), pivotMat);
        this.pivotMarker.renderOrder = 42;
        this.guideRoot.add(this.pivotMarker);

        const moveMat = new THREE.MeshBasicMaterial({
            color: 0xffc400,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.65,
            depthTest: false,
            depthWrite: false
        });
        this.freeMoveRing = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.018, 12, 96), moveMat);
        this.freeMoveRing.visible = false;
        this.guideRoot.add(this.freeMoveRing);

        const rotateMat = new THREE.MeshBasicMaterial({
            color: 0xbf5af2,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.82,
            depthTest: false,
            depthWrite: false
        });
        this.rotateRing = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.024, 12, 128), rotateMat);
        this.rotateRing.visible = false;
        this.guideRoot.add(this.rotateRing);
    }

    enter(mode, pivot, camera = null) {
        this.mode = mode;
        this.buffer = "";
        this.axis = null;
        this.pointerDelta.set(0, 0);
        this.rotationAngle = 0;
        this.pivot.copy(pivot);
        this.updateGuides(camera);
    }

    setAxis(axis, camera = null) {
        this.axis = axis;
        this.updateGuides(camera);
    }

    updateGuides(camera = null) {
        this.guideRoot.visible = this.mode !== 'IDLE';
        this.guideRoot.position.copy(this.pivot);
        Object.values(this.axisGuides).forEach(g => g.visible = false);
        Object.values(this.axisRotateRings).forEach(g => g.visible = false);

        const cameraScale = camera ? Math.max(this.pivot.distanceTo(camera.position) * 0.08, 0.85) : 1.0;
        this.freeMoveRing.scale.setScalar(cameraScale);
        this.rotateRing.scale.setScalar(cameraScale);
        this.pivotMarker.scale.setScalar(Math.max(1, cameraScale * 0.18));

        this.freeMoveRing.visible = this.mode === 'MOVE' && !this.axis;
        this.rotateRing.visible = this.mode === 'ROTATE' && !this.axis;

        if (camera && (this.freeMoveRing.visible || this.rotateRing.visible)) {
            this.freeMoveRing.lookAt(camera.position);
            this.rotateRing.lookAt(camera.position);
        }

        if (this.axis && this.mode !== 'IDLE') {
            this.axisGuides[this.axis].visible = true;
            if (this.mode === 'ROTATE') {
                const ring = this.axisRotateRings[this.axis];
                ring.visible = true;
                ring.scale.setScalar(cameraScale * 1.15);
            }
        }
    }

    getNumericValue() {
        if (this.buffer !== "") {
            const val = parseFloat(this.buffer);
            if (!isNaN(val)) return val;
        }
        return null;
    }

    exit() {
        this.mode = 'IDLE';
        this.axis = null;
        this.buffer = "";
        this.pointerDelta.set(0, 0);
        this.rotationAngle = 0;
        this.guideRoot.visible = false;
        Object.values(this.axisGuides).forEach(g => g.visible = false);
        Object.values(this.axisRotateRings).forEach(g => g.visible = false);
        this.freeMoveRing.visible = false;
        this.rotateRing.visible = false;
    }
}
