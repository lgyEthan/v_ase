"""Vendor-neutral typed tools over the shared, revisioned live document.

This module needs no MCP or model SDK. Schemas come from ``ai_schema``;
``FunctionTools`` supplies definitions and executes native function calls.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from functools import lru_cache
import time
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote_to_bytes, urlsplit
import uuid

import requests
from jsonschema import Draft202012Validator

from .ai_discovery import (SEARCH_PROPERTIES, TOOL_SCHEMA_PROPERTIES, GUIDE_PROPERTIES, CORE_TOOL_NAMES,
                           GROUP_DESCRIPTIONS, tool_group, search_catalog, read_guide)

from .ai_schema import (
    AI_CONTROL_SCHEMA, AI_DESCRIBE_PROFILES, AI_EXPORT_PARAMETERS, AI_QUERY_SCHEMAS,
    AI_OPERATION_PARAMETERS, AI_RENDER_PARAMETERS, BOOLEAN, INDEX, INDICES,
    NUMBER, PAIR_CUTOFFS, RDF_PROPERTIES, STRING, VECTOR, _ai_operation_schema,
)


def _object(properties=None, required=()):
    return {"type": "object", "properties": deepcopy(properties or {}),
            "required": list(required), "additionalProperties": False}


def _snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _flatten(schema):
    """Merge conjunctive object fragments without dropping their constraints."""
    result = deepcopy(schema)
    branches = result.pop("allOf", [])
    rest = []
    for branch in branches:
        branch = _flatten(branch)
        result.setdefault("properties", {}).update(branch.pop("properties", {}))
        required = branch.pop("required", [])
        if required:
            result["required"] = list(dict.fromkeys(result.get("required", []) + required))
        if branch:
            rest.append(branch)
    if rest:
        result["allOf"] = rest
    return result


def _tool_schema(schema):
    """Use snake_case for declared fields; preserve user-defined map keys."""
    if isinstance(schema, list):
        return [_tool_schema(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key in {"$schema", "$id", "title"}:
            continue
        if key == "properties":
            result[key] = {_snake(k): _tool_schema(v) for k, v in value.items()}
        elif key == "required":
            result[key] = [_snake(k) for k in value]
        elif key in {"items", "prefixItems", "anyOf", "oneOf", "allOf", "if", "then", "else", "not", "additionalProperties"}:
            result[key] = _tool_schema(value)
        else:
            result[key] = deepcopy(value)
    if result.get("type") == "object" and "properties" in result:
        result.setdefault("additionalProperties", False)
    return result


def _backend_arguments(value, schema):
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for branch in schema.get("allOf", []):
            props = {**props, **branch.get("properties", {})}
        names = {_snake(k): k for k in props}
        extra = schema.get("additionalProperties", {})
        return {names.get(k, k): _backend_arguments(v, props.get(names.get(k, k), extra if isinstance(extra, dict) else {}))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_backend_arguments(v, schema.get("items", {})) for v in value]
    # Find object alternatives (e.g. image options and explicit pivots).
    return value


DESTRUCTIVE_OPERATIONS = {
    "delete-selection", "set-identity", "set-constraints", "wrap", "translate-all",
    "set-unit-cell", "build-bulk", "set-supercell", "make-supercell",
    "move-selection", "rotate-selection", "scale-selection", "rotate-to-commensurate",
    "apply-commensurate-cell", "undo", "redo", "reset-coordinates",
    "start-relaxation", "relax-added-atoms", "run-registry-relaxation",
    "set-registry-translation", "cancel-registry-relaxation", "cancel-add-atoms",
    "clear-relaxation-trajectory", "exit-relaxation-mode", "load-structure",
    "remove-volumetric", "restore-app-visual-defaults",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict
    method: str
    operation: str | None = None
    field: str | None = None
    export_format: str | None = None
    mutates: bool = False

    @property
    def input_schema(self):
        return _tool_schema(self.schema)

    def definition(self):
        writes = self.mutates or self.method in {"render", "export"}
        return {"name": self.name, "description": self.description,
                "inputSchema": self.input_schema,
                "annotations": {"readOnlyHint": not writes,
                                "destructiveHint": self.operation in DESTRUCTIVE_OPERATIONS,
                                "idempotentHint": not writes,
                                "openWorldHint": False}}


GUARDS = {
    "expectedRevision": {**AI_CONTROL_SCHEMA["properties"]["expectedRevision"],
                         "description": "Required revision from the last describe. On conflict, re-read and review the human edit; never force a retry."},
    "expectedDocumentId": {**AI_CONTROL_SCHEMA["properties"]["expectedDocumentId"],
                           "description": "Required documentId from describe. Protects against a human switching tabs."},
    "responseProfile": AI_CONTROL_SCHEMA["properties"]["responseProfile"],
    "requestId": AI_CONTROL_SCHEMA["properties"]["requestId"],
}
GUARD_REQUIRED = ["expectedRevision", "expectedDocumentId"]
INTERRUPT_OPERATIONS = {"stop-relaxation", "stop-added-atoms", "stop-registry-relaxation"}
CAMERA_SCHEMA = AI_CONTROL_SCHEMA["properties"]["renderArea"]["properties"]["camera"]
RENDER_OPTIONS = _object({
    **{k: BOOLEAN for k in ("transparentBackground", "includeGrid", "includeAxes", "includeCell", "includePlaneBorders")},
    "selectionAppearance": {"enum": ["publication", "interactive"], "default": "publication"},
    "backgroundColor": STRING, "scaleMode": {"enum": ["viewport", "physical"]},
    "pixelsPerAngstrom": {"type": "number", "exclusiveMinimum": 0},
    "sphereQuality": {"enum": ["viewport", "auto", "low", "medium", "high", "ultra"]},
    "sphereQualityScale": {"type": "number", "exclusiveMinimum": 0},
    "renderMode": {"enum": ["modeling", "studio", "studio-shadow"]},
    "sunIntensity": {"type": "number", "minimum": 0},
    "sunPosition": VECTOR, "sunTarget": VECTOR, "camera": CAMERA_SCHEMA,
})
RENDER_PROPERTIES = {
    "format": {"enum": AI_RENDER_PARAMETERS["formats"]},
    "width": {"type": "integer", "minimum": 64, "maximum": 8192},
    "height": {"type": "integer", "minimum": 64, "maximum": 8192},
    "cameraSource": AI_RENDER_PARAMETERS["cameraSource"], "options": RENDER_OPTIONS,
}


def tool_catalog() -> dict[str, ToolSpec]:
    """Complete, deterministic catalog. Applications may load only selected tools."""
    result = {}
    def add(spec):
        if spec.name in result:
            raise ValueError(f"Duplicate tool {spec.name}")
        Draft202012Validator.check_schema(spec.input_schema)
        result[spec.name] = spec

    add(ToolSpec("vase_search_tools", "Find a bounded set of tools by feature or exact name. Returns short matches, not the full catalog or duplicate schemas.",
                 _object(SEARCH_PROPERTIES, ["query"]), "local"))
    add(ToolSpec("vase_tool_schema", "Read the exact typed schemas for at most four named tools. Use only when the host has not already supplied them.",
                 _object(TOOL_SCHEMA_PROPERTIES, ["names"]), "local"))
    add(ToolSpec("vase_read_guide", "Read one short scientific workflow or an exact section, with bounded paging. Parameter schemas come from tools.",
                 _object(GUIDE_PROPERTIES, ["topic"]), "local"))
    add(ToolSpec("vase_inspect_image", "Inspect an image artifact produced by this connection. MCP returns image content directly; native hosts embed the validated artifact bytes as an image, never as text.",
                 _object({"uri": {"type": "string", "minLength": 1}}, ["uri"]), "local"))
    common_display = {key: AI_CONTROL_SCHEMA["properties"]["display"]["properties"][key]
                      for key in ("atomDisplayMode", "showBonds", "showCell", "showAxes", "showGrid",
                                  "showOverlays", "viewportBackground", "atomRadiusScale")}
    style_schema = _object({**common_display, **GUARDS}, GUARD_REQUIRED)
    style_schema["anyOf"] = [{"required": [key]} for key in common_display]
    add(ToolSpec("vase_style_scene", "Change common figure settings in one visual transaction. For flat atoms and hidden bonds set atom_display_mode='2d' and show_bonds=false. Preserves camera, pair policies and every unmentioned setting. No geometry lookup is needed for these toggles.",
                 style_schema, "apply", operation="apply-scene", mutates=True))

    add(ToolSpec("vase_describe", "Read the live GUI document. Start with summary; use a focused profile only when needed. Lengths are Angstrom, angles degrees, indices zero-based.",
                 _object({"profile": {"enum": list(AI_DESCRIBE_PROFILES)}, **{k: BOOLEAN for k in ("includePositions", "includeProperties", "includeOverrides")}}), "describe"))
    for name in ("ready", "documents", "newDocument"):
        add(ToolSpec("vase_" + _snake(name), {"ready": "Check that the shared human GUI is connected.", "documents": "List document tabs in the connected workspace.", "newDocument": "Create and activate an empty editable document tab in the shared workspace."}[name], _object(), name, mutates=name == "newDocument"))
    add(ToolSpec("vase_activate", "Activate the requested human GUI tab. Describe again before any edit.", _object({"sessionId": STRING}, ["sessionId"]), "activate", mutates=True))
    add(ToolSpec("vase_capabilities", "Read the compact live feature catalog, including installed scientific capabilities.", _object({"profile": {"enum": ["summary", "full"]}}), "capabilities"))
    for field, schema in AI_CONTROL_SCHEMA["properties"].items():
        if field in GUARDS or field == "operation":
            continue
        add(ToolSpec("vase_set_" + _snake(field), f"Set {field} in the same live document. " + schema.get("description", "") + " Review changedPaths in the result.",
                     _object({field: schema, **GUARDS}, [field, *GUARD_REQUIRED]), "apply", field=field, mutates=True))
    for name, contract in AI_QUERY_SCHEMAS.items():
        add(ToolSpec("vase_" + name.replace("-", "_"), contract["description"],
                     _object(contract["properties"], contract.get("required", [])), "query", operation=name))
    for name, contract in AI_OPERATION_PARAMETERS.items():
        schema = _flatten(_ai_operation_schema(name))
        schema["properties"].pop("name", None)
        schema["properties"].update(deepcopy(GUARDS))
        schema["required"] = [k for k in schema.get("required", []) if k != "name"] + (["expectedDocumentId"] if name in INTERRUPT_OPERATIONS else GUARD_REQUIRED)
        schema["additionalProperties"] = False
        description = f"{name}. Mode: {contract['mode']}. " + contract.get("notes", "")
        conditions = [k for k in contract["required"] if k not in schema["properties"]]
        if conditions:
            description += " Prerequisites: " + ", ".join(conditions) + "."
        add(ToolSpec("vase_" + name.replace("-", "_"), description, schema, "apply", operation=name, mutates=True))
    add(ToolSpec("vase_pause_playback", "Pause the active movie and synchronize its displayed frame. Requires document identity; revision is optional because playback keeps advancing it.", _object(GUARDS, ["expectedDocumentId"]), "apply", operation="set-playback", mutates=True))
    add(ToolSpec("vase_render", "Render the shared GUI to a unique local artifact. Returns a resource URI and exact camera/dimensions, never inline Base64. Inspect the image for final visual quality.", _object(RENDER_PROPERTIES), "render"))
    export_properties = {
        **RENDER_PROPERTIES, **RDF_PROPERTIES,
        "imageFormat": {"enum": ["png", "jpeg", "webp", "pdf"]},
        "container": {"enum": ["mov", "avi"]},
        "fps": {"type": "number", "exclusiveMinimum": 0},
        "interpolationMultiplier": {"type": "integer", "minimum": 1},
        "interpolationMic": BOOLEAN, "includeCell": BOOLEAN, "embedProject": BOOLEAN,
    }
    for op in ("calculate-commensurate", "calculate-registry-map"):
        export_properties.update(_flatten(_ai_operation_schema(op))["properties"])
    for fmt, contract in AI_EXPORT_PARAMETERS.items():
        props = {k: deepcopy(export_properties[k]) for k in contract["optional"]}
        if fmt == "video":
            for key in ("width", "height"):
                props[key]["multipleOf"] = 2
            props["fps"].update(minimum=1, maximum=60)
            props["interpolationMultiplier"]["maximum"] = 64
        if fmt == "html":
            for key in ("width", "height"):
                props[key]["minimum"] = 256
        if fmt in {"video", "html"}:
            props["options"]["properties"]["transparentBackground"] = {"const": False}
        add(ToolSpec("vase_export_" + fmt.replace("-", "_"), f"Export {fmt} from the shared GUI to a unique local artifact. " + contract.get("notes", ""), _object(props), "export", export_format=fmt))
    add(ToolSpec("vase_events", "Poll human/agent collaboration events. Keep the returned cursor; after an event or gap, describe the live document before editing.", _object({"after": INDEX, "timeout": {"type": "number", "minimum": 0, "maximum": 30}}), "events"))
    return result


@lru_cache(maxsize=1)
def catalog_fingerprint():
    definitions = [spec.definition() for spec in tool_catalog().values()]
    return hashlib.sha256(json.dumps(definitions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ToolError(ValueError):
    """A recoverable tool failure with an explicit mutation outcome."""
    def __init__(self, message, *, code="invalid_arguments", outcome="not_applied"):
        super().__init__(message)
        self.code, self.outcome = code, outcome

    def as_dict(self):
        return {"error": {"code": self.code, "message": str(self), "outcome": self.outcome}}


class FunctionTools:
    """Connect native typed calls to an existing v_ase handshake command_url.

    No model calls or API key are involved. Close the client after handoff;
    closing it does not close the human's GUI or delete exported artifacts.
    """
    def __init__(self, command_url: str, *, artifact_dir: str | Path = "v_ase-artifacts", timeout: float = 300):
        parsed = urlsplit(command_url)
        match = re.fullmatch(r"/api/ai/command/(session|workspace)/([A-Za-z0-9_-]+)", parsed.path)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment or not match):
            raise ValueError("command_url must be a loopback v_ase handshake command endpoint.")
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 1800:
            raise ValueError("timeout must be finite and in (0, 1800] seconds.")
        self.command_url, self.timeout = command_url, timeout
        route = "workspace" if match[1] == "workspace" else ""
        identifier = "workspace_id" if match[1] == "workspace" else "session_id"
        self.human_url = f"{parsed.scheme}://{parsed.netloc}/{route}?{identifier}={match[2]}"
        self.event_url = f"{parsed.scheme}://{parsed.netloc}/api/ai/{'workspace-events' if match[1] == 'workspace' else 'events'}/{match[2]}"
        self.artifact_dir = Path(artifact_dir).expanduser().resolve()
        self.artifacts: dict[str, dict] = {}
        self.scope = match[1]
        self.catalog = {name: spec for name, spec in tool_catalog().items()
                        if self.scope == "workspace" or spec.method not in {"documents", "activate", "newDocument"}}
        self.http = requests.Session()
        self.http.trust_env = False  # Local documents must never go through a proxy.
        self._contract_verified = False
        self.metrics = {"calls": 0, "request_bytes": 0, "response_bytes": 0, "elapsed_seconds": 0.0}

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def definitions(self, names=None):
        return [self.catalog[name].definition() for name in (self.catalog if names is None else names)]

    def initial_definitions(self):
        """Small starting catalog for hosts that explicitly load schemas later."""
        return self.definitions(sorted(CORE_TOOL_NAMES.intersection(self.catalog)))

    def deferred_function_tools(self, *, namespace="vase", strict=True):
        """Responses-style core plus small namespaces of deferred functions.

        The consuming host must provide its tool-search facility. Hosts without
        deferred loading can use initial_definitions plus vase_tool_schema and
        install the returned definitions before the next model request.
        """
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", namespace):
            raise ValueError("namespace must be a simple tool namespace identifier")
        result = []
        groups = {}
        for definition in self.function_tools(strict=strict):
            name = definition["name"]
            definition["defer_loading"] = name not in CORE_TOOL_NAMES
            if name in CORE_TOOL_NAMES:
                result.append(definition)
            else:
                groups.setdefault(tool_group(self.catalog[name]), []).append(definition)
        for group in sorted(groups):
            definitions = groups[group]
            for offset in range(0, len(definitions), 8):
                suffix = f"_{offset // 8 + 1}" if len(definitions) > 8 else ""
                result.append({"type": "namespace", "name": f"{namespace}_{group}{suffix}",
                               "description": GROUP_DESCRIPTIONS[group],
                               "tools": definitions[offset:offset + 8]})
        return result

    def function_tools(self, names=None, *, strict=True):
        """Responses-style definitions; load only names relevant to the task.

        Strict mode uses null for omission and typed key/value lists for dynamic
        maps. Execute these with call_function(), which restores canonical data
        and applies the original scientific and cross-field validation.
        """
        from .function_schema import strict_schema
        return [{"type": "function", "name": d["name"], "description": d["description"],
                 "parameters": strict_schema(d["inputSchema"]) if strict else d["inputSchema"],
                 "strict": strict} for d in self.definitions(names)]

    def call_function(self, name: str, arguments: str | dict, *, strict=True):
        """Execute native model function arguments without any shell layer."""
        from .function_schema import decode_strict, strict_schema
        if isinstance(arguments, str):
            def unique_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f"Duplicate argument key: {key}")
                    result[key] = value
                return result
            try:
                arguments = json.loads(arguments, object_pairs_hook=unique_keys)
            except ValueError as exc:
                raise ToolError(f"Invalid function arguments: {exc}") from exc
        if strict:
            spec = self.catalog.get(name)
            if spec is None:
                raise ToolError(f"Unknown tool {name!r}.", code="unknown_tool")
            schema = spec.input_schema
            error = next(Draft202012Validator(strict_schema(schema)).iter_errors(arguments), None)
            if error is not None:
                raise ToolError(error.message)
            try:
                arguments = decode_strict(arguments, schema)
            except ValueError as exc:
                raise ToolError(str(exc)) from exc
        return self.call(name, arguments)

    def _verify_contract(self):
        if self._contract_verified:
            return
        try:
            response = self.http.post(self.command_url, json={"method": "schema", "params": {"scope": "summary"}}, timeout=10, allow_redirects=False)
            fingerprint = response.json().get("result", {}).get("tool_catalog_fingerprint")
        except (requests.RequestException, ValueError) as exc:
            raise ToolError("Cannot read the live tool contract. Check that the GUI server is running.", code="connection_error") from exc
        if not response.ok or fingerprint != catalog_fingerprint():
            raise ToolError("The live GUI and typed adapter have different tool contracts. Restart them with the same v_ase version.", code="contract_mismatch")
        self._contract_verified = True

    def call(self, name: str, arguments: dict | None = None) -> Any:
        spec = self.catalog.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool {name!r}. Use the advertised catalog.", code="unknown_tool")
        arguments = {} if arguments is None else arguments
        try:
            json.dumps(arguments, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ToolError("Arguments must be finite JSON values.") from exc
        error = next(Draft202012Validator(spec.input_schema).iter_errors(arguments), None)
        if error is not None:
            path = ".".join(str(p) for p in error.absolute_path) or "arguments"
            raise ToolError(f"{path}: {error.message}")
        if spec.method == "local":
            params = _backend_arguments(arguments, spec.schema)
            if name == "vase_inspect_image":
                metadata, _ = self.read_artifact(params["uri"])
                if metadata["mimeType"] not in {"image/png", "image/jpeg", "image/webp"}:
                    raise ToolError("Only PNG/JPEG/WebP artifacts can be inspected as images.")
                return {"artifact": metadata, "delivery": "image",
                        "nativeHostAction": "Embed read_artifact(uri) bytes as image input. Do not print binary or Base64 text."}
            if name == "vase_search_tools":
                return search_catalog(self.catalog, params["query"], params.get("limit", 4))
            if name == "vase_tool_schema":
                unknown = [value for value in params["names"] if value not in self.catalog]
                if unknown:
                    raise ToolError("Unknown tools: " + ", ".join(unknown), code="unknown_tool")
                return {"tools": self.definitions(params["names"])}
            if name == "vase_read_guide":
                from .ai import ai_skill_path
                try:
                    return read_guide(ai_skill_path(), params["topic"], section=params.get("section"),
                                      offset=params.get("offset", 0), max_characters=params.get("maxCharacters", 5000),
                                      expected_sha256=params.get("expectedSha256"))
                except (OSError, ValueError) as exc:
                    raise ToolError(str(exc), code="guide_error") from exc
            raise ToolError("Unknown local tool.", code="unknown_tool")
        self._verify_contract()
        started = time.perf_counter()
        params = _backend_arguments(arguments, spec.schema)
        if spec.method == "apply":
            if spec.operation:
                if spec.name == "vase_pause_playback":
                    params["playing"] = False
                guards = {k: params.pop(k) for k in GUARDS if k in params}
                if spec.name == "vase_style_scene":
                    if not params:
                        raise ToolError("Supply at least one figure setting.")
                    params = {"patch": {"display": params}}
                params = {**guards, "operation": {"name": spec.operation, **params}}
            params.setdefault("responseProfile", "summary")
        elif spec.method == "query":
            params = {"name": spec.operation, **params}
        elif spec.method in {"describe", "capabilities"}:
            params.setdefault("profile", "summary")
        elif spec.export_format:
            params["format"] = spec.export_format
        try:
            if spec.method == "events":
                params.setdefault("timeout", 0)
                params.setdefault("after", 0)
                response = self.http.get(self.event_url, params=params, timeout=params.get("timeout", 0) + 5, allow_redirects=False)
            else:
                response = self.http.post(self.command_url, json={"method": spec.method, "params": params, "timeout_seconds": self.timeout}, timeout=self.timeout + 5, allow_redirects=False)
        except requests.RequestException as exc:
            raise ToolError("The live bridge request failed. Describe before retrying; a timed-out edit may have completed.", code="transport_error", outcome="unknown") from exc
        self.metrics["calls"] += 1
        self.metrics["elapsed_seconds"] += time.perf_counter() - started
        body = response.request.body or b""
        self.metrics["request_bytes"] += len(body.encode() if isinstance(body, str) else body)
        self.metrics["response_bytes"] += len(response.content)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ToolError("The bridge returned non-JSON data.", code="invalid_response", outcome="unknown") from exc
        if not response.ok or response.is_redirect:
            structured = payload.get("detail")
            if isinstance(structured, dict) and structured.get("code"):
                raise ToolError(str(structured.get("message", "Scene command failed."))[:2000],
                                code=structured["code"], outcome=structured.get("outcome", "unknown"))
            detail = str(payload.get("detail", response.reason))[:2000]
            conflict = "revision conflict" in detail.lower() or "active document changed" in detail.lower()
            ambiguous = "multiple live browsers" in detail.lower()
            raise ToolError(detail, code="conflict" if conflict else "ambiguous_browser" if ambiguous else "bridge_error", outcome="not_applied" if conflict or ambiguous else "unknown")
        result = payload if spec.method == "events" else payload.get("result")
        return self._save_artifact(result)

    def _save_artifact(self, result):
        if not isinstance(result, dict) or "dataUrl" not in result:
            return result
        header, separator, encoded = str(result["dataUrl"]).partition(",")
        if not separator or not header.startswith("data:"):
            raise ToolError("Invalid artifact data URL.", code="invalid_artifact", outcome="unknown")
        try:
            data = base64.b64decode(encoded, validate=True) if header.endswith(";base64") else unquote_to_bytes(encoded)
        except ValueError as exc:
            raise ToolError("Invalid artifact encoding.", code="invalid_artifact", outcome="unknown") from exc
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(str(result.get("filename", "artifact.bin"))).name)
        path = self.artifact_dir / f"{uuid.uuid4().hex}-{filename}"
        with path.open("xb") as stream:
            stream.write(data)
        metadata = {"uri": path.as_uri(), "path": str(path), "name": filename,
                    "mimeType": result.get("mimeType", "application/octet-stream"),
                    "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.artifacts[metadata["uri"]] = metadata
        return {**{k: v for k, v in result.items() if k != "dataUrl"}, "artifact": metadata}

    def read_artifact(self, uri: str) -> tuple[dict, bytes]:
        metadata = self.artifacts.get(uri)
        if metadata is None:
            raise ToolError("Resource is not an artifact produced by this connection.", code="unknown_resource")
        path = Path(metadata["path"])
        if path.is_symlink() or path.resolve().parent != self.artifact_dir:
            raise ToolError("Artifact path changed after export.", code="invalid_artifact")
        data = path.read_bytes()
        if len(data) != metadata["size"] or hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            raise ToolError("Artifact content changed after export. Request a new export.", code="invalid_artifact")
        return metadata, data
