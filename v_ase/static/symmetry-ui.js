class SymmetryPhononSupport {
    setupSymmetryPhononAnalysis() {
        document.getElementById('btn-analyze-symmetry')?.addEventListener(
            'click',
            () => this.analyzeCurrentSymmetry()
        );
        document.getElementById('btn-symmetry-path')?.addEventListener(
            'click',
            () => this.calculateHighSymmetryPath()
        );
        document.querySelectorAll('[data-symmetry-transform]').forEach(button => {
            button.addEventListener('click', () => {
                this.applySymmetryTransform(button.dataset.symmetryTransform);
            });
        });
        document.getElementById('btn-phonon-displacements')?.addEventListener(
            'click',
            () => this.createFiniteDisplacementTrajectory()
        );
        const projectInput = document.getElementById('phonopy-project-file');
        document.getElementById('btn-load-phonopy-project')?.addEventListener(
            'click',
            () => projectInput?.click()
        );
        projectInput?.addEventListener('change', () => {
            const file = projectInput.files?.[0];
            projectInput.value = '';
            if (file) this.loadPhonopyProject(file);
        });
        document.getElementById('btn-phonon-modes')?.addEventListener(
            'click',
            () => this.calculatePhononModes()
        );
        document.getElementById('btn-phonon-bands')?.addEventListener(
            'click',
            () => this.calculatePhononBandStructure()
        );
        ['phonon-q-x', 'phonon-q-y', 'phonon-q-z'].forEach(id => {
            document.getElementById(id)?.addEventListener('input', () => {
                this.state.phononSelectedNacDirection = null;
                this.state.phononBandSelection = null;
                this.updatePhononBandSelectionUI();
            });
        });
        document.getElementById('btn-phonon-modulate')?.addEventListener(
            'click',
            () => this.createPhononModeTrajectory()
        );
    }

    finiteScienceNumber(id, label, {
        minimum = -Infinity,
        maximum = Infinity,
        integer = false
    } = {}) {
        const input = document.getElementById(id);
        const value = Number(input?.value);
        if (!Number.isFinite(value)) throw new Error(`${label} must be finite.`);
        if (integer && !Number.isInteger(value)) throw new Error(`${label} must be an integer.`);
        if (value < minimum || value > maximum) {
            throw new Error(`${label} must be between ${minimum} and ${maximum}.`);
        }
        return value;
    }

    scienceVector(ids, label, options = {}) {
        return ids.map((id, index) => this.finiteScienceNumber(
            id,
            `${label} ${'xyz'[index]}`,
            options
        ));
    }

    symmetryAnalysisOptions() {
        const symprec = this.finiteScienceNumber(
            'symmetry-symprec',
            'Position tolerance',
            { minimum: 1e-8, maximum: 1 }
        );
        const angleTolerance = this.finiteScienceNumber(
            'symmetry-angle-tolerance',
            'Angle tolerance',
            { minimum: -1, maximum: 180 }
        );
        const positions = this.state.vizOnly
            ? this.state.atoms?.positions
            : this.backendPositionsPayload();
        return {
            symprec,
            angle_tolerance: angleTolerance,
            type_basis: document.getElementById('symmetry-type-basis')?.value === 'label'
                ? 'label'
                : 'element',
            magnetic: Boolean(document.getElementById('chk-symmetry-magnetic')?.checked),
            positions
        };
    }

    setScienceStatus(id, state, title, detail = '') {
        const status = document.getElementById(id);
        if (!status) return;
        status.dataset.state = state;
        const titleElement = status.querySelector('.analysis-status-title');
        const detailElement = status.querySelector('.analysis-status-detail');
        if (titleElement) titleElement.textContent = title;
        if (detailElement) detailElement.textContent = detail;
    }

    async analyzeCurrentSymmetry() {
        try {
            const options = this.symmetryAnalysisOptions();
            options.tolerances = [
                options.symprec / 100,
                options.symprec / 10,
                options.symprec,
                options.symprec * 10,
                options.symprec * 100
            ].filter(value => value >= 1e-8 && value <= 1);
            this.setScienceStatus(
                'symmetry-status',
                'loading',
                'Analyzing symmetry',
                `spglib tolerance ${options.symprec} A`
            );
            const result = await this.withBusy(
                'Analyzing crystallographic symmetry...',
                () => this.api.analyzeSymmetry(options)
            );
            this.state.symmetryResult = result;
            this.renderSymmetryResult(result);
        } catch (error) {
            this.setScienceStatus('symmetry-status', 'warning', 'Symmetry unavailable', error.message);
            this.toast(`Symmetry analysis failed: ${error.message}`, 'error');
        }
    }

    renderSymmetryResult(result) {
        const container = document.getElementById('symmetry-result');
        if (!container) return;
        const text = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = `${value ?? '-'}`;
        };
        if (result.kind === 'magnetic') {
            container.classList.add('hidden');
            this.setScienceStatus(
                'symmetry-status',
                'ready',
                `Magnetic space group UNI ${result.uni_number}`,
                `${result.operation_count} operations; type ${result.magnetic_spacegroup_type}.`
            );
            return;
        }
        container.classList.remove('hidden');
        text('symmetry-spacegroup', result.international);
        text('symmetry-number', `No. ${result.number}`);
        text('symmetry-pointgroup', result.pointgroup);
        text('symmetry-crystal-system', result.crystal_system);
        text('symmetry-operation-count', result.operation_count);
        text('symmetry-orbit-count', result.orbits?.length || 0);
        const orbitList = document.getElementById('symmetry-orbits');
        orbitList?.replaceChildren(...(result.orbits || []).map(orbit => {
            const row = document.createElement('div');
            row.className = 'symmetry-orbit-row';
            const number = document.createElement('strong');
            number.textContent = `${orbit.orbit}`;
            const site = document.createElement('span');
            site.textContent = `${orbit.wyckoff}  ${orbit.site_symmetry || '-'}`;
            const identity = document.createElement('span');
            const labels = (orbit.labels || []).join(', ');
            identity.textContent = `${labels || orbit.element} | ${orbit.multiplicity} atom${orbit.multiplicity === 1 ? '' : 's'}`;
            identity.title = `Indices: ${(orbit.indices || []).join(', ')}`;
            row.append(number, site, identity);
            return row;
        }));
        const warnings = (result.warnings || []).join(' ');
        const scan = result.tolerance_scan || [];
        const stableGroups = new Set(
            scan.filter(item => !item.error).map(item => `${item.number}:${item.international}`)
        );
        const stability = scan.length
            ? `${stableGroups.size === 1 ? 'Stable' : 'Changes'} across ${scan.length} tested tolerances.`
            : '';
        this.setScienceStatus(
            'symmetry-status',
            warnings ? 'warning' : 'ready',
            `${result.international} (No. ${result.number})`,
            [stability, warnings].filter(Boolean).join(' ')
        );
    }

    invalidateScientificResults() {
        this.state.symmetryResult = null;
        this.state.symmetryPath = null;
        this.state.phononBandStructure = null;
        this.state.phononBandSelection = null;
        this.state.phononSelectedNacDirection = null;
        this.state.phononModes = null;
        this.state.phononTrajectoryMetadata = null;
        this.state.phononBandRequestToken += 1;
        this.state.phononBandCalculationPending = false;
        document.getElementById('symmetry-result')?.classList.add('hidden');
        document.getElementById('symmetry-orbits')?.replaceChildren();
        document.getElementById('symmetry-path-result')?.classList.add('hidden');
        document.getElementById('phonon-mode-result')?.classList.add('hidden');
        document.getElementById('phonon-band-result')?.classList.add('hidden');
        this.setScienceStatus(
            'symmetry-status',
            'idle',
            'Not analyzed',
            'Inspect the current frame with spglib.'
        );
        this.setScienceStatus(
            'phonon-band-status',
            'idle',
            'Band structure unavailable',
            'Load force constants to calculate the HPKOT path.'
        );
    }

    async calculateHighSymmetryPath() {
        try {
            const result = await this.withBusy(
                'Calculating the standard reciprocal path...',
                () => this.api.fetchHighSymmetryPath(this.symmetryAnalysisOptions())
            );
            this.state.symmetryPath = result;
            const container = document.getElementById('symmetry-path-result');
            if (container) {
                container.classList.remove('hidden');
                const segments = (result.path || [])
                    .map(([start, end]) => `${start} -> ${end}`)
                    .join(' | ');
                container.textContent = [
                    `${result.bravais_lattice || '-'} / ${result.spacegroup_international || '-'} No. ${result.spacegroup_number ?? '-'}`,
                    segments || 'No path segments returned.'
                ].join('\n');
            }
            this.toast('Calculated the HPKOT high-symmetry path.', 'success');
        } catch (error) {
            this.toast(`Reciprocal path failed: ${error.message}`, 'error');
        }
    }

    async applySymmetryTransform(mode) {
        if (!['primitive', 'conventional', 'refine'].includes(mode)) return;
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        const accepted = await this.showConfirmModal({
            title: `Create ${mode} structure?`,
            intro: 'This replaces the loaded trajectory with one standardized frame.',
            items: [
                'Atom ordering and atom count may change.',
                'Constraints and calculators are removed when no exact mapping exists.',
                'The complete replacement can be undone with Ctrl+Z.'
            ],
            confirmText: `Create ${mode}`
        });
        if (!accepted) return;
        try {
            const result = await this.withBusy(
                `Creating ${mode} structure...`,
                () => this.api.transformBySymmetry({
                    ...this.symmetryAnalysisOptions(),
                    mode,
                    idealize: true
                })
            );
            const metadata = result.symmetry_transform || {};
            this.setAtomsData(result, { clearSelection: true });
            const warnings = (metadata.warnings || []).join(' ');
            this.toast(
                `${mode[0].toUpperCase()}${mode.slice(1)} structure created: ${metadata.source_atom_count ?? '-'} -> ${metadata.result_atom_count ?? '-'} atoms.${warnings ? ` ${warnings}` : ''}`,
                warnings ? 'warning' : 'success'
            );
            await this.analyzeCurrentSymmetry();
        } catch (error) {
            this.toast(`Symmetry transform failed: ${error.message}`, 'error');
        }
    }

    async createFiniteDisplacementTrajectory() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        let supercell;
        let distance;
        try {
            supercell = this.scienceVector(
                ['phonon-super-x', 'phonon-super-y', 'phonon-super-z'],
                'Supercell',
                { minimum: 1, maximum: 20, integer: true }
            );
            distance = this.finiteScienceNumber(
                'phonon-displacement-distance',
                'Displacement',
                { minimum: 1e-6, maximum: 1 }
            );
        } catch (error) {
            this.toast(error.message, 'error');
            return;
        }
        const accepted = await this.showConfirmModal({
            title: 'Generate finite-displacement inputs?',
            intro: 'The current trajectory will be replaced by symmetry-reduced calculation inputs.',
            items: [
                `Supercell: ${supercell.join(' x ')}; displacement: ${distance} A.`,
                'These frames do not contain forces and are not physical phonon modes.',
                'Use Ctrl+Z to restore the current trajectory.'
            ],
            confirmText: 'Generate inputs'
        });
        if (!accepted) return;
        try {
            const result = await this.withBusy(
                'Generating symmetry-reduced finite displacements...',
                () => this.api.generatePhononDisplacements({
                    supercell_matrix: supercell,
                    distance,
                    symprec: this.symmetryAnalysisOptions().symprec,
                    positions: this.backendPositionsPayload()
                })
            );
            const metadata = result.phonon || {};
            this.state.phononModelSummary = metadata;
            this.state.phononBandStructure = null;
            this.state.phononBandSelection = null;
            this.state.phononSelectedNacDirection = null;
            this.state.phononModes = null;
            this.state.phononTrajectoryMetadata = null;
            this.setAtomsData(result, { clearSelection: true });
            this.state.display.displacementReferenceMode = 'phonon';
            this.syncDisplacementControls();
            this.renderer.setDisplayOptions(this.state.display);
            this.renderPhononModelSummary(metadata);
            this.setScienceStatus(
                'phonon-band-status',
                'warning',
                'Force constants required',
                'Calculate forces for every displaced frame, then load the completed project.'
            );
            document.getElementById('phonon-band-result')?.classList.add('hidden');
            document.getElementById('phonon-mode-result')?.classList.add('hidden');
            this.toast(
                `Generated ${metadata.displacement_count || result.metadata?.frame_count || 0} finite-displacement inputs. Forces are still required.`,
                'success'
            );
        } catch (error) {
            this.toast(`Finite displacement generation failed: ${error.message}`, 'error');
        }
    }

    async loadPhonopyProject(file) {
        try {
            const result = await this.withBusy(
                `Loading ${file.name}...`,
                () => this.api.loadPhonopyProject(file)
            );
            this.state.phononModelSummary = result;
            this.state.phononBandStructure = null;
            this.state.phononBandSelection = null;
            this.state.phononSelectedNacDirection = null;
            this.state.phononModes = null;
            this.state.phononTrajectoryMetadata = null;
            this.renderPhononModelSummary(result);
            document.getElementById('phonon-mode-result')?.classList.add('hidden');
            this.toast(
                result.has_force_constants
                    ? 'Loaded phonopy force constants.'
                    : 'Loaded phonopy project, but it does not contain force constants.',
                result.has_force_constants ? 'success' : 'warning'
            );
            if (result.has_force_constants) {
                await this.calculatePhononBandStructure({ silent: true });
            } else {
                this.setScienceStatus(
                    'phonon-band-status',
                    'warning',
                    'Force constants required',
                    'This project contains calculation inputs but no physical dispersion.'
                );
            }
        } catch (error) {
            this.setScienceStatus(
                'phonon-model-status',
                'warning',
                'Could not load phonopy project',
                error.message
            );
            this.toast(`Phonopy load failed: ${error.message}`, 'error');
        }
    }

    renderPhononModelSummary(result) {
        if (!result) {
            this.setScienceStatus(
                'phonon-model-status',
                'idle',
                'No phonopy model',
                'Load a phonopy YAML that contains force constants.'
            );
            return;
        }
        const supercell = Array.isArray(result.supercell_matrix)
            ? result.supercell_matrix.map(row => row.join(' ')).join('; ')
            : '-';
        this.setScienceStatus(
            'phonon-model-status',
            result.has_force_constants ? 'ready' : 'warning',
            result.has_force_constants ? 'Force constants ready' : 'Calculation inputs only',
            `${result.unit_atoms ?? '-'} unit atoms; ${result.supercell_atoms ?? '-'} supercell atoms; P=[${supercell}].`
        );
    }

    async calculatePhononBandStructure({ silent = false } = {}) {
        if (this.state.phononBandCalculationPending) return null;
        this.state.phononBandCalculationPending = true;
        const token = ++this.state.phononBandRequestToken;
        let referenceDistance;
        try {
            referenceDistance = this.finiteScienceNumber(
                'phonon-band-spacing',
                'Band spacing',
                { minimum: 0.005, maximum: 1 }
            );
        } catch (error) {
            this.toast(error.message, 'error');
            this.state.phononBandCalculationPending = false;
            return null;
        }
        this.setScienceStatus(
            'phonon-band-status',
            'loading',
            'Calculating band structure',
            `SeeK-path HPKOT spacing ${referenceDistance} 1/A`
        );
        try {
            const request = () => this.api.fetchPhononBandStructure({
                reference_distance: referenceDistance,
                symprec: this.finiteScienceNumber(
                    'symmetry-symprec',
                    'Position tolerance',
                    { minimum: 1e-8, maximum: 1 }
                ),
                angle_tolerance: this.finiteScienceNumber(
                    'symmetry-angle-tolerance',
                    'Angle tolerance',
                    { minimum: -1, maximum: 180 }
                )
            });
            const result = silent
                ? await request()
                : await this.withBusy('Calculating the phonon band structure...', request);
            if (token !== this.state.phononBandRequestToken) return null;
            this.state.phononBandStructure = result;
            this.state.phononBandSelection = null;
            this.state.phononSelectedNacDirection = null;
            this.renderPhononBandStructure(result);
            this.setScienceStatus(
                'phonon-band-status',
                result.has_imaginary ? 'warning' : 'ready',
                `${result.bravais_lattice} phonon dispersion`,
                `${result.qpoint_count} q-points; ${result.band_count} bands; ${result.convention} path.`
            );
            if (!silent) this.toast('Calculated the interactive phonon band structure.', 'success');
            return result;
        } catch (error) {
            if (token !== this.state.phononBandRequestToken) return null;
            this.state.phononBandStructure = null;
            this.state.phononBandSelection = null;
            document.getElementById('phonon-band-result')?.classList.add('hidden');
            this.setScienceStatus(
                'phonon-band-status',
                'warning',
                'Band structure unavailable',
                error.message
            );
            this.toast(`Phonon band structure failed: ${error.message}`, 'error');
            return null;
        } finally {
            if (token === this.state.phononBandRequestToken) {
                this.state.phononBandCalculationPending = false;
            }
        }
    }

    phononBandLabel(label) {
        return String(label || '').replaceAll('GAMMA', 'Γ');
    }

    phononBandPointLabel(point) {
        if (!point) return '';
        if (point.pathLabel) return this.phononBandLabel(point.pathLabel);
        const tick = (this.state.phononBandStructure?.ticks || []).find(item => (
            Math.abs(Number(item.distance) - Number(point.distance)) <= 1e-9
        ));
        return this.phononBandLabel(tick?.label || '');
    }

    phononBandPointShortText(point) {
        if (!point) return '';
        const label = this.phononBandPointLabel(point);
        const location = label ? `${label} · ` : '';
        return `${location}ν${point.band} · ${Number(point.frequency).toFixed(3)} THz`;
    }

    phononBandPointText(point) {
        if (!point) return 'Point at a branch, then click to select q and ν.';
        const label = this.phononBandPointLabel(point);
        const location = label ? `${label} · ` : '';
        const q = point.qpoint.map(value => Number(value).toFixed(4)).join(', ');
        const frequency = Number(point.frequency).toFixed(4);
        const dimension = Array.isArray(point.dimension)
            ? ` | mode cell ${point.dimension.join(' x ')}`
            : ' | no small diagonal mode cell found';
        const imaginary = point.frequency < -1e-8 ? ' (imaginary)' : '';
        return `Selected ${location}ν${point.band} | q=(${q}) | ${frequency} THz${imaginary}${dimension}`;
    }

    phononBandNearestPoint(event) {
        const plot = document.getElementById('phonon-band-plot');
        const result = this.state.phononBandStructure;
        const geometry = plot?.__vAseBandGeometry;
        if (!plot || !result || !geometry) return null;
        const rect = plot.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return null;
        const px = (event.clientX - rect.left) * geometry.width / rect.width;
        const py = (event.clientY - rect.top) * geometry.height / rect.height;
        let nearest = null;
        let nearestDistance = Infinity;
        (result.segments || []).forEach((segment, segmentIndex) => {
            (segment.distances || []).forEach((distance, pointIndex) => {
                const x = geometry.x(Number(distance));
                (segment.frequencies?.[pointIndex] || []).forEach((frequency, bandIndex) => {
                    const y = geometry.y(Number(frequency));
                    const metric = (x - px) ** 2 + (y - py) ** 2;
                    if (metric >= nearestDistance) return;
                    nearestDistance = metric;
                    nearest = {
                        segmentIndex,
                        pointIndex,
                        band: bandIndex + 1,
                        distance: Number(distance),
                        qpoint: [...segment.qpoints[pointIndex]],
                        frequency: Number(frequency),
                        nacDirection: segment.nac_directions?.[pointIndex]
                            ? [...segment.nac_directions[pointIndex]]
                            : null,
                        dimension: segment.suggested_dimensions?.[pointIndex]
                            ? [...segment.suggested_dimensions[pointIndex]]
                            : null,
                        pathLabel: (result.ticks || []).find(item => (
                            Math.abs(Number(item.distance) - Number(distance)) <= 1e-9
                        ))?.label || '',
                        x,
                        y
                    };
                });
            });
        });
        return nearest;
    }

    updatePhononBandCursor(point, { selected = false } = {}) {
        const plot = document.getElementById('phonon-band-plot');
        if (!plot) return;
        const prefix = selected ? 'selected' : 'hover';
        const line = plot.querySelector(`.phonon-band-${prefix}-line`);
        const horizontal = plot.querySelector(`.phonon-band-${prefix}-horizontal`);
        const halo = plot.querySelector(`.phonon-band-${prefix}-halo`);
        const marker = plot.querySelector(`.phonon-band-${prefix}-point`);
        const tag = plot.querySelector(`.phonon-band-${prefix}-tag`);
        const tagText = tag?.querySelector('text');
        if (!marker || !tag) return;
        if (!point) {
            line?.setAttribute('visibility', 'hidden');
            horizontal?.setAttribute('visibility', 'hidden');
            halo?.setAttribute('visibility', 'hidden');
            marker.setAttribute('visibility', 'hidden');
            tag.setAttribute('visibility', 'hidden');
            return;
        }
        const geometry = plot.__vAseBandGeometry;
        if (line) {
            line.setAttribute('x1', `${point.x}`);
            line.setAttribute('x2', `${point.x}`);
            line.setAttribute('visibility', 'visible');
        }
        if (horizontal) {
            horizontal.setAttribute('x1', `${geometry?.margin?.left ?? 0}`);
            horizontal.setAttribute('x2', `${point.x}`);
            horizontal.setAttribute('y1', `${point.y}`);
            horizontal.setAttribute('y2', `${point.y}`);
            horizontal.setAttribute('visibility', 'visible');
        }
        if (halo) {
            halo.setAttribute('cx', `${point.x}`);
            halo.setAttribute('cy', `${point.y}`);
            halo.setAttribute('visibility', 'visible');
        }
        marker.setAttribute('cx', `${point.x}`);
        marker.setAttribute('cy', `${point.y}`);
        marker.setAttribute('visibility', 'visible');
        const tagWidth = selected ? 92 : 138;
        const tagHeight = 25;
        const width = geometry?.width || 640;
        const height = geometry?.height || 350;
        const tagX = point.x + tagWidth + 18 > width
            ? point.x - tagWidth - 10
            : point.x + 10;
        const tagY = point.y < 44
            ? point.y + 10
            : Math.min(height - tagHeight - 5, point.y - tagHeight - 9);
        tag.setAttribute('transform', `translate(${tagX} ${tagY})`);
        tag.setAttribute('visibility', 'visible');
        if (tagText) {
            const pointLabel = this.phononBandPointLabel(point) || 'q';
            tagText.textContent = selected
                ? `${pointLabel} · ν${point.band}`
                : this.phononBandPointShortText(point);
        }
    }

    updatePhononBandSelectionUI(point = this.state.phononBandSelection) {
        const output = document.getElementById('phonon-band-selection');
        if (output) output.textContent = this.phononBandPointText(point);
        const selection = output?.closest('.phonon-band-selection');
        if (selection) selection.dataset.state = point ? 'selected' : 'idle';
        const meta = document.getElementById('phonon-band-meta');
        if (meta) {
            const result = this.state.phononBandStructure;
            meta.textContent = point
                ? this.phononBandPointShortText(point)
                : `${result?.convention || '-'} · q path · ${result?.frequency_unit || 'THz'}`;
        }
        const plot = document.getElementById('phonon-band-plot');
        plot?.querySelectorAll('.phonon-band-branch').forEach(path => {
            path.classList.toggle(
                'is-selected',
                Boolean(point) && Number(path.dataset.band) === Number(point.band)
            );
        });
        this.updatePhononBandCursor(point, { selected: true });
    }

    renderPhononBandStructure(result) {
        const container = document.getElementById('phonon-band-result');
        const plot = document.getElementById('phonon-band-plot');
        if (!container || !plot || !result?.segments?.length) return;
        container.classList.remove('hidden');
        const title = document.getElementById('phonon-band-title');
        const meta = document.getElementById('phonon-band-meta');
        if (title) title.textContent = `${result.spacegroup_international} phonons`;
        if (meta) meta.textContent = `${result.convention} · ${result.frequency_unit}`;

        const svg = (name, attributes = {}, text = '') => {
            const element = document.createElementNS('http://www.w3.org/2000/svg', name);
            Object.entries(attributes).forEach(([key, value]) => {
                element.setAttribute(key, `${value}`);
            });
            if (text) element.textContent = text;
            return element;
        };
        const margin = { left: 62, right: 17, top: 17, bottom: 66 };
        const width = 640;
        const height = 350;
        const xMin = Number(result.ticks?.[0]?.distance ?? result.segments[0].distances[0]);
        const xMax = Number(
            result.ticks?.[result.ticks.length - 1]?.distance
            ?? result.segments[result.segments.length - 1].distances.at(-1)
        );
        const rawMin = Math.min(0, Number(result.frequency_min));
        const rawMax = Math.max(0, Number(result.frequency_max));
        const frequencySpan = Math.max(1e-6, rawMax - rawMin);
        const yMin = rawMin - frequencySpan * 0.07;
        const yMax = rawMax + frequencySpan * 0.07;
        const x = value => margin.left + (Number(value) - xMin) / Math.max(1e-12, xMax - xMin)
            * (width - margin.left - margin.right);
        const y = value => height - margin.bottom - (Number(value) - yMin) / (yMax - yMin)
            * (height - margin.top - margin.bottom);
        plot.setAttribute('viewBox', `0 0 ${width} ${height}`);
        plot.__vAseBandGeometry = { x, y, yMin, yMax, width, height, margin };
        plot.replaceChildren();

        const yTicks = 5;
        for (let index = 0; index <= yTicks; index += 1) {
            const frequency = yMin + (yMax - yMin) * index / yTicks;
            const py = y(frequency);
            plot.append(
                svg('line', {
                    x1: margin.left,
                    y1: py,
                    x2: width - margin.right,
                    y2: py,
                    class: 'phonon-band-grid'
                }),
                svg('text', {
                    x: margin.left - 8,
                    y: py + 5,
                    'text-anchor': 'end',
                    class: 'phonon-band-axis-label'
                }, frequency.toFixed(1))
            );
        }
        if (yMin < 0 && yMax > 0) {
            plot.append(svg('line', {
                x1: margin.left,
                y1: y(0),
                x2: width - margin.right,
                y2: y(0),
                class: 'phonon-band-zero'
            }));
        }
        (result.ticks || []).forEach(tick => {
            const px = x(tick.distance);
            plot.append(
                svg('line', {
                    x1: px,
                    y1: margin.top,
                    x2: px,
                    y2: height - margin.bottom,
                    class: 'phonon-band-tick-line'
                }),
                svg('text', {
                    x: px,
                    y: height - 35,
                    'text-anchor': 'middle',
                    class: 'phonon-band-label'
                }, this.phononBandLabel(tick.label))
            );
        });
        plot.append(svg('text', {
            x: (margin.left + width - margin.right) / 2,
            y: height - 9,
            'text-anchor': 'middle',
            class: 'phonon-band-axis-title'
        }, 'Wavevector path q'));
        plot.append(svg('text', {
            x: 17,
            y: (margin.top + height - margin.bottom) / 2,
            transform: `rotate(-90 17 ${(margin.top + height - margin.bottom) / 2})`,
            'text-anchor': 'middle',
            class: 'phonon-band-axis-label'
        }, 'Frequency (THz)'));

        for (let bandIndex = 0; bandIndex < Number(result.band_count); bandIndex += 1) {
            result.segments.forEach(segment => {
                const commands = (segment.distances || []).map((distance, pointIndex) => {
                    const frequency = segment.frequencies?.[pointIndex]?.[bandIndex];
                    return `${pointIndex === 0 ? 'M' : 'L'} ${x(distance).toFixed(3)} ${y(frequency).toFixed(3)}`;
                }).join(' ');
                plot.append(svg('path', {
                    d: commands,
                    class: 'phonon-band-branch',
                    'data-band': bandIndex + 1
                }));
            });
        }
        plot.append(
            svg('line', {
                x1: 0,
                y1: margin.top,
                x2: 0,
                y2: height - margin.bottom,
                visibility: 'hidden',
                class: 'phonon-band-selected-line'
            }),
            svg('line', {
                x1: margin.left,
                y1: 0,
                x2: margin.left,
                y2: 0,
                visibility: 'hidden',
                class: 'phonon-band-selected-horizontal'
            }),
            svg('circle', {
                cx: 0,
                cy: 0,
                r: 10,
                visibility: 'hidden',
                class: 'phonon-band-selected-halo'
            }),
            svg('circle', {
                cx: 0,
                cy: 0,
                r: 6.5,
                visibility: 'hidden',
                class: 'phonon-band-selected-point'
            }),
            (() => {
                const group = svg('g', {
                    visibility: 'hidden',
                    class: 'phonon-band-selected-tag'
                });
                group.append(
                    svg('rect', { width: 92, height: 25, rx: 4 }),
                    svg('text', { x: 8, y: 17 })
                );
                return group;
            })(),
            svg('circle', {
                cx: 0,
                cy: 0,
                r: 5,
                visibility: 'hidden',
                class: 'phonon-band-hover-point'
            }),
            (() => {
                const group = svg('g', {
                    visibility: 'hidden',
                    class: 'phonon-band-hover-tag'
                });
                group.append(
                    svg('rect', { width: 138, height: 25, rx: 4 }),
                    svg('text', { x: 8, y: 17 })
                );
                return group;
            })()
        );
        plot.onpointermove = event => {
            const point = this.phononBandNearestPoint(event);
            this.updatePhononBandCursor(point);
        };
        plot.onpointerleave = () => this.updatePhononBandCursor(null);
        plot.onclick = event => {
            const point = this.phononBandNearestPoint(event);
            if (point) this.selectPhononBandPoint(point);
        };
        this.updatePhononBandSelectionUI();
    }

    async selectPhononBandPoint(point) {
        this.state.phononBandSelection = { ...point };
        this.state.phononSelectedNacDirection = point.nacDirection
            ? [...point.nacDirection]
            : null;
        ['phonon-q-x', 'phonon-q-y', 'phonon-q-z'].forEach((id, index) => {
            const input = document.getElementById(id);
            if (input) input.value = Number(point.qpoint[index]).toPrecision(10).replace(/\.?0+$/, '');
        });
        const bandInput = document.getElementById('phonon-mode-band');
        if (bandInput) bandInput.value = `${point.band}`;
        if (Array.isArray(point.dimension)) {
            ['phonon-mode-super-x', 'phonon-mode-super-y', 'phonon-mode-super-z'].forEach((id, index) => {
                const input = document.getElementById(id);
                if (input) input.value = `${point.dimension[index]}`;
            });
        }
        this.updatePhononBandSelectionUI();
        await this.calculatePhononModes({ preferredBand: point.band, silent: true });
    }

    phononQPoint() {
        return this.scienceVector(
            ['phonon-q-x', 'phonon-q-y', 'phonon-q-z'],
            'q-point'
        );
    }

    async calculatePhononModes({ preferredBand = null, silent = false } = {}) {
        try {
            const axis = document.getElementById('phonon-projection-axis')?.value;
            const projection = {
                x: [1, 0, 0],
                y: [0, 1, 0],
                z: [0, 0, 1]
            }[axis] || null;
            const request = () => this.api.fetchPhononModes({
                    qpoint: this.phononQPoint(),
                    nac_direction: this.state.phononSelectedNacDirection,
                    projection_direction: projection
                });
            const result = silent
                ? await request()
                : await this.withBusy('Diagonalizing the dynamical matrix...', request);
            this.state.phononModes = result;
            this.renderPhononModes(result, preferredBand);
            if (!silent) {
                this.toast(`Calculated ${result.band_count} modes at q=(${result.qpoint.join(', ')}).`, 'success');
            }
            return result;
        } catch (error) {
            this.toast(`Phonon mode calculation failed: ${error.message}`, 'error');
            return null;
        }
    }

    renderPhononModes(result, preferredBand = null) {
        const container = document.getElementById('phonon-mode-result');
        if (!container) return;
        const requestedBand = Number(
            preferredBand ?? document.getElementById('phonon-mode-band')?.value ?? 1
        );
        container.classList.remove('hidden');
        container.replaceChildren(...(result.bands || []).map(mode => {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'phonon-mode-row';
            row.setAttribute('aria-selected', mode.band === requestedBand ? 'true' : 'false');
            const band = document.createElement('strong');
            band.textContent = `${mode.band}`;
            const frequency = document.createElement('span');
            frequency.className = `phonon-mode-frequency${mode.imaginary ? ' imaginary' : ''}`;
            frequency.textContent = `${Number(mode.frequency_thz).toFixed(4)} THz`;
            const character = document.createElement('span');
            const longitudinal = Number.isFinite(mode.longitudinal_fraction)
                ? `, L ${(100 * mode.longitudinal_fraction).toFixed(0)}%`
                : '';
            const projected = Number.isFinite(mode.directional_fraction)
                ? `, P ${(100 * mode.directional_fraction).toFixed(0)}%`
                : '';
            character.textContent = `${String(mode.dominant_axis || '-').toUpperCase()} dominant${longitudinal}${projected}`;
            row.append(band, frequency, character);
            row.addEventListener('click', () => {
                document.getElementById('phonon-mode-band').value = `${mode.band}`;
                if (this.state.phononBandSelection) {
                    this.state.phononBandSelection.band = mode.band;
                    this.state.phononBandSelection.frequency = mode.frequency_thz;
                    const geometry = document.getElementById('phonon-band-plot')?.__vAseBandGeometry;
                    if (geometry) this.state.phononBandSelection.y = geometry.y(mode.frequency_thz);
                    this.updatePhononBandSelectionUI();
                }
                container.querySelectorAll('.phonon-mode-row').forEach(item => {
                    item.setAttribute('aria-selected', item === row ? 'true' : 'false');
                });
            });
            return row;
        }));
        const bandInput = document.getElementById('phonon-mode-band');
        if (bandInput) bandInput.max = `${Math.max(1, Number(result.band_count) || 1)}`;
    }

    async createPhononModeTrajectory() {
        if (!this.canEditAtoms()) {
            this.editOnlyToast();
            return;
        }
        let options;
        try {
            options = {
                qpoint: this.phononQPoint(),
                band: this.finiteScienceNumber(
                    'phonon-mode-band',
                    'Band',
                    { minimum: 1, maximum: 100000, integer: true }
                ),
                amplitude: this.finiteScienceNumber(
                    'phonon-mode-amplitude',
                    'Amplitude',
                    { minimum: 0, maximum: 10 }
                ),
                phase_degrees: this.finiteScienceNumber(
                    'phonon-mode-phase',
                    'Phase',
                    { minimum: -1000000, maximum: 1000000 }
                ),
                frames: this.finiteScienceNumber(
                    'phonon-mode-frames',
                    'Frames',
                    { minimum: 1, maximum: 240, integer: true }
                ),
                dimension: this.scienceVector(
                    ['phonon-mode-super-x', 'phonon-mode-super-y', 'phonon-mode-super-z'],
                    'Mode supercell',
                    { minimum: 1, maximum: 50, integer: true }
                ),
                oscillation: Boolean(document.getElementById('chk-phonon-oscillation')?.checked),
                nac_direction: this.state.phononSelectedNacDirection
            };
        } catch (error) {
            this.toast(error.message, 'error');
            return;
        }
        const accepted = await this.showConfirmModal({
            title: 'Create phonon-mode trajectory?',
            intro: 'This replaces the current trajectory with the selected mass-weighted phonon mode.',
            items: [
                `q=(${options.qpoint.join(', ')}), band ${options.band}, amplitude ${options.amplitude} A.`,
                `Mode supercell: ${options.dimension.join(' x ')}; frames: ${options.frames}.`,
                'The q-point must be commensurate with the selected mode supercell.'
            ],
            confirmText: 'Create trajectory'
        });
        if (!accepted) return;
        const previousPhononTrajectoryMetadata = this.state.phononTrajectoryMetadata;
        this.state.phononTrajectoryMetadata = null;
        try {
            const scientificState = {
                phononModelSummary: this.state.phononModelSummary,
                phononBandStructure: this.state.phononBandStructure,
                phononBandSelection: this.state.phononBandSelection
                    ? { ...this.state.phononBandSelection }
                    : null,
                phononSelectedNacDirection: this.state.phononSelectedNacDirection
                    ? [...this.state.phononSelectedNacDirection]
                    : null,
                phononModes: this.state.phononModes
            };
            const result = await this.withBusy(
                'Generating the phonon-mode trajectory...',
                () => this.api.generatePhononModeTrajectory(options)
            );
            const metadata = result.phonon || {};
            this.setAtomsData(result, { clearSelection: true });
            Object.assign(this.state, scientificState);
            this.state.display.displacementReferenceMode = 'phonon';
            this.syncDisplacementControls();
            this.renderer.setDisplayOptions(this.state.display);
            this.state.phononTrajectoryMetadata = { ...metadata };
            this.renderPhononModelSummary(scientificState.phononModelSummary);
            if (scientificState.phononBandStructure) {
                this.renderPhononBandStructure(scientificState.phononBandStructure);
                const bands = scientificState.phononBandStructure;
                this.setScienceStatus(
                    'phonon-band-status',
                    bands.has_imaginary ? 'warning' : 'ready',
                    `${bands.bravais_lattice} phonon dispersion`,
                    `${bands.qpoint_count} q-points; ${bands.band_count} bands; ${bands.convention} path.`
                );
            }
            if (scientificState.phononModes) {
                this.renderPhononModes(scientificState.phononModes, options.band);
            }
            this.toast(
                `Created ${metadata.frame_count || 1} frame${metadata.frame_count === 1 ? '' : 's'} for band ${metadata.band}; ${Number(metadata.frequency_thz).toFixed(4)} THz.`,
                metadata.imaginary ? 'warning' : 'success'
            );
        } catch (error) {
            this.state.phononTrajectoryMetadata = previousPhononTrajectoryMetadata;
            this.toast(`Phonon trajectory failed: ${error.message}`, 'error');
        }
    }
}

export function installSymmetryPhononMethods(AppClass) {
    for (const name of Object.getOwnPropertyNames(SymmetryPhononSupport.prototype)) {
        if (name === 'constructor') continue;
        Object.defineProperty(
            AppClass.prototype,
            name,
            Object.getOwnPropertyDescriptor(SymmetryPhononSupport.prototype, name)
        );
    }
}
