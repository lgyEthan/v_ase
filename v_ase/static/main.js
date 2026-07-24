import * as THREE from 'three';
import { ASEApi } from './api.js?v=0.0.74&rev=1';
import { ASERenderer } from './renderer.js?v=0.0.74&rev=1';
import { ASESelection } from './selection.js?v=0.0.74&rev=1';
import { ASETransform } from './transform.js?v=0.0.74&rev=1';

class VAseApp {
    constructor() {
        this.sessionId = new URLSearchParams(window.location.search).get('session_id');
        this.api = new ASEApi(this.sessionId);
        this.pendingApply = Promise.resolve();
        
        this.renderer = new ASERenderer(document.getElementById('app-viewport'));
        this.selection = new ASESelection(this.renderer);
        this.transform = new ASETransform(this.renderer.scene);
        this.initialDesignSettings = null;
        this.frameLoadInFlight = false;
        this.pendingFrameIndex = null;
        this.controlCommitState = new WeakMap();
        this.renderer.onFrame = () => this.updateOrientationWidget();
        this.renderer.onCameraChange = event => this.syncAtomicScaleFromCamera({
            forceInput: event?.source !== 'scale-input'
        });
        
        this.state = {
            atoms: null,
            selected: new Set(),
            replicaSelected: new Map(),
            selectionOrder: [],
            originalPositions: [], // For preview transforms
            isDragging: false,
            pointerDownTime: 0,
            lastPointer: new THREE.Vector2(window.innerWidth / 2, window.innerHeight / 2),
            transformStartPointer: new THREE.Vector2(window.innerWidth / 2, window.innerHeight / 2),
            suppressNextPointerUp: false,
            clipboard: null,
            display: {
                showBonds: false,
                showCell: true,
                showAxes: true,
                showGrid: true,
                showOverlays: true,
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
                commensurateGuide: false,
                commensurateSnap: true,
                commensurateStrainTolerance: 0.01,
                commensurateMaxIndex: 32,
                commensurateSnapRangeDeg: 2.0,
                supercell: [1, 1, 1],
                projectionMode: 'orthographic',
                viewportBackground: 'dark',
                atomDisplayMode: '3d',
                viewRotationStepDeg: 15,
                lightingMode: 'modeling',
                sunIntensity: 2.2,
                sunPosition: [8, -10, 14],
                sunTarget: [0, 0, 0],
                sunGizmo: false,
                blenderExportMode: 'instanced',
                exportIncludeCell: true,
                imageFramingMode: 'viewport',
                atomicScalePixelsPerAngstrom: null,
                imageSphereQuality: 'viewport',
                imageSmoothnessScale: 1,
                videoFormat: 'mov',
                videoFps: 12
            },
            antiAliasing: true,
            sphereQuality: 'auto',
            applyConstraints: true,
            vizOnly: false,
            moveIncrement: 0,
            rotateIncrementDeg: 0,
            transformReadout: '',
            hoveredIndex: null,
            hoveredReference: null,
            displayConfigLoaded: false,
            rotationScreenPivot: new THREE.Vector2(window.innerWidth / 2, window.innerHeight / 2),
            rotationLastAngle: 0,
            rotationPointerActive: false,
            commensurateCandidates: [],
            commensurateSearch: null,
            commensurateRequestToken: 0,
            commensurateReferenceDirection: null,
            commensurateGuideRadius: 4,
            commensurateSnappedCandidate: null,
            transformSubject: null,
            sunSelected: null,
            sunTransformOriginal: null,
            trajectoryTimer: null,
            trajectoryPlaybackSource: null,
            trajectoryBinaryCache: null,
            trajectoryBinaryPromise: null,
            relaxTrajectory: {
                frames: [],
                frame: 0,
                sourceFrame: 0,
                active: false,
                finished: false
            },
            typeOrder: [],
            typeIndices: new Map(),
            pendingTypeRenames: new Set(),
            cachedFmax: null,
            displayApplyRequest: null,
            exportPreviewEnabled: false,
            imageExportProfile: null,
            exportPreviewProfile: null,
            hoverPickTimer: null,
            hoverPointer: null,
            orientationSignature: null,
            isRelaxing: false
        };

        this.inspectorGroup = 'inspect';

        this.init();
    }

    async init() {
        this.setBusy('Loading structure...');
        try {
            if (!this.sessionId) {
                const active = await this.api.fetchActiveSession();
                this.sessionId = active.session_id;
                this.api.sessionId = this.sessionId;
            }
            this.setupWebSocket();
            this.setupInspectorResizer();
            this.setupInspectorNavigation();
            this.setupViewControls();
            this.setupLightingControls();
            this.setupCreateAtomWidget();
            this.setupEventListeners();
            this.setupInputCommitBehavior();
            this.setupNumberInputHoldGuards();
            await this.refresh();
        } catch (err) {
            console.error("v_ase initialization failed:", err);
            this.toast(`Initialization failed: ${err.message}`, 'error');
        } finally {
            this.clearBusy();
        }
    }

    canEditAtoms() {
        return !this.state.vizOnly;
    }

    canViewportSelectAtoms() {
        return true;
    }

    updateEditingAvailability() {
        document.body.dataset.vizOnly = this.state.vizOnly ? 'true' : 'false';
        document.querySelectorAll('[data-edit-only]').forEach(el => {
            if ('disabled' in el) el.disabled = this.state.vizOnly;
        });
        if (this.state.vizOnly && this.transform.mode !== 'IDLE') {
            this.cancelTransform();
        }
    }

    editOnlyToast() {
        this.toast('Visualization mode is lightweight; use --interactive to enable atom editing.', 'warning');
    }

    setupCreateAtomWidget() {
        const widget = document.getElementById('create-atom-widget');
        if (!widget) return;
        const typeSelect = document.getElementById('create-atom-type');
        const labelInput = document.getElementById('create-atom-label');
        const toggle = document.getElementById('btn-create-atom-toggle');
        const close = document.getElementById('btn-create-atom-close');
        const head = document.getElementById('create-atom-drag');
        const centerButton = document.getElementById('btn-create-atom-center');
        const selectedButton = document.getElementById('btn-create-atom-selected');
        const addButton = document.getElementById('btn-create-atom-add');
        if (typeSelect && !typeSelect.options.length) {
            this.chemicalElementOptions().forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                option.textContent = symbol;
                typeSelect.appendChild(option);
            });
            typeSelect.value = 'H';
        }
        const setExpanded = expanded => widget.classList.toggle('collapsed', !expanded);
        const setPositionInputs = vector => {
            ['x', 'y', 'z'].forEach((axis, idx) => {
                const input = document.getElementById(`create-atom-${axis}`);
                if (input) input.value = Number(vector.getComponent(idx).toFixed(4));
            });
        };
        toggle?.addEventListener('click', event => {
            event.preventDefault();
            setExpanded(true);
            this.syncCreateAtomDefaults({ position: true });
        });
        close?.addEventListener('click', event => {
            event.preventDefault();
            setExpanded(false);
        });
        typeSelect?.addEventListener('change', () => {
            if (!labelInput) return;
            const current = this.normalizedTypeLabel(labelInput.value);
            if (!current || this.chemicalElementOptions().includes(current)) {
                labelInput.value = typeSelect.value;
            }
        });
        centerButton?.addEventListener('click', event => {
            event.preventDefault();
            setPositionInputs(this.createAtomViewCenter());
        });
        selectedButton?.addEventListener('click', event => {
            event.preventDefault();
            setPositionInputs(this.getSceneCenter());
        });
        addButton?.addEventListener('click', event => {
            event.preventDefault();
            this.createAtomFromWidget();
        });
        this.makeCreateAtomWidgetDraggable(widget, head);
    }

    makeCreateAtomWidgetDraggable(widget, handle) {
        if (!widget || !handle) return;
        let dragging = false;
        let startX = 0;
        let startY = 0;
        let startLeft = 0;
        let startTop = 0;
        const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
        const onMove = event => {
            if (!dragging) return;
            const rect = widget.getBoundingClientRect();
            const left = clamp(startLeft + event.clientX - startX, 12, window.innerWidth - rect.width - 12);
            const top = clamp(startTop + event.clientY - startY, 84, window.innerHeight - rect.height - 88);
            widget.style.left = `${left}px`;
            widget.style.top = `${top}px`;
            widget.style.right = 'auto';
            widget.style.bottom = 'auto';
        };
        const onUp = () => {
            if (!dragging) return;
            dragging = false;
            document.body.classList.remove('dragging-create-atom');
            window.removeEventListener('pointermove', onMove, true);
            window.removeEventListener('pointerup', onUp, true);
            window.removeEventListener('pointercancel', onUp, true);
        };
        handle.addEventListener('pointerdown', event => {
            if (event.target?.closest?.('button')) return;
            event.preventDefault();
            event.stopPropagation();
            const rect = widget.getBoundingClientRect();
            dragging = true;
            startX = event.clientX;
            startY = event.clientY;
            startLeft = rect.left;
            startTop = rect.top;
            document.body.classList.add('dragging-create-atom');
            handle.setPointerCapture?.(event.pointerId);
            window.addEventListener('pointermove', onMove, true);
            window.addEventListener('pointerup', onUp, true);
            window.addEventListener('pointercancel', onUp, true);
        });
    }

    syncCreateAtomDefaults({ position = false } = {}) {
        const typeSelect = document.getElementById('create-atom-type');
        const labelInput = document.getElementById('create-atom-label');
        if (typeSelect && !typeSelect.value) typeSelect.value = 'H';
        if (labelInput && !this.normalizedTypeLabel(labelInput.value)) labelInput.value = typeSelect?.value || 'H';
        if (position) {
            const center = this.createAtomViewCenter();
            ['x', 'y', 'z'].forEach((axis, idx) => {
                const input = document.getElementById(`create-atom-${axis}`);
                if (input && !input.value) input.value = Number(center.getComponent(idx).toFixed(4));
            });
        }
    }

    createAtomViewCenter() {
        const target = this.renderer?.controls?.target;
        if (target) return target.clone();
        if (this.state.atoms?.positions?.length) return this.getSceneCenter();
        return new THREE.Vector3(0, 0, 0);
    }

    createAtomPositionFromWidget() {
        const fallback = this.createAtomViewCenter();
        const values = ['x', 'y', 'z'].map((axis, idx) => {
            const input = document.getElementById(`create-atom-${axis}`);
            const value = Number(input?.value);
            return Number.isFinite(value) ? value : fallback.getComponent(idx);
        });
        return values;
    }

    async createAtomFromWidget() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const typeSelect = document.getElementById('create-atom-type');
        const labelInput = document.getElementById('create-atom-label');
        const rawLabel = this.normalizedTypeLabel(labelInput?.value);
        const baseSymbol = typeSelect?.value || this.detectedElementForLabel(rawLabel) || 'H';
        const symbol = rawLabel || baseSymbol;
        const position = this.createAtomPositionFromWidget();
        try {
            const before = this.state.atoms?.positions?.length || 0;
            const data = await this.api.addAtom(symbol, position, baseSymbol);
            this.setAtomsData(data, { clearSelection: true });
            if (data.positions?.length > before) {
                this.state.selected.add(data.positions.length - 1);
                this.updateSelectionVisuals();
                this.updateUI();
            }
            this.toast(`Created ${symbol} at (${position.map(v => v.toFixed(2)).join(', ')}).`, 'success');
        } catch (err) {
            this.toast(`Create atom failed: ${err.message}`, 'error');
        }
    }

    setupNumberInputHoldGuards() {
        this.enhanceNumberInputHoldGuards(document);
        this.numberInputHoldObserver = new MutationObserver(mutations => {
            for (const mutation of mutations) {
                mutation.addedNodes.forEach(node => {
                    if (node instanceof HTMLElement) this.enhanceNumberInputHoldGuards(node);
                });
            }
        });
        this.numberInputHoldObserver.observe(document.body, { childList: true, subtree: true });
    }

    enhanceNumberInputHoldGuards(root = document) {
        const inputs = [];
        if (root instanceof HTMLInputElement && root.type === 'number') inputs.push(root);
        if (root.querySelectorAll) inputs.push(...root.querySelectorAll('input[type="number"]:not([data-hold-guarded])'));
        inputs.forEach(input => this.bindNumberInputHoldGuard(input));
    }

    bindNumberInputHoldGuard(input) {
        if (!input || input.dataset.holdGuarded === 'true') return;
        input.dataset.holdGuarded = 'true';
        const stop = () => {
            window.removeEventListener('pointerup', stop, true);
            window.removeEventListener('pointercancel', stop, true);
            window.removeEventListener('blur', stop, true);
        };
        const pressHandler = event => {
            if (event.button !== 0 || input.disabled || input.readOnly) return;
            const direction = this.nativeNumberSpinDirection(input, event);
            if (!direction) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            input.focus({ preventScroll: true });
            this.stepNumberInputOnce(input, direction);
            window.addEventListener('pointerup', stop, true);
            window.addEventListener('pointercancel', stop, true);
            window.addEventListener('blur', stop, true);
        };
        input.addEventListener('pointerdown', pressHandler, true);
    }

    nativeNumberSpinDirection(input, event) {
        const rect = input.getBoundingClientRect();
        if (!rect.width || !rect.height) return 0;
        if (event.clientY < rect.top || event.clientY > rect.bottom) return 0;
        const spinnerWidth = Math.min(28, Math.max(16, rect.width * 0.28));
        const isRtl = getComputedStyle(input).direction === 'rtl';
        const inSpinRegion = isRtl
            ? event.clientX >= rect.left && event.clientX <= rect.left + spinnerWidth
            : event.clientX <= rect.right && event.clientX >= rect.right - spinnerWidth;
        if (!inSpinRegion) return 0;
        return event.clientY < rect.top + rect.height / 2 ? 1 : -1;
    }

    stepNumberInputOnce(input, direction) {
        try {
            direction > 0 ? input.stepUp() : input.stepDown();
        } catch {
            const step = Number(input.step || 1);
            const delta = Number.isFinite(step) && step > 0 ? step : 1;
            const current = Number(input.value || 0);
            let next = (Number.isFinite(current) ? current : 0) + direction * delta;
            const min = Number(input.min);
            const max = Number(input.max);
            if (Number.isFinite(min)) next = Math.max(min, next);
            if (Number.isFinite(max)) next = Math.min(max, next);
            input.value = String(next);
        }
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    isCommittableInput(element) {
        if (element instanceof HTMLTextAreaElement) return true;
        if (!(element instanceof HTMLInputElement)) return false;
        return !['button', 'submit', 'reset', 'file', 'checkbox', 'radio', 'range'].includes(element.type);
    }

    isDisplayCommitInput(element) {
        return element.matches([
            '#bond-cutoff',
            '#bond-custom-color',
            '#super-x', '#super-y', '#super-z',
            '#commensurate-strain',
            '#commensurate-max-index',
            '#commensurate-snap-range',
            '.element-bond-cutoff',
            '.element-radius-input',
            '.element-color-input'
        ].join(','));
    }

    commitInputValue(element, { dispatchChange = true } = {}) {
        if (!this.isCommittableInput(element)) return;
        const record = this.controlCommitState.get(element);
        const dirty = !record || record.dirty || record.value !== element.value;
        this.controlCommitState.set(element, { value: element.value, dirty: false });
        if (dispatchChange && dirty) {
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (this.isDisplayCommitInput(element)) {
            try {
                this.applyDisplayOptions();
            } catch (error) {
                this.toast(error.message, 'error');
            }
        } else if (element.matches('#sun-position-x, #sun-position-y, #sun-position-z, #sun-target-x, #sun-target-y, #sun-target-z')) {
            this.applyLightingControls();
        }
    }

    setupInputCommitBehavior() {
        document.addEventListener('focusin', event => {
            if (!this.isCommittableInput(event.target)) return;
            this.controlCommitState.set(event.target, { value: event.target.value, dirty: false });
        }, true);
        document.addEventListener('input', event => {
            if (!this.isCommittableInput(event.target)) return;
            const previous = this.controlCommitState.get(event.target) || { value: event.target.value, dirty: false };
            previous.dirty = previous.value !== event.target.value;
            this.controlCommitState.set(event.target, previous);
        }, true);
        document.addEventListener('change', event => {
            if (!this.isCommittableInput(event.target)) return;
            this.controlCommitState.set(event.target, { value: event.target.value, dirty: false });
        }, true);
        document.addEventListener('keydown', event => {
            if (!this.isCommittableInput(event.target)) return;
            if (event.key === 'Tab') {
                this.commitInputValue(event.target);
                return;
            }
            if (event.key !== 'Enter' || event.target instanceof HTMLTextAreaElement) return;
            event.preventDefault();
            this.commitInputValue(event.target);
            event.target.blur();
        });
        document.addEventListener('focusout', event => {
            if (!this.isCommittableInput(event.target)) return;
            this.commitInputValue(event.target);
        }, true);
    }

    clampInspectorWidth(width) {
        const minWidth = 356;
        const maxWidth = Math.max(minWidth, Math.min(760, window.innerWidth - 260));
        return Math.max(minWidth, Math.min(maxWidth, Math.round(width)));
    }

    setInspectorWidth(width, persist = false) {
        const clamped = this.clampInspectorWidth(width);
        document.documentElement.style.setProperty('--inspector-width', `${clamped}px`);
        document.body.classList.toggle('inspector-wide', clamped >= 520);
        if (persist) {
            try {
                window.localStorage?.setItem('v_ase.inspectorWidth', String(clamped));
            } catch {
                // Local storage may be unavailable in restricted browser contexts.
            }
        }
        this.renderer?.onResize?.();
    }

    setupInspectorResizer() {
        const resizer = document.getElementById('inspector-resizer');
        if (!resizer) return;
        let savedWidth = null;
        try {
            savedWidth = Number(window.localStorage?.getItem('v_ase.inspectorWidth'));
        } catch {
            savedWidth = null;
        }
        this.setInspectorWidth(Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : 416);
        const onMove = event => {
            this.setInspectorWidth(window.innerWidth - event.clientX, false);
        };
        const onUp = event => {
            document.body.classList.remove('resizing-inspector');
            this.setInspectorWidth(window.innerWidth - event.clientX, true);
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            window.removeEventListener('pointercancel', onUp);
        };
        resizer.addEventListener('pointerdown', event => {
            if (document.body.classList.contains('inspector-collapsed')) return;
            event.preventDefault();
            event.stopPropagation();
            document.body.classList.add('resizing-inspector');
            resizer.setPointerCapture?.(event.pointerId);
            window.addEventListener('pointermove', onMove);
            window.addEventListener('pointerup', onUp);
            window.addEventListener('pointercancel', onUp);
        });
    }

    setInspectorCollapsed(collapsed, persist = true) {
        const next = Boolean(collapsed);
        document.body.classList.toggle('inspector-collapsed', next);
        const button = document.getElementById('btn-inspector-collapse');
        if (button) {
            button.setAttribute('aria-expanded', next ? 'false' : 'true');
            button.setAttribute('aria-label', next ? 'Expand control panel' : 'Collapse control panel');
            button.title = next ? 'Expand control panel' : 'Collapse control panel';
        }
        if (persist) {
            try {
                window.localStorage?.setItem('v_ase.inspectorCollapsed', next ? '1' : '0');
            } catch {
                // Local storage may be unavailable in restricted browser contexts.
            }
        }
        this.renderer?.onResize?.();
    }

    setInspectorGroup(group, persist = true) {
        const migrations = { edit: 'structure', scene: 'display' };
        const available = new Set(['inspect', 'structure', 'display', 'output']);
        const requested = migrations[group] || group;
        const next = available.has(requested) ? requested : 'inspect';
        this.inspectorGroup = next;
        document.querySelectorAll('[data-inspector-group]').forEach(button => {
            const active = button.dataset.inspectorGroup === next;
            button.setAttribute('aria-selected', active ? 'true' : 'false');
            button.tabIndex = active ? 0 : -1;
        });
        document.querySelectorAll('#inspector [data-panel-group]').forEach(panel => {
            panel.classList.toggle('group-hidden', panel.dataset.panelGroup !== next);
        });
        const label = document.getElementById('inspector-context');
        if (label) {
            const labels = { output: 'Export & Save' };
            label.textContent = labels[next] || (next.charAt(0).toUpperCase() + next.slice(1));
        }
        if (persist) {
            try {
                window.localStorage?.setItem('v_ase.inspectorGroup', next);
            } catch {
                // Local storage may be unavailable in restricted browser contexts.
            }
        }
    }

    setupInspectorNavigation() {
        let savedGroup = 'inspect';
        let collapsed = true;
        try {
            savedGroup = window.localStorage?.getItem('v_ase.inspectorGroup') || 'inspect';
            const savedCollapsed = window.localStorage?.getItem('v_ase.inspectorCollapsed');
            collapsed = savedCollapsed === null ? true : savedCollapsed === '1';
        } catch {
            savedGroup = 'inspect';
            collapsed = true;
        }
        document.querySelectorAll('[data-inspector-group]').forEach(button => {
            button.addEventListener('click', () => this.setInspectorGroup(button.dataset.inspectorGroup));
        });
        document.getElementById('btn-inspector-collapse')?.addEventListener('click', () => {
            this.setInspectorCollapsed(!document.body.classList.contains('inspector-collapsed'));
        });
        this.setInspectorGroup(savedGroup, false);
        this.setInspectorCollapsed(collapsed, false);
    }

    normalizedViewRotationStep(value = this.state.display.viewRotationStepDeg) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.max(0.1, Math.min(360, parsed)) : 15;
    }

    syncViewControls(options = this.state.display) {
        const background = options.viewportBackground === 'white' ? 'white' : 'dark';
        const displayMode = options.atomDisplayMode === '2d' ? '2d' : '3d';
        const step = this.normalizedViewRotationStep(options.viewRotationStepDeg);
        const backgroundSelect = document.getElementById('viewport-background');
        const displaySelect = document.getElementById('atom-display-mode');
        const stepInput = document.getElementById('view-rotate-step');
        if (backgroundSelect && document.activeElement !== backgroundSelect) backgroundSelect.value = background;
        if (displaySelect && document.activeElement !== displaySelect) displaySelect.value = displayMode;
        if (stepInput && document.activeElement !== stepInput) stepInput.value = `${step}`;
        document.querySelectorAll('[data-view-background]').forEach(button => {
            button.setAttribute('aria-pressed', button.dataset.viewBackground === background ? 'true' : 'false');
        });
        document.querySelectorAll('[data-atom-display-mode]').forEach(button => {
            button.setAttribute('aria-pressed', button.dataset.atomDisplayMode === displayMode ? 'true' : 'false');
        });
        document.body.dataset.viewportBackground = background;
        document.body.dataset.atomDisplayMode = displayMode;
    }

    applyViewDisplayOption(key, value) {
        if (key === 'viewportBackground') {
            this.state.display.viewportBackground = value === 'white' ? 'white' : 'dark';
        } else if (key === 'atomDisplayMode') {
            this.state.display.atomDisplayMode = value === '2d' ? '2d' : '3d';
        } else {
            return;
        }
        this.syncViewControls();
        this.renderer.setDisplayOptions(this.state.display);
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
    }

    completeCameraViewChange(source = 'view-toolbar') {
        const camera = this.renderer.camera;
        camera.lookAt(this.renderer.controls.target);
        camera.updateMatrixWorld(true);
        this.renderer.controls.endGesture?.();
        this.renderer.controls.update?.();
        this.renderer.syncSelectionOutlines();
        this.transform.updateGuides(camera);
        this.renderer.onCameraChange?.({ source });
        this.updateOrientationWidget();
        this.renderer.requestRender();
    }

    rotateCameraView(axis, visualDegrees) {
        const vectors = {
            X: new THREE.Vector3(1, 0, 0),
            Y: new THREE.Vector3(0, 1, 0),
            Z: new THREE.Vector3(0, 0, 1)
        };
        const worldAxis = vectors[axis];
        const degrees = Number(visualDegrees);
        if (!worldAxis || !Number.isFinite(degrees) || Math.abs(degrees) < 1e-12) return;
        const camera = this.renderer.camera;
        const target = this.renderer.controls.target.clone();
        const inverseViewRotation = new THREE.Quaternion().setFromAxisAngle(
            worldAxis,
            -THREE.MathUtils.degToRad(degrees)
        );
        const offset = camera.position.clone().sub(target).applyQuaternion(inverseViewRotation);
        camera.position.copy(target).add(offset);
        camera.up.applyQuaternion(inverseViewRotation).normalize();
        this.completeCameraViewChange('view-rotate');
        this.toast(`View rotated ${degrees > 0 ? '+' : ''}${degrees.toFixed(2)} deg around ${axis}.`, 'success');
    }

    setViewToAxis(axis, sign = 1) {
        const vectors = {
            X: new THREE.Vector3(1, 0, 0),
            Y: new THREE.Vector3(0, 1, 0),
            Z: new THREE.Vector3(0, 0, 1)
        };
        const base = vectors[axis];
        if (!base) return;
        const normalizedSign = Number(sign) < 0 ? -1 : 1;
        const camera = this.renderer.camera;
        const target = this.renderer.controls.target.clone();
        const distance = Math.max(camera.position.distanceTo(target), 4);
        camera.position.copy(target).addScaledVector(base, normalizedSign * distance);
        camera.up.copy(axis === 'Z'
            ? new THREE.Vector3(0, 1, 0)
            : new THREE.Vector3(0, 0, 1));
        this.completeCameraViewChange('view-align');
        this.toast(`View aligned to ${normalizedSign > 0 ? '+' : '-'}${axis}.`, 'success');
    }

    setupViewControls() {
        const widget = document.getElementById('view-widget');
        const card = document.getElementById('view-card');
        const trigger = document.getElementById('btn-view-toggle');
        const setOpen = open => {
            card?.classList.toggle('hidden', !open);
            trigger?.setAttribute('aria-expanded', open ? 'true' : 'false');
            widget?.classList.toggle('open', open);
        };
        trigger?.addEventListener('click', event => {
            event.stopPropagation();
            setOpen(card?.classList.contains('hidden'));
        });
        document.getElementById('btn-view-close')?.addEventListener('click', () => setOpen(false));
        document.addEventListener('pointerdown', event => {
            if (!card?.classList.contains('hidden') && widget && !widget.contains(event.target)) setOpen(false);
        });
        document.querySelectorAll('[data-view-background]').forEach(button => {
            button.addEventListener('click', () => {
                this.applyViewDisplayOption('viewportBackground', button.dataset.viewBackground);
            });
        });
        document.querySelectorAll('[data-atom-display-mode]').forEach(button => {
            button.addEventListener('click', () => {
                this.applyViewDisplayOption('atomDisplayMode', button.dataset.atomDisplayMode);
            });
        });
        document.getElementById('viewport-background')?.addEventListener('change', event => {
            this.applyViewDisplayOption('viewportBackground', event.target.value);
        });
        document.getElementById('atom-display-mode')?.addEventListener('change', event => {
            this.applyViewDisplayOption('atomDisplayMode', event.target.value);
        });
        const stepInput = document.getElementById('view-rotate-step');
        const commitStep = () => {
            const step = this.normalizedViewRotationStep(stepInput?.value);
            this.state.display.viewRotationStepDeg = step;
            if (stepInput) stepInput.value = `${step}`;
            this.syncViewControls();
        };
        stepInput?.addEventListener('change', commitStep);
        stepInput?.addEventListener('blur', commitStep);
        document.querySelectorAll('[data-view-rotate-axis]').forEach(button => {
            button.addEventListener('click', () => {
                commitStep();
                const sign = Number(button.dataset.viewRotateSign) < 0 ? -1 : 1;
                this.rotateCameraView(
                    button.dataset.viewRotateAxis,
                    sign * this.state.display.viewRotationStepDeg
                );
            });
        });
        document.querySelectorAll('[data-view-align-axis]').forEach(button => {
            button.addEventListener('click', () => {
                this.setViewToAxis(button.dataset.viewAlignAxis, Number(button.dataset.viewAlignSign));
            });
        });
        this.syncViewControls();
    }

    lightingVectorFromInputs(prefix, fallback) {
        return ['x', 'y', 'z'].map((axis, index) => {
            const value = Number(document.getElementById(`${prefix}-${axis}`)?.value);
            return Number.isFinite(value) ? value : fallback[index];
        });
    }

    syncLightingControls(options = this.state.display) {
        const mode = options.lightingMode || 'modeling';
        const setValue = (id, value) => {
            const element = document.getElementById(id);
            if (element && document.activeElement !== element) element.value = `${value}`;
        };
        setValue('lighting-mode', mode);
        setValue('sun-intensity', Number(options.sunIntensity ?? 2.2));
        const intensityValue = document.getElementById('sun-intensity-value');
        if (intensityValue) intensityValue.textContent = Number(options.sunIntensity ?? 2.2).toFixed(2);
        ['x', 'y', 'z'].forEach((axis, index) => {
            setValue(`sun-position-${axis}`, Number(options.sunPosition?.[index] ?? [8, -10, 14][index]).toFixed(3));
            setValue(`sun-target-${axis}`, Number(options.sunTarget?.[index] ?? 0).toFixed(3));
        });
        const gizmo = document.getElementById('chk-sun-gizmo');
        if (gizmo) gizmo.checked = Boolean(options.sunGizmo);
        const cardMode = document.getElementById('lighting-card-mode');
        if (cardMode) cardMode.textContent = mode === 'studio-shadow' ? 'Soft Shadow' : mode === 'studio' ? 'Studio Sun' : 'Modeling';
        const widget = document.getElementById('lighting-widget');
        if (widget) widget.dataset.mode = mode;
        document.querySelectorAll('.lighting-card-body input:not(#lighting-mode), .lighting-card-body button').forEach(control => {
            if (control.id === 'chk-sun-gizmo') return;
            control.disabled = mode === 'modeling';
        });
    }

    applyLightingControls() {
        const fallbackPosition = this.state.display.sunPosition || [8, -10, 14];
        const fallbackTarget = this.state.display.sunTarget || [0, 0, 0];
        this.state.display.lightingMode = document.getElementById('lighting-mode')?.value || 'modeling';
        this.state.display.sunIntensity = Math.max(0, Number(document.getElementById('sun-intensity')?.value || 2.2));
        this.state.display.sunPosition = this.lightingVectorFromInputs('sun-position', fallbackPosition);
        this.state.display.sunTarget = this.lightingVectorFromInputs('sun-target', fallbackTarget);
        this.state.display.sunGizmo = Boolean(document.getElementById('chk-sun-gizmo')?.checked);
        this.renderer.setLightingOptions(this.state.display);
        if (!this.sunIsSelectable()) {
            if (this.state.transformSubject === 'sun' && this.transform.mode !== 'IDLE') this.cancelTransform();
            this.setSunSelected(false, { update: false });
        } else if (this.state.sunSelected) {
            this.renderer.setSunGizmoSelected(this.state.sunSelected);
        }
        this.syncLightingControls();
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
    }

    sunIsSelectable() {
        return this.state.display.lightingMode !== 'modeling' && Boolean(this.state.display.sunGizmo);
    }

    setSunSelected(selected, { clearAtoms = true, update = true } = {}) {
        const requested = selected === true ? 'source' : selected;
        const next = this.sunIsSelectable() && ['source', 'target'].includes(requested)
            ? requested
            : null;
        this.state.sunSelected = next;
        this.renderer.setSunGizmoSelected(next);
        if (next && clearAtoms && this.selectionCount() > 0) {
            this.clearAtomSelection();
            this.updateSelectionVisuals();
        }
        if (update) {
            this.updateToolState();
            this.updateUI();
        }
    }

    setupLightingControls() {
        const widget = document.getElementById('lighting-widget');
        const card = document.getElementById('lighting-card');
        const trigger = document.getElementById('btn-lighting-toggle');
        const setOpen = open => {
            card?.classList.toggle('hidden', !open);
            trigger?.setAttribute('aria-expanded', open ? 'true' : 'false');
            widget?.classList.toggle('open', open);
        };
        trigger?.addEventListener('click', event => {
            event.stopPropagation();
            setOpen(card?.classList.contains('hidden'));
        });
        document.getElementById('btn-lighting-close')?.addEventListener('click', () => setOpen(false));
        document.addEventListener('pointerdown', event => {
            if (!card?.classList.contains('hidden') && widget && !widget.contains(event.target)) setOpen(false);
        });
        document.getElementById('lighting-mode')?.addEventListener('change', () => this.applyLightingControls());
        document.getElementById('sun-intensity')?.addEventListener('input', () => this.applyLightingControls());
        ['sun-position-x', 'sun-position-y', 'sun-position-z', 'sun-target-x', 'sun-target-y', 'sun-target-z'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => this.applyLightingControls());
        });
        document.getElementById('chk-sun-gizmo')?.addEventListener('change', () => this.applyLightingControls());
        document.getElementById('btn-sun-from-view')?.addEventListener('click', () => {
            const camera = this.renderer.camera;
            const target = this.renderer.controls.target;
            this.state.display.sunPosition = [camera.position.x, camera.position.y, camera.position.z];
            this.state.display.sunTarget = [target.x, target.y, target.z];
            this.syncLightingControls();
            this.applyLightingControls();
        });
        document.getElementById('btn-sun-target-selection')?.addEventListener('click', () => {
            const target = this.getSceneCenter();
            this.state.display.sunTarget = [target.x, target.y, target.z];
            this.syncLightingControls();
            this.applyLightingControls();
        });
        this.renderer.onLightingChange = options => {
            this.state.display.sunPosition = [...options.sunPosition];
            this.state.display.sunTarget = [...options.sunTarget];
            this.syncLightingControls();
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        };
        this.syncLightingControls();
    }

    async refresh() {
        try {
            if (this.state.displayConfigLoaded) this.captureBondSettingsFromControls();
            const data = await this.api.fetchAtoms();
            if (!data || !data.positions) return;

            this.state.atoms = data;
            this.rebuildTypeIndexCache(data.symbols || []);
            this.state.cachedFmax = this.computeFmax(data.forces || []);
            this.clearRelaxTrajectoryIfTopologyChanged(data);
            this.state.originalPositions = data.positions.map(p => [...p]);
            if (data.metadata?.trajectory_positions_binary && !data.trajectory_positions) {
                this.loadTrajectoryCache({ background: true });
            }
            this.applyInitialDisplayConfig(data);
            this.renderElementBondControls();
            this.renderElementRadiusControls();
            this.updateEditingAvailability();
            this.updateUI();
            
            this.state.display.vizOnly = this.state.vizOnly;
            const requestedAtomicScale = Number(this.state.display.atomicScalePixelsPerAngstrom);
            const hasRequestedAtomicScale = Number.isFinite(requestedAtomicScale) && requestedAtomicScale > 0;
            this.renderer.setDisplayOptions(this.state.display, { rebuild: false });
            this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
            const projectCamera = data.metadata?.config?.initial_design_settings?.camera;
            if (projectCamera) this.applyCameraSettings(projectCamera, { syncScale: false });
            if (projectCamera && hasRequestedAtomicScale) {
                this.renderer.setPixelsPerAngstrom(requestedAtomicScale);
            } else {
                this.syncAtomicScaleFromCamera({ forceInput: true });
            }
            if (!this.initialDesignSettings) this.initialDesignSettings = this.designSettingsSnapshot();
            
            this.updateSelectionVisuals();
            this.updateDocumentAvailability();
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        } catch (err) {
            console.error("DEBUG: Refresh Failed:", err);
        }
    }

    updateUI() {
        this.pruneSelection();
        const meta = this.state.atoms.metadata;
        const selectedEntries = this.selectionEntries();
        const setHtml = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        
        setHtml('prop-natoms', meta.natoms);
        const calcDetails = meta.calculator_details || {};
        const calcLabel = meta.calculator || "NONE";
        setHtml('val-calc', calcDetails.is_default_repulsion && calcDetails.effective_device
            ? `${calcLabel}/${calcDetails.effective_device}`
            : calcLabel);
        const idleMode = this.state.sunSelected
            ? `LIGHT ${this.state.sunSelected === 'target' ? 'TARGET' : 'SOURCE'}`
            : (this.state.vizOnly ? 'VIEW' : 'SELECT');
        setHtml('val-mode', this.transform.mode === 'IDLE' ? idleMode : this.transform.mode);
        setHtml('val-energy', typeof meta.energy === 'number' ? meta.energy.toFixed(4) : "-");
        setHtml('val-fmax', Number.isFinite(this.state.cachedFmax) ? this.state.cachedFmax.toFixed(4) : "-");
        
        const pbc = this.state.atoms.pbc.map(p => p ? 'T' : 'F').join('');
        setHtml('prop-pbc', pbc);
        setHtml('prop-selected', selectedEntries.length);
        this.setCopyableSelectionText(
            'selected-indices',
            selectedEntries.map(reference => this.selectionReferenceLabel(reference)).join(', ') || '-'
        );
        this.setCopyableSelectionText(
            'selected-elements',
            selectedEntries.map(reference => this.selectionReferenceSymbol(reference)).join(', ') || '-'
        );
        this.setSelectionCenterText(this.getSelectionCenterText());
        this.updateSelectionMeasureUI(selectedEntries);
        this.updateTrajectoryUI();
        this.updateElementSelectionControls();
        this.updateSelectionConstraintControls();

        this.updateCalculatorControls(meta);

        const relaxBtn = document.getElementById('btn-relax');
        if (relaxBtn) relaxBtn.disabled = !meta.has_calculator || this.state.isRelaxing;
        const stopRelaxBtn = document.getElementById('btn-stop-relax');
        if (stopRelaxBtn) stopRelaxBtn.disabled = !this.state.isRelaxing;

        this.updateCommandReadout();
        const hoverReadout = document.getElementById('hover-readout');
        if (hoverReadout) hoverReadout.innerText = this.atomHoverText(this.state.hoveredReference);

        document.body.dataset.mode = this.transform.mode.toLowerCase();
    }

    setCopyableSelectionText(id, value) {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerText = value;
        el._copyValue = value === '-' ? '' : value;
        el.title = value.length <= 512 ? value : `${value.slice(0, 509)}...`;
    }

    setSelectionCenterText(value) {
        const el = document.getElementById('selected-center');
        if (!el) return;
        const lines = String(value).split('\n');
        el.replaceChildren();
        lines.forEach(line => {
            const row = document.createElement('span');
            row.className = 'selection-center-line';
            row.textContent = line;
            el.appendChild(row);
        });
    }

    updateSelectionMeasureUI(selectedEntries = this.selectionEntries()) {
        const detail = this.getSelectionMeasureText(selectedEntries);
        const panelValue = document.getElementById('selected-measure');
        if (panelValue) panelValue.innerText = detail;
        const readout = document.getElementById('selection-measure-readout');
        const readoutValue = document.getElementById('selection-measure-value');
        if (!readout || !readoutValue) return;
        const summary = this.getSelectionMeasureSummary(selectedEntries);
        readoutValue.innerText = summary;
        readout.classList.toggle('hidden', selectedEntries.length === 0);
    }

    async copySelectionField(targetId) {
        const el = document.getElementById(targetId);
        const text = el?._copyValue || el?.innerText || '';
        if (!text || text === '-') {
            this.toast('Nothing to copy.', 'warning');
            return;
        }
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const area = document.createElement('textarea');
                area.value = text;
                area.style.position = 'fixed';
                area.style.opacity = '0';
                document.body.appendChild(area);
                area.focus();
                area.select();
                document.execCommand('copy');
                document.body.removeChild(area);
            }
            this.toast('Copied selection field.', 'success');
        } catch (err) {
            this.toast(`Copy failed: ${err.message}`, 'error');
        }
    }

    repulsionCalculatorDetails() {
        return this.state.atoms?.metadata?.calculator_details || {};
    }

    currentCalculatorPayload() {
        const details = this.repulsionCalculatorDetails();
        if (!details.is_default_repulsion) return null;
        const device = document.getElementById('calc-device')?.value || details.requested_device || 'cpu';
        const cpuThreads = parseInt(document.getElementById('calc-cpus')?.value || details.cpu_threads || '4', 10);
        return {
            device,
            cpu_threads: Number.isFinite(cpuThreads) ? cpuThreads : 4
        };
    }

    cpuThreadChoices(details) {
        const fromBackend = Array.isArray(details.cpu_thread_options) && details.cpu_thread_options.length
            ? details.cpu_thread_options
            : [];
        if (fromBackend.length) return fromBackend;
        const count = Math.max(1, Number(navigator.hardwareConcurrency || 4));
        return Array.from({ length: count }, (_, idx) => idx + 1);
    }

    updateCalculatorControls(meta) {
        const details = meta?.calculator_details || {};
        const controls = document.getElementById('calc-controls');
        const device = document.getElementById('calc-device');
        const cpus = document.getElementById('calc-cpus');
        if (!controls || !device || !cpus) return;

        const isRepulsion = Boolean(details.is_default_repulsion);
        controls.classList.toggle('disabled', !isRepulsion);
        controls.title = isRepulsion
            ? 'Repulsion calculator settings only'
            : 'Device and CPU thread settings are only used by the default repulsion calculator.';

        const cpuValue = String(details.cpu_threads || 4);
        const choices = this.cpuThreadChoices(details);
        if (cpus.dataset.options !== choices.join(',')) {
            cpus.innerHTML = '';
            choices.forEach(value => {
                const option = document.createElement('option');
                option.value = String(value);
                option.innerText = String(value);
                cpus.appendChild(option);
            });
            cpus.dataset.options = choices.join(',');
        }
        cpus.value = choices.includes(Number(cpuValue)) ? cpuValue : String(Math.min(4, choices[choices.length - 1] || 1));

        const requested = details.requested_device || 'cpu';
        device.value = requested === 'cuda' ? 'cuda' : 'cpu';
        const cudaOption = [...device.options].find(option => option.value === 'cuda');
        if (cudaOption) cudaOption.disabled = !details.cuda_available;
        device.disabled = !isRepulsion || this.state.isRelaxing;
        cpus.disabled = !isRepulsion || this.state.isRelaxing || device.value !== 'cpu';
    }

    async applyCalculatorControls() {
        const payload = this.currentCalculatorPayload();
        if (!payload) return;
        try {
            const data = await this.api.updateCalculatorConfig(payload);
            this.setAtomsData(data);
            const details = data.metadata?.calculator_details || {};
            const suffix = details.backend === 'torch'
                ? `torch/${details.effective_device}`
                : 'numpy';
            this.toast(`Repulsion calculator set to ${suffix}.`, 'success');
        } catch (err) {
            this.toast(`Calculator settings failed: ${err.message}`, 'error');
        }
    }

    toast(message, type = 'info') {
        const root = document.getElementById('toast-container');
        if (!root) return;
        const item = document.createElement('div');
        item.className = `toast ${type}`;
        item.innerText = message;
        root.appendChild(item);
        setTimeout(() => item.classList.add('show'), 10);
        setTimeout(() => {
            item.classList.remove('show');
            setTimeout(() => item.remove(), 180);
        }, 2600);
    }

    isPhysicalKey(event, code, fallbackKeys = []) {
        if (event.code === code) return true;
        const key = typeof event.key === 'string' ? event.key.toLowerCase() : '';
        return fallbackKeys.includes(key);
    }

    keyCodeValue(event) {
        if (event.code?.startsWith('Digit')) return event.code.slice(5);
        if (event.code?.startsWith('Numpad')) {
            const value = event.code.slice(6);
            if (/^\d$/.test(value)) return value;
            if (value === 'Decimal') return '.';
            if (value === 'Subtract') return '-';
            if (value === 'Add') return '+';
        }
        if (event.code === 'Minus') return '-';
        if (event.code === 'Period') return '.';
        if (/^[0-9.+-]$/.test(event.key || '')) return event.key;
        return null;
    }

    axisFromKey(event) {
        if (event.code === 'KeyX') return 'X';
        if (event.code === 'KeyY') return 'Y';
        if (event.code === 'KeyZ') return 'Z';
        const key = typeof event.key === 'string' ? event.key.toLowerCase() : '';
        if (key === 'x') return 'X';
        if (key === 'y') return 'Y';
        if (key === 'z') return 'Z';
        return null;
    }

    readTransformSettings() {
        const moveIncrement = Number(document.getElementById('move-increment')?.value || 0);
        const rotateIncrementDeg = Number(document.getElementById('rotate-increment')?.value || 0);
        this.state.moveIncrement = Number.isFinite(moveIncrement) && moveIncrement > 0 ? moveIncrement : 0;
        this.state.rotateIncrementDeg = Number.isFinite(rotateIncrementDeg) && rotateIncrementDeg > 0 ? rotateIncrementDeg : 0;
    }

    snapScalar(value, increment) {
        if (!Number.isFinite(value) || !Number.isFinite(increment) || increment <= 0) return value;
        return Math.round(value / increment) * increment;
    }

    snapMoveDelta(delta, axisVec = null) {
        const increment = this.state.moveIncrement || 0;
        if (increment <= 0) return delta;
        if (axisVec && axisVec.lengthSq() > 0) {
            const scalar = delta.dot(axisVec);
            return axisVec.clone().multiplyScalar(this.snapScalar(scalar, increment));
        }
        return new THREE.Vector3(
            this.snapScalar(delta.x, increment),
            this.snapScalar(delta.y, increment),
            this.snapScalar(delta.z, increment)
        );
    }

    snapRotationAngle(angle) {
        const incrementDeg = this.state.rotateIncrementDeg || 0;
        if (incrementDeg <= 0) return angle;
        return THREE.MathUtils.degToRad(this.snapScalar(THREE.MathUtils.radToDeg(angle), incrementDeg));
    }

    formatNumber(value, digits = 3) {
        return Number.isFinite(value) ? value.toFixed(digits) : '-';
    }

    formatVector(values, digits = 3) {
        if (!values || values.some(v => !Number.isFinite(Number(v)))) return '-';
        return values.map(v => Number(v).toFixed(digits)).join(', ');
    }

    formatVectorTuple(values, digits = 3) {
        const text = this.formatVector(values, digits);
        return text === '-' ? '-' : `(${text})`;
    }

    formatMoveReadout(delta) {
        const length = delta.length();
        return `d=(${this.formatNumber(delta.x)}, ${this.formatNumber(delta.y)}, ${this.formatNumber(delta.z)}) A | |d|=${this.formatNumber(length)} A`;
    }

    formatRotateReadout(angle) {
        return `${this.formatNumber(THREE.MathUtils.radToDeg(angle), 2)} deg`;
    }

    transformMouseLabel() {
        if (this.transform.mode === 'MOVE' && this.state.moveIncrement > 0) {
            return `mouse / ${this.state.moveIncrement.toFixed(2)} A`;
        }
        if (this.transform.mode === 'ROTATE' && this.state.rotateIncrementDeg > 0) {
            return `mouse / ${this.state.rotateIncrementDeg} deg`;
        }
        return 'mouse';
    }

    commandValueText() {
        if (this.transform.mode === 'ROTATE' && this.state.commensurateSnappedCandidate) {
            return this.state.transformReadout;
        }
        if (this.transform.buffer) {
            const unit = this.transform.mode === 'MOVE' ? 'A' : 'deg';
            return `${this.transform.buffer} ${unit}`;
        }
        return this.state.transformReadout || this.transformMouseLabel();
    }

    updateCommandReadout() {
        const cmdBuf = document.getElementById('cmd-buffer');
        if (!cmdBuf) return;
        const setHtml = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        if (this.transform.mode !== 'IDLE') {
            cmdBuf.classList.remove('hidden');
            const lightHandle = this.state.sunTransformOriginal?.handle || this.state.sunSelected || 'source';
            setHtml(
                'cmd-mode',
                this.state.transformSubject === 'sun'
                    ? `SUN ${lightHandle.toUpperCase()} ${this.transform.mode}`
                    : this.transform.mode
            );
            setHtml('cmd-axis', this.transform.axis || 'NONE');
            setHtml('cmd-val', this.commandValueText());
        } else {
            cmdBuf.classList.add('hidden');
        }
    }

    setAtomsData(data, { clearSelection = false, preserveDisplay = true } = {}) {
        if (preserveDisplay) this.captureBondSettingsFromControls();
        this.state.atoms = data;
        this.rebuildTypeIndexCache(data.symbols || []);
        this.state.cachedFmax = this.computeFmax(data.forces || []);
        this.clearRelaxTrajectoryIfTopologyChanged(data);
        this.reconcileTypeOrder(data.symbols || []);
        this.state.originalPositions = data.positions.map(p => [...p]);
        if (data.trajectory_positions) {
            this.state.trajectoryBinaryCache = null;
            this.state.trajectoryBinaryPromise = null;
        } else if (!data.metadata?.trajectory_positions_binary) {
            this.state.trajectoryBinaryCache = null;
            this.state.trajectoryBinaryPromise = null;
        } else if (!this.state.trajectoryBinaryCache && !this.state.trajectoryBinaryPromise) {
            this.loadTrajectoryCache({ background: true });
        }
        if (clearSelection) {
            this.clearAtomSelection();
        } else {
            this.pruneSelection();
        }
        this.state.display.vizOnly = this.state.vizOnly;
        this.renderElementBondControls();
        this.renderer.setDisplayOptions(this.state.display, { rebuild: false });
        this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
        this.renderElementRadiusControls();
        this.updateEditingAvailability();
        this.setHoveredAtom(null);
        this.updateSelectionVisuals();
        this.updateUI();
        this.updateDocumentAvailability();
    }

    hasLoadedAtoms() {
        return Boolean(this.state.atoms?.positions?.length);
    }

    updateDocumentAvailability() {
        const hasAtoms = this.hasLoadedAtoms();
        document.getElementById('empty-workspace')?.classList.toggle('hidden', hasAtoms);
        document.querySelectorAll('[data-requires-atoms]').forEach(element => {
            if ('disabled' in element) element.disabled = !hasAtoms;
        });
    }

    async loadTrajectoryCache({ background = false } = {}) {
        if (this.state.atoms?.trajectory_positions?.length) return null;
        if (this.state.trajectoryBinaryCache) return this.state.trajectoryBinaryCache;
        if (!this.state.atoms?.metadata?.trajectory_positions_binary) return null;
        if (this.state.trajectoryBinaryPromise) return this.state.trajectoryBinaryPromise;

        const load = async () => {
            const cache = await this.api.fetchTrajectoryPositions();
            const expectedFrames = this.state.atoms?.metadata?.frame_count || 0;
            const expectedAtoms = this.state.atoms?.positions?.length || 0;
            if (cache.frames !== expectedFrames || cache.atoms !== expectedAtoms) {
                throw new Error('Trajectory cache shape does not match the loaded structure.');
            }
            this.state.trajectoryBinaryCache = cache;
            return cache;
        };

        const promise = load().catch(err => {
            if (!background) throw err;
            this.toast(`Trajectory cache failed: ${err.message}`, 'warning');
            return null;
        }).finally(() => {
            this.state.trajectoryBinaryPromise = null;
        });
        this.state.trajectoryBinaryPromise = promise;
        return promise;
    }

    materializeBinaryFrame(cache, frameIndex) {
        const positions = new Array(cache.atoms);
        const offset = frameIndex * cache.atoms * 3;
        for (let i = 0; i < cache.atoms; i++) {
            const base = offset + i * 3;
            positions[i] = [cache.values[base], cache.values[base + 1], cache.values[base + 2]];
        }
        return positions;
    }

    materializeFlatFrame(values, atoms) {
        const positions = new Array(atoms);
        for (let i = 0; i < atoms; i++) {
            const base = i * 3;
            positions[i] = [values[base], values[base + 1], values[base + 2]];
        }
        return positions;
    }

    loadedFrameCount() {
        return this.state.atoms?.metadata?.frame_count || 1;
    }

    relaxFrameCount() {
        return this.state.relaxTrajectory?.frames?.length || 0;
    }

    primaryTimelineSource() {
        if (this.loadedFrameCount() > 1) return 'loaded';
        if (this.relaxFrameCount() > 1) return 'relax';
        return 'loaded';
    }

    timelineFrameCount(source = this.primaryTimelineSource()) {
        return source === 'relax' ? this.relaxFrameCount() : this.loadedFrameCount();
    }

    timelineFrameIndex(source = this.primaryTimelineSource()) {
        if (source === 'relax') return this.state.relaxTrajectory?.frame || 0;
        return this.state.atoms?.metadata?.current_frame || 0;
    }

    startRelaxTrajectory() {
        const meta = this.state.atoms?.metadata || {};
        const sourceFrame = Number.isFinite(Number(meta.current_frame)) ? Number(meta.current_frame) : 0;
        this.state.relaxTrajectory = {
            frames: [],
            frame: 0,
            sourceFrame,
            active: true,
            finished: false
        };
        const positions = this.currentPositionsFromScene?.() || this.state.atoms?.positions || [];
        if (positions.length) this.appendRelaxFrame(positions, { force: true });
        this.updateTrajectoryUI();
    }

    samePositionFrame(a, b) {
        if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
        for (let i = 0; i < a.length; i++) {
            const pa = a[i];
            const pb = b[i];
            if (!pa || !pb) return false;
            for (let axis = 0; axis < 3; axis++) {
                if (Math.abs(Number(pa[axis]) - Number(pb[axis])) > 1e-10) return false;
            }
        }
        return true;
    }

    appendRelaxFrame(positions, { force = false } = {}) {
        if (!Array.isArray(positions) || !positions.length) return;
        const trajectory = this.state.relaxTrajectory;
        if (!trajectory.active && !trajectory.frames.length) {
            trajectory.active = true;
        }
        const frame = positions.map(p => [...p]);
        const last = trajectory.frames[trajectory.frames.length - 1];
        if (!force && last && this.samePositionFrame(last, frame)) return;
        trajectory.frames.push(frame);
        trajectory.frame = trajectory.frames.length - 1;
        this.updateTrajectoryUI();
    }

    relaxOverridePositions(frameIndex) {
        const trajectory = this.state.relaxTrajectory;
        if (!trajectory?.frames?.length) return null;
        if (trajectory.sourceFrame !== frameIndex) return null;
        return trajectory.frames[trajectory.frames.length - 1];
    }

    async loadRelaxFrame(index) {
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        const count = this.relaxFrameCount();
        if (count <= 0) return;
        const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
        const positions = this.state.relaxTrajectory.frames[normalized];
        if (!positions) return;
        this.state.relaxTrajectory.frame = normalized;
        this.state.atoms.positions = positions;
        this.state.originalPositions = this.state.vizOnly ? positions : positions.map(p => [...p]);
        this.renderer.updatePositions(positions);
        this.updateUI();
    }

    clearRelaxTrajectoryIfTopologyChanged(data) {
        const relax = this.state.relaxTrajectory;
        if (!relax?.frames?.length) return;
        const natoms = data?.positions?.length || 0;
        if (relax.frames[0]?.length === natoms) return;
        this.state.relaxTrajectory = {
            frames: [],
            frame: 0,
            sourceFrame: 0,
            active: false,
            finished: false
        };
    }

    pruneSelection() {
        const count = this.state.atoms?.positions?.length || 0;
        this.state.selected.forEach(idx => {
            if (idx < 0 || idx >= count) this.state.selected.delete(idx);
            else if (!this.isAtomVisible(idx)) this.state.selected.delete(idx);
        });
        this.state.replicaSelected.forEach((reference, key) => {
            if (!this.replicaReferenceIsSelectable(reference)) this.state.replicaSelected.delete(key);
        });
    }

    applyInitialDisplayConfig(data) {
        if (this.state.displayConfigLoaded) return;
        const config = data.metadata?.config || {};
        this.state.display.showBonds = Boolean(config.show_bonds);
        this.state.display.showCell = config.show_cell !== false;
        this.state.display.showAxes = config.show_axes !== false;
        this.state.display.showGrid = config.show_grid !== false;
        this.state.display.showOverlays = config.show_overlays !== false;
        this.state.display.showPeriodicBonds = Boolean(config.show_periodic_bonds);
        this.state.display.bondStyle = ['cylinder', 'flat'].includes(config.bond_style)
            ? config.bond_style
            : this.state.display.bondStyle;
        this.state.display.bondThickness = Math.max(0.02, Math.min(0.6,
            Number(config.bond_thickness || this.state.display.bondThickness)));
        this.state.display.bondColorMode = ['split', 'custom'].includes(config.bond_color_mode)
            ? config.bond_color_mode
            : this.state.display.bondColorMode;
        if (/^#[0-9A-Fa-f]{6}$/.test(config.bond_custom_color || '')) {
            this.state.display.bondCustomColor = config.bond_custom_color;
        }
        this.state.applyConstraints = config.apply_constraint !== false;
        this.state.antiAliasing = config.anti_aliasing !== false;
        this.state.sphereQuality = config.sphere_quality || 'auto';
        this.state.display.atomRadiusScale = Number(config.atom_radius_scale || 1.0);
        this.state.display.elementRadii = config.element_radii || {};
        this.state.display.elementColors = config.element_colors || {};
        this.state.display.elementVisible = config.element_visible || {};
        this.state.display.rotatePivot = config.rotate_pivot || this.state.display.rotatePivot;
        this.state.display.commensurateGuide = Boolean(
            config.commensurate_guide ?? config.unit_cell_aware_rotate ?? this.state.display.commensurateGuide
        );
        this.state.display.commensurateSnap = config.commensurate_snap !== false;
        const initialStrainTolerance = Number(config.commensurate_strain_tolerance);
        const initialMaxIndex = parseInt(config.commensurate_max_index, 10);
        const initialSnapRange = Number(config.commensurate_snap_range_deg);
        this.state.display.commensurateStrainTolerance = Number.isFinite(initialStrainTolerance)
            ? Math.max(0, Math.min(0.25, initialStrainTolerance))
            : this.state.display.commensurateStrainTolerance;
        this.state.display.commensurateMaxIndex = Number.isFinite(initialMaxIndex)
            ? Math.max(2, Math.min(64, initialMaxIndex))
            : this.state.display.commensurateMaxIndex;
        this.state.display.commensurateSnapRangeDeg = Number.isFinite(initialSnapRange)
            ? Math.max(0, Math.min(15, initialSnapRange))
            : this.state.display.commensurateSnapRangeDeg;
        this.state.display.projectionMode = config.projection_mode || this.state.display.projectionMode;
        this.state.display.viewportBackground = config.viewport_background === 'white' ? 'white' : 'dark';
        this.state.display.atomDisplayMode = config.atom_display_mode === '2d' ? '2d' : '3d';
        this.state.display.viewRotationStepDeg = this.normalizedViewRotationStep(
            config.view_rotation_step_deg ?? this.state.display.viewRotationStepDeg
        );
        this.state.vizOnly = Boolean(config.viz_only);
        this.state.display.vizOnly = this.state.vizOnly;
        document.getElementById('chk-bonds').checked = this.state.display.showBonds;
        document.getElementById('chk-periodic-bonds').checked = this.state.display.showPeriodicBonds;
        document.getElementById('bond-style').value = this.state.display.bondStyle;
        document.getElementById('bond-thickness').value = this.state.display.bondThickness;
        document.getElementById('bond-color-mode').value = this.state.display.bondColorMode;
        document.getElementById('bond-custom-color').value = this.state.display.bondCustomColor;
        document.getElementById('chk-cell').checked = this.state.display.showCell;
        document.getElementById('chk-axes').checked = this.state.display.showAxes;
        document.getElementById('chk-grid').checked = this.state.display.showGrid;
        document.getElementById('chk-overlays').checked = this.state.display.showOverlays;
        document.getElementById('chk-constraints').checked = this.state.applyConstraints;
        document.getElementById('chk-antialias').checked = this.state.antiAliasing;
        document.getElementById('sphere-quality').value = this.state.sphereQuality;
        const radiusScale = document.getElementById('atom-radius-scale');
        if (radiusScale) radiusScale.value = this.state.display.atomRadiusScale;
        document.getElementById('rotate-pivot').value = this.state.display.rotatePivot;
        document.getElementById('chk-commensurate-guide').checked = this.state.display.commensurateGuide;
        document.getElementById('chk-commensurate-snap').checked = this.state.display.commensurateSnap;
        document.getElementById('commensurate-strain').value = this.state.display.commensurateStrainTolerance * 100;
        document.getElementById('commensurate-max-index').value = this.state.display.commensurateMaxIndex;
        document.getElementById('commensurate-snap-range').value = this.state.display.commensurateSnapRangeDeg;
        const projectionMode = document.getElementById('projection-mode');
        if (projectionMode) projectionMode.value = this.state.display.projectionMode;
        this.syncViewControls();
        this.syncAtomicScaleFromCamera({ forceInput: true, syncPreview: false });
        this.updateRadiusScaleLabel();
        this.syncLightingControls();
        this.updateEditingAvailability();
        this.state.displayConfigLoaded = true;
        if (config.initial_design_settings) {
            this.applyDesignSettings(config.initial_design_settings, { render: false });
        }
    }

    updateTrajectoryUI() {
        const meta = this.state.atoms?.metadata || {};
        const loadedCount = meta.frame_count || 1;
        const relaxCount = this.relaxFrameCount();
        const source = this.primaryTimelineSource();
        const count = this.timelineFrameCount(source);
        const index = this.timelineFrameIndex(source);
        const panel = document.getElementById('trajectory-panel');
        if (panel) {
            panel.classList.toggle('hidden', loadedCount <= 1 && relaxCount <= 1);
            panel.dataset.primarySource = source;
        }
        const sourceLabel = document.getElementById('timeline-source-label');
        if (sourceLabel) {
            sourceLabel.innerText = source === 'relax' ? 'RELAX' : 'LOADED';
            sourceLabel.classList.toggle('relax', source === 'relax');
        }
        const slider = document.getElementById('frame-slider');
        if (slider) {
            slider.max = Math.max(0, count - 1);
            slider.value = index;
            slider.disabled = count <= 1;
        }
        const label = document.getElementById('frame-label');
        if (label) label.innerText = `${Math.min(index + 1, count)} / ${count}`;
        const play = document.getElementById('btn-play');
        if (play) {
            play.innerText = this.state.trajectoryTimer ? '⏸' : '▶';
            play.disabled = count <= 1;
        }
        const prev = document.getElementById('btn-frame-prev');
        const next = document.getElementById('btn-frame-next');
        if (prev) prev.disabled = count <= 1;
        if (next) next.disabled = count <= 1;
        const fps = document.getElementById('movie-fps');
        if (fps) fps.disabled = count <= 1;
        const skip = document.getElementById('movie-skip');
        if (skip) skip.disabled = count <= 1;
        const relaxRow = document.getElementById('relax-trajectory-row');
        const showRelaxRow = loadedCount > 1 && relaxCount > 1;
        if (relaxRow) relaxRow.classList.toggle('hidden', !showRelaxRow);
        const relaxSlider = document.getElementById('relax-frame-slider');
        if (relaxSlider) {
            relaxSlider.max = Math.max(0, relaxCount - 1);
            relaxSlider.value = Math.min(this.state.relaxTrajectory.frame || 0, Math.max(0, relaxCount - 1));
            relaxSlider.disabled = relaxCount <= 1;
        }
        const relaxLabel = document.getElementById('relax-frame-label');
        if (relaxLabel) {
            const relaxIndex = Math.min((this.state.relaxTrajectory.frame || 0) + 1, Math.max(1, relaxCount));
            relaxLabel.innerText = `${relaxIndex} / ${Math.max(1, relaxCount)}`;
        }
        const exportVideo = document.getElementById('btn-export-video');
        if (exportVideo) {
            exportVideo.disabled = loadedCount <= 1;
            exportVideo.title = loadedCount <= 1 ? 'Export Video is available for loaded trajectory files only.' : 'Export the loaded trajectory as a MOV or AVI video.';
        }
    }

    updateSelectionVisuals() {
        this.renderer.setSelection(this.state.selected);
        this.renderer.setReplicaSelection(this.state.vizOnly ? this.state.replicaSelected.values() : []);
    }

    getFixedIndices() {
        return new Set(this.state.atoms?.constraints?.fixed_indices || []);
    }

    vectorAlmostEqual(a, b, tol = 1e-6) {
        return Array.isArray(a) && Array.isArray(b) && a.length === 3 && b.length === 3 &&
            a.every((value, index) => Math.abs(Number(value) - Number(b[index])) <= tol);
    }

    constraintVector(kind, index) {
        const constraints = this.state.atoms?.constraints || {};
        const table = kind === 'fixed_line' ? constraints.fixed_line : constraints.fixed_plane;
        return table?.[index] || table?.[String(index)] || null;
    }

    selectedDirectionalConstraintState(indices = [...this.state.selected]) {
        if (!indices.length) return { kind: 'none', vector: null };
        const states = indices.map(index => {
            const line = this.constraintVector('fixed_line', index);
            const plane = this.constraintVector('fixed_plane', index);
            if (line && plane) return { kind: 'mixed', vector: null };
            if (line) return { kind: 'fixed_line', vector: line };
            if (plane) return { kind: 'fixed_plane', vector: plane };
            return { kind: 'none', vector: null };
        });
        const first = states[0];
        if (states.some(state => state.kind !== first.kind)) return { kind: 'mixed', vector: null };
        if (first.kind === 'none' || first.kind === 'mixed') return { kind: first.kind, vector: null };
        const sameVector = states.every(state => this.vectorAlmostEqual(state.vector, first.vector));
        return { kind: sameVector ? first.kind : 'mixed', vector: sameVector ? first.vector : null };
    }

    selectedFixAtomsState(indices = [...this.state.selected]) {
        if (!indices.length) return 'none';
        const fixed = this.getFixedIndices();
        const count = indices.filter(index => fixed.has(index)).length;
        if (count === 0) return 'none';
        return count === indices.length ? 'all' : 'partial';
    }

    readConstraintVector(kind = document.getElementById('constraint-kind')?.value || 'fixed_line') {
        const ids = ['constraint-x', 'constraint-y', 'constraint-z'];
        const vector = ids.map(id => Number(document.getElementById(id)?.value));
        if (vector.some(value => !Number.isFinite(value))) {
            throw new Error('Constraint vector must contain three numeric values.');
        }
        const length = Math.hypot(vector[0], vector[1], vector[2]);
        if (length <= 1e-12) {
            throw new Error(kind === 'fixed_plane' ? 'FixedPlane normal cannot be zero.' : 'FixedLine direction cannot be zero.');
        }
        return vector.map(value => value / length);
    }

    setConstraintVectorInputs(vector) {
        const fallback = vector || [1, 0, 0];
        ['constraint-x', 'constraint-y', 'constraint-z'].forEach((id, index) => {
            const input = document.getElementById(id);
            if (input) {
                const value = Number(fallback[index] || 0);
                input.value = Number.isFinite(value) ? String(Number(value.toFixed(3))) : '0';
            }
        });
    }

    updateSelectionConstraintControls() {
        if (this.state.vizOnly) return;
        const indices = [...this.state.selected].sort((a, b) => a - b);
        const fixBox = document.getElementById('constraint-fixatoms');
        const kindSelect = document.getElementById('constraint-kind');
        const stateText = document.getElementById('constraint-selection-state');
        const applyButton = document.getElementById('btn-apply-constraint');
        const clearButton = document.getElementById('btn-clear-directional-constraint');
        const inputs = ['constraint-x', 'constraint-y', 'constraint-z']
            .map(id => document.getElementById(id))
            .filter(Boolean);
        if (!fixBox || !kindSelect) return;

        const hasSelection = indices.length > 0;
        const fixedState = this.selectedFixAtomsState(indices);
        fixBox.disabled = !hasSelection || this.state.vizOnly;
        fixBox.checked = fixedState === 'all';
        fixBox.indeterminate = fixedState === 'partial';
        fixBox.dataset.fixAtomsState = fixedState;

        const directional = this.selectedDirectionalConstraintState(indices);
        if (document.activeElement !== kindSelect) {
            kindSelect.value = directional.kind;
        }
        kindSelect.disabled = !hasSelection || this.state.vizOnly;
        if (directional.vector && !inputs.includes(document.activeElement)) {
            this.setConstraintVectorInputs(directional.vector);
        } else if (!hasSelection && !inputs.includes(document.activeElement)) {
            this.setConstraintVectorInputs([1, 0, 0]);
        }
        const vectorEnabled = hasSelection && !this.state.vizOnly && ['fixed_line', 'fixed_plane'].includes(kindSelect.value);
        inputs.forEach(input => { input.disabled = !vectorEnabled; });
        if (applyButton) applyButton.disabled = !vectorEnabled;
        if (clearButton) clearButton.disabled = !hasSelection || this.state.vizOnly || directional.kind === 'none';
        if (stateText) {
            const fixedLabel = fixedState === 'all' ? 'FixAtoms' : fixedState === 'partial' ? 'partial FixAtoms' : 'free';
            const dirLabel = directional.kind === 'fixed_line' ? 'FixedLine'
                : directional.kind === 'fixed_plane' ? 'FixedPlane'
                : directional.kind === 'mixed' ? 'mixed directional constraints'
                : 'no directional constraint';
            stateText.innerText = hasSelection
                ? `${indices.length} selected: ${fixedLabel}, ${dirLabel}.`
                : 'Select atoms to edit constraints.';
        }
    }

    async updateSelectedConstraints(options, message = 'Updating constraints...') {
        const indices = [...this.state.selected].sort((a, b) => a - b);
        if (!indices.length) {
            this.toast('Select atoms before editing constraints.', 'warning');
            return;
        }
        try {
            const data = await this.withBusy(
                message,
                () => this.api.updateConstraints(indices, options, this.backendPositionsPayload(), this.state.applyConstraints)
            );
            this.setAtomsData(data);
            indices.forEach(index => this.state.selected.add(index));
            this.updateSelectionVisuals();
            this.updateUI();
            this.toast('Constraints updated.', 'success');
        } catch (err) {
            this.toast(`Constraint update failed: ${err.message}`, 'error');
        }
    }

    async toggleSelectedFixAtoms() {
        const box = document.getElementById('constraint-fixatoms');
        const current = box?.dataset?.fixAtomsState || this.selectedFixAtomsState();
        const next = current === 'none';
        if (box) {
            box.indeterminate = false;
            box.checked = next;
        }
        await this.updateSelectedConstraints({ fix_atoms: next }, next ? 'Applying FixAtoms...' : 'Clearing FixAtoms...');
    }

    async applySelectedDirectionalConstraint() {
        const kind = document.getElementById('constraint-kind')?.value || 'none';
        if (!['fixed_line', 'fixed_plane'].includes(kind)) {
            this.toast('Choose FixedLine or FixedPlane before applying a directional constraint.', 'warning');
            return;
        }
        let vector;
        try {
            vector = this.readConstraintVector(kind);
        } catch (err) {
            this.toast(err.message, 'error');
            return;
        }
        await this.updateSelectedConstraints(
            { directional_kind: kind, vector },
            kind === 'fixed_line' ? 'Applying FixedLine...' : 'Applying FixedPlane...'
        );
    }

    async clearSelectedDirectionalConstraint() {
        await this.updateSelectedConstraints({ directional_kind: 'none' }, 'Clearing directional constraints...');
    }

    isEditableIndex(idx) {
        if (!this.state.applyConstraints) return true;
        return !this.getFixedIndices().has(idx);
    }

    normalizedConstraintVector(values) {
        if (!values || values.length !== 3) return null;
        const v = new THREE.Vector3(values[0], values[1], values[2]);
        return v.lengthSq() > 1e-12 ? v.normalize() : null;
    }

    constrainedMoveDelta(index, delta) {
        if (!this.state.applyConstraints) return delta.clone();
        const constraints = this.state.atoms?.constraints || {};
        let result = delta.clone();

        const cart = constraints.fixed_cartesian?.[index] || constraints.fixed_cartesian?.[String(index)];
        if (cart) {
            if (cart[0]) result.x = 0;
            if (cart[1]) result.y = 0;
            if (cart[2]) result.z = 0;
        }

        const line = constraints.fixed_line?.[index] || constraints.fixed_line?.[String(index)];
        const lineDir = this.normalizedConstraintVector(line);
        if (lineDir) {
            return lineDir.multiplyScalar(result.dot(lineDir));
        }

        const plane = constraints.fixed_plane?.[index] || constraints.fixed_plane?.[String(index)];
        const normal = this.normalizedConstraintVector(plane);
        if (normal) {
            result.addScaledVector(normal, -result.dot(normal));
        }
        return result;
    }

    currentPositionsFromScene() {
        return this.renderer.currentPositions();
    }

    backendPositionsPayload() {
        return this.state.vizOnly ? null : this.currentPositionsFromScene();
    }

    currentCameraForExport() {
        const camera = this.renderer.camera;
        const controls = this.renderer.controls;
        const canvas = this.renderer.domElement;
        camera.updateMatrixWorld();
        return {
            position: [camera.position.x, camera.position.y, camera.position.z],
            target: [controls.target.x, controls.target.y, controls.target.z],
            up: [camera.up.x, camera.up.y, camera.up.z],
            projection: this.state.display.projectionMode || this.renderer.projectionMode || 'perspective',
            fov: camera.fov || this.renderer.perspectiveCamera?.fov || 50,
            zoom: camera.zoom || 1,
            ortho_scale: camera.isOrthographicCamera ? (camera.top - camera.bottom) / Math.max(camera.zoom || 1, 1e-6) : null,
            near: camera.near,
            far: camera.far,
            aspect: Math.max(1, canvas?.clientWidth || 1) / Math.max(1, canvas?.clientHeight || 1)
        };
    }

    atomicScaleText(value) {
        const scale = Number(value);
        if (!Number.isFinite(scale) || scale <= 0) return '100.00';
        return scale >= 100 ? scale.toFixed(1) : scale.toFixed(2);
    }

    updateAtomicScaleSpan(pixelsPerAngstrom = this.renderer?.currentPixelsPerAngstrom?.()) {
        const note = document.getElementById('atomic-scale-span');
        if (!note) return;
        const scale = Number(pixelsPerAngstrom);
        const canvas = this.renderer?.domElement;
        if (!Number.isFinite(scale) || scale <= 0 || !canvas) {
            note.textContent = 'Viewport span: -- Å × -- Å';
            return;
        }
        const width = Math.max(1, canvas.clientWidth || this.renderer.container?.clientWidth || 1) / scale;
        const height = Math.max(1, canvas.clientHeight || this.renderer.container?.clientHeight || 1) / scale;
        note.textContent = `Viewport span: ${width.toFixed(2)} Å × ${height.toFixed(2)} Å`;
    }

    syncAtomicScaleFromCamera({ forceInput = false, syncPreview = true } = {}) {
        if (!this.state?.display || !this.renderer?.camera) return null;
        const measured = Number(this.renderer.currentPixelsPerAngstrom());
        if (!Number.isFinite(measured) || measured <= 0) return null;
        const scale = Number(measured.toFixed(4));
        const previous = Number(this.state.display.atomicScalePixelsPerAngstrom);
        const changed = !Number.isFinite(previous) || Math.abs(previous - scale) > 1e-4;
        this.state.display.atomicScalePixelsPerAngstrom = scale;
        const input = document.getElementById('atomic-scale');
        if (input && (forceInput || document.activeElement !== input)) {
            input.value = this.atomicScaleText(scale);
        }
        this.updateAtomicScaleSpan(scale);
        if (changed && syncPreview && this.state.exportPreviewEnabled) {
            this.syncImageExportPreview();
        }
        return scale;
    }

    applyAtomicScaleFromControl({ normalize = false } = {}) {
        const input = document.getElementById('atomic-scale');
        if (!input) return;
        const requested = Number(input.value);
        if (!Number.isFinite(requested) || requested <= 0) return;
        const clamped = Math.max(0.1, Math.min(5000, requested));
        const applied = this.renderer.setPixelsPerAngstrom(clamped, { source: 'scale-input' });
        this.state.display.atomicScalePixelsPerAngstrom = Number(applied.toFixed(4));
        if (normalize) input.value = this.atomicScaleText(applied);
        this.updateAtomicScaleSpan(applied);
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
    }

    currentLightingForExport() {
        const display = this.state.display || {};
        return {
            mode: display.lightingMode || 'modeling',
            intensity: Number(display.sunIntensity ?? 2.2),
            position: [...(display.sunPosition || [8, -10, 14])],
            target: [...(display.sunTarget || [0, 0, 0])],
            color: [1.0, 0.960784, 0.87451]
        };
    }

    isReplicaReference(reference) {
        return Boolean(
            reference &&
            typeof reference === 'object' &&
            reference.kind === 'replica' &&
            Number.isInteger(reference.index) &&
            Array.isArray(reference.cellOffset) &&
            reference.cellOffset.length === 3
        );
    }

    normalizeSelectionReference(reference) {
        if (reference === null || reference === undefined) return null;
        if (this.isReplicaReference(reference)) {
            const cellOffset = reference.cellOffset.map(value => Number(value));
            if (!cellOffset.every(Number.isInteger)) return null;
            return {
                kind: 'replica',
                index: reference.index,
                cellOffset,
                key: this.renderer.supercellReferenceKey(reference.index, cellOffset)
            };
        }
        if (reference && typeof reference === 'object' && reference.kind === 'atom') {
            return Number.isInteger(reference.index)
                ? { kind: 'atom', index: reference.index, key: `atom:${reference.index}` }
                : null;
        }
        const index = Number(reference);
        if (!Number.isInteger(index)) return null;
        return { kind: 'atom', index, key: `atom:${index}` };
    }

    selectionReferenceKey(reference) {
        return this.normalizeSelectionReference(reference)?.key || null;
    }

    selectionEntries() {
        const available = new Map();
        this.state.selected.forEach(index => {
            const reference = this.normalizeSelectionReference(index);
            if (reference) available.set(reference.key, reference);
        });
        if (this.state.vizOnly) {
            this.state.replicaSelected.forEach((reference, key) => available.set(key, reference));
        }
        const entries = [];
        this.state.selectionOrder.forEach(key => {
            const reference = available.get(key);
            if (!reference) return;
            entries.push(reference);
            available.delete(key);
        });
        available.forEach(reference => entries.push(reference));
        this.state.selectionOrder = entries.map(reference => reference.key);
        return entries;
    }

    selectionCount() {
        return this.state.selected.size + (this.state.vizOnly ? this.state.replicaSelected.size : 0);
    }

    clearAtomSelection() {
        this.state.selected.clear();
        this.state.replicaSelected.clear();
        this.state.selectionOrder = [];
    }

    replicaReferenceIsSelectable(reference) {
        if (!this.state.vizOnly || !this.isReplicaReference(reference)) return false;
        const count = this.state.atoms?.positions?.length || 0;
        if (reference.index < 0 || reference.index >= count || !this.isAtomVisible(reference.index)) return false;
        const reps = this.state.display.supercell || [1, 1, 1];
        const offset = reference.cellOffset.map(Number);
        return offset.every((value, axis) => Number.isInteger(value) && value >= 0 && value < (reps[axis] || 1)) &&
            offset.some(value => value !== 0);
    }

    hasSelectionReference(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized) return false;
        if (normalized.kind === 'replica') return this.state.replicaSelected.has(normalized.key);
        return this.state.selected.has(normalized.index);
    }

    addSelectionReference(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized || !this.isAtomVisible(normalized.index)) return false;
        const alreadySelected = this.hasSelectionReference(normalized);
        if (normalized.kind === 'replica') {
            if (!this.replicaReferenceIsSelectable(normalized)) return false;
            this.state.replicaSelected.set(normalized.key, normalized);
        } else {
            this.state.selected.add(normalized.index);
        }
        if (!alreadySelected) this.state.selectionOrder.push(normalized.key);
        return true;
    }

    removeSelectionReference(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized) return;
        if (normalized.kind === 'replica') this.state.replicaSelected.delete(normalized.key);
        else this.state.selected.delete(normalized.index);
        this.state.selectionOrder = this.state.selectionOrder.filter(key => key !== normalized.key);
    }

    toggleSelectionReference(reference) {
        if (this.hasSelectionReference(reference)) this.removeSelectionReference(reference);
        else this.addSelectionReference(reference);
    }

    selectionReferencePosition(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized) return null;
        if (normalized.kind === 'replica') {
            const position = this.renderer.replicaSelectionPosition(normalized);
            return position?.clone?.() || null;
        }
        const position = this.currentAtomPosition(normalized.index);
        return position ? new THREE.Vector3(...position) : null;
    }

    selectionReferenceLabel(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized) return '-';
        return normalized.kind === 'replica'
            ? `${normalized.index}@[${normalized.cellOffset.join(',')}]`
            : String(normalized.index);
    }

    selectionReferenceSymbol(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        return normalized ? (this.state.atoms?.symbols?.[normalized.index] || '-') : '-';
    }

    getSelectionCenterText() {
        const selected = this.selectionEntries();
        if (!this.state.atoms || selected.length === 0) return '-';
        const center = [0, 0, 0];
        let count = 0;
        selected.forEach(reference => {
            const p = this.selectionReferencePosition(reference);
            if (!p) return;
            center[0] += p.x; center[1] += p.y; center[2] += p.z;
            count++;
        });
        if (!count) return '-';
        const cart = center.map(v => v / count);
        const cartText = cart.map(v => v.toFixed(3)).join(', ');
        if (!this.renderer?.hasValidCell?.()) return `${cartText} A`;
        const frac = this.renderer.cartToFrac(new THREE.Vector3(cart[0], cart[1], cart[2]));
        const fracText = [frac.x, frac.y, frac.z].map(v => v.toFixed(4)).join(', ');
        return `${cartText} A\n(frac ${fracText})`;
    }

    selectionDelta(first, second) {
        const a = this.normalizeSelectionReference(first);
        const b = this.normalizeSelectionReference(second);
        if (!a || !b) return null;
        if (a.kind === 'atom' && b.kind === 'atom') {
            const start = this.renderer.getAtomPosition?.(a.index);
            if (start && this.renderer.minimumImageDelta) {
                return this.renderer.minimumImageDelta(a.index, b.index, start);
            }
        }
        const pi = this.selectionReferencePosition(a);
        const pj = this.selectionReferencePosition(b);
        if (!pi || !pj) return null;
        return pj.clone().sub(pi);
    }

    selectionDistance(i, j) {
        const delta = this.selectionDelta(i, j);
        return delta ? delta.length() : NaN;
    }

    selectionAngle(i, j, k) {
        const ji = this.selectionDelta(j, i);
        const jk = this.selectionDelta(j, k);
        if (!ji || !jk || ji.lengthSq() < 1e-12 || jk.lengthSq() < 1e-12) return NaN;
        return THREE.MathUtils.radToDeg(ji.angleTo(jk));
    }

    getSelectionMeasureText(selectedReferences = this.selectionEntries()) {
        if (!this.state.atoms || selectedReferences.length === 0) return '-';
        if (selectedReferences.length === 1) return '1 atom selected';
        if (selectedReferences.length === 2) {
            const [i, j] = selectedReferences;
            const distance = this.selectionDistance(i, j);
            return Number.isFinite(distance)
                ? `d(${this.selectionReferenceLabel(i)}-${this.selectionReferenceLabel(j)}) = ${this.formatNumber(distance, 4)} A`
                : '-';
        }
        if (selectedReferences.length === 3) {
            const [i, j, k] = selectedReferences;
            const left = this.selectionDistance(i, j);
            const right = this.selectionDistance(j, k);
            const angle = this.selectionAngle(i, j, k);
            if (![left, right, angle].every(Number.isFinite)) return '-';
            const labels = [i, j, k].map(reference => this.selectionReferenceLabel(reference));
            return `d(${labels[0]}-${labels[1]}) = ${this.formatNumber(left, 4)} A | d(${labels[1]}-${labels[2]}) = ${this.formatNumber(right, 4)} A | angle(${labels.join('-')}) = ${this.formatNumber(angle, 2)} deg`;
        }
        return `${selectedReferences.length} atoms selected`;
    }

    getSelectionMeasureSummary(selectedReferences = this.selectionEntries()) {
        if (!this.state.atoms || selectedReferences.length === 0) return '-';
        if (selectedReferences.length === 1) return '1 atom selected';
        if (selectedReferences.length === 2) {
            const distance = this.selectionDistance(selectedReferences[0], selectedReferences[1]);
            return Number.isFinite(distance)
                ? `Distance ${this.formatNumber(distance, 4)} A`
                : 'Distance unavailable';
        }
        if (selectedReferences.length === 3) {
            const [i, j, k] = selectedReferences;
            const left = this.selectionDistance(i, j);
            const right = this.selectionDistance(j, k);
            const angle = this.selectionAngle(i, j, k);
            if (![left, right, angle].every(Number.isFinite)) return 'Angle unavailable';
            return `Angle ${this.formatNumber(angle, 2)} deg | D1 ${this.formatNumber(left, 4)} A | D2 ${this.formatNumber(right, 4)} A`;
        }
        return `${selectedReferences.length} atoms selected`;
    }

    worldToScreen(vec) {
        const projected = vec.clone().project(this.renderer.camera);
        return new THREE.Vector2(
            (projected.x + 1) * window.innerWidth / 2,
            (-projected.y + 1) * window.innerHeight / 2
        );
    }

    showMarquee(left, top, width, height) {
        const marquee = document.getElementById('marquee');
        if (!marquee) return;
        marquee.classList.remove('hidden');
        marquee.style.left = `${left}px`;
        marquee.style.top = `${top}px`;
        marquee.style.width = `${width}px`;
        marquee.style.height = `${height}px`;
    }

    hideMarquee() {
        const marquee = document.getElementById('marquee');
        if (!marquee) return;
        marquee.classList.add('hidden');
        marquee.style.left = '0px';
        marquee.style.top = '0px';
        marquee.style.width = '0px';
        marquee.style.height = '0px';
    }

    alignViewToAxis(axis) {
        const axisVectors = {
            X: new THREE.Vector3(1, 0, 0),
            Y: new THREE.Vector3(0, 1, 0),
            Z: new THREE.Vector3(0, 0, 1)
        };
        const baseDir = axisVectors[axis];
        if (!baseDir) return 1;
        const camera = this.renderer.camera;
        const controls = this.renderer.controls;
        const target = controls.target.clone();
        const distance = Math.max(camera.position.distanceTo(target), 4.0);
        const viewDir = new THREE.Vector3().subVectors(camera.position, target);
        const currentSign = viewDir.lengthSq() > 1e-12
            ? Math.sign(viewDir.normalize().dot(baseDir))
            : 0;
        const perfectlyAligned = Math.abs(viewDir.dot(baseDir)) > 0.99995;
        const sign = perfectlyAligned && currentSign > 0 ? -1 : 1;
        const dir = baseDir.clone().multiplyScalar(sign);
        camera.up.copy(axis === 'Z' ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1));
        camera.position.copy(target).add(dir.clone().multiplyScalar(distance));
        camera.lookAt(target);
        controls.target.copy(target);
        controls.endGesture?.();
        controls.update?.();
        this.renderer.syncSelectionOutlines();
        this.transform.updateGuides(camera);
        this.updateOrientationWidget();
        this.renderer.requestRender();
        return sign;
    }

    ensureOrientationWidget() {
        const posGroup = document.getElementById('ow-pos-group');
        const negGroup = document.getElementById('ow-neg-group');
        const lineGroup = document.getElementById('ow-line-group');
        if (!posGroup || !negGroup || !lineGroup || posGroup.dataset.ready === 'true') return Boolean(posGroup);
        const axes = [
            { id: 'x', label: 'X', color: getComputedStyle(document.documentElement).getPropertyValue('--axis-x').trim() || '#f05b55' },
            { id: 'y', label: 'Y', color: getComputedStyle(document.documentElement).getPropertyValue('--axis-y').trim() || '#69b942' },
            { id: 'z', label: 'Z', color: getComputedStyle(document.documentElement).getPropertyValue('--axis-z').trim() || '#408cd5' }
        ];
        axes.forEach(axis => {
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.id = `ow-line-${axis.id}`;
            line.classList.add('orientation-line');
            line.setAttribute('stroke', axis.color);
            line.setAttribute('x1', '0');
            line.setAttribute('y1', '0');
            lineGroup.appendChild(line);

            const neg = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            neg.id = `ow-neg-${axis.id}`;
            neg.classList.add('orientation-dot', 'negative');
            neg.setAttribute('stroke', axis.color);
            neg.setAttribute('r', '9');
            negGroup.appendChild(neg);

            const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            dot.id = `ow-pos-${axis.id}`;
            dot.classList.add('orientation-dot', 'positive');
            dot.setAttribute('fill', axis.color);
            dot.setAttribute('r', '14');
            posGroup.appendChild(dot);

            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.id = `ow-label-${axis.id}`;
            text.classList.add('orientation-label');
            text.textContent = axis.label;
            posGroup.appendChild(text);
        });
        posGroup.dataset.ready = 'true';
        return true;
    }

    updateOrientationWidget() {
        if (!this.ensureOrientationWidget()) return;
        const camera = this.renderer?.camera;
        if (!camera) return;
        camera.updateMatrixWorld();
        const q = camera.quaternion;
        const signature = `${q.x.toFixed(6)}:${q.y.toFixed(6)}:${q.z.toFixed(6)}:${q.w.toFixed(6)}`;
        if (signature === this.state.orientationSignature) return;
        this.state.orientationSignature = signature;
        const inverse = camera.quaternion.clone().invert();
        const axes = {
            x: new THREE.Vector3(1, 0, 0),
            y: new THREE.Vector3(0, 1, 0),
            z: new THREE.Vector3(0, 0, 1)
        };
        Object.entries(axes).forEach(([id, world]) => {
            const positive = world.clone().applyQuaternion(inverse);
            const negative = world.clone().multiplyScalar(-1).applyQuaternion(inverse);
            const positiveScale = 39;
            const negativeScale = 33;
            const px = positive.x * positiveScale;
            const py = -positive.y * positiveScale;
            const nx = negative.x * negativeScale;
            const ny = -negative.y * negativeScale;
            const front = THREE.MathUtils.clamp(0.58 + positive.z * 0.32, 0.28, 0.95);

            const line = document.getElementById(`ow-line-${id}`);
            if (line) {
                line.setAttribute('x2', px.toFixed(2));
                line.setAttribute('y2', py.toFixed(2));
                line.style.opacity = String(front);
            }
            const dot = document.getElementById(`ow-pos-${id}`);
            if (dot) {
                dot.setAttribute('cx', px.toFixed(2));
                dot.setAttribute('cy', py.toFixed(2));
                dot.setAttribute('r', (13.2 + positive.z * 1.8).toFixed(2));
                dot.style.opacity = String(THREE.MathUtils.clamp(0.72 + positive.z * 0.24, 0.46, 1));
            }
            const label = document.getElementById(`ow-label-${id}`);
            if (label) {
                label.setAttribute('x', px.toFixed(2));
                label.setAttribute('y', py.toFixed(2));
                label.style.opacity = dot?.style.opacity || '1';
            }
            const neg = document.getElementById(`ow-neg-${id}`);
            if (neg) {
                neg.setAttribute('cx', nx.toFixed(2));
                neg.setAttribute('cy', ny.toFixed(2));
                neg.setAttribute('r', (8.0 + negative.z * 1.1).toFixed(2));
                neg.style.opacity = String(THREE.MathUtils.clamp(0.32 + negative.z * 0.26, 0.18, 0.64));
            }
        });
    }

    currentAtomPosition(index) {
        const mesh = this.renderer.atomMeshByIndex.get(index);
        if (mesh) return [mesh.position.x, mesh.position.y, mesh.position.z];
        return this.state.atoms?.positions?.[index] || null;
    }

    atomHoverText(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized || !this.state.atoms?.symbols?.[normalized.index]) {
            return 'Hover atom: -';
        }
        const index = normalized.index;
        const symbol = this.state.atoms.symbols[index];
        const position = this.selectionReferencePosition(normalized);
        const pos = position ? position.toArray() : null;
        const force = this.state.atoms.forces?.[index] || null;
        const charge = this.state.atoms.charges?.[index];
        const tag = this.state.atoms.tags?.[index];
        const magmom = this.state.atoms.magmoms?.[index];
        const parts = [
            `#${this.selectionReferenceLabel(normalized)} ${symbol}`,
            `pos=${this.formatVectorTuple(pos)}`,
            `force=${this.formatVectorTuple(force)}`,
            `charge=${this.formatNumber(Number(charge), 4)}`,
            `tag=${tag ?? '-'}`,
            `magmom=${this.formatNumber(Number(magmom), 4)}`
        ];
        return parts.join('  |  ');
    }

    setHoveredAtom(reference) {
        const normalized = reference === null || reference === undefined
            ? null
            : this.normalizeSelectionReference(reference);
        this.state.hoveredReference = normalized;
        this.state.hoveredIndex = normalized?.index ?? null;
        const readout = document.getElementById('hover-readout');
        if (readout) readout.innerText = this.atomHoverText(normalized);
    }

    queueHoverPick(event) {
        this.state.hoverPointer = { clientX: event.clientX, clientY: event.clientY };
        if (this.state.hoverPickTimer !== null) return;
        this.state.hoverPickTimer = window.setTimeout(() => {
            this.state.hoverPickTimer = null;
            const pointer = this.state.hoverPointer;
            if (!pointer || this.transform.mode !== 'IDLE' || this.state.isDragging) {
                this.setHoveredAtom(null);
                return;
            }
            this.setHoveredAtom(this.selection.pickHover(
                pointer,
                this.renderer.atomMeshes,
                this.renderer.supercellGroup
            ));
        }, 32);
    }

    pointerAngleAroundPivot(pointer) {
        return Math.atan2(pointer.y - this.state.rotationScreenPivot.y, pointer.x - this.state.rotationScreenPivot.x);
    }

    updateRotationFromPointer(clientX, clientY) {
        const pointer = new THREE.Vector2(clientX, clientY);
        if (pointer.distanceTo(this.state.rotationScreenPivot) < 12) return;
        const angle = this.pointerAngleAroundPivot(pointer);
        if (!this.state.rotationPointerActive) {
            this.state.rotationLastAngle = angle;
            this.state.rotationPointerActive = true;
            return;
        }
        let delta = angle - this.state.rotationLastAngle;
        while (delta > Math.PI) delta -= Math.PI * 2;
        while (delta < -Math.PI) delta += Math.PI * 2;
        // Screen Y grows downward, so invert the pointer angle delta to make
        // clockwise mouse motion produce clockwise viewport rotation.
        this.transform.rotationAngle -= delta;
        this.state.rotationLastAngle = angle;
    }

    sunTransformMoveDelta() {
        const numVal = this.transform.getNumericValue();
        const axisVec = new THREE.Vector3();
        if (this.transform.axis === 'X') axisVec.set(1, 0, 0);
        else if (this.transform.axis === 'Y') axisVec.set(0, 1, 0);
        else if (this.transform.axis === 'Z') axisVec.set(0, 0, 1);

        const camera = this.renderer.camera;
        camera.updateMatrixWorld();
        const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
        const distance = Math.max(this.transform.pivot.distanceTo(camera.position), 1e-6);
        const zoom = Math.max(camera.zoom || 1, 1e-6);
        const height = camera.isOrthographicCamera
            ? (camera.top - camera.bottom) / zoom
            : 2 * Math.tan((camera.fov || 50) * Math.PI / 360) * distance;
        const width = camera.isOrthographicCamera
            ? (camera.right - camera.left) / zoom
            : height * (camera.aspect || this.renderer.viewportAspect?.() || 1);

        const delta = new THREE.Vector3();
        if (numVal !== null && this.transform.axis) {
            delta.copy(axisVec).multiplyScalar(numVal);
        } else if (numVal === null && this.transform.axis) {
            const screen = right.clone().multiplyScalar(this.transform.pointerDelta.x * width)
                .add(up.clone().multiplyScalar(this.transform.pointerDelta.y * height));
            delta.copy(axisVec).multiplyScalar(screen.dot(axisVec));
        } else if (numVal === null) {
            delta.copy(right).multiplyScalar(this.transform.pointerDelta.x * width)
                .add(up.multiplyScalar(this.transform.pointerDelta.y * height));
        }
        return numVal === null ? this.snapMoveDelta(delta, this.transform.axis ? axisVec : null) : delta;
    }

    sunTransformRotation() {
        const numeric = this.transform.getNumericValue();
        let angle = numeric === null
            ? -this.snapRotationAngle(this.transform.rotationAngle)
            : THREE.MathUtils.degToRad(numeric);
        if (!Number.isFinite(angle)) angle = 0;

        const axis = new THREE.Vector3();
        if (this.transform.axis === 'X') axis.set(1, 0, 0);
        else if (this.transform.axis === 'Y') axis.set(0, 1, 0);
        else if (this.transform.axis === 'Z') axis.set(0, 0, 1);
        else this.renderer.camera.getWorldDirection(axis).normalize();
        return {
            angle,
            quaternion: new THREE.Quaternion().setFromAxisAngle(axis, angle)
        };
    }

    applySunTransformPreview() {
        const original = this.state.sunTransformOriginal;
        if (!original || this.transform.mode === 'IDLE') return;
        const handle = original.handle === 'target' ? 'target' : 'source';
        const originalPosition = new THREE.Vector3(...original.position);
        const originalTarget = new THREE.Vector3(...original.target);
        let position = originalPosition.clone();
        let target = originalTarget.clone();

        if (this.transform.mode === 'MOVE') {
            const delta = this.sunTransformMoveDelta();
            if (handle === 'target') target.add(delta);
            else {
                position.add(delta);
                target.add(delta);
            }
            this.state.transformReadout = this.formatMoveReadout(delta);
        } else if (this.transform.mode === 'ROTATE') {
            const { angle, quaternion } = this.sunTransformRotation();
            let targetOffset = originalTarget.clone().sub(originalPosition);
            if (targetOffset.lengthSq() <= 1e-12) targetOffset.set(0, 0, -10);
            targetOffset.applyQuaternion(quaternion);
            target.copy(position).add(targetOffset);
            this.state.transformReadout = this.formatRotateReadout(angle);
        }

        this.state.display.sunPosition = position.toArray();
        this.state.display.sunTarget = target.toArray();
        this.renderer.updateSunTransform(this.state.display.sunPosition, this.state.display.sunTarget, { notify: false });
        this.transform.updateGuides(this.renderer.camera);
        this.syncLightingControls();
        this.updateCommandReadout();
    }

    applyTransformPreview() {
        if (this.transform.mode === 'IDLE') return;
        if (this.state.transformSubject === 'sun') {
            this.applySunTransformPreview();
            return;
        }

        const numVal = this.transform.getNumericValue();
        const hasNum = numVal !== null;
        
        const axisVec = new THREE.Vector3();
        if (this.transform.axis === 'X') axisVec.set(1, 0, 0);
        else if (this.transform.axis === 'Y') axisVec.set(0, 1, 0);
        else if (this.transform.axis === 'Z') axisVec.set(0, 0, 1);

        const camera = this.renderer.camera;
        camera.updateMatrixWorld();
        
        // For free move
        const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
        const up = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
        const viewAxis = new THREE.Vector3();
        camera.getWorldDirection(viewAxis).normalize();
        const dist = Math.max(this.transform.pivot.distanceTo(camera.position), 1e-6);
        
        const zoom = Math.max(camera.zoom || 1, 1e-6);
        const heightPlane = camera.isOrthographicCamera
            ? (camera.top - camera.bottom) / zoom
            : 2 * Math.tan((camera.fov || 50) * Math.PI / 360) * dist;
        const widthPlane = camera.isOrthographicCamera
            ? (camera.right - camera.left) / zoom
            : heightPlane * (camera.aspect || this.renderer.viewportAspect?.() || 1);
        
        const moveDelta = new THREE.Vector3();
        if (this.transform.mode === 'MOVE') {
            if (hasNum && this.transform.axis) {
                moveDelta.copy(axisVec).multiplyScalar(numVal);
            } else if (!hasNum) {
                if (this.transform.axis) {
                    // Project mouse delta to axis
                    const screenDeltaX = this.transform.pointerDelta.x * widthPlane;
                    const screenDeltaY = this.transform.pointerDelta.y * heightPlane;
                    const screenVec = new THREE.Vector3().copy(right).multiplyScalar(screenDeltaX).add(up.multiplyScalar(screenDeltaY));
                    const proj = screenVec.dot(axisVec);
                    moveDelta.copy(axisVec).multiplyScalar(proj);
                } else {
                    // Free view-plane move
                    moveDelta.copy(right).multiplyScalar(this.transform.pointerDelta.x * widthPlane)
                             .add(up.multiplyScalar(this.transform.pointerDelta.y * heightPlane));
                }
            }
            if (!hasNum) {
                moveDelta.copy(this.snapMoveDelta(moveDelta, this.transform.axis ? axisVec : null));
            }
            this.state.transformReadout = this.formatMoveReadout(moveDelta);
        }
        
        const q = new THREE.Quaternion();
        let appliedRotationAngle = 0;
        if (this.transform.mode === 'ROTATE') {
            let angle = 0;
            if (hasNum) {
                angle = THREE.MathUtils.degToRad(numVal);
            } else {
                angle = this.transform.rotationAngle;
            }
            if (!hasNum) angle = this.snapRotationAngle(angle);
            angle = this.snapCommensurateAngle(angle);
            if (!Number.isFinite(angle)) angle = 0;
            appliedRotationAngle = angle;
            const snapped = this.state.commensurateSnappedCandidate;
            this.state.transformReadout = snapped
                ? `${this.formatRotateReadout(angle)} | MATCH e=${(snapped.strain * 100).toFixed(3)}% | N=${snapped.area}`
                : this.formatRotateReadout(angle);
            this.updateCommensurateAngleStatus(angle);
            
            if (this.transform.axis) {
                q.setFromAxisAngle(axisVec, angle);
            } else {
                // camera.getWorldDirection() points away from the viewer.  A
                // screen-space rotation must use the opposite axis so free R
                // follows the same visible direction as axis-locked rotation.
                q.setFromAxisAngle(viewAxis, -angle);
            }
        }

        const changed = [];
        this.renderer.forEachAtomProxy((mesh, idx) => {
            if (this.state.selected.has(idx) && this.isEditableIndex(idx)) {
                const orig = this.state.originalPositions[idx];
                if (!orig || orig.some(v => !Number.isFinite(v))) return;
                const origVec = new THREE.Vector3(...orig);
                
                if (this.transform.mode === 'MOVE') {
                    mesh.position.copy(origVec).add(this.constrainedMoveDelta(idx, moveDelta));
                } else if (this.transform.mode === 'ROTATE') {
                    const offset = origVec.clone().sub(this.transform.pivot);
                    offset.applyQuaternion(q);
                    const rotatedTarget = this.transform.pivot.clone().add(offset);
                    const constrainedDelta = this.constrainedMoveDelta(idx, rotatedTarget.sub(origVec));
                    mesh.position.copy(origVec).add(constrainedDelta);
                }
                if (![mesh.position.x, mesh.position.y, mesh.position.z].every(Number.isFinite)) {
                    mesh.position.copy(origVec);
                }
                changed.push(idx);
            }
        });
        this.renderer.flushAtomInstances(changed);
        this.renderer.syncSelectionOutlines();
        this.renderer.refreshBondsForCurrentPositions();
        this.renderer.updateSupercellPositions();
        this.renderer.updateHookeanPositions();
        this.updateSelectionMeasureUI();
        if (this.transform.mode === 'ROTATE') {
            this.renderCommensurateRotationGuides(appliedRotationAngle);
        }
        
        // Async backend projection is only needed for translation. Rotation
        // already projects each atom's displacement through the same local
        // line/plane/fixed constraints before commit.
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        if (this.transform.mode === 'MOVE') {
            this.constraintTimeout = setTimeout(() => this.previewConstraints(), 50);
        }
        this.updateCommandReadout();
        this.renderer.requestRender();
    }
    
    async previewConstraints() {
        if (!this.state.applyConstraints) return;
        if (this.state.transformSubject !== 'atoms') return;
        if (this.transform.mode !== 'MOVE' || this.state.selected.size === 0) return;
        const newPositions = this.currentPositionsFromScene();
        try {
            const data = await this.api.getConstrainedPositions(newPositions, this.state.applyConstraints);
            if (data.positions && this.transform.mode !== 'IDLE') {
                const changed = [];
                this.renderer.forEachAtomProxy((mesh, index) => {
                    if (this.state.selected.has(index)) {
                        const p = data.positions[index];
                        if (p && p.every(Number.isFinite)) mesh.position.set(p[0], p[1], p[2]);
                        changed.push(index);
                    }
                });
                this.renderer.flushAtomInstances(changed);
                this.renderer.syncSelectionOutlines();
                this.renderer.refreshBondsForCurrentPositions();
                this.renderer.updateSupercellPositions();
                this.renderer.updateHookeanPositions();
                this.updateSelectionMeasureUI();
                this.renderer.requestRender();
            }
        } catch (err) {
            console.error("Constraint preview error:", err);
        }
    }

    commitTransform() {
        if (this.state.transformSubject === 'sun') return this.commitSunTransform();
        if (this.transform.mode === 'IDLE' || this.state.selected.size === 0) return;
        if (!this.canEditAtoms()) {
            this.cancelTransform();
            this.editOnlyToast();
            return;
        }
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        const newPositions = this.currentPositionsFromScene();
        this.state.atoms.positions = newPositions.map(p => [...p]);
        this.state.originalPositions = newPositions.map(p => [...p]);
        this.state.transformReadout = '';
        this.clearCommensurateRotation({ keepStatus: true });

        // Confirm immediately in the viewport. Backend apply follows asynchronously
        // and may correct constrained positions authoritatively.
        this.transform.exit();
        this.state.transformSubject = null;
        this.renderer.controls.enabled = true;
        this.updateToolState();
        this.updateSelectionVisuals();
        this.updateUI();

        this.pendingApply = this.api.applyPositions(newPositions, this.state.applyConstraints).then(data => {
            this.setAtomsData(data);
            return data;
        }).catch(err => {
            this.toast(`Apply failed: ${err.message}`, 'error');
            throw err;
        });
        return this.pendingApply;
    }

    enterTransformMode(mode) {
        if (this.state.sunSelected) {
            this.enterSunTransformMode(mode);
            return;
        }
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const editableSelection = [...this.state.selected].filter(idx => this.isEditableIndex(idx));
        if (editableSelection.length === 0) return;

        this.state.originalPositions = this.currentPositionsFromScene().map(p => [...p]);
        this.readTransformSettings();
        this.safeApplyDisplayOptions();
        const pivot = this.rotationPivotPosition(editableSelection);
        this.state.transformReadout = '';
        this.state.transformStartPointer.copy(this.state.lastPointer);
        this.state.rotationScreenPivot.copy(this.worldToScreen(pivot));
        this.state.rotationLastAngle = 0;
        this.state.rotationPointerActive = false;
        this.state.transformSubject = 'atoms';
        this.transform.enter(mode, pivot, this.renderer.camera);
        this.prepareCommensurateRotation(editableSelection);
        this.renderer.controls.enabled = false;
        this.updateToolState();
        this.updateUI();
    }

    cancelTransform() {
        if (this.state.transformSubject === 'sun') {
            this.cancelSunTransform();
            return;
        }
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        this.renderer.updatePositions(this.state.originalPositions);
        this.state.transformReadout = '';
        this.clearCommensurateRotation({ keepStatus: true });
        this.transform.exit();
        this.state.transformSubject = null;
        this.renderer.controls.enabled = true;
        this.updateToolState();
        this.updateUI();
    }

    enterSunTransformMode(mode) {
        if (!this.state.sunSelected || !this.sunIsSelectable()) return;
        this.readTransformSettings();
        const position = [...(this.state.display.sunPosition || [8, -10, 14])];
        const target = [...(this.state.display.sunTarget || [0, 0, 0])];
        const handle = this.state.sunSelected === 'target' ? 'target' : 'source';
        const pivotValues = mode === 'ROTATE' || handle === 'source' ? position : target;
        const pivot = new THREE.Vector3(...pivotValues);
        this.state.sunTransformOriginal = { position, target, handle };
        this.state.transformSubject = 'sun';
        this.state.transformReadout = '';
        this.state.transformStartPointer.copy(this.state.lastPointer);
        this.state.rotationScreenPivot.copy(this.worldToScreen(pivot));
        this.state.rotationLastAngle = 0;
        this.state.rotationPointerActive = false;
        this.transform.enter(mode, pivot, this.renderer.camera);
        this.renderer.controls.enabled = false;
        this.updateToolState();
        this.updateUI();
    }

    commitSunTransform() {
        if (this.transform.mode === 'IDLE') return;
        this.state.sunTransformOriginal = null;
        this.state.transformReadout = '';
        this.transform.exit();
        this.state.transformSubject = null;
        this.renderer.controls.enabled = true;
        this.renderer.setSunGizmoSelected(this.state.sunSelected);
        this.syncLightingControls();
        this.updateToolState();
        this.updateUI();
    }

    cancelSunTransform() {
        const original = this.state.sunTransformOriginal;
        if (original) {
            this.state.display.sunPosition = [...original.position];
            this.state.display.sunTarget = [...original.target];
            this.renderer.updateSunTransform(original.position, original.target, { notify: false });
        }
        this.state.sunTransformOriginal = null;
        this.state.transformReadout = '';
        this.transform.exit();
        this.state.transformSubject = null;
        this.renderer.controls.enabled = true;
        this.renderer.setSunGizmoSelected(this.state.sunSelected);
        this.syncLightingControls();
        this.updateToolState();
        this.updateUI();
    }

    updateToolState() {
        document.getElementById('tool-select')?.classList.toggle('active', this.transform.mode === 'IDLE');
        document.getElementById('tool-move')?.classList.toggle('active', this.transform.mode === 'MOVE');
        document.getElementById('tool-rotate')?.classList.toggle('active', this.transform.mode === 'ROTATE');
    }

    hasUsableCell() {
        return this.state.atoms?.cell?.some(v => new THREE.Vector3(...v).lengthSq() > 1e-12);
    }

    wrapVisibleAtomsIntoCell() {
        if (!this.hasUsableCell() || !this.renderer?.cartToFrac || !this.renderer?.fracToCart) {
            throw new Error('Wrap requires a defined unit cell.');
        }
        const pbc = this.state.atoms?.pbc || [true, true, true];
        const shouldWrap = pbc.some(Boolean) ? pbc : [true, true, true];
        const wrapped = this.state.atoms.positions.map((pos, index) => {
            const current = this.currentAtomPosition(index) || pos;
            const frac = this.renderer.cartToFrac(new THREE.Vector3(current[0], current[1], current[2]));
            ['x', 'y', 'z'].forEach((component, axis) => {
                if (!shouldWrap[axis]) return;
                const value = frac[component];
                frac[component] = value - Math.floor(value);
            });
            const cart = this.renderer.fracToCart(frac);
            return [cart.x, cart.y, cart.z];
        });
        this.state.atoms.positions = wrapped.map(p => [...p]);
        this.state.originalPositions = wrapped;
        this.renderer.updatePositions(wrapped);
        this.updateSelectionVisuals();
        this.updateUI();
    }

    normalizeSupercellInputs() {
        const ids = ['super-x', 'super-y', 'super-z'];
        let reps = ids.map(id => Math.max(1, parseInt(document.getElementById(id).value || '1', 10)));
        const pbc = this.state.atoms?.pbc || [false, false, false];

        if (!this.hasUsableCell()) {
            if (reps.some(v => v > 1)) this.toast('Supercell requires a defined unit cell.', 'warning');
            reps = [1, 1, 1];
        } else {
            reps = reps.map((value, i) => {
                if (value > 1 && !pbc[i]) {
                    this.toast(`Supercell ${['X', 'Y', 'Z'][i]} requires PBC=True in that direction.`, 'warning');
                    return 1;
                }
                return value;
            });
        }

        ids.forEach((id, i) => { document.getElementById(id).value = reps[i]; });
        return reps;
    }

    elementPairKey(a, b) {
        return [a, b].sort().join('-');
    }

    uniqueElements() {
        return this.reconcileTypeOrder(this.state.atoms?.symbols || []);
    }

    computeFmax(forces = []) {
        let maximum = null;
        for (const force of forces) {
            if (!Array.isArray(force) || force.length < 3) continue;
            const x = Number(force[0]);
            const y = Number(force[1]);
            const z = Number(force[2]);
            if (![x, y, z].every(Number.isFinite)) continue;
            const magnitude = Math.sqrt(x * x + y * y + z * z);
            maximum = maximum === null ? magnitude : Math.max(maximum, magnitude);
        }
        return maximum;
    }

    rebuildTypeIndexCache(symbols = []) {
        const cache = new Map();
        symbols.forEach((symbol, index) => {
            if (!cache.has(symbol)) cache.set(symbol, []);
            cache.get(symbol).push(index);
        });
        this.state.typeIndices = cache;
        return cache;
    }

    naturalTypeCompare(a, b) {
        return String(a).localeCompare(String(b), undefined, {
            numeric: true,
            sensitivity: 'base'
        });
    }

    reconcileTypeOrder(symbols = []) {
        const presentList = [...new Set(symbols.filter(Boolean))];
        const present = new Set(presentList);
        const existingOrder = this.state.typeOrder || [];
        const ordered = [];
        existingOrder.forEach(symbol => {
            if (present.has(symbol) && !ordered.includes(symbol)) {
                ordered.push(symbol);
            }
        });
        const newSymbols = presentList
            .filter(symbol => !ordered.includes(symbol))
            .sort((a, b) => this.naturalTypeCompare(a, b));
        if (!existingOrder.length) ordered.splice(0, ordered.length);
        ordered.push(...newSymbols);
        this.state.typeOrder = ordered;
        return ordered;
    }

    replaceTypeOrder(oldSymbol, newSymbol) {
        if (!newSymbol) return;
        const order = [...(this.state.typeOrder || [])];
        const existing = order.indexOf(newSymbol);
        const index = order.indexOf(oldSymbol);
        if (index >= 0) {
            order[index] = newSymbol;
            if (existing >= 0 && existing !== index) order.splice(existing, 1);
        } else if (existing < 0) {
            order.push(newSymbol);
        }
        this.state.typeOrder = [...new Set(order)];
    }

    typeLabelExists(label, exceptLabel = null) {
        return (this.state.atoms?.symbols || []).some(symbol => symbol === label && symbol !== exceptLabel);
    }

    uniqueTypeLabel(desiredLabel, exceptLabel = null) {
        const base = this.normalizedTypeLabel(desiredLabel);
        if (!base) return base;
        if (!this.typeLabelExists(base, exceptLabel)) return base;
        let suffix = 2;
        let candidate = `${base}_${suffix}`;
        while (this.typeLabelExists(candidate, exceptLabel)) {
            suffix += 1;
            candidate = `${base}_${suffix}`;
        }
        return candidate;
    }

    labelForBaseTypeChange(currentLabel, baseSymbol) {
        return currentLabel;
    }

    elementIndices(symbol) {
        return this.state.typeIndices?.get(symbol) || [];
    }

    isElementVisible(symbol) {
        return this.state.display.elementVisible?.[symbol] !== false;
    }

    isAtomVisible(index) {
        const symbol = this.state.atoms?.symbols?.[index];
        return !symbol || this.isElementVisible(symbol);
    }

    visibleElementIndices(symbol) {
        if (!this.isElementVisible(symbol)) return [];
        return this.elementIndices(symbol);
    }

    pruneHiddenSelection() {
        this.state.selected.forEach(index => {
            if (!this.isAtomVisible(index)) this.state.selected.delete(index);
        });
        this.state.replicaSelected.forEach((reference, key) => {
            if (!this.isAtomVisible(reference.index)) this.state.replicaSelected.delete(key);
        });
    }

    elementSelectionState(symbol) {
        const indices = this.elementIndices(symbol);
        const replicas = this.state.vizOnly ? this.renderer.supercellSelectionReferences(symbol) : [];
        const total = indices.length + replicas.length;
        if (!total) return 'none';
        const selected = indices.filter(index => this.state.selected.has(index)).length +
            replicas.filter(reference => this.state.replicaSelected.has(reference.key)).length;
        if (selected === 0) return 'none';
        return selected === total ? 'all' : 'partial';
    }

    safeControlId(prefix, value) {
        return `${prefix}-${String(value).replace(/[^A-Za-z0-9_-]/g, '_')}`;
    }

    validHexColor(value) {
        return typeof value === 'string' && /^#[0-9A-Fa-f]{6}$/.test(value);
    }

    elementVisualColor(symbol) {
        const override = this.state.display.elementColors?.[symbol];
        if (this.validHexColor(override)) return override;
        const symbols = this.state.atoms?.symbols || [];
        const colors = this.state.atoms?.visual?.colors || [];
        const index = symbols.findIndex(item => item === symbol);
        const color = colors[index];
        return this.validHexColor(color) ? color : '#cccccc';
    }

    normalizedTypeLabel(value) {
        return String(value || '').trim();
    }

    chemicalElementOptions() {
        return [
            'H','He','Li','Be','B','C','N','O','F','Ne',
            'Na','Mg','Al','Si','P','S','Cl','Ar','K','Ca',
            'Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn',
            'Ga','Ge','As','Se','Br','Kr','Rb','Sr','Y','Zr',
            'Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd','In','Sn',
            'Sb','Te','I','Xe','Cs','Ba','La','Ce','Pr','Nd',
            'Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb',
            'Lu','Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg',
            'Tl','Pb','Bi','Po','At','Rn','Fr','Ra','Ac','Th',
            'Pa','U','Np','Pu','Am','Cm','Bk','Cf','Es','Fm',
            'Md','No','Lr','Rf','Db','Sg','Bh','Hs','Mt','Ds',
            'Rg','Cn','Nh','Fl','Mc','Lv','Ts','Og'
        ];
    }

    ensureElementTypeDatalist() {
        const list = document.getElementById('element-type-options');
        if (!list || list.dataset.ready === 'true') return;
        const fragment = document.createDocumentFragment();
        this.chemicalElementOptions().forEach(symbol => {
            const option = document.createElement('option');
            option.value = symbol;
            fragment.appendChild(option);
        });
        list.appendChild(fragment);
        list.dataset.ready = 'true';
    }

    baseElementForLabel(label, fallback = 'H') {
        return this.detectedElementForLabel(label) || fallback;
    }

    detectedElementForLabel(label) {
        const text = this.normalizedTypeLabel(label);
        const known = new Set(this.chemicalElementOptions());
        if (known.has(text)) return text;
        const prefix = text.split('_', 1)[0];
        if (known.has(prefix)) return prefix;
        const match = text.match(/^([A-Z][a-z]?)/);
        return match && known.has(match[1]) ? match[1] : null;
    }

    chemicalSymbolForLabel(label) {
        const index = (this.state.atoms?.symbols || []).findIndex(symbol => symbol === label);
        return this.state.atoms?.chemical_symbols?.[index] || this.baseElementForLabel(label);
    }

    transferElementDisplaySettings(oldSymbol, newSymbol, { appearance = true } = {}) {
        if (!oldSymbol || !newSymbol || oldSymbol === newSymbol) return;
        const maps = [
            ...(appearance ? [this.state.display.elementRadii, this.state.display.elementColors] : []),
            this.state.display.elementVisible
        ];
        maps.forEach(map => {
            if (!map || !(oldSymbol in map)) return;
            if (!(newSymbol in map)) map[newSymbol] = map[oldSymbol];
            delete map[oldSymbol];
        });
        const cutoffs = this.state.display.elementBondCutoffs || {};
        const partners = new Set([oldSymbol, newSymbol, ...(this.state.atoms?.symbols || [])]);
        partners.forEach(partner => {
            const oldKey = this.elementPairKey(oldSymbol, partner);
            if (!(oldKey in cutoffs)) return;
            const mappedPartner = partner === oldSymbol ? newSymbol : partner;
            const newKey = this.elementPairKey(newSymbol, mappedPartner);
            if (!(newKey in cutoffs)) cutoffs[newKey] = cutoffs[oldKey];
        });
    }

    uniqueElementPairs() {
        const elements = this.uniqueElements();
        const pairs = [];
        for (let i = 0; i < elements.length; i++) {
            for (let j = i; j < elements.length; j++) {
                pairs.push([elements[i], elements[j]]);
            }
        }
        return pairs;
    }

    defaultElementCutoff(a, b) {
        const elementA = this.chemicalSymbolForLabel(a);
        const elementB = this.chemicalSymbolForLabel(b);
        return Number((1.2 * (this.elementCovalentRadius(elementA) + this.elementCovalentRadius(elementB))).toFixed(3));
    }

    elementVdwRadius(element) {
        const radii = this.state.atoms?.visual?.vdw_radii || [];
        const symbols = this.state.atoms?.chemical_symbols || [];
        const values = radii.filter((_, index) => symbols[index] === element).map(Number).filter(Number.isFinite);
        if (!values.length) return null;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    elementCovalentRadius(element) {
        const radii = this.state.atoms?.visual?.bond_radii || this.state.atoms?.visual?.covalent_radii || [];
        const symbols = this.state.atoms?.chemical_symbols || [];
        const values = radii.filter((_, index) => symbols[index] === element).map(Number).filter(Number.isFinite);
        if (!values.length) return 0.75;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    elementVisualRadius(symbol) {
        const radii = this.state.atoms?.visual?.radii || [];
        const symbols = this.state.atoms?.symbols || [];
        const values = radii.filter((_, index) => symbols[index] === symbol).map(Number).filter(Number.isFinite);
        if (!values.length) return this.elementCovalentRadius(this.chemicalSymbolForLabel(symbol));
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    defaultElementRadius(element) {
        const value = Number(this.state.atoms?.visual?.element_radii?.[element]);
        if (Number.isFinite(value) && value > 0) return value;
        return this.elementCovalentRadius(element);
    }

    defaultElementColor(element) {
        const color = this.state.atoms?.visual?.element_colors?.[element];
        return this.validHexColor(color) ? color : null;
    }

    setElementBaseDefaults(label, baseSymbol, { color = false } = {}) {
        if (!label || !baseSymbol) return;
        const radius = this.defaultElementRadius(baseSymbol);
        if (Number.isFinite(radius) && radius > 0) {
            this.state.display.elementRadii[label] = Number(radius.toFixed(4));
        } else {
            delete this.state.display.elementRadii[label];
        }
        if (color) {
            const nextColor = this.defaultElementColor(baseSymbol);
            if (nextColor) this.state.display.elementColors[label] = nextColor;
            else delete this.state.display.elementColors[label];
        } else {
            delete this.state.display.elementColors[label];
        }
    }

    updateRadiusScaleLabel() {
        const scale = Number(document.getElementById('atom-radius-scale')?.value || this.state.display.atomRadiusScale || 1);
        const label = document.getElementById('atom-radius-scale-value');
        if (label) label.innerText = `${(Number.isFinite(scale) ? scale : 1).toFixed(2)}x`;
    }

    renderElementRadiusControls() {
        const root = document.getElementById('element-radius-list');
        if (!root || !this.state.atoms?.symbols) return;
        this.ensureElementTypeDatalist();
        const active = document.activeElement;
        const existingFocus = {
            radius: active?.dataset?.elementRadius,
            name: active?.dataset?.elementName,
            color: active?.dataset?.elementColor,
            type: active?.dataset?.elementType
        };
        root.innerHTML = '';
        this.uniqueElements().forEach(symbol => {
            if (!(symbol in this.state.display.elementRadii)) {
                this.state.display.elementRadii[symbol] = Number(this.elementVisualRadius(symbol).toFixed(4));
            }
            if (!(symbol in this.state.display.elementVisible)) {
                this.state.display.elementVisible[symbol] = true;
            }
            const row = document.createElement('div');
            row.className = 'element-radius-row element-appearance-row';
            const currentElement = this.chemicalSymbolForLabel(symbol);
            const typeIndices = [...this.elementIndices(symbol)];
            const typeSelect = document.createElement('input');
            typeSelect.type = 'text';
            typeSelect.setAttribute('list', 'element-type-options');
            typeSelect.setAttribute('aria-label', `Element type for ${symbol}`);
            typeSelect.className = 'element-type-select';
            typeSelect.dataset.elementType = symbol;
            typeSelect.title = `${typeIndices.length} atom${typeIndices.length === 1 ? '' : 's'} with label ${symbol}`;
            typeSelect.value = currentElement;

            const visibleBox = document.createElement('input');
            visibleBox.type = 'checkbox';
            visibleBox.className = 'element-check element-visible-checkbox';
            visibleBox.dataset.elementVisible = symbol;
            visibleBox.checked = this.isElementVisible(symbol);
            visibleBox.title = `Show ${symbol} atoms in the viewport`;
            visibleBox.addEventListener('change', () => {
                this.state.display.elementVisible = {
                    ...(this.state.display.elementVisible || {}),
                    [symbol]: visibleBox.checked
                };
                if (!visibleBox.checked) {
                    this.elementIndices(symbol).forEach(index => this.state.selected.delete(index));
                    this.state.replicaSelected.forEach((reference, key) => {
                        if (this.state.atoms?.symbols?.[reference.index] === symbol) {
                            this.state.replicaSelected.delete(key);
                        }
                    });
                }
                this.safeApplyDisplayOptions();
                this.updateElementSelectionControls();
                this.updateUI();
            });

            const selectBox = document.createElement('input');
            selectBox.type = 'checkbox';
            selectBox.className = 'element-check element-select-checkbox';
            selectBox.dataset.elementSelect = symbol;
            selectBox.disabled = !this.isElementVisible(symbol);
            selectBox.title = `Select all visible ${symbol} atoms`;
            const selectionState = this.elementSelectionState(symbol);
            selectBox.checked = selectionState === 'all';
            selectBox.indeterminate = selectionState === 'partial';
            selectBox.addEventListener('change', () => this.toggleElementSelection(symbol, selectBox.checked));

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.id = this.safeControlId('element-name', symbol);
            nameInput.className = 'element-name-input';
            nameInput.dataset.elementName = symbol;
            nameInput.value = symbol;
            const previewDetectedBase = () => {
                const next = this.normalizedTypeLabel(nameInput.value);
                const inferredBase = this.detectedElementForLabel(next);
                if (inferredBase) {
                    if (typeSelect.value !== inferredBase) typeSelect.value = inferredBase;
                    const radius = this.defaultElementRadius(inferredBase);
                    if (Number.isFinite(radius) && radius > 0) input.value = Number(radius.toFixed(4));
                }
            };
            let renameRequestKey = null;
            const commitRename = async (baseOverride = null) => {
                const desired = this.normalizedTypeLabel(nameInput.value);
                const inferredBase = this.detectedElementForLabel(desired);
                const base = baseOverride || inferredBase;
                const requestKey = `${desired}\u0000${base || ''}`;
                if (!desired || renameRequestKey === requestKey) return;
                if (desired === symbol && (!base || base === currentElement)) return;
                renameRequestKey = requestKey;
                const applied = await this.renameElementType(symbol, desired, base, typeIndices);
                if (!applied && nameInput.isConnected) renameRequestKey = null;
            };
            typeSelect.addEventListener('change', () => {
                if (!this.chemicalElementOptions().includes(typeSelect.value)) {
                    const invalidType = typeSelect.value;
                    typeSelect.value = currentElement;
                    this.toast(`${invalidType || 'Unknown'} is not a valid element type.`, 'warning');
                    return;
                }
                const radius = this.defaultElementRadius(typeSelect.value);
                if (Number.isFinite(radius) && radius > 0) input.value = Number(radius.toFixed(4));
                nameInput.value = this.labelForBaseTypeChange(symbol, typeSelect.value);
                commitRename(typeSelect.value);
            });
            nameInput.addEventListener('keydown', event => {
                if (event.key === 'Escape') {
                    event.preventDefault();
                    nameInput.value = symbol;
                    nameInput.blur();
                }
            });
            nameInput.addEventListener('input', () => {
                renameRequestKey = null;
                previewDetectedBase();
            });
            nameInput.addEventListener('change', () => commitRename());

            const color = document.createElement('input');
            color.type = 'color';
            color.className = 'element-color-input';
            color.dataset.elementColor = symbol;
            color.value = this.elementVisualColor(symbol);
            color.title = `Color for ${symbol}`;
            color.addEventListener('input', () => {
                this.state.display.elementColors[symbol] = color.value;
                this.safeApplyDisplayOptions();
                this.updateSelectedTypeControls();
            });
            color.addEventListener('change', () => {
                this.state.display.elementColors[symbol] = color.value;
                this.safeApplyDisplayOptions();
                this.updateSelectedTypeControls();
            });

            const input = document.createElement('input');
            input.type = 'number';
            input.id = this.safeControlId('element-radius', symbol);
            input.className = 'element-radius-input';
            input.dataset.elementRadius = symbol;
            input.min = '0.05';
            input.step = '0.01';
            input.value = this.state.display.elementRadii[symbol];
            input.addEventListener('change', () => this.safeApplyDisplayOptions());
            input.addEventListener('input', () => this.safeApplyDisplayOptions());

            row.append(typeSelect, visibleBox, selectBox, nameInput, color, input);
            root.appendChild(row);
        });
        const focusMatch = [...root.querySelectorAll('[data-element-radius], [data-element-name], [data-element-color], [data-element-type]')]
            .find(el => (
                (existingFocus.radius && el.dataset.elementRadius === existingFocus.radius) ||
                (existingFocus.name && el.dataset.elementName === existingFocus.name) ||
                (existingFocus.color && el.dataset.elementColor === existingFocus.color) ||
                (existingFocus.type && el.dataset.elementType === existingFocus.type)
            ));
        focusMatch?.focus();
    }

    parseElementRadii() {
        const radii = {};
        document.querySelectorAll('.element-radius-input').forEach(input => {
            const value = parseFloat(input.value);
            if (Number.isFinite(value) && value > 0) {
                radii[input.dataset.elementRadius] = value;
            }
        });
        return radii;
    }

    parseElementColors() {
        const colors = {};
        document.querySelectorAll('.element-color-input').forEach(input => {
            if (this.validHexColor(input.value)) {
                colors[input.dataset.elementColor] = input.value;
            }
        });
        Object.entries(this.state.display.elementColors || {}).forEach(([symbol, color]) => {
            if (this.validHexColor(color) && !(symbol in colors)) colors[symbol] = color;
        });
        return colors;
    }

    parseElementVisibility() {
        const visible = { ...(this.state.display.elementVisible || {}) };
        document.querySelectorAll('.element-visible-checkbox').forEach(input => {
            visible[input.dataset.elementVisible] = input.checked;
        });
        return visible;
    }

    updateElementSelectionControls() {
        document.querySelectorAll('.element-select-checkbox').forEach(input => {
            const symbol = input.dataset.elementSelect;
            input.disabled = !this.isElementVisible(symbol);
            const state = this.elementSelectionState(symbol);
            input.checked = state === 'all';
            input.indeterminate = state === 'partial';
        });
        document.querySelectorAll('.element-visible-checkbox').forEach(input => {
            input.checked = this.isElementVisible(input.dataset.elementVisible);
        });
    }

    toggleElementSelection(symbol, checked) {
        const targets = this.visibleElementIndices(symbol);
        targets.forEach(index => {
            if (checked) this.state.selected.add(index);
            else this.state.selected.delete(index);
        });
        if (this.state.vizOnly) {
            this.renderer.supercellSelectionReferences(symbol).forEach(reference => {
                if (checked) this.addSelectionReference(reference);
                else this.removeSelectionReference(reference);
            });
        }
        this.updateSelectionVisuals();
        this.updateElementSelectionControls();
        this.updateUI();
    }

    selectElement(symbol) {
        this.toggleElementSelection(symbol, true);
    }

    async renameElementType(oldSymbol, nextLabel, baseSymbol = null, expectedIndices = null) {
        const desiredLabel = this.normalizedTypeLabel(nextLabel);
        if (!desiredLabel) {
            this.toast('Atom type name cannot be empty.', 'warning');
            return false;
        }
        if (this.state.pendingTypeRenames.has(oldSymbol)) return true;
        const indices = Array.isArray(expectedIndices)
            ? [...expectedIndices]
            : [...this.elementIndices(oldSymbol)];
        const labels = this.state.atoms?.symbols || [];
        if (!indices.length || indices.some(index => labels[index] !== oldSymbol)) return false;

        const label = this.uniqueTypeLabel(desiredLabel, oldSymbol);
        if (desiredLabel && label !== desiredLabel) {
            this.toast(`Label ${desiredLabel} already exists; using ${label} to keep atom types separate.`, 'warning');
        }
        const base = baseSymbol === null || baseSymbol === undefined
            ? this.detectedElementForLabel(label)
            : baseSymbol;
        const oldBase = this.chemicalSymbolForLabel(oldSymbol);
        const effectiveBase = base || oldBase;
        const preserveAppearance = effectiveBase === oldBase;
        this.state.pendingTypeRenames.add(oldSymbol);
        try {
            if (!this.canEditAtoms()) {
                this.renameElementTypeForVisualization(oldSymbol, label, indices, effectiveBase, { preserveAppearance });
                return true;
            }
            const actionText = label === oldSymbol
                ? `Updating ${oldSymbol} element type to ${effectiveBase}`
                : `Renaming ${oldSymbol} to ${label}`;
            const data = await this.withBusy(
                `${actionText} for ${indices.length} atom${indices.length === 1 ? '' : 's'}...`,
                () => this.api.updateAtomTypes(indices, label, this.backendPositionsPayload(), this.state.applyConstraints, base)
            );
            this.transferElementDisplaySettings(oldSymbol, label, { appearance: preserveAppearance });
            if (!preserveAppearance) this.setElementBaseDefaults(label, effectiveBase);
            this.replaceTypeOrder(oldSymbol, label);
            this.setAtomsData(data);
            this.toast(
                label === oldSymbol
                    ? `Updated ${label} element type to ${effectiveBase}.`
                    : `Renamed ${oldSymbol} to ${label}.`,
                'success'
            );
            return true;
        } catch (err) {
            this.toast(`Rename failed: ${err.message}`, 'error');
            return false;
        } finally {
            this.state.pendingTypeRenames.delete(oldSymbol);
        }
    }

    renameElementTypeForVisualization(oldSymbol, label, indices = this.elementIndices(oldSymbol), baseSymbol = null, { preserveAppearance = true } = {}) {
        if (!this.state.atoms || !indices.length) return;
        const base = baseSymbol || this.chemicalSymbolForLabel(oldSymbol);
        const radius = this.defaultElementRadius(base);
        const color = this.defaultElementColor(base);
        indices.forEach(index => {
            this.state.atoms.symbols[index] = label;
            if (Array.isArray(this.state.atoms.atom_types)) {
                this.state.atoms.atom_types[index] = label;
            }
            if (Array.isArray(this.state.atoms.chemical_symbols)) {
                this.state.atoms.chemical_symbols[index] = base;
            }
            if (!preserveAppearance && Number.isFinite(radius) && radius > 0 && Array.isArray(this.state.atoms.visual?.radii)) {
                this.state.atoms.visual.radii[index] = radius;
            }
            if (!preserveAppearance && Number.isFinite(radius) && radius > 0 && Array.isArray(this.state.atoms.visual?.covalent_radii)) {
                this.state.atoms.visual.covalent_radii[index] = radius;
            }
            if (!preserveAppearance && color && Array.isArray(this.state.atoms.visual?.colors)) {
                this.state.atoms.visual.colors[index] = color;
            }
        });
        this.rebuildTypeIndexCache(this.state.atoms.symbols || []);
        const selected = new Set();
        this.state.selected.forEach(index => {
            if (this.isElementVisible(this.state.atoms.symbols[index])) selected.add(index);
        });
        this.state.selected = selected;
        this.transferElementDisplaySettings(oldSymbol, label, { appearance: preserveAppearance });
        if (!preserveAppearance) this.setElementBaseDefaults(label, base, { color: true });
        this.replaceTypeOrder(oldSymbol, label);
        this.renderElementBondControls();
        this.renderer.renameAtomType(oldSymbol, label, indices, this.state.display, base);
        this.renderElementRadiusControls();
        this.updateElementSelectionControls();
        this.pruneSelection();
        this.updateSelectionVisuals();
        this.updateUI();
        this.toast(
            label === oldSymbol
                ? `Updated ${label} element type to ${base} for this visualization.`
                : `Renamed ${oldSymbol} to ${label} for this visualization.`,
            'success'
        );
    }

    selectedTypeLabel() {
        const selected = [...this.state.selected].filter(index => this.state.atoms?.symbols?.[index]);
        if (!selected.length) return '';
        const labels = [...new Set(selected.map(index => this.state.atoms.symbols[index]))];
        return labels.length === 1 ? labels[0] : '';
    }

    updateSelectedTypeControls() {
        const name = document.getElementById('selected-type-name');
        const color = document.getElementById('selected-type-color');
        const apply = document.getElementById('btn-apply-selected-type');
        if (!name || !color || !apply) return;
        const hasSelection = this.state.selected.size > 0;
        const label = this.selectedTypeLabel();
        name.disabled = !hasSelection;
        color.disabled = !hasSelection;
        apply.disabled = !hasSelection;
        name.placeholder = hasSelection ? 'Mixed selected types' : 'Select atoms first';
        if (!document.activeElement || document.activeElement !== name) {
            name.value = hasSelection ? label : '';
        }
        const colorSymbol = label || [...this.state.selected].map(i => this.state.atoms?.symbols?.[i]).find(Boolean);
        color.value = colorSymbol ? this.elementVisualColor(colorSymbol) : '#cccccc';
    }

    async applySelectedTypeEdit() {
        const indices = [...this.state.selected].sort((a, b) => a - b);
        if (!indices.length) {
            this.toast('Select atoms before changing atom type.', 'warning');
            return;
        }
        const input = document.getElementById('selected-type-name');
        const color = document.getElementById('selected-type-color');
        const label = this.normalizedTypeLabel(input?.value);
        if (!label) {
            this.toast('Atom type name cannot be empty.', 'warning');
            return;
        }
        const previousLabels = [...new Set(indices.map(index => this.state.atoms.symbols[index]))];
        const exclusivePrevious = previousLabels.length === 1 ? previousLabels[0] : null;
        const uniqueLabel = this.uniqueTypeLabel(label, exclusivePrevious);
        if (uniqueLabel !== label) {
            this.toast(`Label ${label} already exists; using ${uniqueLabel} to keep atom types separate.`, 'warning');
        }
        const previousBase = previousLabels.length === 1 ? this.chemicalSymbolForLabel(previousLabels[0]) : null;
        const detectedBase = this.detectedElementForLabel(uniqueLabel);
        const base = detectedBase || previousBase || 'H';
        const preserveAppearance = !detectedBase || (previousLabels.length === 1 && previousBase === detectedBase);
        if (preserveAppearance && this.validHexColor(color?.value)) {
            this.state.display.elementColors[uniqueLabel] = color.value;
        }
        if (!this.canEditAtoms()) {
            this.applySelectedTypeForVisualization(indices, uniqueLabel, base, { preserveAppearance });
            return;
        }
        try {
            const data = await this.withBusy(
                `Changing ${indices.length} selected atom${indices.length === 1 ? '' : 's'} to ${uniqueLabel}...`,
                () => this.api.updateAtomTypes(indices, uniqueLabel, this.backendPositionsPayload(), this.state.applyConstraints, detectedBase)
            );
            if (previousLabels.length === 1) {
                this.transferElementDisplaySettings(previousLabels[0], uniqueLabel, { appearance: preserveAppearance });
                this.replaceTypeOrder(previousLabels[0], uniqueLabel);
            }
            if (!preserveAppearance) this.setElementBaseDefaults(uniqueLabel, base);
            this.setAtomsData(data);
            indices.forEach(index => this.state.selected.add(index));
            this.updateSelectionVisuals();
            this.updateUI();
            this.toast(`Updated selected atoms to ${uniqueLabel}.`, 'success');
        } catch (err) {
            this.toast(`Selected atom type update failed: ${err.message}`, 'error');
        }
    }

    applySelectedTypeForVisualization(indices, label, baseSymbol, { preserveAppearance = true } = {}) {
        if (!this.state.atoms || !indices.length) return;
        const radius = this.defaultElementRadius(baseSymbol);
        const color = this.defaultElementColor(baseSymbol);
        indices.forEach(index => {
            this.state.atoms.symbols[index] = label;
            if (Array.isArray(this.state.atoms.atom_types)) this.state.atoms.atom_types[index] = label;
            if (Array.isArray(this.state.atoms.chemical_symbols)) this.state.atoms.chemical_symbols[index] = baseSymbol;
            if (!preserveAppearance && Number.isFinite(radius) && radius > 0 && Array.isArray(this.state.atoms.visual?.radii)) {
                this.state.atoms.visual.radii[index] = radius;
            }
            if (!preserveAppearance && Number.isFinite(radius) && radius > 0 && Array.isArray(this.state.atoms.visual?.covalent_radii)) {
                this.state.atoms.visual.covalent_radii[index] = radius;
            }
            if (!preserveAppearance && color && Array.isArray(this.state.atoms.visual?.colors)) {
                this.state.atoms.visual.colors[index] = color;
            }
        });
        this.rebuildTypeIndexCache(this.state.atoms.symbols || []);
        if (!preserveAppearance) this.setElementBaseDefaults(label, baseSymbol, { color: true });
        this.renderElementBondControls();
        this.renderer.rebuildAtoms(this.state.atoms, this.state.atoms.metadata?.custom_colors || {});
        this.updateSelectionVisuals();
        this.renderElementRadiusControls();
        this.updateElementSelectionControls();
        this.updateUI();
        this.toast(`Updated selected atoms to ${label} for this visualization.`, 'success');
    }

    renderElementBondControls({ capture = true } = {}) {
        const root = document.getElementById('element-bond-list');
        if (!root || !this.state.atoms?.symbols) return;
        if (capture) this.captureBondSettingsFromControls();
        const existingFocus = document.activeElement?.dataset?.pairKey;
        root.innerHTML = '';
        this.uniqueElementPairs().forEach(([a, b]) => {
            const key = this.elementPairKey(a, b);
            if (!(key in this.state.display.elementBondCutoffs)) {
                this.state.display.elementBondCutoffs[key] = Number(this.defaultElementCutoff(a, b).toFixed(3));
            }
            const row = document.createElement('div');
            row.className = 'element-bond-row';
            const label = document.createElement('label');
            label.htmlFor = `bond-cutoff-${key}`;
            label.innerText = key;
            const input = document.createElement('input');
            input.type = 'number';
            input.id = `bond-cutoff-${key}`;
            input.className = 'element-bond-cutoff';
            input.dataset.pairKey = key;
            input.min = '0';
            input.step = '0.05';
            input.value = this.state.display.elementBondCutoffs[key];
            input.addEventListener('change', () => this.safeApplyDisplayOptions());
            input.addEventListener('input', () => {
                if (document.getElementById('bond-mode').value === 'element') this.safeApplyDisplayOptions();
            });
            row.append(label, input);
            root.appendChild(row);
        });
        if (existingFocus) {
            root.querySelector(`[data-pair-key="${existingFocus}"]`)?.focus();
        }
        this.updateBondModeUI();
    }

    parseElementBondCutoffs() {
        const cutoffs = {};
        document.querySelectorAll('.element-bond-cutoff').forEach(input => {
            const value = parseFloat(input.value);
            if (Number.isFinite(value) && value >= 0) {
                cutoffs[input.dataset.pairKey] = value;
            }
        });
        return cutoffs;
    }

    captureBondSettingsFromControls({ strictManual = false } = {}) {
        if (!this.state?.display) return;
        const mode = document.getElementById('bond-mode')?.value;
        if (['auto', 'element', 'manual'].includes(mode)) {
            this.state.display.bondMode = mode;
        }
        const scale = Number(document.getElementById('bond-cutoff')?.value);
        if (Number.isFinite(scale) && scale > 0) {
            this.state.display.bondCutoffScale = Math.max(0.5, scale);
        }
        const style = document.getElementById('bond-style')?.value;
        if (['cylinder', 'flat'].includes(style)) this.state.display.bondStyle = style;
        const thickness = Number(document.getElementById('bond-thickness')?.value);
        if (Number.isFinite(thickness) && thickness > 0) {
            this.state.display.bondThickness = Math.max(0.02, Math.min(0.6, thickness));
        }
        const colorMode = document.getElementById('bond-color-mode')?.value;
        if (['split', 'custom'].includes(colorMode)) this.state.display.bondColorMode = colorMode;
        const customColor = document.getElementById('bond-custom-color')?.value;
        if (/^#[0-9A-Fa-f]{6}$/.test(customColor || '')) {
            this.state.display.bondCustomColor = customColor;
        }
        this.state.display.elementBondCutoffs = {
            ...(this.state.display.elementBondCutoffs || {}),
            ...this.parseElementBondCutoffs()
        };
        if (this.state.display.bondMode !== 'manual') return;
        try {
            this.state.display.manualBondPairs = this.parseBondPairs();
        } catch (error) {
            if (strictManual) throw error;
            // Preserve the last valid topology while a manual pair is being
            // typed or a topology-changing backend response is being applied.
        }
    }

    updateBondModeUI() {
        const mode = document.getElementById('bond-mode')?.value || this.state.display.bondMode;
        const elementPanel = document.getElementById('element-bond-panel');
        const pairText = document.getElementById('bond-pairs');
        const cutoffRow = document.getElementById('bond-cutoff')?.closest('.prop-row');
        if (elementPanel) elementPanel.classList.toggle('hidden', mode !== 'element');
        if (pairText) pairText.classList.toggle('hidden', mode !== 'manual');
        if (cutoffRow) cutoffRow.classList.toggle('hidden', mode === 'manual');
        this.updateBondAppearanceUI();
    }

    updateBondAppearanceUI() {
        const mode = document.getElementById('bond-color-mode')?.value || this.state.display.bondColorMode;
        document.getElementById('bond-custom-color-row')?.classList.toggle('hidden', mode !== 'custom');
        const rawThickness = Number(document.getElementById('bond-thickness')?.value || this.state.display.bondThickness);
        const thickness = Number.isFinite(rawThickness) ? rawThickness : 0.11;
        const output = document.getElementById('bond-thickness-value');
        if (output) output.innerText = `${thickness.toFixed(2)} A`;
    }

    parseBondPairs() {
        const text = document.getElementById('bond-pairs').value.trim();
        if (!text) return [];
        const count = this.state.atoms?.positions?.length || 0;
        const pairs = [];
        const seen = new Set();
        const tokens = text.split(/[\n,;]+/).map(v => v.trim()).filter(Boolean);
        tokens.forEach(token => {
            const elementMatch = token.match(/^([A-Za-z][A-Za-z0-9_+]*)\s*[-:]\s*([A-Za-z][A-Za-z0-9_+]*)\s*(?:[:=]\s*)?([0-9]*\.?[0-9]+)$/);
            if (elementMatch) {
                const key = this.elementPairKey(elementMatch[1], elementMatch[2]);
                this.state.display.elementBondCutoffs[key] = parseFloat(elementMatch[3]);
                return;
            }
            const match = token.match(/^(\d+)\s*(?:-|\s)\s*(\d+)$/);
            if (!match) throw new Error(`Invalid bond pair: ${token}`);
            const i = parseInt(match[1], 10);
            const j = parseInt(match[2], 10);
            if (i === j || i < 0 || j < 0 || i >= count || j >= count) {
                throw new Error(`Bond pair out of range: ${token}`);
            }
            const a = Math.min(i, j);
            const b = Math.max(i, j);
            const key = `${a}-${b}`;
            if (!seen.has(key)) {
                pairs.push([a, b]);
                seen.add(key);
            }
        });
        return pairs;
    }

    writeBondPairs(pairs) {
        document.getElementById('bond-pairs').value = pairs.map(([i, j]) => `${i}-${j}`).join(', ');
    }

    applyDisplayOptions() {
        if (this.state.displayApplyRequest !== null) {
            cancelAnimationFrame(this.state.displayApplyRequest);
            this.state.displayApplyRequest = null;
        }
        this.state.display.showBonds = document.getElementById('chk-bonds').checked;
        this.state.display.showCell = document.getElementById('chk-cell').checked;
        this.state.display.showAxes = document.getElementById('chk-axes').checked;
        this.state.display.showGrid = document.getElementById('chk-grid').checked;
        this.state.display.showOverlays = document.getElementById('chk-overlays')?.checked !== false;
        this.state.display.showPeriodicBonds = Boolean(document.getElementById('chk-periodic-bonds')?.checked);
        this.state.display.exportIncludeCell = document.getElementById('export-include-cell')?.checked !== false;
        this.state.display.projectionMode = document.getElementById('projection-mode')?.value || 'perspective';
        this.state.display.viewportBackground = document.getElementById('viewport-background')?.value === 'white'
            ? 'white'
            : 'dark';
        this.state.display.atomDisplayMode = document.getElementById('atom-display-mode')?.value === '2d'
            ? '2d'
            : '3d';
        this.state.display.viewRotationStepDeg = this.normalizedViewRotationStep(
            document.getElementById('view-rotate-step')?.value
        );
        this.state.applyConstraints = document.getElementById('chk-constraints').checked;
        this.state.antiAliasing = document.getElementById('chk-antialias').checked;
        this.state.sphereQuality = document.getElementById('sphere-quality').value;
        this.state.display.rotatePivot = document.getElementById('rotate-pivot')?.value || 'selection';
        this.state.display.commensurateGuide = Boolean(document.getElementById('chk-commensurate-guide')?.checked);
        this.state.display.commensurateSnap = document.getElementById('chk-commensurate-snap')?.checked !== false;
        const strainPercent = parseFloat(document.getElementById('commensurate-strain')?.value || '1');
        this.state.display.commensurateStrainTolerance = Number.isFinite(strainPercent) && strainPercent >= 0
            ? Math.min(25, strainPercent) / 100
            : 0.01;
        const maxIndex = parseInt(document.getElementById('commensurate-max-index')?.value || '32', 10);
        this.state.display.commensurateMaxIndex = Number.isFinite(maxIndex)
            ? Math.max(2, Math.min(64, maxIndex))
            : 32;
        const snapRange = parseFloat(document.getElementById('commensurate-snap-range')?.value || '2');
        this.state.display.commensurateSnapRangeDeg = Number.isFinite(snapRange)
            ? Math.max(0, Math.min(15, snapRange))
            : 2;
        this.captureBondSettingsFromControls({ strictManual: true });
        const radiusScale = parseFloat(document.getElementById('atom-radius-scale')?.value || '1');
        this.state.display.atomRadiusScale = Number.isFinite(radiusScale) && radiusScale > 0 ? radiusScale : 1.0;
        this.state.display.elementRadii = this.parseElementRadii();
        this.state.display.elementColors = this.parseElementColors();
        this.state.display.elementVisible = this.parseElementVisibility();
        this.state.display.supercell = this.normalizeSupercellInputs();
        this.state.display.antiAliasing = this.state.antiAliasing;
        this.state.display.sphereQuality = this.state.sphereQuality;
        this.state.display.vizOnly = this.state.vizOnly;
        this.state.display.blenderExportMode = document.getElementById('blender-export-mode')?.value || 'instanced';
        this.updateRadiusScaleLabel();
        this.syncViewControls();
        this.pruneSelection();
        this.renderer.setDisplayOptions(this.state.display);
        this.updateSelectionVisuals();
        this.updateElementSelectionControls();
        this.updateBondModeUI();
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
    }

    safeApplyDisplayOptions() {
        if (this.state.displayApplyRequest !== null) return;
        this.state.displayApplyRequest = requestAnimationFrame(() => {
            this.state.displayApplyRequest = null;
            try {
                this.applyDisplayOptions();
            } catch (err) {
                this.toast(err.message, 'error');
            }
        });
    }

    clonePlain(value) {
        if (window.structuredClone) return window.structuredClone(value);
        return JSON.parse(JSON.stringify(value));
    }

    designSettingsSnapshot() {
        this.readTransformSettings();
        this.syncAtomicScaleFromCamera({ forceInput: true, syncPreview: false });
        return {
            schema: 'v_ase.visual_settings.v2',
            display: this.clonePlain(this.state.display),
            camera: this.currentCameraForExport(),
            applyConstraints: this.state.applyConstraints,
            antiAliasing: this.state.antiAliasing,
            sphereQuality: this.state.sphereQuality,
            moveIncrement: this.state.moveIncrement,
            rotateIncrementDeg: this.state.rotateIncrementDeg,
            imageExportProfile: this.clonePlain(this.currentImageExportProfile())
        };
    }

    setSupercellInputs(reps = [1, 1, 1]) {
        ['super-x', 'super-y', 'super-z'].forEach((id, index) => {
            const input = document.getElementById(id);
            if (input) input.value = `${Math.max(1, parseInt(reps[index] || 1, 10))}`;
        });
    }

    identityMatrix3() {
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    }

    parseSupercellMatrix() {
        return [0, 1, 2].map(row => [0, 1, 2].map(col => {
            const value = Number(document.getElementById(`matrix-${row}${col}`)?.value ?? (row === col ? 1 : 0));
            if (!Number.isInteger(value)) throw new Error('make_supercell matrix entries must be integers.');
            return value;
        }));
    }

    setSupercellMatrixInputs(matrix = this.identityMatrix3()) {
        for (let row = 0; row < 3; row++) {
            for (let col = 0; col < 3; col++) {
                const input = document.getElementById(`matrix-${row}${col}`);
                if (input) input.value = `${matrix[row]?.[col] ?? (row === col ? 1 : 0)}`;
            }
        }
    }

    isIdentityMatrix(matrix) {
        return matrix.every((row, i) => row.every((value, j) => value === (i === j ? 1 : 0)));
    }

    syncDesignControls() {
        const display = this.state.display;
        const setChecked = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.checked = Boolean(value);
        };
        const setValue = (id, value) => {
            const el = document.getElementById(id);
            if (el) el.value = value;
        };
        setChecked('chk-bonds', display.showBonds);
        setChecked('chk-cell', display.showCell);
        setChecked('chk-axes', display.showAxes);
        setChecked('chk-grid', display.showGrid);
        setChecked('chk-overlays', display.showOverlays !== false);
        setChecked('chk-periodic-bonds', display.showPeriodicBonds);
        setChecked('export-include-cell', display.exportIncludeCell !== false);
        setValue('projection-mode', display.projectionMode || 'perspective');
        setValue('viewport-background', display.viewportBackground === 'white' ? 'white' : 'dark');
        setValue('atom-display-mode', display.atomDisplayMode === '2d' ? '2d' : '3d');
        setValue('view-rotate-step', this.normalizedViewRotationStep(display.viewRotationStepDeg));
        const atomicScale = Number(display.atomicScalePixelsPerAngstrom);
        if (Number.isFinite(atomicScale) && atomicScale > 0) {
            setValue('atomic-scale', this.atomicScaleText(atomicScale));
        }
        setChecked('chk-constraints', this.state.applyConstraints);
        setChecked('chk-antialias', this.state.antiAliasing);
        setValue('sphere-quality', this.state.sphereQuality);
        setValue('rotate-pivot', display.rotatePivot || 'selection');
        setChecked('chk-commensurate-guide', display.commensurateGuide);
        setChecked('chk-commensurate-snap', display.commensurateSnap !== false);
        setValue('commensurate-strain', (display.commensurateStrainTolerance ?? 0.01) * 100);
        setValue('commensurate-max-index', display.commensurateMaxIndex ?? 32);
        setValue('commensurate-snap-range', display.commensurateSnapRangeDeg ?? 2);
        setValue('bond-mode', display.bondMode || 'auto');
        setValue('bond-cutoff', display.bondCutoffScale || 1.0);
        setValue('bond-style', display.bondStyle || 'cylinder');
        setValue('bond-thickness', display.bondThickness || 0.11);
        setValue('bond-color-mode', display.bondColorMode || 'split');
        setValue('bond-custom-color', display.bondCustomColor || '#c8ccd0');
        setValue('blender-export-mode', display.blenderExportMode || 'instanced');
        setValue('atom-radius-scale', display.atomRadiusScale || 1);
        setValue('move-increment', this.state.moveIncrement || 0);
        setValue('rotate-increment', this.state.rotateIncrementDeg || 0);
        this.setSupercellInputs(display.supercell || [1, 1, 1]);
        this.writeBondPairs(display.manualBondPairs || []);
        this.syncViewControls(display);
        this.syncLightingControls(display);
        this.updateRadiusScaleLabel();
        this.updateBondAppearanceUI();
    }

    reconcileDesignDisplay(nextDisplay = {}) {
        const migratedDisplay = { ...this.clonePlain(nextDisplay) };
        const legacyFramingMode = migratedDisplay.imageScaleMode;
        if (!Object.prototype.hasOwnProperty.call(migratedDisplay, 'imageFramingMode')) {
            migratedDisplay.imageFramingMode = legacyFramingMode === 'physical' ? 'physical' : 'viewport';
        }
        if (!Object.prototype.hasOwnProperty.call(migratedDisplay, 'atomicScalePixelsPerAngstrom')
            && legacyFramingMode === 'physical') {
            migratedDisplay.atomicScalePixelsPerAngstrom = migratedDisplay.imagePixelsPerAngstrom;
        }
        delete migratedDisplay.imageScaleMode;
        delete migratedDisplay.imagePixelsPerAngstrom;
        if (!Object.prototype.hasOwnProperty.call(migratedDisplay, 'commensurateGuide')
            && Object.prototype.hasOwnProperty.call(migratedDisplay, 'unitCellAwareRotate')) {
            migratedDisplay.commensurateGuide = Boolean(migratedDisplay.unitCellAwareRotate);
        }
        delete migratedDisplay.unitCellAwareRotate;
        delete migratedDisplay.rotateStrainCutoff;
        nextDisplay = migratedDisplay;
        const finiteClamped = (value, fallback, minimum, maximum) => {
            const parsed = Number(value);
            return Math.max(minimum, Math.min(maximum, Number.isFinite(parsed) ? parsed : fallback));
        };
        const integerClamped = (value, fallback, minimum, maximum) => {
            const parsed = parseInt(value, 10);
            return Math.max(minimum, Math.min(maximum, Number.isFinite(parsed) ? parsed : fallback));
        };
        const labels = [...new Set(this.state.atoms?.symbols || [])];
        const atomCount = this.state.atoms?.positions?.length || 0;
        const pickLabelMap = (source, fallback = {}) => {
            const result = {};
            labels.forEach(label => {
                if (source && Object.prototype.hasOwnProperty.call(source, label)) result[label] = source[label];
                else if (fallback && Object.prototype.hasOwnProperty.call(fallback, label)) result[label] = fallback[label];
            });
            return result;
        };

        const elementRadii = pickLabelMap(nextDisplay.elementRadii);
        labels.forEach(label => {
            const radius = Number(elementRadii[label]);
            if (!Number.isFinite(radius) || radius <= 0) {
                elementRadii[label] = Number(this.elementVisualRadius(label).toFixed(4));
            }
        });
        const elementColors = pickLabelMap(nextDisplay.elementColors);
        Object.keys(elementColors).forEach(label => {
            if (!this.validHexColor(elementColors[label])) delete elementColors[label];
        });
        const elementVisible = pickLabelMap(nextDisplay.elementVisible);
        labels.forEach(label => {
            elementVisible[label] = elementVisible[label] !== false;
        });

        const savedCutoffs = nextDisplay.elementBondCutoffs || {};
        const elementBondCutoffs = {};
        for (let i = 0; i < labels.length; i++) {
            for (let j = i; j < labels.length; j++) {
                const key = this.elementPairKey(labels[i], labels[j]);
                const saved = Number(savedCutoffs[key]);
                elementBondCutoffs[key] = Number.isFinite(saved) && saved >= 0
                    ? saved
                    : this.defaultElementCutoff(labels[i], labels[j]);
            }
        }

        const manualBondPairs = (nextDisplay.manualBondPairs || []).filter(pair => {
            if (!Array.isArray(pair) || pair.length < 2) return false;
            const i = Number(pair[0]);
            const j = Number(pair[1]);
            return Number.isInteger(i) && Number.isInteger(j) && i >= 0 && j >= 0 && i < atomCount && j < atomCount && i !== j;
        }).map(pair => [Number(pair[0]), Number(pair[1])]);

        const requestedSupercell = Array.isArray(nextDisplay.supercell) ? nextDisplay.supercell : [1, 1, 1];
        const pbc = this.state.atoms?.pbc || [false, false, false];
        const usableCell = this.hasUsableCell();
        const supercell = [0, 1, 2].map(axis => {
            const value = Math.max(1, parseInt(requestedSupercell[axis] || 1, 10));
            return usableCell && (value === 1 || Boolean(pbc[axis])) ? value : 1;
        });

        return {
            ...this.clonePlain(nextDisplay),
            commensurateGuide: Boolean(nextDisplay.commensurateGuide),
            commensurateSnap: nextDisplay.commensurateSnap !== false,
            commensurateStrainTolerance: finiteClamped(
                nextDisplay.commensurateStrainTolerance, 0.01, 0, 0.25
            ),
            commensurateMaxIndex: integerClamped(
                nextDisplay.commensurateMaxIndex, 32, 2, 64
            ),
            commensurateSnapRangeDeg: finiteClamped(
                nextDisplay.commensurateSnapRangeDeg, 2, 0, 15
            ),
            manualBondPairs,
            elementBondCutoffs,
            elementRadii,
            elementColors,
            elementVisible,
            imageFramingMode: nextDisplay.imageFramingMode === 'physical' ? 'physical' : 'viewport',
            atomicScalePixelsPerAngstrom: (() => {
                const value = Number(nextDisplay.atomicScalePixelsPerAngstrom);
                return Number.isFinite(value) && value > 0
                    ? Math.max(0.1, Math.min(5000, value))
                    : null;
            })(),
            imageSphereQuality: ['viewport', 'auto', 'low', 'medium', 'high', 'ultra'].includes(
                nextDisplay.imageSphereQuality
            ) ? nextDisplay.imageSphereQuality : 'viewport',
            imageSmoothnessScale: finiteClamped(
                nextDisplay.imageSmoothnessScale, 1, 0.5, 2
            ),
            viewportBackground: nextDisplay.viewportBackground === 'white' ? 'white' : 'dark',
            atomDisplayMode: nextDisplay.atomDisplayMode === '2d' ? '2d' : '3d',
            viewRotationStepDeg: finiteClamped(
                nextDisplay.viewRotationStepDeg, 15, 0.1, 360
            ),
            videoFormat: ['mov', 'avi'].includes(nextDisplay.videoFormat)
                ? nextDisplay.videoFormat
                : 'mov',
            videoFps: finiteClamped(nextDisplay.videoFps, 12, 1, 60),
            supercell
        };
    }

    applyCameraSettings(cameraSettings, { syncScale = true } = {}) {
        if (!cameraSettings || !this.renderer?.camera || !this.renderer?.controls) return;
        const vector = (value, fallback) => Array.isArray(value) && value.length === 3 && value.every(item => Number.isFinite(Number(item)))
            ? value.map(Number)
            : fallback;
        const projection = cameraSettings.projection === 'perspective' ? 'perspective' : 'orthographic';
        this.state.display.projectionMode = projection;
        this.renderer.setProjectionMode(projection);
        const camera = this.renderer.camera;
        const target = vector(cameraSettings.target, [0, 0, 0]);
        const position = vector(cameraSettings.position, [10, 10, 10]);
        const up = vector(cameraSettings.up, [0, 0, 1]);
        camera.position.fromArray(position);
        camera.up.fromArray(up).normalize();
        this.renderer.controls.target.fromArray(target);
        const near = Number(cameraSettings.near);
        const far = Number(cameraSettings.far);
        if (Number.isFinite(near) && near > 0) camera.near = near;
        if (Number.isFinite(far) && far > camera.near) camera.far = far;
        if (camera.isPerspectiveCamera) {
            const fov = Number(cameraSettings.fov);
            if (Number.isFinite(fov) && fov > 1 && fov < 179) camera.fov = fov;
            const zoom = Number(cameraSettings.zoom);
            camera.zoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
        } else if (camera.isOrthographicCamera) {
            const scale = Number(cameraSettings.ortho_scale);
            if (Number.isFinite(scale) && scale > 0) {
                const aspect = Math.max(0.01, this.renderer.container.clientWidth / Math.max(1, this.renderer.container.clientHeight));
                camera.zoom = 1;
                camera.top = scale * 0.5;
                camera.bottom = -scale * 0.5;
                camera.left = -scale * 0.5 * aspect;
                camera.right = scale * 0.5 * aspect;
            }
        }
        camera.lookAt(this.renderer.controls.target);
        camera.updateProjectionMatrix();
        camera.updateMatrixWorld(true);
        if (syncScale) this.syncAtomicScaleFromCamera({ forceInput: true });
        this.renderer.requestRender();
    }

    applyDesignSettings(settings, { render = true } = {}) {
        if (!settings) return;
        const source = settings.settings || settings;
        const nextDisplay = this.reconcileDesignDisplay(source.display || source);
        const requestedAtomicScale = Number(nextDisplay.atomicScalePixelsPerAngstrom);
        this.state.display = {
            ...this.state.display,
            ...this.clonePlain(nextDisplay),
            manualBondPairs: this.clonePlain(nextDisplay.manualBondPairs),
            elementBondCutoffs: this.clonePlain(nextDisplay.elementBondCutoffs),
            elementRadii: this.clonePlain(nextDisplay.elementRadii),
            elementColors: this.clonePlain(nextDisplay.elementColors),
            elementVisible: this.clonePlain(nextDisplay.elementVisible),
            supercell: this.clonePlain(nextDisplay.supercell)
        };
        if ('applyConstraints' in source) this.state.applyConstraints = Boolean(source.applyConstraints);
        if ('antiAliasing' in source) this.state.antiAliasing = Boolean(source.antiAliasing);
        if ('sphereQuality' in source) this.state.sphereQuality = source.sphereQuality || 'auto';
        if ('moveIncrement' in source) this.state.moveIncrement = Number(source.moveIncrement) || 0;
        if ('rotateIncrementDeg' in source) this.state.rotateIncrementDeg = Number(source.rotateIncrementDeg) || 0;
        this.state.imageExportProfile = source.imageExportProfile
            ? this.normalizedImageExportProfile(source.imageExportProfile)
            : null;
        if (this.state.imageExportProfile) {
            this.setImageExportProfile(this.state.imageExportProfile, { syncPreview: false });
        }
        this.syncDesignControls();
        this.renderElementBondControls({ capture: false });
        this.renderElementRadiusControls();
        this.syncDesignControls();
        if (source.camera) this.applyCameraSettings(source.camera, { syncScale: false });
        if (Number.isFinite(requestedAtomicScale) && requestedAtomicScale > 0) {
            this.renderer.setPixelsPerAngstrom(requestedAtomicScale);
        } else {
            this.syncAtomicScaleFromCamera({ forceInput: true });
        }
        if (render) {
            this.renderer.setDisplayOptions(this.state.display);
            this.updateSelectionVisuals();
            this.updateBondModeUI();
            this.updateUI();
        }
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
    }

    showConfirmModal({ title, intro, items, confirmText = 'Yes', cancelText = 'No', danger = false }) {
        const list = items.map(item => `<li>${item}</li>`).join('');
        this.showModal(`
            <h2>${title}</h2>
            <p class="modal-intro">${intro}</p>
            <ul class="confirm-list">${list}</ul>
        `, `
            <button id="modal-cancel-confirm" class="btn">${cancelText}</button>
            <button id="modal-confirm-action" class="btn ${danger ? 'danger' : 'primary'}">${confirmText}</button>
        `);
        return new Promise(resolve => {
            const container = document.getElementById('modal-container');
            let settled = false;
            const cancelOnBackdrop = event => {
                if (event.target?.id === 'modal-container') done(false);
            };
            const done = value => {
                if (settled) return;
                settled = true;
                container?.removeEventListener('pointerdown', cancelOnBackdrop);
                this.closeModal();
                resolve(value);
            };
            document.getElementById('modal-cancel-confirm')?.addEventListener('click', () => done(false), { once: true });
            document.getElementById('modal-confirm-action')?.addEventListener('click', () => done(true), { once: true });
            container?.addEventListener('pointerdown', cancelOnBackdrop);
        });
    }

    confirmFullReset() {
        return this.showConfirmModal({
            title: 'Reset everything?',
            intro: 'This returns the viewer to the loaded starting state.',
            items: [
                'Coordinates: every trajectory frame goes back to the original file.',
                'Cell: any applied supercell returns to the original unit cell.',
                'Visual settings: bonds, radii, grid, axes, quality, and cutoffs return to startup values.',
                'Selection: current selection is cleared.'
            ],
            confirmText: 'Yes, reset all',
            danger: true
        });
    }

    confirmCoordinateReset() {
        return this.showConfirmModal({
            title: 'Reset coordinates?',
            intro: 'This keeps visual settings but restores the physical structure.',
            items: [
                'Coordinates: every trajectory frame returns to its original atom positions.',
                'Cell: the structure returns to the original 1 x 1 x 1 unit cell.',
                'Visual settings kept: bond display, bond cutoffs, atom radii, grid, axes, and rendering quality.',
                'Selection: current selection is cleared.'
            ],
            confirmText: 'Yes, reset coordinates',
            danger: true
        });
    }

    setBusy(message = 'Working...') {
        const overlay = document.getElementById('busy-overlay');
        const text = document.getElementById('busy-message');
        if (text) text.innerText = message;
        overlay?.classList.remove('hidden');
        document.body.dataset.busy = 'true';
    }

    clearBusy() {
        document.getElementById('busy-overlay')?.classList.add('hidden');
        delete document.body.dataset.busy;
    }

    async withBusy(message, task) {
        this.setBusy(message);
        await new Promise(resolve => requestAnimationFrame(() => resolve()));
        try {
            return await task();
        } finally {
            this.clearBusy();
        }
    }

    async setSupercellAsCell() {
        try {
            const reps = this.normalizeSupercellInputs();
            if (reps.every(v => v === 1)) {
                this.toast('Choose a supercell larger than 1 x 1 x 1 first.', 'warning');
                return;
            }
            const data = await this.withBusy(
                `Applying ${reps.join(' x ')} supercell to ${this.state.atoms.metadata.frame_count || 1} frame${(this.state.atoms.metadata.frame_count || 1) > 1 ? 's' : ''}...`,
                () => this.api.applySupercell(this.backendPositionsPayload(), reps, this.state.applyConstraints)
            );
            this.setAtomsData(data, { clearSelection: true });
            ['super-x', 'super-y', 'super-z'].forEach(id => { document.getElementById(id).value = '1'; });
            this.state.display.supercell = [1, 1, 1];
            this.renderer.setDisplayOptions(this.state.display);
            this.toast(`Set ${reps.join(' x ')} supercell as editable cell for all frames.`, 'success');
        } catch (err) {
            this.toast(`Set supercell failed: ${err.message}`, 'error');
        }
    }

    async applyMakeSupercellMatrix() {
        try {
            const matrix = this.parseSupercellMatrix();
            if (this.isIdentityMatrix(matrix)) {
                this.toast('Choose a non-identity make_supercell matrix first.', 'warning');
                return;
            }
            const frameCount = this.state.atoms.metadata.frame_count || 1;
            const data = await this.withBusy(
                `Applying make_supercell matrix to ${frameCount} frame${frameCount > 1 ? 's' : ''}...`,
                () => this.api.applySupercellMatrix(this.backendPositionsPayload(), matrix, this.state.applyConstraints)
            );
            this.setAtomsData(data, { clearSelection: true });
            this.setSupercellMatrixInputs();
            this.toast('Applied make_supercell matrix to all frames.', 'success');
        } catch (err) {
            this.toast(`make_supercell failed: ${err.message}`, 'error');
        }
    }

    copySelection() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        if (!this.state.selected.size) {
            this.toast('No atoms selected to copy.', 'warning');
            return;
        }
        this.pruneSelection();
        const indices = [...this.state.selected].sort((a, b) => a - b);
        if (!indices.length) {
            this.toast('No atoms selected to copy.', 'warning');
            return;
        }
        const positions = indices.map(i => [...this.state.atoms.positions[i]]);
        const symbols = indices.map(i => this.state.atoms.symbols[i]);
        const center = positions.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1], acc[2] + p[2]], [0, 0, 0])
            .map(v => v / positions.length);
        this.state.clipboard = {
            symbols,
            offsets: positions.map(p => [p[0] - center[0], p[1] - center[1], p[2] - center[2]])
        };
        this.toast(`Copied ${symbols.length} atom${symbols.length > 1 ? 's' : ''}.`, 'success');
    }

    async pasteSelection() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        if (!this.state.clipboard) {
            this.toast('Clipboard is empty.', 'warning');
            return;
        }
        const base = this.getSceneCenter();
        const offset = new THREE.Vector3(0.45, 0.45, 0);
        const positions = this.state.clipboard.offsets.map(p => [
            base.x + offset.x + p[0],
            base.y + offset.y + p[1],
            base.z + offset.z + p[2]
        ]);
        try {
            const before = this.state.atoms.positions.length;
            const data = await this.api.addAtoms(this.state.clipboard.symbols, positions);
            this.setAtomsData(data, { clearSelection: true });
            for (let i = before; i < data.positions.length; i++) this.state.selected.add(i);
            this.updateSelectionVisuals();
            this.updateUI();
            this.toast(`Pasted ${positions.length} atom${positions.length > 1 ? 's' : ''}.`, 'success');
        } catch (err) {
            this.toast(`Paste failed: ${err.message}`, 'error');
        }
    }

    async deleteSelection() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        if (!this.state.selected.size) {
            this.toast('No atoms selected to delete.', 'warning');
            return;
        }
        this.pruneSelection();
        const indices = [...this.state.selected].sort((a, b) => a - b);
        if (!indices.length) {
            this.toast('No atoms selected to delete.', 'warning');
            return;
        }
        try {
            const data = await this.api.deleteAtoms(indices);
            this.setAtomsData(data, { clearSelection: true });
            this.toast(`Deleted ${indices.length} atom${indices.length > 1 ? 's' : ''}.`, 'success');
        } catch (err) {
            this.toast(`Delete failed: ${err.message}`, 'error');
        }
    }

    getSceneCenter() {
        if (this.state.selected.size) {
            const c = new THREE.Vector3();
            let count = 0;
            this.state.selected.forEach(i => {
                const p = this.state.atoms.positions[i];
                if (!p) return;
                c.add(new THREE.Vector3(...p));
                count++;
            });
            if (count) return c.divideScalar(count);
        }
        const c = new THREE.Vector3();
        this.state.atoms.positions.forEach(p => c.add(new THREE.Vector3(...p)));
        return c.divideScalar(Math.max(1, this.state.atoms.positions.length));
    }

    cellCenter() {
        const cell = this.state.atoms?.cell || [];
        if (!this.hasUsableCell() || cell.length < 3) return new THREE.Vector3(0, 0, 0);
        return new THREE.Vector3()
            .add(new THREE.Vector3(...cell[0]))
            .add(new THREE.Vector3(...cell[1]))
            .add(new THREE.Vector3(...cell[2]))
            .multiplyScalar(0.5);
    }

    rotationPivotPosition(editableSelection) {
        const mode = this.state.display.rotatePivot || 'selection';
        if (mode === 'origin') return new THREE.Vector3(0, 0, 0);
        if (mode === 'cell') {
            if (!this.hasUsableCell()) {
                this.toast('Unit-cell center pivot requires a defined unit cell. Using selection COM.', 'warning');
            } else {
                return this.cellCenter();
            }
        }
        const pivot = new THREE.Vector3();
        editableSelection.forEach(idx => {
            const p = this.state.atoms.positions[idx];
            pivot.add(new THREE.Vector3(p[0], p[1], p[2]));
        });
        return pivot.divideScalar(Math.max(1, editableSelection.length));
    }

    updateCommensurateStatus(message, state = '') {
        const element = document.getElementById('commensurate-status');
        if (!element) return;
        element.textContent = message;
        if (state) element.dataset.state = state;
        else delete element.dataset.state;
    }

    clearCommensurateRotation({ keepStatus = false } = {}) {
        this.state.commensurateRequestToken += 1;
        this.state.commensurateCandidates = [];
        this.state.commensurateSearch = null;
        this.state.commensurateReferenceDirection = null;
        this.state.commensurateSnappedCandidate = null;
        this.renderer.clearCommensurateGuides?.();
        this.updateCommensurateCandidatesReadout([]);
        if (!keepStatus) {
            this.updateCommensurateStatus('Lock X, Y, or Z during R to scan periodic cell matches.');
        }
    }

    commensurateRotationEnabled() {
        return Boolean(
            this.transform.mode === 'ROTATE'
            && this.state.display.commensurateGuide
            && this.transform.axis
            && this.hasUsableCell()
            && (this.state.atoms?.pbc || []).filter(Boolean).length >= 2
        );
    }

    lockedRotationAxisVector() {
        if (this.transform.axis === 'X') return new THREE.Vector3(1, 0, 0);
        if (this.transform.axis === 'Y') return new THREE.Vector3(0, 1, 0);
        if (this.transform.axis === 'Z') return new THREE.Vector3(0, 0, 1);
        return null;
    }

    commensurateReferenceForSelection(editableSelection, axis) {
        let reference = null;
        let maxLength = 0;
        editableSelection.forEach(index => {
            const position = this.state.originalPositions[index];
            if (!position) return;
            const offset = new THREE.Vector3(...position).sub(this.transform.pivot);
            offset.addScaledVector(axis, -offset.dot(axis));
            const length = offset.length();
            if (length > maxLength) {
                maxLength = length;
                reference = offset.normalize();
            }
        });
        if (!reference || maxLength < 1e-5) {
            reference = Math.abs(axis.z) < 0.9
                ? new THREE.Vector3(0, 0, 1).cross(axis).normalize()
                : new THREE.Vector3(1, 0, 0);
        }
        this.state.commensurateGuideRadius = Math.max(3.2, maxLength * 1.18);
        return reference;
    }

    async prepareCommensurateRotation(editableSelection = [...this.state.selected]) {
        const token = ++this.state.commensurateRequestToken;
        this.state.commensurateCandidates = [];
        this.state.commensurateSearch = null;
        this.state.commensurateSnappedCandidate = null;
        this.renderer.clearCommensurateGuides?.();

        if (!this.state.display.commensurateGuide) {
            this.updateCommensurateStatus('Commensurate cell guide is disabled.');
            return;
        }
        if (this.transform.mode !== 'ROTATE' || !this.transform.axis) {
            this.updateCommensurateStatus('Lock X, Y, or Z during R to scan periodic cell matches.');
            return;
        }
        if (!this.hasUsableCell() || (this.state.atoms?.pbc || []).filter(Boolean).length < 2) {
            this.updateCommensurateStatus('A defined cell with at least two periodic directions is required.', 'warning');
            return;
        }
        const axis = this.lockedRotationAxisVector();
        if (!axis) return;
        this.state.commensurateReferenceDirection = this.commensurateReferenceForSelection(editableSelection, axis);
        this.updateCommensurateStatus('Scanning integer periodic-cell boundaries...', 'ready');
        try {
            const result = await this.api.commensurateAngles(
                this.transform.axis,
                this.state.display.commensurateMaxIndex,
                this.state.display.commensurateStrainTolerance
            );
            if (token !== this.state.commensurateRequestToken || this.transform.mode !== 'ROTATE') return;
            this.state.commensurateSearch = result;
            this.state.commensurateCandidates = Array.isArray(result.candidates) ? result.candidates : [];
            const tolerance = (Number(result.strain_tolerance || 0) * 100).toFixed(2);
            const family = String(result.lattice_family || '2D').replace('-', ' ');
            const summary = `${family}: ${this.state.commensurateCandidates.length} matches, boundary strain <= ${tolerance}%.`;
            this.updateCommensurateStatus(result.warning ? `${summary} ${result.warning}` : summary, result.warning ? 'warning' : 'ready');
            this.applyTransformPreview();
        } catch (error) {
            if (token !== this.state.commensurateRequestToken) return;
            this.updateCommensurateStatus(error.message, 'warning');
        }
    }

    candidateInstanceNearAngle(candidate, angleDeg) {
        const base = Number(candidate.angle_deg);
        const turns = Math.round((angleDeg - base) / 360);
        const targetAngleDeg = base + turns * 360;
        return {
            ...candidate,
            targetAngleDeg,
            deltaDeg: targetAngleDeg - angleDeg
        };
    }

    nearestCommensurateCandidate(angle) {
        if (!this.commensurateRotationEnabled() || !this.state.commensurateCandidates.length) return null;
        const angleDeg = THREE.MathUtils.radToDeg(angle);
        const identityAngle = Math.round(angleDeg / 360) * 360;
        const identity = {
            angle_deg: 0,
            area: 1,
            deltaDeg: identityAngle - angleDeg,
            family: 'identity',
            identity: true,
            magic_reference: false,
            strain: 0,
            targetAngleDeg: identityAngle
        };
        return [identity, ...this.state.commensurateCandidates
            .map(candidate => this.candidateInstanceNearAngle(candidate, angleDeg))
        ].sort((first, second) => Math.abs(first.deltaDeg) - Math.abs(second.deltaDeg))[0] || null;
    }

    snapCommensurateAngle(angle) {
        this.state.commensurateSnappedCandidate = null;
        const nearest = this.nearestCommensurateCandidate(angle);
        if (!nearest || !this.state.display.commensurateSnap) return angle;
        const snapRange = Math.max(0, Number(this.state.display.commensurateSnapRangeDeg || 0));
        if (Math.abs(nearest.deltaDeg) > snapRange) return angle;
        this.state.commensurateSnappedCandidate = nearest;
        return THREE.MathUtils.degToRad(nearest.targetAngleDeg);
    }

    updateCommensurateAngleStatus(angle) {
        if (!this.commensurateRotationEnabled() || !this.state.commensurateCandidates.length) return;
        const nearest = this.nearestCommensurateCandidate(angle);
        if (!nearest) return;
        const snapped = this.state.commensurateSnappedCandidate;
        const candidate = snapped || nearest;
        const label = snapped ? 'Snapped' : 'Nearest';
        const delta = snapped ? '' : `, delta ${Math.abs(nearest.deltaDeg).toFixed(3)} deg`;
        const warning = this.state.commensurateSearch?.warning
            ? ` ${this.state.commensurateSearch.warning}`
            : '';
        this.updateCommensurateStatus(
            `${label}: ${candidate.targetAngleDeg.toFixed(6)} deg, boundary strain ${(candidate.strain * 100).toFixed(4)}%, N=${candidate.area}${delta}.${warning}`,
            snapped ? 'snap' : (warning ? 'warning' : 'ready')
        );
    }

    commensurateGuideCandidates(angle) {
        if (!this.commensurateRotationEnabled() || !this.state.commensurateCandidates.length) return [];
        const angleDeg = THREE.MathUtils.radToDeg(angle);
        const active = this.state.commensurateSnappedCandidate;
        const ranked = this.state.commensurateCandidates
            .map(candidate => this.candidateInstanceNearAngle(candidate, angleDeg))
            .sort((first, second) => Math.abs(first.deltaDeg) - Math.abs(second.deltaDeg));
        const chosen = [];
        const addCandidate = candidate => {
            if (!candidate || candidate.identity) return;
            const displayAngle = candidate.targetAngleDeg;
            const isActive = Boolean(active) && Math.abs(displayAngle - active.targetAngleDeg) < 1e-5;
            const duplicate = chosen.some(item => Math.abs(item.targetAngleDeg - displayAngle) < 1e-5);
            if (duplicate) return;
            const separated = chosen.every(item => Math.abs(item.targetAngleDeg - displayAngle) >= 1.35);
            if (!isActive && !candidate.magic_reference && !separated) return;
            chosen.push(candidate);
        };

        addCandidate(active);
        addCandidate(ranked[0]);
        addCandidate(ranked.find(candidate => candidate.magic_reference));
        for (const candidate of ranked) {
            addCandidate(candidate);
            if (chosen.length >= 7) break;
        }
        const nearest = this.nearestCommensurateCandidate(angle);
        return chosen.slice(0, 7).map(candidate => {
            const isActive = Boolean(active) && Math.abs(candidate.targetAngleDeg - active.targetAngleDeg) < 1e-5;
            const isPrimary = Boolean(nearest)
                && Math.abs(candidate.targetAngleDeg - nearest.targetAngleDeg) < 1e-5;
            const prefix = isActive ? 'SNAP ' : candidate.magic_reference ? 'TBG ' : '';
            return {
                ...candidate,
                angle_deg: candidate.targetAngleDeg,
                active: isActive,
                primary: isPrimary,
                label: isActive || isPrimary
                    ? `${prefix}${candidate.targetAngleDeg.toFixed(2)} deg`
                    : null
            };
        });
    }

    updateCommensurateCandidatesReadout(candidates) {
        const container = document.getElementById('commensurate-candidates-readout');
        const values = document.getElementById('commensurate-candidates-values');
        if (!container || !values) return;
        if (!candidates?.length) {
            delete container.dataset.signature;
            values.replaceChildren();
            container.classList.add('hidden');
            return;
        }
        const signature = candidates.map(candidate => [
            Number(candidate.angle_deg).toFixed(5),
            candidate.active ? 'a' : candidate.magic_reference ? 'm' : candidate.primary ? 'p' : ''
        ].join(':')).join('|');
        if (container.dataset.signature === signature) return;
        container.dataset.signature = signature;
        values.replaceChildren();
        candidates.forEach(candidate => {
            const chip = document.createElement('span');
            chip.className = 'commensurate-candidate-chip';
            if (candidate.active) chip.classList.add('active');
            else if (candidate.magic_reference) chip.classList.add('magic');
            else if (candidate.primary) chip.classList.add('primary');
            chip.textContent = `${Number(candidate.angle_deg).toFixed(2)} deg`;
            chip.title = `Boundary strain ${(Number(candidate.strain) * 100).toFixed(4)}%; N=${candidate.area}`;
            values.appendChild(chip);
        });
        container.classList.remove('hidden');
    }

    renderCommensurateRotationGuides(angle) {
        const axis = this.lockedRotationAxisVector();
        const reference = this.state.commensurateReferenceDirection;
        const candidates = this.commensurateGuideCandidates(angle);
        if (!axis || !reference || !candidates.length) {
            this.renderer.clearCommensurateGuides?.();
            this.updateCommensurateCandidatesReadout([]);
            return;
        }
        this.updateCommensurateCandidatesReadout(candidates);
        this.renderer.setCommensurateGuides?.({
            pivot: this.transform.pivot.toArray(),
            axis: axis.toArray(),
            reference: reference.toArray(),
            radius: this.state.commensurateGuideRadius,
            baselineActive: Boolean(this.state.commensurateSnappedCandidate?.identity),
            candidates
        });
    }

    setupWebSocket() {
        if (!this.sessionId) return;
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${protocol}://${window.location.host}/ws/${this.sessionId}`);
        this.ws = ws;
        const closeSocket = () => {
            try {
                if (this.ws && this.ws.readyState <= WebSocket.OPEN) this.ws.close(1000, 'page closing');
            } catch {
                // Page teardown path; ignore browser-specific close races.
            }
        };
        window.addEventListener('pagehide', closeSocket, { once: true });
        window.addEventListener('beforeunload', closeSocket, { once: true });
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'relax_step') {
                this.state.atoms.positions = msg.positions;
                this.state.originalPositions = msg.positions.map(p => [...p]);
                this.appendRelaxFrame(msg.positions);
                this.renderer.updatePositions(msg.positions);
                const energy = document.getElementById('val-energy');
                const fmax = document.getElementById('val-fmax');
                if (energy) energy.innerText = msg.energy.toFixed(6);
                if (fmax) fmax.innerText = msg.fmax.toFixed(6);
            }
            if (msg.type === 'relax_finished') {
                this.state.isRelaxing = false;
                if (Array.isArray(msg.positions)) {
                    this.appendRelaxFrame(msg.positions, { force: this.relaxFrameCount() <= 1 });
                    this.state.atoms.positions = msg.positions;
                    this.state.originalPositions = msg.positions.map(p => [...p]);
                    this.renderer.updatePositions(msg.positions);
                } else if (this.state.atoms?.positions?.length) {
                    this.appendRelaxFrame(this.state.atoms.positions, { force: this.relaxFrameCount() <= 1 });
                }
                this.state.relaxTrajectory.finished = true;
                this.toast(`Relax ${msg.status}.`, msg.status === 'error' ? 'error' : 'success');
                this.updateUI();
                this.refresh().then(() => {
                    if (this.state.atoms?.positions?.length) {
                        this.appendRelaxFrame(this.state.atoms.positions, { force: this.relaxFrameCount() <= 1 });
                    }
                    this.updateTrajectoryUI();
                });
            }
        };
    }

    downloadBlob(blob, filename, mimeType = 'application/octet-stream') {
        const fileBlob = blob?.type === mimeType ? blob : new Blob([blob], { type: mimeType });
        const url = URL.createObjectURL(fileBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.rel = 'noopener';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            URL.revokeObjectURL(url);
            a.remove();
        }, 1200);
    }

    downloadDataUrl(dataUrl, filename) {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = filename;
        a.rel = 'noopener';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => a.remove(), 1200);
    }

    filePickerTypes(filename, mimeType) {
        const lower = filename.toLowerCase();
        if (lower.endsWith('.vase')) {
            return [{ description: 'v_ase project', accept: { 'application/vnd.v-ase.project+zip': ['.vase'] } }];
        }
        if (lower.endsWith('.json')) {
            return [{ description: 'JSON settings', accept: { 'application/json': ['.json'] } }];
        }
        if (lower.endsWith('.py')) {
            return [{ description: 'Python script', accept: { 'text/x-python': ['.py'] } }];
        }
        if (lower.endsWith('.3dm')) {
            return [{ description: 'Rhino 3DM scene', accept: { 'model/vnd.3dm': ['.3dm'] } }];
        }
        if (lower.endsWith('.zip')) {
            return [{ description: 'OBJ scene bundle', accept: { 'application/zip': ['.zip'] } }];
        }
        if (lower.endsWith('.pkl') || lower.endsWith('.pickle')) {
            return [{ description: 'Pickle file', accept: { 'application/octet-stream': ['.pkl', '.pickle'] } }];
        }
        if (lower.endsWith('.webm')) {
            return [{ description: 'WebM video', accept: { 'video/webm': ['.webm'] } }];
        }
        if (lower.endsWith('.mov')) {
            return [{ description: 'QuickTime movie', accept: { 'video/quicktime': ['.mov'] } }];
        }
        if (lower.endsWith('.avi')) {
            return [{ description: 'AVI movie', accept: { 'video/x-msvideo': ['.avi'] } }];
        }
        if (lower.endsWith('.png')) {
            return [{ description: 'PNG image', accept: { 'image/png': ['.png'] } }];
        }
        return [{ description: 'v_ase export', accept: { [mimeType]: ['.vasp', '.poscar', '.txt'] } }];
    }

    async savePreparedBlob(blob, filename, mimeType = 'application/octet-stream') {
        let writable = null;
        const canUseSavePicker = window.showSaveFilePicker && window.isSecureContext && !navigator.webdriver;
        if (canUseSavePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: this.filePickerTypes(filename, mimeType)
                });
                writable = await handle.createWritable();
            } catch (err) {
                if (err?.name === 'AbortError') return false;
                console.warn('showSaveFilePicker failed; falling back to browser download.', err);
            }
        }
        if (writable) {
            await writable.write(blob);
            await writable.close();
            return true;
        }
        this.downloadBlob(blob, filename, mimeType);
        return true;
    }

    async saveBlobFromAction(action, filename, mimeType = 'application/octet-stream', busyMessage = 'Preparing export...') {
        const blob = await this.withBusy(busyMessage, action);
        return await this.savePreparedBlob(blob, filename, mimeType);
    }

    closeModal() {
        document.getElementById('modal-container')?.classList.add('hidden');
    }

    showModal(contentHtml, actionsHtml = '<button id="modal-close" class="btn">Close</button>') {
        const container = document.getElementById('modal-container');
        const content = document.getElementById('modal-content');
        const actions = document.querySelector('#modal-container .modal-actions');
        if (!container || !content || !actions) return;
        content.innerHTML = contentHtml;
        actions.innerHTML = actionsHtml;
        container.classList.remove('hidden');
        actions.querySelector('#modal-close')?.addEventListener('click', () => this.closeModal());
    }

    formatFileSize(bytes) {
        const value = Number(bytes) || 0;
        if (value < 1024) return `${value} B`;
        if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
        if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
        return `${(value / 1024 ** 3).toFixed(2)} GB`;
    }

    chooseStructureFile() {
        const input = document.getElementById('structure-file');
        if (!input) return;
        input.value = '';
        input.click();
    }

    showOpenFileModal(file) {
        this.showModal(`
            <h2>Open File</h2>
            <div class="open-file-summary">
                <strong id="open-file-name"></strong>
                <span id="open-file-size"></span>
            </div>
            <div class="export-grid">
                <label for="open-file-format">Reader</label>
                <select id="open-file-format">
                    <option value="" selected>Auto detect</option>
                    <option value="poscar">POSCAR / CONTCAR</option>
                    <option value="xdatcar">XDATCAR</option>
                    <option value="vasprun.xml">vasprun.xml</option>
                    <option value="lammpstrj">LAMMPS trajectory</option>
                    <option value="data">LAMMPS data</option>
                    <option value="traj">ASE trajectory</option>
                    <option value="xyz">XYZ</option>
                    <option value="extxyz">Extended XYZ</option>
                    <option value="vase">v_ase project</option>
                </select>
                <label for="open-file-index">Frames</label>
                <input id="open-file-index" type="text" value=":" autocomplete="off" spellcheck="false">
            </div>
            <p class="modal-intro">Use <strong>:</strong> for all frames, <strong>-1</strong> for the last frame, or an integer frame index.</p>
        `, `
            <button id="open-file-cancel" class="btn">Cancel</button>
            <button id="open-file-confirm" class="btn primary">Open</button>
        `);
        const name = document.getElementById('open-file-name');
        const size = document.getElementById('open-file-size');
        if (name) {
            name.textContent = file.name;
            name.title = file.name;
        }
        if (size) size.textContent = this.formatFileSize(file.size);
        document.getElementById('open-file-cancel')?.addEventListener('click', () => this.closeModal(), { once: true });
        document.getElementById('open-file-confirm')?.addEventListener('click', async () => {
            const inputFormat = document.getElementById('open-file-format')?.value || '';
            const index = document.getElementById('open-file-index')?.value.trim() || ':';
            this.closeModal();
            await this.loadStructureFile(file, inputFormat, index);
        }, { once: true });
    }

    async loadStructureFile(file, inputFormat = '', index = ':') {
        try {
            this.stopPlayback();
            if (this.transform.mode !== 'IDLE') this.cancelTransform();
            const hadLoadedAtoms = this.hasLoadedAtoms();
            let inheritedSettings = null;
            if (hadLoadedAtoms) {
                try {
                    this.applyDisplayOptions();
                } catch {
                    // Keep the last valid manual topology while preserving all
                    // other committed visual controls during a document swap.
                    this.captureBondSettingsFromControls();
                }
                inheritedSettings = this.designSettingsSnapshot();
            }
            const data = await this.withBusy(
                `Reading ${file.name}...`,
                () => this.api.loadStructureFile(file, inputFormat, index)
            );
            const isProject = data.loaded_file?.kind === 'project' || Boolean(data.project);
            const projectSettings = data.project?.settings || data.metadata?.config?.initial_design_settings;
            const settings = isProject ? projectSettings : inheritedSettings;
            this.state.typeOrder = [];
            this.state.trajectoryBinaryCache = null;
            this.state.trajectoryBinaryPromise = null;
            this.state.relaxTrajectory = { frames: [], frame: 0, sourceFrame: 0, active: false, finished: false };
            this.renderer.needsInitialCameraFit = !settings?.camera;
            this.setAtomsData(data, { clearSelection: true, preserveDisplay: !isProject });
            if (settings) {
                this.applyDesignSettings(settings);
                this.initialDesignSettings = isProject
                    ? this.clonePlain(settings)
                    : this.designSettingsSnapshot();
            } else {
                this.initialDesignSettings = this.designSettingsSnapshot();
            }
            const frameCount = data.metadata?.frame_count || 1;
            this.toast(
                `Opened ${data.loaded_file?.filename || file.name}${frameCount > 1 ? ` (${frameCount} frames)` : ''}.`,
                'success'
            );
        } catch (err) {
            this.toast(`Open file failed: ${err.message}`, 'error');
        }
    }

    showShortcutsModal() {
        this.showModal(`
            <h2>Shortcuts</h2>
            <div class="shortcut-grid">
                <span>Left click</span><label>Select / confirm transform</label>
                <span>Shift + click</span><label>Add or remove selection</label>
                <span>Left drag</span><label>Box select</label>
                <span>Middle drag</span><label>Orbit viewport</label>
                <span>Shift + middle drag</span><label>Pan viewport</label>
                <span>Space</span><label>Play or pause trajectory</label>
                <span>Tab</span><label>Open control panel while it is collapsed</label>
                <span>G</span><label>Move selected atoms or Sun handle</label>
                <span>R</span><label>Rotate selected atoms or Sun direction</label>
                <span>Sun source + G</span><label>Move source and target together</label>
                <span>Sun target + G</span><label>Move target only</label>
                <span>Sun handle + R</span><label>Rotate target around source</label>
                <span>X / Y / Z</span><label>Align view in select mode</label>
                <span>X / Y / Z</span><label>Lock transform axis in G/R mode</label>
                <span>Enter</span><label>Confirm transform</label>
                <span>Esc</span><label>Cancel transform, or close the open control panel and return focus to the viewport</label>
                <span>Ctrl+C / V / Z</span><label>Copy, paste, undo</label>
                <span>Delete</span><label>Delete selected atoms</label>
            </div>
            <h3 class="help-section-title">Geometry Export</h3>
            <div class="help-save-grid">
                <strong>Rhino 3DM (.3dm)</strong>
                <span>Editable instanced atoms and bonds, optional unit-cell layers, and saved camera views in Angstrom units. Requires: python -m pip install "v_ase-gui[rhino]"</span>
                <strong>OBJ Bundle (.zip)</strong>
                <span>Dependency-free static geometry with separately named atoms and bonds. Extract the OBJ, MTL, and camera/metadata JSON into the same directory.</span>
                <strong>Blender Script (.py)</strong>
                <span>Best for camera, Sun lighting, trajectory animation, bonds, materials, and optimized instancing in Blender.</span>
            </div>
            <h3 class="help-section-title">Saving</h3>
            <div class="help-save-grid">
                <strong>ASE Pickle (.pkl)</strong>
                <span>Current ASE Atoms data for Python: coordinates, labels, cell, PBC, constraints, arrays, and valid SinglePointCalculator results. Visual settings are excluded.</span>
                <strong>Visual Settings (.json)</strong>
                <span>Reusable display preset: bonds, appearance, camera, lighting, quality, and supercell preview. Atomic coordinates are not included.</span>
                <strong>v_ase Project (.vase)</strong>
                <span>Complete working state: structures or trajectory, current frame, coordinates, cell, constraints, labels, cached results, and visual setup.</span>
            </div>
        `);
    }

    imageOutputDimensions() {
        const width = Math.max(256, parseInt(document.getElementById('image-width')?.value || '1920', 10));
        const height = Math.max(256, parseInt(document.getElementById('image-height')?.value || '1080', 10));
        return { width, height };
    }

    defaultImageExportOptions() {
        const display = this.state.display;
        const pixelsPerAngstrom = Math.max(0.1, Math.min(5000,
            Number(this.renderer.currentPixelsPerAngstrom()) || 100));
        return {
            transparentBackground: false,
            backgroundColor: '#ffffff',
            includeGrid: display.showGrid !== false,
            includeAxes: display.showAxes !== false,
            includeCell: display.exportIncludeCell !== false,
            scaleMode: display.imageFramingMode === 'physical' ? 'physical' : 'viewport',
            pixelsPerAngstrom,
            sphereQuality: display.imageSphereQuality || 'viewport',
            sphereQualityScale: Math.max(0.5, Math.min(2,
                Number(display.imageSmoothnessScale) || 1)),
            renderMode: display.lightingMode || 'modeling',
            sunIntensity: Number(display.sunIntensity ?? 2.2),
            sunPosition: [...(display.sunPosition || [8, -10, 14])],
            sunTarget: [...(display.sunTarget || [0, 0, 0])]
        };
    }

    imagePreviewOptions() {
        return { ...this.currentImageExportProfile().options };
    }

    normalizedImageExportProfile(profile = null) {
        const fallback = this.defaultImageExportOptions();
        const source = profile?.options || {};
        const dimensions = profile
            ? { width: profile.width, height: profile.height }
            : this.imageOutputDimensions();
        const renderModeSelection = ['current', 'modeling', 'studio', 'studio-shadow'].includes(
            source.renderModeSelection
        ) ? source.renderModeSelection : 'current';
        const renderMode = renderModeSelection === 'current'
            ? (this.state.display.lightingMode || 'modeling')
            : renderModeSelection;
        const vector = (value, defaultValue) => (
            Array.isArray(value) && value.length === 3 && value.every(item => Number.isFinite(Number(item)))
                ? value.map(Number)
                : [...defaultValue]
        );
        return {
            kind: 'image',
            width: Math.max(256, Math.round(Number(dimensions.width) || 1920)),
            height: Math.max(256, Math.round(Number(dimensions.height) || 1080)),
            options: {
                transparentBackground: source.transparentBackground ?? fallback.transparentBackground,
                backgroundColor: source.backgroundColor || fallback.backgroundColor,
                includeGrid: source.includeGrid ?? fallback.includeGrid,
                includeAxes: source.includeAxes ?? fallback.includeAxes,
                includeCell: source.includeCell ?? fallback.includeCell,
                scaleMode: source.scaleMode === 'physical' ? 'physical' : 'viewport',
                pixelsPerAngstrom: Math.max(0.1, Math.min(5000,
                    Number(source.pixelsPerAngstrom) || fallback.pixelsPerAngstrom)),
                sphereQuality: ['viewport', 'auto', 'low', 'medium', 'high', 'ultra'].includes(
                    source.sphereQuality
                ) ? source.sphereQuality : fallback.sphereQuality,
                sphereQualityScale: Math.max(0.5, Math.min(2,
                    Number(source.sphereQualityScale) || fallback.sphereQualityScale)),
                renderModeSelection,
                renderMode,
                sunIntensity: Math.max(0, Number(source.sunIntensity ?? fallback.sunIntensity)),
                sunPosition: vector(source.sunPosition, fallback.sunPosition),
                sunTarget: vector(source.sunTarget, fallback.sunTarget)
            }
        };
    }

    currentImageExportProfile() {
        const profile = this.normalizedImageExportProfile(this.state.imageExportProfile);
        this.state.imageExportProfile = profile;
        return profile;
    }

    setImageExportProfile(profile, { syncInputs = true, syncPreview = true } = {}) {
        const normalized = this.normalizedImageExportProfile(profile);
        this.state.imageExportProfile = normalized;
        this.state.exportPreviewProfile = null;
        if (syncInputs) {
            const widthInput = document.getElementById('image-width');
            const heightInput = document.getElementById('image-height');
            if (widthInput) widthInput.value = `${normalized.width}`;
            if (heightInput) heightInput.value = `${normalized.height}`;
        }
        if (syncPreview && this.state.exportPreviewEnabled) this.syncImageExportPreview();
        return normalized;
    }

    syncImageExportPreview() {
        const profile = this.state.exportPreviewProfile || this.currentImageExportProfile();
        const { width, height } = profile;
        const enabled = Boolean(this.state.exportPreviewEnabled && this.state.atoms?.positions?.length);
        this.renderer.setExportPreview({
            enabled,
            width,
            height,
            options: profile.options
        });
        const button = document.getElementById('btn-preview-image');
        if (button) {
            button.setAttribute('aria-pressed', enabled ? 'true' : 'false');
            button.title = enabled ? 'Hide export image preview' : 'Preview the exact export image area';
        }
    }

    showExportImageModal() {
        this.state.exportPreviewProfile = null;
        const initialProfile = this.currentImageExportProfile();
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        const { width, height, options: imageOptions } = initialProfile;
        const position = imageOptions.sunPosition;
        const target = imageOptions.sunTarget;
        const scaleMode = imageOptions.scaleMode;
        const pixelsPerAngstrom = imageOptions.pixelsPerAngstrom;
        const sphereQuality = imageOptions.sphereQuality;
        const smoothnessScale = imageOptions.sphereQualityScale;
        const selected = (value, current) => value === current ? 'selected' : '';
        this.showModal(`
            <h2>Export Image</h2>
            <div class="export-image-columns">
                <div class="export-image-column">
                <div class="export-grid">
                    <label for="export-width">Width</label>
                    <input type="number" id="export-width" value="${width}" min="256" step="128">
                    <label for="export-height">Height</label>
                    <input type="number" id="export-height" value="${height}" min="256" step="128">
                </div>
                <label class="check-row" for="export-transparent">
                    <span>Transparent background</span>
                    <input type="checkbox" id="export-transparent" ${imageOptions.transparentBackground ? 'checked' : ''}>
                </label>
                <label class="check-row" for="export-grid">
                    <span>Include grid</span>
                    <input type="checkbox" id="export-grid" ${imageOptions.includeGrid ? 'checked' : ''}>
                </label>
                <label class="check-row" for="export-axes">
                    <span>Include axes</span>
                    <input type="checkbox" id="export-axes" ${imageOptions.includeAxes ? 'checked' : ''}>
                </label>
                <label class="check-row" for="export-cell">
                    <span>Include unit cell</span>
                    <input type="checkbox" id="export-cell" ${imageOptions.includeCell ? 'checked' : ''}>
                </label>
                <div class="export-render-section">
                    <div class="export-section-title">Framing</div>
                    <div class="export-grid">
                        <label for="export-framing-mode">Frame</label>
                        <select id="export-framing-mode">
                            <option value="viewport" ${selected('viewport', scaleMode)}>Current viewport</option>
                            <option value="physical" ${selected('physical', scaleMode)}>Atomic scale from View</option>
                        </select>
                    </div>
                    <p id="export-scale-note" class="export-note"></p>
                </div>
                <div class="export-render-section">
                    <div class="export-section-title">Atom surface</div>
                    <div class="export-grid">
                        <label for="export-sphere-quality">Atom smoothness</label>
                        <select id="export-sphere-quality">
                            <option value="viewport" ${selected('viewport', sphereQuality)}>Viewport setting</option>
                            <option value="auto" ${selected('auto', sphereQuality)}>Auto</option>
                            <option value="low" ${selected('low', sphereQuality)}>Low</option>
                            <option value="medium" ${selected('medium', sphereQuality)}>Medium</option>
                            <option value="high" ${selected('high', sphereQuality)}>High</option>
                            <option value="ultra" ${selected('ultra', sphereQuality)}>Ultra</option>
                        </select>
                        <label for="export-smoothness-scale">Smoothness scale</label>
                        <input type="number" id="export-smoothness-scale" value="${smoothnessScale.toFixed(2)}" min="0.5" max="2" step="0.1">
                    </div>
                    <p id="export-smoothness-note" class="export-note"></p>
                </div>
                </div>
                <div class="export-image-column">
                <div class="export-render-section">
                <div class="export-section-title">Rendering</div>
                <div class="export-grid">
                    <label for="export-render-mode">Renderer</label>
                    <select id="export-render-mode">
                        <option value="current" ${selected('current', imageOptions.renderModeSelection)}>Viewport setting</option>
                        <option value="modeling" ${selected('modeling', imageOptions.renderModeSelection)}>Modeling</option>
                        <option value="studio" ${selected('studio', imageOptions.renderModeSelection)}>Studio Sun</option>
                        <option value="studio-shadow" ${selected('studio-shadow', imageOptions.renderModeSelection)}>Sun + Soft Shadow</option>
                    </select>
                    <label for="export-sun-intensity">Brightness</label>
                    <input type="number" id="export-sun-intensity" value="${Number(imageOptions.sunIntensity).toFixed(2)}" min="0" max="8" step="0.05">
                </div>
                <div class="export-light-vector">
                    <span>Sun position</span>
                    <div>
                        ${position.map((value, index) => `<input type="number" id="export-sun-position-${index}" value="${Number(value).toFixed(3)}" step="0.25" aria-label="Export Sun position ${index + 1}">`).join('')}
                    </div>
                </div>
                <div class="export-light-vector">
                    <span>Direction target</span>
                    <div>
                        ${target.map((value, index) => `<input type="number" id="export-sun-target-${index}" value="${Number(value).toFixed(3)}" step="0.25" aria-label="Export Sun target ${index + 1}">`).join('')}
                    </div>
                </div>
                </div>
                </div>
            </div>
        `, `
            <button id="modal-close" class="btn">Cancel</button>
            <button id="modal-export-image" class="btn primary">Export</button>
        `);
        document.querySelector('#modal-container .modal')?.classList.add('export-image-modal');

        const readImageProfile = () => {
            const renderModeSelection = document.getElementById('export-render-mode')?.value || 'current';
            return this.normalizedImageExportProfile({
                width: Math.max(256, parseInt(document.getElementById('export-width')?.value || `${width}`, 10)),
                height: Math.max(256, parseInt(document.getElementById('export-height')?.value || `${height}`, 10)),
                options: {
                    transparentBackground: Boolean(document.getElementById('export-transparent')?.checked),
                    backgroundColor: '#ffffff',
                    includeGrid: Boolean(document.getElementById('export-grid')?.checked),
                    includeAxes: Boolean(document.getElementById('export-axes')?.checked),
                    includeCell: Boolean(document.getElementById('export-cell')?.checked),
                    scaleMode: document.getElementById('export-framing-mode')?.value === 'physical'
                        ? 'physical'
                        : 'viewport',
                    pixelsPerAngstrom: Math.max(0.1, Math.min(5000,
                        Number(this.renderer.currentPixelsPerAngstrom()) || pixelsPerAngstrom)),
                    sphereQuality: document.getElementById('export-sphere-quality')?.value || 'viewport',
                    sphereQualityScale: Math.max(0.5, Math.min(2,
                        Number(document.getElementById('export-smoothness-scale')?.value) || smoothnessScale)),
                    renderModeSelection,
                    renderMode: renderModeSelection === 'current'
                        ? (this.state.display.lightingMode || 'modeling')
                        : renderModeSelection,
                    sunIntensity: Math.max(0,
                        Number(document.getElementById('export-sun-intensity')?.value) || 0),
                    sunPosition: [0, 1, 2].map(index =>
                        Number(document.getElementById(`export-sun-position-${index}`)?.value) || 0),
                    sunTarget: [0, 1, 2].map(index =>
                        Number(document.getElementById(`export-sun-target-${index}`)?.value) || 0)
                }
            });
        };

        const updateExportSummary = () => {
            const profile = this.setImageExportProfile(readImageProfile());
            const mode = profile.options.scaleMode;
            const outputWidth = profile.width;
            const outputHeight = profile.height;
            const ppa = profile.options.pixelsPerAngstrom;
            const scaleNote = document.getElementById('export-scale-note');
            if (scaleNote) {
                const projectionNote = this.state.display.projectionMode === 'perspective'
                    ? 'Perspective scale is defined at the camera target plane.'
                    : 'Orthographic scale is uniform at every depth.';
                scaleNote.textContent = mode === 'physical'
                    ? `Uses View > Atomic scale (${ppa.toFixed(2)} px/Å). Frame span: ${(outputWidth / ppa).toFixed(2)} Å × ${(outputHeight / ppa).toFixed(2)} Å. ${projectionNote}`
                    : 'Uses the live camera direction and scale, then crops its projection to fill the requested output aspect ratio. Preview Area shows the exact exported region.';
            }

            const qualityInput = document.getElementById('export-sphere-quality');
            const quality = qualityInput?.value === 'viewport'
                ? (this.state.sphereQuality || 'auto')
                : (qualityInput?.value || 'auto');
            const multiplier = Math.max(0.5, Math.min(2,
                Number(document.getElementById('export-smoothness-scale')?.value) || smoothnessScale));
            const segments = this.renderer.sphereQualitySegmentsFor(
                quality,
                this.state.atoms?.positions?.length || 0,
                multiplier
            );
            const smoothnessNote = document.getElementById('export-smoothness-note');
            if (smoothnessNote) {
                smoothnessNote.textContent = `${segments} sphere segments at ${multiplier.toFixed(2)}× in both Preview Area and the exported image.`;
            }
        };
        [
            'export-width', 'export-height', 'export-smoothness-scale',
            'export-sun-intensity', 'export-sun-position-0', 'export-sun-position-1',
            'export-sun-position-2', 'export-sun-target-0', 'export-sun-target-1',
            'export-sun-target-2'
        ]
            .forEach(id => document.getElementById(id)?.addEventListener('input', updateExportSummary));
        [
            'export-transparent', 'export-grid', 'export-axes', 'export-cell', 'export-framing-mode',
            'export-sphere-quality', 'export-render-mode'
        ]
            .forEach(id => document.getElementById(id)?.addEventListener('change', updateExportSummary));
        updateExportSummary();

        document.getElementById('modal-export-image')?.addEventListener('click', () => {
            try {
                const profile = this.setImageExportProfile(readImageProfile());
                const { width: exportWidth, height: exportHeight, options } = profile;
                Object.assign(this.state.display, {
                    imageFramingMode: options.scaleMode,
                    atomicScalePixelsPerAngstrom: options.pixelsPerAngstrom,
                    imageSphereQuality: options.sphereQuality,
                    imageSmoothnessScale: options.sphereQualityScale
                });
                const dataUrl = this.renderer.exportPNG(exportWidth, exportHeight, options);
                this.syncImageExportPreview();
                this.downloadDataUrl(dataUrl, `v_ase-${exportWidth}x${exportHeight}.png`);
                this.closeModal();
                this.toast('Image export started.', 'success');
            } catch (err) {
                this.toast(`Image export failed: ${err.message}`, 'error');
            }
        });
    }

    showExportVideoModal() {
        const meta = this.state.atoms?.metadata || {};
        const count = meta.frame_count || 1;
        if (count <= 1) {
            this.toast('Export Video is available only for trajectory files.', 'warning');
            return;
        }
        const width = Math.max(256, parseInt(document.getElementById('image-width').value || '1920', 10));
        const height = Math.max(256, parseInt(document.getElementById('image-height').value || '1080', 10));
        const fps = Math.min(60, Math.max(1, Number(this.state.display.videoFps) || this.currentPlaybackFps()));
        const format = ['mov', 'avi'].includes(this.state.display.videoFormat)
            ? this.state.display.videoFormat
            : 'mov';
        const lighting = this.state.display;
        const position = lighting.sunPosition || [8, -10, 14];
        const target = lighting.sunTarget || [0, 0, 0];
        const scaleMode = lighting.imageFramingMode === 'physical' ? 'physical' : 'viewport';
        const pixelsPerAngstrom = Math.max(0.1, Math.min(5000,
            Number(this.renderer.currentPixelsPerAngstrom()) || 100));
        const sphereQuality = ['viewport', 'auto', 'low', 'medium', 'high', 'ultra'].includes(
            lighting.imageSphereQuality
        ) ? lighting.imageSphereQuality : 'viewport';
        const smoothnessScale = Math.max(0.5, Math.min(2,
            Number(lighting.imageSmoothnessScale) || 1));
        const selected = (value, current) => value === current ? 'selected' : '';
        this.showModal(`
            <h2>Export Video</h2>
            <p class="modal-intro">Render every loaded trajectory frame using the exact Preview Area camera and crop.</p>
            <div class="export-image-columns">
                <div class="export-image-column">
                    <div class="export-grid">
                        <label for="video-format">Format</label>
                        <select id="video-format">
                            <option value="mov" ${selected('mov', format)}>MOV (H.264)</option>
                            <option value="avi" ${selected('avi', format)}>AVI (MPEG-4)</option>
                        </select>
                        <label for="video-width">Width</label>
                        <input type="number" id="video-width" value="${width}" min="256" step="128">
                        <label for="video-height">Height</label>
                        <input type="number" id="video-height" value="${height}" min="256" step="128">
                        <label for="video-fps">FPS</label>
                        <input type="number" id="video-fps" value="${fps}" min="1" max="60" step="1">
                    </div>
                    <label class="check-row" for="video-grid">
                        <span>Include grid</span>
                        <input type="checkbox" id="video-grid" ${this.state.display.showGrid ? 'checked' : ''}>
                    </label>
                    <label class="check-row" for="video-axes">
                        <span>Include axes</span>
                        <input type="checkbox" id="video-axes" ${this.state.display.showAxes ? 'checked' : ''}>
                    </label>
                    <label class="check-row" for="video-cell">
                        <span>Include unit cell</span>
                        <input type="checkbox" id="video-cell" ${this.state.display.exportIncludeCell !== false ? 'checked' : ''}>
                    </label>
                    <div class="export-render-section">
                        <div class="export-section-title">Framing</div>
                        <div class="export-grid">
                            <label for="video-framing-mode">Frame</label>
                            <select id="video-framing-mode">
                                <option value="viewport" ${selected('viewport', scaleMode)}>Current viewport</option>
                                <option value="physical" ${selected('physical', scaleMode)}>Atomic scale from View</option>
                            </select>
                        </div>
                        <p id="video-scale-note" class="export-note"></p>
                    </div>
                    <div class="export-render-section">
                        <div class="export-section-title">Atom surface</div>
                        <div class="export-grid">
                            <label for="video-sphere-quality">Atom smoothness</label>
                            <select id="video-sphere-quality">
                                <option value="viewport" ${selected('viewport', sphereQuality)}>Viewport setting</option>
                                <option value="auto" ${selected('auto', sphereQuality)}>Auto</option>
                                <option value="low" ${selected('low', sphereQuality)}>Low</option>
                                <option value="medium" ${selected('medium', sphereQuality)}>Medium</option>
                                <option value="high" ${selected('high', sphereQuality)}>High</option>
                                <option value="ultra" ${selected('ultra', sphereQuality)}>Ultra</option>
                            </select>
                            <label for="video-smoothness-scale">Smoothness scale</label>
                            <input type="number" id="video-smoothness-scale" value="${smoothnessScale.toFixed(2)}" min="0.5" max="2" step="0.1">
                        </div>
                    </div>
                </div>
                <div class="export-image-column">
                    <div class="export-render-section">
                        <div class="export-section-title">Rendering</div>
                        <div class="export-grid">
                            <label for="video-render-mode">Renderer</label>
                            <select id="video-render-mode">
                                <option value="current">Viewport setting</option>
                                <option value="modeling">Modeling</option>
                                <option value="studio">Studio Sun</option>
                                <option value="studio-shadow">Sun + Soft Shadow</option>
                            </select>
                            <label for="video-sun-intensity">Brightness</label>
                            <input type="number" id="video-sun-intensity" value="${Number(lighting.sunIntensity ?? 2.2).toFixed(2)}" min="0" max="8" step="0.05">
                        </div>
                        <div class="export-light-vector">
                            <span>Sun position</span>
                            <div>
                                ${position.map((value, index) => `<input type="number" id="video-sun-position-${index}" value="${Number(value).toFixed(3)}" step="0.25" aria-label="Video Sun position ${index + 1}">`).join('')}
                            </div>
                        </div>
                        <div class="export-light-vector">
                            <span>Direction target</span>
                            <div>
                                ${target.map((value, index) => `<input type="number" id="video-sun-target-${index}" value="${Number(value).toFixed(3)}" step="0.25" aria-label="Video Sun target ${index + 1}">`).join('')}
                            </div>
                        </div>
                    </div>
                    <p class="export-video-background-note">Video background is fixed to white. MOV and AVI export do not use transparency.</p>
                </div>
            </div>
        `, `
            <button id="modal-close" class="btn">Cancel</button>
            <button id="modal-export-video" class="btn primary">Export</button>
        `);
        document.querySelector('#modal-container .modal')?.classList.add('export-image-modal');

        const readVideoOptions = () => {
            const outputWidth = Math.ceil(Math.max(256,
                parseInt(document.getElementById('video-width')?.value || `${width}`, 10)) / 2) * 2;
            const outputHeight = Math.ceil(Math.max(256,
                parseInt(document.getElementById('video-height')?.value || `${height}`, 10)) / 2) * 2;
            const selectedRenderMode = document.getElementById('video-render-mode')?.value || 'current';
            const renderMode = selectedRenderMode === 'current'
                ? (this.state.display.lightingMode || 'modeling')
                : selectedRenderMode;
            return {
                width: outputWidth,
                height: outputHeight,
                fps: Math.min(60, Math.max(1,
                    Number(document.getElementById('video-fps')?.value) || fps)),
                format: document.getElementById('video-format')?.value === 'avi' ? 'avi' : 'mov',
                transparentBackground: false,
                backgroundColor: '#ffffff',
                includeGrid: Boolean(document.getElementById('video-grid')?.checked),
                includeAxes: Boolean(document.getElementById('video-axes')?.checked),
                includeCell: Boolean(document.getElementById('video-cell')?.checked),
                scaleMode: document.getElementById('video-framing-mode')?.value === 'physical'
                    ? 'physical'
                    : 'viewport',
                pixelsPerAngstrom: Math.max(0.1, Math.min(5000,
                    Number(this.renderer.currentPixelsPerAngstrom()) || pixelsPerAngstrom)),
                sphereQuality: document.getElementById('video-sphere-quality')?.value || 'viewport',
                sphereQualityScale: Math.max(0.5, Math.min(2,
                    Number(document.getElementById('video-smoothness-scale')?.value) || smoothnessScale)),
                renderMode,
                sunIntensity: Math.max(0,
                    Number(document.getElementById('video-sun-intensity')?.value) || 0),
                sunPosition: [0, 1, 2].map(index =>
                    Number(document.getElementById(`video-sun-position-${index}`)?.value) || 0),
                sunTarget: [0, 1, 2].map(index =>
                    Number(document.getElementById(`video-sun-target-${index}`)?.value) || 0)
            };
        };

        const updateVideoPreview = () => {
            const options = readVideoOptions();
            const note = document.getElementById('video-scale-note');
            if (note) {
                note.textContent = options.scaleMode === 'physical'
                    ? `${options.pixelsPerAngstrom.toFixed(2)} px/Å; frame span ${(options.width / options.pixelsPerAngstrom).toFixed(2)} Å × ${(options.height / options.pixelsPerAngstrom).toFixed(2)} Å.`
                    : 'Uses the current camera direction and magnification with the requested output aspect ratio.';
            }
            const { width: previewWidth, height: previewHeight, fps: _fps, format: _format, ...renderOptions } = options;
            this.state.exportPreviewProfile = {
                width: previewWidth,
                height: previewHeight,
                options: renderOptions
            };
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        };
        [
            'video-width', 'video-height', 'video-fps', 'video-smoothness-scale',
            'video-sun-intensity', 'video-sun-position-0', 'video-sun-position-1',
            'video-sun-position-2', 'video-sun-target-0', 'video-sun-target-1',
            'video-sun-target-2'
        ].forEach(id => document.getElementById(id)?.addEventListener('input', updateVideoPreview));
        [
            'video-format', 'video-grid', 'video-axes', 'video-cell', 'video-framing-mode',
            'video-sphere-quality', 'video-render-mode'
        ].forEach(id => document.getElementById(id)?.addEventListener('change', updateVideoPreview));
        updateVideoPreview();

        document.getElementById('modal-export-video')?.addEventListener('click', async () => {
            try {
                const options = readVideoOptions();
                Object.assign(this.state.display, {
                    imageFramingMode: options.scaleMode,
                    atomicScalePixelsPerAngstrom: options.pixelsPerAngstrom,
                    imageSphereQuality: options.sphereQuality,
                    imageSmoothnessScale: options.sphereQualityScale,
                    videoFormat: options.format,
                    videoFps: options.fps
                });
                const imageWidthInput = document.getElementById('image-width');
                const imageHeightInput = document.getElementById('image-height');
                if (imageWidthInput) imageWidthInput.value = `${options.width}`;
                if (imageHeightInput) imageHeightInput.value = `${options.height}`;
                await this.exportTrajectoryVideo(options);
            } catch (err) {
                this.toast(`Video export failed: ${err.message}`, 'error');
            }
        });
        document.getElementById('modal-close')?.addEventListener('click', () => {
            this.state.exportPreviewProfile = null;
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        }, { once: true });
    }

    async exportTrajectoryVideo({ width, height, fps, format, ...renderOptions }) {
        const meta = this.state.atoms?.metadata || {};
        const frameCount = meta.frame_count || 1;
        if (frameCount <= 1) throw new Error('A trajectory with at least two frames is required.');
        const canvas = this.renderer.domElement;
        if (!canvas.captureStream || !window.MediaRecorder) {
            throw new Error('This browser does not support canvas video recording.');
        }
        const outputWidth = Math.ceil(Math.max(256, Number(width) || 1920) / 2) * 2;
        const outputHeight = Math.ceil(Math.max(256, Number(height) || 1080) / 2) * 2;
        const outputFps = Math.min(60, Math.max(1, Number(fps) || 12));
        const outputFormat = format === 'avi' ? 'avi' : 'mov';
        const originalFrame = meta.current_frame || 0;
        if (this.state.trajectoryTimer) {
            clearTimeout(this.state.trajectoryTimer);
            this.state.trajectoryTimer = null;
            this.state.trajectoryPlaybackSource = null;
            this.updateTrajectoryUI();
        }
        const chunks = [];
        let capture = this.renderer.beginExportCapture(outputWidth, outputHeight, renderOptions);
        const stream = canvas.captureStream(outputFps);
        const videoTrack = stream.getVideoTracks()[0];
        const mimeType = [
            'video/webm;codecs=vp9',
            'video/webm;codecs=vp8',
            'video/webm',
            'video/mp4;codecs=avc1.42E01E',
            'video/mp4'
        ].find(candidate => MediaRecorder.isTypeSupported?.(candidate)) || '';
        const recorderOptions = {
            videoBitsPerSecond: Math.max(8_000_000, outputWidth * outputHeight * outputFps * 0.18)
        };
        if (mimeType) recorderOptions.mimeType = mimeType;
        const recorder = new MediaRecorder(stream, recorderOptions);
        const finished = new Promise((resolve, reject) => {
            recorder.ondataavailable = event => {
                if (event.data && event.data.size) chunks.push(event.data);
            };
            recorder.onerror = () => reject(recorder.error || new Error('MediaRecorder failed.'));
            recorder.onstop = () => resolve();
        });

        this.closeModal();
        this.setBusy(`Rendering ${frameCount} trajectory frames...`);
        recorder.start(100);
        try {
            await new Promise(resolve => setTimeout(resolve, 80));
            for (let frame = 0; frame < frameCount; frame++) {
                await this.loadFrame(frame);
                this.renderer.renderExportCaptureFrame(capture);
                videoTrack?.requestFrame?.();
                this.setBusy(`Rendering trajectory frame ${frame + 1} / ${frameCount}...`);
                await new Promise(resolve => setTimeout(resolve, 1000 / outputFps));
            }
            recorder.stop();
            await finished;
            stream.getTracks().forEach(track => track.stop());
            this.renderer.endExportCapture(capture);
            capture = null;
            const recording = new Blob(chunks, {
                type: recorder.mimeType || mimeType || 'application/octet-stream'
            });
            this.setBusy(`Encoding ${outputFormat.toUpperCase()} video...`);
            const video = await this.api.transcodeVideo(recording, outputFormat);
            const filename = `v_ase-trajectory.${outputFormat}`;
            const outputMime = outputFormat === 'avi' ? 'video/x-msvideo' : 'video/quicktime';
            const saved = await this.savePreparedBlob(video, filename, outputMime);
            if (saved) this.toast(`${outputFormat.toUpperCase()} video saved.`, 'success');
        } finally {
            stream.getTracks().forEach(track => track.stop());
            if (recorder.state !== 'inactive') recorder.stop();
            if (capture) this.renderer.endExportCapture(capture);
            await this.loadFrame(originalFrame);
            this.state.exportPreviewProfile = null;
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
            this.clearBusy();
        }
    }

    async loadFrame(index) {
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        const meta = this.state.atoms?.metadata || {};

        if (meta.virtual_trajectory) {
            const count = meta.frame_count || 1;
            const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
            const frame = await this.api.fetchFramePositions(normalized);
            if (frame.atoms !== this.state.atoms.positions.length) {
                throw new Error('Frame atom count does not match the loaded structure.');
            }
            this.state.atoms.metadata.current_frame = frame.frame;
            this.state.atoms.metadata.frame_count = frame.frames || count;
            if (Array.isArray(frame.cell)) {
                const oldCell = JSON.stringify(this.state.atoms.cell || []);
                const newCell = JSON.stringify(frame.cell);
                this.state.atoms.cell = frame.cell;
                this.renderer.atomsData.cell = frame.cell;
                if (oldCell !== newCell) {
                    this.renderer.rebuildCell(frame.cell);
                    this.renderer.rebuildSupercell();
                }
            }
            if (Array.isArray(frame.pbc)) this.state.atoms.pbc = frame.pbc;
            const override = this.relaxOverridePositions(normalized);
            if (override) {
                this.state.atoms.positions = override;
                this.state.originalPositions = this.state.vizOnly ? override : override.map(p => [...p]);
                this.renderer.updatePositions(override);
                this.updateUI();
                return;
            }
            this.renderer.updatePositionsFlat(frame.values, 0, frame.atoms);
            if (this.state.trajectoryTimer) {
                this.updateTrajectoryUI();
            } else {
                const positions = this.materializeFlatFrame(frame.values, frame.atoms);
                this.state.atoms.positions = positions;
                this.state.originalPositions = this.state.vizOnly ? positions : positions.map(p => [...p]);
                this.updateUI();
            }
            return;
        }

        if (this.state.atoms?.trajectory_positions) {
            const count = this.state.atoms.metadata.frame_count || 1;
            const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
            const framePositions = this.state.atoms.trajectory_positions[normalized];
            if (!Array.isArray(framePositions)) return;
            this.state.atoms.metadata.current_frame = normalized;
            const positions = this.relaxOverridePositions(normalized) || framePositions;
            this.state.atoms.positions = positions;
            this.state.originalPositions = this.state.vizOnly ? positions : positions.map(p => [...p]);
            this.renderer.updatePositions(this.state.atoms.positions);
            if (this.state.trajectoryTimer) {
                this.updateTrajectoryUI();
            } else {
                this.updateUI();
            }
            return;
        }

        const binaryCache = this.state.trajectoryBinaryCache || await this.loadTrajectoryCache({ background: false });
        if (binaryCache) {
            const count = this.state.atoms.metadata.frame_count || 1;
            const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
            const offset = normalized * binaryCache.atoms * 3;
            this.state.atoms.metadata.current_frame = normalized;
            const override = this.relaxOverridePositions(normalized);
            if (override) {
                this.renderer.updatePositions(override);
            } else {
                this.renderer.updatePositionsFlat(binaryCache.values, offset, binaryCache.atoms);
            }
            if (this.state.trajectoryTimer) {
                this.updateTrajectoryUI();
            } else {
                const framePositions = override || this.materializeBinaryFrame(binaryCache, normalized);
                this.state.atoms.positions = framePositions;
                this.state.originalPositions = this.state.vizOnly ? framePositions : framePositions.map(p => [...p]);
                this.updateUI();
            }
            return;
        }

        const data = await this.api.setFrame(index);
        if (data?.metadata?.positions_only && Array.isArray(data.positions)) {
            this.state.atoms.metadata.current_frame = data.metadata.current_frame;
            this.state.atoms.metadata.frame_count = data.metadata.frame_count || this.state.atoms.metadata.frame_count;
            this.state.atoms.positions = data.positions;
            this.state.originalPositions = this.state.vizOnly ? data.positions : data.positions.map(p => [...p]);
            if (Array.isArray(data.cell)) {
                const oldCell = JSON.stringify(this.state.atoms.cell || []);
                const newCell = JSON.stringify(data.cell);
                this.state.atoms.cell = data.cell;
                this.renderer.atomsData.cell = data.cell;
                if (oldCell !== newCell) {
                    this.renderer.rebuildCell(data.cell);
                    this.renderer.rebuildSupercell();
                }
            }
            if (Array.isArray(data.pbc)) this.state.atoms.pbc = data.pbc;
            const override = this.relaxOverridePositions(data.metadata.current_frame);
            if (override) {
                this.state.atoms.positions = override;
                this.state.originalPositions = this.state.vizOnly ? override : override.map(p => [...p]);
            }
            this.renderer.updatePositions(this.state.atoms.positions);
            if (this.state.trajectoryTimer) {
                this.updateTrajectoryUI();
            } else {
                this.updateUI();
            }
            return;
        }
        this.setAtomsData(data, { clearSelection: true });
    }

    queueFrameLoad(index) {
        const source = this.primaryTimelineSource();
        if (source === 'relax') {
            this.loadRelaxFrame(index).catch(err => this.toast(`Relax frame load failed: ${err.message}`, 'error'));
            return;
        }
        const count = this.loadedFrameCount();
        if (count <= 1) return;
        const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
        this.pendingFrameIndex = normalized;
        const label = document.getElementById('frame-label');
        if (label) label.innerText = `${normalized + 1} / ${count}`;
        if (!this.frameLoadInFlight) {
            this.flushFrameLoadQueue().catch(err => this.toast(`Frame load failed: ${err.message}`, 'error'));
        }
    }

    async flushFrameLoadQueue() {
        this.frameLoadInFlight = true;
        try {
            while (this.pendingFrameIndex !== null) {
                const next = this.pendingFrameIndex;
                this.pendingFrameIndex = null;
                await this.loadFrame(next);
            }
        } finally {
            this.frameLoadInFlight = false;
        }
    }

    async stepFrame(delta, source = this.primaryTimelineSource()) {
        const count = this.timelineFrameCount(source);
        if (count <= 1) return;
        const current = this.timelineFrameIndex(source);
        const next = (current + delta + count) % count;
        if (source === 'relax') {
            await this.loadRelaxFrame(next);
        } else {
            await this.loadFrame(next);
        }
    }

    currentPlaybackFps() {
        return Math.min(60, Math.max(1, parseFloat(document.getElementById('movie-fps').value || '12')));
    }

    currentPlaybackSkip() {
        const input = document.getElementById('movie-skip');
        const value = Math.floor(Number(input?.value || 0));
        return Math.min(999, Math.max(0, Number.isFinite(value) ? value : 0));
    }

    currentPlaybackStep() {
        return this.currentPlaybackSkip() + 1;
    }

    stopPlayback() {
        if (this.state.trajectoryTimer) {
            clearTimeout(this.state.trajectoryTimer);
            this.state.trajectoryTimer = null;
            const source = this.state.trajectoryPlaybackSource || this.primaryTimelineSource();
            this.state.trajectoryPlaybackSource = null;
            this.updateTrajectoryUI();
            if (source === 'loaded' && this.state.atoms?.metadata?.current_frame !== undefined) {
                if (this.state.atoms.metadata.virtual_trajectory) {
                    this.loadFrame(this.state.atoms.metadata.current_frame).catch(err => console.warn("Failed to sync frame", err));
                } else {
                    this.api.setFrame(this.state.atoms.metadata.current_frame).catch(err => console.warn("Failed to sync frame", err));
                }
            }
        }
    }

    async startPlayback() {
        const meta = this.state.atoms?.metadata || {};
        const source = this.primaryTimelineSource();
        if (this.timelineFrameCount(source) <= 1 || this.state.trajectoryTimer) return;
        if (source === 'loaded' && meta.trajectory_positions_binary && !this.state.trajectoryBinaryCache) {
            const cache = await this.withBusy(
                'Loading trajectory cache...',
                () => this.loadTrajectoryCache({ background: false })
            );
            if (!cache) return;
        }
        this.state.trajectoryPlaybackSource = source;
        const tick = async () => {
            if (!this.state.trajectoryTimer) return;
            try {
                await this.stepFrame(this.currentPlaybackStep(), this.state.trajectoryPlaybackSource || source);
            } catch (err) {
                this.toast(`Movie playback failed: ${err.message}`, 'error');
                this.stopPlayback();
                return;
            }
            if (!this.state.trajectoryTimer) return;
            this.state.trajectoryTimer = setTimeout(tick, 1000 / this.currentPlaybackFps());
        };
        this.state.trajectoryTimer = setTimeout(tick, 0);
        this.updateTrajectoryUI();
    }

    async restartPlayback() {
        if (!this.state.trajectoryTimer) return;
        this.stopPlayback();
        await this.startPlayback();
    }

    async togglePlayback() {
        if (this.state.trajectoryTimer) {
            this.stopPlayback();
            return;
        }
        await this.startPlayback();
        this.updateTrajectoryUI();
    }

    setupEventListeners() {
        window.addEventListener('resize', () => this.renderer.onResize());

        document.getElementById('btn-open-file')?.addEventListener('click', () => this.chooseStructureFile());
        document.getElementById('btn-empty-open')?.addEventListener('click', () => this.chooseStructureFile());
        document.getElementById('structure-file')?.addEventListener('change', event => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (file) this.showOpenFileModal(file);
        });
        
        document.getElementById('btn-reset').onclick = async () => {
            try {
                if (!await this.confirmFullReset()) return;
                const data = await this.withBusy(
                    'Resetting coordinates and visual settings...',
                    () => this.api.reset()
                );
                this.applyDesignSettings(this.initialDesignSettings, { render: false });
                this.setAtomsData(data, { clearSelection: true });
                this.toast('Reset to the loaded starting state.', 'success');
            } catch (err) {
                this.toast(`Reset failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-reset-coords').onclick = async () => {
            try {
                if (!await this.confirmCoordinateReset()) return;
                const preservedSettings = this.designSettingsSnapshot();
                preservedSettings.display.supercell = [1, 1, 1];
                const data = await this.withBusy(
                    'Resetting coordinates and original unit cell...',
                    () => this.api.resetCoordinates()
                );
                this.applyDesignSettings(preservedSettings, { render: false });
                this.setAtomsData(data, { clearSelection: true });
                this.toast('Coordinates and original unit cell restored. Visual settings were kept.', 'success');
            } catch (err) {
                this.toast(`Coordinate reset failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-wrap').onclick = async () => {
            try {
                if (!this.hasUsableCell()) {
                    this.toast('Wrap requires a defined unit cell.', 'warning');
                    return;
                }
                if (this.state.vizOnly) {
                    this.wrapVisibleAtomsIntoCell();
                    this.toast('Wrapped the visible frame into the unit cell.', 'success');
                    return;
                }
                const frameCount = this.state.atoms.metadata.frame_count || 1;
                const data = await this.withBusy(
                    `Wrapping ${frameCount} frame${frameCount > 1 ? 's' : ''} into the unit cell...`,
                    () => this.api.wrap(this.backendPositionsPayload(), this.state.applyConstraints)
                );
                this.setAtomsData(data);
                this.toast('Wrapped atoms into the unit cell for all frames.', 'success');
            } catch (err) {
                this.toast(`Wrap failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-delete-selection').onclick = () => this.deleteSelection();
        document.querySelectorAll('[data-copy-target]').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                this.copySelectionField(button.dataset.copyTarget);
            });
        });
        document.getElementById('constraint-fixatoms')?.addEventListener('change', (event) => {
            event.preventDefault();
            this.toggleSelectedFixAtoms();
        });
        document.getElementById('constraint-kind')?.addEventListener('change', () => {
            const kind = document.getElementById('constraint-kind')?.value || 'none';
            if (kind === 'fixed_line') this.setConstraintVectorInputs([1, 0, 0]);
            if (kind === 'fixed_plane') this.setConstraintVectorInputs([0, 0, 1]);
            this.updateSelectionConstraintControls();
        });
        ['constraint-x', 'constraint-y', 'constraint-z'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => this.updateSelectionConstraintControls());
        });
        document.getElementById('btn-apply-constraint')?.addEventListener('click', () => this.applySelectedDirectionalConstraint());
        document.getElementById('btn-clear-directional-constraint')?.addEventListener('click', () => this.clearSelectedDirectionalConstraint());
        document.getElementById('btn-undo').onclick = async () => {
            try {
                const data = await this.api.undo();
                this.setAtomsData(data);
                this.toast('Undo.', 'success');
            } catch (err) {
                this.toast(`Undo failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-redo').onclick = async () => {
            try {
                const data = await this.api.redo();
                this.setAtomsData(data);
                this.toast('Redo.', 'success');
            } catch (err) {
                this.toast(`Redo failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-poscar').onclick = async () => {
            try {
                const saved = await this.saveBlobFromAction(
                    () => this.api.exportPoscar(this.backendPositionsPayload(), this.state.applyConstraints),
                    'POSCAR',
                    'application/octet-stream',
                    'Preparing POSCAR export...'
                );
                if (saved) this.toast('POSCAR export saved.', 'success');
            } catch (err) {
                this.toast(`POSCAR export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-pickle').onclick = async () => {
            try {
                const saved = await this.saveBlobFromAction(
                    () => this.api.exportPickle(this.backendPositionsPayload(), this.state.applyConstraints),
                    'atoms.pkl',
                    'application/octet-stream',
                    'Preparing ASE Pickle export...'
                );
                if (saved) this.toast('ASE Pickle export saved.', 'success');
            } catch (err) {
                this.toast(`ASE Pickle export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-blender').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.exportBlender(
                        this.backendPositionsPayload(),
                        this.state.applyConstraints,
                        this.currentCameraForExport(),
                        this.clonePlain(this.state.display),
                        this.renderer.bondPairs || [],
                        this.currentLightingForExport(),
                        this.state.display.exportIncludeCell !== false
                    ),
                    'v_ase_blender_scene.py',
                    'text/x-python',
                    'Preparing Blender export...'
                );
                if (saved) this.toast('Blender export script saved.', 'success');
            } catch (err) {
                this.toast(`Blender export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-3dm').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.export3dm(
                        this.backendPositionsPayload(),
                        this.state.applyConstraints,
                        this.clonePlain(this.state.display),
                        this.renderer.bondPairs || [],
                        this.renderer.supercellBridgeBondRecords || [],
                        this.currentCameraForExport(),
                        this.state.display.exportIncludeCell !== false
                    ),
                    'v_ase_scene.3dm',
                    'model/vnd.3dm',
                    'Building editable Rhino 3DM scene...'
                );
                if (saved) this.toast('Rhino 3DM scene saved.', 'success');
            } catch (err) {
                this.toast(`3DM export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-obj').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.exportObj(
                        this.backendPositionsPayload(),
                        this.state.applyConstraints,
                        this.clonePlain(this.state.display),
                        this.renderer.bondPairs || [],
                        this.renderer.supercellBridgeBondRecords || [],
                        this.currentCameraForExport(),
                        this.state.display.exportIncludeCell !== false
                    ),
                    'v_ase_obj_scene.zip',
                    'application/zip',
                    'Building OBJ scene and metadata bundle...'
                );
                if (saved) this.toast('OBJ scene bundle saved.', 'success');
            } catch (err) {
                this.toast(`OBJ export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-image').onclick = () => {
            this.showExportImageModal();
        };
        document.getElementById('btn-preview-image').onclick = () => {
            this.state.exportPreviewProfile = null;
            this.state.exportPreviewEnabled = !this.state.exportPreviewEnabled;
            this.syncImageExportPreview();
        };
        ['image-width', 'image-height'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => {
                const dimensions = this.imageOutputDimensions();
                const profile = this.currentImageExportProfile();
                this.setImageExportProfile({
                    ...profile,
                    width: dimensions.width,
                    height: dimensions.height
                }, { syncInputs: false });
            });
        });
        document.getElementById('btn-export-video').onclick = () => {
            this.showExportVideoModal();
        };
        document.getElementById('btn-save-project').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.saveProject(
                        this.backendPositionsPayload(),
                        this.designSettingsSnapshot(),
                        this.state.applyConstraints
                    ),
                    'v_ase_project.vase',
                    'application/vnd.v-ase.project+zip',
                    'Saving complete v_ase project...'
                );
                if (saved) this.toast('Complete .vase project saved.', 'success');
            } catch (err) {
                this.toast(`Save project failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-load-project').onclick = () => {
            document.getElementById('project-file')?.click();
        };
        document.getElementById('project-file').onchange = async (event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            await this.loadStructureFile(file, 'vase', ':');
        };
        document.getElementById('btn-save-settings').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.saveVisualSettings(this.designSettingsSnapshot()),
                    'v_ase_visual_settings.json',
                    'application/json',
                    'Saving visual settings...'
                );
                if (saved) this.toast('Visual settings saved without structure data.', 'success');
            } catch (err) {
                this.toast(`Save settings failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-load-settings').onclick = () => {
            document.getElementById('settings-file')?.click();
        };
        document.getElementById('settings-file').onchange = async (event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            try {
                const data = await this.api.loadVisualSettings(file);
                this.applyDesignSettings(data.settings || data);
                this.toast('Visual settings applied to matching labels; new labels use defaults.', 'success');
            } catch (err) {
                this.toast(`Load settings failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-relax').onclick = async () => {
            if (!this.state.atoms.metadata.has_calculator) {
                this.toast('Relax requires an attached ASE calculator.', 'warning');
                return;
            }
            const fmax = parseFloat(document.getElementById('relax-fmax').value || '0.05');
            const steps = parseInt(document.getElementById('relax-steps').value || '200', 10);
            try {
                this.startRelaxTrajectory();
                const response = await this.api.relaxStart(
                    this.backendPositionsPayload(),
                    fmax,
                    steps,
                    this.state.applyConstraints,
                    this.currentCalculatorPayload()
                );
                if (response.status === 'started' || response.status === 'restarting') {
                    this.state.isRelaxing = true;
                    this.toast(response.status === 'restarting' ? 'Relaxation restarting.' : 'Relaxation started.', 'success');
                } else {
                    this.state.relaxTrajectory.active = false;
                    this.toast(response.message || 'Relaxation did not start.', 'warning');
                }
                this.updateUI();
            } catch (err) {
                this.state.relaxTrajectory.active = false;
                this.toast(`Relax failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-stop-relax').onclick = async () => {
            try {
                await this.api.relaxStop();
                this.toast('Stopping relaxation...', 'warning');
            } catch (err) {
                this.toast(`Stop relax failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('calc-device')?.addEventListener('change', () => {
            const cpus = document.getElementById('calc-cpus');
            if (cpus) cpus.disabled = document.getElementById('calc-device')?.value !== 'cpu';
            this.applyCalculatorControls();
        });
        document.getElementById('calc-cpus')?.addEventListener('change', () => this.applyCalculatorControls());
        document.getElementById('chk-bonds').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-periodic-bonds').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-cell').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-axes').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-grid').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-overlays').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('projection-mode').onchange = () => this.safeApplyDisplayOptions();
        const atomicScale = document.getElementById('atomic-scale');
        atomicScale.oninput = () => this.applyAtomicScaleFromControl();
        atomicScale.onchange = () => this.applyAtomicScaleFromControl({ normalize: true });
        document.getElementById('chk-antialias').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('sphere-quality').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('atom-radius-scale').oninput = () => this.safeApplyDisplayOptions();
        document.getElementById('atom-radius-scale').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-constraints').onchange = () => {
            this.safeApplyDisplayOptions();
            this.updateSelectionVisuals();
            this.toast(this.state.applyConstraints ? 'Constraints enabled.' : 'Constraints disabled for free editing.', 'success');
        };
        document.getElementById('bond-mode').onchange = () => {
            this.updateBondModeUI();
            this.safeApplyDisplayOptions();
        };
        document.getElementById('bond-cutoff').onchange = () => {
            this.renderElementBondControls();
            this.safeApplyDisplayOptions();
        };
        document.getElementById('bond-cutoff').oninput = () => this.safeApplyDisplayOptions();
        document.getElementById('bond-style').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('blender-export-mode').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('export-include-cell').onchange = event => {
            const includeCell = event.target.checked;
            this.state.display.exportIncludeCell = includeCell;
            const profile = this.currentImageExportProfile();
            profile.options.includeCell = includeCell;
            this.setImageExportProfile(profile);
            this.safeApplyDisplayOptions();
        };
        document.getElementById('bond-thickness').oninput = () => {
            this.updateBondAppearanceUI();
            this.safeApplyDisplayOptions();
        };
        document.getElementById('bond-thickness').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('bond-color-mode').onchange = () => {
            this.updateBondAppearanceUI();
            this.safeApplyDisplayOptions();
        };
        document.getElementById('bond-custom-color').oninput = () => this.safeApplyDisplayOptions();
        document.getElementById('bond-custom-color').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('btn-bond-apply').onclick = () => {
            const mode = document.getElementById('bond-mode').value;
            if (mode === 'manual') {
                const beforeKeys = Object.keys(this.state.display.elementBondCutoffs).length;
                const hasElementCutoff = /[A-Z][a-z]?\s*[-:]\s*[A-Z][a-z]?\s*(?:[:=]\s*)?[0-9]/.test(
                    document.getElementById('bond-pairs').value || ''
                );
                this.parseBondPairs();
                if (hasElementCutoff || Object.keys(this.state.display.elementBondCutoffs).length > beforeKeys) {
                    document.getElementById('bond-mode').value = 'element';
                    this.renderElementBondControls();
                }
            }
            this.safeApplyDisplayOptions();
            this.toast('Bond settings applied.', 'success');
        };
        document.getElementById('btn-bond-infer').onclick = () => {
            document.getElementById('bond-mode').value = 'auto';
            this.safeApplyDisplayOptions();
            this.writeBondPairs(this.renderer.bondPairs || []);
            this.toast('Bond pairs inferred from current geometry.', 'success');
        };
        ['super-x', 'super-y', 'super-z'].forEach(id => {
            document.getElementById(id).onchange = () => this.safeApplyDisplayOptions();
            document.getElementById(id).oninput = () => this.safeApplyDisplayOptions();
        });
        document.getElementById('btn-set-supercell').onclick = () => this.setSupercellAsCell();
        document.getElementById('btn-apply-supercell-matrix').onclick = () => this.applyMakeSupercellMatrix();
        document.getElementById('btn-shortcuts').onclick = () => {
            this.showShortcutsModal();
        };
        document.getElementById('modal-close')?.addEventListener('click', () => this.closeModal());
        const modalContainer = document.getElementById('modal-container');
        modalContainer?.addEventListener('pointerdown', (e) => {
            if (!modalContainer.classList.contains('hidden')) {
                e.stopPropagation();
                if (e.target?.id === 'modal-container') this.closeModal();
            }
        });
        ['pointermove', 'pointerup', 'click', 'wheel'].forEach(type => {
            modalContainer?.addEventListener(type, (e) => {
                if (!modalContainer.classList.contains('hidden')) {
                    e.stopPropagation();
                    if (type === 'wheel') e.preventDefault();
                }
            }, { passive: false });
        });
        document.getElementById('btn-frame-prev').onclick = () => this.stepFrame(-1).catch(err => this.toast(err.message, 'error'));
        document.getElementById('btn-frame-next').onclick = () => this.stepFrame(1).catch(err => this.toast(err.message, 'error'));
        document.getElementById('btn-play').onclick = () => this.togglePlayback().catch(err => this.toast(`Movie playback failed: ${err.message}`, 'error'));
        document.getElementById('frame-slider').oninput = (e) => {
            this.queueFrameLoad(e.target.value);
        };
        document.getElementById('frame-slider').onchange = (e) => {
            this.queueFrameLoad(e.target.value);
        };
        document.getElementById('relax-frame-slider')?.addEventListener('input', e => {
            this.loadRelaxFrame(e.target.value).catch(err => this.toast(`Relax frame load failed: ${err.message}`, 'error'));
        });
        document.getElementById('relax-frame-slider')?.addEventListener('change', e => {
            this.loadRelaxFrame(e.target.value).catch(err => this.toast(`Relax frame load failed: ${err.message}`, 'error'));
        });
        document.getElementById('movie-fps').oninput = () => {
            this.restartPlayback().catch(err => this.toast(`Movie playback failed: ${err.message}`, 'error'));
        };
        document.getElementById('movie-fps').onchange = () => {
            this.restartPlayback().catch(err => this.toast(`Movie playback failed: ${err.message}`, 'error'));
        };
        const movieSkip = document.getElementById('movie-skip');
        movieSkip.oninput = () => this.currentPlaybackSkip();
        movieSkip.onchange = () => this.currentPlaybackSkip();
        document.getElementById('tool-select')?.addEventListener('click', () => {
            if (this.transform.mode !== 'IDLE') this.cancelTransform();
        });
        document.getElementById('tool-move')?.addEventListener('click', () => this.enterTransformMode('MOVE'));
        document.getElementById('tool-rotate')?.addEventListener('click', () => this.enterTransformMode('ROTATE'));
        this.readTransformSettings();
        ['move-increment', 'rotate-increment'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => {
                this.readTransformSettings();
                if (this.transform.mode !== 'IDLE') this.applyTransformPreview();
                this.updateUI();
            });
        });
        document.getElementById('rotate-pivot')?.addEventListener('change', () => {
            this.safeApplyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.toast('Rotate pivot changes apply to the next rotate operation.', 'warning');
        });
        const refreshCommensurateSearch = () => {
            this.applyDisplayOptions();
            if (this.transform.mode === 'ROTATE') {
                this.prepareCommensurateRotation([...this.state.selected].filter(idx => this.isEditableIndex(idx)));
            }
        };
        document.getElementById('chk-commensurate-guide')?.addEventListener('change', refreshCommensurateSearch);
        document.getElementById('chk-commensurate-snap')?.addEventListener('change', () => {
            this.applyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.applyTransformPreview();
        });
        ['commensurate-strain', 'commensurate-max-index'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', refreshCommensurateSearch);
        });
        document.getElementById('commensurate-snap-range')?.addEventListener('input', () => {
            this.applyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.applyTransformPreview();
        });
        document.getElementById('commensurate-snap-range')?.addEventListener('change', () => {
            this.applyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.applyTransformPreview();
        });

        const canvas = this.renderer.domElement;
        canvas.tabIndex = 0;
        canvas.setAttribute('aria-label', '3D structure viewport');
        canvas.addEventListener('pointermove', (e) => {
            this.state.lastPointer.set(e.clientX, e.clientY);
            if (this.canViewportSelectAtoms() && this.transform.mode === 'IDLE' && !this.state.isDragging) {
                this.queueHoverPick(e);
            } else {
                this.setHoveredAtom(null);
            }
        }, { passive: true });

        canvas.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return; // Left click only
            if (document.activeElement && document.activeElement !== canvas) document.activeElement.blur?.();
            canvas.focus({ preventScroll: true });
            if (this.transform.mode !== 'IDLE') {
                e.preventDefault();
                this.state.suppressNextPointerUp = true;
                this.commitTransform();
                return;
            }
            const sunHandle = this.renderer.pickSunHandle?.(e);
            if (sunHandle) {
                e.preventDefault();
                e.stopPropagation();
                this.state.suppressNextPointerUp = true;
                this.setSunSelected(sunHandle);
                canvas.focus({ preventScroll: true });
                return;
            }
            if (this.state.sunSelected) this.setSunSelected(false, { update: false });
            if (!this.canViewportSelectAtoms()) {
                this.setHoveredAtom(null);
                return;
            }
            this.state.isDragging = true;
            this.state.pointerDownTime = performance.now();
            this.selection.startPoint.set(e.clientX, e.clientY);
            this.hideMarquee();
            this.renderer.controls.enabled = false; // Disable orbit on left click
        });

        canvas.addEventListener('pointermove', (e) => {
            if (this.transform.mode !== 'IDLE') {
                this.transform.pointerDelta.x = (e.clientX - this.state.transformStartPointer.x) / window.innerWidth;
                this.transform.pointerDelta.y = -(e.clientY - this.state.transformStartPointer.y) / window.innerHeight;
                if (this.transform.mode === 'ROTATE' && this.transform.getNumericValue() === null) {
                    this.updateRotationFromPointer(e.clientX, e.clientY);
                }
                this.transform.updateGuides(this.renderer.camera);
                this.applyTransformPreview();
                return;
            }
            
            if (this.canViewportSelectAtoms() && this.state.isDragging) {
                const left = Math.min(this.selection.startPoint.x, e.clientX);
                const top = Math.min(this.selection.startPoint.y, e.clientY);
                const width = Math.abs(e.clientX - this.selection.startPoint.x);
                const height = Math.abs(e.clientY - this.selection.startPoint.y);
                
                if (width > 5 || height > 5) {
                    this.showMarquee(left, top, width, height);
                } else {
                    this.hideMarquee();
                }
            }
        });

        canvas.addEventListener('pointerup', (e) => {
            if (e.button !== 0) return;
            if (this.state.suppressNextPointerUp) {
                this.state.suppressNextPointerUp = false;
                this.state.isDragging = false;
                this.hideMarquee();
                return;
            }
            if (!this.canViewportSelectAtoms()) {
                this.state.isDragging = false;
                this.renderer.controls.enabled = true;
                this.hideMarquee();
                return;
            }
            this.state.isDragging = false;
            this.renderer.controls.enabled = true;
            
            if (this.transform.mode !== 'IDLE') {
                return;
            }

            this.hideMarquee();

            const clickDuration = performance.now() - this.state.pointerDownTime;
            const dist = Math.hypot(e.clientX - this.selection.startPoint.x, e.clientY - this.selection.startPoint.y);

            if (clickDuration < 300 && dist < 5) {
                // Single Click
                const picked = this.selection.pick(
                    e,
                    this.renderer.atomMeshes,
                    this.renderer.supercellGroup,
                    this.state.vizOnly
                );
                if (!e.shiftKey) this.clearAtomSelection();

                if (picked !== null) {
                    if (e.shiftKey) this.toggleSelectionReference(picked);
                    else this.addSelectionReference(picked);
                }
                this.updateSelectionVisuals();
                this.updateUI();
            } else if (dist >= 5) {
                // Box Select
                const rect = {
                    left: Math.min(this.selection.startPoint.x, e.clientX),
                    right: Math.max(this.selection.startPoint.x, e.clientX),
                    top: Math.min(this.selection.startPoint.y, e.clientY),
                    bottom: Math.max(this.selection.startPoint.y, e.clientY)
                };
                const newSelected = this.selection.boxSelect(
                    rect,
                    this.renderer.atomMeshes,
                    this.renderer.camera,
                    this.renderer.supercellGroup,
                    this.state.vizOnly
                );

                if (!e.shiftKey) this.clearAtomSelection();
                newSelected.forEach(reference => this.addSelectionReference(reference));
                this.updateSelectionVisuals();
                this.updateUI();
            }
        });

        canvas.addEventListener('pointercancel', () => {
            this.state.isDragging = false;
            this.renderer.controls.enabled = true;
            this.hideMarquee();
        });

        window.addEventListener('keydown', (e) => {
            const tag = e.target?.tagName?.toLowerCase();
            const isFormControl = ['input', 'textarea', 'select', 'button'].includes(tag) || e.target?.isContentEditable;
            const inspectorCollapsed = document.body.classList.contains('inspector-collapsed');
            if (e.key === 'Escape' && this.transform.mode === 'IDLE') {
                const modal = document.getElementById('modal-container');
                if (modal && !modal.classList.contains('hidden')) {
                    e.preventDefault();
                    this.closeModal();
                    return;
                }
                if (!inspectorCollapsed) {
                    e.preventDefault();
                    if (this.isCommittableInput(e.target)) this.commitInputValue(e.target);
                    e.target?.blur?.();
                    this.setInspectorCollapsed(true);
                    canvas.focus({ preventScroll: true });
                    return;
                }
            }
            if ((e.code === 'Tab' || e.key === 'Tab') && inspectorCollapsed && !isFormControl && this.transform.mode === 'IDLE') {
                e.preventDefault();
                this.setInspectorCollapsed(false);
                return;
            }
            if (['input', 'textarea', 'select'].includes(tag)) return;
            if ((e.ctrlKey || e.metaKey) && this.transform.mode === 'IDLE') {
                if (this.isPhysicalKey(e, 'KeyC', ['c'])) {
                    e.preventDefault();
                    if (this.canEditAtoms()) this.copySelection();
                    else this.editOnlyToast();
                    return;
                }
                if (this.isPhysicalKey(e, 'KeyV', ['v'])) {
                    e.preventDefault();
                    if (this.canEditAtoms()) this.pasteSelection();
                    else this.editOnlyToast();
                    return;
                }
                if (this.isPhysicalKey(e, 'KeyZ', ['z'])) {
                    e.preventDefault();
                    if (!this.canEditAtoms()) {
                        this.editOnlyToast();
                        return;
                    }
                    (e.shiftKey ? this.api.redo() : this.api.undo())
                        .then(data => {
                            this.setAtomsData(data);
                            this.toast(e.shiftKey ? 'Redo.' : 'Undo.', 'success');
                        })
                        .catch(err => this.toast(`${e.shiftKey ? 'Redo' : 'Undo'} failed: ${err.message}`, 'error'));
                    return;
                }
            }
            // Typing in buffer
            if (this.transform.mode !== 'IDLE') {
                const axis = this.axisFromKey(e);
                if (e.key === 'Escape') {
                    e.preventDefault();
                    this.cancelTransform();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    this.commitTransform();
                } else if (axis) {
                    e.preventDefault();
                    this.transform.setAxis(axis, this.renderer.camera);
                    if (this.transform.mode === 'ROTATE' && this.state.transformSubject === 'atoms') {
                        this.prepareCommensurateRotation([...this.state.selected].filter(idx => this.isEditableIndex(idx)));
                    }
                    this.applyTransformPreview();
                    this.updateUI();
                } else if (this.keyCodeValue(e) !== null) {
                    e.preventDefault();
                    this.transform.buffer += this.keyCodeValue(e);
                    this.applyTransformPreview();
                    this.updateUI();
                } else if (e.key === 'Backspace') {
                    e.preventDefault();
                    this.transform.buffer = this.transform.buffer.slice(0, -1);
                    this.applyTransformPreview();
                    this.updateUI();
                }
            } else {
                if ((e.code === 'Space' || e.key === ' ') && e.target?.tagName?.toLowerCase() !== 'button') {
                    if (this.timelineFrameCount(this.primaryTimelineSource()) > 1) {
                        e.preventDefault();
                        this.togglePlayback().catch(err => this.toast(`Movie playback failed: ${err.message}`, 'error'));
                        return;
                    }
                }
                if (this.state.sunSelected &&
                    (this.isPhysicalKey(e, 'KeyG', ['g']) || this.isPhysicalKey(e, 'KeyR', ['r']))) {
                    e.preventDefault();
                    const mode = this.isPhysicalKey(e, 'KeyR', ['r']) ? 'ROTATE' : 'MOVE';
                    this.enterSunTransformMode(mode);
                    return;
                }
                if (this.isPhysicalKey(e, 'KeyA', ['a'])) {
                    e.preventDefault();
                    this.setSunSelected(false, { update: false });
                    if (e.altKey) {
                        this.clearAtomSelection();
                    } else {
                        this.clearAtomSelection();
                        this.state.atoms.positions.forEach((_, idx) => this.addSelectionReference(idx));
                        if (this.state.vizOnly) {
                            this.renderer.supercellSelectionReferences().forEach(reference => {
                                this.addSelectionReference(reference);
                            });
                        }
                    }
                    this.updateSelectionVisuals();
                    this.updateUI();
                    return;
                }
                const axis = this.axisFromKey(e);
                if (axis) {
                    e.preventDefault();
                    const sign = this.alignViewToAxis(axis);
                    this.toast(`View aligned to ${sign > 0 ? '+' : '-'}${axis}.`, 'success');
                    return;
                }
                if ((e.code === 'Delete' || e.key === 'Delete' || e.code === 'Backspace' || e.key === 'Backspace') && this.state.selected.size > 0) {
                    e.preventDefault();
                    if (this.canEditAtoms()) this.deleteSelection();
                    else this.editOnlyToast();
                    return;
                }
                if (this.state.selected.size > 0 && this.canEditAtoms()) {
                    if (this.isPhysicalKey(e, 'KeyG', ['g']) || this.isPhysicalKey(e, 'KeyR', ['r'])) {
                        e.preventDefault();
                        const mode = this.isPhysicalKey(e, 'KeyR', ['r']) ? 'ROTATE' : 'MOVE';
                        this.enterTransformMode(mode);
                    }
                }
            }
        });
    }
}

window.__V_ASE_APP__ = new VAseApp();
window.__ASE_APP__ = window.__V_ASE_APP__;
