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
                "ITEM: ATOMS id type x y z\n"
            )
            shift = frame * 0.025
            for index in range(atoms):
                column = index % columns
                row = index // columns
                element = 8 if index % 3 == 0 else 6
                x = column * 0.9 + shift
                y = row * 0.9
                z = 5.0 + ((index % 11) - 5) * 0.035
                handle.write(
                    f"{index + 1} {element} {x:.6f} {y:.6f} {z:.6f}\n"
                )


def run_browser_benchmark(
    path: Path,
    *,
    playback_seconds: float,
    benchmark_bonds: bool = False,
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
            browser = playwright.chromium.launch(headless=True)
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
                    const result = {
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

            playback = page.evaluate(
                """async durationMs => {
                    const app = window.__ASE_APP__;
                    document.getElementById('movie-fps').value = '60';
                    const original = app.loadFrame.bind(app);
                    const durations = [];
                    app.loadFrame = async index => {
                        const started = performance.now();
                        const result = await original(index);
                        durations.push(performance.now() - started);
                        return result;
                    };
                    await app.startPlayback();
                    await new Promise(resolve => setTimeout(resolve, durationMs));
                    app.stopPlayback();
                    await new Promise(resolve => setTimeout(resolve, 100));
                    app.loadFrame = original;
                    return {
                        updates: durations.length,
                        meanMs: durations.length
                            ? durations.reduce((sum, value) => sum + value, 0) / durations.length
                            : null,
                        maxMs: durations.length ? Math.max(...durations) : null,
                        currentFrame: app.state.atoms.metadata.current_frame,
                        renderCount: app.renderer.renderCount
                    };
                }""",
                int(playback_seconds * 1000),
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
    args = parser.parse_args()

    if args.input:
        result = run_browser_benchmark(
            args.input.expanduser().resolve(),
            playback_seconds=args.playback_seconds,
            benchmark_bonds=args.benchmark_bonds,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="v_ase-benchmark-") as directory:
            path = Path(directory) / "v_ase_15000x16.lammpstrj"
            write_benchmark_dump(path)
            result = run_browser_benchmark(
                path,
                playback_seconds=args.playback_seconds,
                benchmark_bonds=args.benchmark_bonds,
            )

    print(json.dumps(result, indent=2))
    return int(result["ready_seconds"] > args.max_ready_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
