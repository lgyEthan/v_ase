"""Prepare traceable display scenes from the supplied, pinned model outputs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.io import read, write

DATA = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contained(root, relative):
    """Resolve portable data paths without reading outside the selected dataset."""
    root = Path(root).resolve()
    value = Path(relative)
    result = (root / value).resolve()
    if value.is_absolute() or '..' in value.parts or not result.is_relative_to(root):
        raise ValueError(f'Expected a path inside the dataset: {relative}')
    return result


def load_manifest(data_dir=DATA):
    root = Path(data_dir).resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest.get('schema') != 'v_ase.model_output_figures.v1':
        raise ValueError('Unsupported model-output figure manifest')
    samples = manifest.get('samples', [])
    ids = [sample['id'] for sample in samples]
    if not samples or len(set(ids)) != len(ids):
        raise ValueError('The dataset needs unique sample IDs')
    for sample in samples:
        if Path(sample['id']).name != sample['id'] or sample['id'] in {'.', '..'}:
            raise ValueError('Sample IDs must be simple names')
        for key, hash_key in [('source', 'source_sha256'), ('raw_source', 'raw_sha256')]:
            if key in sample:
                path = contained(root, sample[key])
                if not path.is_file() or digest(path) != sample[hash_key]:
                    raise ValueError(f'Source checksum mismatch: {sample["id"]} / {key}')
    return manifest


def prepare_dataset(data_dir, output_dir):
    data_dir, output_dir = Path(data_dir).resolve(), Path(output_dir).resolve()
    manifest = load_manifest(data_dir)
    display_dir = output_dir / 'display'
    display_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for sample in manifest['samples']:
        source = read(contained(data_dir, sample['source']))
        if len(source) != sample['source_atoms'] or dict(Counter(source.symbols)) != sample['composition']:
            raise ValueError(f'Unexpected source composition: {sample["id"]}')
        if not np.isfinite(source.positions).all() or source.get_volume() <= 0 or not source.pbc.all():
            raise ValueError(f'Invalid periodic source geometry: {sample["id"]}')
        distances = source.get_all_distances(mic=True)
        minimum = float(distances[np.triu_indices(len(source), 1)].min())
        if minimum <= .5:
            raise ValueError(f'Overlapping source atoms: {sample["id"]}')
        basis = np.asarray(sample['basis_matrix'], dtype=float)
        cell = np.asarray(sample['display_cell'], dtype=float)
        if not np.allclose(basis, np.rint(basis)) or not np.isclose(abs(np.linalg.det(basis)), 1):
            raise ValueError('The presentation basis must be an integer unimodular matrix')
        transformed_cell = basis @ source.cell.array
        if not np.allclose(cell @ cell.T, transformed_cell @ transformed_cell.T, rtol=1e-12, atol=1e-12):
            raise ValueError('The display cell changes the source metric')
        if not np.isclose(abs(np.linalg.det(cell)), source.get_volume(), rtol=1e-12, atol=1e-12):
            raise ValueError('The display cell changes the source volume')
        indices = np.asarray([site['source_index'] for site in sample['sites']], dtype=int)
        offsets = np.asarray([site['cell_offset'] for site in sample['sites']], dtype=float)
        if len(indices) != sample['display_atoms'] or np.any(indices < 0) or np.any(indices >= len(source)):
            raise ValueError('Invalid source-to-display indices')
        if not np.equal(offsets, np.rint(offsets)).all():
            raise ValueError('Periodic image offsets must be integers')
        if len({(int(i), tuple(offset)) for i, offset in zip(indices, offsets)}) != len(indices):
            raise ValueError('The presentation repeats an identical periodic site')
        if sample['group'] == 'alm_co' and sorted(indices.tolist()) != list(range(len(source))):
            raise ValueError('ALM presentation must contain each source atom exactly once')
        fractional = source.get_scaled_positions(wrap=False) @ np.linalg.inv(basis)
        fractional += np.asarray(sample['fractional_translation'])
        expected = (fractional[indices] + offsets) @ cell
        display = Atoms([source.symbols[int(i)] for i in indices], positions=expected, cell=cell, pbc=False)
        display.info.update(presentation_only=True, source_sha256=sample['source_sha256'])
        path = display_dir / (sample['id'] + '.traj')
        write(path, display)
        # Validate the actual serialized scene, rather than only pre-export arrays.
        saved = read(path)
        coordinate_error = float(np.max(np.abs(saved.positions - expected)))
        if coordinate_error > 1e-12 or not np.array_equal(saved.cell.array, cell) or saved.pbc.any():
            raise ValueError('The saved display scene changed coordinates, cell or PBC')
        canonical = Atoms(source.symbols, scaled_positions=fractional, cell=saved.cell, pbc=True)
        distance_error = float(np.max(np.abs(distances - canonical.get_all_distances(mic=True))))
        if distance_error > 1e-10:
            raise ValueError('The presentation changes periodic pair distances')
        records.append(dict(id=sample['id'], group=sample['group'], source=sample['source'],
                            source_sha256=sample['source_sha256'], source_atoms=len(source),
                            display=path.relative_to(output_dir).as_posix(), display_sha256=digest(path),
                            display_atoms=len(saved), volume_A3=source.get_volume(),
                            minimum_periodic_distance_A=minimum, periodic_distance_error_A=distance_error,
                            serialized_coordinate_error_A=coordinate_error,
                            source_to_display=sample['sites'], geometry_equivalent=True,
                            **{key: sample[key] for key in ['seed', 'candidate'] if key in sample}))
    (output_dir / 'structure_audit.json').write_text(json.dumps(records, indent=2) + '\n')
    preparation = dict(schema='v_ase.model_output_preparation.v1',
                       recipe_sha256=digest(data_dir / 'manifest.json'), scenes=records)
    (output_dir / 'preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
    return preparation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_dataset(args.data_dir, args.output_dir), indent=2))
