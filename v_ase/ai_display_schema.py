"""Typed display contract; verified against the GUI's complete display defaults."""

DISPLAY_PROPERTIES = {'atomBondStyles': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'atomColorScaleAutoRange': {'type': 'boolean'},
 'atomColorScaleEnabled': {'type': 'boolean'},
 'atomColorScaleField': {'type': 'string'},
 'atomColorScaleGamma': {'type': 'number'},
 'atomColorScaleIndices': {'items': {'type': 'number'}, 'type': 'array'},
 'atomColorScaleMap': {'type': 'string'},
 'atomColorScaleMax': {'type': 'number'},
 'atomColorScaleMin': {'type': 'number'},
 'atomColorScaleRangeMode': {'type': 'string'},
 'atomColorScaleReverse': {'type': 'boolean'},
 'atomColorScaleScope': {'type': 'string'},
 'atomColorScaleTargetLabel': {'type': 'string'},
 'atomColors': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'atomDisplayMode': {'type': 'string'},
 'atomMaterials': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'atomOpacities': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'atomRadiusScale': {'type': 'number'},
 'atomRadiusScales': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'atomicScalePixelsPerAngstrom': {'type': ['number', 'null']},
 'blenderExportMode': {'type': 'string'},
 'bondColorMode': {'type': 'string'},
 'bondCustomColor': {'type': 'string'},
 'bondCutoffScale': {'type': 'number'},
 'bondMaterial': {'type': 'string'},
 'bondMode': {'type': 'string'},
 'bondOpacity': {'type': 'number'},
 'bondStyle': {'type': 'string'},
 'bondThickness': {'type': 'number'},
 'cellColor': {'type': 'string'},
 'cellMaterial': {'type': 'string'},
 'cellThickness': {'type': 'number'},
 'commensurateGuestAngleDeg': {'type': 'number'},
 'commensurateGuestGap': {'type': 'number'},
 'commensurateGuestOffset': {'items': {'type': 'number'}, 'type': 'array'},
 'commensurateGuide': {'type': 'boolean'},
 'commensurateMaxAreaRatio': {'type': 'number'},
 'commensurateMaxIndex': {'type': 'number'},
 'commensurateMode': {'type': 'string'},
 'commensurateShowAtoms': {'type': 'boolean'},
 'commensurateSnap': {'type': 'boolean'},
 'commensurateSnapRangeDeg': {'type': 'number'},
 'commensurateStrainTarget': {'type': 'string'},
 'commensurateStrainTolerance': {'type': 'number'},
 'displacementColor': {'type': 'string'},
 'displacementMic': {'type': 'boolean'},
 'displacementReferenceFrame': {'type': 'number'},
 'displacementReferenceMode': {'type': 'string'},
 'displacementScale': {'type': 'number'},
 'displacementStyle': {'type': 'string'},
 'displacementThickness': {'type': 'number'},
 'exportIncludeCell': {'type': 'boolean'},
 'forceVectorColor': {'type': 'string'},
 'forceVectorScale': {'type': 'number'},
 'forceVectorStyle': {'type': 'string'},
 'forceVectorThickness': {'type': 'number'},
 'hiddenAtomReferences': {'items': {'type': 'number'}, 'type': 'array'},
 'imageFramingMode': {'type': 'string'},
 'imageSmoothnessScale': {'type': 'number'},
 'imageSphereQuality': {'type': 'string'},
 'labelColors': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'labelMaterials': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'labelOpacities': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'labelRadii': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'labelVisible': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'lightingMode': {'type': 'string'},
 'manualBondPairs': {'items': {'type': 'number'}, 'type': 'array'},
 'pairwiseBondCutoffs': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'pairwiseBondRanges': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'pairwiseBondStyles': {'additionalProperties': {'type': 'number'}, 'type': 'object'},
 'pairwiseLabelColumnWidth': {'type': 'number'},
 'projectionMode': {'type': 'string'},
 'rdfBins': {'type': 'number'},
 'rdfCutoff': {'type': ['number', 'null']},
 'rdfPairMode': {'type': 'string'},
 'rdfUsePbc': {'type': 'boolean', 'default': True},
 'registryGridX': {'type': 'number'},
 'registryGridY': {'type': 'number'},
 'registryHkl': {'items': {'type': 'number'}, 'type': 'array'},
 'registryMetric': {'type': 'string'},
 'rotatePivot': {'type': 'string'},
 'selectedAppearanceAffectsBonds': {'type': 'boolean'},
 'showAxes': {'type': 'boolean'},
 'showBonds': {'type': 'boolean'},
 'showCell': {'type': 'boolean'},
 'showDisplacements': {'type': 'boolean'},
 'showForceVectors': {'type': 'boolean'},
 'showGrid': {'type': 'boolean'},
 'showOverlays': {'type': 'boolean'},
 'showConstraints': {'type': 'boolean'},
 'showPeriodicBonds': {'type': 'boolean'},
 'showVolumetric': {'type': 'boolean'},
 'sunGizmo': {'type': 'boolean'},
 'sunIntensity': {'type': 'number'},
 'sunPosition': {'items': {'type': 'number'}, 'type': 'array'},
 'sunTarget': {'items': {'type': 'number'}, 'type': 'array'},
 'supercell': {'items': {'type': 'number'}, 'type': 'array'},
 'translation': {'items': {'type': 'number'}, 'type': 'array'},
 'translationMode': {'type': 'string'},
 'videoFormat': {'type': 'string'},
 'videoFps': {'type': 'number'},
 'videoStartFrame': {'type': 'integer', 'minimum': 0},
 'videoEndFrame': {'type': ['integer', 'null'], 'minimum': 0},
 'videoLoop': {'type': 'boolean'},
 'videoInterpolationMic': {'type': 'boolean'},
 'videoInterpolationMultiplier': {'type': 'number'},
 'viewRotationStepDeg': {'type': 'number'},
 'viewportBackground': {'type': 'string'},
 'volumetricDatasetId': {'type': 'string'},
 'volumetricLevel': {'type': ['number', 'null']},
 'volumetricNegativeColor': {'type': 'string'},
 'volumetricOpacity': {'type': 'number'},
 'volumetricPlanes': {'items': {'type': 'number'}, 'type': 'array'},
 'volumetricPositiveColor': {'type': 'string'},
 'volumetricPrecision': {'type': 'string'},
 'volumetricSmearingSigma': {'type': 'number'},
 'volumetricSmoothingIterations': {'type': 'number'},
 'volumetricStepSize': {'type': 'number'},
 'volumetricSurfaceMode': {'type': 'string'}}

_COLOR = {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}
_MATERIAL = {"enum": ["standard", "metal", "rubber", "unlit"]}
_VECTOR = {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}
_REFERENCE = {"type": "object", "properties": {"index": {"type": "integer", "minimum": 0}, "cellOffset": {**_VECTOR, "items": {"type": "integer"}}}, "required": ["index", "cellOffset"], "additionalProperties": False}
_STYLE = {"type": "object", "properties": {"style": {"enum": ["cylinder", "flat"]}, "material": _MATERIAL, "colorMode": {"enum": ["split", "custom"]}, "color": _COLOR, "opacity": {"type": "number", "minimum": 0, "maximum": 1}, "thickness": {"type": "number", "exclusiveMinimum": 0}}, "additionalProperties": False}
for key in ("labelColors", "atomColors"):
    DISPLAY_PROPERTIES[key] = {"type": "object", "additionalProperties": _COLOR}
for key in ("labelMaterials", "atomMaterials"):
    DISPLAY_PROPERTIES[key] = {"type": "object", "additionalProperties": _MATERIAL}
DISPLAY_PROPERTIES["labelVisible"] = {"type": "object", "additionalProperties": {"type": "boolean"}}
for key in ("atomBondStyles", "pairwiseBondStyles"):
    DISPLAY_PROPERTIES[key] = {"type": "object", "additionalProperties": _STYLE}
DISPLAY_PROPERTIES["pairwiseBondRanges"] = {"type": "object", "additionalProperties": {"type": "object", "properties": {"enabled": {"type": "boolean"}, "min": {"type": "number"}, "max": {"type": "number"}}, "additionalProperties": False}}
DISPLAY_PROPERTIES["manualBondPairs"] = {"type": "array", "items": {"type": "array", "items": {"type": "integer", "minimum": 0}, "minItems": 2, "maxItems": 2}}
DISPLAY_PROPERTIES["hiddenAtomReferences"] = {"type": "array", "items": {"type": "string", "pattern": "^(atom:[0-9]+|replica:[0-9]+:-?[0-9]+,-?[0-9]+,-?[0-9]+)$"}}
DISPLAY_PROPERTIES["atomColorScaleIndices"] = {"type": "array", "items": {"type": "integer", "minimum": 0}}
DISPLAY_PROPERTIES["atomRadiusMapping"] = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "field": {"type": "string"},
        "valueTransform": {"enum": ["identity", "absolute"]},
        "rangeMode": {"enum": ["current", "trajectory", "manual"]},
        "min": {"type": "number"},
        "max": {"type": "number"},
        "minMultiplier": {"type": "number", "minimum": 0, "maximum": 4},
        "maxMultiplier": {"type": "number", "minimum": 0, "maximum": 4},
        "exponent": {"type": "number", "minimum": 0.1, "maximum": 5},
        "scope": {"enum": ["all", "indices"]},
        "indices": {"type": "array", "items": {"type": "integer", "minimum": 0}},
    },
    "additionalProperties": False,
}
for key in ("translation", "sunPosition", "sunTarget", "commensurateGuestOffset"):
    DISPLAY_PROPERTIES[key] = _VECTOR
DISPLAY_PROPERTIES["supercell"] = {**_VECTOR, "items": {"type": "integer", "minimum": 1, "maximum": 64}}
DISPLAY_PROPERTIES["registryHkl"] = {**_VECTOR, "items": {"type": "integer"}}
_ENUMS = {
    "bondMode": ["auto", "pairwise", "manual"], "bondStyle": ["cylinder", "flat"],
    "bondColorMode": ["split", "custom"], "translationMode": ["cartesian", "fractional"],
    "projectionMode": ["orthographic", "perspective"], "atomDisplayMode": ["2d", "3d"],
    "lightingMode": ["modeling", "studio", "studio-shadow"],
    "imageFramingMode": ["viewport", "physical"], "videoFormat": ["mov", "avi", "gif"],
    "displacementReferenceMode": ["previous", "frame"],
    "displacementStyle": ["2d", "3d"], "forceVectorStyle": ["2d", "3d"],
    "volumetricPrecision": ["float32", "float64"], "volumetricSurfaceMode": ["single", "signed"],
    "rdfPairMode": ["active", "selected", "all", "none"],
    "commensurateMode": ["same-lattice", "host-guest"], "commensurateStrainTarget": ["host", "guest"],
    "atomColorScaleScope": ["all", "selected"], "atomColorScaleRangeMode": ["current", "trajectory", "manual"],
    "imageSphereQuality": ["viewport", "auto", "low", "medium", "high", "ultra"],
}
for key, values in _ENUMS.items():
    DISPLAY_PROPERTIES[key] = {"enum": values}
for key in ("bondMaterial", "cellMaterial"):
    DISPLAY_PROPERTIES[key] = _MATERIAL

# Appearance validation mirrors the live per-index and label normalization.
for key in ("labelMaterials", "atomMaterials"):
    DISPLAY_PROPERTIES[key] = {"type": "object", "additionalProperties": {"enum": ["standard", "metal", "rubber"]}}
DISPLAY_PROPERTIES["cellMaterial"] = {"enum": ["unlit", "standard", "metal"]}
DISPLAY_PROPERTIES["atomBondStyles"] = {"type": "object", "additionalProperties": {"type": "object", "properties": {k: v for k, v in _STYLE["properties"].items() if k in {"material", "opacity", "color"}}, "additionalProperties": False}}
DISPLAY_PROPERTIES["atomRadiusScales"] = {"type": "object", "additionalProperties": {"type": "number", "minimum": 0.25, "maximum": 2.5}}
for key in ("labelOpacities", "atomOpacities"):
    DISPLAY_PROPERTIES[key] = {"type": "object", "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1}}
DISPLAY_PROPERTIES["labelRadii"] = {"type": "object", "additionalProperties": {"type": "number", "exclusiveMinimum": 0}}
_GRAPH_AXES = {
    "type": "object", "additionalProperties": False,
    "properties": {key: {"type": ["number", "null"]} for key in ("xMin", "xMax", "yMin", "yMax")},
    "description": "Null uses the automatic limit. Each minimum must be below its maximum.",
}
_GRAPH_TYPOGRAPHY = {
    "fontFamily": {"enum": ["system-ui", "Arial", "Georgia", "monospace"]},
    "fontSize": {"type": "integer", "minimum": 8, "maximum": 24},
    "xTickLabels": {"type": "boolean"},
    "yTickLabels": {"type": "boolean"},
    "tickFormat": {"enum": ["auto", "fixed", "scientific"]},
    "tickPrecision": {"type": "integer", "minimum": 0, "maximum": 8},
}
_GRAPH_SERIES_NAME = {"type": "string", "maxLength": 64}
_GRAPH_SERIES_MODE = {"enum": ["line", "line-markers", "markers", "hidden"]}
_GRAPH_LINE_STYLE = {"enum": ["solid", "dash", "dot", "dash-dot"]}
_GRAPH_MARKER_SHAPE = {"enum": ["circle", "square", "diamond"]}
_GRAPH_MARKER_SIZE = {"type": "number", "minimum": 2, "maximum": 16}
ENERGY_GRAPH_EXTRA_STYLE = {
    **_GRAPH_TYPOGRAPHY,
    "legend": {"type": "boolean"},
    **{f"{prefix}Name": _GRAPH_SERIES_NAME for prefix in ("sample", "fit", "tangent")},
    **{f"{prefix}Mode": _GRAPH_SERIES_MODE for prefix in ("fit", "tangent")},
    **{f"{prefix}Marker": _COLOR for prefix in ("fit", "tangent")},
    **{f"{prefix}MarkerShape": _GRAPH_MARKER_SHAPE for prefix in ("fit", "tangent")},
    **{f"{prefix}MarkerSize": _GRAPH_MARKER_SIZE for prefix in ("fit", "tangent")},
    "tangentLineStyle": _GRAPH_LINE_STYLE,
}
DISPLAY_PROPERTIES["selectedAppearanceFrameScope"] = {"enum": ["all", "current"]}
DISPLAY_PROPERTIES["retainedLabels"] = {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True}
DISPLAY_PROPERTIES["labelBondStyles"] = {
    "type": "object",
    "additionalProperties": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "material": {"enum": ["standard", "metal", "rubber", "unlit"]},
            "opacity": {"type": "number", "minimum": 0, "maximum": 1},
            "color": _COLOR,
        },
    },
}
DISPLAY_PROPERTIES.update({
    "showAtoms": {"type": "boolean"},
    "flatOutlineWidth": {"type": "number", "minimum": 0, "maximum": 0.25},
    "renderFixedRatio": {"type": "boolean"},
    "energyOverlay": {
        "type": "object",
        "properties": {
            "visible": {"type": "boolean"},
            "axes": _GRAPH_AXES,
            "layout": {
                "type": "object",
                "properties": {key: {"type": "number", "minimum": minimum, "maximum": 1}
                               for key, minimum in (("x", 0), ("y", 0), ("width", .05), ("height", .05))},
                "additionalProperties": False,
            },
            "style": {
                "type": "object",
                "properties": {
                    **{key: _COLOR for key in ("line", "marker", "background", "fitColor", "tangentColor")},
                    "stroke": {"type": "number", "minimum": .75, "maximum": 5},
                    "reference": {"enum": ["first", "absolute"]},
                    "dataMode": _GRAPH_SERIES_MODE,
                    "lineStyle": _GRAPH_LINE_STYLE,
                    "fitLineStyle": _GRAPH_LINE_STYLE,
                    "markerShape": _GRAPH_MARKER_SHAPE,
                    "markerSize": _GRAPH_MARKER_SIZE,
                    "backgroundMode": {"enum": ["theme", "color", "transparent"]},
                    "grid": {"type": "boolean"},
                    "cursor": {"type": "boolean"},
                    "fitWidth": {"type": "number", "minimum": .5, "maximum": 8},
                    "tangentWidth": {"type": "number", "minimum": .5, "maximum": 8},
                    "tangentScale": {"type": "number", "minimum": .1, "maximum": 4},
                    **ENERGY_GRAPH_EXTRA_STYLE,
                },
                "additionalProperties": False,
            },
            "neb": {
                "type": "object",
                "properties": {
                    "fit": {"type": "boolean"},
                    "tangents": {"type": "boolean"},
                    "images": {"type": ["integer", "null"], "minimum": 2},
                    "mic": {"type": "boolean", "default": True},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
})

_ANALYSIS_PLOT_PRESENTATION = {
    "placement": {"enum": ["drawer", "viewport"]},
    "axes": _GRAPH_AXES,
    "layout": {
        "type": "object", "additionalProperties": False,
        "properties": {key: {"type": "number", "minimum": minimum, "maximum": 1}
                       for key, minimum in (("x", 0), ("y", 0), ("width", .1), ("height", .1))},
    },
}
DISPLAY_PROPERTIES["analysisPlots"] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        name: {"type": "object", "additionalProperties": False, "properties": dict(_ANALYSIS_PLOT_PRESENTATION)}
        for name in ("rdf", "registry", "commensurate")
    },
}
RDF_GRAPH_STYLE = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "backgroundMode": {"enum": ["theme", "color", "transparent"]}, "background": _COLOR,
        "grid": {"type": "boolean"}, "legend": {"type": "boolean"},
        "lineColor": {"type": ["string", "null"], "pattern": "^#[0-9a-fA-F]{6}$"},
        "lineWidth": {"type": "number", "minimum": .5, "maximum": 8},
        "lineStyle": {"enum": ["solid", "dash", "dot", "dashdot"]},
        "mode": {"enum": ["lines", "lines+markers", "markers"]},
        "markerSize": _GRAPH_MARKER_SIZE,
        **_GRAPH_TYPOGRAPHY,
        "series": {
            "type": "object",
            "propertyNames": {"pattern": r"^(total|[^|]+\|[^|]+)$"},
            "additionalProperties": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "name": _GRAPH_SERIES_NAME,
                    "line": _COLOR,
                    "marker": _COLOR,
                    "stroke": {"type": "number", "minimum": .25, "maximum": 8},
                    "dataMode": _GRAPH_SERIES_MODE,
                    "lineStyle": _GRAPH_LINE_STYLE,
                    "markerShape": _GRAPH_MARKER_SHAPE,
                    "markerSize": _GRAPH_MARKER_SIZE,
                },
            },
        },
    },
}
DISPLAY_PROPERTIES["analysisPlots"]["properties"]["rdf"]["properties"]["style"] = RDF_GRAPH_STYLE
DISPLAY_PROPERTIES["analysisPlots"]["properties"]["commensurate"]["properties"]["projectionAxes"] = _GRAPH_AXES

# Polyhedra preserve an explicit selector/radius contract across every adapter.
from .polyhedra import RULES_SCHEMA
DISPLAY_PROPERTIES.update({
    'showPolyhedra': {'type': 'boolean'},
    'polyhedraRules': RULES_SCHEMA,
    'polyhedraBondedOnly': {'type': 'boolean'},
    'polyhedraAtomMode': {'enum': ['all', 'coordination', 'centers', 'ligands', 'none']},
    'polyhedraCompleteLigands': {'type': 'boolean'},
    'polyhedraShowCenterBonds': {'type': 'boolean'},
    'polyhedraRespectVisibility': {'type': 'boolean'},
})


DISPLAY_PROPERTIES['waterSurface'] = {
    'type': 'object', 'additionalProperties': False,
    'description': 'H2O density envelope. Appearance only; not molecular dynamics. Selected source captures oxygen indices.',
    'properties': {
        'enabled': {'type': 'boolean'}, 'source': {'enum': ['auto', 'selected']},
        'indices': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}},
        'color': {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$'},
        'opacity': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'lighting': {'type': 'boolean'}, 'hideMolecules': {'type': 'boolean'},
        'roughness': {'type': 'number', 'minimum': .02, 'maximum': 1},
        'smoothing': {'type': 'number', 'minimum': .5, 'maximum': 3},
        'level': {'type': 'number', 'minimum': .1, 'maximum': 3},
        'spacing': {'type': 'number', 'minimum': .3, 'maximum': 1.5},
        'ohCutoff': {'type': 'number', 'minimum': .8, 'maximum': 1.6},
    },
}

# Numeric, shared viewport/export geometry quality. Zero preserves legacy presets.
DISPLAY_PROPERTIES['atomSmoothness'] = {'anyOf': [{'const': 0}, {'type': 'integer', 'minimum': 8, 'maximum': 128, 'multipleOf': 2}]}
for key in ('isosurfaceInterpolation', 'waterInterpolation'):
    DISPLAY_PROPERTIES[key] = {'type': 'integer', 'minimum': 0, 'maximum': 8}
for key in ('isosurfaceMeshSmoothing', 'waterMeshSmoothing'):
    DISPLAY_PROPERTIES[key] = {'type': 'integer', 'minimum': 0, 'maximum': 100}
