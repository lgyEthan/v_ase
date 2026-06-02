import * as THREE from 'three';
import { ASEApi } from './api.js';
import { ASERenderer } from './renderer.js';
import { ASESelection } from './selection.js';
import { ASETransform } from './transform.js';

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
        
        this.state = {
            atoms: null,
            selected: new Set(),
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
                bondMode: 'auto',
                bondCutoffScale: 1.25,
                manualBondPairs: [],
                elementBondCutoffs: {},
                atomRadiusScale: 1.0,
                elementRadii: {},
                rotatePivot: 'selection',
                unitCellAwareRotate: false,
                rotateStrainCutoff: 0.15,
                supercell: [1, 1, 1]
            },
            antiAliasing: true,
            sphereQuality: 'auto',
            applyConstraints: true,
            moveIncrement: 0,
            rotateIncrementDeg: 0,
            transformReadout: '',
            hoveredIndex: null,
            displayConfigLoaded: false,
            rotationScreenPivot: new THREE.Vector2(window.innerWidth / 2, window.innerHeight / 2),
            rotationLastAngle: 0,
            rotationPointerActive: false,
            rotationReferenceBonds: [],
            rotationInvalid: false,
            rotationMaxStrain: 0,
            rotationViolationCount: 0,
            trajectoryTimer: null,
            isRelaxing: false
        };

        this.init();
    }

    async init() {
        try {
            if (!this.sessionId) {
                const active = await this.api.fetchActiveSession();
                this.sessionId = active.session_id;
                this.api.sessionId = this.sessionId;
            }
            this.setupWebSocket();
            this.setupEventListeners();
            await this.refresh();
        } catch (err) {
            console.error("v_ase initialization failed:", err);
            this.toast(`Initialization failed: ${err.message}`, 'error');
        }
    }

    async refresh() {
        try {
            const data = await this.api.fetchAtoms();
            if (!data || !data.positions) return;

            this.state.atoms = data;
            this.state.originalPositions = data.positions.map(p => [...p]);
            this.applyInitialDisplayConfig(data);
            this.renderElementBondControls();
            this.renderElementRadiusControls();
            if (!this.initialDesignSettings) this.initialDesignSettings = this.designSettingsSnapshot();
            this.updateUI();
            
            this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
            this.renderer.setDisplayOptions(this.state.display);
            
            this.updateSelectionVisuals();
        } catch (err) {
            console.error("DEBUG: Refresh Failed:", err);
        }
    }

    updateUI() {
        this.pruneSelection();
        const meta = this.state.atoms.metadata;
        const selectedIndices = [...this.state.selected];
        const setHtml = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        
        setHtml('prop-natoms', meta.natoms);
        setHtml('val-calc', meta.calculator || "NONE");
        setHtml('val-mode', this.transform.mode === 'IDLE' ? 'SELECT' : this.transform.mode);
        setHtml('val-energy', typeof meta.energy === 'number' ? meta.energy.toFixed(4) : "-");
        const validForces = (this.state.atoms.forces || [])
            .filter(f => Array.isArray(f) && f.length >= 3 && f.slice(0, 3).every(v => Number.isFinite(Number(v))));
        if (validForces.length) {
            const fmax = Math.max(...validForces.map(f => Math.sqrt(Number(f[0]) ** 2 + Number(f[1]) ** 2 + Number(f[2]) ** 2)));
            setHtml('val-fmax', Number.isFinite(fmax) ? fmax.toFixed(4) : "-");
        } else {
            setHtml('val-fmax', "-");
        }
        
        const pbc = this.state.atoms.pbc.map(p => p ? 'T' : 'F').join('');
        setHtml('prop-pbc', pbc);
        setHtml('prop-selected', this.state.selected.size);
        setHtml('selected-indices', selectedIndices.join(', ') || '-');
        setHtml('selected-elements', selectedIndices.map(i => this.state.atoms.symbols[i]).join(', ') || '-');
        setHtml('selected-center', this.getSelectionCenterText());
        setHtml('selected-measure', this.getSelectionMeasureText(selectedIndices));
        this.updateTrajectoryUI();

        const relaxBtn = document.getElementById('btn-relax');
        if (relaxBtn) relaxBtn.disabled = !meta.has_calculator || this.state.isRelaxing;
        const stopRelaxBtn = document.getElementById('btn-stop-relax');
        if (stopRelaxBtn) stopRelaxBtn.disabled = !this.state.isRelaxing;

        this.updateCommandReadout();

        document.body.dataset.mode = this.transform.mode.toLowerCase();
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
            setHtml('cmd-mode', this.transform.mode);
            setHtml('cmd-axis', this.transform.axis || 'NONE');
            setHtml('cmd-val', this.commandValueText());
        } else {
            cmdBuf.classList.add('hidden');
        }
    }

    setAtomsData(data, { clearSelection = false } = {}) {
        this.state.atoms = data;
        this.state.originalPositions = data.positions.map(p => [...p]);
        if (clearSelection) {
            this.state.selected.clear();
        } else {
            this.pruneSelection();
        }
        this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
        this.renderer.setDisplayOptions(this.state.display);
        this.renderElementBondControls();
        this.renderElementRadiusControls();
        this.setHoveredAtom(null);
        this.updateSelectionVisuals();
        this.updateUI();
    }

    pruneSelection() {
        const count = this.state.atoms?.positions?.length || 0;
        this.state.selected.forEach(idx => {
            if (idx < 0 || idx >= count) this.state.selected.delete(idx);
        });
    }

    applyInitialDisplayConfig(data) {
        if (this.state.displayConfigLoaded) return;
        const config = data.metadata?.config || {};
        this.state.display.showBonds = Boolean(config.show_bonds);
        this.state.display.showCell = config.show_cell !== false;
        this.state.display.showAxes = config.show_axes !== false;
        this.state.display.showGrid = config.show_grid !== false;
        this.state.applyConstraints = config.apply_constraint !== false;
        this.state.antiAliasing = config.anti_aliasing !== false;
        this.state.sphereQuality = config.sphere_quality || 'auto';
        this.state.display.atomRadiusScale = Number(config.atom_radius_scale || 1.0);
        this.state.display.elementRadii = config.element_radii || {};
        this.state.display.rotatePivot = config.rotate_pivot || this.state.display.rotatePivot;
        this.state.display.unitCellAwareRotate = Boolean(config.unit_cell_aware_rotate);
        this.state.display.rotateStrainCutoff = Number(config.rotate_strain_cutoff || this.state.display.rotateStrainCutoff);
        document.getElementById('chk-bonds').checked = this.state.display.showBonds;
        document.getElementById('chk-cell').checked = this.state.display.showCell;
        document.getElementById('chk-axes').checked = this.state.display.showAxes;
        document.getElementById('chk-grid').checked = this.state.display.showGrid;
        document.getElementById('chk-constraints').checked = this.state.applyConstraints;
        document.getElementById('chk-antialias').checked = this.state.antiAliasing;
        document.getElementById('sphere-quality').value = this.state.sphereQuality;
        const radiusScale = document.getElementById('atom-radius-scale');
        if (radiusScale) radiusScale.value = this.state.display.atomRadiusScale;
        document.getElementById('rotate-pivot').value = this.state.display.rotatePivot;
        document.getElementById('chk-unit-aware-rotate').checked = this.state.display.unitCellAwareRotate;
        document.getElementById('rotate-strain-cutoff').value = this.state.display.rotateStrainCutoff;
        this.updateRadiusScaleLabel();
        this.state.displayConfigLoaded = true;
    }

    updateTrajectoryUI() {
        const meta = this.state.atoms?.metadata || {};
        const count = meta.frame_count || 1;
        const index = meta.current_frame || 0;
        const panel = document.getElementById('trajectory-panel');
        if (panel) panel.classList.toggle('hidden', count <= 1);
        const slider = document.getElementById('frame-slider');
        if (slider) {
            slider.max = Math.max(0, count - 1);
            slider.value = index;
        }
        const label = document.getElementById('frame-label');
        if (label) label.innerText = `${Math.min(index + 1, count)} / ${count}`;
        const play = document.getElementById('btn-play');
        if (play) play.innerText = this.state.trajectoryTimer ? '⏸' : '▶';
        const exportVideo = document.getElementById('btn-export-video');
        if (exportVideo) {
            exportVideo.disabled = count <= 1;
            exportVideo.title = count <= 1 ? 'Export Video is available for trajectory files only.' : 'Export the trajectory as a WebM video.';
        }
    }

    updateSelectionVisuals() {
        this.renderer.setSelection(this.state.selected);
    }

    getFixedIndices() {
        return new Set(this.state.atoms?.constraints?.fixed_indices || []);
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
        const positions = this.state.atoms.positions.map(p => [...p]);
        this.renderer.atomMeshes.children.forEach(mesh => {
            const idx = mesh.userData.index;
            if (idx === undefined || mesh.userData.lockMarker) return;
            positions[idx] = [mesh.position.x, mesh.position.y, mesh.position.z];
        });
        return positions;
    }

    currentCameraForExport() {
        const camera = this.renderer.camera;
        const controls = this.renderer.controls;
        camera.updateMatrixWorld();
        return {
            position: [camera.position.x, camera.position.y, camera.position.z],
            target: [controls.target.x, controls.target.y, controls.target.z],
            up: [camera.up.x, camera.up.y, camera.up.z],
            fov: camera.fov,
            near: camera.near,
            far: camera.far
        };
    }

    getSelectionCenterText() {
        if (!this.state.atoms || this.state.selected.size === 0) return '-';
        const center = [0, 0, 0];
        let count = 0;
        this.state.selected.forEach(i => {
            const p = this.currentAtomPosition(i);
            if (!p) return;
            center[0] += p[0]; center[1] += p[1]; center[2] += p[2];
            count++;
        });
        if (!count) return '-';
        return center.map(v => (v / count).toFixed(3)).join(', ');
    }

    selectionDelta(i, j) {
        const start = this.renderer.getAtomPosition?.(i);
        if (start && this.renderer.minimumImageDelta) {
            return this.renderer.minimumImageDelta(i, j, start);
        }
        const pi = this.currentAtomPosition(i);
        const pj = this.currentAtomPosition(j);
        if (!pi || !pj) return null;
        return new THREE.Vector3(pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2]);
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

    getSelectionMeasureText(selectedIndices = [...this.state.selected]) {
        if (!this.state.atoms || selectedIndices.length < 2) return '-';
        if (selectedIndices.length === 2) {
            const [i, j] = selectedIndices;
            const distance = this.selectionDistance(i, j);
            return Number.isFinite(distance) ? `d(${i}-${j}) = ${this.formatNumber(distance, 4)} A` : '-';
        }
        if (selectedIndices.length === 3) {
            const [i, j, k] = selectedIndices;
            const left = this.selectionDistance(i, j);
            const right = this.selectionDistance(j, k);
            const angle = this.selectionAngle(i, j, k);
            if (![left, right, angle].every(Number.isFinite)) return '-';
            return `d(${i}-${j}) = ${this.formatNumber(left, 4)} A | d(${j}-${k}) = ${this.formatNumber(right, 4)} A | angle(${i}-${j}-${k}) = ${this.formatNumber(angle, 2)} deg`;
        }
        return `${selectedIndices.length} atoms selected`;
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
        const dir = axisVectors[axis];
        if (!dir) return;
        const camera = this.renderer.camera;
        const controls = this.renderer.controls;
        const target = controls.target.clone();
        const distance = Math.max(camera.position.distanceTo(target), 4.0);
        camera.up.copy(axis === 'Z' ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(0, 0, 1));
        camera.position.copy(target).add(dir.clone().multiplyScalar(distance));
        camera.lookAt(target);
        controls.target.copy(target);
        controls.endGesture?.();
        controls.update?.();
        this.renderer.syncSelectionOutlines();
        this.transform.updateGuides(camera);
    }

    currentAtomPosition(index) {
        const mesh = this.renderer.atomMeshByIndex.get(index);
        if (mesh) return [mesh.position.x, mesh.position.y, mesh.position.z];
        return this.state.atoms?.positions?.[index] || null;
    }

    atomHoverText(index) {
        if (index === null || index === undefined || !this.state.atoms?.symbols?.[index]) {
            return 'Hover atom: -';
        }
        const symbol = this.state.atoms.symbols[index];
        const pos = this.currentAtomPosition(index);
        const force = this.state.atoms.forces?.[index] || null;
        const charge = this.state.atoms.charges?.[index];
        const tag = this.state.atoms.tags?.[index];
        const magmom = this.state.atoms.magmoms?.[index];
        const parts = [
            `#${index} ${symbol}`,
            `pos=${this.formatVectorTuple(pos)}`,
            `force=${this.formatVectorTuple(force)}`,
            `charge=${this.formatNumber(Number(charge), 4)}`,
            `tag=${tag ?? '-'}`,
            `magmom=${this.formatNumber(Number(magmom), 4)}`
        ];
        return parts.join('  |  ');
    }

    setHoveredAtom(index) {
        const normalized = index === null || index === undefined ? null : index;
        if (this.state.hoveredIndex === normalized) return;
        this.state.hoveredIndex = normalized;
        const readout = document.getElementById('hover-readout');
        if (readout) readout.innerText = this.atomHoverText(normalized);
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

    applyTransformPreview() {
        if (this.transform.mode === 'IDLE') return;

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
        
        // FOV factor
        const fov = camera.fov * Math.PI / 180;
        const heightPlane = 2 * Math.tan(fov / 2) * dist;
        const widthPlane = heightPlane * camera.aspect;
        
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
        if (this.transform.mode === 'ROTATE') {
            let angle = 0;
            if (hasNum) {
                angle = THREE.MathUtils.degToRad(numVal);
            } else {
                angle = this.transform.rotationAngle;
            }
            if (!hasNum) angle = this.snapRotationAngle(angle);
            if (!Number.isFinite(angle)) angle = 0;
            this.state.transformReadout = this.formatRotateReadout(angle);
            
            if (this.transform.axis) {
                q.setFromAxisAngle(axisVec, angle);
            } else {
                q.setFromAxisAngle(viewAxis, angle); // Free rotate around current view axis
            }
        }

        this.renderer.atomMeshes.children.forEach(mesh => {
            const idx = mesh.userData.index;
            if (mesh.userData.lockMarker || idx === undefined) return;
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
            }
        });
        this.renderer.syncSelectionOutlines();
        this.renderer.updateBondPositions();
        this.renderer.updateSupercellPositions();
        this.renderer.updateHookeanPositions();
        const measure = document.getElementById('selected-measure');
        if (measure) measure.innerText = this.getSelectionMeasureText();
        if (this.transform.mode === 'ROTATE') {
            this.validateRotationStrain();
        }
        
        // Async backend projection is only needed for translation. Rotation
        // already projects each atom's displacement through the same local
        // line/plane/fixed constraints before commit.
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        if (this.transform.mode === 'MOVE') {
            this.constraintTimeout = setTimeout(() => this.previewConstraints(), 50);
        }
        this.updateCommandReadout();
    }
    
    async previewConstraints() {
        if (!this.state.applyConstraints) return;
        if (this.transform.mode !== 'MOVE' || this.state.selected.size === 0) return;
        const newPositions = this.currentPositionsFromScene();
        try {
            const data = await this.api.getConstrainedPositions(newPositions, this.state.applyConstraints);
            if (data.positions && this.transform.mode !== 'IDLE') {
                this.renderer.atomMeshes.children.forEach(mesh => {
                    if (mesh.userData.lockMarker || mesh.userData.index === undefined) return;
                    if (this.state.selected.has(mesh.userData.index)) {
                        const p = data.positions[mesh.userData.index];
                        if (p && p.every(Number.isFinite)) mesh.position.set(p[0], p[1], p[2]);
                    }
                });
                this.renderer.syncSelectionOutlines();
                this.renderer.updateBondPositions();
                this.renderer.updateSupercellPositions();
                this.renderer.updateHookeanPositions();
                const measure = document.getElementById('selected-measure');
                if (measure) measure.innerText = this.getSelectionMeasureText();
            }
        } catch (err) {
            console.error("Constraint preview error:", err);
        }
    }

    commitTransform() {
        if (this.transform.mode === 'IDLE' || this.state.selected.size === 0) return;
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        if (this.transform.mode === 'ROTATE' && this.state.rotationInvalid) {
            this.toast(
                `Rotate blocked: ${this.state.rotationViolationCount} bond strain violation${this.state.rotationViolationCount > 1 ? 's' : ''}.`,
                'error'
            );
            return;
        }
        
        const newPositions = this.currentPositionsFromScene();
        this.state.atoms.positions = newPositions.map(p => [...p]);
        this.state.originalPositions = newPositions.map(p => [...p]);
        this.state.transformReadout = '';
        this.state.rotationInvalid = false;
        this.state.rotationReferenceBonds = [];
        this.renderer.clearStrainViolations?.();
        delete document.body.dataset.rotateInvalid;

        // Confirm immediately in the viewport. Backend apply follows asynchronously
        // and may correct constrained positions authoritatively.
        this.transform.exit();
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
        this.transform.enter(mode, pivot, this.renderer.camera);
        this.prepareRotationValidation(editableSelection);
        this.renderer.controls.enabled = false;
        this.updateToolState();
        this.updateUI();
    }

    cancelTransform() {
        if (this.constraintTimeout) clearTimeout(this.constraintTimeout);
        this.renderer.updatePositions(this.state.originalPositions);
        this.state.transformReadout = '';
        this.state.rotationInvalid = false;
        this.state.rotationReferenceBonds = [];
        this.renderer.clearStrainViolations?.();
        delete document.body.dataset.rotateInvalid;
        this.transform.exit();
        this.renderer.controls.enabled = true;
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
        return [...new Set(this.state.atoms?.symbols || [])].sort();
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
        const ri = this.elementCovalentRadius(a);
        const rj = this.elementCovalentRadius(b);
        const scale = Math.max(0.5, parseFloat(document.getElementById('bond-cutoff')?.value || '1.25'));
        return Math.max(0.55, (ri + rj) * scale);
    }

    elementCovalentRadius(symbol) {
        const radii = this.state.atoms?.visual?.covalent_radii || [];
        const symbols = this.state.atoms?.symbols || [];
        const values = radii.filter((_, index) => symbols[index] === symbol).map(Number).filter(Number.isFinite);
        if (!values.length) return 0.75;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    elementVisualRadius(symbol) {
        const radii = this.state.atoms?.visual?.radii || [];
        const symbols = this.state.atoms?.symbols || [];
        const values = radii.filter((_, index) => symbols[index] === symbol).map(Number).filter(Number.isFinite);
        if (!values.length) return this.elementCovalentRadius(symbol);
        return values.reduce((sum, value) => sum + value, 0) / values.length;
    }

    updateRadiusScaleLabel() {
        const scale = Number(document.getElementById('atom-radius-scale')?.value || this.state.display.atomRadiusScale || 1);
        const label = document.getElementById('atom-radius-scale-value');
        if (label) label.innerText = `${(Number.isFinite(scale) ? scale : 1).toFixed(2)}x`;
    }

    renderElementRadiusControls() {
        const root = document.getElementById('element-radius-list');
        if (!root || !this.state.atoms?.symbols) return;
        const existingFocus = document.activeElement?.dataset?.elementRadius;
        root.innerHTML = '';
        this.uniqueElements().forEach(symbol => {
            if (!(symbol in this.state.display.elementRadii)) {
                this.state.display.elementRadii[symbol] = Number(this.elementVisualRadius(symbol).toFixed(4));
            }
            const row = document.createElement('div');
            row.className = 'element-radius-row';
            const label = document.createElement('label');
            label.htmlFor = `element-radius-${symbol}`;
            label.innerText = symbol;
            const input = document.createElement('input');
            input.type = 'number';
            input.id = `element-radius-${symbol}`;
            input.className = 'element-radius-input';
            input.dataset.elementRadius = symbol;
            input.min = '0.05';
            input.step = '0.01';
            input.value = this.state.display.elementRadii[symbol];
            input.addEventListener('change', () => this.safeApplyDisplayOptions());
            input.addEventListener('input', () => this.safeApplyDisplayOptions());
            row.append(label, input);
            root.appendChild(row);
        });
        if (existingFocus) {
            root.querySelector(`[data-element-radius="${existingFocus}"]`)?.focus();
        }
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

    renderElementBondControls() {
        const root = document.getElementById('element-bond-list');
        if (!root || !this.state.atoms?.symbols) return;
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
            if (Number.isFinite(value) && value > 0) {
                cutoffs[input.dataset.pairKey] = value;
            }
        });
        return cutoffs;
    }

    updateBondModeUI() {
        const mode = document.getElementById('bond-mode')?.value || this.state.display.bondMode;
        const elementPanel = document.getElementById('element-bond-panel');
        const pairText = document.getElementById('bond-pairs');
        const cutoffRow = document.getElementById('bond-cutoff')?.closest('.prop-row');
        if (elementPanel) elementPanel.classList.toggle('hidden', mode !== 'element');
        if (pairText) pairText.classList.toggle('hidden', mode !== 'manual');
        if (cutoffRow) cutoffRow.classList.toggle('hidden', mode === 'manual');
    }

    parseBondPairs() {
        const text = document.getElementById('bond-pairs').value.trim();
        if (!text) return [];
        const count = this.state.atoms?.positions?.length || 0;
        const pairs = [];
        const seen = new Set();
        const tokens = text.split(/[\n,;]+/).map(v => v.trim()).filter(Boolean);
        tokens.forEach(token => {
            const elementMatch = token.match(/^([A-Z][a-z]?)\s*[-:]\s*([A-Z][a-z]?)\s*(?:[:=]\s*)?([0-9]*\.?[0-9]+)$/);
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
        this.state.display.showBonds = document.getElementById('chk-bonds').checked;
        this.state.display.showCell = document.getElementById('chk-cell').checked;
        this.state.display.showAxes = document.getElementById('chk-axes').checked;
        this.state.display.showGrid = document.getElementById('chk-grid').checked;
        this.state.applyConstraints = document.getElementById('chk-constraints').checked;
        this.state.antiAliasing = document.getElementById('chk-antialias').checked;
        this.state.sphereQuality = document.getElementById('sphere-quality').value;
        this.state.display.rotatePivot = document.getElementById('rotate-pivot')?.value || 'selection';
        this.state.display.unitCellAwareRotate = Boolean(document.getElementById('chk-unit-aware-rotate')?.checked);
        const strainCutoff = parseFloat(document.getElementById('rotate-strain-cutoff')?.value || '0.15');
        this.state.display.rotateStrainCutoff = Number.isFinite(strainCutoff) && strainCutoff >= 0 ? strainCutoff : 0.15;
        this.state.display.bondMode = document.getElementById('bond-mode').value;
        this.state.display.bondCutoffScale = Math.max(0.5, parseFloat(document.getElementById('bond-cutoff').value || '1.25'));
        this.state.display.elementBondCutoffs = this.parseElementBondCutoffs();
        const radiusScale = parseFloat(document.getElementById('atom-radius-scale')?.value || '1');
        this.state.display.atomRadiusScale = Number.isFinite(radiusScale) && radiusScale > 0 ? radiusScale : 1.0;
        this.state.display.elementRadii = this.parseElementRadii();
        if (this.state.display.bondMode === 'manual') {
            this.state.display.manualBondPairs = this.parseBondPairs();
        }
        this.state.display.supercell = this.normalizeSupercellInputs();
        this.state.display.antiAliasing = this.state.antiAliasing;
        this.state.display.sphereQuality = this.state.sphereQuality;
        this.updateRadiusScaleLabel();
        this.renderer.setDisplayOptions(this.state.display);
        this.updateSelectionVisuals();
        this.updateBondModeUI();
    }

    safeApplyDisplayOptions() {
        try {
            this.applyDisplayOptions();
        } catch (err) {
            this.toast(err.message, 'error');
        }
    }

    clonePlain(value) {
        if (window.structuredClone) return window.structuredClone(value);
        return JSON.parse(JSON.stringify(value));
    }

    designSettingsSnapshot() {
        this.readTransformSettings();
        return {
            schema: 'v_ase.visual_settings.v1',
            display: this.clonePlain(this.state.display),
            applyConstraints: this.state.applyConstraints,
            antiAliasing: this.state.antiAliasing,
            sphereQuality: this.state.sphereQuality,
            moveIncrement: this.state.moveIncrement,
            rotateIncrementDeg: this.state.rotateIncrementDeg
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
        setChecked('chk-constraints', this.state.applyConstraints);
        setChecked('chk-antialias', this.state.antiAliasing);
        setValue('sphere-quality', this.state.sphereQuality);
        setValue('rotate-pivot', display.rotatePivot || 'selection');
        setChecked('chk-unit-aware-rotate', display.unitCellAwareRotate);
        setValue('rotate-strain-cutoff', display.rotateStrainCutoff ?? 0.15);
        setValue('bond-mode', display.bondMode || 'auto');
        setValue('bond-cutoff', display.bondCutoffScale || 1.25);
        setValue('atom-radius-scale', display.atomRadiusScale || 1);
        setValue('move-increment', this.state.moveIncrement || 0);
        setValue('rotate-increment', this.state.rotateIncrementDeg || 0);
        this.setSupercellInputs(display.supercell || [1, 1, 1]);
        this.writeBondPairs(display.manualBondPairs || []);
        this.updateRadiusScaleLabel();
    }

    applyDesignSettings(settings, { render = true } = {}) {
        if (!settings) return;
        const source = settings.settings || settings;
        const nextDisplay = source.display || source;
        this.state.display = {
            ...this.state.display,
            ...this.clonePlain(nextDisplay),
            manualBondPairs: this.clonePlain(nextDisplay.manualBondPairs || []),
            elementBondCutoffs: this.clonePlain(nextDisplay.elementBondCutoffs || {}),
            elementRadii: this.clonePlain(nextDisplay.elementRadii || {}),
            supercell: this.clonePlain(nextDisplay.supercell || [1, 1, 1])
        };
        if ('applyConstraints' in source) this.state.applyConstraints = Boolean(source.applyConstraints);
        if ('antiAliasing' in source) this.state.antiAliasing = Boolean(source.antiAliasing);
        if ('sphereQuality' in source) this.state.sphereQuality = source.sphereQuality || 'auto';
        if ('moveIncrement' in source) this.state.moveIncrement = Number(source.moveIncrement) || 0;
        if ('rotateIncrementDeg' in source) this.state.rotateIncrementDeg = Number(source.rotateIncrementDeg) || 0;
        this.syncDesignControls();
        this.renderElementBondControls();
        this.renderElementRadiusControls();
        this.syncDesignControls();
        if (render) {
            this.renderer.setDisplayOptions(this.state.display);
            this.updateSelectionVisuals();
            this.updateBondModeUI();
            this.updateUI();
        }
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
                () => this.api.applySupercell(this.currentPositionsFromScene(), reps, this.state.applyConstraints)
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
                () => this.api.applySupercellMatrix(this.currentPositionsFromScene(), matrix, this.state.applyConstraints)
            );
            this.setAtomsData(data, { clearSelection: true });
            this.setSupercellMatrixInputs();
            this.toast('Applied make_supercell matrix to all frames.', 'success');
        } catch (err) {
            this.toast(`make_supercell failed: ${err.message}`, 'error');
        }
    }

    copySelection() {
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

    basisVectors() {
        const cell = this.state.atoms?.cell || [];
        if (!this.hasUsableCell() || cell.length < 3) return null;
        return cell.map(v => new THREE.Vector3(...v));
    }

    cartToFracVector(cart, basis) {
        const det = basis[0].dot(new THREE.Vector3().crossVectors(basis[1], basis[2]));
        if (Math.abs(det) < 1e-10) return cart.clone();
        return new THREE.Vector3(
            cart.dot(new THREE.Vector3().crossVectors(basis[1], basis[2])) / det,
            cart.dot(new THREE.Vector3().crossVectors(basis[2], basis[0])) / det,
            cart.dot(new THREE.Vector3().crossVectors(basis[0], basis[1])) / det
        );
    }

    fracToCartVector(frac, basis) {
        return new THREE.Vector3()
            .addScaledVector(basis[0], frac.x)
            .addScaledVector(basis[1], frac.y)
            .addScaledVector(basis[2], frac.z);
    }

    minimumImageDeltaFromPositions(positions, i, j) {
        const start = new THREE.Vector3(...positions[i]);
        const end = new THREE.Vector3(...positions[j]);
        const delta = new THREE.Vector3().subVectors(end, start);
        const pbc = this.state.atoms?.pbc || [false, false, false];
        const basis = this.basisVectors();
        if (!basis || !pbc.some(Boolean)) return delta;
        const frac = this.cartToFracVector(delta, basis);
        for (let axis = 0; axis < 3; axis++) {
            if (pbc[axis]) frac.setComponent(axis, frac.getComponent(axis) - Math.round(frac.getComponent(axis)));
        }
        return this.fracToCartVector(frac, basis);
    }

    rotationValidationEnabled() {
        return (
            this.transform.mode === 'ROTATE'
            && Boolean(this.state.display.unitCellAwareRotate)
            && this.hasUsableCell()
            && (this.state.atoms?.pbc || []).some(Boolean)
        );
    }

    prepareRotationValidation(editableSelection) {
        this.state.rotationReferenceBonds = [];
        this.state.rotationInvalid = false;
        this.state.rotationMaxStrain = 0;
        this.state.rotationViolationCount = 0;
        this.renderer.clearStrainViolations?.();
        delete document.body.dataset.rotateInvalid;

        if (!this.rotationValidationEnabled()) return;
        const selected = new Set(editableSelection);
        const pairs = this.renderer.bondPairs?.length ? this.renderer.bondPairs : (this.renderer.inferBondPairs?.() || []);
        const seen = new Set();
        pairs.forEach(([i, j]) => {
            if (!selected.has(i) && !selected.has(j)) return;
            const key = `${Math.min(i, j)}-${Math.max(i, j)}`;
            if (seen.has(key)) return;
            seen.add(key);
            const delta = this.minimumImageDeltaFromPositions(this.state.originalPositions, i, j);
            const length = delta.length();
            if (Number.isFinite(length) && length > 1e-6) {
                this.state.rotationReferenceBonds.push({ i, j, length });
            }
        });
    }

    validateRotationStrain() {
        this.state.rotationInvalid = false;
        this.state.rotationMaxStrain = 0;
        this.state.rotationViolationCount = 0;
        this.renderer.clearStrainViolations?.();
        delete document.body.dataset.rotateInvalid;
        if (!this.rotationValidationEnabled() || !this.state.rotationReferenceBonds.length) return;

        const cutoff = Math.max(0, Number(this.state.display.rotateStrainCutoff ?? 0.15));
        const positions = this.currentPositionsFromScene();
        const violations = [];
        let maxStrain = 0;
        this.state.rotationReferenceBonds.forEach(ref => {
            const delta = this.minimumImageDeltaFromPositions(positions, ref.i, ref.j);
            const length = delta.length();
            if (!Number.isFinite(length)) return;
            const strain = Math.abs(length - ref.length) / Math.max(ref.length, 1e-9);
            maxStrain = Math.max(maxStrain, strain);
            if (strain > cutoff) {
                const start = new THREE.Vector3(...positions[ref.i]);
                const end = start.clone().add(delta);
                violations.push({
                    i: ref.i,
                    j: ref.j,
                    strain,
                    start: start.toArray(),
                    end: end.toArray()
                });
            }
        });

        this.state.rotationMaxStrain = maxStrain;
        this.state.rotationViolationCount = violations.length;
        if (violations.length) {
            this.state.rotationInvalid = true;
            document.body.dataset.rotateInvalid = 'true';
            this.state.transformReadout = `INVALID strain ${(maxStrain * 100).toFixed(1)}% > ${(cutoff * 100).toFixed(1)}%`;
            this.renderer.setStrainViolations?.(violations);
        }
    }

    setupWebSocket() {
        if (!this.sessionId) return;
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const ws = new WebSocket(`${protocol}://${window.location.host}/ws/${this.sessionId}`);
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'relax_step') {
                this.state.atoms.positions = msg.positions;
                this.state.originalPositions = msg.positions.map(p => [...p]);
                this.renderer.updatePositions(msg.positions);
                const energy = document.getElementById('val-energy');
                const fmax = document.getElementById('val-fmax');
                if (energy) energy.innerText = msg.energy.toFixed(6);
                if (fmax) fmax.innerText = msg.fmax.toFixed(6);
            }
            if (msg.type === 'relax_finished') {
                this.state.isRelaxing = false;
                this.toast(`Relax ${msg.status}.`, msg.status === 'error' ? 'error' : 'success');
                this.updateUI();
                this.refresh();
            }
        };
    }

    downloadBlob(blob, filename, mimeType = 'application/octet-stream') {
        const fileBlob = blob.type === mimeType ? blob : new Blob([blob], { type: mimeType });
        const url = URL.createObjectURL(fileBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    downloadDataUrl(dataUrl, filename) {
        const a = document.createElement('a');
        a.href = dataUrl;
        a.download = filename;
        a.click();
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

    showShortcutsModal() {
        this.showModal(`
            <h2>Shortcuts</h2>
            <div class="shortcut-grid">
                <span>Left click</span><label>Select / confirm transform</label>
                <span>Shift + click</span><label>Add or remove selection</label>
                <span>Left drag</span><label>Box select</label>
                <span>Middle drag</span><label>Orbit viewport</label>
                <span>Right drag</span><label>Pan viewport</label>
                <span>Space</span><label>Play or pause trajectory</label>
                <span>G</span><label>Move selected atoms</label>
                <span>R</span><label>Rotate selected atoms</label>
                <span>X / Y / Z</span><label>Align view in select mode</label>
                <span>X / Y / Z</span><label>Lock transform axis in G/R mode</label>
                <span>Enter</span><label>Confirm transform</label>
                <span>Esc</span><label>Cancel transform</label>
                <span>Ctrl+C / V / Z</span><label>Copy, paste, undo</label>
                <span>Delete</span><label>Delete selected atoms</label>
            </div>
        `);
    }

    showExportImageModal() {
        const width = Math.max(256, parseInt(document.getElementById('image-width').value || '1920', 10));
        const height = Math.max(256, parseInt(document.getElementById('image-height').value || '1080', 10));
        this.showModal(`
            <h2>Export Image</h2>
            <div class="export-grid">
                <label for="export-width">Width</label>
                <input type="number" id="export-width" value="${width}" min="256" step="128">
                <label for="export-height">Height</label>
                <input type="number" id="export-height" value="${height}" min="256" step="128">
            </div>
            <label class="check-row" for="export-transparent">
                <span>Transparent background</span>
                <input type="checkbox" id="export-transparent">
            </label>
            <label class="check-row" for="export-grid">
                <span>Include grid</span>
                <input type="checkbox" id="export-grid" ${this.state.display.showGrid ? 'checked' : ''}>
            </label>
            <label class="check-row" for="export-axes">
                <span>Include axes</span>
                <input type="checkbox" id="export-axes" ${this.state.display.showAxes ? 'checked' : ''}>
            </label>
        `, `
            <button id="modal-close" class="btn">Cancel</button>
            <button id="modal-export-image" class="btn primary">Export</button>
        `);

        document.getElementById('modal-export-image')?.addEventListener('click', () => {
            try {
                const exportWidth = Math.max(256, parseInt(document.getElementById('export-width').value || `${width}`, 10));
                const exportHeight = Math.max(256, parseInt(document.getElementById('export-height').value || `${height}`, 10));
                const transparentBackground = document.getElementById('export-transparent').checked;
                const includeGrid = document.getElementById('export-grid').checked;
                const includeAxes = document.getElementById('export-axes').checked;
                const dataUrl = this.renderer.exportPNG(exportWidth, exportHeight, {
                    transparentBackground,
                    includeGrid,
                    includeAxes
                });
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
        const width = Math.max(256, parseInt(document.getElementById('image-width').value || '1280', 10));
        const height = Math.max(256, parseInt(document.getElementById('image-height').value || '720', 10));
        const fps = Math.min(60, Math.max(1, parseFloat(document.getElementById('movie-fps').value || '12')));
        this.showModal(`
            <h2>Export Video</h2>
            <p class="modal-intro">Render the loaded trajectory as a WebM movie.</p>
            <div class="export-grid">
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
        `, `
            <button id="modal-close" class="btn">Cancel</button>
            <button id="modal-export-video" class="btn primary">Export</button>
        `);

        document.getElementById('modal-export-video')?.addEventListener('click', async () => {
            try {
                await this.exportTrajectoryVideo({
                    width: Math.max(256, parseInt(document.getElementById('video-width').value || `${width}`, 10)),
                    height: Math.max(256, parseInt(document.getElementById('video-height').value || `${height}`, 10)),
                    fps: Math.min(60, Math.max(1, parseFloat(document.getElementById('video-fps').value || `${fps}`))),
                    includeGrid: document.getElementById('video-grid').checked,
                    includeAxes: document.getElementById('video-axes').checked
                });
            } catch (err) {
                this.toast(`Video export failed: ${err.message}`, 'error');
            }
        });
    }

    async exportTrajectoryVideo({ width, height, fps, includeGrid, includeAxes }) {
        const meta = this.state.atoms?.metadata || {};
        const frameCount = meta.frame_count || 1;
        if (frameCount <= 1) throw new Error('A trajectory with at least two frames is required.');
        const canvas = this.renderer.domElement;
        if (!canvas.captureStream || !window.MediaRecorder) {
            throw new Error('This browser does not support canvas video recording.');
        }

        const originalFrame = meta.current_frame || 0;
        const oldSize = new THREE.Vector2();
        this.renderer.renderer.getSize(oldSize);
        const oldPixelRatio = this.renderer.renderer.getPixelRatio();
        const oldAspect = this.renderer.camera.aspect;
        const oldGridVisible = this.renderer.gridGroup?.visible;
        const oldAxesVisible = this.renderer.axesHelper?.visible;
        const chunks = [];
        const stream = canvas.captureStream(fps);
        const mimeType = MediaRecorder.isTypeSupported?.('video/webm;codecs=vp9')
            ? 'video/webm;codecs=vp9'
            : 'video/webm';
        const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8_000_000 });
        const finished = new Promise((resolve, reject) => {
            recorder.ondataavailable = event => {
                if (event.data && event.data.size) chunks.push(event.data);
            };
            recorder.onerror = () => reject(recorder.error || new Error('MediaRecorder failed.'));
            recorder.onstop = () => resolve();
        });

        const applyExportVisibility = () => {
            if (this.renderer.gridGroup) this.renderer.gridGroup.visible = includeGrid && this.state.display.showGrid;
            if (this.renderer.axesHelper) this.renderer.axesHelper.visible = includeAxes && this.state.display.showAxes;
        };

        this.closeModal();
        this.setBusy(`Rendering ${frameCount} trajectory frames...`);
        recorder.start(100);
        try {
            this.renderer.renderer.setPixelRatio(1);
            this.renderer.renderer.setSize(width, height, false);
            this.renderer.camera.aspect = width / height;
            this.renderer.camera.updateProjectionMatrix();
            for (let frame = 0; frame < frameCount; frame++) {
                await this.loadFrame(frame);
                applyExportVisibility();
                this.renderer.updateBondPositions();
                this.renderer.syncSelectionOutlines();
                this.renderer.renderer.render(this.renderer.scene, this.renderer.camera);
                await new Promise(resolve => setTimeout(resolve, 1000 / fps));
            }
            recorder.stop();
            await finished;
            const blob = new Blob(chunks, { type: mimeType });
            this.downloadBlob(blob, 'v_ase-trajectory.webm', mimeType);
            this.toast('Video export started.', 'success');
        } finally {
            stream.getTracks().forEach(track => track.stop());
            if (recorder.state !== 'inactive') recorder.stop();
            this.renderer.renderer.setPixelRatio(oldPixelRatio);
            this.renderer.renderer.setSize(oldSize.x, oldSize.y, false);
            this.renderer.camera.aspect = oldAspect;
            this.renderer.camera.updateProjectionMatrix();
            if (this.renderer.gridGroup) this.renderer.gridGroup.visible = oldGridVisible;
            if (this.renderer.axesHelper) this.renderer.axesHelper.visible = oldAxesVisible;
            await this.loadFrame(originalFrame);
            this.clearBusy();
        }
    }

    async loadFrame(index) {
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        const data = await this.api.setFrame(index);
        this.setAtomsData(data, { clearSelection: true });
    }

    queueFrameLoad(index) {
        const meta = this.state.atoms?.metadata || {};
        const count = meta.frame_count || 1;
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

    async stepFrame(delta) {
        const meta = this.state.atoms.metadata;
        const count = meta.frame_count || 1;
        if (count <= 1) return;
        const next = (meta.current_frame + delta + count) % count;
        await this.loadFrame(next);
    }

    currentPlaybackFps() {
        return Math.min(60, Math.max(1, parseFloat(document.getElementById('movie-fps').value || '12')));
    }

    stopPlayback() {
        if (this.state.trajectoryTimer) {
            clearTimeout(this.state.trajectoryTimer);
            this.state.trajectoryTimer = null;
            this.updateTrajectoryUI();
        }
    }

    startPlayback() {
        const meta = this.state.atoms?.metadata || {};
        if ((meta.frame_count || 1) <= 1 || this.state.trajectoryTimer) return;
        const tick = async () => {
            if (!this.state.trajectoryTimer) return;
            try {
                await this.stepFrame(1);
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

    restartPlayback() {
        if (!this.state.trajectoryTimer) return;
        this.stopPlayback();
        this.startPlayback();
    }

    togglePlayback() {
        if (this.state.trajectoryTimer) {
            this.stopPlayback();
            return;
        }
        this.startPlayback();
        this.updateTrajectoryUI();
    }

    setupEventListeners() {
        window.addEventListener('resize', () => this.renderer.onResize());
        
        document.getElementById('btn-done').onclick = async () => {
            try {
                await this.pendingApply;
                await this.api.done(this.currentPositionsFromScene(), this.state.applyConstraints);
                this.toast('Done. Python return value is ready.', 'success');
            } catch (err) {
                this.toast(`Done failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-cancel').onclick = async () => {
            try {
                await this.api.cancel();
                this.toast('Cancelled.', 'success');
            } catch (err) {
                this.toast(`Cancel failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-apply').onclick = async () => {
            try {
                const data = await this.api.applyPositions(this.currentPositionsFromScene(), this.state.applyConstraints);
                this.setAtomsData(data);
                this.toast(this.state.applyConstraints ? 'Applied constraints and positions.' : 'Applied positions without constraints.', 'success');
            } catch (err) {
                this.toast(`Apply failed: ${err.message}`, 'error');
            }
        };
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
                const frameCount = this.state.atoms.metadata.frame_count || 1;
                const data = await this.withBusy(
                    `Wrapping ${frameCount} frame${frameCount > 1 ? 's' : ''} into the unit cell...`,
                    () => this.api.wrap(this.currentPositionsFromScene(), this.state.applyConstraints)
                );
                this.setAtomsData(data);
                this.toast('Wrapped atoms into the unit cell for all frames.', 'success');
            } catch (err) {
                this.toast(`Wrap failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-delete-selection').onclick = () => this.deleteSelection();
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
                const blob = await this.api.exportPoscar(this.currentPositionsFromScene(), this.state.applyConstraints);
                this.downloadBlob(blob, 'POSCAR');
                this.toast('POSCAR export started.', 'success');
            } catch (err) {
                this.toast(`POSCAR export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-pickle').onclick = async () => {
            try {
                const blob = await this.api.exportPickle(this.currentPositionsFromScene(), false, this.state.applyConstraints);
                this.downloadBlob(blob, 'atoms.pkl');
                this.toast('Pickle export started.', 'success');
            } catch (err) {
                this.toast(`Pickle export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-blender').onclick = async () => {
            try {
                const blob = await this.api.exportBlender(
                    this.currentPositionsFromScene(),
                    this.state.applyConstraints,
                    this.currentCameraForExport()
                );
                this.downloadBlob(blob, 'v_ase_blender_scene.py', 'text/x-python');
                this.toast('Blender export script started.', 'success');
            } catch (err) {
                this.toast(`Blender export failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-export-image').onclick = () => {
            this.showExportImageModal();
        };
        document.getElementById('btn-export-video').onclick = () => {
            this.showExportVideoModal();
        };
        document.getElementById('btn-save-settings').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const blob = await this.api.saveVisualSettings(this.designSettingsSnapshot());
                this.downloadBlob(blob, 'v_ase_visual_settings.pkl');
                this.toast('Visual settings saved.', 'success');
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
                this.toast('Visual settings loaded.', 'success');
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
                const response = await this.api.relaxStart(this.currentPositionsFromScene(), fmax, steps, this.state.applyConstraints);
                if (response.status === 'started') {
                    this.state.isRelaxing = true;
                    this.toast('Relaxation started.', 'success');
                } else {
                    this.toast(response.message || 'Relaxation did not start.', 'warning');
                }
                this.updateUI();
            } catch (err) {
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
        document.getElementById('chk-bonds').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-cell').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-axes').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-grid').onchange = () => this.safeApplyDisplayOptions();
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
        document.getElementById('btn-play').onclick = () => this.togglePlayback();
        document.getElementById('frame-slider').oninput = (e) => {
            this.queueFrameLoad(e.target.value);
        };
        document.getElementById('frame-slider').onchange = (e) => {
            this.queueFrameLoad(e.target.value);
        };
        document.getElementById('movie-fps').oninput = () => {
            this.restartPlayback();
        };
        document.getElementById('movie-fps').onchange = () => {
            this.restartPlayback();
        };
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
        document.getElementById('chk-unit-aware-rotate')?.addEventListener('change', () => {
            this.safeApplyDisplayOptions();
            if (this.transform.mode === 'ROTATE') {
                this.prepareRotationValidation([...this.state.selected].filter(idx => this.isEditableIndex(idx)));
                this.applyTransformPreview();
            }
        });
        document.getElementById('rotate-strain-cutoff')?.addEventListener('input', () => {
            this.safeApplyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.applyTransformPreview();
        });
        document.getElementById('rotate-strain-cutoff')?.addEventListener('change', () => {
            this.safeApplyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.applyTransformPreview();
        });

        const canvas = this.renderer.domElement;
        canvas.addEventListener('pointermove', (e) => {
            this.state.lastPointer.set(e.clientX, e.clientY);
            if (this.transform.mode === 'IDLE' && !this.state.isDragging) {
                this.setHoveredAtom(this.selection.pick(e, this.renderer.atomMeshes));
            } else {
                this.setHoveredAtom(null);
            }
        }, { passive: true });

        canvas.addEventListener('pointerdown', (e) => {
            if (e.button !== 0) return; // Left click only
            if (this.transform.mode !== 'IDLE') {
                e.preventDefault();
                this.state.suppressNextPointerUp = true;
                this.commitTransform();
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
            
            if (this.state.isDragging) {
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
                const picked = this.selection.pick(e, this.renderer.atomMeshes);
                if (!e.shiftKey) this.state.selected.clear();
                
                if (picked !== null) {
                    if (this.state.selected.has(picked)) {
                        this.state.selected.delete(picked);
                    } else {
                        this.state.selected.add(picked);
                    }
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
                const newSelected = this.selection.boxSelect(rect, this.renderer.atomMeshes, this.renderer.camera);
                
                if (!e.shiftKey) this.state.selected.clear();
                newSelected.forEach(idx => this.state.selected.add(idx));
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
            if (['input', 'textarea', 'select'].includes(tag)) return;
            if ((e.ctrlKey || e.metaKey) && this.transform.mode === 'IDLE') {
                if (this.isPhysicalKey(e, 'KeyC', ['c'])) {
                    e.preventDefault();
                    this.copySelection();
                    return;
                }
                if (this.isPhysicalKey(e, 'KeyV', ['v'])) {
                    e.preventDefault();
                    this.pasteSelection();
                    return;
                }
                if (this.isPhysicalKey(e, 'KeyZ', ['z'])) {
                    e.preventDefault();
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
                    const frameCount = this.state.atoms?.metadata?.frame_count || 1;
                    if (frameCount > 1) {
                        e.preventDefault();
                        this.togglePlayback();
                        return;
                    }
                }
                if (this.isPhysicalKey(e, 'KeyA', ['a'])) {
                    e.preventDefault();
                    if (e.altKey) {
                        this.state.selected.clear();
                    } else {
                        this.state.atoms.positions.forEach((_, idx) => this.state.selected.add(idx));
                    }
                    this.updateSelectionVisuals();
                    this.updateUI();
                    return;
                }
                const axis = this.axisFromKey(e);
                if (axis) {
                    e.preventDefault();
                    this.alignViewToAxis(axis);
                    this.toast(`View aligned to ${axis}.`, 'success');
                    return;
                }
                if ((e.code === 'Delete' || e.key === 'Delete' || e.code === 'Backspace' || e.key === 'Backspace') && this.state.selected.size > 0) {
                    e.preventDefault();
                    this.deleteSelection();
                    return;
                }
                if (this.state.selected.size > 0) {
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
