"""Benchmark the large-trajectory browser path used by v_ase.

The default workload is a deterministic 15,000-atom, 16-frame LAMMPS dump.
Playwright is required only for running this development benchmark.
"""

from __future__ import annotations

import argparse
import io
import json
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

from playwright.sync_api import sync_playwright

from v_ase.session import sessions
from v_ase.viewer import find_free_port, view


def write_benchmark_dump(
    path: Path,
    *,
    atoms: int = 15_000,
    frames: int = 16,
    include_scalars: bool = False,
) -> None:
    columns = 150
    rows = (atoms + columns - 1) // columns
    with path.open("w", encoding="ascii") as handle:
        for frame in range(frames):
            handle.write(
                "ITEM: TIMESTEP\n"
                f"{frame}\n"
                "ITEM: NUMBER OF ATOMS\n"
                f"{atoms}\n"
                "ITEM: BOX BOUNDS pp pp pp\n"
                f"0 {columns * 0.9:.6f}\n"
                f"0 {rows * 0.9:.6f}\n"
                "0 12.000000\n"
                + (
                    "ITEM: ATOMS id type x y z q fx fy fz c_uncertainty\n"
                    if include_scalars
                    else "ITEM: ATOMS id type x y z\n"
                )
            )
            shift = frame * 0.025
            for index in range(atoms):
                column = index % columns
                row = index // columns
                element = 8 if index % 3 == 0 else 6
                x = column * 0.9 + shift
                y = row * 0.9
                z = 5.0 + ((index % 11) - 5) * 0.035
                suffix = ""
                if include_scalars:
                    charge = ((index % 17) - 8) * 0.01 + frame * 0.001
                    force = 0.02 * (frame + 1)
                    uncertainty = (index % 101) * 0.005 + frame * 0.02
                    suffix = (
                        f" {charge:.6f} {force:.6f} 0.000000 0.000000"
                        f" {uncertainty:.6f}"
                    )
                handle.write(f"{index + 1} {element} {x:.6f} {y:.6f} {z:.6f}{suffix}\n")


def run_browser_benchmark(
    path: Path,
    *,
    playback_seconds: float,
    benchmark_bonds: bool = False,
    benchmark_colorscale: bool = False,
) -> dict:
    port = find_free_port()
    backend_started = time.perf_counter()
    with redirect_stdout(io.StringIO()):
        editor = view(
            path,
            notebook=True,
            block=False,
            port=port,
            viz_only=True,
            close_on_disconnect=False,
        )
    backend_open_seconds = time.perf_counter() - backend_started
    session = sessions[editor.session_id]
    expected_atoms = len(session.working_atoms)
    expected_frames = session.frame_count
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            )
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            started = time.perf_counter()
            page.goto(editor.url)
            page.wait_for_function(
                """expected => {
                    const app = window.__ASE_APP__;
                    return app?.state?.atoms?.metadata?.natoms === expected.atoms
                        && app?.state?.atoms?.metadata?.frame_count === expected.frames
                        && app?.renderer?.atomMeshByIndex?.size === expected.atoms
                        && app?.renderer?.renderCount > 0;
                }""",
                arg={"atoms": expected_atoms, "frames": expected_frames},
                timeout=30_000,
            )
            browser_render_seconds = time.perf_counter() - started

            page.wait_for_function(
                "window.__ASE_APP__?.state?.trajectoryBinaryCache !== null",
                timeout=30_000,
            )
            cache = page.evaluate(
                """() => {
                    const cache = window.__ASE_APP__.state.trajectoryBinaryCache;
                    return {
                        atoms: cache.atoms,
                        frames: cache.frames,
                        bytes: cache.values.byteLength
                    };
                }"""
            )

            idle_start = page.evaluate("window.__ASE_APP__.renderer.renderCount")
            page.wait_for_timeout(900)
            idle_end = page.evaluate("window.__ASE_APP__.renderer.renderCount")

            colorscale = None
            if benchmark_colorscale:
                page.evaluate("""() => {
                    const input = document.getElementById('chk-atom-colorscale');
                    input.checked = true;
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                }""")
                page.wait_for_function(
                    "window.__ASE_APP__.atomColorScaleRuntime.catalog?.fields?.length > 3",
                    timeout=30_000,
                )
                fields = page.evaluate(
                    "window.__ASE_APP__.atomColorScaleRuntime.catalog.fields"
                )
                field_id = next(
                    (
                        item["id"]
                        for item in fields
                        if item.get("name") == "c_uncertainty"
                    ),
                    "position:z",
                )
                page.evaluate("""async fieldId => {
                    const app = window.__ASE_APP__;
                    app.state.display.atomColorScaleField = fieldId;
                    app.state.display.atomColorScaleRangeMode = 'current';
                    app.atomColorScaleRuntime.rangeSignature = '';
                    app.syncAtomColorScaleControls();
                    await app.updateAtomColorScale({quiet: true});
                }""", field_id)
                scan_started = time.perf_counter()
                page.evaluate(
                    "window.__ASE_APP__.fitAtomColorScaleRange('trajectory')"
                )
                scan_seconds = time.perf_counter() - scan_started
                colorscale = page.evaluate("""fieldId => ({
                    fieldId,
                    minimum: window.__ASE_APP__.state.display.atomColorScaleMin,
                    maximum: window.__ASE_APP__.state.display.atomColorScaleMax,
                    coloredAtoms: window.__ASE_APP__.renderer.atomColorScaleColors.filter(Boolean).length
                })""", field_id)
                colorscale["trajectory_scan_seconds"] = round(scan_seconds, 4)
                colorscale.update(page.evaluate("""async () => {
                    const app = window.__ASE_APP__;
                    let started = performance.now();
                    app.renderer.refreshAtomColors();
                    const directColorRefreshMs = performance.now() - started;
                    started = performance.now();
                    await app.updateAtomColorScale({quiet: true, refreshBonds: false});
                    return {
                        directColorRefreshMs,
                        cachedColorScaleUpdateMs: performance.now() - started
                    };
                }"""))

            page.evaluate(
                """async () => {
                    const app = window.__ASE_APP__;
                    document.getElementById('movie-fps').value = '60';
                    const original = app.loadFrame.bind(app);
                    const originalRenderFrame = app.renderer.renderFrame.bind(app.renderer);
                    const durations = [];
                    const updateTimestamps = [];
                    const renderDurations = [];
                    app.loadFrame = async index => {
                        const started = performance.now();
                        updateTimestamps.push(started);
                        const result = await original(index);
                        durations.push(performance.now() - started);
                        return result;
                    };
                    app.renderer.renderFrame = () => {
                        const started = performance.now();
                        const result = originalRenderFrame();
                        renderDurations.push(performance.now() - started);
                        return result;
                    };
                    window.__V_ASE_PLAYBACK_BENCHMARK__ = {
                        app,
                        original,
                        originalRenderFrame,
                        durations,
                        updateTimestamps,
                        renderDurations
                    };
                    await app.startPlayback();
                }"""
            )
            page.wait_for_timeout(int(playback_seconds * 1000))
            playback = page.evaluate(
                """async () => {
                    const benchmark = window.__V_ASE_PLAYBACK_BENCHMARK__;
                    const {
                        app,
                        original,
                        originalRenderFrame,
                        durations,
                        updateTimestamps,
                        renderDurations
                    } = benchmark;
                    const timerActiveBeforeStop = Boolean(app.state.trajectoryTimer);
                    app.stopPlayback();
                    await new Promise(resolve => setTimeout(resolve, 100));
                    app.loadFrame = original;
                    app.renderer.renderFrame = originalRenderFrame;
                    delete window.__V_ASE_PLAYBACK_BENCHMARK__;
                    return {
                        updates: durations.length,
                        meanMs: durations.length
                            ? durations.reduce((sum, value) => sum + value, 0) / durations.length
                            : null,
                        maxMs: durations.length ? Math.max(...durations) : null,
                        renders: renderDurations.length,
                        meanRenderMs: renderDurations.length
                            ? renderDurations.reduce((sum, value) => sum + value, 0) / renderDurations.length
                            : null,
                        maxRenderMs: renderDurations.length ? Math.max(...renderDurations) : null,
                        timerActiveBeforeStop,
                        requestedFps: app.currentPlaybackFps(),
                        visibilityState: document.visibilityState,
                        updateIntervalsMs: updateTimestamps.slice(1).map(
                            (value, index) => value - updateTimestamps[index]
                        ),
                        currentFrame: app.state.atoms.metadata.current_frame,
                        renderCount: app.renderer.renderCount
                    };
                }"""
            )

            # Run synthetic renderer stress tests after real playback so their
            # short-lived allocations cannot be mistaken for playback stalls.
            frame_sweeps = page.evaluate(
                """() => {
                    const app = window.__ASE_APP__;
                    const cache = app.state.trajectoryBinaryCache;
                    const measure = lightingMode => {
                        app.renderer.setLightingOptions(
                            {...app.renderer.lightingOptions, lightingMode},
                            {requestRender: false}
                        );
                        const started = performance.now();
                        for (let frame = 0; frame < cache.frames; frame += 1) {
                            app.renderer.updatePositionsFlat(
                                cache.values,
                                frame * cache.atoms * 3,
                                cache.atoms
                            );
                        }
                        const totalMs = performance.now() - started;
                        return {
                            frames: cache.frames,
                            totalMs,
                            meanMs: totalMs / cache.frames
                        };
                    };
                    const measureBuffersOnly = () => {
                        const renderer = app.renderer;
                        const refs = renderer.atomInstanceRefsByIndex;
                        const positions = renderer.atomsData.positions;
                        const started = performance.now();
                        for (let frame = 0; frame < cache.frames; frame += 1) {
                            const frameOffset = frame * cache.atoms * 3;
                            for (let index = 0; index < cache.atoms; index += 1) {
                                const base = frameOffset + index * 3;
                                const x = cache.values[base];
                                const y = cache.values[base + 1];
                                const z = cache.values[base + 2];
                                const position = positions[index];
                                position[0] = x;
                                position[1] = y;
                                position[2] = z;
                                const ref = refs[index];
                                ref.proxy.position.x = x;
                                ref.proxy.position.y = y;
                                ref.proxy.position.z = z;
                                ref.matrix[ref.matrixOffset + 12] = x;
                                ref.matrix[ref.matrixOffset + 13] = y;
                                ref.matrix[ref.matrixOffset + 14] = z;
                            }
                            renderer.atomInstanceMeshes.forEach(mesh => {
                                mesh.instanceMatrix.needsUpdate = true;
                            });
                        }
                        const totalMs = performance.now() - started;
                        return {frames: cache.frames, totalMs, meanMs: totalMs / cache.frames};
                    };
                    const result = {
                        buffersOnly: measureBuffersOnly(),
                        modeling: measure('modeling'),
                        studio: measure('studio'),
                        studioShadow: measure('studio-shadow')
                    };
                    app.renderer.setLightingOptions(
                        {...app.renderer.lightingOptions, lightingMode: 'modeling'},
                        {requestRender: false}
                    );
                    return result;
                }"""
            )
            bond_sweep = None
            if benchmark_bonds:
                bond_sweep = page.evaluate(
                    """() => {
                        const app = window.__ASE_APP__;
                        const cache = app.state.trajectoryBinaryCache;
                        app.state.display.showBonds = true;
                        app.renderer.setDisplayOptions(
                            {...app.state.display, showBonds: true},
                            {rebuild: false}
                        );
                        const setupStarted = performance.now();
                        app.renderer.rebuildBonds();
                        const setupMs = performance.now() - setupStarted;
                        const inferenceStarted = performance.now();
                        app.renderer.inferCurrentBondTopology();
                        const inferenceMs = performance.now() - inferenceStarted;
                        const geometryStarted = performance.now();
                        app.renderer.updateBondPositions();
                        const geometryMs = performance.now() - geometryStarted;
                        const frames = Math.min(4, cache.frames);
                        const sweepStarted = performance.now();
                        for (let frame = 0; frame < frames; frame += 1) {
                            app.renderer.updatePositionsFlat(
                                cache.values,
                                frame * cache.atoms * 3,
                                cache.atoms
                            );
                        }
                        const totalMs = performance.now() - sweepStarted;
                        const result = {
                            bonds: app.renderer.bondPairs.length,
                            setupMs,
                            inferenceMs,
                            geometryMs,
                            frames,
                            totalMs,
                            meanMs: totalMs / frames
                        };
                        app.state.display.showBonds = false;
                        app.renderer.setDisplayOptions(
                            {...app.state.display, showBonds: false},
                            {rebuild: false}
                        );
                        app.renderer.rebuildBonds();
                        return result;
                    }"""
                )
            browser.close()
    finally:
        editor.close()

    return {
        "input": str(path),
        "input_bytes": path.stat().st_size,
        "atoms": expected_atoms,
        "frames": expected_frames,
        "backend_open_seconds": round(backend_open_seconds, 4),
        "browser_render_seconds": round(browser_render_seconds, 4),
        "ready_seconds": round(backend_open_seconds + browser_render_seconds, 4),
        "idle_render_frames_0_9s": idle_end - idle_start,
        "trajectory_cache": cache,
        "direct_frame_sweeps": frame_sweeps,
        "bond_frame_sweep": bond_sweep,
        "colorscale": colorscale,
        "playback_seconds": playback_seconds,
        "playback": playback,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", type=Path)
    parser.add_argument("--max-ready-seconds", type=float, default=5.0)
    parser.add_argument("--playback-seconds", type=float, default=1.5)
    parser.add_argument(
        "--benchmark-bonds",
        action="store_true",
        help="also measure automatic bond inference and four bonded frame updates",
    )
    parser.add_argument(
        "--benchmark-colorscale",
        action="store_true",
        help="also scan and play a trajectory-consistent per-atom colorscale",
    )
    args = parser.parse_args()

    if args.input:
        result = run_browser_benchmark(
            args.input.expanduser().resolve(),
            playback_seconds=args.playback_seconds,
            benchmark_bonds=args.benchmark_bonds,
            benchmark_colorscale=args.benchmark_colorscale,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="v_ase-benchmark-") as directory:
            path = Path(directory) / "v_ase_15000x16.lammpstrj"
            write_benchmark_dump(path, include_scalars=args.benchmark_colorscale)
            result = run_browser_benchmark(
                path,
                playback_seconds=args.playback_seconds,
                benchmark_bonds=args.benchmark_bonds,
                benchmark_colorscale=args.benchmark_colorscale,
            )

    print(json.dumps(result, indent=2))
    return int(result["ready_seconds"] > args.max_ready_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
