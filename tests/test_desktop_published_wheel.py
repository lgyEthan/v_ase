"""Desktop releases must install the verified PyPI artifact despite index lag."""
import hashlib
import io
import json
from pathlib import Path
import runpy

import pytest


@pytest.mark.parametrize('failure', [None, 'version', 'missing', 'yanked', 'host', 'digest'])
def test_published_wheel_validates_metadata_and_bytes(tmp_path, failure):
    namespace = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'desktop/scripts/prepare_runtime.py'))
    resolver = namespace['published_wheel']
    data = b'published-wheel-fixture'
    (tmp_path / 'package.json').write_text(json.dumps({'version': '0.4.8'}))
    item = {'filename': 'v_ase_gui-0.4.8-py3-none-any.whl', 'packagetype': 'bdist_wheel',
            'url': 'https://files.pythonhosted.org/packages/verified.whl',
            'digests': {'sha256': hashlib.sha256(data).hexdigest()}, 'yanked': False}
    payload = {'info': {'version': '0.4.8'}, 'urls': [item]}
    if failure == 'version': payload['info']['version'] = '0.4.7'
    if failure == 'missing': payload['urls'] = []
    if failure == 'yanked': item['yanked'] = True
    if failure == 'host': item['url'] = 'https://example.org/foreign.whl'
    if failure == 'digest': item['digests']['sha256'] = '0' * 64
    downloads = []

    def fetch(url, **kwargs):
        if url.endswith('/json'):
            return io.BytesIO(json.dumps(payload).encode())
        downloads.append(url)
        return io.BytesIO(data)

    resolver.__globals__['urlopen'] = fetch
    if failure:
        with pytest.raises(SystemExit): resolver(tmp_path)
        assert not list((tmp_path / '.cache').glob('*.whl'))
    else:
        wheel = resolver(tmp_path)
        assert wheel.read_bytes() == data
        assert resolver(tmp_path) == wheel
        assert len(downloads) == 1
        wheel.write_bytes(b'corrupted cache')
        assert resolver(tmp_path).read_bytes() == data
        assert len(downloads) == 2
