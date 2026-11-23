"""Package a reviewed figure workflow without treating open issues as a pass."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(repo, input_dir, report_dir, manuscript_dir, destination):
    repo, input_dir, report_dir, manuscript_dir, destination = map(
        lambda path: Path(path).resolve(), [repo, input_dir, report_dir, manuscript_dir, destination])
    verify = runpy.run_path(str(repo / 'examples/model_output_figures/render.py'))['verify_outputs']
    receipt = verify(repo / 'examples/model_output_figures', input_dir)
    checks = json.loads((input_dir / 'evidence/checks.json').read_text())
    entries = {}
    for folder, prefix in [(repo / 'examples/model_output_figures', 'examples/model_output_figures'),
                           (input_dir, 'review'), (manuscript_dir, 'manuscript')]:
        for path in folder.rglob('*'):
            relative = path.relative_to(folder)
            if (not path.is_file() or any(part in {'api_artifacts', '__pycache__'} for part in relative.parts)
                    or path.name in {'bundle_index.json', 'status.json'}):
                continue
            entries[prefix + '/' + relative.as_posix()] = path
    for name in ['model_output_review.pdf', 'model_output_publication_figure.pdf']:
        entries['report/' + name] = report_dir / name
    for name in ['build_model_output_report.py', 'package_model_output_review.py']:
        entries['scripts/' + name] = repo / 'scripts' / name
    for name in ['docs/model-output-figures.md', 'docs/assets/model_output_figures.png']:
        entries['documentation/' + Path(name).name] = repo / name
    passed = (checks['full_suite']['status'] == 'passed'
              and checks.get('visual_qa', {}).get('passed') is True)
    index = dict(schema='v_ase.model_output_review_bundle.v1', review_date=receipt['review_date'],
                 runtime_version=receipt['runtime']['version'],
                 status='verified' if passed else 'reviewed_with_open_issues',
                 files={name: digest(path) for name, path in sorted(entries.items())})
    index_path = input_dir / 'bundle_index.json'
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    entries['review/bundle_index.json'] = index_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(entries.items()):
            archive.write(path, name)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC check failed')
        for name, expected in index['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('Archive content hash mismatch: ' + name)
    status = dict(status=index['status'], review_date=index['review_date'], version=index['runtime_version'],
                  scientific_scenes_verified=len(receipt['scenes']), full_suite=checks['full_suite'],
                  bundle_sha256=digest(destination), bundle_files=len(entries))
    (input_dir / 'status.json').write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, required=True)
    parser.add_argument('--manuscript-dir', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    package(args.repo_root, args.input_dir, args.report_dir, args.manuscript_dir, args.destination)
