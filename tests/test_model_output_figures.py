"""Scientific and portability regressions for the published model-output example."""
from pathlib import Path
import json
import runpy
import shutil
import subprocess
import sys

import numpy as np
import pytest
from ase.io import read

DATA = Path(__file__).resolve().parents[1] / 'examples/model_output_figures'
PREPARE = runpy.run_path(str(DATA / 'prepare.py'))
RENDER = runpy.run_path(str(DATA / 'render.py'))


def test_standalone_preparation_survives_relocation_and_serialization(tmp_path):
    relocated = tmp_path / 'a different directory' / 'dataset'
    shutil.copytree(DATA, relocated)
    output = tmp_path / 'generated'
    result = subprocess.run([sys.executable, '-I', str(relocated / 'prepare.py'),
                             '--output-dir', str(output)], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads((output / 'preparation.json').read_text())
    assert len(report['scenes']) == 6
    for scene in report['scenes']:
        atoms = read(output / scene['display'])
        assert len(atoms) == scene['display_atoms']
        assert not atoms.pbc.any()
        assert scene['serialized_coordinate_error_A'] == 0
        assert scene['periodic_distance_error_A'] < 1e-10
        if scene['group'] == 'alm_co':
            assert len(atoms) == 22


def test_changed_generated_structure_cannot_be_silently_reused(tmp_path):
    relocated = tmp_path / 'data'
    shutil.copytree(DATA, relocated)
    source = next((relocated / 'sources').glob('*.cif'))
    source.write_bytes(source.read_bytes() + b'\n# changed\n')
    with pytest.raises(ValueError, match='checksum mismatch'):
        PREPARE['prepare_dataset'](relocated, tmp_path / 'output')


@pytest.mark.parametrize('mutation', ['metric', 'fractional-offset', 'extra-alm-site', 'external-path'])
def test_invalid_presentation_cannot_be_labelled_geometry_preserving(tmp_path, mutation):
    relocated = tmp_path / 'data'
    shutil.copytree(DATA, relocated)
    path = relocated / 'manifest.json'
    manifest = json.loads(path.read_text())
    sample = manifest['samples'][3]
    if mutation == 'metric':
        sample['display_cell'][0][0] += .5
    elif mutation == 'fractional-offset':
        sample['sites'][0]['cell_offset'][0] += .25
    elif mutation == 'extra-alm-site':
        sample['sites'].append(dict(sample['sites'][0]))
        sample['display_atoms'] += 1
    else:
        sample['source'] = '../outside.cif'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        PREPARE['prepare_dataset'](relocated, tmp_path / 'output')


@pytest.mark.parametrize('which', ['preparation', 'render'])
def test_recipe_changes_invalidate_old_success_receipts(tmp_path, which):
    prepared = PREPARE['prepare_dataset'](DATA, tmp_path)
    receipt = dict(recipe_sha256=prepared['recipe_sha256'], scenes=[])
    if which == 'preparation':
        prepared['recipe_sha256'] = '0' * 64
        (tmp_path / 'preparation.json').write_text(json.dumps(prepared))
    else:
        receipt['recipe_sha256'] = '0' * 64
    (tmp_path / 'render_manifest.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='recipe changed'):
        RENDER['verify_outputs'](DATA, tmp_path)


def test_partial_render_does_not_count_as_complete_validation(tmp_path):
    prepared = PREPARE['prepare_dataset'](DATA, tmp_path)
    receipt = dict(recipe_sha256=prepared['recipe_sha256'], scenes=[{'id': 'auo2_1337'}])
    (tmp_path / 'render_manifest.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='Incomplete'):
        RENDER['verify_outputs'](DATA, tmp_path)
