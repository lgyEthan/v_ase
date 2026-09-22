'use strict';

const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const { createHash, randomUUID } = require('node:crypto');

async function fingerprint(filename) {
    let stat;
    try { stat = await fsp.lstat(filename, { bigint: true }); }
    catch (error) { if (error.code === 'ENOENT') return null; throw error; }
    if (!stat.isFile()) throw new Error('The selected target is no longer a regular file.');
    const hash = createHash('sha256');
    for await (const chunk of fs.createReadStream(filename)) hash.update(chunk);
    return `${stat.dev}:${stat.ino}:${stat.size}:${stat.mtimeNs}:${hash.digest('hex')}`;
}

class FileVault {
    constructor() { this.handles = new Map(); this.writes = new Map(); this.pendingPaths = new Set(); }

    // Called only by main-process OS dialogs, never with a renderer-supplied path.
    async authorize(owner, filename) {
        let resolved;
        try { resolved = await fsp.realpath(filename); }
        catch (error) {
            if (error.code !== 'ENOENT') throw error;
            resolved = path.join(await fsp.realpath(path.dirname(filename)), path.basename(filename));
        }
        const token = randomUUID();
        const record = { owner, path: resolved, version: await fingerprint(resolved) };
        this.handles.set(token, record);
        return { token, name: path.basename(resolved) };
    }

    fork(owner, token, newOwner) {
        const record = this.handle(owner, token);
        const next = randomUUID();
        // Keep the original fingerprint: detaching must not accept an external edit.
        this.handles.set(next, { ...record, owner: newOwner });
        return { token: next, name: path.basename(record.path) };
    }

    handle(owner, token) {
        const record = this.handles.get(token);
        if (!record || record.owner !== owner) throw new Error('Unknown file permission. Choose the file again.');
        return record;
    }

    async stat(owner, token) {
        const record = this.handle(owner, token);
        let info;
        try { info = await fsp.stat(record.path); }
        catch (error) { if (error.code !== 'ENOENT') throw error; }
        return { name: path.basename(record.path), size: info?.size || 0, lastModified: Math.trunc(info?.mtimeMs || 0) };
    }

    async read(owner, token, offset) {
        const record = this.handle(owner, token);
        if (!Number.isSafeInteger(offset) || offset < 0) throw new Error('Invalid read offset.');
        const file = await fsp.open(record.path, 'r');
        try {
            const size = (await file.stat()).size;
            if (offset > size) throw new Error('Invalid read offset.');
            if (offset === 0 && await fingerprint(record.path) !== record.version) {
                throw new Error('The file changed. Choose it again.');
            }
            const buffer = Buffer.alloc(Math.min(4 * 1024 * 1024, size - offset));
            const { bytesRead } = await file.read(buffer, 0, buffer.length, offset);
            if (offset + bytesRead >= size && await fingerprint(record.path) !== record.version) {
                throw new Error('The file changed while opening. Choose it again.');
            }
            return buffer.subarray(0, bytesRead);
        } finally { await file.close(); }
    }

    same(owner, first, second) {
        const a = this.handle(owner, first).path, b = this.handle(owner, second).path;
        return process.platform === 'win32' ? a.toLowerCase() === b.toLowerCase() : a === b;
    }

    async begin(owner, token) {
        const grant = this.handle(owner, token);
        const key = process.platform === 'win32' ? grant.path.toLowerCase() : grant.path;
        if (this.pendingPaths.has(key)) {
            throw new Error('This file already has a pending save.');
        }
        this.pendingPaths.add(key);
        try {
            const version = grant.version;
            if (await fingerprint(grant.path) !== version) {
                throw new Error('The file changed outside v_ase. Reload it or use Save As.');
            }
            const id = randomUUID();
            const temporary = path.join(path.dirname(grant.path), `.vase-${id}.tmp`);
            const mode = version ? (await fsp.stat(grant.path)).mode : 0o666;
            const file = await fsp.open(temporary, 'wx', mode);
            this.writes.set(id, { owner, grant, temporary, file, key, version });
            return id;
        } catch (error) {
            this.pendingPaths.delete(key);
            throw error;
        }
    }

    transaction(owner, id) {
        const record = this.writes.get(id);
        if (!record || record.owner !== owner) throw new Error('Unknown save transaction.');
        return record;
    }

    async chunk(owner, id, bytes) {
        const record = this.transaction(owner, id);
        if (!(bytes instanceof Uint8Array) || bytes.byteLength > 4 * 1024 * 1024) {
            throw new Error('Invalid file chunk.');
        }
        await record.file.writeFile(bytes);
    }

    async finish(owner, id) {
        const record = this.transaction(owner, id);
        try {
            await record.file.sync();
            await record.file.close();
            if (await fingerprint(record.grant.path) !== record.version) {
                throw new Error('The file changed while saving. Reload it or use Save As.');
            }
            await fsp.rename(record.temporary, record.grant.path);
            record.grant.version = await fingerprint(record.grant.path);
        } finally {
            this.writes.delete(id);
            this.pendingPaths.delete(record.key);
            await record.file.close().catch(() => {});
            await fsp.unlink(record.temporary).catch(() => {});
        }
    }

    async abort(owner, id) {
        const record = this.transaction(owner, id);
        this.writes.delete(id);
        this.pendingPaths.delete(record.key);
        await record.file.close().catch(() => {});
        await fsp.unlink(record.temporary).catch(() => {});
    }

    async revoke(owner) {
        for (const [id, record] of this.writes) if (record.owner === owner) await this.abort(owner, id);
        for (const [token, record] of this.handles) if (record.owner === owner) this.handles.delete(token);
    }
}

module.exports = { FileVault, fingerprint };
