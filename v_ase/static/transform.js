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
        this.mode = 'IDLE'; // IDLE, MOVE, ROTATE, SCALE
        this.axis = null; // X, Y, Z
        this.buffer = "";
        this.pointerDelta = new THREE.Vector2(0, 0);
        this.rotationAngle = 0;
        this.scaleFactor = 1;
        this.pivot = new THREE.Vector3();
        this.visualOffset = new THREE.Vector3();
        this.rotationGuide = null;

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

        this.rotationGuideGroup = new THREE.Group();
        this.rotationGuideGroup.name = 'v_ase_rotation_reference_guides';
        this.rotationGuideGroup.visible = false;
        this.guideRoot.add(this.rotationGuideGroup);

        const segmentGeometry = new THREE.CylinderGeometry(1, 1, 1, 12, 1, false);
        const material = (color, opacity) => new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity,
            depthTest: false,
            depthWrite: false,
            toneMapped: false
        });
        this.rotationAxisMaterial = material(cssColor('--neutral-400', '#8d9995'), 0.52);
        this.rotationStartMaterial = material(cssColor('--neutral-500', '#71807a'), 0.86);
        this.rotationCurrentMaterial = material(cssColor('--amber', '#f3be57'), 1.0);
        this.rotationAxisLine = new THREE.Mesh(segmentGeometry, this.rotationAxisMaterial);
        this.rotationStartLine = new THREE.Mesh(segmentGeometry, this.rotationStartMaterial);
        this.rotationCurrentLine = new THREE.Mesh(segmentGeometry, this.rotationCurrentMaterial);
        this.rotationAxisLine.name = 'v_ase_rotation_axis';
        this.rotationStartLine.name = 'v_ase_rotation_start_reference';
        this.rotationCurrentLine.name = 'v_ase_rotation_current_reference';
        this.rotationAxisLine.userData.rotationGuideRole = 'axis';
        this.rotationStartLine.userData.rotationGuideRole = 'start';
        this.rotationCurrentLine.userData.rotationGuideRole = 'current';
        this.rotationAxisLine.renderOrder = 43;
        this.rotationStartLine.renderOrder = 44;
        this.rotationCurrentLine.renderOrder = 46;
        this.rotationGuideGroup.add(
            this.rotationAxisLine,
            this.rotationStartLine,
            this.rotationCurrentLine
        );
    }

    enter(mode, pivot, camera = null, { visualOffset = null } = {}) {
        this.mode = mode;
        this.buffer = "";
        this.axis = null;
        this.pointerDelta.set(0, 0);
        this.rotationAngle = 0;
        this.scaleFactor = 1;
        this.pivot.copy(pivot);
        this.visualOffset.copy(visualOffset?.isVector3 ? visualOffset : new THREE.Vector3());
        this.rotationGuide = null;
        this.updateGuides(camera);
    }

    setAxis(axis, camera = null) {
        this.axis = axis;
        this.updateGuides(camera);
    }

    placeGuideSegment(mesh, start, end, radius) {
        const delta = end.clone().sub(start);
        const length = delta.length();
        if (length <= 1e-8) {
            mesh.visible = false;
            return;
        }
        mesh.visible = true;
        mesh.position.copy(start).addScaledVector(delta, 0.5);
        mesh.quaternion.setFromUnitVectors(
            new THREE.Vector3(0, 1, 0),
            delta.normalize()
        );
        mesh.scale.set(radius, length, radius);
    }

    rotationAxisColor(axis) {
        const normalized = axis.clone().normalize();
        const tolerance = 1e-5;
        if (Math.abs(Math.abs(normalized.x) - 1) < tolerance) {
            return cssColor(...AXIS_COLOR_PROPERTIES.X);
        }
        if (Math.abs(Math.abs(normalized.y) - 1) < tolerance) {
            return cssColor(...AXIS_COLOR_PROPERTIES.Y);
        }
        if (Math.abs(Math.abs(normalized.z) - 1) < tolerance) {
            return cssColor(...AXIS_COLOR_PROPERTIES.Z);
        }
        return cssColor('--neutral-400', '#8d9995');
    }

    setRotationGuide({ axis, reference, radius = 3, angle = 0 } = {}, camera = null) {
        const normal = axis?.isVector3 ? axis.clone() : new THREE.Vector3(...(axis || []));
        const baseline = reference?.isVector3
            ? reference.clone()
            : new THREE.Vector3(...(reference || []));
        if (normal.lengthSq() <= 1e-12 || baseline.lengthSq() <= 1e-12) {
            this.rotationGuide = null;
            this.rotationGuideGroup.visible = false;
            return;
        }
        normal.normalize();
        baseline.addScaledVector(normal, -baseline.dot(normal));
        if (baseline.lengthSq() <= 1e-12) {
            this.rotationGuide = null;
            this.rotationGuideGroup.visible = false;
            return;
        }
        baseline.normalize();
        this.rotationGuide = {
            axis: normal,
            reference: baseline,
            radius: Math.max(1.4, Number(radius) || 3),
            angle: Number.isFinite(Number(angle)) ? Number(angle) : 0
        };
        this.updateGuides(camera);
    }

    updateRotationGuideGeometry(cameraScale) {
        const guide = this.rotationGuide;
        const visible = this.mode === 'ROTATE' && Boolean(guide);
        this.rotationGuideGroup.visible = visible;
        if (!visible) return;

        const radius = guide.radius;
        const lineRadius = THREE.MathUtils.clamp(cameraScale * 0.016, 0.025, 0.070);
        const axisRadius = lineRadius * 0.66;
        const start = guide.reference.clone();
        const current = start.clone().applyAxisAngle(guide.axis, guide.angle);
        const inner = radius * 0.15;
        this.rotationAxisMaterial.color.set(this.rotationAxisColor(guide.axis));
        this.placeGuideSegment(
            this.rotationAxisLine,
            guide.axis.clone().multiplyScalar(-radius * 0.52),
            guide.axis.clone().multiplyScalar(radius * 0.52),
            axisRadius
        );
        this.placeGuideSegment(
            this.rotationStartLine,
            start.clone().multiplyScalar(inner),
            start.clone().multiplyScalar(radius),
            lineRadius * 0.72
        );
        this.placeGuideSegment(
            this.rotationCurrentLine,
            current.clone().multiplyScalar(inner),
            current.clone().multiplyScalar(radius),
            lineRadius
        );
    }

    updateGuides(camera = null) {
        this.guideRoot.visible = this.mode !== 'IDLE';
        this.guideRoot.position.copy(this.pivot).add(this.visualOffset);
        Object.values(this.axisGuides).forEach(g => g.visible = false);

        const cameraScale = camera ? Math.max(this.pivot.distanceTo(camera.position) * 0.08, 0.85) : 1.0;
        this.pivotMarker.scale.setScalar(Math.max(1, cameraScale * 0.18));

        if (this.axis && this.mode !== 'IDLE' && !(this.mode === 'ROTATE' && this.rotationGuide)) {
            this.axisGuides[this.axis].visible = true;
        }
        this.updateRotationGuideGeometry(cameraScale);
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
        this.scaleFactor = 1;
        this.rotationGuide = null;
        this.guideRoot.visible = false;
        this.rotationGuideGroup.visible = false;
        Object.values(this.axisGuides).forEach(g => g.visible = false);
    }
}
