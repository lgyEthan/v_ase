"""Install/uninstall on a disposable Windows CI runner and inspect real associations."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import winreg

if os.environ.get('CI') != 'true':
    raise SystemExit('Run only on a disposable CI runner; this exercises the installer.')
root = Path(__file__).resolve().parents[1]
extensions = json.loads((root / 'file-formats.json').read_text())['structureExtensions']
installers = list((root / 'dist').glob('v_ase-*-win-x64.exe'))
assert len(installers) == 1, installers
classes = r'Software\Classes'


def value(path, name=''):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, classes + '\\' + path) as key:
            return winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


before = {ext: value('.' + ext) for ext in extensions}
with tempfile.TemporaryDirectory(prefix='vase-associations-') as temp:
    install = Path(temp) / 'app'
    subprocess.run([str(installers[0]), '/S', '/currentuser', f'/D={install}'], check=True, timeout=300)
    executable = install / 'v_ase.exe'
    assert executable.is_file()
    for ext in extensions:
        assert value('.' + ext) == before[ext], f'Changed the default for .{ext}'
        assert value('.' + ext + r'\OpenWithProgids', 'org.v-ase.structure') is not None, ext
    progid = value('.vase')[0]
    command = value(progid + r'\shell\open\command')[0]
    assert str(executable).lower() in command.lower() and '"%1"' in command
    assert 'document' in value(progid + r'\DefaultIcon')[0].lower()
    structure_icon = value(r'org.v-ase.structure\DefaultIcon')[0].strip('"')
    assert Path(structure_icon).is_file()
    uninstallers = list(install.glob('Uninstall*.exe'))
    assert len(uninstallers) == 1
    subprocess.run([str(uninstallers[0]), '/S', '/currentuser'], check=True, timeout=300)
    deadline = time.monotonic() + 60
    while executable.exists() and time.monotonic() < deadline:
        time.sleep(.2)
    assert not executable.exists()
    for ext in extensions:
        assert value('.' + ext) == before[ext], f'Uninstall changed .{ext}'
        assert value('.' + ext + r'\OpenWithProgids', 'org.v-ase.structure') is None, ext
output = root / 'smoke-output' / 'file-associations.json'
output.write_text(json.dumps({'extensions': extensions, 'defaultsPreserved': True,
                              'registered': True, 'uninstalledCleanly': True}, indent=2))
print(output.read_text())
