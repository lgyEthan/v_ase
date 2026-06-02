export class ASEApi {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.baseUrl = window.location.origin && window.location.origin !== 'null'
            ? window.location.origin
            : document.baseURI;
        this.mock = Boolean(window.__V_ASE_MOCK__);
        this.mockState = this.mock ? this.createMockState() : null;
    }

    mockElementVisual(symbol) {
        const table = {
            H: { color: '#FFFFFF', radius: 0.2759 },
            C: { color: '#909090', radius: 0.6764 },
            N: { color: '#2F50F8', radius: 0.6319 },
            O: { color: '#FF0D0D', radius: 0.5874 },
            F: { color: '#90DF50', radius: 0.5073 },
            Si: { color: '#EFC79F', radius: 0.9879 },
            S: { color: '#FFFF2F', radius: 0.9345 },
            Na: { color: '#AB5CF1', radius: 1.4774 },
            Cl: { color: '#1FEF1F', radius: 0.9078 }
        };
        return table[symbol] || { color: '#cccccc', radius: 0.75 };
    }

    mockVisualForSymbols(symbols) {
        const entries = symbols.map(symbol => this.mockElementVisual(symbol));
        return {
            color_source: 'ase.gui.view.View.colors using ase.data.colors.jmol_colors',
            radius_source: 'ase.gui.images.Images.get_radii: ase.data.covalent_radii * 0.89',
            colors: entries.map(item => item.color),
            radii: entries.map(item => item.radius),
            covalent_radii: entries.map(item => item.radius),
            radius_scale: 0.89
        };
    }

    createMockAtoms() {
        const symbols = ['O', 'H', 'H'];
        return {
            symbols,
            positions: [
                [0.000, 0.000, 0.000],
                [1.250, 0.750, 0.000],
                [6.750, 0.750, 0.000]
            ],
            cell: [[8, 0, 0], [0, 8, 0], [0, 0, 8]],
            pbc: [true, true, true],
            forces: [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
            tags: [0, 1, 2],
            charges: [0, 0, 0],
            magmoms: [0, 0, 0],
            visual: this.mockVisualForSymbols(symbols),
            constraints: {
                fixed_indices: [0],
                fixed_cartesian: {},
                fixed_line: { "1": [1, 0, 0] },
                fixed_plane: { "2": [0, 0, 1] },
                hookean: [
                    { kind: 'two atoms', indices: [1, 2], threshold: 4.80, spring: 5.0 }
                ]
            },
            metadata: {
                natoms: 3,
                calculator: 'MOCK',
                has_calculator: false,
                energy: null,
                current_frame: 0,
                frame_count: 1,
                custom_colors: {},
                config: {
                    show_cell: true,
                    show_axes: true,
                    show_grid: true,
                    show_bonds: true,
                    apply_constraint: true
                }
            }
        };
    }

    clone(value) {
        if (window.structuredClone) return window.structuredClone(value);
        return JSON.parse(JSON.stringify(value));
    }

    createMockState() {
        const original = this.createMockAtoms();
        return {
            original: this.clone(original),
            atoms: this.clone(original),
            history: [],
            redo: []
        };
    }

    mockResponse(data) {
        return Promise.resolve(this.clone(data));
    }

    mockPushHistory() {
        this.mockState.history.push(this.clone(this.mockState.atoms));
        if (this.mockState.history.length > 50) this.mockState.history.shift();
        this.mockState.redo = [];
    }

    mockApplyPositions(positions, { history = true } = {}) {
        if (history) this.mockPushHistory();
        this.mockState.atoms.positions = positions.map(p => [...p]);
        this.mockState.atoms.metadata.natoms = this.mockState.atoms.positions.length;
        return this.mockResponse(this.mockState.atoms);
    }

    sessionPath(path) {
        if (this.mock) return path.replace('{session_id}', 'mock-session');
        if (!this.sessionId || this.sessionId === 'null') {
            throw new Error("No active v_ase session. Open the viewer through v_ase.view(...).");
        }
        return path.replace('{session_id}', encodeURIComponent(this.sessionId));
    }

    async request(path, options = {}, { expect = 'json', needsSession = true } = {}) {
        if (this.mock) {
            return await this.handleMockRequest(path, options, { expect, needsSession });
        }
        if (window.location.protocol === 'file:') {
            throw new Error("v_ase API is not available from a local file. Start it with v_ase.view(...).");
        }

        const apiPath = needsSession ? this.sessionPath(path) : path;
        const url = new URL(apiPath, this.baseUrl);
        let res;
        try {
            res = await fetch(url, options);
        } catch (err) {
            throw new Error(`Cannot reach v_ase server at ${this.baseUrl}. Restart the viewer session and reload this page.`);
        }

        if (!res.ok) {
            let message = "";
            try {
                const contentType = res.headers.get('content-type') || '';
                if (contentType.includes('application/json')) {
                    const data = await res.json();
                    message = data.detail || data.message || JSON.stringify(data);
                } else {
                    message = await res.text();
                }
            } catch {
                message = "";
            }
            throw new Error(message || `v_ase request failed (${res.status})`);
        }

        if (expect === 'blob') return await res.blob();
        if (expect === 'text') return await res.text();
        return await res.json();
    }

    async handleMockRequest(path, options = {}, { expect = 'json' } = {}) {
        if (path.includes('/api/session/active')) {
            return { session_id: 'mock-session', count: 1 };
        }
        if (path.includes('/api/atoms/')) {
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/constrain/')) {
            const payload = JSON.parse(options.body || '{}');
            return { positions: payload.positions || this.mockState.atoms.positions };
        }
        if (path.includes('/api/apply/')) {
            const payload = JSON.parse(options.body || '{}');
            return await this.mockApplyPositions(payload.positions || this.mockState.atoms.positions);
        }
        if (path.includes('/api/supercell/apply/')) {
            const payload = JSON.parse(options.body || '{}');
            const reps = payload.reps || [1, 1, 1];
            const source = this.clone(this.mockState.atoms);
            const basePositions = payload.positions || source.positions;
            const cell = source.cell || [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
            const symbols = [];
            const positions = [];
            const forces = [];
            const tags = [];
            const charges = [];
            const magmoms = [];
            for (let ix = 0; ix < reps[0]; ix++) {
                for (let iy = 0; iy < reps[1]; iy++) {
                    for (let iz = 0; iz < reps[2]; iz++) {
                        const shift = [
                            cell[0][0] * ix + cell[1][0] * iy + cell[2][0] * iz,
                            cell[0][1] * ix + cell[1][1] * iy + cell[2][1] * iz,
                            cell[0][2] * ix + cell[1][2] * iy + cell[2][2] * iz
                        ];
                        source.symbols.forEach((symbol, idx) => {
                            symbols.push(symbol);
                            const p = basePositions[idx];
                            positions.push([p[0] + shift[0], p[1] + shift[1], p[2] + shift[2]]);
                            forces.push(source.forces?.[idx] ? [...source.forces[idx]] : [0, 0, 0]);
                            tags.push(source.tags?.[idx] ?? 0);
                            charges.push(source.charges?.[idx] ?? 0);
                            magmoms.push(source.magmoms?.[idx] ?? 0);
                        });
                    }
                }
            }
            this.mockPushHistory();
            this.mockState.atoms.symbols = symbols;
            this.mockState.atoms.positions = positions;
            this.mockState.atoms.forces = forces;
            this.mockState.atoms.tags = tags;
            this.mockState.atoms.charges = charges;
            this.mockState.atoms.magmoms = magmoms;
            this.mockState.atoms.visual = this.mockVisualForSymbols(symbols);
            this.mockState.atoms.cell = [
                source.cell[0].map(v => v * reps[0]),
                source.cell[1].map(v => v * reps[1]),
                source.cell[2].map(v => v * reps[2])
            ];
            this.mockState.atoms.metadata.natoms = positions.length;
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/supercell/matrix/')) {
            const payload = JSON.parse(options.body || '{}');
            const matrix = payload.matrix || [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
            const reps = [matrix[0][0] || 1, matrix[1][1] || 1, matrix[2][2] || 1].map(v => Math.max(1, Math.abs(parseInt(v, 10) || 1)));
            return await this.handleMockRequest('/api/supercell/apply/', {
                ...options,
                body: JSON.stringify({ ...payload, reps })
            }, { expect });
        }
        if (path.includes('/api/reset/')) {
            this.mockPushHistory();
            this.mockState.atoms = this.clone(this.mockState.original);
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/reset-coordinates/')) {
            this.mockPushHistory();
            this.mockState.atoms = this.clone(this.mockState.original);
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/settings/save/')) {
            return new Blob([options.body || '{}'], { type: 'application/octet-stream' });
        }
        if (path.includes('/api/settings/load/')) {
            return { schema: 'v_ase.visual_settings.v1', settings: {} };
        }
        if (path.includes('/api/undo/')) {
            if (this.mockState.history.length) {
                this.mockState.redo.push(this.clone(this.mockState.atoms));
                this.mockState.atoms = this.mockState.history.pop();
            }
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/redo/')) {
            if (this.mockState.redo.length) {
                this.mockState.history.push(this.clone(this.mockState.atoms));
                this.mockState.atoms = this.mockState.redo.pop();
            }
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/add/')) {
            const payload = JSON.parse(options.body || '{}');
            const symbols = payload.symbols || [payload.symbol];
            const positions = payload.positions || [payload.position];
            this.mockPushHistory();
            symbols.forEach((symbol, idx) => {
                this.mockState.atoms.symbols.push(symbol);
                this.mockState.atoms.positions.push([...positions[idx]]);
                this.mockState.atoms.forces.push([0, 0, 0]);
                this.mockState.atoms.tags.push(0);
                this.mockState.atoms.charges.push(0);
                this.mockState.atoms.magmoms.push(0);
            });
            this.mockState.atoms.visual = this.mockVisualForSymbols(this.mockState.atoms.symbols);
            this.mockState.atoms.metadata.natoms = this.mockState.atoms.positions.length;
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/delete/')) {
            const payload = JSON.parse(options.body || '{}');
            const deleted = new Set((payload.indices || []).map(Number));
            if (!deleted.size) return await this.mockResponse(this.mockState.atoms);
            const indexMap = new Map();
            let next = 0;
            this.mockState.atoms.symbols.forEach((_, idx) => {
                if (!deleted.has(idx)) indexMap.set(idx, next++);
            });
            this.mockPushHistory();
            const keep = (_, idx) => !deleted.has(idx);
            this.mockState.atoms.symbols = this.mockState.atoms.symbols.filter(keep);
            this.mockState.atoms.positions = this.mockState.atoms.positions.filter(keep);
            this.mockState.atoms.forces = (this.mockState.atoms.forces || []).filter(keep);
            this.mockState.atoms.tags = (this.mockState.atoms.tags || []).filter(keep);
            this.mockState.atoms.charges = (this.mockState.atoms.charges || []).filter(keep);
            this.mockState.atoms.magmoms = (this.mockState.atoms.magmoms || []).filter(keep);
            this.mockState.atoms.visual = this.mockVisualForSymbols(this.mockState.atoms.symbols);
            const constraints = this.mockState.atoms.constraints || {};
            constraints.fixed_indices = (constraints.fixed_indices || [])
                .filter(idx => indexMap.has(idx))
                .map(idx => indexMap.get(idx));
            for (const key of ['fixed_cartesian', 'fixed_line', 'fixed_plane']) {
                const mapped = {};
                Object.entries(constraints[key] || {}).forEach(([idx, value]) => {
                    const oldIndex = Number(idx);
                    if (indexMap.has(oldIndex)) mapped[String(indexMap.get(oldIndex))] = value;
                });
                constraints[key] = mapped;
            }
            constraints.hookean = (constraints.hookean || []).flatMap(item => {
                if (item.kind === 'two atoms' && item.indices?.every(idx => indexMap.has(idx))) {
                    return [{ ...item, indices: item.indices.map(idx => indexMap.get(idx)) }];
                }
                if ((item.kind === 'point' || item.kind === 'plane') && indexMap.has(item.index)) {
                    return [{ ...item, index: indexMap.get(item.index) }];
                }
                return [];
            });
            this.mockState.atoms.metadata.natoms = this.mockState.atoms.positions.length;
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/wrap/')) {
            const payload = JSON.parse(options.body || '{}');
            const positions = payload.positions || this.mockState.atoms.positions;
            const cell = this.mockState.atoms.cell || [];
            const pbc = this.mockState.atoms.pbc || [false, false, false];
            const lengths = [cell[0]?.[0], cell[1]?.[1], cell[2]?.[2]];
            const wrapped = positions.map(pos => pos.map((value, axis) => {
                const length = lengths[axis];
                if (!pbc[axis] || !Number.isFinite(length) || Math.abs(length) < 1e-9) return value;
                return ((value % length) + length) % length;
            }));
            return await this.mockApplyPositions(wrapped);
        }
        if (path.includes('/api/frame/')) {
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/relax/start/')) {
            return { status: 'error', message: 'Mock session has no calculator.' };
        }
        if (path.includes('/api/relax/stop/')) {
            return { status: 'stopped' };
        }
        if (path.includes('/api/export/blender/')) {
            return new Blob(['# v_ase mock Blender script\n'], { type: 'text/x-python' });
        }
        if (expect === 'blob') {
            return new Blob(['v_ase mock export\n'], { type: 'application/octet-stream' });
        }
        if (path.includes('/api/done/') || path.includes('/api/cancel/')) {
            return { status: 'ok' };
        }
        throw new Error(`Unhandled mock ASE API path: ${path}`);
    }

    jsonPost(path, payload = {}) {
        return this.request(path, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
    }

    post(path) {
        return this.request(path, { method: 'POST' });
    }

    async fetchAtoms() {
        return await this.request(`/api/atoms/{session_id}`);
    }

    async fetchActiveSession() {
        const data = await this.request('/api/session/active', {}, { needsSession: false });
        if (!data.session_id) {
            throw new Error(`No active v_ase session (${data.count || 0} sessions found).`);
        }
        return data;
    }

    async applyPositions(positions, applyConstraint = true) {
        return await this.jsonPost(`/api/apply/{session_id}`, { positions, apply_constraint: applyConstraint });
    }

    async getConstrainedPositions(positions, applyConstraint = true) {
        return await this.jsonPost(`/api/constrain/{session_id}`, { positions, apply_constraint: applyConstraint });
    }

    async addAtom(symbol, position) {
        return await this.jsonPost(`/api/add/{session_id}`, { symbol, position });
    }

    async addAtoms(symbols, positions) {
        return await this.jsonPost(`/api/add/{session_id}`, { symbols, positions });
    }

    async deleteAtoms(indices) {
        return await this.jsonPost(`/api/delete/{session_id}`, { indices });
    }

    async undo() {
        return await this.post(`/api/undo/{session_id}`);
    }

    async redo() {
        return await this.post(`/api/redo/{session_id}`);
    }

    async done(positions, applyConstraint = true) {
        const data = await this.jsonPost(`/api/done/{session_id}`, { positions, apply_constraint: applyConstraint });
        window.close();
        return data;
    }

    async cancel() {
        const data = await this.post(`/api/cancel/{session_id}`);
        window.close();
        return data;
    }

    async reset() {
        return await this.post(`/api/reset/{session_id}`);
    }

    async resetCoordinates() {
        return await this.post(`/api/reset-coordinates/{session_id}`);
    }

    async wrap(positions, applyConstraint = true) {
        return await this.jsonPost(`/api/wrap/{session_id}`, { positions, apply_constraint: applyConstraint });
    }

    async applySupercell(positions, reps, applyConstraint = true) {
        return await this.jsonPost(`/api/supercell/apply/{session_id}`, { positions, reps, apply_constraint: applyConstraint });
    }

    async applySupercellMatrix(positions, matrix, applyConstraint = true) {
        return await this.jsonPost(`/api/supercell/matrix/{session_id}`, { positions, matrix, apply_constraint: applyConstraint });
    }

    async setFrame(index) {
        return await this.jsonPost(`/api/frame/{session_id}`, { index });
    }

    async relaxStart(positions, fmax, steps, applyConstraint = true) {
        return await this.request(`/api/relax/start/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ positions, fmax, steps, apply_constraint: applyConstraint })
        });
    }

    async relaxStop() {
        return await this.post(`/api/relax/stop/{session_id}`);
    }

    async exportPoscar(positions, applyConstraint = true) {
        return await this.request(`/api/export/poscar/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ positions, apply_constraint: applyConstraint })
        }, { expect: 'blob' });
    }

    async exportPickle(positions, includeCalculator = false, applyConstraint = true) {
        return await this.request(`/api/export/pickle/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ positions, include_calculator: includeCalculator, apply_constraint: applyConstraint })
        }, { expect: 'blob' });
    }

    async exportBlender(positions, applyConstraint = true, camera = null) {
        const body = { positions, apply_constraint: applyConstraint };
        if (camera) body.camera = camera;
        return await this.request(`/api/export/blender/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async saveVisualSettings(settings) {
        return await this.request(`/api/settings/save/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ settings })
        }, { expect: 'blob' });
    }

    async loadVisualSettings(file) {
        const body = file instanceof Blob ? await file.arrayBuffer() : file;
        return await this.request(`/api/settings/load/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/octet-stream'},
            body
        });
    }
}
