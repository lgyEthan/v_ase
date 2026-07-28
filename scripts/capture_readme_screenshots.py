"""Capture README screenshots and GIFs from local v_ase scenes."""

from __future__ import annotations

import argparse
import base64
import math
import os
import shutil
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.build import fcc111
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.manual_showcase import make_frames
from v_ase import view
from examples.readme_scenes import (
    make_crowded_c60_relaxation_scene,
    make_ethane_measurement_scene,
    make_ferrocene_scene,
    make_graphene_hbn_commensurate_scene,
    make_hookean_surface_scene,
    make_phosphorene_twist_scene,
    make_surface_fixedplane_scene,
    make_cnt_fixedline_scene,
)


def parse_media_size(value: str | None, default: tuple[int, int]) -> tuple[int, int]:
    if not value:
        return default
    try:
        width, height = value.lower().split("x", 1)
        return int(width), int(height)
    except ValueError:
        return default


def configured_asset_dir() -> Path:
    value = os.environ.get("V_ASE_README_ASSET_DIR")
    if not value:
        return ROOT / "docs" / "assets"
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def sync_github_readme_assets() -> None:
    canonical_dir = (ROOT / "docs" / "assets").resolve()
    if ASSET_DIR.resolve() != canonical_dir:
        return
    github_dir = canonical_dir / "github"
    github_dir.mkdir(parents=True, exist_ok=True)
    for source in canonical_dir.glob("readme_*"):
        if source.is_file():
            shutil.copy2(source, github_dir / source.name)


ASSET_DIR = configured_asset_dir()
MEDIA_SIZE = parse_media_size(os.environ.get("V_ASE_README_MEDIA_SIZE"), (1920, 1080))
LOGO_SIZE = parse_media_size(os.environ.get("V_ASE_LOGO_SIZE"), (6144, 1890))
LOGO_RENDER_SIZE = parse_media_size(os.environ.get("V_ASE_LOGO_RENDER_SIZE"), (7680, 2362))
LOGO_SUBSTRATE_COLOR = os.environ.get("V_ASE_LOGO_SUBSTRATE_COLOR", "#71493f")
LOGO_LETTER_COLOR = os.environ.get("V_ASE_LOGO_LETTER_COLOR", "#d7f26f")
LOGO_LETTER_RADIUS = float(os.environ.get("V_ASE_LOGO_LETTER_RADIUS", "0.67"))
LOGO_PIXELS_PER_ANGSTROM = float(os.environ.get("V_ASE_LOGO_PIXELS_PER_ANGSTROM", "92"))

LOGO_GLYPHS = {
    "V": {"width": 6.0, "paths": (((0.0, 8.0), (3.0, 0.0), (6.0, 8.0)),)},
    "_": {"width": 4.5, "paths": (((0.0, 0.0), (4.5, 0.0)),)},
    "A": {
        "width": 6.0,
        "paths": (
            ((0.0, 0.0), (3.0, 8.0), (6.0, 0.0)),
            ((1.35, 3.65), (4.65, 3.65)),
        ),
    },
    "S": {
        "width": 6.0,
        "paths": ((
            (6.0, 8.0), (1.5, 8.0), (0.45, 7.45), (0.0, 6.35),
            (0.45, 5.35), (1.5, 4.65), (4.55, 3.55), (5.55, 2.9),
            (6.0, 1.85), (5.55, 0.75), (4.55, 0.15), (0.0, 0.15),
        ),),
    },
    "E": {
        "width": 6.0,
        "paths": (
            ((0.0, 0.0), (0.0, 8.0)),
            ((0.0, 8.0), (6.0, 8.0)),
            ((0.0, 4.0), (5.0, 4.0)),
            ((0.0, 0.0), (6.0, 0.0)),
        ),
    },
}


def logo_paths(text: str = "V_ASE") -> tuple[list[tuple[tuple[float, float], ...]], float]:
    paths = []
    offset = 0.0
    gap = 2.0
    for character in text:
        glyph = LOGO_GLYPHS[character]
        paths.extend(
            tuple((point[0] + offset, point[1]) for point in path)
            for path in glyph["paths"]
        )
        offset += float(glyph["width"]) + gap
    return paths, offset - gap


def sample_logo_points(paths, x_scale: float, y_scale: float, spacing: float):
    points = []
    for path in paths:
        for segment_index, (start, end) in enumerate(zip(path, path[1:])):
            start_xy = np.array([start[0] * x_scale, start[1] * y_scale])
            end_xy = np.array([end[0] * x_scale, end[1] * y_scale])
            intervals = max(1, int(np.ceil(np.linalg.norm(end_xy - start_xy) / spacing)))
            for index in range(0 if segment_index == 0 else 1, intervals + 1):
                point = start_xy + (end_xy - start_xy) * (index / intervals)
                points.append((float(point[0]), float(point[1])))
    deduplicated = []
    for point in points:
        if all(np.linalg.norm(np.subtract(point, existing)) > spacing * 0.35 for existing in deduplicated):
            deduplicated.append(point)
    return deduplicated


def make_logo_scene() -> Atoms:
    surface = fcc111("Cu", size=(30, 10, 1), a=3.615, vacuum=7.5, orthogonal=True)
    top_z = float(surface.positions[:, 2].max())
    paths, logical_width = logo_paths()
    sampled = sample_logo_points(paths, x_scale=1.75, y_scale=2.0, spacing=1.4)
    cell_x, cell_y, _ = surface.cell.lengths()
    origin_x = (float(cell_x) - logical_width * 1.75) / 2
    origin_y = (float(cell_y) - 8.0 * 2.0) / 2
    oxygen = Atoms(
        symbols=["O"] * len(sampled),
        positions=[[origin_x + x, origin_y + y, top_z + 1.45] for x, y in sampled],
    )
    atoms = surface + oxygen
    center = (np.min(atoms.positions, axis=0) + np.max(atoms.positions, axis=0)) / 2
    atoms.positions -= center
    atoms.info["readme_scene"] = "v_ase_atomistic_logo"
    return atoms


def open_panels(page, panels):
    page.evaluate(
        """(panels) => {
            const openSet = new Set(panels);
            document.querySelectorAll('#inspector details').forEach((details) => {
                const key = details.dataset.panel || details.id;
                details.open = openSet.has(key);
            });
        }""",
        panels,
    )


def configure_inspector(page, group: str, panels, width=416):
    selected_section = None
    page.evaluate(
        """({ group, width }) => {
            const app = window.__V_ASE_APP__;
            app.setInspectorCollapsed(false, false);
            app.setInspectorGroup(group, false);
            app.setInspectorWidth(width, false);
        }""",
        {"group": group, "width": width},
    )
    open_panels(page, panels)
    if group == "structure" and panels:
        section = panels[0]
        if section in {
            "appearance",
            "cell-replication",
            "cell-transform",
            "transform",
            "constraints",
            "bonding",
            "scientific-tools",
        }:
            page.select_option("#structure-section-select", section)
            selected_section = section
    page.wait_for_function(
        """(minimumWidth) => {
            const inspector = document.getElementById('inspector');
            return inspector
                && !document.body.classList.contains('inspector-collapsed')
                && inspector.getBoundingClientRect().width >= minimumWidth;
        }""",
        arg=max(336, width - 2),
    )
    page.wait_for_timeout(100)
    if selected_section:
        page.evaluate(
            """(section) => {
                const selector = document.getElementById('structure-section-select');
                if (selector) selector.value = section;
            }""",
            selected_section,
        )


def set_display(page, options):
    page.evaluate(
        """(options) => {
            const app = window.__V_ASE_APP__;
            const current = app.state.display || {};
            const merged = {
                ...current,
                ...options,
                labelRadii: options.labelRadii || current.labelRadii || {},
                labelColors: options.labelColors || current.labelColors || {},
                labelVisible: options.labelVisible || current.labelVisible || {},
                pairwiseBondCutoffs: options.pairwiseBondCutoffs || current.pairwiseBondCutoffs || {},
                pairwiseBondRanges: options.pairwiseBondRanges || current.pairwiseBondRanges || {},
                manualBondPairs: options.manualBondPairs || current.manualBondPairs || [],
                supercell: options.supercell || current.supercell || [1, 1, 1]
            };
            if (app.applyDesignSettings) {
                app.applyDesignSettings({ display: merged }, { render: true });
            } else {
                app.state.display = merged;
                app.renderer.setDisplayOptions(app.state.display);
                app.updateUI();
            }
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        options,
    )


def set_view_toggles(page, *, grid=None, axes=None, cell=None):
    for element_id, value, state_key in (
        ("chk-grid", grid, "showGrid"),
        ("chk-axes", axes, "showAxes"),
        ("chk-cell", cell, "showCell"),
    ):
        if value is None:
            continue
        page.locator(f"#{element_id}").set_checked(bool(value))
        expected = "true" if value else "false"
        page.wait_for_function(
            f"window.__V_ASE_APP__.state.display.{state_key} === {expected}"
        )
    page.evaluate("""() => {
        const app = window.__V_ASE_APP__;
        app.renderer.setDisplayOptions(app.state.display, { rebuild: false });
        app.renderer.renderNow();
    }""")


def set_readme_lighting(page, target, *, intensity=2.9, position_offset=(-12.0, -15.0, 20.0)):
    target = [float(value) for value in target]
    position = [target[i] + float(position_offset[i]) for i in range(3)]
    set_display(page, {
        "lightingMode": "studio-shadow",
        "sunIntensity": float(intensity),
        "sunPosition": position,
        "sunTarget": target,
        "sunGizmo": False,
        "antialias": True,
        "sphereQuality": "ultra",
    })
    page.evaluate(
        """() => {
            const renderer = window.__V_ASE_APP__.renderer;
            renderer.fitSunShadowCamera?.();
            renderer.renderer.render(renderer.scene, renderer.camera);
            renderer.renderer.render(renderer.scene, renderer.camera);
        }"""
    )
    page.wait_for_timeout(300)


def save_logo_render(page, path: Path):
    width, height = LOGO_SIZE
    render_width, render_height = LOGO_RENDER_SIZE
    data_url = page.evaluate(
        """({ width, height, pixelsPerAngstrom }) => window.__V_ASE_APP__.renderer.exportPNG(width, height, {
            transparentBackground: true,
            includeGrid: false,
            includeAxes: false,
            includeCell: false,
            renderMode: 'studio-shadow',
            sunIntensity: 2.45,
            sunPosition: [-22, -26, 42],
            sunTarget: [0, 0, 0],
            sphereQuality: 'ultra',
            sphereQualityScale: 2,
            scaleMode: 'physical',
            pixelsPerAngstrom
        })""",
        {
            "width": render_width,
            "height": render_height,
            "pixelsPerAngstrom": LOGO_PIXELS_PER_ANGSTROM,
        },
    )
    payload = base64.b64decode(data_url.split(",", 1)[1])
    image = Image.open(BytesIO(payload)).convert("RGBA")
    raw_output = os.environ.get("V_ASE_LOGO_RAW_OUTPUT")
    if raw_output:
        raw_path = Path(raw_output).expanduser()
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(raw_path, optimize=True, compress_level=9)
    bounds = image.getbbox()
    if bounds:
        image = image.crop(bounds)
    padding = max(32, round(min(width, height) * 0.035))
    scale = min((width - padding * 2) / image.width, (height - padding * 2) / image.height)
    target_size = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    # Resize premultiplied RGBA so transparent black pixels cannot bleed into
    # the atom silhouettes during high-quality downsampling.
    image = image.convert("RGBa").resize(
        target_size,
        Image.Resampling.LANCZOS,
    ).convert("RGBA")
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((width - image.width) // 2, (height - image.height) // 2))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, optimize=True, compress_level=9)


def capture_logo(browser):
    atoms = make_logo_scene()
    editor, page = open_scene(browser, atoms, show_bonds=False)
    try:
        set_display(page, {
            "showCell": False,
            "showAxes": False,
            "showGrid": False,
            "showBonds": False,
            "showOverlays": False,
            "atomRadiusScale": 0.96,
            "labelRadii": {"Cu": 1.278, "O": LOGO_LETTER_RADIUS},
            "labelColors": {"Cu": LOGO_SUBSTRATE_COLOR, "O": LOGO_LETTER_COLOR},
            "labelMaterials": {"Cu": "rubber", "O": "standard"},
            "projectionMode": "orthographic",
        })
        page.evaluate(
            """() => {
                const app = window.__V_ASE_APP__;
                const renderer = app.renderer;
                renderer.setProjectionMode('orthographic');
                renderer.controls.target.set(0, 0, 0);
                renderer.camera.up.set(0, 1, 0);
                renderer.camera.position.set(5.5, -10.5, 70);
                renderer.camera.lookAt(renderer.controls.target);
                renderer.fitCameraToStructure();
                const centeredOffset = renderer.camera.position.clone().sub(renderer.controls.target);
                renderer.controls.target.set(0, 0, 0);
                renderer.camera.position.copy(centeredOffset);
                renderer.camera.lookAt(renderer.controls.target);
                renderer.camera.zoom *= 1.02;
                renderer.camera.updateProjectionMatrix();
            }"""
        )
        set_readme_lighting(page, [0, 0, 0], intensity=2.65, position_offset=(-26, -30, 46))
        output_override = os.environ.get("V_ASE_LOGO_OUTPUT")
        logo_output = Path(output_override).expanduser() if output_override else (
            ROOT / "docs" / "assets" / "v_ase-logo.png"
        )
        save_logo_render(page, logo_output)
        if not output_override:
            static_logo = ROOT / "v_ase" / "static" / "v_ase-logo.png"
            static_logo.write_bytes(logo_output.read_bytes())
    finally:
        page.close()
        editor.close()


def set_selection(page, indices):
    page.evaluate(
        """(indices) => {
            const app = window.__V_ASE_APP__;
            app.clearAtomSelection();
            indices.forEach(index => app.addSelectionReference(index));
            app.updateSelectionVisuals();
            app.renderer.syncConstraintGuides();
            app.updateUI();
        }""",
        indices,
    )


def enter_mode(page, mode, axis=None):
    page.evaluate(
        """async ({ mode, axis }) => {
            const app = window.__V_ASE_APP__;
            app.enterTransformMode(mode);
            if (axis) {
                app.transform.setAxis(axis, app.renderer.camera);
                if (mode === 'ROTATE') {
                    await app.prepareCommensurateRotation([...app.state.selected]);
                }
            }
            app.updateUI();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        {"mode": mode, "axis": axis},
    )


def start_atom_rotation(page, indices, *, axis: str, pivot_mode: str):
    page.evaluate(
        """async ({ indices, axis, pivotMode }) => {
            const app = window.__V_ASE_APP__;
            if (app.transform.mode !== 'IDLE') {
                app.transform.exit();
                app.state.transformSubject = null;
                app.renderer.controls.enabled = true;
                app.clearCommensurateRotation({ keepStatus: true });
            }
            app.clearAtomSelection();
            indices.forEach(index => app.addSelectionReference(index));
            app.state.display.rotatePivot = pivotMode;
            const pivotInput = document.getElementById('rotate-pivot');
            if (pivotInput) pivotInput.value = pivotMode;
            app.updateSelectionVisuals();
            app.enterTransformMode('ROTATE');
            app.transform.setAxis(axis, app.renderer.camera);
            app.configureRotationReference(indices);
            await app.prepareCommensurateRotation(indices);
            app.updateUI();
            app.renderer.renderNow();
        }""",
        {
            "indices": [int(index) for index in indices],
            "axis": axis,
            "pivotMode": pivot_mode,
        },
    )


def set_atom_rotation_angle(page, angle_degrees: float, status: str = ""):
    page.evaluate(
        """({ angleDegrees, status }) => {
            const app = window.__V_ASE_APP__;
            app.transform.rotationAngle = angleDegrees * Math.PI / 180;
            app.applyTransformPreview();
            if (status) {
                app.state.transformReadout =
                    `${app.formatRotateReadout(app.transform.rotationAngle)} | ${status}`;
                app.updateCommandReadout();
            }
            app.renderer.renderNow();
        }""",
        {"angleDegrees": float(angle_degrees), "status": status},
    )


def set_camera(page, *, target, position, up=(0, 0, 1), fov=38):
    page.evaluate(
        """({ target, position, up, fov }) => {
            const app = window.__V_ASE_APP__;
            const camera = app.renderer.camera;
            camera.fov = fov;
            camera.up.set(up[0], up[1], up[2]);
            camera.position.set(position[0], position[1], position[2]);
            app.renderer.controls.target.set(target[0], target[1], target[2]);
            camera.lookAt(app.renderer.controls.target);
            camera.updateProjectionMatrix();
            app.renderer.syncSelectionOutlines();
            app.renderer.syncConstraintGuides();
            app.renderer.syncLockMarkers?.();
            app.renderer.updateHookeanPositions();
            app.transform?.updateGuides?.(camera);
            app.renderer.renderer.render(app.renderer.scene, camera);
        }""",
        {"target": target, "position": position, "up": up, "fov": fov},
    )
    page.wait_for_timeout(250)


def set_atomic_scale(page, pixels_per_angstrom: float):
    page.evaluate(
        """(value) => {
            const app = window.__V_ASE_APP__;
            app.renderer.setPixelsPerAngstrom(value);
            app.syncAtomicScaleFromCamera?.({ forceInput: true });
            app.renderer.renderNow();
        }""",
        float(pixels_per_angstrom),
    )
    page.wait_for_timeout(250)


def settle_view(page, *, target=None, position=None, fov=38):
    page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            app.renderer.fitCameraToStructure();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }"""
    )
    page.wait_for_timeout(400)
    if target is not None and position is not None:
        set_camera(page, target=target, position=position, fov=fov)


def update_positions(page, positions):
    page.evaluate(
        """(positions) => {
            const app = window.__V_ASE_APP__;
            app.state.atoms.positions = positions.map((p) => [...p]);
            app.renderer.updatePositions(positions);
            app.renderer.syncSelectionOutlines();
            app.renderer.syncConstraintGuides();
            app.renderer.updateHookeanPositions();
            app.renderer.refreshBondsForCurrentPositions();
            app.renderer.updateSupercellPositions();
            app.updateUI();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }""",
        [[float(v) for v in row] for row in positions],
    )


def screenshot_frame(page) -> Image.Image:
    raw = page.screenshot(type="png")
    image = Image.open(BytesIO(raw)).convert("RGB")
    if image.size != MEDIA_SIZE:
        image = image.resize(MEDIA_SIZE, Image.Resampling.LANCZOS)
    return image


def save_gif(frames: list[Image.Image], path: Path, duration=85):
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=False,
        disposal=2,
    )


def capture_animation(
    page,
    path: Path,
    position_frames: list[np.ndarray],
    duration=85,
    on_frame=None,
):
    frames = []
    for frame_index, positions in enumerate(position_frames):
        update_positions(page, positions)
        if on_frame is not None:
            on_frame(page, frame_index, len(position_frames))
        page.wait_for_timeout(35)
        frames.append(screenshot_frame(page))
    save_gif(frames, path, duration=duration)


def open_scene(browser, atoms_or_frames, *, show_bonds=False):
    editor = view(
        atoms_or_frames,
        block=False,
        viz_only=False,
        show_cell=True,
        show_axes=True,
        show_bonds=show_bonds,
        respect_constraints=True,
        allow_relax=False,
    )
    url = f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}"
    page = browser.new_page(
        viewport={"width": MEDIA_SIZE[0], "height": MEDIA_SIZE[1]},
        device_scale_factor=1,
    )
    page.goto(url)
    page.wait_for_function("window.__V_ASE_APP__ && window.__V_ASE_APP__.state.atoms")
    return editor, page


def sinusoidal_frames(base: np.ndarray, index: int, delta_fn, count=34) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        phase = math.sin(2 * math.pi * step / count)
        positions = base.copy()
        positions[index] = base[index] + np.asarray(delta_fn(phase), dtype=float)
        frames.append(positions)
    return frames


def plane_sweep_frames(base: np.ndarray, index: int, count=38) -> list[np.ndarray]:
    offsets = [
        np.array([-1.25, -0.65, 0.0]),
        np.array([1.25, -0.45, 0.0]),
        np.array([0.95, 0.90, 0.0]),
        np.array([-1.10, 0.72, 0.0]),
        np.array([-1.25, -0.65, 0.0]),
    ]
    frames = []
    for step in range(count):
        t = step / max(1, count - 1)
        scaled = t * (len(offsets) - 1)
        seg = min(int(scaled), len(offsets) - 2)
        local = scaled - seg
        smooth = 0.5 - 0.5 * math.cos(math.pi * local)
        positions = base.copy()
        positions[index] = base[index] + offsets[seg] * (1 - smooth) + offsets[seg + 1] * smooth
        frames.append(positions)
    return frames


def hookean_group_frames(base: np.ndarray, indices: list[int], delta: np.ndarray, count=42) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        t = 0.5 - 0.5 * math.cos(2 * math.pi * step / count)
        positions = base.copy()
        for idx in indices:
            positions[idx] = base[idx] + delta * t
        frames.append(positions)
    return frames


def capture_phosphorene_media(browser) -> None:
    source, _, frames, metadata = make_phosphorene_twist_scene()
    editor, page = open_scene(browser, source, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.56,
            "showBonds": True,
            "bondThickness": 0.20,
            "showGrid": False,
            "showCell": False,
            "showAxes": False,
            "viewportBackground": "white",
            "rotatePivot": "selection",
            "commensurateGuide": False,
            "labelMaterials": {"P": "standard"},
        })
        configure_inspector(page, "structure", ["transform"], width=430)
        center = np.mean(source.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([18.0, -31.0, 17.0])).tolist(),
            fov=32,
        )
        set_atomic_scale(page, 27.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=3.15,
            position_offset=(-18.0, -24.0, 30.0),
        )
        rendered_frames: list[Image.Image] = []
        active_operation = None
        operation_frames = metadata["frame_operations"]
        for frame, operation in zip(frames, operation_frames):
            operation_index = int(operation["operation_index"])
            if operation_index != active_operation:
                update_positions(page, frame.positions)
                start_atom_rotation(
                    page,
                    operation["selected_indices"],
                    axis=metadata["axis"],
                    pivot_mode="selection",
                )
                set_view_toggles(page, grid=False, axes=False, cell=False)
                active_operation = operation_index
            set_atom_rotation_angle(
                page,
                operation["angle_degrees"],
                (
                    f"step {operation_index + 1}/{operation['operation_count']} | "
                    f"slices {int(operation['slice_start']) + 1}-end"
                ),
            )
            page.wait_for_timeout(35)
            rendered_frames.append(screenshot_frame(page))
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_phosphorene_twist.gif",
            duration=105,
        )
        rendered_frames[-1].save(ASSET_DIR / "readme_overview.png", optimize=True)
    finally:
        page.close()
        editor.close()


def capture_ferrocene_media(browser) -> None:
    atoms, indices = make_ferrocene_scene()
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.74,
            "showBonds": True,
            "bondThickness": 0.18,
            "showGrid": False,
            "showCell": False,
            "showAxes": False,
            "viewportBackground": "white",
            "rotatePivot": "origin",
            "commensurateGuide": False,
            "labelMaterials": {"Fe": "metal", "C": "standard", "H": "standard"},
        })
        configure_inspector(page, "structure", ["transform"], width=420)
        settle_view(
            page,
            target=[0.0, 0.0, 0.0],
            position=[6.4, -8.6, 5.4],
            fov=31,
        )
        set_atomic_scale(page, 142.0)
        set_readme_lighting(
            page,
            [0.0, 0.0, 0.0],
            intensity=3.05,
            position_offset=(-6.0, -8.0, 10.0),
        )
        start_atom_rotation(
            page,
            indices["top_ring"],
            axis="Z",
            pivot_mode="origin",
        )
        set_view_toggles(page, grid=False, axes=False, cell=False)
        rendered_frames: list[Image.Image] = []
        count = 36
        for frame_index in range(count):
            phase = 0.5 - 0.5 * math.cos(2 * math.pi * frame_index / (count - 1))
            angle = 72.0 * phase
            set_atom_rotation_angle(page, angle, "pivot: origin (Fe)")
            page.wait_for_timeout(35)
            rendered_frames.append(screenshot_frame(page))
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_ferrocene_pivot.gif",
            duration=90,
        )
        rendered_frames[count // 2].save(
            ASSET_DIR / "readme_rotate.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_commensurate_media(browser) -> None:
    atoms, indices = make_graphene_hbn_commensurate_scene()
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.52,
            "showBonds": True,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "labelColors": {"C": "#46545b", "B": "#d89a4a", "N": "#3f72c9"},
            "commensurateGuide": True,
            "commensurateSnap": False,
            "commensurateMaxIndex": 32,
            "commensurateStrainTolerance": 0.01,
        })
        set_selection(page, indices["hbn"])
        configure_inspector(page, "structure", ["transform"], width=440)
        center = np.mean(atoms.positions, axis=0)
        camera_target = center + np.array([-2.2, 0.0, 0.45])
        set_camera(
            page,
            target=camera_target.tolist(),
            position=(camera_target + np.array([0.0, 0.0, 31.0])).tolist(),
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        set_readme_lighting(page, center.tolist(), intensity=3.0, position_offset=(-10.0, -13.0, 18.0))
        set_atomic_scale(page, 59.0)
        start_atom_rotation(
            page,
            indices["hbn"],
            axis="Z",
            pivot_mode="selection",
        )
        set_view_toggles(page, grid=False, axes=False, cell=True)
        page.wait_for_function("window.__V_ASE_APP__.state.commensurateCandidates?.length > 0")
        target_angle = page.evaluate("""() => {
            const candidates = window.__V_ASE_APP__.state.commensurateCandidates || [];
            const ranked = [...candidates].sort((left, right) =>
                Math.abs(Math.abs(Number(left.angle_deg)) - 6)
                - Math.abs(Math.abs(Number(right.angle_deg)) - 6)
            );
            return Math.abs(Number(ranked[0]?.angle_deg || 6));
        }""")
        rendered_frames: list[Image.Image] = []
        count = 38
        peak_frame = count // 2
        for frame_index in range(count):
            phase = 0.5 - 0.5 * math.cos(2 * math.pi * frame_index / (count - 1))
            angle = target_angle * phase
            set_atom_rotation_angle(
                page,
                angle,
                f"cell match: {target_angle:.2f} deg",
            )
            page.wait_for_timeout(35)
            rendered_frames.append(screenshot_frame(page))
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_commensurate.gif",
            duration=95,
        )
        rendered_frames[peak_frame].save(
            ASSET_DIR / "readme_commensurate.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_bond_media(browser) -> None:
    atoms = make_frames()[-1]
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.58,
            "bondMode": "pairwise",
            "showBonds": True,
            "pairwiseBondRanges": {
                "Na-Na": {"enabled": False, "max": 3.15},
                "Cl-Na": {"enabled": True, "max": 3.10},
                "Cl-Cl": {"enabled": False, "max": 3.55},
            },
            "showGrid": True,
            "viewportBackground": "white",
        })
        configure_inspector(page, "structure", ["bonding"], width=520)
        center = np.mean(atoms.positions, axis=0)
        settle_view(page, target=center.tolist(), position=(center + np.array([12, -16, 11])).tolist(), fov=37)
        set_readme_lighting(page, center.tolist(), intensity=2.8)
        page.screenshot(path=ASSET_DIR / "readme_bonds.png")
    finally:
        page.close()
        editor.close()


def capture_constraint_media(browser) -> None:
    fixedline_atoms, line_idx = make_cnt_fixedline_scene()
    editor, page = open_scene(browser, fixedline_atoms, show_bonds=True)
    try:
        set_display(page, {"atomRadiusScale": 0.54, "showBonds": True, "showGrid": True})
        set_selection(page, [line_idx["ion"]])
        configure_inspector(page, "structure", ["constraints", "transform"])
        target = [7.0, 7.0, line_idx["z_length"] * 0.52]
        settle_view(page, target=target, position=[16.5, -6.2, line_idx["z_length"] * 0.72], fov=38)
        set_readme_lighting(page, target, intensity=2.8)
        page.screenshot(path=ASSET_DIR / "readme_constraints.png")
        enter_mode(page, "MOVE", "Z")
        capture_animation(
            page,
            ASSET_DIR / "readme_fixedline.gif",
            sinusoidal_frames(
                fixedline_atoms.get_positions(),
                line_idx["ion"],
                lambda phase: [0, 0, 2.2 * phase],
            ),
        )
    finally:
        page.close()
        editor.close()

    fixedplane_atoms, plane_idx = make_surface_fixedplane_scene()
    editor, page = open_scene(browser, fixedplane_atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.60,
            "showBonds": True,
            "showGrid": False,
            "showCell": True,
            "viewportBackground": "white",
        })
        set_selection(page, [plane_idx["ion"]])
        configure_inspector(page, "structure", ["constraints", "transform"])
        ion_position = fixedplane_atoms.positions[plane_idx["ion"]]
        target = (ion_position + np.array([0.0, 0.0, -0.7])).tolist()
        settle_view(
            page,
            target=target,
            position=(np.asarray(target) + np.array([7.8, -10.2, 7.2])).tolist(),
            fov=36,
        )
        set_atomic_scale(page, 72.0)
        set_readme_lighting(page, target, intensity=2.75)
        enter_mode(page, "MOVE", None)

        def keep_fixed_plane_motion_guide(active_page, _frame_index, _frame_total):
            active_page.evaluate(
                """(atomIndex) => {
                    const app = window.__V_ASE_APP__;
                    app.renderer.setConstraintMotionGuides({
                        mode: 'MOVE',
                        indices: [atomIndex],
                        originalPositions: app.state.originalPositions,
                        applyConstraints: true
                    });
                    app.renderer.renderNow();
                }""",
                plane_idx["ion"],
            )

        capture_animation(
            page,
            ASSET_DIR / "readme_fixedplane.gif",
            plane_sweep_frames(fixedplane_atoms.get_positions(), plane_idx["ion"]),
            on_frame=keep_fixed_plane_motion_guide,
        )
    finally:
        page.close()
        editor.close()

    hookean_atoms, indices = make_hookean_surface_scene()
    editor, page = open_scene(browser, hookean_atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.54,
            "labelRadii": {"Cu": 0.42, "C": 0.56, "O": 0.60, "H": 0.28},
            "showBonds": True,
            "showGrid": True,
        })
        set_selection(page, [])
        configure_inspector(page, "inspect", ["structure-info", "selection"])
        base = hookean_atoms.get_positions()
        carbon_pos = base[indices["carbon"]].copy()
        oxygen_pos = base[indices["oxygen"]].copy()
        direction = oxygen_pos - carbon_pos
        direction /= np.linalg.norm(direction)
        preview_delta = direction * 1.38
        target = (carbon_pos + oxygen_pos) * 0.5 + preview_delta * 0.48 + np.array([0.15, 0.05, 0.12])
        settle_view(page, target=target.tolist(), position=(target + np.array([3.9, -4.7, 2.9])).tolist(), fov=33)
        set_atomic_scale(page, min(230.0, MEDIA_SIZE[0] / 9.5))
        set_readme_lighting(page, target.tolist(), intensity=3.0, position_offset=(-7.0, -9.0, 12.0))
        active_preview = base.copy()
        active_preview[indices["oxygen"]] += preview_delta
        active_preview[indices["hydroxyl_h"]] += preview_delta
        update_positions(page, active_preview)
        page.screenshot(path=ASSET_DIR / "readme_hookean.png")
        end = carbon_pos + direction * 3.02
        delta = end - oxygen_pos
        capture_animation(
            page,
            ASSET_DIR / "readme_hookean.gif",
            hookean_group_frames(base, [indices["oxygen"], indices["hydroxyl_h"]], delta),
        )
    finally:
        page.close()
        editor.close()


def capture_measurement_media(browser) -> None:
    atoms, indices = make_ethane_measurement_scene()
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.78,
            "showBonds": True,
            "showGrid": False,
            "showCell": False,
            "showAxes": False,
            "viewportBackground": "white",
        })
        configure_inspector(page, "inspect", ["selection"], width=500)
        center = np.mean(atoms.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([4.8, -6.4, 4.0])).tolist(),
            fov=31,
        )
        set_atomic_scale(page, 178.0)
        set_readme_lighting(page, center.tolist(), intensity=2.85, position_offset=(-6.0, -8.0, 10.0))
        rendered_frames: list[Image.Image] = []
        ordered = indices["ordered_selection"]
        for selection_size in (2, 3, 4, 3):
            set_selection(page, ordered[:selection_size])
            page.wait_for_timeout(140)
            frame = screenshot_frame(page)
            rendered_frames.extend([frame.copy() for _ in range(5)])
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_measurement.gif",
            duration=125,
        )
        set_selection(page, ordered)
        page.wait_for_timeout(120)
        screenshot_frame(page).save(
            ASSET_DIR / "readme_measurement.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()

    initial = fcc111("Cu", size=(3, 4, 2), vacuum=6.0, orthogonal=True)
    displaced = initial.copy()
    center = np.mean(initial.positions, axis=0)
    offsets = displaced.positions - center
    displacement = np.column_stack([
        0.42 * np.sin(offsets[:, 1] * 0.75),
        0.36 * np.cos(offsets[:, 0] * 0.65),
        0.18 + 0.12 * np.sin((offsets[:, 0] + offsets[:, 1]) * 0.55),
    ])
    displaced.positions += displacement
    editor, page = open_scene(browser, [initial, displaced], show_bonds=False)
    try:
        set_display(page, {
            "atomRadiusScale": 0.60,
            "showBonds": False,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "displacementReferenceMode": "previous",
            "displacementMic": True,
            "displacementStyle": "3d",
            "displacementScale": 3.4,
            "displacementThickness": 0.12,
            "displacementColor": "#dc5c32",
        })
        configure_inspector(page, "analysis", ["displacement"], width=455)
        page.evaluate("window.__V_ASE_APP__.loadFrame(1)")
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.metadata.current_frame === 1"
        )
        page.check("#chk-displacement")
        page.wait_for_function(
            "Number(window.__V_ASE_APP__.renderer.domElement.dataset.displacementCount || 0) > 0"
        )
        center = np.mean(displaced.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([7.5, -10.5, 8.0])).tolist(),
            fov=34,
        )
        set_atomic_scale(page, 77.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.9,
            position_offset=(-8.0, -10.0, 13.0),
        )
        screenshot_frame(page).save(
            ASSET_DIR / "readme_displacement.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_relaxation_media(browser) -> None:
    initial, relaxed, frames, _ = make_crowded_c60_relaxation_scene()
    editor, page = open_scene(browser, initial, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.46,
            "showBonds": False,
            "showGrid": False,
            "showCell": False,
            "viewportBackground": "white",
        })
        configure_inspector(page, "structure", ["scientific-tools"], width=430)
        center = np.mean(initial.positions, axis=0)
        settle_view(page, target=center.tolist(), position=(center + np.array([8.5, -10.5, 7.5])).tolist(), fov=35)
        set_atomic_scale(page, 82.0)
        set_readme_lighting(page, center.tolist(), intensity=2.9, position_offset=(-8.0, -10.0, 13.0))
        position_frames = [frame.positions for frame in frames]
        capture_animation(
            page,
            ASSET_DIR / "readme_relaxation.gif",
            position_frames,
            duration=95,
        )
        update_positions(page, relaxed.positions)
        page.screenshot(path=ASSET_DIR / "readme_relaxation.png")
    finally:
        page.close()
        editor.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--logo-only",
        action="store_true",
        help="Regenerate only the shared transparent v_ase logo asset.",
    )
    parser.add_argument(
        "--skip-logo",
        action="store_true",
        help="Keep the existing logo while regenerating README scenes.",
    )
    parser.add_argument(
        "--only",
        choices=(
            "phosphorene",
            "ferrocene",
            "commensurate",
            "bonds",
            "constraints",
            "measurement",
            "relaxation",
        ),
        help="Regenerate one README scene group.",
    )
    args = parser.parse_args()
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    import webbrowser

    original_open = webbrowser.open
    webbrowser.open = lambda *args, **kwargs: True

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            if args.logo_only:
                capture_logo(browser)
                return 0
            if not args.skip_logo and ASSET_DIR.resolve() == (ROOT / "docs" / "assets").resolve():
                capture_logo(browser)
            captures = {
                "phosphorene": capture_phosphorene_media,
                "ferrocene": capture_ferrocene_media,
                "commensurate": capture_commensurate_media,
                "bonds": capture_bond_media,
                "constraints": capture_constraint_media,
                "measurement": capture_measurement_media,
                "relaxation": capture_relaxation_media,
            }
            if args.only:
                captures[args.only](browser)
            else:
                for capture in captures.values():
                    capture(browser)
        finally:
            browser.close()
            webbrowser.open = original_open

    sync_github_readme_assets()
    print(f"Wrote README media to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
