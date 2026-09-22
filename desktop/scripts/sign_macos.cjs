'use strict';

// Sign a disposable, already tested CI app. Private keys remain in Keychain.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { signAsync } = require('@electron/osx-sign');

const [input, identity] = process.argv.slice(2);
if (process.platform !== 'darwin' || !input || !identity || identity === '-') {
  throw new Error('Usage on macOS: node scripts/sign_macos.cjs /absolute/path/v_ase.app "Developer ID Application: …"');
}
const app = fs.realpathSync(input);
const identifier = execFileSync('/usr/libexec/PlistBuddy', [
  '-c', 'Print :CFBundleIdentifier', path.join(app, 'Contents', 'Info.plist'),
], { encoding: 'utf8' }).trim();
if (!app.endsWith('.app') || identifier !== 'org.v-ase.desktop') {
  throw new Error('Expected the v_ase desktop application bundle');
}
// osx-sign also discovers binary data (PNG, ASAR, wheels). Only Mach-O code
// and enclosing code bundles need signatures; signing data adds resource forks.
const magic = new Set(['feedface', 'cefaedfe', 'feedfacf', 'cffaedfe',
  'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca']);
let count = 0;
function isCode(file) {
  if (fs.statSync(file).isDirectory()) return /\.(app|framework)$/.test(file);
  const descriptor = fs.openSync(file, 'r');
  try {
    const header = Buffer.alloc(4);
    return fs.readSync(descriptor, header, 0, 4, 0) === 4 && magic.has(header.toString('hex'));
  } finally {
    fs.closeSync(descriptor);
  }
}
signAsync({
  app,
  identity,
  platform: 'darwin',
  type: 'distribution',
  preAutoEntitlements: false,
  preEmbedProvisioningProfile: false,
  strictVerify: true,
  ignore: file => !isCode(file),
  optionsForFile: () => {
    count += 1;
    if (count === 1 || count % 25 === 0) console.log(`Signing code component ${count}…`);
    return {
      hardenedRuntime: true,
      entitlements: path.resolve(__dirname, '../assets/entitlements.mac.plist'),
    };
  },
}).then(() => {
  execFileSync('codesign', ['--display', '--verbose=4', app], { stdio: 'inherit' });
  console.log(`Developer ID signing complete: ${count} code components.`);
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});
