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
        const base = this.baseSymbolForLabel(symbol);
        const table = {
            H: { color: '#FFFFFF', radius: 0.2759, bond: 0.31, vdw: 1.20 },
            C: { color: '#909090', radius: 0.6764, bond: 0.76, vdw: 1.70 },
            N: { color: '#2F50F8', radius: 0.6319, bond: 0.71, vdw: 1.55 },
            O: { color: '#FF0D0D', radius: 0.5874, bond: 0.66, vdw: 1.52 },
            F: { color: '#90DF50', radius: 0.5073, bond: 0.57, vdw: 1.47 },
            Si: { color: '#EFC79F', radius: 0.9879, bond: 1.11, vdw: 2.10 },
            S: { color: '#FFFF2F', radius: 0.9345, bond: 1.05, vdw: 1.80 },
            Na: { color: '#AB5CF1', radius: 1.4774, bond: 1.66, vdw: 2.27 },
            Cl: { color: '#1FEF1F', radius: 0.9078, bond: 1.02, vdw: 1.75 }
        };
        return table[base] || { color: '#cccccc', radius: 0.75, bond: 0.75, vdw: null };
    }

    baseSymbolForLabel(label) {
        const text = String(label || '').trim();
        if (!text) return 'X';
        const known = new Set(['H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne', 'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Br', 'I']);
        if (known.has(text)) return text;
        const match = text.match(/^([A-Z][a-z]?)/);
        return match && known.has(match[1]) ? match[1] : 'X';
    }

    mockVisualForSymbols(symbols) {
        const entries = symbols.map(symbol => this.mockElementVisual(symbol));
        return {
            color_source: 'ase.gui.view.View.colors using ase.data.colors.jmol_colors',
            radius_source: 'ase.gui.images.Images.get_radii: ase.data.covalent_radii * 0.89',
            colors: entries.map(item => item.color),
            radii: entries.map(item => item.radius),
            covalent_radii: entries.map(item => item.radius),
            bond_radii: entries.map(item => item.bond),
            vdw_radii: entries.map(item => item.vdw),
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
            chemical_symbols: symbols.map(symbol => this.baseSymbolForLabel(symbol)),
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
                calculator: 'Repulsion',
                has_calculator: true,
                energy: null,
                current_frame: 0,
                frame_count: 1,
                custom_colors: {},
                calculator_details: {
                    is_default_repulsion: true,
                    backend: 'numpy',
                    requested_device: 'cpu',
                    effective_device: 'cpu',
                    cpu_threads: 4,
                    cpu_thread_options: [1, 2, 3, 4],
                    torch_available: false,
                    cuda_available: false
                },
                config: {
                    show_cell: true,
                    show_axes: true,
                    show_grid: true,
                    show_overlays: true,
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
            this.mockState.atoms.chemical_symbols = symbols.map(symbol => this.baseSymbolForLabel(symbol));
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
        if (path.includes('/api/commensurate/')) {
            const payload = JSON.parse(options.body || '{}');
            return {
                axis: payload.axis || 'Z',
                lattice_family: 'hexagonal',
                periodic_axes: [0, 1],
                axis_alignment: 1,
                strain_tolerance: payload.strain_tolerance ?? 0.01,
                max_index: payload.max_index ?? 32,
                warning: null,
                candidates: [
                    { angle_deg: -21.7867893, strain: 0, area: 7, family: 'hexagonal-r1', magic_reference: false },
                    { angle_deg: -13.1735511, strain: 0, area: 19, family: 'hexagonal-r1', magic_reference: false },
                    { angle_deg: -1.0501209, strain: 0, area: 2977, family: 'hexagonal-r1', magic_reference: true },
                    { angle_deg: 1.0501209, strain: 0, area: 2977, family: 'hexagonal-r1', magic_reference: true },
                    { angle_deg: 13.1735511, strain: 0, area: 19, family: 'hexagonal-r1', magic_reference: false },
                    { angle_deg: 21.7867893, strain: 0, area: 7, family: 'hexagonal-r1', magic_reference: false }
                ]
            };
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
            return new Blob([options.body || '{}'], { type: 'application/json' });
        }
        if (path.includes('/api/settings/load/')) {
            return { schema: 'v_ase.visual_settings.v2', settings: {} };
        }
        if (path.includes('/api/project/save/')) {
            return new Blob(['v_ase mock project\n'], { type: 'application/vnd.v-ase.project+zip' });
        }
        if (path.includes('/api/project/load/')) {
            return { ...await this.mockResponse(this.mockState.atoms), project: { schema: 'v_ase.project.v1', settings: {} } };
        }
        if (path.includes('/api/export/video/')) {
            return options.body instanceof Blob
                ? options.body
                : new Blob([options.body || ''], { type: 'video/quicktime' });
        }
        if (path.includes('/api/file/load/')) {
            return {
                ...await this.mockResponse(this.mockState.atoms),
                loaded_file: { filename: 'mock.xyz', kind: 'structure', format: 'auto' }
            };
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
            const baseSymbols = payload.base_symbols || symbols.map(() => payload.base_symbol || null);
            const positions = payload.positions || [payload.position];
            this.mockPushHistory();
            symbols.forEach((symbol, idx) => {
                const baseSymbol = baseSymbols[idx] || this.baseSymbolForLabel(symbol);
                this.mockState.atoms.symbols.push(symbol);
                this.mockState.atoms.chemical_symbols.push(baseSymbol);
                this.mockState.atoms.positions.push([...positions[idx]]);
                this.mockState.atoms.forces.push([0, 0, 0]);
                this.mockState.atoms.tags.push(0);
                this.mockState.atoms.charges.push(0);
                this.mockState.atoms.magmoms.push(0);
            });
            this.mockState.atoms.visual = this.mockVisualForSymbols(this.mockState.atoms.chemical_symbols);
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
            this.mockState.atoms.chemical_symbols = this.mockState.atoms.symbols.map(symbol => this.baseSymbolForLabel(symbol));
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
        if (path.includes('/api/atom-types/')) {
            const payload = JSON.parse(options.body || '{}');
            const indices = (payload.indices || []).map(Number);
            const label = String(payload.label || '').trim();
            const baseSymbol = payload.base_symbol || null;
            if (!indices.length || !label) return await this.mockResponse(this.mockState.atoms);
            this.mockPushHistory();
            indices.forEach(idx => {
                if (idx >= 0 && idx < this.mockState.atoms.symbols.length) {
                    this.mockState.atoms.symbols[idx] = label;
                    if (baseSymbol) this.mockState.atoms.chemical_symbols[idx] = baseSymbol;
                }
            });
            this.mockState.atoms.visual = this.mockVisualForSymbols(this.mockState.atoms.symbols);
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/constraints/')) {
            const payload = JSON.parse(options.body || '{}');
            const indices = new Set((payload.indices || []).map(Number));
            const constraints = this.mockState.atoms.constraints || {
                fixed_indices: [],
                fixed_cartesian: {},
                fixed_line: {},
                fixed_plane: {},
                hookean: []
            };
            this.mockPushHistory();
            if (payload.fix_atoms !== undefined && payload.fix_atoms !== null) {
                const fixed = new Set((constraints.fixed_indices || []).map(Number));
                indices.forEach(idx => {
                    if (payload.fix_atoms) fixed.add(idx);
                    else fixed.delete(idx);
                });
                constraints.fixed_indices = [...fixed].sort((a, b) => a - b);
            }
            if (payload.directional_kind !== undefined && payload.directional_kind !== null) {
                indices.forEach(idx => {
                    delete constraints.fixed_line[String(idx)];
                    delete constraints.fixed_line[idx];
                    delete constraints.fixed_plane[String(idx)];
                    delete constraints.fixed_plane[idx];
                });
                const vector = payload.vector || [1, 0, 0];
                if (payload.directional_kind === 'fixed_line') {
                    indices.forEach(idx => { constraints.fixed_line[String(idx)] = vector; });
                } else if (payload.directional_kind === 'fixed_plane') {
                    indices.forEach(idx => { constraints.fixed_plane[String(idx)] = vector; });
                }
            }
            this.mockState.atoms.constraints = constraints;
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/calculator/')) {
            const payload = JSON.parse(options.body || '{}');
            const details = this.mockState.atoms.metadata.calculator_details || {
                is_default_repulsion: true,
                requested_device: 'cpu',
                effective_device: 'cpu',
                backend: 'numpy',
                cpu_threads: 4,
                cpu_thread_options: [1, 2, 3, 4],
                torch_available: false,
                cuda_available: false
            };
            details.requested_device = payload.device || details.requested_device || 'cpu';
            details.effective_device = details.requested_device === 'cuda' && details.cuda_available ? 'cuda' : 'cpu';
            details.cpu_threads = payload.cpu_threads || details.cpu_threads || 4;
            this.mockState.atoms.metadata.has_calculator = true;
            this.mockState.atoms.metadata.calculator = 'Repulsion';
            this.mockState.atoms.metadata.calculator_details = details;
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
            return { status: 'started' };
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

    async fetchTrajectoryPositions() {
        const apiPath = this.sessionPath(`/api/trajectory/positions/{session_id}`);
        const res = await fetch(new URL(apiPath, this.baseUrl));
        if (!res.ok) {
            let message = '';
            try {
                const data = await res.json();
                message = data.detail || JSON.stringify(data);
            } catch {
                message = await res.text().catch(() => '');
            }
            throw new Error(message || `Trajectory cache request failed (${res.status})`);
        }
        const frames = parseInt(res.headers.get('X-V-Ase-Frames') || '0', 10);
        const atoms = parseInt(res.headers.get('X-V-Ase-Atoms') || '0', 10);
        const buffer = await res.arrayBuffer();
        const values = new Float32Array(buffer);
        if (!frames || !atoms || values.length !== frames * atoms * 3) {
            throw new Error('Trajectory cache shape does not match the received binary payload.');
        }
        return { frames, atoms, values };
    }

    async fetchFramePositions(index) {
        const apiPath = this.sessionPath(`/api/frame/positions/{session_id}/${index}`);
        const res = await fetch(new URL(apiPath, this.baseUrl));
        if (!res.ok) {
            let message = '';
            try {
                const data = await res.json();
                message = data.detail || JSON.stringify(data);
            } catch {
                message = await res.text().catch(() => '');
            }
            throw new Error(message || `Frame position request failed (${res.status})`);
        }
        const frame = parseInt(res.headers.get('X-V-Ase-Frame') || `${index}`, 10);
        const frames = parseInt(res.headers.get('X-V-Ase-Frames') || '0', 10);
        const atoms = parseInt(res.headers.get('X-V-Ase-Atoms') || '0', 10);
        let cell = null;
        let pbc = null;
        try { cell = JSON.parse(res.headers.get('X-V-Ase-Cell') || 'null'); } catch { cell = null; }
        try { pbc = JSON.parse(res.headers.get('X-V-Ase-Pbc') || 'null'); } catch { pbc = null; }
        const buffer = await res.arrayBuffer();
        const values = new Float32Array(buffer);
        if (!atoms || values.length !== atoms * 3) {
            throw new Error('Frame position payload shape does not match the loaded structure.');
        }
        return { frame, frames, atoms, values, cell, pbc };
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

    async addAtom(symbol, position, baseSymbol = null) {
        const payload = { symbol, position };
        if (baseSymbol) payload.base_symbol = baseSymbol;
        return await this.jsonPost(`/api/add/{session_id}`, payload);
    }

    async addAtoms(symbols, positions, baseSymbols = null) {
        const payload = { symbols, positions };
        if (baseSymbols) payload.base_symbols = baseSymbols;
        return await this.jsonPost(`/api/add/{session_id}`, payload);
    }

    async deleteAtoms(indices) {
        return await this.jsonPost(`/api/delete/{session_id}`, { indices });
    }

    async updateAtomTypes(indices, label, positions = null, applyConstraint = true, baseSymbol = null) {
        const payload = { indices, label, apply_constraint: applyConstraint };
        if (baseSymbol) payload.base_symbol = baseSymbol;
        if (positions) payload.positions = positions;
        return await this.jsonPost(`/api/atom-types/{session_id}`, payload);
    }

    async updateConstraints(indices, options = {}, positions = null, applyConstraint = true) {
        const payload = { indices, apply_constraint: applyConstraint, ...options };
        if (positions) payload.positions = positions;
        return await this.jsonPost(`/api/constraints/{session_id}`, payload);
    }

    async updateCalculatorConfig(config = {}) {
        return await this.jsonPost(`/api/calculator/{session_id}`, config);
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

    async commensurateAngles(axis, maxIndex = 32, strainTolerance = 0.01) {
        return await this.jsonPost(`/api/commensurate/{session_id}`, {
            axis,
            max_index: maxIndex,
            strain_tolerance: strainTolerance
        });
    }

    async setFrame(index) {
        return await this.jsonPost(`/api/frame/{session_id}`, { index });
    }

    async relaxStart(positions, fmax, steps, applyConstraint = true, calculator = null) {
        const body = { positions, fmax, steps, apply_constraint: applyConstraint };
        if (calculator) body.calculator = calculator;
        return await this.request(`/api/relax/start/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
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

    async exportPickle(positions, applyConstraint = true) {
        return await this.request(`/api/export/pickle/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ positions, apply_constraint: applyConstraint })
        }, { expect: 'blob' });
    }

    async exportBlender(positions, applyConstraint = true, camera = null, display = null, bondPairs = null, lighting = null) {
        const body = { positions, apply_constraint: applyConstraint };
        if (camera) body.camera = camera;
        if (display) body.display = display;
        if (bondPairs) body.bond_pairs = bondPairs;
        if (lighting) body.lighting = lighting;
        return await this.request(`/api/export/blender/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async exportCad(format, positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null) {
        const body = { positions, apply_constraint: applyConstraint };
        if (display) body.display = display;
        if (bondPairs) body.bond_pairs = bondPairs;
        if (bondBridges) body.bond_bridges = bondBridges;
        return await this.request(`/api/export/${format}/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async export3dm(positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null) {
        return await this.exportCad('3dm', positions, applyConstraint, display, bondPairs, bondBridges);
    }

    async exportObj(positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null) {
        return await this.exportCad('obj', positions, applyConstraint, display, bondPairs, bondBridges);
    }

    async transcodeVideo(recording, format = 'mov') {
        const normalized = ['mov', 'avi'].includes(String(format).toLowerCase())
            ? String(format).toLowerCase()
            : 'mov';
        return await this.request(
            `/api/export/video/{session_id}?format=${encodeURIComponent(normalized)}`,
            {
                method: 'POST',
                headers: {'Content-Type': recording?.type || 'video/webm'},
                body: recording
            },
            { expect: 'blob' }
        );
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

    async saveProject(positions, settings, applyConstraint = true) {
        return await this.request(`/api/project/save/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ positions, settings, apply_constraint: applyConstraint })
        }, { expect: 'blob' });
    }

    async loadProject(file) {
        const body = file instanceof Blob ? await file.arrayBuffer() : file;
        return await this.request(`/api/project/load/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/octet-stream'},
            body
        });
    }

    async loadStructureFile(file, inputFormat = '', index = ':') {
        const params = new URLSearchParams({
            filename: file?.name || 'structure',
            index: index || ':'
        });
        if (inputFormat) params.set('input_format', inputFormat);
        return await this.request(`/api/file/load/{session_id}?${params.toString()}`, {
            method: 'POST',
            headers: {'Content-Type': file?.type || 'application/octet-stream'},
            body: file
        });
    }
}
