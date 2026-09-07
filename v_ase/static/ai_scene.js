import * as THREE from 'three';

const MAP_FIELDS = new Set([
    'labelColors', 'labelRadii', 'labelVisible', 'labelMaterials', 'labelOpacities',
    'atomColors', 'atomRadiusScales', 'atomMaterials', 'atomOpacities', 'atomBondStyles',
    'pairwiseBondCutoffs', 'pairwiseBondRanges', 'pairwiseBondStyles'
]);
const PATCH_FIELDS = new Set(['frame', 'display', 'quality', 'camera', 'renderArea',
    'selection', 'planeSelection', 'clearSelections']);
const TRACKED = [
    'loadFrame', 'completeTrajectoryFrameUpdate', 'refreshVolumetricDataForCurrentFrame',
    'updateVolumetricSurface', 'renderVolumetricPlane', 'renderAllVolumetricPlanes',
    'recolorVolumetricPlanes', 'updateAtomColorScale', 'updateForceVectorsForCurrentFrame',
    'refreshDisplacementAnalysis', 'calculateRdf', 'prepareCommensurateSupercellProposal'
];
const copy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = (value, digits = 6) => Number.isFinite(value) ? Number(value.toFixed(digits)) : null;
const vector = value => value.toArray().map(component => finite(component));

function fail(message, code = 'invalid_arguments', outcome = 'not_applied') {
    const error = new Error(message);
    error.code = code;
    error.outcome = outcome;
    return error;
}

function integer(value, fallback, minimum, maximum, name) {
    if (value === undefined) return fallback;
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
        throw fail(`${name} must be an integer in ${minimum}..${maximum}.`);
    }
    return value;
}

function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (!plain(value)) return value;
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
}

function requireFiniteJSON(value, seen = new Set()) {
    if (typeof value === 'number' && !Number.isFinite(value)) throw fail('Scene numbers must be finite.');
    if (value && typeof value === 'object') {
        if (seen.has(value)) throw fail('Scene arguments must not contain cycles.');
        seen.add(value);
        for (const item of Object.values(value)) requireFiniteJSON(item, seen);
        seen.delete(value);
    }
}

async function fingerprint(value) {
    const text = JSON.stringify(canonical(value));
    if (!globalThis.crypto?.subtle) {
        // Remote HTTP origins can lack SubtleCrypto. This remains a consistency
        // fingerprint, never an authorization or content-authenticity check.
        let hash = 0x811c9dc5;
        for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 0x01000193) >>> 0;
        return 'fnv1a32:' + hash.toString(16).padStart(8, '0');
    }
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return 'sha256:' + [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, '0')).join('');
}

function pageCollector(offset, limit) {
    return {
        rows: [], total: 0,
        add(create) {
            const index = this.total++;
            if (index >= offset && this.rows.length < limit) this.rows.push(create());
        },
        result() {
            const end = offset + this.rows.length;
            return {items: this.rows, total: this.total, offset, limit,
                nextOffset: end < this.total ? end : null};
        }
    };
}

function atomFilter(app, request) {
    const sets = ['indices', 'labels', 'elements'].map(key => {
        if (request[key] !== undefined && !Array.isArray(request[key])) throw fail(`${key} must be an array.`);
        return new Set(request[key] || []);
    });
    const data = app.state.atoms || {};
    return index => (!sets[0].size || sets[0].has(index))
        && (!sets[1].size || sets[1].has(data.symbols?.[index]))
        && (!sets[2].size || sets[2].has(data.chemical_symbols?.[index]));
}

function projection(renderer, effective, width, height) {
    const setup = renderer.exportCameraSetup(width, height, {...effective.options, camera: effective.camera});
    const camera = setup.camera;
    const frustum = new THREE.Frustum().setFromProjectionMatrix(
        new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
    );
    return {
        camera, frustum,
        point(world) {
            const ndc = world.clone().project(camera);
            return {pixels: [finite((ndc.x + 1) * width / 2, 3), finite((1 - ndc.y) * height / 2, 3)],
                depthNdc: finite(ndc.z), depthAngstrom: finite(-world.clone().applyMatrix4(camera.matrixWorldInverse).z)};
        }
    };
}

function relevantTask(app, name) {
    const d = app.state.display;
    // RDF is a separate analysis panel, not part of the rendered 3D figure.
    if (name === 'calculateRdf') return false;
    if (name.startsWith('renderVolumetricPlane:')) {
        const id = name.slice('renderVolumetricPlane:'.length);
        return app.volumetricPlanes().some(p => p.id === id && p.visible);
    }
    if (/VolumetricSurface/.test(name)) return d.showVolumetric;
    if (/VolumetricPlane/.test(name)) return app.volumetricPlanes().some(p => p.visible);
    if (/AtomColorScale/.test(name)) return d.atomColorScaleEnabled;
    if (/ForceVectors/.test(name)) return d.showForceVectors;
    if (/Displacement/.test(name)) return d.showDisplacements;
    return true;
}

function holdSceneInput() {
    const preventInput = event => {
        if (event.isTrusted) { event.preventDefault(); event.stopImmediatePropagation(); }
    };
    const names = ['pointerdown', 'mousedown', 'keydown', 'wheel', 'click', 'input', 'change'];
    names.forEach(type => document.addEventListener(type, preventInput, {capture: true, passive: false}));
    return () => names.forEach(type => document.removeEventListener(type, preventInput, true));
}

export function installAIScene(App) {
    const proto = App.prototype;

    for (const [method, field, path] of [
        ['setVolumetricPlaneSelection', 'selectedVolumetricPlanes', 'interaction.planeIds'],
        ['setSunSelected', 'sunSelected', 'interaction.lightHandle'],
        ['setRenderAreaSelected', 'renderAreaSelected', 'interaction.renderAreaSelected']
    ]) {
        const original = proto[method];
        const signature = value => JSON.stringify(value instanceof Set ? [...value].sort() : (value ?? null));
        proto[method] = function (...args) {
            const before = signature(this.state[field]);
            const result = original.apply(this, args);
            if (signature(this.state[field]) !== before) this.scheduleCollaborationEvent({
                source: this.currentCollaborationActor(), categories: ['selection'],
                changedPaths: [path], summary: 'Scene selection changed.'});
            return result;
        };
    }

    // Observe the same asynchronous work launched by the GUI and semantic API.
    // Keeping the returned rejection intact preserves each caller's error handling.
    for (const name of TRACKED) {
        const original = proto[name];
        if (typeof original !== 'function') continue;
        proto[name] = function (...args) {
            this.aiSceneTasks ||= new Map();
            this.aiSceneFailures ||= new Map();
            this.aiSceneTaskGeneration ||= new Map();
            const taskName = name === 'renderVolumetricPlane' ? `${name}:${args[0]?.id || ''}` : name;
            const token = Symbol(taskName);
            this.aiSceneTaskGeneration.set(taskName, token);
            let result;
            try { result = original.apply(this, args); }
            catch (error) { result = Promise.reject(error); }
            const pending = Promise.resolve(result).then(value => {
                if (this.aiSceneTaskGeneration.get(taskName) === token) {
                    const failures = name === 'renderAllVolumetricPlanes' && Array.isArray(value)
                        ? value.filter(item => item.status === 'rejected') : [];
                    if (failures.length) this.aiSceneFailures.set(taskName, failures.map(item => String(item.reason?.message || item.reason)).join('; ').slice(0,500));
                    else this.aiSceneFailures.delete(taskName);
                }
                return value;
            }, error => {
                if (this.aiSceneTaskGeneration.get(taskName) === token) {
                    this.aiSceneFailures.set(taskName, String(error?.message || error).slice(0, 500));
                }
                throw error;
            }).finally(() => this.aiSceneTasks.delete(token));
            this.aiSceneTasks.set(token, {name: taskName, pending});
            return pending;
        };
    }

    proto.aiInteractionSnapshot = function () {
        return {
            atomReferences: this.aiSelectionSnapshot({includePositions: false}),
            planeIds: [...this.state.selectedVolumetricPlanes].sort(),
            lightHandle: this.state.sunSelected || null,
            renderAreaSelected: Boolean(this.state.renderAreaSelected),
            selectionAppearanceForPublication: 'neutral-plane-borders; no selection outlines',
        };
    };

    proto.aiSceneReadiness = function () {
        const tasks = [...(this.aiSceneTasks?.values() || [])].map(v => v.name);
        const pending = tasks.filter(name => relevantTask(this, name));
        for (const key of ['displacementRefreshTimer', 'volumetricPlanePreviewTimer', 'volumetricPlaneSettledTimer']) {
            if (this.state[key] != null) pending.push(key);
        }
        if (this.atomColorScaleRuntime.refreshRequest != null) pending.push('atom-colorscale-scheduled');
        const errors = [...(this.aiSceneFailures?.entries() || [])]
            .filter(([name]) => relevantTask(this, name)).map(([task, message]) => ({task, message}));
        const d = this.state.display;
        const frame = Number(this.state.atoms?.metadata?.current_frame || 0);
        const stale = [];
        if (d.showVolumetric && (!this.state.volumetricSurfaceSummary || !this.renderer.volumetricGroup.visible)) stale.push('isosurface');
        if (d.atomColorScaleEnabled && this.atomColorScaleRuntime.renderedFrame !== frame) stale.push('atom-colorscale');
        if (d.showForceVectors && this.forceVectorRuntime.renderedFrame !== frame) stale.push('force-vectors');
        if (d.showDisplacements && this.state.displacementStats?.current_frame !== frame) stale.push('displacements');
        for (const plane of this.volumetricPlanes().filter(p => p.visible && !this.state.volumetricFrameHiddenPlaneIds.has(p.id))) {
            if (!this.renderer.volumetricPlanes.has(plane.id)) stale.push(`plane:${plane.id}`);
        }
        const playback = this.aiPlaybackSnapshot();
        return {ready: pending.length === 0 && errors.length === 0 && stale.length === 0 && !playback.playing && !this.state.isRelaxing,
            frame, pending: [...new Set(pending)], stale, errors,
            nonBlockingWork: {
                pending: [...new Set(tasks.filter(name => !relevantTask(this, name)))],
                errors: [...(this.aiSceneFailures?.entries() || [])]
                    .filter(([name]) => !relevantTask(this, name)).map(([task, message]) => ({task, message}))
            },
            playing: playback.playing, relaxing: Boolean(this.state.isRelaxing),
            videoExportActive: Boolean(this.state.videoExportId), transactionActive: Boolean(this.aiSceneTransactionActive)};
    };

    proto.aiWaitForScene = async function ({wait = true, timeoutMs = 15000} = {}) {
        const timeout = integer(timeoutMs, 15000, 1, 30000, 'timeoutMs');
        if (wait === false) return this.aiSceneReadiness();
        const deadline = performance.now() + timeout;
        let stable = 0;
        while (true) {
            const state = this.aiSceneReadiness();
            if (state.playing || state.relaxing || state.errors.length) return state;
            if (state.ready) stable += 1;
            else stable = 0;
            // Allow scheduled frame/display refreshes to register their work.
            if (stable >= 2) return state;
            if (performance.now() >= deadline) return {...state, timedOut: true};
            await new Promise(resolve => setTimeout(resolve, Math.min(40, Math.max(1, deadline - performance.now()))));
        }
    };

    proto.aiSceneSnapshot = async function (request = {}) {
        const sections = new Set(request.sections || []);
        if ([...sections].some(s => !['atoms', 'bonds', 'planes', 'analysis', 'preview'].includes(s))) throw fail('Unknown scene section.');
        const limit = integer(request.limit, 64, 1, 256, 'limit');
        const profile = this.currentImageExportProfile();
        const width = integer(request.width, profile.width || 1920, 64, 8192, 'width');
        const height = integer(request.height, profile.height || 1080, 64, 8192, 'height');
        const readiness = await this.aiWaitForScene(request);
        this.flushVisualHistoryCommit();
        await this.flushCollaborationEvents();
        const revision = this.collaborationRevision;
        const r = this.renderer;
        const d = this.state.display;
        const atoms = this.state.atoms || {};
        const interaction = this.aiInteractionSnapshot();
        const effective = this.aiEffectiveRenderSnapshot({width, height, cameraSource: request.cameraSource || 'auto'});
        const view = projection(r, effective, width, height);
        const filter = atomFilter(this, request);
        const selectedIndices = request.indices?.length ? [...request.indices].sort((a,b) => a-b)
            : Array.from({length: atoms.positions?.length || 0}, (_, i) => i);
        const candidates = selectedIndices.filter(index => index >= 0 && index < (atoms.positions?.length || 0) && filter(index));
        const visibleOnly = request.visibleOnly !== false;
        const cell = r.hasValidCell() ? r.cellBasis() : null;
        const repeats = cell ? (d.supercell || [1, 1, 1]) : [1, 1, 1];
        const offsets = repeats.map(n => r.supercellAxisOffsets(n));
        const replicaCount = repeats.reduce((a,b) => a*b,1);
        const candidatePairs = sections.has('bonds')
            ? (d.bondMode === 'manual' ? (d.manualBondPairs || []) : (r.bondPairs || [])).filter(([i,j]) => filter(i) && filter(j)) : [];
        if ((sections.has('atoms') && candidates.length * replicaCount > 200000)
            || (sections.has('bonds') && candidatePairs.length * replicaCount > 200000)) {
            throw fail('Geometry inspection would scan over 200,000 references. Filter by indices/elements/labels or reduce display repetitions; summary inspection remains available.', 'scene_too_large');
        }
        const data = {
            protocol: 'v_ase.scene.v1', documentId: this.sessionId, document: this.workspaceDocumentTitle(),
            revision, frame: Number(atoms.metadata?.current_frame || 0), frameCount: this.loadedFrameCount(),
            units: {length: 'angstrom', screen: 'output pixels; top-left origin', angle: 'degree'},
            readiness, render: effective,
            display: {atomMode: r.atomDisplayMode(), atomRadiusScale: d.atomRadiusScale,
                showBonds: Boolean(d.showBonds), bondMode: d.bondMode,
                configuredManualEdgeCount: d.manualBondPairs?.length || 0,
                candidateBaseEdgeCount: r.bondPairs?.length || 0,
                renderedBaseEdgeCount: d.showBonds && r.bondGroup.visible ? (r.bondPairs?.length || 0) : 0,
                background: d.viewportBackground, lighting: d.lightingMode,
                showCell: Boolean(d.showCell), showAxes: Boolean(d.showAxes), showGrid: Boolean(d.showGrid),
                showScientificOverlays: d.showOverlays !== false,
                repetitions: [...repeats], visualTranslationAngstrom: vector(r.visualTranslationVector())},
            counts: {baseAtoms: atoms.positions?.length || 0, configuredPlanes: this.volumetricPlanes().length},
            interaction: {...interaction, atomReferences: interaction.atomReferences.slice(0, limit),
                atomSelectionCount: interaction.atomReferences.length,
                planeIds: interaction.planeIds.slice(0, limit), planeSelectionCount: interaction.planeIds.length},
            visibilityDefinition: 'Enabled geometry intersecting the output camera frustum. Occlusion and transparent-surface compositing require the final render.',
            geometryScope: {baseAndPeriodicDisplay: true,
                commensuratePreviewActive: Boolean(this.state.commensurateProposal),
                previewDetails: r.commensurateSupercellPreview ? 'Request section preview for the displayed host/guest rows; these are not base-atom references.' : null},
            guides: {scene: 'vase_read_guide(topic="scene")', physicalData: 'vase_describe(profile="structure")'},
        };
        if (sections.has('atoms')) {
            const rows = pageCollector(integer(request.atomOffset, 0, 0, Number.MAX_SAFE_INTEGER, 'atomOffset'), limit);
            for (const ix of offsets[0]) for (const iy of offsets[1]) for (const iz of offsets[2]) {
                const offset = [ix, iy, iz];
                const base = !offset.some(Boolean);
                const shift = cell ? r.cellOffsetVector(offset, cell) : new THREE.Vector3();
                for (const index of candidates) {
                    const world = r.toVisualAtomPosition(r.getAtomPosition(index).add(shift));
                    const radius = r.atomVisualRadius(index);
                    const enabled = (base ? r.atomMeshes.visible : r.supercellGroup.visible)
                        && r.atomReferenceVisible(index, base ? null : offset)
                        && (r.atomMeshByIndex.get(index)?.visible !== false) && r.atomVisualOpacity(index) > 0;
                    const intersectsFrustum = view.frustum.intersectsSphere(new THREE.Sphere(world, radius));
                    if (visibleOnly && (!enabled || !intersectsFrustum)) continue;
                    rows.add(() => ({reference: {index, cellOffset: offset}, label: atoms.symbols?.[index],
                        element: atoms.chemical_symbols?.[index], positionAngstrom: vector(world),
                        ...view.point(world), radiusAngstrom: finite(radius),
                        appearance: {color: r.atomVisualColor(index, r.customColors?.[index]),
                            material: r.atomMaterialPreset(index), opacity: r.atomVisualOpacity(index)},
                        enabled, intersectsFrustum, occlusion: 'not-tested'}));
                }
            }
            data.atoms = rows.result();
        }
        if (sections.has('bonds')) {
            const rows = pageCollector(integer(request.bondOffset, 0, 0, Number.MAX_SAFE_INTEGER, 'bondOffset'), limit);
            const pairs = candidatePairs;
            const rendered = new Set((r.bondPairs || []).map(([i, j]) => `${Math.min(i,j)}:${Math.max(i,j)}`));
            for (const ix of offsets[0]) for (const iy of offsets[1]) for (const iz of offsets[2]) {
                const offset = [ix, iy, iz];
                const shift = cell ? r.cellOffsetVector(offset, cell) : new THREE.Vector3();
                for (const [i, j] of pairs) {
                    if (!filter(i) || !filter(j)) continue;
                    const periodic = d.showPeriodicBonds ? r.minimumImageBondData(i, j).imageOffset : [0, 0, 0];
                    const endOffset = offset.map((v, axis) => v + periodic[axis]);
                    const start = r.toVisualAtomPosition(r.getAtomPosition(i).add(shift));
                    const end = start.clone().add(r.bondDelta(i, j));
                    const appearance = r.bondAppearance(i, j);
                    const enabled = (offset.some(Boolean) ? r.supercellGroup.visible : r.bondGroup.visible)
                        && Boolean(d.showBonds) && rendered.has(`${Math.min(i,j)}:${Math.max(i,j)}`)
                        && r.atomReferenceVisible(i, offset.some(Boolean) ? offset : null)
                        && r.atomReferenceVisible(j, endOffset.some(Boolean) ? endOffset : null);
                    const intersectsFrustum = view.frustum.intersectsBox(new THREE.Box3().setFromPoints([start, end]).expandByScalar(appearance.thickness));
                    if (visibleOnly && (!enabled || !intersectsFrustum)) continue;
                    rows.add(() => ({endpoints: [{index: i, cellOffset: offset}, {index: j, cellOffset: endOffset}],
                        positionAngstrom: [vector(start), vector(end)], screen: [view.point(start), view.point(end)],
                        segments: r.bondSegmentsForPair(i, j).map(segment => ({from: segment.t0, to: segment.t1,
                            ...segment.appearance, color: new THREE.Color(r.bondSegmentColor(segment)).getStyle()})),
                        enabled, intersectsFrustum, occlusion: 'not-tested'}));
                }
            }
            // Bridge bonds between displayed cells are additional rendered
            // instances, even when ordinary periodic-image bonds are disabled.
            for (const record of r.supercellBridgeBondRecords || []) {
                const {i, j, imageOffset} = record;
                if (!filter(i) || !filter(j)) continue;
                for (const offset of r.supercellBridgeStartOffsets(imageOffset, repeats)) {
                    const endOffset = offset.map((v, axis) => v + imageOffset[axis]);
                    const start = r.toVisualAtomPosition(r.getAtomPosition(i).add(r.cellOffsetVector(offset)));
                    const end = start.clone().add(r.bondDeltaInto(new THREE.Vector3(), i, j, null, imageOffset));
                    const appearance = r.bondAppearance(i, j);
                    const enabled = r.supercellGroup.visible && Boolean(d.showBonds) && r.atomReferenceVisible(i, offset.some(Boolean) ? offset : null)
                        && r.atomReferenceVisible(j, endOffset.some(Boolean) ? endOffset : null);
                    const intersectsFrustum = view.frustum.intersectsBox(new THREE.Box3().setFromPoints([start,end]).expandByScalar(appearance.thickness));
                    if (visibleOnly && (!enabled || !intersectsFrustum)) continue;
                    rows.add(() => ({endpoints: [{index:i,cellOffset:offset},{index:j,cellOffset:endOffset}],
                        bridge: true, positionAngstrom: [vector(start),vector(end)], screen:[view.point(start),view.point(end)],
                        segments:r.bondSegmentsForPair(i,j).map(segment => ({from:segment.t0,to:segment.t1,
                            ...segment.appearance,color:new THREE.Color(r.bondSegmentColor(segment)).getStyle()})),
                        enabled,intersectsFrustum,occlusion:'not-tested'}));
                }
            }
            data.bonds = rows.result();
        }
        if (sections.has('planes')) {
            const rows = pageCollector(integer(request.planeOffset, 0, 0, Number.MAX_SAFE_INTEGER, 'planeOffset'), limit);
            r.scene.updateMatrixWorld(true);
            for (const plane of this.volumetricPlanes()) {
                const record = r.volumetricPlanes.get(plane.id);
                const enabled = Boolean(plane.visible && record?.group.visible && r.volumetricPlaneGroup.visible)
                    && !this.state.volumetricFrameHiddenPlaneIds.has(plane.id);
                const bounds = record ? new THREE.Box3().setFromObject(record.group) : null;
                const intersectsFrustum = Boolean(bounds && !bounds.isEmpty() && view.frustum.intersectsBox(bounds));
                if (visibleOnly && (!enabled || !intersectsFrustum)) continue;
                rows.add(() => {
                    const geometry = record?.perimeterGeometry?.getAttribute('position');
                    const vertices = [];
                    if (geometry) for (let i = 0; i < Math.min(32, geometry.count); i++) {
                        const p = new THREE.Vector3().fromBufferAttribute(geometry, i).applyMatrix4(record.perimeter.matrixWorld);
                        vertices.push({...view.point(p), positionAngstrom: vector(p)});
                    }
                    return {...copy(plane), hiddenForCurrentFrame: this.state.volumetricFrameHiddenPlaneIds.has(plane.id),
                        enabled, intersectsFrustum, occlusion: 'not-tested',
                        selected: this.state.selectedVolumetricPlanes.has(plane.id),
                        viewportPerimeter: record ? {color: '#' + record.perimeterMaterial.color.getHexString(), opacity: record.perimeterMaterial.opacity} : null,
                        publicationPerimeter: {color: '#89d9cc', opacity: 0.72},
                        screenPerimeter: vertices, perimeterTruncated: (geometry?.count || 0) > 32};
                });
            }
            data.planes = rows.result();
        }
        const preview = r.commensurateSupercellPreview?.preview;
        if (sections.has('preview')) {
            if (!preview) data.preview = null;
            else {
                if ((preview.positions?.length || 0) > 200000) throw fail('Commensurate preview exceeds the bounded geometry limit.', 'scene_too_large');
                const rows = pageCollector(integer(request.previewOffset,0,0,Number.MAX_SAFE_INTEGER,'previewOffset'),limit);
                const bonds = pageCollector(integer(request.previewBondOffset,0,0,Number.MAX_SAFE_INTEGER,'previewBondOffset'),limit);
                const matches = row => (!request.elements?.length || request.elements.includes(r.commensuratePreviewChemicalSymbol(preview,row)))
                    && (!request.labels?.length || request.labels.includes(r.commensuratePreviewLabel(preview,row)))
                    && (!request.indices?.length || request.indices.includes(preview.atom_indices?.[row]))
                    && (!request.components?.length || request.components.includes(preview.components?.[row] || 'lattice'));
                const ref = row => ({kind:'commensurate-preview',row,
                    component:preview.components?.[row] || 'lattice',sourceIndex:preview.atom_indices?.[row]});
                (preview.positions || []).forEach((position,row) => {
                    if (!matches(row)) return;
                    const world = r.toVisualAtomPosition(position);
                    const radius = r.commensuratePreviewRadius(preview,row);
                    const enabled = r.commensurateSupercellGroup.visible && r.commensuratePreviewRowVisible(preview,row)
                        && r.commensuratePreviewOpacity(preview,row) > 0;
                    const intersectsFrustum = view.frustum.intersectsSphere(new THREE.Sphere(world,radius));
                    if (visibleOnly && (!enabled || !intersectsFrustum)) return;
                    rows.add(() => ({reference:ref(row),label:r.commensuratePreviewLabel(preview,row),
                        element:r.commensuratePreviewChemicalSymbol(preview,row),core:preview.core_mask?.[row] !== false,
                        positionAngstrom:vector(world),...view.point(world),radiusAngstrom:finite(radius),
                        appearance:{color:r.commensuratePreviewColor(preview,row),material:r.commensuratePreviewMaterial(preview,row),
                            opacity:r.commensuratePreviewOpacity(preview,row)},enabled,intersectsFrustum,occlusion:'not-tested'}));
                });
                for (const [i,j] of r.commensuratePreviewBondPairs(preview)) {
                    if (!matches(i) || !matches(j)) continue;
                    const start=r.toVisualAtomPosition(preview.positions[i]),end=r.toVisualAtomPosition(preview.positions[j]);
                    const enabled=r.commensurateSupercellGroup.visible && Boolean(d.showBonds);
                    const intersectsFrustum=view.frustum.intersectsBox(new THREE.Box3().setFromPoints([start,end]).expandByScalar(r.bondThickness()));
                    if (visibleOnly && (!enabled || !intersectsFrustum)) continue;
                    bonds.add(() => ({endpoints:[ref(i),ref(j)],positionAngstrom:[vector(start),vector(end)],
                        screen:[view.point(start),view.point(end)],appearance:{style:r.effectiveBondStyle(),
                            thickness:r.bondThickness(),material:'standard',opacity:1,
                            colors:d.bondColorMode === 'custom' ? [d.bondCustomColor]
                                : [r.commensuratePreviewColor(preview,i),r.commensuratePreviewColor(preview,j)]},
                        enabled,intersectsFrustum,occlusion:'not-tested'}));
                }
                data.preview={cell:copy(preview.cell),commonCell:copy(preview.common_cell),
                    hostCell:copy(preview.host_cell),guestCell:copy(preview.guest_cell),
                    atoms:rows.result(),bonds:bonds.result(),materialized:false};
            }
        }
        if (sections.has('analysis')) {
            data.analysis = {
                volumeCount: this.volumetricDatasets().length,
                volumesTruncated: this.volumetricDatasets().length > limit,
                volumes: this.volumetricDatasets().map(v => ({id: v.id, name: v.name, quantity: v.quantity,
                    units: v.units, shape: v.shape || v.grid_shape, minimum: v.minimum, maximum: v.maximum})).slice(0, limit),
                surface: copy(this.state.volumetricSurfaceSummary),
                colorscale: {enabled: d.atomColorScaleEnabled, field: d.atomColorScaleField,
                    map: d.atomColorScaleMap, minimum: d.atomColorScaleMin, maximum: d.atomColorScaleMax,
                    frame: this.atomColorScaleRuntime.renderedFrame},
                displacement: this.state.displacementStats ? {frame: this.state.displacementStats.current_frame,
                    referenceFrame: d.displacementReferenceFrame, minimumImage: Boolean(d.displacementMic),
                    scale: d.displacementScale, visible: Boolean(d.showDisplacements)} : null,
                rdf: this.state.rdfResult ? {bins: this.state.rdfResult.bins, cutoff: this.state.rdfResult.cutoff,
                    frame: this.state.rdfResult.frame_index, normalization: this.state.rdfResult.normalization} : null,
                commensurate: {candidateCount: this.state.commensurateSearch?.candidates?.length || 0,
                    proposalPending: Boolean(this.state.commensurateProposal)},
                queries: ['atom-scalar-catalog', 'frame-properties', 'force-vectors'],
            };
        }
        data.sceneFingerprint = await fingerprint({documentId: data.documentId, revision, frame: data.frame,
            display: d, render: effective, interaction, positions: r.currentPositions(),
            surface: this.state.volumetricSurfaceSummary, preview, readiness});
        if (revision !== this.collaborationRevision) throw fail('Scene changed during inspection. Read another snapshot.', 'conflict');
        if (request.expectedSceneFingerprint && request.expectedSceneFingerprint !== data.sceneFingerprint) {
            throw fail('Scene changed while paging. Start from offset 0.', 'conflict');
        }
        return data;
    };

    proto.aiSceneStateForRestore = function () {
        const camera = this.renderer.camera;
        return {visual: this.visualHistorySnapshot(), frame: Number(this.state.atoms?.metadata?.current_frame || 0),
            camera: copy(this.cameraSettingsSnapshot()), interaction: this.aiInteractionSnapshot(),
            cameraRuntime: {position: camera.position.toArray(), quaternion: camera.quaternion.toArray(),
                up: camera.up.toArray(), target: this.renderer.controls.target.toArray(),
                values: Object.fromEntries(['zoom', 'near', 'far', 'aspect', 'fov', 'left', 'right', 'top', 'bottom']
                    .filter(key => Number.isFinite(camera[key])).map(key => [key, camera[key]]))},
            renderArea: {enabled: Boolean(this.state.exportPreviewEnabled), followViewport: Boolean(this.state.exportPreviewFollowViewport),
                camera: copy(this.state.exportPreviewCamera)}};
    };

    proto.aiRestoreCameraRuntime = function (saved) {
        if (!saved) return;
        const camera = this.renderer.camera;
        Object.assign(camera, saved.values);
        camera.position.fromArray(saved.position);
        camera.quaternion.fromArray(saved.quaternion);
        camera.up.fromArray(saved.up);
        this.renderer.controls.target.fromArray(saved.target);
        camera.updateProjectionMatrix();
        camera.updateMatrixWorld(true);
        this.renderer.requestRender();
    };

    proto.aiRestoreSceneState = async function (snapshot) {
        const previous = this.historyReplay;
        this.historyReplay = true;
        try {
            this.aiSceneFailures?.clear();
            this.state.volumetricRequestToken += 1;
            for (const [id, token] of this.state.volumetricPlaneRequestTokens) this.state.volumetricPlaneRequestTokens.set(id, token + 1);
            this.atomColorScaleRuntime.requestToken += 1;
            this.forceVectorRuntime.requestToken += 1;
            this.state.displacementRequestToken += 1;
            if (snapshot.frame !== Number(this.state.atoms?.metadata?.current_frame || 0)) await this.loadFrame(snapshot.frame);
            this.applyVisualHistorySnapshot(snapshot.visual);
            this.applyCameraSettings(snapshot.camera, {syncScale: false});
            this.aiRestoreCameraRuntime(snapshot.cameraRuntime);
            this.state.exportPreviewEnabled = snapshot.renderArea.enabled;
            this.state.exportPreviewFollowViewport = snapshot.renderArea.followViewport;
            this.state.exportPreviewCamera = copy(snapshot.renderArea.camera);
            this.clearAtomSelection();
            for (const ref of snapshot.interaction.atomReferences) this.addSelectionReference(ref);
            this.setVolumetricPlaneSelection(snapshot.interaction.planeIds, {update: false});
            this.setSunSelected(snapshot.interaction.lightHandle, {update: false});
            this.setRenderAreaSelected(snapshot.interaction.renderAreaSelected, {update: false});
            this.updateSelectionVisuals();
            this.syncImageExportPreview();
            this.updateUI();
            const readiness = await this.aiWaitForScene();
            if (!readiness.ready) throw fail('Scene restoration did not settle. Inspect readiness before editing.', 'rollback_failed', 'unknown');
            this.resetVisualHistoryBaseline();
        } finally { this.historyReplay = previous; }
    };

    proto.aiSelectVolumetricPlanes = function ({planeIds, clearAtoms = false, clearGizmos = false}) {
        const available = new Set(this.volumetricPlanes().map(p => p.id));
        if (!Array.isArray(planeIds) || planeIds.some(id => typeof id !== 'string' || !available.has(id))) {
            throw fail('planeIds must contain existing plane IDs; use [] to deselect.');
        }
        if (clearAtoms) this.clearAtomSelection();
        if (clearGizmos) {
            this.setSunSelected(false, {update: false});
            this.setRenderAreaSelected(false, {update: false});
        }
        this.setVolumetricPlaneSelection(planeIds);
        this.updateSelectionVisuals();
    };

    proto.aiApplyScene = async function (operation, guards = {}) {
        const {name, ...request} = operation;
        requireFiniteJSON(request);
        // The validator is shared with typed tools; direct JS/CLI calls get the
        // same closed schema before any state is changed.
        const validation = await fetch('/api/ai/validate-scene-patch', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request)});
        if (!validation.ok) {
            const detail = await validation.json();
            throw fail(typeof detail.detail === 'string' ? detail.detail : JSON.stringify(detail.detail));
        }
        const patch = copy(operation.patch);
        if (!plain(patch) || Object.keys(patch).some(key => !PATCH_FIELDS.has(key))) throw fail('Invalid scene patch.');
        const readiness = await this.aiWaitForScene({timeoutMs: operation.timeoutMs});
        if (!readiness.ready || readiness.videoExportActive) throw fail('Pause playback/relaxation and settle the scene before applying a visual transaction.', 'scene_not_ready');
        // Validation/readiness may yield to a human event. Recheck immediately
        // before preparing and locking the transaction.
        this.flushVisualHistoryCommit();
        await this.flushCollaborationEvents();
        if (guards.expectedDocumentId !== this.sessionId || guards.expectedRevision !== this.collaborationRevision) {
            throw fail('The document or revision changed before the scene transaction. Inspect the current scene.', 'conflict');
        }
        if (this.addAtomsSessionActive() || this.state.registryRelaxation) {
            throw fail('Finish the active insertion/registry session before changing a scene transaction.', 'scene_not_ready');
        }
        if (this.transform?.mode && this.transform.mode !== 'IDLE') throw fail('Finish the active transform before a scene transaction.', 'scene_not_ready');
        const count = this.state.atoms?.positions?.length || 0;
        if (patch.frame !== undefined && (patch.frame < 0 || patch.frame >= this.loadedFrameCount())) throw fail('Scene frame is outside the loaded trajectory.');
        const indices = [...(patch.selection?.indices || []), ...(patch.selection?.references || []).map(r => r.index),
            ...(patch.display?.manualBondPairs || []).flat()];
        if (patch.frame === undefined && indices.some(i => !Number.isInteger(i) || i < 0 || i >= count)) throw fail('Scene patch contains an invalid atom index.');
        if (patch.clearSelections && (patch.selection || patch.planeSelection)) throw fail('Use clearSelections alone or supply explicit selection fields.');
        if (patch.planeSelection?.planeIds.length && patch.selection) {
            throw fail('Selecting planes follows the GUI selection rules and clears atoms. Supply only one selection target.');
        }
        if (patch.display) {
            for (const key of MAP_FIELDS) if (patch.display[key] && operation.mapMode !== 'replace') {
                const existing = copy(this.state.display[key] || {});
                for (const [entry, value] of Object.entries(patch.display[key])) {
                    existing[entry] = plain(value) && plain(existing[entry]) ? {...existing[entry], ...value} : value;
                }
                patch.display[key] = existing;
            }
            const datasets = new Set(this.volumetricDatasets().map(v => v.id));
            if (patch.display.volumetricDatasetId && !datasets.has(patch.display.volumetricDatasetId)) throw fail('Unknown scalar dataset ID.');
            if (patch.display.volumetricPlanes?.some(p => !datasets.has(p.datasetId))) throw fail('Every plane must reference an existing scalar dataset.');
        }
        const planeIds = new Set((patch.display?.volumetricPlanes || this.volumetricPlanes()).map(p => p.id));
        if (patch.planeSelection?.planeIds.some(id => !planeIds.has(id))) throw fail('Plane selection references an unknown plane.');
        if (patch.renderArea?.camera && !this.normalizedCameraSettings(patch.renderArea.camera)) throw fail('Invalid Render Area camera.');
        const before = this.aiSceneStateForRestore();
        const oldReplay = this.historyReplay;
        this.historyReplay = true;
        this.aiSceneTransactionActive = true;
        const releaseInput = holdSceneInput();
        document.body.dataset.sceneUpdating = 'true';
        try {
            const {planeSelection, clearSelections, display, quality, frame, ...controls} = patch;
            if (frame !== undefined) await this.loadFrame(frame);
            const targetCount = this.state.atoms?.positions?.length || 0;
            if (indices.some(i => !Number.isInteger(i) || i < 0 || i >= targetCount)) throw fail('Scene indices must belong to the requested target frame.');
            if (display || quality) {
                const visual = this.visualHistorySnapshot();
                // Preserve the complete image profile: applyDesignSettings also
                // restores export settings, even for a small display change.
                this.applyDesignSettings({...visual,
                    display: {...copy(this.state.display), ...(display || {}), ...(quality || {})},
                    ...(quality || {}), camera: before.camera, renderArea: before.renderArea});
                // Saved visual presets normalize orthographic zoom into their
                // scale. A small style edit must preserve the live camera too.
                if (display?.atomicScalePixelsPerAngstrom === undefined) {
                    this.aiRestoreCameraRuntime(before.cameraRuntime);
                }
                // The preset loader synchronizes export cameras while its
                // temporary normalized viewport is active. Restore the saved
                // export state before applying any explicitly requested camera.
                this.state.imageExportProfile = copy(visual.imageExportProfile);
                this.state.exportPreviewCamera = copy(before.renderArea.camera);
                this.state.exportPreviewFollowViewport = before.renderArea.followViewport;
                this.state.exportPreviewEnabled = before.renderArea.enabled;
            }
            await this.aiApply({...controls, responseProfile: 'summary'});
            if (clearSelections) {
                this.clearAtomSelection();
                this.aiSelectVolumetricPlanes({planeIds: [], clearGizmos: true});
            } else if (planeSelection) this.aiSelectVolumetricPlanes(planeSelection);
            const settled = await this.aiWaitForScene({timeoutMs: operation.timeoutMs});
            if (!settled.ready) throw fail('Scene generation did not settle. Restoring the previous scene.', 'scene_not_ready', 'unknown');
            const after = this.aiSceneStateForRestore();
            this.historyReplay = oldReplay;
            if (JSON.stringify(before) !== JSON.stringify(after)) this.recordHistoryAction({kind: 'scene', source: 'agent-scene', before, after});
            this.resetVisualHistoryBaseline();
            const changedScenePaths = this.collaborationChangedPaths(before, after);
            const applied = {};
            for (const key of Object.keys(operation.patch)) {
                if (key === 'display') {
                    applied.display = Object.fromEntries(Object.entries(operation.patch.display).map(([field, value]) => [field,
                        MAP_FIELDS.has(field) && plain(value) && operation.mapMode !== 'replace'
                            ? Object.fromEntries(Object.keys(value).map(entry => [entry, copy(after.visual.display[field]?.[entry])]))
                            : copy(after.visual.display[field])]));
                } else if (key === 'quality') applied.quality = {antiAliasing: after.visual.antiAliasing, sphereQuality: after.visual.sphereQuality};
                else if (['frame','camera','renderArea'].includes(key)) applied[key] = copy(after[key]);
                else applied.interaction = copy(after.interaction);
            }
            const boundedApplied = JSON.stringify(applied).length <= 12000 ? applied
                : {omitted: true, fields: Object.keys(applied), reason: 'Requested state exceeds the 12,000-character receipt limit; inspect a focused scene page.'};
            this.aiLastSceneReceipt = {transaction: {status: 'applied', scientificData: 'not-modified-by-scene-patch', mapMode: operation.mapMode || 'merge'},
                applied: boundedApplied, readiness: {...settled, transactionActive: false}, changedScenePaths,
                changesTruncated: changedScenePaths.length >= 64,
                next: 'Inspect only the relevant scene section if changed paths cannot establish the requested result.'};
        } catch (error) {
            try {
                await this.aiRestoreSceneState(before);
                throw fail(String(error?.message || error), error?.code || 'scene_patch_failed', 'rolled_back');
            } catch (rollback) {
                if (rollback.outcome === 'rolled_back') throw rollback;
                throw fail(`Scene patch failed: ${error.message}. Restoration failed: ${rollback.message}. Inspect the live scene.`, 'rollback_failed', 'unknown');
            }
        } finally {
            this.historyReplay = oldReplay;
            this.aiSceneTransactionActive = false;
            delete document.body.dataset.sceneUpdating;
            releaseInput();
        }
    };

    const schedule = proto.scheduleCollaborationEvent;
    proto.scheduleCollaborationEvent = function (...args) {
        if (this.aiSceneTransactionActive) return;
        return schedule.apply(this, args);
    };

    const render = proto.aiRender;
    proto.aiRender = async function (...args) {
        // Canvas encoding yields before export restores temporary materials.
        // Preserve the inspected scene throughout that interval.
        const releaseInput = holdSceneInput();
        try { return await render.apply(this, args); }
        finally { releaseInput(); }
    };

    proto.aiWithRetryReceipt = async function (command, run) {
        if (!plain(command)) throw fail('An AI control command must be an object.');
        requireFiniteJSON(command);
        if (command.requestId === undefined) return await run();
        if (typeof command.requestId !== 'string' || !command.requestId.length || command.requestId.length > 128) throw fail('requestId must contain 1..128 characters.');
        if (command.expectedDocumentId !== this.sessionId) throw fail('A retry key requires the current expectedDocumentId.', 'conflict');
        this.aiRetryReceipts ||= new Map();
        const signature = JSON.stringify(canonical(command));
        const existing = this.aiRetryReceipts.get(command.requestId);
        if (existing) {
            if (existing.signature !== signature) throw fail('requestId was already used with different arguments.', 'idempotency_conflict');
            if (existing.error) throw fail(existing.error.message, existing.error.code, existing.error.outcome);
            return {...copy(existing.value), retry: {requestId: command.requestId, replayed: true,
                receiptRevision: existing.value?.mutation?.revision, currentRevision: this.collaborationRevision}};
        }
        if (signature.length > 1024 * 1024) throw fail('A keyed command must be smaller than one million characters. Split the task into bounded edits.');
        this.aiRetryReceiptBytes ||= 0;
        while (this.aiRetryReceipts.size >= 128 || this.aiRetryReceiptBytes + signature.length * 2 + 65536 > 8 * 1024 * 1024) {
            const key = this.aiRetryReceipts.keys().next().value;
            if (key === undefined) break;
            this.aiRetryReceiptBytes -= this.aiRetryReceipts.get(key).bytes || 0;
            this.aiRetryReceipts.delete(key);
        }
        const record = {signature, bytes: signature.length * 2};
        this.aiRetryReceipts.set(command.requestId, record);
        this.aiRetryReceiptBytes += record.bytes;
        try {
            const value = await run();
            const serialized = JSON.stringify(value);
            record.value = serialized.length <= 32000 ? copy(value) : {
                protocol: value.protocol, documentId: value.documentId || this.sessionId,
                frame: value.frame, collaboration: value.collaboration, mutation: value.mutation,
                responseCompacted: true, next: 'The mutation is already complete. Inspect the needed current state instead of repeating it.'};
            const receiptBytes = JSON.stringify(record.value).length * 2;
            record.bytes += receiptBytes;
            this.aiRetryReceiptBytes += receiptBytes;
            return {...value, retry: {requestId: command.requestId, replayed: false, retention: 'up-to-128-receipts-and-8-MiB-in-live-document'}};
        } catch (error) {
            const message = String(error?.message || error).slice(0, 2000);
            const conflict = /revision conflict|active document changed/i.test(message);
            record.error = {message, code: error?.code || (conflict ? 'conflict' : 'command_failed'),
                outcome: error?.outcome || (conflict ? 'not_applied' : 'unknown')};
            const errorBytes = JSON.stringify(record.error).length * 2;
            record.bytes += errorBytes;
            this.aiRetryReceiptBytes += errorBytes;
            error.code = record.error.code;
            error.outcome = record.error.outcome;
            throw error;
        }
    };
}
