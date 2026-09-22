'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');

// Run before electron-builder signs the framework and application resources.
module.exports = async context => {
    if (context.electronPlatformName !== 'darwin') return;
    const source = path.join(context.packager.projectDir, 'runtime', 'graphics');
    const contents = path.join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`, 'Contents');
    await fs.copyFile(path.join(source, 'libvulkan.dylib'),
        path.join(contents, 'Frameworks', 'Electron Framework.framework', 'Libraries', 'libvulkan.dylib'));
    await fs.cp(source, path.join(contents, 'Resources', 'graphics'), { recursive: true });
};
