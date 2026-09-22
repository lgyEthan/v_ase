'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { FileVault } = require('../file-vault.cjs');

async function fixture(t) {
    const root = await fs.mkdtemp(path.join(os.tmpdir(), 'vase-native-save-'));
    const vault = new FileVault();
    t.after(async () => { await vault.revoke(7); await fs.rm(root, { recursive: true, force: true }); });
    return { root, vault };
}

test('native Save preserves the original until an atomic successful close', async t => {
    const { root, vault } = await fixture(t);
    const file = path.join(root, 'sample.vase');
    await fs.writeFile(file, 'original');
    const handle = await vault.authorize(7, file);
    const id = await vault.begin(7, handle.token);
    await vault.chunk(7, id, Buffer.from('updated'));
    assert.equal(await fs.readFile(file, 'utf8'), 'original');
    await vault.finish(7, id);
    assert.equal(await fs.readFile(file, 'utf8'), 'updated');
    assert.equal((await vault.stat(7, handle.token)).size, 7);
    const second = await vault.authorize(7, file);
    assert.equal(vault.same(7, handle.token, second.token), true);
});

test('external writes, cancelled saves and foreign tokens cannot replace a project', async t => {
    const { root, vault } = await fixture(t);
    const file = path.join(root, 'sample.html');
    await fs.writeFile(file, 'original');
    const handle = await vault.authorize(7, file);
    await assert.rejects(vault.begin(8, handle.token), /Unknown file/);
    const id = await vault.begin(7, handle.token);
    await vault.chunk(7, id, Buffer.from('pending'));
    await fs.writeFile(file, 'external');
    await assert.rejects(vault.finish(7, id), /changed while saving/);
    assert.equal(await fs.readFile(file, 'utf8'), 'external');
    await assert.rejects(vault.begin(7, handle.token), /changed outside/);
    const second = await vault.authorize(7, file);
    const cancelled = await vault.begin(7, second.token);
    await vault.chunk(7, cancelled, Buffer.from('discard'));
    await vault.abort(7, cancelled);
    assert.deepEqual(await fs.readdir(root), ['sample.html']);
    assert.equal(await fs.readFile(file, 'utf8'), 'external');
});

test('new files, save collisions, oversized chunks and revocation are bounded', async t => {
    const { root, vault } = await fixture(t);
    const handle = await vault.authorize(7, path.join(root, 'new.vase'));
    assert.equal((await vault.stat(7, handle.token)).size, 0);
    const id = await vault.begin(7, handle.token);
    await assert.rejects(vault.begin(7, handle.token), /pending save/);
    await assert.rejects(vault.chunk(7, id, Buffer.alloc(4 * 1024 * 1024 + 1)), /Invalid file chunk/);
    await vault.revoke(7);
    assert.deepEqual(await fs.readdir(root), []);
    await assert.rejects(vault.stat(7, handle.token), /Unknown file/);
});

test('native Open reads only granted files in bounded chunks and detects changes', async t => {
    const { root, vault } = await fixture(t);
    const file = path.join(root, 'large.xyz');
    const original = Buffer.alloc(4 * 1024 * 1024 + 7, 65);
    await fs.writeFile(file, original);
    const handle = await vault.authorize(7, file);
    const first = await vault.read(7, handle.token, 0);
    assert.equal(first.length, 4 * 1024 * 1024);
    const last = await vault.read(7, handle.token, first.length);
    assert.deepEqual(Buffer.concat([first, last]), original);
    await assert.rejects(vault.read(8, handle.token, 0), /Unknown file/);
    await assert.rejects(vault.read(7, handle.token, -1), /Invalid read/);
    await fs.writeFile(file, 'changed');
    await assert.rejects(vault.read(7, handle.token, 0), /file changed/);
});

test('simultaneous document saves cannot acquire the same target', async t => {
    const { root, vault } = await fixture(t);
    const handle = await vault.authorize(7, path.join(root, 'race.vase'));
    const results = await Promise.allSettled([vault.begin(7, handle.token), vault.begin(7, handle.token)]);
    assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
    assert.match(results.find(result => result.status === 'rejected').reason.message, /pending save/);
    await vault.abort(7, results.find(result => result.status === 'fulfilled').value);
    const retry = await vault.begin(7, handle.token);
    await vault.abort(7, retry);
});
