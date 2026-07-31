import * as THREE from 'three';
import { ASEApi } from './api.js?v=0.1.2&rev=1';
import { ASERenderer } from './renderer.js?v=0.1.2&rev=1';
import { ASESelection } from './selection.js?v=0.1.2&rev=1';
import { ASETransform } from './transform.js?v=0.1.2&rev=1';
import {
    interpolateTrajectoryFrames,
    interpolatedFrameCount,
    normalizeInterpolationMultiplier
} from './trajectory.js?v=0.1.2&rev=1';

const CHEMICAL_ELEMENT_SYMBOLS = Object.freeze([
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
]);
const CHEMICAL_ELEMENT_SET = new Set(CHEMICAL_ELEMENT_SYMBOLS);
const LEGACY_PAIRWISE_CUTOFF_KEY = 'elementBondCutoffs';
const LEGACY_LABEL_DISPLAY_KEYS = Object.freeze({
    elementRadii: 'labelRadii',
    elementColors: 'labelColors',
    elementVisible: 'labelVisible'
});
const ATOM_MATERIAL_PRESETS = Object.freeze(['standard', 'metal', 'rubber']);

class VAseApp {
    constructor() {
        const urlParams = new URLSearchParams(window.location.search);
        this.sessionId = urlParams.get('session_id');
        this.workspaceId = urlParams.get('workspace_id');
        this.workspaceChild = urlParams.get('workspace_child') === '1';
        this.workspaceActive = !this.workspaceChild;
        this.workspaceNeedsRefresh = false;
        this.workspaceOpenRequests = new Map();
        this.workspaceRequestSequence = 0;
        this.undoTimeline = [];
        this.redoTimeline = [];
        this.historyReplay = false;
        this.visualHistoryBaseline = null;
        this.visualHistoryPending = null;
        this.visualHistoryTimer = null;
        this.visualHistoryReady = false;
        this.collaborationReady = false;
        this.collaborationRevision = 0;
        this.collaborationActorDepth = 0;
        this.collaborationPending = new Map();
        this.collaborationSelectionSignature = null;
        this.collaborationCameraSignature = null;
        this.collaborationFrame = null;
        this.api = new ASEApi(this.sessionId);
        this.api.onUndoableMutation = ({ path } = {}) => {
            this.recordStructureHistoryAction();
            const details = this.collaborationMutationDetails(path);
            this.scheduleCollaborationEvent({
                ...details,
                source: this.currentCollaborationActor(path)
            });
        };
        this.api.onCollaborationMutation = ({ path } = {}) => {
            const details = this.collaborationMutationDetails(path);
            this.scheduleCollaborationEvent({
                ...details,
                source: this.currentCollaborationActor(path)
            });
        };
        this.pendingApply = Promise.resolve();
        
        this.renderer = new ASERenderer(document.getElementById('app-viewport'));
        if (this.workspaceChild) this.renderer.setSuspended(true);
        this.selection = new ASESelection(this.renderer);
        this.transform = new ASETransform(this.renderer.scene);
        this.initialDesignSettings = null;
        this.frameLoadInFlight = false;
        this.pendingFrameIndex = null;
        this.timelineStepQueue = Promise.resolve();
        this.controlCommitState = new WeakMap();
        this.renderer.onFrame = () => {
            this.updateOrientationWidget();
            this.updateSelectionMeasurementOverlay();
        };
        this.renderer.onCameraChange = event => {
            this.syncAtomicScaleFromCamera({
                forceInput: event?.source !== 'scale-input'
            });
            this.observeCollaborationCamera(event?.source || 'camera');
        };
        this.renderer.controls.onGestureStart = () => this.flushVisualHistoryCommit();
        this.renderer.controls.onGestureEnd = () => {
            this.syncAtomicScaleFromCamera({ forceInput: true });
            this.adoptCameraViewWithoutHistory();
        };
        
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
                showBonds: true,
                showCell: true,
                showAxes: true,
                showGrid: true,
                showOverlays: true,
                showPeriodicBonds: false,
                cellThickness: 0.04,
                cellColor: '#d6bd67',
                cellMaterial: 'unlit',
                bondMode: 'auto',
                bondCutoffScale: 1.0,
                manualBondPairs: [],
                pairwiseBondCutoffs: {},
                pairwiseBondRanges: {},
                pairwiseLabelColumnWidth: 210,
                bondStyle: 'cylinder',
                bondThickness: 0.25,
                bondColorMode: 'split',
                bondCustomColor: '#c8ccd0',
                atomRadiusScale: 0.6,
                labelRadii: {},
                labelColors: {},
                labelVisible: {},
                labelMaterials: {},
                atomMaterials: {},
                rotatePivot: 'selection',
                commensurateGuide: true,
                commensurateSnap: false,
                commensurateStrainTolerance: 0.01,
                commensurateMaxIndex: 32,
                commensurateSnapRangeDeg: 2.0,
                supercell: [1, 1, 1],
                translation: [0, 0, 0],
                translationMode: 'cartesian',
                projectionMode: 'orthographic',
                viewportBackground: 'white',
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
                videoFps: 12,
                videoInterpolationMultiplier: 1,
                videoInterpolationMic: true,
                showDisplacements: false,
                displacementReferenceMode: 'previous',
                displacementReferenceFrame: 0,
                displacementMic: true,
                displacementStyle: '3d',
                displacementScale: 1,
                displacementThickness: 0.08,
                displacementColor: '#e58b2a',
                showVolumetric: false,
                volumetricPrecision: 'float32',
                volumetricDatasetId: '',
                volumetricLevel: null,
                volumetricSurfaceMode: 'single',
                volumetricStepSize: 1,
                volumetricOpacity: 0.72,
                volumetricPositiveColor: '#2f8fdb',
                volumetricNegativeColor: '#e05b78',
                rdfCutoff: null,
                rdfBins: 200,
                rdfPairMode: 'active'
            },
            antiAliasing: true,
            sphereQuality: 'auto',
            applyConstraints: true,
            vizOnly: false,
            translationCoordinateMode: 'cartesian',
            moveIncrement: 0,
            rotateIncrementDeg: 0,
            transformReadout: '',
            hoveredIndex: null,
            hoveredReference: null,
            displayConfigLoaded: false,
            rotationScreenPivot: new THREE.Vector2(window.innerWidth / 2, window.innerHeight / 2),
            rotationLastAngle: 0,
            rotationPointerActive: false,
            rotationReferenceDirection: null,
            rotationGuideAxis: null,
            rotationGuideRadius: 3,
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
            timelineSource: 'loaded',
            trajectoryBinaryCache: null,
            trajectoryBinaryPromise: null,
            relaxTrajectory: {
                frames: [],
                frame: 0,
                sourceFrame: 0,
                active: false,
                finished: false
            },
            labelOrder: [],
            trajectoryLabels: [],
            trajectoryLabelElements: {},
            labelIndexCache: new Map(),
            pendingLabelRenames: new Set(),
            modeSwitchInFlight: false,
            cachedFmax: null,
            displayApplyRequest: null,
            bondApplyRequest: null,
            exportPreviewEnabled: false,
            imageExportProfile: null,
            exportPreviewProfile: null,
            hoverPickTimer: null,
            hoverPointer: null,
            orientationSignature: null,
            isRelaxing: false,
            displacementRequestToken: 0,
            displacementRefreshTimer: null,
            displacementStats: null,
            volumetricRequestToken: 0,
            rdfResult: null,
            rdfRequestToken: 0,
            plotlyPromise: null,
            videoExportId: null,
            videoExportStartedAt: null
        };
        this.api.currentFrameProvider = () => Number(
            this.state.atoms?.metadata?.current_frame ?? 0
        );

        this.inspectorGroup = 'inspect';
        this.handleWorkspaceMessage = this.handleWorkspaceMessage.bind(this);
        if (this.workspaceChild) {
            window.addEventListener('message', this.handleWorkspaceMessage);
        }

        this.ready = this.init();
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
            this.setupDisplacementAnalysis();
            this.setupVolumetricAnalysis();
            this.setupRdfAnalysis();
            this.setupViewControls();
            this.setupRuntimeModeControls();
            this.setupSelectedAppearanceControls();
            this.setupLightingControls();
            this.setupCreateAtomWidget();
            this.setupEventListeners();
            this.setupInputCommitBehavior();
            this.setupNumberInputHoldGuards();
            await this.refresh();
            this.collaborationReady = true;
            this.collaborationSelectionSignature = this.collaborationSelectionKey();
            this.collaborationCameraSignature = this.collaborationCameraKey();
            this.collaborationFrame = Number(this.state.atoms?.metadata?.current_frame || 0);
            await this.publishCollaborationEvent({
                type: 'session.ready',
                source: 'system',
                categories: ['state'],
                changedPaths: [],
                summary: 'The live v_ase document is ready for human and agent collaboration.'
            });
            this.notifyWorkspaceDocument('v_ase:document-ready');
        } catch (err) {
            console.error("v_ase initialization failed:", err);
            this.toast(`Initialization failed: ${err.message}`, 'error');
        } finally {
            this.clearBusy();
        }
    }

    workspaceDocumentTitle() {
        const configured = this.state.atoms?.metadata?.config?.document_name;
        const title = String(configured || 'Untitled').trim();
        return title || 'Untitled';
    }

    projectFilename() {
        const title = this.workspaceDocumentTitle();
        const withoutProjectExtension = title.replace(/\.vase$/i, '');
        const stem = withoutProjectExtension.includes('.')
            ? withoutProjectExtension.replace(/\.[^.]+$/, '')
            : withoutProjectExtension;
        const safe = stem
            .replace(/[\\/:*?"<>|]+/g, '_')
            .replace(/^\.+|\.+$/g, '')
            .trim();
        return `${safe || 'v_ase_project'}.vase`;
    }

    htmlViewFilename() {
        return this.projectFilename().replace(/\.vase$/i, '_view.html');
    }

    htmlProjectFilename() {
        return this.projectFilename().replace(/\.vase$/i, '.html');
    }

    notifyWorkspaceDocument(type = 'v_ase:document-title') {
        const title = this.workspaceDocumentTitle();
        document.title = `${title} - v_ase`;
        if (!this.workspaceChild || window.parent === window) return;
        window.parent.postMessage({
            type,
            sessionId: this.sessionId,
            title,
        }, window.location.origin);
    }

    async setWorkspaceActive(active) {
        const next = Boolean(active);
        if (this.workspaceActive === next && !this.workspaceNeedsRefresh) return;
        this.workspaceActive = next;
        if (!next) {
            this.stopPlayback();
            if (this.transform.mode !== 'IDLE') this.cancelTransform();
            this.renderer.setSuspended(true);
            return;
        }
        this.renderer.setSuspended(false);
        if (this.workspaceNeedsRefresh) {
            this.workspaceNeedsRefresh = false;
            await this.refresh();
        } else {
            this.renderer.onResize();
            this.renderer.requestRender();
        }
    }

    handleWorkspaceMessage(event) {
        if (event.origin !== window.location.origin || event.source !== window.parent) return;
        const message = event.data || {};
        if (message.type === 'v_ase:workspace-active') {
            this.setWorkspaceActive(message.active).catch(err => {
                console.error('Failed to activate workspace document:', err);
            });
        } else if (message.type === 'v_ase:workspace-dispose') {
            this.stopPlayback();
            this.renderer.setSuspended(true);
            this.workspaceOpenRequests.forEach(({ reject }) => {
                reject(new Error('The source structure tab was closed.'));
            });
            this.workspaceOpenRequests.clear();
            try {
                if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
                    this.ws.close(1000, 'document tab closed');
                }
            } catch {
                // The parent removes this frame immediately after disposal.
            }
        } else if (message.type === 'v_ase:workspace-open-result') {
            const pending = this.workspaceOpenRequests.get(message.requestId);
            if (!pending) return;
            this.workspaceOpenRequests.delete(message.requestId);
            if (message.ok) pending.resolve(message);
            else pending.reject(new Error(message.error || 'Could not open a new structure tab.'));
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
        document.querySelectorAll('[data-runtime-mode]').forEach(button => {
            const selected = button.dataset.runtimeMode === (this.state.vizOnly ? 'view' : 'edit');
            button.setAttribute('aria-pressed', selected ? 'true' : 'false');
            button.disabled = this.state.modeSwitchInFlight;
        });
        this.updateSelectedAppearanceControls();
    }

    setupRuntimeModeControls() {
        document.querySelectorAll('[data-runtime-mode]').forEach(button => {
            button.addEventListener('click', () => {
                const vizOnly = button.dataset.runtimeMode === 'view';
                this.switchRuntimeMode(vizOnly).catch(err => {
                    this.toast(`Mode change failed: ${err.message}`, 'error');
                });
            });
        });
    }

    setupSelectedAppearanceControls() {
        const labelInput = document.getElementById('selected-atom-label');
        const applyLabel = document.getElementById('btn-apply-selected-label');
        const material = document.getElementById('selected-atom-material');
        applyLabel?.addEventListener('click', () => {
            this.applySelectedLabelEdit().catch(err => {
                this.toast(`Label update failed: ${err.message}`, 'error');
            });
        });
        labelInput?.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            this.applySelectedLabelEdit().catch(err => {
                this.toast(`Label update failed: ${err.message}`, 'error');
            });
        });
        material?.addEventListener('change', () => {
            if (material.value === 'mixed') return;
            this.applySelectedMaterial(material.value);
        });
    }

    normalizedAtomMaterialPreset(value) {
        return ATOM_MATERIAL_PRESETS.includes(value) ? value : 'standard';
    }

    atomMaterialPreset(index, display = this.state.display) {
        const override = display.atomMaterials?.[index] ?? display.atomMaterials?.[String(index)];
        if (override) return this.normalizedAtomMaterialPreset(override);
        const label = this.state.atoms?.symbols?.[index];
        return this.normalizedAtomMaterialPreset(display.labelMaterials?.[label]);
    }

    selectedAtomIndices() {
        const atomCount = this.state.atoms?.positions?.length || 0;
        return [...this.state.selected]
            .filter(index => Number.isInteger(index) && index >= 0 && index < atomCount)
            .sort((a, b) => a - b);
    }

    updateSelectedAppearanceControls() {
        const labelInput = document.getElementById('selected-atom-label');
        const applyLabel = document.getElementById('btn-apply-selected-label');
        const material = document.getElementById('selected-atom-material');
        const count = document.getElementById('selected-appearance-count');
        if (!labelInput || !applyLabel || !material || !count) return;

        const indices = this.selectedAtomIndices();
        const enabled = !this.state.vizOnly && indices.length > 0 && !this.state.modeSwitchInFlight;
        count.textContent = indices.length
            ? `${indices.length} atom${indices.length === 1 ? '' : 's'}`
            : 'None';
        labelInput.disabled = !enabled;
        applyLabel.disabled = !enabled;
        material.disabled = !enabled;

        const labels = [...new Set(indices.map(index => this.state.atoms?.symbols?.[index]).filter(Boolean))];
        if (document.activeElement !== labelInput) {
            labelInput.value = labels.length === 1 ? labels[0] : '';
            labelInput.placeholder = indices.length
                ? (labels.length > 1 ? 'Mixed labels' : 'Label')
                : 'Select atoms';
        }
        const materials = [...new Set(indices.map(index => this.atomMaterialPreset(index)))];
        material.value = materials.length === 1 ? materials[0] : 'mixed';
    }

    applySelectedMaterial(value) {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const preset = this.normalizedAtomMaterialPreset(value);
        const indices = this.selectedAtomIndices();
        if (!indices.length) {
            this.toast('Select atoms before changing material.', 'warning');
            return;
        }
        const atomMaterials = { ...(this.state.display.atomMaterials || {}) };
        indices.forEach(index => {
            const label = this.state.atoms?.symbols?.[index];
            const inherited = this.normalizedAtomMaterialPreset(
                this.state.display.labelMaterials?.[label]
            );
            if (preset === inherited) delete atomMaterials[index];
            else atomMaterials[index] = preset;
        });
        this.state.display.atomMaterials = atomMaterials;
        this.safeApplyDisplayOptions();
        this.renderAppearanceRows();
        this.updateSelectedAppearanceControls();
    }

    uniqueTransitionLabel(base, usedLabels) {
        if (!usedLabels.has(base)) {
            usedLabels.add(base);
            return base;
        }
        let suffix = 2;
        let candidate = `${base}_${suffix}`;
        while (usedLabels.has(candidate)) {
            suffix += 1;
            candidate = `${base}_${suffix}`;
        }
        usedLabels.add(candidate);
        return candidate;
    }

    viewModeIdentityPlan() {
        const sourceLabels = [...(this.state.atoms?.symbols || [])];
        const chemicalSymbols = [...(this.state.atoms?.chemical_symbols || [])];
        const nextLabels = [...sourceLabels];
        const nextDisplay = this.clonePlain(this.state.display);
        nextDisplay.labelMaterials = { ...(nextDisplay.labelMaterials || {}) };
        nextDisplay.atomMaterials = {};

        const usedLabels = new Set(this.uniqueAtomLabels());
        const originByLabel = new Map();
        const nextOrder = [];
        this.uniqueAtomLabels().forEach(sourceLabel => {
            const indices = this.labelIndices(sourceLabel);
            const groups = new Map();
            indices.forEach(index => {
                const preset = this.atomMaterialPreset(index);
                if (!groups.has(preset)) groups.set(preset, []);
                groups.get(preset).push(index);
            });
            const orderedGroups = [...groups.entries()].sort((a, b) => {
                const inherited = this.normalizedAtomMaterialPreset(
                    this.state.display.labelMaterials?.[sourceLabel]
                );
                if (a[0] === inherited && b[0] !== inherited) return -1;
                if (b[0] === inherited && a[0] !== inherited) return 1;
                if (a[1].length !== b[1].length) return b[1].length - a[1].length;
                return a[1][0] - b[1][0];
            });
            orderedGroups.forEach(([preset, atomIndices], groupIndex) => {
                const targetLabel = groupIndex === 0
                    ? sourceLabel
                    : this.uniqueTransitionLabel(sourceLabel, usedLabels);
                atomIndices.forEach(index => { nextLabels[index] = targetLabel; });
                nextDisplay.labelMaterials[targetLabel] = preset;
                ['labelRadii', 'labelColors', 'labelVisible'].forEach(key => {
                    nextDisplay[key] = { ...(nextDisplay[key] || {}) };
                    if (
                        targetLabel !== sourceLabel
                        && Object.prototype.hasOwnProperty.call(nextDisplay[key], sourceLabel)
                    ) {
                        nextDisplay[key][targetLabel] = nextDisplay[key][sourceLabel];
                    }
                });
                originByLabel.set(targetLabel, sourceLabel);
                nextOrder.push(targetLabel);
            });
        });

        const nextCutoffs = {};
        const nextRanges = {};
        for (let i = 0; i < nextOrder.length; i++) {
            for (let j = i; j < nextOrder.length; j++) {
                const labelA = nextOrder[i];
                const labelB = nextOrder[j];
                const originA = originByLabel.get(labelA) || labelA;
                const originB = originByLabel.get(labelB) || labelB;
                const key = this.labelPairKey(labelA, labelB);
                const range = this.pairwiseBondRange(originA, originB);
                nextRanges[key] = { ...range };
                nextCutoffs[key] = range.enabled ? range.max : 0;
            }
        }
        nextDisplay.pairwiseBondCutoffs = nextCutoffs;
        nextDisplay.pairwiseBondRanges = nextRanges;
        nextDisplay.vizOnly = true;
        return {
            labels: nextLabels,
            chemicalSymbols,
            display: nextDisplay,
            labelOrder: nextOrder
        };
    }

    async switchRuntimeMode(vizOnly) {
        if (this.state.modeSwitchInFlight || vizOnly === this.state.vizOnly) return;
        if (this.state.isRelaxing) {
            this.toast('Stop the active relaxation before changing mode.', 'warning');
            return;
        }
        if (this.frameLoadInFlight) {
            this.toast('Wait for the current trajectory frame to finish loading.', 'warning');
            return;
        }
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        this.stopPlayback();

        const plan = vizOnly
            ? this.viewModeIdentityPlan()
            : {
                labels: [...(this.state.atoms?.symbols || [])],
                chemicalSymbols: [...(this.state.atoms?.chemical_symbols || [])],
                display: this.clonePlain(this.state.display),
                labelOrder: [...this.uniqueAtomLabels()]
            };
        plan.display.vizOnly = vizOnly;
        this.state.modeSwitchInFlight = true;
        this.updateEditingAvailability();
        try {
            const frameCount = this.loadedFrameCount();
            const message = vizOnly
                ? 'Preparing optimized View mode...'
                : `Preparing editable ASE state${frameCount > 1 ? ` for ${frameCount} frames` : ''}...`;
            const data = await this.withBusy(
                message,
                () => this.api.updateSessionMode(vizOnly, {
                    labels: plan.labels,
                    chemical_symbols: plan.chemicalSymbols,
                    positions: this.backendPositionsPayload()
                })
            );
            this.state.vizOnly = vizOnly;
            this.state.display = plan.display;
            this.state.display.vizOnly = vizOnly;
            this.state.labelOrder = [...plan.labelOrder];
            if (!vizOnly) this.state.replicaSelected.clear();
            this.setAtomsData(data, { preserveDisplay: false });
            (data.mode_transition_warnings || []).forEach(message => {
                this.toast(message, 'warning');
            });
            this.toast(
                vizOnly
                    ? 'View mode enabled. Structure editing is disabled.'
                    : 'Edit mode enabled. ASE-backed atom editing is ready.',
                'success'
            );
            this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(),
                categories: ['mode'],
                changedPaths: ['mode'],
                summary: `The live document switched to ${vizOnly ? 'View' : 'Edit'} mode.`
            });
        } catch (err) {
            this.toast(`Mode change failed: ${err.message}`, 'error');
        } finally {
            this.state.modeSwitchInFlight = false;
            this.updateEditingAvailability();
            this.updateUI();
        }
    }

    editOnlyToast() {
        this.toast('Switch the top-bar mode to Edit to modify atoms.', 'warning');
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
            '.pairwise-bond-max',
            '.label-radius-input',
            '.label-color-input'
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
        const migrations = {
            edit: 'structure',
            appearance: 'structure',
            bonds: 'structure',
            scene: 'view',
            display: 'view',
            output: 'export'
        };
        const available = new Set(['inspect', 'structure', 'analysis', 'view', 'export']);
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
            const labels = { export: 'Export' };
            label.textContent = labels[next] || (next.charAt(0).toUpperCase() + next.slice(1));
        }
        document.getElementById('structure-section-picker')?.classList.toggle(
            'hidden',
            next !== 'structure'
        );
        if (persist) {
            try {
                window.localStorage?.setItem('v_ase.inspectorGroup', next);
            } catch {
                // Local storage may be unavailable in restricted browser contexts.
            }
        }
        if (next === 'structure') {
            requestAnimationFrame(() => this.syncStructureSectionNavigation());
        }
    }

    structureSectionTargets() {
        const select = document.getElementById('structure-section-select');
        return [...(select?.options || [])]
            .map(option => ({
                option,
                panel: document.querySelector(
                    `#inspector-content [data-panel="${option.value}"]`
                )
            }))
            .filter(item => item.panel);
    }

    syncStructureSectionNavigation() {
        if (this.inspectorGroup !== 'structure') return;
        const content = document.getElementById('inspector-content');
        const select = document.getElementById('structure-section-select');
        const targets = this.structureSectionTargets().filter(
            ({ option, panel }) => !option.disabled && panel.offsetParent !== null
        );
        if (!content || !select || !targets.length) return;
        const threshold = content.getBoundingClientRect().top + 28;
        let active = targets[0];
        for (const candidate of targets) {
            if (candidate.panel.getBoundingClientRect().top <= threshold) active = candidate;
        }
        if (content.scrollTop + content.clientHeight >= content.scrollHeight - 2) {
            active = targets[targets.length - 1];
        }
        select.value = active.option.value;
    }

    setupStructureSectionNavigation() {
        const content = document.getElementById('inspector-content');
        const select = document.getElementById('structure-section-select');
        if (!content || !select) return;
        select.addEventListener('change', () => {
            const panel = document.querySelector(
                `#inspector-content [data-panel="${select.value}"]`
            );
            if (!panel || panel.offsetParent === null) return;
            panel.open = true;
            const contentTop = content.getBoundingClientRect().top;
            const top = Math.max(
                0,
                content.scrollTop + panel.getBoundingClientRect().top - contentTop
            );
            content.scrollTo({ top, behavior: 'smooth' });
        });
        let frame = null;
        content.addEventListener('scroll', () => {
            if (frame !== null) return;
            frame = requestAnimationFrame(() => {
                frame = null;
                this.syncStructureSectionNavigation();
            });
        }, { passive: true });
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
        this.setupStructureSectionNavigation();
        this.setInspectorGroup(savedGroup, false);
        this.setInspectorCollapsed(collapsed, false);
    }

    setupDisplacementAnalysis() {
        const recompute = () => {
            this.readDisplacementControls();
            this.scheduleDisplacementAnalysisRefresh();
        };
        const restyle = () => this.readDisplacementControls();
        document.getElementById('chk-displacement')?.addEventListener('change', recompute);
        document.getElementById('displacement-reference-mode')?.addEventListener('change', recompute);
        document.getElementById('displacement-reference-frame')?.addEventListener('change', recompute);
        document.getElementById('chk-displacement-mic')?.addEventListener('change', recompute);
        document.getElementById('displacement-style')?.addEventListener('change', restyle);
        document.getElementById('displacement-scale')?.addEventListener('input', restyle);
        document.getElementById('displacement-thickness')?.addEventListener('input', restyle);
        document.getElementById('displacement-color')?.addEventListener('input', restyle);
        this.syncDisplacementControls();
    }

    readDisplacementControls({ applyRenderer = true } = {}) {
        const frameCount = Math.max(1, Number(this.state.atoms?.metadata?.frame_count) || 1);
        const mode = document.getElementById('displacement-reference-mode')?.value === 'frame'
            ? 'frame'
            : 'previous';
        const referenceInput = document.getElementById('displacement-reference-frame');
        const referenceFrame = Math.max(
            0,
            Math.min(frameCount - 1, (parseInt(referenceInput?.value || '1', 10) || 1) - 1)
        );
        const scale = Math.max(
            0.05,
            Math.min(10, Number(document.getElementById('displacement-scale')?.value) || 1)
        );
        const thickness = Math.max(
            0.01,
            Math.min(0.5, Number(document.getElementById('displacement-thickness')?.value) || 0.08)
        );
        const color = document.getElementById('displacement-color')?.value;
        Object.assign(this.state.display, {
            showDisplacements: Boolean(document.getElementById('chk-displacement')?.checked),
            displacementReferenceMode: mode,
            displacementReferenceFrame: referenceFrame,
            displacementMic: document.getElementById('chk-displacement-mic')?.checked !== false,
            displacementStyle: document.getElementById('displacement-style')?.value === '2d' ? '2d' : '3d',
            displacementScale: scale,
            displacementThickness: thickness,
            displacementColor: /^#[0-9a-f]{6}$/i.test(color || '') ? color : '#e58b2a'
        });
        if (referenceInput) {
            referenceInput.min = '1';
            referenceInput.max = `${frameCount}`;
            referenceInput.value = `${referenceFrame + 1}`;
        }
        this.syncDisplacementControls();
        if (applyRenderer) {
            this.renderer.setDisplayOptions(this.state.display);
            this.scheduleVisualHistoryCommit('displacement');
        }
    }

    syncDisplacementControls(display = this.state.display) {
        const setChecked = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.checked = Boolean(value);
        };
        const setValue = (id, value) => {
            const element = document.getElementById(id);
            if (element && document.activeElement !== element) element.value = `${value}`;
        };
        setChecked('chk-displacement', display.showDisplacements);
        setChecked('chk-displacement-mic', display.displacementMic !== false);
        setValue('displacement-reference-mode', display.displacementReferenceMode === 'frame' ? 'frame' : 'previous');
        setValue('displacement-reference-frame', (Number(display.displacementReferenceFrame) || 0) + 1);
        setValue('displacement-style', display.displacementStyle === '2d' ? '2d' : '3d');
        setValue('displacement-scale', Number(display.displacementScale) || 1);
        setValue('displacement-thickness', Number(display.displacementThickness) || 0.08);
        setValue('displacement-color', display.displacementColor || '#e58b2a');
        document.getElementById('displacement-reference-frame-row')?.classList.toggle(
            'hidden',
            display.displacementReferenceMode !== 'frame'
        );
        const scaleOutput = document.getElementById('displacement-scale-value');
        if (scaleOutput) scaleOutput.textContent = `${(Number(display.displacementScale) || 1).toFixed(2)}x`;
        const thicknessOutput = document.getElementById('displacement-thickness-value');
        if (thicknessOutput) {
            thicknessOutput.textContent = `${(Number(display.displacementThickness) || 0.08).toFixed(2)} A`;
        }
    }

    setDisplacementStatus(state, title, detail = '') {
        const status = document.getElementById('displacement-status');
        if (!status) return;
        status.dataset.state = state;
        const titleElement = status.querySelector('.analysis-status-title');
        const detailElement = status.querySelector('.analysis-status-detail');
        if (titleElement) titleElement.textContent = title;
        if (detailElement) detailElement.textContent = detail;
    }

    clearDisplacementStats() {
        this.state.displacementStats = null;
        document.getElementById('displacement-stats')?.classList.add('hidden');
        this.renderer.clearDisplacementVectors();
    }

    updateDisplacementStats(data) {
        this.state.displacementStats = data;
        document.getElementById('displacement-stats')?.classList.remove('hidden');
        const setText = (id, text) => {
            const element = document.getElementById(id);
            if (element) element.textContent = text;
        };
        setText(
            'displacement-frame-summary',
            `${Number(data.reference_frame) + 1} -> ${Number(data.current_frame) + 1}`
        );
        setText(
            'displacement-mapped',
            `${data.matched} atoms (${data.mapping === 'index' ? 'index' : 'particle ID'})`
        );
        setText(
            'displacement-mean-rms',
            `${Number(data.stats?.mean || 0).toFixed(4)} / ${Number(data.stats?.rms || 0).toFixed(4)} A`
        );
        setText('displacement-max', `${Number(data.stats?.max || 0).toFixed(4)} A`);
    }

    scheduleDisplacementAnalysisRefresh(delay = 70) {
        if (this.state.displacementRefreshTimer !== null) {
            clearTimeout(this.state.displacementRefreshTimer);
        }
        this.state.displacementRefreshTimer = setTimeout(() => {
            this.state.displacementRefreshTimer = null;
            this.refreshDisplacementAnalysis().catch(error => {
                this.setDisplacementStatus('warning', 'Displacement unavailable', error.message);
                this.clearDisplacementStats();
            });
        }, Math.max(0, delay));
    }

    async refreshDisplacementAnalysis({
        positions = null,
        frameIndex = null,
        suppressBusy = false
    } = {}) {
        const token = ++this.state.displacementRequestToken;
        const frameCount = Number(this.state.atoms?.metadata?.frame_count) || 1;
        if (!this.state.display.showDisplacements) {
            this.setDisplacementStatus(
                'idle',
                'Displacement vectors hidden',
                frameCount > 1 ? 'Enable Show vectors to calculate them.' : 'Load a trajectory with at least two frames.'
            );
            this.clearDisplacementStats();
            return;
        }
        if (frameCount <= 1) {
            this.setDisplacementStatus(
                'warning',
                'Displacement unavailable',
                'At least two trajectory frames are required.'
            );
            this.clearDisplacementStats();
            return;
        }

        const currentFrame = frameIndex === null
            ? (Number(this.state.atoms?.metadata?.current_frame) || 0)
            : Math.max(0, Math.min(frameCount - 1, Number(frameIndex) || 0));
        if (this.state.display.displacementReferenceMode === 'previous' && currentFrame === 0) {
            this.setDisplacementStatus(
                'warning',
                'No previous frame',
                'Move to frame 2 or choose a specific reference frame.'
            );
            this.clearDisplacementStats();
            return;
        }
        this.setDisplacementStatus(
            'loading',
            'Calculating displacement',
            `Frame ${currentFrame + 1} of ${frameCount}`
        );
        const busyTimer = suppressBusy ? null : setTimeout(() => {
            if (token === this.state.displacementRequestToken && !document.body.dataset.busy) {
                this.setBusy('Calculating displacement vectors...');
                document.body.dataset.displacementBusy = `${token}`;
            }
        }, 450);
        try {
            const payload = {
                reference_mode: this.state.display.displacementReferenceMode,
                reference_frame: this.state.display.displacementReferenceFrame,
                frame_index: currentFrame,
                mic: this.state.display.displacementMic
            };
            if (Array.isArray(positions)) payload.positions = positions;
            else if (!this.state.vizOnly) payload.positions = this.backendPositionsPayload();
            const data = await this.api.fetchDisplacements(payload);
            if (token !== this.state.displacementRequestToken) return;
            if (data.status !== 'ok') {
                this.setDisplacementStatus('warning', 'Displacement unavailable', data.message || 'No data.');
                this.clearDisplacementStats();
                return;
            }
            this.renderer.setDisplacementVectors(data, this.state.display);
            this.updateDisplacementStats(data);
            const mic = data.mic_applied ? 'MIC' : 'direct';
            const warning = (data.warnings || []).join(' ');
            this.setDisplacementStatus(
                warning ? 'warning' : 'ready',
                `${data.matched} displacement vectors`,
                warning || `${mic} mapping from frame ${data.reference_frame + 1} to ${data.current_frame + 1}.`
            );
        } finally {
            if (busyTimer !== null) clearTimeout(busyTimer);
            if (document.body.dataset.displacementBusy === `${token}`) {
                delete document.body.dataset.displacementBusy;
                this.clearBusy();
            }
        }
    }

    volumetricDatasets() {
        const datasets = this.state.atoms?.metadata?.volumetric_datasets;
        return Array.isArray(datasets) ? datasets : [];
    }

    volumetricImportPrecision() {
        return this.state.display.volumetricPrecision === 'float64'
            ? 'float64'
            : 'float32';
    }

    setVolumeStatus(state, title, detail = '') {
        const status = document.getElementById('volume-status');
        if (!status) return;
        status.dataset.state = state;
        const titleElement = status.querySelector('.analysis-status-title');
        const detailElement = status.querySelector('.analysis-status-detail');
        if (titleElement) titleElement.textContent = title;
        if (detailElement) detailElement.textContent = detail;
    }

    selectedVolumetricDataset() {
        const datasets = this.volumetricDatasets();
        const selectedId = this.state.display.volumetricDatasetId;
        return datasets.find(dataset => dataset.id === selectedId) || datasets[0] || null;
    }

    defaultVolumetricLevel(dataset) {
        if (!dataset) return null;
        const minimum = Number(dataset.minimum);
        const maximum = Number(dataset.maximum);
        if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || maximum <= minimum) return null;
        if (minimum < 0 && maximum > 0) {
            return Math.max(Math.abs(minimum), Math.abs(maximum)) * 0.18;
        }
        return minimum + (maximum - minimum) * 0.22;
    }

    formatScalarValue(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed)) return '-';
        const magnitude = Math.abs(parsed);
        return magnitude !== 0 && (magnitude < 1e-3 || magnitude >= 1e4)
            ? parsed.toExponential(4)
            : parsed.toPrecision(6);
    }

    formatByteCount(value) {
        const bytes = Math.max(0, Number(value) || 0);
        if (bytes < 1024) return `${Math.round(bytes)} B`;
        const units = ['KiB', 'MiB', 'GiB', 'TiB'];
        let scaled = bytes;
        let unit = -1;
        do {
            scaled /= 1024;
            unit += 1;
        } while (scaled >= 1024 && unit < units.length - 1);
        return `${scaled >= 100 ? scaled.toFixed(0) : scaled.toFixed(1)} ${units[unit]}`;
    }

    renderVolumetricControls() {
        const datasets = this.volumetricDatasets();
        const empty = document.getElementById('volume-empty');
        const controls = document.getElementById('volume-controls');
        empty?.classList.toggle('hidden', datasets.length > 0);
        controls?.classList.toggle('hidden', datasets.length === 0);
        const select = document.getElementById('volume-dataset');
        if (!select) return;

        const previousId = this.state.display.volumetricDatasetId;
        select.replaceChildren();
        datasets.forEach(dataset => {
            const option = document.createElement('option');
            option.value = dataset.id;
            option.textContent = dataset.name;
            select.appendChild(option);
        });
        const selected = datasets.find(dataset => dataset.id === previousId) || datasets[0] || null;
        if (!selected) {
            this.state.display.volumetricDatasetId = '';
            this.state.display.showVolumetric = false;
            this.renderer.clearVolumetricSurfaces();
            return;
        }
        const datasetChanged = selected.id !== previousId;
        this.state.display.volumetricDatasetId = selected.id;
        select.value = selected.id;
        if (datasetChanged || !Number.isFinite(Number(this.state.display.volumetricLevel))) {
            this.state.display.volumetricLevel = this.defaultVolumetricLevel(selected);
        }

        const summary = document.getElementById('volume-summary');
        if (summary) {
            summary.replaceChildren();
            const entries = [
                ['Grid', (selected.shape || []).join(' x ')],
                ['Range', `${this.formatScalarValue(selected.minimum)} to ${this.formatScalarValue(selected.maximum)}`],
                ['Quantity', `${selected.quantity || 'scalar field'} · ${selected.units || 'file native'}`],
                [
                    'Precision',
                    `${selected.precision === 'float64' ? 'FP64' : 'FP32'} · ${
                        this.formatByteCount(Number(selected.memory_bytes) || 0)
                    }`
                ]
            ];
            entries.forEach(([label, value]) => {
                const key = document.createElement('strong');
                const text = document.createElement('span');
                key.textContent = label;
                text.textContent = value;
                summary.append(key, text);
            });
        }

        const differenceTerms = document.getElementById('volume-difference-terms');
        if (differenceTerms) {
            differenceTerms.replaceChildren();
            datasets.forEach((dataset, index) => {
                const row = document.createElement('label');
                row.className = 'volume-difference-term';
                const enabled = document.createElement('input');
                enabled.type = 'checkbox';
                enabled.dataset.datasetId = dataset.id;
                enabled.checked = index < Math.min(3, datasets.length);
                const name = document.createElement('span');
                name.textContent = dataset.name;
                name.title = dataset.name;
                const coefficient = document.createElement('input');
                coefficient.type = 'number';
                coefficient.step = 'any';
                coefficient.value = index === 0 ? '1' : '-1';
                coefficient.setAttribute('aria-label', `Coefficient for ${dataset.name}`);
                row.append(enabled, name, coefficient);
                differenceTerms.appendChild(row);
            });
        }
        this.syncVolumetricControls();
    }

    syncVolumetricControls() {
        const display = this.state.display;
        const setValue = (id, value) => {
            const element = document.getElementById(id);
            if (element && document.activeElement !== element && value !== null && value !== undefined) {
                element.value = `${value}`;
            }
        };
        const visible = document.getElementById('chk-volume-visible');
        if (visible) visible.checked = Boolean(display.showVolumetric);
        setValue('volume-import-precision', this.volumetricImportPrecision());
        setValue('volume-surface-mode', display.volumetricSurfaceMode === 'signed' ? 'signed' : 'single');
        setValue('volume-level', display.volumetricLevel);
        setValue('volume-step', [1, 2, 4].includes(Number(display.volumetricStepSize))
            ? Number(display.volumetricStepSize)
            : 1);
        setValue('volume-positive-color', display.volumetricPositiveColor || '#2f8fdb');
        setValue('volume-negative-color', display.volumetricNegativeColor || '#e05b78');
        setValue('volume-opacity', Number(display.volumetricOpacity) || 0.72);
        const output = document.getElementById('volume-opacity-value');
        if (output) output.textContent = (Number(display.volumetricOpacity) || 0.72).toFixed(2);
    }

    readVolumetricControls() {
        const level = Number(document.getElementById('volume-level')?.value);
        Object.assign(this.state.display, {
            volumetricPrecision: document.getElementById('volume-import-precision')?.value === 'float64'
                ? 'float64'
                : 'float32',
            showVolumetric: Boolean(document.getElementById('chk-volume-visible')?.checked),
            volumetricDatasetId: document.getElementById('volume-dataset')?.value || '',
            volumetricLevel: Number.isFinite(level) ? level : null,
            volumetricSurfaceMode: document.getElementById('volume-surface-mode')?.value === 'signed'
                ? 'signed'
                : 'single',
            volumetricStepSize: [1, 2, 4].includes(Number(document.getElementById('volume-step')?.value))
                ? Number(document.getElementById('volume-step')?.value)
                : 1,
            volumetricOpacity: Math.max(
                0.05,
                Math.min(1, Number(document.getElementById('volume-opacity')?.value) || 0.72)
            ),
            volumetricPositiveColor: document.getElementById('volume-positive-color')?.value || '#2f8fdb',
            volumetricNegativeColor: document.getElementById('volume-negative-color')?.value || '#e05b78'
        });
        this.syncVolumetricControls();
    }

    decodeIsosurface(buffer) {
        const bytes = new Uint8Array(buffer);
        const magic = new TextDecoder().decode(bytes.slice(0, 8));
        if (magic !== 'VASEISO1' || bytes.byteLength < 12) {
            throw new Error('v_ase returned an invalid isosurface payload.');
        }
        const view = new DataView(buffer);
        const headerLength = view.getUint32(8, true);
        const headerStart = 12;
        const dataStart = headerStart + headerLength;
        if (dataStart > bytes.byteLength) throw new Error('Isosurface header is truncated.');
        const header = JSON.parse(new TextDecoder().decode(bytes.slice(headerStart, dataStart)));
        const vertexBytes = Number(header.vertex_count) * 3 * 4;
        const faceBytes = Number(header.face_count) * 3 * 4;
        if (dataStart + vertexBytes + faceBytes !== bytes.byteLength) {
            throw new Error('Isosurface mesh dimensions do not match its payload.');
        }
        return {
            header,
            vertices: new Float32Array(buffer.slice(dataStart, dataStart + vertexBytes)),
            faces: new Uint32Array(buffer.slice(dataStart + vertexBytes))
        };
    }

    async updateVolumetricSurface() {
        this.readVolumetricControls();
        const token = ++this.state.volumetricRequestToken;
        const dataset = this.selectedVolumetricDataset();
        if (!dataset || !this.state.display.showVolumetric) {
            this.renderer.clearVolumetricSurfaces();
            this.setVolumeStatus('idle', dataset ? 'Isosurface hidden' : 'No scalar field', '');
            return;
        }
        const requested = Number(this.state.display.volumetricLevel);
        if (!Number.isFinite(requested)) {
            throw new Error('Enter a finite isovalue.');
        }
        const levels = this.state.display.volumetricSurfaceMode === 'signed'
            ? [...new Set([Math.abs(requested), -Math.abs(requested)])]
            : [requested];
        const available = levels.filter(level => (
            level > Number(dataset.minimum) && level < Number(dataset.maximum)
        ));
        if (!available.length) {
            throw new Error(
                `Isovalue must be between ${this.formatScalarValue(dataset.minimum)} `
                + `and ${this.formatScalarValue(dataset.maximum)}.`
            );
        }
        this.setVolumeStatus('loading', 'Generating isosurface', `${dataset.name}`);
        const meshes = await Promise.all(available.map(async level => {
            const payload = await this.api.fetchIsosurface({
                dataset_id: dataset.id,
                level,
                step_size: this.state.display.volumetricStepSize
            });
            const decoded = this.decodeIsosurface(payload);
            return {
                datasetId: dataset.id,
                level,
                vertices: decoded.vertices,
                faces: decoded.faces,
                cell: decoded.header.cell,
                color: level < 0
                    ? this.state.display.volumetricNegativeColor
                    : this.state.display.volumetricPositiveColor,
                opacity: this.state.display.volumetricOpacity
            };
        }));
        if (token !== this.state.volumetricRequestToken) return;
        this.renderer.setVolumetricSurfaces(meshes);
        this.setVolumeStatus(
            available.length < levels.length ? 'warning' : 'ready',
            `${meshes.length} isosurface${meshes.length === 1 ? '' : 's'}`,
            available.length < levels.length
                ? 'One signed level lies outside this dataset range.'
                : `${meshes.reduce((sum, mesh) => sum + mesh.faces.length / 3, 0).toLocaleString()} triangles`
        );
        this.scheduleVisualHistoryCommit('volumetric');
    }

    async addVolumetricFile(file) {
        if (!file) return;
        const data = await this.withBusy(
            `Reading ${file.name}...`,
            () => this.api.appendStructureFile(
                file,
                '',
                ':',
                this.volumetricImportPrecision()
            )
        );
        if (data.loaded_file?.source_kind !== 'volumetric') {
            throw new Error('The selected file did not contain supported volumetric data.');
        }
        const wasEmpty = !this.hasLoadedAtoms();
        this.setAtomsData(data, {
            clearSelection: wasEmpty,
            preserveDisplay: true,
            preserveRdf: true
        });
        this.renderVolumetricControls();
        this.toast(
            `Added ${Number(data.loaded_file?.appended_volumetric_datasets) || 0} scalar field`
            + `${Number(data.loaded_file?.appended_volumetric_datasets) === 1 ? '' : 's'}.`,
            'success'
        );
    }

    setupVolumetricAnalysis() {
        const fileInput = document.getElementById('volume-file');
        document.getElementById('volume-import-precision')?.addEventListener('change', event => {
            this.state.display.volumetricPrecision = event.target.value === 'float64'
                ? 'float64'
                : 'float32';
            this.scheduleVisualHistoryCommit('volumetric-import-precision');
        });
        document.getElementById('btn-volume-add')?.addEventListener('click', () => fileInput?.click());
        fileInput?.addEventListener('change', async () => {
            const file = fileInput.files?.[0];
            fileInput.value = '';
            try {
                await this.addVolumetricFile(file);
            } catch (error) {
                this.setVolumeStatus('warning', 'Could not load scalar field', error.message);
                this.toast(`Volumetric data failed: ${error.message}`, 'error');
            }
        });
        document.getElementById('volume-dataset')?.addEventListener('change', () => {
            this.state.display.volumetricDatasetId = document.getElementById('volume-dataset')?.value || '';
            this.state.display.volumetricLevel = this.defaultVolumetricLevel(this.selectedVolumetricDataset());
            this.syncVolumetricControls();
            if (this.state.display.showVolumetric) {
                this.updateVolumetricSurface().catch(error => {
                    this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                });
            }
        });
        ['chk-volume-visible', 'volume-surface-mode'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', () => {
                this.updateVolumetricSurface().catch(error => {
                    this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                    this.renderer.clearVolumetricSurfaces();
                });
            });
        });
        ['volume-opacity', 'volume-positive-color', 'volume-negative-color'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => {
                this.readVolumetricControls();
                if (this.state.display.showVolumetric) {
                    this.renderer.updateVolumetricSurfaceStyle({
                        positiveColor: this.state.display.volumetricPositiveColor,
                        negativeColor: this.state.display.volumetricNegativeColor,
                        opacity: this.state.display.volumetricOpacity
                    });
                }
            });
            document.getElementById(id)?.addEventListener('change', () => {
                this.scheduleVisualHistoryCommit('volumetric-style');
            });
        });
        document.getElementById('btn-volume-refresh')?.addEventListener('click', () => {
            this.updateVolumetricSurface().catch(error => {
                this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                this.renderer.clearVolumetricSurfaces();
            });
        });
        document.getElementById('btn-volume-delete')?.addEventListener('click', async () => {
            const dataset = this.selectedVolumetricDataset();
            if (!dataset) return;
            try {
                const result = await this.api.deleteVolumetricDataset(dataset.id);
                this.state.atoms.metadata.volumetric_datasets = result.volumetric_datasets || [];
                this.state.display.volumetricDatasetId = '';
                this.renderer.clearVolumetricSurfaces();
                this.renderVolumetricControls();
            } catch (error) {
                this.toast(`Remove scalar field failed: ${error.message}`, 'error');
            }
        });
        document.getElementById('btn-volume-difference')?.addEventListener('click', async () => {
            const terms = [...document.querySelectorAll('.volume-difference-term')]
                .filter(row => row.querySelector('input[type="checkbox"]')?.checked)
                .map(row => ({
                    id: row.querySelector('input[type="checkbox"]')?.dataset.datasetId,
                    coefficient: Number(row.querySelector('input[type="number"]')?.value)
                }));
            if (terms.length < 2 || terms.some(term => !Number.isFinite(term.coefficient))) {
                this.toast('Select at least two grids with finite coefficients.', 'warning');
                return;
            }
            try {
                const result = await this.withBusy(
                    'Calculating volumetric difference...',
                    () => this.api.createVolumetricDifference({
                        dataset_ids: terms.map(term => term.id),
                        coefficients: terms.map(term => term.coefficient),
                        name: 'Charge density difference'
                    })
                );
                this.state.atoms.metadata.volumetric_datasets = result.volumetric_datasets || [];
                this.state.display.volumetricDatasetId = result.dataset.id;
                this.state.display.volumetricLevel = this.defaultVolumetricLevel(result.dataset);
                this.renderVolumetricControls();
                this.toast('Created charge density difference.', 'success');
            } catch (error) {
                this.toast(`Density difference failed: ${error.message}`, 'error');
            }
        });
        this.renderVolumetricControls();
    }

    rdfOptions() {
        const cutoffText = document.getElementById('rdf-cutoff')?.value.trim() || '';
        const cutoff = cutoffText ? Number(cutoffText) : null;
        const bins = Math.max(8, Math.min(5000, parseInt(
            document.getElementById('rdf-bins')?.value || '200',
            10
        ) || 200));
        const pairMode = ['active', 'all', 'none'].includes(
            document.getElementById('rdf-pair-mode')?.value
        ) ? document.getElementById('rdf-pair-mode').value : 'active';
        Object.assign(this.state.display, {
            rdfCutoff: Number.isFinite(cutoff) ? cutoff : null,
            rdfBins: bins,
            rdfPairMode: pairMode
        });
        return {
            cutoff: Number.isFinite(cutoff) ? cutoff : null,
            bins,
            pair_mode: pairMode,
            active_pairs: this.activeRdfPairs()
        };
    }

    activeRdfPairs() {
        const labels = this.state.atoms?.symbols || [];
        if (this.state.display.bondMode === 'pairwise') {
            return this.uniqueLabelPairs().filter(([left, right]) => {
                const range = this.pairwiseBondRange(left, right);
                return range.enabled && Number(range.max) > 0;
            });
        }

        const sourcePairs = this.state.display.bondMode === 'manual'
            ? this.state.display.manualBondPairs || []
            : this.renderer.bondPairs || [];
        const activePairs = new Map();
        sourcePairs.forEach(([first, second]) => {
            const left = labels[first];
            const right = labels[second];
            if (!left || !right) return;
            const key = this.labelPairKey(left, right);
            activePairs.set(key, [left, right]);
        });
        return [...activePairs.values()];
    }

    setRdfStatus(state, title, detail = '') {
        const status = document.getElementById('rdf-status');
        if (!status) return;
        status.dataset.state = state;
        const titleElement = status.querySelector('.analysis-status-title');
        const detailElement = status.querySelector('.analysis-status-detail');
        if (titleElement) titleElement.textContent = title;
        if (detailElement) detailElement.textContent = detail;
    }

    invalidateRdfResult(
        detail = 'The structure or trajectory frame changed. Calculate the RDF again.'
    ) {
        const status = document.getElementById('rdf-status');
        const wasCalculating = status?.dataset?.state === 'loading';
        const hadResult = Boolean(this.state.rdfResult);
        this.state.rdfRequestToken += 1;
        this.state.rdfResult = null;
        const exportButton = document.getElementById('btn-rdf-export');
        if (exportButton) exportButton.disabled = true;
        const plot = document.getElementById('rdf-plot');
        if (plot && window.Plotly?.purge) window.Plotly.purge(plot);
        document.getElementById('analysis-drawer')?.classList.add('hidden');
        if (hadResult || wasCalculating) {
            this.setRdfStatus('idle', 'RDF needs recalculation', detail);
        }
    }

    ensurePlotly() {
        if (window.Plotly) return Promise.resolve(window.Plotly);
        if (this.state.plotlyPromise) return this.state.plotlyPromise;
        this.state.plotlyPromise = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = new URL('/api/vendor/plotly.js', window.location.origin).href;
            script.async = true;
            script.onload = () => window.Plotly
                ? resolve(window.Plotly)
                : reject(new Error('Plotly loaded without its browser API.'));
            script.onerror = () => reject(new Error('Could not load the local Plotly bundle.'));
            document.head.appendChild(script);
        });
        return this.state.plotlyPromise;
    }

    async plotRdf(result) {
        const Plotly = await this.ensurePlotly();
        const plot = document.getElementById('rdf-plot');
        const drawer = document.getElementById('analysis-drawer');
        if (!plot || !drawer) return;
        drawer.classList.remove('hidden');
        const style = getComputedStyle(document.documentElement);
        const textColor = style.getPropertyValue('--text').trim() || '#dce4e3';
        const mutedColor = style.getPropertyValue('--muted').trim() || '#879392';
        const lineColor = style.getPropertyValue('--line').trim() || '#33403f';
        const teal = style.getPropertyValue('--teal').trim() || '#58d5bd';
        const palette = [teal, '#e58b2a', '#6aa7ff', '#e05b78', '#a7d46f', '#c49ae8'];
        const traces = [{
            x: result.radius,
            y: result.total,
            type: 'scatter',
            mode: 'lines',
            name: 'Total',
            line: { color: teal, width: 2.4 }
        }];
        Object.entries(result.partial || {}).forEach(([name, values], index) => {
            traces.push({
                x: result.radius,
                y: values,
                type: 'scatter',
                mode: 'lines',
                name: name.replace('|', ' - '),
                line: { color: palette[(index + 1) % palette.length], width: 1.5 }
            });
        });
        await Plotly.react(plot, traces, {
            autosize: true,
            margin: { l: 56, r: 18, t: 16, b: 48 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: textColor, family: 'Inter, system-ui, sans-serif', size: 11 },
            xaxis: {
                title: 'r / Å',
                gridcolor: lineColor,
                zeroline: false,
                color: mutedColor
            },
            yaxis: {
                title: 'g(r)',
                gridcolor: lineColor,
                zerolinecolor: lineColor,
                color: mutedColor
            },
            legend: {
                orientation: 'h',
                x: 0,
                y: 1.08,
                bgcolor: 'rgba(0,0,0,0)'
            },
            hovermode: 'x unified'
        }, {
            responsive: true,
            displaylogo: false,
            scrollZoom: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        });
    }

    async calculateRdf() {
        const token = ++this.state.rdfRequestToken;
        const options = this.rdfOptions();
        this.setRdfStatus(
            'loading',
            'Calculating RDF',
            'Counting every periodic image inside the requested spherical cutoff.'
        );
        const result = await this.withBusy(
            'Calculating radial distribution function...',
            () => this.api.fetchRdf(options)
        );
        if (token !== this.state.rdfRequestToken) return;
        this.state.rdfResult = result;
        document.getElementById('btn-rdf-export').disabled = false;
        await this.plotRdf(result);
        const warning = (result.warnings || []).join(' ');
        const imageSpan = Array.isArray(result.periodic_image_span)
            ? result.periodic_image_span.join(' × ')
            : 'automatic';
        const pairCount = Object.keys(result.partial || {}).length;
        this.setRdfStatus(
            warning ? 'warning' : 'ready',
            `${result.bins} bins · cutoff ${Number(result.cutoff).toFixed(3)} Å`,
            warning || `${pairCount} pair curve${pairCount === 1 ? '' : 's'} plus total · periodic image span ${imageSpan}.`
        );
        this.scheduleVisualHistoryCommit('rdf');
    }

    setupAnalysisDrawerResize() {
        const drawer = document.getElementById('analysis-drawer');
        const resizer = document.getElementById('analysis-drawer-resizer');
        if (!drawer || !resizer) return;
        resizer.addEventListener('pointerdown', event => {
            event.preventDefault();
            const startY = event.clientY;
            const startHeight = drawer.getBoundingClientRect().height;
            const onMove = moveEvent => {
                const height = Math.max(
                    210,
                    Math.min(window.innerHeight * 0.62, startHeight + startY - moveEvent.clientY)
                );
                drawer.style.height = `${height}px`;
                window.Plotly?.Plots?.resize?.(document.getElementById('rdf-plot'));
            };
            const onUp = () => {
                window.removeEventListener('pointermove', onMove);
                window.removeEventListener('pointerup', onUp);
                window.removeEventListener('pointercancel', onUp);
            };
            window.addEventListener('pointermove', onMove);
            window.addEventListener('pointerup', onUp);
            window.addEventListener('pointercancel', onUp);
        });
    }

    syncRdfControls() {
        const cutoff = document.getElementById('rdf-cutoff');
        const bins = document.getElementById('rdf-bins');
        const mode = document.getElementById('rdf-pair-mode');
        if (cutoff && document.activeElement !== cutoff) {
            cutoff.value = this.state.display.rdfCutoff === null
                ? ''
                : `${this.state.display.rdfCutoff}`;
        }
        if (bins && document.activeElement !== bins) bins.value = `${this.state.display.rdfBins || 200}`;
        if (mode && document.activeElement !== mode) mode.value = this.state.display.rdfPairMode || 'active';
    }

    setupRdfAnalysis() {
        this.syncRdfControls();
        ['rdf-cutoff', 'rdf-bins', 'rdf-pair-mode'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => {
                this.invalidateRdfResult(
                    'RDF settings changed. Calculate the RDF again before exporting CSV.'
                );
            });
        });
        document.getElementById('btn-rdf-calculate')?.addEventListener('click', () => {
            this.calculateRdf().catch(error => {
                this.setRdfStatus('warning', 'RDF unavailable', error.message);
                this.toast(`RDF failed: ${error.message}`, 'error');
            });
        });
        document.getElementById('btn-rdf-export')?.addEventListener('click', async () => {
            try {
                const blob = await this.withBusy(
                    'Preparing RDF data...',
                    () => this.api.exportRdfCsv(this.rdfOptions())
                );
                this.downloadBlob(blob, 'v_ase_rdf.csv', 'text/csv');
            } catch (error) {
                this.toast(`RDF export failed: ${error.message}`, 'error');
            }
        });
        document.getElementById('btn-analysis-drawer-close')?.addEventListener('click', () => {
            document.getElementById('analysis-drawer')?.classList.add('hidden');
        });
        this.setupAnalysisDrawerResize();
    }

    normalizedViewRotationStep(value = this.state.display.viewRotationStepDeg) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? Math.max(0.1, Math.min(360, parsed)) : 15;
    }

    syncViewControls(options = this.state.display) {
        const background = options.viewportBackground === 'dark' ? 'dark' : 'white';
        const displayMode = options.atomDisplayMode === '2d' ? '2d' : '3d';
        const showGrid = options.showGrid !== false;
        const step = this.normalizedViewRotationStep(options.viewRotationStepDeg);
        const backgroundSelect = document.getElementById('viewport-background');
        const displaySelect = document.getElementById('atom-display-mode');
        const stepInput = document.getElementById('view-rotate-step');
        const gridButton = document.getElementById('btn-grid-toggle');
        if (backgroundSelect && document.activeElement !== backgroundSelect) backgroundSelect.value = background;
        if (displaySelect && document.activeElement !== displaySelect) displaySelect.value = displayMode;
        if (stepInput && document.activeElement !== stepInput) stepInput.value = `${step}`;
        if (gridButton) {
            const action = showGrid ? 'Hide' : 'Show';
            gridButton.setAttribute('aria-pressed', showGrid ? 'true' : 'false');
            gridButton.setAttribute('aria-label', `${action} viewport grid`);
            gridButton.title = `${action} viewport grid`;
        }
        document.body.dataset.viewportBackground = background;
        document.body.dataset.atomDisplayMode = displayMode;
    }

    applyViewDisplayOption(key, value) {
        if (key === 'viewportBackground') {
            this.state.display.viewportBackground = value === 'dark' ? 'dark' : 'white';
        } else if (key === 'atomDisplayMode') {
            this.state.display.atomDisplayMode = value === '2d' ? '2d' : '3d';
        } else {
            return;
        }
        this.syncViewControls();
        this.renderer.setDisplayOptions(this.state.display);
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        this.scheduleVisualHistoryCommit('view-display');
    }

    setViewportGridVisible(visible) {
        this.state.display.showGrid = Boolean(visible);
        const checkbox = document.getElementById('chk-grid');
        if (checkbox) checkbox.checked = this.state.display.showGrid;
        this.syncViewControls();
        this.renderer.setDisplayOptions(this.state.display, { rebuild: false });
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        this.scheduleVisualHistoryCommit('grid');
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
        this.adoptCameraViewWithoutHistory();
        this.renderer.requestRender();
    }

    cameraSettingsSnapshot() {
        const camera = this.currentCameraForExport();
        return {
            position: [...camera.position],
            target: [...camera.target],
            up: [...camera.up],
            projection: camera.projection,
            fov: camera.fov,
            zoom: camera.zoom,
            ortho_scale: camera.ortho_scale,
            near: camera.near,
            far: camera.far
        };
    }

    recordHistoryAction(action) {
        if (this.historyReplay || !action) return;
        this.undoTimeline.push(action);
        if (this.undoTimeline.length > 100) this.undoTimeline.shift();
        this.redoTimeline = [];
    }

    recordStructureHistoryAction() {
        this.flushVisualHistoryCommit();
        this.recordHistoryAction({
            kind: 'structure',
            visualBefore: this.visualHistoryReady
                ? this.visualHistorySnapshot()
                : null
        });
    }

    resetHistoryTimeline() {
        this.undoTimeline = [];
        this.redoTimeline = [];
        this.resetVisualHistoryBaseline();
    }

    visualHistorySnapshot() {
        return {
            schema: 'v_ase.visual_history.v1',
            display: this.clonePlain(this.state.display),
            applyConstraints: Boolean(this.state.applyConstraints),
            antiAliasing: Boolean(this.state.antiAliasing),
            sphereQuality: this.state.sphereQuality || 'auto',
            moveIncrement: Number(this.state.moveIncrement) || 0,
            rotateIncrementDeg: Number(this.state.rotateIncrementDeg) || 0,
            imageExportProfile: this.clonePlain(this.currentImageExportProfile())
        };
    }

    visualHistorySnapshotsEqual(first, second) {
        if (!first || !second) return first === second;
        return JSON.stringify(first) === JSON.stringify(second);
    }

    resetVisualHistoryBaseline() {
        if (this.visualHistoryTimer !== null) {
            clearTimeout(this.visualHistoryTimer);
            this.visualHistoryTimer = null;
        }
        this.visualHistoryPending = null;
        this.visualHistoryReady = Boolean(this.state.atoms?.positions);
        this.visualHistoryBaseline = this.visualHistoryReady
            ? this.visualHistorySnapshot()
            : null;
    }

    scheduleVisualHistoryCommit(source = 'visual-settings') {
        if (this.historyReplay || !this.visualHistoryReady) return;
        const before = this.visualHistoryPending?.before || this.visualHistoryBaseline;
        if (!before) {
            this.visualHistoryBaseline = this.visualHistorySnapshot();
            return;
        }
        this.visualHistoryPending = {
            kind: 'visual',
            source: this.visualHistoryPending?.source || source,
            collaborationSource: (
                this.visualHistoryPending?.collaborationSource
                || this.currentCollaborationActor(source)
            ),
            before
        };
        if (this.visualHistoryTimer !== null) clearTimeout(this.visualHistoryTimer);
        this.visualHistoryTimer = window.setTimeout(
            () => this.flushVisualHistoryCommit(),
            180
        );
    }

    flushVisualHistoryCommit() {
        if (this.visualHistoryTimer !== null) {
            clearTimeout(this.visualHistoryTimer);
            this.visualHistoryTimer = null;
        }
        const pending = this.visualHistoryPending;
        this.visualHistoryPending = null;
        if (!pending) return;
        const action = {
            ...pending,
            after: this.visualHistorySnapshot()
        };
        if (!action || this.visualHistorySnapshotsEqual(action.before, action.after)) return;
        this.visualHistoryBaseline = this.clonePlain(action.after);
        this.recordHistoryAction(action);
        const changedPaths = this.collaborationChangedPaths(
            action.before,
            action.after
        );
        const categories = new Set(['display']);
        if (changedPaths.some(path => path.startsWith('applyConstraints'))) {
            categories.add('constraints');
        }
        if (changedPaths.some(path => path.startsWith('imageExportProfile'))) {
            categories.add('export');
        }
        this.scheduleCollaborationEvent({
            source: action.collaborationSource || this.currentCollaborationActor(action.source),
            categories: [...categories],
            changedPaths,
            summary: 'Visual settings changed.'
        });
    }

    applyVisualHistorySnapshot(snapshot) {
        if (!snapshot) return;
        const previousReplay = this.historyReplay;
        this.historyReplay = true;
        try {
            this.applyDesignSettings(this.clonePlain(snapshot));
            this.visualHistoryBaseline = this.visualHistorySnapshot();
            this.visualHistoryPending = null;
        } finally {
            this.historyReplay = previousReplay;
        }
    }

    adoptCameraViewWithoutHistory() {
        if (
            this.historyReplay
            || !this.visualHistoryReady
            || this.visualHistoryPending
        ) {
            return;
        }
        this.visualHistoryBaseline = this.visualHistorySnapshot();
    }

    async performUndo() {
        this.flushVisualHistoryCommit();
        const action = this.undoTimeline.pop();
        if (!action) {
            if (!this.canEditAtoms()) {
                this.toast('Nothing to undo.', 'warning');
                return;
            }
            const data = await this.api.undo();
            this.setAtomsData(data);
            this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(),
                categories: ['structure'],
                changedPaths: ['structure'],
                summary: 'The last structure change was undone.'
            });
            this.toast('Undo.', 'success');
            return;
        }
        try {
            if (action.kind === 'visual') {
                this.applyVisualHistorySnapshot(action.before);
                this.toast('Visual setting undone.', 'success');
            } else {
                this.historyReplay = true;
                if (!action.visualAfter && this.visualHistoryReady) {
                    action.visualAfter = this.visualHistorySnapshot();
                }
                const data = await this.api.undo();
                this.setAtomsData(data);
                if (
                    action.visualBefore
                    && !this.visualHistorySnapshotsEqual(action.visualBefore, action.visualAfter)
                ) {
                    this.applyVisualHistorySnapshot(action.visualBefore);
                } else {
                    this.resetVisualHistoryBaseline();
                }
                this.toast('Undo.', 'success');
            }
            this.redoTimeline.push(action);
            this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(),
                categories: action.kind === 'visual' ? ['display'] : ['structure'],
                changedPaths: [action.kind === 'visual' ? 'display' : 'structure'],
                summary: `The last ${action.kind} change was undone.`
            });
        } catch (err) {
            this.undoTimeline.push(action);
            throw err;
        } finally {
            this.historyReplay = false;
        }
    }

    async performRedo() {
        this.flushVisualHistoryCommit();
        const action = this.redoTimeline.pop();
        if (!action) {
            if (!this.canEditAtoms()) {
                this.toast('Nothing to redo.', 'warning');
                return;
            }
            const data = await this.api.redo();
            this.setAtomsData(data);
            this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(),
                categories: ['structure'],
                changedPaths: ['structure'],
                summary: 'The last structure change was redone.'
            });
            this.toast('Redo.', 'success');
            return;
        }
        try {
            if (action.kind === 'visual') {
                this.applyVisualHistorySnapshot(action.after);
                this.toast('Visual setting redone.', 'success');
            } else {
                this.historyReplay = true;
                const data = await this.api.redo();
                this.setAtomsData(data);
                if (
                    action.visualAfter
                    && !this.visualHistorySnapshotsEqual(action.visualBefore, action.visualAfter)
                ) {
                    this.applyVisualHistorySnapshot(action.visualAfter);
                } else {
                    this.resetVisualHistoryBaseline();
                }
                this.toast('Redo.', 'success');
            }
            this.undoTimeline.push(action);
            this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(),
                categories: action.kind === 'visual' ? ['display'] : ['structure'],
                changedPaths: [action.kind === 'visual' ? 'display' : 'structure'],
                summary: `The last ${action.kind} change was redone.`
            });
        } catch (err) {
            this.redoTimeline.push(action);
            throw err;
        } finally {
            this.historyReplay = false;
        }
    }

    cameraViewBasis() {
        const camera = this.renderer.camera;
        const target = this.renderer.controls.target.clone();
        const offset = camera.position.clone().sub(target);
        camera.updateMatrixWorld(true);
        const orientation = camera.getWorldQuaternion(new THREE.Quaternion());
        const right = new THREE.Vector3(1, 0, 0).applyQuaternion(orientation).normalize();
        const up = new THREE.Vector3(0, 1, 0).applyQuaternion(orientation).normalize();
        const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(orientation).normalize();
        return { target, offset, forward, right, up };
    }

    rotateCameraView(direction, stepDegrees = this.state.display.viewRotationStepDeg) {
        const degrees = this.normalizedViewRotationStep(stepDegrees);
        const basis = this.cameraViewBasis();
        const directions = {
            left: { axis: basis.up, sign: 1 },
            right: { axis: basis.up, sign: -1 },
            up: { axis: basis.right, sign: -1 },
            down: { axis: basis.right, sign: 1 },
            'roll-ccw': { axis: basis.forward, sign: 1 },
            'roll-cw': { axis: basis.forward, sign: -1 }
        };
        const rotation = directions[direction];
        if (!rotation) return;
        const viewRotation = new THREE.Quaternion().setFromAxisAngle(
            rotation.axis,
            rotation.sign * THREE.MathUtils.degToRad(degrees)
        );
        const camera = this.renderer.camera;
        const offset = basis.offset.applyQuaternion(viewRotation);
        camera.position.copy(basis.target).add(offset);
        camera.up.copy(basis.up).applyQuaternion(viewRotation).normalize();
        this.completeCameraViewChange('view-rotate');
    }

    setupViewControls() {
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
        document.querySelectorAll('[data-view-rotate]').forEach(button => {
            button.addEventListener('click', () => {
                commitStep();
                this.rotateCameraView(button.dataset.viewRotate, this.state.display.viewRotationStepDeg);
            });
        });
        document.getElementById('btn-grid-toggle')?.addEventListener('click', () => {
            this.setViewportGridVisible(this.state.display.showGrid === false);
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
        this.scheduleVisualHistoryCommit('lighting');
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
            const target = this.renderer.toVisualAtomPosition(this.getSceneCenter());
            this.state.display.sunTarget = [target.x, target.y, target.z];
            this.syncLightingControls();
            this.applyLightingControls();
        });
        this.renderer.onLightingChange = options => {
            this.state.display.sunPosition = [...options.sunPosition];
            this.state.display.sunTarget = [...options.sunTarget];
            this.syncLightingControls();
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
            this.scheduleVisualHistoryCommit('lighting-gizmo');
        };
        this.syncLightingControls();
    }

    async refresh() {
        try {
            if (this.state.displayConfigLoaded) this.captureBondSettingsFromControls();
            const data = await this.api.fetchAtoms();
            if (!data || !data.positions) return;

            this.state.atoms = data;
            this.syncTrajectoryIdentity(data);
            this.rebuildLabelIndexCache(data.symbols || []);
            this.state.cachedFmax = this.computeFmax(data.forces || []);
            this.clearRelaxTrajectoryIfTopologyChanged(data);
            this.state.originalPositions = this.state.vizOnly
                ? data.positions
                : data.positions.map(position => [...position]);
            if (data.metadata?.trajectory_positions_binary && !data.trajectory_positions) {
                this.loadTrajectoryCache({ background: true });
            }
            this.applyInitialDisplayConfig(data);
            this.renderPairwiseBondControls();
            this.renderAppearanceRows();
            this.updateEditingAvailability();
            this.updateUI();
            
            this.state.display.vizOnly = this.state.vizOnly;
            const requestedAtomicScale = Number(this.state.display.atomicScalePixelsPerAngstrom);
            const hasRequestedAtomicScale = Number.isFinite(requestedAtomicScale) && requestedAtomicScale > 0;
            this.renderer.setDisplayOptions(this.state.display, { rebuild: false });
            this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
            this.renderVolumetricControls();
            if (this.state.display.showVolumetric) {
                this.updateVolumetricSurface().catch(error => {
                    this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                });
            }
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
            this.notifyWorkspaceDocument();
            this.scheduleDisplacementAnalysisRefresh();
            this.resetVisualHistoryBaseline();
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
        this.updateLabelSelectionControls();
        this.updateSelectedAppearanceControls();
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
        const cutoffScaleValue = Number(
            document.getElementById('calc-cutoff-scale')?.value ?? details.cutoff_scale ?? 0.7
        );
        const strengthValue = Number(
            document.getElementById('calc-strength')?.value ?? details.k_repulsion ?? 1.0
        );
        return {
            device,
            cpu_threads: Number.isFinite(cpuThreads) ? cpuThreads : 4,
            cutoff_scale: Number.isFinite(cutoffScaleValue)
                ? Math.max(0.05, Math.min(3, cutoffScaleValue))
                : 0.7,
            k_repulsion: Number.isFinite(strengthValue)
                ? Math.max(0, Math.min(1000, strengthValue))
                : 1.0
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
        const cutoffScale = document.getElementById('calc-cutoff-scale');
        const strength = document.getElementById('calc-strength');
        if (!controls || !device || !cpus || !cutoffScale || !strength) return;

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
        if (document.activeElement !== cutoffScale) {
            cutoffScale.value = Number(details.cutoff_scale ?? 0.7).toFixed(2);
        }
        if (document.activeElement !== strength) {
            strength.value = Number(details.k_repulsion ?? 1.0).toFixed(2);
        }
        cutoffScale.disabled = !isRepulsion || this.state.isRelaxing;
        strength.disabled = !isRepulsion || this.state.isRelaxing;
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

    async rotateSelectionFromPanel() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const editableSelection = [...this.state.selected].filter(index => this.isEditableIndex(index));
        if (editableSelection.length === 0) {
            this.toast('Select at least one editable atom before rotating.', 'warning');
            return;
        }
        const axis = document.getElementById('selection-rotate-axis')?.value || 'Z';
        const angleInput = document.getElementById('selection-rotate-angle');
        const angleDegrees = Number(angleInput?.value);
        if (!['X', 'Y', 'Z'].includes(axis) || !Number.isFinite(angleDegrees)) {
            this.toast('Rotation axis and angle must be valid.', 'error');
            angleInput?.focus();
            return;
        }
        if (Math.abs(angleDegrees) <= 1e-12) {
            this.toast('Rotation angle is zero; coordinates were not changed.', 'warning');
            return;
        }
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        this.enterTransformMode('ROTATE');
        if (this.transform.mode !== 'ROTATE') return;
        this.transform.setAxis(axis, this.renderer.camera);
        this.configureRotationReference(editableSelection);
        await this.prepareCommensurateRotation(editableSelection);
        this.transform.buffer = String(angleDegrees);
        this.applyTransformPreview();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        await this.commitTransform();
        this.toast(
            `Rotated ${editableSelection.length} atom${editableSelection.length === 1 ? '' : 's'} `
            + `${angleDegrees.toFixed(3)} deg around ${axis}.`,
            'success'
        );
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

    setAtomsData(
        data,
        {
            clearSelection = false,
            preserveDisplay = true,
            preserveRdf = false,
            resetTrajectoryIdentity = false
        } = {}
    ) {
        if (!preserveRdf) this.invalidateRdfResult();
        const previousVolumeSignature = JSON.stringify(
            this.volumetricDatasets().map(dataset => [
                dataset.id,
                dataset.shape,
                dataset.cell
            ])
        );
        if (preserveDisplay) this.captureBondSettingsFromControls();
        this.state.atoms = data;
        this.syncTrajectoryIdentity(data, { reset: resetTrajectoryIdentity });
        this.rebuildLabelIndexCache(data.symbols || []);
        this.state.cachedFmax = this.computeFmax(data.forces || []);
        this.clearRelaxTrajectoryIfTopologyChanged(data);
        this.reconcileLabelOrder(data.symbols || []);
        this.state.originalPositions = this.state.vizOnly
            ? data.positions
            : data.positions.map(position => [...position]);
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
        this.renderPairwiseBondControls({ capture: preserveDisplay });
        this.renderer.setDisplayOptions(this.state.display, { rebuild: false });
        this.renderer.rebuildAtoms(data, data.metadata.custom_colors || {});
        this.renderVolumetricControls();
        const nextVolumeSignature = JSON.stringify(
            this.volumetricDatasets().map(dataset => [
                dataset.id,
                dataset.shape,
                dataset.cell
            ])
        );
        if (nextVolumeSignature !== previousVolumeSignature) {
            if (!this.volumetricDatasets().length || !this.state.display.showVolumetric) {
                this.renderer.clearVolumetricSurfaces();
            } else {
                queueMicrotask(() => {
                    this.updateVolumetricSurface().catch(error => {
                        this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                        this.renderer.clearVolumetricSurfaces();
                    });
                });
            }
        }
        this.renderAppearanceRows();
        this.updateEditingAvailability();
        this.setHoveredAtom(null);
        this.updateSelectionVisuals();
        this.updateUI();
        this.updateDocumentAvailability();
        this.scheduleDisplacementAnalysisRefresh();
        this.observeCollaborationFrame();
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

    timelineSourceAvailable(source) {
        return source === 'relax'
            ? this.relaxFrameCount() > 1
            : this.loadedFrameCount() > 1;
    }

    primaryTimelineSource() {
        const requested = this.state.timelineSource;
        if (this.timelineSourceAvailable(requested)) return requested;
        if (this.loadedFrameCount() > 1) return 'loaded';
        if (this.relaxFrameCount() > 1) return 'relax';
        return 'loaded';
    }

    secondaryTimelineSource() {
        if (this.loadedFrameCount() <= 1 || this.relaxFrameCount() <= 1) return null;
        return this.primaryTimelineSource() === 'loaded' ? 'relax' : 'loaded';
    }

    timelineSourceName(source, { compact = false } = {}) {
        if (source === 'loaded') return compact ? 'SOURCE' : 'Source frames';
        const calculator = String(this.state.atoms?.metadata?.calculator || '').trim();
        const calculatorName = calculator && calculator.toLowerCase() !== 'none'
            ? calculator
            : '';
        if (compact) {
            return /repulsion/i.test(calculatorName) ? 'RELAX · REPULSION' : 'RELAXATION';
        }
        return calculatorName ? `Relaxation · ${calculatorName}` : 'Relaxation';
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
        this.state.timelineSource = 'relax';
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
        if (this.state.timelineSource === 'relax') this.state.timelineSource = 'loaded';
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
        this.state.display.showBonds = config.show_bonds !== false;
        this.state.display.showCell = config.show_cell !== false;
        this.state.display.showAxes = config.show_axes !== false;
        this.state.display.showGrid = config.show_grid !== false;
        this.state.display.showOverlays = config.show_overlays !== false;
        this.state.display.showPeriodicBonds = Boolean(config.show_periodic_bonds);
        const initialCellThickness = Number(
            config.cell_thickness ?? this.state.display.cellThickness
        );
        this.state.display.cellThickness = Number.isFinite(initialCellThickness)
            ? Math.max(0.01, Math.min(0.30, initialCellThickness))
            : this.state.display.cellThickness;
        if (/^#[0-9A-Fa-f]{6}$/.test(config.cell_color || '')) {
            this.state.display.cellColor = config.cell_color;
        }
        this.state.display.cellMaterial = ['unlit', 'standard', 'metal'].includes(config.cell_material)
            ? config.cell_material
            : this.state.display.cellMaterial;
        this.state.display.bondStyle = ['cylinder', 'flat'].includes(config.bond_style)
            ? config.bond_style
            : this.state.display.bondStyle;
        const initialBondThickness = Number(
            config.bond_thickness ?? this.state.display.bondThickness
        );
        this.state.display.bondThickness = Number.isFinite(initialBondThickness)
            ? Math.max(0.02, Math.min(0.6, initialBondThickness))
            : this.state.display.bondThickness;
        this.state.display.bondColorMode = ['split', 'custom'].includes(config.bond_color_mode)
            ? config.bond_color_mode
            : this.state.display.bondColorMode;
        if (/^#[0-9A-Fa-f]{6}$/.test(config.bond_custom_color || '')) {
            this.state.display.bondCustomColor = config.bond_custom_color;
        }
        this.state.applyConstraints = config.apply_constraint !== false;
        this.state.antiAliasing = config.anti_aliasing !== false;
        this.state.sphereQuality = config.sphere_quality || 'auto';
        const initialRadiusScale = Number(
            config.atom_radius_scale ?? this.state.display.atomRadiusScale
        );
        this.state.display.atomRadiusScale = Number.isFinite(initialRadiusScale) && initialRadiusScale > 0
            ? initialRadiusScale
            : this.state.display.atomRadiusScale;
        this.state.display.labelRadii = config.element_radii || {};
        this.state.display.labelColors = config.element_colors || {};
        this.state.display.labelVisible = config.element_visible || {};
        this.state.display.labelMaterials = config.label_materials || {};
        this.state.display.atomMaterials = config.atom_materials || {};
        this.state.display.rotatePivot = config.rotate_pivot || this.state.display.rotatePivot;
        this.state.display.commensurateGuide = Boolean(
            config.commensurate_guide ?? config.unit_cell_aware_rotate ?? this.state.display.commensurateGuide
        );
        this.state.display.commensurateSnap = Boolean(
            config.commensurate_snap ?? this.state.display.commensurateSnap
        );
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
        this.state.display.viewportBackground = config.viewport_background === 'dark' ? 'dark' : 'white';
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
        document.getElementById('cell-thickness').value = this.state.display.cellThickness;
        document.getElementById('cell-color').value = this.state.display.cellColor;
        document.getElementById('cell-material').value = this.state.display.cellMaterial;
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

    async setTimelineSource(source) {
        if (!this.timelineSourceAvailable(source)) return;
        this.stopPlayback();
        this.state.timelineSource = source;
        this.updateTrajectoryUI();
        if (source === 'relax') {
            await this.loadRelaxFrame(this.timelineFrameIndex('relax'));
        } else {
            await this.loadFrame(this.timelineFrameIndex('loaded'));
        }
        this.updateTrajectoryUI();
    }

    syncTimelineSourceSelect(source, loadedCount, relaxCount) {
        const select = document.getElementById('timeline-source-select');
        if (!select) return;
        const available = [];
        if (loadedCount > 1) available.push('loaded');
        if (relaxCount > 1) available.push('relax');
        if (!available.length) available.push('loaded');
        const signature = available
            .map(item => `${item}:${this.timelineSourceName(item)}`)
            .join('|');
        if (select.dataset.signature !== signature) {
            select.replaceChildren(...available.map(item => {
                const option = document.createElement('option');
                option.value = item;
                option.textContent = this.timelineSourceName(item);
                return option;
            }));
            select.dataset.signature = signature;
        }
        select.value = source;
        select.disabled = available.length <= 1;
        select.classList.toggle('relax', source === 'relax');
        select.title = `${this.timelineSourceName(source)} controls playback, Space, and Left/Right arrow keys.`;
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
        this.syncTimelineSourceSelect(source, loadedCount, relaxCount);
        const slider = document.getElementById('frame-slider');
        if (slider) {
            slider.max = Math.max(0, count - 1);
            slider.value = index;
            slider.disabled = count <= 1;
            slider.setAttribute('aria-label', `${this.timelineSourceName(source)} frame`);
        }
        const label = document.getElementById('frame-label');
        if (label) label.innerText = `${Math.min(index + 1, count)} / ${count}`;
        const play = document.getElementById('btn-play');
        if (play) {
            play.innerText = this.state.trajectoryTimer ? '⏸' : '▶';
            play.disabled = count <= 1;
            play.title = `Play/Pause ${this.timelineSourceName(source)}`;
        }
        const prev = document.getElementById('btn-frame-prev');
        const next = document.getElementById('btn-frame-next');
        if (prev) {
            prev.disabled = count <= 1;
            prev.title = `Previous ${this.timelineSourceName(source)} frame (Left Arrow)`;
        }
        if (next) {
            next.disabled = count <= 1;
            next.title = `Next ${this.timelineSourceName(source)} frame (Right Arrow)`;
        }
        const fps = document.getElementById('movie-fps');
        if (fps) fps.disabled = count <= 1;
        const skip = document.getElementById('movie-skip');
        if (skip) skip.disabled = count <= 1;

        const secondary = this.secondaryTimelineSource();
        const secondaryRow = document.getElementById('secondary-trajectory-row');
        if (secondaryRow) {
            secondaryRow.classList.toggle('hidden', !secondary);
            secondaryRow.dataset.source = secondary || '';
        }
        const secondarySourceLabel = document.getElementById('secondary-timeline-source-label');
        if (secondarySourceLabel && secondary) {
            secondarySourceLabel.innerText = this.timelineSourceName(secondary, { compact: true });
            secondarySourceLabel.classList.toggle('relax', secondary === 'relax');
            secondarySourceLabel.title = `${this.timelineSourceName(secondary)}. Select it above to use playback and arrow-key controls.`;
        }
        const secondarySlider = document.getElementById('secondary-frame-slider');
        if (secondarySlider && secondary) {
            const secondaryCount = this.timelineFrameCount(secondary);
            const secondaryIndex = this.timelineFrameIndex(secondary);
            secondarySlider.max = Math.max(0, secondaryCount - 1);
            secondarySlider.value = Math.min(secondaryIndex, Math.max(0, secondaryCount - 1));
            secondarySlider.disabled = secondaryCount <= 1;
            secondarySlider.setAttribute('aria-label', `${this.timelineSourceName(secondary)} frame`);
        }
        const secondaryLabel = document.getElementById('secondary-frame-label');
        if (secondaryLabel && secondary) {
            const secondaryCount = this.timelineFrameCount(secondary);
            const secondaryIndex = this.timelineFrameIndex(secondary);
            secondaryLabel.innerText = `${Math.min(secondaryIndex + 1, secondaryCount)} / ${secondaryCount}`;
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
        this.updateSelectionMeasurementOverlay();
        this.observeCollaborationSelection();
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
        const selectionSignature = indices.join(',');
        if (kindSelect.dataset.selectionSignature !== selectionSignature) {
            kindSelect.dataset.selectionSignature = selectionSignature;
            delete kindSelect.dataset.draftKind;
        }
        const fixedState = this.selectedFixAtomsState(indices);
        fixBox.disabled = !hasSelection || this.state.vizOnly;
        fixBox.checked = fixedState === 'all';
        fixBox.indeterminate = fixedState === 'partial';
        fixBox.dataset.fixAtomsState = fixedState;

        const directional = this.selectedDirectionalConstraintState(indices);
        const draftKind = kindSelect.dataset.draftKind;
        const hasDirectionalDraft = hasSelection && ['fixed_line', 'fixed_plane'].includes(draftKind);
        if (!hasDirectionalDraft && document.activeElement !== kindSelect && !inputs.includes(document.activeElement)) {
            kindSelect.value = directional.kind;
        }
        kindSelect.disabled = !hasSelection || this.state.vizOnly;
        if (directional.vector && !hasDirectionalDraft && !inputs.includes(document.activeElement)) {
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
            return false;
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
            return true;
        } catch (err) {
            this.toast(`Constraint update failed: ${err.message}`, 'error');
            return false;
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
        const updated = await this.updateSelectedConstraints(
            { directional_kind: kind, vector },
            kind === 'fixed_line' ? 'Applying FixedLine...' : 'Applying FixedPlane...'
        );
        if (updated) {
            const kindSelect = document.getElementById('constraint-kind');
            if (kindSelect) delete kindSelect.dataset.draftKind;
            this.updateSelectionConstraintControls();
        }
    }

    async clearSelectedDirectionalConstraint() {
        const updated = await this.updateSelectedConstraints(
            { directional_kind: 'none' },
            'Clearing directional constraints...'
        );
        if (updated) {
            const kindSelect = document.getElementById('constraint-kind');
            if (kindSelect) delete kindSelect.dataset.draftKind;
            this.updateSelectionConstraintControls();
        }
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

    selectionReferenceUnitCellPosition(reference) {
        const normalized = this.normalizeSelectionReference(reference);
        if (!normalized) return null;
        const position = this.currentAtomPosition(normalized.index);
        if (!position) return null;
        const cart = new THREE.Vector3(...position);
        if (!this.renderer?.hasValidCell?.()) return cart;
        const frac = this.renderer.cartToFrac(cart);
        const pbc = this.state.atoms?.pbc || [false, false, false];
        for (let axis = 0; axis < 3; axis++) {
            if (!pbc[axis]) continue;
            const value = frac.getComponent(axis);
            frac.setComponent(axis, value - Math.floor(value));
        }
        return this.renderer.fracToCart(frac);
    }

    selectionIncludesReplica(selectedReferences = this.selectionEntries()) {
        return selectedReferences.some(reference => (
            this.normalizeSelectionReference(reference)?.kind === 'replica'
        ));
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

    selectionDelta(first, second, { mic = true } = {}) {
        const a = this.normalizeSelectionReference(first);
        const b = this.normalizeSelectionReference(second);
        if (!a || !b) return null;
        const pi = this.selectionReferencePosition(a);
        const pj = this.selectionReferencePosition(b);
        if (!pi || !pj) return null;
        const delta = pj.clone().sub(pi);
        if (!mic || !this.renderer?.hasValidCell?.()) return delta;
        const pbc = this.state.atoms?.pbc || [false, false, false];
        if (!pbc.some(Boolean)) return delta;
        const frac = this.renderer.cartToFrac(delta);
        for (let axis = 0; axis < 3; axis++) {
            if (!pbc[axis]) continue;
            frac.setComponent(axis, frac.getComponent(axis) - Math.round(frac.getComponent(axis)));
        }
        return this.renderer.fracToCart(frac);
    }

    selectionDistance(i, j, options = {}) {
        const delta = this.selectionDelta(i, j, options);
        return delta ? delta.length() : NaN;
    }

    selectionUnitCellDistance(i, j) {
        const first = this.selectionReferenceUnitCellPosition(i);
        const second = this.selectionReferenceUnitCellPosition(j);
        return first && second ? second.sub(first).length() : NaN;
    }

    selectionAngle(i, j, k, options = {}) {
        const ji = this.selectionDelta(j, i, options);
        const jk = this.selectionDelta(j, k, options);
        if (!ji || !jk || ji.lengthSq() < 1e-12 || jk.lengthSq() < 1e-12) return NaN;
        return THREE.MathUtils.radToDeg(ji.angleTo(jk));
    }

    selectionTorsion(i, j, k, l, options = {}) {
        const ij = this.selectionDelta(i, j, options);
        const jk = this.selectionDelta(j, k, options);
        const kl = this.selectionDelta(k, l, options);
        if (!ij || !jk || !kl || ij.lengthSq() < 1e-12 || jk.lengthSq() < 1e-12 || kl.lengthSq() < 1e-12) {
            return NaN;
        }
        const firstNormal = ij.clone().cross(jk);
        const secondNormal = jk.clone().cross(kl);
        if (firstNormal.lengthSq() < 1e-12 || secondNormal.lengthSq() < 1e-12) return NaN;
        firstNormal.normalize();
        secondNormal.normalize();
        const middle = jk.clone().normalize();
        return THREE.MathUtils.radToDeg(Math.atan2(
            firstNormal.clone().cross(secondNormal).dot(middle),
            firstNormal.dot(secondNormal)
        ));
    }

    selectionMeasurementMap(selectedReferences) {
        return selectedReferences.map((reference, index) => (
            `a${index + 1}=#${this.selectionReferenceLabel(reference)} ${this.selectionReferenceSymbol(reference)}`
        )).join(', ');
    }

    selectionCountText(selectedReferences = this.selectionEntries()) {
        const counts = new Map();
        selectedReferences.forEach(reference => {
            const label = this.selectionReferenceSymbol(reference);
            counts.set(label, (counts.get(label) || 0) + 1);
        });
        const breakdown = [...counts.entries()]
            .map(([label, count]) => `${label}: ${count}`)
            .join(', ');
        return `${selectedReferences.length} atoms selected${breakdown ? ` | ${breakdown}` : ''}`;
    }

    getSelectionMeasureText(selectedReferences = this.selectionEntries()) {
        if (!this.state.atoms || selectedReferences.length === 0) return '-';
        const referenceMap = this.selectionMeasurementMap(selectedReferences);
        if (selectedReferences.length === 1) return referenceMap;
        if (selectedReferences.length === 2) {
            const [i, j] = selectedReferences;
            const direct = this.selectionDistance(i, j, { mic: false });
            const mic = this.selectionDistance(i, j, { mic: true });
            if (![direct, mic].every(Number.isFinite)) return '-';
            const lines = [
                referenceMap,
                `Direct: d(a1-a2) = ${this.formatNumber(direct, 4)} A`,
                `MIC: d(a1-a2) = ${this.formatNumber(mic, 4)} A`
            ];
            if (this.selectionIncludesReplica(selectedReferences)) {
                const unitCell = this.selectionUnitCellDistance(i, j);
                if (Number.isFinite(unitCell)) {
                    lines.push(`Unit cell: d(a1-a2) = ${this.formatNumber(unitCell, 4)} A`);
                }
            }
            return lines.join('\n');
        }
        if (selectedReferences.length === 3) {
            const [i, j, k] = selectedReferences;
            const direct = [
                this.selectionDistance(i, j, { mic: false }),
                this.selectionDistance(j, k, { mic: false }),
                this.selectionAngle(i, j, k, { mic: false })
            ];
            if (!direct.every(Number.isFinite)) return '-';
            return `${referenceMap}\nDirect: d(a1-a2) = ${this.formatNumber(direct[0], 4)} A | d(a2-a3) = ${this.formatNumber(direct[1], 4)} A | angle(a1-a2-a3) = ${this.formatNumber(direct[2], 2)} deg`;
        }
        if (selectedReferences.length === 4) {
            const [i, j, k, l] = selectedReferences;
            const direct = [
                this.selectionDistance(i, j, { mic: false }),
                this.selectionDistance(j, k, { mic: false }),
                this.selectionDistance(k, l, { mic: false }),
                this.selectionTorsion(i, j, k, l, { mic: false })
            ];
            if (!direct.every(Number.isFinite)) return '-';
            return `${referenceMap}\nDirect: d(a1-a2) = ${this.formatNumber(direct[0], 4)} A | d(a2-a3) = ${this.formatNumber(direct[1], 4)} A | d(a3-a4) = ${this.formatNumber(direct[2], 4)} A | torsion(a1-a2-a3-a4) = ${this.formatNumber(direct[3], 2)} deg`;
        }
        return this.selectionCountText(selectedReferences);
    }

    getSelectionMeasureSummary(selectedReferences = this.selectionEntries()) {
        if (!this.state.atoms || selectedReferences.length === 0) return '-';
        if (selectedReferences.length === 1) {
            return `a1 = #${this.selectionReferenceLabel(selectedReferences[0])}`;
        }
        if (selectedReferences.length === 2) {
            const direct = this.selectionDistance(selectedReferences[0], selectedReferences[1], { mic: false });
            const mic = this.selectionDistance(selectedReferences[0], selectedReferences[1], { mic: true });
            if (![direct, mic].every(Number.isFinite)) return 'Distance unavailable';
            let summary = `Distance a1-a2 | Direct ${this.formatNumber(direct, 4)} A | MIC ${this.formatNumber(mic, 4)} A`;
            if (this.selectionIncludesReplica(selectedReferences)) {
                const unitCell = this.selectionUnitCellDistance(
                    selectedReferences[0],
                    selectedReferences[1]
                );
                if (Number.isFinite(unitCell)) {
                    summary += ` | Unit cell ${this.formatNumber(unitCell, 4)} A`;
                }
            }
            return summary;
        }
        if (selectedReferences.length === 3) {
            const [i, j, k] = selectedReferences;
            const direct = this.selectionAngle(i, j, k, { mic: false });
            return Number.isFinite(direct)
                ? `Angle a1-a2-a3 | Direct ${this.formatNumber(direct, 2)} deg`
                : 'Angle unavailable';
        }
        if (selectedReferences.length === 4) {
            const direct = this.selectionTorsion(...selectedReferences, { mic: false });
            return Number.isFinite(direct)
                ? `Torsion a1-a2-a3-a4 | Direct ${this.formatNumber(direct, 2)} deg`
                : 'Torsion unavailable';
        }
        return this.selectionCountText(selectedReferences);
    }

    worldToScreen(vec) {
        const projected = vec.clone().project(this.renderer.camera);
        return new THREE.Vector2(
            (projected.x + 1) * window.innerWidth / 2,
            (-projected.y + 1) * window.innerHeight / 2
        );
    }

    updateSelectionMeasurementOverlay(selectedReferences = this.selectionEntries()) {
        const overlay = document.getElementById('measurement-overlay');
        if (!overlay) return;
        const count = selectedReferences.length;
        const enabled = this.state.display.showOverlays !== false &&
            !this.state.exportPreviewEnabled &&
            count > 0 && count <= 4;
        overlay.replaceChildren();
        overlay.classList.toggle('hidden', !enabled);
        overlay.dataset.measureCount = enabled ? String(count) : '0';
        overlay.dataset.measureKind = enabled
            ? (count === 1 ? 'point' : count === 2 ? 'distance' : count === 3 ? 'angle' : 'torsion')
            : 'none';
        if (!enabled) return;

        const width = window.innerWidth;
        const height = window.innerHeight;
        overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
        overlay.setAttribute('width', `${width}`);
        overlay.setAttribute('height', `${height}`);
        const camera = this.renderer.camera;
        camera.updateMatrixWorld(true);
        const points = selectedReferences.map((reference, index) => {
            const position = this.selectionReferencePosition(reference);
            if (!position) return null;
            const projected = this.renderer.toVisualAtomPosition(position).project(camera);
            if (![projected.x, projected.y, projected.z].every(Number.isFinite) ||
                projected.z < -1 || projected.z > 1) {
                return null;
            }
            return {
                x: (projected.x + 1) * width / 2,
                y: (-projected.y + 1) * height / 2,
                reference,
                order: index + 1
            };
        });
        if (points.some(point => !point)) {
            overlay.classList.add('hidden');
            overlay.dataset.measureCount = '0';
            overlay.dataset.measureKind = 'none';
            return;
        }

        const namespace = 'http://www.w3.org/2000/svg';
        const appendSvg = (name, attributes = {}, parent = overlay) => {
            const node = document.createElementNS(namespace, name);
            Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
            parent.appendChild(node);
            return node;
        };
        const shortenedSegment = (start, end, padding = 16) => {
            const dx = end.x - start.x;
            const dy = end.y - start.y;
            const length = Math.hypot(dx, dy);
            if (length <= padding * 2 + 1) return [start, end];
            const ux = dx / length;
            const uy = dy / length;
            return [
                { x: start.x + ux * padding, y: start.y + uy * padding },
                { x: end.x - ux * padding, y: end.y - uy * padding }
            ];
        };
        const appendLine = (start, end, className) => {
            const [a, b] = shortenedSegment(start, end);
            return appendSvg('line', {
                x1: a.x.toFixed(2),
                y1: a.y.toFixed(2),
                x2: b.x.toFixed(2),
                y2: b.y.toFixed(2),
                class: className
            });
        };
        const appendValueBadge = (x, y, text) => {
            const group = appendSvg('g', {
                class: 'measure-value-badge',
                transform: `translate(${x.toFixed(2)} ${y.toFixed(2)})`
            });
            const badgeWidth = Math.max(76, Math.min(340, text.length * 7.3 + 20));
            appendSvg('rect', {
                x: (-badgeWidth / 2).toFixed(2),
                y: -13,
                width: badgeWidth.toFixed(2),
                height: 26,
                rx: 6
            }, group);
            const label = appendSvg('text', { x: 0, y: 0.8 }, group);
            label.textContent = text;
        };

        for (let index = 0; index < points.length - 1; index++) {
            const className = count === 4 && index === 1
                ? 'measure-connector measure-torsion-axis'
                : 'measure-connector';
            appendLine(points[index], points[index + 1], className);
        }

        if (count === 2) {
            const center = {
                x: (points[0].x + points[1].x) / 2,
                y: (points[0].y + points[1].y) / 2
            };
            const dx = points[1].x - points[0].x;
            const dy = points[1].y - points[0].y;
            const length = Math.max(1, Math.hypot(dx, dy));
            const direct = this.selectionDistance(...selectedReferences, { mic: false });
            const mic = this.selectionDistance(...selectedReferences, { mic: true });
            if ([direct, mic].every(Number.isFinite)) {
                const values = [
                    `Direct ${this.formatNumber(direct, 3)}`,
                    `MIC ${this.formatNumber(mic, 3)}`
                ];
                if (this.selectionIncludesReplica(selectedReferences)) {
                    const unitCell = this.selectionUnitCellDistance(...selectedReferences);
                    if (Number.isFinite(unitCell)) {
                        values.push(`Cell ${this.formatNumber(unitCell, 3)}`);
                    }
                }
                appendValueBadge(
                    center.x - dy / length * 22,
                    center.y + dx / length * 22,
                    `${values.join(' | ')} A`
                );
            }
        } else if (count === 3) {
            const center = points[1];
            const firstAngle = Math.atan2(points[0].y - center.y, points[0].x - center.x);
            const lastAngle = Math.atan2(points[2].y - center.y, points[2].x - center.x);
            let sweep = lastAngle - firstAngle;
            while (sweep > Math.PI) sweep -= Math.PI * 2;
            while (sweep < -Math.PI) sweep += Math.PI * 2;
            const firstLength = Math.hypot(points[0].x - center.x, points[0].y - center.y);
            const lastLength = Math.hypot(points[2].x - center.x, points[2].y - center.y);
            const radius = Math.max(15, Math.min(34, Math.min(firstLength, lastLength) * 0.24));
            const start = {
                x: center.x + Math.cos(firstAngle) * radius,
                y: center.y + Math.sin(firstAngle) * radius
            };
            const end = {
                x: center.x + Math.cos(firstAngle + sweep) * radius,
                y: center.y + Math.sin(firstAngle + sweep) * radius
            };
            appendSvg('path', {
                class: 'measure-angle-arc',
                d: `M ${start.x.toFixed(2)} ${start.y.toFixed(2)} A ${radius.toFixed(2)} ${radius.toFixed(2)} 0 0 ${sweep >= 0 ? 1 : 0} ${end.x.toFixed(2)} ${end.y.toFixed(2)}`
            });
            const direct = this.selectionAngle(...selectedReferences, { mic: false });
            if (Number.isFinite(direct)) {
                const middleAngle = firstAngle + sweep / 2;
                appendValueBadge(
                    center.x + Math.cos(middleAngle) * (radius + 20),
                    center.y + Math.sin(middleAngle) * (radius + 20),
                    `Direct ${this.formatNumber(direct, 1)} deg`
                );
            }
        } else if (count === 4) {
            const center = {
                x: (points[1].x + points[2].x) / 2,
                y: (points[1].y + points[2].y) / 2
            };
            const dx = points[2].x - points[1].x;
            const dy = points[2].y - points[1].y;
            const length = Math.max(1, Math.hypot(dx, dy));
            const direct = this.selectionTorsion(...selectedReferences, { mic: false });
            if (Number.isFinite(direct)) {
                appendValueBadge(
                    center.x - dy / length * 24,
                    center.y + dx / length * 24,
                    `Direct ${this.formatNumber(direct, 1)} deg`
                );
            }
        }

        const centroid = points.reduce(
            (sum, point) => ({ x: sum.x + point.x / count, y: sum.y + point.y / count }),
            { x: 0, y: 0 }
        );
        points.forEach((point, index) => {
            let dx = point.x - centroid.x;
            let dy = point.y - centroid.y;
            let length = Math.hypot(dx, dy);
            if (length < 7) {
                const fallbackAngle = -Math.PI / 2 + index * Math.PI * 2 / Math.max(1, count);
                dx = Math.cos(fallbackAngle);
                dy = Math.sin(fallbackAngle);
                length = 1;
            }
            const labelPoint = {
                x: point.x + dx / length * 30,
                y: point.y + dy / length * 30
            };
            appendSvg('line', {
                class: 'measure-label-leader',
                x1: point.x.toFixed(2),
                y1: point.y.toFixed(2),
                x2: labelPoint.x.toFixed(2),
                y2: labelPoint.y.toFixed(2)
            });
            const group = appendSvg('g', {
                class: 'measure-atom-badge',
                'data-measure-order': point.order,
                'data-reference': this.selectionReferenceLabel(point.reference),
                transform: `translate(${labelPoint.x.toFixed(2)} ${labelPoint.y.toFixed(2)})`
            });
            appendSvg('rect', { x: -17, y: -11, width: 34, height: 22, rx: 6 }, group);
            const text = appendSvg('text', { x: 0, y: 0.7 }, group);
            text.textContent = `a${point.order}`;
        });
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
        const canonicalUp = axis === 'Z'
            ? new THREE.Vector3(0, 1, 0)
            : new THREE.Vector3(0, 0, 1);
        const basis = this.cameraViewBasis();
        const poseTolerance = 1 - 1e-7;
        const positiveDirectionAligned = basis.offset.lengthSq() > 1e-12
            && basis.offset.clone().normalize().dot(baseDir) > poseTolerance;
        const canonicalUpAligned = basis.up.dot(canonicalUp) > poseTolerance;
        const sign = positiveDirectionAligned && canonicalUpAligned ? -1 : 1;
        const dir = baseDir.clone().multiplyScalar(sign);
        camera.up.copy(canonicalUp);
        camera.position.copy(target).add(dir.clone().multiplyScalar(distance));
        camera.lookAt(target);
        controls.target.copy(target);
        controls.endGesture?.();
        controls.update?.();
        this.renderer.syncSelectionOutlines();
        this.transform.updateGuides(camera);
        this.updateOrientationWidget();
        this.adoptCameraViewWithoutHistory();
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
            this.updateRotationReferenceGuide(appliedRotationAngle);
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
        this.renderer.clearConstraintMotionGuides?.();

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
        this.state.rotationScreenPivot.copy(
            this.worldToScreen(this.renderer.toVisualAtomPosition(pivot))
        );
        this.state.rotationLastAngle = 0;
        this.state.rotationPointerActive = false;
        this.state.transformSubject = 'atoms';
        this.transform.enter(mode, pivot, this.renderer.camera, {
            visualOffset: this.renderer.visualTranslationVector?.() || new THREE.Vector3()
        });
        this.renderer.setConstraintMotionGuides?.({
            mode,
            indices: editableSelection,
            originalPositions: this.state.originalPositions,
            applyConstraints: this.state.applyConstraints
        });
        if (mode === 'ROTATE') {
            this.configureRotationReference(editableSelection);
            this.prepareCommensurateRotation(editableSelection);
        } else {
            this.clearCommensurateRotation({ keepStatus: true });
        }
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
        this.renderer.clearConstraintMotionGuides?.();
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
        this.renderer.clearConstraintMotionGuides?.();
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

    labelPairKey(a, b) {
        return [a, b].sort().join('-');
    }

    uniqueAtomLabels() {
        return this.reconcileLabelOrder(this.state.atoms?.symbols || []);
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

    rebuildLabelIndexCache(symbols = []) {
        const cache = new Map();
        symbols.forEach((symbol, index) => {
            if (!cache.has(symbol)) cache.set(symbol, []);
            cache.get(symbol).push(index);
        });
        this.state.labelIndexCache = cache;
        return cache;
    }

    naturalTypeCompare(a, b) {
        return String(a).localeCompare(String(b), undefined, {
            numeric: true,
            sensitivity: 'base'
        });
    }

    syncTrajectoryIdentity(data = this.state.atoms, { reset = false } = {}) {
        const payload = data?.metadata?.config?.trajectory_identity;
        const labels = reset || payload
            ? []
            : [...(this.state.trajectoryLabels || [])];
        const elements = reset || payload
            ? {}
            : this.clonePlain(this.state.trajectoryLabelElements || {});
        const add = (label, element = null) => {
            if (!label) return;
            if (!labels.includes(label)) labels.push(label);
            if (!elements[label]) elements[label] = [];
            if (CHEMICAL_ELEMENT_SET.has(element) && !elements[label].includes(element)) {
                elements[label].push(element);
            }
        };
        (payload?.labels || []).forEach(label => {
            const knownElements = payload?.elements?.[label] || [];
            if (knownElements.length) knownElements.forEach(element => add(label, element));
            else add(label);
        });
        const currentLabels = data?.symbols || [];
        const currentElements = data?.chemical_symbols || [];
        currentLabels.forEach((label, index) => add(label, currentElements[index]));
        this.state.trajectoryLabels = labels;
        this.state.trajectoryLabelElements = elements;
    }

    availableAtomLabels(symbols = this.state.atoms?.symbols || []) {
        return [...new Set([
            ...(this.state.trajectoryLabels || []),
            ...symbols.filter(Boolean)
        ])];
    }

    reconcileLabelOrder(symbols = []) {
        const presentList = this.availableAtomLabels(symbols);
        const present = new Set(presentList);
        const existingOrder = this.state.labelOrder || [];
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
        this.state.labelOrder = ordered;
        return ordered;
    }

    replaceLabelOrder(oldSymbol, newSymbol) {
        if (!newSymbol) return;
        const order = [...(this.state.labelOrder || [])];
        const existing = order.indexOf(newSymbol);
        const index = order.indexOf(oldSymbol);
        if (existing >= 0 && index >= 0 && existing !== index) {
            order.splice(index, 1);
        } else if (index >= 0) {
            order[index] = newSymbol;
        } else if (existing < 0) {
            order.push(newSymbol);
        }
        this.state.labelOrder = [...new Set(order)];
    }

    updateLocalTrajectoryIdentity(oldSymbol, label, baseSymbol = null) {
        const frameCount = Number(this.state.atoms?.metadata?.frame_count) || 1;
        const labels = [...(this.state.trajectoryLabels || [])];
        const elements = this.clonePlain(this.state.trajectoryLabelElements || {});
        const sourceElements = elements[oldSymbol] || [];
        const oldIndex = labels.indexOf(oldSymbol);
        const targetIndex = labels.indexOf(label);
        const removeOld = frameCount === 1 && oldSymbol !== label;

        if (removeOld && oldIndex >= 0) {
            if (targetIndex >= 0) labels.splice(oldIndex, 1);
            else labels[oldIndex] = label;
            delete elements[oldSymbol];
        } else if (targetIndex < 0) {
            labels.push(label);
        }

        const knownElements = elements[label] || [];
        elements[label] = [...new Set([
            ...knownElements,
            ...sourceElements,
            ...(CHEMICAL_ELEMENT_SET.has(baseSymbol) ? [baseSymbol] : [])
        ])];
        this.state.trajectoryLabels = [...new Set(labels)];
        this.state.trajectoryLabelElements = elements;
    }

    labelIndices(symbol) {
        return this.state.labelIndexCache?.get(symbol) || [];
    }

    isLabelVisible(symbol) {
        return this.state.display.labelVisible?.[symbol] !== false;
    }

    isAtomVisible(index) {
        const symbol = this.state.atoms?.symbols?.[index];
        return !symbol || this.isLabelVisible(symbol);
    }

    visibleLabelIndices(symbol) {
        if (!this.isLabelVisible(symbol)) return [];
        return this.labelIndices(symbol);
    }

    pruneHiddenSelection() {
        this.state.selected.forEach(index => {
            if (!this.isAtomVisible(index)) this.state.selected.delete(index);
        });
        this.state.replicaSelected.forEach((reference, key) => {
            if (!this.isAtomVisible(reference.index)) this.state.replicaSelected.delete(key);
        });
    }

    labelSelectionState(symbol) {
        const indices = this.labelIndices(symbol);
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

    labelVisualColor(symbol) {
        const override = this.state.display.labelColors?.[symbol];
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
        return CHEMICAL_ELEMENT_SYMBOLS;
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
        if (CHEMICAL_ELEMENT_SET.has(text)) return text;
        const prefix = text.split('_', 1)[0];
        if (CHEMICAL_ELEMENT_SET.has(prefix)) return prefix;
        const match = text.match(/^([A-Z][a-z]?)/);
        return match && CHEMICAL_ELEMENT_SET.has(match[1]) ? match[1] : null;
    }

    chemicalSymbolForLabel(label) {
        const index = (this.state.atoms?.symbols || []).findIndex(symbol => symbol === label);
        if (index >= 0) return this.state.atoms?.chemical_symbols?.[index] || this.baseElementForLabel(label);
        const known = this.state.trajectoryLabelElements?.[label] || [];
        return known.length === 1 ? known[0] : this.baseElementForLabel(label);
    }

    chemicalSymbolsForLabel(label) {
        const chemicalSymbols = this.state.atoms?.chemical_symbols || [];
        return [...new Set([
            ...(this.state.trajectoryLabelElements?.[label] || []),
            this.labelIndices(label)
                .map(index => chemicalSymbols[index])
                .filter(symbol => CHEMICAL_ELEMENT_SET.has(symbol))
        ].flat())];
    }

    transferLabelDisplaySettings(
        oldSymbol,
        newSymbol,
        { appearance = true, removeSource = true, copySource = true } = {}
    ) {
        if (!oldSymbol || !newSymbol || oldSymbol === newSymbol) return;
        const maps = [
            ...(appearance ? [this.state.display.labelRadii, this.state.display.labelColors] : []),
            this.state.display.labelMaterials,
            this.state.display.labelVisible
        ];
        maps.forEach(map => {
            if (!map || !(oldSymbol in map)) return;
            if (copySource && !(newSymbol in map)) map[newSymbol] = map[oldSymbol];
            if (removeSource) delete map[oldSymbol];
        });
        const cutoffs = this.state.display.pairwiseBondCutoffs || {};
        const ranges = this.state.display.pairwiseBondRanges || {};
        const partners = new Set([
            oldSymbol,
            newSymbol,
            ...(this.state.labelOrder || []),
            ...(this.state.atoms?.symbols || [])
        ]);
        partners.forEach(partner => {
            const oldKey = this.labelPairKey(oldSymbol, partner);
            const mappedPartner = partner === oldSymbol ? newSymbol : partner;
            const newKey = this.labelPairKey(newSymbol, mappedPartner);
            if (copySource && oldKey in cutoffs && !(newKey in cutoffs)) {
                cutoffs[newKey] = cutoffs[oldKey];
            }
            if (copySource && oldKey in ranges && !(newKey in ranges)) {
                ranges[newKey] = { ...ranges[oldKey] };
            }
        });
        if (removeSource) {
            partners.forEach(partner => {
                delete cutoffs[this.labelPairKey(oldSymbol, partner)];
                delete ranges[this.labelPairKey(oldSymbol, partner)];
            });
        }
    }

    uniqueLabelPairs() {
        const labels = this.uniqueAtomLabels();
        const pairs = [];
        for (let i = 0; i < labels.length; i++) {
            for (let j = i; j < labels.length; j++) {
                pairs.push([labels[i], labels[j]]);
            }
        }
        return pairs;
    }

    defaultPairwiseCutoff(a, b) {
        const elementA = this.chemicalSymbolForLabel(a);
        const elementB = this.chemicalSymbolForLabel(b);
        return Number(this.renderer.autoBondBaseCutoffFromValues(
            this.elementCovalentRadius(elementA),
            this.elementCovalentRadius(elementB),
            this.renderer.autoBondElementClass(elementA),
            this.renderer.autoBondElementClass(elementB)
        ).toFixed(3));
    }

    defaultPairwiseBondRange(a, b) {
        const maximum = this.defaultPairwiseCutoff(a, b);
        return {
            enabled: maximum > 0,
            min: 0,
            max: maximum
        };
    }

    pairwiseBondRange(a, b, display = this.state.display) {
        const key = this.labelPairKey(a, b);
        const fallback = this.defaultPairwiseBondRange(a, b);
        const source = display?.pairwiseBondRanges?.[key];
        const legacyCutoffs = display?.pairwiseBondCutoffs || {};
        const hasLegacyMaximum = Object.prototype.hasOwnProperty.call(
            legacyCutoffs,
            key
        );
        const hasAnyLegacyCutoff = Object.keys(legacyCutoffs).length > 0;
        const parsedLegacyMaximum = Number(legacyCutoffs[key]);
        const legacyMaximum = Number.isFinite(parsedLegacyMaximum)
            ? Math.max(0, parsedLegacyMaximum)
            : null;
        if (source && typeof source === 'object') {
            if (hasAnyLegacyCutoff && !hasLegacyMaximum) {
                return { enabled: false, min: 0, max: 0 };
            }
            const maximum = Number(source.max);
            const max = Number.isFinite(maximum) && maximum >= 0 ? maximum : fallback.max;
            const sourceEnabled = source.enabled !== false && max > 0;
            if (hasLegacyMaximum && legacyMaximum !== null) {
                const legacyEnabled = legacyMaximum > 0;
                const recordsAgree = sourceEnabled === legacyEnabled && (
                    !sourceEnabled || Math.abs(max - legacyMaximum) <= 1e-12
                );
                if (!recordsAgree) {
                    return {
                        enabled: legacyEnabled,
                        min: 0,
                        max: legacyMaximum
                    };
                }
            }
            return {
                enabled: sourceEnabled,
                min: 0,
                max
            };
        }
        if (hasLegacyMaximum && legacyMaximum !== null) {
            return {
                enabled: legacyMaximum > 0,
                min: 0,
                max: legacyMaximum
            };
        }
        return fallback;
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

    labelVisualRadius(symbol) {
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
            this.state.display.labelRadii[label] = Number(radius.toFixed(4));
        } else {
            delete this.state.display.labelRadii[label];
        }
        if (color) {
            const nextColor = this.defaultElementColor(baseSymbol);
            if (nextColor) this.state.display.labelColors[label] = nextColor;
            else delete this.state.display.labelColors[label];
        } else {
            delete this.state.display.labelColors[label];
        }
    }

    updateRadiusScaleLabel() {
        const scale = Number(
            document.getElementById('atom-radius-scale')?.value
            || this.state.display.atomRadiusScale
            || 0.6
        );
        const label = document.getElementById('atom-radius-scale-value');
        if (label) label.innerText = `${(Number.isFinite(scale) ? scale : 1).toFixed(2)}x`;
    }

    renderAppearanceRows() {
        const root = document.getElementById('appearance-table-body');
        if (!root || !this.state.atoms?.symbols) return;
        this.ensureElementTypeDatalist();
        const active = document.activeElement;
        const existingFocus = {
            label: active?.dataset?.atomLabel,
            field: active?.dataset?.appearanceField
        };
        root.innerHTML = '';
        this.uniqueAtomLabels().forEach(symbol => {
            if (!(symbol in this.state.display.labelRadii)) {
                this.state.display.labelRadii[symbol] = Number(this.labelVisualRadius(symbol).toFixed(4));
            }
            if (!(symbol in this.state.display.labelVisible)) {
                this.state.display.labelVisible[symbol] = true;
            }
            const row = document.createElement('div');
            row.className = 'appearance-row';
            const labelAtomIndices = [...this.labelIndices(symbol)];
            const currentElements = this.chemicalSymbolsForLabel(symbol);
            const currentElement = currentElements.length === 1 ? currentElements[0] : null;
            const typeSelect = document.createElement('input');
            typeSelect.type = 'text';
            typeSelect.setAttribute('list', 'element-type-options');
            typeSelect.setAttribute('aria-label', `Element type for ${symbol}`);
            typeSelect.className = 'chemical-type-select';
            typeSelect.dataset.atomLabel = symbol;
            typeSelect.dataset.appearanceField = 'type';
            typeSelect.title = `${labelAtomIndices.length} atom${labelAtomIndices.length === 1 ? '' : 's'} with label ${symbol}`;
            typeSelect.value = currentElement || '';
            typeSelect.placeholder = currentElements.length > 1 ? 'Mixed' : 'Element';
            typeSelect.disabled = labelAtomIndices.length === 0;

            const visibleBox = document.createElement('input');
            visibleBox.type = 'checkbox';
            visibleBox.className = 'label-check label-visible-checkbox';
            visibleBox.dataset.atomLabel = symbol;
            visibleBox.dataset.appearanceField = 'visible';
            visibleBox.checked = this.isLabelVisible(symbol);
            visibleBox.title = `Show ${symbol} atoms in the viewport`;
            visibleBox.addEventListener('change', () => {
                this.state.display.labelVisible = {
                    ...(this.state.display.labelVisible || {}),
                    [symbol]: visibleBox.checked
                };
                if (!visibleBox.checked) {
                    this.labelIndices(symbol).forEach(index => this.state.selected.delete(index));
                    this.state.replicaSelected.forEach((reference, key) => {
                        if (this.state.atoms?.symbols?.[reference.index] === symbol) {
                            this.state.replicaSelected.delete(key);
                        }
                    });
                }
                this.safeApplyDisplayOptions();
                this.updateLabelSelectionControls();
                this.updateUI();
            });

            const selectBox = document.createElement('input');
            selectBox.type = 'checkbox';
            selectBox.className = 'label-check label-select-checkbox';
            selectBox.dataset.atomLabel = symbol;
            selectBox.dataset.appearanceField = 'select';
            selectBox.disabled = !this.isLabelVisible(symbol) || labelAtomIndices.length === 0;
            selectBox.title = `Select all visible ${symbol} atoms`;
            const selectionState = this.labelSelectionState(symbol);
            selectBox.checked = selectionState === 'all';
            selectBox.indeterminate = selectionState === 'partial';
            selectBox.addEventListener('change', () => this.toggleLabelSelection(symbol, selectBox.checked));

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.id = this.safeControlId('atom-label', symbol);
            nameInput.className = 'atom-label-input';
            nameInput.dataset.atomLabel = symbol;
            nameInput.dataset.appearanceField = 'label';
            nameInput.value = symbol;
            nameInput.disabled = labelAtomIndices.length === 0;
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
                const requestKey = `${desired}\u0000${baseOverride || ''}`;
                if (!desired || renameRequestKey === requestKey) return;
                if (desired === symbol && (!baseOverride || baseOverride === currentElement)) return;
                renameRequestKey = requestKey;
                const applied = await this.renameAtomLabel(symbol, desired, baseOverride, labelAtomIndices);
                if (!applied && nameInput.isConnected) renameRequestKey = null;
            };
            typeSelect.addEventListener('change', () => {
                if (!this.chemicalElementOptions().includes(typeSelect.value)) {
                    const invalidType = typeSelect.value;
                    typeSelect.value = currentElement || '';
                    this.toast(`${invalidType || 'Unknown'} is not a valid element type.`, 'warning');
                    return;
                }
                const radius = this.defaultElementRadius(typeSelect.value);
                if (Number.isFinite(radius) && radius > 0) input.value = Number(radius.toFixed(4));
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
            color.className = 'label-color-input';
            color.dataset.atomLabel = symbol;
            color.dataset.appearanceField = 'color';
            color.value = this.labelVisualColor(symbol);
            color.title = `Color for ${symbol}`;
            color.addEventListener('input', () => {
                this.state.display.labelColors[symbol] = color.value;
                this.safeApplyDisplayOptions();
                this.updateSelectedAppearanceControls();
            });
            color.addEventListener('change', () => {
                this.state.display.labelColors[symbol] = color.value;
                this.safeApplyDisplayOptions();
                this.updateSelectedAppearanceControls();
            });

            const input = document.createElement('input');
            input.type = 'number';
            input.id = this.safeControlId('label-radius', symbol);
            input.className = 'label-radius-input';
            input.dataset.atomLabel = symbol;
            input.dataset.appearanceField = 'radius';
            input.min = '0.05';
            input.step = '0.01';
            input.value = this.state.display.labelRadii[symbol];
            input.addEventListener('change', () => this.safeApplyDisplayOptions());
            input.addEventListener('input', () => this.safeApplyDisplayOptions());

            const material = document.createElement('select');
            material.className = 'appearance-material-select';
            material.dataset.atomLabel = symbol;
            material.dataset.appearanceField = 'material';
            const activeMaterials = [...new Set(labelAtomIndices.map(index => this.atomMaterialPreset(index)))];
            if (activeMaterials.length > 1) {
                const mixed = document.createElement('option');
                mixed.value = 'mixed';
                mixed.textContent = 'Mixed';
                mixed.disabled = true;
                material.appendChild(mixed);
            }
            ATOM_MATERIAL_PRESETS.forEach(preset => {
                const option = document.createElement('option');
                option.value = preset;
                option.textContent = preset[0].toUpperCase() + preset.slice(1);
                material.appendChild(option);
            });
            material.value = activeMaterials.length === 1 ? activeMaterials[0] : 'mixed';
            material.title = this.state.vizOnly
                ? `Material for all ${symbol} atoms`
                : `Set material for every atom currently labelled ${symbol}`;
            material.addEventListener('change', () => {
                if (material.value === 'mixed') return;
                const preset = this.normalizedAtomMaterialPreset(material.value);
                this.state.display.labelMaterials = {
                    ...(this.state.display.labelMaterials || {}),
                    [symbol]: preset
                };
                const atomMaterials = { ...(this.state.display.atomMaterials || {}) };
                labelAtomIndices.forEach(index => { delete atomMaterials[index]; });
                this.state.display.atomMaterials = atomMaterials;
                this.safeApplyDisplayOptions();
                this.updateSelectedAppearanceControls();
            });

            row.append(typeSelect, visibleBox, selectBox, nameInput, color, input, material);
            root.appendChild(row);
        });
        const focusMatch = [...root.querySelectorAll('[data-atom-label][data-appearance-field]')]
            .find(element => (
                element.dataset.atomLabel === existingFocus.label
                && element.dataset.appearanceField === existingFocus.field
            ));
        focusMatch?.focus();
    }

    parseLabelRadii() {
        const radii = {};
        document.querySelectorAll('.label-radius-input').forEach(input => {
            const value = parseFloat(input.value);
            if (Number.isFinite(value) && value > 0) {
                radii[input.dataset.atomLabel] = value;
            }
        });
        return radii;
    }

    parseLabelColors() {
        const colors = {};
        document.querySelectorAll('.label-color-input').forEach(input => {
            if (this.validHexColor(input.value)) {
                colors[input.dataset.atomLabel] = input.value;
            }
        });
        Object.entries(this.state.display.labelColors || {}).forEach(([symbol, color]) => {
            if (this.validHexColor(color) && !(symbol in colors)) colors[symbol] = color;
        });
        return colors;
    }

    parseLabelVisibility() {
        const visible = { ...(this.state.display.labelVisible || {}) };
        document.querySelectorAll('.label-visible-checkbox').forEach(input => {
            visible[input.dataset.atomLabel] = input.checked;
        });
        return visible;
    }

    updateLabelSelectionControls() {
        document.querySelectorAll('.label-select-checkbox').forEach(input => {
            const symbol = input.dataset.atomLabel;
            input.disabled = !this.isLabelVisible(symbol) || this.labelIndices(symbol).length === 0;
            const state = this.labelSelectionState(symbol);
            input.checked = state === 'all';
            input.indeterminate = state === 'partial';
        });
        document.querySelectorAll('.label-visible-checkbox').forEach(input => {
            input.checked = this.isLabelVisible(input.dataset.atomLabel);
        });
    }

    toggleLabelSelection(symbol, checked) {
        const targets = this.visibleLabelIndices(symbol);
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
        this.updateLabelSelectionControls();
        this.updateUI();
    }

    selectLabel(symbol) {
        this.toggleLabelSelection(symbol, true);
    }

    async renameAtomLabel(oldSymbol, nextLabel, baseSymbol = null, expectedIndices = null) {
        const desiredLabel = this.normalizedTypeLabel(nextLabel);
        if (!desiredLabel) {
            this.toast('Atom type name cannot be empty.', 'warning');
            return false;
        }
        if (this.state.pendingLabelRenames.has(oldSymbol)) return true;
        const indices = Array.isArray(expectedIndices)
            ? [...expectedIndices]
            : [...this.labelIndices(oldSymbol)];
        const labels = this.state.atoms?.symbols || [];
        if (!indices.length || indices.some(index => labels[index] !== oldSymbol)) return false;

        const label = desiredLabel;
        const sourceIndexSet = new Set(indices);
        const targetIndices = labels
            .map((value, index) => ({ value, index }))
            .filter(entry => entry.value === label && !sourceIndexSet.has(entry.index))
            .map(entry => entry.index);
        const targetBases = [...new Set(
            targetIndices
                .map(index => this.state.atoms?.chemical_symbols?.[index])
                .filter(symbol => CHEMICAL_ELEMENT_SET.has(symbol))
        )];
        const targetExists = targetIndices.length > 0;
        const inferredBase = this.detectedElementForLabel(label);
        const base = baseSymbol || (targetBases.length === 1 ? targetBases[0] : inferredBase);
        const oldBases = [...new Set(
            indices
                .map(index => this.state.atoms?.chemical_symbols?.[index])
                .filter(symbol => CHEMICAL_ELEMENT_SET.has(symbol))
        )];
        const preserveAppearance = !base || (oldBases.length === 1 && oldBases[0] === base);
        if (label === oldSymbol && !baseSymbol && (!base || preserveAppearance)) return true;
        this.state.pendingLabelRenames.add(oldSymbol);
        try {
            if (!this.canEditAtoms()) {
                this.renameAtomLabelForVisualization(oldSymbol, label, indices, base, {
                    preserveAppearance,
                    targetExists
                });
                return true;
            }
            const actionText = label === oldSymbol
                ? `Updating ${oldSymbol} element type to ${base}`
                : `Renaming ${oldSymbol} to ${label}`;
            const data = await this.withBusy(
                `${actionText} for ${indices.length} atom${indices.length === 1 ? '' : 's'}...`,
                () => this.api.updateAtomIdentity(indices, label, this.backendPositionsPayload(), this.state.applyConstraints, base)
            );
            this.transferLabelDisplaySettings(oldSymbol, label, {
                appearance: preserveAppearance,
                removeSource: label !== oldSymbol,
                copySource: !targetExists
            });
            if (!preserveAppearance && !targetExists && base) {
                this.setElementBaseDefaults(label, base);
            }
            if (label !== oldSymbol) this.replaceLabelOrder(oldSymbol, label);
            this.setAtomsData(data, { preserveDisplay: false });
            this.toast(
                label === oldSymbol
                    ? `Updated ${label} element type to ${base}.`
                    : (targetExists
                        ? `Merged ${oldSymbol} into label ${label}.`
                        : `Renamed ${oldSymbol} to ${label}.`),
                'success'
            );
            return true;
        } catch (err) {
            this.toast(`Rename failed: ${err.message}`, 'error');
            return false;
        } finally {
            this.state.pendingLabelRenames.delete(oldSymbol);
        }
    }

    renameAtomLabelForVisualization(
        oldSymbol,
        label,
        indices = this.labelIndices(oldSymbol),
        baseSymbol = null,
        { preserveAppearance = true, targetExists = false } = {}
    ) {
        if (!this.state.atoms || !indices.length) return;
        const radius = baseSymbol ? this.defaultElementRadius(baseSymbol) : null;
        const color = baseSymbol ? this.defaultElementColor(baseSymbol) : null;
        indices.forEach(index => {
            this.state.atoms.symbols[index] = label;
            if (Array.isArray(this.state.atoms.atom_types)) {
                this.state.atoms.atom_types[index] = label;
            }
            if (baseSymbol && Array.isArray(this.state.atoms.chemical_symbols)) {
                this.state.atoms.chemical_symbols[index] = baseSymbol;
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
        this.rebuildLabelIndexCache(this.state.atoms.symbols || []);
        const selected = new Set();
        this.state.selected.forEach(index => {
            if (this.isLabelVisible(this.state.atoms.symbols[index])) selected.add(index);
        });
        this.state.selected = selected;
        this.transferLabelDisplaySettings(oldSymbol, label, {
            appearance: preserveAppearance,
            removeSource: label !== oldSymbol,
            copySource: !targetExists
        });
        if (!preserveAppearance && !targetExists && baseSymbol) {
            this.setElementBaseDefaults(label, baseSymbol, { color: true });
        }
        this.updateLocalTrajectoryIdentity(oldSymbol, label, baseSymbol);
        if (label !== oldSymbol) this.replaceLabelOrder(oldSymbol, label);
        this.renderPairwiseBondControls();
        this.renderer.renameAtomLabel(oldSymbol, label, indices, this.state.display, baseSymbol);
        this.renderAppearanceRows();
        this.updateLabelSelectionControls();
        this.pruneSelection();
        this.updateSelectionVisuals();
        this.updateUI();
        this.toast(
            label === oldSymbol
                ? `Updated ${label} element type to ${baseSymbol} for this visualization.`
                : (targetExists
                    ? `Merged ${oldSymbol} into label ${label} for this visualization.`
                    : `Renamed ${oldSymbol} to ${label} for this visualization.`),
            'success'
        );
    }

    prepareLabelOrderForIdentityChange(indices, targetLabel) {
        const selected = new Set(indices);
        const simulated = (this.state.atoms?.symbols || []).map(
            (label, index) => selected.has(index) ? targetLabel : label
        );
        const present = new Set(simulated);
        const current = [...this.uniqueAtomLabels()];
        const affected = [...new Set(indices.map(index => this.state.atoms?.symbols?.[index]).filter(Boolean))];
        const targetAlreadyOrdered = current.includes(targetLabel);
        const next = current.filter(label => present.has(label));
        if (!targetAlreadyOrdered && present.has(targetLabel)) {
            const affectedPositions = affected
                .map(label => current.indexOf(label))
                .filter(index => index >= 0);
            const insertAt = affectedPositions.length
                ? Math.min(...affectedPositions) + 1
                : next.length;
            next.splice(Math.min(insertAt, next.length), 0, targetLabel);
        }
        this.state.labelOrder = [...new Set(next)];
    }

    async applySelectedLabelEdit() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const indices = this.selectedAtomIndices();
        if (!indices.length) {
            this.toast('Select atoms before changing their label.', 'warning');
            return;
        }
        const input = document.getElementById('selected-atom-label');
        const label = this.normalizedTypeLabel(input?.value);
        if (!label) {
            this.toast('Atom label cannot be empty.', 'warning');
            return;
        }
        const previousLabels = [...new Set(indices.map(index => this.state.atoms.symbols[index]))];
        if (previousLabels.length === 1 && previousLabels[0] === label) return;

        const selectedSet = new Set(indices);
        const targetIndices = this.labelIndices(label);
        const targetExists = targetIndices.length > 0;
        const targetBases = [...new Set(
            targetIndices
                .map(index => this.state.atoms?.chemical_symbols?.[index])
                .filter(symbol => CHEMICAL_ELEMENT_SET.has(symbol))
        )];
        const previousBases = [...new Set(
            indices
                .map(index => this.state.atoms?.chemical_symbols?.[index])
                .filter(symbol => CHEMICAL_ELEMENT_SET.has(symbol))
        )];
        const detectedBase = this.detectedElementForLabel(label);
        const base = targetBases.length === 1 ? targetBases[0] : detectedBase;
        const preserveAppearance = !base || (previousBases.length === 1 && previousBases[0] === base);
        const priorMaterials = new Map(indices.map(index => [index, this.atomMaterialPreset(index)]));

        try {
            const data = await this.withBusy(
                `Assigning ${indices.length} selected atom${indices.length === 1 ? '' : 's'} to ${label}...`,
                () => this.api.updateAtomIdentity(
                    indices,
                    label,
                    this.backendPositionsPayload(),
                    this.state.applyConstraints,
                    base
                )
            );

            let copiedSource = targetExists;
            previousLabels.filter(source => source !== label).forEach(source => {
                const sourceStillPresent = this.labelIndices(source).some(index => !selectedSet.has(index));
                this.transferLabelDisplaySettings(source, label, {
                    appearance: preserveAppearance,
                    removeSource: !sourceStillPresent,
                    copySource: !copiedSource
                });
                if (!copiedSource) copiedSource = true;
            });
            if (!preserveAppearance && !targetExists && base) {
                this.setElementBaseDefaults(label, base);
            }

            const targetMaterial = this.normalizedAtomMaterialPreset(
                this.state.display.labelMaterials?.[label]
            );
            const atomMaterials = { ...(this.state.display.atomMaterials || {}) };
            indices.forEach(index => {
                const previous = priorMaterials.get(index) || 'standard';
                if (previous === targetMaterial) delete atomMaterials[index];
                else atomMaterials[index] = previous;
            });
            this.state.display.atomMaterials = atomMaterials;
            this.prepareLabelOrderForIdentityChange(indices, label);
            this.setAtomsData(data, { preserveDisplay: false });
            indices.forEach(index => this.state.selected.add(index));
            this.updateSelectionVisuals();
            this.updateUI();
            this.toast(
                targetExists
                    ? `Merged selected atoms into label ${label}.`
                    : `Assigned selected atoms to label ${label}.`,
                'success'
            );
        } catch (err) {
            this.toast(`Selected label update failed: ${err.message}`, 'error');
        }
    }

    async applySelectedTypeEdit() {
        return await this.applySelectedLabelEdit();
    }

    renderPairwiseBondControls({ capture = true } = {}) {
        const root = document.getElementById('pairwise-bond-list');
        if (!root || !this.state.atoms?.symbols) return;
        this.applyPairwiseLabelColumnWidth();
        if (capture) this.captureBondSettingsFromControls();
        const existingFocus = document.activeElement?.dataset?.pairKey
            ? {
                key: document.activeElement.dataset.pairKey,
                field: document.activeElement.dataset.pairField
            }
            : null;
        root.innerHTML = '';
        this.uniqueLabelPairs().forEach(([a, b]) => {
            const key = this.labelPairKey(a, b);
            const range = this.pairwiseBondRange(a, b);
            this.state.display.pairwiseBondRanges[key] = { ...range };
            this.state.display.pairwiseBondCutoffs[key] = range.enabled ? range.max : 0;
            const row = document.createElement('div');
            row.className = 'pairwise-bond-row';
            row.dataset.pairKey = key;

            const enabled = document.createElement('input');
            enabled.type = 'checkbox';
            enabled.className = 'pairwise-bond-enabled';
            enabled.dataset.pairKey = key;
            enabled.dataset.pairField = 'enabled';
            enabled.checked = range.enabled;
            enabled.setAttribute('aria-label', `Enable ${key} bonds`);

            const label = document.createElement('span');
            label.className = 'pairwise-bond-pair-label';
            label.innerText = key;
            label.title = key;

            const makeDistanceInput = (field, value) => {
                const input = document.createElement('input');
                input.type = 'number';
                input.className = `pairwise-bond-${field}`;
                input.dataset.pairKey = key;
                input.dataset.pairField = field;
                input.min = '0';
                input.step = '0.05';
                input.value = Number(value).toFixed(3);
                input.setAttribute('aria-label', `${key} ${field}imum distance in Angstrom`);
                input.addEventListener('input', () => this.safeApplyBondOptions());
                input.addEventListener('change', () => this.safeApplyBondOptions());
                return input;
            };
            const maximum = makeDistanceInput('max', range.max);
            enabled.addEventListener('change', () => this.safeApplyBondOptions());
            row.append(enabled, label, maximum);
            root.appendChild(row);
        });
        if (existingFocus) {
            const target = [...root.querySelectorAll('[data-pair-key]')].find(element => (
                element.dataset.pairKey === existingFocus.key
                && element.dataset.pairField === existingFocus.field
            ));
            target?.focus();
        }
        this.updateBondModeUI();
    }

    normalizedPairwiseLabelColumnWidth(value = this.state.display.pairwiseLabelColumnWidth) {
        const parsed = Number(value);
        return Math.round(Math.max(120, Math.min(520, Number.isFinite(parsed) ? parsed : 210)));
    }

    applyPairwiseLabelColumnWidth(value = this.state.display.pairwiseLabelColumnWidth) {
        const width = this.normalizedPairwiseLabelColumnWidth(value);
        this.state.display.pairwiseLabelColumnWidth = width;
        const panel = document.getElementById('pairwise-bond-panel');
        panel?.style.setProperty('--pair-label-width', `${width}px`);
        const resizer = document.getElementById('pairwise-label-column-resizer');
        if (resizer) {
            resizer.setAttribute('aria-valuemin', '120');
            resizer.setAttribute('aria-valuemax', '520');
            resizer.setAttribute('aria-valuenow', String(width));
        }
        return width;
    }

    setupPairwiseLabelColumnResizer() {
        const resizer = document.getElementById('pairwise-label-column-resizer');
        if (!resizer || resizer.dataset.bound === 'true') return;
        resizer.dataset.bound = 'true';
        let drag = null;
        const finish = event => {
            if (!drag) return;
            if (event?.pointerId === drag.pointerId && resizer.hasPointerCapture?.(drag.pointerId)) {
                resizer.releasePointerCapture(drag.pointerId);
            }
            drag = null;
            document.body.classList.remove('resizing-pairwise-column');
        };
        resizer.addEventListener('pointerdown', event => {
            if (event.button !== 0) return;
            drag = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startWidth: this.normalizedPairwiseLabelColumnWidth()
            };
            resizer.setPointerCapture?.(event.pointerId);
            document.body.classList.add('resizing-pairwise-column');
            event.preventDefault();
            event.stopPropagation();
        });
        resizer.addEventListener('pointermove', event => {
            if (!drag || event.pointerId !== drag.pointerId) return;
            this.applyPairwiseLabelColumnWidth(
                drag.startWidth + event.clientX - drag.startX
            );
            event.preventDefault();
        });
        ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => {
            resizer.addEventListener(type, finish);
        });
        resizer.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            const current = this.normalizedPairwiseLabelColumnWidth();
            const next = event.key === 'Home'
                ? 120
                : event.key === 'End'
                    ? 520
                    : current + (event.key === 'ArrowRight' ? 12 : -12);
            this.applyPairwiseLabelColumnWidth(next);
            event.preventDefault();
        });
        this.applyPairwiseLabelColumnWidth();
    }

    parsePairwiseBondRanges() {
        const ranges = {};
        const cutoffs = {};
        document.querySelectorAll('.pairwise-bond-row').forEach(row => {
            const key = row.dataset.pairKey;
            if (!key) return;
            const current = this.state.display.pairwiseBondRanges?.[key] || {
                enabled: true,
                min: 0,
                max: 0
            };
            const enabled = row.querySelector('.pairwise-bond-enabled')?.checked !== false;
            const rawMaximum = Number(row.querySelector('.pairwise-bond-max')?.value);
            const maximum = Number.isFinite(rawMaximum)
                ? Math.max(0, rawMaximum)
                : Math.max(0, Number(current.max) || 0);
            ranges[key] = { enabled, min: 0, max: maximum };
            cutoffs[key] = enabled ? maximum : 0;
        });
        return { ranges, cutoffs };
    }

    captureBondSettingsFromControls({ strictManual = false } = {}) {
        if (!this.state?.display) return;
        const mode = document.getElementById('bond-mode')?.value;
        if (['auto', 'pairwise', 'manual'].includes(mode)) {
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
        const parsedSpecifications = this.parsePairwiseBondRanges();
        this.state.display.pairwiseBondRanges = {
            ...(this.state.display.pairwiseBondRanges || {}),
            ...parsedSpecifications.ranges
        };
        this.state.display.pairwiseBondCutoffs = {
            ...(this.state.display.pairwiseBondCutoffs || {}),
            ...parsedSpecifications.cutoffs
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
        const pairwisePanel = document.getElementById('pairwise-bond-panel');
        const pairText = document.getElementById('bond-pairs');
        const manualHint = document.getElementById('bond-manual-hint');
        const cutoffRow = document.getElementById('bond-cutoff')?.closest('.prop-row');
        if (pairwisePanel) pairwisePanel.classList.toggle('hidden', mode !== 'pairwise');
        if (pairText) pairText.classList.toggle('hidden', mode !== 'manual');
        if (manualHint) manualHint.classList.toggle('hidden', mode !== 'manual');
        if (cutoffRow) cutoffRow.classList.toggle('hidden', mode !== 'auto');
        this.updateBondAppearanceUI();
    }

    updateBondAppearanceUI() {
        const mode = document.getElementById('bond-color-mode')?.value || this.state.display.bondColorMode;
        document.getElementById('bond-custom-color-row')?.classList.toggle('hidden', mode !== 'custom');
        const rawThickness = Number(document.getElementById('bond-thickness')?.value || this.state.display.bondThickness);
        const thickness = Number.isFinite(rawThickness) ? rawThickness : 0.25;
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
        const cellThickness = Number(document.getElementById('cell-thickness')?.value);
        this.state.display.cellThickness = Number.isFinite(cellThickness)
            ? Math.max(0.01, Math.min(0.30, cellThickness))
            : 0.04;
        const cellColor = document.getElementById('cell-color')?.value;
        this.state.display.cellColor = this.validHexColor(cellColor) ? cellColor : '#d6bd67';
        const cellMaterial = document.getElementById('cell-material')?.value;
        this.state.display.cellMaterial = ['unlit', 'standard', 'metal'].includes(cellMaterial)
            ? cellMaterial
            : 'unlit';
        this.state.display.showAxes = document.getElementById('chk-axes').checked;
        this.state.display.showGrid = document.getElementById('chk-grid').checked;
        this.state.display.showOverlays = document.getElementById('chk-overlays')?.checked !== false;
        this.state.display.showPeriodicBonds = Boolean(document.getElementById('chk-periodic-bonds')?.checked);
        this.state.display.exportIncludeCell = document.getElementById('export-include-cell')?.checked !== false;
        this.state.display.projectionMode = document.getElementById('projection-mode')?.value || 'perspective';
        this.state.display.viewportBackground = document.getElementById('viewport-background')?.value === 'dark'
            ? 'dark'
            : 'white';
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
        const radiusScale = parseFloat(document.getElementById('atom-radius-scale')?.value || '0.6');
        this.state.display.atomRadiusScale = Number.isFinite(radiusScale) && radiusScale > 0
            ? radiusScale
            : 0.6;
        this.state.display.labelRadii = this.parseLabelRadii();
        this.state.display.labelColors = this.parseLabelColors();
        this.state.display.labelVisible = this.parseLabelVisibility();
        this.state.display.supercell = this.normalizeSupercellInputs();
        this.state.display.antiAliasing = this.state.antiAliasing;
        this.state.display.sphereQuality = this.state.sphereQuality;
        this.state.display.vizOnly = this.state.vizOnly;
        this.state.display.blenderExportMode = document.getElementById('blender-export-mode')?.value || 'instanced';
        this.readDisplacementControls({ applyRenderer: false });
        this.updateRadiusScaleLabel();
        this.syncViewControls();
        this.pruneSelection();
        this.renderer.setDisplayOptions(this.state.display);
        this.updateSelectionVisuals();
        this.updateLabelSelectionControls();
        this.updateBondModeUI();
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        this.scheduleVisualHistoryCommit('display');
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

    applyBondOptions() {
        if (this.state.bondApplyRequest !== null) {
            cancelAnimationFrame(this.state.bondApplyRequest);
            this.state.bondApplyRequest = null;
        }
        const previousRdfPairs = (
            this.state.rdfResult
            && this.state.display.rdfPairMode === 'active'
        ) ? JSON.stringify(this.activeRdfPairs()) : null;
        this.state.display.showBonds = Boolean(document.getElementById('chk-bonds')?.checked);
        this.state.display.showPeriodicBonds = Boolean(
            document.getElementById('chk-periodic-bonds')?.checked
        );
        this.captureBondSettingsFromControls();
        this.updateBondModeUI();
        this.renderer.setDisplayOptions({
            showBonds: this.state.display.showBonds,
            showPeriodicBonds: this.state.display.showPeriodicBonds,
            bondMode: this.state.display.bondMode,
            bondCutoffScale: this.state.display.bondCutoffScale,
            manualBondPairs: this.state.display.manualBondPairs,
            pairwiseBondCutoffs: this.state.display.pairwiseBondCutoffs,
            pairwiseBondRanges: this.state.display.pairwiseBondRanges,
            bondStyle: this.state.display.bondStyle,
            bondThickness: this.state.display.bondThickness,
            bondColorMode: this.state.display.bondColorMode,
            bondCustomColor: this.state.display.bondCustomColor
        });
        if (
            previousRdfPairs !== null
            && previousRdfPairs !== JSON.stringify(this.activeRdfPairs())
        ) {
            this.invalidateRdfResult(
                'Active bond-pair settings changed. Calculate the RDF again.'
            );
        }
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        this.scheduleVisualHistoryCommit('bonds');
    }

    safeApplyBondOptions() {
        if (this.state.bondApplyRequest !== null) return;
        this.state.bondApplyRequest = requestAnimationFrame(() => {
            this.state.bondApplyRequest = null;
            try {
                this.applyBondOptions();
            } catch (err) {
                this.toast(err.message, 'error');
            }
        });
    }

    clonePlain(value) {
        if (window.structuredClone) return window.structuredClone(value);
        return JSON.parse(JSON.stringify(value));
    }

    currentCollaborationActor(sourceHint = '') {
        const hint = String(sourceHint || '').toLowerCase();
        if (this.collaborationActorDepth > 0 || hint.startsWith('ai-')) return 'agent';
        if (hint === 'system') return 'system';
        return 'human';
    }

    collaborationContext() {
        return {
            document: this.workspaceDocumentTitle(),
            frame: Number(this.state.atoms?.metadata?.current_frame || 0),
            atom_count: Number(
                this.state.atoms?.metadata?.natoms
                || this.state.atoms?.positions?.length
                || 0
            ),
            selection_count: this.selectionCount()
        };
    }

    collaborationSelectionKey() {
        return JSON.stringify(this.selectionEntries().map(reference => {
            const normalized = this.normalizeSelectionReference(reference);
            return normalized?.key || null;
        }).filter(Boolean));
    }

    collaborationCameraKey() {
        if (!this.renderer?.camera) return null;
        return JSON.stringify(this.cameraSettingsSnapshot());
    }

    collaborationChangedPaths(before, after, prefix = '', output = []) {
        if (output.length >= 64) return output;
        if (before === after) return output;
        const beforeObject = before && typeof before === 'object' && !Array.isArray(before);
        const afterObject = after && typeof after === 'object' && !Array.isArray(after);
        if (beforeObject && afterObject) {
            const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
            for (const key of keys) {
                this.collaborationChangedPaths(
                    before[key],
                    after[key],
                    prefix ? `${prefix}.${key}` : key,
                    output
                );
                if (output.length >= 64) break;
            }
            return output;
        }
        if (JSON.stringify(before) !== JSON.stringify(after)) {
            output.push(prefix || 'state');
        }
        return output;
    }

    collaborationMutationDetails(path = '') {
        const endpoint = String(path || '');
        const table = [
            ['/api/file/append', ['document', 'trajectory'], ['trajectory.frames'], 'Structures were appended to the trajectory.'],
            ['/api/file/load', ['document', 'structure', 'trajectory'], ['document', 'structure', 'trajectory'], 'A structure or trajectory replaced the live document.'],
            ['/api/project/load/', ['document', 'structure', 'display'], ['document', 'structure', 'display'], 'A v_ase project replaced the live document.'],
            ['/api/settings/load/', ['display'], ['display'], 'Reusable visual settings were loaded.'],
            ['/api/calculator/', ['structure'], ['calculator'], 'The ASE calculator configuration changed.'],
            ['/api/relax/start/', ['structure', 'trajectory'], ['relaxation.status'], 'Structure relaxation started.'],
            ['/api/relax/stop/', ['structure', 'trajectory'], ['relaxation.status'], 'Structure relaxation stopped.'],
            ['/api/atom-identity/', ['structure'], ['structure.identity'], 'Atom identity changed.'],
            ['/api/constraints/', ['constraints'], ['constraints'], 'ASE constraints changed.'],
            ['/api/supercell/', ['structure'], ['structure.cell', 'structure.positions'], 'The working supercell changed.'],
            ['/api/translate/', ['structure'], ['structure.positions'], 'Atom coordinates were translated.'],
            ['/api/add/', ['structure'], ['structure.topology'], 'An atom was added.'],
            ['/api/delete/', ['structure'], ['structure.topology'], 'Selected atoms were deleted.'],
            ['/api/wrap/', ['structure'], ['structure.positions'], 'Atoms were wrapped into the cell.'],
            ['/api/reset-coordinates/', ['structure'], ['structure.positions'], 'Atom coordinates were reset.'],
            ['/api/reset/', ['structure', 'display'], ['structure', 'display'], 'The document was reset.'],
            ['/api/apply/', ['structure'], ['structure.positions'], 'Atom coordinates changed.']
        ];
        const match = table.find(([prefix]) => endpoint.includes(prefix));
        if (match) {
            return {
                categories: match[1],
                changedPaths: match[2],
                summary: match[3]
            };
        }
        return {
            categories: ['structure'],
            changedPaths: ['structure'],
            summary: 'The atomic structure changed.'
        };
    }

    collaborationSummary(source, categories, summaries = []) {
        const unique = [...new Set(
            summaries.map(value => String(value || '').trim()).filter(Boolean)
        )];
        if (unique.length) return unique.slice(0, 3).join(' ');
        const actor = source === 'agent' ? 'Agent' : source === 'system' ? 'System' : 'Human';
        return `${actor} changed ${categories.join(', ')}.`;
    }

    scheduleCollaborationEvent({
        type = 'state.changed',
        source = this.currentCollaborationActor(),
        categories = ['state'],
        changedPaths = [],
        summary = '',
        delay = 160
    } = {}) {
        if (!this.collaborationReady) return;
        const actor = ['human', 'agent', 'system'].includes(source) ? source : 'human';
        const pending = this.collaborationPending.get(actor) || {
            type,
            source: actor,
            categories: new Set(),
            changedPaths: new Set(),
            summaries: [],
            timer: null
        };
        categories.forEach(category => pending.categories.add(category));
        changedPaths.forEach(path => pending.changedPaths.add(path));
        if (summary) pending.summaries.push(summary);
        if (pending.timer !== null) clearTimeout(pending.timer);
        pending.timer = window.setTimeout(
            () => void this.flushCollaborationEvents(actor),
            Math.max(0, delay)
        );
        this.collaborationPending.set(actor, pending);
    }

    async publishCollaborationEvent({
        type = 'state.changed',
        source = 'human',
        categories = ['state'],
        changedPaths = [],
        summary = 'Session state changed.'
    } = {}) {
        if (!this.sessionId) return null;
        try {
            const event = await this.api.publishCollaborationEvent({
                type,
                source,
                categories: [...new Set(categories)],
                changed_paths: [...new Set(changedPaths)].slice(0, 64),
                summary,
                ...this.collaborationContext()
            });
            this.collaborationRevision = Math.max(
                this.collaborationRevision,
                Number(event?.revision) || 0
            );
            return event;
        } catch (err) {
            console.warn('Collaboration event publish failed:', err);
            return null;
        }
    }

    async flushCollaborationEvents(source = null) {
        const actors = source
            ? [source]
            : [...this.collaborationPending.keys()];
        for (const actor of actors) {
            const pending = this.collaborationPending.get(actor);
            if (!pending) continue;
            if (pending.timer !== null) clearTimeout(pending.timer);
            this.collaborationPending.delete(actor);
            const categories = [...pending.categories];
            await this.publishCollaborationEvent({
                type: pending.type,
                source: pending.source,
                categories,
                changedPaths: [...pending.changedPaths],
                summary: this.collaborationSummary(
                    pending.source,
                    categories,
                    pending.summaries
                )
            });
        }
        return this.collaborationRevision;
    }

    observeCollaborationCamera(source = 'camera') {
        const signature = this.collaborationCameraKey();
        if (signature === null) return;
        if (this.collaborationCameraSignature === null) {
            this.collaborationCameraSignature = signature;
            return;
        }
        if (signature === this.collaborationCameraSignature) return;
        this.collaborationCameraSignature = signature;
        this.scheduleCollaborationEvent({
            source: this.currentCollaborationActor(source),
            categories: ['camera'],
            changedPaths: ['camera'],
            summary: 'The viewport camera changed.'
        });
    }

    observeCollaborationSelection() {
        const signature = this.collaborationSelectionKey();
        if (this.collaborationSelectionSignature === null) {
            this.collaborationSelectionSignature = signature;
            return;
        }
        if (signature === this.collaborationSelectionSignature) return;
        this.collaborationSelectionSignature = signature;
        this.scheduleCollaborationEvent({
            source: this.currentCollaborationActor(),
            categories: ['selection'],
            changedPaths: ['selection.references'],
            summary: `${this.selectionCount()} atom selection reference(s) are active.`
        });
    }

    observeCollaborationFrame() {
        const frame = Number(this.state.atoms?.metadata?.current_frame || 0);
        if (this.collaborationFrame === null) {
            this.collaborationFrame = frame;
            return;
        }
        if (frame === this.collaborationFrame) return;
        this.collaborationFrame = frame;
        this.scheduleCollaborationEvent({
            source: this.currentCollaborationActor(),
            categories: ['frame', 'trajectory'],
            changedPaths: ['trajectory.frame'],
            summary: `The active trajectory frame changed to ${frame}.`
        });
    }

    collaborationCommandDetails(command = {}) {
        const categories = new Set();
        const changedPaths = new Set();
        if (command.frame !== undefined) {
            categories.add('frame');
            categories.add('trajectory');
            changedPaths.add('trajectory.frame');
        }
        if (command.mode !== undefined) {
            categories.add('mode');
            changedPaths.add('mode');
        }
        if (command.display !== undefined || command.quality !== undefined) {
            categories.add('display');
            changedPaths.add('display');
        }
        if (command.applyConstraints !== undefined) {
            categories.add('constraints');
            changedPaths.add('applyConstraints');
        }
        if (command.camera !== undefined) {
            categories.add('camera');
            changedPaths.add('camera');
        }
        if (command.selection !== undefined) {
            categories.add('selection');
            changedPaths.add('selection.references');
        }
        if (command.operation !== undefined) {
            const operation = typeof command.operation === 'string'
                ? command.operation
                : command.operation?.name;
            if (operation === 'set-constraints') categories.add('constraints');
            else if ([
                'refresh-displacements',
                'load-volumetric',
                'show-volumetric',
                'combine-volumetric',
                'remove-volumetric',
                'calculate-rdf'
            ].includes(operation)) categories.add('analysis');
            else if (['start-relaxation', 'stop-relaxation'].includes(operation)) {
                categories.add('trajectory');
                categories.add('structure');
            } else {
                categories.add('structure');
            }
            changedPaths.add(`operation.${operation || 'unknown'}`);
        }
        if (!categories.size) categories.add('state');
        return {
            source: 'agent',
            categories: [...categories],
            changedPaths: [...changedPaths],
            summary: 'Agent applied a structured v_ase command.'
        };
    }

    aiSelectionSnapshot() {
        return this.selectionEntries().map(reference => {
            const normalized = this.normalizeSelectionReference(reference);
            if (!normalized) return null;
            return normalized.kind === 'replica'
                ? {
                    kind: 'replica',
                    index: normalized.index,
                    cellOffset: [...normalized.cellOffset],
                    label: this.selectionReferenceSymbol(normalized),
                    position: this.selectionReferencePosition(normalized)?.toArray() || null
                }
                : {
                    kind: 'atom',
                    index: normalized.index,
                    label: this.selectionReferenceSymbol(normalized),
                    position: this.selectionReferencePosition(normalized)?.toArray() || null
                };
        }).filter(Boolean);
    }

    aiDescribe({ includePositions = true } = {}) {
        const atoms = this.state.atoms || {};
        const positions = includePositions
            ? (atoms.positions || []).map((position, index) => {
                const current = this.currentAtomPosition(index);
                return current ? [...current] : [...position];
            })
            : undefined;
        const labelCounts = {};
        const elementCounts = {};
        (atoms.symbols || []).forEach(label => {
            labelCounts[label] = (labelCounts[label] || 0) + 1;
        });
        (atoms.chemical_symbols || []).forEach(symbol => {
            elementCounts[symbol] = (elementCounts[symbol] || 0) + 1;
        });
        const result = {
            protocol: 'v_ase.ai.v1',
            units: { length: 'angstrom', angle: 'degree' },
            document: this.workspaceDocumentTitle(),
            mode: this.state.vizOnly ? 'view' : 'edit',
            frame: Number(atoms.metadata?.current_frame || 0),
            frameCount: Number(atoms.metadata?.frame_count || 1),
            atomCount: Number(atoms.metadata?.natoms || atoms.positions?.length || 0),
            labels: [...(atoms.symbols || [])],
            chemicalSymbols: [...(atoms.chemical_symbols || [])],
            atomicNumbers: [...(atoms.atomic_numbers || [])],
            labelCounts,
            elementCounts,
            cell: this.clonePlain(atoms.cell || []),
            pbc: [...(atoms.pbc || [])],
            constraints: this.clonePlain(atoms.constraints || {}),
            tags: [...(atoms.tags || [])],
            charges: [...(atoms.charges || [])],
            magneticMoments: [...(atoms.magmoms || [])],
            forces: this.clonePlain(atoms.forces || []),
            calculator: {
                attached: Boolean(atoms.metadata?.has_calculator),
                name: atoms.metadata?.calculator || null,
                details: this.clonePlain(atoms.metadata?.calculator_details || {})
            },
            selection: this.aiSelectionSnapshot(),
            measurement: this.getSelectionMeasureText(),
            display: this.clonePlain(this.state.display),
            camera: this.cameraSettingsSnapshot(),
            imageExport: this.clonePlain(this.currentImageExportProfile()),
            analysis: {
                volumetricDatasets: this.clonePlain(this.volumetricDatasets()),
                rdf: this.state.rdfResult ? {
                    schema: this.state.rdfResult.schema,
                    bins: this.state.rdfResult.bins,
                    requestedCutoff: this.state.rdfResult.requested_cutoff,
                    cutoff: this.state.rdfResult.cutoff,
                    uniqueMicCutoff: (
                        this.state.rdfResult.unique_mic_cutoff
                        ?? this.state.rdfResult.safe_cutoff
                    ),
                    // Retained for agents written against v_ase <= 0.1.1.
                    safeCutoff: this.state.rdfResult.safe_cutoff,
                    periodicImageExtent: [
                        ...(this.state.rdfResult.periodic_image_extent || [])
                    ],
                    periodicImageSpan: [
                        ...(this.state.rdfResult.periodic_image_span || [])
                    ],
                    pairMode: this.state.rdfResult.pair_mode,
                    partialCurves: Object.keys(this.state.rdfResult.partial || {}),
                    warnings: [...(this.state.rdfResult.warnings || [])],
                    frame: this.state.rdfResult.frame_index
                } : null
            },
            collaboration: {
                protocol: 'v_ase.collaboration.v1',
                revision: this.collaborationRevision,
                eventStream: true
            }
        };
        if (includePositions) result.positions = positions;
        return result;
    }

    setAIAxisView(axis) {
        const normalized = String(axis || '').trim().toUpperCase();
        const match = /^([+-])([XYZ])$/.exec(normalized);
        if (!match) {
            throw new Error('camera.axis must be one of +X, -X, +Y, -Y, +Z, or -Z.');
        }
        const vectors = {
            X: new THREE.Vector3(1, 0, 0),
            Y: new THREE.Vector3(0, 1, 0),
            Z: new THREE.Vector3(0, 0, 1)
        };
        const direction = vectors[match[2]].multiplyScalar(match[1] === '+' ? 1 : -1);
        const camera = this.renderer.camera;
        const target = this.renderer.controls.target.clone();
        const distance = Math.max(camera.position.distanceTo(target), 4);
        camera.up.copy(match[2] === 'Z'
            ? new THREE.Vector3(0, 1, 0)
            : new THREE.Vector3(0, 0, 1));
        camera.position.copy(target).addScaledVector(direction, distance);
        this.completeCameraViewChange('ai-axis-view');
    }

    async aiCapabilities() {
        const schemaUrl = new URL('/api/ai/schema', window.location.origin).href;
        let discovery = {};
        try {
            const response = await fetch(schemaUrl);
            if (response.ok) discovery = await response.json();
        } catch {
            // The static capability lists below remain usable offline.
        }
        return {
            protocol: 'v_ase.ai.v1',
            schemaUrl,
            operationParameters: this.clonePlain(discovery.operation_parameters || {}),
            exportParameters: this.clonePlain(discovery.export_parameters || {}),
            state: [
                'atoms', 'labels', 'elements', 'positions', 'cell', 'pbc',
                'constraints', 'forces', 'charges', 'tags', 'magnetic-moments',
                'selection', 'measurement', 'trajectory', 'camera', 'display',
                'volumetric-data', 'rdf', 'collaboration'
            ],
            apply: [
                'expectedRevision', 'frame', 'mode', 'display', 'quality',
                'applyConstraints', 'camera', 'selection', 'operation'
            ],
            operations: [
                'wrap', 'translate-all', 'set-supercell', 'make-supercell',
                'add-atom', 'delete-selection', 'set-identity', 'set-constraints',
                'move-selection', 'rotate-selection', 'undo', 'redo',
                'reset-coordinates', 'start-relaxation', 'stop-relaxation',
                'refresh-displacements', 'load-volumetric', 'show-volumetric',
                'combine-volumetric', 'remove-volumetric', 'calculate-rdf'
            ],
            exports: [
                'image', 'video', 'poscar', 'pickle', 'blender', '3dm', 'obj',
                'html', 'project', 'settings', 'rdf-csv'
            ]
        };
    }

    aiFiniteVector(value, name = 'vector') {
        if (
            !Array.isArray(value)
            || value.length !== 3
            || !value.every(component => Number.isFinite(Number(component)))
        ) {
            throw new Error(`${name} must contain three finite numbers.`);
        }
        return value.map(Number);
    }

    aiOperationIndices(operation) {
        const values = operation.indices === undefined
            ? this.selectedAtomIndices()
            : operation.indices;
        if (!Array.isArray(values) || !values.length) {
            throw new Error('The operation requires selected atoms or a non-empty indices array.');
        }
        const atomCount = this.state.atoms?.positions?.length || 0;
        const indices = [...new Set(values.map(Number))];
        if (!indices.every(index => Number.isInteger(index) && index >= 0 && index < atomCount)) {
            throw new Error(`Operation indices must be integers inside 0..${Math.max(0, atomCount - 1)}.`);
        }
        return indices;
    }

    aiRequireEdit(operationName) {
        if (this.state.vizOnly) {
            throw new Error(`${operationName} requires Edit mode. Apply {mode: "edit"} first.`);
        }
    }

    async aiApplyOperation(operation) {
        if (typeof operation === 'string') operation = { name: operation };
        if (!operation || typeof operation !== 'object' || Array.isArray(operation)) {
            throw new Error('operation must be a string or object with a name.');
        }
        const name = String(operation.name || '').trim().toLowerCase();
        const applyConstraints = operation.applyConstraints ?? this.state.applyConstraints;
        const positions = () => this.backendPositionsPayload().map(position => [...position]);
        const setData = (data, clearSelection = false) => {
            this.setAtomsData(data, { clearSelection });
            return data;
        };

        if (name === 'wrap') {
            if (!this.hasUsableCell()) throw new Error('Wrap requires a defined unit cell.');
            if (this.state.vizOnly) {
                this.wrapVisibleAtomsIntoCell();
                return;
            }
            setData(await this.api.wrap(positions(), applyConstraints));
            return;
        }
        if (name === 'translate-all') {
            this.aiRequireEdit('translate-all');
            const vector = this.aiFiniteVector(operation.vector);
            const coordinateMode = operation.coordinateMode === 'fractional'
                ? 'fractional'
                : 'cartesian';
            setData(await this.api.applyTranslation(
                positions(), vector, coordinateMode, applyConstraints
            ));
            return;
        }
        if (name === 'set-supercell') {
            this.aiRequireEdit('set-supercell');
            const reps = this.aiFiniteVector(operation.reps, 'reps');
            if (!reps.every(value => Number.isInteger(value) && value >= 1 && value <= 64)) {
                throw new Error('Supercell repetitions must be integers from 1 to 64.');
            }
            setData(await this.api.applySupercell(positions(), reps, applyConstraints), true);
            this.finalizeMaterializedSupercellDisplay();
            return;
        }
        if (name === 'make-supercell') {
            this.aiRequireEdit('make-supercell');
            const matrix = operation.matrix;
            if (
                !Array.isArray(matrix)
                || matrix.length !== 3
                || !matrix.every(row => (
                    Array.isArray(row)
                    && row.length === 3
                    && row.every(value => Number.isInteger(Number(value)))
                ))
            ) {
                throw new Error('matrix must be a 3 x 3 integer array.');
            }
            setData(await this.api.applySupercellMatrix(
                positions(),
                matrix.map(row => row.map(Number)),
                applyConstraints
            ), true);
            this.finalizeMaterializedSupercellDisplay();
            return;
        }
        if (name === 'add-atom') {
            this.aiRequireEdit('add-atom');
            const label = String(operation.label || operation.element || '').trim();
            if (!label) throw new Error('add-atom requires label or element.');
            const position = this.aiFiniteVector(operation.position, 'position');
            setData(await this.api.addAtom(label, position, operation.element || null));
            return;
        }
        if (name === 'delete-selection') {
            this.aiRequireEdit('delete-selection');
            setData(await this.api.deleteAtoms(this.aiOperationIndices(operation)), true);
            return;
        }
        if (name === 'set-identity') {
            this.aiRequireEdit('set-identity');
            const label = String(operation.label || '').trim();
            if (!label) throw new Error('set-identity requires a non-empty label.');
            setData(await this.api.updateAtomIdentity(
                this.aiOperationIndices(operation),
                label,
                positions(),
                applyConstraints,
                operation.element || null
            ));
            return;
        }
        if (name === 'set-constraints') {
            this.aiRequireEdit('set-constraints');
            const options = {};
            if (operation.fixAtoms !== undefined) options.fix_atoms = Boolean(operation.fixAtoms);
            if (operation.clearDirectional) options.directional_kind = 'none';
            else if (operation.kind !== undefined) options.directional_kind = String(operation.kind);
            if (operation.vector !== undefined) options.vector = this.aiFiniteVector(operation.vector);
            setData(await this.api.updateConstraints(
                this.aiOperationIndices(operation),
                options,
                positions(),
                applyConstraints
            ));
            return;
        }
        if (name === 'move-selection') {
            this.aiRequireEdit('move-selection');
            const vector = this.aiFiniteVector(operation.vector);
            const next = positions();
            this.aiOperationIndices(operation).forEach(index => {
                next[index] = next[index].map((value, axis) => value + vector[axis]);
            });
            setData(await this.api.applyPositions(next, applyConstraints));
            return;
        }
        if (name === 'rotate-selection') {
            this.aiRequireEdit('rotate-selection');
            const axis = this.aiFiniteVector(operation.axis || [0, 0, 1], 'axis');
            const axisVector = new THREE.Vector3(...axis);
            if (axisVector.lengthSq() <= 1e-16) throw new Error('Rotation axis must be non-zero.');
            axisVector.normalize();
            const angle = Number(operation.angleDeg);
            if (!Number.isFinite(angle)) throw new Error('rotate-selection requires finite angleDeg.');
            const indices = this.aiOperationIndices(operation);
            const next = positions();
            let pivot;
            if (Array.isArray(operation.pivot)) {
                pivot = new THREE.Vector3(...this.aiFiniteVector(operation.pivot, 'pivot'));
            } else if (operation.pivot === 'active') {
                pivot = new THREE.Vector3(...next[indices[indices.length - 1]]);
            } else if (operation.pivot === 'origin') {
                pivot = new THREE.Vector3(0, 0, 0);
            } else if (operation.pivot === 'cell') {
                const cell = this.state.atoms?.cell || [];
                pivot = new THREE.Vector3();
                cell.forEach(row => pivot.add(new THREE.Vector3(...row).multiplyScalar(0.5)));
            } else {
                pivot = new THREE.Vector3();
                indices.forEach(index => pivot.add(new THREE.Vector3(...next[index])));
                pivot.multiplyScalar(1 / indices.length);
            }
            const quaternion = new THREE.Quaternion().setFromAxisAngle(
                axisVector,
                THREE.MathUtils.degToRad(angle)
            );
            indices.forEach(index => {
                const point = new THREE.Vector3(...next[index])
                    .sub(pivot)
                    .applyQuaternion(quaternion)
                    .add(pivot);
                next[index] = point.toArray();
            });
            setData(await this.api.applyPositions(next, applyConstraints));
            return;
        }
        if (name === 'undo') {
            await this.performUndo();
            return;
        }
        if (name === 'redo') {
            await this.performRedo();
            return;
        }
        if (name === 'reset-coordinates') {
            this.aiRequireEdit('reset-coordinates');
            setData(await this.api.resetCoordinates(), true);
            return;
        }
        if (name === 'start-relaxation') {
            this.aiRequireEdit('start-relaxation');
            if (!this.state.atoms?.metadata?.has_calculator) {
                throw new Error('Relaxation requires an attached ASE calculator.');
            }
            this.startRelaxTrajectory();
            const response = await this.api.relaxStart(
                positions(),
                Number(operation.fmax) || 0.05,
                Math.max(1, Math.round(Number(operation.steps) || 200)),
                applyConstraints,
                operation.calculator || this.currentCalculatorPayload()
            );
            this.state.isRelaxing = ['started', 'restarting'].includes(response.status);
            this.updateUI();
            return;
        }
        if (name === 'stop-relaxation') {
            await this.api.relaxStop();
            return;
        }
        if (name === 'refresh-displacements') {
            if (operation.display) {
                this.applyDesignSettings({
                    display: {
                        ...this.clonePlain(this.state.display),
                        ...this.clonePlain(operation.display)
                    }
                });
            }
            await this.refreshDisplacementAnalysis();
            return;
        }
        if (name === 'load-volumetric') {
            const path = String(operation.path || '').trim();
            if (!path) throw new Error('load-volumetric requires a path.');
            const requestedPrecision = operation.precision === 'float64'
                || operation.precision === 'fp64'
                ? 'float64'
                : operation.precision === 'float32'
                    || operation.precision === 'fp32'
                    ? 'float32'
                    : this.volumetricImportPrecision();
            const data = await this.api.appendStructurePath(
                path,
                String(operation.format || ''),
                ':',
                requestedPrecision
            );
            if (data.loaded_file?.source_kind !== 'volumetric') {
                throw new Error('The requested path did not contain supported volumetric data.');
            }
            this.state.display.volumetricPrecision = requestedPrecision;
            this.setAtomsData(data, {
                clearSelection: !this.hasLoadedAtoms(),
                preserveDisplay: true,
                preserveRdf: true
            });
            this.renderVolumetricControls();
            return;
        }
        if (name === 'show-volumetric') {
            const datasetId = String(operation.datasetId || '').trim();
            const dataset = this.volumetricDatasets().find(item => item.id === datasetId);
            if (!dataset) throw new Error(`Volumetric dataset '${datasetId}' was not found.`);
            const level = Number(operation.level);
            if (!Number.isFinite(level)) throw new Error('show-volumetric requires a finite level.');
            Object.assign(this.state.display, {
                showVolumetric: true,
                volumetricDatasetId: datasetId,
                volumetricLevel: level,
                volumetricSurfaceMode: operation.surfaceMode === 'signed' ? 'signed' : 'single',
                volumetricStepSize: [1, 2, 4].includes(Number(operation.stepSize))
                    ? Number(operation.stepSize)
                    : this.state.display.volumetricStepSize,
                volumetricOpacity: operation.opacity === undefined
                    ? this.state.display.volumetricOpacity
                    : Math.max(0.05, Math.min(1, Number(operation.opacity) || 0.72)),
                volumetricPositiveColor: this.validHexColor(operation.positiveColor)
                    ? operation.positiveColor
                    : this.state.display.volumetricPositiveColor,
                volumetricNegativeColor: this.validHexColor(operation.negativeColor)
                    ? operation.negativeColor
                    : this.state.display.volumetricNegativeColor
            });
            this.renderVolumetricControls();
            await this.updateVolumetricSurface();
            return;
        }
        if (name === 'combine-volumetric') {
            if (
                !Array.isArray(operation.datasetIds)
                || !Array.isArray(operation.coefficients)
                || operation.datasetIds.length < 2
                || operation.datasetIds.length !== operation.coefficients.length
            ) {
                throw new Error(
                    'combine-volumetric requires matching datasetIds and coefficients arrays.'
                );
            }
            const result = await this.api.createVolumetricDifference({
                dataset_ids: operation.datasetIds.map(value => String(value)),
                coefficients: operation.coefficients.map(Number),
                name: String(operation.name || 'Charge density difference'),
                precision: operation.precision === 'float64' || operation.precision === 'fp64'
                    ? 'float64'
                    : operation.precision === 'float32' || operation.precision === 'fp32'
                        ? 'float32'
                        : undefined
            });
            this.state.atoms.metadata.volumetric_datasets = result.volumetric_datasets || [];
            this.state.display.volumetricDatasetId = result.dataset.id;
            this.state.display.volumetricLevel = this.defaultVolumetricLevel(result.dataset);
            this.renderVolumetricControls();
            return;
        }
        if (name === 'remove-volumetric') {
            const datasetId = String(operation.datasetId || '').trim();
            if (!datasetId) throw new Error('remove-volumetric requires datasetId.');
            const result = await this.api.deleteVolumetricDataset(datasetId);
            this.state.atoms.metadata.volumetric_datasets = result.volumetric_datasets || [];
            if (this.state.display.volumetricDatasetId === datasetId) {
                this.state.display.volumetricDatasetId = '';
                this.state.display.showVolumetric = false;
                this.renderer.clearVolumetricSurfaces();
            }
            this.renderVolumetricControls();
            return;
        }
        if (name === 'calculate-rdf') {
            const pairMode = ['active', 'all', 'none'].includes(operation.pairMode)
                ? operation.pairMode
                : this.state.display.rdfPairMode;
            const cutoffInput = document.getElementById('rdf-cutoff');
            const binsInput = document.getElementById('rdf-bins');
            const modeInput = document.getElementById('rdf-pair-mode');
            if (cutoffInput) {
                cutoffInput.value = operation.cutoff === undefined || operation.cutoff === null
                    ? ''
                    : `${Number(operation.cutoff)}`;
            }
            if (binsInput && operation.bins !== undefined) binsInput.value = `${Number(operation.bins)}`;
            if (modeInput) modeInput.value = pairMode;
            const options = this.rdfOptions();
            if (Array.isArray(operation.activePairs)) {
                options.active_pairs = this.clonePlain(operation.activePairs);
            }
            const token = ++this.state.rdfRequestToken;
            const result = await this.api.fetchRdf(options);
            if (token !== this.state.rdfRequestToken) {
                throw new Error(
                    'The structure or trajectory frame changed while RDF was being '
                    + 'calculated. Inspect the current state and retry.'
                );
            }
            this.state.rdfResult = result;
            document.getElementById('btn-rdf-export').disabled = false;
            await this.plotRdf(result);
            const warning = (result.warnings || []).join(' ');
            this.setRdfStatus(
                warning ? 'warning' : 'ready',
                `${result.bins} bins · cutoff ${Number(result.cutoff).toFixed(3)} Å`,
                warning || `${Object.keys(result.partial || {}).length} pair curves plus total.`
            );
            return;
        }
        throw new Error(`Unsupported AI operation '${name}'.`);
    }

    async aiApply(command = {}) {
        if (!command || typeof command !== 'object' || Array.isArray(command)) {
            throw new Error('AI control command must be an object.');
        }
        if (command.expectedRevision !== undefined) {
            const expected = Number(command.expectedRevision);
            if (!Number.isInteger(expected) || expected < 0) {
                throw new Error('expectedRevision must be a non-negative integer.');
            }
            if (expected !== this.collaborationRevision) {
                throw new Error(
                    `Collaboration revision conflict: expected ${expected}, `
                    + `current ${this.collaborationRevision}. Call describe() `
                    + 'and review the human change before retrying.'
                );
            }
        }
        if (command.frame !== undefined) {
            const frame = Number(command.frame);
            if (!Number.isInteger(frame) || frame < 0 || frame >= this.loadedFrameCount()) {
                throw new Error(`frame must be an integer from 0 to ${Math.max(0, this.loadedFrameCount() - 1)}.`);
            }
            await this.loadFrame(frame);
        }
        if (command.mode !== undefined) {
            if (!['view', 'edit'].includes(command.mode)) {
                throw new Error("mode must be 'view' or 'edit'.");
            }
            const vizOnly = command.mode === 'view';
            if (vizOnly !== this.state.vizOnly) await this.switchRuntimeMode(vizOnly);
        }
        if (command.display !== undefined) {
            if (!command.display || typeof command.display !== 'object' || Array.isArray(command.display)) {
                throw new Error('display must be an object.');
            }
            this.applyDesignSettings({
                display: {
                    ...this.clonePlain(this.state.display),
                    ...this.clonePlain(command.display)
                }
            });
        }
        if (command.quality !== undefined) {
            if (!command.quality || typeof command.quality !== 'object' || Array.isArray(command.quality)) {
                throw new Error('quality must be an object.');
            }
            const sphereQuality = command.quality.sphereQuality || this.state.sphereQuality;
            if (!['auto', 'low', 'medium', 'high', 'ultra'].includes(sphereQuality)) {
                throw new Error("quality.sphereQuality must be auto, low, medium, high, or ultra.");
            }
            const antiAliasing = command.quality.antiAliasing ?? this.state.antiAliasing;
            this.applyDesignSettings({
                display: {
                    ...this.clonePlain(this.state.display),
                    antiAliasing: Boolean(antiAliasing),
                    sphereQuality
                },
                antiAliasing: Boolean(antiAliasing),
                sphereQuality
            });
        }
        if (command.applyConstraints !== undefined) {
            this.state.applyConstraints = Boolean(command.applyConstraints);
            const input = document.getElementById('chk-constraints');
            if (input) input.checked = this.state.applyConstraints;
            this.renderer.setApplyConstraints?.(this.state.applyConstraints);
        }
        if (command.camera !== undefined) {
            const cameraCommand = command.camera;
            if (!cameraCommand || typeof cameraCommand !== 'object' || Array.isArray(cameraCommand)) {
                throw new Error('camera must be an object.');
            }
            if (cameraCommand.projection) {
                const projection = cameraCommand.projection === 'perspective'
                    ? 'perspective'
                    : 'orthographic';
                if (projection !== this.state.display.projectionMode) {
                    this.scheduleVisualHistoryCommit('ai-projection');
                }
                this.state.display.projectionMode = projection;
                this.renderer.setProjectionMode(projection);
            }
            if (cameraCommand.axis) this.setAIAxisView(cameraCommand.axis);
            if (
                cameraCommand.position !== undefined
                || cameraCommand.target !== undefined
                || cameraCommand.up !== undefined
            ) {
                this.applyCameraSettings({
                    ...this.cameraSettingsSnapshot(),
                    ...this.clonePlain(cameraCommand)
                });
            }
            if (cameraCommand.fit !== undefined) {
                if (cameraCommand.fit !== 'structure') {
                    throw new Error("camera.fit currently supports only 'structure'.");
                }
                this.renderer.fitCameraToStructure();
                this.completeCameraViewChange('ai-fit');
            }
            if (cameraCommand.orbit) {
                this.rotateCameraView(
                    cameraCommand.orbit.direction,
                    cameraCommand.orbit.degrees ?? this.state.display.viewRotationStepDeg
                );
            }
            this.adoptCameraViewWithoutHistory();
        }
        if (command.selection !== undefined) {
            const selection = command.selection;
            if (!selection || typeof selection !== 'object' || Array.isArray(selection)) {
                throw new Error('selection must be an object.');
            }
            if (selection.clear !== false) this.clearAtomSelection();
            const atomCount = this.state.atoms?.positions?.length || 0;
            (selection.indices || []).forEach(index => {
                if (!Number.isInteger(index) || index < 0 || index >= atomCount) {
                    throw new Error(`selection index ${index} is outside 0..${Math.max(0, atomCount - 1)}.`);
                }
                this.addSelectionReference(index);
            });
            (selection.references || []).forEach(reference => {
                if (!this.addSelectionReference(reference)) {
                    throw new Error(`Selection reference could not be selected: ${JSON.stringify(reference)}.`);
                }
            });
            this.updateSelectionVisuals();
            this.updateUI();
        }
        if (command.operation !== undefined) {
            await this.aiApplyOperation(command.operation);
        }
        this.renderer.renderNow();
        return this.aiDescribe();
    }

    async aiRender(request = {}) {
        const width = Math.max(64, Math.min(8192, Math.round(Number(request.width) || 1920)));
        const height = Math.max(64, Math.min(8192, Math.round(Number(request.height) || 1080)));
        const format = this.normalizedImageFormat(request.format);
        const options = {
            ...this.defaultImageExportOptions(),
            ...this.clonePlain(request.options || {})
        };
        this.renderer.renderNow();
        const blob = await this.renderOptimizedImage(width, height, options, format);
        const dataUrl = await this.blobToDataUrl(blob);
        return {
            protocol: 'v_ase.ai.v1',
            mimeType: this.imageMimeType(format),
            format,
            filename: `v_ase-render.${format}`,
            bytes: blob.size,
            width,
            height,
            dataUrl,
            camera: this.cameraSettingsSnapshot(),
            options
        };
    }

    async aiExport(request = {}) {
        const format = String(request.format || '').trim().toLowerCase();
        if (format === 'image') {
            const imageFormat = this.normalizedImageFormat(request.imageFormat);
            return {
                ...(await this.aiRender({...request, format: imageFormat})),
                exportFormat: 'image'
            };
        }
        if (format === 'video') {
            const blob = await this.exportTrajectoryVideo(
                {
                    width: request.width || 1920,
                    height: request.height || 1080,
                    fps: request.fps || 12,
                    format: request.container === 'avi' ? 'avi' : 'mov',
                    interpolationMultiplier: request.interpolationMultiplier || 1,
                    interpolationMic: request.interpolationMic !== false,
                    ...this.clonePlain(request.options || {})
                },
                null,
                { returnBlob: true }
            );
            const container = request.container === 'avi' ? 'avi' : 'mov';
            return {
                protocol: 'v_ase.ai.v1',
                format: 'video',
                filename: `v_ase-trajectory.${container}`,
                mimeType: blob.type || (container === 'avi' ? 'video/x-msvideo' : 'video/quicktime'),
                bytes: blob.size,
                dataUrl: await this.blobToDataUrl(blob)
            };
        }

        const positions = this.backendPositionsPayload();
        const includeCell = request.includeCell ?? this.state.display.exportIncludeCell !== false;
        const display = this.clonePlain(this.state.display);
        const camera = this.currentCameraForExport();
        const bonds = this.renderer.bondPairs || [];
        const bridges = this.renderer.supercellBridgeBondRecords || [];
        let blob;
        let filename;
        let mimeType;
        if (format === 'poscar') {
            blob = await this.api.exportPoscar(positions, this.state.applyConstraints);
            filename = 'POSCAR';
            mimeType = 'application/octet-stream';
        } else if (format === 'pickle') {
            blob = await this.api.exportPickle(positions, this.state.applyConstraints);
            filename = 'atoms.pkl';
            mimeType = 'application/octet-stream';
        } else if (format === 'blender') {
            blob = await this.api.exportBlender(
                positions,
                this.state.applyConstraints,
                camera,
                display,
                bonds,
                this.currentLightingForExport(),
                includeCell
            );
            filename = 'v_ase_blender_scene.py';
            mimeType = 'text/x-python';
        } else if (format === '3dm') {
            blob = await this.api.export3dm(
                positions,
                this.state.applyConstraints,
                display,
                bonds,
                bridges,
                camera,
                includeCell
            );
            filename = 'v_ase_scene.3dm';
            mimeType = 'model/vnd.3dm';
        } else if (format === 'obj') {
            blob = await this.api.exportObj(
                positions,
                this.state.applyConstraints,
                display,
                bonds,
                bridges,
                camera,
                includeCell
            );
            filename = 'v_ase_obj_scene.zip';
            mimeType = 'application/zip';
        } else if (format === 'html') {
            const currentProfile = this.currentImageExportProfile();
            const profile = this.htmlExportProfile({
                ...currentProfile,
                width: request.width || currentProfile.width,
                height: request.height || currentProfile.height,
                options: {
                    ...currentProfile.options,
                    ...this.clonePlain(request.options || {}),
                    transparentBackground: false
                }
            });
            const rendered = await this.renderHtmlCompositionPreview(profile);
            blob = await this.api.exportHtml(
                positions,
                this.designSettingsSnapshot(),
                this.state.applyConstraints,
                [...this.state.selected],
                this.workspaceDocumentTitle(),
                request.embedProject === true,
                rendered.contract,
                rendered.url
            );
            filename = this.htmlViewFilename();
            mimeType = 'text/html';
        } else if (format === 'project') {
            blob = await this.api.saveProject(
                positions,
                this.designSettingsSnapshot(),
                this.state.applyConstraints
            );
            filename = this.projectFilename();
            mimeType = 'application/vnd.v-ase.project+zip';
        } else if (format === 'settings') {
            blob = await this.api.saveVisualSettings(this.designSettingsSnapshot());
            filename = 'v_ase-settings.json';
            mimeType = 'application/json';
        } else if (format === 'rdf-csv') {
            const options = this.rdfOptions();
            if (request.cutoff !== undefined) options.cutoff = request.cutoff;
            if (request.bins !== undefined) options.bins = request.bins;
            if (request.pairMode !== undefined) options.pair_mode = request.pairMode;
            if (request.activePairs !== undefined) {
                options.active_pairs = this.clonePlain(request.activePairs);
            }
            blob = await this.api.exportRdfCsv(options);
            filename = 'v_ase_rdf.csv';
            mimeType = 'text/csv';
        } else {
            throw new Error(
                "export format must be image, video, poscar, pickle, blender, "
                + "3dm, obj, html, project, settings, or rdf-csv."
            );
        }
        return {
            protocol: 'v_ase.ai.v1',
            format,
            filename,
            mimeType: blob.type || mimeType,
            bytes: blob.size,
            dataUrl: await this.blobToDataUrl(blob)
        };
    }

    blobToDataUrl(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(reader.error || new Error('Image encoding failed.'));
            reader.readAsDataURL(blob);
        });
    }

    async renderOptimizedImage(
        width,
        height,
        options = {},
        format = 'png',
        onProgress = null
    ) {
        onProgress?.({ phase: 'render', ratio: 0 });
        const source = await this.renderer.exportPNGBlob(width, height, options);
        onProgress?.({ phase: 'capture', ratio: 1, bytes: source.size });
        return await this.api.encodeImage(source, format, onProgress);
    }

    async aiApplyCollaboratively(command = {}) {
        this.flushVisualHistoryCommit();
        await this.flushCollaborationEvents();
        this.collaborationActorDepth += 1;
        let completed = false;
        try {
            await this.aiApply(command);
            completed = true;
            this.scheduleCollaborationEvent(this.collaborationCommandDetails(command));
        } finally {
            this.flushVisualHistoryCommit();
            await this.flushCollaborationEvents('agent');
            this.collaborationActorDepth = Math.max(0, this.collaborationActorDepth - 1);
        }
        return completed ? this.aiDescribe() : null;
    }

    createAIBridge() {
        const app = this;
        return Object.freeze({
            protocol: 'v_ase.ai.v1',
            ready: async () => {
                await app.ready;
                return {
                    protocol: 'v_ase.ai.v1',
                    ready: true,
                    sessionId: app.sessionId,
                    document: app.workspaceDocumentTitle(),
                    collaborationRevision: app.collaborationRevision
                };
            },
            describe: async options => {
                await app.ready;
                return app.aiDescribe(options);
            },
            capabilities: async () => {
                await app.ready;
                return await app.aiCapabilities();
            },
            apply: async command => {
                await app.ready;
                return await app.aiApplyCollaboratively(command);
            },
            render: async request => {
                await app.ready;
                return await app.aiRender(request);
            },
            export: async request => {
                await app.ready;
                return await app.aiExport(request);
            }
        });
    }

    async postAICommandResult(message, payload) {
        const target = new URL(String(message.result_url || ''), window.location.origin);
        if (target.origin !== window.location.origin) {
            throw new Error('AI command result URL must use the current v_ase origin.');
        }
        const response = await fetch(target.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try {
                const data = await response.json();
                detail = data.detail || detail;
            } catch {
                // Keep the HTTP status when the server returned no JSON detail.
            }
            throw new Error(`Could not return AI command result: ${detail}`);
        }
    }

    async handleAICommandMessage(message) {
        if (
            message?.type !== 'ai_command'
            || !message.command_id
            || !message.method
            || !message.result_url
        ) {
            return false;
        }
        let payload;
        try {
            await this.ready;
            const bridge = window.v_aseAI || this.createAIBridge();
            const method = String(message.method);
            if (typeof bridge[method] !== 'function') {
                throw new Error(`AI method '${method}' is not available on a document session.`);
            }
            const noArgumentMethods = new Set(['ready', 'capabilities']);
            const result = noArgumentMethods.has(method)
                ? await bridge[method]()
                : await bridge[method](message.params ?? {});
            payload = { ok: true, result };
        } catch (error) {
            payload = {
                ok: false,
                error: {
                    name: String(error?.name || 'Error'),
                    message: String(error?.message || error || 'AI command failed.')
                }
            };
        }
        try {
            await this.postAICommandResult(message, payload);
        } catch (error) {
            console.error(error);
        }
        return true;
    }

    designSettingsSnapshot({ includeAtomOverrides = true } = {}) {
        this.readTransformSettings();
        this.syncAtomicScaleFromCamera({ forceInput: true, syncPreview: false });
        const display = this.clonePlain(this.state.display);
        if (!includeAtomOverrides) display.atomMaterials = {};
        return {
            schema: 'v_ase.visual_settings.v3',
            display,
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
        setValue('cell-thickness', display.cellThickness ?? 0.04);
        setValue('cell-color', this.validHexColor(display.cellColor) ? display.cellColor : '#d6bd67');
        setValue('cell-material', ['unlit', 'standard', 'metal'].includes(display.cellMaterial)
            ? display.cellMaterial
            : 'unlit');
        setChecked('chk-axes', display.showAxes);
        setChecked('chk-grid', display.showGrid);
        setChecked('chk-overlays', display.showOverlays !== false);
        setChecked('chk-periodic-bonds', display.showPeriodicBonds);
        setChecked('export-include-cell', display.exportIncludeCell !== false);
        setValue('projection-mode', display.projectionMode || 'perspective');
        setValue('viewport-background', display.viewportBackground === 'dark' ? 'dark' : 'white');
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
        setValue('bond-thickness', display.bondThickness || 0.25);
        setValue('bond-color-mode', display.bondColorMode || 'split');
        setValue('bond-custom-color', display.bondCustomColor || '#c8ccd0');
        setValue('blender-export-mode', display.blenderExportMode || 'instanced');
        setValue('atom-radius-scale', display.atomRadiusScale || 0.6);
        setValue('move-increment', this.state.moveIncrement || 0);
        setValue('rotate-increment', this.state.rotateIncrementDeg || 0);
        this.syncDisplacementControls(display);
        this.setSupercellInputs(display.supercell || [1, 1, 1]);
        this.setTranslationCoordinateMode(
            display.translationMode === 'fractional' ? 'fractional' : 'cartesian',
            { convert: false, render: false }
        );
        this.applyPairwiseLabelColumnWidth(display.pairwiseLabelColumnWidth);
        this.writeBondPairs(display.manualBondPairs || []);
        this.syncViewControls(display);
        this.syncLightingControls(display);
        this.updateRadiusScaleLabel();
        this.updateBondAppearanceUI();
    }

    reconcileDesignDisplay(nextDisplay = {}) {
        const migratedDisplay = { ...this.clonePlain(nextDisplay) };
        if (
            !Object.prototype.hasOwnProperty.call(migratedDisplay, 'pairwiseBondCutoffs')
            && Object.prototype.hasOwnProperty.call(migratedDisplay, LEGACY_PAIRWISE_CUTOFF_KEY)
        ) {
            migratedDisplay.pairwiseBondCutoffs = migratedDisplay[LEGACY_PAIRWISE_CUTOFF_KEY];
        }
        if (
            !Object.prototype.hasOwnProperty.call(migratedDisplay, 'pairwiseBondRanges')
            && migratedDisplay.pairwiseBondCutoffs
        ) {
            migratedDisplay.pairwiseBondRanges = Object.fromEntries(
                Object.entries(migratedDisplay.pairwiseBondCutoffs).map(([key, rawMaximum]) => {
                    const maximum = Number(rawMaximum);
                    const max = Number.isFinite(maximum) ? Math.max(0, maximum) : 0;
                    return [key, { enabled: max > 0, min: 0, max }];
                })
            );
        }
        delete migratedDisplay[LEGACY_PAIRWISE_CUTOFF_KEY];
        Object.entries(LEGACY_LABEL_DISPLAY_KEYS).forEach(([legacyKey, currentKey]) => {
            if (
                !Object.prototype.hasOwnProperty.call(migratedDisplay, currentKey)
                && Object.prototype.hasOwnProperty.call(migratedDisplay, legacyKey)
            ) {
                migratedDisplay[currentKey] = migratedDisplay[legacyKey];
            }
            delete migratedDisplay[legacyKey];
        });
        if (migratedDisplay.bondMode === 'element') migratedDisplay.bondMode = 'pairwise';
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
        const labels = this.availableAtomLabels();
        const atomCount = this.state.atoms?.positions?.length || 0;
        const pickLabelMap = (source, fallback = {}) => {
            const result = {};
            labels.forEach(label => {
                if (source && Object.prototype.hasOwnProperty.call(source, label)) result[label] = source[label];
                else if (fallback && Object.prototype.hasOwnProperty.call(fallback, label)) result[label] = fallback[label];
            });
            return result;
        };

        const labelRadii = pickLabelMap(nextDisplay.labelRadii);
        labels.forEach(label => {
            const radius = Number(labelRadii[label]);
            if (!Number.isFinite(radius) || radius <= 0) {
                labelRadii[label] = Number(this.labelVisualRadius(label).toFixed(4));
            }
        });
        const labelColors = pickLabelMap(nextDisplay.labelColors);
        Object.keys(labelColors).forEach(label => {
            if (!this.validHexColor(labelColors[label])) delete labelColors[label];
        });
        const labelVisible = pickLabelMap(nextDisplay.labelVisible);
        labels.forEach(label => {
            labelVisible[label] = labelVisible[label] !== false;
        });
        const labelMaterials = pickLabelMap(nextDisplay.labelMaterials);
        labels.forEach(label => {
            labelMaterials[label] = this.normalizedAtomMaterialPreset(labelMaterials[label]);
        });
        const atomMaterials = {};
        Object.entries(nextDisplay.atomMaterials || {}).forEach(([rawIndex, preset]) => {
            const index = Number(rawIndex);
            if (
                Number.isInteger(index)
                && index >= 0
                && index < atomCount
                && ATOM_MATERIAL_PRESETS.includes(preset)
            ) {
                atomMaterials[index] = preset;
            }
        });

        const savedCutoffs = nextDisplay.pairwiseBondCutoffs || {};
        const savedRanges = nextDisplay.pairwiseBondRanges || {};
        const pairwiseBondCutoffs = {};
        const pairwiseBondRanges = {};
        for (let i = 0; i < labels.length; i++) {
            for (let j = i; j < labels.length; j++) {
                const key = this.labelPairKey(labels[i], labels[j]);
                const range = this.pairwiseBondRange(labels[i], labels[j], {
                    pairwiseBondRanges: savedRanges,
                    pairwiseBondCutoffs: savedCutoffs
                });
                pairwiseBondRanges[key] = range;
                pairwiseBondCutoffs[key] = range.enabled ? range.max : 0;
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
        let translation = this.normalizedTranslationVector(nextDisplay.translation);
        let translationMode = nextDisplay.translationMode === 'fractional'
            ? 'fractional'
            : 'cartesian';
        if (translationMode === 'fractional' && !usableCell) {
            translationMode = 'cartesian';
            translation = [0, 0, 0];
        }

        return {
            ...this.clonePlain(nextDisplay),
            cellThickness: finiteClamped(nextDisplay.cellThickness, 0.04, 0.01, 0.30),
            cellColor: this.validHexColor(nextDisplay.cellColor)
                ? nextDisplay.cellColor
                : '#d6bd67',
            cellMaterial: ['unlit', 'standard', 'metal'].includes(nextDisplay.cellMaterial)
                ? nextDisplay.cellMaterial
                : 'unlit',
            commensurateGuide: nextDisplay.commensurateGuide !== false,
            commensurateSnap: Boolean(nextDisplay.commensurateSnap),
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
            pairwiseBondCutoffs,
            pairwiseBondRanges,
            labelRadii,
            labelColors,
            labelVisible,
            labelMaterials,
            atomMaterials,
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
            viewportBackground: nextDisplay.viewportBackground === 'dark' ? 'dark' : 'white',
            atomDisplayMode: nextDisplay.atomDisplayMode === '2d' ? '2d' : '3d',
            viewRotationStepDeg: finiteClamped(
                nextDisplay.viewRotationStepDeg, 15, 0.1, 360
            ),
            videoFormat: ['mov', 'avi'].includes(nextDisplay.videoFormat)
                ? nextDisplay.videoFormat
                : 'mov',
            videoFps: finiteClamped(nextDisplay.videoFps, 12, 1, 60),
            videoInterpolationMultiplier: integerClamped(
                nextDisplay.videoInterpolationMultiplier, 1, 1, 64
            ),
            videoInterpolationMic: nextDisplay.videoInterpolationMic !== false,
            showDisplacements: Boolean(nextDisplay.showDisplacements),
            displacementReferenceMode: nextDisplay.displacementReferenceMode === 'frame'
                ? 'frame'
                : 'previous',
            displacementReferenceFrame: integerClamped(
                nextDisplay.displacementReferenceFrame, 0, 0, Math.max(0, this.loadedFrameCount() - 1)
            ),
            displacementMic: nextDisplay.displacementMic !== false,
            displacementStyle: nextDisplay.displacementStyle === '2d' ? '2d' : '3d',
            displacementScale: finiteClamped(nextDisplay.displacementScale, 1, 0.05, 10),
            displacementThickness: finiteClamped(nextDisplay.displacementThickness, 0.08, 0.01, 0.5),
            displacementColor: this.validHexColor(nextDisplay.displacementColor)
                ? nextDisplay.displacementColor
                : '#e58b2a',
            showVolumetric: Boolean(nextDisplay.showVolumetric),
            volumetricPrecision: nextDisplay.volumetricPrecision === 'float64'
                ? 'float64'
                : 'float32',
            volumetricDatasetId: String(nextDisplay.volumetricDatasetId || ''),
            volumetricLevel: Number.isFinite(Number(nextDisplay.volumetricLevel))
                ? Number(nextDisplay.volumetricLevel)
                : null,
            volumetricSurfaceMode: nextDisplay.volumetricSurfaceMode === 'signed'
                ? 'signed'
                : 'single',
            volumetricStepSize: [1, 2, 4].includes(Number(nextDisplay.volumetricStepSize))
                ? Number(nextDisplay.volumetricStepSize)
                : 1,
            volumetricOpacity: finiteClamped(nextDisplay.volumetricOpacity, 0.72, 0.05, 1),
            volumetricPositiveColor: this.validHexColor(nextDisplay.volumetricPositiveColor)
                ? nextDisplay.volumetricPositiveColor
                : '#2f8fdb',
            volumetricNegativeColor: this.validHexColor(nextDisplay.volumetricNegativeColor)
                ? nextDisplay.volumetricNegativeColor
                : '#e05b78',
            rdfCutoff: Number.isFinite(Number(nextDisplay.rdfCutoff)) && Number(nextDisplay.rdfCutoff) > 0
                ? Number(nextDisplay.rdfCutoff)
                : null,
            rdfBins: integerClamped(nextDisplay.rdfBins, 200, 8, 5000),
            rdfPairMode: ['active', 'all', 'none'].includes(nextDisplay.rdfPairMode)
                ? nextDisplay.rdfPairMode
                : 'active',
            pairwiseLabelColumnWidth: finiteClamped(
                nextDisplay.pairwiseLabelColumnWidth, 210, 120, 520
            ),
            translation,
            translationMode,
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
            pairwiseBondCutoffs: this.clonePlain(nextDisplay.pairwiseBondCutoffs),
            pairwiseBondRanges: this.clonePlain(nextDisplay.pairwiseBondRanges),
            labelRadii: this.clonePlain(nextDisplay.labelRadii),
            labelColors: this.clonePlain(nextDisplay.labelColors),
            labelVisible: this.clonePlain(nextDisplay.labelVisible),
            labelMaterials: this.clonePlain(nextDisplay.labelMaterials),
            atomMaterials: this.clonePlain(nextDisplay.atomMaterials),
            supercell: this.clonePlain(nextDisplay.supercell),
            translation: this.clonePlain(nextDisplay.translation)
        };
        if ('applyConstraints' in source) this.state.applyConstraints = Boolean(source.applyConstraints);
        if ('antiAliasing' in source) {
            this.state.antiAliasing = Boolean(source.antiAliasing);
            this.state.display.antiAliasing = this.state.antiAliasing;
        }
        if ('sphereQuality' in source) {
            this.state.sphereQuality = source.sphereQuality || 'auto';
            this.state.display.sphereQuality = this.state.sphereQuality;
        }
        if ('moveIncrement' in source) this.state.moveIncrement = Number(source.moveIncrement) || 0;
        if ('rotateIncrementDeg' in source) this.state.rotateIncrementDeg = Number(source.rotateIncrementDeg) || 0;
        this.state.imageExportProfile = source.imageExportProfile
            ? this.normalizedImageExportProfile(source.imageExportProfile)
            : null;
        if (this.state.imageExportProfile) {
            this.setImageExportProfile(this.state.imageExportProfile, { syncPreview: false });
        }
        this.syncDesignControls();
        this.renderPairwiseBondControls({ capture: false });
        this.renderAppearanceRows();
        this.syncRdfControls();
        this.syncDesignControls();
        if (source.camera) this.applyCameraSettings(source.camera, { syncScale: false });
        if (Number.isFinite(requestedAtomicScale) && requestedAtomicScale > 0) {
            this.renderer.setPixelsPerAngstrom(requestedAtomicScale);
        } else {
            this.syncAtomicScaleFromCamera({ forceInput: true });
        }
        if (render) {
            this.renderer.setDisplayOptions(this.state.display);
            this.renderVolumetricControls();
            if (this.state.display.showVolumetric) {
                this.updateVolumetricSurface().catch(error => {
                    this.setVolumeStatus('warning', 'Isosurface unavailable', error.message);
                });
            }
            this.updateSelectionVisuals();
            this.updateBondModeUI();
            this.updateUI();
            this.scheduleDisplacementAnalysisRefresh();
        }
        if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        this.scheduleVisualHistoryCommit('visual-settings');
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
                'Visual settings: bonds, radii, grid, axes, quality, cutoffs, and displayed replication return to startup values.',
                'Visual translation: the atom offset returns to (0, 0, 0).',
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
                'Cell: any physically materialized supercell returns to the original unit cell.',
                'Visual settings kept: displayed replication, visual translation, bonds, radii, grid, axes, and rendering quality.',
                'Selection: current selection is cleared.'
            ],
            confirmText: 'Yes, reset coordinates',
            danger: true
        });
    }

    formatRemainingTime(seconds) {
        const value = Number(seconds);
        if (!Number.isFinite(value) || value < 0) return 'Estimating time remaining...';
        const rounded = Math.max(0, Math.ceil(value));
        if (rounded < 60) return `About ${rounded} s remaining`;
        const minutes = Math.floor(rounded / 60);
        const remainder = rounded % 60;
        return `About ${minutes} min ${remainder.toString().padStart(2, '0')} s remaining`;
    }

    estimatedRemainingFromProgress(startedAt, progress) {
        const elapsed = (performance.now() - Number(startedAt)) / 1000;
        const completed = Math.max(0, Math.min(100, Number(progress) || 0));
        if (!Number.isFinite(elapsed) || elapsed < 0.4 || completed < 8 || completed >= 100) {
            return null;
        }
        return elapsed * (100 - completed) / completed;
    }

    setBusyProgress(progress, {
        message = null,
        etaSeconds = null,
        complete = false
    } = {}) {
        const bar = document.getElementById('busy-progress');
        const fill = bar?.querySelector('span');
        const meta = document.getElementById('busy-progress-meta');
        const percent = document.getElementById('busy-progress-percent');
        const eta = document.getElementById('busy-progress-eta');
        const text = document.getElementById('busy-message');
        if (!bar || !fill || !meta || !percent || !eta) return;
        const requested = Math.max(0, Math.min(100, Number(progress) || 0));
        const capped = complete ? requested : Math.min(99, requested);
        const previous = Number(document.body.dataset.busyProgress || 0);
        const next = Math.max(previous, capped);
        document.body.dataset.busyProgress = `${next}`;
        bar.dataset.mode = 'determinate';
        bar.setAttribute('aria-valuemin', '0');
        bar.setAttribute('aria-valuemax', '100');
        bar.setAttribute('aria-valuenow', `${Math.round(next)}`);
        fill.style.width = `${next}%`;
        percent.textContent = `${Math.floor(next)}%`;
        eta.textContent = complete && next >= 100
            ? 'Complete'
            : this.formatRemainingTime(etaSeconds);
        meta.classList.remove('hidden');
        if (message !== null && text) text.textContent = message;
    }

    setBusy(message = 'Working...', {
        title = 'Working',
        progress = null,
        etaSeconds = null
    } = {}) {
        const overlay = document.getElementById('busy-overlay');
        const text = document.getElementById('busy-message');
        const heading = document.getElementById('busy-title');
        const bar = document.getElementById('busy-progress');
        const fill = bar?.querySelector('span');
        const meta = document.getElementById('busy-progress-meta');
        if (heading) heading.textContent = title;
        if (text) text.innerText = message;
        delete document.body.dataset.busyProgress;
        if (progress === null) {
            if (bar) {
                bar.dataset.mode = 'indeterminate';
                bar.removeAttribute('aria-valuenow');
            }
            if (fill) fill.style.width = '';
            meta?.classList.add('hidden');
        }
        overlay?.classList.remove('hidden');
        document.body.dataset.busy = 'true';
        if (progress !== null) {
            this.setBusyProgress(progress, { message, etaSeconds });
        }
    }

    clearBusy() {
        document.getElementById('busy-overlay')?.classList.add('hidden');
        delete document.body.dataset.busy;
        delete document.body.dataset.busyProgress;
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
            this.finalizeMaterializedSupercellDisplay();
            this.toast(`Set ${reps.join(' x ')} supercell as editable cell for all frames.`, 'success');
        } catch (err) {
            this.toast(`Set supercell failed: ${err.message}`, 'error');
        }
    }

    finalizeMaterializedSupercellDisplay() {
        ['super-x', 'super-y', 'super-z'].forEach(id => {
            const input = document.getElementById(id);
            if (input) input.value = '1';
        });
        this.state.display.supercell = [1, 1, 1];
        this.renderer.setDisplayOptions(this.state.display);
        // The preview reset belongs to the same physical supercell operation.
        // Starting a new visual-history entry here would make Undo require two steps.
        this.resetVisualHistoryBaseline();
    }

    normalizedTranslationVector(vector = [0, 0, 0]) {
        if (!Array.isArray(vector) || vector.length < 3) return [0, 0, 0];
        return vector.slice(0, 3).map(value => {
            const parsed = Number(value);
            return Number.isFinite(parsed) ? parsed : 0;
        });
    }

    translationVectorToCartesian(vector, mode = this.state.translationCoordinateMode) {
        const values = this.normalizedTranslationVector(vector);
        if (mode !== 'fractional') return values;
        if (!this.hasUsableCell()) {
            if (values.every(value => Math.abs(value) < 1e-12)) return [0, 0, 0];
            throw new Error('Fractional translation requires a defined unit cell.');
        }
        return this.renderer.fracToCart(new THREE.Vector3(...values)).toArray();
    }

    translationVectorFromCartesian(vector, mode = this.state.translationCoordinateMode) {
        const values = this.normalizedTranslationVector(vector);
        if (mode !== 'fractional') return values;
        if (!this.hasUsableCell()) {
            if (values.every(value => Math.abs(value) < 1e-12)) return [0, 0, 0];
            throw new Error('Fractional translation requires a defined unit cell.');
        }
        return this.renderer.cartToFrac(new THREE.Vector3(...values)).toArray();
    }

    writeTranslationControls(vector = this.state.display.translation) {
        const values = this.normalizedTranslationVector(vector);
        ['translate-x', 'translate-y', 'translate-z'].forEach((id, index) => {
            const input = document.getElementById(id);
            if (!input) return;
            const rounded = Math.abs(values[index]) < 5e-13
                ? 0
                : Number(values[index].toFixed(8));
            input.value = String(rounded);
        });
    }

    setTranslationCoordinateMode(mode, { convert = true, render = true } = {}) {
        const next = mode === 'fractional' ? 'fractional' : 'cartesian';
        if (convert && next === 'fractional' && !this.hasUsableCell()) {
            this.toast('Fractional translation requires a defined unit cell.', 'warning');
            return false;
        }
        const current = this.state.display.translationMode === 'fractional'
            ? 'fractional'
            : 'cartesian';
        let vector = this.normalizedTranslationVector(this.state.display.translation);
        if (convert && current !== next) {
            const cartesian = this.translationVectorToCartesian(vector, current);
            vector = this.translationVectorFromCartesian(cartesian, next);
            this.state.display.translation = vector;
        }
        this.state.display.translationMode = next;
        this.state.translationCoordinateMode = next;
        document.querySelectorAll('[data-translation-mode]').forEach(button => {
            button.setAttribute(
                'aria-pressed',
                button.dataset.translationMode === next ? 'true' : 'false'
            );
        });
        const step = next === 'fractional' ? '0.05' : '0.1';
        ['translate-x', 'translate-y', 'translate-z'].forEach(id => {
            document.getElementById(id)?.setAttribute('step', step);
        });
        this.writeTranslationControls(vector);
        if (render) {
            this.renderer.setDisplayOptions({
                translation: this.state.display.translation,
                translationMode: next
            });
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        }
        return true;
    }

    translationVectorFromControls() {
        const vector = ['translate-x', 'translate-y', 'translate-z'].map(id => {
            const value = Number(document.getElementById(id)?.value);
            if (!Number.isFinite(value)) throw new Error('Translation components must be finite numbers.');
            return value;
        });
        return vector;
    }

    async applyAtomTranslation() {
        try {
            const vector = this.translationVectorFromControls();
            const mode = this.state.translationCoordinateMode === 'fractional'
                ? 'fractional'
                : 'cartesian';
            this.translationVectorToCartesian(vector, mode);
            this.state.display.translation = [...vector];
            this.state.display.translationMode = mode;
            this.renderer.setDisplayOptions({
                translation: this.state.display.translation,
                translationMode: mode
            });
            this.writeTranslationControls(vector);
            this.updateSelectionMeasurementOverlay();
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
            const unit = mode === 'fractional' ? 'fractional' : 'Å';
            const reset = vector.every(value => Math.abs(value) < 1e-12);
            this.toast(
                reset
                    ? 'Visual atom translation reset to (0, 0, 0).'
                    : `Visual atom translation set to (${vector.join(', ')}) ${unit}; ASE coordinates and cell unchanged.`,
                'success'
            );
        } catch (err) {
            this.toast(`Translation failed: ${err.message}`, 'error');
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
                const p = this.currentAtomPosition(i);
                if (!p) return;
                c.add(new THREE.Vector3(...p));
                count++;
            });
            if (count) return c.divideScalar(count);
        }
        const c = new THREE.Vector3();
        let count = 0;
        this.renderer.forEachAtomProxy(mesh => {
            if (mesh.visible === false) return;
            c.add(mesh.position);
            count++;
        });
        return c.divideScalar(Math.max(1, count));
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

    activeRotationPivotIndex(editableSelection) {
        const editable = new Set(editableSelection);
        for (let orderIndex = this.state.selectionOrder.length - 1; orderIndex >= 0; orderIndex--) {
            const key = this.state.selectionOrder[orderIndex];
            if (!key?.startsWith?.('atom:')) continue;
            const index = Number(key.slice('atom:'.length));
            if (Number.isInteger(index) && editable.has(index)) return index;
        }
        for (let index = editableSelection.length - 1; index >= 0; index--) {
            if (Number.isInteger(editableSelection[index])) return editableSelection[index];
        }
        return null;
    }

    rotationPivotPosition(editableSelection) {
        const mode = this.state.display.rotatePivot || 'selection';
        if (mode === 'origin') return new THREE.Vector3(0, 0, 0);
        if (mode === 'active') {
            const index = this.activeRotationPivotIndex(editableSelection);
            const position = index === null ? null : this.currentAtomPosition(index);
            if (position) return new THREE.Vector3(...position);
            this.toast('Active-atom pivot requires a selected atom. Using selection COM.', 'warning');
        }
        if (mode === 'cell') {
            if (!this.hasUsableCell()) {
                this.toast('Unit-cell center pivot requires a defined unit cell. Using selection COM.', 'warning');
            } else {
                return this.cellCenter();
            }
        }
        const pivot = new THREE.Vector3();
        editableSelection.forEach(idx => {
            const p = this.currentAtomPosition(idx);
            if (!p) return;
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

    activeRotationAxisVector() {
        const locked = this.lockedRotationAxisVector();
        if (locked) return locked;
        const viewAxis = new THREE.Vector3();
        this.renderer.camera.getWorldDirection(viewAxis);
        return viewAxis.lengthSq() > 1e-12
            ? viewAxis.normalize()
            : new THREE.Vector3(0, 0, -1);
    }

    rotationPlaneDirection(vector, axis) {
        const direction = vector?.isVector3
            ? vector.clone()
            : new THREE.Vector3(...(vector || []));
        direction.addScaledVector(axis, -direction.dot(axis));
        return direction.lengthSq() > 1e-12 ? direction.normalize() : null;
    }

    rotationCellReference(axis) {
        const cell = this.state.atoms?.cell || [];
        for (const vector of cell) {
            const projected = this.rotationPlaneDirection(vector, axis);
            if (projected) return projected;
        }
        return null;
    }

    selectionPrincipalRotationReference(editableSelection, axis) {
        const cellReference = this.rotationCellReference(axis);
        const basisU = cellReference || (() => {
            const candidates = [
                new THREE.Vector3(1, 0, 0),
                new THREE.Vector3(0, 1, 0),
                new THREE.Vector3(0, 0, 1)
            ].sort((left, right) => Math.abs(left.dot(axis)) - Math.abs(right.dot(axis)));
            return this.rotationPlaneDirection(candidates[0], axis);
        })();
        if (!basisU) return null;
        const basisV = axis.clone().cross(basisU).normalize();
        const points = [];
        let maxLength = 0;
        editableSelection.forEach(index => {
            const position = this.state.originalPositions[index];
            if (!position) return;
            const offset = new THREE.Vector3(...position).sub(this.transform.pivot);
            offset.addScaledVector(axis, -offset.dot(axis));
            maxLength = Math.max(maxLength, offset.length());
            points.push([
                offset.dot(basisU),
                offset.dot(basisV)
            ]);
        });
        if (points.length < 2) return { reference: null, maxLength, anisotropy: 0 };

        const mean = points.reduce(
            (sum, point) => [sum[0] + point[0], sum[1] + point[1]],
            [0, 0]
        ).map(value => value / points.length);
        let xx = 0;
        let xy = 0;
        let yy = 0;
        points.forEach(point => {
            const x = point[0] - mean[0];
            const y = point[1] - mean[1];
            xx += x * x;
            xy += x * y;
            yy += y * y;
        });
        const trace = xx + yy;
        if (trace <= 1e-12) return { reference: null, maxLength, anisotropy: 0 };
        const separation = Math.hypot(xx - yy, 2 * xy);
        const angle = 0.5 * Math.atan2(2 * xy, xx - yy);
        const reference = basisU.clone()
            .multiplyScalar(Math.cos(angle))
            .addScaledVector(basisV, Math.sin(angle))
            .normalize();
        const preferred = cellReference || basisU;
        if (reference.dot(preferred) < 0) reference.multiplyScalar(-1);
        return {
            reference,
            maxLength,
            anisotropy: separation / trace
        };
    }

    rotationReferenceForSelection(editableSelection, axis) {
        const principal = this.selectionPrincipalRotationReference(editableSelection, axis);
        const cellReference = this.rotationCellReference(axis);
        const maxLength = principal?.maxLength || 0;
        let reference = (
            principal?.reference && principal.anisotropy >= 0.08
                ? principal.reference
                : cellReference || principal?.reference
        );
        if (!reference || maxLength < 1e-5) {
            this.renderer.camera.updateMatrixWorld();
            reference = new THREE.Vector3().setFromMatrixColumn(
                this.renderer.camera.matrixWorld,
                0
            );
            reference = this.rotationPlaneDirection(reference, axis);
            if (!reference) {
                reference = Math.abs(axis.z) < 0.9
                    ? new THREE.Vector3(0, 0, 1).cross(axis)
                    : new THREE.Vector3(1, 0, 0);
            }
            reference.normalize();
        }
        return {
            reference,
            radius: Math.max(3.2, maxLength * 1.45)
        };
    }

    configureRotationReference(editableSelection = [...this.state.selected]) {
        if (this.transform.mode !== 'ROTATE') return;
        const axis = this.activeRotationAxisVector();
        const { reference, radius } = this.rotationReferenceForSelection(editableSelection, axis);
        this.state.rotationGuideAxis = axis.clone();
        this.state.rotationReferenceDirection = reference.clone();
        this.state.rotationGuideRadius = radius;
        this.transform.setRotationGuide({
            axis,
            reference,
            radius,
            angle: 0
        }, this.renderer.camera);
    }

    updateRotationReferenceGuide(angle) {
        if (this.transform.mode !== 'ROTATE') return;
        const axis = this.activeRotationAxisVector();
        const editableSelection = [...this.state.selected].filter(idx => this.isEditableIndex(idx));
        const axisChanged = !this.state.rotationGuideAxis
            || this.state.rotationGuideAxis.angleTo(axis) > 1e-5;
        if (axisChanged || !this.state.rotationReferenceDirection) {
            this.configureRotationReference(editableSelection);
        }
        const guideAngle = this.transform.axis ? angle : -angle;
        this.transform.setRotationGuide({
            axis,
            reference: this.state.rotationReferenceDirection,
            radius: this.state.rotationGuideRadius,
            angle: guideAngle
        }, this.renderer.camera);
    }

    commensurateReferenceForSelection(editableSelection, axis) {
        const { reference, radius } = this.rotationReferenceForSelection(editableSelection, axis);
        this.state.commensurateGuideRadius = Math.max(3.2, radius);
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
        this.configureRotationReference(editableSelection);
        this.state.commensurateReferenceDirection = this.state.rotationReferenceDirection
            ? this.state.rotationReferenceDirection.clone()
            : this.commensurateReferenceForSelection(editableSelection, axis);
        this.state.commensurateGuideRadius = Math.max(3.2, this.state.rotationGuideRadius * 0.82);
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
        const primaryCandidate = nearest && !nearest.identity ? nearest : ranked[0];
        return chosen.slice(0, 7).map(candidate => {
            const isActive = Boolean(active) && Math.abs(candidate.targetAngleDeg - active.targetAngleDeg) < 1e-5;
            const isPrimary = Boolean(primaryCandidate)
                && Math.abs(candidate.targetAngleDeg - primaryCandidate.targetAngleDeg) < 1e-5;
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
            let msg;
            try {
                msg = JSON.parse(event.data);
            } catch {
                return;
            }
            if (msg.type === 'ai_command') {
                void this.handleAICommandMessage(msg);
                return;
            }
            if (
                msg.type === 'video_export_progress'
                && msg.export_id
                && msg.export_id === this.state.videoExportId
            ) {
                const ratio = Math.max(0, Math.min(1, Number(msg.progress) || 0));
                const frameDetail = Number(msg.frame_count) > 0
                    ? ` · ${Math.min(Number(msg.frame) || 0, Number(msg.frame_count))}/${Number(msg.frame_count)}`
                    : '';
                this.setBusyProgress(78 + ratio * 20, {
                    message: `Encoding video${frameDetail}...`,
                    etaSeconds: msg.eta_seconds
                });
            }
            if (msg.type === 'relax_step') {
                this.state.atoms.positions = msg.positions;
                this.state.originalPositions = msg.positions.map(p => [...p]);
                this.appendRelaxFrame(msg.positions);
                if (this.workspaceActive) {
                    this.renderer.updatePositions(msg.positions);
                } else {
                    this.workspaceNeedsRefresh = true;
                }
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
                    if (this.workspaceActive) {
                        this.renderer.updatePositions(msg.positions);
                    } else {
                        this.workspaceNeedsRefresh = true;
                    }
                } else if (this.state.atoms?.positions?.length) {
                    this.appendRelaxFrame(this.state.atoms.positions, { force: this.relaxFrameCount() <= 1 });
                }
                this.state.relaxTrajectory.finished = true;
                this.scheduleCollaborationEvent({
                    source: 'system',
                    categories: ['structure', 'trajectory'],
                    changedPaths: ['structure.positions', 'relaxation.status'],
                    summary: `Structure relaxation ${msg.status}.`
                });
                this.toast(`Relax ${msg.status}.`, msg.status === 'error' ? 'error' : 'success');
                this.updateUI();
                if (!this.workspaceActive) {
                    this.workspaceNeedsRefresh = true;
                    return;
                }
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
        if (lower.endsWith('.html') || lower.endsWith('.htm')) {
            return [{ description: 'Self-contained HTML view', accept: { 'text/html': ['.html', '.htm'] } }];
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
        if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
            return [{ description: 'JPEG image', accept: { 'image/jpeg': ['.jpg', '.jpeg'] } }];
        }
        if (lower.endsWith('.pdf')) {
            return [{ description: 'PDF image', accept: { 'application/pdf': ['.pdf'] } }];
        }
        if (lower.endsWith('.webp')) {
            return [{ description: 'Lossless WebP image', accept: { 'image/webp': ['.webp'] } }];
        }
        return [{ description: 'v_ase export', accept: { [mimeType]: ['.vasp', '.poscar', '.txt'] } }];
    }

    async chooseSaveDestination(filename, mimeType = 'application/octet-stream') {
        const canUseSavePicker = window.showSaveFilePicker && window.isSecureContext && !navigator.webdriver;
        if (canUseSavePicker) {
            try {
                const handle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: this.filePickerTypes(filename, mimeType)
                });
                return { handle, browserDownload: false };
            } catch (err) {
                if (err?.name === 'AbortError') return null;
                console.warn('showSaveFilePicker failed; falling back to browser download.', err);
            }
        }
        return { handle: null, browserDownload: true };
    }

    async savePreparedBlob(
        blob,
        filename,
        mimeType = 'application/octet-stream',
        destination = null
    ) {
        const selected = destination || await this.chooseSaveDestination(filename, mimeType);
        if (!selected) return false;
        if (selected.handle) {
            const writable = await selected.handle.createWritable();
            await writable.write(blob);
            await writable.close();
            return true;
        }
        this.downloadBlob(blob, filename, mimeType);
        return true;
    }

    async saveBlobFromAction(action, filename, mimeType = 'application/octet-stream', busyMessage = 'Preparing export...') {
        const destination = await this.chooseSaveDestination(filename, mimeType);
        if (!destination) return false;
        const blob = await this.withBusy(busyMessage, action);
        return await this.savePreparedBlob(blob, filename, mimeType, destination);
    }

    closeModal() {
        document.getElementById('modal-container')?.classList.add('hidden');
    }

    showModal(contentHtml, actionsHtml = '<button id="modal-close" class="btn">Close</button>') {
        const container = document.getElementById('modal-container');
        const content = document.getElementById('modal-content');
        const actions = document.querySelector('#modal-container .modal-actions');
        if (!container || !content || !actions) return;
        container.querySelector('.modal')?.classList.remove(
            'export-image-modal',
            'html-export-modal'
        );
        content.innerHTML = contentHtml;
        actions.innerHTML = actionsHtml;
        container.classList.remove('hidden');
        actions.querySelector('#modal-close')?.addEventListener('click', () => this.closeModal());
    }

    htmlExportProfile(profile = null) {
        const source = profile || this.currentImageExportProfile();
        const normalized = this.normalizedImageExportProfile({
            ...source,
            options: {
                ...source.options,
                transparentBackground: false,
                backgroundColor: source.options?.backgroundColor || '#ffffff'
            }
        });
        return {...normalized, kind: 'html'};
    }

    htmlExportContract(profile = null) {
        const normalized = this.htmlExportProfile(profile);
        return {
            ...normalized,
            composition: this.renderer.exportCompositionSnapshot(
                normalized.width,
                normalized.height,
                normalized.options
            )
        };
    }

    async renderHtmlCompositionPreview(profile = null, { poster = false } = {}) {
        const contract = this.htmlExportContract(profile);
        const sourceLongEdge = Math.max(contract.width, contract.height);
        const targetLongEdge = poster
            ? Math.min(2560, Math.max(1920, sourceLongEdge))
            : Math.min(960, sourceLongEdge);
        const scale = targetLongEdge / sourceLongEdge;
        const width = Math.max(1, Math.round(contract.width * scale));
        const height = Math.max(1, Math.round(contract.height * scale));
        const options = {...contract.options};
        if (options.scaleMode === 'physical') {
            options.pixelsPerAngstrom = Math.max(
                0.1,
                Number(options.pixelsPerAngstrom || 100) * scale
            );
        }
        const blob = await this.renderer.exportPNGBlob(width, height, options);
        return {
            url: await this.blobToDataUrl(blob),
            aspect: contract.width / Math.max(1, contract.height),
            width,
            height,
            contract
        };
    }

    showHtmlExportModal({ projectSave = false } = {}) {
        const title = projectSave ? 'Save HTML Project' : 'Export HTML View';
        const intro = projectSave
            ? 'Save an interactive browser document and, by default, embed the complete editable v_ase project.'
            : 'Export a lightweight, offline 3D view. It uses the same composition as Preview Area and remains orbitable after opening.';
        const initialProfile = this.htmlExportProfile();
        this.showModal(`
            <h2>${title}</h2>
            <p class="modal-intro">${intro}</p>
            <div class="html-export-layout">
                <figure class="html-view-preview loading">
                    <img id="html-export-preview" alt="Exact exported HTML structure frame">
                    <figcaption id="html-export-preview-caption">Shared export frame</figcaption>
                </figure>
                <div class="html-export-controls">
                    <div class="export-section-title">Framing</div>
                    <div class="html-composition-readout">
                        <span>Preview Area crop</span>
                        <strong>${initialProfile.width} x ${initialProfile.height}</strong>
                    </div>
                    <p class="html-composition-note">
                        HTML uses the exact Preview Area camera and aspect ratio. Its live
                        WebGL resolution adapts to the browser display; v_ase embeds an
                        optimized high-resolution poster automatically.
                    </p>
                    <div class="export-section-title">Scene overlays</div>
                    <label class="check-row" for="html-include-grid">
                        <span>Include grid</span>
                        <input id="html-include-grid" type="checkbox"
                               ${initialProfile.options.includeGrid ? 'checked' : ''}>
                    </label>
                    <label class="check-row" for="html-include-axes">
                        <span>Include axes</span>
                        <input id="html-include-axes" type="checkbox"
                               ${initialProfile.options.includeAxes ? 'checked' : ''}>
                    </label>
                    <label class="check-row" for="html-include-cell">
                        <span>Include unit cell</span>
                        <input id="html-include-cell" type="checkbox"
                               ${initialProfile.options.includeCell ? 'checked' : ''}>
                    </label>
                </div>
            </div>
            <label class="html-project-option" for="html-embed-project">
                <input id="html-embed-project" type="checkbox"
                       ${projectSave ? 'checked' : ''}>
                <span>
                    <strong>Embed editable .vase project</strong>
                    <small id="html-embed-project-detail"></small>
                </span>
            </label>
            <div class="html-export-summary" id="html-export-summary">
                <strong></strong>
                <span></span>
            </div>
        `, `
            <button id="html-export-cancel" class="btn">Cancel</button>
            <button id="html-export-confirm" class="btn primary">Save HTML</button>
        `);
        document.querySelector('#modal-container .modal')?.classList.add('html-export-modal');
        const previewImage = document.getElementById('html-export-preview');
        const previewFigure = previewImage?.closest('.html-view-preview');
        const previewCaption = document.getElementById('html-export-preview-caption');
        const embed = document.getElementById('html-embed-project');
        const detail = document.getElementById('html-embed-project-detail');
        const summary = document.getElementById('html-export-summary');
        let previewGeneration = 0;
        let previewTimer = null;

        const readProfile = () => {
            const current = this.currentImageExportProfile();
            return this.htmlExportProfile({
                ...current,
                options: {
                    ...current.options,
                    includeGrid: Boolean(document.getElementById('html-include-grid')?.checked),
                    includeAxes: Boolean(document.getElementById('html-include-axes')?.checked),
                    includeCell: Boolean(document.getElementById('html-include-cell')?.checked),
                    transparentBackground: false
                }
            });
        };

        const syncProjectOption = () => {
            const enabled = embed?.checked === true;
            if (detail) {
                detail.textContent = enabled
                    ? 'Lossless reopening in v_ase. The file is larger because it also contains the complete project archive.'
                    : 'Smaller view-only HTML with no editable project archive.';
            }
            if (summary) {
                summary.innerHTML = enabled
                    ? '<strong>Interactive view + complete project</strong><span>Opens in a browser and restores all editable state when loaded in v_ase.</span>'
                    : '<strong>Interactive view only</strong><span>Opens offline in a browser or notebook without recoverable .vase project data.</span>';
            }
        };

        const refreshPreview = async () => {
            const generation = ++previewGeneration;
            const profile = this.setImageExportProfile(readProfile());
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
            previewFigure?.classList.add('loading');
            previewFigure?.classList.remove('unavailable');
            if (previewCaption) {
                previewCaption.textContent = `Shared export frame  ${profile.width} x ${profile.height}`;
            }
            try {
                const rendered = await this.renderHtmlCompositionPreview(profile);
                if (generation !== previewGeneration || !document.getElementById('html-export-preview')) return;
                previewImage.src = rendered.url;
                previewImage.style.aspectRatio = `${rendered.aspect}`;
                previewFigure?.classList.remove('loading');
            } catch (error) {
                if (generation !== previewGeneration) return;
                console.warn('Could not prepare the exact HTML composition preview.', error);
                previewFigure?.classList.remove('loading');
                previewFigure?.classList.add('unavailable');
            }
        };

        const schedulePreview = () => {
            if (previewTimer !== null) window.clearTimeout(previewTimer);
            previewTimer = window.setTimeout(refreshPreview, 120);
        };
        embed?.addEventListener('change', syncProjectOption);
        ['html-include-grid', 'html-include-axes', 'html-include-cell'].forEach(id => {
            document.getElementById(id)?.addEventListener('change', schedulePreview);
        });
        syncProjectOption();
        refreshPreview();

        document.getElementById('html-export-cancel')?.addEventListener(
            'click',
            () => {
                previewGeneration += 1;
                if (previewTimer !== null) window.clearTimeout(previewTimer);
                this.closeModal();
            },
            { once: true }
        );
        document.getElementById('html-export-confirm')?.addEventListener('click', async () => {
            const embedProject = embed?.checked === true;
            const profile = this.setImageExportProfile(readProfile());
            previewGeneration += 1;
            if (previewTimer !== null) window.clearTimeout(previewTimer);
            this.closeModal();
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    async () => {
                        const rendered = await this.renderHtmlCompositionPreview(
                            profile,
                            { poster: true }
                        );
                        return await this.api.exportHtml(
                            this.backendPositionsPayload(),
                            this.designSettingsSnapshot(),
                            this.state.applyConstraints,
                            [...this.state.selected],
                            this.workspaceDocumentTitle(),
                            embedProject,
                            rendered.contract,
                            rendered.url
                        );
                    },
                    projectSave ? this.htmlProjectFilename() : this.htmlViewFilename(),
                    'text/html',
                    embedProject
                        ? 'Building HTML view with project recovery...'
                        : 'Building lightweight HTML view...'
                );
                if (saved) {
                    this.toast(
                        embedProject
                            ? 'HTML saved with its complete embedded .vase project.'
                            : 'Interactive view-only HTML saved without project data.',
                        'success'
                    );
                }
            } catch (err) {
                this.toast(`HTML export failed: ${err.message}`, 'error');
            }
        }, { once: true });
    }

    formatFileSize(bytes) {
        const value = Number(bytes) || 0;
        if (value < 1024) return `${value} B`;
        if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
        if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
        return `${(value / 1024 ** 3).toFixed(2)} GB`;
    }

    chooseSystemStructureFile() {
        const input = document.getElementById('structure-file');
        if (!input) return;
        input.value = '';
        input.click();
    }

    chooseStructureFile() {
        this.chooseSystemStructureFile();
    }

    showOpenFileModal(file) {
        const newTabAvailable = this.workspaceChild && window.parent !== window;
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
                    <option value="html">v_ase HTML project</option>
                </select>
                <label for="open-file-index">Frames</label>
                <input id="open-file-index" type="text" value=":" autocomplete="off" spellcheck="false">
            </div>
            <p class="modal-intro">Use <strong>:</strong> for all frames, <strong>-1</strong> for the last frame, or an integer frame index.</p>
            <fieldset class="open-file-modes">
                <legend>Open as</legend>
                <label class="open-file-mode">
                    <input type="radio" name="open-file-mode" value="replace" checked>
                    <span>
                        <strong>Replace this tab</strong>
                        <small>Open the selected document in the current tab. A .vase project or project-embedded HTML restores its complete visual setup.</small>
                    </span>
                </label>
                <label class="open-file-mode">
                    <input type="radio" name="open-file-mode" value="append">
                    <span>
                        <strong>Add to trajectory</strong>
                        <small>Append every selected frame to this tab for movie playback. A .vase file or project-embedded HTML contributes structures only.</small>
                    </span>
                </label>
                <label class="open-file-mode${newTabAvailable ? '' : ' disabled'}">
                    <input type="radio" name="open-file-mode" value="new-tab"${newTabAvailable ? '' : ' disabled'}>
                    <span>
                        <strong>Open in new tab</strong>
                        <small>${newTabAvailable
                            ? 'Create an independent structure tab with its own state and .vase project.'
                            : 'Available when v_ase is running in its multi-tab workspace.'}</small>
                    </span>
                </label>
            </fieldset>
        `, `
            <button id="open-file-cancel" class="btn">Cancel</button>
            <button id="open-file-confirm" class="btn primary">Replace</button>
        `);
        const name = document.getElementById('open-file-name');
        const size = document.getElementById('open-file-size');
        if (name) {
            name.textContent = file.name;
            name.title = file.name;
        }
        if (size) size.textContent = this.formatFileSize(file.size);
        const confirm = document.getElementById('open-file-confirm');
        const syncConfirmLabel = () => {
            const mode = document.querySelector('input[name="open-file-mode"]:checked')?.value || 'replace';
            const labels = {
                replace: 'Replace',
                append: 'Add Frames',
                'new-tab': 'Open New Tab'
            };
            if (confirm) confirm.textContent = labels[mode];
        };
        document.querySelectorAll('input[name="open-file-mode"]').forEach(input => {
            input.addEventListener('change', syncConfirmLabel);
        });
        document.getElementById('open-file-cancel')?.addEventListener('click', () => this.closeModal(), { once: true });
        confirm?.addEventListener('click', async () => {
            const inputFormat = document.getElementById('open-file-format')?.value || '';
            const index = document.getElementById('open-file-index')?.value.trim() || ':';
            const mode = document.querySelector('input[name="open-file-mode"]:checked')?.value || 'replace';
            this.closeModal();
            if (mode === 'append') {
                await this.appendStructureFile(file, inputFormat, index);
            } else if (mode === 'new-tab') {
                await this.openStructureFileInNewTab(file, inputFormat, index);
            } else {
                await this.loadStructureFile(file, inputFormat, index);
            }
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
                () => this.api.loadStructureFile(
                    file,
                    inputFormat,
                    index,
                    this.volumetricImportPrecision()
                )
            );
            this.resetHistoryTimeline();
            const isProject = data.loaded_file?.kind === 'project' || Boolean(data.project);
            const projectSettings = data.project?.settings || data.metadata?.config?.initial_design_settings;
            const settings = isProject ? projectSettings : inheritedSettings;
            this.state.labelOrder = [];
            this.state.trajectoryBinaryCache = null;
            this.state.trajectoryBinaryPromise = null;
            this.state.timelineSource = 'loaded';
            this.state.relaxTrajectory = { frames: [], frame: 0, sourceFrame: 0, active: false, finished: false };
            this.renderer.needsInitialCameraFit = !settings?.camera;
            this.setAtomsData(data, {
                clearSelection: true,
                preserveDisplay: !isProject,
                resetTrajectoryIdentity: true
            });
            if (settings) {
                this.applyDesignSettings(settings);
                this.initialDesignSettings = isProject
                    ? this.clonePlain(settings)
                    : this.designSettingsSnapshot();
            } else {
                this.initialDesignSettings = this.designSettingsSnapshot();
            }
            this.resetVisualHistoryBaseline();
            const frameCount = data.metadata?.frame_count || 1;
            this.toast(
                `Opened ${data.loaded_file?.filename || file.name}${frameCount > 1 ? ` (${frameCount} frames)` : ''}.`,
                'success'
            );
            this.notifyWorkspaceDocument();
        } catch (err) {
            this.toast(`Open file failed: ${err.message}`, 'error');
        }
    }

    async appendStructureFile(file, inputFormat = '', index = ':') {
        try {
            this.stopPlayback();
            if (this.transform.mode !== 'IDLE') this.cancelTransform();
            const wasEmpty = !this.hasLoadedAtoms();
            try {
                this.applyDisplayOptions();
            } catch {
                this.captureBondSettingsFromControls();
            }
            const data = await this.withBusy(
                `Adding ${file.name} to trajectory...`,
                () => this.api.appendStructureFile(
                    file,
                    inputFormat,
                    index,
                    this.volumetricImportPrecision()
                )
            );
            this.resetHistoryTimeline();
            this.state.trajectoryBinaryCache = null;
            this.state.trajectoryBinaryPromise = null;
            this.state.timelineSource = 'loaded';
            this.state.relaxTrajectory = {
                frames: [],
                frame: 0,
                sourceFrame: 0,
                active: false,
                finished: false
            };
            this.renderer.needsInitialCameraFit = wasEmpty;
            this.setAtomsData(data, {
                clearSelection: wasEmpty,
                preserveDisplay: true,
                preserveRdf: data.loaded_file?.source_kind === 'volumetric'
            });
            if (wasEmpty) this.initialDesignSettings = this.designSettingsSnapshot();
            this.resetVisualHistoryBaseline();
            if (data.loaded_file?.source_kind === 'volumetric') {
                const addedVolumes = Number(data.loaded_file?.appended_volumetric_datasets) || 0;
                this.renderVolumetricControls();
                this.toast(
                    `Added ${addedVolumes} scalar field${addedVolumes === 1 ? '' : 's'} `
                    + `from ${data.loaded_file?.filename || file.name}.`,
                    'success'
                );
                this.notifyWorkspaceDocument();
                return;
            }
            const added = Number(data.loaded_file?.appended_frames) || 0;
            const total = Number(data.metadata?.frame_count) || 1;
            const projectNote = data.loaded_file?.project_settings_ignored
                ? ' Structures were imported; .vase visual settings were intentionally ignored.'
                : '';
            this.toast(
                `Added ${added} frame${added === 1 ? '' : 's'} from ${data.loaded_file?.filename || file.name}. `
                + `Trajectory now has ${total} frame${total === 1 ? '' : 's'}.${projectNote}`,
                'success'
            );
            this.notifyWorkspaceDocument();
        } catch (err) {
            this.toast(`Add to trajectory failed: ${err.message}`, 'error');
        }
    }

    async openStructureFileInNewTab(file, inputFormat = '', index = ':') {
        if (!this.workspaceChild || window.parent === window) {
            this.toast('New structure tabs are available in the v_ase workspace.', 'warning');
            return;
        }
        const requestId = `${this.sessionId}:${Date.now()}:${++this.workspaceRequestSequence}`;
        try {
            const result = await this.withBusy(
                `Opening ${file.name} in a new tab...`,
                () => new Promise((resolve, reject) => {
                    this.workspaceOpenRequests.set(requestId, { resolve, reject });
                    window.parent.postMessage({
                        type: 'v_ase:document-open-new',
                        sessionId: this.sessionId,
                        requestId,
                        file,
                        serverPath: null,
                        fileName: file.name,
                        inputFormat,
                        index,
                        volumetricPrecision: this.volumetricImportPrecision()
                    }, window.location.origin);
                })
            );
            this.toast(`Opened ${result.title || file.name} in a new tab.`, 'success');
        } catch (err) {
            this.workspaceOpenRequests.delete(requestId);
            this.toast(`Open new tab failed: ${err.message}`, 'error');
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
                <span>Space</span><label>Play or pause the selected timeline</label>
                <span>&larr; / &rarr;</span><label>Previous or next frame in the selected timeline</label>
                <span>Tab / Esc</span><label>Open the control panel while it is collapsed</label>
                <span>G</span><label>Move selected atoms or Sun handle</label>
                <span>R</span><label>Rotate selected atoms or Sun direction</label>
                <span>Sun source + G</span><label>Move source and target together</label>
                <span>Sun target + G</span><label>Move target only</label>
                <span>Sun handle + R</span><label>Rotate target around source</label>
                <span>X / Y / Z</span><label>Align view in select mode</label>
                <span>X / Y / Z</span><label>Lock transform axis in G/R mode</label>
                <span>Enter</span><label>Confirm transform</label>
                <span>Esc</span><label>Cancel a transform, close a modal, or close the open control panel and return focus to the viewport</label>
                <span>Ctrl+C / V / Z</span><label>Copy, paste, undo an edit or visual setting</label>
                <span>Delete</span><label>Delete selected atoms</label>
            </div>
            <h3 class="help-section-title">Opening Files</h3>
            <div class="help-save-grid">
                <strong>Replace this tab</strong>
                <span>Replace the current structure or trajectory. A .vase project also restores its saved visual setup.</span>
                <strong>Add to trajectory</strong>
                <span>Append every selected frame to the current movie while keeping this tab's visual setup. A .vase file contributes structures only.</span>
                <strong>Open in new tab</strong>
                <span>Create an independent structure tab. A .vase project restores its complete state in that new tab.</span>
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
                <strong>Browser save access</strong>
                <span>Chrome may state that this site can view changes to the file you selected. This is the browser's File System Access notice; v_ase receives access only to the destination you explicitly choose.</span>
                <strong>ASE Pickle (.pkl)</strong>
                <span>Current ASE Atoms data for Python: coordinates, labels, cell, PBC, constraints, arrays, and valid SinglePointCalculator results. Visual settings are excluded.</span>
                <strong>Visual Settings (.json)</strong>
                <span>Reusable display preset: bonds, appearance, camera, lighting, quality, display replication, and visual translation. Atomic coordinates are not included.</span>
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

    normalizedImageFormat(value, fallback = 'png') {
        const normalized = String(value || '').trim().toLowerCase();
        if (normalized === 'jpeg') return 'jpg';
        return ['png', 'jpg', 'pdf', 'webp'].includes(normalized) ? normalized : fallback;
    }

    imageMimeType(format) {
        return {
            png: 'image/png',
            jpg: 'image/jpeg',
            pdf: 'application/pdf',
            webp: 'image/webp'
        }[this.normalizedImageFormat(format)] || 'image/png';
    }

    imageFormatSupportsTransparency(format) {
        return ['png', 'webp'].includes(this.normalizedImageFormat(format));
    }

    defaultImageExportOptions() {
        const display = this.state.display;
        const pixelsPerAngstrom = Math.max(0.1, Math.min(5000,
            Number(this.renderer.currentPixelsPerAngstrom()) || 100));
        return {
            transparentBackground: false,
            backgroundColor: '#ffffff',
            includeGrid: false,
            includeAxes: true,
            includeCell: true,
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
            format: this.normalizedImageFormat(profile?.format),
            width: Math.max(256, Math.round(Number(dimensions.width) || 1920)),
            height: Math.max(256, Math.round(Number(dimensions.height) || 1080)),
            options: {
                transparentBackground: this.imageFormatSupportsTransparency(profile?.format)
                    ? (source.transparentBackground ?? fallback.transparentBackground)
                    : false,
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
        const { width, height, format: imageFormat, options: imageOptions } = initialProfile;
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
                    <label for="export-image-format">Format</label>
                    <select id="export-image-format">
                        <option value="png" ${selected('png', imageFormat)}>PNG (lossless, compatible)</option>
                        <option value="jpg" ${selected('jpg', imageFormat)}>JPEG (compact, opaque)</option>
                        <option value="pdf" ${selected('pdf', imageFormat)}>PDF (single-page raster)</option>
                        <option value="webp" ${selected('webp', imageFormat)}>WebP (lossless, compact)</option>
                    </select>
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
                format: document.getElementById('export-image-format')?.value || 'png',
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
            const transparency = document.getElementById('export-transparent');
            if (transparency) {
                const supportsTransparency = this.imageFormatSupportsTransparency(profile.format);
                transparency.disabled = !supportsTransparency;
                transparency.checked = supportsTransparency && profile.options.transparentBackground;
                transparency.closest('.check-row')?.classList.toggle('disabled', !supportsTransparency);
                transparency.title = supportsTransparency
                    ? 'Keep the canvas background transparent.'
                    : `${profile.format.toUpperCase()} output is composited onto white.`;
            }
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
            'export-image-format', 'export-transparent', 'export-grid', 'export-axes', 'export-cell', 'export-framing-mode',
            'export-sphere-quality', 'export-render-mode'
        ]
            .forEach(id => document.getElementById(id)?.addEventListener('change', updateExportSummary));
        updateExportSummary();

        document.getElementById('modal-export-image')?.addEventListener('click', async () => {
            try {
                const profile = this.setImageExportProfile(readImageProfile());
                const { width: exportWidth, height: exportHeight, format, options } = profile;
                const mimeType = this.imageMimeType(format);
                const filename = `v_ase-${exportWidth}x${exportHeight}.${format}`;
                const destination = await this.chooseSaveDestination(filename, mimeType);
                if (!destination) return;
                Object.assign(this.state.display, {
                    imageFramingMode: options.scaleMode,
                    atomicScalePixelsPerAngstrom: options.pixelsPerAngstrom,
                    imageSphereQuality: options.sphereQuality,
                    imageSmoothnessScale: options.sphereQualityScale
                });
                const startedAt = performance.now();
                const updateProgress = (progress, message, complete = false) => {
                    this.setBusyProgress(progress, {
                        message,
                        etaSeconds: complete
                            ? 0
                            : this.estimatedRemainingFromProgress(startedAt, progress),
                        complete
                    });
                };
                this.setBusy(
                    `Preparing ${exportWidth} x ${exportHeight} image...`,
                    {
                        title: 'Export Image',
                        progress: 2,
                        etaSeconds: null
                    }
                );
                await new Promise(resolve => requestAnimationFrame(resolve));
                const blob = await this.renderOptimizedImage(
                    exportWidth,
                    exportHeight,
                    options,
                    format,
                    event => {
                        const ratio = Math.max(0, Math.min(1, Number(event?.ratio) || 0));
                        if (event?.phase === 'render') {
                            updateProgress(8, 'Rendering the exact Preview Area...');
                        } else if (event?.phase === 'capture') {
                            updateProgress(48, 'Captured the full-resolution scene.');
                        } else if (event?.phase === 'upload') {
                            updateProgress(50 + ratio * 20, 'Sending pixels to the image encoder...');
                        } else if (event?.phase === 'encoding') {
                            updateProgress(74, `Encoding ${format.toUpperCase()} without changing dimensions...`);
                        } else if (event?.phase === 'download') {
                            updateProgress(80 + ratio * 14, 'Receiving the encoded image...');
                        } else if (event?.phase === 'complete') {
                            updateProgress(95, 'Image encoding finished.');
                        }
                    }
                );
                updateProgress(97, 'Writing the selected output file...');
                const saved = await this.savePreparedBlob(
                    blob,
                    filename,
                    mimeType,
                    destination
                );
                this.syncImageExportPreview();
                if (saved) {
                    updateProgress(100, 'Image export saved.', true);
                    await new Promise(resolve => window.setTimeout(resolve, 120));
                    this.closeModal();
                    this.toast('Image export saved.', 'success');
                }
            } catch (err) {
                this.toast(`Image export failed: ${err.message}`, 'error');
            } finally {
                this.clearBusy();
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
        const interpolationMultiplier = normalizeInterpolationMultiplier(
            this.state.display.videoInterpolationMultiplier
        );
        const interpolationMic = this.state.display.videoInterpolationMic !== false;
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
                        <label for="video-interpolation-multiplier">Interpolation</label>
                        <input type="number" id="video-interpolation-multiplier"
                               value="${interpolationMultiplier}" min="1" max="64" step="1"
                               aria-describedby="video-interpolation-note">
                    </div>
                    <label class="check-row" for="video-interpolation-mic">
                        <span>Minimum image convention</span>
                        <input type="checkbox" id="video-interpolation-mic" ${interpolationMic ? 'checked' : ''}>
                    </label>
                    <p id="video-interpolation-note" class="export-note"></p>
                    <p class="export-note">Visible displacement vectors are recalculated and rendered for every output frame.</p>
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
                interpolationMultiplier: normalizeInterpolationMultiplier(
                    document.getElementById('video-interpolation-multiplier')?.value
                        || interpolationMultiplier
                ),
                interpolationMic: Boolean(
                    document.getElementById('video-interpolation-mic')?.checked
                ),
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
            const interpolationNote = document.getElementById('video-interpolation-note');
            const interpolationToggle = document.getElementById('video-interpolation-mic');
            const outputFrames = interpolatedFrameCount(count, options.interpolationMultiplier);
            if (interpolationToggle) interpolationToggle.disabled = options.interpolationMultiplier <= 1;
            if (interpolationNote) {
                interpolationNote.textContent = options.interpolationMultiplier <= 1
                    ? `${count} source frames → ${outputFrames} output frames (${(outputFrames / options.fps).toFixed(2)} s). Every source frame is retained once.`
                    : `${options.interpolationMultiplier}× creates ${outputFrames} frames (${(outputFrames / options.fps).toFixed(2)} s). Higher values take longer to render.`;
            }
            const {
                width: previewWidth,
                height: previewHeight,
                fps: _fps,
                format: _format,
                interpolationMultiplier: _interpolationMultiplier,
                interpolationMic: _interpolationMic,
                ...renderOptions
            } = options;
            this.state.exportPreviewProfile = {
                width: previewWidth,
                height: previewHeight,
                options: renderOptions
            };
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        };
        [
            'video-width', 'video-height', 'video-fps', 'video-interpolation-multiplier',
            'video-smoothness-scale',
            'video-sun-intensity', 'video-sun-position-0', 'video-sun-position-1',
            'video-sun-position-2', 'video-sun-target-0', 'video-sun-target-1',
            'video-sun-target-2'
        ].forEach(id => document.getElementById(id)?.addEventListener('input', updateVideoPreview));
        [
            'video-format', 'video-interpolation-mic', 'video-grid', 'video-axes',
            'video-cell', 'video-framing-mode',
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
                    videoFps: options.fps,
                    videoInterpolationMultiplier: options.interpolationMultiplier,
                    videoInterpolationMic: options.interpolationMic
                });
                const imageWidthInput = document.getElementById('image-width');
                const imageHeightInput = document.getElementById('image-height');
                if (imageWidthInput) imageWidthInput.value = `${options.width}`;
                if (imageHeightInput) imageHeightInput.value = `${options.height}`;
                const filename = `v_ase-trajectory.${options.format}`;
                const outputMime = options.format === 'avi'
                    ? 'video/x-msvideo'
                    : 'video/quicktime';
                const destination = await this.chooseSaveDestination(filename, outputMime);
                if (!destination) return;
                await this.exportTrajectoryVideo(options, destination);
            } catch (err) {
                this.toast(`Video export failed: ${err.message}`, 'error');
            }
        });
        document.getElementById('modal-close')?.addEventListener('click', () => {
            this.state.exportPreviewProfile = null;
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
        }, { once: true });
    }

    videoFrameSnapshot() {
        const positions = this.renderer?.atomsData?.positions || this.state.atoms?.positions || [];
        const flattened = new Float64Array(positions.length * 3);
        positions.forEach((position, index) => {
            const offset = index * 3;
            flattened[offset] = Number(position?.[0]) || 0;
            flattened[offset + 1] = Number(position?.[1]) || 0;
            flattened[offset + 2] = Number(position?.[2]) || 0;
        });
        return {
            positions: flattened,
            count: positions.length,
            cell: Array.isArray(this.state.atoms?.cell)
                ? this.state.atoms.cell.map(row => [...row])
                : null,
            pbc: Array.isArray(this.state.atoms?.pbc) ? [...this.state.atoms.pbc] : [false, false, false],
            chemicalSymbols: [...(this.state.atoms?.chemical_symbols || [])],
            labels: [...(this.state.atoms?.symbols || [])]
        };
    }

    videoFramesAreInterpolable(first, second) {
        if (first.count !== second.count) {
            throw new Error('Interpolation requires the same atom count in every trajectory frame.');
        }
        const sameValues = (a, b) => (
            a.length === b.length && a.every((value, index) => value === b[index])
        );
        if (
            !sameValues(first.chemicalSymbols, second.chemicalSymbols)
            || !sameValues(first.labels, second.labels)
        ) {
            throw new Error('Interpolation requires stable atom ordering, chemical types, and labels.');
        }
    }

    videoAnalysisPositions(sample = null) {
        const flattened = sample?.positions;
        const count = Number(sample?.count) || 0;
        if (flattened && count > 0) {
            return Array.from({ length: count }, (_, index) => {
                const offset = index * 3;
                return [
                    Number(flattened[offset]) || 0,
                    Number(flattened[offset + 1]) || 0,
                    Number(flattened[offset + 2]) || 0
                ];
            });
        }
        const positions = this.renderer?.atomsData?.positions || this.state.atoms?.positions || [];
        return positions.map(position => [
            Number(position?.[0]) || 0,
            Number(position?.[1]) || 0,
            Number(position?.[2]) || 0
        ]);
    }

    async synchronizeVideoDisplacements(sample = null) {
        if (!this.state.display.showDisplacements) return;
        if (this.state.displacementRefreshTimer !== null) {
            clearTimeout(this.state.displacementRefreshTimer);
            this.state.displacementRefreshTimer = null;
        }
        await this.refreshDisplacementAnalysis({
            positions: this.videoAnalysisPositions(sample),
            frameIndex: Number(this.state.atoms?.metadata?.current_frame) || 0,
            suppressBusy: true
        });
    }

    async captureCurrentVideoFrame(
        capture,
        videoTrack,
        outputIndex,
        outputCount,
        outputFps,
        startedAt
    ) {
        this.renderer.renderExportCaptureFrame(capture);
        videoTrack?.requestFrame?.();
        const elapsedSeconds = Math.max(0.001, (performance.now() - startedAt) / 1000);
        const secondsPerFrame = elapsedSeconds / Math.max(1, outputIndex);
        const etaSeconds = secondsPerFrame * Math.max(0, outputCount - outputIndex);
        this.setBusyProgress(3 + (outputIndex / outputCount) * 72, {
            message: `Rendering frame ${outputIndex} of ${outputCount}...`,
            etaSeconds
        });
        await new Promise(resolve => setTimeout(resolve, 1000 / outputFps));
    }

    async renderVideoCaptureSample(
        capture,
        videoTrack,
        sample,
        outputIndex,
        outputCount,
        outputFps,
        startedAt
    ) {
        this.applyFrameLattice(sample.cell, sample.pbc);
        this.renderer.updatePositionsFlat(sample.positions, 0, sample.count);
        await this.synchronizeVideoDisplacements(sample);
        await this.captureCurrentVideoFrame(
            capture, videoTrack, outputIndex, outputCount, outputFps, startedAt
        );
    }

    async exportTrajectoryVideo({
        width,
        height,
        fps,
        format,
        interpolationMultiplier = 1,
        interpolationMic = true,
        ...renderOptions
    }, destination, { returnBlob = false } = {}) {
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
        const interpolationFactor = normalizeInterpolationMultiplier(interpolationMultiplier);
        const outputFrameCount = interpolatedFrameCount(frameCount, interpolationFactor);
        const outputFormat = format === 'avi' ? 'avi' : 'mov';
        const filename = `v_ase-trajectory.${outputFormat}`;
        const outputMime = outputFormat === 'avi' ? 'video/x-msvideo' : 'video/quicktime';
        const selectedDestination = returnBlob
            ? null
            : (destination || await this.chooseSaveDestination(filename, outputMime));
        if (!returnBlob && !selectedDestination) return false;
        const originalFrame = meta.current_frame || 0;
        const exportId = globalThis.crypto?.randomUUID?.()
            || `video-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const renderingStartedAt = performance.now();
        this.state.videoExportId = exportId;
        this.state.videoExportStartedAt = renderingStartedAt;
        if (this.state.trajectoryTimer) {
            clearTimeout(this.state.trajectoryTimer);
            this.state.trajectoryTimer = null;
            this.state.trajectoryPlaybackSource = null;
            this.updateTrajectoryUI();
        }
        const chunks = [];
        let capture = this.renderer.beginExportCapture(outputWidth, outputHeight, renderOptions);
        let stream = canvas.captureStream(0);
        let videoTrack = stream.getVideoTracks()[0];
        if (typeof videoTrack?.requestFrame !== 'function') {
            stream.getTracks().forEach(track => track.stop());
            stream = canvas.captureStream(outputFps);
            videoTrack = stream.getVideoTracks()[0];
        }
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
        this.setBusy(`Preparing ${outputFrameCount} video frames...`, {
            title: 'Exporting video',
            progress: 1
        });
        recorder.start(100);
        try {
            await new Promise(resolve => setTimeout(resolve, 80));
            let outputIndex = 0;
            let micFallback = false;
            if (interpolationFactor <= 1) {
                for (let frame = 0; frame < frameCount; frame++) {
                    await this.loadFrame(frame);
                    await this.synchronizeVideoDisplacements(this.videoFrameSnapshot());
                    outputIndex += 1;
                    await this.captureCurrentVideoFrame(
                        capture,
                        videoTrack,
                        outputIndex,
                        outputFrameCount,
                        outputFps,
                        renderingStartedAt
                    );
                }
            } else {
                await this.loadFrame(0);
                let first = this.videoFrameSnapshot();
                await this.synchronizeVideoDisplacements(first);
                outputIndex += 1;
                await this.captureCurrentVideoFrame(
                    capture,
                    videoTrack,
                    outputIndex,
                    outputFrameCount,
                    outputFps,
                    renderingStartedAt
                );
                for (let frame = 1; frame < frameCount; frame++) {
                    await this.loadFrame(frame);
                    const second = this.videoFrameSnapshot();
                    this.videoFramesAreInterpolable(first, second);
                    for (let subframe = 1; subframe < interpolationFactor; subframe++) {
                        const sample = interpolateTrajectoryFrames(
                            first,
                            second,
                            subframe / interpolationFactor,
                            { useMic: interpolationMic }
                        );
                        if (interpolationMic && !sample.micApplied) micFallback = true;
                        outputIndex += 1;
                        await this.renderVideoCaptureSample(
                            capture,
                            videoTrack,
                            sample,
                            outputIndex,
                            outputFrameCount,
                            outputFps,
                            renderingStartedAt
                        );
                    }
                    outputIndex += 1;
                    await this.renderVideoCaptureSample(
                        capture,
                        videoTrack,
                        second,
                        outputIndex,
                        outputFrameCount,
                        outputFps,
                        renderingStartedAt
                    );
                    first = second;
                }
            }
            recorder.stop();
            await finished;
            stream.getTracks().forEach(track => track.stop());
            this.renderer.endExportCapture(capture);
            capture = null;
            const recording = new Blob(chunks, {
                type: recorder.mimeType || mimeType || 'application/octet-stream'
            });
            this.setBusyProgress(77, {
                message: `Uploading frames for ${outputFormat.toUpperCase()} encoding...`
            });
            const video = await this.api.transcodeVideo(
                recording,
                outputFormat,
                outputFps,
                outputFrameCount,
                exportId
            );
            this.setBusyProgress(98, {
                message: 'Finalizing encoded video...',
                etaSeconds: 1
            });
            if (returnBlob) {
                this.setBusyProgress(100, {
                    message: 'Video export complete.',
                    etaSeconds: 0,
                    complete: true
                });
                await new Promise(resolve => setTimeout(resolve, 160));
                return video;
            }
            this.setBusyProgress(99, {
                message: 'Writing the selected output file...',
                etaSeconds: 1
            });
            const saved = await this.savePreparedBlob(
                video,
                filename,
                outputMime,
                selectedDestination
            );
            if (saved) {
                this.setBusyProgress(100, {
                    message: 'Video export complete.',
                    etaSeconds: 0,
                    complete: true
                });
                await new Promise(resolve => setTimeout(resolve, 220));
                this.toast(`${outputFormat.toUpperCase()} video saved.`, 'success');
            }
            if (micFallback) {
                this.toast(
                    'MIC was unavailable for one or more transitions; direct interpolation was used there.',
                    'warning'
                );
            }
        } finally {
            stream.getTracks().forEach(track => track.stop());
            if (recorder.state !== 'inactive') recorder.stop();
            if (capture) this.renderer.endExportCapture(capture);
            await this.loadFrame(originalFrame);
            this.state.videoExportId = null;
            this.state.videoExportStartedAt = null;
            this.state.exportPreviewProfile = null;
            if (this.state.exportPreviewEnabled) this.syncImageExportPreview();
            this.clearBusy();
        }
    }

    applyFrameLattice(cell, pbc) {
        if (Array.isArray(cell)) {
            const oldCell = JSON.stringify(this.state.atoms.cell || []);
            const newCell = JSON.stringify(cell);
            this.state.atoms.cell = cell;
            this.renderer.atomsData.cell = cell;
            if (oldCell !== newCell) {
                this.renderer.rebuildCell(cell);
                this.renderer.rebuildSupercell();
            }
        }
        if (Array.isArray(pbc)) {
            const changed = JSON.stringify(this.state.atoms.pbc || []) !== JSON.stringify(pbc);
            this.state.atoms.pbc = pbc;
            this.renderer.atomsData.pbc = pbc;
            if (changed) this.renderer.invalidateBondNeighborCache();
        }
    }

    completeTrajectoryFrameUpdate() {
        this.pruneSelection();
        this.updateSelectionVisuals();
        this.observeCollaborationFrame();
        if (this.state.display.showDisplacements) {
            this.renderer.clearDisplacementVectors();
        }
        this.scheduleDisplacementAnalysisRefresh();
    }

    async loadFrame(index) {
        if (this.transform.mode !== 'IDLE') this.cancelTransform();
        const meta = this.state.atoms?.metadata || {};

        if (meta.virtual_trajectory) {
            const count = meta.frame_count || 1;
            const normalized = Math.max(0, Math.min(count - 1, parseInt(index, 10) || 0));
            const binaryCache = this.state.trajectoryBinaryCache;
            if (
                this.state.trajectoryTimer
                && binaryCache
                && binaryCache.frames === count
                && binaryCache.atoms === this.state.atoms.positions.length
            ) {
                const offset = normalized * binaryCache.atoms * 3;
                this.state.atoms.metadata.current_frame = normalized;
                const override = this.relaxOverridePositions(normalized);
                if (override) {
                    this.renderer.updatePositions(override);
                } else {
                    this.renderer.updatePositionsFlat(binaryCache.values, offset, binaryCache.atoms);
                }
                this.updateTrajectoryUI();
                this.completeTrajectoryFrameUpdate();
                return;
            }
            const frame = await this.api.fetchFramePositions(normalized);
            if (frame.atoms !== this.state.atoms.positions.length) {
                throw new Error('Frame atom count does not match the loaded structure.');
            }
            this.state.atoms.metadata.current_frame = frame.frame;
            this.state.atoms.metadata.frame_count = frame.frames || count;
            this.applyFrameLattice(frame.cell, frame.pbc);
            const override = this.relaxOverridePositions(normalized);
            if (override) {
                this.state.atoms.positions = override;
                this.state.originalPositions = this.state.vizOnly ? override : override.map(p => [...p]);
                this.renderer.updatePositions(override);
                this.updateUI();
                this.completeTrajectoryFrameUpdate();
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
            this.completeTrajectoryFrameUpdate();
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
            this.completeTrajectoryFrameUpdate();
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
            this.completeTrajectoryFrameUpdate();
            return;
        }

        const data = await this.api.setFrame(index);
        if (data?.metadata?.positions_only && Array.isArray(data.positions)) {
            this.state.atoms.metadata.current_frame = data.metadata.current_frame;
            this.state.atoms.metadata.frame_count = data.metadata.frame_count || this.state.atoms.metadata.frame_count;
            this.state.atoms.positions = data.positions;
            this.state.originalPositions = this.state.vizOnly ? data.positions : data.positions.map(p => [...p]);
            this.applyFrameLattice(data.cell, data.pbc);
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
            this.completeTrajectoryFrameUpdate();
            return;
        }
        this.setAtomsData(data, { clearSelection: false });
    }

    queueFrameLoad(index, source = this.primaryTimelineSource()) {
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

    requestFrameStep(delta) {
        const source = this.primaryTimelineSource();
        if (this.timelineFrameCount(source) <= 1) return Promise.resolve();
        this.stopPlayback();
        this.timelineStepQueue = this.timelineStepQueue
            .catch(() => {})
            .then(() => this.stepFrame(delta, source));
        return this.timelineStepQueue;
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
            if (!file) return;
            if (!this.hasLoadedAtoms()) {
                this.loadStructureFile(file, '', ':');
                return;
            }
            this.showOpenFileModal(file);
        });
        
        document.getElementById('btn-reset').onclick = async () => {
            try {
                if (!await this.confirmFullReset()) return;
                const data = await this.withBusy(
                    'Resetting coordinates and visual settings...',
                    () => this.api.reset()
                );
                this.applyDesignSettings(this.initialDesignSettings, { render: false });
                this.state.display.translation = [0, 0, 0];
                this.state.display.translationMode = 'cartesian';
                this.syncDesignControls();
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
                const data = await this.withBusy(
                    'Resetting physical coordinates and original unit cell...',
                    () => this.api.resetCoordinates()
                );
                this.applyDesignSettings(preservedSettings, { render: false });
                this.setAtomsData(data, { clearSelection: true });
                this.toast('Physical coordinates and original unit cell restored. Display replication and visual translation were kept.', 'success');
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
            const kindSelect = document.getElementById('constraint-kind');
            const kind = kindSelect?.value || 'none';
            if (kindSelect) {
                if (['fixed_line', 'fixed_plane'].includes(kind)) {
                    kindSelect.dataset.draftKind = kind;
                } else {
                    delete kindSelect.dataset.draftKind;
                }
            }
            if (kind === 'fixed_line') this.setConstraintVectorInputs([1, 0, 0]);
            if (kind === 'fixed_plane') this.setConstraintVectorInputs([0, 0, 1]);
            this.updateSelectionConstraintControls();
        });
        document.getElementById('btn-apply-constraint')?.addEventListener('click', () => this.applySelectedDirectionalConstraint());
        document.getElementById('btn-clear-directional-constraint')?.addEventListener('click', () => this.clearSelectedDirectionalConstraint());
        document.getElementById('btn-undo').onclick = () => {
            this.performUndo().catch(err => this.toast(`Undo failed: ${err.message}`, 'error'));
        };
        document.getElementById('btn-redo').onclick = () => {
            this.performRedo().catch(err => this.toast(`Redo failed: ${err.message}`, 'error'));
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
        document.getElementById('btn-export-html').onclick = () => {
            this.showHtmlExportModal({ projectSave: false });
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
                    this.projectFilename(),
                    'application/vnd.v-ase.project+zip',
                    'Saving complete v_ase project...'
                );
                if (saved) this.toast('Complete .vase project saved.', 'success');
            } catch (err) {
                this.toast(`Save project failed: ${err.message}`, 'error');
            }
        };
        document.getElementById('btn-save-project-html').onclick = () => {
            this.showHtmlExportModal({ projectSave: true });
        };
        document.getElementById('btn-load-project').onclick = () => {
            document.getElementById('project-file')?.click();
        };
        document.getElementById('project-file').onchange = async (event) => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if (!file) return;
            await this.loadStructureFile(file, '', ':');
        };
        document.getElementById('btn-save-settings').onclick = async () => {
            try {
                this.applyDisplayOptions();
                const saved = await this.saveBlobFromAction(
                    () => this.api.saveVisualSettings(
                        this.designSettingsSnapshot({ includeAtomOverrides: false })
                    ),
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
        document.getElementById('calc-cutoff-scale')?.addEventListener('change', () => this.applyCalculatorControls());
        document.getElementById('calc-strength')?.addEventListener('change', () => this.applyCalculatorControls());
        document.getElementById('chk-bonds').onchange = () => this.safeApplyBondOptions();
        document.getElementById('chk-periodic-bonds').onchange = () => this.safeApplyBondOptions();
        document.getElementById('chk-cell').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('cell-thickness').oninput = () => this.safeApplyDisplayOptions();
        document.getElementById('cell-thickness').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('cell-color').oninput = () => this.safeApplyDisplayOptions();
        document.getElementById('cell-color').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('cell-material').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-axes').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-grid').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('chk-overlays').onchange = () => this.safeApplyDisplayOptions();
        document.getElementById('projection-mode').onchange = () => this.safeApplyDisplayOptions();
        const atomicScale = document.getElementById('atomic-scale');
        atomicScale.addEventListener('focus', () => this.flushVisualHistoryCommit());
        atomicScale.oninput = () => {
            this.applyAtomicScaleFromControl();
            this.scheduleVisualHistoryCommit('atomic-scale');
        };
        atomicScale.onchange = () => {
            this.applyAtomicScaleFromControl({ normalize: true });
            this.scheduleVisualHistoryCommit('atomic-scale');
        };
        atomicScale.addEventListener('blur', () => this.flushVisualHistoryCommit());
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
            this.safeApplyBondOptions();
        };
        document.getElementById('bond-cutoff').onchange = () => this.safeApplyBondOptions();
        document.getElementById('bond-cutoff').oninput = () => this.safeApplyBondOptions();
        document.getElementById('bond-style').onchange = () => this.safeApplyBondOptions();
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
            this.safeApplyBondOptions();
        };
        document.getElementById('bond-thickness').onchange = () => this.safeApplyBondOptions();
        document.getElementById('bond-color-mode').onchange = () => {
            this.updateBondAppearanceUI();
            this.safeApplyBondOptions();
        };
        document.getElementById('bond-custom-color').oninput = () => this.safeApplyBondOptions();
        document.getElementById('bond-custom-color').onchange = () => this.safeApplyBondOptions();
        document.getElementById('bond-pairs').oninput = () => this.safeApplyBondOptions();
        document.getElementById('bond-pairs').onchange = () => this.safeApplyBondOptions();
        document.getElementById('btn-bond-reset-specifications').onclick = () => {
            const ranges = {};
            const cutoffs = {};
            this.uniqueLabelPairs().forEach(([a, b]) => {
                const key = this.labelPairKey(a, b);
                const range = this.defaultPairwiseBondRange(a, b);
                ranges[key] = range;
                cutoffs[key] = range.max;
            });
            this.state.display.pairwiseBondRanges = ranges;
            this.state.display.pairwiseBondCutoffs = cutoffs;
            document.getElementById('bond-mode').value = 'pairwise';
            this.renderPairwiseBondControls({ capture: false });
            this.applyBondOptions();
            this.toast('Pair specifications reset to element-radius suggestions.', 'success');
        };
        this.setupPairwiseLabelColumnResizer();
        ['super-x', 'super-y', 'super-z'].forEach(id => {
            document.getElementById(id).onchange = () => this.safeApplyDisplayOptions();
            document.getElementById(id).oninput = () => this.safeApplyDisplayOptions();
        });
        document.querySelectorAll('[data-translation-mode]').forEach(button => {
            button.addEventListener('click', () => {
                this.setTranslationCoordinateMode(button.dataset.translationMode);
            });
        });
        this.setTranslationCoordinateMode(this.state.translationCoordinateMode);
        document.getElementById('btn-apply-translation').onclick = () => this.applyAtomTranslation();
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
        document.getElementById('timeline-source-select')?.addEventListener('change', event => {
            this.setTimelineSource(event.target.value)
                .catch(err => this.toast(`Timeline switch failed: ${err.message}`, 'error'));
        });
        document.getElementById('btn-frame-prev').onclick = () => this.requestFrameStep(-1).catch(err => this.toast(err.message, 'error'));
        document.getElementById('btn-frame-next').onclick = () => this.requestFrameStep(1).catch(err => this.toast(err.message, 'error'));
        document.getElementById('btn-play').onclick = () => this.togglePlayback().catch(err => this.toast(`Movie playback failed: ${err.message}`, 'error'));
        document.getElementById('frame-slider').oninput = (e) => {
            this.queueFrameLoad(e.target.value, this.primaryTimelineSource());
        };
        document.getElementById('frame-slider').onchange = (e) => {
            this.queueFrameLoad(e.target.value, this.primaryTimelineSource());
        };
        document.getElementById('secondary-frame-slider')?.addEventListener('input', e => {
            const source = document.getElementById('secondary-trajectory-row')?.dataset.source;
            if (source) this.queueFrameLoad(e.target.value, source);
        });
        document.getElementById('secondary-frame-slider')?.addEventListener('change', e => {
            const source = document.getElementById('secondary-trajectory-row')?.dataset.source;
            if (source) this.queueFrameLoad(e.target.value, source);
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
        document.getElementById('rotate-pivot')?.addEventListener('change', event => {
            this.state.display.rotatePivot = event.currentTarget.value || 'selection';
            this.safeApplyDisplayOptions();
            if (this.transform.mode === 'ROTATE') this.toast('Rotate pivot changes apply to the next rotate operation.', 'warning');
        });
        document.getElementById('btn-rotate-selection-exact')?.addEventListener('click', () => {
            this.rotateSelectionFromPanel()
                .catch(err => this.toast(`Rotation failed: ${err.message}`, 'error'));
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
                e.preventDefault();
                e.target?.blur?.();
                this.setInspectorCollapsed(false);
                return;
            }
            if ((e.code === 'Tab' || e.key === 'Tab') && inspectorCollapsed && !isFormControl && this.transform.mode === 'IDLE') {
                e.preventDefault();
                this.setInspectorCollapsed(false);
                return;
            }
            if (['input', 'textarea', 'select'].includes(tag)) return;
            const modalOpen = !document.getElementById('modal-container')?.classList.contains('hidden');
            if (
                !modalOpen
                && !isFormControl
                && this.transform.mode === 'IDLE'
                && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')
                && !e.ctrlKey
                && !e.metaKey
                && !e.altKey
            ) {
                if (this.timelineFrameCount(this.primaryTimelineSource()) > 1) {
                    e.preventDefault();
                    const delta = e.key === 'ArrowLeft' ? -1 : 1;
                    this.requestFrameStep(delta)
                        .catch(err => this.toast(`Frame change failed: ${err.message}`, 'error'));
                }
                return;
            }
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
                    (e.shiftKey ? this.performRedo() : this.performUndo())
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
window.v_aseAI = window.__V_ASE_APP__.createAIBridge();
window.__V_ASE_AI__ = window.v_aseAI;
