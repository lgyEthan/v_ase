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
            return;
        }
        const offset = new THREE.Vector3().subVectors(this.camera.position, this.target);
        offset.multiplyScalar(Math.min(8, Math.max(0.125, factor)));
        this.camera.position.copy(this.target).add(offset);
        this.camera.lookAt(this.target);
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
        this.setupScene();
        this.animate();
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

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
        this.renderer.setClearColor(0x303235, 1);
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.domElement = this.renderer.domElement;
        this.container.appendChild(this.renderer.domElement);

        this.controls = new BlenderTumbleControls(this.camera, this.renderer.domElement);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x6a7078, 1.18);
        this.scene.add(hemiLight);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.68);
        this.scene.add(ambientLight);
        
        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.50);
        dirLight1.position.set(10, 20, 10);
        this.scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.50);
        dirLight2.position.set(-10, -20, 10);
        this.scene.add(dirLight2);

        const dirLight3 = new THREE.DirectionalLight(0xffffff, 0.36);
        dirLight3.position.set(12, -14, 8);
        this.scene.add(dirLight3);

        const dirLight4 = new THREE.DirectionalLight(0xffffff, 0.34);
        dirLight4.position.set(-12, 14, -8);
        this.scene.add(dirLight4);

        this.cameraFillLight = new THREE.PointLight(0xffffff, 1.15, 0, 1.35);
        this.scene.add(this.cameraFillLight);
        this.cameraFillTarget = new THREE.Object3D();
        this.scene.add(this.cameraFillTarget);
        this.cameraFillDirectionalLight = new THREE.DirectionalLight(0xffffff, 0.48);
        this.cameraFillDirectionalLight.target = this.cameraFillTarget;
        this.scene.add(this.cameraFillDirectionalLight);

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
        this.useInstancedAtoms = false;
        this.instanceDummy = new THREE.Object3D();
        this.geometryCache = new Map();
        this.materialCache = new Map();
        this.atomsData = null;
        this.needsInitialCameraFit = true;
        this.customColors = {};
        this.displayOptions = {
            showCell: true,
            showAxes: true,
            showGrid: true,
            showBonds: false,
            bondMode: 'auto',
            bondCutoffScale: 1.0,
            manualBondPairs: [],
            elementBondCutoffs: {},
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
            vizOnly: false
        };
        this.bondPairs = [];
        this.bondGeometry = new THREE.CylinderGeometry(0.055, 0.055, 1, 16);
        this.bondMaterial = new THREE.MeshStandardMaterial({
            color: 0xc8ccd0,
            roughness: 0.55,
            metalness: 0.04,
            transparent: true,
            opacity: 0.9
        });
        this.strainViolationGeometry = new THREE.CylinderGeometry(0.085, 0.085, 1, 24);
        this.strainViolationMaterial = new THREE.MeshBasicMaterial({
            color: 0xff3b30,
            transparent: true,
            opacity: 0.88,
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

    applyAtomVisibility() {
        if (this.useInstancedAtoms) {
            this.atomMeshByIndex.forEach((proxy, index) => {
                proxy.visible = this.atomTypeVisible(index);
                this.updateAtomInstanceMatrix(index);
            });
            this.atomInstanceRefs.forEach(({ mesh }) => {
                mesh.instanceMatrix.needsUpdate = true;
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
                const idx = group.userData.constraintGuideFor;
                group.visible = this.atomTypeVisible(idx);
            });
            this.refreshBondsForCurrentPositions();
            this.updateSupercellPositions();
            this.updateHookeanPositions();
            return;
        }
        this.atomMeshes.children.forEach(mesh => {
            const index = mesh.userData.index;
            if (index === undefined) return;
            const visible = this.atomTypeVisible(index);
            mesh.visible = visible;
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
            const idx = group.userData.constraintGuideFor;
            group.visible = this.atomTypeVisible(idx);
        });
        this.refreshBondsForCurrentPositions();
        this.updateSupercellPositions();
        this.updateHookeanPositions();
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
        this.atomsData = atoms;
        this.customColors = customColors || {};
        this.refreshViewportGuidesForStructure();
        
        if (!atoms || !atoms.symbols) return;

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
            return;
        }
        atoms.symbols.forEach((sym, i) => {
            const radius = this.atomVisualRadius(i);
            const color = this.atomVisualColor(i, customColors[i]);
            const isFixed = fixed.has(i);

            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `${radius}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(radius, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
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
    }

    shouldUseInstancedAtoms(atoms) {
        const count = atoms?.symbols?.length || 0;
        return count >= 2000 || (this.displayOptions.vizOnly && count >= 500);
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
            const radius = this.atomVisualRadius(i);
            const isFixed = fixed.has(i);
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `${radius}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            const materialKey = `${geometryKey}:${isFixed ? 'fixed' : 'normal'}:instanced`;
            const key = `${geometryKey}|${materialKey}`;
            if (!groups.has(key)) {
                groups.set(key, { radius, geometryKey, materialKey, fixed: isFixed, segments: atomSegments, indices: [] });
            }
            groups.get(key).indices.push(i);
        });

        groups.forEach(group => {
            if (!this.geometryCache.has(group.geometryKey)) {
                this.geometryCache.set(
                    group.geometryKey,
                    new THREE.SphereGeometry(group.radius, group.segments, Math.max(8, Math.floor(group.segments * 0.65)))
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
            this.atomMeshes.add(mesh);

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
        this.instanceDummy.position.copy(proxy.position);
        const visible = proxy.visible !== false && this.atomTypeVisible(index);
        const scale = visible ? 1 : 0;
        this.instanceDummy.scale.setScalar(scale);
        this.instanceDummy.rotation.set(0, 0, 0);
        this.instanceDummy.updateMatrix();
        ref.mesh.setMatrixAt(ref.instanceId, this.instanceDummy.matrix);
    }

    flushAtomInstances(indices = null) {
        if (!this.useInstancedAtoms) return;
        if (indices) {
            indices.forEach(index => this.updateAtomInstanceMatrix(index));
        }
        this.atomInstanceRefs.forEach(({ mesh }) => {
            mesh.instanceMatrix.needsUpdate = true;
        });
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

    clearGroup(group) {
        while(group.children.length > 0) {
            const child = group.children[0];
            group.remove(child);
            if(!child.userData?.sharedGeometry && child.geometry) child.geometry.dispose();
            if(!child.userData?.sharedMaterial && child.material) child.material.dispose();
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
        const points = [];
        if (this.atomsData?.positions?.length) {
            this.atomsData.positions.forEach((position, index) => {
                if (!position || position.length < 3) return;
                const p = new THREE.Vector3(...position);
                if (![p.x, p.y, p.z].every(Number.isFinite)) return;
                const radius = this.atomVisualRadius(index);
                points.push(
                    p.clone().add(new THREE.Vector3(radius, radius, radius)),
                    p.clone().add(new THREE.Vector3(-radius, -radius, -radius))
                );
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
            points.push(...corners);
        }

        if (!points.length) return null;
        const box = new THREE.Box3().setFromPoints(points);
        if (box.isEmpty()) return null;
        return box;
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
        const ratio = this.displayOptions.antiAliasing === false
            ? 1
            : Math.min(window.devicePixelRatio || 1, 2);
        this.renderer.setPixelRatio(ratio);
        this.renderer.setSize(window.innerWidth, window.innerHeight, false);
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
    }

    updateViewLighting() {
        if (!this.cameraFillLight || !this.camera) return;
        this.cameraFillLight.position.copy(this.camera.position);
        if (this.cameraFillDirectionalLight && this.cameraFillTarget) {
            this.cameraFillDirectionalLight.position.copy(this.camera.position);
            this.cameraFillTarget.position.copy(this.controls?.target || new THREE.Vector3());
            this.cameraFillDirectionalLight.target.updateMatrixWorld();
        }
    }

    rebuildCell(cell) {
        if (!cell || cell.length !== 3) return;
        const a = new THREE.Vector3(...cell[0]);
        const b = new THREE.Vector3(...cell[1]);
        const c = new THREE.Vector3(...cell[2]);
        if (a.lengthSq() === 0 && b.lengthSq() === 0 && c.lengthSq() === 0) return;

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
    }

    updatePositions(positions) {
        if (this.atomsData) {
            this.atomsData.positions = positions.map(p => [...p]);
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
            this.updateBondPositions();
            this.updateSupercellPositions();
            this.updateHookeanPositions();
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
        this.updateBondPositions();
        this.updateSupercellPositions();
        this.updateHookeanPositions();
    }

    setDisplayOptions(options) {
        const previous = {
            ...this.displayOptions,
            manualBondPairs: [...(this.displayOptions.manualBondPairs || [])],
            elementBondCutoffs: { ...(this.displayOptions.elementBondCutoffs || {}) },
            elementRadii: { ...(this.displayOptions.elementRadii || {}) },
            elementColors: { ...(this.displayOptions.elementColors || {}) },
            elementVisible: { ...(this.displayOptions.elementVisible || {}) },
            supercell: [...(this.displayOptions.supercell || [1, 1, 1])]
        };
        this.displayOptions = {
            ...this.displayOptions,
            ...options,
            manualBondPairs: [...(options.manualBondPairs || this.displayOptions.manualBondPairs || [])],
            elementBondCutoffs: { ...(options.elementBondCutoffs || this.displayOptions.elementBondCutoffs || {}) },
            elementRadii: { ...(options.elementRadii || this.displayOptions.elementRadii || {}) },
            elementColors: { ...(options.elementColors || this.displayOptions.elementColors || {}) },
            elementVisible: { ...(options.elementVisible || this.displayOptions.elementVisible || {}) },
            supercell: [...(options.supercell || this.displayOptions.supercell || [1, 1, 1])]
        };
        const qualityChanged = previous.antiAliasing !== this.displayOptions.antiAliasing ||
            previous.sphereQuality !== this.displayOptions.sphereQuality ||
            previous.atomRadiusScale !== this.displayOptions.atomRadiusScale ||
            JSON.stringify(previous.elementRadii || {}) !== JSON.stringify(this.displayOptions.elementRadii || {}) ||
            JSON.stringify(previous.elementColors || {}) !== JSON.stringify(this.displayOptions.elementColors || {});
        const overlayChanged = previous.showOverlays !== this.displayOptions.showOverlays;
        const visibilityChanged = JSON.stringify(previous.elementVisible || {}) !== JSON.stringify(this.displayOptions.elementVisible || {});
        const supercellChanged = JSON.stringify(previous.supercell || [1, 1, 1]) !== JSON.stringify(this.displayOptions.supercell || [1, 1, 1]);
        if (previous.projectionMode !== this.displayOptions.projectionMode) {
            this.setProjectionMode(this.displayOptions.projectionMode);
        }
        if (qualityChanged || overlayChanged) {
            if (qualityChanged) this.updateRenderQuality();
            if (this.atomsData) {
                this.rebuildAtoms(this.atomsData, this.customColors);
            }
            this.applyOverlayVisibility();
            return;
        }
        this.cellGroup.visible = this.displayOptions.showCell;
        if (this.axesHelper) this.axesHelper.visible = this.displayOptions.showAxes;
        if (this.gridGroup) this.gridGroup.visible = this.displayOptions.showGrid;
        this.applyOverlayVisibility();
        const bondsChanged = previous.showBonds !== this.displayOptions.showBonds ||
            previous.bondMode !== this.displayOptions.bondMode ||
            previous.bondCutoffScale !== this.displayOptions.bondCutoffScale ||
            previous.manualBondPairs !== this.displayOptions.manualBondPairs ||
            JSON.stringify(previous.elementBondCutoffs || {}) !== JSON.stringify(this.displayOptions.elementBondCutoffs || {}) ||
            visibilityChanged;
        if (bondsChanged) this.rebuildBonds();
        if (supercellChanged) this.rebuildSupercell();
        if (visibilityChanged) this.applyAtomVisibility();
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
        if (this.useInstancedAtoms) {
            this.rebuildAtoms(this.atomsData, this.customColors);
            return;
        }
        const segmentCount = this.sphereQualitySegments(this.atomsData.symbols.length);
        indices.forEach(index => {
            const mesh = this.atomMeshByIndex.get(index);
            if (!mesh) return;
            const radius = this.atomVisualRadius(index);
            const color = this.atomVisualColor(index, this.customColors[index]);
            const isFixed = Boolean(mesh.userData.fixed) && this.fixedAtomDisplayEnabled();
            const atomSegments = isFixed ? this.fixedAtomSegments(segmentCount) : segmentCount;
            const geometryKey = `${radius}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.geometryCache.has(geometryKey)) {
                this.geometryCache.set(
                    geometryKey,
                    new THREE.SphereGeometry(radius, atomSegments, Math.max(8, Math.floor(atomSegments * 0.65)))
                );
            }
            const materialKey = `${color}:${isFixed ? 'fixed' : 'normal'}:${atomSegments}`;
            if (!this.materialCache.has(materialKey)) {
                this.materialCache.set(materialKey, this.createAtomMaterial(color, isFixed));
            }
            mesh.geometry = this.geometryCache.get(geometryKey);
            mesh.material = this.materialCache.get(materialKey);
            mesh.visible = this.atomTypeVisible(index);
        });
    }

    inferBondPairs() {
        if (!this.atomsData || !this.atomsData.positions) return [];
        if (this.atomsData.positions.length > 2000) return this.inferBondPairsCellList();
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
                const d = this.minimumImageDelta(i, j, pi).length();
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
        const useFractionalGrid = Boolean(basis && pbc.some(Boolean));
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
                            const d = this.minimumImageDelta(i, j, pi).length();
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
        if (!this.displayOptions.showBonds || !this.atomsData) return;
        const hookeanExcluded = this.hookeanBondExclusions();
        this.bondPairs = precomputedPairs || (this.displayOptions.bondMode === 'manual'
            ? this.displayOptions.manualBondPairs.filter(([i, j]) =>
                this.atomMeshByIndex.has(i) && this.atomMeshByIndex.has(j) &&
                this.atomTypeVisible(i) && this.atomTypeVisible(j) &&
                !hookeanExcluded.has(this.hookeanPairKey(i, j)))
            : this.inferBondPairs());
        if (!this.bondPairs.length) return;
        this.bondPairs.forEach(([i, j]) => {
            const bond = new THREE.Mesh(this.bondGeometry, this.bondMaterial);
            bond.userData = { bondPair: [i, j], sharedGeometry: true, sharedMaterial: true };
            bond.renderOrder = -1;
            this.bondGroup.add(bond);
            this.positionBondMesh(bond, i, j);
        });
    }

    updateBondPositions() {
        if (!this.displayOptions.showBonds || !this.bondGroup.children.length || !this.bondPairs?.length) return;
        this.bondGroup.children.forEach(bond => {
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
    }

    clearStrainViolations() {
        this.clearGroup(this.strainViolationGroup);
    }

    getAtomPosition(index) {
        const mesh = this.atomMeshByIndex.get(index);
        if (mesh) return mesh.position.clone();
        return new THREE.Vector3(...this.atomsData.positions[index]);
    }

    cellBasis() {
        if (!this.hasValidCell()) return null;
        return this.atomsData.cell.map(v => new THREE.Vector3(...v));
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
        const cell = basis || this.cellBasis();
        if (!cell) return cart.clone();
        const det = cell[0].dot(new THREE.Vector3().crossVectors(cell[1], cell[2]));
        if (Math.abs(det) < 1e-10) return cart.clone();
        return new THREE.Vector3(
            cart.dot(new THREE.Vector3().crossVectors(cell[1], cell[2])) / det,
            cart.dot(new THREE.Vector3().crossVectors(cell[2], cell[0])) / det,
            cart.dot(new THREE.Vector3().crossVectors(cell[0], cell[1])) / det
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

    positionBondMesh(bond, i, j) {
        const a = this.atomMeshByIndex.get(i);
        const b = this.atomMeshByIndex.get(j);
        if (!a || !b || !this.atomTypeVisible(i) || !this.atomTypeVisible(j)) {
            bond.visible = false;
            return;
        }
        const start = a.position;
        const delta = this.minimumImageDelta(i, j, start);
        const length = delta.length();
        if (length < 1e-6) {
            bond.visible = false;
            return;
        }
        bond.visible = true;
        bond.position.copy(start).addScaledVector(delta, 0.5);
        bond.scale.set(1, length, 1);
        bond.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), delta.normalize());
    }

    hasValidCell() {
        if (!this.atomsData?.cell || this.atomsData.cell.length !== 3) return false;
        return this.atomsData.cell.some(v => new THREE.Vector3(...v).lengthSq() > 1e-12);
    }

    rebuildSupercell() {
        this.clearGroup(this.supercellGroup);
        if (!this.atomsData || !this.hasValidCell()) return;
        const reps = this.displayOptions.supercell || [1, 1, 1];
        if (reps.every(v => v <= 1)) return;
        const cell = this.atomsData.cell.map(v => new THREE.Vector3(...v));
        this.addSupercellCellPreview(cell, reps);
        if (this.displayOptions.vizOnly) {
            this.rebuildVizOnlySupercellAtoms(cell, reps);
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
        const groups = new Map();
        this.atomsData.symbols.forEach((sym, index) => {
            const radius = this.atomVisualRadius(index);
            const color = this.atomVisualColor(index, this.customColors[index]);
            const geometryKey = `${radius}:supercell:${segmentCount}`;
            const materialKey = `supercell:viz:${geometryKey}:${color}`;
            const key = `${geometryKey}|${materialKey}`;
            if (!groups.has(key)) groups.set(key, { radius, color, geometryKey, materialKey, indices: [] });
            groups.get(key).indices.push(index);
        });

        groups.forEach(group => {
            if (!this.geometryCache.has(group.geometryKey)) {
                this.geometryCache.set(
                    group.geometryKey,
                    new THREE.SphereGeometry(group.radius, segmentCount, Math.max(10, Math.floor(segmentCount * 0.65)))
                );
            }
            if (!this.materialCache.has(group.materialKey)) {
                this.materialCache.set(group.materialKey, new THREE.MeshStandardMaterial({
                    color: group.color,
                    roughness: 0.54,
                    metalness: 0.04
                }));
            }
            const total = group.indices.length * shifts.length;
            const mesh = new THREE.InstancedMesh(
                this.geometryCache.get(group.geometryKey),
                this.materialCache.get(group.materialKey),
                total
            );
            mesh.frustumCulled = false;
            mesh.userData = { supercellInstanced: true, entries: [], sharedGeometry: true, sharedMaterial: true };
            let instanceId = 0;
            shifts.forEach(shift => {
                group.indices.forEach(index => {
                    const entry = { index, shift: shift.clone(), instanceId };
                    mesh.userData.entries.push(entry);
                    this.setSupercellInstanceMatrix(mesh, entry);
                    instanceId++;
                });
            });
            mesh.instanceMatrix.needsUpdate = true;
            this.supercellGroup.add(mesh);
        });
    }

    setSupercellInstanceMatrix(mesh, entry) {
        const atom = this.atomMeshByIndex.get(entry.index);
        const visible = atom && this.atomTypeVisible(entry.index);
        const position = visible
            ? atom.position.clone().add(entry.shift)
            : new THREE.Vector3(0, 0, 0);
        this.instanceDummy.position.copy(position);
        this.instanceDummy.rotation.set(0, 0, 0);
        this.instanceDummy.scale.setScalar(visible ? 1 : 0);
        this.instanceDummy.updateMatrix();
        mesh.setMatrixAt(entry.instanceId, this.instanceDummy.matrix);
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
                mesh.userData.entries.forEach(entry => this.setSupercellInstanceMatrix(mesh, entry));
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
        selectedIndices.forEach(idx => {
            const atom = this.atomMeshByIndex.get(idx);
            if (!atom) return;
            if (fixedLine[idx] || fixedLine[String(idx)]) {
                this.addFixedLineGuide(idx, fixedLine[idx] || fixedLine[String(idx)]);
            }
            if (fixedPlane[idx] || fixedPlane[String(idx)]) {
                this.addFixedPlaneGuide(idx, fixedPlane[idx] || fixedPlane[String(idx)]);
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

    addFixedPlaneGuide(index, normalValues) {
        const atom = this.atomMeshByIndex.get(index);
        if (!atom) return;
        const normal = this.normalizedVector(normalValues);
        const planeOffset = 0.04;
        const group = new THREE.Group();
        group.userData = {
            constraintGuideFor: index,
            kind: 'fixed_plane',
            normal: normal.toArray(),
            anchor: atom.position.toArray(),
            planeOffset
        };

        const guideSize = Math.max(8, Math.min(80, (this.desiredGuideSize?.() || 24) * 0.52));
        const plane = new THREE.Mesh(new THREE.PlaneGeometry(guideSize, guideSize), this.constraintMaterials.planeSoft);
        plane.userData.sharedMaterial = true;
        plane.renderOrder = 16;
        group.add(plane);

        const half = guideSize * 0.5;
        const cross = guideSize * 0.34;
        const edgeRadius = Math.max(0.008, guideSize * 0.0016);
        const crossRadius = Math.max(0.010, guideSize * 0.0018);
        const normalRadius = Math.max(0.012, guideSize * 0.0021);
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

        const tickLength = Math.max(0.9, Math.min(2.4, guideSize * 0.085));
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
            const atom = this.atomMeshByIndex.get(group.userData.constraintGuideFor);
            if (!atom || !this.atomTypeVisible(group.userData.constraintGuideFor)) {
                group.visible = false;
                return;
            }
            group.visible = true;
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

    clearSelectionOutlines() {
        while(this.selectionOutlines.children.length > 0) {
            const child = this.selectionOutlines.children[0];
            this.selectionOutlines.remove(child);
            if(child.geometry) child.geometry.dispose();
            if(child.material) child.material.dispose();
        }
    }

    setSelection(selectedIndices) {
        this.clearSelectionOutlines();
        const selected = new Set(selectedIndices);
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
    }

    syncSelectionOutlines() {
        this.selectionOutlines.children.forEach(outline => {
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
    }

    exportPNG(width, height, options = {}) {
        const transparentBackground = Boolean(options.transparentBackground);
        const includeGrid = options.includeGrid !== false;
        const includeAxes = options.includeAxes !== false;
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
            return this.renderer.domElement.toDataURL('image/png');
        } finally {
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
        }
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.updateBondPositions();
        this.syncSelectionOutlines();
        this.onFrame?.();
        this.updateViewLighting();
        this.renderer.render(this.scene, this.camera);
    }
}
