export const MAX_ATOM_SCALAR_CACHE_BYTES = 32 * 1024 * 1024;
const MAX_CATALOG_ENTRIES = 16;

export class AtomScalarStore {
    constructor(api, contextProvider = () => ({})) {
        this.api = api;
        this.contextProvider = contextProvider;
        this.generation = 0;
        this.catalogCache = new Map();
        this.valueCache = new Map();
        this.valueCacheBytes = 0;
        this.pending = new Map();
    }

    context() {
        const value = this.contextProvider?.() || {};
        return {
            documentId: String(value.documentId || ''),
            dataGeneration: Number(value.dataGeneration || 0),
            timeline: String(value.timeline || 'loaded'),
            frame: Number(value.frame || 0),
            atomCount: Number(value.atomCount || 0),
            signature: String(value.signature || '')
        };
    }

    contextKey(frame = this.context().frame) {
        const context = this.context();
        return [
            context.documentId,
            context.dataGeneration,
            context.timeline,
            frame,
            context.atomCount,
            context.signature
        ].join('|');
    }

    invalidate() {
        this.generation += 1;
        this.catalogCache.clear();
        this.valueCache.clear();
        this.valueCacheBytes = 0;
        this.pending.clear();
    }

    shared(key, loader) {
        if (this.pending.has(key)) return this.pending.get(key);
        const promise = Promise.resolve().then(loader).finally(() => {
            if (this.pending.get(key) === promise) this.pending.delete(key);
        });
        this.pending.set(key, promise);
        return promise;
    }

    async catalog({ refresh = false } = {}) {
        const frame = this.context().frame;
        const key = `catalog|${this.contextKey(frame)}`;
        if (refresh) this.catalogCache.delete(key);
        if (!this.catalogCache.has(key)) {
            const generation = this.generation;
            const catalog = await this.shared(key, () => this.api.fetchAtomScalarCatalog(frame));
            if (generation !== this.generation) throw new Error('Per-atom property catalog became stale.');
            this.catalogCache.set(key, catalog);
            while (this.catalogCache.size > MAX_CATALOG_ENTRIES) {
                this.catalogCache.delete(this.catalogCache.keys().next().value);
            }
        }
        return this.catalogCache.get(key);
    }

    coordinateValues(field) {
        const component = { 'position:x': 0, 'position:y': 1, 'position:z': 2 }[field];
        const positions = this.contextProvider?.()?.positions;
        if (component === undefined || !Array.isArray(positions)) return null;
        return Float64Array.from(positions, position => Number(position?.[component]));
    }

    async values(field, { frame = this.context().frame, allFrames = false } = {}) {
        const coordinate = !allFrames ? this.coordinateValues(field) : null;
        if (coordinate) return { values: coordinate, frames: 1, startFrame: frame, atoms: coordinate.length, cache: 'coordinates' };
        const context = this.context();
        if (context.timeline === 'relax' && !allFrames) {
            // Optimizer previews contain positions, not the loaded trajectory's
            // calculator arrays. Reusing the latter would misstate the figure.
            return {
                values: Float64Array.from({ length: context.atomCount }, () => Number.NaN),
                frames: 1, startFrame: frame, atoms: context.atomCount,
                cache: 'unavailable', unavailable: true
            };
        }
        const key = `values|${this.contextKey(allFrames ? 0 : frame)}|${field}|${allFrames ? 'all' : 'one'}`;
        if (!this.valueCache.has(key)) {
            const generation = this.generation;
            const result = await this.shared(
                key,
                () => this.api.fetchAtomScalarValues(field, frame, allFrames)
            );
            if (generation !== this.generation) throw new Error('Per-atom property values became stale.');
            const bytes = Number(result?.values?.byteLength || 0);
            if (bytes <= MAX_ATOM_SCALAR_CACHE_BYTES) {
                this.valueCache.set(key, result);
                this.valueCacheBytes += bytes;
                while (this.valueCacheBytes > MAX_ATOM_SCALAR_CACHE_BYTES
                    || this.valueCache.size > 64) {
                    const oldest = this.valueCache.keys().next().value;
                    this.valueCacheBytes -= Number(this.valueCache.get(oldest)?.values?.byteLength || 0);
                    this.valueCache.delete(oldest);
                }
            }
            return result;
        }
        const cached = this.valueCache.get(key);
        this.valueCache.delete(key);
        this.valueCache.set(key, cached);
        return cached;
    }

    async range(field, { frame = this.context().frame, allFrames = false, indices = null } = {}) {
        return await this.api.fetchAtomScalarRange(field, frame, allFrames, indices);
    }
}
