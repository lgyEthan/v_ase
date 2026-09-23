'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const config = require('../package.json').build;
const extensions = require('../file-formats.json').structureExtensions;

test('only vase is registered as a default; Mac structure handlers are Alternate', () => {
    assert.deepEqual(config.fileAssociations.map(item => item.ext), ['vase']);
    const formats = config.mac.fileAssociations[0];
    assert.equal(formats.rank, 'Alternate');
    assert.deepEqual(formats.ext, extensions);
    for (const ext of ['extxyz', 'xyz', 'vasp', 'cif', 'traj', 'html', 'cube']) assert.ok(extensions.includes(ext));
});
test('Windows structure candidates never modify extension defaults or UserChoice', () => {
    const source = fs.readFileSync(path.join(root, 'assets/file-associations.nsh'), 'utf8');
    const registryWrites = source.split('\n').filter(line => /^\s*WriteReg/.test(line));
    assert.ok(!registryWrites.some(line => line.includes('UserChoice')));
    for (const ext of extensions) {
        const lines = registryWrites.filter(line => line.includes(`\\.${ext}\\`));
        assert.equal(lines.length, 1);
        assert.match(lines[0], /WriteRegNone .*\\OpenWithProgids/);
    }
    assert.match(source, /AllowSilentDefaultTakeOver/);
    assert.match(source, /DeleteRegValue.*OpenWithProgids/);
});
test('documents use dedicated platform icons, separate from the application castle', () => {
    for (const extension of ['icns', 'ico', 'png']) {
        const app = fs.readFileSync(path.join(root, `assets/icon.${extension}`));
        for (const stem of ['document', 'structure-document']) {
            const icon = fs.readFileSync(path.join(root, `assets/${stem}.${extension}`));
            assert.ok(icon.length > 1000);
            assert.ok(!app.equals(icon));
        }
    }
});
