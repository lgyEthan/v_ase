import * as THREE from 'three';

const AXIS_COLOR_PROPERTIES = {
    X: ['--axis-x', '#f05b55'],
    Y: ['--axis-y', '#69b942'],
    Z: ['--axis-z', '#408cd5']
};

function cssColor(property, fallback) {
    if (typeof document === 'undefined') return fallback;
    const value = getComputedStyle(document.documentElement).getPropertyValue(property).trim();
    return value || fallback;
}

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
        Object.entries(AXIS_COLOR_PROPERTIES).forEach(([axis, [property, fallback]]) => {
            const color = cssColor(property, fallback);
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
        });

        const pivotMat = new THREE.MeshBasicMaterial({
            color: cssColor('--amber', '#f3be57'),
            transparent: true,
            opacity: 0.95,
            depthTest: false,
            depthWrite: false
        });
        this.pivotMarker = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 12), pivotMat);
        this.pivotMarker.renderOrder = 42;
        this.guideRoot.add(this.pivotMarker);

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

        const cameraScale = camera ? Math.max(this.pivot.distanceTo(camera.position) * 0.08, 0.85) : 1.0;
        this.pivotMarker.scale.setScalar(Math.max(1, cameraScale * 0.18));

        if (this.axis && this.mode !== 'IDLE') {
            this.axisGuides[this.axis].visible = true;
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
    }
}
