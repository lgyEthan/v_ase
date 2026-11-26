import * as THREE from 'three';
import { TrajectoryEnergyOverlay } from './trajectory_energy.js';
import { ASERenderer } from './renderer.js';
import { rdfPlotlyTrace, rdfSeriesStyles } from './distribution_plot.js';

function finiteVector(value, fallback) {
    if (
        Array.isArray(value)
        && value.length === 3
        && value.every(item => Number.isFinite(Number(item)))
    ) {
        return value.map(Number);
    }
    return [...fallback];
}

function clampFrame(index, count) {
    return Math.max(0, Math.min(Math.max(0, count - 1), Math.round(Number(index) || 0)));
}

function bytesFromBase64(source) {
    const binary = atob(String(source || '').replace(/\s+/g, ''));
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index++) {
        bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
}

function applyCamera(renderer, settings) {
    const source = settings?.camera || {};
    const projection = source.projection === 'perspective' ? 'perspective' : 'orthographic';
    renderer.setProjectionMode(projection);
    const camera = renderer.camera;
    const position = finiteVector(source.position, [10, 10, 10]);
    const target = finiteVector(source.target, [0, 0, 0]);
    const up = finiteVector(source.up, [0, 0, 1]);
    camera.position.fromArray(position);
    camera.up.fromArray(up).normalize();
    renderer.controls.target.fromArray(target);

    const near = Number(source.near);
    const far = Number(source.far);
    if (Number.isFinite(near) && near > 0) camera.near = near;
    if (Number.isFinite(far) && far > camera.near) camera.far = far;
    if (camera.isPerspectiveCamera) {
        const fov = Number(source.fov);
        const zoom = Number(source.zoom);
        if (Number.isFinite(fov) && fov > 1 && fov < 179) camera.fov = fov;
        camera.zoom = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
    } else {
        const scale = Number(source.ortho_scale);
        if (Number.isFinite(scale) && scale > 0) {
            const aspect = Math.max(
                0.01,
                renderer.container.clientWidth / Math.max(1, renderer.container.clientHeight)
            );
            camera.zoom = 1;
            camera.top = scale * 0.5;
            camera.bottom = -scale * 0.5;
            camera.left = -scale * 0.5 * aspect;
            camera.right = scale * 0.5 * aspect;
        }
    }
    camera.lookAt(renderer.controls.target);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
    renderer.requestRender();
}

function sizeViewerFrame(savedAspect) {
    const stage = document.querySelector('.viewer-stage');
    const frame = document.getElementById('viewer-frame');
    if (!stage || !frame) return { width: 1, height: 1 };
    const stageRect = stage.getBoundingClientRect();
    const stageWidth = Math.max(1, stageRect.width);
    const stageHeight = Math.max(1, stageRect.height);
    const aspect = Number.isFinite(Number(savedAspect)) && Number(savedAspect) > 0
        ? Number(savedAspect)
        : stageWidth / stageHeight;
    let width = stageWidth;
    let height = width / aspect;
    if (height > stageHeight) {
        height = stageHeight;
        width = height * aspect;
    }
    const fittedWidth = Math.max(1, Math.floor(width));
    const fittedHeight = Math.max(1, Math.floor(height));
    frame.style.width = `${fittedWidth}px`;
    frame.style.height = `${fittedHeight}px`;
    return { width: fittedWidth, height: fittedHeight };
}

function fitViewerFrame(renderer, savedAspect) {
    const { width, height } = sizeViewerFrame(savedAspect);
    renderer.renderer.setSize(Math.max(1, width), Math.max(1, height), false);
    renderer.updateCameraProjection(width / Math.max(1, height));
    renderer.requestRender();
}

function installViewOnlyPointerControls(renderer) {
    const canvas = renderer.domElement;
    canvas.addEventListener('pointerdown', event => {
        if (event.button !== 0 || !renderer.controls.enabled) return;
        renderer.controls.startGesture(event, event.shiftKey ? 'pan' : 'rotate');
    });
}

function downloadEmbeddedProject(projectBase64, filename) {
    const bytes = bytesFromBase64(projectBase64);
    const blob = new Blob([bytes], { type: 'application/vnd.v-ase.project+zip' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'v_ase_project.vase';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function metadataRows(scene, frame) {
    const hasEmbeddedProject = scene.hasEmbeddedProject === true;
    return [
        ['Document', scene.documentName || 'v_ase view'],
        ['Atoms', String(frame?.positions?.length || 0)],
        ['Frames', String(scene.frames.length)],
        ['Units', frame?.metadata?.units || 'angstrom'],
        ['Created with', `v_ase ${scene.createdWith?.version || ''}`.trim()],
        ['Embedded project', hasEmbeddedProject ? 'Included' : 'Not included'],
        ['Project schema', hasEmbeddedProject ? (scene.projectSchema || 'v_ase.project.v1') : 'None'],
        ['HTML schema', scene.schema || 'v_ase.html-view.v1'],
    ];
}

function renderMetadata(scene, frame) {
    const grid = document.querySelector('.metadata-grid');
    if (!grid) return;
    grid.replaceChildren();
    metadataRows(scene, frame).forEach(([name, value]) => {
        const key = document.createElement('dt');
        key.textContent = name;
        const detail = document.createElement('dd');
        detail.textContent = value;
        grid.append(key, detail);
    });
}

function mountStandaloneRdf(host, capture, frames, initialFrame, style) {
    if (!capture?.chart || !window.Plotly) return null;
    const panel = document.createElement('section');
    panel.className = 'standalone-rdf-overlay';
    panel.setAttribute('aria-label', capture.title);
    for (const [property, value] of Object.entries({ left: capture.layout.x, top: capture.layout.y,
        width: capture.layout.width, height: capture.layout.height })) panel.style[property] = `${value * 100}%`;
    for (const [key, value] of Object.entries(capture.palette || {})) panel.style.setProperty(`--rdf-${key}`, value);
    const header = document.createElement('header');
    const title = document.createElement('strong');
    const frame = document.createElement('span');
    title.textContent = capture.title;
    header.append(title, frame);
    const plot = document.createElement('div');
    plot.className = 'standalone-rdf-plot';
    panel.append(header, plot);
    host.append(panel);

    const savedTraces = new Map(capture.chart.data.map(trace => [trace.uid, trace]));
    const savedRadius = capture.chart.data[0].x;
    const savedLayout = capture.chart.layout;
    const visibility = new Map();
    let frameIndex = initialFrame;
    let resetRevision = 0;
    let drawnRevision = 0;
    let drawnYLabel;
    let lastDraw = '';
    let rendering = null;

    const draw = async (index, revision, scale) => {
        const useSaved = !frames.length;
        const result = frames[index];
        if (drawnRevision === revision) {
            for (const trace of plot.data || []) visibility.set(trace.uid, trace.visible);
        }
        let frameTraces = [];
        if (useSaved) frameTraces = capture.chart.data;
        else if (result) {
            const radius = result.radius || savedRadius;
            frameTraces = rdfSeriesStyles(result, style, capture.seriesTheme).map(series => {
                const values = series.key === 'total' ? result.total : result.partial[series.key];
                const trace = rdfPlotlyTrace(series, radius, values);
                return { ...trace, ...savedTraces.get(trace.uid), x: radius, y: values };
            });
        }
        title.textContent = result && !useSaved ? result.title : capture.title;
        frame.textContent = !useSaved && !result ? `Unavailable · Frame ${index + 1}`
            : frames.length && index !== capture.frame ? `Frame ${index + 1}` : '';

        panel.style.setProperty('--rdf-scale', scale);
        header.style.height = `${capture.headerHeight * scale}px`;
        const sized = font => ({ ...font, size: Math.max(1, Number(font?.size || 11) * scale) });
        const traces = frameTraces.map(trace => ({ ...trace,
            visible: trace.visible === false ? false : visibility.get(trace.uid) ?? trace.visible,
            line: { ...trace.line, width: Number(trace.line?.width || 0) * scale },
            marker: { ...trace.marker, size: Number(trace.marker?.size || 0) * scale },
        }));
        const layout = structuredClone(savedLayout);
        const savedYLabel = savedLayout.yaxis?.title?.text;
        const yLabel = !useSaved && result?.yLabel || savedYLabel;
        if (yLabel !== savedYLabel) {
            // The units can change in a trajectory with different PBC per frame.
            layout.yaxis = { ...layout.yaxis, title: { text: yLabel }, autorange: true };
            delete layout.yaxis.range;
            layout.shapes = [];
            layout.annotations = [];
        }
        if (drawnRevision === revision && plot._fullLayout) {
            const xRange = plot._fullLayout.xaxis?.range;
            const yRange = plot._fullLayout.yaxis?.range;
            if (xRange) layout.xaxis = { ...layout.xaxis, range: [...xRange], autorange: false };
            if (yRange && drawnYLabel === yLabel) {
                layout.yaxis = { ...layout.yaxis, range: [...yRange], autorange: false };
            }
            layout.dragmode = plot._fullLayout.dragmode;
        }
        const viewRevision = `v-ase-rdf:${revision}`;
        layout.xaxis = { ...layout.xaxis, uirevision: viewRevision };
        layout.yaxis = { ...layout.yaxis, uirevision: `${revision}:${yLabel}` };
        await window.Plotly.react(plot, traces, { ...layout, autosize: true, uirevision: viewRevision,
            font: sized(layout.font),
            annotations: layout.annotations?.map(note => ({ ...note, font: sized(note.font) })),
            margin: Object.fromEntries(Object.entries(layout.margin || {}).map(([key, value]) => [key, value * scale])),
        }, { responsive: true, displaylogo: false, scrollZoom: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'] });
        drawnRevision = revision;
        drawnYLabel = yLabel;
        panel.dataset.frame = String(index);
    };

    const requestDraw = () => {
        if (rendering) return rendering;
        rendering = Promise.resolve().then(async () => {
            // Coalesce frame and resize requests while Plotly is busy; draw
            // the most recent frame before leaving the queue.
            for (;;) {
                const scale = Math.min(host.clientWidth / capture.referenceWidth, host.clientHeight / capture.referenceHeight);
                const next = `${frameIndex}:${resetRevision}:${scale}`;
                if (!scale || next === lastDraw) break;
                await draw(frameIndex, resetRevision, scale);
                lastDraw = next;
            }
        }).finally(() => { rendering = null; });
        return rendering;
    };
    const update = () => requestDraw().catch(error => console.warn('Could not draw the saved distribution.', error));
    const ready = update();
    new ResizeObserver(update).observe(host);
    return {
        ready,
        updateFrame(index) {
            frameIndex = index;
            return update();
        },
        resetView() {
            resetRevision += 1;
            visibility.clear();
            return update();
        },
    };
}

export function startStandaloneViewer(scene, projectBase64, rdfFrames = []) {
    const frames = Array.isArray(scene?.frames) ? scene.frames : [];
    if (!frames.length) throw new Error('The exported HTML contains no structure frames.');

    const settings = scene.settings?.settings || scene.settings || {};
    const exportProfile = scene.exportProfile || {};
    const composition = exportProfile.composition || {};
    const exportOptions = exportProfile.options || {};
    const display = {
        ...(settings.display || {}),
        vizOnly: true,
        sunGizmo: false,
        showGrid: exportOptions.includeGrid === true,
        showAxes: exportOptions.includeAxes !== false,
        showCell: exportOptions.includeCell !== false,
        lightingMode: exportOptions.renderMode || settings.display?.lightingMode || 'modeling',
        sunIntensity: Number.isFinite(Number(exportOptions.sunIntensity))
            ? Number(exportOptions.sunIntensity)
            : settings.display?.sunIntensity,
        sunPosition: finiteVector(
            exportOptions.sunPosition,
            settings.display?.sunPosition || [8, -10, 14]
        ),
        sunTarget: finiteVector(
            exportOptions.sunTarget,
            settings.display?.sunTarget || [0, 0, 0]
        ),
        viewportBackground: String(exportOptions.backgroundColor || '').toLowerCase() === '#ffffff'
            ? 'white'
            : (settings.display?.viewportBackground || 'white')
    };
    if (
        exportOptions.sphereQuality
        && exportOptions.sphereQuality !== 'viewport'
    ) {
        display.sphereQuality = exportOptions.sphereQuality;
    }
    const savedCamera = composition.camera || settings.camera || scene.camera || null;
    const savedAspect = (
        Number(composition.aspect)
        || Number(exportProfile.aspect)
        || Number(savedCamera?.aspect)
        || 16 / 9
    );
    const viewerFrame = document.getElementById('viewer-frame');
    sizeViewerFrame(savedAspect);
    const renderer = new ASERenderer(viewerFrame);
    fitViewerFrame(renderer, savedAspect);
    renderer.needsInitialCameraFit = !savedCamera;
    renderer.setDisplayOptions(display, { rebuild: false });
    installViewOnlyPointerControls(renderer);

    let frameIndex = clampFrame(scene.currentFrame, frames.length);
    let timer = null;
    const includeGraph = exportOptions.includeGraph ?? (display.energyOverlay?.visible === true);
    const energy = scene.trajectoryEnergy && includeGraph
        ? new TrajectoryEnergyOverlay(viewerFrame, { seek: index => {
            stopPlayback();
            if (index !== frameIndex) renderFrame(index);
        }, capture: exportProfile.energyGraph,
        backdrop: () => exportOptions.backgroundColor || '#ffffff' }) : null;
    if (energy) {
        energy.setSettings({ ...display.energyOverlay, visible: true });
        energy.setData(scene.trajectoryEnergy);
        if (exportProfile.energyGraph && scene.hasPoster) viewerFrame.dataset.energyInPoster = 'true';
    }
    const rdf = includeGraph ? mountStandaloneRdf(
        viewerFrame, exportProfile.rdfGraph, rdfFrames, frameIndex, display.analysisPlots?.rdf?.style
    ) : null;
    if (rdf && scene.hasPoster) viewerFrame.dataset.rdfInPoster = 'true';
    const timeline = document.getElementById('timeline');
    const slider = document.getElementById('frame-slider');
    const frameLabel = document.getElementById('frame-label');
    const playButton = document.getElementById('play-frame');
    const fpsInput = document.getElementById('playback-fps');
    const hasEmbeddedProject = (
        scene.hasEmbeddedProject === true
        && typeof projectBase64 === 'string'
        && projectBase64.trim().length > 0
    );

    const updateFrameControls = () => {
        slider.value = String(frameIndex);
        slider.style.setProperty('--range-fill', `${frames.length > 1 ? frameIndex / (frames.length - 1) * 100 : 0}%`);
        slider.setAttribute('aria-valuetext', `Frame ${frameIndex + 1} of ${frames.length}`);
        frameLabel.textContent = `${frameIndex + 1} / ${frames.length}`;
        document.documentElement.dataset.vAseFrame = String(frameIndex);
        energy?.updateFrame(frameIndex);
        rdf?.updateFrame(frameIndex);
    };

    const renderFrame = index => {
        frameIndex = clampFrame(index, frames.length);
        const frame = frames[frameIndex];
        renderer.setDisplayOptions(display, { rebuild: false });
        renderer.rebuildAtoms(frame, frame.metadata?.custom_colors || {});
        if (frame.metadata?.atom_radius_factors || renderer.atomRadiusFactors) {
            renderer.setAtomRadiusFactors(frame.metadata?.atom_radius_factors || null);
        }
        renderer.setAtomColorScaleColors(frame.metadata?.atom_color_scale?.colors || null);
        if (display.showDisplacements && scene.displacements?.[frameIndex]) {
            renderer.setDisplacementVectors(scene.displacements[frameIndex], display);
        }
        renderer.setSelection(scene.selection || []);
        renderMetadata(scene, frame);
        updateFrameControls();
        document.documentElement.dataset.vAseAtomCount = String(frame.positions?.length || 0);
        renderer.renderNow();
    };

    const stopPlayback = () => {
        if (timer !== null) clearInterval(timer);
        timer = null;
        playButton.textContent = '▶';
        playButton.setAttribute('aria-label', 'Play trajectory');
    };

    const startPlayback = () => {
        stopPlayback();
        const fps = Math.max(1, Math.min(60, Math.round(Number(fpsInput.value) || 12)));
        fpsInput.value = String(fps);
        playButton.textContent = '❚❚';
        playButton.setAttribute('aria-label', 'Pause trajectory');
        timer = setInterval(() => {
            renderFrame((frameIndex + 1) % frames.length);
        }, 1000 / fps);
    };

    slider.min = '0';
    slider.max = String(Math.max(0, frames.length - 1));
    timeline.hidden = frames.length <= 1;
    slider.addEventListener('input', () => {
        stopPlayback();
        renderFrame(slider.value);
    });
    document.getElementById('previous-frame').addEventListener('click', () => {
        stopPlayback();
        renderFrame(frameIndex - 1);
    });
    document.getElementById('next-frame').addEventListener('click', () => {
        stopPlayback();
        renderFrame(frameIndex + 1);
    });
    playButton.addEventListener('click', () => {
        if (timer === null) startPlayback();
        else stopPlayback();
    });
    fpsInput.addEventListener('change', () => {
        if (timer !== null) startPlayback();
    });

    const resetCamera = () => {
        if (savedCamera) applyCamera(renderer, { camera: savedCamera });
        else renderer.fitCameraToStructure();
    };
    const resetView = () => {
        resetCamera();
        return rdf?.resetView();
    };
    document.getElementById('reset-view').addEventListener('click', resetView);
    const downloadProject = document.getElementById('download-project');
    downloadProject.hidden = !hasEmbeddedProject;
    if (hasEmbeddedProject) {
        downloadProject.addEventListener('click', () => {
            downloadEmbeddedProject(projectBase64, scene.projectFilename);
        });
    }
    const metadata = document.getElementById('metadata-popover');
    const metadataButton = document.getElementById('show-metadata');
    const setMetadataOpen = open => {
        metadata.hidden = !open;
        metadataButton.setAttribute('aria-expanded', String(open));
    };
    metadataButton.addEventListener('click', () => setMetadataOpen(metadata.hidden));
    document.addEventListener('pointerdown', event => {
        if (!metadata.contains(event.target) && !metadataButton.contains(event.target)) setMetadataOpen(false);
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !metadata.hidden) {
            event.preventDefault(); setMetadataOpen(false); metadataButton.focus(); return;
        }
        // Space on a focused button activates that button. Form editing must
        // not also start playback or reset the scientific camera.
        if (event.target.closest?.('input, button, select, textarea')) return;
        if (event.code === 'Space' && frames.length > 1) {
            event.preventDefault();
            if (timer === null) startPlayback();
            else stopPlayback();
        } else if (event.key === 'ArrowLeft' && frames.length > 1) {
            event.preventDefault();
            stopPlayback();
            renderFrame(frameIndex - 1);
        } else if (event.key === 'ArrowRight' && frames.length > 1) {
            event.preventDefault();
            stopPlayback();
            renderFrame(frameIndex + 1);
        } else if (event.key === 'Home') {
            event.preventDefault();
            resetView();
        }
    });

    const resize = () => {
        fitViewerFrame(renderer, savedAspect);
        renderer.renderNow();
    };
    window.addEventListener('resize', resize);
    document.getElementById('document-title').textContent = scene.documentName || 'v_ase view';
    document.title = `${scene.documentName || 'v_ase view'} - v_ase`;
    renderFrame(frameIndex);
    if (savedCamera) applyCamera(renderer, { camera: savedCamera });
    else renderer.fitCameraToStructure();
    renderer.renderNow();
    const poster = document.getElementById('standalone-poster');
    const revealUi = () => {
        document.documentElement.dataset.vAseUi = 'visible';
    };
    document.addEventListener('pointermove', revealUi, { capture: true, once: true });
    document.addEventListener('focusin', revealUi, { capture: true, once: true });
    document.addEventListener('keydown', revealUi, { capture: true, once: true });
    let revealInteractiveCanvas = () => {};
    if (poster && !poster.hidden) {
        let releaseFinished = false;
        revealInteractiveCanvas = ({ showControls = true } = {}) => {
            if (poster.hidden || poster.classList.contains('is-releasing')) return;
            if (showControls) revealUi();
            poster.classList.add('is-releasing');
            document.documentElement.dataset.vAsePoster = 'releasing';
            const finish = () => {
                if (releaseFinished) return;
                releaseFinished = true;
                poster.hidden = true;
                poster.classList.remove('is-releasing');
                document.documentElement.dataset.vAsePoster = 'replaced';
            };
            poster.addEventListener('transitionend', finish, { once: true });
            window.setTimeout(finish, 180);
        };
        document.documentElement.dataset.vAsePoster = 'ready';
        (rdf?.ready || Promise.resolve()).catch(error => {
            console.warn('Could not draw the saved distribution.', error);
        }).then(() => window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                window.setTimeout(() => {
                    revealInteractiveCanvas({ showControls: false });
                }, 32);
            });
        }));
    }

    window.v_aseStandalone = {
        protocol: 'v_ase.html-view.v1',
        renderer,
        scene,
        get frameIndex() {
            return frameIndex;
        },
        setFrame: renderFrame,
        resetCamera,
        resetView,
        revealInteractiveCanvas,
        hasEmbeddedProject,
        projectBytes: () => (
            hasEmbeddedProject ? bytesFromBase64(projectBase64) : new Uint8Array()
        )
    };
    document.documentElement.dataset.vAseReady = 'true';
    document.documentElement.dataset.vAseFrameCount = String(frames.length);
}
