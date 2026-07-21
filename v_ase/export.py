from fastapi.responses import FileResponse
from typing import Dict, Any
from ase.io import write
import tempfile
import pickle
import numpy as np
from .serialization import atoms_to_json

def _apply_payload_positions(session, payload: Dict[str, Any]):
    if payload and "positions" in payload and not bool((session.config or {}).get("viz_only", False)):
        session.working_atoms.set_positions(
            np.array(payload["positions"]),
            apply_constraint=bool(payload.get("apply_constraint", True)),
        )
    return session.working_atoms
 
def _atoms_for_vasp_export(atoms):
    if atoms.cell.rank == 3:
        return atoms

    export_atoms = atoms.copy()
    export_atoms.calc = None
    export_atoms.center(vacuum=8.0)
    export_atoms.set_pbc([False, False, False])
    return export_atoms


def export_poscar_response(session, payload: Dict[str, Any]):
    atoms = _apply_payload_positions(session, payload)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vasp")
    tmp.close()
    write(tmp.name, _atoms_for_vasp_export(atoms), format="vasp")
    return FileResponse(tmp.name, filename="POSCAR", media_type="application/octet-stream")


def export_pickle_response(session, payload: Dict[str, Any]):
    _apply_payload_positions(session, payload)
    include_calc = payload.get("include_calculator", False)

    atoms_to_save = session.working_atoms.copy()
    if not include_calc:
        atoms_to_save.calc = None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pkl")
    tmp.close()
    try:
        with open(tmp.name, "wb") as handle:
            pickle.dump(atoms_to_save, handle)
    except Exception as exc:
        if include_calc:
            atoms_to_save.calc = None
            with open(tmp.name, "wb") as handle:
                pickle.dump(atoms_to_save, handle)
        else:
            raise exc
    return FileResponse(tmp.name, filename="atoms.pkl", media_type="application/octet-stream")


def _trajectory_frames_json(session):
    frames = getattr(session, "trajectory_frames", []) or []
    if len(frames) <= 1:
        return []
    return [atoms_to_json(frame) for frame in frames]


def _minimum_image_delta(delta, cell, pbc):
    delta = np.asarray(delta, dtype=float)
    if not any(pbc or []) or not cell:
        return delta
    matrix = np.asarray(cell, dtype=float)
    if matrix.shape != (3, 3) or abs(np.linalg.det(matrix)) < 1e-10:
        return delta
    try:
        fractional = np.linalg.solve(matrix.T, delta)
    except np.linalg.LinAlgError:
        return delta
    for axis, periodic in enumerate(pbc):
        if periodic:
            fractional[axis] -= np.round(fractional[axis])
    return matrix.T @ fractional


def _display_bonds(data: Dict[str, Any], display: Dict[str, Any], explicit_pairs=None):
    display = display or {}
    if display.get("showBonds") is False:
        return []

    positions = np.asarray(data.get("positions") or [], dtype=float)
    labels = list(data.get("symbols") or [])
    symbols = list(data.get("chemical_symbols") or labels)
    if len(positions) != len(symbols):
        return []
    if len(labels) != len(symbols):
        labels = symbols

    cell = data.get("cell") or []
    pbc = data.get("pbc") or [False, False, False]
    visual = data.get("visual") or {}
    covalent_source = visual.get("bond_radii") or visual.get("covalent_radii") or []
    covalent = [float(value) if value is not None else 0.75 for value in covalent_source]
    if len(covalent) < len(symbols):
        covalent.extend([0.75] * (len(symbols) - len(covalent)))
    vdw = []
    for value in visual.get("vdw_radii", []):
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = 0.0
        vdw.append(parsed if np.isfinite(parsed) and parsed > 0 else 0.0)
    if len(vdw) < len(symbols):
        vdw.extend([0.0] * (len(symbols) - len(vdw)))

    def pair_key(i, j):
        return "-".join(sorted((str(labels[i]), str(labels[j]))))

    def cutoff(i, j):
        if display.get("bondMode") == "element":
            element_cutoffs = display.get("elementBondCutoffs") or {}
            key = pair_key(i, j)
            if key not in element_cutoffs:
                return 0.0
            try:
                return max(0.0, float(element_cutoffs[key]))
            except (TypeError, ValueError):
                return 0.0
        scale = float(display.get("bondCutoffScale") or 1.0)
        if vdw[i] > 0 and vdw[j] > 0:
            return 0.6 * (vdw[i] + vdw[j]) * scale
        return (covalent[i] + covalent[j] + 0.4) * scale

    raw_pairs = explicit_pairs
    if not raw_pairs and display.get("bondMode") == "manual":
        raw_pairs = display.get("manualBondPairs") or []

    pairs = []
    include_periodic_images = bool(display.get("showPeriodicBonds"))

    def bond_delta(i, j):
        direct = positions[j] - positions[i]
        if include_periodic_images:
            return _minimum_image_delta(direct, cell, pbc)
        return direct

    if raw_pairs:
        for pair in raw_pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            i, j = int(pair[0]), int(pair[1])
            if 0 <= i < len(symbols) and 0 <= j < len(symbols) and i != j:
                pairs.append((min(i, j), max(i, j)))
    else:
        max_atoms = 3500
        if len(symbols) > max_atoms:
            return []
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                delta = bond_delta(i, j)
                if float(np.linalg.norm(delta)) <= cutoff(i, j):
                    pairs.append((i, j))

    seen = set()
    bonds = []
    for i, j in pairs:
        key = (i, j)
        if key in seen:
            continue
        seen.add(key)
        delta = bond_delta(i, j)
        bonds.append({
            "i": i,
            "j": j,
            "start": positions[i].tolist(),
            "end": (positions[i] + delta).tolist(),
            "length": float(np.linalg.norm(delta)),
        })
    return bonds


def _blender_script(data: Dict[str, Any]) -> str:
    return f'''# Generated by v_ase. Run in Blender with: blender --python this_file.py
import math
import bpy
from mathutils import Vector

DATA = {repr(data)}
FRAMES = DATA.get("frames", [])
CAMERA = DATA.get("camera", {{}})
BONDS = DATA.get("bonds", [])
CELL = DATA.get("cell", [])
DISPLAY = DATA.get("display", {{}})
LIGHTING = DATA.get("lighting", {{}})
BOND_STYLE = DISPLAY.get("bondStyle", "cylinder")
BOND_COLOR_MODE = DISPLAY.get("bondColorMode", "split")
BOND_CUSTOM_COLOR = DISPLAY.get("bondCustomColor", "#c8ccd0")
BLENDER_OBJECT_MODE = DISPLAY.get("blenderExportMode", "instanced")
try:
    BOND_THICKNESS = max(0.02, min(0.6, float(DISPLAY.get("bondThickness", 0.11))))
except (TypeError, ValueError):
    BOND_THICKNESS = 0.11

VISUAL = DATA.get("visual", {{}})
ATOM_COLORS = VISUAL.get("colors", [])
ATOM_RADII = VISUAL.get("radii", VISUAL.get("covalent_radii", []))
ATOM_LABELS = DATA.get("symbols", [])
DISPLAY_ELEMENT_COLORS = DISPLAY.get("elementColors", {{}})
DISPLAY_ELEMENT_RADII = DISPLAY.get("elementRadii", {{}})
DISPLAY_ELEMENT_VISIBLE = DISPLAY.get("elementVisible", {{}})
try:
    ATOM_RADIUS_SCALE = max(0.01, float(DISPLAY.get("atomRadiusScale", 1.0)))
except (TypeError, ValueError):
    ATOM_RADIUS_SCALE = 1.0
FALLBACK_COLOR = (0.8, 0.8, 0.8, 1.0)
FALLBACK_RADIUS = 0.7

def clamp01(value):
    return max(0.0, min(1.0, float(value)))

def hex_to_rgba(value):
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 6:
            try:
                return (
                    int(text[0:2], 16) / 255.0,
                    int(text[2:4], 16) / 255.0,
                    int(text[4:6], 16) / 255.0,
                    1.0,
                )
            except ValueError:
                pass
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (clamp01(value[0]), clamp01(value[1]), clamp01(value[2]), clamp01(value[3]) if len(value) > 3 else 1.0)
    return FALLBACK_COLOR

def get_atom_color(index):
    if 0 <= index < len(ATOM_LABELS):
        display_color = DISPLAY_ELEMENT_COLORS.get(ATOM_LABELS[index])
        if display_color:
            return hex_to_rgba(display_color)
    if 0 <= index < len(ATOM_COLORS):
        return hex_to_rgba(ATOM_COLORS[index])
    return FALLBACK_COLOR

def get_atom_radius(index, fallback=FALLBACK_RADIUS):
    if 0 <= index < len(ATOM_LABELS):
        try:
            display_radius = float(DISPLAY_ELEMENT_RADII.get(ATOM_LABELS[index], 0.0))
            if display_radius > 0:
                return display_radius * ATOM_RADIUS_SCALE
        except (TypeError, ValueError):
            pass
    if 0 <= index < len(ATOM_RADII):
        try:
            radius = float(ATOM_RADII[index])
            if radius > 0:
                return radius * ATOM_RADIUS_SCALE
        except (TypeError, ValueError):
            pass
    return fallback * ATOM_RADIUS_SCALE

def material(name, color, alpha=1.0):
    mat = bpy.data.materials.new(name)
    rgba = (clamp01(color[0]), clamp01(color[1]), clamp01(color[2]), clamp01(alpha))
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        base_color = bsdf.inputs.get("Base Color")
        if base_color is not None:
            base_color.default_value = rgba
        alpha_input = bsdf.inputs.get("Alpha")
        if alpha_input is not None:
            alpha_input.default_value = rgba[3]
        roughness = bsdf.inputs.get("Roughness")
        if roughness is not None:
            roughness.default_value = 0.42
    if alpha < 1.0:
        try:
            mat.surface_render_method = "DITHERED"
        except (AttributeError, TypeError, ValueError):
            try:
                mat.blend_method = "BLEND"
            except (AttributeError, TypeError, ValueError):
                pass
        if hasattr(mat, "show_transparent_back"):
            mat.show_transparent_back = True
    return mat

ATOM_MATS = {{}}
ATOM_MESHES = {{}}
BOND_MATS = {{}}
MAT_LINE = material("v_ase fixed line", (0.3, 0.8, 1.0, 0.55), 0.55)
MAT_PLANE = material("v_ase fixed plane", (0.25, 1.0, 0.78, 0.22), 0.22)
MAT_HOOKEAN = material("v_ase Hookean active spring", (1.0, 0.58, 0.18, 1.0), 1.0)
MAT_HOOKEAN_INACTIVE = material("v_ase Hookean inactive spring", (0.56, 0.72, 1.0, 0.48), 0.48)
MAT_HOOKEAN_GUIDE = material("v_ase Hookean threshold guide", (0.68, 0.76, 0.85, 0.42), 0.42)
MAT_HOOKEAN_HOOK = material("v_ase Hookean hook latch", (0.48, 0.72, 1.0, 0.86), 0.86)
MAT_HOOKEAN_SLACK = material("v_ase Hookean inactive gap", (0.72, 0.76, 0.85, 0.38), 0.38)
MAT_HOOKEAN_ACTIVE_MARKER = material("v_ase Hookean active marker", (0.22, 0.85, 0.59, 0.92), 0.92)
MAT_HOOKEAN_INACTIVE_MARKER = material("v_ase Hookean inactive marker", (0.46, 0.66, 1.0, 0.78), 0.78)
MAT_HOOKEAN_THRESHOLD_MARKER = material("v_ase Hookean threshold marker", (1.0, 0.82, 0.35, 0.9), 0.9)
MAT_BOND = material("v_ase custom bond", hex_to_rgba(BOND_CUSTOM_COLOR), 1.0)
MAT_CELL = material("v_ase unit cell", (0.92, 0.78, 0.34, 0.72), 0.72)

def get_bond_mat(index):
    color = get_atom_color(index)
    key = f"{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}"
    if key not in BOND_MATS:
        BOND_MATS[key] = material(f"v_ase atom-colored bond {{key}}", color, 1.0)
    return BOND_MATS[key]

def get_atom_mat(index, symbol):
    color = get_atom_color(index)
    key = f"{{symbol}}_{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}"
    if key not in ATOM_MATS:
        ATOM_MATS[key] = material(f"atom {{symbol}}", color, 1.0)
    return ATOM_MATS[key]

def get_atom_mesh(index, symbol):
    color = get_atom_color(index)
    radius = get_atom_radius(index)
    material_key = f"{{symbol}}_{{color[0]:.4f}}_{{color[1]:.4f}}_{{color[2]:.4f}}"
    mesh_key = f"r{{radius:.4f}}_{{material_key}}"
    if mesh_key not in ATOM_MESHES:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radius, location=(0, 0, 0))
        source = bpy.context.object
        source.name = f"v_ase_atom_mesh_source_{{mesh_key}}"
        mesh = source.data
        mesh.name = f"v_ase_atom_mesh_{{mesh_key}}"
        mesh.materials.append(get_atom_mat(index, symbol))
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        bpy.data.objects.remove(source, do_unlink=True)
        ATOM_MESHES[mesh_key] = mesh
    return ATOM_MESHES[mesh_key]

def safe_name(value):
    text = "".join(char if char.isalnum() or char in "_-" else "_" for char in str(value))
    return text[:48] or "type"

def geometry_node_group(name):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    if hasattr(group, "interface"):
        group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        group.inputs.new("NodeSocketGeometry", "Geometry")
        group.outputs.new("NodeSocketGeometry", "Geometry")
    return group

def add_instanced_atom_group(symbol, indices, positions):
    name = f"atoms_{{safe_name(symbol)}}"
    mesh = bpy.data.meshes.new(name + "_points")
    mesh.from_pydata([positions[index] for index in indices], [], [])
    mesh.update()
    atom_index = mesh.attributes.new("atom_index", "INT", "POINT")
    atom_index.data.foreach_set("value", indices)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj["v_ase_atom_group"] = True
    obj["v_ase_label"] = str(symbol)
    obj["v_ase_atom_count"] = len(indices)
    if DISPLAY_ELEMENT_VISIBLE.get(symbol) is False:
        obj.hide_viewport = True
        obj.hide_render = True

    group = geometry_node_group(name + "_instances")
    nodes = group.nodes
    links = group.links
    node_in = nodes.new("NodeGroupInput")
    node_out = nodes.new("NodeGroupOutput")
    sphere = nodes.new("GeometryNodeMeshIcoSphere")
    set_material = nodes.new("GeometryNodeSetMaterial")
    shade_smooth = nodes.new("GeometryNodeSetShadeSmooth")
    instances = nodes.new("GeometryNodeInstanceOnPoints")
    quality = str(DISPLAY.get("sphereQuality", "auto"))
    subdivisions = {{"low": 1, "medium": 2, "high": 3, "ultra": 4, "auto": 3}}.get(quality, 3)
    sphere.inputs["Radius"].default_value = get_atom_radius(indices[0])
    sphere.inputs["Subdivisions"].default_value = subdivisions
    set_material.inputs["Material"].default_value = get_atom_mat(indices[0], symbol)
    if "Shade Smooth" in shade_smooth.inputs:
        shade_smooth.inputs["Shade Smooth"].default_value = True
    links.new(node_in.outputs["Geometry"], instances.inputs["Points"])
    links.new(sphere.outputs["Mesh"], set_material.inputs["Geometry"])
    links.new(set_material.outputs["Geometry"], shade_smooth.inputs["Geometry"])
    links.new(shade_smooth.outputs["Geometry"], instances.inputs["Instance"])
    links.new(instances.outputs["Instances"], node_out.inputs["Geometry"])
    modifier = obj.modifiers.new("v_ase atom instances", "NODES")
    modifier.node_group = group
    return obj, list(indices)

def add_instanced_atoms(positions, symbols):
    grouped = {{}}
    for index, symbol in enumerate(symbols):
        color = get_atom_color(index)
        radius = get_atom_radius(index)
        key = (str(symbol), round(radius, 6), tuple(round(value, 6) for value in color[:3]))
        grouped.setdefault(key, []).append(index)
    groups = []
    for (symbol, _radius, _color), indices in grouped.items():
        groups.append(add_instanced_atom_group(symbol, indices, positions))
    return groups

def animation_fcurves(animated_data):
    animation_data = getattr(animated_data, "animation_data", None)
    action = getattr(animation_data, "action", None)
    if action is None:
        return []
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    slot = getattr(animation_data, "action_slot", None)
    curves = []
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            channelbag = None
            for method_name in ("channelbag", "channelbag_for_slot"):
                method = getattr(strip, method_name, None)
                if method is None or slot is None:
                    continue
                try:
                    channelbag = method(slot)
                    break
                except (RuntimeError, TypeError, ValueError):
                    continue
            if channelbag is not None:
                curves.extend(list(getattr(channelbag, "fcurves", [])))
    return curves

def add_group_trajectory_shape_keys(groups, frames):
    if len(frames) <= 1:
        return
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = len(frames)
    for obj, indices in groups:
        obj.shape_key_add(name="Basis")
        for frame_number, frame_data in enumerate(frames, start=1):
            key = obj.shape_key_add(name=f"frame_{{frame_number:05d}}")
            coordinates = []
            for atom_index in indices:
                coordinates.extend(frame_data["positions"][atom_index])
            key.data.foreach_set("co", coordinates)
            if frame_number > 1:
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=frame_number - 1)
            key.value = 1.0
            key.keyframe_insert(data_path="value", frame=frame_number)
            if frame_number < len(frames):
                key.value = 0.0
                key.keyframe_insert(data_path="value", frame=frame_number + 1)
            key.value = 0.0
        if obj.data.shape_keys:
            for fcurve in animation_fcurves(obj.data.shape_keys):
                for point in fcurve.keyframe_points:
                    point.interpolation = "LINEAR"

def look_at_axis(obj, direction):
    direction = Vector(direction)
    if direction.length == 0:
        return
    quat = direction.to_track_quat("Z", "Y")
    obj.rotation_euler = quat.to_euler()

def look_at_camera(obj, target):
    direction = Vector(target) - obj.location
    if direction.length == 0:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def add_scene_camera():
    position = CAMERA.get("position")
    target = CAMERA.get("target")
    if isinstance(position, (list, tuple)) and len(position) == 3 and isinstance(target, (list, tuple)) and len(target) == 3:
        bpy.ops.object.camera_add(location=position)
        obj = bpy.context.object
        obj.name = "v_ase_view_camera"
        look_at_camera(obj, target)
        try:
            if CAMERA.get("projection") == "orthographic":
                obj.data.type = "ORTHO"
                obj.data.ortho_scale = max(0.1, float(CAMERA.get("ortho_scale") or 10.0))
            else:
                obj.data.angle = math.radians(float(CAMERA.get("fov", 50.0)))
        except (TypeError, ValueError):
            pass
        try:
            obj.data.clip_start = max(0.001, float(CAMERA.get("near", obj.data.clip_start)))
            obj.data.clip_end = max(obj.data.clip_start + 1.0, float(CAMERA.get("far", obj.data.clip_end)))
        except (TypeError, ValueError):
            pass
        bpy.context.scene.camera = obj
        return obj

    bpy.ops.object.camera_add(location=(8, -9, 6), rotation=(math.radians(60), 0, math.radians(42)))
    obj = bpy.context.object
    obj.name = "v_ase_view_camera"
    bpy.context.scene.camera = obj
    return obj

def add_scene_lighting():
    mode = LIGHTING.get("mode", DISPLAY.get("lightingMode", "modeling"))
    if mode in ("studio", "studio-shadow"):
        position = LIGHTING.get("position", DISPLAY.get("sunPosition", (8, -10, 14)))
        target = LIGHTING.get("target", DISPLAY.get("sunTarget", (0, 0, 0)))
        color = LIGHTING.get("color", (1.0, 0.960784, 0.87451))
        try:
            intensity = max(0.0, float(LIGHTING.get("intensity", DISPLAY.get("sunIntensity", 2.2))))
        except (TypeError, ValueError):
            intensity = 2.2
        try:
            position = Vector(position)
            target = Vector(target)
        except Exception:
            position = Vector((8, -10, 14))
            target = Vector((0, 0, 0))

        source = bpy.data.objects.new("v_ase_sun_source", None)
        source.empty_display_type = "CIRCLE"
        source.empty_display_size = 0.45
        source.location = position
        source["v_ase_role"] = "sun_source"
        bpy.context.collection.objects.link(source)

        target_handle = bpy.data.objects.new("v_ase_sun_target", None)
        target_handle.empty_display_type = "SPHERE"
        target_handle.empty_display_size = 0.32
        target_handle.location = target
        target_handle["v_ase_role"] = "sun_target"
        bpy.context.collection.objects.link(target_handle)

        light_data = bpy.data.lights.new("v_ase_studio_sun_data", type="SUN")
        obj = bpy.data.objects.new("v_ase_studio_sun", light_data)
        bpy.context.collection.objects.link(obj)
        obj.parent = source
        obj.location = (0, 0, 0)
        obj.data.energy = intensity
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            obj.data.color = tuple(clamp01(value) for value in color[:3])
        direction = target - position
        if direction.length <= 1e-10:
            direction = Vector((0, 0, -1))
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        track = obj.constraints.new(type="TRACK_TO")
        track.name = "Aim at v_ase target"
        track.target = target_handle
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        obj["v_ase_mode"] = mode
        obj["v_ase_target"] = target[:]
        obj["v_ase_direction"] = direction.normalized()[:]
        obj["v_ase_intensity"] = intensity
        if hasattr(obj.data, "angle"):
            obj.data.angle = math.radians(2.0 if mode == "studio-shadow" else 0.5)

        world = bpy.context.scene.world
        if world is not None:
            world.use_nodes = True
            background = world.node_tree.nodes.get("Background")
            if background is not None:
                background.inputs["Color"].default_value = (0.075, 0.085, 0.095, 1.0)
                background.inputs["Strength"].default_value = 0.24
        return obj

    bpy.ops.object.light_add(type="AREA", location=(5, -6, 8))
    obj = bpy.context.object
    obj.name = "v_ase_area_light"
    obj.data.energy = 450
    obj.data.size = 5
    return obj

def add_cylinder_between(name, start, end, radius, mat):
    start = Vector(start); end = Vector(end)
    mid = (start + end) * 0.5
    length = (end - start).length
    if length <= 1e-8:
        return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, end - start)
    obj.data.materials.append(mat)
    return obj

def add_flat_between(name, start, end, width, mat):
    start = Vector(start); end = Vector(end)
    axis = end - start
    length = axis.length
    if length <= 1e-8:
        return None
    direction = axis.normalized()
    camera_position = CAMERA.get("position", (8, -9, 6))
    camera_target = CAMERA.get("target", (0, 0, 0))
    view = Vector(camera_target) - Vector(camera_position)
    side = direction.cross(view)
    if side.length <= 1e-8:
        side = direction.cross(Vector((0, 0, 1)))
    if side.length <= 1e-8:
        side = direction.cross(Vector((0, 1, 0)))
    side.normalize()
    half = side * (width * 0.5)
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([start - half, end - half, end + half, start + half], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_bond_piece(name, start, end, mat):
    if BOND_STYLE == "flat":
        return add_flat_between(name, start, end, BOND_THICKNESS, mat)
    return add_cylinder_between(name, start, end, BOND_THICKNESS * 0.5, mat)

def add_curve_segments(name, segments, radius, mat):
    if not segments:
        return None
    curve = bpy.data.curves.new(name + "_curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = radius
    curve.bevel_resolution = 1
    curve.resolution_v = 0
    curve.fill_mode = "FULL"
    for start, end in segments:
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (*Vector(start), 1.0)
        spline.points[1].co = (*Vector(end), 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_flat_segments(name, segments, width, mat):
    if not segments:
        return None
    vertices = []
    faces = []
    camera_position = Vector(CAMERA.get("position", (8, -9, 6)))
    camera_target = Vector(CAMERA.get("target", (0, 0, 0)))
    view = camera_target - camera_position
    for start_value, end_value in segments:
        start = Vector(start_value); end = Vector(end_value)
        axis = end - start
        if axis.length <= 1e-8:
            continue
        direction = axis.normalized()
        side = direction.cross(view)
        if side.length <= 1e-8:
            side = direction.cross(Vector((0, 0, 1)))
        if side.length <= 1e-8:
            side = direction.cross(Vector((0, 1, 0)))
        side.normalize()
        half = side * (width * 0.5)
        offset = len(vertices)
        vertices.extend([start - half, end - half, end + half, start + half])
        faces.append((offset, offset + 1, offset + 2, offset + 3))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_bond_groups(bonds):
    grouped = {{}}
    for bond_index, bond in enumerate(bonds):
        i = int(bond.get("i", 0)); j = int(bond.get("j", 0))
        start = Vector(bond.get("start")); end = Vector(bond.get("end"))
        pieces = []
        if BOND_COLOR_MODE == "split":
            midpoint = (start + end) * 0.5
            pieces = [(start, midpoint, get_bond_mat(i)), (midpoint, end, get_bond_mat(j))]
        else:
            pieces = [(start, end, MAT_BOND)]
        for piece_start, piece_end, mat in pieces:
            grouped.setdefault(mat.name, {{"material": mat, "segments": []}})["segments"].append((piece_start, piece_end))
    for group_index, item in enumerate(grouped.values()):
        name = f"bond_group_{{group_index:03d}}"
        if BOND_STYLE == "flat":
            add_flat_segments(name, item["segments"], BOND_THICKNESS, item["material"])
        else:
            add_curve_segments(name, item["segments"], BOND_THICKNESS * 0.5, item["material"])

def add_unit_cell(cell):
    if not isinstance(cell, (list, tuple)) or len(cell) != 3:
        return
    try:
        a, b, c = [Vector(v) for v in cell]
    except Exception:
        return
    corners = [
        Vector((0, 0, 0)),
        a,
        b,
        c,
        a + b,
        a + c,
        b + c,
        a + b + c,
    ]
    edges = [
        (0, 1), (0, 2), (0, 3),
        (1, 4), (1, 5),
        (2, 4), (2, 6),
        (3, 5), (3, 6),
        (4, 7), (5, 7), (6, 7),
    ]
    add_curve_segments("unit_cell_edges", [(corners[i], corners[j]) for i, j in edges], 0.026, MAT_CELL)

def add_plane_disc(name, center, normal, radius, mat):
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius, fill_type="TRIFAN", location=center)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, normal)
    obj.data.materials.append(mat)
    return obj

def add_poly_curve(name, points, mat, bevel=0.025):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = bevel
    poly = curve.splines.new("POLY")
    poly.points.add(len(points) - 1)
    for idx, p in enumerate(points):
        poly.points[idx].co = (p.x, p.y, p.z, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj

def add_ring(name, center, direction, radius, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=radius * 0.12, major_segments=48, minor_segments=8, location=center)
    obj = bpy.context.object
    obj.name = name
    look_at_axis(obj, direction)
    obj.data.materials.append(mat)
    return obj

def hookean_state(length, threshold):
    if threshold is None or threshold <= 0:
        return "active"
    if abs(length - threshold) <= max(0.035, threshold * 0.025):
        return "threshold"
    return "inactive" if length < threshold else "active"

def hookean_marker_material(state):
    if state == "active":
        return MAT_HOOKEAN_ACTIVE_MARKER
    if state == "threshold":
        return MAT_HOOKEAN_THRESHOLD_MARKER
    return MAT_HOOKEAN_INACTIVE_MARKER

def add_hookean_spring(name, start, end, threshold=None, radius_start=0.7, radius_end=0.7):
    start = Vector(start); end = Vector(end)
    axis = end - start
    length = axis.length
    if length <= 1e-8:
        return None
    direction = axis.normalized()
    helper = direction.cross(Vector((0, 0, 1)))
    if helper.length < 1e-6:
        helper = direction.cross(Vector((0, 1, 0)))
    u = helper.normalized()
    v = direction.cross(u).normalized()
    center = (start + end) * 0.5

    def to_world(x, y, z=0.0):
        return center + direction * y + u * x + v * z

    left_center = -length / 2
    right_center = length / 2
    left = left_center + min(radius_start * 0.55 + 0.04, length * 0.24)
    right = right_center - min(radius_end * 0.55 + 0.04, length * 0.24)
    span = max(0.12, abs(right - left))
    state = hookean_state(length, threshold)
    gate_width = max(0.12, min(span * 0.09, 0.28))
    lock_half = max(0.08, min(span * 0.045, 0.18))
    threshold_y = left_center + threshold if threshold and threshold > 0 else left + span * 0.52
    spring_start = threshold_y
    spring_end = right
    spring_len = max(0.001, spring_end - spring_start)
    amplitude = min(0.16, span * 0.08)
    coils = max(6, round(5 + spring_len * 2.2))
    steps = max(8, coils * 2)

    add_poly_curve(name + "_dead_zone_rail", [
        to_world(0, left, 0),
        to_world(0, threshold_y, 0),
    ], MAT_HOOKEAN_GUIDE, bevel=0.018)

    add_poly_curve(name + "_cutoff_gate", [
        to_world(-gate_width, threshold_y, 0),
        to_world(gate_width, threshold_y, 0),
    ], hookean_marker_material(state), bevel=0.024 if state == "inactive" else 0.034)

    if state != "inactive":
        add_poly_curve(name + "_lock_pin", [
            to_world(0, threshold_y - lock_half, 0),
            to_world(0, threshold_y + lock_half, 0),
        ], hookean_marker_material(state), bevel=0.034)

    if state != "inactive" and spring_end > spring_start:
        spring_points = [to_world(0, spring_start, 0)]
        for step in range(1, steps):
            t = step / steps
            x = amplitude if step % 2 else -amplitude
            spring_points.append(to_world(x, spring_start + (spring_end - spring_start) * t, 0))
        spring_points.append(to_world(0, spring_end, 0))
        add_poly_curve(name + "_spring", spring_points, MAT_HOOKEAN)

    if state == "inactive" and threshold_y > right:
        add_poly_curve(name + "_inactive_gap", [to_world(0, right, 0), to_world(0, threshold_y, 0)], MAT_HOOKEAN_SLACK, bevel=0.015)
    return None

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete()

scene = bpy.context.scene
for render_engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scene.render.engine = render_engine
        break
    except (TypeError, ValueError):
        continue
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except (TypeError, ValueError):
    pass

positions = DATA["positions"]
symbols = DATA["symbols"]
atoms = []
atom_groups = []
if BLENDER_OBJECT_MODE == "objects":
    for idx, (symbol, pos) in enumerate(zip(symbols, positions)):
        obj = bpy.data.objects.new(f"atom_{{idx:04d}}_{{symbol}}", get_atom_mesh(idx, symbol))
        obj.name = f"atom_{{idx:04d}}_{{symbol}}"
        obj.location = pos
        obj["v_ase_atom_index"] = idx
        if DISPLAY_ELEMENT_VISIBLE.get(symbol) is False:
            obj.hide_viewport = True
            obj.hide_render = True
        bpy.context.collection.objects.link(obj)
        atoms.append(obj)
else:
    atom_groups = add_instanced_atoms(positions, symbols)

add_unit_cell(CELL)

if BLENDER_OBJECT_MODE == "objects":
    for bond_index, bond in enumerate(BONDS):
        i = int(bond.get("i", 0)); j = int(bond.get("j", 0))
        start = Vector(bond.get("start")); end = Vector(bond.get("end"))
        name = f"bond_{{i}}_{{j}}_{{bond_index:04d}}"
        if BOND_COLOR_MODE == "split":
            midpoint = (start + end) * 0.5
            add_bond_piece(name + "_start", start, midpoint, get_bond_mat(i))
            add_bond_piece(name + "_end", midpoint, end, get_bond_mat(j))
        else:
            add_bond_piece(name, start, end, MAT_BOND)
else:
    add_bond_groups(BONDS)

def frame_topology_matches(frame_data):
    return (
        frame_data.get("symbols") == symbols
        and len(frame_data.get("positions", [])) == len(symbols)
    )

if len(FRAMES) > 1 and all(frame_topology_matches(frame) for frame in FRAMES):
    if BLENDER_OBJECT_MODE == "objects":
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = len(FRAMES)
        for frame_number, frame_data in enumerate(FRAMES, start=1):
            for idx, obj in enumerate(atoms):
                obj.location = frame_data["positions"][idx]
                obj.keyframe_insert(data_path="location", frame=frame_number)
        for obj in atoms:
            for fcurve in animation_fcurves(obj):
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = "LINEAR"
    else:
        add_group_trajectory_shape_keys(atom_groups, FRAMES)

constraints = DATA.get("constraints", {{}})
for idx_text, direction in constraints.get("fixed_line", {{}}).items():
    idx = int(idx_text)
    start = Vector(positions[idx]) - Vector(direction).normalized() * 2.2
    end = Vector(positions[idx]) + Vector(direction).normalized() * 2.2
    add_cylinder_between(f"fixed_line_{{idx}}", start, end, 0.035, MAT_LINE)

for idx_text, normal in constraints.get("fixed_plane", {{}}).items():
    idx = int(idx_text)
    add_plane_disc(f"fixed_plane_{{idx}}", positions[idx], normal, 1.6, MAT_PLANE)

for item in constraints.get("hookean", []):
    if item.get("kind") == "two atoms":
        i, j = item["indices"]
        add_hookean_spring(
            f"hookean_{{i}}_{{j}}",
            positions[i],
            positions[j],
            threshold=item.get("threshold"),
            radius_start=get_atom_radius(i),
            radius_end=get_atom_radius(j),
        )
    elif item.get("kind") == "point":
        idx = item["index"]
        add_hookean_spring(
            f"hookean_{{idx}}_point",
            positions[idx],
            item["origin"],
            threshold=item.get("threshold"),
            radius_start=get_atom_radius(idx),
            radius_end=0.18,
        )
    elif item.get("kind") == "plane":
        idx = item["index"]
        A, B, C, D = item["plane"]
        normal = Vector((A, B, C))
        pos = Vector(positions[idx])
        signed = (A * pos.x + B * pos.y + C * pos.z + D) / max(normal.length, 1e-9)
        center = pos - normal.normalized() * signed
        add_plane_disc(f"hookean_plane_{{idx}}", center, normal, 1.25, MAT_PLANE)
        add_hookean_spring(
            f"hookean_{{idx}}_plane_spring",
            pos,
            center,
            threshold=None,
            radius_start=get_atom_radius(idx),
            radius_end=0.18,
        )

add_scene_lighting()
add_scene_camera()
'''


def export_blender_response(session, payload: Dict[str, Any]):
    atoms = _apply_payload_positions(session, payload)
    if getattr(session, "trajectory_frames", None):
        session.sync_current_frame()
    data = atoms_to_json(atoms)
    frames = _trajectory_frames_json(session)
    if frames:
        data["frames"] = frames
    display = payload.get("display") or {}
    if display:
        data["display"] = display
    lighting = payload.get("lighting") or {
        "mode": display.get("lightingMode", "modeling"),
        "intensity": display.get("sunIntensity", 2.2),
        "position": display.get("sunPosition", [8, -10, 14]),
        "target": display.get("sunTarget", [0, 0, 0]),
        "color": [1.0, 0.960784, 0.87451],
    }
    data["lighting"] = lighting
    data["bonds"] = _display_bonds(data, display, payload.get("bond_pairs"))
    if payload.get("camera"):
        data["camera"] = payload["camera"]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_v_ase_blender.py", mode="w", encoding="utf-8")
    tmp.write(_blender_script(data))
    tmp.close()
    return FileResponse(tmp.name, filename="v_ase_blender_scene.py", media_type="text/x-python")
