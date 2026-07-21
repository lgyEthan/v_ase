import * as THREE from 'three';

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
        this.onWindowBlur = () => this.endGesture(null, { force: true });

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
        event.preventDefault();
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

    doZoom(deltaY) {
        const factor = Math.exp(deltaY * this.zoomSpeed);
        if (this.camera.isOrthographicCamera) {
            this.camera.zoom = Math.max(0.05, Math.min(80, this.camera.zoom / factor));
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
        if (this.activePointerId !== null && this.domElement.hasPointerCapture?.(this.activePointerId)) {
            this.domElement.releasePointerCapture(this.activePointerId);
        }
        this.removeWindowGestureListeners();
        document.body.style.userSelect = this.previousUserSelect;
        this.state = 'idle';
        this.activePointerId = null;
        this.activeButton = null;
        this.activeButtonsMask = 0;
    }

    update() {
        return false;
    }
}

const FALLBACK_ATOM_COLOR = '#cccccc';
const FALLBACK_ATOM_RADIUS = 0.7;
const FALLBACK_COVALENT_RADIUS = 0.75;
const COVALENT_BOND_TOLERANCE = 1.2;

export class ASERenderer {
    constructor(container) {
        this.container = container;
        this.renderRequestId = null;
        this.renderCount = 0;
        this.setupScene();
        this.setLightingOptions(this.lightingOptions);
        this.requestRender();
    }

    setupScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x303235);
        
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
        this.renderer.setClearColor(0x303235, 1);
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.renderer.shadowMap.enabled = false;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.domElement = this.renderer.domElement;
        this.container.appendChild(this.renderer.domElement);

        this.controls = new BlenderTumbleControls(this.camera, this.renderer.domElement);
        this.controls.onChange = () => this.requestRender();

        this.modelingLightGroup = new THREE.Group();
        this.modelingLightGroup.name = 'v_ase_modeling_lights';
        this.scene.add(this.modelingLightGroup);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x6a7078, 1.18);
        this.modelingLightGroup.add(hemiLight);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.68);
        this.modelingLightGroup.add(ambientLight);
        
        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.50);
        dirLight1.position.set(10, 20, 10);
        this.modelingLightGroup.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.50);
        dirLight2.position.set(-10, -20, 10);
        this.modelingLightGroup.add(dirLight2);

        const dirLight3 = new THREE.DirectionalLight(0xffffff, 0.36);
        dirLight3.position.set(12, -14, 8);
        this.modelingLightGroup.add(dirLight3);

        const dirLight4 = new THREE.DirectionalLight(0xffffff, 0.34);
        dirLight4.position.set(-12, 14, -8);
        this.modelingLightGroup.add(dirLight4);

        this.cameraFillLight = new THREE.PointLight(0xffffff, 1.15, 0, 1.35);
        this.modelingLightGroup.add(this.cameraFillLight);
        this.cameraFillTarget = new THREE.Object3D();
        this.modelingLightGroup.add(this.cameraFillTarget);
        this.cameraFillDirectionalLight = new THREE.DirectionalLight(0xffffff, 0.48);
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

        this.viewportGuides = this.buildViewportGuides();
        this.gridGroup = this.viewportGuides.gridGroup;
        this.axesHelper = this.viewportGuides.axisGroup;
        this.scene.add(this.gridGroup);
        this.scene.add(this.axesHelper);

        this.atomMeshes = new THREE.Group();
        this.scene.add(this.atomMeshes);

        this.selectionOutlines = new THREE.Group();
        this.scene.add(this.selectionOutlines);

        this.cellGroup = new THREE.Group();
        this.scene.add(this.cellGroup);
        this.bondGroup = new THREE.Group();
        this.scene.add(this.bondGroup);
        this.strainViolationGroup = new THREE.Group();
        this.scene.add(this.strainViolationGroup);
        this.supercellGroup = new THREE.Group();
        this.scene.add(this.supercellGroup);
        this.constraintMarkGroup = new THREE.Group();
        this.scene.add(this.constraintMarkGroup);
        this.constraintGuideGroup = new THREE.Group();
        this.scene.add(this.constraintGuideGroup);
        this.hookeanGroup = new THREE.Group();
        this.scene.add(this.hookeanGroup);
        this.atomMeshByIndex = new Map();
        this.atomInstanceRefs = new Map();
        this.atomInstanceMeshes = new Set();
        this.atomIndicesBySymbol = new Map();
        this.useInstancedAtoms = false;
        this.instanceDummy = new THREE.Object3D();
        this.bondInstanceDummy = new THREE.Object3D();
        this.yAxis = new THREE.Vector3(0, 1, 0);
        this.geometryCache = new Map();
        this.materialCache = new Map();
        this.atomsData = null;
        this.cellCache = null;
        this.needsInitialCameraFit = true;
        this.customColors = {};
        this.displayOptions = {
            showCell: true,
            showAxes: true,
            showGrid: true,
            showBonds: false,
            showPeriodicBonds: false,
            bondMode: 'auto',
            bondCutoffScale: 1.0,
            manualBondPairs: [],
            elementBondCutoffs: {},
            bondStyle: 'cylinder',
            bondThickness: 0.11,
            bondColorMode: 'split',
            bondCustomColor: '#c8ccd0',
            atomRadiusScale: 1.0,
            elementRadii: {},
            elementColors: {},
            elementVisible: {},
            rotatePivot: 'selection',
            unitCellAwareRotate: false,
            rotateStrainCutoff: 0.15,
            projectionMode: 'orthographic',
            showOverlays: true,
            supercell: [1, 1, 1],
            antiAliasing: true,
            sphereQuality: 'auto',
            vizOnly: false,
            lightingMode: 'modeling',
            sunIntensity: 2.2,
            sunPosition: [8, -10, 14],
            sunTarget: [0, 0, 0],
            sunGizmo: false
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
        this.bondCylinderGeometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 16);
        this.bondFlatGeometry = new THREE.PlaneGeometry(1, 1);
        this.bondFlatBasis = new THREE.Matrix4();
        this.bondFlatX = new THREE.Vector3();
        this.bondFlatY = new THREE.Vector3();
        this.bondFlatZ = new THREE.Vector3();
        this.strainViolationGeometry = new THREE.CylinderGeometry(0.085, 0.085, 1, 24);
        this.strainViolationMaterial = new THREE.MeshBasicMaterial({
            color: 0xff3b30,
            transparent: true,
            opacity: 0.88,
            depthWrite: false
        });
        this.selectionOutlineGeometry = new THREE.SphereGeometry(1, 18, 12);
        this.selectionOutlineMaterial = new THREE.MeshBasicMaterial({
            color: 0xffc400,
            side: THREE.BackSide,
            transparent: true,
            opacity: 1.0,
            depthWrite: false
        });
        this.constraintMaterials = {
            line: new THREE.MeshBasicMaterial({
                color: 0x76d7f2,
                transparent: true,
                opacity: 0.46,
                depthTest: true,
                depthWrite: false
            }),
            lineFade: new THREE.MeshBasicMaterial({
                color: 0x76d7f2,
                transparent: true,
                opacity: 0.16,
                depthTest: true,
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
            hookean: new THREE.MeshBasicMaterial({
                color: 0xff9f43,
                transparent: true,
                opacity: 0.92,
                depthWrite: false
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

    normalizedLightingVector(value, fallback) {
        if (!Array.isArray(value) || value.length < 3) return [...fallback];
        return value.slice(0, 3).map((component, index) => {
            const parsed = Number(component);
            return Number.isFinite(parsed) ? parsed : fallback[index];
        });
    }

    setLightingOptions(options = {}) {
        const previousMode = this.lightingOptions?.lightingMode || 'modeling';
        const mode = ['studio', 'studio-shadow'].includes(options.lightingMode)
            ? options.lightingMode
            : 'modeling';
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

        const studio = mode !== 'modeling';
        this.modelingLightGroup.visible = !studio;
        this.studioLightGroup.visible = studio;
        this.studioSunLight.intensity = this.lightingOptions.sunIntensity;
        this.applyStudioSunDirection();
        this.sunGizmoGroup.visible = studio && sunGizmo;
        if (!this.sunGizmoGroup.visible) this.setSunGizmoSelected(false);
        this.renderer.toneMapping = studio ? THREE.ACESFilmicToneMapping : THREE.NoToneMapping;
        this.renderer.toneMappingExposure = studio ? 1.05 : 1.0;
        this.domElement.dataset.lightingMode = mode;
        this.domElement.dataset.shadowMode = mode === 'studio-shadow' ? 'true' : 'false';
        this.setShadowMode(mode === 'studio-shadow');
        this.syncSunGizmo();
        if (previousMode !== mode && mode === 'studio-shadow') this.fitSunShadowCamera();
        this.requestRender();
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
        [this.atomMeshes, this.bondGroup, this.supercellGroup].forEach(group => {
            group?.traverse?.(object => {
                if (!object.isMesh) return;
                object.castShadow = enabled;
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
            if (!proxy || proxy.visible === false || !this.atomTypeVisible(index)) return;
            const radius = Math.max(0.05, Number(this.atomVisualRadius(index) || 0.5));
            low.copy(proxy.position).addScalar(-radius);
            high.copy(proxy.position).addScalar(radius);
            base.expandByPoint(low);
            base.expandByPoint(high);
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

    setSunGizmoSelected(handle) {
        const requested = handle === true ? 'source' : handle;
        this.sunGizmoSelected = this.sunGizmoGroup?.visible && ['source', 'target'].includes(requested)
            ? requested
            : null;
        const sourceRing = this.sunGizmoGroup?.userData?.sourceSelectionRing;
        const targetShell = this.sunGizmoGroup?.userData?.targetSelectionShell;
        if (sourceRing) sourceRing.visible = this.sunGizmoSelected === 'source';
        if (targetShell) targetShell.visible = this.sunGizmoSelected === 'target';
        this.requestRender();
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

    atomVisualRadius(index) {
        const symbol = this.atomsData?.symbols?.[index];
        const elementRadius = Number(this.displayOptions?.elementRadii?.[symbol]);
        const sourceRadius = Number.isFinite(elementRadius) && elementRadius > 0
            ? elementRadius
            : Number(this.atomsData?.visual?.radii?.[index]);
        const scale = Number(this.displayOptions?.atomRadiusScale || 1);
        const radius = Number.isFinite(sourceRadius) && sourceRadius > 0 ? sourceRadius : FALLBACK_ATOM_RADIUS;
        return radius * (Number.isFinite(scale) && scale > 0 ? scale : 1);
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
        const symbol = this.atomsData?.symbols?.[index];
        const elementColor = this.displayOptions?.elementColors?.[symbol];
        if (this.validHexColor(elementColor)) return elementColor;
        if (this.validHexColor(explicitColor)) return explicitColor;
        const color = this.atomsData?.visual?.colors?.[index];
        return this.validHexColor(color) ? color : FALLBACK_ATOM_COLOR;
    }

    fixedAtomDisplayEnabled() {
        return this.displayOptions.showOverlays !== false;
    }

    atomMaterialSpec(color, isFixed = false) {
        const base = new THREE.Color(color);
        if (!isFixed) {
            return {
                color: base,
                roughness: 0.42,
                metalness: 0.08,
                emissive: base.clone().multiplyScalar(0.08),
                emissiveIntensity: 0.28,
                flatShading: false
            };
        }
        return {
            color: base,
            roughness: 0.98,
            metalness: 0.0,
            emissive: base.clone().multiplyScalar(0.04),
            emissiveIntensity: 0.20,
            flatShading: true
        };
    }

    createAtomMaterial(color, isFixed = false) {
        const spec = this.atomMaterialSpec(color, isFixed);
        const material = new THREE.MeshStandardMaterial({
            color: spec.color,
            roughness: spec.roughness,
            metalness: spec.metalness,
            emissive: spec.emissive,
            emissiveIntensity: spec.emissiveIntensity,
            flatShading: spec.flatShading,
            transparent: false,
            opacity: 1.0
        });
        if (isFixed) this.applyFixedAtomEtchedShader(material);
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

    fixedAdjustedColor(color, isFixed = false) {
        return this.atomMaterialSpec(color, isFixed).color;
    }

    atomTypeVisible(index) {
        const symbol = this.atomsData?.symbols?.[index];
        return !symbol || this.displayOptions?.elementVisible?.[symbol] !== false;
    }

    rebuildAtomSymbolIndex() {
        this.atomIndicesBySymbol.clear();
        (this.atomsData?.symbols || []).forEach((symbol, index) => {
            if (!this.atomIndicesBySymbol.has(symbol)) this.atomIndicesBySymbol.set(symbol, []);
            this.atomIndicesBySymbol.get(symbol).push(index);
        });
    }

    applyAtomVisibility(changedSymbols = null) {
        const affectedIndices = changedSymbols?.length
            ? changedSymbols.flatMap(symbol => this.atomIndicesBySymbol.get(symbol) || [])
            : null;
        if (this.useInstancedAtoms) {
            const updateIndex = (index) => {
                const proxy = this.atomMeshByIndex.get(index);
                if (!proxy) return;
                proxy.visible = this.atomTypeVisible(index);
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
                outline.visible = this.atomTypeVisible(idx);
            });
            this.constraintMarkGroup.children.forEach(group => {
                const idx = group.userData.constraintGuideFor;
                group.visible = this.atomTypeVisible(idx);
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
            if (mesh) mesh.visible = this.atomTypeVisible(index);
        });
        this.selectionOutlines.children.forEach(outline => {
            const idx = outline.userData.outlineFor;
            outline.visible = this.atomTypeVisible(idx);
        });
        this.constraintMarkGroup.children.forEach(group => {
            const idx = group.userData.constraintGuideFor;
            group.visible = this.atomTypeVisible(idx);
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
        const grid = new THREE.GridHelper(guideSize, divisions, 0x5a5d62, 0x42454a);
        grid.rotation.x = Math.PI / 2;
        grid.material.transparent = true;
        grid.material.opacity = 0.58;
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
        axisGroup.add(makeLine([-half, 0, 0], [half, 0, 0], 0xff5a52, 0.68));
        axisGroup.add(makeLine([0, -half, 0], [0, half, 0], 0x44d665, 0.68));
        axisGroup.add(makeLine([0, 0, -half], [0, 0, half], 0x4da0ff, 0.62));
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
        // Remove existing meshes cleanly
        while(this.atomMeshes.children.length > 0){ 
            const child = this.atomMeshes.children[0];
            this.atomMeshes.remove(child); 
        }
        while(this.cellGroup.children.length > 0){
            const child = this.cellGroup.children[0];
            this.cellGroup.remove(child);
            if(child.geometry) child.geometry.dispose();
            if(child.material) child.material.dispose();
        }
        this.clearGroup(this.bondGroup);
        this.clearGroup(this.strainViolationGroup);
        this.clearGroup(this.supercellGroup);
        this.clearGroup(this.constraintMarkGroup);
        this.clearGroup(this.constraintGuideGroup);
        this.clearGroup(this.hookeanGroup);
        this.clearSelectionOutlines();
        this.atomMeshByIndex.clear();
        this.atomInstanceRefs.clear();
        this.atomInstanceMeshes.clear();
        this.atomIndicesBySymbol.clear();
        this.atomsData = atoms;
        this.invalidateCellCache();
        this.customColors = customColors || {};
        this.updateRenderQuality();
        this.refreshViewportGuidesForStructure();
        
        if (!atoms || !atoms.symbols) return;

        this.rebuildAtomSymbolIndex();
        const fixed = this.fixedAtomDisplayEnabled() ? new Set(atoms.constraints?.fixed_indices || []) : new Set();
        const segmentCount = this.sphereQualitySegments(atoms.symbols.length);
        this.useInstancedAtoms = this.shouldUseInstancedAtoms(atoms);
        if (this.useInstancedAtoms) {
            this.rebuildInstancedAtoms(atoms, this.customColors, fixed, segmentCount);
            this.rebuildCell(atoms.cell);
            this.rebuildBonds();
            this.rebuildHookeanConstraints();
            this.rebuildSupercell();
            this.applyOverlayVisibility();
            if (this.needsInitialCameraFit) {
                this.fitCameraToStructure();
                this.needsInitialCameraFit = false;
            }
            this.applyShadowFlags();
            this.refreshStudioSunForStructure({ invalidate: false });
            this.requestRender();
            return;
        }
        atoms.symbols.forEach((sym, i) => {
            const radius = this.atomVisualRadius(i);
            const color = this.atomVisualColor(i, customColors[i]);
            const isFixed = fixed.has(i);

            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(1, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
                );
            }
            const materialKey = `${color}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(materialKey, this.createAtomMaterial(color, isFixed));
            }
            const geo = this.geometryCache.get(geometryKey);
            const mat = this.materialCache.get(materialKey);
            const mesh = new THREE.Mesh(geo, mat);
            
            const pos = atoms.positions[i];
            mesh.position.set(pos[0], pos[1], pos[2]);
            mesh.scale.setScalar(radius);
            mesh.userData = { index: i, symbol: sym, fixed: isFixed };
            mesh.visible = this.atomTypeVisible(i);
            
            this.atomMeshes.add(mesh);
            this.atomMeshByIndex.set(i, mesh);

        });

        this.rebuildCell(atoms.cell);
        this.rebuildBonds();
        this.rebuildHookeanConstraints();
        this.rebuildSupercell();
        this.applyOverlayVisibility();
        if (this.needsInitialCameraFit) {
            this.fitCameraToStructure();
            this.needsInitialCameraFit = false;
        }
        this.applyShadowFlags();
        this.refreshStudioSunForStructure({ invalidate: false });
        this.requestRender();
    }

    shouldUseInstancedAtoms(atoms) {
        const count = atoms?.symbols?.length || 0;
        return count >= 256 || (this.displayOptions.vizOnly && count >= 128);
    }

    atomProxy(index, position, symbol, fixed = false) {
        return {
            position: position.clone(),
            visible: this.atomTypeVisible(index),
            userData: { index, symbol, fixed }
        };
    }

    rebuildInstancedAtoms(atoms, customColors, fixed, segmentCount) {
        const groups = new Map();
        atoms.symbols.forEach((sym, i) => {
            const isFixed = fixed.has(i);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            const materialKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:instanced`;
            const key = `${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!groups.has(key)) {
                groups.set(key, { geometryKey, materialKey, fixed: isFixed, segments: atomSegments, indices: [] });
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
                const spec = this.atomMaterialSpec('#ffffff', group.fixed);
                const material = new THREE.MeshStandardMaterial({
                    color: 0xffffff,
                    roughness: spec.roughness,
                    metalness: spec.metalness,
                    emissive: spec.emissive,
                    emissiveIntensity: spec.emissiveIntensity,
                    flatShading: spec.flatShading
                });
                if (group.fixed) this.applyFixedAtomEtchedShader(material);
                this.materialCache.set(group.materialKey, material);
            }
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(group.geometryKey),
                this.materialCache.get(group.materialKey),
                group.indices.length
            );
            mesh.userData = { instancedAtoms: true, atomIndices: group.indices, sharedGeometry: true, sharedMaterial: true };
            mesh.frustumCulled = false;
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            this.atomMeshes.add(mesh);
            this.atomInstanceMeshes.add(mesh);

            group.indices.forEach((index, instanceId) => {
                const position = new THREE.Vector3(...atoms.positions[index]);
                const proxy = this.atomProxy(index, position, atoms.symbols[index], fixed.has(index));
                this.atomMeshByIndex.set(index, proxy);
                this.atomInstanceRefs.set(index, { mesh, instanceId });
                mesh.setColorAt(instanceId, this.fixedAdjustedColor(this.atomVisualColor(index, customColors[index]), fixed.has(index)));
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
        const visible = proxy.visible !== false && this.atomTypeVisible(index);
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

    sphereQualitySegments(atomCount = 0) {
        const quality = this.displayOptions.sphereQuality || 'auto';
        if (quality === 'low') return 12;
        if (quality === 'medium') return 24;
        if (quality === 'high') return 40;
        if (quality === 'ultra') return 64;
        return atomCount > 1500 ? 12 : atomCount > 400 ? 18 : 32;
    }

    fixedAtomSegments(segmentCount) {
        return Math.max(10, Math.min(18, Math.floor(segmentCount * 0.55)));
    }

    structureBounds() {
        const box = new THREE.Box3();
        let hasPoint = false;
        if (this.atomsData?.positions?.length) {
            this.atomsData.positions.forEach((position, index) => {
                if (!position || position.length < 3) return;
                const [x, y, z] = position.map(Number);
                if (![x, y, z].every(Number.isFinite)) return;
                const radius = this.atomVisualRadius(index);
                box.min.x = Math.min(box.min.x, x - radius);
                box.min.y = Math.min(box.min.y, y - radius);
                box.min.z = Math.min(box.min.z, z - radius);
                box.max.x = Math.max(box.max.x, x + radius);
                box.max.y = Math.max(box.max.y, y + radius);
                box.max.z = Math.max(box.max.z, z + radius);
                hasPoint = true;
            });
        }

        if (this.hasValidCell()) {
            const [a, b, c] = this.atomsData.cell.map(v => new THREE.Vector3(...v));
            const corners = [
                new THREE.Vector3(0, 0, 0),
                a,
                b,
                c,
                a.clone().add(b),
                a.clone().add(c),
                b.clone().add(c),
                a.clone().add(b).add(c)
            ];
            corners.forEach(point => box.expandByPoint(point));
            hasPoint = true;
        }

        return hasPoint && !box.isEmpty() ? box : null;
    }

    fitCameraToStructure() {
        const box = this.structureBounds();
        if (!box) return;
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        box.getCenter(center);
        box.getSize(size);
        const radius = Math.max(size.length() * 0.5, 1.0);

        const currentDirection = new THREE.Vector3().subVectors(this.camera.position, this.controls.target);
        if (currentDirection.lengthSq() < 1e-10) {
            currentDirection.set(1, 1, 0.8);
        }
        currentDirection.normalize();

        const aspect = this.viewportAspect();
        const verticalFov = THREE.MathUtils.degToRad(this.perspectiveCamera?.fov || this.camera.fov || 50);
        const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * Math.max(aspect, 1e-6));
        const fitFov = Math.max(0.1, Math.min(verticalFov, horizontalFov));
        const distance = Math.max(4.0, (radius / Math.sin(fitFov / 2)) * 1.18);

        this.controls.target.copy(center);
        this.camera.position.copy(center).addScaledVector(currentDirection, distance);
        this.camera.near = Math.max(0.01, distance / 1000);
        this.camera.far = Math.max(1000, distance + radius * 20);
        this.camera.lookAt(center);
        if (this.camera !== this.perspectiveCamera) {
            this.perspectiveCamera.position.copy(this.camera.position);
            this.perspectiveCamera.up.copy(this.camera.up);
        }
        if (this.camera !== this.orthographicCamera) {
            this.orthographicCamera.position.copy(this.camera.position);
            this.orthographicCamera.up.copy(this.camera.up);
        }
        this.perspectiveCamera.near = this.camera.near;
        this.perspectiveCamera.far = this.camera.far;
        this.orthographicCamera.near = this.camera.near;
        this.orthographicCamera.far = this.camera.far;
        this.updateCameraProjection(aspect);
        this.controls.update?.();
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
        const nextMode = mode === 'orthographic' ? 'orthographic' : 'perspective';
        if (nextMode === this.projectionMode) {
            this.updateCameraProjection();
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
        this.requestRender();
    }

    updateViewLighting() {
        if (!this.camera) return;
        if (this.modelingLightGroup?.visible && this.cameraFillLight) {
            this.cameraFillLight.position.copy(this.camera.position);
            if (this.cameraFillDirectionalLight && this.cameraFillTarget) {
                this.cameraFillDirectionalLight.position.copy(this.camera.position);
                this.cameraFillTarget.position.copy(this.controls?.target || new THREE.Vector3());
                this.cameraFillDirectionalLight.target.updateMatrixWorld();
            }
        }
        this.updateSunGizmoScale();
    }

    rebuildCell(cell) {
        this.clearGroup(this.cellGroup);
        this.invalidateCellCache();
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
        const points = [];
        edgePairs.forEach(([i, j]) => {
            points.push(corners[i], corners[j]);
        });
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const mat = new THREE.LineBasicMaterial({ color: 0x8b7f6a, transparent: true, opacity: 0.65 });
        this.cellGroup.add(new THREE.LineSegments(geo, mat));
        this.cellGroup.visible = this.displayOptions.showCell;
        this.requestRender();
    }

    updatePositions(positions) {
        if (this.atomsData) {
            this.atomsData.positions = positions;
        }
        if (this.useInstancedAtoms) {
            positions.forEach((p, idx) => {
                const proxy = this.atomMeshByIndex.get(idx);
                if (!proxy || !p) return;
                proxy.position.set(p[0], p[1], p[2]);
                proxy.visible = this.atomTypeVisible(idx);
                this.updateAtomInstanceMatrix(idx);
            });
            this.flushAtomInstances();
            this.syncSelectionOutlines();
            this.syncConstraintGuides();
            this.refreshBondsForCurrentPositions();
            this.updateSupercellPositions();
            this.updateHookeanPositions();
            this.refreshStudioSunForStructure();
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
        this.updateSupercellPositions();
        this.updateHookeanPositions();
        this.refreshStudioSunForStructure();
        this.requestRender();
    }

    updatePositionsFlat(values, offset = 0, count = this.atomsData?.positions?.length || 0) {
        if (!values || !count) return;
        if (this.useInstancedAtoms) {
            for (let idx = 0; idx < count; idx++) {
                const base = offset + idx * 3;
                const proxy = this.atomMeshByIndex.get(idx);
                if (!proxy) continue;
                proxy.position.set(values[base], values[base + 1], values[base + 2]);
                proxy.visible = this.atomTypeVisible(idx);
                this.updateAtomInstanceMatrix(idx);
            }
            this.flushAtomInstances();
            this.syncSelectionOutlines();
            this.syncConstraintGuides();
            this.refreshBondsForCurrentPositions();
            this.updateSupercellPositions();
            this.updateHookeanPositions();
            this.refreshStudioSunForStructure();
            return;
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
        this.updateSupercellPositions();
        this.updateHookeanPositions();
        this.refreshStudioSunForStructure();
        this.requestRender();
    }

    setDisplayOptions(options, { rebuild = true } = {}) {
        const previous = {
            ...this.displayOptions,
            manualBondPairs: [...(this.displayOptions.manualBondPairs || [])],
            elementBondCutoffs: { ...(this.displayOptions.elementBondCutoffs || {}) },
            elementRadii: { ...(this.displayOptions.elementRadii || {}) },
            elementColors: { ...(this.displayOptions.elementColors || {}) },
            elementVisible: { ...(this.displayOptions.elementVisible || {}) },
            supercell: [...(this.displayOptions.supercell || [1, 1, 1])],
            sunPosition: [...(this.displayOptions.sunPosition || [8, -10, 14])],
            sunTarget: [...(this.displayOptions.sunTarget || [0, 0, 0])]
        };
        this.displayOptions = {
            ...this.displayOptions,
            ...options,
            manualBondPairs: [...(options.manualBondPairs || this.displayOptions.manualBondPairs || [])],
            elementBondCutoffs: { ...(options.elementBondCutoffs || this.displayOptions.elementBondCutoffs || {}) },
            elementRadii: { ...(options.elementRadii || this.displayOptions.elementRadii || {}) },
            elementColors: { ...(options.elementColors || this.displayOptions.elementColors || {}) },
            elementVisible: { ...(options.elementVisible || this.displayOptions.elementVisible || {}) },
            supercell: [...(options.supercell || this.displayOptions.supercell || [1, 1, 1])],
            sunPosition: [...(options.sunPosition || this.displayOptions.sunPosition || [8, -10, 14])],
            sunTarget: [...(options.sunTarget || this.displayOptions.sunTarget || [0, 0, 0])]
        };
        const antiAliasingChanged = previous.antiAliasing !== this.displayOptions.antiAliasing;
        const sphereQualityChanged = previous.sphereQuality !== this.displayOptions.sphereQuality;
        const radiusChanged = previous.atomRadiusScale !== this.displayOptions.atomRadiusScale ||
            JSON.stringify(previous.elementRadii || {}) !== JSON.stringify(this.displayOptions.elementRadii || {});
        const colorChanged = JSON.stringify(previous.elementColors || {}) !== JSON.stringify(this.displayOptions.elementColors || {});
        const overlayChanged = previous.showOverlays !== this.displayOptions.showOverlays;
        const visibilityChanged = JSON.stringify(previous.elementVisible || {}) !== JSON.stringify(this.displayOptions.elementVisible || {});
        const changedVisibilitySymbols = visibilityChanged
            ? [...new Set([
                ...Object.keys(previous.elementVisible || {}),
                ...Object.keys(this.displayOptions.elementVisible || {})
            ])].filter(symbol => previous.elementVisible?.[symbol] !== this.displayOptions.elementVisible?.[symbol])
            : [];
        const supercellChanged = JSON.stringify(previous.supercell || [1, 1, 1]) !== JSON.stringify(this.displayOptions.supercell || [1, 1, 1]);
        const lightingChanged = previous.lightingMode !== this.displayOptions.lightingMode ||
            previous.sunIntensity !== this.displayOptions.sunIntensity ||
            previous.sunGizmo !== this.displayOptions.sunGizmo ||
            JSON.stringify(previous.sunPosition || []) !== JSON.stringify(this.displayOptions.sunPosition || []) ||
            JSON.stringify(previous.sunTarget || []) !== JSON.stringify(this.displayOptions.sunTarget || []);
        if (previous.projectionMode !== this.displayOptions.projectionMode) {
            this.setProjectionMode(this.displayOptions.projectionMode);
        }
        if (lightingChanged) this.setLightingOptions(this.displayOptions);
        if (!rebuild) {
            if (antiAliasingChanged) this.updateRenderQuality();
            this.cellGroup.visible = this.displayOptions.showCell;
            if (this.axesHelper) this.axesHelper.visible = this.displayOptions.showAxes;
            if (this.gridGroup) this.gridGroup.visible = this.displayOptions.showGrid;
            this.applyOverlayVisibility();
            this.requestRender();
            return;
        }
        if (antiAliasingChanged) this.updateRenderQuality();
        if (sphereQualityChanged || overlayChanged) {
            if (this.atomsData) {
                this.rebuildAtoms(this.atomsData, this.customColors);
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
        this.cellGroup.visible = this.displayOptions.showCell;
        if (this.axesHelper) this.axesHelper.visible = this.displayOptions.showAxes;
        if (this.gridGroup) this.gridGroup.visible = this.displayOptions.showGrid;
        this.applyOverlayVisibility();
        const bondsChanged = previous.showBonds !== this.displayOptions.showBonds ||
            previous.showPeriodicBonds !== this.displayOptions.showPeriodicBonds ||
            previous.bondMode !== this.displayOptions.bondMode ||
            previous.bondCutoffScale !== this.displayOptions.bondCutoffScale ||
            previous.bondStyle !== this.displayOptions.bondStyle ||
            previous.bondThickness !== this.displayOptions.bondThickness ||
            previous.bondColorMode !== this.displayOptions.bondColorMode ||
            previous.bondCustomColor !== this.displayOptions.bondCustomColor ||
            (colorChanged && this.displayOptions.bondColorMode === 'split') ||
            JSON.stringify(previous.manualBondPairs || []) !== JSON.stringify(this.displayOptions.manualBondPairs || []) ||
            JSON.stringify(previous.elementBondCutoffs || {}) !== JSON.stringify(this.displayOptions.elementBondCutoffs || {}) ||
            visibilityChanged;
        if (visibilityChanged) this.applyAtomVisibility(changedVisibilitySymbols);
        else if (bondsChanged) this.rebuildBonds();
        if (supercellChanged) this.rebuildSupercell();
        if ((radiusChanged || supercellChanged) && !visibilityChanged) {
            this.refreshStudioSunForStructure();
        }
        this.requestRender();
    }

    applyOverlayVisibility() {
        const visible = this.displayOptions.showOverlays !== false;
        if (this.selectionOutlines) this.selectionOutlines.visible = visible;
        if (this.constraintGuideGroup) this.constraintGuideGroup.visible = visible;
        if (this.constraintMarkGroup) this.constraintMarkGroup.visible = visible;
        if (this.hookeanGroup) this.hookeanGroup.visible = visible;
    }

    renameAtomType(oldSymbol, label, indices = [], displayOptions = null, baseSymbol = null) {
        if (!this.atomsData?.symbols) return;
        indices.forEach(index => {
            if (this.atomsData.symbols[index] === oldSymbol) {
                this.atomsData.symbols[index] = label;
            }
            if (baseSymbol && Array.isArray(this.atomsData.chemical_symbols)) {
                this.atomsData.chemical_symbols[index] = baseSymbol;
            }
            const mesh = this.atomMeshByIndex.get(index);
            if (mesh?.userData) mesh.userData.symbol = label;
        });
        this.rebuildAtomSymbolIndex();
        if (displayOptions) {
            this.displayOptions = {
                ...this.displayOptions,
                ...displayOptions,
                manualBondPairs: [...(displayOptions.manualBondPairs || this.displayOptions.manualBondPairs || [])],
                elementBondCutoffs: { ...(displayOptions.elementBondCutoffs || this.displayOptions.elementBondCutoffs || {}) },
                elementRadii: { ...(displayOptions.elementRadii || this.displayOptions.elementRadii || {}) },
                elementColors: { ...(displayOptions.elementColors || this.displayOptions.elementColors || {}) },
                elementVisible: { ...(displayOptions.elementVisible || this.displayOptions.elementVisible || {}) },
                supercell: [...(displayOptions.supercell || this.displayOptions.supercell || [1, 1, 1])]
            };
        }
        this.refreshAtomAppearance(indices);
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
                    this.fixedAdjustedColor(this.atomVisualColor(index, this.customColors[index]), Boolean(proxy.userData.fixed))
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
            const isFixed = Boolean(mesh.userData.fixed) && this.fixedAtomDisplayEnabled();
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(1, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
                );
            }
            const materialKey = `${color}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(materialKey, this.createAtomMaterial(color, isFixed));
            }
            mesh.geometry = this.geometryCache.get(geometryKey);
            mesh.material = this.materialCache.get(materialKey);
            mesh.scale.setScalar(radius);
            mesh.visible = this.atomTypeVisible(index);
        });
        this.requestRender();
    }

    inferBondPairs() {
        if (!this.atomsData || !this.atomsData.positions) return [];
        // Interactive transforms re-run inference on every visual update. Use
        // the spatial index early enough to keep medium-sized edits responsive.
        if (this.atomsData.positions.length > 384) return this.inferBondPairsCellList();
        const pairs = [];
        const hookeanExcluded = this.hookeanBondExclusions();
        const count = this.atomsData.positions.length;
        for (let i = 0; i < count; i++) {
            if (!this.atomTypeVisible(i)) continue;
            const pi = this.getAtomPosition(i);
            for (let j = i + 1; j < count; j++) {
                if (!this.atomTypeVisible(j)) continue;
                if (hookeanExcluded.has(this.hookeanPairKey(i, j))) continue;
                const cutoff = this.bondCutoffForPair(i, j);
                if (!Number.isFinite(cutoff) || cutoff <= 0) continue;
                const d = this.bondDelta(i, j, pi).length();
                if (d > 0.15 && d <= cutoff) pairs.push([i, j]);
            }
        }
        return pairs;
    }

    bondCutoffForPair(i, j) {
        if (this.displayOptions.bondMode === 'element') {
            return this.elementBondCutoff(this.atomChemicalSymbol(i), this.atomChemicalSymbol(j));
        }
        return this.autoBondCutoff(i, j);
    }

    elementPairKey(a, b) {
        return [a, b].sort().join('-');
    }

    elementBondCutoff(a, b) {
        const cutoffs = this.displayOptions.elementBondCutoffs || {};
        const value = Number(cutoffs[this.elementPairKey(a, b)]);
        return Number.isFinite(value) ? value : null;
    }

    autoBondCutoff(i, j) {
        const scale = Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
        return COVALENT_BOND_TOLERANCE * (this.atomCovalentRadius(i) + this.atomCovalentRadius(j)) * scale;
    }

    maxPossibleBondCutoff() {
        if (!this.atomsData?.positions?.length) return 0;
        if (this.displayOptions.bondMode === 'element') {
            const values = Object.values(this.displayOptions.elementBondCutoffs || {})
                .map(Number)
                .filter(value => Number.isFinite(value) && value > 0);
            return values.length ? Math.max(...values) : 0;
        }
        const scale = Math.max(0.1, Number(this.displayOptions.bondCutoffScale || 1));
        let maxCovalent = 0;
        for (let i = 0; i < this.atomsData.positions.length; i++) {
            if (!this.atomTypeVisible(i)) continue;
            maxCovalent = Math.max(maxCovalent, this.atomCovalentRadius(i));
        }
        return COVALENT_BOND_TOLERANCE * 2 * maxCovalent * scale;
    }

    inferBondPairsCellList() {
        const count = this.atomsData?.positions?.length || 0;
        if (!count) return [];
        const maxCutoff = this.maxPossibleBondCutoff();
        if (!Number.isFinite(maxCutoff) || maxCutoff <= 0) return [];

        const pairs = [];
        const hookeanExcluded = this.hookeanBondExclusions();
        const pbc = this.atomsData?.pbc || [false, false, false];
        const basis = this.hasValidCell() ? this.cellBasis() : null;
        const useFractionalGrid = Boolean(this.displayOptions.showPeriodicBonds && basis && pbc.some(Boolean));
        const positions = new Array(count);
        const sortable = [];

        if (useFractionalGrid) {
            const lengths = basis.map(v => Math.max(1e-6, v.length()));
            const bins = lengths.map(length => Math.max(1, Math.floor(length / maxCutoff)));
            for (let i = 0; i < count; i++) {
                if (!this.atomTypeVisible(i)) continue;
                const pos = this.getAtomPosition(i);
                positions[i] = pos;
                const frac = this.cartToFrac(pos, basis);
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
            this.collectBondPairsFromCells(sortable, bins, positions, hookeanExcluded, pairs, pbc);
            return pairs;
        }

        const box = new THREE.Box3();
        for (let i = 0; i < count; i++) {
            if (!this.atomTypeVisible(i)) continue;
            const pos = this.getAtomPosition(i);
            positions[i] = pos;
            box.expandByPoint(pos);
        }
        if (box.isEmpty()) return [];
        const min = box.min;
        const size = new THREE.Vector3();
        box.getSize(size);
        const bins = [
            Math.max(1, Math.ceil(size.x / maxCutoff)),
            Math.max(1, Math.ceil(size.y / maxCutoff)),
            Math.max(1, Math.ceil(size.z / maxCutoff))
        ];
        for (let i = 0; i < count; i++) {
            const pos = positions[i];
            if (!pos) continue;
            const ix = Math.max(0, Math.min(bins[0] - 1, Math.floor((pos.x - min.x) / maxCutoff)));
            const iy = Math.max(0, Math.min(bins[1] - 1, Math.floor((pos.y - min.y) / maxCutoff)));
            const iz = Math.max(0, Math.min(bins[2] - 1, Math.floor((pos.z - min.z) / maxCutoff)));
            sortable.push({
                index: i,
                ix,
                iy,
                iz
            });
        }
        this.collectBondPairsFromCells(sortable, bins, positions, hookeanExcluded, pairs, [false, false, false]);
        return pairs;
    }

    collectBondPairsFromCells(items, bins, positions, hookeanExcluded, pairs, periodicAxes = [false, false, false]) {
        const cells = new Map();
        const keyOf = (ix, iy, iz) => `${ix}|${iy}|${iz}`;
        const wrap = (value, size, axis) => {
            if (!periodicAxes[axis]) return value;
            return ((value % size) + size) % size;
        };
        items.forEach(item => {
            const key = keyOf(item.ix, item.iy, item.iz);
            if (!cells.has(key)) cells.set(key, []);
            cells.get(key).push(item.index);
        });
        items.forEach(item => {
            const i = item.index;
            const pi = positions[i];
            if (!pi) return;
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
                        if (!bucket) continue;
                        bucket.forEach(j => {
                            if (j <= i || hookeanExcluded.has(this.hookeanPairKey(i, j))) return;
                            const cutoff = this.bondCutoffForPair(i, j);
                            if (!Number.isFinite(cutoff) || cutoff <= 0) return;
                            const d = this.bondDelta(i, j, pi).length();
                            if (d > 0.15 && d <= cutoff) pairs.push([i, j]);
                        });
                    }
                }
            }
        });
    }

    bondPairsEqual(a = [], b = []) {
        if (a.length !== b.length) return false;
        for (let index = 0; index < a.length; index++) {
            if (a[index][0] !== b[index][0] || a[index][1] !== b[index][1]) return false;
        }
        return true;
    }

    refreshBondsForCurrentPositions() {
        if (!this.displayOptions.showBonds) return;
        if (this.displayOptions.bondMode === 'manual') {
            this.updateBondPositions();
            return;
        }
        const nextPairs = this.inferBondPairs();
        if (this.bondPairsEqual(nextPairs, this.bondPairs || [])) {
            this.updateBondPositions();
        } else {
            this.rebuildBonds(nextPairs);
        }
    }

    rebuildBonds(precomputedPairs = null) {
        this.clearGroup(this.bondGroup);
        this.bondPairs = [];
        this.domElement.dataset.bondCount = '0';
        this.domElement.dataset.periodicBonds = this.displayOptions.showPeriodicBonds ? 'true' : 'false';
        this.domElement.dataset.bondStyle = this.displayOptions.bondStyle || 'cylinder';
        this.domElement.dataset.bondColorMode = this.displayOptions.bondColorMode || 'split';
        this.domElement.dataset.bondThickness = String(this.bondThickness());
        if (!this.displayOptions.showBonds || !this.atomsData) {
            this.requestRender();
            return;
        }
        const hookeanExcluded = this.hookeanBondExclusions();
        this.bondPairs = precomputedPairs || (this.displayOptions.bondMode === 'manual'
            ? this.displayOptions.manualBondPairs.filter(([i, j]) =>
                this.atomMeshByIndex.has(i) && this.atomMeshByIndex.has(j) &&
                this.atomTypeVisible(i) && this.atomTypeVisible(j) &&
                !hookeanExcluded.has(this.hookeanPairKey(i, j)))
            : this.inferBondPairs());
        this.domElement.dataset.bondCount = String(this.bondPairs.length);
        if (!this.bondPairs.length) {
            this.requestRender();
            return;
        }
        const split = this.displayOptions.bondColorMode !== 'custom';
        const segments = this.bondPairs.flatMap(([i, j]) => split
            ? [
                { i, j, t0: 0, t1: 0.5, colorIndex: i },
                { i, j, t0: 0.5, t1: 1, colorIndex: j }
            ]
            : [{ i, j, t0: 0, t1: 1, colorIndex: null }]);
        const flat = this.displayOptions.bondStyle === 'flat';
        const segmentsByColor = new Map();
        segments.forEach(segment => {
            const color = this.bondSegmentColor(segment);
            if (!segmentsByColor.has(color)) segmentsByColor.set(color, []);
            segmentsByColor.get(color).push(segment);
        });
        segmentsByColor.forEach((colorSegments, color) => {
            const mesh = new THREE.InstancedMesh(
                flat ? this.bondFlatGeometry : this.bondCylinderGeometry,
                this.bondMaterial(flat ? 'flat' : 'cylinder', color),
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
                sharedGeometry: true,
                sharedMaterial: true
            };
            colorSegments.forEach((segment, instanceId) => {
                this.positionBondInstance(mesh, instanceId, segment.i, segment.j, segment.t0, segment.t1);
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.bondGroup.add(mesh);
        });
        this.applyShadowFlags();
        this.requestRender();
    }

    updateBondPositions() {
        if (!this.displayOptions.showBonds || !this.bondGroup.children.length || !this.bondPairs?.length) return;
        this.bondGroup.children.forEach(bond => {
            if (bond.userData.instancedBonds) {
                (bond.userData.bondSegments || []).forEach((segment, instanceId) => {
                    this.positionBondInstance(bond, instanceId, segment.i, segment.j, segment.t0, segment.t1);
                });
                bond.instanceMatrix.needsUpdate = true;
                return;
            }
            const [i, j] = bond.userData.bondPair || [];
            this.positionBondMesh(bond, i, j);
        });
    }

    setStrainViolations(violations = []) {
        this.clearGroup(this.strainViolationGroup);
        violations.slice(0, 96).forEach(item => {
            const start = new THREE.Vector3(...item.start);
            const end = new THREE.Vector3(...item.end);
            const delta = new THREE.Vector3().subVectors(end, start);
            const length = delta.length();
            if (!Number.isFinite(length) || length < 1e-6) return;
            const marker = new THREE.Mesh(this.strainViolationGeometry, this.strainViolationMaterial);
            marker.userData = { sharedGeometry: true, sharedMaterial: true, strainViolation: true, strain: item.strain };
            marker.renderOrder = 24;
            marker.position.copy(start).addScaledVector(delta, 0.5);
            marker.scale.set(1, length, 1);
            marker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize());
            this.strainViolationGroup.add(marker);
        });
        this.requestRender();
    }

    clearStrainViolations() {
        this.clearGroup(this.strainViolationGroup);
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

    ensureCellCache() {
        const cell = this.atomsData?.cell;
        if (!cell || cell.length !== 3) return null;
        const key = cell.flat().join(',');
        if (this.cellCache?.key === key) return this.cellCache;
        const basis = cell.map(values => new THREE.Vector3(...values));
        const determinant = basis[0].dot(new THREE.Vector3().crossVectors(basis[1], basis[2]));
        const valid = basis.some(vector => vector.lengthSq() > 1e-12) && Math.abs(determinant) > 1e-12;
        const reciprocal = valid ? [
            new THREE.Vector3().crossVectors(basis[1], basis[2]).divideScalar(determinant),
            new THREE.Vector3().crossVectors(basis[2], basis[0]).divideScalar(determinant),
            new THREE.Vector3().crossVectors(basis[0], basis[1]).divideScalar(determinant)
        ] : null;
        this.cellCache = { key, basis, reciprocal, valid };
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

    cartToFrac(cart, basis = null) {
        const cache = basis ? null : this.ensureCellCache();
        const cell = basis || cache?.basis;
        if (!cell) return cart.clone();
        const reciprocal = cache?.reciprocal || (() => {
            const det = cell[0].dot(new THREE.Vector3().crossVectors(cell[1], cell[2]));
            if (Math.abs(det) < 1e-10) return null;
            return [
                new THREE.Vector3().crossVectors(cell[1], cell[2]).divideScalar(det),
                new THREE.Vector3().crossVectors(cell[2], cell[0]).divideScalar(det),
                new THREE.Vector3().crossVectors(cell[0], cell[1]).divideScalar(det)
            ];
        })();
        if (!reciprocal) return cart.clone();
        return new THREE.Vector3(
            cart.dot(reciprocal[0]),
            cart.dot(reciprocal[1]),
            cart.dot(reciprocal[2])
        );
    }

    minimumImageDelta(i, j, startOverride = null) {
        const start = startOverride || this.getAtomPosition(i);
        const end = this.getAtomPosition(j);
        const delta = new THREE.Vector3().subVectors(end, start);
        const pbc = this.atomsData?.pbc || [false, false, false];
        if (!this.hasValidCell() || !pbc.some(Boolean)) return delta;
        const basis = this.cellBasis();
        const frac = this.cartToFrac(delta, basis);
        for (let axis = 0; axis < 3; axis++) {
            if (pbc[axis]) frac.setComponent(axis, frac.getComponent(axis) - Math.round(frac.getComponent(axis)));
        }
        return this.fracToCart(frac, basis);
    }

    directAtomDelta(i, j, startOverride = null) {
        const start = startOverride || this.getAtomPosition(i);
        const end = this.getAtomPosition(j);
        return new THREE.Vector3().subVectors(end, start);
    }

    bondDelta(i, j, startOverride = null) {
        return this.displayOptions.showPeriodicBonds
            ? this.minimumImageDelta(i, j, startOverride)
            : this.directAtomDelta(i, j, startOverride);
    }

    bondThickness() {
        const value = Number(this.displayOptions.bondThickness);
        return Number.isFinite(value) ? Math.max(0.02, Math.min(0.6, value)) : 0.11;
    }

    bondSegmentColor(segment) {
        const requested = segment.colorIndex === null
            ? this.displayOptions.bondCustomColor
            : this.atomVisualColor(segment.colorIndex, this.customColors[segment.colorIndex]);
        return this.validHexColor(requested) ? requested.toLowerCase() : '#c8ccd0';
    }

    bondMaterial(style, color) {
        const key = `bond:${style}:${color}`;
        if (this.materialCache.has(key)) return this.materialCache.get(key);
        const material = style === 'flat'
            ? new THREE.MeshBasicMaterial({
                color,
                side: THREE.DoubleSide,
                toneMapped: false
            })
            : new THREE.MeshStandardMaterial({
                color,
                roughness: 0.5,
                metalness: 0.03
            });
        this.materialCache.set(key, material);
        return material;
    }

    orientFlatBond(object, direction) {
        const y = this.bondFlatY.copy(direction).normalize();
        const z = this.camera.getWorldDirection(this.bondFlatZ).multiplyScalar(-1);
        z.addScaledVector(y, -z.dot(y));
        if (z.lengthSq() < 1e-10) {
            z.copy(this.camera.up).addScaledVector(y, -this.camera.up.dot(y));
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
        if (!a || !b || !this.atomTypeVisible(i) || !this.atomTypeVisible(j)) {
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
        if (this.displayOptions.bondStyle === 'flat') {
            bond.scale.set(this.bondThickness(), length, 1);
            this.orientFlatBond(bond, delta);
        } else {
            bond.scale.set(this.bondThickness(), length, this.bondThickness());
            bond.quaternion.setFromUnitVectors(this.yAxis, delta.normalize());
        }
    }

    positionBondInstance(mesh, instanceId, i, j, t0 = 0, t1 = 1) {
        const a = this.atomMeshByIndex.get(i);
        const b = this.atomMeshByIndex.get(j);
        const dummy = this.bondInstanceDummy;
        if (!a || !b || !this.atomTypeVisible(i) || !this.atomTypeVisible(j)) {
            dummy.position.set(0, 0, 0);
            dummy.quaternion.identity();
            dummy.scale.set(0, 0, 0);
            dummy.updateMatrix();
            mesh.setMatrixAt(instanceId, dummy.matrix);
            return;
        }
        const atomStart = a.position;
        const fullDelta = this.bondDelta(i, j, atomStart);
        const start = atomStart.clone().addScaledVector(fullDelta, t0);
        const delta = fullDelta.multiplyScalar(t1 - t0);
        const length = delta.length();
        if (!Number.isFinite(length) || length < 1e-6) {
            dummy.position.set(0, 0, 0);
            dummy.quaternion.identity();
            dummy.scale.set(0, 0, 0);
            dummy.updateMatrix();
            mesh.setMatrixAt(instanceId, dummy.matrix);
            return;
        }
        dummy.position.copy(start).addScaledVector(delta, 0.5);
        if (this.displayOptions.bondStyle === 'flat') {
            dummy.scale.set(this.bondThickness(), length, 1);
            this.orientFlatBond(dummy, delta);
        } else {
            dummy.scale.set(this.bondThickness(), length, this.bondThickness());
            dummy.quaternion.setFromUnitVectors(this.yAxis, delta.normalize());
        }
        dummy.updateMatrix();
        mesh.setMatrixAt(instanceId, dummy.matrix);
    }

    hasValidCell() {
        return Boolean(this.ensureCellCache()?.valid);
    }

    rebuildSupercell() {
        this.clearGroup(this.supercellGroup);
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
        if (this.displayOptions.vizOnly) {
            this.rebuildVizOnlySupercellAtoms(cell, reps);
            this.applyShadowFlags();
            this.requestRender();
            return;
        }
        const fixed = new Set(this.atomsData.constraints?.fixed_indices || []);
        const maxGhostAtoms = 5000;
        let ghostCount = 0;
        const ghostSegments = Math.max(10, Math.floor(this.sphereQualitySegments(this.atomsData.symbols.length) * 0.62));
        for (let ix = 0; ix < reps[0]; ix++) {
            for (let iy = 0; iy < reps[1]; iy++) {
                for (let iz = 0; iz < reps[2]; iz++) {
                    if (ix === 0 && iy === 0 && iz === 0) continue;
                    const shift = new THREE.Vector3()
                        .addScaledVector(cell[0], ix)
                        .addScaledVector(cell[1], iy)
                        .addScaledVector(cell[2], iz);
                    this.atomsData.symbols.forEach((sym, i) => {
                        if (ghostCount >= maxGhostAtoms) return;
                        const radius = this.atomVisualRadius(i);
                        const color = this.atomVisualColor(i);
                        const geometryKey = `${radius}:ghost:${ghostSegments}`;
                        if (!this.geometryCache.has(geometryKey)) {
                            this.geometryCache.set(geometryKey, new THREE.SphereGeometry(
                                radius * 0.88,
                                ghostSegments,
                                Math.max(8, Math.floor(ghostSegments * 0.62))
                            ));
                        }
                        const materialKey = `${color}:ghost`;
                        if (!this.materialCache.has(materialKey)) {
                            this.materialCache.set(materialKey, new THREE.MeshStandardMaterial({
                                color,
                                roughness: 0.54,
                                transparent: true,
                                opacity: fixed.has(i) ? 0.32 : 0.48,
                                depthWrite: false
                            }));
                        }
                        const mesh = new THREE.Mesh(this.geometryCache.get(geometryKey), this.materialCache.get(materialKey));
                        const p = this.atomMeshByIndex.get(i)?.position || new THREE.Vector3(...this.atomsData.positions[i]);
                        mesh.position.copy(p).add(shift);
                        mesh.userData = { ghostFor: i, shift };
                        mesh.visible = this.atomTypeVisible(i);
                        this.supercellGroup.add(mesh);
                        ghostCount++;
                    });
                }
            }
        }
        this.applyShadowFlags();
        this.requestRender();
    }

    supercellShifts(cell, reps) {
        const shifts = [];
        for (let ix = 0; ix < reps[0]; ix++) {
            for (let iy = 0; iy < reps[1]; iy++) {
                for (let iz = 0; iz < reps[2]; iz++) {
                    if (ix === 0 && iy === 0 && iz === 0) continue;
                    shifts.push(new THREE.Vector3()
                        .addScaledVector(cell[0], ix)
                        .addScaledVector(cell[1], iy)
                        .addScaledVector(cell[2], iz));
                }
            }
        }
        return shifts;
    }

    rebuildVizOnlySupercellAtoms(cell, reps) {
        const shifts = this.supercellShifts(cell, reps);
        if (!shifts.length) return;
        const segmentCount = this.sphereQualitySegments(this.atomsData.symbols.length);
        const fixed = this.fixedAtomDisplayEnabled()
            ? new Set(this.atomsData.constraints?.fixed_indices || [])
            : new Set();
        const groups = new Map();
        this.atomsData.symbols.forEach((sym, index) => {
            const isFixed = fixed.has(index);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            const materialKey = `unit-sphere:${isFixed ? 'fixed' : 'normal'}:instanced`;
            const key = `${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!groups.has(key)) groups.set(key, { isFixed, atomSegments, geometryKey, materialKey, indices: [] });
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
                const spec = this.atomMaterialSpec('#ffffff', group.isFixed);
                const material = new THREE.MeshStandardMaterial({
                    color: 0xffffff,
                    roughness: spec.roughness,
                    metalness: spec.metalness,
                    emissive: spec.emissive,
                    emissiveIntensity: spec.emissiveIntensity,
                    flatShading: spec.flatShading
                });
                if (group.isFixed) this.applyFixedAtomEtchedShader(material);
                this.materialCache.set(group.materialKey, material);
            }
            const total = group.indices.length * shifts.length;
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(group.geometryKey),
                this.materialCache.get(group.materialKey),
                total
            );
            mesh.frustumCulled = false;
            mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
            mesh.userData = {
                supercellInstanced: true,
                atomIndices: group.indices,
                shifts,
                sharedGeometry: true,
                sharedMaterial: true
            };
            let instanceId = 0;
            shifts.forEach(shift => {
                group.indices.forEach(index => {
                    this.setSupercellInstanceMatrix(mesh, instanceId, index, shift);
                    mesh.setColorAt(
                        instanceId,
                        this.fixedAdjustedColor(this.atomVisualColor(index, this.customColors[index]), group.isFixed)
                    );
                    instanceId++;
                });
            });
            mesh.instanceMatrix.needsUpdate = true;
            if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
            this.supercellGroup.add(mesh);
        });
    }

    setSupercellInstanceMatrix(mesh, instanceId, index, shift) {
        const atom = this.atomMeshByIndex.get(index);
        const visible = atom && this.atomTypeVisible(index);
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

    addSupercellCellPreview(cell, reps) {
        const edgePairs = [[0,1],[0,2],[0,3],[1,4],[1,5],[2,4],[2,6],[3,5],[3,6],[4,7],[5,7],[6,7]];
        const points = [];
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
        for (let ix = 0; ix < reps[0]; ix++) {
            for (let iy = 0; iy < reps[1]; iy++) {
                for (let iz = 0; iz < reps[2]; iz++) {
                    const shift = new THREE.Vector3()
                        .addScaledVector(cell[0], ix)
                        .addScaledVector(cell[1], iy)
                        .addScaledVector(cell[2], iz);
                    const corners = baseCorners(shift);
                    edgePairs.forEach(([i, j]) => points.push(corners[i], corners[j]));
                }
            }
        }
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const mat = new THREE.LineBasicMaterial({
            color: 0xffc65a,
            transparent: true,
            opacity: 0.54,
            depthWrite: false
        });
        const lines = new THREE.LineSegments(geo, mat);
        lines.userData = { supercellCellPreview: true };
        this.supercellGroup.add(lines);
    }

    updateSupercellPositions() {
        if (!this.supercellGroup.children.length) return;
        this.supercellGroup.children.forEach(mesh => {
            if (mesh.userData.supercellCellPreview) return;
            if (mesh.userData.supercellInstanced) {
                let instanceId = 0;
                mesh.userData.shifts.forEach(shift => {
                    mesh.userData.atomIndices.forEach(index => {
                        this.setSupercellInstanceMatrix(mesh, instanceId, index, shift);
                        instanceId++;
                    });
                });
                mesh.instanceMatrix.needsUpdate = true;
                return;
            }
            const atom = this.atomMeshByIndex.get(mesh.userData.ghostFor);
            if (!atom || !this.atomTypeVisible(mesh.userData.ghostFor)) {
                mesh.visible = false;
                return;
            }
            mesh.visible = true;
            mesh.position.copy(atom.position).add(mesh.userData.shift);
        });
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
        return indices.some(idx => this.atomTypeVisible(idx));
    }

    orientYAxis(object, direction) {
        object.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.clone().normalize());
    }

    hookeanPairKey(i, j) {
        const a = Math.min(i, j);
        const b = Math.max(i, j);
        return `${a}-${b}`;
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
        this.clearGroup(this.constraintGuideGroup);
        if (!this.atomsData?.constraints || !selectedIndices.size || this.displayOptions.showOverlays === false) return;
        const fixedLine = this.atomsData.constraints.fixed_line || {};
        const fixedPlane = this.atomsData.constraints.fixed_plane || {};
        const compactPlane = selectedIndices.size > 1;
        selectedIndices.forEach(idx => {
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom) return;
            if (fixedLine[idx] || fixedLine[String(idx)]) {
                this.addFixedLineGuide(idx, fixedLine[idx] || fixedLine[String(idx)]);
            }
            const planeNormal = fixedPlane[idx] || fixedPlane[String(idx)];
            if (planeNormal) {
                this.addFixedPlaneGuide(idx, planeNormal, { compact: compactPlane });
            }
        });
    }

    addFixedLineGuide(index, directionValues) {
        const atom = this.atomMeshByIndex.get(index);
        if (!atom) return;
        const direction = this.normalizedVector(directionValues);
        const group = new THREE.Group();
        group.userData = { constraintGuideFor: index, kind: 'fixed_line', direction: direction.toArray() };

        const length = Math.max(6.0, Math.min(18.0, (this.desiredGuideSize?.() || 12) * 0.22));
        const center = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.line);
        center.userData = { sharedMaterial: true, lineGuideSegment: true };
        this.setLinePoints(center, [
            new THREE.Vector3(0, -length * 0.32, 0),
            new THREE.Vector3(0, length * 0.32, 0)
        ], 'lineGuideCenter', 0.014);
        group.add(center);

        [-1, 1].forEach(sign => {
            const fade = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.lineFade);
            fade.userData = { sharedMaterial: true, lineGuideFade: true };
            this.setLinePoints(fade, [
                new THREE.Vector3(0, sign * length * 0.32, 0),
                new THREE.Vector3(0, sign * length * 0.50, 0)
            ], `lineGuideFade${sign}`, 0.010);
            group.add(fade);
        });
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
        const compact = Boolean(options.compact);
        const group = new THREE.Group();
        group.userData = {
            constraintGuideFor: index,
            kind: 'fixed_plane',
            normal: normal.toArray(),
            anchor: atom.position.toArray(),
            planeOffset
        };

        const atomRadius = this.atomVisualRadius?.(index) || 0.55;
        const guideSize = compact
            ? Math.max(1.15, Math.min(2.8, atomRadius * 2.8))
            : Math.max(8, Math.min(80, (this.desiredGuideSize?.() || 24) * 0.52));
        const planeGeometry = compact
            ? new THREE.CircleGeometry(guideSize * 0.5, 48)
            : new THREE.PlaneGeometry(guideSize, guideSize);
        const plane = new THREE.Mesh(planeGeometry, compact ? this.constraintMaterials.planeAggregate : this.constraintMaterials.planeSoft);
        plane.userData.sharedMaterial = true;
        plane.renderOrder = 16;
        group.add(plane);

        const half = guideSize * 0.5;
        const cross = guideSize * (compact ? 0.26 : 0.34);
        const edgeRadius = Math.max(0.008, guideSize * 0.0016);
        const crossRadius = Math.max(0.010, guideSize * 0.0018);
        const normalRadius = Math.max(0.012, guideSize * 0.0021);
        if (compact) {
            const ring = new THREE.Mesh(
                new THREE.RingGeometry(half * 0.94, half, 64),
                this.constraintMaterials.planePerimeter
            );
            ring.userData = { sharedMaterial: true, fixedPlanePerimeter: true };
            ring.renderOrder = 18;
            group.add(ring);
        } else {
            const edges = [
                [[-half, -half, 0.002], [half, -half, 0.002]],
                [[half, -half, 0.002], [half, half, 0.002]],
                [[half, half, 0.002], [-half, half, 0.002]],
                [[-half, half, 0.002], [-half, -half, 0.002]]
            ];
            edges.forEach((edge, edgeIndex) => {
                const line = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.planePerimeter);
                line.userData = { sharedMaterial: true, fixedPlanePerimeter: true };
                this.setLinePoints(line, edge.map(p => new THREE.Vector3(...p)), `fixedPlaneEdge${edgeIndex}`, edgeRadius);
                line.renderOrder = 18;
                group.add(line);
            });
        }

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

        const tickLength = compact
            ? Math.max(0.32, Math.min(0.72, guideSize * 0.24))
            : Math.max(0.9, Math.min(2.4, guideSize * 0.085));
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
            if (!atom || !this.atomTypeVisible(idx)) return;
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

        const spring = new THREE.Mesh(new THREE.BufferGeometry(), this.constraintMaterials.hookean);
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

    makeFlatSpringPoints(startY, endY, amplitude = 0.11, coils = 8, laneOffset = 0) {
        if (endY - startY < 1e-4) return [
            new THREE.Vector3(0, startY, laneOffset),
            new THREE.Vector3(0, endY, laneOffset)
        ];
        const points = [new THREE.Vector3(0, startY, laneOffset)];
        const steps = Math.max(8, coils * 2);
        for (let i = 1; i < steps; i++) {
            const t = i / steps;
            const x = i % 2 === 0 ? -amplitude : amplitude;
            points.push(new THREE.Vector3(x, THREE.MathUtils.lerp(startY, endY, t), laneOffset));
        }
        points.push(new THREE.Vector3(0, endY, laneOffset));
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
        if (Math.abs(length - threshold) <= Math.max(0.035, threshold * 0.025)) return 'threshold';
        return length < threshold ? 'inactive' : 'active';
    }

    hookeanStateMaterial(state) {
        if (state === 'active') return this.constraintMaterials.hookeanActiveMarker;
        if (state === 'threshold') return this.constraintMaterials.hookeanThresholdMarker;
        return this.constraintMaterials.hookeanInactiveMarker;
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
        const coils = Math.max(6, Math.round(5 + springLength * 2.2));

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
            this.setLinePoints(springLine, this.makeFlatSpringPoints(
                springStart,
                springEnd,
                Math.min(0.22, span * 0.10),
                coils,
                0
            ), 'springSignature', 0.030);
        }
        springLine.material = state === 'inactive' ? this.constraintMaterials.hookeanInactive : this.constraintMaterials.hookean;
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
                if (!atom || !this.atomTypeVisible(item.index)) {
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
            if (!atom || !this.atomTypeVisible(spec.i) || (spec.kind === 'two_atoms' && !this.atomTypeVisible(spec.j))) {
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
            if (!atom || !this.atomTypeVisible(idx)) {
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

    setSelection(selectedIndices) {
        this.clearSelectionOutlines();
        const selected = new Set(selectedIndices);
        const visibleIndices = [...selected].filter(idx => this.atomMeshByIndex.has(idx) && this.atomTypeVisible(idx));
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
            if (!mesh || !this.atomTypeVisible(idx)) return;
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

            const haloGeo = new THREE.RingGeometry(radius * 1.28, radius * 1.36, 48);
            const haloMat = new THREE.MeshBasicMaterial({
                color: 0xffd84d,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.85,
                depthWrite: false
            });
            const halo = new THREE.Mesh(haloGeo, haloMat);
            halo.position.copy(mesh.position);
            halo.lookAt(this.camera.position);
            halo.userData = { outlineFor: idx, billboard: true };
            halo.renderOrder = 11;
            this.selectionOutlines.add(halo);
        });
        this.rebuildConstraintGuides(selected);
        this.applyOverlayVisibility();
        this.requestRender();
    }

    setSelectionInstanceMatrix(mesh, instanceId, index) {
        const atom = this.atomMeshByIndex.get(index);
        const visible = atom && this.atomTypeVisible(index);
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
            if (!mesh || !this.atomTypeVisible(idx)) {
                outline.visible = false;
                return;
            }
            outline.visible = true;
            outline.position.copy(mesh.position);
            if (outline.userData.billboard) {
                outline.lookAt(this.camera.position);
            }
        });
        this.syncConstraintGuides();
    }

    onResize() {
        this.updateCameraProjection();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.requestRender();
    }

    exportPNG(width, height, options = {}) {
        const transparentBackground = Boolean(options.transparentBackground);
        const includeGrid = options.includeGrid !== false;
        const includeAxes = options.includeAxes !== false;
        const oldLighting = {
            ...this.lightingOptions,
            sunPosition: [...(this.lightingOptions?.sunPosition || [8, -10, 14])],
            sunTarget: [...(this.lightingOptions?.sunTarget || [0, 0, 0])]
        };
        const requestedMode = ['modeling', 'studio', 'studio-shadow'].includes(options.renderMode)
            ? options.renderMode
            : oldLighting.lightingMode;
        const oldSize = new THREE.Vector2();
        this.renderer.getSize(oldSize);
        const oldPixelRatio = this.renderer.getPixelRatio();
        const oldPerspectiveAspect = this.perspectiveCamera?.aspect;
        const oldOrtho = this.orthographicCamera ? {
            left: this.orthographicCamera.left,
            right: this.orthographicCamera.right,
            top: this.orthographicCamera.top,
            bottom: this.orthographicCamera.bottom
        } : null;
        const oldBackground = this.scene.background;
        const oldClearColor = this.renderer.getClearColor(new THREE.Color()).clone();
        const oldClearAlpha = this.renderer.getClearAlpha();
        const oldGridVisible = this.gridGroup?.visible;
        const oldAxesVisible = this.axesHelper?.visible;

        try {
            this.setLightingOptions({
                ...oldLighting,
                lightingMode: requestedMode,
                sunIntensity: Number.isFinite(Number(options.sunIntensity))
                    ? Number(options.sunIntensity)
                    : oldLighting.sunIntensity,
                sunPosition: options.sunPosition || oldLighting.sunPosition,
                sunTarget: options.sunTarget || oldLighting.sunTarget,
                sunGizmo: false
            });
            if (transparentBackground) {
                this.scene.background = null;
                this.renderer.setClearColor(0x000000, 0);
            } else {
                this.scene.background = oldBackground || new THREE.Color(0x303235);
                this.renderer.setClearColor(0x303235, 1);
            }
            if (this.gridGroup) this.gridGroup.visible = includeGrid && this.displayOptions.showGrid;
            if (this.axesHelper) this.axesHelper.visible = includeAxes && this.displayOptions.showAxes;

            this.renderer.setPixelRatio(1);
            this.renderer.setSize(width, height, false);
            this.updateCameraProjection(width / height);
            this.updateBondPositions();
            this.syncSelectionOutlines();
            this.updateHookeanPositions();
            this.updateViewLighting();
            this.renderer.render(this.scene, this.camera);
            if (requestedMode === 'studio-shadow') this.renderer.render(this.scene, this.camera);
            return this.renderer.domElement.toDataURL('image/png');
        } finally {
            this.setLightingOptions(oldLighting);
            this.scene.background = oldBackground;
            this.renderer.setClearColor(oldClearColor, oldClearAlpha);
            if (this.gridGroup) this.gridGroup.visible = oldGridVisible;
            if (this.axesHelper) this.axesHelper.visible = oldAxesVisible;
            this.renderer.setPixelRatio(oldPixelRatio);
            this.renderer.setSize(oldSize.x, oldSize.y, false);
            if (this.perspectiveCamera && Number.isFinite(oldPerspectiveAspect)) {
                this.perspectiveCamera.aspect = oldPerspectiveAspect;
            }
            if (this.orthographicCamera && oldOrtho) {
                Object.assign(this.orthographicCamera, oldOrtho);
            }
            this.camera.updateProjectionMatrix();
            this.updateBondPositions();
            this.syncSelectionOutlines();
            this.requestRender();
        }
    }

    requestRender() {
        if (this.renderRequestId !== null) return;
        this.renderRequestId = requestAnimationFrame(() => {
            this.renderRequestId = null;
            this.renderFrame();
        });
    }

    renderFrame() {
        this.controls.update();
        if (this.displayOptions.bondStyle === 'flat') this.updateBondPositions();
        this.syncSelectionOutlines();
        this.onFrame?.();
        this.updateViewLighting();
        this.renderer.render(this.scene, this.camera);
        this.renderCount += 1;
        this.domElement.dataset.renderCount = String(this.renderCount);
    }

    renderNow() {
        if (this.renderRequestId !== null) {
            cancelAnimationFrame(this.renderRequestId);
            this.renderRequestId = null;
        }
        this.renderFrame();
    }

    animate() {
        this.requestRender();
    }
}
