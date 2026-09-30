'use strict';

// A renderer animation frame can precede the native compositor's new bitmap.
// Keep pixel assertions strict while allowing bounded presentation latency.
module.exports = async function waitForVisualFrame(read, accepts, {
    timeout = 15000, interval = 80,
} = {}) {
    const deadline = Date.now() + timeout;
    let bitmap;
    do {
        bitmap = await read();
        if (accepts(bitmap)) return bitmap;
        await new Promise(resolve => setTimeout(resolve, interval));
    } while (Date.now() < deadline);
    return bitmap;
};
