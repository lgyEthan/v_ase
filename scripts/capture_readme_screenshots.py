"""Capture README screenshots and GIFs from local v_ase scenes."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import Sequence

import numpy as np
from ase import Atoms
from ase.build import fcc111, molecule
from ase.geometry import find_mic
from ase.io import read
from ase.io.cube import write_cube
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.manual_showcase import make_frames
from v_ase import view
from v_ase.ai import ai_handshake
from examples.readme_scenes import (
    make_atom_colorscale_trajectory,
    make_copper_oxide_bond_scene,
    make_crowded_c60_relaxation_scene,
    make_ethane_measurement_scene,
    make_ferrocene_scene,
    make_graphene_hbn_commensurate_scene,
    make_hookean_surface_scene,
    make_layered_water_channel_scene,
    make_ai_pyridinic_graphene_scene,
    make_amorphous_cuzr_rdf_scene,
    make_graphene_pi_volumetric_scene,
    make_material_preset_scene,
    make_phosphorene_twist_scene,
    make_random_addition_scene,
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


def write_ai_collaboration_recording_html(
    figure_html: str,
    stage_records: Sequence[dict[str, object]],
    output: Path,
) -> None:
    """Write a self-contained, auto-playing recording surface.

    The stage images come from the same live CLI/GUI workflow used for the
    README animation. Keeping them in one local HTML file lets a human record
    a lossless MOV without running v_ase or a web server again.
    """

    if not stage_records:
        raise ValueError("AI collaboration recording requires at least one stage.")
    records_json = json.dumps(
        list(stage_records),
        ensure_ascii=True,
        separators=(",", ":"),
    ).replace("</", "<\\/")
    first_image = str(stage_records[0].get("image") or "")
    if first_image:
        figure_html = figure_html.replace(
            "../assets/readme_ai_collaboration_live.png",
            first_image,
        )
    playback = f"""
<script id="v-ase-collaboration-records" type="application/json">{records_json}</script>
<script>
(() => {{
  const records = JSON.parse(
    document.getElementById('v-ase-collaboration-records').textContent
  );
  let index = 0;
  let playing = true;
  let generation = 0;

  const fitStage = () => {{
    const scale = Math.min(window.innerWidth / 1800, window.innerHeight / 1080);
    const left = Math.max(0, (window.innerWidth - 1800 * scale) / 2);
    const top = Math.max(0, (window.innerHeight - 1080 * scale) / 2);
    document.body.style.transformOrigin = 'top left';
    document.body.style.transform = `translate(${{left}}px, ${{top}}px) scale(${{scale}})`;
  }};

  const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  const holdFor = record => (
    record.flow === 'reply' || record.flow === 'complete' ? 2600 : 1750
  );

  const play = async token => {{
    while (token === generation) {{
      if (!playing) {{
        await delay(80);
        continue;
      }}
      const record = records[index];
      await window.setCollaborationStage(record);
      document.documentElement.dataset.recordingStage = String(index + 1);
      document.documentElement.dataset.recordingFlow = String(record.flow || '');
      await delay(holdFor(record));
      if (!playing || token !== generation) continue;
      index = (index + 1) % records.length;
      if (index === 0) await delay(900);
    }}
  }};

  const restart = () => {{
    generation += 1;
    index = 0;
    playing = true;
    play(generation);
  }};

  window.addEventListener('resize', fitStage);
  window.addEventListener('keydown', event => {{
    if (event.code === 'Space') {{
      event.preventDefault();
      playing = !playing;
      document.documentElement.dataset.recordingPaused = String(!playing);
    }} else if (event.key.toLowerCase() === 'r') {{
      restart();
    }}
  }});
  window.v_aseCollaborationRecording = {{
    records,
    restart,
    pause: () => {{ playing = false; }},
    resume: () => {{ playing = true; }},
    get index() {{ return index; }},
    get playing() {{ return playing; }},
  }};
  fitStage();
  play(generation);
}})();
</script>
"""
    document = figure_html.replace("</body>", f"{playback}</body>", 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


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


def collapse_inspector(page):
    page.evaluate("""() => {
        const app = window.__V_ASE_APP__;
        app.setInspectorCollapsed(true, false);
        app.renderer.renderNow();
    }""")
    page.wait_for_function(
        "document.body.classList.contains('inspector-collapsed')"
    )
    page.wait_for_timeout(100)


def set_display(page, options):
    page.evaluate(
        """(options) => {
            const app = window.__V_ASE_APP__;
            const current = app.state.display || {};
            const merged = {
                ...current,
                ...options,
                labelRadii: {...(current.labelRadii || {}), ...(options.labelRadii || {})},
                labelColors: {...(current.labelColors || {}), ...(options.labelColors || {})},
                labelMaterials: {...(current.labelMaterials || {}), ...(options.labelMaterials || {})},
                labelVisible: {...(current.labelVisible || {}), ...(options.labelVisible || {})},
                pairwiseBondCutoffs: {
                    ...(current.pairwiseBondCutoffs || {}),
                    ...(options.pairwiseBondCutoffs || {})
                },
                pairwiseBondRanges: {
                    ...(current.pairwiseBondRanges || {}),
                    ...(options.pairwiseBondRanges || {})
                },
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


def start_atom_rotation(
    page,
    indices,
    *,
    axis: str,
    pivot_mode: str,
    pivot_index: int | None = None,
):
    page.evaluate(
        """async ({ indices, axis, pivotMode, pivotIndex }) => {
            const app = window.__V_ASE_APP__;
            if (app.transform.mode !== 'IDLE') {
                app.transform.exit();
                app.state.transformSubject = null;
                app.renderer.controls.enabled = true;
                app.clearCommensurateRotation({ keepStatus: true });
            }
            app.clearAtomSelection();
            indices.forEach(index => app.addSelectionReference(index));
            if (Number.isInteger(pivotIndex) && !indices.includes(pivotIndex)) {
                app.addSelectionReference(pivotIndex);
            }
            app.state.display.rotatePivot = pivotMode;
            const pivotInput = document.getElementById('rotate-pivot');
            if (pivotInput) pivotInput.value = pivotMode;
            const exactAxisInput = document.getElementById('selection-rotate-axis');
            if (exactAxisInput) exactAxisInput.value = axis;
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
            "pivotIndex": None if pivot_index is None else int(pivot_index),
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


def set_camera(page, *, target, position, up=(0, 0, 1), fov=38, wait_ms=250):
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
    page.wait_for_timeout(max(0, int(wait_ms)))


def append_camera_x_orbit(
    frames: list[Image.Image],
    page,
    *,
    target: np.ndarray,
    radius: float,
    start_degrees: float,
    end_degrees: float,
    count: int,
    fov: float,
) -> None:
    """Record an above-to-below camera orbit around the scene X axis."""

    for angle_degrees in np.linspace(start_degrees, end_degrees, max(2, count)):
        angle = math.radians(float(angle_degrees))
        offset = np.array([
            0.0,
            -radius * math.cos(angle),
            radius * math.sin(angle),
        ])
        set_camera(
            page,
            target=target.tolist(),
            position=(target + offset).tolist(),
            up=(0, 0, 1),
            fov=fov,
            wait_ms=45,
        )
        frames.append(screenshot_frame(page))


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


def settle_view(page, *, target=None, position=None, up=(0, 0, 1), fov=38):
    page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            app.renderer.fitCameraToStructure();
            app.renderer.renderer.render(app.renderer.scene, app.renderer.camera);
        }"""
    )
    page.wait_for_timeout(400)
    if target is not None and position is not None:
        set_camera(page, target=target, position=position, up=up, fov=fov)


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


def append_hold(frames: list[Image.Image], page, count: int) -> None:
    frame = screenshot_frame(page)
    frames.extend(frame.copy() for _ in range(max(1, int(count))))


def projected_atom_points(page) -> list[dict[str, float | int]]:
    return page.evaluate(
        """() => {
            const app = window.__V_ASE_APP__;
            const camera = app.renderer.camera;
            camera.updateMatrixWorld(true);
            const points = [];
            app.renderer.forEachAtomProxy((mesh, index) => {
                if (mesh.visible === false || !app.renderer.atomLabelVisible(index)) return;
                const point = mesh.position.clone().project(camera);
                if (![point.x, point.y, point.z].every(Number.isFinite)
                    || point.z < -1 || point.z > 1) return;
                points.push({
                    index,
                    x: (point.x + 1) * window.innerWidth / 2,
                    y: (-point.y + 1) * window.innerHeight / 2
                });
            });
            return points;
        }"""
    )


def tail_selection_rectangle(page, indices: list[int]) -> dict[str, float]:
    points = projected_atom_points(page)
    selected_set = {int(index) for index in indices}
    selected = [point for point in points if int(point["index"]) in selected_set]
    excluded = [point for point in points if int(point["index"]) not in selected_set]
    if len(selected) != len(selected_set):
        raise AssertionError(
            f"Only {len(selected)} of {len(selected_set)} target atoms project into the viewport."
        )
    if not excluded:
        raise AssertionError("Tail selection needs at least one fixed reference ridge.")

    target_mean = float(np.mean([point["x"] for point in selected]))
    excluded_mean = float(np.mean([point["x"] for point in excluded]))
    width, height = MEDIA_SIZE
    vertical_margin = 28.0
    if target_mean > excluded_mean:
        boundary = 0.5 * (
            min(float(point["x"]) for point in selected)
            + max(float(point["x"]) for point in excluded)
        )
        left = boundary
        right = min(width - 8.0, max(float(point["x"]) for point in selected) + 34.0)
    else:
        boundary = 0.5 * (
            max(float(point["x"]) for point in selected)
            + min(float(point["x"]) for point in excluded)
        )
        left = max(8.0, min(float(point["x"]) for point in selected) - 34.0)
        right = boundary
    top = max(72.0, min(float(point["y"]) for point in selected) - vertical_margin)
    bottom = min(height - 22.0, max(float(point["y"]) for point in selected) + vertical_margin)
    return {"left": left, "right": right, "top": top, "bottom": bottom}


def drag_select_tail(
    page,
    indices: list[int],
    output_frames: list[Image.Image],
    *,
    marquee_frames: int = 3,
) -> None:
    rectangle = tail_selection_rectangle(page, indices)
    start = (rectangle["right"], rectangle["bottom"])
    end = (rectangle["left"], rectangle["top"])
    page.mouse.move(*start)
    page.mouse.down(button="left")
    for step in range(1, max(2, marquee_frames) + 1):
        fraction = step / max(2, marquee_frames)
        page.mouse.move(
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
        )
        page.wait_for_timeout(55)
        output_frames.append(screenshot_frame(page))
    page.mouse.up(button="left")
    page.wait_for_timeout(90)
    selected = page.evaluate(
        """() => [...window.__V_ASE_APP__.state.selected]
            .filter(reference => Number.isInteger(reference))
            .sort((a, b) => a - b)"""
    )
    expected = sorted(int(index) for index in indices)
    if selected != expected:
        missing = sorted(set(expected) - set(selected))
        unexpected = sorted(set(selected) - set(expected))
        raise AssertionError(
            f"Actual box selection returned {len(selected)} atoms; expected {len(expected)}. "
            f"Missing {missing[:12]}; unexpected {unexpected[:12]}."
        )
    append_hold(output_frames, page, 2)


def open_transform_panel_for_capture(page, output_frames: list[Image.Image], *, detailed: bool) -> None:
    page.keyboard.press("Tab")
    page.wait_for_function(
        "() => !document.body.classList.contains('inspector-collapsed')"
    )
    if detailed:
        append_hold(output_frames, page, 1)
    page.click('[data-inspector-group="structure"]')
    page.select_option("#structure-section-select", "transform")
    page.evaluate("""() => {
        const panel = document.querySelector('[data-panel="transform"]');
        const content = document.getElementById('inspector-content');
        const select = document.getElementById('structure-section-select');
        if (!panel || !content || !select) return;
        panel.open = true;
        const contentTop = content.getBoundingClientRect().top;
        const top = Math.max(
            0,
            content.scrollTop + panel.getBoundingClientRect().top - contentTop
        );
        content.scrollTo({top, behavior: 'instant'});
        select.value = 'transform';
    }""")
    page.wait_for_function(
        """() => {
            const panel = document.querySelector('[data-panel="transform"]');
            const content = document.getElementById('inspector-content');
            const select = document.getElementById('structure-section-select');
            if (!panel || !content || !select) return false;
            const panelRect = panel.getBoundingClientRect();
            const contentRect = content.getBoundingClientRect();
            return select.value === 'transform'
                && panelRect.top >= contentRect.top - 3
                && panelRect.top <= contentRect.top + 36;
        }"""
    )
    page.wait_for_timeout(120)
    append_hold(output_frames, page, 2 if detailed else 1)


def apply_exact_panel_rotation(
    page,
    angle_degrees: float,
    output_frames: list[Image.Image],
    *,
    detailed: bool,
) -> None:
    before_positions = np.asarray(
        page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
        dtype=float,
    )
    page.select_option("#rotate-pivot", "selection")
    page.select_option("#selection-rotate-axis", "X")
    angle_input = page.locator("#selection-rotate-angle")
    angle_input.click()
    angle_input.press("ControlOrMeta+A")
    angle_input.type(f"{angle_degrees:.6f}")
    if detailed:
        append_hold(output_frames, page, 2)

    button = page.locator("#btn-rotate-selection-exact")
    box = button.bounding_box()
    if not box:
        raise AssertionError("Exact rotation button is not visible in the Transform panel.")
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    if detailed:
        output_frames.append(screenshot_frame(page))
    button.click()
    page.wait_for_function(
        """(before) => window.__V_ASE_APP__.state.atoms.positions.some(
            (position, index) => position.some(
                (value, axis) => Math.abs(value - before[index][axis]) > 1e-8
            )
        )""",
        arg=before_positions.tolist(),
    )
    page.wait_for_function("() => window.__V_ASE_APP__.transform.mode === 'IDLE'")
    page.evaluate("async () => await window.__V_ASE_APP__.pendingApply")
    page.wait_for_timeout(90)
    after_positions = np.asarray(
        page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
        dtype=float,
    )
    displacement = float(np.max(np.abs(after_positions - before_positions)))
    if displacement <= 1e-8:
        raise AssertionError(
            "The exact-rotation panel button completed without changing selected coordinates."
        )
    append_hold(output_frames, page, 2 if detailed else 1)
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.body.classList.contains('inspector-collapsed')"
    )
    if detailed:
        append_hold(output_frames, page, 1)


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


def open_scene(browser, atoms_or_frames, *, show_bonds=False, viz_only=False):
    editor = view(
        atoms_or_frames,
        block=False,
        viz_only=viz_only,
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


def external_ai_command_url(editor, *, workspace: bool = False) -> str:
    """Return the same loopback command URL printed by ``v_ase gui --cli``."""
    url = editor.url if workspace else (
        f"http://127.0.0.1:{editor.port}/?session_id={editor.session_id}"
    )
    command_url = ai_handshake(url).get("command_url")
    if not command_url:
        raise AssertionError("README capture could not discover the AI command URL.")
    return str(command_url)


def run_external_ai_command(
    command_url: str,
    method: str,
    params: dict | None = None,
    *,
    timeout: float = 180.0,
):
    """Invoke the public ``v_ase api`` executable, not an in-page helper."""
    command = [
        sys.executable,
        "-m",
        "v_ase.cli",
        "api",
        command_url,
        method,
        "--timeout",
        f"{float(timeout):g}",
    ]
    if params is not None:
        command.extend(["--params", json.dumps(params, separators=(",", ":"))])
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout + 10.0,
        )
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"v_ase api {method} failed with exit {exc.returncode}: "
            f"stdout={exc.stdout!r}; stderr={exc.stderr!r}"
        ) from exc
    try:
        envelope = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"v_ase api returned non-JSON output for {method}: {completed.stdout!r}"
        ) from exc
    if "result" not in envelope:
        raise AssertionError(f"v_ase api returned no result for {method}: {envelope!r}")
    return envelope["result"]


def run_external_ai_apply(command_url: str, command: dict):
    """Apply one revision-guarded command through the external CLI."""
    before = run_external_ai_command(
        command_url,
        "describe",
        {"includePositions": False},
    )
    guarded = {
        **command,
        "expectedRevision": before["collaboration"]["revision"],
    }
    return run_external_ai_command(command_url, "apply", guarded)


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
    source, twisted, _, metadata = make_phosphorene_twist_scene()
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
            "labelColors": metadata["sublayer_colors"],
            "labelMaterials": {
                "P_upper": "standard",
                "P_lower": "standard",
            },
        })
        collapse_inspector(page)
        center = 0.5 * (
            np.min(source.positions, axis=0)
            + np.max(source.positions, axis=0)
        )
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([0.0, -28.0, 26.0])).tolist(),
            fov=34,
        )
        set_atomic_scale(page, 42.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=3.15,
            position_offset=(-18.0, -24.0, 30.0),
        )
        rendered_frames: list[Image.Image] = []
        set_selection(page, [])
        page.wait_for_timeout(120)
        append_hold(rendered_frames, page, 7)

        operations = metadata["operations"]
        angle_increment = float(metadata["angle_increment_degrees"])
        for operation_index, operation in enumerate(operations):
            detailed = operation_index < 2
            drag_select_tail(
                page,
                operation["selected_indices"],
                rendered_frames,
                marquee_frames=4 if detailed else 2,
            )
            open_transform_panel_for_capture(
                page,
                rendered_frames,
                detailed=detailed,
            )
            apply_exact_panel_rotation(
                page,
                angle_increment,
                rendered_frames,
                detailed=detailed,
            )

        actual_positions = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        if not np.allclose(actual_positions, twisted.positions, atol=2e-5, rtol=0):
            max_error = float(np.max(np.abs(actual_positions - twisted.positions)))
            raise AssertionError(
                "Recorded browser edits missed the literature-angle target "
                f"by {max_error:.3e} A."
            )
        set_selection(page, [])
        append_hold(rendered_frames, page, 4)
        append_camera_x_orbit(
            rendered_frames,
            page,
            target=center,
            radius=38.0,
            start_degrees=43.0,
            end_degrees=-43.0,
            count=24,
            fov=34,
        )
        append_hold(rendered_frames, page, 6)
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_phosphorene_twist.gif",
            duration=115,
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
        rendered_frames: list[Image.Image] = []
        start_atom_rotation(
            page,
            indices["top_ring"],
            axis="Z",
            pivot_mode="active",
            pivot_index=indices["iron"][0],
        )
        set_view_toggles(page, grid=False, axes=False, cell=False)
        count = 30
        for frame_index in range(count):
            phase = math.sin(math.pi * frame_index / (count - 1))
            angle = 72.0 * phase
            set_atom_rotation_angle(
                page,
                angle,
                "1/2 | active pivot: Fe #0 | R Z",
            )
            page.wait_for_timeout(35)
            rendered_frames.append(screenshot_frame(page))

        update_positions(page, atoms.positions)
        start_atom_rotation(
            page,
            indices["top_ring"],
            axis="X",
            pivot_mode="active",
            pivot_index=indices["iron"][0],
        )
        set_view_toggles(page, grid=False, axes=False, cell=False)
        for frame_index in range(count):
            phase = math.sin(math.pi * frame_index / (count - 1))
            angle = 38.0 * phase
            set_atom_rotation_angle(
                page,
                angle,
                "2/2 | active pivot: Fe #0 | R X ring fold",
            )
            page.wait_for_timeout(35)
            rendered_frames.append(screenshot_frame(page))
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_ferrocene_pivot.gif",
            duration=90,
        )
        rendered_frames[count + count // 2].save(
            ASSET_DIR / "readme_rotate.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_commensurate_media(browser) -> None:
    atoms, indices = make_graphene_hbn_commensurate_scene()
    editor, page = open_scene(browser, atoms, show_bonds=True, viz_only=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.52,
            "showBonds": True,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "labelColors": {"C": "#46545b", "B": "#d89a4a", "N": "#3f72c9"},
            "commensurateGuide": False,
            "commensurateSnap": False,
            "commensurateMaxIndex": 32,
            "commensurateStrainTolerance": 0.01,
            "commensurateMaxAreaRatio": 16,
            "commensurateShowAtoms": False,
            "commensurateGuestAngleDeg": 17.0,
        })
        configure_inspector(page, "structure", ["transform"], width=470)
        page.add_style_tag(content="""
            #measurement-overlay,
            #selection-measure-readout,
            #hover-readout,
            #coord-readout { display: none !important; }
            #commensurate-plot .xtitle,
            #commensurate-plot .ytitle,
            #commensurate-plot .ztitle { font-weight: 900 !important; }
            #readme-commensurate-stage {
                position: fixed; z-index: 5000; top: 76px; left: 22px;
                max-width: 760px; padding: 12px 16px;
                border: 2px solid #c6d4d2; border-left: 8px solid #161a1d;
                border-radius: 6px; background: rgba(255,255,255,.97);
                color: #223437; box-shadow: 0 6px 20px rgba(20,38,41,.14);
                pointer-events: none;
            }
            #readme-commensurate-stage strong { display: block; font-size: 21px; }
            #readme-commensurate-stage span { display: block; margin-top: 4px; font-size: 17px; font-weight: 760; }
        """)
        page.evaluate("""() => {
            const overlay = document.createElement('div');
            overlay.id = 'readme-commensurate-stage';
            overlay.innerHTML = '<strong>PARENT LATTICES</strong><span>Host fixed · guest rotates · common cell hidden until a bounded strain match</span>';
            document.body.appendChild(overlay);
            window.__setReadmeCommensurateStage = (title, detail, color = '#161a1d') => {
                overlay.querySelector('strong').textContent = title;
                overlay.querySelector('span').textContent = detail;
                overlay.style.borderLeftColor = color;
            };
        }""")
        center = np.mean(atoms.positions, axis=0)
        set_readme_lighting(page, center.tolist(), intensity=3.0, position_offset=(-10.0, -13.0, 18.0))
        set_selection(page, indices["hbn"])
        page.locator("#chk-commensurate-guide").set_checked(True)
        page.wait_for_function("window.__V_ASE_APP__.state.commensurateCandidates?.length > 0")
        page.wait_for_function(
            "window.__V_ASE_APP__.state.display.commensurateShowAtoms === false"
        )
        page.wait_for_function("""() => {
            const preview = window.__V_ASE_APP__.state.commensurateProposal?.data?.preview;
            return preview && preview.include_atoms === false
                && window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                    .some(child => child.userData?.commensurateHostPrimitiveGrid)
                && window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                    .some(child => child.userData?.commensurateGuestPrimitiveGrid);
        }""")
        target_angle = page.evaluate("""() => {
            const candidates = window.__V_ASE_APP__.state.commensurateCandidates || [];
            const ranked = [...candidates]
                .filter(candidate => Number(candidate.area_ratio || candidate.area) <= 16)
                .sort((left, right) =>
                    Math.abs(Math.abs(Number(left.angle_deg)) - 21.786789)
                    - Math.abs(Math.abs(Number(right.angle_deg)) - 21.786789)
                );
            return Math.abs(Number(ranked[0]?.angle_deg || 21.786789));
        }""")
        preview_bounds = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const preview = app.state.commensurateProposal.data.preview;
            const bounds = app.renderer.commensuratePreviewBounds(preview);
            const minimum = bounds.min.toArray();
            const maximum = bounds.max.toArray();
            return {
                center: minimum.map((value, index) => 0.5 * (value + maximum[index])),
                size: minimum.map((value, index) => maximum[index] - value)
            };
        }""")
        preview_center = preview_bounds["center"]
        camera_distance = max(24.0, max(preview_bounds["size"][:2]) * 2.4)
        set_camera(
            page,
            target=preview_center,
            position=[preview_center[0], preview_center[1], preview_center[2] + camera_distance],
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const bounds = app.renderer.commensuratePreviewBounds(
                app.state.commensurateProposal.data.preview
            );
            app.renderer.fitCameraToStructure(bounds);
            app.renderer.renderNow();
        }""")
        set_view_toggles(page, grid=False, axes=False, cell=True)
        page.evaluate("window.__V_ASE_APP__.closeAnalysisDrawer()")
        set_camera(
            page,
            target=preview_center,
            position=[preview_center[0], preview_center[1], preview_center[2] + camera_distance],
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        set_atomic_scale(page, 55.0)
        rendered_frames: list[Image.Image] = []
        initial_context = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const preview = app.state.commensurateProposal.data.preview;
            const children = app.renderer.commensurateSupercellGroup.children;
            return {
                hostShape: preview.host_grid_shape,
                guestShape: preview.guest_grid_shape,
                hostOrigins: preview.host_grid_lattice_origins,
                guestAnchor: preview.guest_offset,
                guestGridCenter: [0, 1, 2].map(axis => (
                    preview.guest_grid_lattice_origins.reduce(
                        (sum, origin) => sum + Number(origin[axis]), 0
                    ) / preview.guest_grid_lattice_origins.length
                    + 0.5 * (
                        Number(preview.guest_primitive_vectors[0][axis])
                        + Number(preview.guest_primitive_vectors[1][axis])
                    )
                )),
                guestGridRadii: preview.guest_grid_lattice_origins.map(origin => Math.hypot(
                    ...origin.map((value, axis) => Number(value) - Number(preview.guest_offset[axis]))
                )).sort((left, right) => left - right),
                guestGridCount: preview.guest_grid_lattice_origins?.length,
                parentFixed: preview.parent_lattices_fixed,
                commonCells: children.filter(child => child.userData?.commensurateSuggestedCell).length,
                hostGrids: children.filter(child => child.userData?.commensurateHostPrimitiveGrid).length,
                guestGrids: children.filter(child => child.userData?.commensurateGuestPrimitiveGrid).length,
                baseSelectionVisible: app.renderer.selectionOutlines.visible
            };
        }""")
        if initial_context["commonCells"] != 0 or not initial_context["parentFixed"]:
            raise AssertionError("Commensurate mode must start with fixed parent lattices and no common cell.")
        if initial_context["hostGrids"] != 1 or initial_context["guestGrids"] != 1:
            raise AssertionError("Both parent superlattices must be visible immediately.")
        if initial_context["baseSelectionVisible"]:
            raise AssertionError("Cells-only commensurate mode leaked base atom selection outlines.")
        page.evaluate("""() => window.__setReadmeCommensurateStage(
            '1 · PARENT LATTICES ONLY',
            'Black host grid stays fixed · orange guest grid rotates · no common cell yet'
        )""")
        append_hold(rendered_frames, page, 8)
        page.locator('details.commensurate-advanced').evaluate(
            "element => { element.open = true; }"
        )
        page.locator("#chk-commensurate-show-atoms").set_checked(True)
        page.wait_for_function(
            "Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms) > 0"
        )
        independent_atoms = page.evaluate("""() => ({
            atoms: Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms),
            bonds: Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewBonds),
            common: window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                .filter(child => child.userData?.commensurateSuggestedCell).length
        })""")
        if independent_atoms["atoms"] <= 0 or independent_atoms["bonds"] <= 0:
            raise AssertionError("Commensurate atom visibility did not include atoms and bonds.")
        if independent_atoms["common"] != 0:
            raise AssertionError("Showing atoms exposed an unresolved common cell.")
        page.evaluate("""() => window.__setReadmeCommensurateStage(
            '2 · OPTIONAL ATOMS + BONDS',
            'Atom visibility is independent · the unresolved common cell remains hidden',
            '#087f70'
        )""")
        append_hold(rendered_frames, page, 10)
        page.locator("#chk-commensurate-show-atoms").set_checked(False)
        page.wait_for_function(
            "Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms) === 0"
        )
        page.evaluate("""() => window.__setReadmeCommensurateStage(
            '3 · ROTATE THE GUEST LATTICE',
            'The parent grid extent and origin remain fixed while only its orientation changes',
            '#f58220'
        )""")
        append_hold(rendered_frames, page, 8)
        count = 24
        initial_angle = 17.0
        for frame_index in range(count):
            phase = 0.5 - 0.5 * math.cos(math.pi * frame_index / (count - 1))
            angle = initial_angle + (target_angle - initial_angle) * phase
            page.evaluate(
                """(angle) => {
                    const input = document.getElementById('commensurate-guest-angle');
                    input.value = Number(angle).toFixed(8);
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                }""",
                angle,
            )
            page.wait_for_function(
                """angle => Math.abs(
                    Number(window.__V_ASE_APP__.state.commensurateProposal?.data?.preview?.display_angle_deg)
                    - Number(angle)
                ) < 1e-5""",
                arg=angle,
            )
            invariant = page.evaluate("""() => {
                const app = window.__V_ASE_APP__;
                const preview = app.state.commensurateProposal.data.preview;
                return {
                    hostShape: preview.host_grid_shape,
                    guestShape: preview.guest_grid_shape,
                    hostOrigins: preview.host_grid_lattice_origins,
                    guestAnchor: preview.guest_offset,
                    guestGridCenter: [0, 1, 2].map(axis => (
                        preview.guest_grid_lattice_origins.reduce(
                            (sum, origin) => sum + Number(origin[axis]), 0
                        ) / preview.guest_grid_lattice_origins.length
                        + 0.5 * (
                            Number(preview.guest_primitive_vectors[0][axis])
                            + Number(preview.guest_primitive_vectors[1][axis])
                        )
                    )),
                    guestGridRadii: preview.guest_grid_lattice_origins.map(origin => Math.hypot(
                        ...origin.map((value, axis) => Number(value) - Number(preview.guest_offset[axis]))
                    )).sort((left, right) => left - right),
                    guestGridCount: preview.guest_grid_lattice_origins?.length,
                    parentFixed: preview.parent_lattices_fixed,
                    baseSelectionVisible: app.renderer.selectionOutlines.visible
                };
            }""")
            if {
                key: value for key, value in invariant.items()
                if key not in {"guestGridCenter", "guestGridRadii"}
            } != {
                "hostShape": initial_context["hostShape"],
                "guestShape": initial_context["guestShape"],
                "hostOrigins": initial_context["hostOrigins"],
                "guestAnchor": initial_context["guestAnchor"],
                "guestGridCount": initial_context["guestGridCount"],
                "parentFixed": True,
                "baseSelectionVisible": False,
            }:
                raise AssertionError("A commensurate candidate resized the fixed parent-lattice window.")
            np.testing.assert_allclose(
                invariant["guestGridCenter"],
                initial_context["guestAnchor"],
                atol=1e-8,
            )
            np.testing.assert_allclose(
                invariant["guestGridRadii"],
                initial_context["guestGridRadii"],
                atol=1e-7,
            )
            rendered_frames.append(screenshot_frame(page))
        cells_only_frame = rendered_frames[0].copy()
        page.wait_for_function(
            "window.__V_ASE_APP__.state.commensurateProposal?.data?.suggestion_visible === true"
        )
        preview_context = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const preview = app.state.commensurateProposal.data.preview;
            const children = app.renderer.commensurateSupercellGroup.children;
            return {
                hostGridShape: preview.host_grid_shape,
                guestGridShape: preview.guest_grid_shape,
                hostNotation: preview.host_notation,
                guestNotation: preview.guest_notation,
                hostLabels: children.filter(child => child.userData?.commensurateHostCellLabel).length,
                guestLabels: children.filter(child => child.userData?.commensurateGuestCellLabel).length,
                suggestedCell: children.some(child => child.userData?.commensurateSuggestedCell)
            };
        }""")
        if min(preview_context["hostGridShape"][:2]) < 3:
            raise AssertionError("README host primitive grid does not surround the common cell.")
        if min(preview_context["guestGridShape"][:2]) < 3:
            raise AssertionError("README guest primitive grid does not surround the common cell.")
        if not all((
            preview_context["hostNotation"],
            preview_context["guestNotation"],
            preview_context["suggestedCell"],
        )):
            raise AssertionError("README commensurate cells are missing notation or boundaries.")
        if preview_context["hostLabels"] or preview_context["guestLabels"]:
            raise AssertionError("Fixed parent-lattice labels clutter the commensurate viewport.")
        if page.locator("#chk-commensurate-show-atoms").is_checked():
            raise AssertionError("Candidate discovery changed the user-controlled atom visibility.")
        page.evaluate("""() => window.__setReadmeCommensurateStage(
            '4 · STRAIN-QUALIFIED COMMON CELL',
            'The teal boundary appears only at the accepted commensurate angle',
            '#139c68'
        )""")
        append_hold(rendered_frames, page, 12)
        save_gif(
            rendered_frames,
            ASSET_DIR / "readme_commensurate.gif",
            duration=95,
        )
        cells_only_frame.save(
            ASSET_DIR / "readme_commensurate.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()

    fixture = ROOT / "examples" / "commensurate_host_guest"
    host = read(fixture / "graphene_host.extxyz")
    host_guest_target_angle = 19.10660535
    editor, page = open_scene(browser, host, show_bonds=True, viz_only=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.52,
            "showBonds": True,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "commensurateGuide": False,
            "commensurateSnap": False,
            "commensurateStrainTolerance": 0.025,
            "commensurateMaxAreaRatio": 16,
            "commensurateShowAtoms": False,
            "commensurateGuestAngleDeg": 8.0,
        })
        configure_inspector(page, "structure", ["transform"], width=470)
        page.add_style_tag(content="""
            #measurement-overlay,
            #selection-measure-readout,
            #hover-readout,
            #coord-readout { display: none !important; }
            #readme-host-guest-stage {
                position: fixed; z-index: 5000; top: 76px; left: 22px;
                max-width: 815px; padding: 12px 16px;
                border: 2px solid #c6d4d2; border-left: 8px solid #161a1d;
                border-radius: 6px; background: rgba(255,255,255,.97);
                color: #223437; box-shadow: 0 6px 20px rgba(20,38,41,.14);
                pointer-events: none;
            }
            #readme-host-guest-stage strong { display: block; font-size: 21px; }
            #readme-host-guest-stage span { display: block; margin-top: 4px; font-size: 17px; font-weight: 760; }
        """)
        page.evaluate("""() => {
            const overlay = document.createElement('div');
            overlay.id = 'readme-host-guest-stage';
            overlay.innerHTML = '<strong>HEXAGONAL GRAPHENE HOST + RECTANGULAR MoS₂ GUEST</strong><span>Different cell shapes and lengths · cells only by default</span>';
            document.body.appendChild(overlay);
            window.__setReadmeHostGuestStage = (title, detail, color = '#161a1d') => {
                overlay.querySelector('strong').textContent = title;
                overlay.querySelector('span').textContent = detail;
                overlay.style.borderLeftColor = color;
            };
        }""")
        center = np.mean(host.positions, axis=0)
        set_camera(
            page,
            target=center.tolist(),
            position=(center + np.array([0.0, 0.0, 26.0])).tolist(),
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        set_view_toggles(page, grid=False, axes=False, cell=True)
        page.locator("#chk-commensurate-guide").set_checked(True)
        page.wait_for_function("window.__V_ASE_APP__.state.commensurateCandidates?.length > 0")
        page.locator("#commensurate-guest-file").set_input_files(
            str(fixture / "mos2_guest.extxyz")
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.display.commensurateMode === 'host-guest'"
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.commensurateProposal?.data?.preview?.mode === 'host-guest'"
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.state.commensurateProposal?.data?.preview?.include_atoms === false"
        )
        preview_bounds = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const bounds = app.renderer.commensuratePreviewBounds(
                app.state.commensurateProposal.data.preview
            );
            const minimum = bounds.min.toArray();
            const maximum = bounds.max.toArray();
            return {
                center: minimum.map((value, index) => 0.5 * (value + maximum[index])),
                size: minimum.map((value, index) => maximum[index] - value)
            };
        }""")
        preview_center = preview_bounds["center"]
        camera_distance = max(24.0, max(preview_bounds["size"][:2]) * 2.4)
        set_camera(
            page,
            target=preview_center,
            position=[preview_center[0], preview_center[1], preview_center[2] + camera_distance],
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const bounds = app.renderer.commensuratePreviewBounds(
                app.state.commensurateProposal.data.preview
            );
            app.renderer.fitCameraToStructure(bounds);
            app.renderer.renderNow();
        }""")
        page.wait_for_function("""() => {
            const traces = Array.from(document.getElementById('commensurate-plot').data || []);
            return traces.some(trace => trace.meta?.role === 'angle-area-floor')
                && traces.some(trace => trace.meta?.role === 'candidate-floor-projection')
                && traces.some(trace => trace.meta?.role === 'commensurate-candidates')
                && traces.some(trace => trace.meta?.role === 'current-angle-plane');
        }""")
        page.evaluate("""() => {
            const drawer = document.getElementById('analysis-drawer');
            drawer.style.height = '520px';
            window.Plotly?.Plots?.resize?.(document.getElementById('commensurate-plot'));
            window.__V_ASE_APP__.closeAnalysisDrawer();
        }""")
        common_center = page.evaluate("""() => {
            const cell = window.__V_ASE_APP__.state.commensurateProposal
                ?.data?.preview?.common_cell;
            if (!Array.isArray(cell) || cell.length !== 3) return null;
            return [0, 1, 2].map(axis => 0.5 * (
                Number(cell[0][axis] || 0)
                + Number(cell[1][axis] || 0)
                + Number(cell[2][axis] || 0)
            ));
        }""")
        if common_center is None:
            raise AssertionError("Host/guest capture is missing the bounded common-cell geometry.")
        graph_target = preview_center
        set_camera(
            page,
            target=graph_target,
            position=[graph_target[0], graph_target[1], graph_target[2] + camera_distance],
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        set_atomic_scale(page, 32.0)
        graph_state = page.evaluate("""() => {
            const plot = document.getElementById('commensurate-plot');
            return {
                xTitle: plot.layout.scene?.xaxis?.title?.text,
                perspective: plot.layout.scene?.camera?.projection?.type,
                xAspect: Number(plot.layout.scene?.aspectratio?.x || 0),
                zAspect: Number(plot.layout.scene?.aspectratio?.z || 0),
                roles: Array.from(plot.data || []).map(trace => trace.meta?.role || ''),
                previewBonds: Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewBonds || 0)
            };
        }""")
        if graph_state["xTitle"] != "rotation θ / °":
            raise AssertionError("README commensurate graph does not expose rotation as its x axis.")
        if graph_state["perspective"] != "perspective" or graph_state["xAspect"] <= graph_state["zAspect"]:
            raise AssertionError("README commensurate graph is not presented as a legible 3D landscape.")
        if "current-angle-outline" not in graph_state["roles"] or graph_state["previewBonds"] != 0:
            raise AssertionError(
                "README host/guest example must begin as a cells-only parent-lattice view."
            )
        initial_lattices = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const preview = app.state.commensurateProposal.data.preview;
            const children = app.renderer.commensurateSupercellGroup.children;
            return {
                hostShape: preview.host_grid_shape,
                guestShape: preview.guest_grid_shape,
                hostOrigins: preview.host_grid_lattice_origins,
                guestAnchor: preview.guest_offset,
                guestGridCenter: [0, 1, 2].map(axis => (
                    preview.guest_grid_lattice_origins.reduce(
                        (sum, origin) => sum + Number(origin[axis]), 0
                    ) / preview.guest_grid_lattice_origins.length
                    + 0.5 * (
                        Number(preview.guest_primitive_vectors[0][axis])
                        + Number(preview.guest_primitive_vectors[1][axis])
                    )
                )),
                guestGridRadii: preview.guest_grid_lattice_origins.map(origin => Math.hypot(
                    ...origin.map((value, axis) => Number(value) - Number(preview.guest_offset[axis]))
                )).sort((left, right) => left - right),
                commonCenter: [0, 1, 2].map(axis => 0.5 * (
                    Number(preview.common_cell?.[0]?.[axis] || 0)
                    + Number(preview.common_cell?.[1]?.[axis] || 0)
                    + Number(preview.common_cell?.[2]?.[axis] || 0)
                )),
                guestGridCount: preview.guest_grid_lattice_origins?.length,
                hostLengths: preview.host_primitive_vectors.map(vector => Math.hypot(...vector)),
                guestLengths: preview.guest_primitive_vectors.map(vector => Math.hypot(...vector)),
                parentFixed: preview.parent_lattices_fixed,
                commonCells: children.filter(child => child.userData?.commensurateSuggestedCell).length,
                hostLabels: children.filter(child => child.userData?.commensurateHostCellLabel).length,
                guestLabels: children.filter(child => child.userData?.commensurateGuestCellLabel).length,
                baseSelectionVisible: app.renderer.selectionOutlines.visible
            };
        }""")
        if initial_lattices["commonCells"] != 0 or not initial_lattices["parentFixed"]:
            raise AssertionError("Host/guest mode exposed a result cell before the mobile lattice matched.")
        np.testing.assert_allclose(
            np.asarray(initial_lattices["guestAnchor"], dtype=float)[:2],
            [0.0, 0.0],
            atol=0.0,
        )
        np.testing.assert_allclose(
            np.asarray(initial_lattices["commonCenter"], dtype=float)[:2],
            np.asarray(common_center, dtype=float)[:2],
            atol=1e-8,
        )
        if initial_lattices["baseSelectionVisible"]:
            raise AssertionError("Host/guest cells-only mode leaked base selection outlines.")
        if np.allclose(
            initial_lattices["hostLengths"][:2],
            initial_lattices["guestLengths"][:2],
            atol=0.05,
        ):
            raise AssertionError("Host/guest README fixture does not show visibly different lattices.")
        np.testing.assert_allclose(initial_lattices["hostLengths"][:2], [2.46, 2.46], atol=0.03)
        np.testing.assert_allclose(initial_lattices["guestLengths"][:2], [3.18, 5.5079], atol=0.03)
        if initial_lattices["hostLabels"] or initial_lattices["guestLabels"]:
            raise AssertionError("Fixed host/guest parent lattices should remain label-free in the viewport.")
        graph_frames: list[Image.Image] = []
        page.evaluate("""() => window.__setReadmeHostGuestStage(
            '1 · DISTINCT PARENT LATTICES',
            'Black hexagonal host: 2.46 Å · orange rectangular guest: 3.18 × 5.51 Å · shared origin',
            '#161a1d'
        )""")
        append_hold(graph_frames, page, 14)
        page.locator('details.commensurate-advanced').evaluate(
            "element => { element.open = true; }"
        )
        page.locator("#chk-commensurate-show-atoms").set_checked(True)
        page.wait_for_function(
            "Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms) > 0"
        )
        independent_atoms = page.evaluate("""() => ({
            atoms: Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms),
            bonds: Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewBonds),
            common: window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                .filter(child => child.userData?.commensurateSuggestedCell).length
        })""")
        if independent_atoms["atoms"] <= 0 or independent_atoms["bonds"] <= 0:
            raise AssertionError("Host/guest atom visibility did not include both bonded lattices.")
        if independent_atoms["common"] != 0:
            raise AssertionError("Host/guest atom visibility exposed an unresolved common cell.")
        page.evaluate("""() => window.__setReadmeHostGuestStage(
            '2 · OPTIONAL ATOMS + BONDS',
            'Atoms can be shown at any angle; this does not create or hide a common cell',
            '#087f70'
        )""")
        append_hold(graph_frames, page, 14)
        page.locator("#chk-commensurate-show-atoms").set_checked(False)
        page.wait_for_function(
            "Number(window.__V_ASE_APP__.renderer.domElement.dataset.commensuratePreviewAtoms) === 0"
        )
        page.evaluate("""() => window.__setReadmeHostGuestStage(
            '3 · ROTATE MoS₂, KEEP BOTH GRIDS FIXED',
            'Only the guest orientation changes; neither parent lattice resizes or drifts',
            '#f58220'
        )""")
        append_hold(graph_frames, page, 7)
        host_guest_initial_angle = 8.0
        animation_angles = [
            host_guest_initial_angle
            + (host_guest_target_angle - host_guest_initial_angle)
            * (0.5 - 0.5 * math.cos(math.pi * index / 21))
            for index in range(22)
        ]
        for frame_index, angle in enumerate(animation_angles):
            page.evaluate(
                """angle => {
                    const input = document.getElementById('commensurate-guest-angle');
                    input.value = Number(angle).toFixed(8);
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                }""",
                angle,
            )
            page.wait_for_function(
                """angle => Math.abs(
                    Number(window.__V_ASE_APP__.state.commensurateProposal?.data?.preview?.display_angle_deg)
                    - Number(angle)
                ) < 1e-5""",
                arg=angle,
                timeout=30_000,
            )
            invariant = page.evaluate("""() => {
                const app = window.__V_ASE_APP__;
                const preview = app.state.commensurateProposal.data.preview;
                return {
                    hostShape: preview.host_grid_shape,
                    guestShape: preview.guest_grid_shape,
                    hostOrigins: preview.host_grid_lattice_origins,
                    guestAnchor: preview.guest_offset,
                    guestGridCenter: [0, 1, 2].map(axis => (
                        preview.guest_grid_lattice_origins.reduce(
                            (sum, origin) => sum + Number(origin[axis]), 0
                        ) / preview.guest_grid_lattice_origins.length
                        + 0.5 * (
                            Number(preview.guest_primitive_vectors[0][axis])
                            + Number(preview.guest_primitive_vectors[1][axis])
                        )
                    )),
                    guestGridRadii: preview.guest_grid_lattice_origins.map(origin => Math.hypot(
                        ...origin.map((value, axis) => Number(value) - Number(preview.guest_offset[axis]))
                    )).sort((left, right) => left - right),
                    guestGridCount: preview.guest_grid_lattice_origins?.length,
                    hostLengths: preview.host_primitive_vectors.map(vector => Math.hypot(...vector)),
                    guestLengths: preview.guest_primitive_vectors.map(vector => Math.hypot(...vector)),
                    hostLabels: app.renderer.commensurateSupercellGroup.children.filter(
                        child => child.userData?.commensurateHostCellLabel
                    ).length,
                    guestLabels: app.renderer.commensurateSupercellGroup.children.filter(
                        child => child.userData?.commensurateGuestCellLabel
                    ).length,
                    parentFixed: preview.parent_lattices_fixed,
                    baseSelectionVisible: app.renderer.selectionOutlines.visible
                };
            }""")
            if {
                key: value for key, value in invariant.items()
                if key not in {
                    "guestGridCenter",
                    "guestGridRadii",
                    "hostLengths",
                    "guestLengths",
                }
            } != {
                "hostShape": initial_lattices["hostShape"],
                "guestShape": initial_lattices["guestShape"],
                "hostOrigins": initial_lattices["hostOrigins"],
                "guestAnchor": initial_lattices["guestAnchor"],
                "guestGridCount": initial_lattices["guestGridCount"],
                "hostLabels": 0,
                "guestLabels": 0,
                "parentFixed": True,
                "baseSelectionVisible": False,
            }:
                raise AssertionError("Host/guest parent superlattices changed size with the candidate cell.")
            np.testing.assert_allclose(
                invariant["hostLengths"],
                initial_lattices["hostLengths"],
                atol=1e-8,
            )
            np.testing.assert_allclose(
                invariant["guestLengths"],
                initial_lattices["guestLengths"],
                atol=1e-8,
            )
            np.testing.assert_allclose(
                invariant["guestGridCenter"],
                initial_lattices["guestAnchor"],
                atol=1e-8,
            )
            np.testing.assert_allclose(
                invariant["guestGridRadii"],
                initial_lattices["guestGridRadii"],
                atol=1e-7,
            )
            if frame_index == 0:
                unresolved = page.evaluate("""() => ({
                    resolved: window.__V_ASE_APP__.state.commensurateProposal?.data?.match_resolved,
                    commonCells: window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                        .filter(child => child.userData?.commensurateSuggestedCell).length
                })""")
                if unresolved["resolved"] or unresolved["commonCells"]:
                    raise AssertionError("README commensurate animation emphasizes a common cell before matching.")
            page.evaluate("""async () => {
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            }""")
            page.wait_for_timeout(70)
            graph_frames.append(screenshot_frame(page))
        resolved = page.evaluate("""() => ({
            resolved: window.__V_ASE_APP__.state.commensurateProposal?.data?.match_resolved,
            angle: window.__V_ASE_APP__.state.commensurateProposal?.context?.displayAngleDeg,
            target: window.__V_ASE_APP__.state.commensurateProposal?.context?.candidate?.targetAngleDeg,
            delta: window.__V_ASE_APP__.state.commensurateProposal?.context?.candidate?.deltaDeg,
            mode: window.__V_ASE_APP__.state.display.commensurateMode,
            commonCells: window.__V_ASE_APP__.renderer.commensurateSupercellGroup.children
                .filter(child => child.userData?.commensurateSuggestedCell).length
        })""")
        if not resolved["resolved"] or resolved["commonCells"] != 1:
            raise AssertionError(
                f"README commensurate animation did not resolve its final common cell: {resolved!r}"
            )
        page.evaluate("""() => window.__setReadmeHostGuestStage(
            '4 · BOUNDED COMMON CELL FOUND',
            'The teal cell appears only when the current angle satisfies the strain limit',
            '#139c68'
        )""")
        cells_only_host_guest = graph_frames[0].copy()
        if page.locator("#chk-commensurate-show-atoms").is_checked():
            raise AssertionError("Candidate discovery changed the user-controlled atom visibility.")
        append_hold(graph_frames, page, 16)
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            app.showAnalysisDrawer('commensurate', 'Commensurate Angle–Area–Strain Landscape');
            const drawer = document.getElementById('analysis-drawer');
            drawer.style.height = '520px';
            window.Plotly?.Plots?.resize?.(document.getElementById('commensurate-plot'));
            window.__setReadmeHostGuestStage(
                '5 · EXPLORE ALL BOUNDED MATCHES',
                'Interactive 3D landscape: rotation angle × host area × strain',
                '#087f70'
            );
        }""")
        page.wait_for_timeout(240)
        append_hold(graph_frames, page, 28)
        save_gif(
            graph_frames,
            ASSET_DIR / "readme_commensurate_host_guest.gif",
            duration=125,
        )
        cells_only_host_guest.save(
            ASSET_DIR / "readme_commensurate_host_guest.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_registry_media(browser) -> None:
    atoms, indices = make_graphene_hbn_commensurate_scene()
    editor, page = open_scene(browser, atoms, show_bonds=True, viz_only=False)
    try:
        command_url = external_ai_command_url(editor)
        set_display(page, {
            "atomRadiusScale": 0.48,
            "showBonds": True,
            "bondThickness": 0.16,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "supercell": [4, 4, 1],
            "labelColors": {"C": "#3f4b50", "B": "#d69a4b", "N": "#3c70c5"},
        })
        configure_inspector(page, "analysis", ["registry-map"], width=455)
        page.add_style_tag(content="""
            #measurement-overlay,
            #selection-measure-readout,
            #hover-readout,
            #coord-readout { display: none !important; }
        """)
        set_selection(page, indices["hbn"])
        cell = np.asarray(atoms.cell.array, dtype=float)
        result = run_external_ai_apply(command_url, {
            "operation": {
                "name": "calculate-registry-map",
                "indices": indices["hbn"],
                "hkl": [0, 0, 1],
                "metric": "bond-strain",
                "gridX": 40,
                "gridY": 40,
                "pairCutoffs": {
                    "B|C": {"enabled": True, "max": 4.2},
                    "C|N": {"enabled": True, "max": 4.2},
                },
            },
        })
        registry = result["analysis"]["registryMap"]
        if registry["grid"] != [40, 40] or registry["selectedIndices"] != indices["hbn"]:
            raise AssertionError("README registry map did not retain its selected layer or grid.")
        if registry["metric"] != "bond-strain":
            raise AssertionError("README registry map did not retain its physical bond-strain metric.")
        page.wait_for_selector("#registry-plot .plotly", state="attached")
        page.evaluate("""() => {
            const drawer = document.getElementById('analysis-drawer');
            drawer.style.height = '430px';
            window.Plotly?.Plots?.resize?.(document.getElementById('registry-plot'));
            window.__V_ASE_APP__.renderer.fitCameraToStructure();
            window.__V_ASE_APP__.renderer.renderNow();
        }""")
        target = (
            np.mean(atoms.positions, axis=0)
            + 1.5 * (cell[0] + cell[1])
            + np.asarray([2.4, -2.15, 0.0])
        )
        set_camera(
            page,
            target=target.tolist(),
            position=(target + np.array([0.0, 0.0, 34.0])).tolist(),
            up=(0.0, 1.0, 0.0),
            fov=32,
        )
        set_atomic_scale(page, 46.0)
        page.wait_for_timeout(300)
        plot_state = page.evaluate("""() => {
            const plot = document.getElementById('registry-plot');
            const titleText = title => typeof title === 'string' ? title : title?.text;
            return {
                traceCount: plot.data?.length || 0,
                roles: Array.from(plot.data || []).map(trace => trace.meta?.role || ''),
                xTitle: titleText(plot.layout?.xaxis?.title),
                yTitle: titleText(plot.layout?.yaxis?.title),
                xRange: plot.layout?.xaxis?.range,
                yRange: plot.layout?.yaxis?.range,
                xConstraint: plot.layout?.xaxis?.constrain,
                yConstraint: plot.layout?.yaxis?.constrain,
                valueSpan: (() => {
                    const score = Array.from(plot.data || []).find(
                        trace => trace.meta?.role === 'registry-score'
                    );
                    const values = Array.from(score?.marker?.color || [])
                        .map(Number).filter(Number.isFinite);
                    return values.length ? Math.max(...values) - Math.min(...values) : 0;
                })(),
                optimum: window.__V_ASE_APP__.state.registryResult?.optimum_fractional,
                active: window.__V_ASE_APP__.state.activeAnalysisPlot
            };
        }""")
        expected_roles = {
            "registry-score",
            "host-reference-cell",
            "host-reference-basis",
            "registry-optimum",
            "registry-current",
            "registry-current-vector",
        }
        if plot_state["traceCount"] != 6 or set(plot_state["roles"]) != expected_roles:
            raise AssertionError("README registry heatmap is missing its host cell, basis, or map markers.")
        if plot_state["active"] != "registry":
            raise AssertionError("README registry heatmap is not the active analysis plot.")
        if plot_state["xTitle"] != "plane x / Å" or plot_state["yTitle"] != "plane y / Å":
            raise AssertionError("README registry map is missing its physical plane axes.")
        if not (
            plot_state["xRange"][1] > plot_state["xRange"][0]
            and plot_state["yRange"][1] > plot_state["yRange"][0]
        ):
            raise AssertionError("README registry map has a degenerate physical plane boundary.")
        if plot_state["xConstraint"] != "domain" or plot_state["yConstraint"] != "domain":
            raise AssertionError("README registry map does not preserve a readable square domain.")
        if len(plot_state["optimum"] or []) != 2:
            raise AssertionError("README registry map does not expose a suggested minimum.")
        if plot_state["valueSpan"] < 0.02:
            raise AssertionError("README registry heatmap lacks a visibly meaningful value range.")
        screenshot_frame(page).save(
            ASSET_DIR / "readme_registry_map.png",
            optimize=True,
        )

        baseline_positions = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        page.evaluate("""() => {
            window.__V_ASE_APP__.invalidateRegistryResult(
                'Map hidden while rigid translation trials are optimized.'
            );
        }""")
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "start-registry-relaxation",
                "indices": indices["hbn"],
                "hkl": [0, 0, 1],
            },
        })
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "set-registry-translation",
                "coordinates": [0.16, 0.10],
            },
        })
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "run-registry-relaxation",
                "fmax": 0.002,
                "steps": 80,
                "calculator": {
                    "cutoffScale": 2.15,
                    "kRepulsion": 2.4,
                },
            },
        })
        page.wait_for_function("""() => {
            const app = window.__V_ASE_APP__;
            return app.state.registryRelaxation
                && app.state.registryRelaxation.is_relaxing === false
                && app.state.relaxTrajectory?.kind === 'registry'
                && app.state.relaxTrajectory.frames.length >= 2;
        }""", timeout=20_000)
        relaxation = page.evaluate("""() => ({
            frames: window.__V_ASE_APP__.state.relaxTrajectory.frames,
            hkl: window.__V_ASE_APP__.state.registryRelaxation.hkl,
            basis: window.__V_ASE_APP__.state.registryRelaxation.translation_basis_angstrom,
            selected: window.__V_ASE_APP__.state.registryRelaxation.selected_indices
        })""")
        if relaxation["hkl"] != [0, 0, 1]:
            raise AssertionError("README rigid translation did not retain its requested plane.")
        registry_frames = [np.asarray(frame, dtype=float) for frame in relaxation["frames"]]
        selected = np.asarray(relaxation["selected"], dtype=int)
        host = np.asarray([index for index in range(len(atoms)) if index not in set(selected)], dtype=int)
        for frame in registry_frames:
            np.testing.assert_allclose(frame[host], baseline_positions[host], atol=0.0)
            np.testing.assert_allclose(
                frame[selected] - frame[selected[0]],
                baseline_positions[selected] - baseline_positions[selected[0]],
                atol=2e-8,
            )
            np.testing.assert_allclose(frame[selected, 2], baseline_positions[selected, 2], atol=2e-8)

        endpoint_shift = float(np.linalg.norm(
            np.mean(registry_frames[-1][selected] - registry_frames[0][selected], axis=0)
        ))
        if endpoint_shift < 0.03:
            raise AssertionError(
                "README rigid registry relaxation did not produce a visible translation."
            )

        def minimum_projected_host_guest_distance(positions: np.ndarray) -> float:
            trial = atoms.copy()
            trial.positions = positions
            distances = []
            for host_index in host:
                vectors = trial.get_distances(host_index, selected, mic=True, vector=True)
                distances.extend(np.linalg.norm(vectors[:, :2], axis=1).tolist())
            return float(min(distances))

        initial_clearance = minimum_projected_host_guest_distance(registry_frames[0])
        final_clearance = minimum_projected_host_guest_distance(registry_frames[-1])
        if final_clearance < 0.70 or final_clearance < initial_clearance + 0.20:
            raise AssertionError(
                "README registry relaxation did not resolve the visible host/guest overlap: "
                f"{initial_clearance:.4f} Å -> {final_clearance:.4f} Å."
            )

        gif_frames: list[Image.Image] = []
        translation_basis = np.asarray(relaxation["basis"], dtype=float)
        visual_frames = registry_frames
        if len(registry_frames) < 10:
            visual_frames = []
            segment_steps = max(3, math.ceil(10 / max(1, len(registry_frames) - 1)))
            for first, second in zip(registry_frames[:-1], registry_frames[1:]):
                for alpha in np.linspace(0.0, 1.0, segment_steps, endpoint=False):
                    visual_frames.append((1.0 - alpha) * first + alpha * second)
            visual_frames.append(registry_frames[-1])
        for frame_index, positions in enumerate(visual_frames):
            translation = np.mean(
                positions[selected] - baseline_positions[selected],
                axis=0,
            )
            coordinates = np.linalg.lstsq(
                translation_basis.T,
                translation,
                rcond=None,
            )[0]
            page.evaluate(
                """({positions, index, frameCount, coordinates}) => {
                    const app = window.__V_ASE_APP__;
                    app.state.atoms.positions = positions.map(position => [...position]);
                    app.renderer.updatePositions(app.state.atoms.positions);
                    app.updateRegistryMapMarker(coordinates);
                    app.setRegistryRelaxStatus(
                        'ready',
                        'Rigid translation trials',
                        `q₁ ${Number(coordinates[0] || 0).toFixed(4)} · `
                        + `q₂ ${Number(coordinates[1] || 0).toFixed(4)}`
                    );
                    if (app.state.relaxTrajectory?.active) {
                        const sourceCount = app.state.relaxTrajectory.frames.length;
                        app.state.relaxTrajectory.frame = Math.min(
                            sourceCount - 1,
                            Math.round(index * Math.max(1, sourceCount - 1) / Math.max(1, frameCount - 1))
                        );
                    }
                    app.updateTrajectoryUI();
                }""",
                {
                    "positions": positions.tolist(),
                    "index": frame_index,
                    "frameCount": len(visual_frames),
                    "coordinates": coordinates.tolist(),
                },
            )
            page.wait_for_timeout(60)
            gif_frames.append(screenshot_frame(page))
        append_hold(gif_frames, page, 5)
        run_external_ai_apply(command_url, {
            "operation": {"name": "finish-registry-relaxation"},
        })
        page.wait_for_function("""() =>
            window.__V_ASE_APP__.state.registryRelaxation === null
            && window.__V_ASE_APP__.state.relaxTrajectory.active === false
            && document.getElementById('trajectory-panel').classList.contains('hidden')
        """)
        append_hold(gif_frames, page, 7)
        save_gif(
            gif_frames,
            ASSET_DIR / "readme_registry_relax.gif",
            duration=115,
        )
    finally:
        page.close()
        editor.close()


def capture_bond_media(browser) -> None:
    atoms, groups = make_copper_oxide_bond_scene()
    atom_radius_scale = 0.42
    substrate_anchor = groups["substrate_copper"][0]
    substrate_neighbors = [
        index for index in groups["substrate_copper"]
        if index != substrate_anchor
    ]
    substrate_nearest_neighbor = float(np.min(
        atoms.get_distances(substrate_anchor, substrate_neighbors, mic=True)
    ))
    substrate_touching_source_radius = (
        0.5 * substrate_nearest_neighbor / atom_radius_scale
    )
    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": atom_radius_scale,
            "labelRadii": {
                "Cu_substrate": substrate_touching_source_radius,
                "Cu_oxide": 1.12,
                "O_oxide": 0.72,
            },
            "bondMode": "pairwise",
            "showBonds": True,
            "pairwiseBondRanges": {
                "Cu_oxide-Cu_oxide": {"enabled": False, "max": 2.75},
                "Cu_oxide-Cu_substrate": {"enabled": False, "max": 2.75},
                "Cu_oxide-O_oxide": {"enabled": True, "max": 2.08},
                "Cu_substrate-Cu_substrate": {"enabled": False, "max": 2.75},
                "Cu_substrate-O_oxide": {"enabled": True, "max": 2.08},
                "O_oxide-O_oxide": {"enabled": False, "max": 3.00},
            },
            "pairwiseBondCutoffs": {
                "Cu_oxide-Cu_oxide": 0.0,
                "Cu_oxide-Cu_substrate": 0.0,
                "Cu_oxide-O_oxide": 2.08,
                "Cu_substrate-Cu_substrate": 0.0,
                "Cu_substrate-O_oxide": 2.08,
                "O_oxide-O_oxide": 0.0,
            },
            "bondThickness": 0.30,
            "bondColorMode": "split",
            "showGrid": False,
            "showAxes": False,
            "showCell": True,
            "viewportBackground": "white",
            "labelColors": {
                "Cu_substrate": "#744637",
                "Cu_oxide": "#efb34f",
                "O_oxide": "#df2935",
            },
            "labelMaterials": {
                "Cu_substrate": "metal",
                "Cu_oxide": "standard",
                "O_oxide": "rubber",
            },
        })
        configure_inspector(page, "structure", ["bonding"], width=560)
        center = np.mean(atoms.positions, axis=0)
        center[:2] = 0.5 * (atoms.cell[0, :2] + atoms.cell[1, :2])
        camera_target = center + np.array([4.8, 0.0, 0.0])
        settle_view(
            page,
            target=camera_target.tolist(),
            position=(camera_target + np.array([0.0, 0.0, 32.0])).tolist(),
            fov=34,
        )
        set_camera(
            page,
            target=camera_target.tolist(),
            position=(camera_target + np.array([0.0, 0.0, 32.0])).tolist(),
            up=(0, 1, 0),
            fov=34,
        )
        set_atomic_scale(page, 42.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=3.0,
            position_offset=(-10.0, -13.0, 17.0),
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.renderer.bondPairs.length > 0"
        )
        pair_state = page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            const labels = app.state.atoms.symbols;
            return app.renderer.bondPairs.map(([i, j]) =>
                [labels[i], labels[j]].sort().join('-')
            );
        }""")
        expected_visible_pairs = {
            "Cu_oxide-O_oxide",
            "Cu_substrate-O_oxide",
        }
        if not pair_state or set(pair_state) != expected_visible_pairs:
            raise AssertionError(
                "README bonding scene must display only oxide and interface Cu-O pairs."
            )
        control_state = page.evaluate("""() => Object.fromEntries(
            [...document.querySelectorAll('.pairwise-bond-row')].map(row => [
                row.dataset.pairKey,
                {
                    enabled: row.querySelector('.pairwise-bond-enabled').checked,
                    max: Number(row.querySelector('.pairwise-bond-max').value)
                }
            ])
        )""")
        expected_controls = {
            "Cu_oxide-Cu_oxide": {"enabled": False, "max": 2.75},
            "Cu_oxide-Cu_substrate": {"enabled": False, "max": 2.75},
            "Cu_oxide-O_oxide": {"enabled": True, "max": 2.08},
            "Cu_substrate-Cu_substrate": {"enabled": False, "max": 2.75},
            "Cu_substrate-O_oxide": {"enabled": True, "max": 2.08},
            "O_oxide-O_oxide": {"enabled": False, "max": 3.0},
        }
        if control_state != expected_controls:
            raise AssertionError(
                f"README bonding controls differ from the documented settings: {control_state}"
            )
        if len(groups["oxide_oxygen"]) < 30:
            raise AssertionError("README bonding scene requires a resolved Cu2O film.")
        rendered_substrate_radius = page.evaluate(
            "index => window.__V_ASE_APP__.renderer.atomVisualRadius(index)",
            substrate_anchor,
        )
        if not math.isclose(
            2.0 * rendered_substrate_radius,
            substrate_nearest_neighbor,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            raise AssertionError(
                "README Cu(111) substrate must use touching-sphere radii."
            )
        page.evaluate("""() => {
            const selector = document.getElementById('structure-section-select');
            if (selector) selector.value = 'bonding';
            window.__V_ASE_APP__.renderer.renderNow();
        }""")
        page.screenshot(path=ASSET_DIR / "readme_bonds.png")
    finally:
        page.close()
        editor.close()


def capture_material_media(browser) -> None:
    atoms, _ = make_material_preset_scene()
    editor, page = open_scene(browser, atoms, show_bonds=False)
    try:
        set_display(page, {
            "atomRadiusScale": 0.62,
            "showBonds": False,
            "showCell": False,
            "showAxes": False,
            "showGrid": True,
            "viewportBackground": "white",
            "labelMaterials": {
                "Cu_standard": "standard",
                "Cu_metal": "metal",
                "Cu_rubber": "rubber",
            },
        })
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            app.state.labelOrder = ['Cu_standard', 'Cu_metal', 'Cu_rubber'];
            app.renderAppearanceRows();
        }""")
        configure_inspector(page, "structure", ["appearance"], width=560)
        scene_center = np.mean(atoms.positions, axis=0)
        target = scene_center + np.array([3.8, 0.0, 0.0])
        settle_view(
            page,
            target=target.tolist(),
            position=(target + np.array([0.0, -24.0, 10.0])).tolist(),
            fov=34,
        )
        set_atomic_scale(page, 41.0)
        set_readme_lighting(
            page,
            scene_center.tolist(),
            intensity=3.15,
            position_offset=(-11.0, -14.0, 18.0),
        )
        page.screenshot(path=ASSET_DIR / "readme_materials.png")
    finally:
        page.close()
        editor.close()


def capture_ai_edit_media(browser) -> None:
    source, expected_final, metadata = make_ai_pyridinic_graphene_scene()
    editor, page = open_scene(browser, source, show_bonds=True)
    try:
        page.wait_for_function("window.v_aseAI")
        command_url = external_ai_command_url(editor)
        set_display(page, {
            "atomRadiusScale": 0.58,
            "bondThickness": 0.18,
            "showBonds": True,
            "showCell": True,
            "showAxes": False,
            "showGrid": False,
            "viewportBackground": "white",
            "labelColors": {
                "C": "#686d73",
                "N_pyridinic": "#3157d5",
                "Li_site": "#8f4fd6",
            },
            "labelMaterials": {
                "C": "standard",
                "N_pyridinic": "metal",
                "Li_site": "metal",
            },
        })
        collapse_inspector(page)
        target = np.mean(source.positions, axis=0)
        set_camera(
            page,
            target=target.tolist(),
            position=(target + np.array([9.0, -12.0, 23.0])).tolist(),
            up=(0, 0, 1),
            fov=34,
        )
        set_atomic_scale(page, 70.0)
        set_readme_lighting(
            page,
            target.tolist(),
            intensity=3.05,
            position_offset=(-10.0, -12.0, 18.0),
        )

        frames: list[Image.Image] = []

        def hold(count: int) -> None:
            page.wait_for_timeout(50)
            frame = screenshot_frame(page)
            frames.extend(frame.copy() for _ in range(count))

        hold(6)
        run_external_ai_apply(command_url, {
            "mode": "edit",
            "selection": {
                "clear": True,
                "indices": [metadata["vacancy_index"]],
            },
        })
        hold(5)
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "delete-selection",
                "indices": [metadata["vacancy_index"]],
            },
        })
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.positions.length === 71"
        )
        hold(7)
        run_external_ai_apply(command_url, {
            "selection": {
                "clear": True,
                "indices": metadata["neighbors_after"],
            },
        })
        hold(5)
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "set-identity",
                "indices": metadata["neighbors_after"],
                "label": "N_pyridinic",
                "element": "N",
            },
        })
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.symbols.filter(label => label === 'N_pyridinic').length === 3"
        )
        set_display(page, {
            "labelColors": {
                "C": "#686d73",
                "N_pyridinic": "#3157d5",
                "Li_site": "#8f4fd6",
            },
            "labelMaterials": {
                "C": "standard",
                "N_pyridinic": "metal",
                "Li_site": "metal",
            },
        })
        hold(7)
        run_external_ai_apply(command_url, {
            "operation": {
                "name": "add-atom",
                "label": "Li_site",
                "element": "Li",
                "position": metadata["li_position"],
            },
        })
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.positions.length === 72"
        )
        set_display(page, {
            "labelColors": {
                "C": "#686d73",
                "N_pyridinic": "#3157d5",
                "Li_site": "#8f4fd6",
            },
            "labelMaterials": {
                "C": "standard",
                "N_pyridinic": "metal",
                "Li_site": "metal",
            },
        })
        run_external_ai_apply(command_url, {
            "selection": {
                "clear": True,
                "indices": [*metadata["neighbors_after"], metadata["li_index"]],
            },
        })
        hold(10)
        run_external_ai_apply(command_url, {
            "selection": {"clear": True, "indices": []},
        })
        hold(8)

        final_state = run_external_ai_command(
            command_url,
            "describe",
            {"includePositions": True},
        )
        if not np.allclose(final_state["positions"], expected_final.positions):
            raise AssertionError("AI README edit did not reproduce the generated final coordinates.")
        if final_state["chemicalSymbols"] != expected_final.get_chemical_symbols():
            raise AssertionError("AI README edit did not reproduce the generated final elements.")

        save_gif(frames, ASSET_DIR / "readme_ai_edit.gif", duration=110)
        frames[-1].save(ASSET_DIR / "readme_ai_edit.png", optimize=True)
    finally:
        page.close()
        editor.close()


def capture_ai_collaboration_figure(browser) -> None:
    """Create a figure from a real agent edit followed by a real GUI edit."""
    source, expected_final, metadata = make_ai_pyridinic_graphene_scene()
    editor = view(
        source,
        block=False,
        viz_only=False,
        show_cell=True,
        show_axes=False,
        show_bonds=True,
        respect_constraints=True,
        allow_relax=False,
        open_browser=False,
        close_on_disconnect=False,
    )
    page = browser.new_page(
        viewport={"width": MEDIA_SIZE[0], "height": MEDIA_SIZE[1]},
        device_scale_factor=1,
    )
    try:
        page.goto(editor.url)
        page.wait_for_function("window.v_aseAI")
        command_url = external_ai_command_url(editor, workspace=True)
        run_external_ai_command(command_url, "ready")
        initial = run_external_ai_command(
            command_url,
            "describe",
            {"includePositions": True},
        )
        child = next(
            frame for frame in page.frames
            if "workspace_child=1" in frame.url
        )
        collapse_inspector(child)
        child.add_style_tag(content="""
            #top-bar,
            #right-inspector,
            #inspector-handle,
            #orientation-gizmo,
            #orientation-widget,
            .inspector-edge-toggle,
            #trajectory-panel,
            #btn-create-atom-toggle,
            #measurement-overlay,
            #selection-measure-readout,
            #hover-readout,
            #coord-readout { display: none !important; }
        """)
        set_atomic_scale(child, 56.0)
        page.wait_for_timeout(180)

        stage_records: list[dict[str, object]] = []

        def viewport_screenshot() -> bytes:
            return child.locator("#app-viewport").screenshot(type="png")

        def record_stage(
            stage: str,
            operation: str,
            state: dict[str, object],
            flow: str,
        ) -> None:
            child.evaluate("window.__V_ASE_APP__.renderer.renderNow()")
            page.wait_for_timeout(250)
            screenshot = viewport_screenshot()
            stage_records.append({
                "stage": stage,
                "flow": flow,
                "operation": operation,
                "revision": int(state.get("collaboration", {}).get("revision", 0)),
                "image": "data:image/png;base64," + base64.b64encode(screenshot).decode("ascii"),
            })

        record_stage("human", "request received", initial, "request")
        record_stage(
            "agent",
            (
                "read current structure"
            ),
            initial,
            "command",
        )

        async_commands = [
            {
                "selection": {"clear": True, "indices": [metadata["vacancy_index"]]},
                "operation": {
                    "name": "delete-selection",
                    "indices": [metadata["vacancy_index"]],
                },
            },
            {
                "selection": {"clear": True, "indices": metadata["neighbors_after"]},
                "operation": {
                    "name": "set-identity",
                    "indices": metadata["neighbors_after"],
                    "label": "N_pyridinic",
                    "element": "N",
                },
            },
            {
                "operation": {
                    "name": "add-atom",
                    "label": "Li_site",
                    "element": "Li",
                    "position": metadata["li_position"],
                },
            },
            {
                "display": {
                    "atomRadiusScale": 0.58,
                    "bondThickness": 0.18,
                    "showBonds": True,
                    "showCell": True,
                    "showAxes": False,
                    "showGrid": False,
                    "viewportBackground": "white",
                    "cellColor": "#7d6a30",
                    "cellThickness": 0.055,
                    "lightingMode": "studio-shadow",
                    "sunIntensity": 3.05,
                    "labelColors": {
                        "C": "#686d73",
                        "N_pyridinic": "#3157d5",
                        "Li_site": "#8f4fd6",
                    },
                    "labelMaterials": {
                        "C": "standard",
                        "N_pyridinic": "metal",
                        "Li_site": "metal",
                    },
                },
                "quality": {
                    "antiAliasing": True,
                    "sphereQuality": "ultra",
                },
                "camera": {"axis": "+Z", "fit": "structure"},
                "selection": {
                    "clear": True,
                    "indices": [],
                },
            },
        ]
        operation_labels = (
            "delete vacancy-site C",
            "set its 3 neighbors to N",
            "add Li at the exact requested site",
            "set camera +Z · screen up +Y",
        )
        state = initial
        for command, operation_label in zip(async_commands, operation_labels):
            record_stage(
                "agent",
                operation_label,
                state,
                "command",
            )
            state = run_external_ai_apply(command_url, command)
            record_stage(
                "vase",
                operation_label,
                state,
                "live",
            )
        agent_revision = state["collaboration"]["revision"]

        # These are deliberately separate GUI-originated edits, not AI bridge calls.
        child.evaluate("""() => {
            const radius = document.getElementById('atom-radius-scale');
            radius.value = '0.64';
            radius.dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        child.wait_for_function(
            "revision => window.__ASE_APP__.collaborationRevision > revision",
            arg=agent_revision,
        )
        revision_after_radius = child.evaluate(
            "() => window.__ASE_APP__.collaborationRevision"
        )
        radius_state = run_external_ai_command(
            command_url,
            "describe",
            {"includePositions": False},
        )
        record_stage(
            "human",
            "You changed the atom radius",
            radius_state,
            "refine",
        )
        child.evaluate("""() => {
            const thickness = document.getElementById('bond-thickness');
            thickness.value = '0.20';
            thickness.dispatchEvent(new Event('change', {bubbles: true}));
        }""")
        child.wait_for_function(
            "revision => window.__ASE_APP__.collaborationRevision > revision",
            arg=revision_after_radius,
        )
        page.wait_for_timeout(420)
        human_state = run_external_ai_command(
            command_url,
            "describe",
            {"includePositions": False},
        )
        record_stage(
            "human",
            "You refined radius and bond width",
            human_state,
            "refine",
        )

        stream = page.evaluate(
            """async ({workspaceId, after}) => {
                const response = await fetch(
                    `/api/ai/workspace-events/${encodeURIComponent(workspaceId)}`
                    + `?after=${after}&timeout=0`
                );
                return await response.json();
            }""",
            {"workspaceId": editor.workspace_id, "after": agent_revision},
        )
        human_events = [
            event for event in stream["events"]
            if event.get("source") == "human"
        ]
        if len(human_events) < 2:
            raise AssertionError(
                "The collaboration demo did not emit two distinct human GUI events."
            )
        required_categories = {"display"}
        observed_categories = {
            category
            for event in human_events
            for category in event.get("categories", [])
        }
        if not required_categories.issubset(observed_categories):
            raise AssertionError(
                f"Expected human camera/display events, received {human_events!r}"
            )

        final_state = run_external_ai_command(
            command_url,
            "describe",
            {"includePositions": True},
        )
        if not np.allclose(final_state["positions"], expected_final.positions):
            raise AssertionError("Collaboration example changed the verified coordinates.")
        if final_state["chemicalSymbols"] != expected_final.get_chemical_symbols():
            raise AssertionError("Collaboration example changed the verified elements.")
        camera_position = np.asarray(final_state["camera"]["position"], dtype=float)
        camera_target = np.asarray(final_state["camera"]["target"], dtype=float)
        camera_direction = camera_position - camera_target
        camera_direction /= np.linalg.norm(camera_direction)
        if not np.allclose(camera_direction, [0.0, 0.0, 1.0], atol=1e-7):
            raise AssertionError("Collaboration result is not the requested +Z top view.")
        if not np.allclose(final_state["camera"]["up"], [0.0, 1.0, 0.0], atol=1e-7):
            raise AssertionError("Collaboration result does not keep +Y pointing upward.")
        record_stage(
            "agent",
            "read GUI refinements · verify shared state",
            final_state,
            "revision",
        )
        record_stage(
            "vase",
            (
                "requested structure ready · GUI refinements preserved"
            ),
            final_state,
            "complete",
        )
        record_stage(
            "agent",
            (
                "Revision received · radius 0.64 · bond width 0.20 Å · verified"
            ),
            final_state,
            "reply",
        )

        # Reuse one verified render for the final state transitions so the
        # animation communicates state flow without a lighting flicker.
        child.evaluate("window.__V_ASE_APP__.renderer.renderNow()")
        page.wait_for_timeout(300)
        stable_final = (
            "data:image/png;base64,"
            + base64.b64encode(viewport_screenshot()).decode("ascii")
        )
        for record in stage_records[-3:]:
            record["image"] = stable_final

        live_path = ASSET_DIR / "readme_ai_collaboration_live.png"
        live_image = Image.open(BytesIO(viewport_screenshot())).convert("RGB")
        live_image.save(live_path, optimize=True, compress_level=9)

        figure_page = browser.new_page(
            viewport={"width": 1800, "height": 1080},
            device_scale_factor=1,
        )
        try:
            figure_source = ROOT / "docs/design/ai_collaboration_figure.html"
            figure_html = figure_source.read_text(encoding="utf-8").replace(
                "<head>",
                f'<head><base href="{figure_source.parent.as_uri()}/">',
                1,
            )
            logo_data = (
                "data:image/png;base64,"
                + base64.b64encode(
                    (ASSET_DIR / "v_ase-logo.png").read_bytes()
                ).decode("ascii")
            )
            figure_html = figure_html.replace(
                "../assets/v_ase-logo.png",
                logo_data,
            )
            write_ai_collaboration_recording_html(
                figure_html,
                stage_records,
                ROOT / "docs/design/ai_collaboration_recording.html",
            )
            # set_content avoids Chromium retaining a previous file:// document
            # between targeted README capture runs.
            figure_page.set_content(figure_html, wait_until="load")
            # The verified viewport is injected as a data URL for every stage.
            # Do not block on the decorative placeholder's file:// URL: that
            # URL may be intentionally unavailable in a sandboxed Chromium.
            figure_page.wait_for_function(
                "() => typeof window.setCollaborationStage === 'function'"
            )
            base_frames: list[Image.Image] = []
            for record_index, record in enumerate(stage_records):
                figure_page.evaluate(
                    "record => window.setCollaborationStage(record)",
                    record,
                )
                figure_page.wait_for_timeout(70)
                frame = Image.open(BytesIO(
                    figure_page.locator("body").screenshot(type="png")
                )).convert("RGB")
                base_frames.append(frame)
            complete_record = {
                **stage_records[-1],
                "stage": "vase",
                "flow": "complete",
                "showReply": True,
            }
            figure_page.evaluate(
                "record => window.setCollaborationStage(record)",
                complete_record,
            )
            figure_page.wait_for_timeout(100)
            final_frame = Image.open(BytesIO(
                figure_page.locator("body").screenshot(type="png")
            )).convert("RGB")
            collaboration_frames: list[Image.Image] = []
            for record_index, frame in enumerate(base_frames):
                # Keep each state optically exact. Cross-fading two structures
                # reads as a transient duplicate or rollback in README GIFs.
                hold = 14 if record_index in {0, len(base_frames) - 1} else 11
                collaboration_frames.extend([frame.copy() for _ in range(hold)])
            collaboration_frames.extend(final_frame.copy() for _ in range(18))
            save_gif(
                collaboration_frames,
                ASSET_DIR / "readme_ai_collaboration.gif",
                duration=130,
            )
            final_frame.save(
                ASSET_DIR / "readme_ai_collaboration.png",
                optimize=True,
                compress_level=9,
            )
        finally:
            figure_page.close()

        github_dir = ASSET_DIR / "github"
        github_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "readme_ai_collaboration_live.png",
            "readme_ai_collaboration.png",
            "readme_ai_collaboration.gif",
        ):
            shutil.copy2(ASSET_DIR / name, github_dir / name)
    finally:
        page.close()
        editor.close()


def capture_constraint_media(browser) -> None:
    fixedline_atoms, line_idx = make_cnt_fixedline_scene()
    editor, page = open_scene(browser, fixedline_atoms, show_bonds=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.62,
            "showBonds": True,
            "showGrid": False,
            "showCell": False,
            "showAxes": False,
            "viewportBackground": "white",
        })
        set_selection(page, [line_idx["ion"]])
        configure_inspector(page, "structure", ["constraints", "transform"])
        target = np.asarray(fixedline_atoms.positions[line_idx["ion"]], dtype=float)
        view_target = target - np.array([0.0, 0.0, 2.8])
        settle_view(
            page,
            target=view_target.tolist(),
            position=(view_target + np.array([7.0, -12.0, 0.0])).tolist(),
            up=(12.0, 7.0, 0.0),
            fov=34,
        )
        # Align the channel axis with the wide viewport so the complete CNT,
        # moving ion, and centerline stay visible throughout the trajectory.
        set_atomic_scale(page, 68.0)
        set_readme_lighting(
            page,
            target.tolist(),
            intensity=2.9,
            position_offset=(-7.0, -10.0, 12.0),
        )
        collapse_inspector(page)
        set_view_toggles(page, grid=False, axes=False, cell=False)
        set_selection(page, [])
        page.screenshot(path=ASSET_DIR / "readme_constraints.png")
        fixedline_frames: list[Image.Image] = []
        append_hold(fixedline_frames, page, 6)
        set_selection(page, [line_idx["ion"]])
        append_hold(fixedline_frames, page, 5)
        enter_mode(page, "MOVE", "Z")
        for positions in sinusoidal_frames(
            fixedline_atoms.get_positions(),
            line_idx["ion"],
            lambda phase: [0, 0, 2.2 * phase],
        ):
            update_positions(page, positions)
            page.wait_for_timeout(35)
            fixedline_frames.append(screenshot_frame(page))
        save_gif(
            fixedline_frames,
            ASSET_DIR / "readme_fixedline.gif",
            duration=85,
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
        hookean = next(
            constraint
            for constraint in hookean_atoms.constraints
            if getattr(constraint, "indices", None) == [indices["carbon"], indices["oxygen"]]
        )
        threshold = float(hookean.threshold)
        spring_constant = float(hookean.spring)
        initial_distance = float(hookean_atoms.get_distance(
            indices["carbon"],
            indices["oxygen"],
            mic=True,
        ))
        if initial_distance >= threshold:
            raise AssertionError("README Hookean example must begin inside its zero-force rt region.")
        direction = oxygen_pos - carbon_pos
        direction /= np.linalg.norm(direction)
        preview_distance = threshold + 0.95
        preview_delta = direction * (preview_distance - initial_distance)
        target = (carbon_pos + oxygen_pos) * 0.5 + preview_delta * 0.48 + np.array([0.15, 0.05, 0.12])
        settle_view(page, target=target.tolist(), position=(target + np.array([3.9, -4.7, 2.9])).tolist(), fov=33)
        set_atomic_scale(page, min(230.0, MEDIA_SIZE[0] / 9.5))
        set_readme_lighting(page, target.tolist(), intensity=3.0, position_offset=(-7.0, -9.0, 12.0))
        active_preview = base.copy()
        active_preview[indices["oxygen"]] += preview_delta
        active_preview[indices["hydroxyl_h"]] += preview_delta
        update_positions(page, active_preview)
        rendered_hookean = page.evaluate("""() => {
            const group = window.__V_ASE_APP__.renderer.hookeanGroup.children[0];
            const spring = group.children.find(child => child.userData?.springLine);
            spring.geometry.computeBoundingBox();
            const bounds = spring.geometry.boundingBox;
            return {
                state: group.userData.hookeanState,
                distance: group.userData.hookeanDistance,
                threshold: group.userData.hookeanThreshold,
                extension: group.userData.hookeanExtension,
                spriteCount: group.children.filter(child => child.isSprite).length,
                springXSpan: bounds.max.x - bounds.min.x,
                springZSpan: bounds.max.z - bounds.min.z
            };
        }""")
        if rendered_hookean["state"] != "active":
            raise AssertionError("README Hookean spring is not shown in its active regime.")
        if not np.isclose(rendered_hookean["distance"], preview_distance, atol=1e-7):
            raise AssertionError("README Hookean distance does not match the displayed atom geometry.")
        if not np.isclose(rendered_hookean["threshold"], threshold, atol=1e-12):
            raise AssertionError("README Hookean rt does not match the ASE constraint.")
        if not np.isclose(
            rendered_hookean["extension"],
            preview_distance - threshold,
            atol=1e-7,
        ):
            raise AssertionError("README Hookean extension is not max(0, distance - rt).")
        if rendered_hookean["spriteCount"] != 0:
            raise AssertionError("README Hookean visualization must not add numeric annotations.")
        if min(rendered_hookean["springXSpan"], rendered_hookean["springZSpan"]) <= 0.18:
            raise AssertionError("README Hookean spring does not retain visible 3D helical depth.")
        expected_force = spring_constant * (preview_distance - threshold)
        if expected_force <= 0:
            raise AssertionError("README Hookean active force must be positive beyond rt.")
        page.screenshot(path=ASSET_DIR / "readme_hookean.png")
        end = carbon_pos + direction * (threshold + 1.50)
        delta = end - oxygen_pos
        capture_animation(
            page,
            ASSET_DIR / "readme_hookean.gif",
            hookean_group_frames(base, [indices["oxygen"], indices["hydroxyl_h"]], delta),
        )
    finally:
        page.close()
        editor.close()


def _add_insertion_region(page, *, role: str, name: str, bounds: Sequence[float]) -> None:
    """Create one region through the same controls used by an end user."""
    if role not in {"allow", "reject"}:
        raise ValueError(f"Unsupported insertion-region role: {role}")
    normalized = [float(value) for value in bounds]
    if len(normalized) != 6:
        raise ValueError("Insertion-region bounds require xmin/xmax/ymin/ymax/zmin/zmax.")
    before = page.locator("#add-atoms-region-list .add-atoms-region-item").count()
    page.click(f"#btn-add-atoms-{role}-region")
    page.wait_for_function(
        "count => document.querySelectorAll('#add-atoms-region-list .add-atoms-region-item').length === count",
        arg=before + 1,
    )
    page.fill("#add-atoms-region-name", name)
    page.locator("#add-atoms-region-name").blur()
    for selector, value in zip(
        (
            "#add-atoms-xmin", "#add-atoms-xmax",
            "#add-atoms-ymin", "#add-atoms-ymax",
            "#add-atoms-zmin", "#add-atoms-zmax",
        ),
        normalized,
    ):
        page.fill(selector, f"{value:.12g}")
        page.locator(selector).blur()


def _atom_mesh_visual_state(page, count: int) -> list[dict[str, object]]:
    """Read the rendered radius and temporary fixed-material state."""
    return page.evaluate("""count => Array.from(
        {length: count},
        (_, index) => {
            const renderer = window.__V_ASE_APP__.renderer;
            const mesh = renderer.atomMeshByIndex.get(index);
            return {
                scale: mesh?.scale?.toArray?.() || null,
                fixed: Boolean(mesh?.userData?.fixed),
                radius: renderer.atomVisualRadius(index)
            };
        }
    )""", count)


def _assert_temporary_fix_is_material_only(
    before: Sequence[dict[str, object]],
    current: Sequence[dict[str, object]],
    *,
    expected_fixed: bool,
) -> None:
    """Reject temporary fixation that changes a configured atom radius."""
    np.testing.assert_allclose(
        [item["scale"] for item in current],
        [item["scale"] for item in before],
        atol=0.0,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        [item["radius"] for item in current],
        [item["radius"] for item in before],
        atol=0.0,
        rtol=0.0,
    )
    fixed = [bool(item["fixed"]) for item in current]
    if fixed != [expected_fixed] * len(current):
        raise AssertionError(
            "Temporary host fixation changed an unexpected set of atom materials."
        )


def _capture_add_atoms_variant(
    browser,
    *,
    region_role: str,
    gif_name: str,
    save_static: bool = False,
) -> None:
    if region_role not in {"allowed", "prohibited"}:
        raise ValueError(f"Unsupported Add Atoms region role: {region_role}")
    host, metadata = make_random_addition_scene()
    editor, page = open_scene(browser, host, show_bonds=False, viz_only=False)
    try:
        lengths = host.cell.lengths()
        top_z = float(np.max(host.positions[:, 2]))
        center = np.asarray([lengths[0] * 0.5, lengths[1] * 0.5, top_z - 1.7])
        set_display(page, {
            "viewportBackground": "white",
            "projectionMode": "orthographic",
            "showGrid": False,
            "showAxes": False,
            "showCell": True,
            "showBonds": False,
            "showOverlays": True,
            "atomRadiusScale": 0.75,
            "labelRadii": {
                "Cu_surface": 1.55,
                "O_inserted": 0.94,
            },
            "labelColors": {
                "Cu_surface": "#b96f38",
                "O_inserted": "#dc3f3f",
            },
            "labelMaterials": {
                "Cu_surface": "metal",
                "O_inserted": "standard",
            },
            "cellColor": "#96722f",
            "cellThickness": 0.055,
        })
        page.evaluate("window.__V_ASE_APP__.renderer.setProjectionMode('orthographic')")
        set_camera(
            page,
            target=center.tolist(),
            position=(center + np.asarray([20.0, -31.0, 10.5])).tolist(),
            up=(0, 0, 1),
            fov=35,
        )
        page.evaluate("window.__V_ASE_APP__.renderer.fitCameraToStructure()")
        set_atomic_scale(page, 43.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.75,
            position_offset=(-15.0, -20.0, 23.0),
        )
        host_visual_before = _atom_mesh_visual_state(page, len(host))
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            host_visual_before,
            expected_fixed=False,
        )

        page.click("#btn-create-atom-toggle")
        page.click("#add-atoms-tab-batch")
        page.evaluate("""() => {
            const widget = document.getElementById('create-atom-widget');
            widget.style.left = '22px';
            widget.style.right = 'auto';
            widget.style.top = '82px';
            widget.style.bottom = 'auto';
        }""")

        allow_region = metadata["allow_region"]
        reject_region = metadata["reject_region"]
        bounds = np.asarray(allow_region["bounds"], dtype=float)
        _add_insertion_region(
            page,
            role="allow",
            name=allow_region["name"],
            bounds=bounds,
        )
        if region_role == "prohibited":
            _add_insertion_region(
                page,
                role="reject",
                name=reject_region["name"],
                bounds=np.asarray(reject_region["bounds"], dtype=float),
            )
        page.locator("#add-atoms-allow-escape").set_checked(False)

        for entry_index, entry in enumerate(metadata["entries"]):
            if entry_index:
                page.click("#btn-add-atoms-entry")
            row = page.locator("#add-atoms-entries .add-atoms-entry-row").nth(entry_index)
            row.locator(".add-atoms-entry-type").select_option(entry["element"])
            row.locator(".add-atoms-entry-label").fill(entry["label"])
            row.locator(".add-atoms-entry-count").fill(str(entry["count"]))
        page.fill("#add-atoms-seed", str(metadata["seed"]))
        page.select_option("#add-atoms-cutoff-basis", "pairwise")
        page.fill("#add-atoms-cutoff-scale", "1.00")
        page.fill("#add-atoms-strength", "2.5")
        page.fill("#add-atoms-fmax", "0.002")
        page.fill("#add-atoms-steps", "180")
        unique_elements = {
            *host.get_chemical_symbols(),
            *(entry["element"] for entry in metadata["entries"]),
        }
        expected_pair_rows = len(unique_elements) * (len(unique_elements) + 1) // 2
        page.wait_for_function(
            "count => document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').length >= count",
            arg=expected_pair_rows,
        )
        page.evaluate("""cutoffs => {
            document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').forEach(row => {
                if (!(row.dataset.pair in cutoffs)) return;
                const input = row.querySelector('input');
                input.value = String(cutoffs[row.dataset.pair]);
                input.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""", {"Cu-Cu": 0.0, "Cu-O": 1.78, "O-O": 2.20})

        frames: list[Image.Image] = []
        append_hold(frames, page, 7)
        page.click("#btn-add-atoms-scatter")
        added_count = sum(int(entry["count"]) for entry in metadata["entries"])
        page.wait_for_function(
            "count => window.__V_ASE_APP__.addAtomsUI?.active?.new_count === count",
            arg=added_count,
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.renderer.addAtomsRegionGroup.visible === true"
        )
        # Newly introduced labels are initialized by the live structure load;
        # apply the publication palette after that catalog exists.
        set_display(page, {
            "labelRadii": {
                "Cu_surface": 1.55,
                "O_inserted": 0.94,
            },
            "labelColors": {
                "Cu_surface": "#b96f38",
                "O_inserted": "#dc3f3f",
            },
            "labelMaterials": {
                "Cu_surface": "metal",
                "O_inserted": "standard",
            },
        })
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            _atom_mesh_visual_state(page, len(host)),
            expected_fixed=True,
        )
        scattered_positions = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        np.testing.assert_array_equal(scattered_positions[: len(host)], host.positions)
        inserted = scattered_positions[len(host):]
        inserted_inside = np.all(
            (inserted >= bounds[::2]) & (inserted <= bounds[1::2]),
            axis=1,
        )
        if not bool(np.all(inserted_inside)):
            raise AssertionError("Cu(111) Add Atoms demo scattered outside its surface zone.")
        if region_role == "prohibited":
            reject_bounds = np.asarray(reject_region["bounds"], dtype=float)
            inside_reject = np.all(
                (inserted >= reject_bounds[::2]) & (inserted <= reject_bounds[1::2]),
                axis=1,
            )
            if bool(np.any(inside_reject)):
                raise AssertionError("Protected Cu(111) terrace received an inserted oxygen.")
        append_hold(frames, page, 8)

        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            window.__VASE_ADD_ATOMS_TRACE__ = [];
            const original = app.renderer.updatePositions.bind(app.renderer);
            app.renderer.updatePositions = positions => {
                if (app.addAtomsUI?.active?.is_relaxing && Array.isArray(positions)) {
                    window.__VASE_ADD_ATOMS_TRACE__.push(
                        positions.map(position => [...position])
                    );
                }
                return original(positions);
            };
        }""")
        page.click("#btn-add-atoms-relax")
        page.wait_for_function(
            "window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === true"
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
            timeout=20_000,
        )
        page.wait_for_function("""() => {
            const app = window.__V_ASE_APP__;
            return app.state.relaxTrajectory?.active === true
                && app.state.relaxTrajectory?.kind === 'add-atoms'
                && app.state.relaxTrajectory.frames.length > 1;
        }""")
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            app.setAddAtomsPane('batch');
            app.setAddAtomsRegionSelected(true, {update: false});
            app.updateAddAtomsRegionPreview();
            app.updateTrajectoryUI();
        }""")
        page.wait_for_function("""() =>
            document.getElementById('add-atoms-tab-batch')?.classList.contains('active')
            && !document.getElementById('trajectory-panel')?.classList.contains('hidden')
            && !document.getElementById('add-atoms-mode-badge')?.classList.contains('hidden')
        """)
        trace = page.evaluate("window.__VASE_ADD_ATOMS_TRACE__")
        if len(trace) < 4:
            raise AssertionError(
                f"README Add Atoms optimizer produced only {len(trace)} recorded states."
            )
        sample_indices = np.unique(
            np.linspace(0, len(trace) - 1, min(42, len(trace)), dtype=int)
        )
        for output_index, trace_index in enumerate(sample_indices, start=1):
            update_positions(page, trace[int(trace_index)])
            page.evaluate(
                """([step, total]) => window.__V_ASE_APP__.setAddAtomsStatus(
                    'running', `Repelling atoms · ${step}/${total}`
                )""",
                [output_index, len(sample_indices)],
            )
            frames.append(screenshot_frame(page))
        relaxed_positions = np.asarray(
            trace[-1],
            dtype=float,
        )
        update_positions(page, relaxed_positions)
        page.evaluate("""role => window.__V_ASE_APP__.setAddAtomsStatus(
            'active', `${role === 'allowed' ? 'Surface zone' : 'Protected terrace'} · O placement complete`
        )""", region_role)
        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            app.setAddAtomsPane('batch');
            app.setAddAtomsRegionSelected(true, {update: false});
            app.updateAddAtomsRegionPreview();
            app.updateTrajectoryUI();
        }""")
        np.testing.assert_array_equal(relaxed_positions[: len(host)], host.positions)
        displacement = np.linalg.norm(
            relaxed_positions[len(host):] - scattered_positions[len(host):],
            axis=1,
        )
        if float(displacement.max(initial=0.0)) <= 0.05:
            raise AssertionError("README Add Atoms repulsion did not move any inserted atom visibly.")
        if region_role == "prohibited":
            final_inserted = relaxed_positions[len(host):]
            reject_bounds = np.asarray(reject_region["bounds"], dtype=float)
            final_inside = np.all(
                (final_inserted >= reject_bounds[::2])
                & (final_inserted <= reject_bounds[1::2]),
                axis=1,
            )
            if bool(np.any(final_inside)):
                raise AssertionError("Cu(111) oxygen relaxation entered the protected patch.")
        append_hold(frames, page, 8)
        placement_frame = frames[-1].copy()

        page.click("#btn-add-atoms-finish")
        page.wait_for_function(
            "window.__V_ASE_APP__.state.atoms.metadata.atom_addition === null"
        )
        page.wait_for_function(
            "window.__V_ASE_APP__.renderer.addAtomsRegionGroup.visible === false"
        )
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            _atom_mesh_visual_state(page, len(host)),
            expected_fixed=False,
        )
        append_hold(frames, page, 10)
        save_gif(frames, ASSET_DIR / gif_name, duration=105)
        if save_static:
            placement_frame.save(
                ASSET_DIR / "readme_add_atoms.png",
                optimize=True,
                compress_level=9,
            )
    finally:
        page.close()
        editor.close()


def capture_add_atoms_media(browser) -> None:
    _capture_scratch_amorphous_media(browser)
    _capture_add_atoms_variant(
        browser,
        region_role="allowed",
        gif_name="readme_add_atoms_allowed.gif",
        save_static=True,
    )
    shutil.copy2(
        ASSET_DIR / "readme_add_atoms_allowed.gif",
        ASSET_DIR / "readme_add_atoms.gif",
    )
    _capture_add_atoms_variant(
        browser,
        region_role="prohibited",
        gif_name="readme_add_atoms_prohibited.gif",
    )
    _capture_add_molecules_media(browser)


def _capture_scratch_amorphous_media(browser) -> None:
    """Record a real empty-document -> cell -> random batch -> repel workflow."""
    editor, page = open_scene(browser, Atoms(), show_bonds=False, viz_only=False)
    try:
        cell = np.diag([9.2, 9.2, 9.2])
        center = np.asarray([4.6, 4.6, 4.6])
        set_display(page, {
            "viewportBackground": "white",
            "projectionMode": "orthographic",
            "showGrid": False,
            "showAxes": False,
            "showCell": True,
            "showBonds": False,
            "showOverlays": True,
            "atomRadiusScale": 0.58,
            "cellColor": "#7d672f",
            "cellThickness": 0.055,
        })
        configure_inspector(page, "structure", ["cell-replication"], width=430)
        page.evaluate("document.querySelector('[data-panel=\"cell-replication\"]')?.scrollIntoView({block: 'start'})")
        frames: list[Image.Image] = []
        append_hold(frames, page, 7)

        for row in range(3):
            for column in range(3):
                selector = f"#cell-{row}{column}"
                page.fill(selector, f"{cell[row, column]:.6g}")
                page.locator(selector).blur()
        for axis in "xyz":
            page.locator(f"#cell-pbc-{axis}").set_checked(True)
        append_hold(frames, page, 5)
        page.click("#btn-set-unit-cell")
        page.wait_for_function("window.__V_ASE_APP__.hasUsableCell() === true")
        page.wait_for_function("document.getElementById('empty-workspace').classList.contains('hidden')")
        loaded_cell = np.asarray(page.evaluate("window.__V_ASE_APP__.state.atoms.cell"), dtype=float)
        np.testing.assert_allclose(loaded_cell, cell, atol=1e-12)
        if page.evaluate("window.__V_ASE_APP__.state.atoms.positions.length") != 0:
            raise AssertionError("Scratch README scene unexpectedly loaded atoms before insertion.")
        set_camera(
            page,
            target=center.tolist(),
            position=(center + np.asarray([15.5, -20.0, 14.0])).tolist(),
            up=(0, 0, 1),
            fov=34,
        )
        append_hold(frames, page, 7)
        collapse_inspector(page)

        page.click("#btn-create-atom-toggle")
        page.click("#add-atoms-tab-batch")
        page.evaluate("""() => {
            const widget = document.getElementById('create-atom-widget');
            widget.style.left = '22px';
            widget.style.right = 'auto';
            widget.style.top = '82px';
            widget.style.bottom = 'auto';
        }""")
        row = page.locator("#add-atoms-entries .add-atoms-entry-row").first
        row.locator(".add-atoms-entry-type").select_option("Ga")
        row.locator(".add-atoms-entry-label").fill("Ga_amorphous")
        row.locator(".add-atoms-entry-count").fill("54")
        page.click("#add-atoms-placement-random")
        page.fill("#add-atoms-seed", "20260813")
        page.select_option("#add-atoms-cutoff-basis", "pairwise")
        page.fill("#add-atoms-cutoff-scale", "1.00")
        page.fill("#add-atoms-strength", "2.8")
        page.fill("#add-atoms-fmax", "0.025")
        page.fill("#add-atoms-steps", "180")
        page.wait_for_function(
            "document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').length >= 1"
        )
        page.evaluate("""() => {
            document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').forEach(row => {
                if (row.dataset.pair !== 'Ga-Ga') return;
                const input = row.querySelector('input');
                input.value = '2.55';
                input.dispatchEvent(new Event('change', {bubbles: true}));
            });
        }""")
        page.locator(".add-atoms-session-actions").scroll_into_view_if_needed()
        append_hold(frames, page, 7)

        page.click("#btn-add-atoms-scatter")
        page.wait_for_function("window.__V_ASE_APP__.addAtomsUI?.active?.new_count === 54")
        page.wait_for_function("window.__V_ASE_APP__.state.atoms.positions.length === 54")
        set_display(page, {
            "labelRadii": {"Ga_amorphous": 1.12},
            "labelColors": {"Ga_amorphous": "#7f91a7"},
            "labelMaterials": {"Ga_amorphous": "metal"},
        })
        scattered = np.asarray(
            page.evaluate("window.__V_ASE_APP__.state.atoms.positions"),
            dtype=float,
        )
        if not np.all((scattered >= 0.0) & (scattered < 9.2)):
            raise AssertionError("Scratch random placement escaped the half-open primary cell.")
        page.evaluate("window.__V_ASE_APP__.renderer.fitCameraToStructure()")
        set_atomic_scale(page, 49.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.8,
            position_offset=(-13.0, -16.0, 20.0),
        )
        append_hold(frames, page, 9)

        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            window.__VASE_SCRATCH_TRACE__ = [];
            const original = app.renderer.updatePositions.bind(app.renderer);
            app.renderer.updatePositions = positions => {
                if (app.addAtomsUI?.active?.is_relaxing && Array.isArray(positions)) {
                    window.__VASE_SCRATCH_TRACE__.push(
                        positions.map(position => [...position])
                    );
                }
                return original(positions);
            };
        }""")
        page.click("#btn-add-atoms-relax")
        page.wait_for_function("window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === true")
        page.wait_for_function(
            "window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
            timeout=30_000,
        )
        trace = page.evaluate("window.__VASE_SCRATCH_TRACE__")
        if len(trace) < 4:
            raise AssertionError(
                f"Scratch amorphous relaxation produced only {len(trace)} visible states."
            )
        sample_indices = np.unique(
            np.linspace(0, len(trace) - 1, min(44, len(trace)), dtype=int)
        )
        for output_index, trace_index in enumerate(sample_indices, start=1):
            update_positions(page, trace[int(trace_index)])
            page.evaluate(
                """([step, total]) => window.__V_ASE_APP__.setAddAtomsStatus(
                    'running', `Building amorphous Ga · ${step}/${total}`
                )""",
                [output_index, len(sample_indices)],
            )
            frames.append(screenshot_frame(page))
        relaxed = np.asarray(trace[-1], dtype=float)
        if float(np.max(np.linalg.norm(relaxed - scattered, axis=1))) <= 0.08:
            raise AssertionError("Scratch README relaxation did not move a Ga atom visibly.")
        update_positions(page, relaxed)
        page.evaluate("""() => window.__V_ASE_APP__.setAddAtomsStatus(
            'active', 'Amorphous Ga · placement ready'
        )""")
        append_hold(frames, page, 9)
        page.click("#btn-add-atoms-finish")
        page.wait_for_function("window.__V_ASE_APP__.state.atoms.metadata.atom_addition === null")
        page.wait_for_function("window.__V_ASE_APP__.state.atoms.positions.length === 54")
        append_hold(frames, page, 10)
        save_gif(
            frames,
            ASSET_DIR / "readme_scratch_amorphous.gif",
            duration=120,
        )
        frames[-1].save(
            ASSET_DIR / "readme_scratch_amorphous.png",
            optimize=True,
            compress_level=9,
        )
    finally:
        page.close()
        editor.close()


def _capture_add_molecules_media(browser) -> None:
    host, metadata = make_layered_water_channel_scene()
    editor, page = open_scene(browser, host, show_bonds=True, viz_only=False)
    try:
        center = np.sum(np.asarray(host.cell.array, dtype=float), axis=0) * 0.5
        set_display(page, {
            "viewportBackground": "white",
            "projectionMode": "orthographic",
            "showGrid": False,
            "showAxes": False,
            "showCell": True,
            "showBonds": True,
            "showOverlays": True,
            "atomRadiusScale": 0.62,
            "labelRadii": {
                "C_lower_membrane": 0.56,
                "C_upper_membrane": 0.56,
                "O_water": 0.72,
                "H_water": 0.48,
            },
            "labelColors": {
                "C_lower_membrane": "#46535a",
                "C_upper_membrane": "#68767d",
                "O_water": "#d9433f",
                "H_water": "#f4f5f6",
            },
            "labelMaterials": {
                "C_lower_membrane": "metal",
                "C_upper_membrane": "metal",
                "O_water": "standard",
                "H_water": "standard",
            },
            "bondMode": "pairwise",
            "pairwiseBondRanges": {
                "C_lower_membrane-C_lower_membrane": {"enabled": True, "max": 1.55},
                "C_upper_membrane-C_upper_membrane": {"enabled": True, "max": 1.55},
                "H_water-O_water": {"enabled": True, "max": 1.15},
            },
            "pairwiseBondCutoffs": {
                "C_lower_membrane-C_lower_membrane": 1.55,
                "C_upper_membrane-C_upper_membrane": 1.55,
                "H_water-O_water": 1.15,
            },
            "bondThickness": 0.15,
            "cellColor": "#8b6c2c",
            "cellThickness": 0.055,
        })
        page.evaluate("window.__V_ASE_APP__.renderer.setProjectionMode('orthographic')")
        camera_right = np.asarray([38.0, 15.0, 0.0], dtype=float)
        camera_right /= np.linalg.norm(camera_right)
        shifted_target = center - 5.2 * camera_right
        set_camera(
            page,
            target=shifted_target.tolist(),
            position=(shifted_target + np.asarray([8.0, -42.0, 1.8])).tolist(),
            up=(0, 0, 1),
            fov=35,
        )
        page.evaluate("window.__V_ASE_APP__.renderer.fitCameraToStructure()")
        page.evaluate(
            "target => { const r = window.__V_ASE_APP__.renderer; "
            "const dx = target[0] - r.controls.target.x; "
            "const dy = target[1] - r.controls.target.y; "
            "const dz = target[2] - r.controls.target.z; "
            "r.controls.target.set(...target); "
            "r.camera.position.x += dx; r.camera.position.y += dy; "
            "r.camera.position.z += dz; r.renderNow(); }",
            shifted_target.tolist(),
        )
        set_atomic_scale(page, 72.0)
        set_readme_lighting(page, center.tolist(), intensity=2.8, position_offset=(-16, -18, 22))
        host_visual_before = _atom_mesh_visual_state(page, len(host))
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            host_visual_before,
            expected_fixed=False,
        )

        page.click("#btn-create-atom-toggle")
        page.click("#add-atoms-tab-batch")
        page.click("#add-atoms-content-molecules")
        page.wait_for_function(
            "document.querySelector('#add-molecule-entries select')?.options.length >= 150"
        )
        page.evaluate("""() => {
            const widget = document.getElementById('create-atom-widget');
            widget.style.left = '22px';
            widget.style.right = 'auto';
            widget.style.top = '82px';
            widget.style.bottom = 'auto';
            const overlay = document.createElement('div');
            overlay.id = 'readme-molecule-stage';
            overlay.innerHTML = `
                <div class="readme-stage-line">
                    <strong id="readme-molecule-step">1 · DEFINE REGIONS</strong>
                    <span>graphene sheets every 6 Å · PBC x/y/z</span>
                </div>
                <div class="readme-stage-facts">
                    <span><i class="allow"></i>ALLOW ×<b id="readme-allow-count">0</b></span>
                    <span><i class="reject"></i>REJECT ×<b id="readme-reject-count">0</b></span>
                    <span id="readme-domain-volume">cell domain</span>
                    <span id="readme-molecule-detail">add the placement regions</span>
                </div>`;
            document.body.appendChild(overlay);
            const sceneLabels = document.createElement('div');
            sceneLabels.id = 'readme-molecule-scene-labels';
            sceneLabels.innerHTML = `
                <span class="region-label upper">ALLOW · upper 6 Å slit</span>
                <span class="region-label reject">REJECT · gate</span>
                <span class="spacing-label"><b>6 Å</b><i></i></span>
                <span class="region-label lower">ALLOW · lower 6 Å slit</span>`;
            document.body.appendChild(sceneLabels);
            const style = document.createElement('style');
            style.textContent = `
                #readme-molecule-stage {
                    position: fixed; z-index: 5000; top: 78px; left: 500px;
                    width: 920px; padding: 11px 15px 10px;
                    border: 2px solid #bed0cd; border-left: 7px solid #087f70;
                    border-radius: 6px; background: rgba(255,255,255,.96);
                    color: #243638; box-shadow: 0 5px 18px rgba(26,45,48,.13);
                    pointer-events: none; letter-spacing: 0;
                }
                .readme-stage-line { display: flex; align-items: baseline; gap: 17px; }
                .readme-stage-line strong { color: #08796d; font-size: 18px; }
                .readme-stage-line span { font-size: 16px; font-weight: 800; }
                .readme-stage-facts { display: flex; align-items: center; gap: 17px; margin-top: 6px; font-size: 14px; font-weight: 750; }
                .readme-stage-facts i { display: inline-block; width: 14px; height: 14px; margin-right: 5px; vertical-align: -2px; border: 3px solid; }
                .readme-stage-facts i.allow { border-color: #008f78; background: rgba(0,143,120,.15); }
                .readme-stage-facts i.reject { border-color: #ad3b98; background: rgba(173,59,152,.14); }
                #readme-molecule-detail { color: #754d05; }
                #trajectory-panel { display: none !important; }
                #toast-container, .status-group { display: none !important; }
                #readme-molecule-scene-labels { position: fixed; inset: 0; z-index: 4999; pointer-events: none; }
                .region-label { display: none; position: absolute; padding: 5px 8px; border: 2px solid; border-radius: 4px; background: rgba(255,255,255,.94); font-size: 14px; font-weight: 900; }
                .region-label.upper { left: 1280px; top: 190px; color: #006f60; border-color: #008f78; }
                .region-label.lower { left: 1260px; top: 710px; color: #006f60; border-color: #008f78; }
                .region-label.reject { left: 1085px; top: 288px; color: #8d247a; border-color: #ad3b98; }
                .spacing-label { position: absolute; left: 750px; top: 488px; display: flex; align-items: center; gap: 7px; color: #674f1f; font-size: 16px; font-weight: 950; }
                .spacing-label i { display: block; width: 2px; height: 82px; background: #8b6c2c; box-shadow: 0 -5px 0 #8b6c2c, 0 5px 0 #8b6c2c; }
            `;
            document.head.appendChild(style);
            window.__setReadmeMoleculeStage = (step, detail) => {
                document.getElementById('readme-molecule-step').textContent = step;
                document.getElementById('readme-molecule-detail').textContent = detail;
            };
            window.__setReadmeMoleculeDomain = (allow, reject, volume) => {
                document.getElementById('readme-allow-count').textContent = String(allow);
                document.getElementById('readme-reject-count').textContent = String(reject);
                document.getElementById('readme-domain-volume').textContent = volume;
                document.querySelector('.region-label.lower').style.display = allow >= 1 ? 'block' : 'none';
                document.querySelector('.region-label.upper').style.display = allow >= 2 ? 'block' : 'none';
                document.querySelector('.region-label.reject').style.display = reject >= 1 ? 'block' : 'none';
            };
        }""")
        row = page.locator("#add-molecule-entries .add-molecule-entry-row").first
        molecule_spec = metadata["molecules"][0]
        row.locator(".add-molecule-entry-name").select_option(molecule_spec["name"])
        row.locator(".add-molecule-entry-label").fill(molecule_spec["label"])
        row.locator(".add-molecule-entry-count").fill(
            str(metadata["expected_molecule_count"])
        )
        frames: list[Image.Image] = []
        page.evaluate("window.__setReadmeMoleculeStage('1 · DEFINE REGIONS', 'start from the periodic cell')")
        append_hold(frames, page, 11)
        for region_index, region in enumerate(metadata["regions"], start=1):
            _add_insertion_region(
                page,
                role=region["role"],
                name=region["name"],
                bounds=region["bounds"],
            )
            if region_index == 1:
                detail = "lower Allow region added"
            elif region_index == 2:
                detail = "upper Allow region added"
            else:
                detail = "Reject gate subtracted from upper region"
            page.evaluate(
                "detail => window.__setReadmeMoleculeStage('1 · DEFINE REGIONS', detail)",
                detail,
            )
            current_volume = page.locator("#add-atoms-domain-volume").inner_text()
            page.evaluate(
                "([allow, reject, volume]) => window.__setReadmeMoleculeDomain(allow, reject, volume)",
                [
                    min(region_index, 2),
                    1 if region_index >= 3 else 0,
                    f"exact domain {current_volume}",
                ],
            )
            append_hold(frames, page, 12)
        page.click("#add-molecules-quantity-density")
        page.fill(
            "#add-molecules-target-density",
            f"{float(metadata['target_density_g_cm3']):.6f}",
        )
        page.locator("#add-atoms-region-list .add-atoms-region-item").first.click()
        page.wait_for_timeout(100)
        region_visuals = page.evaluate("""() => {
            const children = window.__V_ASE_APP__.renderer.addAtomsRegionGroup.children;
            const sourceFills = children.filter(child => (
                child.userData?.insertionRegionSourceBox
                && !child.userData?.cellEdgeInstances
            ));
            const wrappedFills = children.filter(child => (
                child.userData?.insertionRegionWrappedFragment
                && !child.userData?.cellEdgeInstances
            ));
            const inlet = sourceFills[0];
            inlet?.geometry?.computeBoundingBox?.();
            return {
                sourceFillCount: sourceFills.length,
                wrappedFillCount: wrappedFills.length,
                sourceEdgeCount: children.filter(child => (
                    child.userData?.insertionRegionSourceBox
                    && child.userData?.cellEdgeInstances
                )).length,
                wrappedEdgeCount: children.filter(child => (
                    child.userData?.insertionRegionWrappedFragment
                    && child.userData?.cellEdgeInstances
                )).length,
                inletBounds: inlet?.geometry?.boundingBox
                    ? [inlet.geometry.boundingBox.min.x, inlet.geometry.boundingBox.max.x]
                    : null,
                wrappedShifts: wrappedFills.map(child => child.userData.shift),
            };
        }""")
        if region_visuals["sourceFillCount"] != len(metadata["regions"]):
            raise AssertionError("README Add Molecules did not render one intact source box per region.")
        if region_visuals["sourceEdgeCount"] != len(metadata["regions"]):
            raise AssertionError("README Add Molecules source boxes are missing complete edge sets.")
        if region_visuals["wrappedFillCount"] != 0 or region_visuals["wrappedEdgeCount"] != 0:
            raise AssertionError("README Add Molecules uses in-cell regions and should not need wrapped fragments.")
        np.testing.assert_allclose(region_visuals["inletBounds"], [1.0, 7.0], atol=1e-6)

        page.wait_for_function(
            "expected => document.querySelector('#add-molecules-actual-density')?.textContent.includes(`${expected} molecules`)",
            arg=metadata["expected_molecule_count"],
        )
        page.evaluate(
            "([count, volume]) => { window.__setReadmeMoleculeDomain(2, 1, `exact domain ${volume}`); window.__setReadmeMoleculeStage('2 · READY TO PLACE', `${count} H₂O from target density 0.65 g/cm³`); }",
            [metadata["expected_molecule_count"], page.locator("#add-atoms-domain-volume").inner_text()],
        )
        page.wait_for_function(
            "expected => Math.abs(Number(window.__V_ASE_APP__.addAtomsUI?.domainPreview?.domain?.volume_angstrom3) - expected) < 1e-8",
            arg=float(metadata["accessible_volume_angstrom3"]),
        )
        accessible_volume = float(page.evaluate(
            "window.__V_ASE_APP__.addAtomsUI.domainPreview.domain.volume_angstrom3"
        ))
        if not np.isclose(
            accessible_volume,
            float(metadata["accessible_volume_angstrom3"]),
            atol=1e-8,
            rtol=0.0,
        ):
            raise AssertionError(
                f"README multi-region volume {accessible_volume} does not match the exact reference."
            )
        page.click("#add-atoms-placement-random")
        if not page.locator("#add-atoms-coordinate-basis").is_hidden():
            raise AssertionError("Random molecule placement unexpectedly exposed spacing controls.")
        page.fill("#add-atoms-seed", str(metadata["seed"]))
        page.locator("#add-molecules-random-orientation").set_checked(True)
        page.locator("#add-molecules-rigid").set_checked(True)
        page.locator("#add-atoms-select-added").set_checked(True)
        page.select_option("#add-atoms-cutoff-basis", "pairwise")
        page.evaluate(
            "async () => await window.__V_ASE_APP__.refreshAddAtomsPairCutoffs({preserveManual: false})"
        )
        page.wait_for_function(
            "document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').length >= 6"
        )
        expected_pair_cutoffs = {
            "C-C": 0.0,
            "C-H": 1.90,
            "C-O": 2.60,
            "H-H": 1.35,
            "H-O": 0.0,
            "O-O": 2.90,
        }
        captured_pair_cutoffs = page.evaluate("""cutoffs => {
            document.querySelectorAll('#add-atoms-pair-table .add-atoms-pair-row').forEach(row => {
                if (!(row.dataset.pair in cutoffs)) return;
                const input = row.querySelector('input');
                input.value = String(cutoffs[row.dataset.pair]);
                input.dispatchEvent(new Event('change', {bubbles: true}));
            });
            return window.__V_ASE_APP__.captureAddAtomsPairCutoffs();
        }""", expected_pair_cutoffs)
        for pair, cutoff in expected_pair_cutoffs.items():
            if not np.isclose(float(captured_pair_cutoffs[pair]), cutoff, atol=1e-12):
                raise AssertionError(f"README molecule cutoff {pair} was overwritten asynchronously.")
        page.fill("#add-atoms-strength", "3.2")
        page.fill("#add-atoms-fmax", "0.5")
        page.fill("#add-atoms-steps", "220")
        page.evaluate(
            "window.__setReadmeMoleculeStage('2 · READY TO PLACE', "
            "'10 H₂O · rigid · random orientation · pairwise C/H/O cutoffs')"
        )

        append_hold(frames, page, 12)
        page.click("#btn-add-atoms-scatter")
        page.wait_for_function(
            "count => window.__V_ASE_APP__.addAtomsUI?.active?.molecule_count === count",
            arg=metadata["expected_molecule_count"],
        )
        page.wait_for_function(
            "count => window.__V_ASE_APP__.state.selected.size === count",
            arg=metadata["expected_molecule_count"] * 3,
        )
        summary = page.evaluate("window.__V_ASE_APP__.addAtomsUI.active")
        if [region["role"] for region in summary["regions"]] != ["allow", "allow", "reject"]:
            raise AssertionError("README Add Molecules did not preserve the multi-region Boolean domain.")
        if not np.isclose(
            float(summary["domain"]["volume_angstrom3"]),
            float(metadata["accessible_volume_angstrom3"]),
            atol=1e-8,
        ):
            raise AssertionError("README Add Molecules session changed the exact accessible volume.")
        set_display(page, {
            "labelRadii": {"O_water": 0.72, "H_water": 0.48},
            "labelColors": {"O_water": "#d9433f", "H_water": "#f4f5f6"},
            "labelMaterials": {"O_water": "standard", "H_water": "standard"},
            "pairwiseBondRanges": {"H_water-O_water": {"enabled": True, "max": 1.15}},
            "pairwiseBondCutoffs": {"H_water-O_water": 1.15},
        })
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            _atom_mesh_visual_state(page, len(host)),
            expected_fixed=True,
        )
        page.evaluate("window.__V_ASE_APP__.renderer.selectionOutlines.visible = false")
        scattered = np.asarray(page.evaluate("window.__V_ASE_APP__.state.atoms.positions"))
        np.testing.assert_array_equal(scattered[: len(host)], host.positions)
        page.evaluate(
            "count => window.__setReadmeMoleculeStage('2 · RANDOM PLACEMENT', `${count} H₂O · random positions + orientations in Boolean domain`)",
            metadata["expected_molecule_count"],
        )
        append_hold(frames, page, 12)

        page.evaluate("""() => {
            const app = window.__V_ASE_APP__;
            window.__VASE_ADD_MOLECULES_TRACE__ = [];
            const original = app.renderer.updatePositions.bind(app.renderer);
            app.renderer.updatePositions = positions => {
                if (app.addAtomsUI?.active?.is_relaxing && Array.isArray(positions)) {
                    window.__VASE_ADD_MOLECULES_TRACE__.push(positions.map(position => [...position]));
                }
                return original(positions);
            };
        }""")
        page.click("#btn-add-atoms-relax")
        page.wait_for_function("window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === true")
        page.wait_for_function(
            "window.__V_ASE_APP__.addAtomsUI?.active?.is_relaxing === false",
            timeout=20_000,
        )
        trace = page.evaluate("window.__VASE_ADD_MOLECULES_TRACE__")
        final_positions = page.evaluate("window.__V_ASE_APP__.state.atoms.positions")
        if not trace or not np.allclose(
            np.asarray(trace[-1], dtype=float),
            np.asarray(final_positions, dtype=float),
            atol=1e-12,
        ):
            trace.append(final_positions)
        if len(trace) < 3:
            raise AssertionError("README Add Molecules optimizer produced too few visible states.")
        sample_indices = np.unique(np.linspace(0, len(trace) - 1, min(36, len(trace)), dtype=int))
        for output_index, trace_index in enumerate(sample_indices, start=1):
            update_positions(page, trace[int(trace_index)])
            page.evaluate("window.__V_ASE_APP__.renderer.selectionOutlines.visible = false")
            page.evaluate(
                """([step, total]) => window.__V_ASE_APP__.setAddAtomsStatus(
                    'running', `Optimizer trajectory · frame ${step}/${total}`
                )""",
                [output_index, len(sample_indices)],
            )
            page.evaluate(
                """([step, total]) => window.__setReadmeMoleculeStage(
                    '3 · RIGID-BODY REPULSION',
                    `MIC · host fixed · rigid H₂O · region exit allowed · frame ${step}/${total}`
                )""",
                [output_index, len(sample_indices)],
            )
            frame = screenshot_frame(page)
            frames.append(frame)
        relaxed = np.asarray(trace[-1], dtype=float)
        np.testing.assert_array_equal(relaxed[: len(host)], host.positions)
        molecule_center_motion = []
        for start in range(len(host), len(relaxed), 3):
            center_delta = np.mean(
                relaxed[start:start + 3] - scattered[start:start + 3],
                axis=0,
            )
            mic_delta, _ = find_mic(center_delta, host.cell, host.pbc)
            molecule_center_motion.append(float(np.linalg.norm(mic_delta)))
        center_rms_motion = float(np.sqrt(np.mean(np.square(molecule_center_motion))))
        if center_rms_motion < 0.50:
            raise AssertionError(
                "README rigid-water example did not show enough molecular motion: "
                f"MIC center RMS {center_rms_motion:.4f} Angstrom."
            )
        reference = molecule("H2O").positions
        reference_distances = np.linalg.norm(reference[:, None] - reference[None, :], axis=2)
        for start in range(len(host), len(relaxed), 3):
            current = relaxed[start:start + 3]
            current_distances = np.linalg.norm(current[:, None] - current[None, :], axis=2)
            np.testing.assert_allclose(current_distances, reference_distances, atol=2e-7)
        page.evaluate(
            "([count, status, step, maximum]) => window.__setReadmeMoleculeStage("
            "'4 · READY', `${count} rigid H₂O · ${status} ${step}/${maximum} · host/cell unchanged`) ",
            [
                metadata["expected_molecule_count"],
                str(page.evaluate("window.__V_ASE_APP__.addAtomsUI.active.status")),
                int(page.evaluate("window.__V_ASE_APP__.addAtomsUI.active.step || 0")),
                int(page.evaluate("window.__V_ASE_APP__.addAtomsUI.active.max_steps || 0")),
            ],
        )
        page.evaluate(
            "total => window.__V_ASE_APP__.setAddAtomsStatus('complete', `Optimizer trajectory complete · ${total} frames`)",
            len(sample_indices),
        )
        append_hold(frames, page, 18)
        final_frame = frames[-1].copy()
        final_frame.save(
            ASSET_DIR / "readme_add_molecules.png",
            optimize=True,
            compress_level=9,
        )
        page.click("#btn-add-atoms-finish")
        page.wait_for_function("window.__V_ASE_APP__.state.atoms.metadata.atom_addition === null")
        if page.evaluate("window.__V_ASE_APP__.renderer.addAtomsRegionGroup.visible"):
            raise AssertionError("Finishing Add Molecules left its temporary regions visible.")
        _assert_temporary_fix_is_material_only(
            host_visual_before,
            _atom_mesh_visual_state(page, len(host)),
            expected_fixed=False,
        )
        page.evaluate(
            "count => { window.__setReadmeMoleculeDomain(0, 0, 'regions removed'); "
            "window.__setReadmeMoleculeStage("
            "'5 · COMMITTED', `${count} H₂O retained · temporary host fixation released · regions removed`); } ",
            metadata["expected_molecule_count"],
        )
        if page.locator(".region-label:visible").count():
            raise AssertionError("Committed Add Molecules media retained a temporary region label.")
        append_hold(frames, page, 18)
        save_gif(frames, ASSET_DIR / "readme_add_molecules.gif", duration=115)
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
        collapse_inspector(page)
        center = np.mean(atoms.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([4.2, -5.6, 3.5])).tolist(),
            fov=31,
        )
        set_atomic_scale(page, 275.0)
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


def capture_volumetric_media(browser) -> None:
    atoms, values = make_graphene_pi_volumetric_scene()
    cube_path = ROOT / ".v_ase-readme-graphene-pi.cube"
    with cube_path.open("w", encoding="utf-8") as handle:
        write_cube(handle, atoms, data=values)

    editor, page = open_scene(browser, atoms, show_bonds=True)
    try:
        command_url = external_ai_command_url(editor)
        set_display(page, {
            "atomRadiusScale": 0.54,
            "showBonds": True,
            "bondThickness": 0.18,
            "showGrid": False,
            "showCell": False,
            "showAxes": False,
            "viewportBackground": "white",
            "lightingMode": "studio-shadow",
            "labelColors": {
                "C_pi_A": "#30383d",
                "C_pi_B": "#607078",
            },
            "labelMaterials": {
                "C_pi_A": "standard",
                "C_pi_B": "standard",
            },
        })
        configure_inspector(page, "analysis", ["volumetric"], width=470)
        loaded = run_external_ai_apply(command_url, {
            "operation": {
                "name": "load-volumetric",
                "path": cube_path.relative_to(ROOT).as_posix(),
            },
        })
        dataset = loaded["analysis"]["volumetricDatasets"][-1]
        result = run_external_ai_apply(command_url, {
            "operation": {
                "name": "show-volumetric",
                "datasetId": dataset["id"],
                "level": float(np.max(np.abs(values)) * 0.22),
                "surfaceMode": "signed",
                "stepSize": 1,
                "smearingSigma": 0.45,
                "smoothingIterations": 7,
                "opacity": 0.56,
                "positiveColor": "#258fbd",
                "negativeColor": "#dc5976",
            },
        })
        if not result["analysis"]["volumetricDatasets"]:
            raise AssertionError("README volumetric scene did not load its scalar field.")
        page.wait_for_function(
            """() => Number(
                window.__V_ASE_APP__.renderer.domElement.dataset.volumetricSurfaceCount || 0
            ) >= 2"""
        )
        center = np.mean(atoms.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([8.8, -10.5, 6.8])).tolist(),
            fov=33,
        )
        set_atomic_scale(page, 86.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=3.0,
            position_offset=(-7.0, -9.0, 12.0),
        )
        opacity_state = page.evaluate(
            """() => {
                const app = window.__V_ASE_APP__;
                return {
                    value: document.getElementById('volume-opacity-value')?.textContent,
                    smearing: document.getElementById('volume-smearing')?.value,
                    smoothing: document.getElementById('volume-smoothing')?.value,
                    status: document.getElementById('volume-status')?.textContent,
                    materials: app.renderer.volumetricSurfaces.map(surface => ({
                        opacity: surface.material.opacity,
                        transparent: surface.material.transparent
                    }))
                };
            }"""
        )
        if opacity_state["value"] != "0.56":
            raise AssertionError("README volumetric opacity readout is not synchronized.")
        if opacity_state["smearing"] != "0.45" or opacity_state["smoothing"] != "7":
            raise AssertionError("README volumetric refinement controls are not synchronized.")
        if "σ 0.45 voxel" not in opacity_state["status"] or "7 smoothing passes" not in opacity_state["status"]:
            raise AssertionError("README volumetric refinement status is incomplete.")
        if not all(
            abs(material["opacity"] - 0.56) < 1e-6 and material["transparent"]
            for material in opacity_state["materials"]
        ):
            raise AssertionError("README isosurface opacity was not applied to its materials.")
        level_frames = []
        maximum_level = float(max(abs(dataset["minimum"]), abs(dataset["maximum"])))
        level_fractions = [
            *np.linspace(0.05, 0.46, 12),
            *np.linspace(0.46, 0.05, 12)[1:],
        ]
        level_values = [maximum_level * float(fraction) for fraction in level_fractions]
        for level in level_values:
            page.evaluate(
                """async level => {
                    const app = window.__V_ASE_APP__;
                    app.state.display.volumetricLevel = Number(level);
                    app.syncVolumetricControls();
                    await app.updateVolumetricSurface({recordHistory: false});
                }""",
                level,
            )
            page.wait_for_function(
                """level => {
                    const app = window.__V_ASE_APP__;
                    const summary = app.state.volumetricSurfaceSummary;
                    return summary
                        && Math.abs(Number(summary.requestedLevel) - Number(level)) < 1e-8
                        && Number(app.renderer.domElement.dataset.volumetricSurfaceCount || 0) >= 2;
                }""",
                arg=level,
                timeout=30_000,
            )
            page.wait_for_timeout(55)
            level_frames.append(screenshot_frame(page))
        save_gif(
            level_frames,
            ASSET_DIR / "readme_volumetric.gif",
            duration=195,
        )
        page.evaluate(
            """level => {
                const slider = document.getElementById('volume-level-slider');
                slider.value = `${level}`;
                slider.dispatchEvent(new Event('input', {bubbles: true}));
                slider.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            float(np.max(np.abs(values)) * 0.22),
        )
        page.wait_for_function(
            """level => Math.abs(
                Number(window.__V_ASE_APP__.state.volumetricSurfaceSummary?.requestedLevel)
                - Number(level)
            ) < 1e-8""",
            arg=float(np.max(np.abs(values)) * 0.22),
            timeout=30_000,
        )
        screenshot_frame(page).save(
            ASSET_DIR / "readme_volumetric.png",
            optimize=True,
        )

        plane_result = run_external_ai_apply(command_url, {
            "operation": {
                "name": "add-volumetric-plane",
                "datasetId": dataset["id"],
                "planeName": "(1 0 0) multi-center pi-field section",
                "hkl": [1, 0, 0],
                "resolution": 1024,
                "colormap": "coolwarm",
                "autoRange": False,
                "vmin": -maximum_level * 0.30,
                "vmax": maximum_level * 0.30,
                "opacity": 0.84,
                "visible": True,
            },
        })
        plane = plane_result["analysis"]["volumetricPlanes"][-1]
        plane_state = {
            "id": plane["id"],
            "minimum": plane["offsetRangeAngstrom"][0],
            "maximum": plane["offsetRangeAngstrom"][1],
            "vmin": -maximum_level * 0.30,
            "vmax": maximum_level * 0.30,
        }
        page.wait_for_function(
            """() => window.__V_ASE_APP__.renderer.volumetricPlanes.size === 1"""
        )
        run_external_ai_apply(command_url, {
            "display": {
                "showVolumetric": False,
                "showCell": True,
                "showGrid": False,
                "showAxes": False,
            },
        })
        page.evaluate(
            """() => {
                const app = window.__V_ASE_APP__;
                app.setVolumetricToolView('planes');
                const panel = document.querySelector('.volume-plane-panel');
                panel.scrollIntoView({block: 'start', behavior: 'instant'});
            }"""
        )
        set_camera(
            page,
            target=center.tolist(),
            position=(center + np.array([13.5, -15.5, 10.5])).tolist(),
            up=(0.0, 0.0, 1.0),
            fov=32,
        )
        set_atomic_scale(page, 58.0)
        page.wait_for_timeout(180)
        span = plane_state["maximum"] - plane_state["minimum"]
        offsets = [
            *np.linspace(0.12, 0.88, 33),
            *np.linspace(0.86, 0.14, 31),
        ]
        plane_frames = []
        for fraction in offsets:
            offset = plane_state["minimum"] + span * fraction
            run_external_ai_apply(command_url, {
                "operation": {
                    "name": "update-volumetric-planes",
                    "planeIds": [plane_state["id"]],
                    "offsetAngstrom": offset,
                    "autoRange": False,
                    "vmin": plane_state["vmin"],
                    "vmax": plane_state["vmax"],
                },
            })
            fixed_range = page.evaluate(
                """id => {
                    const plane = window.__V_ASE_APP__.state.display.volumetricPlanes
                        .find(candidate => candidate.id === id);
                    return [plane.autoRange, plane.vmin, plane.vmax];
                }""",
                plane_state["id"],
            )
            if fixed_range[0] or not np.allclose(
                fixed_range[1:],
                [plane_state["vmin"], plane_state["vmax"]],
            ):
                raise AssertionError("README plane animation changed its fixed color range.")
            page.wait_for_timeout(45)
            plane_frames.append(screenshot_frame(page))
        save_gif(
            plane_frames,
            ASSET_DIR / "readme_volumetric_plane.gif",
            duration=105,
        )
        plane_frames[len(plane_frames) // 2].save(
            ASSET_DIR / "readme_volumetric_plane.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()
        cube_path.unlink(missing_ok=True)


def capture_atom_colorscale_media(browser) -> None:
    frames = make_atom_colorscale_trajectory()
    force_norms = np.concatenate([
        np.linalg.norm(frame.get_forces(), axis=1)
        for frame in frames
    ])
    if float(np.ptp(force_norms)) < 0.35:
        raise AssertionError("README force colorscale lacks a visible trajectory-wide range.")
    editor, page = open_scene(browser, frames, show_bonds=False, viz_only=True)
    try:
        set_display(page, {
            "atomRadiusScale": 0.46,
            "showBonds": False,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "lightingMode": "studio-shadow",
            "showForceVectors": True,
            "forceVectorStyle": "3d",
            "forceVectorScale": 3.4,
            "forceVectorThickness": 0.045,
            "forceVectorColor": "#db4b32",
        })
        configure_inspector(page, "structure", ["appearance"], width=475)
        result = page.evaluate(
            """async () => {
                await window.v_aseAI.apply({
                    operation: {
                        name: 'set-atom-colorscale',
                        enabled: true,
                        field: 'force:norm',
                        map: 'turbo',
                        scope: 'all',
                        rangeMode: 'trajectory',
                        gamma: 0.72
                    }
                });
                return await window.v_aseAI.describe({includePositions: false});
            }"""
        )
        color_scale = result["display"]
        if color_scale["atomColorScaleField"] != "force:norm":
            raise AssertionError("README colorscale did not select force magnitude.")
        if color_scale["atomColorScaleRangeMode"] != "trajectory":
            raise AssertionError("README colorscale did not lock a full-trajectory range.")
        if color_scale["atomColorScaleScope"] != "all":
            raise AssertionError("README colorscale did not apply to the complete structure.")
        page.wait_for_selector("#atom-colorscale-legend:not(.hidden)")
        page.wait_for_function(
            "count => window.__V_ASE_APP__.renderer.atomColorScaleColors?.filter(Boolean).length === count",
            arg=len(frames[0]),
        )
        page.wait_for_function(
            "count => Number(window.__V_ASE_APP__.renderer.domElement.dataset.forceVectorCount) === count",
            arg=len(frames[0]),
        )
        page.evaluate(
            """() => {
                const panel = document.querySelector('[data-panel="appearance"]');
                panel?.scrollIntoView({block: 'start'});
                document.getElementById('inspector-content').scrollTop = 0;
                window.__V_ASE_APP__.renderer.selectionOutlines.visible = false;
                const badge = document.createElement('div');
                badge.id = 'readme-force-contract';
                badge.textContent = '97 / 97 atoms mapped · ASE EMT force colors + vectors';
                Object.assign(badge.style, {
                    position: 'fixed', left: '34px', bottom: '38px', zIndex: '4000',
                    padding: '10px 15px', border: '2px solid #26383b', borderRadius: '5px',
                    background: 'rgba(255,255,255,.96)', color: '#1d2f32',
                    fontSize: '17px', fontWeight: '850', letterSpacing: '0'
                });
                document.body.appendChild(badge);
            }"""
        )
        center = np.mean(frames[0].positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([18.0, -24.0, 15.0])).tolist(),
            fov=34,
        )
        set_atomic_scale(page, 39.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.9,
            position_offset=(-12.0, -12.0, 18.0),
        )
        gif_frames = []
        ranges = []
        force_signatures = []
        for frame_index in range(len(frames)):
            page.evaluate(
                "async (index) => await window.__V_ASE_APP__.loadFrame(index)",
                frame_index,
            )
            page.wait_for_function(
                "index => window.__V_ASE_APP__.state.atoms.metadata.current_frame === index",
                arg=frame_index,
            )
            page.wait_for_timeout(55)
            page.evaluate("window.__V_ASE_APP__.renderer.selectionOutlines.visible = false")
            color_state = page.evaluate("""() => ({
                count: window.__V_ASE_APP__.renderer.atomColorScaleColors?.filter(Boolean).length,
                unique: new Set(window.__V_ASE_APP__.renderer.atomColorScaleColors || []).size
            })""")
            if color_state["count"] != len(frames[frame_index]) or color_state["unique"] < 6:
                raise AssertionError("README probe scan did not color every atom with a useful range.")
            ranges.append(page.evaluate(
                """() => [
                    window.__V_ASE_APP__.state.display.atomColorScaleMin,
                    window.__V_ASE_APP__.state.display.atomColorScaleMax
                ]"""
            ))
            force_snapshot = page.evaluate("""expectedForces => {
                const app = window.__V_ASE_APP__;
                const entries = app.renderer.forceVectorGroup.userData.entries || [];
                return {
                    alignments: entries.map(entry => {
                    const source = expectedForces[entry.index] || [0, 0, 0];
                    const direction = entry.vector || [0, 0, 0];
                    const sourceLength = Math.hypot(...source);
                    const directionLength = Math.hypot(...direction);
                    if (sourceLength <= 1e-12 || directionLength <= 1e-12) return 0;
                    return direction.reduce(
                        (sum, value, axis) => sum + value * source[axis],
                        0
                    ) / (sourceLength * directionLength);
                    }),
                    vectors: entries.map(entry => [entry.index, ...entry.vector])
                };
            }""", frames[frame_index].get_forces().tolist())
            if (
                len(force_snapshot["alignments"]) != len(frames[frame_index])
                or min(force_snapshot["alignments"]) < 1 - 1e-8
            ):
                raise AssertionError("README force arrows do not follow the stored Cartesian forces.")
            force_signatures.append(np.asarray(force_snapshot["vectors"], dtype=float))
            gif_frames.append(screenshot_frame(page))
        reference_range = np.asarray(ranges[0], dtype=float)
        if not all(np.allclose(np.asarray(item, dtype=float), reference_range) for item in ranges[1:]):
            raise AssertionError("README trajectory colorscale changed vmin/vmax between frames.")
        if not any(
            current.shape == force_signatures[0].shape
            and not np.allclose(current[:, 1:], force_signatures[0][:, 1:])
            for current in force_signatures[1:]
        ):
            raise AssertionError("README trajectory force arrows stayed fixed between frames.")
        save_gif(
            gif_frames + list(reversed(gif_frames[1:-1])),
            ASSET_DIR / "readme_atom_colorscale.gif",
            duration=230,
        )
        gif_frames[len(gif_frames) // 2].save(
            ASSET_DIR / "readme_atom_colorscale.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_rdf_media(browser) -> None:
    atoms = make_amorphous_cuzr_rdf_scene()
    editor, page = open_scene(browser, atoms, show_bonds=False)
    try:
        set_display(page, {
            "atomRadiusScale": 0.34,
            "showBonds": False,
            "showGrid": False,
            "showCell": True,
            "showAxes": False,
            "viewportBackground": "white",
            "lightingMode": "studio-shadow",
            "labelColors": {
                "Cu_glass": "#b66b36",
                "Zr_glass": "#63a5b5",
            },
            "labelMaterials": {
                "Cu_glass": "metal",
                "Zr_glass": "standard",
            },
        })
        configure_inspector(page, "analysis", ["rdf"], width=450)
        result = page.evaluate(
            """async () => {
                await window.v_aseAI.apply({
                    operation: {
                        name: 'calculate-rdf',
                        cutoff: 11.0,
                        bins: 180,
                        pairMode: 'all'
                    }
                });
                const rdf = window.__V_ASE_APP__.state.rdfResult;
                const tail = rdf.radius
                    .map((radius, index) => [radius, rdf.total[index]])
                    .filter(([radius]) => radius > 7.0)
                    .map(([, value]) => value);
                const mean = tail.reduce((sum, value) => sum + value, 0) / tail.length;
                const variance = tail.reduce(
                    (sum, value) => sum + (value - mean) ** 2,
                    0
                ) / tail.length;
                return {
                    mean,
                    standardDeviation: Math.sqrt(variance),
                    tailCount: tail.length,
                    partialNames: Object.keys(rdf.partial || {})
                };
            }"""
        )
        if abs(result["mean"] - 1.0) > 0.05 or result["standardDeviation"] > 0.08:
            raise AssertionError(
                "README amorphous RDF does not reach a flat bulk plateau."
            )
        if len(result["partialNames"]) < 3:
            raise AssertionError("README RDF does not show all pairwise curves.")
        page.wait_for_selector("#rdf-plot .plotly", state="attached")
        page.wait_for_selector(
            "#rdf-plot .annotation-text",
            state="attached",
        )
        page.evaluate(
            """() => {
                const drawer = document.getElementById('analysis-drawer');
                drawer.style.height = '390px';
                window.Plotly?.Plots?.resize?.(document.getElementById('rdf-plot'));
            }"""
        )
        center = np.mean(atoms.positions, axis=0)
        settle_view(
            page,
            target=center.tolist(),
            position=(center + np.array([37.0, -42.0, 34.0])).tolist(),
            fov=34,
        )
        set_atomic_scale(page, 23.0)
        set_readme_lighting(
            page,
            center.tolist(),
            intensity=2.9,
            position_offset=(-22.0, -25.0, 34.0),
        )
        page.wait_for_timeout(350)
        screenshot_frame(page).save(
            ASSET_DIR / "readme_rdf.png",
            optimize=True,
        )
    finally:
        page.close()
        editor.close()


def capture_analysis_media(browser) -> None:
    capture_registry_media(browser)
    capture_volumetric_media(browser)
    capture_atom_colorscale_media(browser)
    capture_rdf_media(browser)


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
            "registry",
            "bonds",
            "materials",
            "ai",
            "collaboration",
            "scratch",
            "add-atoms",
            "constraints",
            "measurement",
            "relaxation",
            "volumetric",
            "colorscale",
            "rdf",
            "analysis",
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
                "registry": capture_registry_media,
                "bonds": capture_bond_media,
                "materials": capture_material_media,
                "ai": capture_ai_edit_media,
                "collaboration": capture_ai_collaboration_figure,
                "scratch": _capture_scratch_amorphous_media,
                "add-atoms": capture_add_atoms_media,
                "constraints": capture_constraint_media,
                "measurement": capture_measurement_media,
                "relaxation": capture_relaxation_media,
                "volumetric": capture_volumetric_media,
                "colorscale": capture_atom_colorscale_media,
                "rdf": capture_rdf_media,
                "analysis": capture_analysis_media,
            }
            if args.only:
                captures[args.only](browser)
            else:
                for name, capture in captures.items():
                    if name == "analysis":
                        continue
                    capture(browser)
        finally:
            browser.close()
            webbrowser.open = original_open

    sync_github_readme_assets()
    print(f"Wrote README media to {ASSET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
