"""Bounded scene inspection and visual transactions, shared by every adapter."""
from copy import deepcopy


def object_schema(properties, required=()):
    return {"type": "object", "properties": deepcopy(properties),
            "required": list(required), "additionalProperties": False}


SCENE_SNAPSHOT_PROPERTIES = {
    "sections": {"type": "array", "items": {"enum": ["atoms", "bonds", "planes", "analysis", "preview", "polyhedra"]},
                 "uniqueItems": True, "default": [],
                 "description": "Summary is always returned. Request geometry only to identify atoms/edges; no voxel or trajectory arrays are returned."},
    "elements": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
    "labels": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
    "indices": {"type": "array", "items": {"type": "integer", "minimum": 0}, "uniqueItems": True},
    "visibleOnly": {"type": "boolean", "default": True,
                    "description": "Filter by visibility settings and intersection with the camera frustum. Occlusion by other surfaces is not inferred."},
    "limit": {"type": "integer", "minimum": 1, "maximum": 256, "default": 64},
    "atomOffset": {"type": "integer", "minimum": 0, "default": 0},
    "bondOffset": {"type": "integer", "minimum": 0, "default": 0},
    "polyhedronOffset": {"type": "integer", "minimum": 0, "default": 0},
    "planeOffset": {"type": "integer", "minimum": 0, "default": 0},
    "previewOffset": {"type": "integer", "minimum": 0, "default": 0},
    "previewBondOffset": {"type": "integer", "minimum": 0, "default": 0},
    "components": {"type": "array", "items": {"enum": ["host", "guest", "lattice"]}, "uniqueItems": True,
                   "description": "Optional component filter for commensurate preview rows."},
    "expectedSceneFingerprint": {"type": "string", "description": "Use the first page's fingerprint to reject pagination after the scene changes."},
    "width": {"type": "integer", "minimum": 64, "maximum": 8192},
    "height": {"type": "integer", "minimum": 64, "maximum": 8192},
    "cameraSource": {"enum": ["auto", "viewport", "render-area", "image-export"], "default": "auto"},
    "wait": {"type": "boolean", "default": True},
    "timeoutMs": {"type": "integer", "minimum": 1, "maximum": 30000, "default": 15000},
}

PLANE_SELECTION_SCHEMA = object_schema({
    "planeIds": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True},
    "clearAtoms": {"type": "boolean", "default": False,
                   "description": "Also clear atoms when deselecting planes. Selecting nonempty plane IDs always clears atom selection and the light handle, following GUI rules."},
    "clearGizmos": {"type": "boolean", "default": False},
}, ["planeIds"])


def install_scene_contracts(control, operations, queries, render_parameters):
    """Called after the display schema is complete; no circular imports."""
    control["properties"]["requestId"] = {
        "type": "string", "minLength": 1, "maxLength": 128,
        "description": "Optional retry key. Reuse only with identical arguments after an uncertain reply. This live document retains up to 128 keyed receipts within 8 MiB; restart/reload/eviction ends retention. Large replay responses are compact receipts.",
    }
    patch = object_schema({
        key: control["properties"][key]
        for key in ("frame", "display", "quality", "camera", "renderArea", "selection")
    })
    patch["minProperties"] = 1
    patch["properties"]["planeSelection"] = PLANE_SELECTION_SCHEMA
    patch["properties"]["clearSelections"] = {"type": "boolean",
        "description": "Clear atom/replica/plane selection and light/render-area handles without deleting scene objects."}
    props = {
        "patch": patch,
        "mapMode": {"enum": ["merge", "replace"], "default": "merge",
                    "description": "Merge supplied label/atom/pair override maps by default. Arrays, including manualBondPairs and volumetricPlanes, are explicit replacements. replace replaces only maps actually supplied."},
        "timeoutMs": {"type": "integer", "minimum": 1, "maximum": 30000, "default": 15000},
    }
    operation = control["properties"]["operation"]["oneOf"][1]
    for name, fields, required, note in [
        ("apply-scene", props, ["patch"],
         "Apply one visual/frame transaction without changing stored scientific data. Requires document and revision guards. Unmentioned fields survive; background rendering settles before success. On failure restore the previous visual/frame state and report the rollback outcome. Returns a bounded change receipt, not the full scene. Physical edits use their dedicated tools."),
        ("select-volumetric-planes", PLANE_SELECTION_SCHEMA["properties"], ["planeIds"],
         "Select the exact plane IDs, or [] to clear plane selection. Optional clearAtoms/clearGizmos clear the other selection types. This changes interaction state only, never plane geometry or scientific arrays."),
    ]:
        operations[name] = {"mode": "view-or-edit", "required": required,
                            "optional": [key for key in fields if key not in required], "notes": note}
        operation["properties"]["name"]["enum"].append(name)
        operation["allOf"].append({"if": {"required": ["name"], "properties": {"name": {"const": name}}},
                                   "then": {"properties": deepcopy(fields), "required": required}})
    queries["scene-snapshot"] = {"description": "Inspect the actual rendered scene: camera/crop, interaction state and readiness. Add bounded geometry sections for renderer-resolved atom positions, periodic references and per-edge appearance. Start with the default summary for simple display edits.",
                                 "properties": deepcopy(SCENE_SNAPSHOT_PROPERTIES)}
    queries["scene-readiness"] = {"description": "Wait for frame, surface, plane, scalar-color and vector rendering to settle; reports pending work and errors without images.",
                                  "properties": {key: deepcopy(SCENE_SNAPSHOT_PROPERTIES[key]) for key in ("wait", "timeoutMs")}}
    render_parameters["option_fields"].extend(["selectionAppearance", "includePlaneBorders"])
    render_parameters["notes"] += " Publication selectionAppearance (default) suppresses selection highlights and uses neutral plane borders without changing live selection. interactive preserves selection appearance; includePlaneBorders=false omits only plane perimeters."


def scene_validation_schema(control):
    """JSON validator endpoint used by the JS mirror before a scene mutation."""
    branches = control["properties"]["operation"]["oneOf"][1]["allOf"]
    fields = next(branch["then"]["properties"] for branch in branches
                  if branch["if"]["properties"]["name"].get("const") == "apply-scene")
    return object_schema(fields, ["patch"])
