"""Coordination hulls from explicit, distance-bounded atomic neighborhoods.

Geometry is independent of visual bonds and calculators. Periodic vertices keep
(base index, integer image shift) identities; no ideal coordination is imposed.
"""
from __future__ import annotations

import itertools
import math
from copy import deepcopy

import numpy as np
from scipy.spatial import ConvexHull, QhullError, cKDTree

from .io import atom_labels
from .neighbors import _partial_periodic_search_geometry, _nonperiodic_search_geometry

MAX_CENTERS = 5000
MAX_VERTICES = 100000
MAX_NEIGHBORS = 512
MAX_IMAGE_QUERIES = 2000000

SELECTOR_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'elements': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 118},
        'labels': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 512},
        'indices': {'type': 'array', 'items': {'type': 'integer', 'minimum': 0}, 'maxItems': MAX_CENTERS},
    },
}
RULE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['id', 'centers', 'maxDistance'],
    'properties': {
        'id': {'type': 'string', 'minLength': 1, 'maxLength': 80},
        'name': {'type': 'string', 'maxLength': 120}, 'enabled': {'type': 'boolean'},
        'centers': SELECTOR_SCHEMA, 'ligands': SELECTOR_SCHEMA,
        'minDistance': {'type': 'number', 'minimum': 0},
        'maxDistance': {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 100},
        'periodic': {'type': 'boolean'},
        'minCoordination': {'type': 'integer', 'minimum': 3, 'maximum': MAX_NEIGHBORS},
        'maxCoordination': {'type': 'integer', 'minimum': 3, 'maximum': MAX_NEIGHBORS},
        'planar': {'type': 'boolean'}, 'showFaces': {'type': 'boolean'}, 'showEdges': {'type': 'boolean'},
        'color': {'type': ['string', 'null'], 'pattern': '^#[0-9a-fA-F]{6}$'},
        'opacity': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'edgeColor': {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$'},
        'edgeRadius': {'type': 'number', 'minimum': 0.001, 'maximum': 0.3},
        'explicit': {'type': 'array', 'maxItems': MAX_CENTERS, 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['center', 'vertices'],
            'properties': {
                'center': {'type': 'integer', 'minimum': 0},
                'vertices': {'type': 'array', 'minItems': 3, 'maxItems': MAX_NEIGHBORS, 'items': {
                    'type': 'object', 'additionalProperties': False, 'required': ['index'],
                    'properties': {'index': {'type': 'integer', 'minimum': 0},
                        'cellOffset': {'type': 'array', 'minItems': 3, 'maxItems': 3,
                                       'items': {'type': 'integer', 'minimum': -128, 'maximum': 128}}},
                }},
            },
        }},
    },
}
RULES_SCHEMA = {'type': 'array', 'items': RULE_SCHEMA, 'maxItems': 32}


def normalize_rules(rules):
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(RULES_SCHEMA).iter_errors(rules))
    if errors:
        raise ValueError(f'Invalid polyhedra rule: {errors[0].message}')
    result = []
    ids = set()
    for supplied in rules:
        rule = {'enabled': True, 'ligands': {}, 'minDistance': 0., 'periodic': True,
                'minCoordination': 3, 'maxCoordination': 32, 'planar': True,
                'showFaces': True, 'showEdges': True, 'color': None, 'opacity': .28,
                'edgeColor': '#374151', 'edgeRadius': .025, **deepcopy(supplied)}
        if rule['id'] in ids:
            raise ValueError('Polyhedra rule IDs must be unique.')
        ids.add(rule['id'])
        if not np.isfinite([rule['minDistance'], rule['maxDistance'], rule['opacity'], rule['edgeRadius']]).all():
            raise ValueError('Polyhedra distances and appearance values must be finite.')
        if rule['minDistance'] >= rule['maxDistance']:
            raise ValueError('Polyhedra minimum distance must be smaller than maximum distance.')
        if rule['minCoordination'] > rule['maxCoordination']:
            raise ValueError('Polyhedra minimum coordination exceeds maximum coordination.')
        result.append(rule)
    return result


def _select(atoms, selector, labels):
    chosen = np.ones(len(atoms), dtype=bool)
    for field, values in selector.items():
        if field == 'indices':
            if any(i >= len(atoms) for i in values):
                raise ValueError('A polyhedra atom index is outside this frame. Update the rule or use labels.')
            chosen &= np.isin(np.arange(len(atoms)), values)
        elif field == 'elements':
            from ase.data import atomic_numbers
            if any(x not in atomic_numbers for x in values):
                raise ValueError('A polyhedra element selector is not an ASE element symbol.')
            chosen &= np.isin(atoms.get_chemical_symbols(), values)
        else:
            chosen &= np.isin(labels, values)
    return np.flatnonzero(chosen)


def _neighborhoods(atoms, centers, ligands, rule):
    """Stream image queries; count before materializing neighbor lists."""
    if not len(centers) or not len(ligands):
        return {int(i): [] for i in centers}
    positions = np.asarray(atoms.positions, dtype=float)
    pbc = np.asarray(atoms.pbc, dtype=bool) & rule['periodic']
    cutoff = rule['maxDistance']
    if pbc.any():
        if np.linalg.matrix_rank(np.asarray(atoms.cell)[pbc], tol=1e-12) != int(pbc.sum()):
            raise ValueError('Periodic polyhedra require independent periodic cell vectors.')
        cell, _ = _partial_periodic_search_geometry(np.asarray(atoms.cell), positions, pbc, cutoff)
    else:
        cell, _ = _nonperiodic_search_geometry(positions, cutoff)
    inverse = np.linalg.inv(cell)
    fractional = positions @ inverse
    wraps = np.zeros_like(fractional, dtype=np.int64)
    wraps[:, pbc] = np.floor(fractional[:, pbc]).astype(np.int64)
    canonical = positions - wraps @ cell
    cf = canonical[centers] @ inverse
    lf = canonical[ligands] @ inverse
    radius = cutoff * np.linalg.norm(inverse, axis=0)
    ranges = [range(math.ceil(cf[:, k].min() - lf[:, k].max() - radius[k] - 1e-10),
                    math.floor(cf[:, k].max() - lf[:, k].min() + radius[k] + 1e-10) + 1)
              if pbc[k] else range(1) for k in range(3)]
    if math.prod(map(len, ranges)) * len(centers) > MAX_IMAGE_QUERIES:
        raise ValueError('Polyhedra image search exceeds the work budget. Reduce the cutoff or center selection.')
    tree = cKDTree(canonical[ligands])
    found = {int(i): [] for i in centers}
    epsilon = max(1e-10, cutoff * 1e-12)
    for offset in itertools.product(*ranges):
        offset = np.asarray(offset, dtype=np.int64)
        for start in range(0, len(centers), 256):
            group = centers[start:start + 256]
            query = canonical[group] - offset @ cell
            counts = tree.query_ball_point(query, cutoff + epsilon, return_length=True)
            if any(len(found[int(i)]) + int(n) > MAX_NEIGHBORS + 1 for i, n in zip(group, counts)):
                raise ValueError('A polyhedra center has over 512 candidate neighbors. Reduce the cutoff or ligand selection.')
            for center, hits in zip(group, tree.query_ball_point(query, cutoff + epsilon)):
                for hit in hits:
                    vertex = int(ligands[hit])
                    shift = offset + wraps[center] - wraps[vertex]
                    delta = positions[vertex] + shift @ cell - positions[center]
                    distance = float(np.linalg.norm(delta))
                    if distance < rule['minDistance'] - epsilon:
                        continue
                    if distance <= epsilon:
                        if vertex == center and not np.any(shift): continue
                        raise ValueError('A ligand coincides with its polyhedra center. Adjust the selection or minimum distance.')
                    found[int(center)].append((vertex, shift.tolist(), delta, distance))
    return found


def _hull(points):
    """Return outward triangles and true polygon edges, without facet diagonals."""
    points = np.asarray(points, dtype=float)
    mean = points.mean(axis=0)
    centered = points - mean
    scale = max(float(np.linalg.norm(centered, axis=1).max(initial=0)), 1e-12)
    _, singular, axes = np.linalg.svd(centered / scale, full_matrices=False)
    tolerance = max(1e-10, scale * 1e-9)
    rank = int(np.sum(singular > tolerance / scale))
    if rank < 2:
        return {'rank': rank, 'status': 'collinear-or-coincident', 'toleranceAngstrom': tolerance}
    try:
        if rank == 2:
            projected = centered @ axes[:2].T / scale
            hull = ConvexHull(projected)
            polygon = [int(i) for i in hull.vertices]
            triangles = [[polygon[0], polygon[i], polygon[i + 1]] for i in range(1, len(polygon)-1)]
            edges = [[polygon[i], polygon[(i+1) % len(polygon)]] for i in range(len(polygon))]
            origin = (-mean) @ axes[:2].T / scale
            in_plane = abs(float(mean @ axes[2])) <= tolerance
            inside = in_plane and bool(np.all(hull.equations[:, :2] @ origin + hull.equations[:, 2] <= 1e-9))
            return {'rank': 2, 'status': 'planar', 'triangles': triangles, 'edges': edges,
                    'faces': [polygon], 'area': float(hull.volume * scale**2), 'volume': 0.,
                    'centerInside': inside, 'hullVertexCount': len(polygon), 'toleranceAngstrom': tolerance}
        hull = ConvexHull(centered / scale)
    except QhullError:
        return {'rank': rank, 'status': 'numerically-degenerate', 'toleranceAngstrom': tolerance}
    triangles = []
    facet_groups = []
    planes = []
    groups = []
    for simplex, equation in zip(hull.simplices, hull.equations):
        triangle = list(map(int, simplex))
        a, b, c = points[triangle]
        if np.dot(np.cross(b-a, c-a), equation[:3]) < 0:
            triangle[1], triangle[2] = triangle[2], triangle[1]
        triangles.append(triangle)
        group = next((i for i, plane in enumerate(planes)
                      if np.linalg.norm(plane[:3] - equation[:3]) < 1e-8 and abs(plane[3]-equation[3]) < 1e-9), None)
        if group is None:
            group = len(planes); planes.append(equation); groups.append(set())
        groups[group].update(triangle); facet_groups.append(group)
    owners = {}
    for triangle, group in zip(triangles, facet_groups):
        for a, b in zip(triangle, triangle[1:] + triangle[:1]):
            owners.setdefault(tuple(sorted((a, b))), set()).add(group)
    edges = [list(edge) for edge, groups_ in sorted(owners.items()) if len(groups_) > 1]
    faces = []
    for vertices, plane in zip(groups, planes):
        vertices = sorted(vertices)
        center = points[vertices].mean(axis=0)
        first = points[vertices[0]] - center; first /= np.linalg.norm(first)
        second = np.cross(plane[:3], first)
        vertices.sort(key=lambda i: math.atan2(np.dot(points[i]-center, second), np.dot(points[i]-center, first)))
        faces.append(vertices)
    inside = np.all(hull.equations[:, :3] @ (-mean / scale) + hull.equations[:, 3] <= 1e-9)
    return {'rank': 3, 'status': 'solid', 'triangles': triangles, 'edges': edges, 'faces': faces,
            'volume': float(hull.volume * scale**3), 'area': float(hull.area * scale**2),
            'centerInside': bool(inside), 'hullVertexCount': len(hull.vertices), 'toleranceAngstrom': tolerance}


def calculate_polyhedra(atoms, rules, *, labels=None):
    """Calculate deterministic coordination hulls. No calculator is evaluated."""
    rules = normalize_rules(rules)
    positions = np.asarray(atoms.positions, dtype=float)
    if not np.all(np.isfinite(positions)) or not np.all(np.isfinite(atoms.cell)):
        raise ValueError('Polyhedra require finite coordinates and cell vectors.')
    labels = list(atom_labels(atoms) if labels is None else labels)
    if len(labels) != len(atoms) or any(not isinstance(x, str) for x in labels):
        raise ValueError('Polyhedra labels must contain one string per atom.')
    result, diagnostics = [], []
    total_centers = total_vertices = 0
    for rule in rules:
        if not rule['enabled']: continue
        centers = _select(atoms, rule['centers'], labels)
        ligands = _select(atoms, rule['ligands'], labels)
        if 'explicit' in rule:
            lookup = {}
            for group in rule['explicit']:
                center = group['center']
                if center not in centers or center in lookup:
                    raise ValueError('Explicit polyhedra centers must be unique members of the center selection.')
                hits = []
                for vertex in group['vertices']:
                    index = vertex['index']; shift = vertex.get('cellOffset', [0,0,0])
                    if index not in ligands:
                        raise ValueError('An explicit polyhedra vertex is outside the ligand selection.')
                    if any(s and (not atoms.pbc[k] or not rule['periodic']) for k, s in enumerate(shift)):
                        raise ValueError('Explicit image shifts require periodicity in that direction.')
                    delta = positions[index] + np.asarray(shift) @ atoms.cell - positions[center]
                    distance = float(np.linalg.norm(delta))
                    if distance <= 1e-10:
                        raise ValueError('A polyhedra vertex coincides with its center.')
                    hits.append((index, shift, delta, distance))
                lookup[center] = hits
            centers = np.asarray(sorted(lookup), dtype=int)
        else:
            if total_centers + len(centers) > MAX_CENTERS:
                raise ValueError('Polyhedra exceed 5000 centers. Use a smaller center selection.')
            lookup = _neighborhoods(atoms, centers, ligands, rule)
        total_centers += len(centers)
        if total_centers > MAX_CENTERS:
            raise ValueError('Polyhedra exceed 5000 centers. Use a smaller center selection.')
        for center in centers:
            hits = sorted(lookup[int(center)], key=lambda x: (x[3], x[0], tuple(x[1])))
            unique = []
            for hit in hits:
                if not any(np.linalg.norm(hit[2] - existing[2]) <= 1e-9 for existing in unique):
                    unique.append(hit)
            count = len(unique)
            record = {'ruleId': rule['id'], 'center': int(center), 'neighborCount': count,
                      'duplicateVertexCount': len(hits)-count}
            if count < rule['minCoordination'] or count > rule['maxCoordination']:
                diagnostics.append({**record, 'status': 'coordination-outside-range'}); continue
            total_vertices += count
            if total_vertices > MAX_VERTICES:
                raise ValueError('Polyhedra exceed 100000 vertices. Reduce the center selection.')
            geometry = _hull([x[2] for x in unique])
            record.update(geometry)
            if 'triangles' not in geometry or (geometry['rank'] == 2 and not rule['planar']):
                diagnostics.append({**record, 'status': 'planar-disabled' if geometry['rank'] == 2 and not rule['planar'] else geometry['status']});continue
            record.update({'vertices': [dict(index=x[0], cellOffset=x[1], position=(positions[center]+x[2]).tolist(), distance=x[3]) for x in unique],
                           'centerPosition': positions[center].tolist(), 'centerLabel': labels[center],
                           'style': {key: rule[key] for key in ('color','opacity','showFaces','showEdges','edgeColor','edgeRadius')}})
            result.append(record)
    return {'polyhedra': result, 'diagnostics': diagnostics, 'centerCount': total_centers,
            'polyhedronCount': len(result), 'vertexCount': total_vertices,
            'units': {'length': 'angstrom', 'area': 'angstrom^2', 'volume': 'angstrom^3'},
            'definition': 'Convex hull of the specified ligand sites; geometry is not a bonding or oxidation-state inference.'}
