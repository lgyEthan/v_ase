"""Bounded NumPy counterpart of water_geometry.js and surface_refinement.js.

Export is independent of a browser or Node installation. The same world-anchored
Gaussian lattice, surface nets, Taubin fairing and curved-edge subdivision are
used; cross-runtime regressions compare the resulting physical mesh.
"""
from itertools import product
import math
import re

import numpy as np
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
from ase.geometry import find_mic

DEFAULTS = dict(enabled=False, source='auto', indices=[], color='#65aaca',
                opacity=.48, lighting=True, roughness=.18, hideMolecules=True,
                smoothing=2., level=.63, spacing=.65, ohCutoff=1.25)
CORNERS = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]])
EDGES = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]


def normalize_water(options):
    cfg = {**DEFAULTS, **(options or {})}
    for key, lo, hi in [('opacity',0,1),('roughness',.02,1),('smoothing',.5,3),
                        ('level',.1,3),('spacing',.3,1.5),('ohCutoff',.8,1.6)]:
        value = float(cfg[key])
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'Water {key} must be between {lo} and {hi}.')
        cfg[key] = value
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', cfg['color']):
        raise ValueError('Water color must be a six-digit hex color.')
    if cfg['source'] not in ('auto', 'selected'):
        raise ValueError('Water source must be auto or selected.')
    if not isinstance(cfg['indices'], list) or any(type(i) is not int or i < 0 for i in cfg['indices']):
        raise ValueError('Water indices must be nonnegative integers.')
    cfg['indices'] = list(dict.fromkeys(cfg['indices']))
    for key in ('enabled', 'lighting', 'hideMolecules'):
        cfg[key] = cfg[key] is True
    return cfg


def detect_water(data, cfg):
    positions = np.asarray(data['positions'], dtype=float).reshape(-1, 3)
    elements = np.asarray(data.get('chemical_symbols') or data['symbols'])
    cell = np.asarray(data['cell'], dtype=float)
    pbc = np.asarray(data.get('pbc', [False]*3), dtype=bool)
    periodic = abs(np.linalg.det(cell)) >= 1e-10
    assigned, molecules = set(), []
    groups = {}
    ids = data.get('molecule_ids', [])
    if len(ids) == len(elements):
        for i, value in enumerate(ids):
            if isinstance(value, int) and value > 0:
                groups.setdefault(value, []).append(i)
    candidates = []
    for group in groups.values():
        assigned.update(group)
        os = [i for i in group if elements[i] == 'O']
        hs = [i for i in group if elements[i] == 'H']
        if len(group) == 3 and len(os) == 1 and len(hs) == 2:
            candidates.append((os[0], *hs))
    if candidates:
        pairs = np.asarray(candidates)
        delta = (positions[pairs[:,1:]] - positions[pairs[:,0,None]]).reshape(-1, 3)
        distance = find_mic(delta, cell, pbc)[1] if periodic else np.linalg.norm(delta, axis=1)
        molecules.extend(m for m, valid in zip(candidates, (distance < cfg['ohCutoff']).reshape(-1,2).all(axis=1)) if valid)
    oxygens = [i for i, e in enumerate(elements) if e == 'O' and i not in assigned]
    hydrogens = [i for i, e in enumerate(elements) if e == 'H' and i not in assigned]
    if oxygens and hydrogens:
        reciprocal = np.linalg.inv(cell) if periodic else np.eye(3)
        reach = [max(1, math.ceil(cfg['ohCutoff'] * np.linalg.norm(reciprocal[:,d]))) if periodic and pbc[d] else 0 for d in range(3)]
        image_count = math.prod(2*r+1 for r in reach)
        if image_count > 4096 or image_count * len(oxygens) > 2_000_000:
            raise ValueError('Periodic water neighbour search exceeds its image budget. Reduce the cell basis or provide molecule IDs.')
        wrapped = positions.copy()
        if periodic:
            fractional = positions @ reciprocal
            fractional[:,pbc] -= np.floor(fractional[:,pbc])
            wrapped = fractional @ cell
        shifts = np.asarray(list(product(*(range(-r,r+1) for r in reach)))) @ cell
        images = (wrapped[oxygens,None,:] + shifts[None,:,:]).reshape(-1,3)
        distance, nearest = cKDTree(images).query(wrapped[hydrogens], distance_upper_bound=cfg['ohCutoff'])
        attached = {o:[] for o in oxygens}
        for h, dist, image in zip(hydrogens, distance, nearest):
            if dist < cfg['ohCutoff']:
                attached[oxygens[image//image_count]].append(h)
        molecules.extend((o,*hs) for o, hs in attached.items() if len(hs) == 2)
    scope = set(cfg['indices'])
    return [m for m in molecules if cfg['source'] == 'auto' or m[0] in scope]


def build_water_geometry(centers, cfg):
    centers = np.asarray(centers, dtype=float).reshape(-1,3)
    empty = (np.empty((0,3),np.float32), np.empty((0,3),np.float32), np.empty((0,3),np.int32))
    if not len(centers):
        return empty
    if len(centers) > 500_000 or not np.isfinite(centers).all():
        raise ValueError('Water surface exceeds its molecule budget or contains invalid positions.')
    pad = 3 * cfg['smoothing']; step = cfg['spacing']
    lo, hi = centers.min(axis=0)-pad, centers.max(axis=0)+pad
    for _ in range(60):
        origin = (np.floor(lo/step)-3)*step
        dims = np.ceil((hi-origin)/step).astype(int)+4
        if max(dims) <= 512 and math.prod(dims) <= 1_200_000 and len(centers)*(2*math.ceil(pad/step)+1)**3 <= 120_000_000:
            break
        step *= 1.15
    if step > cfg['smoothing']*2 or math.prod(dims) > 1_200_000:
        raise ValueError('Water extent is too large for a resolved surface. Reduce repetitions or source scope.')
    nx,ny,nz = map(int,dims); plane = nx*ny
    field = np.zeros((nz,ny,nx), dtype=np.float32)
    radius = math.ceil(pad/step); inv = 1/(2*cfg['smoothing']**2)
    for point in centers:
        q = (point-origin)/step
        low = np.maximum(0,np.floor(q+.5).astype(int)-radius)
        high = np.minimum(dims-1,np.floor(q+.5).astype(int)+radius)
        ex,ey,ez = [np.exp(-((np.arange(a,b+1)-v)*step)**2*inv).astype(np.float32).astype(float) for a,b,v in zip(low,high,q)]
        # JS stores each field addition into Float32, with double intermediate products.
        slab = field[low[2]:high[2]+1,low[1]:high[1]+1,low[0]:high[0]+1]
        slab[:] = slab + ez[:,None,None]*ey[None,:,None]*ex[None,None,:]
    field = field.ravel(); iso = cfg['level']
    bases = np.arange(len(field)).reshape(nz,ny,nx)[1:-2,1:-2,1:-2].ravel()
    offsets = np.array([0,1,nx+1,nx,plane,plane+1,plane+nx+1,plane+nx])
    mask = np.zeros(len(bases), np.uint8)
    for i, offset in enumerate(offsets):
        mask |= (field[bases+offset] >= iso).astype(np.uint8) << i
    active = bases[(mask != 0)&(mask != 255)]
    points = np.zeros((len(active),3)); normals = np.zeros_like(points); count = np.zeros(len(active))
    values = field[active[:,None]+offsets].astype(float)
    for a,b in EDGES:
        crossing = (values[:,a]>=iso)!=(values[:,b]>=iso)
        selected = np.flatnonzero(crossing)
        t = (iso-values[selected,a])/(values[selected,b]-values[selected,a])
        points[selected] += CORNERS[a]+(CORNERS[b]-CORNERS[a])*t[:,None]
        ia,ib = active[selected]+offsets[a], active[selected]+offsets[b]
        for d,stride in enumerate((1,nx,plane)):
            normals[selected,d] += (field[ia-stride].astype(float)-field[ia+stride])*(1-t)+(field[ib-stride].astype(float)-field[ib+stride])*t
        count[selected] += 1
    xyz = np.column_stack((active%nx,(active//nx)%ny,active//plane))
    points = (origin+(xyz+points/count[:,None])*step).astype(np.float32)
    normals = (normals/np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-30)).astype(np.float32)
    cells = np.full(len(field),-1,np.int32); cells[active] = np.arange(len(active))
    inside = field[bases]>=iso
    edge_crossings = np.column_stack([inside!=(field[bases+d]>=iso) for d in (1,nx,plane)])
    rows,axes = np.nonzero(edge_crossings)
    quad_offsets = np.array([[0,-nx,-nx-plane,-plane],[0,-plane,-plane-1,-1],[0,-1,-1-nx,-nx]])
    quads = cells[bases[rows,None]+quad_offsets[axes]]
    quads = quads[(quads>=0).all(axis=1)]
    if len(quads):
        p = points[quads[:,:3]].astype(float)
        flip = (np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])*normals[quads[:,0]]).sum(axis=1)<0
        quads[flip] = quads[flip][:,[0,3,2,1]]
    triangles = quads[:,[0,1,2,0,2,3]].reshape(-1,3)
    return points,normals,triangles


def refine_water_geometry(mesh, subdivision, smoothing):
    positions,normals,triangles = mesh
    subdivision = max(0,min(8,math.floor(float(subdivision)+.5)))
    smoothing = max(0,min(100,math.floor(float(smoothing)+.5)))
    if len(triangles)*4**subdivision > 8_000_000:
        raise ValueError('Surface interpolation exceeds 8,000,000 triangles. Lower subdivision or smooth the original mesh.')
    if not len(triangles):
        return mesh
    def edges_for(faces):
        directed = faces[:,[0,1,1,2,2,0]].reshape(-1,2)
        edges,inverse,counts = np.unique(np.sort(directed,axis=1),axis=0,return_inverse=True,return_counts=True)
        return directed,edges,inverse,counts
    if smoothing:
        directed,edges,_,counts = edges_for(triangles)
        pairs = np.concatenate((directed,directed[:,::-1]))
        adjacency = coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(positions),len(positions))).tocsr()
        degree = np.asarray(adjacency.sum(axis=1)).ravel(); pinned = np.zeros(len(positions),bool)
        pinned[edges[counts!=2].ravel()] = True
        movable = (~pinned)&(degree>0)
        for _ in range(smoothing):
            for factor in (.5,-.53):
                average = adjacency @ positions / np.maximum(degree[:,None],1)
                positions = np.where(movable[:,None],positions+factor*(average-positions),positions).astype(np.float32)
        vectors = positions[triangles].astype(float)
        face_normals = np.cross(vectors[:,1]-vectors[:,0],vectors[:,2]-vectors[:,0])
        updated = np.zeros_like(positions)
        # Preserve triangle/corner accumulation order in Float32.
        np.add.at(updated,triangles.ravel(),np.repeat(face_normals,3,axis=0))
        lengths = np.linalg.norm(updated.astype(float),axis=1)
        normals = np.where(lengths[:,None]>0,updated/np.maximum(lengths[:,None],1e-30),normals).astype(np.float32)
    for _ in range(subdivision):
        _,edges,inverse,counts = edges_for(triangles)
        a,b = edges.T
        pa,pb,na,nb = (v.astype(float) for v in (positions[a],positions[b],normals[a],normals[b]))
        delta = pb-pa
        da = (delta*na).sum(axis=1); db = (-delta*nb).sum(axis=1)
        mid = (pa+pb)*.5-np.where((counts==2)[:,None],(da[:,None]*na+db[:,None]*nb)*.125,0)
        normal = na+nb; normal /= np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-30)
        ab,bc,ca = (inverse.reshape(-1,3)+len(positions)).T
        a,b,c = triangles.T
        triangles = np.column_stack((a,ab,ca,ab,b,bc,ca,bc,c,ab,bc,ca)).reshape(-1,3)
        positions = np.concatenate((positions,mid.astype(np.float32)))
        normals = np.concatenate((normals,normal.astype(np.float32)))
    return positions,normals,triangles


def water_scene(atoms, display, scene):
    from .serialization import atoms_to_json
    from .export import _cell_offsets, _normalized_supercell, _display_translation
    cfg = normalize_water(display.get('waterSurface'))
    data = atoms_to_json(atoms)
    molecules = detect_water(data,cfg)
    reps,cell = _normalized_supercell(display,data)
    offsets = _cell_offsets(reps)
    if len(molecules)*len(offsets)>500_000:
        raise ValueError('Water surface exceeds 500,000 displayed molecules.')
    labels = data['symbols']
    visibility = display.get('labelVisible', {})
    hidden_refs = set(display.get('hiddenAtomReferences', []))
    mode = display.get('polyhedraAtomMode', 'all') if display.get('showPolyhedra') else 'all'
    centers_set = {p['center'] for p in scene['polyhedra']}
    ligands = {(v['index'], tuple(v['cell_offset'])) for p in scene['polyhedra'] for v in p['vertex_references']}
    def source_visible(i, offset):
        key = f"replica:{i}:"+','.join(map(str,offset)) if any(offset) else f'atom:{i}'
        if visibility.get(labels[i]) is False or key in hidden_refs: return False
        center, ligand = i in centers_set, (i,offset) in ligands
        return mode == 'all' or mode == 'centers' and center or mode == 'ligands' and ligand or mode == 'coordination' and (center or ligand)
    hidden,centers = set(),[]
    for molecule in molecules:
        for offset in offsets:
            if not source_visible(molecule[0],offset):
                continue
            centers.append(np.asarray(data['positions'][molecule[0]])+np.asarray(offset)@cell)
            hidden.update((i,offset) for i in molecule)
    mesh = build_water_geometry(centers,cfg)
    if len(mesh[2])*4**max(0,min(8,int(display.get('waterInterpolation',1)))) > 4_000_000:
        raise ValueError('Blender water export exceeds its geometry budget. Lower water subdivision or export fewer repetitions.')
    positions,normals,faces = refine_water_geometry(mesh,display.get('waterInterpolation',1),display.get('waterMeshSmoothing',20))
    positions = positions.astype(float)+_display_translation(display,data['cell'])
    if cfg['hideMolecules'] and len(faces):
        points = {(i,tuple(np.round(np.asarray(data['positions'][i])+np.asarray(offset)@cell+_display_translation(display,data['cell']),8))) for i,offset in hidden}
        scene['atoms'] = [a for a in scene['atoms'] if (a['index'],tuple(a['cell_offset'])) not in hidden]
        scene['bonds'] = [b for b in scene['bonds'] if (b['i'],tuple(np.round(b['full_start'],8))) not in points and (b['j'],tuple(np.round(b['full_end'],8))) not in points]
    return {'vertices':positions.tolist(),'normals':normals.tolist(),'triangles':faces.tolist(),
            'color':cfg['color'],'opacity':cfg['opacity'],'roughness':cfg['roughness'],
            'lighting':cfg['lighting'] and display.get('atomDisplayMode')!='2d',
            'molecules':len(centers)}
