import * as THREE from 'three';

function numberArrayEqual(first = [], second = []) {
    if (first === second) return true;
    if (first.length !== second.length) return false;
    for (let index = 0; index < first.length; index++) {
        if (Number(first[index]) !== Number(second[index])) return false;
    }
    return true;
}

function stringArrayEqual(first = [], second = []) {
    if (first === second) return true;
    if (first.length !== second.length) return false;
    for (let index = 0; index < first.length; index++) {
        if (String(first[index]) !== String(second[index])) return false;
    }
    return true;
}

function flatPairArrayEqual(first = [], second = []) {
    if (first === second) return true;
    if (first.length !== second.length) return false;
    for (let index = 0; index < first.length; index++) {
        const a = first[index];
        const b = second[index];
        if (!a || !b || a[0] !== b[0] || a[1] !== b[1]) return false;
    }
    return true;
}

function scalarRecordEqual(first = {}, second = {}) {
    if (first === second) return true;
    const firstKeys = Object.keys(first);
    const secondKeys = Object.keys(second);
    if (firstKeys.length !== secondKeys.length) return false;
    for (const key of firstKeys) {
        if (!Object.prototype.hasOwnProperty.call(second, key) || first[key] !== second[key]) {
            return false;
        }
    }
    return true;
}

function recordHasEntries(record = {}) {
    for (const key in record) {
        if (Object.prototype.hasOwnProperty.call(record, key)) return true;
    }
    return false;
}

function cloneBondRangeRecord(source = {}) {
    return Object.fromEntries(Object.entries(source).map(([key, range]) => [
        key,
        range && typeof range === 'object'
            ? {
                enabled: range.enabled !== false,
                min: Number(range.min) || 0,
                max: Number(range.max) || 0
            }
            : range
    ]));
}

function bondRangeRecordEqual(first = {}, second = {}) {
    if (first === second) return true;
    const firstKeys = Object.keys(first);
    const secondKeys = Object.keys(second);
    if (firstKeys.length !== secondKeys.length) return false;
    for (const key of firstKeys) {
        const a = first[key];
        const b = second[key];
        if (
            !b
            || Boolean(a?.enabled !== false) !== Boolean(b?.enabled !== false)
            || Number(a?.min || 0) !== Number(b?.min || 0)
            || Number(a?.max || 0) !== Number(b?.max || 0)
        ) {
            return false;
        }
    }
    return true;
}

function cloneBondStyleRecord(source = {}) {
    return Object.fromEntries(Object.entries(source).flatMap(([key, style]) => (
        style && typeof style === 'object'
            ? [[key, {
                style: style.style === 'flat' ? 'flat' : 'cylinder',
                material: ['standard', 'metal', 'rubber', 'unlit'].includes(style.material)
                    ? style.material
                    : 'standard',
                thickness: Math.max(0.02, Math.min(0.6, Number(style.thickness) || 0.25)),
                colorMode: style.colorMode === 'custom' ? 'custom' : 'split',
                color: typeof style.color === 'string' ? style.color : '#c8ccd0',
                opacity: Math.max(0.05, Math.min(1, Number(style.opacity) || 1))
            }]]
            : []
    )));
}

function bondStyleRecordEqual(first = {}, second = {}) {
    if (first === second) return true;
    const firstKeys = Object.keys(first);
    const secondKeys = Object.keys(second);
    if (firstKeys.length !== secondKeys.length) return false;
    for (const key of firstKeys) {
        const a = first[key];
        const b = second[key];
        if (
            !b
            || a.style !== b.style
            || a.material !== b.material
            || Number(a.thickness) !== Number(b.thickness)
            || a.colorMode !== b.colorMode
            || a.color !== b.color
            || Number(a.opacity) !== Number(b.opacity)
        ) return false;
    }
    return true;
}

function cloneAtomBondStyleRecord(source = {}) {
    return Object.fromEntries(Object.entries(source).flatMap(([key, style]) => {
        if (!style || typeof style !== 'object') return [];
        const next = {};
        if (['standard', 'metal', 'rubber', 'unlit'].includes(style.material)) {
            next.material = style.material;
        }
        const opacity = Number(style.opacity);
        if (Number.isFinite(opacity)) next.opacity = Math.max(0, Math.min(1, opacity));
        if (typeof style.color === 'string' && /^#[0-9A-Fa-f]{6}$/.test(style.color)) {
            next.color = style.color.toLowerCase();
        }
        return Object.keys(next).length ? [[String(key), next]] : [];
    }));
}

function atomBondStyleRecordEqual(first = {}, second = {}) {
    if (first === second) return true;
    const firstKeys = Object.keys(first);
    const secondKeys = Object.keys(second);
    if (firstKeys.length !== secondKeys.length) return false;
    return firstKeys.every(key => {
        const a = first[key] || {};
        const b = second[key];
        return b
            && a.material === b.material
            && Number(a.opacity) === Number(b.opacity)
            && a.color === b.color;
    });
}

class BlenderTumbleControls {
    constructor(camera, domElement) {
        this.camera = camera;
        this.domElement = domElement;
        this.target = new THREE.Vector3();
        this.enabled = true;
        this.enableDamping = false;
        this.dampingFactor = 0;
        this.rotateSpeed = 0.011;
        this.panSpeed = 1.0;
        this.zoomSpeed = 0.0012;
        this.state = 'idle';
        this.activePointerId = null;
        this.activeButton = null;
        this.activeButtonsMask = 0;
        this.windowGestureListenersActive = false;
        this.previousUserSelect = '';
        this.lastPointer = new THREE.Vector2();
        this.lastWheelTime = 0;
        this.wheelSpeedHistory = [];
        this.isCurrentGestureMouse = true;
        this.smoothedWheelDelta = new THREE.Vector2();
        this.trackpadRotateScale = 0.42;
        this.onChange = null;
        this.onGestureStart = null;
        this.onGestureEnd = null;
        this.wheelGestureActive = false;
        this.wheelGestureTimer = null;

        this.onContextMenu = (event) => event.preventDefault();
        this.onAuxClick = (event) => {
            if (event.button === 1) event.preventDefault();
        };
        this.onPointerDown = (event) => this.handlePointerDown(event);
        this.onPointerMove = (event) => this.handlePointerMove(event);
        this.onPointerUp = (event) => this.endGesture(event);
        this.onPointerCancel = (event) => this.endGesture(event, { force: true });
        this.onMouseUp = (event) => this.handleMouseUp(event);
        this.onWheel = (event) => this.handleWheel(event);
        this.onLostPointerCapture = (event) => this.handleLostPointerCapture(event);
        this.onWindowBlur = () => {
            this.endGesture(null, { force: true });
            this.finishWheelGesture();
        };

        domElement.addEventListener('contextmenu', this.onContextMenu);
        domElement.addEventListener('auxclick', this.onAuxClick);
        domElement.addEventListener('pointerdown', this.onPointerDown);
        domElement.addEventListener('pointermove', this.onPointerMove);
        domElement.addEventListener('pointerup', this.onPointerUp);
        domElement.addEventListener('pointercancel', this.onPointerCancel);
        domElement.addEventListener('lostpointercapture', this.onLostPointerCapture);
        domElement.addEventListener('wheel', this.onWheel, { passive: false });
    }

    handlePointerDown(event) {
        if (!this.enabled) return;
        if (event.button === 1) {
            this.startGesture(event, event.shiftKey ? 'pan' : 'rotate');
        } else if (event.button === 2) {
            this.startGesture(event, 'pan');
        }
    }

    startGesture(event, state) {
        if (this.state !== 'idle') this.endGesture(null, { force: true });
        this.finishWheelGesture();
        event.preventDefault();
        this.onGestureStart?.({ source: state });
        this.state = state;
        this.activePointerId = event.pointerId;
        this.activeButton = event.button;
        this.activeButtonsMask = this.buttonsMaskForButton(event.button);
        this.lastPointer.set(event.clientX, event.clientY);
        this.previousUserSelect = document.body.style.userSelect || '';
        document.body.style.userSelect = 'none';
        this.domElement.setPointerCapture?.(event.pointerId);
        this.addWindowGestureListeners();
    }

    buttonsMaskForButton(button) {
        if (button === 0) return 1;
        if (button === 1) return 4;
        if (button === 2) return 2;
        return 0;
    }

    addWindowGestureListeners() {
        if (this.windowGestureListenersActive) return;
        window.addEventListener('pointermove', this.onPointerMove, true);
        window.addEventListener('pointerup', this.onPointerUp, true);
        window.addEventListener('pointercancel', this.onPointerCancel, true);
        window.addEventListener('mouseup', this.onMouseUp, true);
        window.addEventListener('blur', this.onWindowBlur, true);
        this.windowGestureListenersActive = true;
    }

    removeWindowGestureListeners() {
        if (!this.windowGestureListenersActive) return;
        window.removeEventListener('pointermove', this.onPointerMove, true);
        window.removeEventListener('pointerup', this.onPointerUp, true);
        window.removeEventListener('pointercancel', this.onPointerCancel, true);
        window.removeEventListener('mouseup', this.onMouseUp, true);
        window.removeEventListener('blur', this.onWindowBlur, true);
        this.windowGestureListenersActive = false;
    }

    handlePointerMove(event) {
        if (!this.enabled || this.state === 'idle') return;
        if (this.activePointerId !== null && event.pointerId !== this.activePointerId) return;
        if (event.buttons !== undefined && event.buttons !== 0 && this.activeButtonsMask && !(event.buttons & this.activeButtonsMask)) {
            this.endGesture(event, { force: true });
            return;
        }
        event.preventDefault();
        const dx = event.clientX - this.lastPointer.x;
        const dy = event.clientY - this.lastPointer.y;
        this.lastPointer.set(event.clientX, event.clientY);
        if (dx === 0 && dy === 0) return;
        if (this.state === 'rotate') {
            this.rotate(dx, dy);
        } else if (this.state === 'pan') {
            this.pan(dx, dy);
        }
    }

    handleLostPointerCapture(event) {
        if (event?.pointerId !== undefined && this.activePointerId !== null && event.pointerId !== this.activePointerId) {
            return;
        }
        // Chrome/Safari can drop pointer capture during middle-button drags while the
        // physical button is still held. Keep the gesture alive; window listeners
        // continue receiving movement, and pointerup/mouseup will finish it.
        if (this.state !== 'idle') this.addWindowGestureListeners();
    }

    handleMouseUp(event) {
        if (this.state === 'idle') return;
        if (this.activeButton === null || event.button === this.activeButton) {
            this.endGesture(null, { force: true });
        }
    }

    handleWheel(event) {
        if (!this.enabled) return;
        event.preventDefault();
        this.beginWheelGesture();
        this.scheduleWheelGestureEnd();

        // 1. Pinch Zoom (Trackpad pinch always sets ctrlKey = true in Chrome/Safari)
        if (event.ctrlKey) {
            this.doZoom(event.deltaY);
            return;
        }

        const now = performance.now();
        const dt = now - (this.lastWheelTime || 0);

        // 2. Lock gesture type at the start of the scroll sequence to prevent "hybrid" behavior
        if (dt > 150) {
            this.wheelSpeedHistory = [];
            this.smoothedWheelDelta.set(0, 0);

            if (event.deltaMode > 0) {
                this.isCurrentGestureMouse = true;
            } else if (event.deltaX === 0 && Math.abs(event.deltaY) > 2) {
                // Physical mouse wheels strictly have deltaX === 0 and larger step sizes.
                this.isCurrentGestureMouse = true;
            } else {
                // Trackpads usually have non-zero deltaX or start with tiny deltaY (e.g., 0.5, 1.2).
                this.isCurrentGestureMouse = false;
            }
        }
        this.lastWheelTime = now;

        // 3. Execute the locked gesture
        if (this.isCurrentGestureMouse) {
            // Physical Mouse: Scroll = Zoom/Pan
            if (event.shiftKey) {
                this.pan(0, event.deltaY * 0.5);
            } else {
                this.doZoom(event.deltaY);
            }
        } else {
            // Trackpad: 2-finger swipe = Orbit (View Rotation)
            const currentSpeed = Math.sqrt(event.deltaX * event.deltaX + event.deltaY * event.deltaY);
            this.wheelSpeedHistory.push(currentSpeed);
            if (this.wheelSpeedHistory.length > 5) {
                this.wheelSpeedHistory.shift();
            }

            let isMomentumTail = false;
            if (this.wheelSpeedHistory.length === 5) {
                let monotonicDecay = true;
                for (let i = 1; i < 5; i++) {
                    if (this.wheelSpeedHistory[i] > this.wheelSpeedHistory[i - 1] + 0.01) {
                        monotonicDecay = false;
                        break;
                    }
                }
                const strongDecay = this.wheelSpeedHistory[0] > currentSpeed * 1.65;
                isMomentumTail = monotonicDecay && strongDecay && currentSpeed < 3.0;
            }

            if (isMomentumTail) return;

            const alpha = dt > 80 ? 1.0 : 0.62;
            this.smoothedWheelDelta.set(
                event.deltaX * alpha + this.smoothedWheelDelta.x * (1 - alpha),
                event.deltaY * alpha + this.smoothedWheelDelta.y * (1 - alpha)
            );
            this.rotate(
                -this.smoothedWheelDelta.x * this.trackpadRotateScale,
                -this.smoothedWheelDelta.y * this.trackpadRotateScale
            );
        }
    }

    beginWheelGesture() {
        if (this.wheelGestureActive) return;
        this.wheelGestureActive = true;
        this.onGestureStart?.({ source: 'wheel' });
    }

    scheduleWheelGestureEnd() {
        if (this.wheelGestureTimer !== null) clearTimeout(this.wheelGestureTimer);
        this.wheelGestureTimer = setTimeout(() => this.finishWheelGesture(), 180);
    }

    finishWheelGesture() {
        if (this.wheelGestureTimer !== null) {
            clearTimeout(this.wheelGestureTimer);
            this.wheelGestureTimer = null;
        }
        if (!this.wheelGestureActive) return;
        this.wheelGestureActive = false;
        this.onGestureEnd?.({ source: 'wheel' });
    }

    doZoom(deltaY) {
        const factor = Math.exp(deltaY * this.zoomSpeed);
        if (this.camera.isOrthographicCamera) {
            this.camera.zoom = Math.max(1e-4, Math.min(1e5, this.camera.zoom / factor));
            this.camera.updateProjectionMatrix();
            this.onChange?.();
            return;
        }
        const offset = new THREE.Vector3().subVectors(this.camera.position, this.target);
        offset.multiplyScalar(Math.min(8, Math.max(0.125, factor)));
        this.camera.position.copy(this.target).add(offset);
        this.camera.lookAt(this.target);
        this.onChange?.();
    }

    rotate(dx, dy) {
        const offset = new THREE.Vector3().subVectors(this.camera.position, this.target);
        if (offset.lengthSq() < 1e-12) return;
        this.camera.updateMatrixWorld();
        const localRight = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0).normalize();
        const localUp = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1).normalize();
        const yaw = new THREE.Quaternion().setFromAxisAngle(localUp, -dx * this.rotateSpeed);
        const pitch = new THREE.Quaternion().setFromAxisAngle(localRight, -dy * this.rotateSpeed);
        const rotation = new THREE.Quaternion().multiplyQuaternions(yaw, pitch);
        offset.applyQuaternion(rotation);
        this.camera.up.applyQuaternion(rotation).normalize();
        this.camera.position.copy(this.target).add(offset);
        this.camera.lookAt(this.target);
        this.onChange?.();
    }

    pan(dx, dy) {
        const offset = new THREE.Vector3().subVectors(this.camera.position, this.target);
        const distance = Math.max(offset.length(), 1);
        const worldPerPixel = this.camera.isOrthographicCamera
            ? (this.camera.top - this.camera.bottom) / Math.max(1, this.domElement.clientHeight * (this.camera.zoom || 1))
            : (2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) * distance) / Math.max(1, this.domElement.clientHeight);
        this.camera.updateMatrixWorld();
        const localRight = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0).normalize();
        const localUp = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1).normalize();
        const delta = new THREE.Vector3()
            .addScaledVector(localRight, -dx * worldPerPixel * this.panSpeed)
            .addScaledVector(localUp, dy * worldPerPixel * this.panSpeed);
        this.camera.position.add(delta);
        this.target.add(delta);
        this.camera.lookAt(this.target);
        this.onChange?.();
    }

    endGesture(event = null, { force = false } = {}) {
        if (!force && event?.pointerId !== undefined && this.activePointerId !== null && event.pointerId !== this.activePointerId) {
            return;
        }
        const completedState = this.state;
        if (this.activePointerId !== null && this.domElement.hasPointerCapture?.(this.activePointerId)) {
            this.domElement.releasePointerCapture(this.activePointerId);
        }
        this.removeWindowGestureListeners();
        document.body.style.userSelect = this.previousUserSelect;
        this.state = 'idle';
        this.activePointerId = null;
        this.activeButton = null;
        this.activeButtonsMask = 0;
        if (completedState !== 'idle') this.onGestureEnd?.({ source: completedState });
    }

    update() {
        return false;
    }

    dispose() {
        this.enabled = false;
        this.endGesture(null, { force: true });
        this.finishWheelGesture();
        this.removeWindowGestureListeners();
        const element = this.domElement;
        element.removeEventListener('contextmenu', this.onContextMenu);
        element.removeEventListener('auxclick', this.onAuxClick);
        element.removeEventListener('pointerdown', this.onPointerDown);
        element.removeEventListener('pointermove', this.onPointerMove);
        element.removeEventListener('pointerup', this.onPointerUp);
        element.removeEventListener('pointercancel', this.onPointerCancel);
        element.removeEventListener('lostpointercapture', this.onLostPointerCapture);
        element.removeEventListener('wheel', this.onWheel);
        this.onChange = null;
        this.onGestureStart = null;
        this.onGestureEnd = null;
    }
}

const FALLBACK_ATOM_COLOR = '#cccccc';
const FALLBACK_ATOM_RADIUS = 0.7;
const FALLBACK_COVALENT_RADIUS = 0.75;
// ASE supplies Cordero et al. covalent radii. Pair-class slack keeps the
// automatic view conservative for H and metal-metal contacts while retaining
// practical coordination distances for metal-ligand bonds.
const AUTO_BOND_HYDROGEN_SLACK = 0.22;
const AUTO_BOND_COVALENT_SLACK = 0.35;
const AUTO_BOND_METAL_LIGAND_SLACK = 0.50;
const AUTO_BOND_CLASS_COVALENT = 0;
const AUTO_BOND_CLASS_HYDROGEN = 1;
const AUTO_BOND_CLASS_METAL = 2;
const METALLIC_ELEMENT_SYMBOLS = new Set([
    'Li', 'Be', 'Na', 'Mg', 'Al', 'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn',
    'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo',
    'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn', 'Cs', 'Ba', 'La', 'Ce',
    'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
    'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb',
    'Bi', 'Po', 'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm',
    'Bk', 'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs',
    'Mt', 'Ds', 'Rg', 'Cn', 'Nh', 'Fl', 'Mc', 'Lv'
]);
const ATOM_MATERIAL_PRESETS = Object.freeze({
    standard: Object.freeze({
        roughness: 0.24,
        metalness: 0.0,
        clearcoat: 0.08,
        clearcoatRoughness: 0.18,
        specularIntensity: 1.0,
        envMapIntensity: 0.0
    }),
    metal: Object.freeze({
        roughness: 0.18,
        metalness: 0.90,
        clearcoat: 0.12,
        clearcoatRoughness: 0.16,
        specularIntensity: 1.0,
        envMapIntensity: 2.15
    }),
    rubber: Object.freeze({
        roughness: 0.88,
        metalness: 0.0,
        clearcoat: 0.0,
        clearcoatRoughness: 0.8,
        specularIntensity: 0.16,
        envMapIntensity: 0.0
    })
});

function cssColor(property, fallback) {
    if (typeof document === 'undefined') return fallback;
    const value = getComputedStyle(document.documentElement).getPropertyValue(property).trim();
    return value || fallback;
}

export class ASERenderer {
    constructor(container) {
        this.container = container;
        this.renderRequestId = null;
        this.exportCaptureActive = false;
        this.suspended = false;
        this.renderCount = 0;
        this.setupScene();
        this.setLightingOptions(this.lightingOptions);
        this.requestRender();
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.viewportBackgroundMode = 'white';
        const viewportBackground = cssColor('--viewport-light-bg', '#ffffff');
        this.scene.background = new THREE.Color(viewportBackground);
        
        const aspect = window.innerWidth / Math.max(1, window.innerHeight);
        this.perspectiveCamera = new THREE.PerspectiveCamera(50, aspect, 0.1, 10000);
        this.orthographicCamera = new THREE.OrthographicCamera(-10 * aspect, 10 * aspect, 10, -10, 0.1, 10000);
        [this.perspectiveCamera, this.orthographicCamera].forEach(camera => {
            camera.up.set(0, 0, 1);
            camera.position.set(10, 10, 10);
        });
        this.camera = this.orthographicCamera;
        this.projectionMode = 'orthographic';

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: false });
        this.renderer.setClearColor(viewportBackground, 1);
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.shadowMap.enabled = false;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.metalEnvironmentMap = null;
        this.metalEnvironmentRenderTarget = null;
        this.domElement = this.renderer.domElement;
        this.domElement.dataset.viewportBackground = this.viewportBackgroundMode;
        this.container.appendChild(this.renderer.domElement);
        this.exportPreviewFrame = document.getElementById('export-preview-frame');
        this.exportPreviewDimensions = document.getElementById('export-preview-dimensions');
        this.exportPreview = {
            enabled: false,
            width: 1920,
            height: 1080,
            options: {}
        };
        this.previewRenderCount = 0;
        this.lastExportPreview = null;
        this.exportPreviewCamera = null;
        this.exportPreviewTarget = null;

        this.controls = new BlenderTumbleControls(this.camera, this.renderer.domElement);
        this.controls.onChange = () => {
            this.onCameraChange?.({ source: 'controls' });
            this.requestRender();
        };

        this.modelingLightGroup = new THREE.Group();
        this.modelingLightGroup.name = 'v_ase_modeling_lights';
        this.scene.add(this.modelingLightGroup);

        // Keep the key light camera-facing so every crystallographic view has
        // the same readable sphere contour. Low world-space fills retain depth
        // without allowing one viewing direction to become dark.
        const hemiLight = new THREE.HemisphereLight(0xffffff, 0xd6dcda, 0.38);
        this.modelingLightGroup.add(hemiLight);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.30);
        this.modelingLightGroup.add(ambientLight);
        
        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.22);
        dirLight1.position.set(10, 20, 10);
        this.modelingLightGroup.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.14);
        dirLight2.position.set(-10, -20, 10);
        this.modelingLightGroup.add(dirLight2);

        const dirLight3 = new THREE.DirectionalLight(0xffffff, 0.12);
        dirLight3.position.set(12, -14, 8);
        this.modelingLightGroup.add(dirLight3);

        const dirLight4 = new THREE.DirectionalLight(0xffffff, 0.10);
        dirLight4.position.set(-12, 14, -8);
        this.modelingLightGroup.add(dirLight4);

        this.cameraFillLight = new THREE.PointLight(0xffffff, 0.16, 0, 1.35);
        this.modelingLightGroup.add(this.cameraFillLight);
        this.cameraFillTarget = new THREE.Object3D();
        this.modelingLightGroup.add(this.cameraFillTarget);
        this.cameraFillDirectionalLight = new THREE.DirectionalLight(0xffffff, 0.88);
        this.cameraFillDirectionalLight.target = this.cameraFillTarget;
        this.modelingLightGroup.add(this.cameraFillDirectionalLight);

        this.studioLightGroup = new THREE.Group();
        this.studioLightGroup.name = 'v_ase_studio_sun_lights';
        this.studioLightGroup.visible = false;
        this.scene.add(this.studioLightGroup);
        this.studioAmbientLight = new THREE.AmbientLight(0xffffff, 0.24);
        this.studioHemisphereLight = new THREE.HemisphereLight(0xf8fbff, 0x27323b, 0.44);
        this.studioSunTarget = new THREE.Object3D();
        this.studioSunLight = new THREE.DirectionalLight(0xfff5df, 2.2);
        this.studioSunLight.name = 'v_ase_studio_sun';
        this.studioSunLight.target = this.studioSunTarget;
        this.studioSunLight.position.set(8, -10, 14);
        this.studioSunLight.shadow.mapSize.set(2048, 2048);
        this.studioSunLight.shadow.bias = -0.00035;
        this.studioSunLight.shadow.normalBias = 0.025;
        this.studioLightGroup.add(this.studioAmbientLight);
        this.studioLightGroup.add(this.studioHemisphereLight);
        this.studioLightGroup.add(this.studioSunTarget);
        this.studioLightGroup.add(this.studioSunLight);

        this.sunGizmoGroup = this.buildSunGizmo();
        this.scene.add(this.sunGizmoGroup);
        this.sunRaycaster = new THREE.Raycaster();
        this.sunGizmoSelected = null;
        this.sunShadowBoundsCache = null;
        this.onLightingChange = null;

        this.renderAreaGizmoGroup = this.buildRenderAreaGizmo();
        this.scene.add(this.renderAreaGizmoGroup);
        this.renderAreaRaycaster = new THREE.Raycaster();

        this.viewportGuides = this.buildViewportGuides();
        this.gridGroup = this.viewportGuides.gridGroup;
        this.axesHelper = this.viewportGuides.axisGroup;
        this.scene.add(this.gridGroup);
        this.scene.add(this.axesHelper);

        this.atomMeshes = new THREE.Group();
        this.scene.add(this.atomMeshes);

        this.selectionOutlines = new THREE.Group();
        this.scene.add(this.selectionOutlines);
        this.replicaSelectionOutlines = new THREE.Group();
        this.scene.add(this.replicaSelectionOutlines);

        this.cellGroup = new THREE.Group();
        this.scene.add(this.cellGroup);
        this.addAtomsRegionGroup = new THREE.Group();
        this.addAtomsRegionConfiguration = null;
        this.addAtomsRegionGroup.name = 'v_ase_add_atoms_region';
        this.scene.add(this.addAtomsRegionGroup);
        this.bondGroup = new THREE.Group();
        this.scene.add(this.bondGroup);
        this.displacementGroup = new THREE.Group();
        this.displacementGroup.name = 'v_ase_displacement_vectors';
        this.scene.add(this.displacementGroup);
        this.forceVectorGroup = new THREE.Group();
        this.forceVectorGroup.name = 'v_ase_force_vectors';
        this.scene.add(this.forceVectorGroup);
        this.volumetricGroup = new THREE.Group();
        this.volumetricGroup.name = 'v_ase_volumetric_isosurfaces';
        this.scene.add(this.volumetricGroup);
        this.volumetricSurfaces = [];
        this.volumetricPlaneGroup = new THREE.Group();
        this.volumetricPlaneGroup.name = 'v_ase_volumetric_planes';
        this.scene.add(this.volumetricPlaneGroup);
        this.volumetricPlanes = new Map();
        this.commensurateGuideGroup = new THREE.Group();
        this.scene.add(this.commensurateGuideGroup);
        this.commensurateGuideSignature = null;
        this.commensurateSupercellGroup = new THREE.Group();
        this.commensurateSupercellGroup.name = 'v_ase_commensurate_supercell_preview';
        this.scene.add(this.commensurateSupercellGroup);
        this.commensurateSupercellPreview = null;
        this.commensurateBaseVisibility = null;
        this.commensurateCameraSnapshot = null;
        this.supercellGroup = new THREE.Group();
        this.scene.add(this.supercellGroup);
        this.constraintMarkGroup = new THREE.Group();
        this.scene.add(this.constraintMarkGroup);
        this.constraintGuideGroup = new THREE.Group();
        this.scene.add(this.constraintGuideGroup);
        this.constraintMotionGuideGroup = new THREE.Group();
        this.constraintMotionGuideGroup.name = 'v_ase_constraint_motion_guides';
        this.scene.add(this.constraintMotionGuideGroup);
        this.hookeanGroup = new THREE.Group();
        this.scene.add(this.hookeanGroup);
        this.atomMeshByIndex = new Map();
        this.atomInstanceRefs = new Map();
        this.atomInstanceRefsByIndex = [];
        this.atomInstanceMeshes = new Set();
        this.atomIndicesByLabel = new Map();
        this.useInstancedAtoms = false;
        this.instanceDummy = new THREE.Object3D();
        this.atomColorScratch = new THREE.Color();
        this.bondInstanceDummy = new THREE.Object3D();
        this.bondDeltaScratch = new THREE.Vector3();
        this.yAxis = new THREE.Vector3(0, 1, 0);
        this.geometryCache = new Map();
        this.materialCache = new Map();
        this.atomsData = null;
        this.cellCache = null;
        this.bondNeighborCache = null;
        this.needsInitialCameraFit = true;
        this.customColors = {};
        this.atomColorScaleColors = null;
        this.displayOptions = {
            showCell: true,
            showAxes: true,
            showGrid: true,
            showBonds: true,
            showPeriodicBonds: false,
            cellThickness: 0.04,
            cellColor: '#d6bd67',
            cellMaterial: 'unlit',
            bondMode: 'auto',
            bondCutoffScale: 1.0,
            manualBondPairs: [],
            pairwiseBondCutoffs: {},
            pairwiseBondRanges: {},
            bondStyle: 'cylinder',
            bondMaterial: 'standard',
            bondThickness: 0.25,
            bondColorMode: 'split',
            bondCustomColor: '#c8ccd0',
            bondOpacity: 1,
            pairwiseBondStyles: {},
            atomRadiusScale: 0.6,
            labelRadii: {},
            labelColors: {},
            labelOpacities: {},
            labelVisible: {},
            labelMaterials: {},
            atomRadiusScales: {},
            atomColors: {},
            atomOpacities: {},
            atomMaterials: {},
            atomBondStyles: {},
            hiddenAtomReferences: [],
            rotatePivot: 'selection',
            commensurateGuide: false,
            commensurateSnap: false,
            commensurateStrainTolerance: 0.01,
            commensurateMaxIndex: 32,
            commensurateMaxAreaRatio: 16,
            commensurateSnapRangeDeg: 2.0,
            projectionMode: 'orthographic',
            viewportBackground: 'white',
            atomDisplayMode: '3d',
            viewRotationStepDeg: 15,
            showOverlays: true,
            supercell: [1, 1, 1],
            translation: [0, 0, 0],
            translationMode: 'cartesian',
            antiAliasing: true,
            sphereQuality: 'auto',
            imageFramingMode: 'viewport',
            atomicScalePixelsPerAngstrom: null,
            imageSphereQuality: 'viewport',
            imageSmoothnessScale: 1,
            vizOnly: false,
            lightingMode: 'modeling',
            sunIntensity: 2.2,
            sunPosition: [8, -10, 14],
            sunTarget: [0, 0, 0],
            sunGizmo: false,
            showDisplacements: false,
            displacementReferenceMode: 'previous',
            displacementReferenceFrame: 0,
            displacementMic: true,
            displacementStyle: '3d',
            displacementScale: 1,
            displacementThickness: 0.08,
            displacementColor: '#e58b2a',
            showForceVectors: false,
            forceVectorStyle: '3d',
            forceVectorScale: 1,
            forceVectorThickness: 0.08,
            forceVectorColor: '#c43f5e'
        };
        this.lightingOptions = {
            lightingMode: 'modeling',
            sunIntensity: 2.2,
            sunPosition: [8, -10, 14],
            sunTarget: [0, 0, 0],
            sunGizmo: false
        };
        this.shadowModeActive = false;
        this.bondPairs = [];
        this.supercellBridgeBondRecords = [];
        this.cellEdgeGeometry = new THREE.CylinderGeometry(1, 1, 1, 10, 1, false);
        this.cellEdgeDummy = new THREE.Object3D();
        this.cellEdgeCameraSignature = '';
        this.bondCylinderGeometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 16);
        this.bondFlatGeometry = new THREE.PlaneGeometry(1, 1);
        this.displacementConeGeometry = new THREE.ConeGeometry(0.5, 1, 12);
        this.displacementFlatHeadGeometry = new THREE.BufferGeometry();
        this.displacementFlatHeadGeometry.setAttribute(
            'position',
            new THREE.Float32BufferAttribute([
                -0.5, -0.5, 0,
                0.5, -0.5, 0,
                0, 0.5, 0
            ], 3)
        );
        this.displacementFlatHeadGeometry.computeVertexNormals();
        this.displacementData = null;
        this.displacementCameraSignature = '';
        this.forceVectorData = null;
        this.forceVectorCameraSignature = '';
        this.displacementDummy = new THREE.Object3D();
        this.displacementDirection = new THREE.Vector3();
        this.displacementStart = new THREE.Vector3();
        this.displacementEnd = new THREE.Vector3();
        this.bondFlatBasis = new THREE.Matrix4();
        this.bondFlatX = new THREE.Vector3();
        this.bondFlatY = new THREE.Vector3();
        this.bondFlatZ = new THREE.Vector3();
        this.selectionOutlineGeometry = new THREE.SphereGeometry(1, 18, 12);
        this.selectionOutlineMaterial = new THREE.MeshBasicMaterial({
            color: 0xffc400,
            side: THREE.BackSide,
            transparent: true,
            opacity: 1.0,
            depthWrite: false
        });
        this.replicaSelectionMutedMaterial = new THREE.MeshBasicMaterial({
            color: 0xffc400,
            side: THREE.BackSide,
            transparent: true,
            opacity: 0.36,
            depthWrite: false
        });
        this.constraintMaterials = {
            line: new THREE.MeshBasicMaterial({
                color: 0x239fb8,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.86,
                depthTest: true,
                depthWrite: false
            }),
            lineFade: new THREE.MeshBasicMaterial({
                color: 0x239fb8,
                transparent: true,
                opacity: 0.16,
                depthTest: true,
                depthWrite: false
            }),
            lineMotion: new THREE.MeshBasicMaterial({
                color: 0x178b9f,
                transparent: true,
                opacity: 0.9,
                depthTest: false,
                depthWrite: false
            }),
            plane: new THREE.MeshBasicMaterial({
                color: 0x3dd6b0,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.18,
                depthTest: true,
                depthWrite: false
            }),
            planeSoft: new THREE.ShaderMaterial({
                transparent: true,
                side: THREE.DoubleSide,
                depthTest: true,
                depthWrite: false,
                uniforms: {
                    color: { value: new THREE.Color(0x3dd6b0) },
                    opacity: { value: 0.14 }
                },
                vertexShader: `
                    varying vec2 vUv;
                    void main() {
                        vUv = uv;
                        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    }
                `,
                fragmentShader: `
                    uniform vec3 color;
                    uniform float opacity;
                    varying vec2 vUv;
                    void main() {
                        vec2 centered = abs(vUv - vec2(0.5)) * 2.0;
                        float edge = max(centered.x, centered.y);
                        float alpha = opacity * (1.0 - smoothstep(0.58, 1.0, edge));
                        gl_FragColor = vec4(color, alpha);
                    }
                `
            }),
            planeAggregate: new THREE.ShaderMaterial({
                transparent: true,
                side: THREE.DoubleSide,
                depthTest: true,
                depthWrite: false,
                uniforms: {
                    color: { value: new THREE.Color(0x3dd6b0) },
                    opacity: { value: 0.055 }
                },
                vertexShader: `
                    varying vec2 vUv;
                    void main() {
                        vUv = uv;
                        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    }
                `,
                fragmentShader: `
                    uniform vec3 color;
                    uniform float opacity;
                    varying vec2 vUv;
                    void main() {
                        vec2 centered = abs(vUv - vec2(0.5)) * 2.0;
                        float edge = max(centered.x, centered.y);
                        float interior = 1.0 - smoothstep(0.42, 0.94, edge);
                        vec2 grid = abs(fract(vUv * 8.0) - 0.5);
                        float sparseGrid = max(
                            smoothstep(0.465, 0.500, grid.x),
                            smoothstep(0.465, 0.500, grid.y)
                        );
                        float alpha = opacity * interior + opacity * 0.42 * sparseGrid * (1.0 - smoothstep(0.72, 1.0, edge));
                        gl_FragColor = vec4(color, alpha);
                    }
                `
            }),
            planePerimeter: new THREE.MeshBasicMaterial({
                color: 0x66f2d5,
                transparent: true,
                opacity: 0.58,
                depthTest: true,
                depthWrite: false
            }),
            planeCrosshair: new THREE.MeshBasicMaterial({
                color: 0xd7fff5,
                transparent: true,
                opacity: 0.62,
                depthTest: true,
                depthWrite: false
            }),
            planeNormal: new THREE.MeshBasicMaterial({
                color: 0xffc857,
                transparent: true,
                opacity: 0.92,
                depthTest: true,
                depthWrite: false
            }),
            planeMotion: new THREE.ShaderMaterial({
                transparent: true,
                side: THREE.DoubleSide,
                depthTest: false,
                depthWrite: false,
                uniforms: {
                    color: { value: new THREE.Color(0x2ab89f) },
                    opacity: { value: 0.18 }
                },
                vertexShader: `
                    varying vec2 vUv;
                    void main() {
                        vUv = uv;
                        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                    }
                `,
                fragmentShader: `
                    uniform vec3 color;
                    uniform float opacity;
                    varying vec2 vUv;
                    void main() {
                        float edge = max(
                            abs((vUv.x - 0.5) * 2.0),
                            abs((vUv.y - 0.5) * 2.0)
                        );
                        float interior = 1.0 - smoothstep(0.72, 1.0, edge);
                        vec2 grid = abs(fract((vUv - vec2(0.5)) * 10.0) - 0.5);
                        float gridLine = max(
                            smoothstep(0.455, 0.500, grid.x),
                            smoothstep(0.455, 0.500, grid.y)
                        );
                        float alpha = opacity * interior
                            + opacity * 0.34 * gridLine * (1.0 - smoothstep(0.70, 1.0, edge));
                        if (alpha < 0.002) discard;
                        gl_FragColor = vec4(color, alpha);
                    }
                `
            }),
            planeMotionPerimeter: new THREE.LineBasicMaterial({
                color: 0x20a58e,
                transparent: true,
                opacity: 1.0,
                depthTest: false,
                depthWrite: false
            }),
            planeMotionAxis: new THREE.MeshBasicMaterial({
                color: 0x178b79,
                transparent: true,
                opacity: 0.88,
                depthTest: false,
                depthWrite: false
            }),
            hookean: new THREE.MeshStandardMaterial({
                color: 0xff9f43,
                roughness: 0.28,
                metalness: 0.16,
                transparent: true,
                opacity: 0.92,
                depthTest: true,
                depthWrite: false
            }),
            hookeanFlat: new THREE.MeshBasicMaterial({
                color: 0xff9f43,
                transparent: true,
                opacity: 0.92,
                depthTest: true,
                depthWrite: false,
                toneMapped: false
            }),
            hookeanInactive: new THREE.MeshBasicMaterial({
                color: 0x8fb7ff,
                transparent: true,
                opacity: 0.48,
                depthWrite: false
            }),
            hookeanGuide: new THREE.MeshBasicMaterial({
                color: 0xaec1d8,
                transparent: true,
                opacity: 0.42,
                depthWrite: false
            }),
            hookeanHook: new THREE.MeshBasicMaterial({
                color: 0x7bb7ff,
                transparent: true,
                opacity: 0.86,
                depthWrite: false
            }),
            hookeanSlack: new THREE.MeshBasicMaterial({
                color: 0xb8c3d8,
                transparent: true,
                opacity: 0.38,
                depthWrite: false
            }),
            hookeanRing: new THREE.MeshBasicMaterial({
                color: 0xffc266,
                transparent: true,
                opacity: 0.86,
                side: THREE.DoubleSide,
                depthWrite: false
            }),
            hookeanActiveMarker: new THREE.MeshBasicMaterial({
                color: 0x38d996,
                transparent: true,
                opacity: 0.92,
                depthWrite: false
            }),
            hookeanInactiveMarker: new THREE.MeshBasicMaterial({
                color: 0x75a9ff,
                transparent: true,
                opacity: 0.78,
                depthWrite: false
            }),
            hookeanThresholdMarker: new THREE.MeshBasicMaterial({
                color: 0xffd15a,
                transparent: true,
                opacity: 0.9,
                depthWrite: false
            })
        };
    }

    buildSunGizmo() {
        const group = new THREE.Group();
        group.name = 'v_ase_sun_gizmo';
        group.visible = false;
        group.renderOrder = 90;

        const sunMaterial = new THREE.MeshBasicMaterial({
            color: 0xffc857,
            transparent: true,
            opacity: 0.96,
            depthTest: false,
            depthWrite: false
        });
        const targetMaterial = new THREE.MeshBasicMaterial({
            color: 0x58d5bd,
            transparent: true,
            opacity: 0.96,
            depthTest: false,
            depthWrite: false
        });
        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0xf7e5b3,
            transparent: true,
            opacity: 0.56,
            depthTest: false,
            depthWrite: false
        });
        const sourceSelectionMaterial = new THREE.MeshBasicMaterial({
            color: 0xffc857,
            transparent: true,
            opacity: 0.92,
            depthTest: false,
            depthWrite: false
        });
        const targetSelectionMaterial = new THREE.MeshBasicMaterial({
            color: 0x58d5bd,
            transparent: true,
            opacity: 0.92,
            wireframe: true,
            depthTest: false,
            depthWrite: false
        });

        const positionHandle = new THREE.Group();
        positionHandle.name = 'v_ase_sun_position_handle';
        const sunCore = new THREE.Mesh(new THREE.SphereGeometry(0.22, 18, 12), sunMaterial);
        const sunRing = new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.035, 8, 28), sunMaterial);
        const sourceSelectionRing = new THREE.Mesh(
            new THREE.TorusGeometry(0.46, 0.025, 8, 36),
            sourceSelectionMaterial
        );
        sourceSelectionRing.visible = false;
        sourceSelectionRing.renderOrder = 92;
        sunCore.userData.sunHandle = 'source';
        sunRing.userData.sunHandle = 'source';
        positionHandle.add(sunCore, sunRing, sourceSelectionRing);

        const targetHandle = new THREE.Group();
        targetHandle.name = 'v_ase_sun_target_handle';
        const targetCore = new THREE.Mesh(new THREE.OctahedronGeometry(0.22, 0), targetMaterial);
        targetCore.userData.sunHandle = 'target';
        const targetSelectionShell = new THREE.Mesh(
            new THREE.OctahedronGeometry(0.33, 0),
            targetSelectionMaterial
        );
        targetSelectionShell.visible = false;
        targetSelectionShell.renderOrder = 92;
        targetHandle.add(targetCore, targetSelectionShell);

        const lineGeometry = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(8, -10, 14),
            new THREE.Vector3(0, 0, 0)
        ]);
        const directionLine = new THREE.Line(lineGeometry, lineMaterial);
        directionLine.name = 'v_ase_sun_direction';
        directionLine.renderOrder = 89;

        group.add(directionLine);
        group.add(positionHandle);
        group.add(targetHandle);
        group.userData = {
            positionHandle,
            targetHandle,
            directionLine,
            sourceSelectionRing,
            targetSelectionShell,
            pickables: [sunCore, sunRing, targetCore]
        };
        return group;
    }

    buildRenderAreaGizmo() {
        const group = new THREE.Group();
        group.name = 'v_ase_render_area_eye';
        group.visible = false;
        group.renderOrder = 140;

        const canvas = document.createElement('canvas');
        canvas.width = 160;
        canvas.height = 112;
        const context = canvas.getContext('2d');
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.lineWidth = 8;
        context.lineCap = 'round';
        context.lineJoin = 'round';
        context.strokeStyle = '#69dfc7';
        context.fillStyle = 'rgba(17, 31, 31, 0.82)';
        context.beginPath();
        context.moveTo(12, 56);
        context.bezierCurveTo(44, 10, 116, 10, 148, 56);
        context.bezierCurveTo(116, 102, 44, 102, 12, 56);
        context.closePath();
        context.fill();
        context.stroke();
        context.beginPath();
        context.arc(80, 56, 22, 0, Math.PI * 2);
        context.fillStyle = '#69dfc7';
        context.fill();
        context.beginPath();
        context.arc(80, 56, 9, 0, Math.PI * 2);
        context.fillStyle = '#10201f';
        context.fill();
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.needsUpdate = true;
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false,
            sizeAttenuation: true
        });
        const eye = new THREE.Sprite(material);
        eye.name = 'v_ase_render_area_eye_handle';
        eye.userData.renderAreaEye = true;
        eye.renderOrder = 142;

        const directionMaterial = new THREE.LineDashedMaterial({
            color: 0x69dfc7,
            transparent: true,
            opacity: 0.54,
            dashSize: 0.22,
            gapSize: 0.16,
            depthTest: false,
            depthWrite: false
        });
        const direction = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(10, 10, 10),
                new THREE.Vector3(0, 0, 0)
            ]),
            directionMaterial
        );
        direction.name = 'v_ase_render_area_direction';
        direction.renderOrder = 139;
        direction.computeLineDistances();
        group.add(direction, eye);
        group.userData = { eye, direction };
        return group;
    }

    setRenderAreaGizmo(cameraSettings, { visible = false, selected = false } = {}) {
        const group = this.renderAreaGizmoGroup;
        if (!group) return;
        group.visible = Boolean(visible && cameraSettings);
        if (!group.visible) {
            this.requestRender();
            return;
        }
        const position = new THREE.Vector3(...cameraSettings.position);
        const target = new THREE.Vector3(...cameraSettings.target);
        const { eye, direction } = group.userData;
        eye.position.copy(position);
        eye.material.color.set(selected ? 0xffc857 : 0xffffff);
        const attribute = direction.geometry.getAttribute('position');
        attribute.setXYZ(0, position.x, position.y, position.z);
        attribute.setXYZ(1, target.x, target.y, target.z);
        attribute.needsUpdate = true;
        direction.geometry.computeBoundingSphere();
        direction.computeLineDistances();
        direction.material.color.set(selected ? 0xffc857 : 0x69dfc7);
        this.updateRenderAreaGizmoScale();
        this.requestRender();
    }

    updateRenderAreaGizmoScale() {
        if (!this.renderAreaGizmoGroup?.visible) return;
        const eye = this.renderAreaGizmoGroup.userData.eye;
        const scale = Math.max(0.42, this.sunWorldPerPixel(eye.position) * 64);
        eye.scale.set(scale * 1.42, scale, 1);
    }

    pickRenderAreaEye(event) {
        if (!this.renderAreaGizmoGroup?.visible || !event) return false;
        const rect = this.domElement.getBoundingClientRect();
        const pointer = new THREE.Vector2(
            ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
            -((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1
        );
        this.renderAreaRaycaster.setFromCamera(pointer, this.camera);
        return this.renderAreaRaycaster.intersectObject(
            this.renderAreaGizmoGroup.userData.eye,
            false
        ).length > 0;
    }

    normalizedLightingVector(value, fallback) {
        if (!Array.isArray(value) || value.length < 3) return [...fallback];
        return value.slice(0, 3).map((component, index) => {
            const parsed = Number(component);
            return Number.isFinite(parsed) ? parsed : fallback[index];
        });
    }

    visualTranslationVector(options = this.displayOptions) {
        const raw = Array.isArray(options?.translation)
            ? options.translation.slice(0, 3)
            : [0, 0, 0];
        const vector = new THREE.Vector3(
            Number(raw[0]) || 0,
            Number(raw[1]) || 0,
            Number(raw[2]) || 0
        );
        if (options?.translationMode !== 'fractional') return vector;
        if (!this.hasValidCell()) return new THREE.Vector3();
        return this.fracToCart(vector);
    }

    toVisualAtomPosition(position, options = this.displayOptions) {
        const vector = position?.isVector3
            ? position.clone()
            : new THREE.Vector3(...(Array.isArray(position) ? position : [0, 0, 0]));
        return vector.add(this.visualTranslationVector(options));
    }

    applyVisualTranslation() {
        const translation = this.visualTranslationVector();
        [
            this.atomMeshes,
            this.selectionOutlines,
            this.replicaSelectionOutlines,
            this.bondGroup,
            this.displacementGroup,
            this.forceVectorGroup,
            this.volumetricGroup,
            this.volumetricPlaneGroup,
            this.commensurateGuideGroup,
            this.commensurateSupercellGroup,
            this.constraintMarkGroup,
            this.constraintGuideGroup,
            this.constraintMotionGuideGroup,
            this.hookeanGroup,
            this.addAtomsRegionGroup
        ].forEach(group => {
            if (group) group.position.copy(translation);
        });
        if (this.supercellGroup) {
            this.supercellGroup.position.set(0, 0, 0);
            this.supercellGroup.children.forEach(child => {
                if (child.userData?.supercellCellPreview) child.position.set(0, 0, 0);
                else child.position.copy(translation);
            });
        }
        this.domElement.dataset.visualTranslation = [
            translation.x,
            translation.y,
            translation.z
        ].map(value => value.toFixed(6)).join(',');
        this.invalidateSunShadowBounds();
        this.refreshStudioSunForStructure({ invalidate: false });
        this.requestRender();
    }

    setLightingOptions(options = {}, { requestRender = true } = {}) {
        const previousMode = this.lightingOptions?.lightingMode || 'modeling';
        const mode = ['studio', 'studio-shadow'].includes(options.lightingMode)
            ? options.lightingMode
            : 'modeling';
        const flatDisplay = this.atomDisplayMode() === '2d';
        const intensity = Math.max(0, Number(options.sunIntensity ?? this.lightingOptions?.sunIntensity ?? 2.2));
        const position = this.normalizedLightingVector(
            options.sunPosition || this.lightingOptions?.sunPosition,
            [8, -10, 14]
        );
        const target = this.normalizedLightingVector(
            options.sunTarget || this.lightingOptions?.sunTarget,
            [0, 0, 0]
        );
        const sunGizmo = Boolean(options.sunGizmo ?? this.lightingOptions?.sunGizmo);
        this.lightingOptions = {
            lightingMode: mode,
            sunIntensity: Number.isFinite(intensity) ? intensity : 2.2,
            sunPosition: position,
            sunTarget: target,
            sunGizmo
        };
        Object.assign(this.displayOptions, this.lightingOptions);

        const studio = !flatDisplay && mode !== 'modeling';
        this.modelingLightGroup.visible = !flatDisplay && !studio;
        this.studioLightGroup.visible = studio;
        this.studioSunLight.intensity = this.lightingOptions.sunIntensity;
        this.applyStudioSunDirection();
        this.sunGizmoGroup.visible = studio && sunGizmo;
        if (!this.sunGizmoGroup.visible) this.setSunGizmoSelected(false, { requestRender });
        this.renderer.toneMapping = studio ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
        this.renderer.toneMappingExposure = studio ? 1.05 : 1.0;
        this.domElement.dataset.lightingMode = flatDisplay ? 'flat' : mode;
        this.domElement.dataset.shadowMode = !flatDisplay && mode === 'studio-shadow' ? 'true' : 'false';
        this.setShadowMode(!flatDisplay && mode === 'studio-shadow');
        this.syncSunGizmo();
        if (!flatDisplay && previousMode !== mode && mode === 'studio-shadow') this.fitSunShadowCamera();
        if (requestRender) this.requestRender();
    }

    setShadowMode(enabled) {
        const next = Boolean(enabled);
        this.renderer.shadowMap.enabled = next;
        this.studioSunLight.castShadow = next;
        if (this.shadowModeActive !== next) {
            this.shadowModeActive = next;
            this.applyShadowFlags();
        }
        if (next) {
            this.studioSunLight.shadow.needsUpdate = true;
            this.fitSunShadowCamera();
        }
    }

    applyShadowFlags() {
        const enabled = Boolean(this.shadowModeActive);
        [
            this.atomMeshes,
            this.cellGroup,
            this.bondGroup,
            this.supercellGroup,
            this.volumetricGroup
        ].forEach(group => {
            group?.traverse?.(object => {
                if (!object.isMesh) return;
                const opacity = Number(object.userData?.opacity);
                object.castShadow = enabled && !(Number.isFinite(opacity) && opacity < 0.999);
                object.receiveShadow = enabled;
            });
        });
    }

    invalidateSunShadowBounds() {
        this.sunShadowBoundsCache = null;
    }

    lightingStructureBounds() {
        if (this.sunShadowBoundsCache) return this.sunShadowBoundsCache.clone();
        const base = new THREE.Box3();
        const low = new THREE.Vector3();
        const high = new THREE.Vector3();
        this.forEachAtomProxy?.((proxy, index) => {
            if (!proxy || proxy.visible === false || !this.atomReferenceVisible(index)) return;
            const radius = Math.max(0.05, Number(this.atomVisualRadius(index) || 0.5));
            low.copy(proxy.position).addScalar(-radius);
            high.copy(proxy.position).addScalar(radius);
            base.expandByPoint(low);
            base.expandByPoint(high);
        });
        this.volumetricSurfaces?.forEach(surface => {
            surface.geometry?.computeBoundingBox?.();
            const bounds = surface.geometry?.boundingBox;
            if (!bounds?.isEmpty?.()) {
                base.union(bounds);
            }
        });

        if (base.isEmpty()) {
            const target = new THREE.Vector3(...(this.lightingOptions?.sunTarget || [0, 0, 0]));
            base.set(target.clone().addScalar(-4), target.clone().addScalar(4));
        }

        const reps = this.displayOptions?.supercell || [1, 1, 1];
        if (reps.some(value => value > 1) && this.hasValidCell()) {
            const cell = this.atomsData.cell.map(vector => new THREE.Vector3(...vector));
            const shiftA = cell[0].multiplyScalar(Math.max(0, reps[0] - 1));
            const shiftB = cell[1].multiplyScalar(Math.max(0, reps[1] - 1));
            const shiftC = cell[2].multiplyScalar(Math.max(0, reps[2] - 1));
            const baseCorners = this.boxCorners(base);
            const expanded = new THREE.Box3();
            for (let a = 0; a <= 1; a++) {
                for (let b = 0; b <= 1; b++) {
                    for (let c = 0; c <= 1; c++) {
                        const shift = new THREE.Vector3()
                            .addScaledVector(shiftA, a)
                            .addScaledVector(shiftB, b)
                            .addScaledVector(shiftC, c);
                        baseCorners.forEach(corner => expanded.expandByPoint(corner.clone().add(shift)));
                    }
                }
            }
            base.copy(expanded);
        }
        base.translate(this.visualTranslationVector());

        this.sunShadowBoundsCache = base.clone();
        return base;
    }

    boxCorners(box) {
        const { min, max } = box;
        return [
            new THREE.Vector3(min.x, min.y, min.z),
            new THREE.Vector3(max.x, min.y, min.z),
            new THREE.Vector3(min.x, max.y, min.z),
            new THREE.Vector3(max.x, max.y, min.z),
            new THREE.Vector3(min.x, min.y, max.z),
            new THREE.Vector3(max.x, min.y, max.z),
            new THREE.Vector3(min.x, max.y, max.z),
            new THREE.Vector3(max.x, max.y, max.z)
        ];
    }

    semanticSunDirection() {
        const source = new THREE.Vector3(...(this.lightingOptions?.sunPosition || [8, -10, 14]));
        const target = new THREE.Vector3(...(this.lightingOptions?.sunTarget || [0, 0, 0]));
        const direction = target.sub(source);
        return direction.lengthSq() > 1e-12 ? direction.normalize() : new THREE.Vector3(0, 0, -1);
    }

    applyStudioSunDirection(bounds = this.lightingStructureBounds()) {
        if (!this.studioSunLight || !this.studioSunTarget) return null;
        const sphere = bounds.getBoundingSphere(new THREE.Sphere());
        const center = sphere.center;
        const radius = Math.max(4, Number(sphere.radius || 4));
        const direction = this.semanticSunDirection();
        const distance = Math.max(12, radius * 3);

        // A Sun is defined only by direction. Keep the editable semantic
        // handles independent while centering the effective light and its
        // orthographic shadow camera on the complete rendered structure.
        this.studioSunTarget.position.copy(center);
        this.studioSunLight.position.copy(center).addScaledVector(direction, -distance);
        this.studioSunTarget.updateMatrixWorld(true);
        this.studioSunLight.updateMatrixWorld(true);
        return { bounds, center, radius, direction, distance };
    }

    refreshStudioSunForStructure({ invalidate = true } = {}) {
        if (invalidate) this.invalidateSunShadowBounds();
        if (!this.studioLightGroup?.visible) return;
        if (this.shadowModeActive) this.fitSunShadowCamera();
        else this.applyStudioSunDirection();
    }

    fitSunShadowCamera() {
        if (!this.studioSunLight?.shadow?.camera) return;
        const setup = this.applyStudioSunDirection(this.lightingStructureBounds());
        if (!setup) return;
        const radius = Math.max(4, setup.radius * 1.25);
        const shadowCamera = this.studioSunLight.shadow.camera;
        shadowCamera.left = -radius;
        shadowCamera.right = radius;
        shadowCamera.top = radius;
        shadowCamera.bottom = -radius;
        shadowCamera.near = Math.max(0.1, setup.distance - radius * 1.6);
        shadowCamera.far = setup.distance + radius * 1.6;
        shadowCamera.updateProjectionMatrix();
        this.studioSunLight.shadow.updateMatrices(this.studioSunLight);
        this.studioSunLight.shadow.needsUpdate = true;
    }

    sunWorldPerPixel(point) {
        const height = Math.max(1, this.domElement?.clientHeight || window.innerHeight || 1);
        if (this.camera?.isOrthographicCamera) {
            return (this.camera.top - this.camera.bottom) / Math.max(1, height * (this.camera.zoom || 1));
        }
        const distance = Math.max(0.1, this.camera.position.distanceTo(point));
        return 2 * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) * distance / height;
    }

    syncSunGizmo() {
        if (!this.sunGizmoGroup) return;
        const position = new THREE.Vector3(...(this.lightingOptions?.sunPosition || [8, -10, 14]));
        const target = new THREE.Vector3(...(this.lightingOptions?.sunTarget || [0, 0, 0]));
        const { positionHandle, targetHandle, directionLine } = this.sunGizmoGroup.userData;
        positionHandle.position.copy(position);
        targetHandle.position.copy(target);
        const attribute = directionLine.geometry.getAttribute('position');
        attribute.setXYZ(0, position.x, position.y, position.z);
        attribute.setXYZ(1, target.x, target.y, target.z);
        attribute.needsUpdate = true;
        directionLine.geometry.computeBoundingSphere();
        this.updateSunGizmoScale();
    }

    updateSunGizmoScale() {
        if (!this.sunGizmoGroup?.visible) return;
        const { positionHandle, targetHandle } = this.sunGizmoGroup.userData;
        const positionScale = Math.max(0.28, this.sunWorldPerPixel(positionHandle.position) * 50);
        const targetScale = Math.max(0.28, this.sunWorldPerPixel(targetHandle.position) * 50);
        positionHandle.scale.setScalar(positionScale);
        targetHandle.scale.setScalar(targetScale);
        positionHandle.quaternion.copy(this.camera.quaternion);
    }

    sunPointerNdc(event) {
        const rect = this.domElement.getBoundingClientRect();
        return new THREE.Vector2(
            ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
            -((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1
        );
    }

    pickSunHandle(event) {
        if (!this.sunGizmoGroup?.visible || !event) return null;
        this.sunRaycaster.setFromCamera(this.sunPointerNdc(event), this.camera);
        const hit = this.sunRaycaster.intersectObjects(this.sunGizmoGroup.userData.pickables, false)[0];
        return hit?.object?.userData?.sunHandle || null;
    }

    setSunGizmoSelected(handle, { requestRender = true } = {}) {
        const requested = handle === true ? 'source' : handle;
        this.sunGizmoSelected = this.sunGizmoGroup?.visible && ['source', 'target'].includes(requested)
            ? requested
            : null;
        const sourceRing = this.sunGizmoGroup?.userData?.sourceSelectionRing;
        const targetShell = this.sunGizmoGroup?.userData?.targetSelectionShell;
        if (sourceRing) sourceRing.visible = this.sunGizmoSelected === 'source';
        if (targetShell) targetShell.visible = this.sunGizmoSelected === 'target';
        if (requestRender) this.requestRender();
    }

    updateSunTransform(position, target, { notify = true } = {}) {
        this.lightingOptions.sunPosition = this.normalizedLightingVector(position, [8, -10, 14]);
        this.lightingOptions.sunTarget = this.normalizedLightingVector(target, [0, 0, 0]);
        this.applyStudioSunDirection();
        Object.assign(this.displayOptions, {
            sunPosition: [...this.lightingOptions.sunPosition],
            sunTarget: [...this.lightingOptions.sunTarget]
        });
        this.syncSunGizmo();
        if (this.shadowModeActive) this.fitSunShadowCamera();
        if (notify) {
            this.onLightingChange?.({
                ...this.lightingOptions,
                sunPosition: [...this.lightingOptions.sunPosition],
                sunTarget: [...this.lightingOptions.sunTarget]
            });
        }
        this.requestRender();
    }

    normalizedViewportBackground(value = this.displayOptions?.viewportBackground) {
        return value === 'dark' ? 'dark' : 'white';
    }

    viewportBackgroundColor(mode = this.viewportBackgroundMode) {
        return mode === 'white'
            ? new THREE.Color(0xffffff)
            : new THREE.Color(cssColor('--viewport-dark-bg', '#2d3333'));
    }

    setViewportBackground(mode, { rebuildGuides = true } = {}) {
        const next = this.normalizedViewportBackground(mode);
        const changed = next !== this.viewportBackgroundMode;
        this.viewportBackgroundMode = next;
        const color = this.viewportBackgroundColor(next);
        this.scene.background = color;
        this.renderer.setClearColor(color, 1);
        if (changed && rebuildGuides && this.gridGroup && this.axesHelper) {
            this.replaceViewportGuides(this.gridGroup.userData?.guideSize || this.desiredGuideSize());
        }
        this.domElement.dataset.viewportBackground = next;
        this.requestRender();
    }

    atomDisplayMode() {
        return this.displayOptions?.atomDisplayMode === '2d' ? '2d' : '3d';
    }

    effectiveBondStyle(requestedStyle = this.displayOptions?.bondStyle) {
        return this.atomDisplayMode() === '2d'
            ? 'flat'
            : (requestedStyle === 'flat' ? 'flat' : 'cylinder');
    }

    atomVisualRadius(index) {
        const label = this.atomsData?.symbols?.[index];
        const labelRadius = Number(this.displayOptions?.labelRadii?.[label]);
        const sourceRadius = Number.isFinite(labelRadius) && labelRadius > 0
            ? labelRadius
            : Number(this.atomsData?.visual?.radii?.[index]);
        const scale = Number(this.displayOptions?.atomRadiusScale || 0.6);
        const atomScaleValue = Number(
            this.displayOptions?.atomRadiusScales?.[index]
            ?? this.displayOptions?.atomRadiusScales?.[String(index)]
        );
        const atomScale = Number.isFinite(atomScaleValue) && atomScaleValue > 0
            ? atomScaleValue
            : 1;
        const radius = Number.isFinite(sourceRadius) && sourceRadius > 0 ? sourceRadius : FALLBACK_ATOM_RADIUS;
        return radius * (Number.isFinite(scale) && scale > 0 ? scale : 0.6) * atomScale;
    }

    atomCovalentRadius(index) {
        const radius = Number(this.atomsData?.visual?.bond_radii?.[index] ?? this.atomsData?.visual?.covalent_radii?.[index]);
        return Number.isFinite(radius) && radius > 0 ? radius : FALLBACK_COVALENT_RADIUS;
    }

    atomVdwRadius(index) {
        const radius = Number(this.atomsData?.visual?.vdw_radii?.[index]);
        return Number.isFinite(radius) && radius > 0 ? radius : null;
    }

    atomChemicalSymbol(index) {
        return this.atomsData?.chemical_symbols?.[index] || this.atomsData?.symbols?.[index] || '';
    }

    validHexColor(value) {
        return typeof value === 'string' && /^#[0-9A-Fa-f]{6}$/.test(value);
    }

    atomVisualColor(index, explicitColor = null) {
        const scaleColor = this.atomColorScaleColors?.[index];
        if (this.validHexColor(scaleColor)) return scaleColor;
        const atomColor = this.displayOptions?.atomColors?.[index]
            ?? this.displayOptions?.atomColors?.[String(index)];
        if (this.validHexColor(atomColor)) return atomColor;
        const label = this.atomsData?.symbols?.[index];
        const labelColor = this.displayOptions?.labelColors?.[label];
        if (this.validHexColor(labelColor)) return labelColor;
        if (this.validHexColor(explicitColor)) return explicitColor;
        const color = this.atomsData?.visual?.colors?.[index];
        return this.validHexColor(color) ? color : FALLBACK_ATOM_COLOR;
    }

    atomVisualOpacity(index) {
        const atomOpacity = Number(
            this.displayOptions?.atomOpacities?.[index]
            ?? this.displayOptions?.atomOpacities?.[String(index)]
        );
        if (Number.isFinite(atomOpacity)) return Math.max(0, Math.min(1, atomOpacity));
        const label = this.atomsData?.symbols?.[index];
        const configured = Number(this.displayOptions?.labelOpacities?.[label]);
        return Math.max(0, Math.min(1, Number.isFinite(configured) ? configured : 1));
    }

    fixedAtomDisplayEnabled() {
        return this.displayOptions.showOverlays !== false;
    }

    normalizedAtomMaterialPreset(value) {
        return Object.prototype.hasOwnProperty.call(ATOM_MATERIAL_PRESETS, value)
            ? value
            : 'standard';
    }

    atomMaterialPreset(index) {
        const atomOverride = this.displayOptions?.atomMaterials?.[index]
            ?? this.displayOptions?.atomMaterials?.[String(index)];
        if (atomOverride) return this.normalizedAtomMaterialPreset(atomOverride);
        const label = this.atomsData?.symbols?.[index];
        return this.normalizedAtomMaterialPreset(this.displayOptions?.labelMaterials?.[label]);
    }

    atomMaterialSpec(color, isFixed = false, presetName = 'standard') {
        const base = new THREE.Color(color);
        const preset = ATOM_MATERIAL_PRESETS[this.normalizedAtomMaterialPreset(presetName)];
        return {
            color: base,
            roughness: isFixed ? Math.max(0.72, preset.roughness) : preset.roughness,
            metalness: isFixed ? preset.metalness * 0.45 : preset.metalness,
            clearcoat: isFixed ? preset.clearcoat * 0.35 : preset.clearcoat,
            clearcoatRoughness: isFixed ? Math.max(0.62, preset.clearcoatRoughness) : preset.clearcoatRoughness,
            specularIntensity: isFixed ? preset.specularIntensity * 0.55 : preset.specularIntensity,
            envMapIntensity: isFixed ? preset.envMapIntensity * 0.72 : preset.envMapIntensity,
            emissive: new THREE.Color(0x000000),
            emissiveIntensity: 0,
            flatShading: isFixed
        };
    }

    ensureMetalEnvironmentMap() {
        if (this.metalEnvironmentMap) return this.metalEnvironmentMap;
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 128;
            const context = canvas.getContext('2d');
            if (!context) return null;

            const background = context.createLinearGradient(0, 0, 0, canvas.height);
            background.addColorStop(0, '#f8fbfa');
            background.addColorStop(0.34, '#d7dfdd');
            background.addColorStop(0.52, '#899493');
            background.addColorStop(0.67, '#414a4b');
            background.addColorStop(1, '#151b1c');
            context.fillStyle = background;
            context.fillRect(0, 0, canvas.width, canvas.height);

            const addSoftbox = (x, y, radius, strength = 1) => {
                const panel = context.createRadialGradient(x, y, 0, x, y, radius);
                panel.addColorStop(0, `rgba(255,255,255,${0.98 * strength})`);
                panel.addColorStop(0.48, `rgba(255,255,255,${0.72 * strength})`);
                panel.addColorStop(1, 'rgba(255,255,255,0)');
                context.fillStyle = panel;
                context.fillRect(x - radius, y - radius, radius * 2, radius * 2);
            };
            addSoftbox(42, 28, 42, 0.92);
            addSoftbox(184, 34, 58, 1.0);
            addSoftbox(239, 70, 30, 0.68);

            const horizon = context.createLinearGradient(0, 0, canvas.width, 0);
            horizon.addColorStop(0, 'rgba(255,255,255,0.05)');
            horizon.addColorStop(0.42, 'rgba(255,255,255,0.62)');
            horizon.addColorStop(0.58, 'rgba(255,255,255,0.72)');
            horizon.addColorStop(1, 'rgba(255,255,255,0.08)');
            context.fillStyle = horizon;
            context.fillRect(0, 61, canvas.width, 7);

            context.fillStyle = 'rgba(5,9,10,0.70)';
            context.fillRect(96, 0, 17, canvas.height);
            context.fillStyle = 'rgba(8,12,13,0.46)';
            context.fillRect(215, 0, 9, canvas.height);
            context.fillStyle = 'rgba(255,255,255,0.50)';
            context.fillRect(0, 5, canvas.width, 4);

            const source = new THREE.CanvasTexture(canvas);
            source.colorSpace = THREE.SRGBColorSpace;
            source.mapping = THREE.EquirectangularReflectionMapping;
            const generator = new THREE.PMREMGenerator(this.renderer);
            generator.compileEquirectangularShader();
            this.metalEnvironmentRenderTarget = generator.fromEquirectangular(source);
            this.metalEnvironmentMap = this.metalEnvironmentRenderTarget.texture;
            this.metalEnvironmentMap.name = 'v_ase_metal_studio_environment';
            source.dispose();
            generator.dispose();
        } catch (error) {
            console.warn('Metal reflection environment unavailable; using direct lighting only.', error);
            this.metalEnvironmentMap = null;
        }
        return this.metalEnvironmentMap;
    }

    createAtomMaterial(color, isFixed = false, presetName = 'standard', opacity = 1) {
        const normalizedOpacity = Math.max(0, Math.min(1, Number(opacity) || 0));
        const transparent = normalizedOpacity < 0.999;
        if (this.atomDisplayMode() === '2d') {
            const material = new THREE.MeshBasicMaterial({
                color: new THREE.Color(color),
                toneMapped: false,
                transparent,
                opacity: normalizedOpacity,
                depthWrite: !transparent
            });
            this.applyFlatAtomShader(material, isFixed);
            return material;
        }
        const normalizedPreset = this.normalizedAtomMaterialPreset(presetName);
        const spec = this.atomMaterialSpec(color, isFixed, presetName);
        const material = new THREE.MeshPhysicalMaterial({
            color: spec.color,
            roughness: spec.roughness,
            metalness: spec.metalness,
            clearcoat: spec.clearcoat,
            clearcoatRoughness: spec.clearcoatRoughness,
            specularIntensity: spec.specularIntensity,
            emissive: spec.emissive,
            emissiveIntensity: spec.emissiveIntensity,
            flatShading: spec.flatShading,
            transparent,
            opacity: normalizedOpacity,
            depthWrite: !transparent,
            envMap: normalizedPreset === 'metal' ? this.ensureMetalEnvironmentMap() : null,
            envMapIntensity: spec.envMapIntensity
        });
        if (isFixed) this.applyFixedAtomEtchedShader(material);
        return material;
    }

    createInstancedAtomMaterial(isFixed = false, presetName = 'standard', opacity = 1) {
        const normalizedOpacity = Math.max(0, Math.min(1, Number(opacity) || 0));
        const transparent = normalizedOpacity < 0.999;
        if (this.atomDisplayMode() === '2d') {
            const material = new THREE.MeshBasicMaterial({
                color: 0xffffff,
                toneMapped: false,
                transparent,
                opacity: normalizedOpacity,
                depthWrite: !transparent
            });
            this.applyFlatAtomShader(material, isFixed);
            return material;
        }
        const normalizedPreset = this.normalizedAtomMaterialPreset(presetName);
        const spec = this.atomMaterialSpec('#ffffff', isFixed, presetName);
        const material = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            roughness: spec.roughness,
            metalness: spec.metalness,
            clearcoat: spec.clearcoat,
            clearcoatRoughness: spec.clearcoatRoughness,
            specularIntensity: spec.specularIntensity,
            emissive: spec.emissive,
            emissiveIntensity: spec.emissiveIntensity,
            flatShading: spec.flatShading,
            transparent,
            opacity: normalizedOpacity,
            depthWrite: !transparent,
            envMap: normalizedPreset === 'metal' ? this.ensureMetalEnvironmentMap() : null,
            envMapIntensity: spec.envMapIntensity
        });
        if (isFixed) this.applyFixedAtomEtchedShader(material);
        return material;
    }

    atomMaterialCacheKey(
        color,
        isFixed,
        atomSegments,
        instanced = false,
        presetName = 'standard',
        opacity = 1
    ) {
        const mode = this.atomDisplayMode();
        const outline = mode === '2d'
            ? `outline-${this.viewportBackgroundMode === 'white' ? 'dark' : 'light'}`
            : 'plain';
        const preset = this.normalizedAtomMaterialPreset(presetName);
        const alpha = Math.max(0, Math.min(1, Number(opacity) || 0)).toFixed(4);
        return instanced
            ? `unit-sphere:${mode}:${outline}:${isFixed ? 'fixed' : 'normal'}:${preset}:alpha-${alpha}:instanced`
            : `${mode}:${outline}:${color}:${isFixed ? 'fixed' : 'normal'}:${preset}:alpha-${alpha}:${atomSegments}`;
    }

    applyFlatAtomShader(material, isFixed = false) {
        if (!material || material.userData?.flatAtomShaderApplied) return material;
        const outline = true;
        const outlineColor = this.viewportBackgroundMode === 'white'
            ? 'vec3(0.012)'
            : 'vec3(0.94)';
        material.userData.flatAtomShaderApplied = true;
        material.userData.flatOutlineEnabled = outline;
        material.userData.fixedEtchedFlatApplied = Boolean(isFixed);
        const etchedCode = isFixed
            ? `
                vec2 fixedMark = vFlatViewNormal.xy;
                float fixedDiagonal = abs(abs(fixedMark.x) - abs(fixedMark.y));
                float fixedStrokeAA = max(fwidth(fixedDiagonal) * 1.55, 0.020);
                float fixedStroke = 1.0 - smoothstep(0.080 - fixedStrokeAA, 0.135 + fixedStrokeAA, fixedDiagonal);
                float fixedRadius = length(fixedMark);
                float fixedReach = smoothstep(0.12, 0.22, fixedRadius)
                    * (1.0 - smoothstep(0.74, 0.88, fixedRadius));
                diffuseColor.rgb = mix(diffuseColor.rgb, ${outlineColor}, fixedStroke * fixedReach);
            `
            : '';
        const outlineCode = outline
            ? `
                float flatFacing = abs(normalize(vFlatViewNormal).z);
                float flatEdgeAA = max(fwidth(flatFacing) * 1.35, 0.008);
                float flatInterior = smoothstep(0.30 - flatEdgeAA, 0.42 + flatEdgeAA, flatFacing);
                diffuseColor.rgb = mix(${outlineColor}, diffuseColor.rgb, flatInterior);
            `
            : '';
        material.onBeforeCompile = shader => {
            if (outline) {
                shader.vertexShader = shader.vertexShader
                    .replace(
                        '#include <common>',
                        '#include <common>\nvarying vec3 vFlatViewNormal;'
                    )
                    .replace(
                        '#include <begin_vertex>',
                        `
                        vec3 vAseFlatObjectNormal = normal;
                        #ifdef USE_INSTANCING
                            mat3 vAseFlatInstanceNormal = mat3(instanceMatrix);
                            vAseFlatObjectNormal /= vec3(
                                dot(vAseFlatInstanceNormal[0], vAseFlatInstanceNormal[0]),
                                dot(vAseFlatInstanceNormal[1], vAseFlatInstanceNormal[1]),
                                dot(vAseFlatInstanceNormal[2], vAseFlatInstanceNormal[2])
                            );
                            vAseFlatObjectNormal = vAseFlatInstanceNormal * vAseFlatObjectNormal;
                        #endif
                        vFlatViewNormal = normalize(normalMatrix * vAseFlatObjectNormal);
                        #include <begin_vertex>
                        `
                    );
                shader.fragmentShader = shader.fragmentShader.replace(
                    '#include <common>',
                    '#include <common>\nvarying vec3 vFlatViewNormal;'
                );
            }
            shader.fragmentShader = shader.fragmentShader.replace(
                '#include <color_fragment>',
                `
                #include <color_fragment>
                ${etchedCode}
                ${outlineCode}
                `
            );
        };
        material.customProgramCacheKey = () => [
            'v-ase-flat-atom-v2',
            isFixed ? 'fixed' : 'normal',
            this.viewportBackgroundMode === 'white' ? 'dark-outline' : 'light-outline'
        ].join(':');
        material.needsUpdate = true;
        return material;
    }

    applyFixedAtomEtchedShader(material) {
        if (!material || material.userData?.fixedEtchedApplied) return material;
        material.userData.fixedEtchedApplied = true;
        material.onBeforeCompile = (shader) => {
            shader.fragmentShader = shader.fragmentShader.replace(
                '#include <color_fragment>',
                `
                #include <color_fragment>
                vec2 etchedUv = gl_FragCoord.xy * 0.022;
                float etchedTheta = etchedUv.x;
                float etchedPhi = etchedUv.y;
                float etchedLineA = abs(fract(etchedTheta * 14.0) - 0.5);
                float etchedLineB = abs(fract(etchedPhi * 11.0 + etchedTheta * 0.5) - 0.5);
                float etchedGrid = 1.0 - smoothstep(0.030, 0.082, min(etchedLineA, etchedLineB));
                vec2 etchedCell = fract(vec2(etchedTheta * 9.0 + etchedPhi * 2.0, etchedPhi * 10.5) + vec2(0.5, 0.0)) - 0.5;
                float etchedDimple = 1.0 - smoothstep(0.16, 0.30, length(etchedCell));
                float etchedMask = clamp(etchedGrid * 0.88 + etchedDimple * 0.32, 0.0, 1.0);
                diffuseColor.rgb = mix(diffuseColor.rgb * 0.94, diffuseColor.rgb * 0.24 + vec3(0.055), etchedMask);
                diffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.0, 0.74, 0.28), etchedGrid * 0.12);
                `
            );
            shader.fragmentShader = shader.fragmentShader.replace(
                '#include <roughnessmap_fragment>',
                `
                #include <roughnessmap_fragment>
                roughnessFactor = min(1.0, roughnessFactor + 0.30);
                `
            );
        };
        material.customProgramCacheKey = () => 'v-ase-fixed-micro-etched-faceted-v3';
        material.needsUpdate = true;
        return material;
    }

    fixedAdjustedColor(color, isFixed = false, presetName = 'standard', target = null) {
        // Fixed/material presets change surface response, not the element hue.
        return (target || new THREE.Color()).set(color);
    }

    atomLabelVisible(index) {
        const label = this.atomsData?.symbols?.[index];
        return !label || this.displayOptions?.labelVisible?.[label] !== false;
    }

    atomReferenceKey(index, cellOffset = null) {
        return Array.isArray(cellOffset)
            ? this.supercellReferenceKey(index, cellOffset)
            : `atom:${index}`;
    }

    atomReferenceVisible(index, cellOffset = null) {
        if (!this.atomLabelVisible(index)) return false;
        const hidden = this.hiddenAtomReferenceSet
            || new Set(this.displayOptions?.hiddenAtomReferences || []);
        return !hidden.has(this.atomReferenceKey(index, cellOffset));
    }

    rebuildAtomLabelIndex() {
        this.atomIndicesByLabel.clear();
        (this.atomsData?.symbols || []).forEach((label, index) => {
            if (!this.atomIndicesByLabel.has(label)) this.atomIndicesByLabel.set(label, []);
            this.atomIndicesByLabel.get(label).push(index);
        });
    }

    applyAtomVisibility(changedSymbols = null) {
        const affectedIndices = changedSymbols?.length
            ? changedSymbols.flatMap(symbol => this.atomIndicesByLabel.get(symbol) || [])
            : null;
        if (this.useInstancedAtoms) {
            const updateIndex = (index) => {
                const proxy = this.atomMeshByIndex.get(index);
                if (!proxy) return;
                proxy.visible = this.atomReferenceVisible(index);
                this.updateAtomInstanceMatrix(index);
            };
            if (affectedIndices) affectedIndices.forEach(updateIndex);
            else this.atomMeshByIndex.forEach((_, index) => updateIndex(index));
            this.atomInstanceMeshes.forEach(mesh => { mesh.instanceMatrix.needsUpdate = true; });
            this.selectionOutlines.children.forEach(outline => {
                if (outline.userData.selectionInstances) {
                    outline.userData.atomIndices.forEach((idx, instanceId) => {
                        this.setSelectionInstanceMatrix(outline, instanceId, idx);
                    });
                    outline.instanceMatrix.needsUpdate = true;
                    return;
                }
                const idx = outline.userData.outlineFor;
                outline.visible = this.atomReferenceVisible(idx);
            });
            this.constraintMarkGroup.children.forEach(group => {
                const idx = group.userData.constraintGuideFor;
                group.visible = this.atomReferenceVisible(idx);
            });
            this.constraintGuideGroup.children.forEach(group => {
                group.visible = this.constraintGuideVisible(group);
            });
            if (this.displayOptions.showBonds) this.refreshBondsForCurrentPositions();
            if (this.supercellGroup.children.length) this.updateSupercellPositions();
            if (this.hookeanGroup.children.length) this.updateHookeanPositions();
            this.refreshStudioSunForStructure();
            this.requestRender();
            return;
        }
        const targets = affectedIndices || [...this.atomMeshByIndex.keys()];
        targets.forEach(index => {
            const mesh = this.atomMeshByIndex.get(index);
            if (mesh) mesh.visible = this.atomReferenceVisible(index);
        });
        this.selectionOutlines.children.forEach(outline => {
            const idx = outline.userData.outlineFor;
            outline.visible = this.atomReferenceVisible(idx);
        });
        this.constraintMarkGroup.children.forEach(group => {
            const idx = group.userData.constraintGuideFor;
            group.visible = this.atomReferenceVisible(idx);
        });
        this.constraintGuideGroup.children.forEach(group => {
            group.visible = this.constraintGuideVisible(group);
        });
        if (this.displayOptions.showBonds) this.refreshBondsForCurrentPositions();
        if (this.supercellGroup.children.length) this.updateSupercellPositions();
        if (this.hookeanGroup.children.length) this.updateHookeanPositions();
        this.refreshStudioSunForStructure();
        this.requestRender();
    }

    gridDivisionsForSize(size) {
        if (!Number.isFinite(size) || size <= 0) return 80;
        const target = Math.max(24, Math.min(160, Math.round(size / 2)));
        return Math.max(24, Math.min(160, target));
    }

    niceGuideSize(rawSize) {
        const value = Math.max(80, Number(rawSize) || 80);
        const exponent = Math.floor(Math.log10(value));
        const base = Math.pow(10, exponent);
        const normalized = value / base;
        const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
        return factor * base;
    }

    cellCorners(cell) {
        const [a, b, c] = cell.map(v => new THREE.Vector3(...v));
        const o = new THREE.Vector3(0, 0, 0);
        return [
            o,
            a,
            b,
            c,
            a.clone().add(b),
            a.clone().add(c),
            b.clone().add(c),
            a.clone().add(b).add(c)
        ];
    }

    desiredGuideSize() {
        let extent = 80;
        const box = this.structureBounds?.();
        if (box) {
            const size = new THREE.Vector3();
            box.getSize(size);
            extent = Math.max(extent, size.x, size.y, size.length() * 0.55);
        }
        if (this.hasValidCell?.()) {
            const corners = this.cellCorners(this.atomsData.cell);
            const cellBox = new THREE.Box3().setFromPoints(corners);
            const cellSize = new THREE.Vector3();
            cellBox.getSize(cellSize);
            extent = Math.max(extent, cellSize.x, cellSize.y, cellSize.length() * 0.55);
        }
        return this.niceGuideSize(extent * 2.4);
    }

    buildViewportGuides(size = 80) {
        const guideSize = this.niceGuideSize(size);
        const half = guideSize / 2;
        const divisions = this.gridDivisionsForSize(guideSize);
        const gridGroup = new THREE.Group();
        const lightViewport = this.viewportBackgroundMode === 'white';
        const grid = new THREE.GridHelper(guideSize, divisions,
            lightViewport ? '#aeb7b3' : cssColor('--neutral-600', '#56625e'),
            lightViewport ? '#e3e8e5' : cssColor('--neutral-650', '#35403d'));
        grid.rotation.x = Math.PI / 2;
        grid.material.transparent = true;
        grid.material.opacity = lightViewport ? 0.48 : 0.58;
        grid.userData = { guide: true, guideSize, divisions };
        gridGroup.add(grid);

        const axisGroup = new THREE.Group();
        const makeLine = (start, end, color, opacity = 0.78) => {
            const geo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(...start),
                new THREE.Vector3(...end)
            ]);
            const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
            return new THREE.Line(geo, mat);
        };
        axisGroup.add(makeLine([-half, 0, 0], [half, 0, 0], cssColor('--axis-x', '#f05b55'), 0.68));
        axisGroup.add(makeLine([0, -half, 0], [0, half, 0], cssColor('--axis-y', '#69b942'), 0.68));
        axisGroup.add(makeLine([0, 0, -half], [0, 0, half], cssColor('--axis-z', '#408cd5'), 0.62));
        gridGroup.userData = { guideSize };
        axisGroup.userData = { guideSize };
        return { gridGroup, axisGroup };
    }

    replaceViewportGuides(size) {
        const showGrid = this.gridGroup?.visible ?? this.displayOptions.showGrid;
        const showAxes = this.axesHelper?.visible ?? this.displayOptions.showAxes;
        if (this.gridGroup) {
            this.scene.remove(this.gridGroup);
            this.clearGroup(this.gridGroup);
        }
        if (this.axesHelper) {
            this.scene.remove(this.axesHelper);
            this.clearGroup(this.axesHelper);
        }
        this.viewportGuides = this.buildViewportGuides(size);
        this.gridGroup = this.viewportGuides.gridGroup;
        this.axesHelper = this.viewportGuides.axisGroup;
        this.gridGroup.visible = showGrid;
        this.axesHelper.visible = showAxes;
        this.scene.add(this.gridGroup);
        this.scene.add(this.axesHelper);
    }

    refreshViewportGuidesForStructure() {
        const desired = this.desiredGuideSize();
        const current = this.gridGroup?.userData?.guideSize || 0;
        if (!current || Math.abs(desired - current) / desired > 0.08) {
            this.replaceViewportGuides(desired);
        }
    }

    rebuildAtoms(atoms, customColors) {
        this.invalidateSunShadowBounds();
        const commensuratePreviewToRestore = this.commensurateSupercellPreview;
        this.clearCommensurateSupercellPreview();
        // Remove existing meshes cleanly
        while(this.atomMeshes.children.length > 0){ 
            const child = this.atomMeshes.children[0];
            this.atomMeshes.remove(child); 
        }
        this.clearGroup(this.cellGroup);
        this.clearGroup(this.bondGroup);
        this.clearDisplacementVectors();
        this.clearForceVectors();
        this.clearCommensurateGuides();
        this.clearGroup(this.commensurateSupercellGroup);
        this.clearGroup(this.supercellGroup);
        this.clearGroup(this.constraintMarkGroup);
        this.clearGroup(this.constraintGuideGroup);
        this.clearGroup(this.constraintMotionGuideGroup);
        this.clearGroup(this.hookeanGroup);
        this.clearSelectionOutlines();
        this.clearReplicaSelectionOutlines();
        this.atomMeshByIndex.clear();
        this.atomInstanceRefs.clear();
        this.atomInstanceRefsByIndex.length = 0;
        this.atomInstanceMeshes.clear();
        this.atomIndicesByLabel.clear();
        this.atomsData = atoms;
        this.invalidateCellCache();
        this.invalidateBondNeighborCache();
        this.customColors = customColors || {};
        this.updateRenderQuality();
        this.refreshViewportGuidesForStructure();
        
        if (!atoms || !atoms.symbols) return;

        this.rebuildAtomLabelIndex();
        const fixed = this.fixedAtomDisplayEnabled() ? new Set(atoms.constraints?.fixed_indices || []) : new Set();
        const segmentCount = this.sphereQualitySegments(atoms.symbols.length);
        this.useInstancedAtoms = this.shouldUseInstancedAtoms(atoms);
        if (this.useInstancedAtoms) {
            this.rebuildInstancedAtoms(atoms, this.customColors, fixed, segmentCount);
            this.rebuildCell(atoms.cell);
            this.rebuildBonds();
            this.rebuildConstraintGuides();
            this.rebuildHookeanConstraints();
            this.rebuildSupercell();
            this.setForceVectors(atoms.forces, this.displayOptions);
            this.applyVisualTranslation();
            this.applyOverlayVisibility();
            if (this.needsInitialCameraFit) {
                this.fitCameraToStructure();
                this.needsInitialCameraFit = false;
            }
            this.applyShadowFlags();
            this.refreshStudioSunForStructure({ invalidate: false });
            if (commensuratePreviewToRestore) {
                this.setCommensurateSupercellPreview(commensuratePreviewToRestore);
            }
            this.requestRender();
            return;
        }
        atoms.symbols.forEach((sym, i) => {
            const radius = this.atomVisualRadius(i);
            const color = this.atomVisualColor(i, customColors[i]);
            const opacity = this.atomVisualOpacity(i);
            const isFixed = fixed.has(i);
            const materialPreset = this.atomMaterialPreset(i);

            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(1, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
                );
            }
            const materialKey = this.atomMaterialCacheKey(
                color, isFixed, atomSegments, false, materialPreset, opacity
            );
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(
                    materialKey,
                    this.createAtomMaterial(color, isFixed, materialPreset, opacity)
                );
            }
            const geo = this.geometryCache.get(geometryKey);
            const mat = this.materialCache.get(materialKey);
            const mesh = new THREE.Mesh(geo, mat);
            
            const pos = atoms.positions[i];
            mesh.position.set(pos[0], pos[1], pos[2]);
            mesh.scale.setScalar(radius);
            mesh.userData = { index: i, symbol: sym, fixed: isFixed, materialPreset, opacity };
            mesh.visible = this.atomReferenceVisible(i);
            
            this.atomMeshes.add(mesh);
            this.atomMeshByIndex.set(i, mesh);

        });

        this.rebuildCell(atoms.cell);
        this.rebuildBonds();
        this.rebuildConstraintGuides();
        this.rebuildHookeanConstraints();
        this.rebuildSupercell();
        this.setForceVectors(atoms.forces, this.displayOptions);
        this.applyVisualTranslation();
        this.applyOverlayVisibility();
        if (this.needsInitialCameraFit) {
            this.fitCameraToStructure();
            this.needsInitialCameraFit = false;
        }
        this.applyShadowFlags();
        this.refreshStudioSunForStructure({ invalidate: false });
        if (commensuratePreviewToRestore) {
            this.setCommensurateSupercellPreview(commensuratePreviewToRestore);
        }
        this.requestRender();
    }

    shouldUseInstancedAtoms(atoms) {
        const count = atoms?.symbols?.length || 0;
        return count >= 256 || (this.displayOptions.vizOnly && count >= 128);
    }

    atomProxy(index, position, symbol, fixed = false, materialPreset = 'standard') {
        return {
            position: position.clone(),
            visible: this.atomReferenceVisible(index),
            userData: { index, symbol, fixed, materialPreset }
        };
    }

    rebuildInstancedAtoms(atoms, customColors, fixed, segmentCount) {
        const groups = new Map();
        atoms.symbols.forEach((sym, i) => {
            const isFixed = fixed.has(i);
            const materialPreset = this.atomMaterialPreset(i);
            const opacity = this.atomVisualOpacity(i);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            const materialKey = this.atomMaterialCacheKey(
                '#ffffff', isFixed, atomSegments, true, materialPreset, opacity
            );
            const key = `${isFixed ? 'fixed' : 'normal'}:${materialPreset}:alpha-${opacity.toFixed(4)}:${atomSegments}`;
            if (!groups.has(key)) {
                groups.set(key, {
                    geometryKey,
                    materialKey,
                    fixed: isFixed,
                    materialPreset,
                    opacity,
                    segments: atomSegments,
                    indices: []
                });
            }
            groups.get(key).indices.push(i);
        });

        groups.forEach(group => {
            if (!this.geometryCache.has(group.geometryKey)) {
                this.geometryCache.set(
                    group.geometryKey,
                    new THREE.SphereGeometry(1, group.segments, Math.max(8, Math.floor(group.segments * 0.65)))
                );
            }
            if (!this.materialCache.has(group.materialKey)) {
                this.materialCache.set(
                    group.materialKey,
                    this.createInstancedAtomMaterial(
                        group.fixed, group.materialPreset, group.opacity
                    )
                );
            }
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(group.geometryKey),
                this.materialCache.get(group.materialKey),
                group.indices.length
            );
            mesh.userData = {
                instancedAtoms: true,
                atomIndices: group.indices,
                fixed: group.fixed,
                materialPreset: group.materialPreset,
                opacity: group.opacity,
                sharedGeometry: true,
                sharedMaterial: true
            };
            mesh.frustumCulled = false;
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            this.atomMeshes.add(mesh);
            this.atomInstanceMeshes.add(mesh);

            group.indices.forEach((index, instanceId) => {
                const position = new THREE.Vector3(...atoms.positions[index]);
                const proxy = this.atomProxy(
                    index,
                    position,
                    atoms.symbols[index],
                    fixed.has(index),
                    group.materialPreset
                );
                this.atomMeshByIndex.set(index, proxy);
                const ref = {
                    mesh,
                    instanceId,
                    proxy,
                    matrix: mesh.instanceMatrix.array,
                    matrixOffset: instanceId * 16
                };
                this.atomInstanceRefs.set(index, ref);
                this.atomInstanceRefsByIndex[index] = ref;
                mesh.setColorAt(
                    instanceId,
                    this.fixedAdjustedColor(
                        this.atomVisualColor(index, customColors[index]),
                        fixed.has(index),
                        group.materialPreset
                    )
                );
                ref.color = mesh.instanceColor.array;
                ref.colorOffset = instanceId * 3;
                this.updateAtomInstanceMatrix(index);
            });
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
        });
    }

    updateAtomInstanceMatrix(index) {
        const ref = this.atomInstanceRefs.get(index);
        const proxy = this.atomMeshByIndex.get(index);
        if (!ref || !proxy) return;
        const visible = proxy.visible !== false && this.atomReferenceVisible(index);
        const scale = visible ? this.atomVisualRadius(index) : 0;
        const matrix = ref.mesh.instanceMatrix.array;
        const offset = ref.instanceId * 16;
        matrix[offset] = scale;
        matrix[offset + 1] = 0;
        matrix[offset + 2] = 0;
        matrix[offset + 3] = 0;
        matrix[offset + 4] = 0;
        matrix[offset + 5] = scale;
        matrix[offset + 6] = 0;
        matrix[offset + 7] = 0;
        matrix[offset + 8] = 0;
        matrix[offset + 9] = 0;
        matrix[offset + 10] = scale;
        matrix[offset + 11] = 0;
        matrix[offset + 12] = visible ? proxy.position.x : 0;
        matrix[offset + 13] = visible ? proxy.position.y : 0;
        matrix[offset + 14] = visible ? proxy.position.z : 0;
        matrix[offset + 15] = 1;
    }

    updateAtomInstanceTranslation(index, x, y, z) {
        const ref = this.atomInstanceRefsByIndex[index] || this.atomInstanceRefs.get(index);
        const proxy = ref?.proxy || this.atomMeshByIndex.get(index);
        if (!ref || !proxy) return;
        proxy.position.x = x;
        proxy.position.y = y;
        proxy.position.z = z;
        const matrix = ref.matrix || ref.mesh.instanceMatrix.array;
        const offset = ref.matrixOffset ?? ref.instanceId * 16;
        matrix[offset + 12] = x;
        matrix[offset + 13] = y;
        matrix[offset + 14] = z;
    }

    flushAtomInstances(indices = null) {
        if (!this.useInstancedAtoms) return;
        if (indices) {
            indices.forEach(index => this.updateAtomInstanceMatrix(index));
        }
        this.atomInstanceMeshes.forEach(mesh => { mesh.instanceMatrix.needsUpdate = true; });
        this.requestRender();
    }

    forEachAtomProxy(callback) {
        if (this.useInstancedAtoms) {
            this.atomMeshByIndex.forEach((proxy, index) => callback(proxy, index));
            return;
        }
        this.atomMeshes.children.forEach(mesh => {
            if (mesh.userData.index === undefined) return;
            callback(mesh, mesh.userData.index);
        });
    }

    currentPositions() {
        const positions = (this.atomsData?.positions || []).map(p => [...p]);
        this.atomMeshByIndex.forEach((proxy, index) => {
            positions[index] = [proxy.position.x, proxy.position.y, proxy.position.z];
        });
        return positions;
    }

    disposeObject(root) {
        const geometries = new Set();
        const materials = new Set();
        root.traverse(object => {
            object.userData?.commensurateTexture?.dispose?.();
            if (object.geometry && !object.userData?.sharedGeometry) geometries.add(object.geometry);
            if (!object.material || object.userData?.sharedMaterial) return;
            const values = Array.isArray(object.material) ? object.material : [object.material];
            values.forEach(material => materials.add(material));
        });
        geometries.forEach(geometry => geometry.dispose());
        materials.forEach(material => material.dispose());
    }

    clearGroup(group) {
        while(group.children.length > 0) {
            const child = group.children[0];
            group.remove(child);
            this.disposeObject(child);
        }
    }

    sphereQualitySegmentsFor(quality = 'auto', atomCount = 0, scale = 1) {
        let baseSegments;
        if (quality === 'low') baseSegments = 12;
        else if (quality === 'medium') baseSegments = 24;
        else if (quality === 'high') baseSegments = 40;
        else if (quality === 'ultra') baseSegments = 64;
        else baseSegments = atomCount > 1500 ? 12 : atomCount > 400 ? 18 : 32;
        const safeScale = Math.max(0.5, Math.min(2, Number(scale) || 1));
        return Math.max(8, Math.min(128, Math.round(baseSegments * safeScale / 2) * 2));
    }

    sphereQualitySegments(atomCount = 0) {
        return this.sphereQualitySegmentsFor(this.displayOptions.sphereQuality || 'auto', atomCount, 1);
    }

    fixedAtomSegments(segmentCount) {
        // FixAtoms is a surface-material state. Reusing the exact sphere
        // tessellation keeps every user-selected radius and silhouette
        // unchanged while the etched/rough material communicates fixation.
        return segmentCount;
    }

    applyExportSphereQuality(quality = 'viewport', scale = 1) {
        const safeScale = Math.max(0.5, Math.min(2, Number(scale) || 1));
        if (quality === 'viewport' && Math.abs(safeScale - 1) < 1e-6) return () => {};
        const resolvedQuality = quality === 'viewport'
            ? (this.displayOptions.sphereQuality || 'auto')
            : quality;
        const atomCount = this.atomsData?.symbols?.length || 0;
        const normalSegments = this.sphereQualitySegmentsFor(resolvedQuality, atomCount, safeScale);
        const assignments = [];
        const geometryFor = fixed => {
            const segments = fixed ? this.fixedAtomSegments(normalSegments) : normalSegments;
            const key = `unit-sphere:${fixed ? 'fixed' : 'normal'}:${segments}`;
            if (!this.geometryCache.has(key)) {
                this.geometryCache.set(
                    key,
                    new THREE.SphereGeometry(1, segments, Math.max(8, Math.floor(segments * 0.65)))
                );
            }
            return this.geometryCache.get(key);
        };
        const replace = mesh => {
            if (!mesh?.geometry) return;
            assignments.push([mesh, mesh.geometry]);
            mesh.geometry = geometryFor(Boolean(mesh.userData?.fixed));
        };
        this.atomMeshes?.children?.forEach(replace);
        this.supercellGroup?.children?.forEach(mesh => {
            if (mesh.userData?.supercellInstanced) replace(mesh);
        });
        return () => {
            assignments.forEach(([mesh, geometry]) => {
                mesh.geometry = geometry;
            });
        };
    }

    structureBounds() {
        const box = new THREE.Box3();
        const atomBox = new THREE.Box3();
        let hasPoint = false;
        if (this.atomsData?.positions?.length) {
            this.atomsData.positions.forEach((position, index) => {
                if (!position || position.length < 3 || !this.atomLabelVisible(index)) return;
                const [x, y, z] = position.map(Number);
                if (![x, y, z].every(Number.isFinite)) return;
                const radius = this.atomVisualRadius(index);
                atomBox.min.x = Math.min(atomBox.min.x, x - radius);
                atomBox.min.y = Math.min(atomBox.min.y, y - radius);
                atomBox.min.z = Math.min(atomBox.min.z, z - radius);
                atomBox.max.x = Math.max(atomBox.max.x, x + radius);
                atomBox.max.y = Math.max(atomBox.max.y, y + radius);
                atomBox.max.z = Math.max(atomBox.max.z, z + radius);
            });
        }

        const repetitions = this.displayOptions?.supercell || [1, 1, 1];
        const visualTranslation = this.visualTranslationVector();
        if (!atomBox.isEmpty()) {
            const atomCorners = this.boxCorners(atomBox);
            const cell = this.hasValidCell()
                ? this.atomsData.cell.map(vector => new THREE.Vector3(...vector))
                : null;
            for (let ix = 0; ix <= (cell ? 1 : 0); ix++) {
                for (let iy = 0; iy <= (cell ? 1 : 0); iy++) {
                    for (let iz = 0; iz <= (cell ? 1 : 0); iz++) {
                        const shift = visualTranslation.clone();
                        if (cell) {
                            shift
                                .addScaledVector(cell[0], ix * Math.max(0, repetitions[0] - 1))
                                .addScaledVector(cell[1], iy * Math.max(0, repetitions[1] - 1))
                                .addScaledVector(cell[2], iz * Math.max(0, repetitions[2] - 1));
                        }
                        atomCorners.forEach(corner => box.expandByPoint(corner.clone().add(shift)));
                    }
                }
            }
            hasPoint = true;
        }

        if (this.hasValidCell()) {
            const [a, b, c] = this.atomsData.cell.map(v => new THREE.Vector3(...v));
            const corners = [
                new THREE.Vector3(0, 0, 0),
                a.clone().multiplyScalar(repetitions[0]),
                b.clone().multiplyScalar(repetitions[1]),
                c.clone().multiplyScalar(repetitions[2]),
                a.clone().multiplyScalar(repetitions[0]).addScaledVector(b, repetitions[1]),
                a.clone().multiplyScalar(repetitions[0]).addScaledVector(c, repetitions[2]),
                b.clone().multiplyScalar(repetitions[1]).addScaledVector(c, repetitions[2]),
                a.clone().multiplyScalar(repetitions[0])
                    .addScaledVector(b, repetitions[1])
                    .addScaledVector(c, repetitions[2])
            ];
            corners.forEach(point => box.expandByPoint(point));
            hasPoint = true;
        }

        return hasPoint && !box.isEmpty() ? box : null;
    }

    fitCameraToStructure(bounds = null) {
        const box = bounds || this.structureBounds();
        if (!box) return;
        const center = new THREE.Vector3();
        box.getCenter(center);

        const backward = new THREE.Vector3().subVectors(this.camera.position, this.controls.target);
        if (backward.lengthSq() < 1e-10) {
            backward.set(1, 1, 0.8);
        }
        backward.normalize();
        const forward = backward.clone().negate();
        const right = new THREE.Vector3().crossVectors(forward, this.camera.up);
        if (right.lengthSq() < 1e-10) right.set(1, 0, 0);
        right.normalize();
        const screenUp = new THREE.Vector3().crossVectors(right, forward).normalize();

        let halfWidth = 0;
        let halfHeight = 0;
        let halfDepth = 0;
        this.boxCorners(box).forEach(corner => {
            const offset = corner.sub(center);
            halfWidth = Math.max(halfWidth, Math.abs(offset.dot(right)));
            halfHeight = Math.max(halfHeight, Math.abs(offset.dot(screenUp)));
            halfDepth = Math.max(halfDepth, Math.abs(offset.dot(backward)));
        });
        halfWidth = Math.max(halfWidth, 0.5);
        halfHeight = Math.max(halfHeight, 0.5);

        const aspect = this.viewportAspect();
        const verticalFov = THREE.MathUtils.degToRad(this.perspectiveCamera?.fov || 50);
        const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * Math.max(aspect, 1e-6));
        const fitMargin = 1.12;
        const perspectiveDistance = Math.max(
            halfHeight / Math.max(Math.tan(verticalFov / 2), 1e-6),
            halfWidth / Math.max(Math.tan(horizontalFov / 2), 1e-6)
        ) * fitMargin + halfDepth;
        const distance = Math.max(4.0, perspectiveDistance);
        const near = Math.max(0.01, distance - halfDepth * 2 - 10);
        const far = Math.max(1000, distance + halfDepth * 2 + 100);

        this.controls.target.copy(center);
        [this.perspectiveCamera, this.orthographicCamera].forEach(camera => {
            camera.position.copy(center).addScaledVector(backward, distance);
            camera.up.copy(screenUp);
            camera.near = near;
            camera.far = far;
            camera.lookAt(center);
        });
        this.perspectiveCamera.aspect = aspect;
        this.perspectiveCamera.updateProjectionMatrix();
        const orthographicHalfHeight = Math.max(halfHeight, halfWidth / Math.max(aspect, 1e-6)) * fitMargin;
        this.orthographicCamera.zoom = 1;
        this.orthographicCamera.left = -orthographicHalfHeight * aspect;
        this.orthographicCamera.right = orthographicHalfHeight * aspect;
        this.orthographicCamera.top = orthographicHalfHeight;
        this.orthographicCamera.bottom = -orthographicHalfHeight;
        this.orthographicCamera.updateProjectionMatrix();
        this.controls.update?.();
        this.updateViewLighting();
        this.onCameraChange?.({ source: 'fit' });
    }

    updateRenderQuality() {
        const atomCount = this.atomsData?.positions?.length || 0;
        let cap = 2;
        if (atomCount >= 15000) cap = 1;
        else if (atomCount >= 5000) cap = 1.25;
        else if (atomCount >= 1000) cap = 1.5;
        const ratio = this.displayOptions.antiAliasing === false
            ? 1
            : Math.min(window.devicePixelRatio || 1, cap);
        this.renderer.setPixelRatio(ratio);
        this.renderer.setSize(window.innerWidth, window.innerHeight, false);
        this.requestRender();
    }

    viewportAspect() {
        const rect = this.container?.getBoundingClientRect?.();
        const width = rect?.width || window.innerWidth || 1;
        const height = rect?.height || window.innerHeight || 1;
        return width / Math.max(1, height);
    }

    updateCameraProjection(aspect = this.viewportAspect()) {
        if (this.perspectiveCamera) {
            this.perspectiveCamera.aspect = aspect;
            this.perspectiveCamera.updateProjectionMatrix();
        }
        if (this.orthographicCamera) {
            const distance = Math.max(
                1,
                this.orthographicCamera.position.distanceTo(this.controls?.target || new THREE.Vector3())
            );
            const fov = THREE.MathUtils.degToRad(this.perspectiveCamera?.fov || 50);
            const halfHeight = Math.max(1.0, distance * Math.tan(fov / 2));
            this.orthographicCamera.left = -halfHeight * aspect;
            this.orthographicCamera.right = halfHeight * aspect;
            this.orthographicCamera.top = halfHeight;
            this.orthographicCamera.bottom = -halfHeight;
            this.orthographicCamera.updateProjectionMatrix();
        }
    }

    setProjectionMode(mode = 'perspective') {
        const pixelsPerAngstrom = this.currentPixelsPerAngstrom();
        const nextMode = mode === 'orthographic' ? 'orthographic' : 'perspective';
        if (nextMode === this.projectionMode) {
            this.updateCameraProjection();
            this.setPixelsPerAngstrom(pixelsPerAngstrom, { requestRender: false, notify: false });
            this.onCameraChange?.({ source: 'projection' });
            this.requestRender();
            return;
        }
        const source = this.camera;
        const target = nextMode === 'orthographic' ? this.orthographicCamera : this.perspectiveCamera;
        target.position.copy(source.position);
        target.up.copy(source.up);
        target.quaternion.copy(source.quaternion);
        target.near = source.near;
        target.far = source.far;
        this.camera = target;
        this.projectionMode = nextMode;
        this.controls.camera = target;
        this.updateCameraProjection();
        this.camera.lookAt(this.controls.target);
        this.setPixelsPerAngstrom(pixelsPerAngstrom, { requestRender: false, notify: false });
        this.onCameraChange?.({ source: 'projection' });
        this.requestRender();
    }

    updateViewLighting(camera = this.camera, target = this.controls?.target) {
        if (!camera) return;
        if (this.modelingLightGroup?.visible && this.cameraFillLight) {
            this.cameraFillLight.position.copy(camera.position);
            if (this.cameraFillDirectionalLight && this.cameraFillTarget) {
                this.cameraFillDirectionalLight.position.copy(camera.position);
                this.cameraFillTarget.position.copy(target || new THREE.Vector3());
                this.cameraFillDirectionalLight.target.updateMatrixWorld();
            }
        }
        this.updateSunGizmoScale();
        this.updateRenderAreaGizmoScale();
    }

    currentPixelsPerAngstrom() {
        const height = Math.max(
            1,
            this.renderer?.domElement?.clientHeight || this.container?.clientHeight || window.innerHeight || 1
        );
        if (this.camera?.isOrthographicCamera) {
            const worldHeight = Math.abs(this.camera.top - this.camera.bottom) /
                Math.max(this.camera.zoom || 1, 1e-6);
            return worldHeight > 1e-9 ? height / worldHeight : 1;
        }
        const target = this.controls?.target || new THREE.Vector3();
        const distance = Math.max(1e-6, this.camera.position.distanceTo(target));
        const effectiveFov = this.camera?.getEffectiveFOV?.() || this.camera?.fov || 50;
        const worldHeight = 2 * distance * Math.tan(THREE.MathUtils.degToRad(effectiveFov) / 2);
        return worldHeight > 1e-9 ? height / worldHeight : 1;
    }

    setPixelsPerAngstrom(value, { requestRender = true, notify = true, source = 'api' } = {}) {
        const targetScale = Math.max(0.1, Math.min(5000, Number(value) || 1));
        const currentScale = Math.max(1e-9, this.currentPixelsPerAngstrom());
        if (this.camera?.isOrthographicCamera) {
            this.camera.zoom = Math.max(
                1e-4,
                Math.min(1e5, (this.camera.zoom || 1) * targetScale / currentScale)
            );
            this.camera.updateProjectionMatrix();
        } else if (this.camera?.isPerspectiveCamera) {
            const target = this.controls?.target || new THREE.Vector3();
            const offset = new THREE.Vector3().subVectors(this.camera.position, target);
            if (offset.lengthSq() < 1e-12) {
                this.camera.getWorldDirection(offset).multiplyScalar(-1);
            }
            const currentDistance = Math.max(1e-6, this.camera.position.distanceTo(target));
            const targetDistance = currentDistance * currentScale / targetScale;
            this.camera.position.copy(target).addScaledVector(offset.normalize(), targetDistance);
            this.camera.lookAt(target);
            this.camera.updateMatrixWorld(true);
        }
        if (notify) this.onCameraChange?.({ source });
        if (requestRender) this.requestRender();
        return this.currentPixelsPerAngstrom();
    }

    cameraFromSettings(settings, aspect = 1) {
        if (!settings || typeof settings !== 'object') return null;
        const vector = (value, fallback) => (
            Array.isArray(value)
            && value.length === 3
            && value.every(component => Number.isFinite(Number(component)))
                ? value.map(Number)
                : [...fallback]
        );
        const projection = settings.projection === 'perspective'
            ? 'perspective'
            : 'orthographic';
        const position = vector(settings.position, [10, 10, 10]);
        const target = new THREE.Vector3(...vector(settings.target, [0, 0, 0]));
        const up = vector(settings.up, [0, 0, 1]);
        const near = Number(settings.near);
        const far = Number(settings.far);
        let camera;
        if (projection === 'perspective') {
            const fov = Number(settings.fov);
            camera = new THREE.PerspectiveCamera(
                Number.isFinite(fov) && fov > 1 && fov < 179 ? fov : 50,
                Math.max(0.01, Number(aspect) || 1),
                Number.isFinite(near) && near > 0 ? near : 0.1,
                Number.isFinite(far) && far > 0 ? far : 10000
            );
            const zoom = Number(settings.zoom);
            camera.zoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
        } else {
            const scale = Number(settings.ortho_scale);
            const worldHeight = Number.isFinite(scale) && scale > 0 ? scale : 20;
            const halfHeight = worldHeight * 0.5;
            const halfWidth = halfHeight * Math.max(0.01, Number(aspect) || 1);
            camera = new THREE.OrthographicCamera(
                -halfWidth,
                halfWidth,
                halfHeight,
                -halfHeight,
                Number.isFinite(near) && near > 0 ? near : 0.1,
                Number.isFinite(far) && far > 0 ? far : 10000
            );
            camera.zoom = 1;
        }
        camera.position.fromArray(position);
        camera.up.fromArray(up).normalize();
        camera.lookAt(target);
        camera.updateProjectionMatrix();
        camera.updateMatrixWorld(true);
        return { camera, target };
    }

    exportCameraSetup(width, height, options = {}) {
        const outputWidth = Math.max(1, Math.round(Number(width) || 1));
        const outputHeight = Math.max(1, Math.round(Number(height) || 1));
        const outputAspect = outputWidth / outputHeight;
        const scaleMode = options.scaleMode === 'physical' ? 'physical' : 'viewport';
        const configured = this.cameraFromSettings(options.camera, outputAspect);
        const target = configured?.target
            || (this.controls?.target || new THREE.Vector3()).clone();
        const camera = configured?.camera || this.camera.clone();
        if (!configured) {
            camera.position.copy(this.camera.position);
            camera.quaternion.copy(this.camera.quaternion);
            camera.up.copy(this.camera.up);
            camera.near = this.camera.near;
            camera.far = this.camera.far;
        }

        let renderWidth = outputWidth;
        let renderHeight = outputHeight;
        let offsetX = 0;
        let offsetY = 0;
        let pixelsPerAngstrom = configured && camera.isOrthographicCamera
            ? outputHeight / Math.max(1e-9, Math.abs(camera.top - camera.bottom))
            : this.currentPixelsPerAngstrom();

        if (scaleMode === 'physical') {
            pixelsPerAngstrom = Math.max(0.1, Math.min(5000, Number(options.pixelsPerAngstrom) || 100));
            const worldWidth = outputWidth / pixelsPerAngstrom;
            const worldHeight = outputHeight / pixelsPerAngstrom;
            if (camera.isOrthographicCamera) {
                camera.zoom = 1;
                camera.left = -worldWidth / 2;
                camera.right = worldWidth / 2;
                camera.top = worldHeight / 2;
                camera.bottom = -worldHeight / 2;
            } else if (camera.isPerspectiveCamera) {
                camera.aspect = outputAspect;
                const effectiveFov = camera.getEffectiveFOV?.() || camera.fov || 50;
                const halfAngle = THREE.MathUtils.degToRad(effectiveFov) / 2;
                const distance = worldHeight / Math.max(2 * Math.tan(halfAngle), 1e-6);
                const offset = new THREE.Vector3().subVectors(camera.position, target);
                if (offset.lengthSq() < 1e-12) {
                    camera.getWorldDirection(offset).multiplyScalar(-1);
                }
                camera.position.copy(target).addScaledVector(offset.normalize(), distance);
                camera.lookAt(target);
            }
        } else {
            if (camera.isPerspectiveCamera) {
                camera.aspect = outputAspect;
            } else if (camera.isOrthographicCamera) {
                const centerX = (camera.left + camera.right) / 2;
                const halfHeight = Math.max(1e-9, Math.abs(camera.top - camera.bottom) / 2);
                const halfWidth = halfHeight * outputAspect;
                camera.left = centerX - halfWidth;
                camera.right = centerX + halfWidth;
            }
        }
        camera.updateProjectionMatrix();
        camera.updateMatrixWorld(true);
        return {
            camera,
            target,
            scaleMode,
            pixelsPerAngstrom,
            renderWidth,
            renderHeight,
            offsetX,
            offsetY,
            outputWidth,
            outputHeight
        };
    }

    exportCompositionSnapshot(width, height, options = {}) {
        const exportView = this.exportCameraSetup(width, height, options);
        const camera = exportView.camera;
        const projection = camera.isPerspectiveCamera ? 'perspective' : 'orthographic';
        const orthoScale = camera.isOrthographicCamera
            ? Math.abs(camera.top - camera.bottom) / Math.max(camera.zoom || 1, 1e-9)
            : null;
        return {
            schema: 'v_ase.export-composition.v1',
            width: exportView.outputWidth,
            height: exportView.outputHeight,
            aspect: exportView.outputWidth / Math.max(1, exportView.outputHeight),
            options: JSON.parse(JSON.stringify(options || {})),
            camera: {
                position: camera.position.toArray(),
                target: exportView.target.toArray(),
                up: camera.up.toArray(),
                projection,
                fov: camera.fov || 50,
                zoom: camera.isPerspectiveCamera ? (camera.zoom || 1) : 1,
                ortho_scale: orthoScale,
                near: camera.near,
                far: camera.far,
                aspect: exportView.outputWidth / Math.max(1, exportView.outputHeight)
            }
        };
    }

    setExportPreview(config = {}) {
        const width = Math.max(1, Math.round(Number(config.width) || 1920));
        const height = Math.max(1, Math.round(Number(config.height) || 1080));
        const next = {
            enabled: Boolean(config.enabled),
            width,
            height,
            options: { ...(config.options || {}) }
        };
        const previousSignature = JSON.stringify(this.exportPreview || {});
        const nextSignature = JSON.stringify(next);
        this.exportPreview = next;
        if (this.exportPreviewFrame) {
            this.exportPreviewFrame.classList.toggle('hidden', !next.enabled);
            this.exportPreviewFrame.setAttribute('aria-hidden', next.enabled ? 'false' : 'true');
            this.exportPreviewFrame.dataset.outputWidth = `${width}`;
            this.exportPreviewFrame.dataset.outputHeight = `${height}`;
        }
        if (this.exportPreviewDimensions) {
            this.exportPreviewDimensions.textContent = `${width} x ${height}`;
        }
        this.domElement.dataset.exportPreview = next.enabled ? 'true' : 'false';
        if (!next.enabled) {
            this.lastExportPreview = null;
            this.exportPreviewCamera = null;
            this.exportPreviewTarget = null;
        }
        if (previousSignature !== nextSignature) this.requestRender();
    }

    exportPreviewRect(width, height) {
        const canvasRect = this.domElement.getBoundingClientRect();
        const canvasWidth = Math.max(1, this.domElement.clientWidth || canvasRect.width || window.innerWidth || 1);
        const canvasHeight = Math.max(1, this.domElement.clientHeight || canvasRect.height || window.innerHeight || 1);
        const outputAspect = Math.max(0.01, Number(width) / Math.max(1, Number(height)));
        const compact = canvasWidth < 640 || canvasHeight < 560;
        const edge = compact ? 12 : 24;

        const topBar = document.getElementById('top-bar')?.getBoundingClientRect();
        const topInset = topBar
            ? Math.max(edge, topBar.bottom - canvasRect.top + (compact ? 10 : 18))
            : edge;
        const commandBar = document.getElementById('command-bar');
        const commandRect = commandBar && getComputedStyle(commandBar).display !== 'none'
            ? commandBar.getBoundingClientRect()
            : null;
        const bottomInset = commandRect && commandRect.height > 0
            ? Math.max(edge, canvasRect.bottom - commandRect.top + (compact ? 8 : 16))
            : edge;
        const inspector = document.getElementById('inspector');
        const inspectorRect = inspector && !document.body.classList.contains('inspector-collapsed')
            ? inspector.getBoundingClientRect()
            : null;
        const rightInset = inspectorRect && inspectorRect.width > 1
            ? Math.max(edge, canvasRect.right - inspectorRect.left + (compact ? 8 : 18))
            : edge;

        const availableWidth = Math.max(120, canvasWidth - edge - rightInset);
        const availableHeight = Math.max(90, canvasHeight - topInset - bottomInset);
        const maxWidth = Math.max(96, Math.min(1100, availableWidth * (compact ? 0.94 : 0.90)));
        const maxHeight = Math.max(54, Math.min(720, availableHeight * (compact ? 0.94 : 0.88)));
        let frameWidth = Math.floor(maxWidth);
        let frameHeight = Math.max(1, Math.round(frameWidth / outputAspect));
        if (frameHeight > maxHeight) {
            frameHeight = Math.floor(maxHeight);
            frameWidth = Math.max(1, Math.round(frameHeight * outputAspect));
        }
        const left = Math.round(edge + (availableWidth - frameWidth) / 2);
        const top = Math.round(topInset + (availableHeight - frameHeight) / 2);
        return {
            left,
            top,
            width: frameWidth,
            height: frameHeight,
            canvasWidth,
            canvasHeight
        };
    }

    updateExportPreviewFrame(rect) {
        if (!this.exportPreviewFrame || !rect) return;
        this.exportPreviewFrame.style.left = `${rect.left}px`;
        this.exportPreviewFrame.style.top = `${rect.top}px`;
        this.exportPreviewFrame.style.width = `${rect.width}px`;
        this.exportPreviewFrame.style.height = `${rect.height}px`;
        this.exportPreviewFrame.dataset.frameAspect = `${rect.width / Math.max(1, rect.height)}`;
    }

    interactionProjectionContext(clientX, clientY) {
        const canvasRect = this.domElement.getBoundingClientRect();
        const preview = this.lastExportPreview?.frameRect;
        if (this.exportPreview?.enabled && preview && this.exportPreviewCamera) {
            const rect = {
                left: canvasRect.left + preview.left,
                top: canvasRect.top + preview.top,
                width: preview.width,
                height: preview.height
            };
            rect.right = rect.left + rect.width;
            rect.bottom = rect.top + rect.height;
            if (
                clientX >= rect.left && clientX <= rect.right
                && clientY >= rect.top && clientY <= rect.bottom
            ) {
                return {
                    camera: this.exportPreviewCamera,
                    target: this.exportPreviewTarget,
                    rect,
                    kind: 'render-area'
                };
            }
        }
        return {
            camera: this.camera,
            target: this.controls?.target,
            rect: {
                left: canvasRect.left,
                top: canvasRect.top,
                right: canvasRect.right,
                bottom: canvasRect.bottom,
                width: Math.max(1, canvasRect.width),
                height: Math.max(1, canvasRect.height)
            },
            kind: 'viewport'
        };
    }

    pointerNdc(event, context = null) {
        const view = context || this.interactionProjectionContext(event.clientX, event.clientY);
        const rect = view.rect;
        return new THREE.Vector2(
            ((event.clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1,
            -((event.clientY - rect.top) / Math.max(1, rect.height)) * 2 + 1
        );
    }

    projectWorldToClient(position, context) {
        const view = context || this.interactionProjectionContext(-1, -1);
        const projected = position.clone().project(view.camera);
        return {
            x: view.rect.left + (projected.x + 1) * 0.5 * view.rect.width,
            y: view.rect.top + (1 - projected.y) * 0.5 * view.rect.height,
            z: projected.z
        };
    }

    beginExportScene(options = {}) {
        const oldLighting = {
            ...this.lightingOptions,
            sunPosition: [...(this.lightingOptions?.sunPosition || [8, -10, 14])],
            sunTarget: [...(this.lightingOptions?.sunTarget || [0, 0, 0])]
        };
        const requestedMode = ['modeling', 'studio', 'studio-shadow'].includes(options.renderMode)
            ? options.renderMode
            : oldLighting.lightingMode;
        const oldBackground = this.scene.background;
        const oldClearColor = this.renderer.getClearColor(new THREE.Color()).clone();
        const oldClearAlpha = this.renderer.getClearAlpha();
        const oldGridVisible = this.gridGroup?.visible;
        const oldAxesVisible = this.axesHelper?.visible;
        const oldCellVisible = this.cellGroup?.visible;
        const oldRenderAreaGizmoVisible = this.renderAreaGizmoGroup?.visible;
        const supercellCellPreviews = (this.supercellGroup?.children || [])
            .filter(child => child.userData?.supercellCellPreview)
            .map(child => ({ child, visible: child.visible }));
        const restoreSphereQuality = this.applyExportSphereQuality(
            options.sphereQuality || 'viewport',
            options.sphereQualityScale ?? 1
        );
        this.setLightingOptions({
            ...oldLighting,
            lightingMode: requestedMode,
            sunIntensity: Number.isFinite(Number(options.sunIntensity))
                ? Number(options.sunIntensity)
                : oldLighting.sunIntensity,
            sunPosition: options.sunPosition || oldLighting.sunPosition,
            sunTarget: options.sunTarget || oldLighting.sunTarget,
            sunGizmo: false
        }, { requestRender: false });
        if (options.transparentBackground) {
            this.scene.background = null;
            this.renderer.setClearColor(0x000000, 0);
        } else {
            const requestedBackground = typeof options.backgroundColor === 'string'
                && /^#[0-9a-f]{6}$/i.test(options.backgroundColor)
                ? new THREE.Color(options.backgroundColor)
                : null;
            this.scene.background = requestedBackground || oldBackground || new THREE.Color(0x303235);
            this.renderer.setClearColor(
                this.scene.background?.isColor ? this.scene.background : new THREE.Color(0x303235),
                1
            );
        }
        if (this.gridGroup) {
            this.gridGroup.visible = options.includeGrid !== false && this.displayOptions.showGrid;
        }
        if (this.axesHelper) {
            this.axesHelper.visible = options.includeAxes !== false && this.displayOptions.showAxes;
        }
        if (this.renderAreaGizmoGroup) this.renderAreaGizmoGroup.visible = false;
        const includeCell = options.includeCell !== false;
        if (this.cellGroup) this.cellGroup.visible = includeCell;
        supercellCellPreviews.forEach(({ child }) => { child.visible = includeCell; });
        return {
            requestedMode,
            restore: () => {
                restoreSphereQuality();
                this.setLightingOptions(oldLighting, { requestRender: false });
                this.scene.background = oldBackground;
                this.renderer.setClearColor(oldClearColor, oldClearAlpha);
                if (this.gridGroup) this.gridGroup.visible = oldGridVisible;
                if (this.axesHelper) this.axesHelper.visible = oldAxesVisible;
                if (this.cellGroup) this.cellGroup.visible = oldCellVisible;
                if (this.renderAreaGizmoGroup) {
                    this.renderAreaGizmoGroup.visible = oldRenderAreaGizmoVisible;
                }
                supercellCellPreviews.forEach(({ child, visible }) => { child.visible = visible; });
            }
        };
    }

    renderExportView(exportView, sceneState) {
        const previousFlatOrientationCamera = this.flatOrientationCamera;
        this.flatOrientationCamera = exportView.camera;
        try {
            this.updateBondPositions();
            this.updateDisplacementVectorMatrices(true);
            this.updateForceVectorMatrices(true);
            this.updateFlatCellEdgeMatrices(true);
            this.syncSelectionOutlines();
            this.updateHookeanPositions();
            this.updateViewLighting(exportView.camera, exportView.target);
            this.renderer.render(this.scene, exportView.camera);
            if (sceneState.requestedMode === 'studio-shadow') {
                this.renderer.render(this.scene, exportView.camera);
            }
        } finally {
            this.flatOrientationCamera = previousFlatOrientationCamera;
        }
    }

    beginExportCapture(width, height, options = {}) {
        if (this.exportCaptureActive) throw new Error('Another export capture is already active.');
        if (this.renderRequestId !== null) {
            cancelAnimationFrame(this.renderRequestId);
            this.renderRequestId = null;
        }
        const exportView = this.exportCameraSetup(width, height, options);
        this.lastExportCapture = {
            outputSize: [exportView.outputWidth, exportView.outputHeight],
            renderSize: [exportView.renderWidth, exportView.renderHeight],
            offset: [exportView.offsetX, exportView.offsetY],
            scaleMode: exportView.scaleMode,
            pixelsPerAngstrom: exportView.pixelsPerAngstrom,
            cameraProjection: exportView.camera.projectionMatrix.elements.slice(),
            cameraPosition: exportView.camera.position.toArray(),
            cameraQuaternion: exportView.camera.quaternion.toArray(),
            options: JSON.parse(JSON.stringify(options || {}))
        };
        const oldSize = new THREE.Vector2();
        this.renderer.getSize(oldSize);
        let capture = null;
        this.exportCaptureActive = true;
        try {
            capture = {
                exportView,
                oldSize,
                oldPixelRatio: this.renderer.getPixelRatio(),
                oldViewport: this.renderer.getViewport(new THREE.Vector4()),
                oldScissor: this.renderer.getScissor(new THREE.Vector4()),
                oldScissorTest: this.renderer.getScissorTest(),
                sceneState: this.beginExportScene(options),
                ended: false
            };
            this.renderer.setPixelRatio(1);
            this.renderer.setSize(exportView.outputWidth, exportView.outputHeight, false);
            this.renderer.setViewport(0, 0, exportView.outputWidth, exportView.outputHeight);
            this.renderer.setScissorTest(false);
            return capture;
        } catch (error) {
            capture?.sceneState?.restore();
            this.exportCaptureActive = false;
            throw error;
        }
    }

    renderExportCaptureFrame(capture) {
        if (!capture || capture.ended) throw new Error('Export capture is not active.');
        const { exportView, sceneState } = capture;
        this.renderer.setViewport(0, 0, exportView.outputWidth, exportView.outputHeight);
        this.renderer.setScissorTest(false);
        this.renderer.clear(true, true, true);
        this.renderer.setViewport(
            exportView.offsetX,
            exportView.offsetY,
            exportView.renderWidth,
            exportView.renderHeight
        );
        this.renderer.setScissor(
            exportView.offsetX,
            exportView.offsetY,
            exportView.renderWidth,
            exportView.renderHeight
        );
        this.renderer.setScissorTest(true);
        this.renderExportView(exportView, sceneState);
    }

    endExportCapture(capture) {
        if (!capture || capture.ended) return;
        capture.ended = true;
        capture.sceneState.restore();
        this.renderer.setPixelRatio(capture.oldPixelRatio);
        this.renderer.setSize(capture.oldSize.x, capture.oldSize.y, false);
        this.renderer.setViewport(
            capture.oldViewport.x,
            capture.oldViewport.y,
            capture.oldViewport.z,
            capture.oldViewport.w
        );
        this.renderer.setScissor(
            capture.oldScissor.x,
            capture.oldScissor.y,
            capture.oldScissor.z,
            capture.oldScissor.w
        );
        this.renderer.setScissorTest(capture.oldScissorTest);
        this.updateBondPositions();
        this.updateDisplacementVectorMatrices(true);
        this.updateForceVectorMatrices(true);
        this.updateFlatCellEdgeMatrices(true);
        this.syncSelectionOutlines();
        this.updateViewLighting();
        this.exportCaptureActive = false;
        this.requestRender();
    }

    renderExportPreview() {
        if (!this.exportPreview?.enabled || !this.exportPreviewFrame) return;
        const { width, height, options } = this.exportPreview;
        const rect = this.exportPreviewRect(width, height);
        this.updateExportPreviewFrame(rect);
        const exportView = this.exportCameraSetup(width, height, options);
        this.exportPreviewCamera = exportView.camera;
        this.exportPreviewTarget = exportView.target;
        const oldViewport = this.renderer.getViewport(new THREE.Vector4());
        const oldScissor = this.renderer.getScissor(new THREE.Vector4());
        const oldScissorTest = this.renderer.getScissorTest();
        const sceneState = this.beginExportScene(options);

        const frameX = Math.max(0, Math.round(rect.left));
        const frameY = Math.max(0, Math.round(rect.canvasHeight - rect.top - rect.height));
        const frameWidth = Math.max(1, Math.round(rect.width));
        const frameHeight = Math.max(1, Math.round(rect.height));
        const scaleX = frameWidth / exportView.outputWidth;
        const scaleY = frameHeight / exportView.outputHeight;
        const contentX = frameX + Math.round(exportView.offsetX * scaleX);
        const contentY = frameY + Math.round(exportView.offsetY * scaleY);
        const contentWidth = Math.max(1, Math.round(exportView.renderWidth * scaleX));
        const contentHeight = Math.max(1, Math.round(exportView.renderHeight * scaleY));

        try {
            this.renderer.setViewport(frameX, frameY, frameWidth, frameHeight);
            this.renderer.setScissor(frameX, frameY, frameWidth, frameHeight);
            this.renderer.setScissorTest(true);
            this.renderer.clear(true, true, true);
            this.renderer.setViewport(contentX, contentY, contentWidth, contentHeight);
            this.renderer.setScissor(contentX, contentY, contentWidth, contentHeight);
            this.renderExportView(exportView, sceneState);
            this.previewRenderCount += 1;
            this.domElement.dataset.previewRenderCount = `${this.previewRenderCount}`;
            this.lastExportPreview = {
                frameRect: { ...rect },
                contentRect: {
                    left: contentX,
                    bottom: contentY,
                    width: contentWidth,
                    height: contentHeight
                },
                outputSize: [exportView.outputWidth, exportView.outputHeight],
                renderSize: [exportView.renderWidth, exportView.renderHeight],
                offset: [exportView.offsetX, exportView.offsetY],
                scaleMode: exportView.scaleMode,
                pixelsPerAngstrom: exportView.pixelsPerAngstrom,
                cameraProjection: exportView.camera.projectionMatrix.elements.slice(),
                cameraPosition: exportView.camera.position.toArray(),
                cameraQuaternion: exportView.camera.quaternion.toArray(),
                cameraTarget: exportView.target.toArray(),
                options: JSON.parse(JSON.stringify(options || {}))
            };
        } finally {
            sceneState.restore();
            this.renderer.setViewport(oldViewport.x, oldViewport.y, oldViewport.z, oldViewport.w);
            this.renderer.setScissor(oldScissor.x, oldScissor.y, oldScissor.z, oldScissor.w);
            this.renderer.setScissorTest(oldScissorTest);
            this.updateBondPositions();
            this.updateDisplacementVectorMatrices(true);
            this.updateForceVectorMatrices(true);
            this.updateFlatCellEdgeMatrices(true);
            this.syncSelectionOutlines();
            this.updateViewLighting();
        }
    }

    rebuildCell(cell) {
        this.clearGroup(this.cellGroup);
        this.invalidateCellCache();
        this.invalidateBondNeighborCache();
        if (!cell || cell.length !== 3) {
            this.requestRender();
            return;
        }
        const a = new THREE.Vector3(...cell[0]);
        const b = new THREE.Vector3(...cell[1]);
        const c = new THREE.Vector3(...cell[2]);
        if (a.lengthSq() === 0 && b.lengthSq() === 0 && c.lengthSq() === 0) {
            this.requestRender();
            return;
        }

        const o = new THREE.Vector3(0, 0, 0);
        const corners = [
            o, a, b, c,
            new THREE.Vector3().addVectors(a, b),
            new THREE.Vector3().addVectors(a, c),
            new THREE.Vector3().addVectors(b, c),
            new THREE.Vector3().addVectors(a, b).add(c)
        ];
        const edgePairs = [[0,1],[0,2],[0,3],[1,4],[1,5],[2,4],[2,6],[3,5],[3,6],[4,7],[5,7],[6,7]];
        const segments = edgePairs.map(([i, j]) => [corners[i], corners[j]]);
        if (!this.displayOptions.vizOnly) {
            const haloColor = this.viewportBackgroundMode === 'white' ? '#263238' : '#f2f5f4';
            const haloMaterial = new THREE.MeshBasicMaterial({
                color: haloColor,
                transparent: true,
                opacity: 0.52,
                depthTest: true,
                depthWrite: false,
                toneMapped: false
            });
            this.addCellEdgeInstances(
                this.cellGroup,
                segments,
                { unitCell: true, editableCellHalo: true },
                {
                    material: haloMaterial,
                    radius: Math.max(0.026, this.normalizedCellThickness() * 0.86)
                }
            );
        }
        this.addCellEdgeInstances(this.cellGroup, segments, { unitCell: true });
        this.updateCellVisibility();
        this.requestRender();
    }

    clearAddAtomsRegion() {
        if (!this.addAtomsRegionGroup) return;
        this.clearGroup(this.addAtomsRegionGroup);
        this.addAtomsRegionGroup.visible = false;
        this.addAtomsRegionGroup.userData = {};
        this.requestRender();
    }

    insertionRegionBasis(cell) {
        if (!Array.isArray(cell) || cell.length !== 3) return null;
        const basis = cell.map(row => new THREE.Vector3(...row.map(Number)));
        if (basis.some(vector => !Number.isFinite(vector.lengthSq()))) return null;
        const determinant = basis[0].dot(new THREE.Vector3().crossVectors(basis[1], basis[2]));
        if (Math.abs(determinant) <= 1e-10) return null;
        return {
            basis,
            reciprocal: [
                new THREE.Vector3().crossVectors(basis[1], basis[2]).divideScalar(determinant),
                new THREE.Vector3().crossVectors(basis[2], basis[0]).divideScalar(determinant),
                new THREE.Vector3().crossVectors(basis[0], basis[1]).divideScalar(determinant)
            ]
        };
    }

    insertionRegionBoundsCorners(bounds) {
        const [xmin, xmax, ymin, ymax, zmin, zmax] = bounds.map(Number);
        return [
            [xmin, ymin, zmin], [xmax, ymin, zmin],
            [xmin, ymax, zmin], [xmin, ymin, zmax],
            [xmax, ymax, zmin], [xmax, ymin, zmax],
            [xmin, ymax, zmax], [xmax, ymax, zmax]
        ].map(value => new THREE.Vector3(...value));
    }

    insertionRegionImages(region, cellData, pbc, pbcAware) {
        const bounds = region.bounds.map(Number);
        if (!cellData || !pbcAware || !pbc.some(Boolean)) {
            return [{ bounds, shift: [0, 0, 0] }];
        }
        const fractional = this.insertionRegionBoundsCorners(bounds).map(point => (
            cellData.reciprocal.map(vector => point.dot(vector))
        ));
        const ranges = [0, 1, 2].map(axis => {
            if (!pbc[axis]) return [0];
            const values = fractional.map(value => value[axis]);
            const lower = Math.ceil(-Math.max(...values) - 1e-9);
            const upper = Math.floor(1 - Math.min(...values) + 1e-9);
            return Array.from({ length: Math.max(0, upper - lower + 1) }, (_, index) => lower + index);
        });
        const images = [];
        for (const i of ranges[0]) {
            for (const j of ranges[1]) {
                for (const k of ranges[2]) {
                    const translation = new THREE.Vector3()
                        .addScaledVector(cellData.basis[0], i)
                        .addScaledVector(cellData.basis[1], j)
                        .addScaledVector(cellData.basis[2], k);
                    images.push({
                        shift: [i, j, k],
                        bounds: [
                            bounds[0] + translation.x, bounds[1] + translation.x,
                            bounds[2] + translation.y, bounds[3] + translation.y,
                            bounds[4] + translation.z, bounds[5] + translation.z
                        ]
                    });
                    if (images.length > 4096) {
                        throw new Error('Insertion region produces too many periodic images.');
                    }
                }
            }
        }
        return images;
    }

    solveInsertionPlanes(first, second, third) {
        const cross23 = new THREE.Vector3().crossVectors(second.normal, third.normal);
        const determinant = first.normal.dot(cross23);
        if (Math.abs(determinant) <= 1e-11) return null;
        return cross23.multiplyScalar(first.limit)
            .add(new THREE.Vector3().crossVectors(third.normal, first.normal).multiplyScalar(second.limit))
            .add(new THREE.Vector3().crossVectors(first.normal, second.normal).multiplyScalar(third.limit))
            .divideScalar(determinant);
    }

    clippedInsertionRegionGeometry(bounds, cellData = null) {
        const [xmin, xmax, ymin, ymax, zmin, zmax] = bounds.map(Number);
        if (![xmin, xmax, ymin, ymax, zmin, zmax].every(Number.isFinite)) return null;
        if (xmax <= xmin || ymax <= ymin || zmax <= zmin) return null;
        const planes = [
            { normal: new THREE.Vector3(1, 0, 0), limit: xmax },
            { normal: new THREE.Vector3(-1, 0, 0), limit: -xmin },
            { normal: new THREE.Vector3(0, 1, 0), limit: ymax },
            { normal: new THREE.Vector3(0, -1, 0), limit: -ymin },
            { normal: new THREE.Vector3(0, 0, 1), limit: zmax },
            { normal: new THREE.Vector3(0, 0, -1), limit: -zmin }
        ];
        if (cellData) {
            cellData.reciprocal.forEach(normal => {
                planes.push({ normal: normal.clone(), limit: 1 });
                planes.push({ normal: normal.clone().multiplyScalar(-1), limit: 0 });
            });
        }
        const vertices = [];
        const vertexKeys = new Set();
        for (let first = 0; first < planes.length - 2; first++) {
            for (let second = first + 1; second < planes.length - 1; second++) {
                for (let third = second + 1; third < planes.length; third++) {
                    const point = this.solveInsertionPlanes(planes[first], planes[second], planes[third]);
                    if (!point || planes.some(plane => plane.normal.dot(point) > plane.limit + 2e-7)) continue;
                    const key = [point.x, point.y, point.z]
                        .map(value => Math.round(value * 1e8))
                        .join(':');
                    if (vertexKeys.has(key)) continue;
                    vertexKeys.add(key);
                    vertices.push(point);
                }
            }
        }
        if (vertices.length < 4) return null;

        // Intersections that merely touch a periodic boundary can contain a
        // coplanar polygon but no 3D volume.  Treat those as empty so a box
        // spanning a complete periodic direction does not draw duplicate
        // zero-thickness wrapped fragments on both cell faces.
        const origin = vertices[0];
        let volumeDeterminant = 0;
        for (let first = 1; first < vertices.length - 2 && volumeDeterminant <= 1e-10; first++) {
            const firstVector = vertices[first].clone().sub(origin);
            for (let second = first + 1; second < vertices.length - 1 && volumeDeterminant <= 1e-10; second++) {
                const secondVector = vertices[second].clone().sub(origin);
                for (let third = second + 1; third < vertices.length; third++) {
                    const thirdVector = vertices[third].clone().sub(origin);
                    volumeDeterminant = Math.max(
                        volumeDeterminant,
                        Math.abs(firstVector.dot(new THREE.Vector3().crossVectors(secondVector, thirdVector)))
                    );
                    if (volumeDeterminant > 1e-10) break;
                }
            }
        }
        if (volumeDeterminant <= 1e-10) return null;

        const triangles = [];
        const edgeKeys = new Set();
        const segments = [];
        planes.forEach(plane => {
            const face = vertices
                .map((point, index) => ({ point, index }))
                .filter(item => Math.abs(plane.normal.dot(item.point) - plane.limit) <= 5e-7);
            if (face.length < 3) return;
            const center = face.reduce(
                (sum, item) => sum.add(item.point),
                new THREE.Vector3()
            ).divideScalar(face.length);
            const normal = plane.normal.clone().normalize();
            const reference = Math.abs(normal.x) < 0.8
                ? new THREE.Vector3(1, 0, 0)
                : new THREE.Vector3(0, 1, 0);
            const firstAxis = new THREE.Vector3().crossVectors(normal, reference).normalize();
            const secondAxis = new THREE.Vector3().crossVectors(normal, firstAxis).normalize();
            face.sort((left, right) => {
                const leftDelta = left.point.clone().sub(center);
                const rightDelta = right.point.clone().sub(center);
                return Math.atan2(leftDelta.dot(secondAxis), leftDelta.dot(firstAxis))
                    - Math.atan2(rightDelta.dot(secondAxis), rightDelta.dot(firstAxis));
            });
            for (let offset = 1; offset < face.length - 1; offset++) {
                triangles.push(face[0].index, face[offset].index, face[offset + 1].index);
            }
            face.forEach((item, index) => {
                const next = face[(index + 1) % face.length];
                const key = [item.index, next.index].sort((a, b) => a - b).join(':');
                if (edgeKeys.has(key)) return;
                edgeKeys.add(key);
                segments.push([item.point, next.point]);
            });
        });
        if (!triangles.length) return null;
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
            'position',
            new THREE.Float32BufferAttribute(vertices.flatMap(vertex => vertex.toArray()), 3)
        );
        geometry.setIndex(triangles);
        geometry.computeVertexNormals();
        return { geometry, segments };
    }

    insertionRegionSegmentKey(start, end) {
        const pointKey = point => point.toArray()
            .map(value => Math.round(Number(value) * 1e7))
            .join(':');
        return [pointKey(start), pointKey(end)].sort().join('|');
    }

    setAddAtomsRegions(configuration = null) {
        if (!this.addAtomsRegionGroup) return;
        this.addAtomsRegionConfiguration = configuration
            ? JSON.parse(JSON.stringify(configuration))
            : null;
        this.clearGroup(this.addAtomsRegionGroup);
        const regions = Array.isArray(configuration?.regions) ? configuration.regions : [];
        if (!configuration || configuration.visible === false || !regions.length) {
            this.addAtomsRegionGroup.visible = false;
            this.requestRender();
            return;
        }
        const selected = new Set((configuration.selectedIds || []).map(String));
        const cell = configuration.cell || this.atomsData?.cell;
        const cellData = this.insertionRegionBasis(cell);
        const pbc = Array.isArray(configuration.pbc)
            ? configuration.pbc.map(Boolean)
            : (this.atomsData?.pbc || [false, false, false]).map(Boolean);
        const pickables = [];
        regions.forEach(region => {
            const regionId = String(region.id || '');
            const bounds = Array.isArray(region.bounds) ? region.bounds.map(Number) : [];
            if (!regionId || bounds.length !== 6 || bounds.some(value => !Number.isFinite(value))) return;
            const rejected = region.role === 'reject' || region.role === 'prohibited';
            const isSelected = selected.has(regionId);
            const color = rejected ? 0xad3b98 : 0x008f78;
            const source = this.clippedInsertionRegionGeometry(bounds, null);
            if (!source) return;
            const sourceEdgeMaterial = new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity: isSelected ? 1 : 0.94,
                depthTest: true,
                depthWrite: false
            });
            if (isSelected) sourceEdgeMaterial.color.offsetHSL(0, 0, 0.12);
            const sourceEdgeMesh = this.addCellEdgeInstances(
                this.addAtomsRegionGroup,
                source.segments,
                {
                    addAtomsRegion: true,
                    insertionRegionSourceBox: true,
                    regionId
                },
                {
                    material: sourceEdgeMaterial,
                    radius: isSelected ? 0.062 : 0.047
                }
            );
            if (sourceEdgeMesh) {
                sourceEdgeMesh.renderOrder = 15;
                sourceEdgeMesh.userData.role = rejected ? 'reject' : 'allow';
                sourceEdgeMesh.userData.shift = [0, 0, 0];
                pickables.push(sourceEdgeMesh);
            }
            const sourceFillOptions = {
                    color,
                    transparent: true,
                    opacity: isSelected ? 0.18 : (rejected ? 0.13 : 0.10),
                    side: THREE.DoubleSide,
                    depthTest: true,
                    depthWrite: false
            };
            const sourceFillMaterial = this.atomDisplayMode() === '2d'
                ? new THREE.MeshBasicMaterial({ ...sourceFillOptions, toneMapped: false })
                : new THREE.MeshStandardMaterial({
                    ...sourceFillOptions,
                    emissive: color,
                    emissiveIntensity: isSelected ? 0.16 : 0.09,
                    metalness: 0.02,
                    roughness: 0.52
                });
            const sourceFill = new THREE.Mesh(
                source.geometry,
                sourceFillMaterial
            );
            sourceFill.renderOrder = 14;
            sourceFill.userData = {
                addAtomsRegion: true,
                insertionRegionSourceBox: true,
                regionId,
                role: rejected ? 'reject' : 'allow',
                shift: [0, 0, 0]
            };
            this.addAtomsRegionGroup.add(sourceFill);

            const images = this.insertionRegionImages(
                { ...region, bounds },
                cellData,
                pbc,
                configuration.pbcAware !== false
            );
            const wrappedSegments = [];
            const segmentKeys = new Set(source.segments.map(
                ([start, end]) => this.insertionRegionSegmentKey(start, end)
            ));
            images.forEach(image => {
                if (image.shift.every(value => value === 0)) return;
                const clipped = this.clippedInsertionRegionGeometry(image.bounds, cellData);
                if (!clipped) return;
                clipped.segments.forEach(segment => {
                    const key = this.insertionRegionSegmentKey(segment[0], segment[1]);
                    if (segmentKeys.has(key)) return;
                    segmentKeys.add(key);
                    wrappedSegments.push(segment);
                });
                const wrappedFillOptions = {
                        color,
                        transparent: true,
                        opacity: isSelected ? 0.12 : (rejected ? 0.085 : 0.065),
                        side: THREE.DoubleSide,
                        depthTest: true,
                        depthWrite: false,
                        polygonOffset: true,
                        polygonOffsetFactor: -1,
                        polygonOffsetUnits: -1
                };
                const wrappedFillMaterial = this.atomDisplayMode() === '2d'
                    ? new THREE.MeshBasicMaterial({ ...wrappedFillOptions, toneMapped: false })
                    : new THREE.MeshStandardMaterial({
                        ...wrappedFillOptions,
                        emissive: color,
                        emissiveIntensity: isSelected ? 0.12 : 0.06,
                        metalness: 0.02,
                        roughness: 0.56
                    });
                const fill = new THREE.Mesh(
                    clipped.geometry,
                    wrappedFillMaterial
                );
                fill.renderOrder = 13;
                fill.userData = {
                    addAtomsRegion: true,
                    insertionRegionWrappedFragment: true,
                    regionId,
                    role: rejected ? 'reject' : 'allow',
                    shift: image.shift
                };
                this.addAtomsRegionGroup.add(fill);
            });
            if (wrappedSegments.length) {
                const wrappedEdgeMaterial = new THREE.MeshBasicMaterial({
                    color,
                    transparent: true,
                    opacity: isSelected ? 0.72 : 0.52,
                    depthTest: true,
                    depthWrite: false
                });
                if (isSelected) wrappedEdgeMaterial.color.offsetHSL(0, 0, 0.12);
                const wrappedEdgeMesh = this.addCellEdgeInstances(
                    this.addAtomsRegionGroup,
                    wrappedSegments,
                    {
                        addAtomsRegion: true,
                        insertionRegionWrappedFragment: true,
                        regionId
                    },
                    {
                        material: wrappedEdgeMaterial,
                        radius: isSelected ? 0.040 : 0.030
                    }
                );
                if (wrappedEdgeMesh) {
                    wrappedEdgeMesh.renderOrder = 14;
                    wrappedEdgeMesh.userData.role = rejected ? 'reject' : 'allow';
                    pickables.push(wrappedEdgeMesh);
                }
            }
        });
        this.addAtomsRegionGroup.userData = {
            pickables,
            selectedIds: [...selected],
            regionCount: regions.length
        };
        this.addAtomsRegionGroup.visible = pickables.length > 0;
        this.addAtomsRegionGroup.position.copy(this.visualTranslationVector());
        this.requestRender();
    }

    setAddAtomsRegion(region = null) {
        if (!region || region.mode !== 'box') {
            this.setAddAtomsRegions(null);
            return;
        }
        this.setAddAtomsRegions({
            regions: [{
                id: 'legacy-region',
                name: 'Region',
                role: region.role === 'prohibited' ? 'reject' : 'allow',
                bounds: region.bounds
            }],
            cell: region.cell,
            pbc: this.atomsData?.pbc,
            pbcAware: true,
            selectedIds: region.selected ? ['legacy-region'] : []
        });
    }

    pickAddAtomsRegion(event) {
        const pickables = this.addAtomsRegionGroup?.userData?.pickables || [];
        if (!event || !this.addAtomsRegionGroup?.visible || !pickables.length) return false;
        this.sunRaycaster.setFromCamera(this.sunPointerNdc(event), this.camera);
        const intersection = this.sunRaycaster.intersectObjects(pickables, false)[0];
        return intersection?.object?.userData?.regionId || false;
    }

    normalizedCellColor() {
        const value = String(this.displayOptions.cellColor || '');
        return /^#[0-9a-f]{6}$/i.test(value) ? value : '#d6bd67';
    }

    normalizedCellThickness() {
        const value = Number(this.displayOptions.cellThickness);
        return THREE.MathUtils.clamp(Number.isFinite(value) ? value : 0.04, 0.01, 0.30);
    }

    normalizedCellMaterial() {
        if (this.atomDisplayMode() === '2d') return 'unlit';
        const value = String(this.displayOptions.cellMaterial || 'unlit');
        return ['unlit', 'standard', 'metal'].includes(value) ? value : 'unlit';
    }

    createCellMaterial() {
        const common = {
            color: new THREE.Color(this.normalizedCellColor()),
            transparent: true,
            opacity: 0.88,
            depthTest: true,
            depthWrite: false
        };
        const preset = this.normalizedCellMaterial();
        if (preset === 'metal') {
            return new THREE.MeshStandardMaterial({
                ...common,
                metalness: 0.82,
                roughness: 0.22
            });
        }
        if (preset === 'standard') {
            return new THREE.MeshStandardMaterial({
                ...common,
                metalness: 0.06,
                roughness: 0.52
            });
        }
        return new THREE.MeshBasicMaterial(common);
    }

    addCellEdgeInstances(group, segments, userData = {}, style = {}) {
        const valid = (segments || []).filter(([start, end]) => (
            start instanceof THREE.Vector3
            && end instanceof THREE.Vector3
            && start.distanceToSquared(end) > 1e-12
        ));
        if (!valid.length) return null;

        const flat = this.atomDisplayMode() === '2d';
        const mesh = new THREE.InstancedMesh(
            flat ? this.bondFlatGeometry : this.cellEdgeGeometry,
            style.material || this.createCellMaterial(),
            valid.length
        );
        const radius = Number.isFinite(Number(style.radius))
            ? Math.max(0.004, Number(style.radius))
            : this.normalizedCellThickness() * 0.5;
        mesh.frustumCulled = false;
        mesh.renderOrder = 3;
        mesh.userData = {
            ...userData,
            sharedGeometry: true,
            cellEdgeInstances: true,
            flatCellEdges: flat,
            cellEdgeRadius: radius,
            cellEdgeSegments: valid.map(([start, end]) => [start.clone(), end.clone()])
        };
        this.updateCellEdgeInstanceMatrices(mesh);
        group.add(mesh);
        return mesh;
    }

    updateCellEdgeInstanceMatrices(mesh) {
        const segments = mesh?.userData?.cellEdgeSegments;
        if (!mesh?.isInstancedMesh || !Array.isArray(segments)) return;
        const flat = mesh.userData.flatCellEdges === true;
        const radius = Math.max(0.004, Number(mesh.userData.cellEdgeRadius) || 0.02);
        segments.forEach(([start, end], index) => {
            const delta = end.clone().sub(start);
            const length = delta.length();
            this.cellEdgeDummy.position.copy(start).add(end).multiplyScalar(0.5);
            if (flat) {
                this.cellEdgeDummy.scale.set(radius * 2, length, 1);
                this.orientFlatBond(this.cellEdgeDummy, delta);
            } else {
                this.cellEdgeDummy.quaternion.setFromUnitVectors(
                    this.yAxis,
                    delta.multiplyScalar(1 / length)
                );
                this.cellEdgeDummy.scale.set(radius, length, radius);
            }
            this.cellEdgeDummy.updateMatrix();
            mesh.setMatrixAt(index, this.cellEdgeDummy.matrix);
        });
        mesh.instanceMatrix.needsUpdate = true;
    }

    updateFlatCellEdgeMatrices(force = false) {
        if (this.atomDisplayMode() !== '2d') return;
        const signature = this.displacementCameraKey();
        if (!force && signature === this.cellEdgeCameraSignature) return;
        this.cellEdgeCameraSignature = signature;
        [
            this.cellGroup,
            this.supercellGroup,
            this.addAtomsRegionGroup,
            this.commensurateSupercellGroup,
            this.commensurateGuideGroup
        ].forEach(group => group?.traverse?.(object => {
            if (object.userData?.flatCellEdges) this.updateCellEdgeInstanceMatrices(object);
        }));
    }

    updateCellVisibility() {
        const visible = this.displayOptions.showCell !== false;
        this.cellGroup.visible = visible;
        this.supercellGroup?.children?.forEach(child => {
            if (child.userData?.supercellCellPreview) child.visible = visible;
        });
    }

    updatePositions(positions) {
        if (this.atomsData) {
            this.atomsData.positions = positions;
        }
        if (this.useInstancedAtoms) {
            for (let index = 0; index < positions.length; index++) {
                const position = positions[index];
                if (!position) continue;
                this.updateAtomInstanceTranslation(
                    index, position[0], position[1], position[2]
                );
            }
            this.atomInstanceMeshes.forEach(mesh => {
                mesh.instanceMatrix.needsUpdate = true;
            });
            this.syncSelectionOutlines();
            this.syncConstraintGuides();
            this.refreshBondsForCurrentPositions();
            if (this.supercellGroup.children.length) {
                this.updateSupercellPositions({ translationsOnly: true });
            }
            if (this.hookeanGroup.children.length) this.updateHookeanPositions();
            this.refreshStudioSunForStructure();
            this.requestRender();
            return;
        }
        this.atomMeshes.children.forEach(mesh => {
            const idx = mesh.userData.index;
            if (idx === undefined || !positions[idx]) return;
            const p = positions[idx];
            mesh.position.set(p[0], p[1], p[2]);
        });
        this.atomMeshByIndex.forEach((proxy, idx) => {
            const p = positions[idx];
            if (p) proxy.position.set(p[0], p[1], p[2]);
        });
        this.syncSelectionOutlines();
        this.syncConstraintGuides();
        this.refreshBondsForCurrentPositions();
        this.updateSupercellPositions({ translationsOnly: true });
        this.updateHookeanPositions();
        this.updateForceVectorMatrices(true);
        this.refreshStudioSunForStructure();
        this.requestRender();
    }

    updatePositionsFlat(values, offset = 0, count = this.atomsData?.positions?.length || 0) {
        if (!values || !count) return;
        const atomPositions = this.atomsData?.positions;
        if (this.useInstancedAtoms) {
            const refs = this.atomInstanceRefsByIndex;
            for (let index = 0; index < count; index++) {
                const base = offset + index * 3;
                const x = values[base];
                const y = values[base + 1];
                const z = values[base + 2];
                const position = atomPositions?.[index];
                if (position) {
                    position[0] = x;
                    position[1] = y;
                    position[2] = z;
                }
                const ref = refs[index];
                if (!ref) continue;
                ref.proxy.position.x = x;
                ref.proxy.position.y = y;
                ref.proxy.position.z = z;
                ref.matrix[ref.matrixOffset + 12] = x;
                ref.matrix[ref.matrixOffset + 13] = y;
                ref.matrix[ref.matrixOffset + 14] = z;
            }
            this.atomInstanceMeshes.forEach(mesh => {
                mesh.instanceMatrix.needsUpdate = true;
            });
            this.syncSelectionOutlines();
            this.syncConstraintGuides();
            this.refreshBondsForCurrentPositions();
            if (this.supercellGroup.children.length) {
                this.updateSupercellPositions({ translationsOnly: true });
            }
            if (this.hookeanGroup.children.length) this.updateHookeanPositions();
            if (this.forceVectorGroup.children.length) this.updateForceVectorMatrices(true);
            this.refreshStudioSunForStructure();
            this.requestRender();
            return;
        }
        if (atomPositions) {
            for (let index = 0; index < count; index++) {
                const base = offset + index * 3;
                const position = atomPositions[index];
                if (!position) continue;
                position[0] = values[base];
                position[1] = values[base + 1];
                position[2] = values[base + 2];
            }
        }
        this.atomMeshes.children.forEach(mesh => {
            const idx = mesh.userData.index;
            if (idx === undefined || idx >= count) return;
            const base = offset + idx * 3;
            mesh.position.set(values[base], values[base + 1], values[base + 2]);
        });
        this.syncSelectionOutlines();
        this.syncConstraintGuides();
        this.refreshBondsForCurrentPositions();
        this.updateSupercellPositions({ translationsOnly: true });
        this.updateHookeanPositions();
        this.updateForceVectorMatrices(true);
        this.refreshStudioSunForStructure();
        this.requestRender();
    }

    setDisplayOptions(options, { rebuild = true } = {}) {
        const previous = this.displayOptions;
        this.displayOptions = {
            ...this.displayOptions,
            ...options,
            manualBondPairs: [...(options.manualBondPairs || this.displayOptions.manualBondPairs || [])],
            pairwiseBondCutoffs: { ...(options.pairwiseBondCutoffs || this.displayOptions.pairwiseBondCutoffs || {}) },
            pairwiseBondRanges: cloneBondRangeRecord(
                options.pairwiseBondRanges || this.displayOptions.pairwiseBondRanges || {}
            ),
            pairwiseBondStyles: cloneBondStyleRecord(
                options.pairwiseBondStyles || this.displayOptions.pairwiseBondStyles || {}
            ),
            labelRadii: { ...(options.labelRadii || this.displayOptions.labelRadii || {}) },
            labelColors: { ...(options.labelColors || this.displayOptions.labelColors || {}) },
            labelOpacities: { ...(options.labelOpacities || this.displayOptions.labelOpacities || {}) },
            labelVisible: { ...(options.labelVisible || this.displayOptions.labelVisible || {}) },
            labelMaterials: { ...(options.labelMaterials || this.displayOptions.labelMaterials || {}) },
            atomRadiusScales: { ...(options.atomRadiusScales || this.displayOptions.atomRadiusScales || {}) },
            atomColors: { ...(options.atomColors || this.displayOptions.atomColors || {}) },
            atomOpacities: { ...(options.atomOpacities || this.displayOptions.atomOpacities || {}) },
            atomMaterials: { ...(options.atomMaterials || this.displayOptions.atomMaterials || {}) },
            atomBondStyles: cloneAtomBondStyleRecord(
                options.atomBondStyles || this.displayOptions.atomBondStyles || {}
            ),
            hiddenAtomReferences: [...(options.hiddenAtomReferences || this.displayOptions.hiddenAtomReferences || [])],
            supercell: [...(options.supercell || this.displayOptions.supercell || [1, 1, 1])],
            translation: [...(options.translation || this.displayOptions.translation || [0, 0, 0])],
            sunPosition: [...(options.sunPosition || this.displayOptions.sunPosition || [8, -10, 14])],
            sunTarget: [...(options.sunTarget || this.displayOptions.sunTarget || [0, 0, 0])]
        };
        this.hiddenAtomReferenceSet = new Set(this.displayOptions.hiddenAtomReferences);
        const antiAliasingChanged = previous.antiAliasing !== this.displayOptions.antiAliasing;
        const sphereQualityChanged = previous.sphereQuality !== this.displayOptions.sphereQuality;
        const atomDisplayModeChanged = previous.atomDisplayMode !== this.displayOptions.atomDisplayMode;
        const viewportBackgroundChanged = previous.viewportBackground !== this.displayOptions.viewportBackground;
        const pairUsesFlatBonds = record => Object.values(record || {}).some(
            style => style?.style === 'flat'
        );
        const flatOutlineChanged = viewportBackgroundChanged && (
            previous.atomDisplayMode === '2d'
            || this.displayOptions.atomDisplayMode === '2d'
            || previous.bondStyle === 'flat'
            || this.displayOptions.bondStyle === 'flat'
            || pairUsesFlatBonds(previous.pairwiseBondStyles)
            || pairUsesFlatBonds(this.displayOptions.pairwiseBondStyles)
        );
        const radiusChanged = previous.atomRadiusScale !== this.displayOptions.atomRadiusScale ||
            !scalarRecordEqual(previous.labelRadii, this.displayOptions.labelRadii) ||
            !scalarRecordEqual(previous.atomRadiusScales, this.displayOptions.atomRadiusScales);
        const colorChanged = !scalarRecordEqual(previous.labelColors, this.displayOptions.labelColors) ||
            !scalarRecordEqual(previous.atomColors, this.displayOptions.atomColors);
        const opacityChanged = !scalarRecordEqual(
            previous.labelOpacities,
            this.displayOptions.labelOpacities
        ) || !scalarRecordEqual(previous.atomOpacities, this.displayOptions.atomOpacities);
        const materialChanged = !scalarRecordEqual(previous.labelMaterials, this.displayOptions.labelMaterials) ||
            !scalarRecordEqual(previous.atomMaterials, this.displayOptions.atomMaterials);
        const overlayChanged = previous.showOverlays !== this.displayOptions.showOverlays;
        const visibilityChanged = !scalarRecordEqual(previous.labelVisible, this.displayOptions.labelVisible);
        const hiddenReferencesChanged = !stringArrayEqual(
            previous.hiddenAtomReferences,
            this.displayOptions.hiddenAtomReferences
        );
        const changedVisibilityLabels = visibilityChanged
            ? [...new Set([
                ...Object.keys(previous.labelVisible || {}),
                ...Object.keys(this.displayOptions.labelVisible || {})
            ])].filter(label => previous.labelVisible?.[label] !== this.displayOptions.labelVisible?.[label])
            : [];
        const supercellChanged = !numberArrayEqual(previous.supercell, this.displayOptions.supercell);
        const translationChanged = previous.translationMode !== this.displayOptions.translationMode ||
            !numberArrayEqual(previous.translation, this.displayOptions.translation);
        const cellStyleChanged = previous.cellThickness !== this.displayOptions.cellThickness ||
            previous.cellColor !== this.displayOptions.cellColor ||
            previous.cellMaterial !== this.displayOptions.cellMaterial;
        const lightingChanged = previous.lightingMode !== this.displayOptions.lightingMode ||
            previous.sunIntensity !== this.displayOptions.sunIntensity ||
            previous.sunGizmo !== this.displayOptions.sunGizmo ||
            !numberArrayEqual(previous.sunPosition, this.displayOptions.sunPosition) ||
            !numberArrayEqual(previous.sunTarget, this.displayOptions.sunTarget);
        const displacementChanged = atomDisplayModeChanged ||
            previous.showDisplacements !== this.displayOptions.showDisplacements ||
            previous.displacementStyle !== this.displayOptions.displacementStyle ||
            previous.displacementScale !== this.displayOptions.displacementScale ||
            previous.displacementThickness !== this.displayOptions.displacementThickness ||
            previous.displacementColor !== this.displayOptions.displacementColor;
        const forceVectorsChanged = atomDisplayModeChanged ||
            previous.showForceVectors !== this.displayOptions.showForceVectors ||
            previous.forceVectorStyle !== this.displayOptions.forceVectorStyle ||
            previous.forceVectorScale !== this.displayOptions.forceVectorScale ||
            previous.forceVectorThickness !== this.displayOptions.forceVectorThickness ||
            previous.forceVectorColor !== this.displayOptions.forceVectorColor;
        const volumetricVisibilityChanged = (
            previous.showVolumetric !== this.displayOptions.showVolumetric
        );
        if (previous.projectionMode !== this.displayOptions.projectionMode) {
            this.setProjectionMode(this.displayOptions.projectionMode);
        }
        if (viewportBackgroundChanged || this.viewportBackgroundMode !== this.normalizedViewportBackground()) {
            this.setViewportBackground(this.displayOptions.viewportBackground);
        }
        this.domElement.dataset.atomDisplayMode = this.atomDisplayMode();
        if (lightingChanged || atomDisplayModeChanged) this.setLightingOptions(this.displayOptions);
        if (!rebuild) {
            if (antiAliasingChanged) this.updateRenderQuality();
            if (translationChanged) this.applyVisualTranslation();
            if (volumetricVisibilityChanged) {
                this.setVolumetricSurfaceVisibility(this.displayOptions.showVolumetric === true);
            }
            this.updateCellVisibility();
            if (this.axesHelper) this.axesHelper.visible = this.displayOptions.showAxes;
            if (this.gridGroup) this.gridGroup.visible = this.displayOptions.showGrid;
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }
        if (antiAliasingChanged) this.updateRenderQuality();
        if (
            sphereQualityChanged
            || overlayChanged
            || atomDisplayModeChanged
            || flatOutlineChanged
            || materialChanged
            || opacityChanged
        ) {
            if (this.atomsData) {
                this.rebuildAtoms(this.atomsData, this.customColors);
            }
            if (this.addAtomsRegionConfiguration) {
                this.setAddAtomsRegions(this.addAtomsRegionConfiguration);
            }
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }
        if ((radiusChanged || colorChanged) && this.atomsData) {
            this.refreshAtomAppearance();
            if ((this.displayOptions.supercell || [1, 1, 1]).some(value => value > 1)) {
                this.rebuildSupercell();
            }
        }
        if (cellStyleChanged && this.atomsData) {
            this.rebuildCell(this.atomsData.cell);
            if ((this.displayOptions.supercell || [1, 1, 1]).some(value => value > 1)) {
                this.rebuildSupercell();
            }
        }
        this.updateCellVisibility();
        if (this.axesHelper) this.axesHelper.visible = this.displayOptions.showAxes;
        if (this.gridGroup) this.gridGroup.visible = this.displayOptions.showGrid;
        this.applyOverlayVisibility();
        const bondsChanged = previous.showBonds !== this.displayOptions.showBonds ||
            previous.showPeriodicBonds !== this.displayOptions.showPeriodicBonds ||
            previous.bondMode !== this.displayOptions.bondMode ||
            previous.bondCutoffScale !== this.displayOptions.bondCutoffScale ||
            previous.bondStyle !== this.displayOptions.bondStyle ||
            previous.bondMaterial !== this.displayOptions.bondMaterial ||
            atomDisplayModeChanged ||
            previous.bondThickness !== this.displayOptions.bondThickness ||
            previous.bondColorMode !== this.displayOptions.bondColorMode ||
            previous.bondCustomColor !== this.displayOptions.bondCustomColor ||
            previous.bondOpacity !== this.displayOptions.bondOpacity ||
            !bondStyleRecordEqual(previous.pairwiseBondStyles, this.displayOptions.pairwiseBondStyles) ||
            !atomBondStyleRecordEqual(previous.atomBondStyles, this.displayOptions.atomBondStyles) ||
            (colorChanged && this.displayOptions.bondColorMode === 'split') ||
            !flatPairArrayEqual(previous.manualBondPairs, this.displayOptions.manualBondPairs) ||
            !scalarRecordEqual(previous.pairwiseBondCutoffs, this.displayOptions.pairwiseBondCutoffs) ||
            !bondRangeRecordEqual(previous.pairwiseBondRanges, this.displayOptions.pairwiseBondRanges) ||
            visibilityChanged ||
            hiddenReferencesChanged;
        if (bondsChanged) this.invalidateBondNeighborCache();
        if (visibilityChanged || hiddenReferencesChanged) {
            this.applyAtomVisibility(hiddenReferencesChanged ? null : changedVisibilityLabels);
        }
        else if (bondsChanged) this.rebuildBonds();
        if (supercellChanged) this.rebuildSupercell();
        if (supercellChanged && this.volumetricSurfaces.length) {
            this.rebuildVolumetricSurfaces();
        }
        if ((displacementChanged || visibilityChanged || hiddenReferencesChanged || supercellChanged) && this.displacementData) {
            this.setDisplacementVectors(this.displacementData, this.displayOptions);
        }
        if ((forceVectorsChanged || visibilityChanged || hiddenReferencesChanged || supercellChanged) && this.atomsData) {
            this.setForceVectors(this.atomsData.forces, this.displayOptions);
        }
        if (translationChanged) this.applyVisualTranslation();
        if (volumetricVisibilityChanged) {
            this.setVolumetricSurfaceVisibility(this.displayOptions.showVolumetric === true);
        }
        if ((radiusChanged || supercellChanged) && !visibilityChanged) {
            this.refreshStudioSunForStructure();
        }
        if (
            this.commensurateSupercellPreview
            && (
                radiusChanged
                || colorChanged
                || opacityChanged
                || materialChanged
                || visibilityChanged
                || hiddenReferencesChanged
                || bondsChanged
                || cellStyleChanged
            )
        ) {
            this.setCommensurateSupercellPreview(this.commensurateSupercellPreview);
        }
        this.requestRender();
    }

    applyOverlayVisibility() {
        const visible = this.displayOptions.showOverlays !== false;
        // A commensurate preview replaces the base structure. Base-selection
        // shells refer to the unrotated atom scene and must never leak into a
        // cells-only (or materialized preview-atom) lattice view.
        const baseSelectionVisible = visible && !this.commensurateSupercellPreview;
        if (this.selectionOutlines) this.selectionOutlines.visible = baseSelectionVisible;
        if (this.replicaSelectionOutlines) {
            this.replicaSelectionOutlines.visible = baseSelectionVisible;
        }
        if (this.constraintGuideGroup) this.constraintGuideGroup.visible = visible;
        if (this.constraintMotionGuideGroup) this.constraintMotionGuideGroup.visible = visible;
        if (this.constraintMarkGroup) this.constraintMarkGroup.visible = visible;
        if (this.hookeanGroup) this.hookeanGroup.visible = visible;
        if (this.displacementGroup) {
            this.displacementGroup.visible = visible && this.displayOptions.showDisplacements === true;
        }
        if (this.forceVectorGroup) {
            this.forceVectorGroup.visible = visible && this.displayOptions.showForceVectors === true;
        }
    }

    renameAtomLabel(oldSymbol, label, indices = [], displayOptions = null, baseSymbol = null) {
        if (!this.atomsData?.symbols) return;
        indices.forEach(index => {
            if (!oldSymbol || this.atomsData.symbols[index] === oldSymbol) {
                this.atomsData.symbols[index] = label;
            }
            if (baseSymbol && Array.isArray(this.atomsData.chemical_symbols)) {
                this.atomsData.chemical_symbols[index] = baseSymbol;
            }
            const mesh = this.atomMeshByIndex.get(index);
            if (mesh?.userData) mesh.userData.symbol = label;
        });
        this.rebuildAtomLabelIndex();
        if (displayOptions) {
            this.displayOptions = {
                ...this.displayOptions,
                ...displayOptions,
                manualBondPairs: [...(displayOptions.manualBondPairs || this.displayOptions.manualBondPairs || [])],
                pairwiseBondCutoffs: { ...(displayOptions.pairwiseBondCutoffs || this.displayOptions.pairwiseBondCutoffs || {}) },
                pairwiseBondRanges: cloneBondRangeRecord(
                    displayOptions.pairwiseBondRanges || this.displayOptions.pairwiseBondRanges || {}
                ),
                labelRadii: { ...(displayOptions.labelRadii || this.displayOptions.labelRadii || {}) },
                labelColors: { ...(displayOptions.labelColors || this.displayOptions.labelColors || {}) },
                labelOpacities: { ...(displayOptions.labelOpacities || this.displayOptions.labelOpacities || {}) },
                labelVisible: { ...(displayOptions.labelVisible || this.displayOptions.labelVisible || {}) },
                labelMaterials: { ...(displayOptions.labelMaterials || this.displayOptions.labelMaterials || {}) },
                atomRadiusScales: { ...(displayOptions.atomRadiusScales || this.displayOptions.atomRadiusScales || {}) },
                atomColors: { ...(displayOptions.atomColors || this.displayOptions.atomColors || {}) },
                atomOpacities: { ...(displayOptions.atomOpacities || this.displayOptions.atomOpacities || {}) },
                atomMaterials: { ...(displayOptions.atomMaterials || this.displayOptions.atomMaterials || {}) },
                atomBondStyles: cloneAtomBondStyleRecord(
                    displayOptions.atomBondStyles || this.displayOptions.atomBondStyles || {}
                ),
                supercell: [...(displayOptions.supercell || this.displayOptions.supercell || [1, 1, 1])]
            };
        }
        if (this.useInstancedAtoms) {
            this.rebuildAtoms(this.atomsData, this.customColors);
            return;
        }
        this.refreshAtomAppearance(indices);
        this.invalidateBondNeighborCache();
        this.rebuildBonds();
        this.rebuildSupercell();
        this.applyAtomVisibility();
    }

    refreshAtomAppearance(indices = []) {
        if (!this.atomsData?.symbols) return;
        const targets = indices.length ? indices : this.atomsData.symbols.map((_, index) => index);
        if (this.useInstancedAtoms) {
            const matrices = new Set();
            const colors = new Set();
            targets.forEach(index => {
                const ref = this.atomInstanceRefs.get(index);
                const proxy = this.atomMeshByIndex.get(index);
                if (!ref || !proxy) return;
                this.updateAtomInstanceMatrix(index);
                ref.mesh.setColorAt(
                    ref.instanceId,
                    this.fixedAdjustedColor(
                        this.atomVisualColor(index, this.customColors[index]),
                        Boolean(proxy.userData.fixed),
                        proxy.userData.materialPreset || this.atomMaterialPreset(index)
                    )
                );
                matrices.add(ref.mesh);
                colors.add(ref.mesh);
            });
            matrices.forEach(mesh => { mesh.instanceMatrix.needsUpdate = true; });
            colors.forEach(mesh => { if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true; });
            this.requestRender();
            return;
        }
        const segmentCount = this.sphereQualitySegments(this.atomsData.symbols.length);
        targets.forEach(index => {
            const mesh = this.atomMeshByIndex.get(index);
            if (!mesh) return;
            const radius = this.atomVisualRadius(index);
            const color = this.atomVisualColor(index, this.customColors[index]);
            const opacity = this.atomVisualOpacity(index);
            const isFixed = Boolean(mesh.userData.fixed) && this.fixedAtomDisplayEnabled();
            const materialPreset = this.atomMaterialPreset(index);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(1, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
                );
            }
            const materialKey = this.atomMaterialCacheKey(
                color, isFixed, atomSegments, false, materialPreset, opacity
            );
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(
                    materialKey,
                    this.createAtomMaterial(color, isFixed, materialPreset, opacity)
                );
            }
            mesh.geometry = this.geometryCache.get(geometryKey);
            mesh.material = this.materialCache.get(materialKey);
            mesh.scale.setScalar(radius);
            mesh.visible = this.atomReferenceVisible(index);
            mesh.userData.materialPreset = materialPreset;
            mesh.userData.opacity = opacity;
        });
        this.requestRender();
    }

    refreshAtomColors(indices = []) {
        if (!this.atomsData?.symbols) return;
        if (this.useInstancedAtoms) {
            const changed = new Set();
            const refs = this.atomInstanceRefsByIndex;
            const scratch = this.atomColorScratch;
            const updateIndex = index => {
                const ref = refs[index] || this.atomInstanceRefs.get(index);
                const proxy = ref?.proxy || this.atomMeshByIndex.get(index);
                if (!ref || !proxy) return;
                this.fixedAdjustedColor(
                    this.atomVisualColor(index, this.customColors[index]),
                    Boolean(proxy.userData.fixed),
                    proxy.userData.materialPreset || this.atomMaterialPreset(index),
                    scratch
                );
                if (ref.color) scratch.toArray(ref.color, ref.colorOffset);
                else ref.mesh.setColorAt(ref.instanceId, scratch);
                changed.add(ref.mesh);
            };
            if (indices.length) indices.forEach(updateIndex);
            else for (let index = 0; index < refs.length; index++) updateIndex(index);
            changed.forEach(mesh => {
                if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            });
            this.requestRender();
            return;
        }
        const targets = indices.length ? indices : this.atomsData.symbols.map((_, index) => index);
        const segmentCount = this.sphereQualitySegments(this.atomsData.symbols.length);
        targets.forEach(index => {
            const mesh = this.atomMeshByIndex.get(index);
            if (!mesh) return;
            const color = this.atomVisualColor(index, this.customColors[index]);
            const opacity = this.atomVisualOpacity(index);
            const isFixed = Boolean(mesh.userData.fixed) && this.fixedAtomDisplayEnabled();
            const materialPreset = this.atomMaterialPreset(index);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const materialKey = this.atomMaterialCacheKey(
                color, isFixed, atomSegments, false, materialPreset, opacity
            );
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(
                    materialKey,
                    this.createAtomMaterial(color, isFixed, materialPreset, opacity)
                );
            }
            mesh.material = this.materialCache.get(materialKey);
        });
        this.requestRender();
    }

    refreshSupercellAtomColors() {
        if (!this.useInstancedAtoms || !this.supercellGroup?.children?.length) return false;
        let changed = false;
        this.supercellGroup.children.forEach(mesh => {
            const indices = mesh.userData?.atomIndices;
            const shifts = mesh.userData?.shifts;
            if (!mesh.isInstancedMesh || !Array.isArray(indices) || !Array.isArray(shifts)) return;
            let instanceId = 0;
            shifts.forEach(() => {
                indices.forEach(index => {
                    mesh.setColorAt(
                        instanceId,
                        this.fixedAdjustedColor(
                            this.atomVisualColor(index, this.customColors[index]),
                            Boolean(mesh.userData.fixed),
                            mesh.userData.materialPreset || this.atomMaterialPreset(index)
                        )
                    );
                    instanceId += 1;
                });
            });
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            changed = true;
        });
        return changed;
    }

    setAtomColorScaleColors(colors = null, { refreshBonds = true } = {}) {
        const atomCount = this.atomsData?.symbols?.length || 0;
        this.atomColorScaleColors = Array.isArray(colors) && colors.length === atomCount
            ? [...colors]
            : null;
        if (!this.atomsData) return;
        this.refreshAtomColors();
        const hasReplicas = (this.displayOptions.supercell || [1, 1, 1]).some(value => value > 1);
        if (hasReplicas) {
            if (!this.refreshSupercellAtomColors()) this.rebuildSupercell();
            else if (refreshBonds && this.displayOptions.showBonds && this.displayOptions.bondColorMode === 'split') {
                this.rebuildSupercellBonds();
            }
        }
        if (refreshBonds && this.displayOptions.showBonds && this.displayOptions.bondColorMode === 'split') {
            this.rebuildBonds();
        }
        this.requestRender();
    }

    inferBondPairs(usePeriodicImages = this.displayOptions.showPeriodicBonds) {
        if (!this.atomsData || !this.atomsData.positions) return [];
        // Interactive transforms re-run inference on every visual update. Use
        // the spatial index early enough to keep medium-sized edits responsive.
        if (this.atomsData.positions.length > 384) return this.inferBondPairsCellList(usePeriodicImages);
        const pairs = [];
        const hookeanExcluded = this.hookeanBondExclusions();
        const count = this.atomsData.positions.length;
        const cellCache = usePeriodicImages ? this.ensureCellCache() : null;
        for (let i = 0; i < count; i++) {
            if (!this.atomLabelVisible(i)) continue;
            for (let j = i + 1; j < count; j++) {
                if (!this.atomLabelVisible(j)) continue;
                if (hookeanExcluded.has(this.hookeanPairKey(i, j))) continue;
                const range = this.bondRangeForPair(i, j);
                if (!range) continue;
                const distanceSquared = this.bondDistanceSquared(
                    i, j, null, usePeriodicImages, cellCache
                );
                if (
                    distanceSquared > 0.0225
                    && distanceSquared >= range.min * range.min
                    && distanceSquared <= range.max * range.max
                ) {
                    pairs.push([i, j]);
                }
            }
        }
        return pairs;
    }

    bondCutoffForPair(i, j) {
        return this.bondRangeForPair(i, j)?.max ?? 0;
    }

    bondRangeForPair(i, j) {
        if (this.displayOptions.bondMode === 'pairwise') {
            return this.pairwiseBondRange(
                this.atomsData.symbols[i],
                this.atomsData.symbols[j]
            );
        }
        const maximum = this.autoBondCutoff(i, j);
        return Number.isFinite(maximum) && maximum > 0
            ? { min: 0, max: maximum }
            : null;
    }

    labelPairKey(a, b) {
        return [a, b].sort().join('-');
    }

    pairwiseBondCutoff(a, b) {
        return this.pairwiseBondRange(a, b)?.max ?? 0;
    }

    pairwiseBondRange(a, b) {
        const key = this.labelPairKey(a, b);
        const ranges = this.displayOptions.pairwiseBondRanges || {};
        const cutoffs = this.displayOptions.pairwiseBondCutoffs || {};
        const hasLegacyMaximum = Object.prototype.hasOwnProperty.call(cutoffs, key);
        const hasAnyLegacyCutoff = recordHasEntries(cutoffs);
        const parsedLegacyMaximum = Number(cutoffs[key]);
        const legacyMaximum = Number.isFinite(parsedLegacyMaximum)
            ? Math.max(0, parsedLegacyMaximum)
            : null;
        const source = ranges[key];
        if (source && typeof source === 'object') {
            if (hasAnyLegacyCutoff && !hasLegacyMaximum) return null;
            const maximum = Number(source.max);
            const sourceEnabled = source.enabled !== false
                && Number.isFinite(maximum)
                && maximum > 0;
            if (hasLegacyMaximum && legacyMaximum !== null) {
                const legacyEnabled = legacyMaximum > 0;
                const recordsAgree = sourceEnabled === legacyEnabled && (
                    !sourceEnabled || Math.abs(maximum - legacyMaximum) <= 1e-12
                );
                if (!recordsAgree) {
                    if (!legacyEnabled) return null;
                    return { min: 0, max: legacyMaximum };
                }
            }
            if (!sourceEnabled) return null;
            return { min: 0, max: maximum };
        }
        return legacyMaximum !== null && legacyMaximum > 0
            ? { min: 0, max: legacyMaximum }
            : null;
    }

    autoBondElementClass(symbol) {
        if (symbol === 'H') return AUTO_BOND_CLASS_HYDROGEN;
        if (METALLIC_ELEMENT_SYMBOLS.has(symbol)) return AUTO_BOND_CLASS_METAL;
        return AUTO_BOND_CLASS_COVALENT;
    }

    autoBondBaseCutoffFromValues(firstRadius, secondRadius, firstClass, secondClass) {
        if (
            (firstClass === AUTO_BOND_CLASS_HYDROGEN && secondClass === AUTO_BOND_CLASS_HYDROGEN)
            || (firstClass === AUTO_BOND_CLASS_METAL && secondClass === AUTO_BOND_CLASS_METAL)
        ) {
            return 0;
        }
        const radiusSum = firstRadius + secondRadius;
        if (
            firstClass === AUTO_BOND_CLASS_HYDROGEN
            || secondClass === AUTO_BOND_CLASS_HYDROGEN
        ) {
            return radiusSum + AUTO_BOND_HYDROGEN_SLACK;
        }
        if (
            firstClass === AUTO_BOND_CLASS_METAL
            || secondClass === AUTO_BOND_CLASS_METAL
        ) {
            return radiusSum + AUTO_BOND_METAL_LIGAND_SLACK;
        }
        return radiusSum + AUTO_BOND_COVALENT_SLACK;
    }

    autoBondCutoff(i, j) {
        const scale = Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
        const firstClass = this.autoBondElementClass(this.atomChemicalSymbol(i));
        const secondClass = this.autoBondElementClass(this.atomChemicalSymbol(j));
        return this.autoBondBaseCutoffFromValues(
            this.atomCovalentRadius(i),
            this.atomCovalentRadius(j),
            firstClass,
            secondClass
        ) * scale;
    }

    buildBondSearchContext() {
        const count = this.atomsData?.positions?.length || 0;
        const visible = new Uint8Array(count);
        for (let index = 0; index < count; index++) {
            visible[index] = this.atomLabelVisible(index) ? 1 : 0;
        }

        if (this.displayOptions.bondMode === 'pairwise') {
            const labels = this.atomsData?.symbols || [];
            const uniqueLabels = [...new Set(labels)];
            const labelIndex = new Map(
                uniqueLabels.map((label, index) => [label, index])
            );
            const labelIds = new Int32Array(count);
            for (let index = 0; index < count; index++) {
                labelIds[index] = labelIndex.get(labels[index]) ?? -1;
            }
            const matrixSize = uniqueLabels.length;
            const minimumSquared = new Float64Array(matrixSize * matrixSize);
            const cutoffSquared = new Float64Array(matrixSize * matrixSize);
            let maxCutoff = 0;
            for (let first = 0; first < matrixSize; first++) {
                for (let second = first; second < matrixSize; second++) {
                    const range = this.pairwiseBondRange(
                        uniqueLabels[first],
                        uniqueLabels[second]
                    );
                    const cutoff = range?.max || 0;
                    const minimum = range?.min || 0;
                    const minimumValueSquared = minimum * minimum;
                    const squared = cutoff * cutoff;
                    minimumSquared[first * matrixSize + second] = minimumValueSquared;
                    minimumSquared[second * matrixSize + first] = minimumValueSquared;
                    cutoffSquared[first * matrixSize + second] = squared;
                    cutoffSquared[second * matrixSize + first] = squared;
                    maxCutoff = Math.max(maxCutoff, cutoff);
                }
            }
            return {
                count,
                visible,
                pairwise: true,
                labelIds,
                matrixSize,
                minimumSquared,
                cutoffSquared,
                maxCutoff
            };
        }

        const scale = Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
        const sourceRadii = (
            this.atomsData?.visual?.bond_radii
            || this.atomsData?.visual?.covalent_radii
            || []
        );
        const chemicalSymbols = this.atomsData?.chemical_symbols || this.atomsData?.symbols || [];
        const radii = new Float64Array(count);
        const elementClasses = new Uint8Array(count);
        const maxRadiusByClass = new Float64Array(3);
        for (let index = 0; index < count; index++) {
            const value = Number(sourceRadii[index]);
            const radius = Number.isFinite(value) && value > 0
                ? value
                : FALLBACK_COVALENT_RADIUS;
            radii[index] = radius;
            const elementClass = this.autoBondElementClass(chemicalSymbols[index]);
            elementClasses[index] = elementClass;
            if (visible[index]) {
                maxRadiusByClass[elementClass] = Math.max(
                    maxRadiusByClass[elementClass],
                    radius
                );
            }
        }
        let maxCutoff = 0;
        for (let firstClass = 0; firstClass < maxRadiusByClass.length; firstClass++) {
            if (maxRadiusByClass[firstClass] <= 0) continue;
            for (let secondClass = firstClass; secondClass < maxRadiusByClass.length; secondClass++) {
                if (maxRadiusByClass[secondClass] <= 0) continue;
                maxCutoff = Math.max(
                    maxCutoff,
                    this.autoBondBaseCutoffFromValues(
                        maxRadiusByClass[firstClass],
                        maxRadiusByClass[secondClass],
                        firstClass,
                        secondClass
                    ) * scale
                );
            }
        }
        return {
            count,
            visible,
            pairwise: false,
            radii,
            elementClasses,
            scale,
            maxCutoff
        };
    }

    bondCutoffSquaredFromSearch(search, i, j) {
        if (search.pairwise) {
            const firstLabel = search.labelIds[i];
            const secondLabel = search.labelIds[j];
            return firstLabel < 0 || secondLabel < 0
                ? 0
                : search.cutoffSquared[
                    firstLabel * search.matrixSize + secondLabel
                ];
        }
        const cutoff = this.autoBondBaseCutoffFromValues(
            search.radii[i],
            search.radii[j],
            search.elementClasses[i],
            search.elementClasses[j]
        ) * search.scale;
        return cutoff * cutoff;
    }

    bondMinimumSquaredFromSearch(search, i, j) {
        if (!search.pairwise) return 0;
        const firstLabel = search.labelIds[i];
        const secondLabel = search.labelIds[j];
        return firstLabel < 0 || secondLabel < 0
            ? 0
            : search.minimumSquared[
                firstLabel * search.matrixSize + secondLabel
            ];
    }

    reusableBondNeighborCandidates(search, usePeriodicImages) {
        const cache = this.bondNeighborCache;
        const pbc = this.atomsData?.pbc || [false, false, false];
        if (
            !cache
            || cache.count !== search.count
            || cache.usePeriodicImages !== usePeriodicImages
            || cache.cellSource !== this.atomsData?.cell
            || cache.pbc[0] !== Boolean(pbc[0])
            || cache.pbc[1] !== Boolean(pbc[1])
            || cache.pbc[2] !== Boolean(pbc[2])
            || Math.abs(cache.maxCutoff - search.maxCutoff) > 1e-12
        ) {
            return null;
        }
        const thresholdSquared = (cache.skin * 0.5) ** 2;
        for (let index = 0; index < search.count; index++) {
            if (!search.visible[index]) continue;
            const position = this.atomMeshByIndex.get(index)?.position;
            if (!position) return null;
            const offset = index * 3;
            const dx = position.x - cache.referencePositions[offset];
            const dy = position.y - cache.referencePositions[offset + 1];
            const dz = position.z - cache.referencePositions[offset + 2];
            if (dx * dx + dy * dy + dz * dz > thresholdSquared) return null;
        }
        return cache.candidatePairs;
    }

    cacheBondNeighborCandidates(
        candidatePairs,
        search,
        usePeriodicImages,
        skin
    ) {
        const referencePositions = new Float32Array(search.count * 3);
        for (let index = 0; index < search.count; index++) {
            const position = this.atomMeshByIndex.get(index)?.position;
            if (!position) continue;
            const offset = index * 3;
            referencePositions[offset] = position.x;
            referencePositions[offset + 1] = position.y;
            referencePositions[offset + 2] = position.z;
        }
        const pbc = this.atomsData?.pbc || [false, false, false];
        this.bondNeighborCache = {
            count: search.count,
            search,
            usePeriodicImages,
            cellSource: this.atomsData?.cell,
            pbc: [Boolean(pbc[0]), Boolean(pbc[1]), Boolean(pbc[2])],
            maxCutoff: search.maxCutoff,
            skin,
            referencePositions,
            candidatePairs
        };
    }

    filterBondNeighborCandidates(candidatePairs, search, usePeriodicImages) {
        const pairs = [];
        const cellCache = usePeriodicImages ? this.ensureCellCache() : null;
        for (let offset = 0; offset < candidatePairs.length; offset += 2) {
            const i = candidatePairs[offset];
            const j = candidatePairs[offset + 1];
            const minimumSquared = this.bondMinimumSquaredFromSearch(search, i, j);
            const cutoffSquared = this.bondCutoffSquaredFromSearch(search, i, j);
            if (!Number.isFinite(cutoffSquared) || cutoffSquared <= 0) continue;
            const distanceSquared = this.bondDistanceSquared(
                i,
                j,
                this.atomMeshByIndex.get(i)?.position || null,
                usePeriodicImages,
                cellCache
            );
            if (
                distanceSquared > 0.0225
                && distanceSquared >= minimumSquared
                && distanceSquared <= cutoffSquared
            ) {
                pairs.push([i, j]);
            }
        }
        return pairs;
    }

    inferBondPairsCellList(usePeriodicImages = this.displayOptions.showPeriodicBonds) {
        const count = this.atomsData?.positions?.length || 0;
        if (!count) return [];
        const search = this.bondNeighborCache?.search || this.buildBondSearchContext();
        const maxCutoff = search.maxCutoff;
        if (!Number.isFinite(maxCutoff) || maxCutoff <= 0) return [];

        const cachedCandidates = this.reusableBondNeighborCandidates(
            search,
            usePeriodicImages
        );
        if (cachedCandidates) {
            return this.filterBondNeighborCandidates(
                cachedCandidates,
                search,
                usePeriodicImages
            );
        }

        const skin = Math.max(0.35, maxCutoff * 0.2);
        const neighborRadius = maxCutoff + skin;
        const candidatePairs = [];
        const hookeanExcluded = this.hookeanBondExclusions();
        const pbc = this.atomsData?.pbc || [false, false, false];
        const cellCache = this.hasValidCell() ? this.ensureCellCache() : null;
        const basis = cellCache?.valid ? cellCache.basis : null;
        const reciprocal = cellCache?.valid ? cellCache.reciprocal : null;
        const useFractionalGrid = Boolean(
            usePeriodicImages && basis && reciprocal && pbc.some(Boolean)
        );
        const positions = new Array(count);
        const sortable = [];

        if (useFractionalGrid) {
            // |b_i| converts a Cartesian cutoff to its maximum fractional
            // extent along cell coordinate i. This remains valid for skewed
            // and monoclinic cells, unlike direct lattice-vector lengths.
            const bins = reciprocal.map(vector => {
                const fractionalExtent = Math.max(
                    1e-12,
                    neighborRadius * vector.length()
                );
                return Math.max(1, Math.floor(1 / fractionalExtent));
            });
            for (let i = 0; i < count; i++) {
                if (!search.visible[i]) continue;
                const pos = this.atomMeshByIndex.get(i)?.position || this.getAtomPosition(i);
                positions[i] = pos;
                const frac = this.cartToFrac(pos, basis, reciprocal);
                for (let axis = 0; axis < 3; axis++) {
                    if (pbc[axis]) {
                        const value = frac.getComponent(axis);
                        frac.setComponent(axis, value - Math.floor(value));
                    }
                }
                const ix = Math.floor(frac.x * bins[0]);
                const iy = Math.floor(frac.y * bins[1]);
                const iz = Math.floor(frac.z * bins[2]);
                sortable.push({ index: i, ix, iy, iz });
            }
            this.collectBondPairsFromCells(
                sortable,
                bins,
                positions,
                hookeanExcluded,
                candidatePairs,
                pbc,
                usePeriodicImages,
                search,
                neighborRadius * neighborRadius
            );
            this.cacheBondNeighborCandidates(
                candidatePairs,
                search,
                usePeriodicImages,
                skin
            );
            return this.filterBondNeighborCandidates(
                candidatePairs,
                search,
                usePeriodicImages
            );
        }

        const box = new THREE.Box3();
        for (let i = 0; i < count; i++) {
            if (!search.visible[i]) continue;
            const pos = this.atomMeshByIndex.get(i)?.position || this.getAtomPosition(i);
            positions[i] = pos;
            box.expandByPoint(pos);
        }
        if (box.isEmpty()) return [];
        const min = box.min;
        const size = new THREE.Vector3();
        box.getSize(size);
        const bins = [
            Math.max(1, Math.floor(size.x / neighborRadius)),
            Math.max(1, Math.floor(size.y / neighborRadius)),
            Math.max(1, Math.floor(size.z / neighborRadius))
        ];
        for (let i = 0; i < count; i++) {
            const pos = positions[i];
            if (!pos) continue;
            const ix = Math.max(0, Math.min(bins[0] - 1, Math.floor((pos.x - min.x) / neighborRadius)));
            const iy = Math.max(0, Math.min(bins[1] - 1, Math.floor((pos.y - min.y) / neighborRadius)));
            const iz = Math.max(0, Math.min(bins[2] - 1, Math.floor((pos.z - min.z) / neighborRadius)));
            sortable.push({
                index: i,
                ix,
                iy,
                iz
            });
        }
        this.collectBondPairsFromCells(
            sortable,
            bins,
            positions,
            hookeanExcluded,
            candidatePairs,
            [false, false, false],
            usePeriodicImages,
            search,
            neighborRadius * neighborRadius
        );
        this.cacheBondNeighborCandidates(
            candidatePairs,
            search,
            usePeriodicImages,
            skin
        );
        return this.filterBondNeighborCandidates(
            candidatePairs,
            search,
            usePeriodicImages
        );
    }

    collectBondPairsFromCells(
        items,
        bins,
        positions,
        hookeanExcluded,
        pairs,
        periodicAxes = [false, false, false],
        usePeriodicImages = false,
        search = this.buildBondSearchContext(),
        candidateRadiusSquared = null
    ) {
        const cells = new Map();
        const keyOf = (ix, iy, iz) => ix + bins[0] * (iy + bins[1] * iz);
        const wrap = (value, size, axis) => {
            if (!periodicAxes[axis]) return value;
            return ((value % size) + size) % size;
        };
        for (const item of items) {
            const key = keyOf(item.ix, item.iy, item.iz);
            if (!cells.has(key)) cells.set(key, []);
            cells.get(key).push(item.index);
        }

        const neighborBuckets = new Map();
        const bucketsFor = item => {
            const sourceKey = keyOf(item.ix, item.iy, item.iz);
            if (neighborBuckets.has(sourceKey)) return neighborBuckets.get(sourceKey);
            const buckets = [];
            const visitedCells = new Set();
            for (let dx = -1; dx <= 1; dx++) {
                const ix = wrap(item.ix + dx, bins[0], 0);
                if (!periodicAxes[0] && (ix < 0 || ix >= bins[0])) continue;
                for (let dy = -1; dy <= 1; dy++) {
                    const iy = wrap(item.iy + dy, bins[1], 1);
                    if (!periodicAxes[1] && (iy < 0 || iy >= bins[1])) continue;
                    for (let dz = -1; dz <= 1; dz++) {
                        const iz = wrap(item.iz + dz, bins[2], 2);
                        if (!periodicAxes[2] && (iz < 0 || iz >= bins[2])) continue;
                        const cellKey = keyOf(ix, iy, iz);
                        if (visitedCells.has(cellKey)) continue;
                        visitedCells.add(cellKey);
                        const bucket = cells.get(cellKey);
                        if (bucket) buckets.push(bucket);
                    }
                }
            }
            neighborBuckets.set(sourceKey, buckets);
            return buckets;
        };

        for (const item of items) {
            const i = item.index;
            if (!positions[i]) continue;
            for (const bucket of bucketsFor(item)) {
                for (const j of bucket) {
                    if (j <= i || hookeanExcluded.has(i * search.count + j)) continue;
                    const cutoffSquared = candidateRadiusSquared
                        ?? this.bondCutoffSquaredFromSearch(search, i, j);
                    const minimumSquared = candidateRadiusSquared === null
                        ? this.bondMinimumSquaredFromSearch(search, i, j)
                        : 0;
                    if (!Number.isFinite(cutoffSquared) || cutoffSquared <= 0) continue;
                    const distanceSquared = this.bondDistanceSquared(
                        i,
                        j,
                        positions[i],
                        usePeriodicImages,
                        usePeriodicImages ? this.cellCache : null
                    );
                    if (
                        distanceSquared > 0.0225
                        && distanceSquared >= minimumSquared
                        && distanceSquared <= cutoffSquared
                    ) {
                        if (candidateRadiusSquared === null) pairs.push([i, j]);
                        else pairs.push(i, j);
                    }
                }
            }
        }
    }

    bondPairsEqual(a = [], b = []) {
        if (a.length !== b.length) return false;
        for (let index = 0; index < a.length; index++) {
            if (a[index][0] !== b[index][0] || a[index][1] !== b[index][1]) return false;
        }
        return true;
    }

    inferCurrentBondTopology() {
        const repeats = this.displayOptions.supercell || [1, 1, 1];
        if (this.displayOptions.bondMode === 'manual') {
            return {
                pairs: null,
                bridgeRecords: this.inferSupercellBridgeBondRecords(repeats)
            };
        }
        if (!this.needsSupercellBridgeBonds(repeats)) {
            return {
                pairs: this.inferBondPairs(),
                bridgeRecords: []
            };
        }

        const periodicPairs = this.inferBondPairs(true);
        const directPairs = periodicPairs.filter(([i, j]) => {
            const range = this.bondRangeForPair(i, j);
            if (!range) return false;
            const distanceSquared = this.bondDistanceSquared(i, j);
            return (
                distanceSquared > 0.0225
                && distanceSquared >= range.min * range.min
                && distanceSquared <= range.max * range.max
            );
        });
        return {
            pairs: directPairs,
            bridgeRecords: this.inferSupercellBridgeBondRecords(repeats, periodicPairs)
        };
    }

    refreshBondsForCurrentPositions() {
        if (!this.displayOptions.showBonds) return;
        const topology = this.inferCurrentBondTopology();
        const nextBridgeRecords = topology.bridgeRecords;
        if (this.displayOptions.bondMode === 'manual') {
            if (this.supercellBridgeBondRecordsEqual(
                nextBridgeRecords, this.supercellBridgeBondRecords
            )) {
                this.updateBondPositions();
            } else {
                this.rebuildBonds(null, nextBridgeRecords);
            }
            return;
        }
        const nextPairs = topology.pairs;
        const bridgeRecordsEqual = this.supercellBridgeBondRecordsEqual(
            nextBridgeRecords, this.supercellBridgeBondRecords
        );
        if (this.bondPairsEqual(nextPairs, this.bondPairs || []) && bridgeRecordsEqual) {
            this.updateBondPositions();
        } else {
            this.rebuildBonds(nextPairs, nextBridgeRecords);
        }
    }

    clearDisplacementVectors({ keepData = false } = {}) {
        this.clearGroup(this.displacementGroup);
        if (!keepData) this.displacementData = null;
        this.displacementCameraSignature = '';
        this.domElement.dataset.displacementCount = '0';
        this.requestRender();
    }

    clearForceVectors({ keepData = false } = {}) {
        this.clearGroup(this.forceVectorGroup);
        this.forceVectorGroup.userData = {};
        if (!keepData) this.forceVectorData = null;
        this.forceVectorCameraSignature = '';
        this.domElement.dataset.forceVectorCount = '0';
        this.requestRender();
    }

    clearVolumetricSurfaces() {
        if (!this.volumetricGroup) return;
        while (this.volumetricGroup.children.length) {
            this.volumetricGroup.remove(this.volumetricGroup.children[0]);
        }
        this.volumetricSurfaces.forEach(surface => {
            surface.geometry?.dispose?.();
            surface.material?.dispose?.();
        });
        this.volumetricSurfaces = [];
        this.domElement.dataset.volumetricSurfaceCount = '0';
        this.requestRender();
    }

    setVolumetricSurfaceVisibility(visible) {
        if (!this.volumetricGroup) return;
        this.volumetricGroup.visible = visible === true;
        this.requestRender();
    }

    disposeVolumetricPlaneRecord(record) {
        if (!record) return;
        record.geometry?.dispose?.();
        record.texture?.dispose?.();
        record.material?.dispose?.();
        record.perimeterGeometry?.dispose?.();
        record.perimeterMaterial?.dispose?.();
    }

    clearVolumetricPlanes(planeIds = null) {
        const requested = planeIds ? new Set(planeIds) : null;
        [...this.volumetricPlanes.entries()].forEach(([planeId, record]) => {
            if (requested && !requested.has(planeId)) return;
            record.group?.removeFromParent?.();
            this.disposeVolumetricPlaneRecord(record);
            this.volumetricPlanes.delete(planeId);
        });
        this.domElement.dataset.volumetricPlaneCount = String(this.volumetricPlanes.size);
        this.invalidateSunShadowBounds();
        this.requestRender();
    }

    setVolumetricPlaneSlice(specification = {}) {
        const planeId = String(specification.planeId || '');
        if (!planeId) return;
        this.clearVolumetricPlanes([planeId]);
        const vertices = Array.isArray(specification.polygonVertices)
            ? specification.polygonVertices
            : [];
        const uv = Array.isArray(specification.polygonUv) ? specification.polygonUv : [];
        if (vertices.length < 3 || uv.length !== vertices.length) return;

        const positions = new Float32Array(vertices.length * 3);
        const textureCoordinates = new Float32Array(vertices.length * 2);
        vertices.forEach((vertex, index) => {
            positions.set(vertex.slice(0, 3).map(value => Number(value) || 0), index * 3);
            textureCoordinates.set(uv[index].slice(0, 2).map(value => Number(value) || 0), index * 2);
        });
        const indices = [];
        for (let index = 1; index < vertices.length - 1; index++) {
            indices.push(0, index, index + 1);
        }
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('uv', new THREE.BufferAttribute(textureCoordinates, 2));
        geometry.setIndex(indices);
        geometry.computeVertexNormals();
        geometry.computeBoundingSphere();

        const width = Math.max(2, Number(specification.width) || 2);
        const height = Math.max(2, Number(specification.height) || 2);
        const rgba = specification.rgba instanceof Uint8Array
            ? specification.rgba
            : new Uint8Array(specification.rgba || []);
        const texture = new THREE.DataTexture(
            rgba,
            width,
            height,
            THREE.RGBAFormat,
            THREE.UnsignedByteType
        );
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.generateMipmaps = false;
        texture.flipY = false;
        texture.needsUpdate = true;

        const opacity = Math.max(0.05, Math.min(1, Number(specification.opacity) || 0.88));
        const material = new THREE.MeshBasicMaterial({
            map: texture,
            side: THREE.DoubleSide,
            transparent: opacity < 0.999,
            opacity,
            depthWrite: opacity >= 0.98,
            toneMapped: false
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.name = `v_ase_volumetric_plane_${planeId}`;
        mesh.renderOrder = 14;
        mesh.userData = { volumetricPlane: true, planeId };

        const perimeterPositions = new Float32Array((vertices.length + 1) * 3);
        vertices.forEach((vertex, index) => {
            perimeterPositions.set(vertex.slice(0, 3).map(value => Number(value) || 0), index * 3);
        });
        perimeterPositions.set(vertices[0].slice(0, 3).map(value => Number(value) || 0), vertices.length * 3);
        const perimeterGeometry = new THREE.BufferGeometry();
        perimeterGeometry.setAttribute('position', new THREE.BufferAttribute(perimeterPositions, 3));
        const perimeterMaterial = new THREE.LineBasicMaterial({
            color: specification.selected ? '#f4be54' : '#89d9cc',
            transparent: true,
            opacity: specification.selected ? 0.98 : 0.72,
            depthTest: true,
            toneMapped: false
        });
        const perimeter = new THREE.Line(perimeterGeometry, perimeterMaterial);
        perimeter.renderOrder = 15;
        perimeter.userData = { volumetricPlanePerimeter: true, planeId };

        const group = new THREE.Group();
        group.add(mesh, perimeter);
        group.visible = specification.visible !== false;
        group.userData = { volumetricPlane: true, planeId };
        this.volumetricPlaneGroup.add(group);
        this.volumetricPlaneGroup.position.copy(this.visualTranslationVector());
        const record = {
            ...specification,
            planeId,
            group,
            mesh,
            geometry,
            texture,
            material,
            perimeter,
            perimeterGeometry,
            perimeterMaterial,
            centroid: new THREE.Vector3(...(specification.centroid || [0, 0, 0])),
            normal: new THREE.Vector3(...(specification.normal || [0, 0, 1])).normalize()
        };
        this.volumetricPlanes.set(planeId, record);
        this.domElement.dataset.volumetricPlaneCount = String(this.volumetricPlanes.size);
        this.invalidateSunShadowBounds();
        this.requestRender();
    }

    updateVolumetricPlaneTexture(planeId, rgba, { opacity = null } = {}) {
        const record = this.volumetricPlanes.get(String(planeId));
        if (!record || !(rgba instanceof Uint8Array)) return;
        record.texture.image.data = rgba;
        record.texture.needsUpdate = true;
        if (opacity !== null) {
            const alpha = Math.max(0.05, Math.min(1, Number(opacity) || 0.88));
            record.material.opacity = alpha;
            record.material.transparent = alpha < 0.999;
            record.material.depthWrite = alpha >= 0.98;
            record.material.needsUpdate = true;
        }
        this.requestRender();
    }

    setVolumetricPlaneSelection(planeIds = []) {
        const selected = new Set(planeIds);
        this.volumetricPlanes.forEach((record, planeId) => {
            const active = selected.has(planeId);
            record.selected = active;
            record.perimeterMaterial.color.set(active ? '#f4be54' : '#89d9cc');
            record.perimeterMaterial.opacity = active ? 0.98 : 0.72;
            record.perimeterMaterial.needsUpdate = true;
        });
        this.requestRender();
    }

    pickVolumetricPlane(event) {
        if (!event || !this.volumetricPlanes.size) return null;
        this.sunRaycaster.setFromCamera(this.sunPointerNdc(event), this.camera);
        const meshes = [...this.volumetricPlanes.values()]
            .filter(record => record.group.visible)
            .map(record => record.mesh);
        const hit = this.sunRaycaster.intersectObjects(meshes, false)[0];
        return hit?.object?.userData?.planeId || null;
    }

    previewVolumetricPlaneTransforms(transforms = {}) {
        this.volumetricPlanes.forEach((record, planeId) => {
            record.group.position.set(0, 0, 0);
            record.group.quaternion.identity();
            const transform = transforms[planeId];
            if (!transform) return;
            if (Array.isArray(transform.translation)) {
                record.group.position.add(new THREE.Vector3(...transform.translation));
            }
            if (Array.isArray(transform.quaternion) && transform.quaternion.length === 4) {
                const quaternion = new THREE.Quaternion(...transform.quaternion).normalize();
                const pivot = new THREE.Vector3(...(transform.pivot || record.centroid.toArray()));
                record.group.quaternion.copy(quaternion);
                record.group.position.add(pivot.clone().sub(pivot.clone().applyQuaternion(quaternion)));
            }
        });
        this.requestRender();
    }

    resetVolumetricPlaneTransforms() {
        this.volumetricPlanes.forEach(record => {
            record.group.position.set(0, 0, 0);
            record.group.quaternion.identity();
        });
        this.requestRender();
    }

    setVolumetricSurfaces(specifications = []) {
        this.clearVolumetricSurfaces();
        this.volumetricSurfaces = specifications.map(specification => {
            const vertices = specification.vertices instanceof Float32Array
                ? specification.vertices
                : new Float32Array(specification.vertices || []);
            const faces = specification.faces instanceof Uint32Array
                ? specification.faces
                : new Uint32Array(specification.faces || []);
            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
            geometry.setIndex(new THREE.BufferAttribute(faces, 1));
            geometry.computeVertexNormals();
            geometry.computeBoundingSphere();
            const opacity = Math.max(0.05, Math.min(1, Number(specification.opacity) || 0.72));
            const material = new THREE.MeshStandardMaterial({
                color: this.validHexColor(specification.color) ? specification.color : '#2f8fdb',
                side: THREE.DoubleSide,
                transparent: opacity < 0.999,
                opacity,
                depthWrite: opacity >= 0.96,
                roughness: 0.42,
                metalness: 0.04
            });
            return {
                ...specification,
                cell: (specification.cell || []).map(vector => [...vector]),
                geometry,
                material
            };
        });
        this.rebuildVolumetricSurfaces();
        this.setVolumetricSurfaceVisibility(this.displayOptions.showVolumetric === true);
    }

    updateVolumetricSurfaceStyle({
        positiveColor = '#2f8fdb',
        negativeColor = '#e05b78',
        opacity = 0.72
    } = {}) {
        const alpha = Math.max(0.05, Math.min(1, Number(opacity) || 0.72));
        this.volumetricSurfaces.forEach(surface => {
            const color = Number(surface.level) < 0 ? negativeColor : positiveColor;
            if (this.validHexColor(color)) surface.material.color.set(color);
            surface.material.opacity = alpha;
            surface.material.transparent = alpha < 0.999;
            surface.material.depthWrite = alpha >= 0.96;
            surface.material.needsUpdate = true;
            surface.color = color;
            surface.opacity = alpha;
        });
        this.invalidateSunShadowBounds();
        if (this.shadowModeActive) this.fitSunShadowCamera();
        this.requestRender();
    }

    rebuildVolumetricSurfaces() {
        if (!this.volumetricGroup) return;
        while (this.volumetricGroup.children.length) {
            this.volumetricGroup.remove(this.volumetricGroup.children[0]);
        }
        const repetitions = this.displayOptions.supercell || [1, 1, 1];
        let count = 0;
        this.volumetricSurfaces.forEach(surface => {
            const cell = surface.cell?.length === 3
                ? surface.cell.map(vector => new THREE.Vector3(...vector))
                : null;
            const translations = [{ cellOffset: [0, 0, 0], vector: new THREE.Vector3() }];
            if (cell) translations.push(...this.supercellTranslations(cell, repetitions));
            translations.forEach(translation => {
                const mesh = new THREE.Mesh(surface.geometry, surface.material);
                mesh.position.copy(translation.vector);
                mesh.userData = {
                    volumetricSurface: true,
                    datasetId: surface.datasetId,
                    level: surface.level,
                    cellOffset: translation.cellOffset,
                    sharedGeometry: true,
                    sharedMaterial: true
                };
                mesh.castShadow = Boolean(this.shadowModeActive);
                mesh.receiveShadow = Boolean(this.shadowModeActive);
                this.volumetricGroup.add(mesh);
                count++;
            });
        });
        this.volumetricGroup.position.copy(this.visualTranslationVector());
        this.volumetricGroup.visible = this.displayOptions.showVolumetric === true;
        this.domElement.dataset.volumetricSurfaceCount = String(count);
        this.invalidateSunShadowBounds();
        this.applyShadowFlags();
        this.requestRender();
    }

    displacementStyle(options = this.displayOptions) {
        return options?.atomDisplayMode === '2d' || options?.displacementStyle === '2d'
            ? '2d'
            : '3d';
    }

    displacementCameraKey() {
        const quaternion = (this.flatOrientationCamera || this.camera).quaternion;
        return [
            quaternion.x.toFixed(5),
            quaternion.y.toFixed(5),
            quaternion.z.toFixed(5),
            quaternion.w.toFixed(5)
        ].join(':');
    }

    setDisplacementVectors(data, options = this.displayOptions) {
        this.clearGroup(this.displacementGroup);
        this.displacementCameraSignature = '';
        this.displacementData = data?.status === 'ok' ? data : null;
        const enabled = options?.showDisplacements === true;
        if (!enabled || !this.displacementData) {
            this.domElement.dataset.displacementCount = '0';
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }

        const starts = this.displacementData.starts || [];
        const vectors = this.displacementData.vectors || [];
        const indices = this.displacementData.indices || [];
        const entries = [];
        const displacementTranslations = [{
            cellOffset: [0, 0, 0],
            vector: new THREE.Vector3()
        }];
        const repetitions = options?.supercell || [1, 1, 1];
        if (this.hasValidCell() && repetitions.some(value => Number(value) > 1)) {
            const cell = this.atomsData.cell.map(vector => new THREE.Vector3(...vector));
            displacementTranslations.push(...this.supercellTranslations(cell, repetitions));
        }
        const count = Math.min(starts.length, vectors.length, indices.length);
        for (let item = 0; item < count; item++) {
            const index = Number(indices[item]);
            const start = starts[item];
            const vector = vectors[item];
            if (
                !Number.isInteger(index)
                || !this.atomLabelVisible(index)
                || !Array.isArray(start)
                || !Array.isArray(vector)
                || start.length < 3
                || vector.length < 3
            ) {
                continue;
            }
            const magnitudeSquared = Number(vector[0]) ** 2 + Number(vector[1]) ** 2 + Number(vector[2]) ** 2;
            if (!Number.isFinite(magnitudeSquared) || magnitudeSquared < 1e-14) continue;
            const visibleStart = this.atomMeshByIndex.get(index)?.position;
            const baseStart = visibleStart
                ? visibleStart.clone()
                : new THREE.Vector3(...start.map(Number));
            displacementTranslations.forEach(translation => {
                const cellReference = translation.cellOffset.some(Boolean)
                    ? translation.cellOffset
                    : null;
                if (!this.atomReferenceVisible(index, cellReference)) return;
                entries.push({
                    index,
                    cellOffset: [...translation.cellOffset],
                    start: baseStart.clone().add(translation.vector).toArray(),
                    vector: vector.map(Number)
                });
            });
        }

        if (!entries.length) {
            this.domElement.dataset.displacementCount = '0';
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }

        const flat = this.displacementStyle(options) === '2d';
        const color = this.validHexColor(options?.displacementColor)
            ? options.displacementColor
            : '#e58b2a';
        const material = flat
            ? new THREE.MeshBasicMaterial({
                color,
                side: THREE.DoubleSide,
                toneMapped: false,
                depthTest: true,
                depthWrite: false
            })
            : new THREE.MeshStandardMaterial({
                color,
                roughness: 0.42,
                metalness: 0.04
            });
        const headMaterial = material.clone();
        const shaft = new THREE.InstancedMesh(
            flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
            material,
            entries.length
        );
        const head = new THREE.InstancedMesh(
            flat ? this.displacementFlatHeadGeometry : this.displacementConeGeometry,
            headMaterial,
            entries.length
        );
        [shaft, head].forEach(mesh => {
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.frustumCulled = false;
            mesh.renderOrder = 5;
            mesh.castShadow = false;
            mesh.receiveShadow = false;
            mesh.userData.sharedGeometry = true;
        });
        shaft.userData.displacementRole = 'shaft';
        head.userData.displacementRole = 'head';
        this.displacementGroup.userData.entries = entries;
        this.displacementGroup.userData.shaft = shaft;
        this.displacementGroup.userData.head = head;
        this.displacementGroup.userData.flat = flat;
        this.displacementGroup.add(shaft, head);
        this.updateDisplacementVectorMatrices(true);
        this.domElement.dataset.displacementCount = String(entries.length);
        this.applyOverlayVisibility();
        this.requestRender();
    }

    updateDisplacementVectorMatrices(force = false) {
        const entries = this.displacementGroup?.userData?.entries;
        const shaft = this.displacementGroup?.userData?.shaft;
        const head = this.displacementGroup?.userData?.head;
        if (!entries?.length || !shaft || !head) return;
        const flat = this.displacementGroup.userData.flat === true;
        const cameraSignature = flat ? this.displacementCameraKey() : '3d';
        if (!force && cameraSignature === this.displacementCameraSignature) return;
        this.displacementCameraSignature = cameraSignature;
        const scale = Math.max(0.05, Math.min(10, Number(this.displayOptions.displacementScale) || 1));
        const thickness = Math.max(
            0.01,
            Math.min(0.5, Number(this.displayOptions.displacementThickness) || 0.08)
        );
        const dummy = this.displacementDummy;

        entries.forEach((entry, instanceId) => {
            this.displacementStart.fromArray(entry.start);
            this.displacementDirection.fromArray(entry.vector).multiplyScalar(scale);
            const length = this.displacementDirection.length();
            if (length < 1e-7) {
                dummy.position.set(0, 0, 0);
                dummy.scale.setScalar(0);
                dummy.updateMatrix();
                shaft.setMatrixAt(instanceId, dummy.matrix);
                head.setMatrixAt(instanceId, dummy.matrix);
                return;
            }
            const direction = this.displacementDirection.normalize();
            this.displacementEnd.copy(this.displacementStart).addScaledVector(direction, length);
            const headLength = Math.min(length * 0.45, Math.max(thickness * 4.2, 0.08));
            const headWidth = Math.max(thickness * 2.7, headLength * 0.48);
            const bodyLength = Math.max(1e-7, length - headLength * 0.72);

            dummy.position.copy(this.displacementStart).addScaledVector(direction, bodyLength * 0.5);
            if (flat) {
                dummy.scale.set(thickness, bodyLength, 1);
                this.orientFlatBond(dummy, direction);
            } else {
                dummy.scale.set(thickness, bodyLength, thickness);
                dummy.quaternion.setFromUnitVectors(this.yAxis, direction);
            }
            dummy.updateMatrix();
            shaft.setMatrixAt(instanceId, dummy.matrix);

            dummy.position.copy(this.displacementEnd).addScaledVector(direction, -headLength * 0.5);
            if (flat) {
                dummy.scale.set(headWidth, headLength, 1);
                this.orientFlatBond(dummy, direction);
            } else {
                dummy.scale.set(headWidth, headLength, headWidth);
                dummy.quaternion.setFromUnitVectors(this.yAxis, direction);
            }
            dummy.updateMatrix();
            head.setMatrixAt(instanceId, dummy.matrix);
        });
        shaft.instanceMatrix.needsUpdate = true;
        head.instanceMatrix.needsUpdate = true;
    }

    forceVectorStyle(options = this.displayOptions) {
        return options?.atomDisplayMode === '2d' || options?.forceVectorStyle === '2d'
            ? '2d'
            : '3d';
    }

    setForceVectors(forces, options = this.displayOptions) {
        this.clearGroup(this.forceVectorGroup);
        this.forceVectorGroup.userData = {};
        this.forceVectorCameraSignature = '';
        this.forceVectorData = Array.isArray(forces) ? forces : null;
        if (options?.showForceVectors !== true || !this.forceVectorData?.length) {
            this.domElement.dataset.forceVectorCount = '0';
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }

        const translations = [{ cellOffset: [0, 0, 0], vector: new THREE.Vector3() }];
        const repetitions = options?.supercell || [1, 1, 1];
        if (this.hasValidCell() && repetitions.some(value => Number(value) > 1)) {
            const cell = this.atomsData.cell.map(vector => new THREE.Vector3(...vector));
            translations.push(...this.supercellTranslations(cell, repetitions));
        }
        const entries = [];
        this.forceVectorData.forEach((vector, index) => {
            if (
                !this.atomLabelVisible(index)
                || !Array.isArray(vector)
                || vector.length < 3
                || !vector.slice(0, 3).every(value => Number.isFinite(Number(value)))
            ) return;
            const values = vector.slice(0, 3).map(Number);
            const magnitudeSquared = values.reduce((sum, value) => sum + value * value, 0);
            if (magnitudeSquared < 1e-14) return;
            translations.forEach(translation => {
                const cellReference = translation.cellOffset.some(Boolean)
                    ? translation.cellOffset
                    : null;
                if (!this.atomReferenceVisible(index, cellReference)) return;
                entries.push({
                    index,
                    cellOffset: [...translation.cellOffset],
                    translation: translation.vector.toArray(),
                    vector: values
                });
            });
        });
        if (!entries.length) {
            this.domElement.dataset.forceVectorCount = '0';
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }

        const flat = this.forceVectorStyle(options) === '2d';
        const color = this.validHexColor(options?.forceVectorColor)
            ? options.forceVectorColor
            : '#c43f5e';
        const material = flat
            ? new THREE.MeshBasicMaterial({
                color,
                side: THREE.DoubleSide,
                toneMapped: false,
                depthTest: true,
                depthWrite: false
            })
            : new THREE.MeshStandardMaterial({
                color,
                roughness: 0.36,
                metalness: 0.03
            });
        const shaft = new THREE.InstancedMesh(
            flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
            material,
            entries.length
        );
        const head = new THREE.InstancedMesh(
            flat ? this.displacementFlatHeadGeometry : this.displacementConeGeometry,
            material.clone(),
            entries.length
        );
        [shaft, head].forEach(mesh => {
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.frustumCulled = false;
            mesh.renderOrder = 6;
            mesh.castShadow = false;
            mesh.receiveShadow = false;
            mesh.userData.sharedGeometry = true;
        });
        shaft.userData.forceVectorRole = 'shaft';
        head.userData.forceVectorRole = 'head';
        Object.assign(this.forceVectorGroup.userData, { entries, shaft, head, flat });
        this.forceVectorGroup.add(shaft, head);
        this.updateForceVectorMatrices(true);
        this.domElement.dataset.forceVectorCount = String(entries.length);
        this.applyOverlayVisibility();
        this.requestRender();
    }

    updateForceVectorMatrices(force = false) {
        const entries = this.forceVectorGroup?.userData?.entries;
        const shaft = this.forceVectorGroup?.userData?.shaft;
        const head = this.forceVectorGroup?.userData?.head;
        if (!entries?.length || !shaft || !head) return;
        const flat = this.forceVectorGroup.userData.flat === true;
        const cameraSignature = flat ? this.displacementCameraKey() : '3d';
        if (!force && cameraSignature === this.forceVectorCameraSignature) return;
        this.forceVectorCameraSignature = cameraSignature;
        const scale = Math.max(0.02, Math.min(5, Number(this.displayOptions.forceVectorScale) || 1));
        const thickness = Math.max(
            0.01,
            Math.min(0.5, Number(this.displayOptions.forceVectorThickness) || 0.08)
        );
        const dummy = this.displacementDummy;
        entries.forEach((entry, instanceId) => {
            const atom = this.atomMeshByIndex.get(entry.index);
            const cellReference = entry.cellOffset?.some(Boolean) ? entry.cellOffset : null;
            if (!atom || !this.atomReferenceVisible(entry.index, cellReference)) {
                dummy.position.set(0, 0, 0);
                dummy.scale.setScalar(0);
                dummy.updateMatrix();
                shaft.setMatrixAt(instanceId, dummy.matrix);
                head.setMatrixAt(instanceId, dummy.matrix);
                return;
            }
            this.displacementStart.copy(atom.position).add(
                new THREE.Vector3(...entry.translation)
            );
            this.displacementDirection.fromArray(entry.vector).multiplyScalar(scale);
            const length = this.displacementDirection.length();
            if (length < 1e-7) {
                dummy.position.set(0, 0, 0);
                dummy.scale.setScalar(0);
                dummy.updateMatrix();
                shaft.setMatrixAt(instanceId, dummy.matrix);
                head.setMatrixAt(instanceId, dummy.matrix);
                return;
            }
            const direction = this.displacementDirection.normalize();
            this.displacementEnd.copy(this.displacementStart).addScaledVector(direction, length);
            const headLength = Math.min(length * 0.45, Math.max(thickness * 4.2, 0.08));
            const headWidth = Math.max(thickness * 2.7, headLength * 0.48);
            const bodyLength = Math.max(1e-7, length - headLength * 0.72);

            dummy.position.copy(this.displacementStart).addScaledVector(direction, bodyLength * 0.5);
            if (flat) {
                dummy.scale.set(thickness, bodyLength, 1);
                this.orientFlatBond(dummy, direction);
            } else {
                dummy.scale.set(thickness, bodyLength, thickness);
                dummy.quaternion.setFromUnitVectors(this.yAxis, direction);
            }
            dummy.updateMatrix();
            shaft.setMatrixAt(instanceId, dummy.matrix);

            dummy.position.copy(this.displacementEnd).addScaledVector(direction, -headLength * 0.5);
            if (flat) {
                dummy.scale.set(headWidth, headLength, 1);
                this.orientFlatBond(dummy, direction);
            } else {
                dummy.scale.set(headWidth, headLength, headWidth);
                dummy.quaternion.setFromUnitVectors(this.yAxis, direction);
            }
            dummy.updateMatrix();
            head.setMatrixAt(instanceId, dummy.matrix);
        });
        shaft.instanceMatrix.needsUpdate = true;
        head.instanceMatrix.needsUpdate = true;
    }

    rebuildBonds(precomputedPairs = null, precomputedBridgeRecords = null) {
        this.clearGroup(this.bondGroup);
        this.clearSupercellBonds();
        this.bondPairs = [];
        this.supercellBridgeBondRecords = [];
        this.domElement.dataset.bondCount = '0';
        this.domElement.dataset.supercellBridgeBondCount = '0';
        this.domElement.dataset.periodicBonds = this.displayOptions.showPeriodicBonds ? 'true' : 'false';
        const pairStyles = Object.values(this.displayOptions.pairwiseBondStyles || {});
        const effectiveStyles = new Set([
            this.effectiveBondStyle(),
            ...pairStyles.map(style => this.effectiveBondStyle(style?.style))
        ]);
        this.domElement.dataset.bondStyle = effectiveStyles.size > 1
            ? 'mixed'
            : [...effectiveStyles][0];
        this.domElement.dataset.requestedBondStyle = this.displayOptions.bondStyle || 'cylinder';
        this.domElement.dataset.bondColorMode = this.displayOptions.bondColorMode || 'split';
        this.domElement.dataset.bondThickness = String(this.bondThickness());
        if (!this.displayOptions.showBonds || !this.atomsData) {
            this.requestRender();
            return;
        }
        if (
            precomputedPairs === null
            && precomputedBridgeRecords === null
            && this.displayOptions.bondMode !== 'manual'
        ) {
            const topology = this.inferCurrentBondTopology();
            precomputedPairs = topology.pairs;
            precomputedBridgeRecords = topology.bridgeRecords;
        }
        const hookeanExcluded = this.hookeanBondExclusions();
        this.bondPairs = precomputedPairs || (this.displayOptions.bondMode === 'manual'
            ? this.displayOptions.manualBondPairs.filter(([i, j]) =>
                this.atomMeshByIndex.has(i) && this.atomMeshByIndex.has(j) &&
                this.atomLabelVisible(i) && this.atomLabelVisible(j) &&
                !hookeanExcluded.has(this.hookeanPairKey(i, j)))
            : this.inferBondPairs());
        this.domElement.dataset.bondCount = String(this.bondPairs.length);
        const segments = this.bondPairs.flatMap(([i, j]) => this.bondSegmentsForPair(i, j));
        const segmentsByAppearance = new Map();
        segments.forEach(segment => {
            const key = this.bondAppearanceKey(segment);
            if (!segmentsByAppearance.has(key)) segmentsByAppearance.set(key, []);
            segmentsByAppearance.get(key).push(segment);
        });
        segmentsByAppearance.forEach(colorSegments => {
            const sample = colorSegments[0];
            const appearance = sample.appearance;
            const color = this.bondSegmentColor(sample);
            const flat = appearance.style === 'flat';
            const mesh = new THREE.InstancedMesh(
                flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
                this.bondMaterial(appearance.style, color, appearance.material, appearance.opacity),
                colorSegments.length
            );
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.frustumCulled = false;
            mesh.renderOrder = -1;
            mesh.userData = {
                instancedBonds: true,
                bondPairs: this.bondPairs,
                bondSegments: colorSegments,
                bondColor: color,
                bondAppearance: { ...appearance },
                sharedGeometry: true,
                sharedMaterial: true
            };
            colorSegments.forEach((segment, instanceId) => {
                this.positionBondInstance(
                    mesh,
                    instanceId,
                    segment.i,
                    segment.j,
                    segment.t0,
                    segment.t1,
                    null,
                    null,
                    segment.appearance?.thickness ?? this.bondThickness(),
                    null,
                    appearance.style
                );
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.bondGroup.add(mesh);
        });
        this.rebuildSupercellBonds(null, null, precomputedBridgeRecords);
        this.applyShadowFlags();
        this.requestRender();
    }

    updateBondPositions() {
        if (!this.displayOptions.showBonds || !this.bondPairs?.length) return;
        if (this.bondGroup.children.length) {
            this.bondGroup.children.forEach(bond => {
                if (bond.userData.instancedBonds) {
                    (bond.userData.bondSegments || []).forEach((segment, instanceId) => {
                        this.positionBondInstance(
                            bond,
                            instanceId,
                            segment.i,
                            segment.j,
                            segment.t0,
                            segment.t1,
                            null,
                            null,
                            segment.appearance?.thickness ?? this.bondThickness(),
                            null,
                            segment.appearance?.style
                        );
                    });
                    bond.instanceMatrix.needsUpdate = true;
                    return;
                }
                const [i, j] = bond.userData.bondPair || [];
                this.positionBondMesh(bond, i, j);
            });
        }
        this.updateSupercellBondPositions();
    }

    commensurateLabelSprite(text, active = false) {
        const canvas = document.createElement('canvas');
        canvas.width = 250;
        canvas.height = 72;
        const context = canvas.getContext('2d');
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.font = '700 25px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        const metrics = context.measureText(text);
        const boxWidth = Math.min(canvas.width - 8, Math.ceil(metrics.width + 34));
        const left = (canvas.width - boxWidth) / 2;
        context.fillStyle = active ? 'rgba(42, 36, 22, 0.94)' : 'rgba(20, 24, 25, 0.86)';
        context.strokeStyle = active ? 'rgba(243, 190, 87, 0.95)' : 'rgba(88, 213, 189, 0.62)';
        context.lineWidth = 2;
        context.beginPath();
        if (typeof context.roundRect === 'function') context.roundRect(left, 9, boxWidth, 54, 9);
        else context.rect(left, 9, boxWidth, 54);
        context.fill();
        context.stroke();
        context.fillStyle = active ? '#ffd77c' : '#d9fff7';
        context.fillText(text, canvas.width / 2, 36);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false,
            toneMapped: false
        });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(2.5, 0.72, 1);
        sprite.renderOrder = 48;
        sprite.userData.commensurateTexture = texture;
        return sprite;
    }

    setCommensurateGuides({ pivot, axis, reference, radius, baselineActive = false, candidates = [] } = {}) {
        if (!pivot || !axis || !reference || !candidates.length) {
            this.clearCommensurateGuides();
            return;
        }
        const rounded = values => values.map(value => Number(value).toFixed(5));
        const signature = JSON.stringify({
            axis: rounded(axis),
            baselineActive,
            candidates: candidates.map(candidate => [
                Number(candidate.angle_deg).toFixed(5),
                Boolean(candidate.active),
                candidate.label || ''
            ]),
            pivot: rounded(pivot),
            radius: Number(radius).toFixed(5),
            reference: rounded(reference)
        });
        if (signature === this.commensurateGuideSignature) return;
        this.clearCommensurateGuides({ resetSignature: false });
        this.commensurateGuideSignature = signature;
        const center = new THREE.Vector3(...pivot);
        const normal = new THREE.Vector3(...axis).normalize();
        const baseline = new THREE.Vector3(...reference)
            .addScaledVector(normal, -new THREE.Vector3(...reference).dot(normal))
            .normalize();
        const guideRadius = Math.max(2.5, Number(radius) || 4);
        if (!baseline.lengthSq()) return;

        const labelAnchors = [];
        const addRay = (
            angleDeg,
            color,
            opacity,
            active,
            label,
            priority = 0,
            candidateIndex = null
        ) => {
            const direction = baseline.clone().applyAxisAngle(normal, THREE.MathUtils.degToRad(angleDeg));
            const start = center.clone().addScaledVector(direction, guideRadius * 0.14);
            const end = center.clone().addScaledVector(direction, guideRadius);
            const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
            const material = new THREE.LineBasicMaterial({
                color,
                transparent: true,
                opacity,
                depthTest: false,
                depthWrite: false,
                toneMapped: false
            });
            const ray = new THREE.Line(geometry, material);
            ray.userData = {
                commensurateCandidate: candidateIndex !== null,
                candidateIndex
            };
            ray.renderOrder = active ? 47 : 45;
            this.commensurateGuideGroup.add(ray);
            if (!label) return;
            labelAnchors.push({
                active,
                label,
                position: end.clone().addScaledVector(direction, guideRadius * 0.11),
                priority
            });
        };

        candidates.forEach((candidate, candidateIndex) => {
            const active = Boolean(candidate.active);
            addRay(
                Number(candidate.angle_deg),
                active ? 0xf3be57 : 0x58d5bd,
                active ? 1.0 : 0.66,
                active,
                candidate.label,
                active ? 3 : (candidate.primary || candidate.magic_reference ? 2 : 0),
                candidateIndex
            );
        });

        const width = Math.max(1, this.renderer.domElement.clientWidth || 1);
        const height = Math.max(1, this.renderer.domElement.clientHeight || 1);
        const occupied = [];
        labelAnchors
            .sort((first, second) => second.priority - first.priority)
            .forEach(anchor => {
                const projected = anchor.position.clone()
                    .add(this.visualTranslationVector())
                    .project(this.camera);
                const screen = {
                    x: (projected.x * 0.5 + 0.5) * width,
                    y: (-projected.y * 0.5 + 0.5) * height
                };
                const collides = occupied.some(point => (
                    Math.abs(point.x - screen.x) < 132 && Math.abs(point.y - screen.y) < 36
                ));
                if (collides && anchor.priority < 2) return;
                if (collides && occupied.some(point => point.priority >= anchor.priority)) return;
                const sprite = this.commensurateLabelSprite(anchor.label, anchor.active);
                sprite.position.copy(anchor.position);
                this.commensurateGuideGroup.add(sprite);
                occupied.push({ ...screen, priority: anchor.priority });
            });
        this.requestRender();
    }

    clearCommensurateGuides({ resetSignature = true } = {}) {
        if (!this.commensurateGuideGroup) return;
        if (resetSignature) this.commensurateGuideSignature = null;
        this.commensurateGuideGroup.traverse(object => {
            object.userData?.commensurateTexture?.dispose?.();
        });
        this.clearGroup(this.commensurateGuideGroup);
        this.requestRender();
    }

    commensuratePreviewBaseGroups() {
        return [
            this.atomMeshes,
            this.selectionOutlines,
            this.replicaSelectionOutlines,
            this.cellGroup,
            this.bondGroup,
            this.supercellGroup,
            this.displacementGroup,
            this.forceVectorGroup,
            this.volumetricGroup,
            this.volumetricPlaneGroup,
            this.constraintMarkGroup,
            this.constraintGuideGroup,
            this.constraintMotionGuideGroup,
            this.hookeanGroup
        ].filter(Boolean);
    }

    hideBaseSceneForCommensuratePreview() {
        if (!this.commensurateBaseVisibility) {
            this.commensurateBaseVisibility = new Map(
                this.commensuratePreviewBaseGroups().map(group => [group, group.visible])
            );
        }
        this.commensuratePreviewBaseGroups().forEach(group => {
            group.visible = false;
        });
    }

    restoreBaseSceneAfterCommensuratePreview() {
        if (!this.commensurateBaseVisibility) return;
        this.commensurateBaseVisibility.forEach((visible, group) => {
            group.visible = visible;
        });
        this.commensurateBaseVisibility = null;
    }

    cameraSnapshot() {
        const capture = camera => ({
            position: camera.position.clone(),
            quaternion: camera.quaternion.clone(),
            up: camera.up.clone(),
            near: camera.near,
            far: camera.far,
            zoom: camera.zoom,
            left: camera.left,
            right: camera.right,
            top: camera.top,
            bottom: camera.bottom,
            aspect: camera.aspect
        });
        return {
            projectionMode: this.projectionMode,
            target: this.controls.target.clone(),
            perspective: capture(this.perspectiveCamera),
            orthographic: capture(this.orthographicCamera)
        };
    }

    restoreCameraSnapshot(snapshot) {
        if (!snapshot) return;
        const restore = (camera, state) => {
            camera.position.copy(state.position);
            camera.quaternion.copy(state.quaternion);
            camera.up.copy(state.up);
            camera.near = state.near;
            camera.far = state.far;
            if (Number.isFinite(state.zoom)) camera.zoom = state.zoom;
            if (Number.isFinite(state.left)) camera.left = state.left;
            if (Number.isFinite(state.right)) camera.right = state.right;
            if (Number.isFinite(state.top)) camera.top = state.top;
            if (Number.isFinite(state.bottom)) camera.bottom = state.bottom;
            if (Number.isFinite(state.aspect)) camera.aspect = state.aspect;
            camera.updateProjectionMatrix();
            camera.updateMatrixWorld(true);
        };
        restore(this.perspectiveCamera, snapshot.perspective);
        restore(this.orthographicCamera, snapshot.orthographic);
        this.projectionMode = snapshot.projectionMode === 'perspective' ? 'perspective' : 'orthographic';
        this.camera = this.projectionMode === 'perspective'
            ? this.perspectiveCamera
            : this.orthographicCamera;
        this.controls.camera = this.camera;
        this.controls.target.copy(snapshot.target);
        this.controls.update?.();
        this.updateViewLighting();
        this.onCameraChange?.({ source: 'commensurate-preview-restore' });
    }

    clearCommensurateSupercellPreview({ requestRender = true, restoreCamera = true } = {}) {
        if (!this.commensurateSupercellGroup) return;
        this.clearGroup(this.commensurateSupercellGroup);
        this.commensurateSupercellPreview = null;
        this.restoreBaseSceneAfterCommensuratePreview();
        if (restoreCamera && this.commensurateCameraSnapshot) {
            this.restoreCameraSnapshot(this.commensurateCameraSnapshot);
        }
        this.commensurateCameraSnapshot = null;
        delete this.domElement.dataset.commensuratePreviewAtoms;
        delete this.domElement.dataset.commensuratePreviewBonds;
        if (requestRender) this.requestRender();
    }

    commensuratePreviewLabel(preview, row) {
        const explicit = preview?.labels?.[row];
        if (explicit !== undefined && explicit !== null) return String(explicit);
        const index = Number(preview?.atom_indices?.[row]);
        return this.atomsData?.symbols?.[index] || '';
    }

    commensuratePreviewChemicalSymbol(preview, row) {
        const explicit = preview?.chemical_symbols?.[row];
        if (explicit !== undefined && explicit !== null) return String(explicit);
        const index = Number(preview?.atom_indices?.[row]);
        return this.atomChemicalSymbol(index);
    }

    commensuratePreviewRowVisible(preview, row) {
        const label = this.commensuratePreviewLabel(preview, row);
        return this.displayOptions?.labelVisible?.[label] !== false;
    }

    commensuratePreviewRadius(preview, row) {
        const label = this.commensuratePreviewLabel(preview, row);
        const configured = Number(this.displayOptions?.labelRadii?.[label]);
        const source = Number.isFinite(configured) && configured > 0
            ? configured
            : Number(preview?.radii?.[row]);
        const scale = Number(this.displayOptions?.atomRadiusScale || 0.6);
        return (Number.isFinite(source) && source > 0 ? source : FALLBACK_ATOM_RADIUS)
            * (Number.isFinite(scale) && scale > 0 ? scale : 0.6);
    }

    commensuratePreviewCovalentRadius(preview, row) {
        const source = Number(preview?.bond_radii?.[row]);
        return Number.isFinite(source) && source > 0 ? source : FALLBACK_COVALENT_RADIUS;
    }

    commensuratePreviewColor(preview, row) {
        const label = this.commensuratePreviewLabel(preview, row);
        const configured = this.displayOptions?.labelColors?.[label];
        if (this.validHexColor(configured)) return configured;
        const explicit = preview?.colors?.[row];
        return this.validHexColor(explicit) ? explicit : FALLBACK_ATOM_COLOR;
    }

    commensuratePreviewMaterial(preview, row) {
        const label = this.commensuratePreviewLabel(preview, row);
        return this.normalizedAtomMaterialPreset(this.displayOptions?.labelMaterials?.[label]);
    }

    commensuratePreviewOpacity(preview, row) {
        const label = this.commensuratePreviewLabel(preview, row);
        const configured = Number(this.displayOptions?.labelOpacities?.[label]);
        return Math.max(0, Math.min(1, Number.isFinite(configured) ? configured : 1));
    }

    commensuratePreviewBounds(preview) {
        const box = new THREE.Box3();
        const positions = preview?.positions || [];
        const atomIndices = preview?.atom_indices || [];
        const translation = this.visualTranslationVector();
        positions.forEach((position, row) => {
            const index = Number(atomIndices[row]);
            if (!Number.isInteger(index) || !this.commensuratePreviewRowVisible(preview, row)) return;
            const center = new THREE.Vector3(...position).add(translation);
            const radius = this.commensuratePreviewRadius(preview, row);
            box.expandByPoint(center.clone().addScalar(radius));
            box.expandByPoint(center.clone().addScalar(-radius));
        });
        const fixedParentLattices = preview?.parent_lattices_fixed === true;
        const cellSpecs = [
            [preview?.has_suggestion === false ? null : (preview?.common_cell || preview?.cell), [0, 0, 0]],
            [fixedParentLattices ? preview?.host_parent_cell : preview?.host_cell, [0, 0, 0]],
            [
                fixedParentLattices ? preview?.guest_parent_cell : preview?.guest_cell,
                preview?.guest_offset || [0, 0, 0]
            ]
        ];
        cellSpecs.forEach(([cell, origin]) => this.commensurateCellSegments(cell, origin).forEach(segment => {
            segment.forEach(point => box.expandByPoint(point.clone().add(translation)));
        }));
        [
            [preview?.host_grid_lattice_origins, preview?.host_primitive_vectors],
            [preview?.guest_grid_lattice_origins, preview?.guest_primitive_vectors]
        ].forEach(([origins, vectors]) => {
            this.commensuratePrimitiveSegments(origins, vectors).forEach(segment => {
                segment.forEach(point => box.expandByPoint(point.clone().add(translation)));
            });
        });
        return box.isEmpty() ? null : box;
    }

    commensurateCellSegments(cell, originValues = [0, 0, 0]) {
        if (!Array.isArray(cell) || cell.length !== 3) return [];
        const [a, b, c] = cell.map(values => new THREE.Vector3(...values));
        const origin = new THREE.Vector3(...originValues);
        const corners = [
            origin,
            origin.clone().add(a),
            origin.clone().add(b),
            origin.clone().add(c),
            origin.clone().add(a).add(b),
            origin.clone().add(a).add(c),
            origin.clone().add(b).add(c),
            origin.clone().add(a).add(b).add(c)
        ];
        return [[0,1],[0,2],[0,3],[1,4],[1,5],[2,4],[2,6],[3,5],[3,6],[4,7],[5,7],[6,7]]
            .map(([first, second]) => [corners[first], corners[second]]);
    }

    commensuratePlanarCellSegments(cell, originValues = [0, 0, 0]) {
        if (!Array.isArray(cell) || cell.length !== 3) return [];
        const origin = new THREE.Vector3(...originValues);
        const a = new THREE.Vector3(...cell[0]);
        const b = new THREE.Vector3(...cell[1]);
        const aCorner = origin.clone().add(a);
        const bCorner = origin.clone().add(b);
        const abCorner = origin.clone().add(a).add(b);
        return [
            [origin, aCorner],
            [origin, bCorner],
            [aCorner, abCorner],
            [bCorner, abCorner]
        ];
    }

    commensuratePrimitiveSegments(origins, vectors) {
        if (!Array.isArray(origins) || !Array.isArray(vectors) || vectors.length < 2) return [];
        const primitive = [vectors[0], vectors[1], [0, 0, 0]];
        const unique = new Map();
        const pointKey = point => [point.x, point.y, point.z]
            .map(value => Math.round(value * 1e7))
            .join(',');
        origins.forEach(origin => {
            this.commensuratePlanarCellSegments(primitive, origin).forEach(segment => {
                const endpoints = segment.map(pointKey).sort();
                const key = endpoints.join('|');
                if (!unique.has(key)) unique.set(key, segment);
            });
        });
        return [...unique.values()];
    }

    commensurateCellLabelSprite(text, color = '#159b8c') {
        const canvas = document.createElement('canvas');
        canvas.width = 760;
        canvas.height = 128;
        const context = canvas.getContext('2d');
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        let fontSize = 42;
        let metrics;
        do {
            context.font = `700 ${fontSize}px Inter, system-ui, sans-serif`;
            metrics = context.measureText(text);
            if (metrics.width <= canvas.width - 66 || fontSize <= 28) break;
            fontSize -= 2;
        } while (fontSize >= 28);
        const boxWidth = Math.min(canvas.width - 12, Math.ceil(metrics.width + 54));
        const left = (canvas.width - boxWidth) / 2;
        context.fillStyle = 'rgba(255,255,255,0.94)';
        context.strokeStyle = color;
        context.lineWidth = 4;
        context.beginPath();
        if (typeof context.roundRect === 'function') context.roundRect(left, 14, boxWidth, 100, 14);
        else context.rect(left, 14, boxWidth, 100);
        context.fill();
        context.stroke();
        context.fillStyle = color;
        context.fillText(text, canvas.width / 2, canvas.height / 2);
        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false,
            depthWrite: false,
            toneMapped: false
        });
        const sprite = new THREE.Sprite(material);
        sprite.renderOrder = 52;
        sprite.userData = {
            commensurateCellLabel: true,
            labelText: text,
            commensurateTexture: texture
        };
        return sprite;
    }

    buildCommensuratePreviewAtoms(preview) {
        const positions = preview.positions || [];
        const atomIndices = preview.atom_indices || [];
        const coreMask = preview.core_mask || [];
        const components = preview.components || [];
        const fixed = this.fixedAtomDisplayEnabled()
            ? new Set(this.atomsData?.constraints?.fixed_indices || [])
            : new Set();
        const segmentCount = this.sphereQualitySegments(positions.length);
        const groups = new Map();
        positions.forEach((position, row) => {
            const index = Number(atomIndices[row]);
            if (!Number.isInteger(index) || !this.commensuratePreviewRowVisible(preview, row)) return;
            const isFixed = components[row] !== 'guest' && fixed.has(index);
            const materialPreset = this.commensuratePreviewMaterial(preview, row);
            const opacity = this.commensuratePreviewOpacity(preview, row);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const core = coreMask[row] !== false;
            const component = String(components[row] || 'lattice');
            const key = `${component}:${isFixed ? 'fixed' : 'normal'}:${materialPreset}:alpha-${opacity.toFixed(4)}:${atomSegments}`;
            if (!groups.has(key)) {
                groups.set(key, {
                    component,
                    isFixed,
                    materialPreset,
                    opacity,
                    atomSegments,
                    rows: [],
                    coreRows: 0,
                    haloRows: 0
                });
            }
            groups.get(key).rows.push(row);
            if (core) groups.get(key).coreRows += 1;
            else groups.get(key).haloRows += 1;
        });

        groups.forEach(group => {
            const geometryKey = `unit-sphere:${group.isFixed ? 'fixed' : 'normal'}:${group.atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(
                        1,
                        group.atomSegments,
                        Math.max(8, Math.floor(group.atomSegments * 0.65))
                    )
                );
            }
            const material = this.createInstancedAtomMaterial(
                group.isFixed, group.materialPreset, group.opacity
            );
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(geometryKey),
                material,
                group.rows.length
            );
            mesh.frustumCulled = false;
            mesh.renderOrder = 1;
            mesh.userData = {
                commensuratePreviewAtoms: true,
                commensurateComponent: group.component,
                commensurateCoreRows: group.coreRows,
                commensurateHaloRows: group.haloRows,
                opacity: group.opacity,
                sharedGeometry: true
            };
            group.rows.forEach((row, instanceId) => {
                const radius = this.commensuratePreviewRadius(preview, row);
                this.instanceDummy.position.set(...positions[row]);
                this.instanceDummy.quaternion.identity();
                this.instanceDummy.scale.setScalar(radius);
                this.instanceDummy.updateMatrix();
                mesh.setMatrixAt(instanceId, this.instanceDummy.matrix);
                mesh.setColorAt(
                    instanceId,
                    this.fixedAdjustedColor(
                        this.commensuratePreviewColor(preview, row),
                        group.isFixed,
                        group.materialPreset
                    )
                );
            });
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            this.commensurateSupercellGroup.add(mesh);
        });
    }

    commensuratePreviewBondRange(preview, firstRow, secondRow) {
        if (this.displayOptions.bondMode === 'pairwise') {
            return this.pairwiseBondRange(
                this.commensuratePreviewLabel(preview, firstRow),
                this.commensuratePreviewLabel(preview, secondRow)
            );
        }
        const scale = Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
        const maximum = this.autoBondBaseCutoffFromValues(
            this.commensuratePreviewCovalentRadius(preview, firstRow),
            this.commensuratePreviewCovalentRadius(preview, secondRow),
            this.autoBondElementClass(this.commensuratePreviewChemicalSymbol(preview, firstRow)),
            this.autoBondElementClass(this.commensuratePreviewChemicalSymbol(preview, secondRow))
        ) * scale;
        return Number.isFinite(maximum) && maximum > 0
            ? { min: 0, max: maximum }
            : null;
    }

    commensuratePreviewMaximumBondCutoff(preview) {
        if (this.displayOptions.bondMode === 'pairwise') {
            return Object.values(this.displayOptions.pairwiseBondRanges || {}).reduce((maximum, range) => {
                const value = range?.enabled === false ? 0 : Number(range?.max);
                return Number.isFinite(value) ? Math.max(maximum, value) : maximum;
            }, 0);
        }
        const radii = (preview?.bond_radii || [])
            .map(Number)
            .filter(value => Number.isFinite(value) && value > 0)
            .sort((left, right) => right - left);
        const radiusSum = (radii[0] || FALLBACK_COVALENT_RADIUS)
            + (radii[1] || radii[0] || FALLBACK_COVALENT_RADIUS);
        return (radiusSum + AUTO_BOND_COVALENT_SLACK)
            * Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
    }

    commensuratePreviewBondPairs(preview) {
        if (!this.displayOptions.showBonds) return [];
        const positions = preview.positions || [];
        const atomIndices = preview.atom_indices || [];
        const components = preview.components || [];
        if (!positions.length) return [];
        const maxCutoff = Math.max(0, this.commensuratePreviewMaximumBondCutoff(preview));
        if (maxCutoff <= 0) return [];
        const inverseBucket = 1 / maxCutoff;
        const buckets = new Map();
        const keyFor = (x, y, z) => `${x},${y},${z}`;
        positions.forEach((position, row) => {
            const index = Number(atomIndices[row]);
            if (!Number.isInteger(index) || !this.commensuratePreviewRowVisible(preview, row)) return;
            const bucket = position.map(value => Math.floor(Number(value) * inverseBucket));
            const key = keyFor(bucket[0], bucket[1], bucket[2]);
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key).push(row);
        });
        const manual = new Set((this.displayOptions.manualBondPairs || []).map(([first, second]) => (
            `${Math.min(first, second)}:${Math.max(first, second)}`
        )));
        const hookeanExcluded = this.hookeanBondExclusions();
        const pairs = [];
        const maxPairs = 300000;
        positions.forEach((position, firstRow) => {
            if (pairs.length >= maxPairs) return;
            const firstIndex = Number(atomIndices[firstRow]);
            if (!Number.isInteger(firstIndex) || !this.commensuratePreviewRowVisible(preview, firstRow)) return;
            const center = position.map(value => Math.floor(Number(value) * inverseBucket));
            for (let dx = -1; dx <= 1; dx++) {
                if (pairs.length >= maxPairs) break;
                for (let dy = -1; dy <= 1; dy++) {
                    if (pairs.length >= maxPairs) break;
                    for (let dz = -1; dz <= 1; dz++) {
                        if (pairs.length >= maxPairs) break;
                        const rows = buckets.get(keyFor(center[0] + dx, center[1] + dy, center[2] + dz)) || [];
                        for (const secondRow of rows) {
                            if (secondRow <= firstRow) continue;
                            // Host/reference and guest/rotating lattices are
                            // independent structures until materialization.
                            // Never infer an inter-layer bond merely because
                            // the preview places their atoms nearby.
                            if (components[firstRow] !== components[secondRow]) continue;
                            const secondIndex = Number(atomIndices[secondRow]);
                            const pairKey = `${Math.min(firstIndex, secondIndex)}:${Math.max(firstIndex, secondIndex)}`;
                            if (hookeanExcluded.has(pairKey)) continue;
                            if (this.displayOptions.bondMode === 'manual' && !manual.has(pairKey)) continue;
                            const range = this.displayOptions.bondMode === 'manual'
                                ? { min: 0, max: maxCutoff }
                                : this.commensuratePreviewBondRange(preview, firstRow, secondRow);
                            if (!range) continue;
                            const second = positions[secondRow];
                            const deltaX = Number(second[0]) - Number(position[0]);
                            const deltaY = Number(second[1]) - Number(position[1]);
                            const deltaZ = Number(second[2]) - Number(position[2]);
                            const distanceSquared = deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ;
                            if (
                                distanceSquared <= 0.0225
                                || distanceSquared < range.min * range.min
                                || distanceSquared > range.max * range.max
                            ) continue;
                            pairs.push([firstRow, secondRow]);
                            if (pairs.length >= maxPairs) break;
                        }
                    }
                }
            }
        });
        return pairs;
    }

    buildCommensuratePreviewBonds(preview) {
        const positions = preview.positions || [];
        const atomIndices = preview.atom_indices || [];
        const pairs = this.commensuratePreviewBondPairs(preview);
        const split = this.displayOptions.bondColorMode !== 'custom';
        const segmentsByColor = new Map();
        pairs.forEach(([firstRow, secondRow]) => {
            const firstIndex = Number(atomIndices[firstRow]);
            const secondIndex = Number(atomIndices[secondRow]);
            const segments = split
                ? [
                    { firstRow, secondRow, t0: 0, t1: 0.5, color: this.commensuratePreviewColor(preview, firstRow) },
                    { firstRow, secondRow, t0: 0.5, t1: 1, color: this.commensuratePreviewColor(preview, secondRow) }
                ]
                : [{ firstRow, secondRow, t0: 0, t1: 1, color: this.displayOptions.bondCustomColor }];
            segments.forEach(segment => {
                const color = this.validHexColor(segment.color)
                    ? segment.color
                    : this.displayOptions.bondCustomColor;
                if (!segmentsByColor.has(color)) segmentsByColor.set(color, []);
                segmentsByColor.get(color).push(segment);
            });
        });
        const flat = this.effectiveBondStyle() === 'flat';
        const thickness = this.bondThickness();
        segmentsByColor.forEach((segments, color) => {
            const mesh = new THREE.InstancedMesh(
                flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
                this.bondMaterial(flat ? 'flat' : 'cylinder', color),
                segments.length
            );
            mesh.frustumCulled = false;
            mesh.renderOrder = -1;
            mesh.userData = {
                commensuratePreviewBonds: true,
                sharedGeometry: true,
                sharedMaterial: true
            };
            const dummy = this.bondInstanceDummy;
            segments.forEach((segment, instanceId) => {
                const start = new THREE.Vector3(...positions[segment.firstRow]);
                const end = new THREE.Vector3(...positions[segment.secondRow]);
                const fullDelta = end.clone().sub(start);
                const fullLength = fullDelta.length();
                const segmentStart = start.clone().addScaledVector(fullDelta, segment.t0);
                const segmentEnd = start.clone().addScaledVector(fullDelta, segment.t1);
                const segmentDelta = segmentEnd.clone().sub(segmentStart);
                const segmentLength = segmentDelta.length();
                const center = segmentStart.add(segmentEnd).multiplyScalar(0.5);
                if (flat) {
                    dummy.position.copy(center);
                    dummy.scale.set(thickness, segmentLength, 1);
                    this.orientFlatBond(dummy, segmentDelta);
                    dummy.updateMatrix();
                    mesh.setMatrixAt(instanceId, dummy.matrix);
                } else {
                    this.writeCylinderBondInstance(
                        mesh,
                        instanceId,
                        segmentDelta,
                        segmentLength,
                        segmentLength,
                        thickness,
                        center.x,
                        center.y,
                        center.z
                    );
                }
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.commensurateSupercellGroup.add(mesh);
        });
        return pairs.length;
    }

    setCommensurateSupercellPreview(payload) {
        const preview = payload?.preview;
        const updatingExistingPreview = Boolean(this.commensurateSupercellPreview);
        const cameraSnapshot = updatingExistingPreview
            ? this.commensurateCameraSnapshot
            : this.cameraSnapshot();
        this.clearCommensurateSupercellPreview({ requestRender: false, restoreCamera: false });
        if (!preview || !Array.isArray(preview.cell)) {
            if (cameraSnapshot) this.restoreCameraSnapshot(cameraSnapshot);
            this.requestRender();
            return;
        }
        this.commensurateCameraSnapshot = cameraSnapshot;
        this.hideBaseSceneForCommensuratePreview();
        this.commensurateSupercellPreview = payload;
        if (preview.positions?.length) this.buildCommensuratePreviewAtoms(preview);
        const bondCount = preview.positions?.length ? this.buildCommensuratePreviewBonds(preview) : 0;
        const addBoundary = (cell, color, opacity, metadata, origin = [0, 0, 0], scale = 1) => {
            if (!Array.isArray(cell) || cell.length !== 3) return;
            const material = new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity,
                depthTest: true,
                depthWrite: false,
                toneMapped: false
            });
            this.addCellEdgeInstances(
                this.commensurateSupercellGroup,
                this.commensuratePlanarCellSegments(cell, origin),
                metadata,
                {
                    material,
                    radius: Math.max(0.025, this.normalizedCellThickness() * scale)
                }
            );
        };
        const addPrimitiveGrid = (origins, vectors, color, metadata, opacity = 0.42) => {
            const segments = this.commensuratePrimitiveSegments(origins, vectors);
            if (!segments.length) return;
            const material = new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity,
                depthTest: true,
                depthWrite: false,
                toneMapped: false
            });
            this.addCellEdgeInstances(
                this.commensurateSupercellGroup,
                segments,
                metadata,
                {
                    material,
                    radius: Math.max(0.016, this.normalizedCellThickness() * 0.42)
                }
            );
        };
        const addCellLabel = (text, cell, originValues, color, side, metadata) => {
            if (!text || !Array.isArray(cell) || cell.length < 2) return;
            const origin = new THREE.Vector3(...originValues);
            const first = new THREE.Vector3(...cell[0]);
            const second = new THREE.Vector3(...cell[1]);
            const firstLength = first.length();
            const secondLength = second.length();
            if (firstLength <= 1e-8 || secondLength <= 1e-8) return;
            const normal = second.clone().normalize().multiplyScalar(
                side * Math.max(0.8, Math.min(firstLength, secondLength) * 0.16)
            );
            const sprite = this.commensurateCellLabelSprite(text, color);
            sprite.position.copy(origin).addScaledVector(first, 0.5).add(normal);
            const width = THREE.MathUtils.clamp(firstLength * 0.54, 3.3, 7.2);
            sprite.scale.set(width, width * 0.175, 1);
            sprite.userData = { ...sprite.userData, ...metadata };
            this.commensurateSupercellGroup.add(sprite);
        };
        const addPrimitiveVectors = (origins, vectors, color, metadata) => {
            if (!Array.isArray(origins) || !origins.length || !Array.isArray(vectors)) return;
            const originValues = origins.reduce((nearest, candidate) => {
                const candidateLength = new THREE.Vector3(...candidate).lengthSq();
                const nearestLength = new THREE.Vector3(...nearest).lengthSq();
                return candidateLength < nearestLength ? candidate : nearest;
            }, origins[0]);
            const origin = new THREE.Vector3(...originValues);
            vectors.slice(0, 2).forEach((values, vectorIndex) => {
                const direction = new THREE.Vector3(...values);
                const length = direction.length();
                if (!Number.isFinite(length) || length <= 1e-9) return;
                direction.normalize();
                const shaftRadius = Math.max(
                    0.045,
                    this.normalizedCellThickness() * 0.82
                );
                const headLength = Math.min(
                    length * 0.24,
                    Math.max(0.18, length * 0.17)
                );
                const shaftLength = Math.max(length - headLength * 0.72, length * 0.62);
                const shaftEnd = origin.clone().addScaledVector(direction, shaftLength);
                const arrow = new THREE.Group();
                arrow.userData = { ...metadata, commensurateVectorIndex: vectorIndex };
                const material = new THREE.MeshBasicMaterial({
                    color,
                    transparent: true,
                    opacity: 1,
                    depthTest: true,
                    depthWrite: false,
                    toneMapped: false
                });
                const shaft = this.addCellEdgeInstances(
                    arrow,
                    [[origin, shaftEnd]],
                    { ...metadata, commensurateVectorShaft: true },
                    { material, radius: shaftRadius }
                );
                if (shaft) shaft.renderOrder = 5;
                const cone = new THREE.Mesh(
                    new THREE.ConeGeometry(1, 1, 18, 1, false),
                    material
                );
                cone.position.copy(origin).addScaledVector(
                    direction,
                    length - headLength * 0.5
                );
                cone.quaternion.setFromUnitVectors(this.yAxis, direction);
                const headRadius = shaftRadius * 2.35;
                cone.scale.set(headRadius, headLength, headRadius);
                cone.renderOrder = 5;
                cone.userData = {
                    ...metadata,
                    commensurateVectorHead: true,
                    commensurateVectorIndex: vectorIndex
                };
                arrow.add(cone);
                this.commensurateSupercellGroup.add(arrow);
            });
        };
        const guestOrigin = preview.mode === 'host-guest'
            ? (preview.guest_offset || [0, 0, 0])
            : [0, 0, 0];
        const gridLabel = (shape) => (
            Array.isArray(shape)
            && shape.length >= 2
            && shape.slice(0, 2).every(value => Number.isFinite(Number(value)))
                ? `${Math.trunc(Number(shape[0]))} × ${Math.trunc(Number(shape[1]))} grid`
                : ''
        );
        const hostGridLabel = gridLabel(preview.host_grid_shape);
        const guestGridLabel = gridLabel(preview.guest_grid_shape);
        const fixedParentLattices = preview.parent_lattices_fixed === true;
        const candidate = payload?.candidate || {};
        const hostColor = this.displayOptions.viewportBackground === 'dark'
            ? 0xf2f5f4
            : 0x161a1d;
        const guestColor = 0xf58220;
        addPrimitiveGrid(
            preview.host_grid_lattice_origins || preview.host_lattice_origins,
            preview.host_primitive_vectors,
            hostColor,
            { commensurateHostPrimitiveGrid: true },
            fixedParentLattices ? 0.68 : 0.38
        );
        addPrimitiveGrid(
            preview.guest_grid_lattice_origins || preview.guest_lattice_origins,
            preview.guest_primitive_vectors,
            guestColor,
            { commensurateGuestPrimitiveGrid: true },
            fixedParentLattices ? 0.72 : 0.44
        );
        addPrimitiveVectors(
            preview.host_lattice_origins,
            preview.host_primitive_vectors,
            hostColor,
            { commensurateHostPrimitiveVector: true }
        );
        addPrimitiveVectors(
            preview.guest_lattice_origins,
            preview.guest_primitive_vectors,
            guestColor,
            { commensurateGuestPrimitiveVector: true }
        );
        const displayedHostCell = fixedParentLattices
            ? (preview.host_parent_cell || preview.host_cell)
            : preview.host_cell;
        const displayedGuestCell = fixedParentLattices
            ? (preview.guest_parent_cell || preview.guest_cell)
            : preview.guest_cell;
        addBoundary(
            displayedHostCell,
            hostColor,
            0.94,
            { commensurateHostCell: true },
            [0, 0, 0],
            1.08
        );
        addBoundary(
            displayedGuestCell,
            guestColor,
            0.94,
            { commensurateGuestCell: true },
            guestOrigin,
            1.08
        );
        // The fixed parent-lattice view can contain hundreds of primitive
        // cells. Keep its viewport geometric: the control panel carries the
        // lattice names and metrics, while the exact primitive vectors and
        // contrasting grids identify host and guest at their shared origin.
        // Labels remain useful for a bounded, candidate-specific preview.
        if (!fixedParentLattices) {
            addCellLabel(
                `HOST ${hostGridLabel} · ${preview.host_notation || ''}`.trim(),
                displayedHostCell,
                [0, 0, 0],
                this.displayOptions.viewportBackground === 'dark' ? '#f2f5f4' : '#161a1d',
                -1,
                { commensurateHostCellLabel: true }
            );
            addCellLabel(
                `GUEST ${guestGridLabel} · ${preview.guest_notation || ''}`.trim(),
                displayedGuestCell,
                guestOrigin,
                '#d8660f',
                1,
                { commensurateGuestCellLabel: true }
            );
        }
        if (preview.has_suggestion !== false && (preview.common_cell || preview.cell)) {
            const suggestionColor = 0x139c68;
            addBoundary(
                preview.common_cell || preview.cell,
                suggestionColor,
                0.92,
                { commensurateSuggestedCell: true },
                [0, 0, 0],
                1.28
            );
            const notation = candidate.host_notation
                || candidate.target_notation
                || candidate.host_matrix_text
                || candidate.target_matrix_text
                || 'validated common cell';
            addCellLabel(
                `COMMON CELL · ${notation}`,
                preview.common_cell || preview.cell,
                [0, 0, 0],
                '#0b7b51',
                1.55,
                { commensurateSuggestedCellLabel: true }
            );
        }
        this.commensurateSupercellGroup.position.copy(this.visualTranslationVector());
        this.domElement.dataset.commensuratePreviewAtoms = String(preview.preview_atom_count || preview.positions.length);
        this.domElement.dataset.commensuratePreviewBonds = String(bondCount);
        this.applyShadowFlags();
        this.requestRender();
    }

    getAtomPosition(index) {
        const mesh = this.atomMeshByIndex.get(index);
        if (mesh) return mesh.position.clone();
        return new THREE.Vector3(...this.atomsData.positions[index]);
    }

    invalidateCellCache() {
        this.cellCache = null;
    }

    invalidateBondNeighborCache() {
        this.bondNeighborCache = null;
    }

    ensureCellCache() {
        const cell = this.atomsData?.cell;
        if (!cell || cell.length !== 3) return null;
        if (this.cellCache?.source === cell) return this.cellCache;
        const basis = cell.map(values => new THREE.Vector3(...values));
        const determinant = basis[0].dot(new THREE.Vector3().crossVectors(basis[1], basis[2]));
        const valid = basis.some(vector => vector.lengthSq() > 1e-12) && Math.abs(determinant) > 1e-12;
        const reciprocal = valid ? [
            new THREE.Vector3().crossVectors(basis[1], basis[2]).divideScalar(determinant),
            new THREE.Vector3().crossVectors(basis[2], basis[0]).divideScalar(determinant),
            new THREE.Vector3().crossVectors(basis[0], basis[1]).divideScalar(determinant)
        ] : null;
        this.cellCache = { source: cell, basis, reciprocal, valid };
        return this.cellCache;
    }

    cellBasis() {
        const cache = this.ensureCellCache();
        return cache?.valid ? cache.basis : null;
    }

    fracToCart(frac, basis = null) {
        const cell = basis || this.cellBasis();
        if (!cell) return new THREE.Vector3();
        return new THREE.Vector3()
            .addScaledVector(cell[0], frac.x)
            .addScaledVector(cell[1], frac.y)
            .addScaledVector(cell[2], frac.z);
    }

    cartToFrac(cart, basis = null, reciprocal = null) {
        const cache = basis && reciprocal ? null : this.ensureCellCache();
        const cell = basis || cache?.basis;
        if (!cell) return cart.clone();
        const cachedReciprocal = reciprocal || (
            !basis || basis === cache?.basis ? cache?.reciprocal : null
        );
        const reciprocalBasis = cachedReciprocal || (() => {
            const det = cell[0].dot(new THREE.Vector3().crossVectors(cell[1], cell[2]));
            if (Math.abs(det) < 1e-10) return null;
            return [
                new THREE.Vector3().crossVectors(cell[1], cell[2]).divideScalar(det),
                new THREE.Vector3().crossVectors(cell[2], cell[0]).divideScalar(det),
                new THREE.Vector3().crossVectors(cell[0], cell[1]).divideScalar(det)
            ];
        })();
        if (!reciprocalBasis) return cart.clone();
        return new THREE.Vector3(
            cart.dot(reciprocalBasis[0]),
            cart.dot(reciprocalBasis[1]),
            cart.dot(reciprocalBasis[2])
        );
    }

    minimumImageDelta(i, j, startOverride = null) {
        return this.minimumImageBondData(i, j, startOverride).delta;
    }

    minimumImageBondData(i, j, startOverride = null) {
        const start = startOverride || this.getAtomPosition(i);
        const end = this.getAtomPosition(j);
        const delta = new THREE.Vector3().subVectors(end, start);
        const pbc = this.atomsData?.pbc || [false, false, false];
        const imageOffset = [0, 0, 0];
        if (!this.hasValidCell() || !pbc.some(Boolean)) return { delta, imageOffset };
        const cache = this.ensureCellCache();
        const basis = cache?.basis;
        const frac = this.cartToFrac(delta, basis, cache?.reciprocal);
        for (let axis = 0; axis < 3; axis++) {
            if (!pbc[axis]) continue;
            const nearestImage = Math.round(frac.getComponent(axis));
            imageOffset[axis] = -nearestImage;
            frac.setComponent(axis, frac.getComponent(axis) - nearestImage);
        }
        return { delta: this.fracToCart(frac, basis), imageOffset };
    }

    directAtomDelta(i, j, startOverride = null) {
        const start = startOverride || this.getAtomPosition(i);
        const end = this.getAtomPosition(j);
        return new THREE.Vector3().subVectors(end, start);
    }

    bondDistanceSquared(
        i,
        j,
        startOverride = null,
        usePeriodicImages = false,
        cellCache = null
    ) {
        const start = startOverride || this.atomMeshByIndex.get(i)?.position;
        const end = this.atomMeshByIndex.get(j)?.position;
        const fallbackStart = this.atomsData?.positions?.[i];
        const fallbackEnd = this.atomsData?.positions?.[j];
        let dx = (end?.x ?? fallbackEnd?.[0] ?? 0) - (start?.x ?? fallbackStart?.[0] ?? 0);
        let dy = (end?.y ?? fallbackEnd?.[1] ?? 0) - (start?.y ?? fallbackStart?.[1] ?? 0);
        let dz = (end?.z ?? fallbackEnd?.[2] ?? 0) - (start?.z ?? fallbackStart?.[2] ?? 0);

        const pbc = this.atomsData?.pbc || [false, false, false];
        const cache = cellCache || (usePeriodicImages ? this.ensureCellCache() : null);
        if (usePeriodicImages && cache?.valid && pbc.some(Boolean)) {
            const reciprocal = cache.reciprocal;
            let fx = dx * reciprocal[0].x + dy * reciprocal[0].y + dz * reciprocal[0].z;
            let fy = dx * reciprocal[1].x + dy * reciprocal[1].y + dz * reciprocal[1].z;
            let fz = dx * reciprocal[2].x + dy * reciprocal[2].y + dz * reciprocal[2].z;
            if (pbc[0]) fx -= Math.round(fx);
            if (pbc[1]) fy -= Math.round(fy);
            if (pbc[2]) fz -= Math.round(fz);
            const basis = cache.basis;
            dx = fx * basis[0].x + fy * basis[1].x + fz * basis[2].x;
            dy = fx * basis[0].y + fy * basis[1].y + fz * basis[2].y;
            dz = fx * basis[0].z + fy * basis[1].z + fz * basis[2].z;
        }
        return dx * dx + dy * dy + dz * dz;
    }

    bondDeltaForImageOffset(i, j, imageOffset = [0, 0, 0], startOverride = null) {
        const delta = this.directAtomDelta(i, j, startOverride);
        const basis = this.cellBasis();
        if (!basis) return delta;
        return delta
            .addScaledVector(basis[0], Number(imageOffset[0]) || 0)
            .addScaledVector(basis[1], Number(imageOffset[1]) || 0)
            .addScaledVector(basis[2], Number(imageOffset[2]) || 0);
    }

    bondDeltaForMode(i, j, startOverride = null, usePeriodicImages = false) {
        return usePeriodicImages
            ? this.minimumImageDelta(i, j, startOverride)
            : this.directAtomDelta(i, j, startOverride);
    }

    bondDelta(i, j, startOverride = null) {
        return this.bondDeltaForMode(i, j, startOverride, this.displayOptions.showPeriodicBonds);
    }

    bondThickness() {
        const value = Number(this.displayOptions.bondThickness);
        return Number.isFinite(value) ? Math.max(0.02, Math.min(0.6, value)) : 0.25;
    }

    normalizedBondMaterial(value) {
        return ['standard', 'metal', 'rubber', 'unlit'].includes(value)
            ? value
            : 'standard';
    }

    bondAppearance(i, j, endpointIndex = null) {
        const left = this.atomsData?.symbols?.[i] || '';
        const right = this.atomsData?.symbols?.[j] || '';
        const override = this.displayOptions.pairwiseBondStyles?.[this.labelPairKey(left, right)];
        const source = override && typeof override === 'object' ? override : {};
        const endpoint = endpointIndex === null
            ? null
            : (
                this.displayOptions.atomBondStyles?.[endpointIndex]
                ?? this.displayOptions.atomBondStyles?.[String(endpointIndex)]
            );
        const endpointSource = endpoint && typeof endpoint === 'object' ? endpoint : {};
        const opacity = Number(endpointSource.opacity ?? source.opacity ?? this.displayOptions.bondOpacity);
        const thickness = Number(source.thickness ?? this.displayOptions.bondThickness);
        const customColor = this.validHexColor(endpointSource.color)
            ? endpointSource.color.toLowerCase()
            : (this.validHexColor(source.color)
                ? source.color.toLowerCase()
                : (this.validHexColor(this.displayOptions.bondCustomColor)
                    ? this.displayOptions.bondCustomColor.toLowerCase()
                    : '#c8ccd0'));
        return {
            style: this.effectiveBondStyle(source.style ?? this.displayOptions.bondStyle),
            material: this.normalizedBondMaterial(
                endpointSource.material ?? source.material ?? this.displayOptions.bondMaterial
            ),
            thickness: Math.max(0.02, Math.min(0.6, Number.isFinite(thickness)
                ? thickness
                : this.bondThickness())),
            colorMode: (source.colorMode ?? this.displayOptions.bondColorMode) === 'custom'
                ? 'custom'
                : 'split',
            customColor,
            opacity: Math.max(0, Math.min(1, Number.isFinite(opacity) ? opacity : 1))
        };
    }

    bondSegmentsForPair(i, j) {
        const base = this.bondAppearance(i, j);
        const leftAppearance = this.bondAppearance(i, j, i);
        const rightAppearance = this.bondAppearance(i, j, j);
        const endpointStyles = this.displayOptions.atomBondStyles || {};
        const leftOverride = endpointStyles[i] ?? endpointStyles[String(i)];
        const rightOverride = endpointStyles[j] ?? endpointStyles[String(j)];
        if (
            base.colorMode === 'custom'
            && !leftOverride
            && !rightOverride
        ) {
            return [{ i, j, t0: 0, t1: 1, colorIndex: null, appearance: base }];
        }
        return [
            {
                i, j, t0: 0, t1: 0.5,
                colorIndex: base.colorMode === 'custom' ? null : i,
                appearance: leftAppearance
            },
            {
                i, j, t0: 0.5, t1: 1,
                colorIndex: base.colorMode === 'custom' ? null : j,
                appearance: rightAppearance
            }
        ];
    }

    bondAppearanceKey(segment) {
        const appearance = segment.appearance || this.bondAppearance(segment.i, segment.j);
        const color = this.bondSegmentColor(segment);
        return [
            appearance.style,
            appearance.material,
            appearance.thickness.toFixed(4),
            appearance.opacity.toFixed(4),
            color
        ].join(':');
    }

    bondSegmentColor(segment) {
        const requested = segment.colorIndex === null
            ? (segment.appearance?.customColor || this.displayOptions.bondCustomColor)
            : this.atomVisualColor(segment.colorIndex, this.customColors[segment.colorIndex]);
        return this.validHexColor(requested) ? requested.toLowerCase() : '#c8ccd0';
    }

    bondMaterial(style, color, presetName = 'standard', opacity = 1) {
        const preset = this.normalizedBondMaterial(presetName);
        const parsedOpacity = Number(opacity);
        const normalizedOpacity = Math.max(0, Math.min(1, Number.isFinite(parsedOpacity)
            ? parsedOpacity
            : 1));
        const transparent = normalizedOpacity < 0.999;
        const key = [
            'bond', style, preset,
            style === 'flat' ? this.viewportBackgroundMode : 'lit',
            color, normalizedOpacity.toFixed(4)
        ].join(':');
        if (this.materialCache.has(key)) return this.materialCache.get(key);
        let material;
        if (preset === 'unlit') {
            material = new THREE.MeshBasicMaterial({
                color,
                side: style === 'flat' ? THREE.DoubleSide : THREE.FrontSide,
                toneMapped: false,
                transparent,
                opacity: normalizedOpacity,
                depthWrite: !transparent
            });
        } else {
            const spec = ATOM_MATERIAL_PRESETS[preset];
            material = new THREE.MeshPhysicalMaterial({
                color,
                roughness: spec.roughness,
                metalness: spec.metalness,
                clearcoat: spec.clearcoat,
                clearcoatRoughness: spec.clearcoatRoughness,
                specularIntensity: spec.specularIntensity,
                envMap: preset === 'metal' ? this.ensureMetalEnvironmentMap() : null,
                envMapIntensity: spec.envMapIntensity,
                side: style === 'flat' ? THREE.DoubleSide : THREE.FrontSide,
                transparent,
                opacity: normalizedOpacity,
                depthWrite: !transparent
            });
        }
        if (style === 'flat') this.applyFlatBondShader(material);
        this.materialCache.set(key, material);
        return material;
    }

    applyFlatBondShader(material) {
        if (!material || material.userData?.flatBondOutlineApplied) return material;
        const outlineColor = this.viewportBackgroundMode === 'white'
            ? 'vec3(0.012)'
            : 'vec3(0.94)';
        material.userData.flatBondOutlineApplied = true;
        material.userData.flatBondOutlineColor = this.viewportBackgroundMode === 'white'
            ? 'dark'
            : 'light';
        material.onBeforeCompile = shader => {
            shader.vertexShader = shader.vertexShader
                .replace(
                    '#include <common>',
                    '#include <common>\nvarying vec2 vVAseBondUv;'
                )
                .replace(
                    '#include <begin_vertex>',
                    'vVAseBondUv = uv;\n#include <begin_vertex>'
                );
            shader.fragmentShader = shader.fragmentShader
                .replace(
                    '#include <common>',
                    '#include <common>\nvarying vec2 vVAseBondUv;'
                )
                .replace(
                    '#include <color_fragment>',
                    `
                    #include <color_fragment>
                    float vAseBondEdge = min(
                        min(vVAseBondUv.x, 1.0 - vVAseBondUv.x),
                        min(vVAseBondUv.y, 1.0 - vVAseBondUv.y)
                    );
                    float vAseBondAA = max(fwidth(vAseBondEdge) * 1.25, 0.006);
                    float vAseBondInterior = smoothstep(
                        0.035 - vAseBondAA,
                        0.080 + vAseBondAA,
                        vAseBondEdge
                    );
                    diffuseColor.rgb = mix(${outlineColor}, diffuseColor.rgb, vAseBondInterior);
                    `
                );
        };
        material.customProgramCacheKey = () => [
            'v-ase-flat-bond-v1',
            this.viewportBackgroundMode === 'white' ? 'dark-outline' : 'light-outline'
        ].join(':');
        material.needsUpdate = true;
        return material;
    }

    orientFlatBond(object, direction) {
        const camera = this.flatOrientationCamera || this.camera;
        const y = this.bondFlatY.copy(direction).normalize();
        const z = camera.getWorldDirection(this.bondFlatZ).multiplyScalar(-1);
        z.addScaledVector(y, -z.dot(y));
        if (z.lengthSq() < 1e-10) {
            z.copy(camera.up).addScaledVector(y, -camera.up.dot(y));
        }
        if (z.lengthSq() < 1e-10) {
            z.set(0, 0, 1).addScaledVector(y, -y.z);
        }
        if (z.lengthSq() < 1e-10) {
            z.set(1, 0, 0).addScaledVector(y, -y.x);
        }
        z.normalize();
        const x = this.bondFlatX.crossVectors(y, z).normalize();
        z.crossVectors(x, y).normalize();
        this.bondFlatBasis.makeBasis(x, y, z);
        object.quaternion.setFromRotationMatrix(this.bondFlatBasis);
    }

    positionBondMesh(bond, i, j) {
        const a = this.atomMeshByIndex.get(i);
        const b = this.atomMeshByIndex.get(j);
        if (!a || !b || !this.atomReferenceVisible(i) || !this.atomReferenceVisible(j)) {
            bond.visible = false;
            return;
        }
        const start = a.position;
        const delta = this.bondDelta(i, j, start);
        const length = delta.length();
        if (length < 1e-6) {
            bond.visible = false;
            return;
        }
        bond.visible = true;
        bond.position.copy(start).addScaledVector(delta, 0.5);
        const style = this.bondAppearance(i, j).style;
        if (style === 'flat') {
            bond.scale.set(this.bondThickness(), length, 1);
            this.orientFlatBond(bond, delta);
        } else {
            bond.scale.set(this.bondThickness(), length, this.bondThickness());
            bond.quaternion.setFromUnitVectors(this.yAxis, delta.normalize());
        }
    }

    positionBondInstance(
        mesh,
        instanceId,
        i,
        j,
        t0 = 0,
        t1 = 1,
        shift = null,
        imageOffset = null,
        thickness = this.bondThickness(),
        cellOffset = null,
        style = this.effectiveBondStyle()
    ) {
        const a = this.atomMeshByIndex.get(i);
        const b = this.atomMeshByIndex.get(j);
        const dummy = this.bondInstanceDummy;
        const startOffset = Array.isArray(cellOffset) ? cellOffset : [0, 0, 0];
        const endpointImageOffset = Array.isArray(imageOffset)
            ? imageOffset
            : (this.displayOptions.showPeriodicBonds
                ? this.minimumImageBondData(i, j).imageOffset
                : [0, 0, 0]);
        const endOffset = startOffset.map((value, axis) => (
            Number(value) + (Number(endpointImageOffset[axis]) || 0)
        ));
        const startCellReference = startOffset.some(Boolean) ? startOffset : null;
        const endCellReference = endOffset.some(Boolean) ? endOffset : null;
        if (
            !a || !b
            || !this.atomReferenceVisible(i, startCellReference)
            || !this.atomReferenceVisible(j, endCellReference)
        ) {
            this.hideBondInstance(mesh, instanceId);
            return;
        }
        const atomStart = a.position;
        const fullDelta = this.bondDeltaInto(
            this.bondDeltaScratch,
            i,
            j,
            atomStart,
            imageOffset
        );
        const fullLength = fullDelta.length();
        const length = fullLength * Math.abs(t1 - t0);
        if (!Number.isFinite(length) || length < 1e-6) {
            this.hideBondInstance(mesh, instanceId);
            return;
        }
        const midpointFactor = (t0 + t1) * 0.5;
        const centerX = atomStart.x + (shift?.x || 0) + fullDelta.x * midpointFactor;
        const centerY = atomStart.y + (shift?.y || 0) + fullDelta.y * midpointFactor;
        const centerZ = atomStart.z + (shift?.z || 0) + fullDelta.z * midpointFactor;
        if (style === 'flat') {
            dummy.position.set(centerX, centerY, centerZ);
            dummy.scale.set(thickness, length, 1);
            this.orientFlatBond(dummy, fullDelta);
            dummy.updateMatrix();
            mesh.setMatrixAt(instanceId, dummy.matrix);
        } else {
            this.writeCylinderBondInstance(
                mesh,
                instanceId,
                fullDelta,
                fullLength,
                length,
                thickness,
                centerX,
                centerY,
                centerZ
            );
        }
    }

    bondDeltaInto(target, i, j, startOverride = null, imageOffset = null) {
        const start = startOverride || this.atomMeshByIndex.get(i)?.position;
        const end = this.atomMeshByIndex.get(j)?.position;
        const fallbackStart = this.atomsData?.positions?.[i];
        const fallbackEnd = this.atomsData?.positions?.[j];
        let dx = (end?.x ?? fallbackEnd?.[0] ?? 0) - (start?.x ?? fallbackStart?.[0] ?? 0);
        let dy = (end?.y ?? fallbackEnd?.[1] ?? 0) - (start?.y ?? fallbackStart?.[1] ?? 0);
        let dz = (end?.z ?? fallbackEnd?.[2] ?? 0) - (start?.z ?? fallbackStart?.[2] ?? 0);
        const needsCell = Boolean(imageOffset || this.displayOptions.showPeriodicBonds);
        const cache = needsCell ? this.ensureCellCache() : null;

        if (imageOffset && cache?.valid) {
            const basis = cache.basis;
            dx += basis[0].x * (Number(imageOffset[0]) || 0)
                + basis[1].x * (Number(imageOffset[1]) || 0)
                + basis[2].x * (Number(imageOffset[2]) || 0);
            dy += basis[0].y * (Number(imageOffset[0]) || 0)
                + basis[1].y * (Number(imageOffset[1]) || 0)
                + basis[2].y * (Number(imageOffset[2]) || 0);
            dz += basis[0].z * (Number(imageOffset[0]) || 0)
                + basis[1].z * (Number(imageOffset[1]) || 0)
                + basis[2].z * (Number(imageOffset[2]) || 0);
        } else if (
            this.displayOptions.showPeriodicBonds
            && cache?.valid
            && (this.atomsData?.pbc || []).some(Boolean)
        ) {
            const reciprocal = cache.reciprocal;
            const pbc = this.atomsData.pbc;
            let fx = dx * reciprocal[0].x + dy * reciprocal[0].y + dz * reciprocal[0].z;
            let fy = dx * reciprocal[1].x + dy * reciprocal[1].y + dz * reciprocal[1].z;
            let fz = dx * reciprocal[2].x + dy * reciprocal[2].y + dz * reciprocal[2].z;
            if (pbc[0]) fx -= Math.round(fx);
            if (pbc[1]) fy -= Math.round(fy);
            if (pbc[2]) fz -= Math.round(fz);
            const basis = cache.basis;
            dx = fx * basis[0].x + fy * basis[1].x + fz * basis[2].x;
            dy = fx * basis[0].y + fy * basis[1].y + fz * basis[2].y;
            dz = fx * basis[0].z + fy * basis[1].z + fz * basis[2].z;
        }
        return target.set(dx, dy, dz);
    }

    hideBondInstance(mesh, instanceId) {
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        for (let index = 0; index < 15; index++) matrix[offset + index] = 0;
        matrix[offset + 15] = 1;
    }

    writeCylinderBondInstance(
        mesh,
        instanceId,
        delta,
        fullLength,
        segmentLength,
        thickness,
        centerX,
        centerY,
        centerZ
    ) {
        const inverseLength = 1 / fullLength;
        const ux = delta.x * inverseLength;
        const uy = delta.y * inverseLength;
        const uz = delta.z * inverseLength;
        const horizontal = Math.hypot(ux, uz);
        const xx = horizontal > 1e-10 ? uz / horizontal : 1;
        const xy = 0;
        const xz = horizontal > 1e-10 ? -ux / horizontal : 0;
        const zx = xy * uz - xz * uy;
        const zy = xz * ux - xx * uz;
        const zz = xx * uy - xy * ux;
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        matrix[offset] = xx * thickness;
        matrix[offset + 1] = xy * thickness;
        matrix[offset + 2] = xz * thickness;
        matrix[offset + 3] = 0;
        matrix[offset + 4] = ux * segmentLength;
        matrix[offset + 5] = uy * segmentLength;
        matrix[offset + 6] = uz * segmentLength;
        matrix[offset + 7] = 0;
        matrix[offset + 8] = zx * thickness;
        matrix[offset + 9] = zy * thickness;
        matrix[offset + 10] = zz * thickness;
        matrix[offset + 11] = 0;
        matrix[offset + 12] = centerX;
        matrix[offset + 13] = centerY;
        matrix[offset + 14] = centerZ;
        matrix[offset + 15] = 1;
    }

    hasValidCell() {
        return Boolean(this.ensureCellCache()?.valid);
    }

    rebuildSupercell() {
        this.clearGroup(this.supercellGroup);
        this.supercellBridgeBondRecords = [];
        this.domElement.dataset.supercellBridgeBondCount = '0';
        if (!this.atomsData || !this.hasValidCell()) {
            this.requestRender();
            return;
        }
        const reps = this.displayOptions.supercell || [1, 1, 1];
        if (reps.every(v => v <= 1)) {
            this.requestRender();
            return;
        }
        const cell = this.atomsData.cell.map(v => new THREE.Vector3(...v));
        this.addSupercellCellPreview(cell, reps);
        this.rebuildSupercellAtoms(cell, reps);
        this.rebuildSupercellBonds(cell, reps);
        this.applyVisualTranslation();
        this.applyShadowFlags();
        this.requestRender();
    }

    supercellAxisOffsets(count) {
        const size = Math.max(1, Math.floor(Number(count) || 1));
        const start = -Math.floor((size - 1) / 2);
        return Array.from({ length: size }, (_, index) => start + index);
    }

    supercellTranslations(cell, reps) {
        const translations = [];
        for (const ix of this.supercellAxisOffsets(reps[0])) {
            for (const iy of this.supercellAxisOffsets(reps[1])) {
                for (const iz of this.supercellAxisOffsets(reps[2])) {
                    if (ix === 0 && iy === 0 && iz === 0) continue;
                    translations.push({
                        cellOffset: [ix, iy, iz],
                        vector: new THREE.Vector3()
                            .addScaledVector(cell[0], ix)
                            .addScaledVector(cell[1], iy)
                            .addScaledVector(cell[2], iz)
                    });
                }
            }
        }
        return translations;
    }

    supercellShifts(cell, reps) {
        return this.supercellTranslations(cell, reps).map(translation => translation.vector);
    }

    rebuildSupercellAtoms(cell, reps) {
        const translations = this.supercellTranslations(cell, reps);
        const shifts = translations.map(translation => translation.vector);
        const cellOffsets = translations.map(translation => translation.cellOffset);
        if (!shifts.length) return;
        const segmentCount = this.sphereQualitySegments(this.atomsData.symbols.length);
        const fixed = this.fixedAtomDisplayEnabled()
            ? new Set(this.atomsData.constraints?.fixed_indices || [])
            : new Set();
        const groups = new Map();
        this.atomsData.symbols.forEach((sym, index) => {
            const isFixed = fixed.has(index);
            const materialPreset = this.atomMaterialPreset(index);
            const opacity = this.atomVisualOpacity(index);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            const color = this.atomVisualColor(index, this.customColors[index]);
            const perInstanceColor = this.useInstancedAtoms;
            const materialKey = perInstanceColor
                ? this.atomMaterialCacheKey(
                    '#ffffff', isFixed, atomSegments, true, materialPreset, opacity
                )
                : this.atomMaterialCacheKey(
                    color, isFixed, atomSegments, false, materialPreset, opacity
                );
            const key = perInstanceColor
                ? `${isFixed ? 'fixed' : 'normal'}:${materialPreset}:alpha-${opacity.toFixed(4)}:${atomSegments}`
                : materialKey;
            if (!groups.has(key)) {
                groups.set(key, {
                    isFixed,
                    atomSegments,
                    geometryKey,
                    materialKey,
                    materialPreset,
                    opacity,
                    color,
                    perInstanceColor,
                    indices: []
                });
            }
            groups.get(key).indices.push(index);
        });

        groups.forEach(group => {
            if (!this.geometryCache.has(group.geometryKey)) {
                this.geometryCache.set(
                    group.geometryKey,
                    new THREE.SphereGeometry(1, group.atomSegments, Math.max(8, Math.floor(group.atomSegments * 0.65)))
                );
            }
            if (!this.materialCache.has(group.materialKey)) {
                const material = group.perInstanceColor
                    ? this.createInstancedAtomMaterial(
                        group.isFixed, group.materialPreset, group.opacity
                    )
                    : this.createAtomMaterial(
                        group.color, group.isFixed, group.materialPreset, group.opacity
                    );
                this.materialCache.set(group.materialKey, material);
            }
            const total = group.indices.length * shifts.length;
            const material = this.materialCache.get(group.materialKey);
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(group.geometryKey),
                material,
                total
            );
            mesh.frustumCulled = false;
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.userData = {
                supercellInstanced: true,
                atomIndices: group.indices,
                shifts,
                cellOffsets,
                fixed: group.isFixed,
                materialPreset: group.materialPreset,
                opacity: group.opacity,
                sharedGeometry: true,
                sharedMaterial: true,
                replicaOpacity: 1
            };
            let instanceId = 0;
            shifts.forEach((shift, shiftIndex) => {
                group.indices.forEach(index => {
                    this.setSupercellInstanceMatrix(
                        mesh,
                        instanceId,
                        index,
                        shift,
                        cellOffsets[shiftIndex]
                    );
                    if (group.perInstanceColor) {
                        mesh.setColorAt(
                            instanceId,
                            this.fixedAdjustedColor(
                                this.atomVisualColor(index, this.customColors[index]),
                                group.isFixed,
                                group.materialPreset
                            )
                        );
                    }
                    instanceId++;
                });
            });
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            this.supercellGroup.add(mesh);
        });
    }

    supercellReferenceKey(index, cellOffset) {
        return `replica:${index}:${cellOffset.join(',')}`;
    }

    supercellAtomReference(mesh, instanceId) {
        if (!mesh?.userData?.supercellInstanced || !Number.isInteger(instanceId)) return null;
        const atomIndices = mesh.userData.atomIndices || [];
        if (!atomIndices.length) return null;
        const shiftIndex = Math.floor(instanceId / atomIndices.length);
        const index = atomIndices[instanceId % atomIndices.length];
        const cellOffset = mesh.userData.cellOffsets?.[shiftIndex];
        if (!Number.isInteger(index) || !Array.isArray(cellOffset)) return null;
        return {
            kind: 'replica',
            index,
            cellOffset: [...cellOffset],
            key: this.supercellReferenceKey(index, cellOffset)
        };
    }

    supercellSelectionReferences(symbol = null) {
        const references = [];
        this.supercellGroup.children.forEach(mesh => {
            if (!mesh.userData?.supercellInstanced) return;
            const atomIndices = mesh.userData.atomIndices || [];
            const cellOffsets = mesh.userData.cellOffsets || [];
            cellOffsets.forEach(cellOffset => {
                atomIndices.forEach(index => {
                    if (!this.atomReferenceVisible(index, cellOffset)) return;
                    if (symbol !== null && this.atomsData?.symbols?.[index] !== symbol) return;
                    references.push({
                        kind: 'replica',
                        index,
                        cellOffset: [...cellOffset],
                        key: this.supercellReferenceKey(index, cellOffset)
                    });
                });
            });
        });
        return references;
    }

    equivalentReplicaSelectionReferences(indices = []) {
        const selected = new Set(
            [...indices]
                .map(value => Number(value))
                .filter(Number.isInteger)
        );
        if (!selected.size) return [];
        return this.supercellSelectionReferences().filter(reference => selected.has(reference.index));
    }

    replicaSelectionPosition(reference) {
        if (!reference || reference.kind !== 'replica' || !Array.isArray(reference.cellOffset)) return null;
        const atom = this.atomMeshByIndex.get(reference.index);
        const cell = this.cellBasis();
        if (!atom || !cell) return null;
        return atom.position.clone()
            .addScaledVector(cell[0], Number(reference.cellOffset[0]) || 0)
            .addScaledVector(cell[1], Number(reference.cellOffset[1]) || 0)
            .addScaledVector(cell[2], Number(reference.cellOffset[2]) || 0);
    }

    needsSupercellBridgeBonds(repeats = this.displayOptions.supercell || [1, 1, 1]) {
        const pbc = this.atomsData?.pbc || [false, false, false];
        return Boolean(
            this.displayOptions.showBonds &&
            !this.displayOptions.showPeriodicBonds &&
            this.hasValidCell() &&
            pbc.some((periodic, axis) => periodic && Number(repeats[axis]) > 1)
        );
    }

    inferSupercellBridgeBondRecords(
        repeats = this.displayOptions.supercell || [1, 1, 1],
        candidatePairs = null
    ) {
        if (!this.needsSupercellBridgeBonds(repeats)) return [];
        const hookeanExcluded = this.hookeanBondExclusions();
        const count = this.atomsData?.positions?.length || 0;
        const pairs = this.displayOptions.bondMode === 'manual'
            ? (this.displayOptions.manualBondPairs || []).filter(([i, j]) => (
                Number.isInteger(i) && Number.isInteger(j) &&
                i >= 0 && j >= 0 && i < count && j < count && i !== j &&
                this.atomLabelVisible(i) && this.atomLabelVisible(j) &&
                !hookeanExcluded.has(this.hookeanPairKey(i, j))
            ))
            : (candidatePairs || this.inferBondPairs(true));
        const records = [];
        const seen = new Set();
        pairs.forEach(([first, second]) => {
            const i = Math.min(first, second);
            const j = Math.max(first, second);
            const { imageOffset } = this.minimumImageBondData(i, j);
            if (!imageOffset.some(Boolean)) return;
            if (!this.supercellBridgeStartOffsets(imageOffset, repeats).length) return;
            const key = `${i}:${j}:${imageOffset.join(',')}`;
            if (seen.has(key)) return;
            seen.add(key);
            records.push({ i, j, imageOffset });
        });
        records.sort((a, b) => (
            a.i - b.i || a.j - b.j ||
            a.imageOffset[0] - b.imageOffset[0] ||
            a.imageOffset[1] - b.imageOffset[1] ||
            a.imageOffset[2] - b.imageOffset[2]
        ));
        return records;
    }

    supercellBridgeBondRecordsEqual(a = [], b = []) {
        if (a.length !== b.length) return false;
        return a.every((record, index) => {
            const other = b[index];
            return record.i === other?.i && record.j === other?.j &&
                record.imageOffset.every((value, axis) => value === other.imageOffset?.[axis]);
        });
    }

    supercellBridgeStartOffsets(imageOffset, repeats) {
        const normalized = [0, 1, 2].map(axis => Math.max(1, Math.floor(Number(repeats[axis]) || 1)));
        const allowed = normalized.map(value => this.supercellAxisOffsets(value));
        const allowedSets = allowed.map(values => new Set(values));
        const offsets = [];
        for (const ix of allowed[0]) {
            for (const iy of allowed[1]) {
                for (const iz of allowed[2]) {
                    const start = [ix, iy, iz];
                    const end = start.map((value, axis) => value + (Number(imageOffset[axis]) || 0));
                    if (end.every((value, axis) => allowedSets[axis].has(value))) {
                        offsets.push(start);
                    }
                }
            }
        }
        return offsets;
    }

    cellOffsetVector(cellOffset, basis = this.cellBasis()) {
        if (!basis) return new THREE.Vector3();
        return new THREE.Vector3()
            .addScaledVector(basis[0], Number(cellOffset[0]) || 0)
            .addScaledVector(basis[1], Number(cellOffset[1]) || 0)
            .addScaledVector(basis[2], Number(cellOffset[2]) || 0);
    }

    clearSupercellBonds() {
        if (!this.supercellGroup) return;
        [...this.supercellGroup.children].forEach(child => {
            if (!child.userData?.supercellBonds) return;
            this.supercellGroup.remove(child);
            this.disposeObject(child);
        });
    }

    rebuildSupercellBonds(cell = null, reps = null, precomputedBridgeRecords = null) {
        this.clearSupercellBonds();
        this.supercellBridgeBondRecords = [];
        this.domElement.dataset.supercellBridgeBondCount = '0';
        if (!this.displayOptions.showBonds || !this.atomsData || !this.hasValidCell()) return;
        const repeats = reps || this.displayOptions.supercell || [1, 1, 1];
        if (repeats.every(value => value <= 1)) return;
        const basis = cell || this.atomsData.cell.map(values => new THREE.Vector3(...values));
        const translations = this.supercellTranslations(basis, repeats);
        if (!translations.length) return;

        const instancesByAppearance = new Map();
        const addInstance = (
            segment,
            shift,
            imageOffset = null,
            bridge = false,
            cellOffset = null
        ) => {
            const key = this.bondAppearanceKey(segment);
            if (!instancesByAppearance.has(key)) instancesByAppearance.set(key, []);
            instancesByAppearance.get(key).push({ segment, shift, imageOffset, bridge, cellOffset });
        };

        this.bondPairs.forEach(([i, j]) => {
            this.bondSegmentsForPair(i, j).forEach(segment => {
                translations.forEach(translation => addInstance(
                    segment,
                    translation.vector,
                    null,
                    false,
                    translation.cellOffset
                ));
            });
        });

        const bridgeRecords = precomputedBridgeRecords === null
            ? this.inferSupercellBridgeBondRecords(repeats)
            : precomputedBridgeRecords;
        this.supercellBridgeBondRecords = bridgeRecords.map(record => ({
            i: record.i,
            j: record.j,
            imageOffset: [...record.imageOffset]
        }));
        let bridgeBondCount = 0;
        bridgeRecords.forEach(record => {
            this.supercellBridgeStartOffsets(record.imageOffset, repeats).forEach(cellOffset => {
                const shift = this.cellOffsetVector(cellOffset, basis);
                this.bondSegmentsForPair(record.i, record.j).forEach(segment => {
                    addInstance(segment, shift, record.imageOffset, true, cellOffset);
                });
                bridgeBondCount++;
            });
        });
        this.domElement.dataset.supercellBridgeBondCount = String(bridgeBondCount);

        instancesByAppearance.forEach(bondInstances => {
            const sample = bondInstances[0].segment;
            const appearance = sample.appearance;
            const color = this.bondSegmentColor(sample);
            const flat = appearance.style === 'flat';
            const material = this.bondMaterial(
                appearance.style,
                color,
                appearance.material,
                appearance.opacity
            );
            const mesh = new THREE.InstancedMesh(
                flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
                material,
                bondInstances.length
            );
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.frustumCulled = false;
            mesh.renderOrder = -1;
            mesh.userData = {
                supercellBonds: true,
                bondInstances,
                bondColor: color,
                bondAppearance: { ...appearance },
                sharedGeometry: true,
                sharedMaterial: true,
                replicaOpacity: 1
            };
            bondInstances.forEach((instance, instanceId) => {
                const segment = instance.segment;
                this.positionBondInstance(
                    mesh,
                    instanceId,
                    segment.i,
                    segment.j,
                    segment.t0,
                    segment.t1,
                    instance.shift,
                    instance.imageOffset,
                    segment.appearance?.thickness ?? this.bondThickness(),
                    instance.cellOffset,
                    appearance.style
                );
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.supercellGroup.add(mesh);
        });
    }

    updateSupercellBondPositions() {
        this.supercellGroup.children.forEach(mesh => {
            if (!mesh.userData?.supercellBonds) return;
            (mesh.userData.bondInstances || []).forEach((instance, instanceId) => {
                const segment = instance.segment;
                this.positionBondInstance(
                    mesh,
                    instanceId,
                    segment.i,
                    segment.j,
                    segment.t0,
                    segment.t1,
                    instance.shift,
                    instance.imageOffset,
                    segment.appearance?.thickness ?? this.bondThickness(),
                    instance.cellOffset,
                    segment.appearance?.style
                );
            });
            mesh.instanceMatrix.needsUpdate = true;
        });
    }

    setSupercellInstanceMatrix(mesh, instanceId, index, shift, cellOffset = null) {
        const atom = this.atomMeshByIndex.get(index);
        const visible = atom && this.atomReferenceVisible(index, cellOffset);
        const scale = visible ? this.atomVisualRadius(index) : 0;
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        matrix[offset] = scale;
        matrix[offset + 1] = 0;
        matrix[offset + 2] = 0;
        matrix[offset + 3] = 0;
        matrix[offset + 4] = 0;
        matrix[offset + 5] = scale;
        matrix[offset + 6] = 0;
        matrix[offset + 7] = 0;
        matrix[offset + 8] = 0;
        matrix[offset + 9] = 0;
        matrix[offset + 10] = scale;
        matrix[offset + 11] = 0;
        matrix[offset + 12] = visible ? atom.position.x + shift.x : 0;
        matrix[offset + 13] = visible ? atom.position.y + shift.y : 0;
        matrix[offset + 14] = visible ? atom.position.z + shift.z : 0;
        matrix[offset + 15] = 1;
    }

    setSupercellInstanceTranslation(mesh, instanceId, index, shift) {
        const atom = this.atomMeshByIndex.get(index);
        if (!atom) return;
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        matrix[offset + 12] = atom.position.x + shift.x;
        matrix[offset + 13] = atom.position.y + shift.y;
        matrix[offset + 14] = atom.position.z + shift.z;
    }

    addSupercellCellPreview(cell, reps) {
        const edgePairs = [[0,1],[0,2],[0,3],[1,4],[1,5],[2,4],[2,6],[3,5],[3,6],[4,7],[5,7],[6,7]];
        const segments = [];
        const edgeKeys = new Set();
        const vectorKey = (point) => [point.x, point.y, point.z]
            .map(value => value.toFixed(8))
            .join(',');
        const addUniqueSegment = (start, end) => {
            const endpoints = [vectorKey(start), vectorKey(end)].sort();
            const key = endpoints.join('|');
            if (edgeKeys.has(key)) return;
            edgeKeys.add(key);
            segments.push([start, end]);
        };
        const baseCorners = (shift) => {
            const o = shift.clone();
            return [
                o,
                o.clone().add(cell[0]),
                o.clone().add(cell[1]),
                o.clone().add(cell[2]),
                o.clone().add(cell[0]).add(cell[1]),
                o.clone().add(cell[0]).add(cell[2]),
                o.clone().add(cell[1]).add(cell[2]),
                o.clone().add(cell[0]).add(cell[1]).add(cell[2])
            ];
        };
        for (const ix of this.supercellAxisOffsets(reps[0])) {
            for (const iy of this.supercellAxisOffsets(reps[1])) {
                for (const iz of this.supercellAxisOffsets(reps[2])) {
                    const shift = new THREE.Vector3()
                        .addScaledVector(cell[0], ix)
                        .addScaledVector(cell[1], iy)
                        .addScaledVector(cell[2], iz);
                    const corners = baseCorners(shift);
                    edgePairs.forEach(([i, j]) => addUniqueSegment(corners[i], corners[j]));
                }
            }
        }
        const originCorners = baseCorners(new THREE.Vector3());
        const originKeys = new Set(edgePairs.map(([i, j]) => {
            const endpoints = [vectorKey(originCorners[i]), vectorKey(originCorners[j])].sort();
            return endpoints.join('|');
        }));
        const mesh = this.addCellEdgeInstances(
            this.supercellGroup,
            segments.filter(([start, end]) => {
                const endpoints = [vectorKey(start), vectorKey(end)].sort();
                return !originKeys.has(endpoints.join('|'));
            }),
            { supercellCellPreview: true }
        );
        if (mesh) mesh.visible = this.displayOptions.showCell !== false;
    }

    updateSupercellPositions({ translationsOnly = false } = {}) {
        if (!this.supercellGroup.children.length) return;
        this.supercellGroup.children.forEach(mesh => {
            if (mesh.userData.supercellCellPreview || mesh.userData.supercellBonds) return;
            if (mesh.userData.supercellInstanced) {
                let instanceId = 0;
                mesh.userData.shifts.forEach((shift, shiftIndex) => {
                    mesh.userData.atomIndices.forEach(index => {
                        if (translationsOnly) {
                            this.setSupercellInstanceTranslation(mesh, instanceId, index, shift);
                        } else {
                            this.setSupercellInstanceMatrix(
                                mesh,
                                instanceId,
                                index,
                                shift,
                                mesh.userData.cellOffsets?.[shiftIndex]
                            );
                        }
                        instanceId++;
                    });
                });
                mesh.instanceMatrix.needsUpdate = true;
                return;
            }
        });
        this.updateSupercellBondPositions();
    }

    normalizedVector(values) {
        const v = new THREE.Vector3(...values);
        return v.lengthSq() > 1e-12 ? v.normalize() : new THREE.Vector3(1, 0, 0);
    }

    canonicalVectorKey(values) {
        const v = this.normalizedVector(values);
        const components = [v.x, v.y, v.z];
        const dominant = components.reduce((best, value, idx) => Math.abs(value) > Math.abs(components[best]) ? idx : best, 0);
        if (components[dominant] < 0) v.multiplyScalar(-1);
        return [v.x, v.y, v.z].map(value => value.toFixed(3)).join(',');
    }

    constraintGuideIndices(group) {
        if (Array.isArray(group.userData.constraintGuideIndices)) return group.userData.constraintGuideIndices;
        const idx = group.userData.constraintGuideFor;
        return idx === undefined ? [] : [idx];
    }

    constraintGuideVisible(group) {
        const indices = this.constraintGuideIndices(group);
        return indices.some(idx => this.atomReferenceVisible(idx));
    }

    orientYAxis(object, direction) {
        object.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
    }

    hookeanPairKey(i, j) {
        const a = Math.min(i, j);
        const b = Math.max(i, j);
        const atomCount = this.atomsData?.positions?.length || 1;
        return a * atomCount + b;
    }

    hookeanBondExclusions() {
        const excluded = new Set();
        (this.atomsData?.constraints?.hookean || []).forEach(item => {
            if (item.kind === 'two atoms' && item.indices?.length === 2) {
                excluded.add(this.hookeanPairKey(item.indices[0], item.indices[1]));
            }
        });
        return excluded;
    }

    rebuildConstraintGuides(selectedIndices = new Set()) {
        if (!this.atomsData?.constraints || this.displayOptions.showOverlays === false) {
            this.clearGroup(this.constraintGuideGroup);
            this.constraintGuideSignature = '';
            return;
        }
        const fixedLine = this.atomsData.constraints.fixed_line || {};
        const fixedPlane = this.atomsData.constraints.fixed_plane || {};
        const constrained = new Set([
            ...Object.keys(fixedLine).map(Number),
            ...Object.keys(fixedPlane).map(Number)
        ]);
        const constrainedIndices = [...constrained].filter(Number.isInteger).sort((a, b) => a - b);
        const signature = JSON.stringify(constrainedIndices.map(idx => ({
            index: idx,
            line: fixedLine[idx] || fixedLine[String(idx)] || null,
            plane: fixedPlane[idx] || fixedPlane[String(idx)] || null,
            radius: Number(this.atomVisualRadius?.(idx) || 0).toFixed(5)
        })));
        const expectedGuideCount = constrainedIndices.reduce((count, idx) => (
            count
            + ((fixedLine[idx] || fixedLine[String(idx)]) ? 1 : 0)
            + ((fixedPlane[idx] || fixedPlane[String(idx)]) ? 1 : 0)
        ), 0);
        if (
            signature === this.constraintGuideSignature
            && this.constraintGuideGroup.children.length === expectedGuideCount
        ) {
            this.constraintGuideGroup.children.forEach(group => {
                group.userData.selected = selectedIndices.has(group.userData.constraintGuideFor);
            });
            return;
        }

        this.clearGroup(this.constraintGuideGroup);
        this.constraintGuideSignature = signature;
        constrainedIndices.forEach(idx => {
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom) return;
            if (fixedLine[idx] || fixedLine[String(idx)]) {
                this.addFixedLineGuide(
                    idx,
                    fixedLine[idx] || fixedLine[String(idx)],
                    { selected: selectedIndices.has(idx) }
                );
            }
            const planeNormal = fixedPlane[idx] || fixedPlane[String(idx)];
            if (planeNormal) {
                this.addFixedPlaneGuide(idx, planeNormal, { selected: selectedIndices.has(idx) });
            }
        });
    }

    constraintGuideMetrics(index) {
        const atomRadius = Math.max(0.12, Number(this.atomVisualRadius?.(index) || 0.55));
        const outerRadius = THREE.MathUtils.clamp(atomRadius * 1.46, 0.34, 2.6);
        const strokeWidth = THREE.MathUtils.clamp(atomRadius * 0.09, 0.022, 0.075);
        return {
            atomRadius,
            outerRadius,
            strokeWidth,
            tubeRadius: strokeWidth * 0.5,
            lineHalfLength: THREE.MathUtils.clamp(atomRadius * 1.90, 0.46, 3.2)
        };
    }

    addFixedLineGuide(index, directionValues, options = {}) {
        const atom = this.atomMeshByIndex.get(index);
        if (!atom) return;
        const direction = this.normalizedVector(directionValues);
        const metrics = this.constraintGuideMetrics(index);
        const group = new THREE.Group();
        group.userData = {
            constraintGuideFor: index,
            kind: 'fixed_line',
            direction: direction.toArray(),
            selected: Boolean(options.selected)
        };

        const center = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.line);
        center.userData = {
            sharedMaterial: true,
            lineGuideSegment: true,
            fixedLineAxis: true
        };
        this.setLinePoints(center, [
            new THREE.Vector3(0, -metrics.lineHalfLength, 0),
            new THREE.Vector3(0, metrics.lineHalfLength, 0)
        ], 'lineGuideCenter', metrics.tubeRadius);
        group.add(center);

        group.position.copy(atom.position);
        this.orientYAxis(group, direction);
        group.renderOrder = 20;
        this.constraintGuideGroup.add(group);
    }

    addFixedPlaneGuide(index, normalValues, options = {}) {
        const atom = this.atomMeshByIndex.get(index);
        if (!atom) return;
        const normal = this.normalizedVector(normalValues);
        const planeOffset = 0.04;
        const metrics = this.constraintGuideMetrics(index);
        const group = new THREE.Group();
        group.userData = {
            constraintGuideFor: index,
            kind: 'fixed_plane',
            normal: normal.toArray(),
            anchor: atom.position.toArray(),
            planeOffset,
            selected: Boolean(options.selected)
        };

        const planeGeometry = new THREE.CircleGeometry(metrics.outerRadius, 48);
        const plane = new THREE.Mesh(planeGeometry, this.constraintMaterials.planeAggregate);
        plane.userData.sharedMaterial = true;
        plane.renderOrder = 16;
        group.add(plane);

        const half = metrics.outerRadius;
        const cross = metrics.outerRadius * 0.52;
        const crossRadius = metrics.tubeRadius * 0.72;
        const normalRadius = metrics.tubeRadius * 0.82;
        const ring = new THREE.Mesh(
            new THREE.RingGeometry(
                Math.max(0.01, half - metrics.strokeWidth),
                half,
                64
            ),
            this.constraintMaterials.planePerimeter
        );
        ring.userData = { sharedMaterial: true, fixedPlanePerimeter: true };
        ring.renderOrder = 18;
        group.add(ring);

        [
            [[-cross, 0, 0.006], [cross, 0, 0.006]],
            [[0, -cross, 0.006], [0, cross, 0.006]]
        ].forEach((axis, axisIndex) => {
            const line = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planeCrosshair);
            line.userData = { sharedMaterial: true, fixedPlaneCrosshair: true };
            this.setLinePoints(line, axis.map(p => new THREE.Vector3(...p)), `fixedPlaneCrosshair${axisIndex}`, crossRadius);
            line.renderOrder = 19;
            group.add(line);
        });

        const tickLength = THREE.MathUtils.clamp(metrics.atomRadius * 0.72, 0.20, 1.0);
        const normalTick = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planeNormal);
        normalTick.userData = { sharedMaterial: true, fixedPlaneNormalTick: true };
        this.setLinePoints(normalTick, [
            new THREE.Vector3(0, 0, 0.08),
            new THREE.Vector3(0, 0, tickLength)
        ], 'fixedPlaneNormalTick', normalRadius);
        normalTick.renderOrder = 20;
        group.add(normalTick);

        group.position.copy(atom.position).addScaledVector(normal, -planeOffset);
        group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
        group.renderOrder = 19;
        this.constraintGuideGroup.add(group);
        this.updateFixedPlaneGuideMotion(group, atom);
    }

    clearConstraintMotionGuides() {
        this.clearGroup(this.constraintMotionGuideGroup);
        this.requestRender();
    }

    setConstraintMotionGuides({
        mode = 'IDLE',
        indices = [],
        originalPositions = [],
        applyConstraints = true
    } = {}) {
        this.clearGroup(this.constraintMotionGuideGroup);
        if (
            mode !== 'MOVE'
            || !applyConstraints
            || this.displayOptions.showOverlays === false
            || !this.atomsData?.constraints
        ) {
            this.requestRender();
            return;
        }

        const fixedLine = this.atomsData.constraints.fixed_line || {};
        const fixedPlane = this.atomsData.constraints.fixed_plane || {};
        if (Object.keys(fixedLine).length === 0 && Object.keys(fixedPlane).length === 0) {
            this.requestRender();
            return;
        }
        const guideSize = Math.max(3.4, Math.min(10.0, (this.desiredGuideSize?.() || 24) * 0.18));
        const edgeWidth = THREE.MathUtils.clamp(guideSize * 0.012, 0.024, 0.065);
        const axisRadius = edgeWidth * 0.42;
        [...new Set(indices.map(Number).filter(Number.isInteger))].forEach(index => {
            const lineValues = fixedLine[index] || fixedLine[String(index)];
            const normalValues = fixedPlane[index] || fixedPlane[String(index)];
            const source = originalPositions[index];
            const atom = this.atomMeshByIndex.get(index);
            if ((!lineValues && !normalValues) || (!source && !atom) || !this.atomReferenceVisible(index)) return;
            const anchor = source
                ? new THREE.Vector3(...source)
                : atom.position.clone();

            if (lineValues) {
                const direction = this.normalizedVector(lineValues);
                const lineGroup = new THREE.Group();
                lineGroup.userData = {
                    kind: 'fixed_line_motion',
                    atomIndex: index,
                    anchor: anchor.toArray(),
                    direction: direction.toArray()
                };
                const line = new THREE.Mesh(
                    new THREE.BufferGeometry(),
                    this.constraintMaterials.lineMotion
                );
                line.userData = {
                    sharedMaterial: true,
                    fixedLineMotionAxis: true
                };
                this.setLinePoints(line, [
                    new THREE.Vector3(0, -guideSize, 0),
                    new THREE.Vector3(0, guideSize, 0)
                ], 'fixedLineMotionAxis', Math.max(axisRadius, edgeWidth * 0.52));
                line.renderOrder = 26;
                lineGroup.add(line);
                lineGroup.position.copy(anchor);
                this.orientYAxis(lineGroup, direction);
                lineGroup.renderOrder = 26;
                this.constraintMotionGuideGroup.add(lineGroup);
            }

            if (!normalValues) return;
            const normal = this.normalizedVector(normalValues);
            const group = new THREE.Group();
            group.userData = {
                kind: 'fixed_plane_motion',
                atomIndex: index,
                anchor: anchor.toArray(),
                normal: normal.toArray()
            };

            const disk = new THREE.Mesh(
                new THREE.PlaneGeometry(guideSize * 2, guideSize * 2, 1, 1),
                this.constraintMaterials.planeMotion
            );
            disk.userData = { sharedMaterial: true, fixedPlaneMotionSurface: true };
            disk.renderOrder = 24;
            group.add(disk);

            const perimeter = new THREE.LineSegments(
                new THREE.EdgesGeometry(
                    new THREE.PlaneGeometry(guideSize * 2, guideSize * 2, 1, 1)
                ),
                this.constraintMaterials.planeMotionPerimeter
            );
            perimeter.userData = { sharedMaterial: true, fixedPlaneMotionPerimeter: true };
            perimeter.renderOrder = 25;
            group.add(perimeter);

            const axisLength = guideSize * 0.78;
            [
                [[-axisLength, 0, 0.01], [axisLength, 0, 0.01]],
                [[0, -axisLength, 0.01], [0, axisLength, 0.01]]
            ].forEach((points, axisIndex) => {
                const line = new THREE.Mesh(
                    new THREE.BufferGeometry(),
                    this.constraintMaterials.planeMotionAxis
                );
                line.userData = {
                    sharedMaterial: true,
                    fixedPlaneMotionAxis: true,
                    axisIndex
                };
                this.setLinePoints(
                    line,
                    points.map(point => new THREE.Vector3(...point)),
                    `fixedPlaneMotionAxis${axisIndex}`,
                    axisRadius
                );
                line.renderOrder = 26;
                group.add(line);
            });

            group.position.copy(anchor).addScaledVector(normal, -0.055);
            group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
            group.renderOrder = 24;
            this.constraintMotionGuideGroup.add(group);
        });
        this.applyVisualTranslation();
        this.requestRender();
    }

    fixedPlaneBasis(normal) {
        const n = normal.clone().normalize();
        const seed = Math.abs(n.z) < 0.86 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
        const u = new THREE.Vector3().crossVectors(seed, n).normalize();
        const v = new THREE.Vector3().crossVectors(n, u).normalize();
        return { u, v, n };
    }

    selectedPlaneCenter(indices) {
        const center = new THREE.Vector3();
        let count = 0;
        indices.forEach(idx => {
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom || !this.atomReferenceVisible(idx)) return;
            center.add(atom.position);
            count += 1;
        });
        return count ? center.multiplyScalar(1 / count) : null;
    }

    addFixedPlaneGuideGroup(indices, normalValues) {
        const normal = this.normalizedVector(normalValues);
        const center = this.selectedPlaneCenter(indices);
        if (!center) return;
        const planeOffset = 0.045;
        const group = new THREE.Group();
        group.userData = {
            constraintGuideIndices: [...indices],
            kind: 'fixed_plane_group',
            normal: normal.toArray(),
            planeOffset
        };

        const { u, v, n } = this.fixedPlaneBasis(normal);
        let maxSpan = 0;
        indices.forEach(idx => {
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom) return;
            const delta = atom.position.clone().sub(center);
            maxSpan = Math.max(maxSpan, Math.abs(delta.dot(u)), Math.abs(delta.dot(v)));
        });
        const guideSize = Math.max(8, Math.min(96, maxSpan * 2 + Math.max(5.5, (this.desiredGuideSize?.() || 18) * 0.18)));
        const plane = new THREE.Mesh(new THREE.PlaneGeometry(guideSize, guideSize), this.constraintMaterials.planeAggregate);
        plane.userData.sharedMaterial = true;
        plane.renderOrder = 15;
        group.add(plane);

        const half = guideSize * 0.5;
        const cross = guideSize * 0.28;
        const edgeRadius = Math.max(0.010, guideSize * 0.0014);
        const crossRadius = Math.max(0.010, guideSize * 0.0015);
        const normalRadius = Math.max(0.012, guideSize * 0.0019);
        [
            [[-half, -half, 0.002], [half, -half, 0.002]],
            [[half, -half, 0.002], [half, half, 0.002]],
            [[half, half, 0.002], [-half, half, 0.002]],
            [[-half, half, 0.002], [-half, -half, 0.002]]
        ].forEach((edge, edgeIndex) => {
            const line = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planePerimeter);
            line.userData = { sharedMaterial: true, fixedPlanePerimeter: true };
            this.setLinePoints(line, edge.map(p => new THREE.Vector3(...p)), `fixedPlaneGroupEdge${edgeIndex}`, edgeRadius);
            line.renderOrder = 17;
            group.add(line);
        });

        [
            [[-cross, 0, 0.006], [cross, 0, 0.006]],
            [[0, -cross, 0.006], [0, cross, 0.006]]
        ].forEach((axis, axisIndex) => {
            const line = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planeCrosshair);
            line.userData = { sharedMaterial: true, fixedPlaneCrosshair: true };
            this.setLinePoints(line, axis.map(p => new THREE.Vector3(...p)), `fixedPlaneGroupCrosshair${axisIndex}`, crossRadius);
            line.renderOrder = 18;
            group.add(line);
        });

        const tickLength = Math.max(0.9, Math.min(2.6, guideSize * 0.07));
        const normalTick = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planeNormal);
        normalTick.userData = { sharedMaterial: true, fixedPlaneNormalTick: true };
        this.setLinePoints(normalTick, [
            new THREE.Vector3(0, 0, 0.08),
            new THREE.Vector3(0, 0, tickLength)
        ], 'fixedPlaneGroupNormalTick', normalRadius);
        normalTick.renderOrder = 20;
        group.add(normalTick);

        indices.forEach((idx, markIndex) => {
            const marker = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planeCrosshair);
            marker.userData = { sharedMaterial: true, fixedPlaneAtomMarker: true, atomIndex: idx, markIndex };
            group.add(marker);
        });

        group.renderOrder = 19;
        this.constraintGuideGroup.add(group);
        this.updateFixedPlaneGuideGroupMotion(group, { u, v, n });
    }

    rebuildHookeanConstraints() {
        this.clearGroup(this.hookeanGroup);
        const hookeans = this.atomsData?.constraints?.hookean || [];
        hookeans.forEach(item => {
            if (item.kind === 'two atoms' && item.indices?.length === 2) {
                this.addHookeanSpring({ kind: 'two_atoms', i: item.indices[0], j: item.indices[1], item });
            } else if (item.kind === 'point' && item.origin) {
                this.addHookeanSpring({ kind: 'point', i: item.index, point: new THREE.Vector3(...item.origin), item });
            } else if (item.kind === 'plane' && item.plane) {
                this.addHookeanPlane(item);
            }
        });
        this.updateHookeanPositions();
    }

    addHookeanSpring(spec) {
        const group = new THREE.Group();
        group.userData = { hookean: spec };

        const hookLine = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.hookeanGuide);
        hookLine.userData = { sharedMaterial: true, hookLine: true };
        group.add(hookLine);

        const catchLine = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.hookeanThresholdMarker);
        catchLine.userData = { sharedMaterial: true, catchLine: true };
        group.add(catchLine);

        const spring = new THREE.Mesh(
            new THREE.BufferGeometry(),
            this.atomDisplayMode() === '2d'
                ? this.constraintMaterials.hookeanFlat
                : this.constraintMaterials.hookean
        );
        spring.userData = { sharedMaterial: true, springLine: true };
        group.add(spring);

        const gapLine = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.hookeanSlack);
        gapLine.userData = { sharedMaterial: true, gapLine: true };
        group.add(gapLine);

        const lockPin = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.hookeanActiveMarker);
        lockPin.userData = { sharedMaterial: true, lockPin: true };
        group.add(lockPin);

        this.hookeanGroup.add(group);
    }

    addHookeanPlane(item) {
        const group = new THREE.Group();
        group.userData = { hookean: { kind: 'plane', item } };
        const disk = new THREE.Mesh(new THREE.CircleGeometry(1.25, 64), this.constraintMaterials.plane);
        const rim = new THREE.Mesh(new THREE.RingGeometry(1.21, 1.26, 80), this.constraintMaterials.hookeanRing);
        disk.userData.sharedMaterial = true;
        rim.userData.sharedMaterial = true;
        group.add(disk, rim);
        this.hookeanGroup.add(group);
    }

    makeSpringPoints(length, radius = 0.13, turns = 8, samples = 120) {
        const points = [];
        const usable = Math.max(0.001, length);
        for (let i = 0; i <= samples; i++) {
            const t = i / samples;
            const angle = t * Math.PI * 2 * turns;
            points.push(new THREE.Vector3(
                Math.cos(angle) * radius,
                (t - 0.5) * usable,
                Math.sin(angle) * radius
            ));
        }
        return points;
    }

    makeHelicalSpringPoints(startY, endY, radius = 0.13, turns = 8, samples = 120) {
        if (endY - startY < 1e-4) return [
            new THREE.Vector3(0, startY, 0),
            new THREE.Vector3(0, endY, 0)
        ];
        const span = endY - startY;
        const lead = Math.min(0.14, span * 0.12);
        const coilStart = startY + lead;
        const coilEnd = endY - lead;
        const coilSpan = Math.max(0.001, coilEnd - coilStart);
        const count = Math.max(32, Math.round(samples));
        const points = [new THREE.Vector3(0, startY, 0)];
        for (let i = 0; i <= count; i++) {
            const t = i / count;
            const angle = t * Math.PI * 2 * turns;
            const ramp = Math.min(1, t * 8, (1 - t) * 8);
            const localRadius = radius * Math.max(0, ramp);
            points.push(new THREE.Vector3(
                Math.cos(angle) * localRadius,
                THREE.MathUtils.lerp(coilStart, coilEnd, t),
                Math.sin(angle) * localRadius
            ));
        }
        points.push(new THREE.Vector3(0, endY, 0));
        return points;
    }

    setLinePoints(line, points, key, radius = 0.026) {
        const signature = points
            .map(p => `${p.x.toFixed(4)},${p.y.toFixed(4)},${p.z.toFixed(4)}`)
            .join('|') + `:${radius.toFixed(4)}`;
        if (line.userData[key] === signature) return;
        line.geometry.dispose();
        const curve = new THREE.CatmullRomCurve3(points);
        line.geometry = new THREE.TubeGeometry(curve, Math.max(8, points.length * 5), radius, 8, false);
        line.userData[key] = signature;
    }

    hookeanEndpointRadius(spec, endpoint) {
        if (endpoint === 'a') return this.atomVisualRadius(spec.i);
        if (endpoint === 'b' && spec.kind === 'two_atoms') return this.atomVisualRadius(spec.j);
        return 0.18;
    }

    hookeanState(length, threshold) {
        if (!Number.isFinite(threshold) || threshold <= 0) return 'active';
        const numericalTolerance = Math.max(1e-7, Math.abs(threshold) * 1e-7);
        if (Math.abs(length - threshold) <= numericalTolerance) return 'threshold';
        return length < threshold ? 'inactive' : 'active';
    }

    hookeanStateMaterial(state) {
        if (state === 'active') return this.constraintMaterials.hookeanActiveMarker;
        if (state === 'threshold') return this.constraintMaterials.hookeanThresholdMarker;
        return this.constraintMaterials.hookeanInactiveMarker;
    }

    hookeanSpringWireRadius() {
        return 0.022;
    }

    updateHookeanLatchGeometry(group, spec, length) {
        const threshold = Number(spec.item?.threshold);
        const state = this.hookeanState(length, threshold);
        const radiusA = this.hookeanEndpointRadius(spec, 'a');
        const radiusB = this.hookeanEndpointRadius(spec, 'b');
        const leftCenter = -length / 2;
        const rightCenter = length / 2;
        const left = leftCenter + Math.min(radiusA * 0.55 + 0.04, length * 0.24);
        const right = rightCenter - Math.min(radiusB * 0.55 + 0.04, length * 0.24);
        const span = Math.max(0.12, Math.abs(right - left));
        const gateWidth = THREE.MathUtils.clamp(span * 0.09, 0.12, 0.28);
        const lockHalf = THREE.MathUtils.clamp(span * 0.045, 0.08, 0.18);
        const thresholdY = Number.isFinite(threshold) && threshold > 0
            ? leftCenter + threshold
            : left + span * 0.52;
        const springStart = thresholdY;
        const springEnd = right;
        const springLength = Math.max(0.001, springEnd - springStart);
        // Keep enough pitch between turns for the helix to read as a spring
        // instead of collapsing into a solid tube at short extensions.
        const coils = THREE.MathUtils.clamp(Math.round(springLength / 0.18), 3, 14);

        const hookLine = group.children.find(child => child.userData.hookLine);
        const catchLine = group.children.find(child => child.userData.catchLine);
        const springLine = group.children.find(child => child.userData.springLine);
        const gapLine = group.children.find(child => child.userData.gapLine);
        const lockPin = group.children.find(child => child.userData.lockPin);

        // Dead-zone rail: the Hookean force is inactive until this exact cutoff.
        this.setLinePoints(hookLine, [
            new THREE.Vector3(0, left, 0),
            new THREE.Vector3(0, thresholdY, 0)
        ], 'hookSignature', 0.018);
        hookLine.material = this.constraintMaterials.hookeanGuide;
        hookLine.userData.sharedMaterial = true;

        // Cutoff gate: a simple crossbar, not a symbolic hook/arrow.
        this.setLinePoints(catchLine, [
            new THREE.Vector3(-gateWidth, thresholdY, 0),
            new THREE.Vector3(gateWidth, thresholdY, 0)
        ], 'catchSignature', state === 'inactive' ? 0.024 : 0.034);
        catchLine.material = this.hookeanStateMaterial(state);
        catchLine.userData.sharedMaterial = true;

        if (lockPin) {
            lockPin.visible = state !== 'inactive';
            if (lockPin.visible) {
                this.setLinePoints(lockPin, [
                    new THREE.Vector3(0, thresholdY - lockHalf, 0),
                    new THREE.Vector3(0, thresholdY + lockHalf, 0)
                ], 'lockSignature', 0.034);
                lockPin.material = this.hookeanStateMaterial(state);
                lockPin.userData.sharedMaterial = true;
            }
        }

        springLine.visible = state !== 'inactive' && springEnd > springStart;
        if (springLine.visible) {
            const coilRadius = THREE.MathUtils.clamp(
                Math.min(radiusA, radiusB) * 0.38,
                0.20,
                0.32
            );
            this.setLinePoints(springLine, this.makeHelicalSpringPoints(
                springStart,
                springEnd,
                Math.min(coilRadius, span * 0.14),
                coils,
                Math.max(72, coils * 18)
            ), 'springSignature', this.hookeanSpringWireRadius());
        }
        springLine.material = state === 'inactive'
            ? this.constraintMaterials.hookeanInactive
            : (this.atomDisplayMode() === '2d'
                ? this.constraintMaterials.hookeanFlat
                : this.constraintMaterials.hookean);
        springLine.userData.sharedMaterial = true;

        gapLine.visible = state === 'inactive' && thresholdY > right;
        if (gapLine.visible) {
            this.setLinePoints(gapLine, [
                new THREE.Vector3(0, right, 0),
                new THREE.Vector3(0, thresholdY, 0)
            ], 'gapSignature', 0.014);
        }

        group.userData.hookeanState = state;
        group.userData.hookeanDistance = length;
        group.userData.hookeanThreshold = Number.isFinite(threshold) ? threshold : null;
        group.userData.hookeanExtension = Number.isFinite(threshold) ? Math.max(0, length - threshold) : length;
    }

    updateHookeanPositions() {
        this.hookeanGroup.children.forEach(group => {
            const spec = group.userData.hookean;
            if (!spec) return;
            if (spec.kind === 'plane') {
                const item = spec.item;
                const atom = this.atomMeshByIndex.get(item.index);
                if (!atom || !this.atomReferenceVisible(item.index)) {
                    group.visible = false;
                    return;
                }
                group.visible = true;
                const [A, B, C, D] = item.plane;
                const normal = this.normalizedVector([A, B, C]);
                const signed = (A * atom.position.x + B * atom.position.y + C * atom.position.z + D) /
                    Math.max(Math.sqrt(A * A + B * B + C * C), 1e-9);
                group.position.copy(atom.position).addScaledVector(normal, -signed);
                group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
                group.userData.hookeanState = signed > 0 ? 'active' : 'inactive';
                group.children.forEach(child => {
                    if (child.userData?.sharedMaterial) {
                        child.material = signed > 0
                            ? this.constraintMaterials.hookeanActiveMarker
                            : this.constraintMaterials.plane;
                    }
                });
                return;
            }

            const atom = this.atomMeshByIndex.get(spec.i);
            if (
                !atom
                || !this.atomReferenceVisible(spec.i)
                || (spec.kind === 'two_atoms' && !this.atomReferenceVisible(spec.j))
            ) {
                group.visible = false;
                return;
            }
            const start = atom.position.clone();
            const end = spec.kind === 'two_atoms'
                ? (this.atomMeshByIndex.has(spec.j) ? start.clone().add(this.minimumImageDelta(spec.i, spec.j, start)) : null)
                : spec.point?.clone();
            if (!end) return;
            const delta = new THREE.Vector3().subVectors(end, start);
            const length = delta.length();
            if (length < 1e-6) {
                group.visible = false;
                return;
            }
            group.visible = true;
            const center = start.clone().addScaledVector(delta, 0.5);
            const direction = delta.clone().normalize();
            group.position.copy(center);
            this.orientYAxis(group, direction);

            this.updateHookeanLatchGeometry(group, spec, length);
        });
    }

    syncConstraintGuides() {
        this.constraintGuideGroup.children.forEach(group => {
            if (!this.constraintGuideVisible(group)) {
                group.visible = false;
                return;
            }
            group.visible = true;
            if (group.userData.kind === 'fixed_plane_group') {
                this.updateFixedPlaneGuideGroupMotion(group);
                return;
            }
            const atom = this.atomMeshByIndex.get(group.userData.constraintGuideFor);
            if (!atom) {
                group.visible = false;
                return;
            }
            if (group.userData.kind === 'fixed_plane') {
                this.updateFixedPlaneGuideMotion(group, atom);
            } else {
                group.position.copy(atom.position);
            }
        });
    }

    updateFixedPlaneGuideMotion(group, atom) {
        const normal = this.normalizedVector(group.userData.normal);
        const planeOffset = Number(group.userData.planeOffset || 0);
        group.position.copy(atom.position).addScaledVector(normal, -planeOffset);
        group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
    }

    updateFixedPlaneGuideGroupMotion(group, basis = null) {
        const normal = this.normalizedVector(group.userData.normal);
        const indices = this.constraintGuideIndices(group);
        const center = this.selectedPlaneCenter(indices);
        if (!center) {
            group.visible = false;
            return;
        }
        const planeOffset = Number(group.userData.planeOffset || 0);
        group.position.copy(center).addScaledVector(normal, -planeOffset);
        group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);

        const inverse = group.quaternion.clone().invert();
        group.children.forEach(child => {
            if (!child.userData.fixedPlaneAtomMarker) return;
            const idx = child.userData.atomIndex;
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom || !this.atomReferenceVisible(idx)) {
                child.visible = false;
                return;
            }
            child.visible = true;
            const local = atom.position.clone().sub(center).applyQuaternion(inverse);
            local.z = 0.012;
            const markerSize = Math.max(0.18, Math.min(0.52, (this.atomVisualRadius?.(idx) || 0.5) * 0.42));
            this.setLinePoints(child, [
                new THREE.Vector3(local.x - markerSize, local.y, local.z),
                new THREE.Vector3(local.x + markerSize, local.y, local.z)
            ], `fixedPlaneGroupAtomMarker${child.userData.markIndex}`, Math.max(0.010, markerSize * 0.035));
            child.renderOrder = 21;
        });
    }

    clearSelectionOutlines() {
        this.clearGroup(this.selectionOutlines);
    }

    clearReplicaSelectionOutlines() {
        this.clearGroup(this.replicaSelectionOutlines);
    }

    setReplicaSelection(references = [], { muted = false } = {}) {
        this.clearReplicaSelectionOutlines();
        const visible = [...references].filter(reference =>
            reference?.kind === 'replica' &&
            this.atomReferenceVisible(reference.index, reference.cellOffset) &&
            this.replicaSelectionPosition(reference)
        );
        if (!visible.length) {
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }
        const outline = new THREE.InstancedMesh(
            this.selectionOutlineGeometry,
            muted ? this.replicaSelectionMutedMaterial : this.selectionOutlineMaterial,
            visible.length
        );
        outline.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        outline.frustumCulled = false;
        outline.renderOrder = 10;
        outline.userData = {
            replicaSelectionInstances: true,
            references: visible.map(reference => ({
                ...reference,
                cellOffset: [...reference.cellOffset]
            })),
            muted: Boolean(muted),
            sharedGeometry: true,
            sharedMaterial: true
        };
        visible.forEach((reference, instanceId) => {
            this.setReplicaSelectionInstanceMatrix(outline, instanceId, reference);
        });
        outline.instanceMatrix.needsUpdate = true;
        this.replicaSelectionOutlines.add(outline);
        this.applyOverlayVisibility();
        this.requestRender();
    }

    setSelection(selectedIndices) {
        this.clearSelectionOutlines();
        const selected = new Set(selectedIndices);
        const visibleIndices = [...selected].filter(
            idx => this.atomMeshByIndex.has(idx) && this.atomReferenceVisible(idx)
        );
        if (visibleIndices.length >= 64) {
            const outline = new THREE.InstancedMesh(
                this.selectionOutlineGeometry,
                this.selectionOutlineMaterial,
                visibleIndices.length
            );
            outline.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            outline.frustumCulled = false;
            outline.renderOrder = 10;
            outline.userData = {
                selectionInstances: true,
                atomIndices: visibleIndices,
                sharedGeometry: true,
                sharedMaterial: true
            };
            visibleIndices.forEach((idx, instanceId) => this.setSelectionInstanceMatrix(outline, instanceId, idx));
            outline.instanceMatrix.needsUpdate = true;
            this.selectionOutlines.add(outline);
            this.rebuildConstraintGuides(selected);
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }
        selected.forEach(idx => {
            const mesh = this.atomMeshByIndex.get(idx);
            if (!mesh || !this.atomReferenceVisible(idx)) return;
            const radius = this.atomVisualRadius(idx);
            const outlineGeo = new THREE.SphereGeometry(radius * 1.18, 32, 18);
            const outlineMat = new THREE.MeshBasicMaterial({
                color: 0xffc400,
                side: THREE.BackSide,
                transparent: true,
                opacity: 1.0,
                depthWrite: false
            });
            const outline = new THREE.Mesh(outlineGeo, outlineMat);
            outline.position.copy(mesh.position);
            outline.userData = { outlineFor: idx };
            outline.renderOrder = 10;
            this.selectionOutlines.add(outline);
        });
        this.rebuildConstraintGuides(selected);
        this.applyOverlayVisibility();
        this.requestRender();
    }

    setSelectionInstanceMatrix(mesh, instanceId, index) {
        const atom = this.atomMeshByIndex.get(index);
        const visible = atom && this.atomReferenceVisible(index);
        const scale = visible ? this.atomVisualRadius(index) * 1.18 : 0;
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        matrix[offset] = scale;
        matrix[offset + 1] = 0;
        matrix[offset + 2] = 0;
        matrix[offset + 3] = 0;
        matrix[offset + 4] = 0;
        matrix[offset + 5] = scale;
        matrix[offset + 6] = 0;
        matrix[offset + 7] = 0;
        matrix[offset + 8] = 0;
        matrix[offset + 9] = 0;
        matrix[offset + 10] = scale;
        matrix[offset + 11] = 0;
        matrix[offset + 12] = visible ? atom.position.x : 0;
        matrix[offset + 13] = visible ? atom.position.y : 0;
        matrix[offset + 14] = visible ? atom.position.z : 0;
        matrix[offset + 15] = 1;
    }

    setReplicaSelectionInstanceMatrix(mesh, instanceId, reference) {
        const position = this.replicaSelectionPosition(reference);
        const visible = position && this.atomReferenceVisible(reference.index, reference.cellOffset);
        const outlineScale = mesh.userData?.muted ? 1.11 : 1.18;
        const scale = visible ? this.atomVisualRadius(reference.index) * outlineScale : 0;
        const matrix = mesh.instanceMatrix.array;
        const offset = instanceId * 16;
        matrix[offset] = scale;
        matrix[offset + 1] = 0;
        matrix[offset + 2] = 0;
        matrix[offset + 3] = 0;
        matrix[offset + 4] = 0;
        matrix[offset + 5] = scale;
        matrix[offset + 6] = 0;
        matrix[offset + 7] = 0;
        matrix[offset + 8] = 0;
        matrix[offset + 9] = 0;
        matrix[offset + 10] = scale;
        matrix[offset + 11] = 0;
        matrix[offset + 12] = visible ? position.x : 0;
        matrix[offset + 13] = visible ? position.y : 0;
        matrix[offset + 14] = visible ? position.z : 0;
        matrix[offset + 15] = 1;
    }

    syncReplicaSelectionOutlines() {
        this.replicaSelectionOutlines.children.forEach(outline => {
            if (!outline.userData.replicaSelectionInstances) return;
            outline.userData.references.forEach((reference, instanceId) => {
                this.setReplicaSelectionInstanceMatrix(outline, instanceId, reference);
            });
            outline.instanceMatrix.needsUpdate = true;
        });
    }

    syncSelectionOutlines() {
        this.selectionOutlines.children.forEach(outline => {
            if (outline.userData.selectionInstances) {
                outline.userData.atomIndices.forEach((idx, instanceId) => {
                    this.setSelectionInstanceMatrix(outline, instanceId, idx);
                });
                outline.instanceMatrix.needsUpdate = true;
                return;
            }
            const idx = outline.userData.outlineFor;
            const mesh = this.atomMeshByIndex.get(idx);
            if (!mesh || !this.atomReferenceVisible(idx)) {
                outline.visible = false;
                return;
            }
            outline.visible = true;
            outline.position.copy(mesh.position);
        });
        this.syncReplicaSelectionOutlines();
        this.syncConstraintGuides();
    }

    onResize() {
        if (this.suspended) return;
        const pixelsPerAngstrom = this.currentPixelsPerAngstrom();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.updateCameraProjection();
        this.setPixelsPerAngstrom(pixelsPerAngstrom, { requestRender: false, notify: false });
        this.onCameraChange?.({ source: 'resize' });
        this.requestRender();
    }

    exportPNG(width, height, options = {}) {
        const capture = this.beginExportCapture(width, height, options);
        try {
            this.renderExportCaptureFrame(capture);
            return this.renderer.domElement.toDataURL('image/png');
        } finally {
            this.endExportCapture(capture);
        }
    }

    async exportPNGBlob(width, height, options = {}) {
        const capture = this.beginExportCapture(width, height, options);
        try {
            this.renderExportCaptureFrame(capture);
            const blob = await new Promise((resolve, reject) => {
                this.renderer.domElement.toBlob(
                    result => result
                        ? resolve(result)
                        : reject(new Error('Canvas PNG encoding failed.')),
                    'image/png'
                );
            });
            return blob;
        } finally {
            this.endExportCapture(capture);
        }
    }

    setSuspended(suspended) {
        const next = Boolean(suspended);
        if (this.suspended === next) return;
        this.suspended = next;
        if (next) {
            if (this.renderRequestId !== null) {
                cancelAnimationFrame(this.renderRequestId);
                this.renderRequestId = null;
            }
            this.controls.enabled = false;
            return;
        }
        this.controls.enabled = true;
        this.onResize();
    }

    requestRender() {
        if (this.suspended || this.exportCaptureActive) return;
        if (this.renderRequestId !== null) return;
        this.renderRequestId = requestAnimationFrame(() => {
            this.renderRequestId = null;
            if (this.suspended) return;
            this.renderFrame();
        });
    }

    renderFrame() {
        if (this.suspended) return;
        this.controls.update();
        if (this.effectiveBondStyle() === 'flat') this.updateBondPositions();
        if (this.displacementStyle() === '2d') this.updateDisplacementVectorMatrices();
        if (this.forceVectorStyle() === '2d') this.updateForceVectorMatrices();
        this.updateFlatCellEdgeMatrices();
        this.syncSelectionOutlines();
        this.onFrame?.();
        this.updateViewLighting();
        this.renderer.render(this.scene, this.camera);
        this.renderExportPreview();
        this.renderCount += 1;
        this.domElement.dataset.renderCount = String(this.renderCount);
    }

    renderNow() {
        if (this.suspended) return;
        if (this.renderRequestId !== null) {
            cancelAnimationFrame(this.renderRequestId);
            this.renderRequestId = null;
        }
        this.renderFrame();
    }

    animate() {
        this.requestRender();
    }

    dispose() {
        if (this.renderRequestId !== null) {
            cancelAnimationFrame(this.renderRequestId);
            this.renderRequestId = null;
        }
        this.suspended = true;
        this.controls?.dispose?.();

        const geometries = new Set(this.geometryCache?.values?.() || []);
        const materials = new Set(this.materialCache?.values?.() || []);
        this.scene?.traverse?.(object => {
            if (object.geometry) geometries.add(object.geometry);
            const objectMaterials = Array.isArray(object.material)
                ? object.material
                : object.material ? [object.material] : [];
            objectMaterials.forEach(material => materials.add(material));
        });
        geometries.forEach(geometry => geometry?.dispose?.());
        materials.forEach(material => {
            for (const value of Object.values(material || {})) {
                if (value?.isTexture) value.dispose?.();
            }
            material?.dispose?.();
        });
        this.metalEnvironmentRenderTarget?.dispose?.();
        if (
            this.metalEnvironmentMap
            && this.metalEnvironmentMap !== this.metalEnvironmentRenderTarget?.texture
        ) {
            this.metalEnvironmentMap.dispose?.();
        }

        this.geometryCache?.clear?.();
        this.materialCache?.clear?.();
        this.atomMeshByIndex?.clear?.();
        this.atomInstanceRefs?.clear?.();
        this.atomInstanceMeshes?.clear?.();
        this.volumetricPlanes?.clear?.();
        this.renderer?.renderLists?.dispose?.();
        this.renderer?.dispose?.();
        this.renderer?.forceContextLoss?.();
        this.domElement?.remove?.();
        this.onFrame = null;
        this.onCameraChange = null;
        this.onLightingChange = null;
    }
}
