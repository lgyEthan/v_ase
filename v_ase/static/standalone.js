import * as THREE from 'three';
import { ASERenderer } from './renderer.js';

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
    frame.style.width = `${Math.max(1, Math.floor(width))}px`;
    frame.style.height = `${Math.max(1, Math.floor(height))}px`;
    return { width, height };
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

export function startStandaloneViewer(scene, projectBase64) {
    const frames = Array.isArray(scene?.frames) ? scene.frames : [];
    if (!frames.length) throw new Error('The exported HTML contains no structure frames.');

    const settings = scene.settings?.settings || scene.settings || {};
    const display = {
        ...(settings.display || {}),
        vizOnly: true,
        sunGizmo: false
    };
    const savedCamera = settings.camera || scene.camera || null;
    const savedAspect = Number(savedCamera?.aspect) || 16 / 9;
    const viewerFrame = document.getElementById('viewer-frame');
    sizeViewerFrame(savedAspect);
    const renderer = new ASERenderer(viewerFrame);
    fitViewerFrame(renderer, savedAspect);
    renderer.needsInitialCameraFit = !savedCamera;
    renderer.setDisplayOptions(display, { rebuild: false });
    installViewOnlyPointerControls(renderer);

    let frameIndex = clampFrame(scene.currentFrame, frames.length);
    let timer = null;
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
        frameLabel.textContent = `${frameIndex + 1} / ${frames.length}`;
        document.documentElement.dataset.vAseFrame = String(frameIndex);
    };

    const renderFrame = index => {
        frameIndex = clampFrame(index, frames.length);
        const frame = frames[frameIndex];
        renderer.setDisplayOptions(display, { rebuild: false });
        renderer.rebuildAtoms(frame, frame.metadata?.custom_colors || {});
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
    document.getElementById('reset-view').addEventListener('click', resetCamera);
    const downloadProject = document.getElementById('download-project');
    downloadProject.hidden = !hasEmbeddedProject;
    if (hasEmbeddedProject) {
        downloadProject.addEventListener('click', () => {
            downloadEmbeddedProject(projectBase64, scene.projectFilename);
        });
    }
    const metadata = document.getElementById('metadata-popover');
    document.getElementById('show-metadata').addEventListener('click', () => {
        metadata.hidden = !metadata.hidden;
    });

    document.addEventListener('keydown', event => {
        if (event.target instanceof HTMLInputElement) return;
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
            resetCamera();
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

    window.v_aseStandalone = {
        protocol: 'v_ase.html-view.v1',
        renderer,
        scene,
        get frameIndex() {
            return frameIndex;
        },
        setFrame: renderFrame,
        resetCamera,
        hasEmbeddedProject,
        projectBytes: () => (
            hasEmbeddedProject ? bytesFromBase64(projectBase64) : new Uint8Array()
        )
    };
    document.documentElement.dataset.vAseReady = 'true';
    document.documentElement.dataset.vAseFrameCount = String(frames.length);
}
