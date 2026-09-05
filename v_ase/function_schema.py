"""Lossless argument codec for providers with strict JSON Schema subsets.

Optional non-null fields use null for omission. Dynamic maps use typed key/value
entries because strict providers forbid arbitrary object keys. Conditional and
cross-field constraints remain enforced by the canonical local validator.
"""
from __future__ import annotations
from copy import deepcopy


def _nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def accepts_null(schema):
    kind = schema.get("type")
    return (kind == "null" or isinstance(kind, list) and "null" in kind
            or "enum" in schema and None in schema["enum"]
            or any(accepts_null(s) for s in schema.get("anyOf", []) + schema.get("oneOf", [])))


def _alternatives(schema):
    return schema.get("anyOf", schema.get("oneOf", []))


def strict_schema(schema):
    """Produce a provider-compatible structural schema, retaining exact types."""
    source = deepcopy(schema)
    alternatives = _alternatives(source)
    if alternatives and all('required' in s and not any(k in s for k in ('type', 'enum', 'properties')) for s in alternatives):
        alternatives = []  # Selection conditions are validated after decoding.
    if alternatives:
        return {"anyOf": [strict_schema(s) for s in alternatives]}
    kind = source.get("type")
    if kind is None and "properties" in source:
        kind = "object"
    if 'const' in source:
        source['enum'] = [source.pop('const')]
    if kind is None and 'enum' in source:
        types = {"null" if v is None else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float)) else "string" for v in source['enum']}
        kind = next(iter(types)) if len(types) == 1 else sorted(types)
    if kind is None:
        raise ValueError(f"A strict function parameter has no concrete type: {source}")
    if isinstance(kind, list) and 'object' in kind:
        return {"anyOf": [strict_schema({**source, 'type': t}) for t in kind]}
    if kind == "object":
        properties = source.get("properties", {})
        extra = source.get("additionalProperties", not bool(properties))
        if not properties and isinstance(extra, dict):
            result = {"type": "array", "items": {
                "type": "object", "properties": {"key": {"type": "string"}, "value": strict_schema(extra)},
                "required": ["key", "value"], "additionalProperties": False,
            }, "description": "Map as key/value entries. Keys must be unique. " + source.get("description", "")}
            return result
        if not properties and extra is True:
            raise ValueError("An unconstrained object cannot be advertised as a strict typed function.")
        required = source.get("required", [])
        result = {"type": "object", "properties": {}, "required": list(properties), "additionalProperties": False}
        for key, item in properties.items():
            converted = strict_schema(item)
            if key in required:
                result["properties"][key] = converted
            elif accepts_null(item):
                # Omission and an explicit scientific null are distinct.
                result["properties"][key] = _nullable({
                    "type": "object", "properties": {"value": converted},
                    "required": ["value"], "additionalProperties": False,
                    "description": "null omits this field; {value: null} explicitly clears it.",
                })
            else:
                result["properties"][key] = _nullable(converted)
    elif kind == "array":
        item = source.get("items")
        if item is None and "prefixItems" in source:
            # Scientific tuple schemas contain homogeneous vector components.
            components = source["prefixItems"]
            if not components or any(v != components[0] for v in components):
                raise ValueError("Heterogeneous positional tuples need a named object schema.")
            item = components[0]
        result = {"type": "array", "items": strict_schema(item or {})}
    else:
        result = {"type": kind}
    # These keywords are supported by standard strict function schemas. The
    # authoritative validator also retains bounds not expressible by a provider.
    for key in ("description", "enum", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "pattern"):
        if key in source:
            result[key] = source[key]
    return result


def decode_strict(value, schema):
    """Restore canonical optional fields and maps without discarding real nulls."""
    alternatives = _alternatives(schema)
    if alternatives:
        from jsonschema import Draft202012Validator
        for branch in alternatives:
            try:
                candidate_schema = strict_schema(branch)
            except ValueError:
                continue
            if Draft202012Validator(candidate_schema).is_valid(value):
                return decode_strict(value, branch)
    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties")
        if not properties and isinstance(extra, dict):
            result = {}
            for entry in value:
                key = entry["key"]
                if key in result:
                    raise ValueError(f"Duplicate map key: {key!r}")
                result[key] = decode_strict(entry["value"], extra)
            return result
        result = {}
        required = schema.get("required", [])
        for key, item in value.items():
            field = properties.get(key, {})
            if key not in required:
                if item is None:
                    continue
                if accepts_null(field):
                    item = item["value"]
            result[key] = None if item is None else decode_strict(item, field)
        return result
    if isinstance(value, list):
        item = schema.get("items", (schema.get("prefixItems") or [{}])[0])
        return [decode_strict(v, item) for v in value]
    return value
