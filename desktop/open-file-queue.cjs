'use strict';

// Finder emits one open-file event per file; Explorer may start one process per
// file. Coalesce a burst before sending it to one ready editor window.
class OpenFileQueue {
    constructor(deliver, { delay = 650, setTimer = setTimeout, clearTimer = clearTimeout } = {}) {
        this.deliver = deliver;
        this.delay = delay;
        this.setTimer = setTimer;
        this.clearTimer = clearTimer;
        this.files = new Map();
        this.timer = null;
        this.draining = null;
    }
    add(files) {
        for (const file of files) {
            const key = process.platform === 'win32' ? file.toLowerCase() : file;
            this.files.set(key, file);
        }
        if (!this.files.size) return;
        if (this.timer !== null) this.clearTimer(this.timer);
        this.timer = this.setTimer(() => { this.timer = null; void this.flush().catch(console.error); }, this.delay);
    }
    async flush() {
        if (this.draining) return this.draining;
        if (this.timer !== null) { this.clearTimer(this.timer); this.timer = null; }
        if (!this.files.size) return;
        const batch = this.files;
        this.files = new Map();
        let delivered = false;
        this.draining = (async () => {
            try {
                if (await this.deliver([...batch.values()]) === false) {
                    this.files = new Map([...batch, ...this.files]);
                } else delivered = true;
            } catch (error) {
                this.files = new Map([...batch, ...this.files]);
                throw error;
            }
        })();
        try { await this.draining; } finally {
            this.draining = null;
            // A debounce can expire while delivery is still awaiting a window.
            // Schedule new arrivals again, but never spin on a not-ready window.
            if (delivered && this.files.size && this.timer === null) {
                this.timer = this.setTimer(() => { this.timer = null; void this.flush().catch(console.error); }, this.delay);
            }
        }
    }
}
module.exports = { OpenFileQueue };
