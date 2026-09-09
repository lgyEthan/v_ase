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
for key in ("translation", "sunPosition", "sunTarget", "commensurateGuestOffset"):
    DISPLAY_PROPERTIES[key] = _VECTOR
DISPLAY_PROPERTIES["supercell"] = {**_VECTOR, "items": {"type": "integer", "minimum": 1, "maximum": 64}}
DISPLAY_PROPERTIES["registryHkl"] = {**_VECTOR, "items": {"type": "integer"}}
_ENUMS = {
    "bondMode": ["auto", "pairwise", "manual"], "bondStyle": ["cylinder", "flat"],
    "bondColorMode": ["split", "custom"], "translationMode": ["cartesian", "fractional"],
    "projectionMode": ["orthographic", "perspective"], "atomDisplayMode": ["2d", "3d"],
    "lightingMode": ["modeling", "studio", "studio-shadow"],
    "imageFramingMode": ["viewport", "physical"], "videoFormat": ["mov", "avi"],
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

# Polyhedra preserve an explicit selector/radius contract across every adapter.
from .polyhedra import RULES_SCHEMA
DISPLAY_PROPERTIES.update({
    'showPolyhedra': {'type': 'boolean'},
    'polyhedraRules': RULES_SCHEMA,
    'polyhedraAtomMode': {'enum': ['all', 'coordination', 'centers', 'ligands', 'none']},
    'polyhedraCompleteLigands': {'type': 'boolean'},
    'polyhedraShowCenterBonds': {'type': 'boolean'},
    'polyhedraRespectVisibility': {'type': 'boolean'},
})
