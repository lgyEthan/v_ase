"""Canonical semantic contracts shared by GUI, HTTP, CLI, and typed tools.

Keep this module independent of ASE, FastAPI, and the MCP SDK so discovery is
cheap and adapters cannot drift into separate scientific implementations.
"""
from copy import deepcopy
from typing import Any, Dict

from .ai import AI_PROTOCOL, COLLABORATION_PROTOCOL
from .limits import MAX_LATTICE_MATCH_AREA_RATIO

_AI_COMMAND_METHODS = frozenset({
    "ready",
    "schema",
    "describe",
    "capabilities",
    "documents",
    "activate",
    "newDocument",
    "apply",
    "render",
    "export",
})
_AI_COMMAND_DEFAULT_TIMEOUT_SECONDS = 300.0

_AI_REPULSION_CALCULATOR_SCHEMA = {
    "type": "object",
    "description": (
        "Optional settings for v_ase's built-in repulsion calculator. Pair "
        "distances are independent from visual bonds. In absolute mode each "
        "pair_cutoffs value is its onset distance in Angstrom. In scaled mode "
        "the value is multiplied by cutoff_scale. Zero disables a pair. Pair "
        "energy and force are exactly zero at and beyond the onset distance."
    ),
    "additionalProperties": False,
    "properties": {
        "device": {"enum": ["cpu", "cuda"]},
        "cpu_threads": {"type": "integer", "minimum": 1},
        "cutoff_mode": {"enum": ["absolute", "scaled"]},
        "cutoff_basis": {"enum": ["covalent", "vdw"]},
        "cutoff_distance": {
            "type": "number", "minimum": 0.01, "maximum": 100,
        },
        "cutoff_scale": {
            "type": "number", "minimum": 0.05, "maximum": 3,
        },
        "pair_cutoffs": {
            "type": "object",
            "description": (
                "Independent repulsion reference distances in Angstrom, keyed "
                "by an unordered label pair such as Cu_surface|O_ads. Zero "
                "disables the pair even if a visual bond is shown."
            ),
            "additionalProperties": {
                "type": "number", "minimum": 0, "maximum": 100,
            },
        },
        "k_repulsion": {
            "type": "number", "minimum": 0, "maximum": 1000,
        },
        "k_boundary": {
            "type": "number", "exclusiveMinimum": 0, "maximum": 1000,
        },
    },
}


AI_CONTROL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": (
        "https://github.com/lgyEthan/v_ase/blob/main/v_ase/skills/"
        "visualizing-atomic-structures-with-v-ase/SKILL.md"
    ),
    "title": "v_ase live semantic control",
    "description": (
        "Commands accepted by the HTTP JSON bridge and optional "
        "window.v_aseAI.apply() mirror. They control the same live document "
        "that a human sees in the v_ase GUI."
    ),
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "expectedDocumentId": {
            "type": "string", "minLength": 1,
            "description": "Reject if the active document differs from the one inspected, even when revisions match.",
        },
        "expectedRevision": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Optional optimistic-concurrency guard. Reject the command "
                "when the live collaboration revision has changed."
            ),
        },
        "responseProfile": {
            "enum": [
                "summary", "structure", "appearance", "bonding",
                "render", "analysis", "full",
            ],
            "description": (
                "Controls the semantic state returned after apply. External CLI "
                "clients default to summary to avoid returning the complete scene "
                "after every mutation; browser callers retain full for compatibility."
            ),
        },
        "frame": {"type": "integer", "minimum": 0},
        "mode": {"enum": ["view", "edit"]},
        "applyConstraints": {"type": "boolean"},
        "quality": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "antiAliasing": {"type": "boolean"},
                "sphereQuality": {
                    "enum": ["auto", "low", "medium", "high", "ultra"],
                },
            },
        },
        "display": {
            "type": "object",
            "description": (
                "Partial visual settings. Common keys include showBonds, "
                "showCell, showAxes, showGrid, viewportBackground, "
                "atomDisplayMode, atomRadiusScale, labelRadii, labelColors, "
                "labelOpacities, labelMaterials, atomRadiusScales, atomColors, "
                "atomOpacities, atomMaterials, atomBondStyles, bondThickness, "
                "bondMaterial, bondOpacity, pairwiseBondStyles (including "
                "pair thickness), supercell, "
                "translation, translationMode, lightingMode, "
                "sunIntensity, sunPosition, and sunTarget."
            ),
            "additionalProperties": True,
        },
        "selection": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "clear": {"type": "boolean"},
                "indices": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0},
                    "uniqueItems": True,
                },
                "references": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["index", "cellOffset"],
                        "properties": {
                            "index": {"type": "integer", "minimum": 0},
                            "cellOffset": {
                                "type": "array",
                                "prefixItems": [
                                    {"type": "integer"},
                                    {"type": "integer"},
                                    {"type": "integer"},
                                ],
                                "minItems": 3,
                                "maxItems": 3,
                            },
                        },
                    },
                },
            },
        },
        "operation": {
            "description": (
                "One semantic structure operation. Supported names are wrap, "
                "translate-all, center-selection-at-origin, compose-view, set-unit-cell, build-bulk, set-supercell, make-supercell, add-atom, "
                "scatter-atoms, scatter-molecules, update-add-atoms-region, "
                "scale-add-atoms-regions, "
                "relax-added-atoms, stop-added-atoms, "
                "finish-add-atoms, cancel-add-atoms, "
                "delete-selection, set-visual-label, style-atoms, configure-bonds, set-identity, set-constraints, "
                "move-selection, rotate-selection, scale-selection, rotate-to-commensurate, "
                "load-commensurate-guest, remove-commensurate-guest, "
                "calculate-commensurate, apply-commensurate-cell, "
                "dismiss-commensurate-cell, calculate-registry-map, "
                "start-registry-relaxation, run-registry-relaxation, "
                "set-registry-translation, "
                "stop-registry-relaxation, finish-registry-relaxation, "
                "cancel-registry-relaxation, undo, redo, "
                "reset-coordinates, start-relaxation, stop-relaxation, "
                "clear-relaxation-trajectory, exit-relaxation-mode, and "
                "refresh-displacements, load-volumetric, show-volumetric, "
                "add-volumetric-plane, update-volumetric-planes, "
                "remove-volumetric-planes, combine-volumetric, "
                "remove-volumetric, calculate-rdf, "
                "set-interface-theme, set-personal-visual-default, and "
                "restore-app-visual-defaults, and set-atom-colorscale."
            ),
            "oneOf": [
                {
                    "type": "string",
                    "enum": [
                        "wrap", "center-selection-at-origin", "undo", "redo", "reset-coordinates",
                        "stop-relaxation", "refresh-displacements",
                        "apply-commensurate-cell", "dismiss-commensurate-cell",
                        "remove-commensurate-guest", "calculate-rdf",
                        "set-personal-visual-default",
                        "stop-added-atoms", "finish-add-atoms", "cancel-add-atoms",
                        "update-add-atoms-region",
                        "stop-registry-relaxation", "finish-registry-relaxation",
                        "cancel-registry-relaxation",
                        "clear-relaxation-trajectory", "exit-relaxation-mode",
                    ],
                },
                {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "enum": [
                                "wrap", "translate-all", "center-selection-at-origin", "compose-view", "set-unit-cell", "build-bulk", "set-supercell",
                                "make-supercell", "add-atom", "scatter-atoms",
                                "scatter-molecules",
                                "update-add-atoms-region", "scale-add-atoms-regions",
                                "relax-added-atoms", "stop-added-atoms",
                                "finish-add-atoms", "cancel-add-atoms",
                                "delete-selection", "set-visual-label", "style-atoms", "configure-bonds", "set-identity",
                                "set-constraints", "move-selection",
                                "rotate-selection", "scale-selection", "rotate-to-commensurate",
                                "load-commensurate-guest",
                                "remove-commensurate-guest",
                                "calculate-commensurate",
                                "apply-commensurate-cell",
                                "dismiss-commensurate-cell",
                                "calculate-registry-map",
                                "start-registry-relaxation",
                                "run-registry-relaxation",
                                "set-registry-translation",
                                "stop-registry-relaxation",
                                "finish-registry-relaxation",
                                "cancel-registry-relaxation",
                                "undo", "redo",
                                "reset-coordinates", "start-relaxation",
                                "stop-relaxation", "clear-relaxation-trajectory",
                                "exit-relaxation-mode",
                                "refresh-displacements",
                                "load-volumetric", "show-volumetric",
                                "add-volumetric-plane",
                                "update-volumetric-planes",
                                "remove-volumetric-planes",
                                "combine-volumetric", "remove-volumetric",
                                "calculate-rdf", "set-interface-theme",
                                "set-personal-visual-default",
                                "restore-app-visual-defaults",
                                "set-atom-colorscale",
                            ],
                        },
                    },
                    "allOf": [
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "build-bulk"}},
                            },
                            "then": {
                                "required": ["formula"],
                                "properties": {
                                    "formula": {"type": "string", "minLength": 1},
                                    "crystalStructure": {
                                        "enum": [
                                            "sc", "fcc", "bcc", "bct", "hcp",
                                            "rhombohedral", "orthorhombic", "diamond",
                                            "zincblende", "rocksalt", "cesiumchloride",
                                            "fluorite", "wurtzite",
                                        ],
                                    },
                                    "cellMode": {
                                        "enum": ["primitive", "orthorhombic", "cubic"],
                                    },
                                    "a": {"type": "number", "exclusiveMinimum": 0},
                                    "b": {"type": "number", "exclusiveMinimum": 0},
                                    "c": {"type": "number", "exclusiveMinimum": 0},
                                    "alpha": {
                                        "type": "number",
                                        "exclusiveMinimum": 0,
                                        "exclusiveMaximum": 180,
                                    },
                                    "covera": {"type": "number", "exclusiveMinimum": 0},
                                    "u": {"type": "number", "minimum": 0, "maximum": 1},
                                    "basis": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                            "minItems": 3,
                                            "maxItems": 3,
                                        },
                                    },
                                    "confirmReplace": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "set-unit-cell"}},
                            },
                            "then": {
                                "required": ["cell"],
                                "properties": {
                                    "cell": {
                                        "type": "array",
                                        "minItems": 3,
                                        "maxItems": 3,
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                            "minItems": 3,
                                            "maxItems": 3,
                                        },
                                    },
                                    "pbc": {
                                        "type": "array",
                                        "items": {"type": "boolean"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "compose-view"}},
                            },
                            "then": {
                                "properties": {
                                    "displaySupercell": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 1, "maximum": 64},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "translation": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "translationMode": {"enum": ["cartesian", "fractional"]},
                                    "centerMotif": {
                                        "type": "object",
                                        "anyOf": [
                                            {"required": ["indices"]},
                                            {"required": ["references"]},
                                        ],
                                        "properties": {
                                            "indices": {
                                                "type": "array",
                                                "items": {"type": "integer", "minimum": 0},
                                                "minItems": 1,
                                                "uniqueItems": True,
                                            },
                                            "references": {
                                                "type": "array",
                                                "minItems": 1,
                                                "items": {
                                                    "type": "object",
                                                    "required": ["index", "cellOffset"],
                                                    "properties": {
                                                        "index": {"type": "integer", "minimum": 0},
                                                        "cellOffset": {
                                                            "type": "array",
                                                            "items": {"type": "integer"},
                                                            "minItems": 3,
                                                            "maxItems": 3,
                                                        },
                                                    },
                                                },
                                            },
                                            "targetFractional": {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 3,
                                                "maxItems": 3,
                                            },
                                            "axes": {
                                                "type": "array",
                                                "items": {"enum": ["a", "b", "c"]},
                                                "minItems": 1,
                                                "uniqueItems": True,
                                            },
                                        },
                                    },
                                    "viewDirection": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "viewFromCellAxis": {
                                        "enum": ["+a", "-a", "+b", "-b", "+c", "-c"],
                                    },
                                    "screenUp": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "screenUpCellAxis": {
                                        "enum": ["+a", "-a", "+b", "-b", "+c", "-c"],
                                    },
                                    "verticalReferences": {
                                        "type": "array",
                                        "minItems": 2,
                                        "maxItems": 2,
                                        "items": {
                                            "type": "object",
                                            "required": ["index", "cellOffset"],
                                            "properties": {
                                                "index": {"type": "integer", "minimum": 0},
                                                "cellOffset": {
                                                    "type": "array",
                                                    "items": {"type": "integer"},
                                                    "minItems": 3,
                                                    "maxItems": 3,
                                                },
                                            },
                                        },
                                    },
                                    "target": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "targetIndices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "targetReferences": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["index", "cellOffset"],
                                            "properties": {
                                                "index": {"type": "integer", "minimum": 0},
                                                "cellOffset": {
                                                    "type": "array",
                                                    "items": {"type": "integer"},
                                                    "minItems": 3,
                                                    "maxItems": 3,
                                                },
                                            },
                                        },
                                    },
                                    "fitIndices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "fitReferences": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["index", "cellOffset"],
                                            "properties": {
                                                "index": {"type": "integer", "minimum": 0},
                                                "cellOffset": {
                                                    "type": "array",
                                                    "items": {"type": "integer"},
                                                    "minItems": 3,
                                                    "maxItems": 3,
                                                },
                                            },
                                        },
                                    },
                                    "preserveOrientation": {"type": "boolean"},
                                    "atomDisplayMode": {"enum": ["2d", "3d"]},
                                    "projection": {"enum": ["orthographic", "perspective"]},
                                    "fit": {"enum": ["displayed", "references", "none"]},
                                    "padding": {"type": "number", "minimum": 0, "maximum": 0.4},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "set-visual-label"}},
                            },
                            "then": {
                                "required": ["indices", "label"],
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "label": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "style-atoms"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["indices"]},
                                    {"required": ["labels"]},
                                    {"required": ["elements"]},
                                ],
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "labels": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "elements": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                                    "material": {"enum": ["standard", "metal", "rubber", "unlit"]},
                                    "opacity": {"type": "number", "minimum": 0, "maximum": 1},
                                    "radiusAngstrom": {"type": "number", "exclusiveMinimum": 0},
                                    "radiusScale": {"type": "number", "exclusiveMinimum": 0},
                                    "affectBonds": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "configure-bonds"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["pairs"]},
                                    {"required": ["indexPairs"]},
                                ],
                                "properties": {
                                    "disableUnspecified": {"type": "boolean"},
                                    "clearEndpointOverrides": {"type": "boolean"},
                                    "indexPairs": {
                                        "type": "array",
                                        "items": {
                                            "type": "array",
                                            "items": {"type": "integer", "minimum": 0},
                                            "minItems": 2,
                                            "maxItems": 2,
                                        },
                                    },
                                    "pairs": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["labels"],
                                            "properties": {
                                                "labels": {
                                                    "type": "array",
                                                    "items": {"type": "string", "minLength": 1},
                                                    "minItems": 2,
                                                    "maxItems": 2,
                                                },
                                                "enabled": {"type": "boolean"},
                                                "maximumAngstrom": {"type": "number", "minimum": 0},
                                                "style": {"enum": ["cylinder", "flat"]},
                                                "material": {"enum": ["standard", "metal", "rubber", "unlit"]},
                                                "thicknessAngstrom": {"type": "number", "exclusiveMinimum": 0},
                                                "colorMode": {"enum": ["split", "custom"]},
                                                "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                                                "opacity": {"type": "number", "minimum": 0.05, "maximum": 1},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scatter-atoms"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["entries"]},
                                    {"required": ["element", "count"]},
                                ],
                                "properties": {
                                    "entries": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["element", "count"],
                                            "properties": {
                                                "element": {"type": "string", "minLength": 1},
                                                "label": {"type": "string", "minLength": 1},
                                                "count": {
                                                    "type": "integer", "minimum": 1, "maximum": 100000
                                                },
                                            },
                                        },
                                    },
                                    "element": {"type": "string", "minLength": 1},
                                    "label": {"type": "string", "minLength": 1},
                                    "count": {"type": "integer", "minimum": 1, "maximum": 100000},
                                    "regionMode": {"enum": ["cell", "box", "regions"]},
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                    "placementMode": {"enum": ["random", "homogeneous", "regular"]},
                                    "regularSpacing": {"type": "number", "exclusiveMinimum": 0},
                                    "coordinateBasis": {"enum": ["cartesian", "fractional"]},
                                    "pbcAware": {"type": "boolean"},
                                    "seed": {"type": ["integer", "null"], "minimum": 0},
                                    "freezeExisting": {"type": "boolean"},
                                    "cutoffBasis": {"enum": ["covalent", "vdw", "pairwise"]},
                                    "cutoffScale": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 3
                                    },
                                    "pairCutoffs": {"type": "object"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scatter-molecules"}},
                            },
                            "then": {
                                "anyOf": [
                                    {"required": ["molecules"]},
                                    {"required": ["molecule", "count"]},
                                ],
                                "properties": {
                                    "molecules": {
                                        "type": "array",
                                        "minItems": 1,
                                        "items": {
                                            "type": "object",
                                            "required": ["name", "count"],
                                            "properties": {
                                                "name": {"type": "string", "minLength": 1},
                                                "label": {"type": "string", "minLength": 1},
                                                "count": {
                                                    "type": "integer", "minimum": 1, "maximum": 20000
                                                },
                                            },
                                        },
                                    },
                                    "molecule": {"type": "string", "minLength": 1},
                                    "label": {"type": "string", "minLength": 1},
                                    "count": {"type": "integer", "minimum": 1, "maximum": 20000},
                                    "regionMode": {"enum": ["cell", "box", "regions"]},
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                    "placementMode": {"enum": ["random", "homogeneous", "regular"]},
                                    "regularSpacing": {"type": "number", "exclusiveMinimum": 0},
                                    "coordinateBasis": {"enum": ["cartesian", "fractional"]},
                                    "pbcAware": {"type": "boolean"},
                                    "randomOrientation": {"type": "boolean"},
                                    "rigidMolecules": {"type": "boolean"},
                                    "quantityMode": {"enum": ["count", "density"]},
                                    "targetDensityGcm3": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 100
                                    },
                                    "seed": {"type": ["integer", "null"], "minimum": 0},
                                    "freezeExisting": {"type": "boolean"},
                                    "cutoffBasis": {"enum": ["covalent", "vdw", "pairwise"]},
                                    "cutoffScale": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 3
                                    },
                                    "pairCutoffs": {"type": "object"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "update-add-atoms-region"}},
                            },
                            "then": {
                                "properties": {
                                    "regions": {
                                        "type": "array",
                                        "maxItems": 32,
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "role", "bounds"],
                                            "properties": {
                                                "id": {"type": "string", "minLength": 1},
                                                "name": {"type": "string", "minLength": 1},
                                                "role": {"enum": ["allow", "reject"]},
                                                "bounds": {
                                                    "type": "array",
                                                    "items": {"type": "number"},
                                                    "minItems": 6,
                                                    "maxItems": 6,
                                                },
                                            },
                                        },
                                    },
                                    "regionId": {"type": "string", "minLength": 1},
                                    "regionName": {"type": "string", "minLength": 1},
                                    "bounds": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 6,
                                        "maxItems": 6,
                                    },
                                    "regionRole": {
                                        "enum": ["allow", "reject", "allowed", "prohibited"]
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scale-add-atoms-regions"}},
                            },
                            "then": {
                                "required": ["regionIds", "factor"],
                                "properties": {
                                    "regionIds": {
                                        "type": "array",
                                        "minItems": 1,
                                        "uniqueItems": True,
                                        "items": {"type": "string", "minLength": 1},
                                    },
                                    "factor": {"type": "number", "exclusiveMinimum": 0},
                                    "axis": {"enum": ["ALL", "X", "Y", "Z"]},
                                    "pivot": {
                                        "oneOf": [
                                            {"const": "selection"},
                                            {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 3,
                                                "maxItems": 3,
                                            },
                                        ],
                                    },
                                    "regionMic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "scale-selection"}},
                            },
                            "then": {
                                "required": ["factor"],
                                "properties": {
                                    "factor": {"type": "number", "exclusiveMinimum": 0},
                                    "axis": {"enum": ["ALL", "X", "Y", "Z"]},
                                    "pivot": {
                                        "oneOf": [
                                            {"enum": ["com", "active", "origin", "cell"]},
                                            {
                                                "type": "array",
                                                "items": {"type": "number"},
                                                "minItems": 3,
                                                "maxItems": 3,
                                            },
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {"name": {"const": "relax-added-atoms"}},
                            },
                            "then": {
                                "properties": {
                                    "calculator": _AI_REPULSION_CALCULATOR_SCHEMA,
                                    "pairCutoffs": {"type": "object"},
                                    "cutoffMode": {"enum": ["absolute", "scaled"]},
                                    "cutoffDistance": {
                                        "type": "number", "minimum": 0.01, "maximum": 100
                                    },
                                    "cutoffScale": {
                                        "type": "number", "minimum": 0.05, "maximum": 3
                                    },
                                    "freezeExisting": {"type": "boolean"},
                                    "strength": {"type": "number", "minimum": 0, "maximum": 1000},
                                    "boundaryStrength": {
                                        "type": "number", "exclusiveMinimum": 0, "maximum": 1000
                                    },
                                    "fmax": {"type": "number", "exclusiveMinimum": 0},
                                    "steps": {"type": "integer", "minimum": 1, "maximum": 100000},
                                    "device": {"enum": ["cpu", "cuda"]},
                                    "cpuThreads": {"type": "integer", "minimum": 1},
                                    "mic": {"type": "boolean"},
                                    "constrainToDomain": {"type": "boolean"},
                                    "allowEscape": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "clear-relaxation-trajectory"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "retain": {"enum": ["displayed", "final"]},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-atom-colorscale"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "enabled": {"type": "boolean"},
                                    "field": {"type": "string", "minLength": 1},
                                    "map": {"type": "string", "minLength": 1},
                                    "customMap": {
                                        "type": "object",
                                        "required": ["mode", "stops"],
                                        "properties": {
                                            "mode": {"enum": ["continuous", "discrete"]},
                                            "stops": {
                                                "type": "array",
                                                "minItems": 2,
                                                "maxItems": 64,
                                                "items": {
                                                    "type": "object",
                                                    "required": ["position", "color"],
                                                    "properties": {
                                                        "position": {
                                                            "type": "number",
                                                            "minimum": 0,
                                                            "maximum": 1,
                                                        },
                                                        "color": {
                                                            "type": "string",
                                                            "pattern": "^#[0-9A-Fa-f]{6}$",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                    "reverse": {"type": "boolean"},
                                    "scope": {"enum": ["all", "selected"]},
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "uniqueItems": True,
                                    },
                                    "autoRange": {"type": "boolean"},
                                    "rangeMode": {
                                        "enum": ["current", "trajectory", "manual"],
                                    },
                                    "minimum": {"type": "number"},
                                    "maximum": {"type": "number"},
                                    "gamma": {
                                        "type": "number",
                                        "minimum": 0.1,
                                        "maximum": 5.0,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "add-volumetric-plane"},
                                },
                            },
                            "then": {
                                "required": ["datasetId", "hkl"],
                                "properties": {
                                    "datasetId": {"type": "string", "minLength": 1},
                                    "planeName": {"type": "string", "minLength": 1},
                                    "hkl": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "offsetAngstrom": {"type": "number"},
                                    "resolution": {"enum": [128, 256, 512, 1024]},
                                    "colormap": {"type": "string", "minLength": 1},
                                    "reverse": {"type": "boolean"},
                                    "autoRange": {"type": "boolean"},
                                    "vmin": {"type": "number"},
                                    "vmax": {"type": "number"},
                                    "opacity": {
                                        "type": "number", "minimum": 0.05, "maximum": 1
                                    },
                                    "visible": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "update-volumetric-planes"},
                                },
                            },
                            "then": {
                                "required": ["planeIds"],
                                "properties": {
                                    "planeIds": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "datasetId": {"type": "string", "minLength": 1},
                                    "planeName": {"type": "string", "minLength": 1},
                                    "hkl": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "offsetAngstrom": {"type": "number"},
                                    "resolution": {"enum": [128, 256, 512, 1024]},
                                    "colormap": {"type": "string", "minLength": 1},
                                    "reverse": {"type": "boolean"},
                                    "autoRange": {"type": "boolean"},
                                    "vmin": {"type": "number"},
                                    "vmax": {"type": "number"},
                                    "opacity": {
                                        "type": "number", "minimum": 0.05, "maximum": 1
                                    },
                                    "visible": {"type": "boolean"},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "remove-volumetric-planes"},
                                },
                            },
                            "then": {
                                "required": ["planeIds"],
                                "properties": {
                                    "planeIds": {
                                        "type": "array",
                                        "items": {"type": "string", "minLength": 1},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-interface-theme"},
                                },
                            },
                            "then": {
                                "required": ["theme"],
                                "properties": {
                                    "theme": {"enum": ["system", "light", "dark"]},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "restore-app-visual-defaults"},
                                },
                            },
                            "then": {
                                "required": ["confirm"],
                                "properties": {
                                    "confirm": {"const": True},
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "load-commensurate-guest"},
                                },
                            },
                            "then": {
                                "required": ["path"],
                                "properties": {
                                    "path": {"type": "string", "minLength": 1},
                                    "format": {"type": "string"},
                                    "calculate": {"type": "boolean"},
                                    "gap": {
                                        "type": "number", "minimum": 0, "maximum": 20
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "calculate-commensurate"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "axis": {"const": "Z"},
                                    "mode": {"enum": ["same-lattice", "host-guest"]},
                                    "strainTarget": {"enum": ["host", "guest"]},
                                    "strainTolerance": {
                                        "type": "number", "minimum": 0, "maximum": 0.25
                                    },
                                    "maxIndex": {
                                        "type": "integer", "minimum": 2, "maximum": 64
                                    },
                                    "maxAreaRatio": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": MAX_LATTICE_MATCH_AREA_RATIO,
                                    },
                                    "angleDeg": {"type": "number"},
                                    "gap": {
                                        "type": "number", "minimum": 0, "maximum": 20
                                    },
                                    "showAtoms": {"type": "boolean"},
                                    "snap": {"type": "boolean"},
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "uniqueItems": True,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "set-registry-translation"},
                                },
                            },
                            "then": {
                                "required": ["coordinates"],
                                "properties": {
                                    "coordinates": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 2,
                                        "maxItems": 3,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "calculate-registry-map"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "metric": {"enum": ["short-contact", "bond-strain"]},
                                    "gridX": {
                                        "type": "integer", "minimum": 4, "maximum": 160
                                    },
                                    "gridY": {
                                        "type": "integer", "minimum": 4, "maximum": 160
                                    },
                                    "pairCutoffs": {"type": "object"},
                                    "hkl": {
                                        "type": "array",
                                        "prefixItems": [
                                            {"type": "integer"},
                                            {"type": "integer"},
                                            {"type": "integer"},
                                        ],
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "start-registry-relaxation"},
                                },
                            },
                            "then": {
                                "properties": {
                                    "indices": {
                                        "type": "array",
                                        "items": {"type": "integer", "minimum": 0},
                                        "minItems": 1,
                                        "uniqueItems": True,
                                    },
                                    "hkl": {
                                        "type": "array",
                                        "prefixItems": [
                                            {"type": "integer"},
                                            {"type": "integer"},
                                            {"type": "integer"},
                                        ],
                                        "minItems": 3,
                                        "maxItems": 3,
                                    },
                                    "space": {"enum": ["plane", "cartesian", "3d"]},
                                    "maxDisplacement": {
                                        "type": "number", "exclusiveMinimum": 0
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "enum": [
                                            "run-registry-relaxation",
                                            "start-relaxation",
                                        ],
                                    },
                                },
                            },
                            "then": {
                                "properties": {
                                    "fmax": {"type": "number", "exclusiveMinimum": 0},
                                    "steps": {
                                        "type": "integer", "minimum": 1, "maximum": 100000
                                    },
                                    "calculator": _AI_REPULSION_CALCULATOR_SCHEMA,
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "load-volumetric"},
                                },
                            },
                            "then": {
                                "required": ["path"],
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "format": {"type": "string"},
                                    "precision": {
                                        "enum": [
                                            "fp32", "float32",
                                            "fp64", "float64",
                                        ],
                                    },
                                },
                            },
                        },
                        {
                            "if": {
                                "required": ["name"],
                                "properties": {
                                    "name": {"const": "show-volumetric"},
                                },
                            },
                            "then": {
                                "required": ["datasetId", "level"],
                                "properties": {
                                    "datasetId": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                    "level": {"type": "number"},
                                    "surfaceMode": {
                                        "enum": ["single", "signed"],
                                    },
                                    "stepSize": {"enum": [1, 2, 4]},
                                    "smearingSigma": {
                                        "type": "number",
                                        "minimum": 0,
                                        "maximum": 8,
                                    },
                                    "smoothingIterations": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "maximum": 30,
                                    },
                                    "opacity": {
                                        "type": "number",
                                        "minimum": 0.05,
                                        "maximum": 1,
                                    },
                                    "positiveColor": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                    "negativeColor": {
                                        "type": "string",
                                        "pattern": "^#[0-9A-Fa-f]{6}$",
                                    },
                                },
                                "allOf": [
                                    {
                                        "if": {
                                            "required": ["surfaceMode"],
                                            "properties": {
                                                "surfaceMode": {
                                                    "const": "signed",
                                                },
                                            },
                                        },
                                        "then": {
                                            "properties": {
                                                "level": {
                                                    "not": {"const": 0},
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                    "additionalProperties": True,
                },
            ],
        },
        "camera": {
            "type": "object",
            "description": (
                "Use axis for a deterministic +/-X, +/-Y, or +/-Z view; use "
                "position/target/up for an explicit camera; fit='structure' "
                "frames the complete structure; orbit applies screen-relative "
                "left/right/up/down/roll-cw/roll-ccw rotations."
            ),
            "additionalProperties": True,
            "properties": {
                "axis": {
                    "enum": ["+X", "-X", "+Y", "-Y", "+Z", "-Z"],
                },
                "position": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "target": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "up": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                },
                "projection": {"enum": ["orthographic", "perspective"]},
                "fit": {"enum": ["structure", "commensurate"]},
                "orbit": {
                    "type": "object",
                    "required": ["direction"],
                    "properties": {
                        "direction": {
                            "enum": [
                                "left", "right", "up", "down",
                                "roll-cw", "roll-ccw",
                            ],
                        },
                        "degrees": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                            "maximum": 360,
                        },
                    },
                },
            },
        },
        "renderArea": {
            "type": "object",
            "description": (
                "Persistent image, video, and HTML framing. Enable it to show "
                "the render gate, follow the viewport while composing, or set "
                "an independent camera that remains fixed while the scene changes."
            ),
            "additionalProperties": False,
            "properties": {
                "enabled": {"type": "boolean"},
                "followViewport": {"type": "boolean"},
                "fromCurrentView": {"type": "boolean"},
                "camera": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "position": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "target": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "up": {
                            "type": "array", "items": {"type": "number"},
                            "minItems": 3, "maxItems": 3,
                        },
                        "projection": {"enum": ["orthographic", "perspective"]},
                        "fov": {
                            "type": "number", "exclusiveMinimum": 1,
                            "exclusiveMaximum": 179,
                        },
                        "zoom": {"type": "number", "exclusiveMinimum": 0},
                        "ortho_scale": {"type": "number", "exclusiveMinimum": 0},
                        "near": {"type": "number", "exclusiveMinimum": 0},
                        "far": {"type": "number", "exclusiveMinimum": 0},
                        "aspect": {"type": "number", "exclusiveMinimum": 0},
                    },
                },
            },
        },
    },
}

AI_OPERATION_PARAMETERS = {
    "compose-view": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [
            "displaySupercell", "translation", "translationMode", "centerMotif",
            "viewDirection", "viewFromCellAxis", "screenUp", "screenUpCellAxis",
            "verticalReferences", "target", "targetIndices", "targetReferences",
            "fitIndices", "fitReferences", "preserveOrientation", "atomDisplayMode",
            "projection", "fit", "padding",
        ],
        "notes": (
            "Creates a reproducible periodic composition without changing ASE coordinates. "
            "displaySupercell is visual replication, not set-supercell. centerMotif translates "
            "the periodic motif to targetFractional along chosen a/b/c axes using atom indices "
            "or explicit periodic references. viewDirection is the target-to-camera vector; "
            "viewFromCellAxis accepts +/-a, +/-b, or +/-c. verticalReferences or an explicit "
            "screen-up vector fixes camera roll. target references may include cellOffset. "
            "fit=displayed includes the actual centered replicas; fit=references frames only "
            "fitIndices/fitReferences so visible motif count can match a reference panel. "
            "preserveOrientation=true keeps the current camera direction and roll while target "
            "and fit change; it cannot be combined with direction or screen-up fields. "
            "atomDisplayMode selects the complete flat 2D or material-aware 3D scene. "
            "padding is the requested fractional border on each image edge."
        ),
    },
    "set-visual-label": {
        "mode": "view",
        "required": ["indices", "label"],
        "optional": [],
        "notes": (
            "Assigns a visualization-only label to exact zero-based atom indices while "
            "preserving ASE elements, coordinates, order, cell, PBC, and constraints. "
            "A topology-compatible trajectory receives the same index mapping in every frame; "
            "otherwise only the active frame is relabelled and the GUI shows a scope notice."
        ),
    },
    "style-atoms": {
        "mode": "view-or-edit",
        "required": ["indices-or-labels-or-elements"],
        "optional": [
            "indices", "labels", "elements", "color", "material", "opacity",
            "radiusAngstrom", "radiusScale", "affectBonds",
        ],
        "notes": (
            "Applies deterministic visualization overrides to the union of exact indices, "
            "visual labels, and ASE elements. radiusAngstrom is the final rendered radius in "
            "Angstrom after the global atom scale; radiusScale is an explicit per-index "
            "multiplier and is mutually exclusive with radiusAngstrom. Chemical identity and "
            "coordinates never change. affectBonds copies material and opacity to bonds "
            "touching the styled indices."
        ),
    },
    "configure-bonds": {
        "mode": "view-or-edit",
        "required": ["pairs-or-indexPairs"],
        "optional": ["pairs", "indexPairs", "disableUnspecified", "clearEndpointOverrides"],
        "notes": (
            "Configures visual bonds by unordered visual-label pair. Each pair may set enabled, "
            "maximumAngstrom, style, material, thicknessAngstrom, colorMode, color, and opacity. "
            "disableUnspecified=true makes the supplied enabled pairs an authoritative allow-list "
            "and disables every other current label pair. An empty pairs array with that flag "
            "means no visual bonds. clearEndpointOverrides=true removes stale atom-level bond "
            "material/color/opacity overrides before pair appearance is applied. Zero or "
            "enabled=false removes one pair. indexPairs switches to exact zero-based atom-pair "
            "selection when a figure highlights only selected edges. An indexPairs-only request "
            "preserves every label-pair cutoff, range, and appearance setting; "
            "disableUnspecified affects label policies only when pairs is explicitly present."
        ),
    },
    "set-atom-colorscale": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [
            "enabled", "field", "map", "customMap", "reverse", "scope", "autoRange",
            "rangeMode", "minimum", "maximum", "gamma", "indices",
        ],
        "notes": (
            "Colors atoms by x/y/z, force norm, or a discovered numeric per-atom "
            "ASE array/calculator result. scope is all or selected. rangeMode is "
            "current, trajectory, or manual; every trajectory frame uses the same "
            "resolved minimum and maximum. Use map=custom with a customMap containing "
            "two or more ordered 0-1 color stops and continuous or discrete mode. "
            "gamma controls contrast. For scope=selected, optional indices freezes "
            "the target atom indices independently of later GUI selection changes. "
            "Without indices, the scope follows the live GUI selection. Disabling it immediately restores the saved "
            "label and element colors."
        ),
    },
    "set-interface-theme": {
        "mode": "view-or-edit",
        "required": ["theme"],
        "optional": [],
        "notes": (
            "theme is system, light, or dark. system follows the browser/OS "
            "color-scheme preference and is the built-in default."
        ),
    },
    "set-personal-visual-default": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
        "notes": (
            "Persists the current reusable visual settings for this OS user. "
            "Coordinates, trajectory data, absolute camera placement, and "
            "per-atom appearance overrides are excluded."
        ),
    },
    "restore-app-visual-defaults": {
        "mode": "view-or-edit",
        "required": ["confirm"],
        "optional": [],
        "notes": (
            "Destructively deletes the saved personal visual default and applies "
            "the built-in v_ase visual settings to the active tab. confirm must "
            "be true and an agent must obtain human approval first."
        ),
    },
    "wrap": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["applyConstraints"],
        "notes": "Requires a usable cell. View mode wraps the displayed atoms only; Edit mode wraps ASE positions with the requested constraint handling.",
    },
    "translate-all": {
        "mode": "edit",
        "required": ["vector"],
        "optional": ["coordinateMode", "applyConstraints"],
        "notes": "coordinateMode is cartesian or fractional.",
    },
    "set-unit-cell": {
        "mode": "edit",
        "required": ["cell"],
        "optional": ["pbc"],
        "notes": (
            "Defines the 3 x 3 ASE cell without scaling atom coordinates. pbc defaults "
            "to [true,true,true]. This also creates a usable scratch document when no "
            "atoms have been loaded."
        ),
    },
    "build-bulk": {
        "mode": "edit",
        "required": ["formula"],
        "optional": [
            "crystalStructure", "cellMode", "a", "b", "c", "alpha",
            "covera", "u", "basis", "confirmReplace",
        ],
        "notes": (
            "Builds a periodic crystal with ase.build.bulk. Query "
            "/api/build/bulk/catalog/{session_id} for installed-ASE reference "
            "materials and compatible cell shapes, then preview through "
            "/api/build/bulk/preview/{session_id}. Custom compounds such as CuO "
            "require crystalStructure and a. c and covera are mutually exclusive. "
            "The operation replaces the active structure and trajectory; an existing "
            "document requires explicit human approval and confirmReplace=true."
        ),
    },
    "set-supercell": {
        "mode": "edit",
        "required": ["reps"],
        "optional": ["applyConstraints"],
        "notes": "reps contains three integers from 1 through 64.",
    },
    "make-supercell": {
        "mode": "edit",
        "required": ["matrix"],
        "optional": ["applyConstraints"],
        "notes": "matrix is a 3 x 3 integer transformation matrix.",
    },
    "add-atom": {
        "mode": "edit",
        "required": ["position", "label-or-element"],
        "optional": ["label", "element"],
    },
    "scatter-atoms": {
        "mode": "edit",
        "required": ["entries-or-element-count"],
        "optional": [
            "entries", "element", "label", "count", "regionMode", "regions", "bounds",
            "regionRole", "regionMic", "constrainToDomain", "allowEscape",
            "placementMode", "regularSpacing", "coordinateBasis", "pbcAware",
            "seed", "freezeExisting", "cutoffBasis", "cutoffScale", "pairCutoffs",
        ],
        "notes": (
            "Starts an Add Atoms session or appends one or more element/label populations "
            "to the active session after placement relaxation is inactive. The first "
            "pre-session structure remains the immutable host across every placement. "
            "placementMode is random, homogeneous, or regular. regular uses optional regularSpacing in A. "
            "coordinateBasis=cartesian optimizes "
            "physical nearest-neighbor spacing in angstrom and is the default; fractional "
            "optimizes normalized cell-coordinate spacing. Random sampling remains volume-uniform "
            "under either basis because the cell transform has a constant Jacobian. "
            "regions defines up to 32 stable-id Cartesian Allow/Reject regions. The exact domain is "
            "the unit cell intersected with the Allow union (or the full cell when no Allow exists), "
            "minus the Reject union. Periodic region images are clipped to the triclinic primary cell "
            "without voxel approximation. A structure without a finite cell requires an Allow region. "
            "Legacy regionMode=box remains accepted. constrainToDomain defaults "
            "to false, so the region controls initial sampling without confining relaxation; "
            "allowEscape is the inverse compatibility field. The default "
            "temporarily fixes every pre-session atom. Follow with common start-relaxation "
            "and finish-add-atoms, append another batch, or use cancel-add-atoms to restore "
            "the exact baseline."
        ),
    },
    "scatter-molecules": {
        "mode": "edit",
        "required": ["molecules-or-molecule-count"],
        "optional": [
            "molecules", "molecule", "label", "count", "regionMode", "regions", "bounds",
            "regionRole", "regionMic", "constrainToDomain", "allowEscape",
            "placementMode", "regularSpacing", "coordinateBasis", "pbcAware",
            "randomOrientation", "rigidMolecules", "seed", "freezeExisting",
            "quantityMode", "targetDensityGcm3", "cutoffBasis", "cutoffScale", "pairCutoffs",
        ],
        "notes": (
            "Starts an Add Molecules session or appends molecules to the active Add session "
            "from the installed ASE G2 molecule catalog. "
            "Query /api/add-session/molecules/{session_id} before choosing a name. Molecule "
            "coordinates are placed and rotated about ASE's native coordinate origin without recentering. "
            "randomOrientation uses Haar-uniform SO(3) rotations. rigidMolecules defaults to "
            "true and preserves each molecule's internal distances during atomwise pairwise "
            "repulsion; false permits ordinary atomwise relaxation. quantityMode=density computes "
            "integer molecule counts from exact accessible volume and reports the realized density. "
            "The placement, region, "
            "host-freeze, relaxation, finish, and cancel semantics match scatter-atoms."
        ),
    },
    "update-add-atoms-region": {
        "mode": "edit",
        "required": ["active-cartesian-add-atoms-session"],
        "optional": [
            "regions", "regionId", "regionName", "bounds", "regionRole",
            "regionMic", "constrainToDomain", "allowEscape",
        ],
        "notes": (
            "Replaces all active Allow/Reject regions, or updates one stable regionId, without moving "
            "staged atoms. Regions can translate as a group but cannot be rotated."
        ),
    },
    "relax-added-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-session"],
        "optional": [
            "calculator", "pairCutoffs", "cutoffMode", "cutoffDistance",
            "cutoffScale", "freezeExisting", "strength", "boundaryStrength",
            "fmax", "steps", "device", "cpuThreads", "mic",
            "constrainToDomain", "allowEscape",
        ],
        "notes": (
            "Compatibility alias for the same shared placement-relaxation path used by "
            "start-relaxation. It starts asynchronous FIRE with one "
            "AdditionRepulsionCalculator attached to the complete staged structure. "
            "device selects CPU or CUDA and "
            "cpuThreads controls CPU parallelism; CUDA falls back to CPU when unavailable. "
            "Every optimizer step is retained in the Add-mode trajectory. Poll "
            "describe.addAtoms or consume collaboration events until is_relaxing is false."
        ),
    },
    "stop-added-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-relaxation"],
        "optional": [],
    },
    "finish-add-atoms": {
        "mode": "edit",
        "required": ["inactive-add-atoms-relaxation"],
        "optional": [],
        "notes": "Commits only inserted atoms; every host coordinate, constraint, and array is restored exactly.",
    },
    "cancel-add-atoms": {
        "mode": "edit",
        "required": ["active-add-atoms-session"],
        "optional": [],
        "notes": "Restores the complete pre-session structure and history state.",
    },
    "delete-selection": {
        "mode": "view-or-edit",
        "required": ["selection-or-indices"],
        "optional": ["indices"],
        "notes": (
            "View mode hides the exact selected visual instances without "
            "changing ASE atoms. Edit mode deletes the corresponding base "
            "atom indices from the physical structure."
        ),
    },
    "set-identity": {
        "mode": "edit",
        "required": ["label", "selection-or-indices"],
        "optional": ["indices", "element", "applyConstraints"],
    },
    "set-constraints": {
        "mode": "edit",
        "required": ["selection-or-indices"],
        "optional": [
            "indices", "fixAtoms", "kind", "vector",
            "clearDirectional", "applyConstraints",
        ],
        "notes": "kind is fixed_line or fixed_plane; vector has three components.",
    },
    "move-selection": {
        "mode": "edit",
        "required": ["vector", "selection-or-indices"],
        "optional": ["indices", "applyConstraints"],
    },
    "rotate-selection": {
        "mode": "edit",
        "required": ["angleDeg", "selection-or-indices"],
        "optional": ["indices", "axis", "pivot", "applyConstraints"],
        "notes": (
            "axis defaults to [0,0,1]. pivot is com, active, origin, cell, "
            "or an explicit three-number position."
        ),
    },
    "scale-selection": {
        "mode": "edit",
        "required": ["factor", "selection-or-indices"],
        "optional": ["indices", "axis", "pivot", "applyConstraints"],
        "notes": (
            "Scales physical Cartesian atom coordinates about the pivot without changing "
            "atom or bond radii. axis is X, Y, Z, or ALL and defaults to ALL. pivot is "
            "com, active, origin, cell, or an explicit three-number position."
        ),
    },
    "scale-add-atoms-regions": {
        "mode": "edit",
        "required": ["regionIds", "factor", "active-add-atoms-session"],
        "optional": ["axis", "pivot", "regionMic", "constrainToDomain", "allowEscape"],
        "notes": (
            "Scales Cartesian insertion-region bounds about their shared center, or an "
            "explicit three-number pivot. axis is X, Y, Z, or ALL."
        ),
    },
    "rotate-to-commensurate": {
        "mode": "edit",
        "required": ["angleDeg", "selection-or-indices"],
        "optional": [
            "indices", "axis", "pivot", "maxAngleDifferenceDeg",
            "strainTolerance", "maxIndex", "maxAreaRatio", "showAtoms",
            "applyConstraints",
        ],
        "notes": (
            "Finds the nearest validated periodic 2D lattice match, rotates the "
            "selected layer to that exact angle, and opens the common-cell proposal. "
            "The default is cells-only; showAtoms=true adds the opaque core and muted "
            "one-primitive-cell boundary shell. axis is strictly Z; maxAreaRatio "
            "defaults to 16 and is explicitly limited to 128. No proposal is made "
            "above the requested limit."
        ),
    },
    "load-commensurate-guest": {
        "mode": "view-or-edit",
        "required": ["path"],
        "optional": [
            "format", "calculate", "strainTarget", "strainTolerance",
            "maxAreaRatio", "maxIndex", "angleDeg", "gap", "showAtoms",
        ],
        "notes": (
            "Loads a separate guest structure from inside the GUI launch directory. "
            "gap is guest minimum z minus host maximum z in angstrom and defaults "
            "to 3. Absolute paths and parent-directory traversal are rejected."
        ),
    },
    "remove-commensurate-guest": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
        "notes": "Removes the separately loaded guest and clears its search/proposal, returning the workspace to same-lattice matching.",
    },
    "calculate-commensurate": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [
            "indices", "axis", "mode", "strainTarget", "strainTolerance",
            "maxAreaRatio", "maxIndex", "angleDeg", "gap", "showAtoms", "snap",
        ],
        "notes": (
            "Searches bounded integer common cells about global Z. Same-lattice "
            "mode requires a selected rotating layer before atom preview or "
            "materialization; host-guest mode requires a loaded guest. Cells-only "
            "preview is the default. maxAreaRatio defaults to 16 and accepts 1..128. "
            "Candidate acceptance uses maximum principal strain; the paper projection "
            "reports mean absolute strain and actual host-plus-guest atom counts."
        ),
    },
    "apply-commensurate-cell": {
        "mode": "edit",
        "required": ["active-commensurate-proposal"],
        "optional": [],
        "notes": "Materializes the active validated proposal as the ASE unit cell.",
    },
    "dismiss-commensurate-cell": {
        "mode": "view-or-edit",
        "required": [],
        "optional": [],
        "notes": "Closes the active proposal and restores the pre-preview camera.",
    },
    "calculate-registry-map": {
        "mode": "view-or-edit",
        "required": ["selection-or-indices"],
        "optional": ["indices", "metric", "gridX", "gridY", "pairCutoffs", "hkl"],
        "notes": (
            "Scans one primitive periodic translation cell in the requested (hkl) plane. "
            "metric is short-contact or bond-strain; both are geometry scores, not energies."
        ),
    },
    "center-selection-at-origin": {
        "mode": "view-or-edit",
        "required": ["selection-or-indices"],
        "optional": ["indices"],
        "notes": (
            "Sets visual translation so the selected atom, or the mass-weighted center "
            "of mass of multiple selected atoms, lies at Cartesian origin. ASE positions "
            "and the unit cell are unchanged."
        ),
    },
    "start-registry-relaxation": {
        "mode": "edit",
        "required": ["selection-or-indices"],
        "optional": ["indices", "hkl", "space", "maxDisplacement"],
        "notes": (
            "Activates rigid translation for a selected component. space=plane (default) "
            "uses two coordinates in the periodic (hkl) plane; space=cartesian uses one "
            "common x/y/z translation in Angstrom with maxDisplacement as the bound "
            "for each Cartesian component. Host coordinates, cell vectors, and "
            "selected internal relative coordinates remain invariant."
        ),
    },
    "set-registry-translation": {
        "mode": "edit",
        "required": ["active-registry-relaxation", "coordinates"],
        "optional": [],
        "notes": (
            "Sets two unwrapped plane-lattice coefficients in plane mode or three "
            "Cartesian Angstrom components in 3D mode, without moving the cell or "
            "changing selected internal coordinates."
        ),
    },
    "run-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": ["fmax", "steps", "calculator"],
        "notes": (
            "Optimizes the active two-coordinate plane or three-coordinate Cartesian "
            "rigid translation with the "
            "attached calculator or the default pairwise repulsion calculator. Consume "
            "registry_relax_step events until is_relaxing is false. calculator may "
            "configure absolute pair_cutoffs as independent onset distances in "
            "Angstrom, or cutoff_mode=scaled with reference pair distances and "
            "cutoff_scale; neither cutoff is a hard constraint."
        ),
    },
    "stop-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": [],
    },
    "finish-registry-relaxation": {
        "mode": "edit",
        "required": ["inactive-registry-relaxation"],
        "optional": [],
        "notes": "Commits the rigid translation as one undoable structure edit and exits the mode.",
    },
    "cancel-registry-relaxation": {
        "mode": "edit",
        "required": ["active-registry-relaxation"],
        "optional": [],
        "notes": "Restores the exact pre-mode coordinates and exits without a history entry.",
    },
    "undo": {"mode": "view-or-edit", "required": [], "optional": [],
             "notes": "Undoes the latest available visual or physical edit in the shared GUI history. Describe afterward to verify the affected state."},
    "redo": {"mode": "view-or-edit", "required": [], "optional": [],
             "notes": "Reapplies the latest undone visual or physical edit in the shared GUI history. Describe afterward to verify the affected state."},
    "reset-coordinates": {
        "mode": "edit",
        "required": [],
        "optional": [],
        "notes": "Restores all frames from the document's stored reset baseline as one undoable physical edit.",
    },
    "start-relaxation": {
        "mode": "edit",
        "required": ["attached-calculator-or-active-add-atoms-session"],
        "optional": ["fmax", "steps", "calculator", "applyConstraints"],
        "notes": (
            "When Add Atoms is active, this common operation routes the same calculator, "
            "cutoff, device, fmax, and step contract through placement relaxation while "
            "preserving the immutable pre-session host. Otherwise an ASE calculator must "
            "be attached to the structure. "
            "For the built-in repulsion calculator, calculator accepts device, "
            "cpu_threads, k_repulsion, cutoff_basis, and independent label-pair "
            "pair_cutoffs. Absolute mode interprets each enabled pair value directly "
            "in Angstrom; scaled mode multiplies its reference distance by "
            "cutoff_scale. "
            "The cutoff is the zero-force onset distance, not a guaranteed minimum "
            "separation."
        ),
    },
    "stop-relaxation": {
        "mode": "edit",
        "required": [],
        "optional": [],
        "notes": "Stops the active ordinary or Add Atoms placement optimizer.",
    },
    "clear-relaxation-trajectory": {
        "mode": "edit",
        "required": ["available-relaxation-trajectory"],
        "optional": ["retain"],
        "notes": (
            "Removes the dedicated optimization movie while leaving its mode active. "
            "retain is final by default or displayed to keep the frame currently shown."
        ),
    },
    "exit-relaxation-mode": {
        "mode": "edit",
        "required": [],
        "optional": ["keep"],
        "notes": (
            "Stops an active optimizer if needed, closes the dedicated movie timeline, "
            "and either keeps current coordinates (default) or restores the exact "
            "pre-relaxation structure when keep=false."
        ),
    },
    "refresh-displacements": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["display"],
        "notes": "Optionally updates display settings, then recomputes displacement analysis for the current frame and configured reference/mapping.",
    },
    "load-volumetric": {
        "mode": "view-or-edit",
        "required": ["path"],
        "optional": ["format", "precision"],
        "notes": (
            "path is resolved inside the GUI launch directory. Supported "
            "formats include CHGCAR, LOCPOT, PARCHG, ELFCAR, Cube, and XSF. "
            "precision is fp32/float32 or fp64/float64 and is applied while reading."
        ),
    },
    "show-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetId", "level"],
        "optional": [
            "surfaceMode", "stepSize", "opacity",
            "positiveColor", "negativeColor", "smearingSigma",
            "smoothingIterations",
        ],
        "notes": (
            "surfaceMode is single or signed; stepSize is 1, 2, or 4. "
            "Signed mode renders +abs(level) and -abs(level), requires a "
            "non-zero level, and may return only the sign that still crosses "
            "the displayed field range after smearing. opacity is 0.05-1; "
            "colors are six-digit #RRGGBB values. "
            "smearingSigma is 0-8 grid points and filters only the displayed "
            "field. smoothingIterations is an integer from 0-30 and fairs only "
            "the extracted mesh. The default safety limits are 134,217,728 "
            "source grid points and 2,000,000 output triangles per surface."
        ),
    },
    "add-volumetric-plane": {
        "mode": "view-or-edit",
        "required": ["datasetId", "hkl"],
        "optional": [
            "planeName", "offsetAngstrom", "resolution", "colormap",
            "reverse", "autoRange", "vmin", "vmax", "opacity", "visible",
        ],
        "notes": (
            "Creates one cell-clipped scalar-field plane. hkl is a non-zero "
            "three-number reciprocal-space normal; offsetAngstrom is the signed "
            "distance from the origin along its Cartesian unit normal. If the "
            "offset is omitted, the plane is centered in the displayed supercell."
        ),
    },
    "update-volumetric-planes": {
        "mode": "view-or-edit",
        "required": ["planeIds"],
        "optional": [
            "datasetId", "planeName", "hkl", "offsetAngstrom", "resolution",
            "colormap", "reverse", "autoRange", "vmin", "vmax", "opacity",
            "visible",
        ],
        "notes": (
            "Applies every supplied field to all planeIds as one visual edit. "
            "resolution is 128, 256, 512, or 1024. vmin/vmax are used when "
            "autoRange is false. Invalid IDs or values reject the whole edit."
        ),
    },
    "remove-volumetric-planes": {
        "mode": "view-or-edit",
        "required": ["planeIds"],
        "optional": [],
        "notes": "Removes all requested planar sections as one visual edit.",
    },
    "combine-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetIds", "coefficients"],
        "optional": ["resultName", "precision"],
        "notes": (
            "All grids must have matching dimensions, cell, origin, PBC, and "
            "units and endpoint conventions. resultName names the output; name "
            "is reserved for the operation. Accumulation uses float64 slabs; "
            "output precision defaults to the highest input precision."
        ),
    },
    "remove-volumetric": {
        "mode": "view-or-edit",
        "required": ["datasetId"],
        "optional": [],
        "notes": "Deletes the specified scalar dataset from the document and clears the active surface when it used that dataset. Source files are unchanged.",
    },
    "calculate-rdf": {
        "mode": "view-or-edit",
        "required": [],
        "optional": ["cutoff", "bins", "pairMode", "activePairs"],
        "notes": (
            "pairMode is active, selected, all, or none. selected filters partial "
            "curves to active bonds whose endpoints are both selected in the GUI; "
            "activePairs can provide the same label-pair filter explicitly. Fully "
            "periodic 3D cells use bulk RDF normalization, while finite no-PBC "
            "structures use an unordered-pair probability density. Every periodic "
            "image inside the requested cutoff is counted; the cutoff is not reduced "
            "to a fixed supercell or MIC radius."
        ),
    },
}

AI_EXPORT_PARAMETERS = {
    "image": {
        "optional": ["imageFormat", "width", "height", "options"],
        "notes": "imageFormat is png, jpeg, webp, or pdf.",
    },
    "video": {
        "optional": [
            "container", "width", "height", "fps",
            "interpolationMultiplier", "interpolationMic", "options",
        ],
        "notes": "container is mov or avi and requires a loaded trajectory. Indexed PNG frames preserve every source/interpolated frame without wall-clock sampling. Native dimensions must be even integers in 64..8192; fps is 1..60 and interpolationMultiplier is 1..64. Video is opaque. The result reports exact width, height, fps, frameCount and sourceFrameCount.",
    },
    "poscar": {"optional": [], "notes": "ASE rejects Cartesian directional constraints that cannot be represented as POSCAR selective dynamics for the current cell. Constraints are never silently removed; use project or pickle to preserve them."},
    "pickle": {"optional": []},
    "blender": {"optional": ["includeCell"]},
    "3dm": {
        "optional": ["includeCell"],
        "notes": "Requires the optional rhino3dm dependency.",
    },
    "obj": {"optional": ["includeCell"]},
    "html": {
        "optional": ["width", "height", "options", "embedProject"],
        "notes": "embedProject defaults to false for a lightweight view-only file. HTML dimensions are integers in 256..8192 and the rendered background is opaque.",
    },
    "project": {"optional": []},
    "settings": {"optional": []},
    "rdf-csv": {
        "optional": ["cutoff", "bins", "pairMode", "activePairs"],
        "notes": (
            "Exports the total RDF and currently requested partial curves. "
            "pairMode accepts active, selected, all, or none; selected requires "
            "the browser-derived selected active label pairs or explicit activePairs."
        ),
    },
    "commensurate-csv": {
        "optional": [
            "mode", "strainTarget", "strainTolerance", "maxAreaRatio", "maxIndex",
        ],
        "notes": (
            "Exports angle, host/guest integer matrices, area ratios, residual "
            "strains, and the scientific references used by the bounded search."
        ),
    },
    "registry-csv": {
        "optional": ["indices", "metric", "gridX", "gridY", "pairCutoffs", "hkl"],
        "notes": (
            "Exports the complete periodic (hkl) translation grid, its exact "
            "lattice basis, Cartesian vectors, and geometry metric values."
        ),
    },
}


AI_DESCRIBE_PROFILES = {
    "summary": {
        "default_for_cli": True,
        "description": (
            "Small document, frame, count, identity-group, selection, calculator, "
            "relaxation, revision, and fingerprint summary."
        ),
        "options": [],
        "fields": [
            "protocol", "profile", "units", "document", "documentId", "mode", "frame",
            "frameCount", "playback", "atomCount", "labelCounts", "elementCounts", "cell",
            "pbc", "selection", "relaxation", "identityGroups", "calculator",
            "collaboration", "stateFingerprint", "availableProfiles",
        ],
    },
    "structure": {
        "description": (
            "Compressed identity groups, structure metadata, constraints, and optional "
            "coordinates or complete per-atom arrays."
        ),
        "options": ["includePositions", "includeProperties"],
        "fields": [
            "summary fields", "identityGroups", "constraints", "addAtoms",
            "calculator", "measurement", "propertyCounts", "positions when requested",
            "complete identity/property arrays when requested",
        ],
    },
    "appearance": {
        "description": (
            "Rendering and style state without inactive label-pair tables. Per-index "
            "overrides are summarized unless explicitly requested."
        ),
        "options": ["includeOverrides"],
        "fields": ["summary fields", "identityGroups", "display", "bonding"],
    },
    "bonding": {
        "description": (
            "Active label-pair policies, exact manual index pairs, default bond style, "
            "and optional coordinates or endpoint overrides."
        ),
        "options": ["includePositions", "includeOverrides"],
        "fields": ["summary fields", "identityGroups", "bonding", "positions when requested"],
    },
    "render": {
        "description": (
            "Compact appearance, viewport camera, stored Render Area, image profile, "
            "and the exact effective render camera source."
        ),
        "options": ["includeOverrides"],
        "fields": [
            "summary fields", "identityGroups", "display", "camera", "renderArea",
            "imageExport", "effectiveRender",
        ],
    },
    "analysis": {
        "description": "Current frame-synchronized analysis state only.",
        "options": [],
        "fields": ["summary fields", "analysis"],
    },
    "full": {
        "default_for_browser_compatibility": True,
        "description": (
            "Complete legacy state. Use only when a focused profile cannot answer the task."
        ),
        "options": ["includePositions"],
        "fields": ["complete legacy state"],
    },
}

AI_RENDER_PARAMETERS = {
    "required": [],
    "optional": ["format", "width", "height", "cameraSource", "options"],
    "cameraSource": {
        "enum": ["auto", "viewport", "render-area", "image-export", "explicit"],
        "default": "auto",
        "notes": (
            "auto uses an explicit options.camera first, then the stored Render Area/image "
            "profile camera, then the viewport. The result reports effectiveRender.source "
            "and the exact camera used. explicit requires options.camera."
        ),
    },
    "formats": ["png", "jpg", "webp", "pdf"],
    "dimension_range_pixels": [64, 8192],
    "option_fields": [
        "transparentBackground", "backgroundColor", "includeGrid", "includeAxes",
        "includeCell", "scaleMode", "pixelsPerAngstrom", "sphereQuality",
        "sphereQualityScale", "renderMode", "sunIntensity", "sunPosition",
        "sunTarget", "camera",
    ],
    "result_fields": [
        "protocol", "mimeType", "format", "filename", "bytes", "width", "height",
        "camera", "options", "effectiveRender", "dataUrl",
    ],
    "notes": (
        "Use a small draft render while composing and one exact-size final render. "
        "The CLI omits Base64 unless --print-data-url is requested; use --save instead."
    ),
}



# Parameter contracts are data, shared unchanged by every transport. Older
# clients may still omit fields; typed adapters validate before any mutation.
NUMBER = {"type": "number"}
BOOLEAN = {"type": "boolean"}
STRING = {"type": "string"}
INDEX = {"type": "integer", "minimum": 0}
VECTOR = {"type": "array", "items": NUMBER, "minItems": 3, "maxItems": 3}
INTEGER_VECTOR = {"type": "array", "items": {"type": "integer"}, "minItems": 3, "maxItems": 3}
INDICES = {"type": "array", "items": INDEX, "uniqueItems": True}
PIVOT = {"anyOf": [{"enum": ["com", "active", "origin", "cell"]}, VECTOR]}
PAIR_CUTOFFS = {"type": "object", "additionalProperties": {"type": "number", "minimum": 0}}
RDF_PROPERTIES = {
    "cutoff": {"type": ["number", "null"], "exclusiveMinimum": 0},
    "bins": {"type": "integer", "minimum": 1},
    "pairMode": {"enum": ["active", "selected", "all", "none"]},
    "activePairs": {"type": "array", "items": {
        "type": "array", "items": STRING, "minItems": 2, "maxItems": 2,
    }},
}
PRECISION = {"enum": ["float32", "float64", "fp32", "fp64"]}


def _complete_operation_contracts():
    operation = AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]

    new = {
        "load-settings": ({"path": STRING}, ["path"], "Load saved visual settings from a relative JSON path below the GUI launch directory. Restores appearance, camera and render profile without replacing atom coordinates."),
        "load-structure": ({"path": STRING, "format": STRING, "index": STRING, "runtimeMode": {"enum": ["view", "edit"]}, "confirmReplace": BOOLEAN}, ["path"], "Open a structure, trajectory, volumetric file, .vase project, or project HTML using a relative path below the GUI launch directory. Use the files query to discover paths. Replaces this tab; a nonempty document requires confirmReplace=true and user intent. Project appearance is restored. ASE index defaults to ':'."),
        "append-structure": ({"path": STRING, "format": STRING, "index": STRING, "runtimeMode": {"enum": ["view", "edit"]}}, ["path"], "Append structures as trajectory frames or scalar grids as fields, using a relative path below the GUI launch directory. Project visual settings are ignored when appending."),
        "duplicate-selection": ({"indices": INDICES}, [], "Duplicate selected base atoms in Edit mode, preserving per-atom arrays, constraints, and appearance. Newly inserted atoms become selected."),
        "configure-calculator": ({"calculator": _AI_REPULSION_CALCULATOR_SCHEMA}, ["calculator"], "Configure the attached default repulsion calculator without starting optimization. Visual bond cutoffs are independent. Requires Edit mode."),
        "set-playback": ({"playing": BOOLEAN, "fps": {"type": "number", "minimum": 1, "maximum": 60}, "skip": {"type": "integer", "minimum": 0, "maximum": 999}, "source": {"enum": ["loaded", "relax"]}}, ["playing"], "Start or stop the selected trajectory timeline. Pause before scientific reads or edits; playback advances revisions and frames."),
    }
    for name, (props, required, notes) in new.items():
        AI_OPERATION_PARAMETERS[name] = {"mode": "edit" if name in {"duplicate-selection", "configure-calculator"} else "view-or-edit", "required": required, "optional": [k for k in props if k not in required], "notes": notes}
        operation["properties"]["name"]["enum"].append(name)
        operation["allOf"].append({"if": {"required": ["name"], "properties": {"name": {"const": name}}}, "then": {"properties": deepcopy(props), "required": required}})
    extras = {
        "translate-all": {"vector": VECTOR, "coordinateMode": {"enum": ["cartesian", "fractional"]}},
        "set-supercell": {"reps": {**INTEGER_VECTOR, "items": {"type": "integer", "minimum": 1, "maximum": 64}}},
        "make-supercell": {"matrix": {"type": "array", "items": INTEGER_VECTOR, "minItems": 3, "maxItems": 3}},
        "add-atom": {"position": VECTOR, "label": {"type": "string", "minLength": 1}, "element": {"type": "string", "minLength": 1}},
        "set-identity": {"label": {"type": "string", "minLength": 1}, "element": STRING},
        "set-constraints": {"fixAtoms": BOOLEAN, "kind": {"enum": ["fixed_line", "fixed_plane", "none"]}, "vector": VECTOR, "clearDirectional": BOOLEAN},
        "move-selection": {"vector": VECTOR},
        "rotate-selection": {"angleDeg": NUMBER, "axis": VECTOR, "pivot": PIVOT},
        "rotate-to-commensurate": {"angleDeg": NUMBER, "axis": VECTOR, "pivot": PIVOT, "maxAngleDifferenceDeg": {"type": "number", "minimum": 0}},
        "exit-relaxation-mode": {"keep": BOOLEAN},
        "refresh-displacements": {"display": AI_CONTROL_SCHEMA["properties"]["display"]},
        "combine-volumetric": {
            "datasetIds": {"type": "array", "items": STRING, "minItems": 2},
            "coefficients": {"type": "array", "items": NUMBER, "minItems": 2},
            "resultName": STRING, "precision": PRECISION,
        },
        "remove-volumetric": {"datasetId": {"type": "string", "minLength": 1}},
        "calculate-rdf": {**RDF_PROPERTIES, "bins": {"type": "integer", "minimum": 8, "maximum": 5000}},
    }
    # Share bounded commensurate controls instead of describing loose numbers.
    commensurate = next(b["then"]["properties"] for b in operation["allOf"]
                        if b["if"]["properties"]["name"].get("const") == "calculate-commensurate")
    for name in ("rotate-to-commensurate", "load-commensurate-guest"):
        target = extras.setdefault(name, {})
        for key in AI_OPERATION_PARAMETERS[name]["optional"]:
            if key in commensurate:
                target.setdefault(key, commensurate[key])
    for name, contract in AI_OPERATION_PARAMETERS.items():
        props = extras.setdefault(name, {})
        if "indices" in contract["optional"]:
            props.setdefault("indices", INDICES)
        if "applyConstraints" in contract["optional"]:
            props.setdefault("applyConstraints", BOOLEAN)
        if props:
            required = [key for key in contract["required"] if key in props]
            branch = {"properties": deepcopy(props)}
            if required:
                branch["required"] = required
            if name == "add-atom":
                branch["anyOf"] = [{"required": ["label"]}, {"required": ["element"]}]
            operation["allOf"].append({
                "if": {"required": ["name"], "properties": {"name": {"const": name}}},
                "then": branch,
            })
    for branch in operation["allOf"]:
        props = branch["then"].get("properties", {})
        if "pairCutoffs" in props:
            props["pairCutoffs"] = deepcopy(PAIR_CUTOFFS)


_complete_operation_contracts()



from .ai_display_schema import DISPLAY_PROPERTIES
_color_scale = next(b["then"]["properties"] for b in AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]["allOf"] if b["if"]["properties"]["name"].get("const") == "set-atom-colorscale")
DISPLAY_PROPERTIES["atomColorScaleCustomMap"] = deepcopy(_color_scale["customMap"])
_plane = next(b["then"]["properties"] for b in AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]["allOf"] if b["if"]["properties"]["name"].get("const") == "add-volumetric-plane")
DISPLAY_PROPERTIES["volumetricPlanes"] = {"type": "array", "items": {"type": "object", "properties": {**{k: v for k, v in deepcopy(_plane).items() if k != "planeName"}, "id": STRING, "name": STRING, "vmin": {"type": ["number", "null"]}, "vmax": {"type": ["number", "null"]}, "offsetMinimum": {"type": ["number", "null"]}, "offsetMaximum": {"type": ["number", "null"]}}, "additionalProperties": False}}
AI_CONTROL_SCHEMA["properties"]["display"].update({"properties": DISPLAY_PROPERTIES, "additionalProperties": False})
AI_CONTROL_SCHEMA["properties"]["camera"]["properties"].update(deepcopy(AI_CONTROL_SCHEMA["properties"]["renderArea"]["properties"]["camera"]["properties"]))
AI_CONTROL_SCHEMA["properties"]["camera"]["additionalProperties"] = False
# refresh-displacements uses a display patch too.
for _branch in AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]["allOf"]:
    if _branch["if"]["properties"]["name"].get("const") == "refresh-displacements":
        _branch["then"]["properties"]["display"] = AI_CONTROL_SCHEMA["properties"]["display"]

# Read and preview tools share browser API methods with their GUI panels.
AI_QUERY_SCHEMAS = {
    "files": {"description": "List files below the GUI launch directory. Use returned relative paths for load/append/guest/volumetric operations; absolute and escaping paths are rejected.", "properties": {"directory": STRING}},
    "bulk-catalog": {"description": "Installed ASE bulk materials and supported crystal/cell choices.", "properties": {}},
    "molecule-catalog": {"description": "Installed ASE molecule names, formulas, and native geometries.", "properties": {}},
    "atom-scalar-catalog": {"description": "Discover available scalar field IDs for the requested frame.", "properties": {"frame": INDEX}},
    "atom-properties": {"description": "Read stored arrays and calculator properties for one base atom without evaluating its calculator.", "properties": {"index": INDEX, "frame": INDEX}, "required": ["index"]},
    "frame-properties": {"description": "Read stored frame properties without evaluating the calculator. includeArrays can be large.", "properties": {"frame": INDEX, "includeArrays": BOOLEAN}},
    "atom-scalar-values": {"description": "Read a discovered scalar field. allFrames returns trajectory data and may be large.", "properties": {"field": STRING, "frame": INDEX, "allFrames": BOOLEAN}, "required": ["field"]},
    "atom-scalar-range": {"description": "Find finite scalar bounds in the current frame or trajectory, optionally restricted to indices.", "properties": {"field": STRING, "frame": INDEX, "allFrames": BOOLEAN, "indices": INDICES}, "required": ["field"]},
    "force-vectors": {"description": "Read stored Cartesian forces for a frame or trajectory. No force calculation is triggered.", "properties": {"frame": INDEX, "allFrames": BOOLEAN}},
    "colormap-catalog": {"description": "Discover installed Matplotlib colormaps.", "properties": {}},
    "colormap-lut": {"description": "Sample a discovered colormap for visual verification.", "properties": {"map": STRING, "reverse": BOOLEAN, "samples": {"type": "integer", "minimum": 16, "maximum": 2048}}},
    "insertion-pair-cutoffs": {"description": "Preview default repulsion onset distances independently of visual bonds.", "properties": {"elements": {"type": "array", "items": STRING}, "basis": {"enum": ["covalent", "vdw"]}, "scale": {"type": "number", "exclusiveMinimum": 0}, "molecules": {"type": "array", "items": STRING}}, "required": ["elements"]},
}

_build_properties = next(b["then"]["properties"] for b in AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]["allOf"] if b["if"]["properties"]["name"].get("const") == "build-bulk")
_molecule_properties = next(b["then"]["properties"] for b in AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]["allOf"] if b["if"]["properties"]["name"].get("const") == "scatter-molecules")
AI_QUERY_SCHEMAS["bulk-preview"] = {"description": "Preview ASE bulk geometry, cell and atom count without replacing the live structure.", "properties": {k: deepcopy(v) for k, v in _build_properties.items() if k != "confirmReplace"}, "required": ["formula"]}
AI_QUERY_SCHEMAS["insertion-domain"] = {"description": "Preview exact accessible insertion volume and optional realized molecular density without adding atoms.", "properties": {k: deepcopy(_molecule_properties[k]) for k in ["regions", "regionMode", "bounds", "regionMic", "regionRole", "molecules", "quantityMode", "targetDensityGcm3"]}}
_AI_COMMAND_METHODS = _AI_COMMAND_METHODS | {"query"}


def _ai_operation_schema(name: str) -> Dict[str, Any]:
    """Return one operation's live JSON Schema without unrelated operations."""
    operation = AI_CONTROL_SCHEMA["properties"]["operation"]["oneOf"][1]
    matches = []
    for branch in operation.get("allOf", []):
        condition = branch.get("if", {}).get("properties", {}).get("name", {})
        applies = condition.get("const") == name or name in condition.get("enum", [])
        if applies and isinstance(branch.get("then"), dict):
            matches.append(deepcopy(branch["then"]))
    return {
        "$schema": AI_CONTROL_SCHEMA["$schema"],
        "title": f"v_ase operation: {name}",
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"const": name}},
        **({"allOf": matches} if matches else {}),
    }


def _ai_schema_summary() -> Dict[str, Any]:
    from .ai_tools import catalog_fingerprint
    return {
        "tool_catalog_fingerprint": catalog_fingerprint(),
        "protocol": AI_PROTOCOL,
        "scope": "summary",
        "command_transport": "http-json-bridge",
        "accepts_natural_language": False,
        "stdin_commands": False,
        "methods": sorted(_AI_COMMAND_METHODS),
        "operations": sorted(AI_OPERATION_PARAMETERS),
        "queries": deepcopy(AI_QUERY_SCHEMAS),
        "exports": sorted(AI_EXPORT_PARAMETERS),
        "describe_profiles": AI_DESCRIBE_PROFILES,
        "apply_response_profiles": list(AI_DESCRIBE_PROFILES),
        "render_parameters": AI_RENDER_PARAMETERS,
        "apply_result": {
            "default_profile": "summary",
            "mutation_fields": [
                "applied", "responseProfile", "beforeRevision", "revision",
                "beforeFingerprint", "stateFingerprint", "changedPaths", "operation",
            ],
        },
        "next": {
            "operation": (
                "Request schema with params {\"operation\":\"NAME\"} before using "
                "an unfamiliar operation."
            ),
            "export": "Request schema with params {\"export\":\"FORMAT\"}.",
            "state": "Use describe profile summary first, then one focused profile.",
        },
    }


def _ai_apply_method_schema() -> Dict[str, Any]:
    properties = {
        key: deepcopy(value)
        for key, value in AI_CONTROL_SCHEMA["properties"].items()
        if key != "operation"
    }
    operation_names = sorted(AI_OPERATION_PARAMETERS)
    properties["operation"] = {
        "description": (
            "One semantic operation. Request its focused operation schema for "
            "operation-specific fields."
        ),
        "oneOf": [
            {"type": "string", "enum": operation_names},
            {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"enum": operation_names}},
            },
        ],
    }
    return {
        "$schema": AI_CONTROL_SCHEMA["$schema"],
        "title": "v_ase apply command",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


def ai_schema_payload(options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return a focused or complete live discovery contract for external agents."""
    options = options if isinstance(options, dict) else {}
    operation_names = options.get("operations")
    if operation_names is not None:
        if not isinstance(operation_names, list) or not operation_names:
            raise ValueError("operations must be a non-empty list of operation names.")
        names = list(dict.fromkeys(str(value).strip() for value in operation_names))
        if len(names) > 16:
            raise ValueError("At most 16 focused operation schemas may be requested together.")
        unknown = [name for name in names if name not in AI_OPERATION_PARAMETERS]
        if unknown:
            raise ValueError(f"Unknown v_ase operation(s): {', '.join(unknown)}.")
        return {
            "protocol": AI_PROTOCOL,
            "scope": "operations",
            "names": names,
            "operations": [
                {
                    "name": name,
                    "contract": deepcopy(AI_OPERATION_PARAMETERS[name]),
                    "schema": _ai_operation_schema(name),
                }
                for name in names
            ],
            "request": {
                "method": "apply",
                "params": {
                    "expectedRevision": "integer from describe",
                    "operation": {"name": "one requested operation"},
                    "responseProfile": "summary",
                },
            },
        }
    operation_name = str(options.get("operation") or "").strip()
    if operation_name:
        if operation_name not in AI_OPERATION_PARAMETERS:
            raise ValueError(f"Unknown v_ase operation '{operation_name}'.")
        return {
            "protocol": AI_PROTOCOL,
            "scope": "operation",
            "name": operation_name,
            "contract": deepcopy(AI_OPERATION_PARAMETERS[operation_name]),
            "schema": _ai_operation_schema(operation_name),
            "request": {
                "method": "apply",
                "params": {
                    "expectedRevision": "integer from describe",
                    "operation": {"name": operation_name},
                    "responseProfile": "summary",
                },
            },
        }
    export_name = str(options.get("export") or "").strip().lower()
    if export_name:
        if export_name not in AI_EXPORT_PARAMETERS:
            raise ValueError(f"Unknown v_ase export format '{export_name}'.")
        return {
            "protocol": AI_PROTOCOL,
            "scope": "export",
            "name": export_name,
            "contract": deepcopy(AI_EXPORT_PARAMETERS[export_name]),
            "request": {"method": "export", "params": {"format": export_name}},
        }
    method_name = str(options.get("method") or "").strip()
    if method_name == "query":
        return {"protocol": AI_PROTOCOL, "scope": "method", "name": "query", "queries": deepcopy(AI_QUERY_SCHEMAS)}
    if method_name == "describe":
        return {
            "protocol": AI_PROTOCOL,
            "scope": "method",
            "name": "describe",
            "profiles": deepcopy(AI_DESCRIBE_PROFILES),
            "request": {"method": "describe", "params": {"profile": "summary"}},
        }
    if method_name == "render":
        return {
            "protocol": AI_PROTOCOL,
            "scope": "method",
            "name": "render",
            "contract": deepcopy(AI_RENDER_PARAMETERS),
        }
    if method_name == "apply":
        return {
            "protocol": AI_PROTOCOL,
            "scope": "method",
            "name": "apply",
            "schema": _ai_apply_method_schema(),
            "response_profiles": deepcopy(AI_DESCRIBE_PROFILES),
            "result": deepcopy(_ai_schema_summary()["apply_result"]),
        }
    if method_name:
        raise ValueError(
            f"Unknown focused schema method '{method_name}'. "
            "Supported methods: apply, describe, query, render."
        )
    if str(options.get("scope") or "").strip().lower() in {"summary", "compact"}:
        return _ai_schema_summary()
    return {
        "protocol": AI_PROTOCOL,
        "command_transport": "http-json-bridge",
        "accepts_natural_language": False,
        "stdin_commands": False,
        "collaboration": {
            "protocol": COLLABORATION_PROTOCOL,
            "delivery": "ndjson-after-handshake",
            "event_endpoint": "/api/ai/events/{session_id}",
            "workspace_event_endpoint": "/api/ai/workspace-events/{workspace_id}",
            "authoritative_state": (
                "POST method describe to command_endpoint after each event. "
                "Use expectedRevision in apply params to avoid overwriting a newer human edit."
            ),
        },
        "command_endpoint": {
            "workspace": "/api/ai/command/workspace/{workspace_id}",
            "document": "/api/ai/command/session/{session_id}",
            "request": {
                "method": "describe",
                "params": {"profile": "summary"},
                "timeout_seconds": _AI_COMMAND_DEFAULT_TIMEOUT_SECONDS,
            },
            "methods": sorted(_AI_COMMAND_METHODS),
        },
        "query_schemas": deepcopy(AI_QUERY_SCHEMAS),
        "control_schema": AI_CONTROL_SCHEMA,
        "operation_parameters": AI_OPERATION_PARAMETERS,
        "export_parameters": AI_EXPORT_PARAMETERS,
        "describe_profiles": AI_DESCRIBE_PROFILES,
        "render_parameters": AI_RENDER_PARAMETERS,
        "browser_api": {
            "object": "window.v_aseAI",
            "methods": [
                "ready()",
                "schema(options)",
                "describe()",
                "capabilities()",
                "documents() [workspace page]",
                "activate(sessionId) [workspace page]",
                "newDocument() [workspace page]",
                "apply(command)",
                "render({width, height, options})",
                "export({format, ...options})",
            ],
        },
    }
