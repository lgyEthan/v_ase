export class ASEApi {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.baseUrl = window.location.origin && window.location.origin !== 'null'
            ? window.location.origin
            : document.baseURI;
        this.mock = Boolean(window.__V_ASE_MOCK__);
        this.mockState = this.mock ? this.createMockState() : null;
        this.onUndoableMutation = null;
        this.onCollaborationMutation = null;
        this.currentFrameProvider = null;
        this.mockCollaborationRevision = 0;
        this.mockVisualDefaults = null;
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
                    cutoff_mode: 'absolute',
                    cutoff_basis: 'covalent',
                    cutoff_distance: 2.0,
                    cutoff_scale: 1.0,
                    pair_cutoffs: {},
                    k_repulsion: 1.0,
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

    async publishCollaborationEvent(payload) {
        if (this.mock) {
            this.mockCollaborationRevision += 1;
            return {
                protocol: 'v_ase.collaboration.v1',
                ...this.clone(payload),
                revision: this.mockCollaborationRevision,
                session_id: 'mock-session'
            };
        }
        return await this.request('/api/ai/events/{session_id}', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
    }

    async request(
        path,
        options = {},
        { expect = 'json', needsSession = true, emitMutation = true } = {}
    ) {
        if (this.mock) {
            const result = await this.handleMockRequest(path, options, { expect, needsSession });
            if (emitMutation) this.emitMutationCallbacks(path, options);
            return result;
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

        let result;
        if (expect === 'blob') result = await res.blob();
        else if (expect === 'arrayBuffer') result = await res.arrayBuffer();
        else if (expect === 'text') result = await res.text();
        else result = await res.json();
        if (emitMutation) this.emitMutationCallbacks(path, options);
        return result;
    }

    emitMutationCallbacks(path, options = {}) {
        if (this.isUndoableMutation(path, options)) {
            this.onUndoableMutation?.({ path });
            return;
        }
        if (this.isCollaborationMutation(path, options)) {
            this.onCollaborationMutation?.({ path });
        }
    }

    isUndoableMutation(path, options = {}) {
        const method = String(options.method || 'GET').toUpperCase();
        if (method === 'PATCH') {
            return path.includes('/api/add-session/region/');
        }
        if (method !== 'POST') return false;
        return [
            '/api/apply/',
            '/api/reset/',
            '/api/reset-coordinates/',
            '/api/wrap/',
            '/api/add/',
            '/api/duplicate/',
            '/api/add-session/start/',
            '/api/add-session/relax/',
            '/api/delete/',
            '/api/atom-identity/',
            '/api/constraints/',
            '/api/build/bulk/apply/',
            '/api/supercell/apply/',
            '/api/supercell/matrix/',
            '/api/commensurate/apply/',
            '/api/registry-relax/finish/',
            '/api/translate/'
        ].some(prefix => path.includes(prefix));
    }

    isCollaborationMutation(path, options = {}) {
        if (!['POST', 'PATCH'].includes(String(options.method || 'GET').toUpperCase())) return false;
        return [
            '/api/file/load/',
            '/api/file/load-path/',
            '/api/file/append/',
            '/api/file/append-path/',
            '/api/project/load/',
            '/api/settings/load/',
            '/api/calculator/',
            '/api/relax/start/',
            '/api/relax/stop/',
            '/api/add-session/relax/',
            '/api/add-session/region/',
            '/api/add-session/stop/',
            '/api/add-session/finish/',
            '/api/add-session/cancel/',
            '/api/registry-relax/start/',
            '/api/registry-relax/run/',
            '/api/registry-relax/translate/',
            '/api/registry-relax/stop/',
            '/api/registry-relax/cancel/'
        ].some(prefix => path.includes(prefix));
    }

    async handleMockRequest(path, options = {}, { expect = 'json' } = {}) {
        if (path.includes('/api/session/active')) {
            return { session_id: 'mock-session', count: 1 };
        }
        if (path.includes('/api/analysis/atom-scalars/catalog/')) {
            return {
                frame_index: 0,
                atom_count: this.mockState.atoms.positions.length,
                fields: [
                    { id: 'position:x', label: 'x coordinate', group: 'Position', source: 'position', name: 'positions', reduction: 'component', component: 0, unit: 'A' },
                    { id: 'position:y', label: 'y coordinate', group: 'Position', source: 'position', name: 'positions', reduction: 'component', component: 1, unit: 'A' },
                    { id: 'position:z', label: 'z coordinate', group: 'Position', source: 'position', name: 'positions', reduction: 'component', component: 2, unit: 'A' },
                    { id: 'force:norm', label: 'Force |norm|', group: 'Calculator results', source: 'force', name: 'forces', reduction: 'norm', component: null, unit: 'eV/A' },
                    { id: 'array::tags::scalar', label: 'tags', group: 'ASE arrays', source: 'array', name: 'tags', reduction: 'scalar', component: null, unit: '' },
                    { id: 'array::initial_charges::scalar', label: 'initial_charges', group: 'ASE arrays', source: 'array', name: 'initial_charges', reduction: 'scalar', component: null, unit: 'e' },
                    { id: 'array::initial_magmoms::scalar', label: 'initial_magmoms', group: 'ASE arrays', source: 'array', name: 'initial_magmoms', reduction: 'scalar', component: null, unit: 'mu_B' }
                ]
            };
        }
        if (path.includes('/api/analysis/colormaps/')) {
            if (String(options.method || 'GET').toUpperCase() === 'POST') {
                const payload = JSON.parse(options.body || '{}');
                const count = Math.max(16, Math.min(2048, parseInt(payload.samples || 256, 10)));
                const endpoints = payload.name === 'coolwarm'
                    ? ['#3B4CC0', '#F7F7F7', '#B40426']
                    : ['#440154', '#21918C', '#FDE725'];
                const colors = Array.from({ length: count }, (_, index) => {
                    const t = count <= 1 ? 0 : index / (count - 1);
                    const segment = Math.min(endpoints.length - 2, Math.floor(t * (endpoints.length - 1)));
                    const local = t * (endpoints.length - 1) - segment;
                    const parse = hex => [1, 3, 5].map(offset => parseInt(hex.slice(offset, offset + 2), 16));
                    const a = parse(endpoints[segment]);
                    const b = parse(endpoints[segment + 1]);
                    const rgb = a.map((value, channel) => Math.round(value + (b[channel] - value) * local));
                    return `#${rgb.map(value => value.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
                });
                if (payload.reverse) colors.reverse();
                return { provider: 'Matplotlib', name: payload.name || 'viridis', reverse: Boolean(payload.reverse), samples: count, colors };
            }
            return {
                provider: 'Matplotlib',
                default: 'viridis',
                preview_samples: 3,
                maps: [
                    { name: 'viridis', category: 'Perceptually uniform sequential', reversed_variant: false, preview: ['#440154', '#21918C', '#FDE725'] },
                    { name: 'plasma', category: 'Perceptually uniform sequential', reversed_variant: false, preview: ['#0D0887', '#CC4778', '#F0F921'] },
                    { name: 'coolwarm', category: 'Diverging', reversed_variant: false, preview: ['#3B4CC0', '#F7F7F7', '#B40426'] },
                    { name: 'tab20', category: 'Qualitative', reversed_variant: false, preview: ['#1F77B4', '#98DF8A', '#9EDAE5'] }
                ]
            };
        }
        if (path.includes('/api/build/bulk/catalog/')) {
            return {
                schema: 'v_ase.ase-build.bulk.v1',
                generator: 'ase.build.bulk',
                ase_version: 'mock',
                cell_modes: [
                    { id: 'primitive', label: 'Native / primitive' },
                    { id: 'orthorhombic', label: 'Orthorhombic' },
                    { id: 'cubic', label: 'Cubic' }
                ],
                structures: [
                    { id: 'fcc', label: 'Face-centered cubic', formula_atoms: 1, formula_hint: 'one element', cell_modes: ['primitive', 'orthorhombic', 'cubic'], parameters: ['a'] },
                    { id: 'hcp', label: 'Hexagonal close-packed', formula_atoms: 1, formula_hint: 'one element', cell_modes: ['primitive', 'orthorhombic'], parameters: ['a', 'c', 'covera'] },
                    { id: 'rocksalt', label: 'Rocksalt', formula_atoms: 2, formula_hint: '1:1 binary formula', cell_modes: ['primitive', 'orthorhombic', 'cubic'], parameters: ['a'] }
                ],
                reference_materials: [
                    { formula: 'Cu', element: 'Cu', crystalstructure: 'fcc', a: 3.61, compatible_cell_modes: ['primitive', 'orthorhombic', 'cubic'], atom_counts: { primitive: 1, orthorhombic: 2, cubic: 4 } },
                    { formula: 'Mg', element: 'Mg', crystalstructure: 'hcp', a: 3.21, compatible_cell_modes: ['primitive', 'orthorhombic'], atom_counts: { primitive: 2, orthorhombic: 4 } }
                ],
                elements: ['H', 'C', 'O', 'Mg', 'Fe', 'Cu'],
                examples: []
            };
        }
        if (path.includes('/api/build/bulk/preview/')) {
            const payload = JSON.parse(options.body || '{}');
            const formula = String(payload.formula || '').trim();
            const structure = String(payload.crystalstructure || payload.crystalStructure || (formula === 'Cu' ? 'fcc' : '')).trim();
            const cellMode = String(payload.cell_mode || payload.cellMode || 'primitive');
            if (!formula) return { valid: false, message: 'Enter a chemical formula.', missing_fields: ['formula'] };
            if (formula === 'CuO' && !structure) {
                return { valid: false, message: 'CuO requires crystal structure and lattice parameter a.', missing_fields: ['crystalstructure', 'a'] };
            }
            if (formula === 'CuO' && !Number.isFinite(Number(payload.a))) {
                return { valid: false, message: 'CuO requires lattice parameter a.', missing_fields: ['a'] };
            }
            if (structure === 'hcp' && cellMode === 'cubic') {
                return { valid: false, message: 'ASE cannot construct a cubic cell for hcp.', missing_fields: [], field: 'cell_mode' };
            }
            const lattice = Number(payload.a) || 3.61;
            const atomCount = formula === 'CuO' ? (cellMode === 'cubic' ? 8 : 2) : (cellMode === 'cubic' ? 4 : 1);
            return {
                valid: true,
                formula,
                crystalstructure: structure || 'fcc',
                cell_mode: cellMode,
                atom_count: atomCount,
                chemical_formula: formula,
                cell: [[lattice, 0, 0], [0, lattice, 0], [0, 0, lattice]],
                cell_parameters: { a: lattice, b: lattice, c: lattice, alpha: 90, beta: 90, gamma: 90 }
            };
        }
        if (path.includes('/api/build/bulk/apply/')) {
            const payload = JSON.parse(options.body || '{}');
            const preview = await this.handleMockRequest('/api/build/bulk/preview/', {
                ...options,
                body: JSON.stringify(payload)
            }, { expect });
            if (!preview.valid) throw new Error(preview.message);
            const count = preview.atom_count;
            const symbols = preview.formula === 'CuO'
                ? Array.from({ length: count }, (_, index) => index % 2 ? 'O' : 'Cu')
                : Array(count).fill(preview.formula);
            this.mockPushHistory();
            this.mockState.atoms.symbols = [...symbols];
            this.mockState.atoms.chemical_symbols = [...symbols];
            this.mockState.atoms.positions = Array.from({ length: count }, (_, index) => [
                (index & 1) * preview.cell_parameters.a * 0.5,
                ((index >> 1) & 1) * preview.cell_parameters.b * 0.5,
                ((index >> 2) & 1) * preview.cell_parameters.c * 0.5
            ]);
            this.mockState.atoms.cell = preview.cell;
            this.mockState.atoms.pbc = [true, true, true];
            this.mockState.atoms.forces = Array.from({ length: count }, () => [0, 0, 0]);
            this.mockState.atoms.tags = Array(count).fill(0);
            this.mockState.atoms.charges = Array(count).fill(0);
            this.mockState.atoms.magmoms = Array(count).fill(0);
            this.mockState.atoms.visual = this.mockVisualForSymbols(symbols);
            this.mockState.atoms.metadata.natoms = count;
            this.mockState.atoms.metadata.frame_count = 1;
            this.mockState.atoms.metadata.current_frame = 0;
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/atoms/')) {
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/mode/')) {
            const payload = JSON.parse(options.body || '{}');
            if (Array.isArray(payload.labels) && payload.labels.length === this.mockState.atoms.symbols.length) {
                this.mockState.atoms.symbols = [...payload.labels];
            }
            if (
                Array.isArray(payload.chemical_symbols)
                && payload.chemical_symbols.length === this.mockState.atoms.symbols.length
            ) {
                this.mockState.atoms.chemical_symbols = [...payload.chemical_symbols];
                this.mockState.atoms.visual = this.mockVisualForSymbols(payload.chemical_symbols);
            }
            if (Array.isArray(payload.positions) && payload.positions.length === this.mockState.atoms.symbols.length) {
                this.mockState.atoms.positions = payload.positions.map(position => [...position]);
            }
            this.mockState.atoms.metadata.config.viz_only = Boolean(payload.viz_only);
            if (!payload.viz_only) {
                this.mockState.atoms.metadata.has_calculator = true;
                this.mockState.atoms.metadata.calculator = 'Repulsion';
            }
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
        if (path.includes('/api/translate/')) {
            const payload = JSON.parse(options.body || '{}');
            const vector = Array.isArray(payload.vector) ? payload.vector.map(Number) : [0, 0, 0];
            let shift = vector;
            if (payload.coordinate_mode === 'fractional') {
                const cell = this.mockState.atoms.cell || [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
                shift = [
                    vector[0] * cell[0][0] + vector[1] * cell[1][0] + vector[2] * cell[2][0],
                    vector[0] * cell[0][1] + vector[1] * cell[1][1] + vector[2] * cell[2][1],
                    vector[0] * cell[0][2] + vector[1] * cell[1][2] + vector[2] * cell[2][2]
                ];
            }
            const positions = (payload.positions || this.mockState.atoms.positions).map(position => [
                position[0] + shift[0],
                position[1] + shift[1],
                position[2] + shift[2]
            ]);
            return await this.mockApplyPositions(positions);
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
        if (path.includes('/api/commensurate/preview/')) {
            const payload = JSON.parse(options.body || '{}');
            const angle = Number(payload.candidate?.angle_deg || 21.7867893);
            const positive = angle >= 0;
            const sourceMatrix = payload.candidate?.source_matrix
                || (positive ? [[2, 1], [-1, 3]] : [[1, 2], [-2, 3]]);
            const targetMatrix = payload.candidate?.target_matrix
                || (positive ? [[1, 2], [-2, 3]] : [[2, 1], [-1, 3]]);
            const positions = payload.positions || this.mockState.atoms.positions;
            const atomIndices = positions.map((_, index) => index);
            const cell = this.mockState.atoms.cell || [[8, 0, 0], [0, 8, 0], [0, 0, 8]];
            const suggestedCell = [
                cell[0].map((value, index) => (
                    targetMatrix[0][0] * value + targetMatrix[0][1] * cell[1][index]
                )),
                cell[0].map((value, index) => (
                    targetMatrix[1][0] * value + targetMatrix[1][1] * cell[1][index]
                )),
                [...cell[2]]
            ];
            const matrixText = matrix => `[[${matrix[0].join(',')}],[${matrix[1].join(',')}]]`;
            return {
                status: 'ok',
                candidate: {
                    angle_deg: angle,
                    strain: 0,
                    area: 7,
                    area_ratio: 7,
                    source_matrix: sourceMatrix,
                    target_matrix: targetMatrix,
                    source_matrix_text: matrixText(sourceMatrix),
                    target_matrix_text: matrixText(targetMatrix),
                    source_notation: '(√7 × √7)',
                    target_notation: '(√7 × √7)',
                    cell_lengths_angstrom: [21.166, 21.166],
                    cell_angle_deg: 60,
                    supercell_supported: true
                },
                search: {
                    axis: payload.axis || 'Z',
                    lattice_family: 'hexagonal',
                    strain_tolerance: payload.strain_tolerance ?? 0.01,
                    max_area_ratio: payload.max_area_ratio ?? 16
                },
                preview: {
                    positions: positions.map(position => [...position]),
                    atom_indices: atomIndices,
                    lattice_indices: positions.map(() => [0, 0, 0]),
                    components: atomIndices.map(index => (
                        (payload.selected_indices || []).includes(index) ? 'rotating' : 'reference'
                    )),
                    core_mask: positions.map(() => true),
                    core_atom_count: positions.length,
                    preview_atom_count: positions.length,
                    padding_cells: 1,
                    cell: suggestedCell,
                    area_ratio: 7
                },
                materialization_supported: true,
                materialization_reason: null
            };
        }
        if (path.includes('/api/commensurate/apply/')) {
            const payload = JSON.parse(options.body || '{}');
            this.mockPushHistory();
            if (Array.isArray(payload.positions)) {
                this.mockState.atoms.positions = payload.positions.map(position => [...position]);
            }
            return await this.mockResponse(this.mockState.atoms);
        }
        if (path.includes('/api/commensurate/')) {
            const payload = JSON.parse(options.body || '{}');
            const candidate = (angle, source, target, area, magic = false) => ({
                angle_deg: angle,
                strain: 0,
                area,
                area_ratio: area,
                source_matrix: source,
                target_matrix: target,
                source_notation: area === 7 ? '(√7 × √7)' : `${area} primitive cells`,
                target_notation: area === 7 ? '(√7 × √7)' : `${area} primitive cells`,
                source_matrix_text: `[[${source[0].join(',')}],[${source[1].join(',')}]]`,
                target_matrix_text: `[[${target[0].join(',')}],[${target[1].join(',')}]]`,
                family: 'hexagonal-r1',
                magic_reference: magic,
                supercell_supported: true
            });
            const negativeSource = [[1, 2], [-2, 3]];
            const negativeTarget = [[2, 1], [-1, 3]];
            const positiveSource = negativeTarget;
            const positiveTarget = negativeSource;
            return {
                axis: payload.axis || 'Z',
                lattice_family: 'hexagonal',
                periodic_axes: [0, 1],
                axis_alignment: 1,
                strain_tolerance: payload.strain_tolerance ?? 0.01,
                max_index: payload.max_index ?? 32,
                max_area_ratio: payload.max_area_ratio ?? 16,
                suggestion_count: 2,
                warning: null,
                candidates: [
                    candidate(-21.7867893, negativeSource, negativeTarget, 7),
                    candidate(-13.1735511, [[2, 3], [-3, 5]], [[3, 2], [-2, 5]], 19),
                    candidate(-1.0501209, [[31, 32], [-32, 63]], [[32, 31], [-31, 63]], 2977, true),
                    candidate(1.0501209, [[32, 31], [-31, 63]], [[31, 32], [-32, 63]], 2977, true),
                    candidate(13.1735511, [[3, 2], [-2, 5]], [[2, 3], [-3, 5]], 19),
                    candidate(21.7867893, positiveSource, positiveTarget, 7)
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
            return { schema: 'v_ase.visual_settings.v3', settings: {} };
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
        if (path.includes('/api/duplicate/')) {
            const payload = JSON.parse(options.body || '{}');
            const indices = [...new Set((payload.indices || []).map(Number))]
                .filter(index => index >= 0 && index < this.mockState.atoms.positions.length)
                .sort((a, b) => a - b);
            this.mockPushHistory();
            const start = this.mockState.atoms.positions.length;
            for (const index of indices) {
                this.mockState.atoms.symbols.push(this.mockState.atoms.symbols[index]);
                this.mockState.atoms.chemical_symbols.push(this.mockState.atoms.chemical_symbols[index]);
                this.mockState.atoms.positions.push([...this.mockState.atoms.positions[index]]);
                this.mockState.atoms.forces.push([...(this.mockState.atoms.forces[index] || [0, 0, 0])]);
                this.mockState.atoms.tags.push(this.mockState.atoms.tags[index] || 0);
                this.mockState.atoms.charges.push(this.mockState.atoms.charges[index] || 0);
                this.mockState.atoms.magmoms.push(this.mockState.atoms.magmoms[index] || 0);
            }
            this.mockState.atoms.visual = this.mockVisualForSymbols(this.mockState.atoms.chemical_symbols);
            this.mockState.atoms.metadata.natoms = this.mockState.atoms.positions.length;
            return {
                ...await this.mockResponse(this.mockState.atoms),
                duplicated_indices: indices.map((_, offset) => start + offset)
            };
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
        if (path.includes('/api/atom-identity/') || path.includes('/api/atom-types/')) {
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
            this.mockState.atoms.visual = this.mockVisualForSymbols(
                this.mockState.atoms.chemical_symbols
            );
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
            details.cutoff_mode = ['scaled', 'bonding'].includes(payload.cutoff_mode)
                ? 'scaled'
                : payload.cutoff_mode === 'absolute'
                    ? 'absolute'
                    : details.cutoff_mode || 'absolute';
            details.cutoff_basis = payload.cutoff_basis === 'vdw' ? 'vdw' : 'covalent';
            details.cutoff_distance = Number.isFinite(Number(payload.cutoff_distance))
                ? Math.max(0.01, Math.min(100, Number(payload.cutoff_distance)))
                : Number(details.cutoff_distance ?? 2.0);
            details.cutoff_scale = Number.isFinite(Number(payload.cutoff_scale))
                ? Math.max(0.05, Math.min(3, Number(payload.cutoff_scale)))
                : Number(details.cutoff_scale ?? 1.0);
            if (payload.pair_cutoffs && typeof payload.pair_cutoffs === 'object') {
                details.pair_cutoffs = this.clone(payload.pair_cutoffs);
            }
            details.k_repulsion = Number.isFinite(Number(payload.k_repulsion))
                ? Math.max(0, Math.min(1000, Number(payload.k_repulsion)))
                : Number(details.k_repulsion ?? 1.0);
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
        if (path.includes('/api/analysis/displacement/')) {
            return {
                status: 'unavailable',
                message: 'Displacement analysis requires at least two trajectory frames.',
                frame_count: 1
            };
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

    jsonPost(path, payload = {}, requestOptions = {}) {
        return this.request(path, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }, requestOptions);
    }

    post(path) {
        return this.request(path, { method: 'POST' });
    }

    currentFrameIndex() {
        const value = Number(this.currentFrameProvider?.());
        return Number.isInteger(value) && value >= 0 ? value : 0;
    }

    framePayload(payload = {}) {
        return {
            ...payload,
            frame_index: this.currentFrameIndex()
        };
    }

    async fetchAtoms() {
        return await this.request(`/api/atoms/{session_id}`);
    }

    async fetchStoredFrameProperties(frameIndex, includeArrays = false) {
        return await this.request(`/api/analysis/frame-properties/{session_id}?frame_index=${frameIndex}&include_arrays=${includeArrays}`);
    }

    async updateSessionMode(vizOnly, identities = {}) {
        return await this.jsonPost(`/api/mode/{session_id}`, this.framePayload({
            viz_only: Boolean(vizOnly),
            ...identities
        }));
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
        return await this.jsonPost(
            `/api/apply/{session_id}`,
            this.framePayload({ positions, apply_constraint: applyConstraint })
        );
    }

    async getConstrainedPositions(positions, applyConstraint = true) {
        return await this.jsonPost(
            `/api/constrain/{session_id}`,
            this.framePayload({ positions, apply_constraint: applyConstraint })
        );
    }

    async addAtom(symbol, position, baseSymbol = null) {
        const payload = { symbol, position };
        if (baseSymbol) payload.base_symbol = baseSymbol;
        return await this.jsonPost(`/api/add/{session_id}`, this.framePayload(payload));
    }

    async addAtoms(symbols, positions, baseSymbols = null) {
        const payload = { symbols, positions };
        if (baseSymbols) payload.base_symbols = baseSymbols;
        return await this.jsonPost(`/api/add/{session_id}`, this.framePayload(payload));
    }

    async duplicateAtoms(indices) {
        return await this.jsonPost(
            `/api/duplicate/{session_id}`,
            this.framePayload({ indices })
        );
    }

    async atomAdditionMoleculeCatalog() {
        return await this.request(`/api/add-session/molecules/{session_id}`);
    }

    async atomAdditionPairCutoffs(elements, basis = 'covalent', scale = 1.0, molecules = []) {
        return await this.jsonPost(
            `/api/add-session/pairs/{session_id}`,
            { elements, basis, scale, molecules }
        );
    }

    async atomAdditionDomain(payload) {
        return await this.jsonPost(`/api/add-session/domain/{session_id}`, payload);
    }

    async startAtomAddition(payload) {
        return await this.jsonPost(
            `/api/add-session/start/{session_id}`,
            this.framePayload(payload)
        );
    }

    async relaxAtomAddition(payload) {
        return await this.jsonPost(`/api/add-session/relax/{session_id}`, payload);
    }

    async updateAtomAdditionRegion(payload) {
        return this.request(`/api/add-session/region/{session_id}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
    }

    async stopAtomAdditionRelaxation() {
        return await this.jsonPost(`/api/add-session/stop/{session_id}`, {});
    }

    async finishAtomAddition() {
        return await this.jsonPost(`/api/add-session/finish/{session_id}`, {});
    }

    async cancelAtomAddition() {
        return await this.jsonPost(`/api/add-session/cancel/{session_id}`, {});
    }

    async deleteAtoms(indices) {
        return await this.jsonPost(`/api/delete/{session_id}`, this.framePayload({ indices }));
    }

    async updateAtomIdentity(indices, label, positions = null, applyConstraint = true, baseSymbol = null) {
        const payload = { indices, label, apply_constraint: applyConstraint };
        if (baseSymbol) payload.base_symbol = baseSymbol;
        if (positions) payload.positions = positions;
        return await this.jsonPost(`/api/atom-identity/{session_id}`, this.framePayload(payload));
    }

    async updateAtomTypes(...args) {
        return await this.updateAtomIdentity(...args);
    }

    async updateConstraints(indices, options = {}, positions = null, applyConstraint = true) {
        const payload = { indices, apply_constraint: applyConstraint, ...options };
        if (positions) payload.positions = positions;
        return await this.jsonPost(`/api/constraints/{session_id}`, this.framePayload(payload));
    }

    async updateCalculatorConfig(config = {}) {
        return await this.jsonPost(`/api/calculator/{session_id}`, this.framePayload(config));
    }

    async undo() {
        return await this.post(`/api/undo/{session_id}`);
    }

    async redo() {
        return await this.post(`/api/redo/{session_id}`);
    }

    async done(positions, applyConstraint = true) {
        const data = await this.jsonPost(
            `/api/done/{session_id}`,
            this.framePayload({ positions, apply_constraint: applyConstraint })
        );
        window.close();
        return data;
    }

    async cancel() {
        const data = await this.post(`/api/cancel/{session_id}`);
        window.close();
        return data;
    }

    async reset() {
        return await this.jsonPost(`/api/reset/{session_id}`, this.framePayload());
    }

    async resetCoordinates() {
        return await this.jsonPost(`/api/reset-coordinates/{session_id}`, this.framePayload());
    }

    async wrap(positions, applyConstraint = true) {
        return await this.jsonPost(
            `/api/wrap/{session_id}`,
            this.framePayload({ positions, apply_constraint: applyConstraint })
        );
    }

    async applySupercell(positions, reps, applyConstraint = true) {
        return await this.jsonPost(
            `/api/supercell/apply/{session_id}`,
            this.framePayload({ positions, reps, apply_constraint: applyConstraint })
        );
    }

    async applySupercellMatrix(positions, matrix, applyConstraint = true) {
        return await this.jsonPost(
            `/api/supercell/matrix/{session_id}`,
            this.framePayload({ positions, matrix, apply_constraint: applyConstraint })
        );
    }

    async setUnitCell(cell, pbc = [true, true, true], scaleAtoms = false) {
        return await this.jsonPost(`/api/cell/{session_id}`, {
            cell,
            pbc,
            scale_atoms: Boolean(scaleAtoms)
        });
    }

    async fetchBulkBuilderCatalog() {
        return await this.request(`/api/build/bulk/catalog/{session_id}`);
    }

    async previewBulkStructure(payload) {
        return await this.jsonPost(`/api/build/bulk/preview/{session_id}`, payload);
    }

    async buildBulkStructure(payload) {
        return await this.jsonPost(`/api/build/bulk/apply/{session_id}`, payload);
    }

    async applyTranslation(positions, vector, coordinateMode = 'cartesian', applyConstraint = true) {
        return await this.jsonPost(`/api/translate/{session_id}`, this.framePayload({
            positions,
            vector,
            coordinate_mode: coordinateMode,
            apply_constraint: applyConstraint
        }));
    }

    async commensurateAngles(
        axis,
        maxIndex = 32,
        strainTolerance = 0.01,
        maxAreaRatio = 16,
        options = {}
    ) {
        return await this.jsonPost(`/api/commensurate/{session_id}`, this.framePayload({
            axis,
            max_index: maxIndex,
            strain_tolerance: strainTolerance,
            max_area_ratio: maxAreaRatio,
            mode: options.mode || 'same-lattice',
            strain_target: options.strainTarget || 'guest',
            selected_indices: Array.isArray(options.selectedIndices)
                ? options.selectedIndices
                : [],
            job_id: options.jobId || undefined
        }));
    }

    async loadCommensurateGuest(file, inputFormat = '') {
        const params = new URLSearchParams({
            filename: file?.name || 'guest.xyz'
        });
        if (inputFormat) params.set('input_format', inputFormat);
        return await this.request(`/api/commensurate/guest/{session_id}?${params.toString()}`, {
            method: 'POST',
            headers: {'Content-Type': file?.type || 'application/octet-stream'},
            body: file
        });
    }

    async loadCommensurateGuestPath(path, inputFormat = '') {
        return await this.jsonPost(`/api/commensurate/guest-path/{session_id}`, {
            path,
            input_format: inputFormat || undefined
        });
    }

    async removeCommensurateGuest() {
        return await this.post(`/api/commensurate/guest/remove/{session_id}`);
    }

    async previewCommensurateSupercell(payload) {
        return await this.jsonPost(
            `/api/commensurate/preview/{session_id}`,
            this.framePayload(payload)
        );
    }

    async applyCommensurateSupercell(payload) {
        return await this.jsonPost(
            `/api/commensurate/apply/{session_id}`,
            this.framePayload(payload)
        );
    }

    async exportCommensurateCsv(options = {}) {
        return await this.request(`/api/analysis/commensurate-csv/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(this.framePayload(options))
        }, { expect: 'blob' });
    }

    async fetchRegistryMap(options = {}) {
        return await this.jsonPost(
            `/api/analysis/registry/{session_id}`,
            this.framePayload(options)
        );
    }

    async exportRegistryCsv(options = {}) {
        return await this.request(`/api/analysis/registry-csv/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(this.framePayload(options))
        }, { expect: 'blob' });
    }

    async startRegistryRelaxation(payload = {}) {
        return await this.jsonPost(
            `/api/registry-relax/start/{session_id}`,
            this.framePayload(payload)
        );
    }

    async runRegistryRelaxation(payload = {}) {
        return await this.jsonPost(`/api/registry-relax/run/{session_id}`, payload);
    }

    async stopRegistryRelaxation() {
        return await this.jsonPost(`/api/registry-relax/stop/{session_id}`, {});
    }

    async translateRegistryRelaxation(coordinates) {
        return await this.jsonPost(`/api/registry-relax/translate/{session_id}`, {
            coordinates: Array.isArray(coordinates) ? coordinates.map(Number) : []
        });
    }

    async finishRegistryRelaxation() {
        return await this.jsonPost(`/api/registry-relax/finish/{session_id}`, {});
    }

    async cancelRegistryRelaxation() {
        return await this.jsonPost(`/api/registry-relax/cancel/{session_id}`, {});
    }

    async fetchAtomScalarCatalog(frameIndex = this.currentFrameIndex()) {
        const query = new URLSearchParams({ frame_index: `${Math.max(0, parseInt(frameIndex, 10) || 0)}` });
        return await this.request(`/api/analysis/atom-scalars/catalog/{session_id}?${query.toString()}`);
    }

    async fetchAtomProperties(atomIndex, frameIndex = this.currentFrameIndex()) {
        const index = Math.max(0, parseInt(atomIndex, 10) || 0);
        const frame = Math.max(0, parseInt(frameIndex, 10) || 0);
        if (this.mock) {
            const atoms = this.mockState.atoms;
            const force = atoms.forces?.[index] ?? null;
            return {
                frame_index: frame,
                atom_index: index,
                atom_count: atoms.positions.length,
                properties: [
                    { source: 'ase', name: 'atomic_number', value: null, shape: [], dtype: 'int64', unit: '' },
                    { source: 'ase', name: 'mass', value: null, shape: [], dtype: 'float64', unit: 'amu' },
                    { source: 'ase', name: 'tag', value: atoms.tags?.[index] ?? 0, shape: [], dtype: 'int64', unit: '' },
                    { source: 'ase', name: 'initial_charge', value: atoms.charges?.[index] ?? 0, shape: [], dtype: 'float64', unit: 'e' },
                    { source: 'ase', name: 'initial_magmom', value: atoms.magmoms?.[index] ?? 0, shape: [], dtype: 'float64', unit: 'mu_B' },
                    ...(Array.isArray(force)
                        ? [{ source: 'calculator', name: 'forces', value: force, shape: [force.length], dtype: 'float64', unit: 'eV/A' }]
                        : [])
                ]
            };
        }
        const query = new URLSearchParams({ frame_index: `${frame}` });
        return await this.request(
            `/api/analysis/atom-properties/{session_id}/${index}?${query.toString()}`,
            {},
            { emitMutation: false }
        );
    }

    async fetchAtomScalarValues(fieldId, frameIndex = this.currentFrameIndex(), allFrames = false) {
        if (this.mock) {
            const atoms = this.mockState.atoms;
            let source;
            if (fieldId === 'force:norm') {
                source = (atoms.forces || []).map(force => Math.hypot(...force.map(Number)));
            } else if (fieldId === 'array::tags::scalar') {
                source = atoms.tags || [];
            } else if (fieldId === 'array::initial_charges::scalar') {
                source = atoms.charges || [];
            } else if (fieldId === 'array::initial_magmoms::scalar') {
                source = atoms.magmoms || [];
            } else {
                throw new Error(`Mock per-atom field is unavailable: ${fieldId}`);
            }
            return {
                frames: 1,
                atoms: atoms.positions.length,
                startFrame: Math.max(0, parseInt(frameIndex, 10) || 0),
                cache: 'frame',
                values: Float32Array.from(source, Number)
            };
        }
        const apiPath = this.sessionPath('/api/analysis/atom-scalars/values/{session_id}');
        const res = await fetch(new URL(apiPath, this.baseUrl), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                field_id: fieldId,
                frame_index: Math.max(0, parseInt(frameIndex, 10) || 0),
                all_frames: Boolean(allFrames)
            })
        });
        if (!res.ok) {
            let message = '';
            try {
                const data = await res.json();
                message = data.detail || JSON.stringify(data);
            } catch {
                message = await res.text().catch(() => '');
            }
            throw new Error(message || `Per-atom scalar request failed (${res.status})`);
        }
        const frames = parseInt(res.headers.get('X-V-Ase-Frames') || '0', 10);
        const atoms = parseInt(res.headers.get('X-V-Ase-Atoms') || '0', 10);
        const startFrame = parseInt(res.headers.get('X-V-Ase-Start-Frame') || '0', 10);
        const cache = res.headers.get('X-V-Ase-Cache') || 'frame';
        const values = new Float32Array(await res.arrayBuffer());
        if (!frames || !atoms || values.length !== frames * atoms) {
            throw new Error('Per-atom scalar cache shape does not match the received binary payload.');
        }
        return { frames, atoms, startFrame, cache, values };
    }

    async fetchForceVectors(frameIndex = this.currentFrameIndex(), allFrames = false) {
        if (this.mock) {
            const atoms = this.mockState.atoms;
            const source = Array.isArray(atoms.forces) ? atoms.forces : [];
            const values = new Float32Array(atoms.positions.length * 3);
            values.fill(Number.NaN);
            source.forEach((force, atomIndex) => {
                if (!Array.isArray(force) || atomIndex >= atoms.positions.length) return;
                for (let axis = 0; axis < 3; axis += 1) {
                    const value = Number(force[axis]);
                    values[atomIndex * 3 + axis] = Number.isFinite(value) ? value : Number.NaN;
                }
            });
            return {
                frames: 1,
                atoms: atoms.positions.length,
                startFrame: Math.max(0, parseInt(frameIndex, 10) || 0),
                cache: 'frame',
                values
            };
        }
        const apiPath = this.sessionPath('/api/analysis/force-vectors/{session_id}');
        const res = await fetch(new URL(apiPath, this.baseUrl), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                frame_index: Math.max(0, parseInt(frameIndex, 10) || 0),
                all_frames: Boolean(allFrames)
            })
        });
        if (!res.ok) {
            let message = '';
            try {
                const data = await res.json();
                message = data.detail || JSON.stringify(data);
            } catch {
                message = await res.text().catch(() => '');
            }
            throw new Error(message || `Force-vector request failed (${res.status})`);
        }
        const frames = parseInt(res.headers.get('X-V-Ase-Frames') || '0', 10);
        const atoms = parseInt(res.headers.get('X-V-Ase-Atoms') || '0', 10);
        const startFrame = parseInt(res.headers.get('X-V-Ase-Start-Frame') || '0', 10);
        const cache = res.headers.get('X-V-Ase-Cache') || 'frame';
        const values = new Float32Array(await res.arrayBuffer());
        if (!frames || !atoms || values.length !== frames * atoms * 3) {
            throw new Error('Force-vector cache shape does not match the received binary payload.');
        }
        return { frames, atoms, startFrame, cache, values };
    }

    async fetchAtomScalarRange(
        fieldId,
        frameIndex = this.currentFrameIndex(),
        allFrames = false,
        indices = null
    ) {
        if (this.mock) {
            const result = await this.fetchAtomScalarValues(fieldId, frameIndex, false);
            const requested = Array.isArray(indices)
                ? indices.map(index => result.values[index]).filter(Number.isFinite)
                : Array.from(result.values).filter(Number.isFinite);
            if (!requested.length) throw new Error('The selected per-atom property has no finite values.');
            let minimum = Math.min(...requested);
            let maximum = Math.max(...requested);
            if (minimum === maximum) {
                const padding = Math.max(1e-12, Math.abs(minimum) * 1e-6);
                minimum -= padding;
                maximum += padding;
            }
            return {
                field_id: fieldId,
                scope: Array.isArray(indices) ? 'selected' : 'all',
                range_mode: allFrames ? 'trajectory' : 'current',
                minimum,
                maximum,
                finite_values: requested.length,
                frames_scanned: 1,
                frames_with_values: 1,
                missing_frames: 0
            };
        }
        return await this.jsonPost('/api/analysis/atom-scalars/range/{session_id}', {
            field_id: fieldId,
            frame_index: Math.max(0, parseInt(frameIndex, 10) || 0),
            all_frames: Boolean(allFrames),
            indices: Array.isArray(indices) ? indices.map(Number) : null
        });
    }

    async fetchColormapCatalog() {
        return await this.request('/api/analysis/colormaps/{session_id}');
    }

    async fetchColormapLut(name = 'viridis', reverse = false, samples = 256) {
        return await this.jsonPost('/api/analysis/colormaps/{session_id}', {
            name,
            reverse: Boolean(reverse),
            samples: Math.max(16, Math.min(2048, parseInt(samples, 10) || 256))
        });
    }

    async setFrame(index) {
        return await this.jsonPost(`/api/frame/{session_id}`, { index });
    }

    async relaxStart(positions, fmax, steps, applyConstraint = true, calculator = null) {
        const body = this.framePayload({ positions, fmax, steps, apply_constraint: applyConstraint });
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

    async clearRelaxTrajectory(kind, positions, useLatest = true) {
        return await this.jsonPost(`/api/relax/trajectory/clear/{session_id}`, {
            kind,
            positions,
            use_latest: Boolean(useLatest)
        });
    }

    async relaxExit(keep = true) {
        return await this.jsonPost(`/api/relax/exit/{session_id}`, {
            keep: Boolean(keep)
        });
    }

    async exportPoscar(positions, applyConstraint = true) {
        const payload = this.framePayload({ positions, apply_constraint: applyConstraint });
        return await this.request(`/api/export/poscar/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }, { expect: 'blob' });
    }

    async exportPickle(positions, applyConstraint = true) {
        const payload = this.framePayload({ positions, apply_constraint: applyConstraint });
        return await this.request(`/api/export/pickle/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }, { expect: 'blob' });
    }

    async exportBlender(positions, applyConstraint = true, camera = null, display = null, bondPairs = null, lighting = null, includeCell = true) {
        const body = this.framePayload({ positions, apply_constraint: applyConstraint });
        if (camera) body.camera = camera;
        if (display) body.display = display;
        if (bondPairs) body.bond_pairs = bondPairs;
        if (lighting) body.lighting = lighting;
        body.include_cell = includeCell !== false;
        return await this.request(`/api/export/blender/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async exportCad(format, positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null, camera = null, includeCell = true) {
        const body = this.framePayload({ positions, apply_constraint: applyConstraint });
        if (display) body.display = display;
        if (bondPairs) body.bond_pairs = bondPairs;
        if (bondBridges) body.bond_bridges = bondBridges;
        if (camera) body.camera = camera;
        body.include_cell = includeCell !== false;
        return await this.request(`/api/export/${format}/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async export3dm(positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null, camera = null, includeCell = true) {
        return await this.exportCad('3dm', positions, applyConstraint, display, bondPairs, bondBridges, camera, includeCell);
    }

    async exportObj(positions, applyConstraint = true, display = null, bondPairs = null, bondBridges = null, camera = null, includeCell = true) {
        return await this.exportCad('obj', positions, applyConstraint, display, bondPairs, bondBridges, camera, includeCell);
    }

    async exportHtml(
        positions,
        settings,
        applyConstraint = true,
        selection = [],
        documentName = 'v_ase view',
        embedProject = false,
        exportProfile = null,
        posterDataUrl = null
    ) {
        const body = this.framePayload({
            positions,
            settings,
            apply_constraint: applyConstraint,
            selection,
            document_name: documentName,
            embed_project: embedProject === true
        });
        if (exportProfile) body.export_profile = exportProfile;
        if (posterDataUrl) body.poster_data_url = posterDataUrl;
        return await this.request(`/api/export/html/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }, { expect: 'blob' });
    }

    async transcodeVideo(
        recording,
        format = 'mov',
        fps = 12,
        frameCount = null,
        exportId = ''
    ) {
        const normalized = ['mov', 'avi'].includes(String(format).toLowerCase())
            ? String(format).toLowerCase()
            : 'mov';
        const normalizedFps = Math.min(60, Math.max(1, Math.round(Number(fps) || 12)));
        const normalizedFrameCount = Number.isFinite(Number(frameCount))
            ? Math.max(1, Math.round(Number(frameCount)))
            : null;
        const query = new URLSearchParams({
            format: normalized,
            fps: String(normalizedFps)
        });
        if (normalizedFrameCount !== null) {
            query.set('frames', String(normalizedFrameCount));
        }
        if (exportId) query.set('export_id', String(exportId));
        return await this.request(
            `/api/export/video/{session_id}?${query.toString()}`,
            {
                method: 'POST',
                headers: {'Content-Type': recording?.type || 'video/webm'},
                body: recording
            },
            { expect: 'blob' }
        );
    }

    async encodeImage(image, format = 'png', onProgress = null) {
        if (this.mock) {
            onProgress?.({ phase: 'complete', ratio: 1 });
            return image;
        }
        const requested = String(format).trim().toLowerCase();
        const normalized = ['png', 'jpg', 'jpeg', 'pdf', 'webp'].includes(requested)
            ? requested
            : 'png';
        if (typeof onProgress !== 'function') {
            return await this.request(
                `/api/export/image/{session_id}?format=${normalized}`,
                {
                    method: 'POST',
                    headers: {'Content-Type': 'image/png'},
                    body: image
                },
                { expect: 'blob' }
            );
        }

        const path = this.sessionPath(`/api/export/image/{session_id}?format=${normalized}`);
        const url = new URL(path, this.baseUrl);
        return await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', url);
            xhr.responseType = 'blob';
            xhr.setRequestHeader('Content-Type', 'image/png');
            xhr.upload.addEventListener('progress', event => {
                onProgress({
                    phase: 'upload',
                    ratio: event.lengthComputable && event.total > 0
                        ? event.loaded / event.total
                        : 0
                });
            });
            xhr.upload.addEventListener('loadend', () => {
                onProgress({ phase: 'encoding', ratio: 0 });
            });
            xhr.addEventListener('progress', event => {
                onProgress({
                    phase: 'download',
                    ratio: event.lengthComputable && event.total > 0
                        ? event.loaded / event.total
                        : 0
                });
            });
            xhr.addEventListener('error', () => {
                reject(new Error(`Cannot reach v_ase server at ${this.baseUrl}. Restart the viewer session and reload this page.`));
            });
            xhr.addEventListener('abort', () => {
                reject(new Error('Image encoding was canceled.'));
            });
            xhr.addEventListener('load', async () => {
                if (xhr.status < 200 || xhr.status >= 300) {
                    let message = '';
                    try {
                        message = await xhr.response?.text();
                        if ((xhr.getResponseHeader('content-type') || '').includes('application/json')) {
                            const data = JSON.parse(message);
                            message = data.detail || data.message || message;
                        }
                    } catch {
                        message = '';
                    }
                    reject(new Error(message || `v_ase request failed (${xhr.status})`));
                    return;
                }
                onProgress({ phase: 'complete', ratio: 1 });
                resolve(xhr.response);
            });
            onProgress({ phase: 'upload', ratio: 0 });
            xhr.send(image);
        });
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

    readMockVisualDefaults() {
        try {
            const raw = window.localStorage.getItem('v_ase_mock_visual_defaults');
            return raw ? JSON.parse(raw) : this.mockVisualDefaults;
        } catch {
            return this.mockVisualDefaults;
        }
    }

    writeMockVisualDefaults(settings) {
        this.mockVisualDefaults = settings ? this.clone(settings) : null;
        try {
            if (settings) {
                window.localStorage.setItem('v_ase_mock_visual_defaults', JSON.stringify(settings));
            } else {
                window.localStorage.removeItem('v_ase_mock_visual_defaults');
            }
        } catch {
            // Static mock pages may run with storage disabled.
        }
    }

    async fetchUserVisualDefaults() {
        if (this.mock) {
            const settings = this.readMockVisualDefaults();
            return {
                schema: 'v_ase.user_preferences.v1',
                configured: Boolean(settings),
                settings: settings ? this.clone(settings) : null
            };
        }
        return await this.request(`/api/preferences/visual-defaults/{session_id}`);
    }

    async saveUserVisualDefaults(settings) {
        if (this.mock) {
            this.writeMockVisualDefaults(settings);
            return {
                schema: 'v_ase.user_preferences.v1',
                configured: true,
                settings: this.clone(settings)
            };
        }
        return await this.request(`/api/preferences/visual-defaults/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ settings })
        });
    }

    async clearUserVisualDefaults() {
        if (this.mock) {
            const removed = Boolean(this.readMockVisualDefaults());
            this.writeMockVisualDefaults(null);
            return {
                schema: 'v_ase.user_preferences.v1',
                configured: false,
                removed,
                settings: null
            };
        }
        return await this.request(`/api/preferences/visual-defaults/{session_id}`, {
            method: 'DELETE'
        });
    }

    async saveProject(positions, settings, applyConstraint = true) {
        const payload = this.framePayload({ positions, settings, apply_constraint: applyConstraint });
        return await this.request(`/api/project/save/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        }, { expect: 'blob' });
    }

    async fetchDisplacements(options = {}) {
        return await this.jsonPost(
            `/api/analysis/displacement/{session_id}`,
            this.framePayload(options)
        );
    }

    async fetchRdf(options = {}) {
        const payload = this.framePayload(options);
        if (Number.isInteger(Number(options.frame_index)) && Number(options.frame_index) >= 0) {
            payload.frame_index = Number(options.frame_index);
        }
        return await this.jsonPost(
            `/api/analysis/rdf/{session_id}`,
            payload
        );
    }

    async exportRdfCsv(options = {}) {
        return await this.request(`/api/analysis/rdf-csv/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(this.framePayload(options))
        }, { expect: 'blob' });
    }

    async fetchIsosurface(options = {}) {
        return await this.request(`/api/volumetric/isosurface/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(options)
        }, { expect: 'arrayBuffer' });
    }

    async fetchVolumetricPlane(options = {}) {
        return await this.request(`/api/volumetric/plane/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(options)
        }, { expect: 'arrayBuffer' });
    }

    async createVolumetricDifference(options = {}) {
        return await this.jsonPost(
            `/api/volumetric/difference/{session_id}`,
            options
        );
    }

    async deleteVolumetricDataset(datasetId) {
        return await this.jsonPost(
            `/api/volumetric/delete/{session_id}`,
            { dataset_id: datasetId }
        );
    }

    async loadProject(file) {
        const body = file instanceof Blob ? await file.arrayBuffer() : file;
        return await this.request(`/api/project/load/{session_id}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/octet-stream'},
            body
        });
    }

    async loadStructureFile(
        file,
        inputFormat = '',
        index = ':',
        volumetricPrecision = 'float32',
        runtimeMode = null
    ) {
        const params = new URLSearchParams({
            filename: file?.name || 'structure',
            index: index || ':',
            volumetric_precision: volumetricPrecision || 'float32'
        });
        if (inputFormat) params.set('input_format', inputFormat);
        if (runtimeMode === 'view' || runtimeMode === 'edit') {
            params.set('runtime_mode', runtimeMode);
        }
        return await this.request(`/api/file/load/{session_id}?${params.toString()}`, {
            method: 'POST',
            headers: {'Content-Type': file?.type || 'application/octet-stream'},
            body: file
        });
    }

    async appendStructureFile(
        file,
        inputFormat = '',
        index = ':',
        volumetricPrecision = 'float32',
        { emitMutation = true } = {}
    ) {
        const params = new URLSearchParams({
            filename: file?.name || 'structure',
            index: index || ':',
            volumetric_precision: volumetricPrecision || 'float32'
        });
        if (inputFormat) params.set('input_format', inputFormat);
        return await this.request(`/api/file/append/{session_id}?${params.toString()}`, {
            method: 'POST',
            headers: {'Content-Type': file?.type || 'application/octet-stream'},
            body: file
        }, { emitMutation });
    }

    async appendStructurePath(
        path,
        inputFormat = '',
        index = ':',
        volumetricPrecision = 'float32',
        { emitMutation = true } = {}
    ) {
        return await this.jsonPost(`/api/file/append-path/{session_id}`, {
            path,
            input_format: inputFormat || null,
            index: index || ':',
            volumetric_precision: volumetricPrecision || 'float32'
        }, { emitMutation });
    }

}
