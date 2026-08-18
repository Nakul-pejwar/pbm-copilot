#!/usr/bin/env node
/**
 * Build + bundle the PBM Copilot Superset extension into a .supx file.
 *
 * Usage (from extensions/pbm-copilot/frontend/):
 *   node bundle.mjs
 *
 * Produces ../../pbm.pbm-copilot-<version>.supx (zip: manifest.json + frontend/dist/*).
 */
import { execSync } from 'node:child_process';
import { createWriteStream, existsSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import archiver from 'archiver';

const frontend = dirname(fileURLToPath(import.meta.url));
const root = dirname(frontend);
const dist = join(frontend, 'dist');
const timestamp = new Date()
  .toISOString()
  .replace(/[-:]/g, '')
  .replace(/\.\d{3}Z$/, 'Z');

console.log('Building frontend assets...');
execSync('npm run build', { cwd: frontend, stdio: 'inherit' });

const extension = JSON.parse(readFileSync(join(root, 'extension.json'), 'utf-8'));
const distFiles = readdirSync(dist).filter((f) => f.endsWith('.js'));
const remoteEntry = distFiles.find((f) => f.startsWith('remoteEntry.'));
if (!remoteEntry) {
  throw new Error('remoteEntry.*.js not found in frontend/dist');
}

const manifest = {
  id: `${extension.publisher}.${extension.name}`,
  publisher: extension.publisher,
  name: extension.name,
  displayName: extension.displayName,
  version: extension.version,
  license: extension.license,
  permissions: extension.permissions ?? [],
  dependencies: [],
  frontend: {
    remoteEntry,
    moduleFederationName: 'pbm_pbmCopilot',
  },
};

const extRoot = join(root, '..');
const out = join(extRoot, `pbm.${extension.name}-${extension.version}.${timestamp}.supx`);
for (const stale of readdirSync(extRoot).filter((f) =>
  f.startsWith(`pbm.${extension.name}-${extension.version}.`) && f.endsWith('.supx')
)) {
  rmSync(join(extRoot, stale));
}

const output = createWriteStream(out);
const archive = archiver('zip', { zlib: { level: 9 } });
archive.pipe(output);
archive.append(JSON.stringify(manifest, null, 2), { name: 'manifest.json' });
for (const f of distFiles) {
  archive.file(join(dist, f), { name: `frontend/dist/${f}` });
}
await archive.finalize();

console.log(`Bundled ${out} (${manifest.id} v${manifest.version}, remoteEntry=${remoteEntry})`);