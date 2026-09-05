"""Regenerate the feature-oriented typed tool reference from canonical schemas."""
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v_ase.ai_tools import tool_catalog


def section(spec):
    name = spec.name
    if spec.export_format or spec.method == 'render': return 'Render and export'
    if any(word in name for word in ('commensurate', 'registry')): return 'Periodic interfaces'
    if any(word in name for word in ('volumetric', 'insertion_domain')) and 'insertion' not in name: return 'Volumetric fields'
    if any(word in name for word in ('scatter', 'added_atoms', 'add_atoms', 'molecule', 'insertion')): return 'Atomic and molecular distributions'
    if any(word in name for word in ('relaxation', 'calculator', 'constraints')): return 'Constraints and relaxation'
    if any(word in name for word in ('rdf', 'scalar', 'properties', 'force_vectors', 'colormap', 'displacements')): return 'Analysis and stored properties'
    if any(word in name for word in ('playback', 'set_frame')): return 'Trajectory playback'
    if any(word in name for word in ('camera', 'compose_view', 'render_area', 'quality')): return 'Camera and framing'
    if any(word in name for word in ('style', 'bonds', 'color', 'display', 'visual', 'theme')): return 'Appearance and bonds'
    if spec.method in {'ready', 'describe', 'capabilities', 'documents', 'activate', 'newDocument', 'events'}: return 'Connection and collaboration'
    if any(word in name for word in ('structure', 'files')): return 'File input'
    return 'Structure editing and construction'


def render():
    groups = {}
    for spec in tool_catalog().values():
        groups.setdefault(section(spec), []).append(spec)
    lines = ['# Tools by feature', '',
             'The catalog below is generated from the same schemas used by MCP and native',
             'function tools. Inputs use snake_case. Scientific units are Angstrom and',
             'degrees; atom and frame indices are zero-based. Tool discovery provides',
             'complete nested types, bounds and conditions.', '',
             '```{contents} On this page', ':local:', ':depth: 1', '```', '',
             'Ordinary editing tools also require `expected_document_id` and',
             '`expected_revision`; these guards and optional `response_profile` are',
             'omitted from the tables for readability. Interrupt controls may omit the',
             'revision. See [connection and recovery](ai-tools.md#read-edit-verify).', '']
    for group, specs in groups.items():
        lines += ['## '+group, '', '```{list-table}', ':header-rows: 1',
                  ':widths: 45 55', '', '* - Tool', '  - Purpose']
        for spec in specs:
            text = re.sub(r'^\S+\. Mode: [^.]+\. ', '', spec.description).replace('|', '\\|').replace('\n', ' ').strip()
            if len(text) > 240:
                text = text[:235].rsplit(' ', 1)[0] + '…'
            lines += [f'* - `{spec.name}`', f'  - {text}']
        lines += ['```', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    target = ROOT / 'docs/ai-tools-reference.md'
    content = render()
    if '--check' in sys.argv:
        if not target.exists() or target.read_text() != content:
            raise SystemExit('Run python scripts/generate_ai_tool_reference.py')
    else:
        target.write_text(content)
