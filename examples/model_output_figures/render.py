"""Render the pinned model outputs and verify each saved, editable project."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import importlib.metadata
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
from urllib.parse import urlsplit
import zipfile

import numpy as np
from PIL import Image
import requests
from ase.io import read

DATA = Path(__file__).resolve().parent
PREPARE = runpy.run_path(str(DATA / 'prepare.py'))
digest, contained = PREPARE['digest'], PREPARE['contained']


def inspect_image(path, width, height):
    pixels = np.asarray(Image.open(path).convert('RGB'))
    if pixels.shape[:2] != (height, width):
        raise ValueError('Wrong image dimensions')
    border = np.concatenate([pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]])
    yy, xx = np.where(np.any(pixels < 242, axis=2))
    if border.min() < 248 or len(xx) <= 1000:
        raise ValueError('Image is blank or touches the export boundary')
    return dict(width=width, height=height, white_border=True,
                content_bbox=[int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())])


def verify_outputs(data_dir, output_dir):
    """Reject stale, partial or altered output; never synthesize success flags."""
    data_dir, output_dir = Path(data_dir).resolve(), Path(output_dir).resolve()
    recipe = PREPARE['load_manifest'](data_dir)
    preparation = json.loads((output_dir / 'preparation.json').read_text())
    rendered = json.loads((output_dir / 'render_manifest.json').read_text())
    expected_hash = digest(data_dir / 'manifest.json')
    if any(record['recipe_sha256'] != expected_hash for record in [preparation, rendered]):
        raise ValueError('The recipe changed after preparation/rendering')
    expected = {sample['id'] for sample in recipe['samples']}
    prepared = {sample['id']: sample for sample in preparation['scenes']}
    scenes = rendered['scenes']
    if len(scenes) != len(expected) or {scene['id'] for scene in scenes} != expected or set(prepared) != expected:
        raise ValueError('Incomplete or duplicate rendered sample set')
    for scene in scenes:
        if scene['display_sha256'] != prepared[scene['id']]['display_sha256']:
            raise ValueError('The rendered scene does not match its prepared display file')
        if digest(contained(output_dir, prepared[scene['id']]['display'])) != scene['display_sha256']:
            raise ValueError('The prepared display file changed')
        for key in ['png', 'project', 'settings']:
            if digest(contained(output_dir, scene[key])) != scene[key + '_sha256']:
                raise ValueError(f'Output checksum mismatch: {scene["id"]} / {key}')
        display = read(contained(output_dir, prepared[scene['id']]['display']))
        with zipfile.ZipFile(contained(output_dir, scene['project'])) as archive:
            saved = read(io.BytesIO(archive.read('structure.traj')), format='traj')
        if (saved.get_chemical_symbols() != display.get_chemical_symbols()
                or not np.array_equal(saved.positions, display.positions)
                or not np.array_equal(saved.cell.array, display.cell.array)
                or not np.array_equal(saved.pbc, display.pbc)):
            raise ValueError('The saved project changed its prepared scientific geometry')
        for key in ['source_geometry_preserved', 'reopened_geometry_preserved',
                    'exact_pixel_reopen', 'stale_revision_rejected', 'visual_edit_undo']:
            if scene[key] is not True:
                raise ValueError(f'Failed validation: {scene["id"]} / {key}')
        if scene['group'] == 'alm_co' and (scene['visible_bonds'] != 0 or scene['display_atoms'] != 22):
            raise ValueError('ALM needs its complete 22-atom cell without bonds')
        inspect_image(contained(output_dir, scene['png']), 2400, scene['height'])
    return rendered


def render_dataset(data_dir, output_dir, workspace_root, url, review_date, expected_version=None):
    import v_ase
    from v_ase.ai_tools import FunctionTools, ToolError

    data_dir, output_dir, workspace_root = map(lambda p: Path(p).resolve(), [data_dir, output_dir, workspace_root])
    recipe = PREPARE['load_manifest'](data_dir)
    version = expected_version or recipe['tested_v_ase_version']
    if v_ase.__version__ != version:
        raise ValueError(f'Expected v_ase {version}, imported {v_ase.__version__} from {v_ase.__file__}')
    if not output_dir.is_relative_to(workspace_root) or '/workspace/' not in url:
        raise ValueError('Use a workspace command URL and an output directory inside its file root')
    preparation = PREPARE['prepare_dataset'](data_dir, output_dir)
    plans = {scene['id']: scene for scene in preparation['scenes']}
    # A Python version string alone cannot establish the connected GUI's build.
    endpoint = urlsplit(url)
    base = f'{endpoint.scheme}://{endpoint.netloc}'
    assets = {}
    for name in ['renderer.js', 'main.js']:
        response = requests.get(base + '/static/' + name, timeout=30)
        response.raise_for_status()
        expected = Path(v_ase.__file__).parent / 'static' / name
        if response.content != expected.read_bytes():
            raise ValueError('Connected GUI assets differ from the imported v_ase package')
        assets[name] = digest(expected)
    for name in ['figures', 'projects', 'evidence']:
        (output_dir / name).mkdir(exist_ok=True)
    receipt = dict(schema='v_ase.model_output_render.v1', review_date=review_date,
                   created_at_utc=datetime.now(timezone.utc).isoformat(),
                   recipe_sha256=preparation['recipe_sha256'],
                   runtime=dict(version=v_ase.__version__, package_path=str(Path(v_ase.__file__).resolve()),
                                python=sys.version, executable=sys.executable, assets=assets,
                                dependencies={n: importlib.metadata.version(n) for n in
                                              ['ase', 'numpy', 'scipy', 'Pillow', 'requests', 'fastapi', 'uvicorn']}),
                   scenes=[])
    manifest_path = output_dir / 'render_manifest.json'
    manifest_path.write_text(json.dumps(receipt, indent=2) + '\n')
    with FunctionTools(url, artifact_dir=output_dir / 'evidence/api_artifacts', timeout=180) as tools:
        tools.call('vase_new_document', {})
        capabilities = tools.call('vase_capabilities', {'profile': 'summary'})
        (output_dir / 'evidence/live_capabilities.json').write_text(json.dumps(capabilities, indent=2))
        for sample in recipe['samples']:
            ident, style, plan = sample['id'], sample['style'], plans[sample['id']]
            state = tools.call('vase_describe', {'profile': 'summary'})

            def change(name, arguments):
                nonlocal state
                revision = state.get('revision', state.get('collaboration', {}).get('revision'))
                state = tools.call(name, dict(arguments, expected_document_id=state['documentId'],
                                             expected_revision=revision, response_profile='summary'))
                if state.get('mutation', {}).get('applied') is not True:
                    raise ValueError(f'Unapplied native operation: {name}')
                return state

            change('vase_load_structure', dict(path=(output_dir / plan['display']).relative_to(workspace_root).as_posix(),
                                              runtime_mode='view', confirm_replace=True))
            before = tools.call('vase_describe', {'profile': 'structure', 'include_positions': True})
            target = (np.asarray(before['cell']).sum(axis=0) * .5).tolist()
            change('vase_set_display', {'display': dict(show_axes=False, show_grid=False, show_cell=True,
                   show_polyhedra=False, show_constraints=False, viewport_background='#ffffff',
                   atom_display_mode=style['mode'], atom_radius_scale=1.,
                   label_colors=style['colors'], label_radii=style['radii'],
                   label_materials={label: 'standard' for label in style['colors']},
                   show_bonds=style['bonds'], show_periodic_bonds=False, bond_mode='pairwise',
                   bond_style='cylinder', bond_thickness=style['thickness'], cell_color='#59636d',
                   cell_thickness=.015, cell_material='unlit', supercell=[1, 1, 1], hidden_atom_references=[])})
            if style['bonds']:
                change('vase_configure_bonds', {'pairs': [dict(labels=['Au', 'O'], enabled=True,
                       maximum_angstrom=2.5, thickness_angstrom=.13, color_mode='split',
                       material='standard', style='cylinder')], 'disable_unspecified': True, 'clear_endpoint_overrides': True})
            change('vase_compose_view', dict(view_direction=style['direction'], screen_up=[0, 0, 1],
                                           target=target, projection='orthographic', fit='displayed', padding=.13))
            change('vase_style_scene', dict(atom_display_mode=style['mode'], show_bonds=style['bonds'], show_cell=True))
            options = dict(include_axes=False, include_grid=False, include_cell=True, background_color='#ffffff',
                           sphere_quality='ultra', render_mode='studio', sun_intensity=3.,
                           sun_position=[12, -18, 25], sun_target=target, selection_appearance='publication',
                           scale_mode='physical', pixels_per_angstrom=style['pixels'])
            rendered = tools.call('vase_render', dict(width=2400, height=style['height'], camera_source='viewport', options=options))
            png = output_dir / 'figures' / (ident + '.png')
            shutil.copyfile(rendered['artifact']['path'], png)
            allowed = {'position', 'target', 'up', 'projection', 'fov', 'zoom', 'ortho_scale', 'orthoScale', 'near', 'far', 'aspect'}
            camera = {('ortho_scale' if k == 'orthoScale' else k): v for k, v in rendered['camera'].items() if k in allowed}
            change('vase_set_render_area', {'render_area': dict(enabled=False, follow_viewport=False, camera=camera)})
            exported = tools.call('vase_export_settings', {})
            settings = json.loads(Path(exported['artifact']['path']).read_text())
            settings['settings']['imageExportProfile'] = dict(width=2400, height=style['height'], options=rendered['options'])
            settings['settings']['imageExportProfile']['options']['renderModeSelection'] = 'studio'
            settings_path = output_dir / 'projects' / (ident + '_settings.json')
            settings_path.write_text(json.dumps(settings, indent=2) + '\n')
            change('vase_load_settings', {'path': settings_path.relative_to(workspace_root).as_posix()})
            scene = tools.call('vase_scene_snapshot', dict(sections=['bonds'], limit=1, visible_only=False))
            if scene['display']['showBonds'] is not style['bonds'] or scene['counts']['baseAtoms'] != sample['display_atoms']:
                raise ValueError('Rendered atom count or bond visibility differs from the recipe')
            visible_bonds = scene['display']['renderedBaseEdgeCount']
            if not style['bonds'] and visible_bonds != 0:
                raise ValueError('The no-bond figure contains visible bonds')
            after = tools.call('vase_describe', {'profile': 'structure', 'include_positions': True})
            if after['structureFingerprint'] != before['structureFingerprint']:
                raise ValueError('Styling changed scientific geometry')
            try:
                tools.call('vase_style_scene', dict(show_bonds=not style['bonds'], expected_document_id=state['documentId'], expected_revision=0))
            except ToolError as error:
                if 'revision' not in str(error).lower() and 'conflict' not in str(error).lower():
                    raise
            else:
                raise ValueError('A stale-revision command was incorrectly accepted')
            exported = tools.call('vase_export_project', {})
            project = output_dir / 'projects' / (ident + '.vase')
            shutil.copyfile(exported['artifact']['path'], project)
            with zipfile.ZipFile(project) as archive:
                if json.loads(archive.read('manifest.json'))['settings']['display']['showBonds'] is not style['bonds']:
                    raise ValueError('The project did not preserve bond visibility')
                saved_atoms = read(io.BytesIO(archive.read('structure.traj')), format='traj')
            prepared_atoms = read(output_dir / plan['display'])
            if (saved_atoms.get_chemical_symbols() != prepared_atoms.get_chemical_symbols()
                    or not np.array_equal(saved_atoms.positions, prepared_atoms.positions)
                    or not np.array_equal(saved_atoms.cell.array, prepared_atoms.cell.array)):
                raise ValueError('The exported project changed the prepared geometry')
            state = tools.call('vase_describe', {'profile': 'summary'})
            change('vase_load_structure', dict(path=project.relative_to(workspace_root).as_posix(), confirm_replace=True))
            reopened = tools.call('vase_describe', {'profile': 'structure', 'include_positions': True})
            if reopened['structureFingerprint'] != before['structureFingerprint']:
                raise ValueError('Project reopening changed scientific geometry')
            repeated = tools.call('vase_render', {})
            if (repeated['width'], repeated['height']) != (2400, style['height']):
                raise ValueError('Project reopening lost the output dimensions')
            if not np.array_equal(np.asarray(Image.open(png)), np.asarray(Image.open(repeated['artifact']['path']))):
                raise ValueError('Project reopening changed the image pixels')
            state = tools.call('vase_describe', {'profile': 'summary'})
            change('vase_style_scene', {'show_bonds': not style['bonds']})
            change('vase_undo', {})
            final = tools.call('vase_scene_snapshot', dict(sections=['bonds'], limit=1))
            if final['display']['showBonds'] is not style['bonds']:
                raise ValueError('Undo did not restore the accepted appearance')
            result = dict(id=ident, group=sample['group'], height=style['height'], display_atoms=sample['display_atoms'],
                          display_sha256=plan['display_sha256'], visible_bonds=visible_bonds,
                          source_geometry_preserved=True, reopened_geometry_preserved=True,
                          exact_pixel_reopen=True, stale_revision_rejected=True, visual_edit_undo=True,
                          image_qa=inspect_image(png, 2400, style['height']), camera=rendered['camera'], options=rendered['options'])
            for key, path in [('png', png), ('project', project), ('settings', settings_path)]:
                result[key] = path.relative_to(output_dir).as_posix()
                result[key + '_sha256'] = digest(path)
            receipt['scenes'].append(result)
            manifest_path.write_text(json.dumps(receipt, indent=2) + '\n')
            print(json.dumps(dict(id=ident, version=v_ase.__version__, exact_pixel_reopen=True, visible_bonds=visible_bonds)), flush=True)
    return verify_outputs(data_dir, output_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workspace-root', type=Path)
    parser.add_argument('--command-url')
    parser.add_argument('--review-date', default=date.today().isoformat())
    parser.add_argument('--expected-version')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    date.fromisoformat(args.review_date)
    if args.verify_only:
        verify_outputs(args.data_dir, args.output_dir)
        print('All supplied scenes, projects, settings and checksums verified')
    elif not args.command_url or not args.workspace_root:
        parser.error('--command-url and --workspace-root are required for rendering')
    else:
        render_dataset(args.data_dir, args.output_dir, args.workspace_root, args.command_url,
                       args.review_date, args.expected_version)
