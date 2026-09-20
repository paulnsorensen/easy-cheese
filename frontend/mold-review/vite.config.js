import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {cpSync, mkdirSync, readdirSync, rmSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, '../..');
const runtimeAssets = resolve(repoRoot, 'src/easy_cheese/skills/mold/assets');

function embedAssets() {
  return {
    name: 'embed-mold-review-assets',
    closeBundle() {
      const dist = resolve(frontendRoot, 'dist');
      rmSync(runtimeAssets, {recursive: true, force: true});
      mkdirSync(runtimeAssets, {recursive: true});
      cpSync(resolve(dist, 'index.html'), resolve(runtimeAssets, 'index.html'));
      cpSync(resolve(dist, 'NOTICE'), resolve(runtimeAssets, 'NOTICE'));
      const hashed = resolve(dist, 'assets');
      for (const name of readdirSync(hashed)) {
        cpSync(resolve(hashed, name), resolve(runtimeAssets, name));
      }
    },
  };
}

export default defineConfig({
  root: frontendRoot,
  plugins: [react(), embedAssets()],
  build: {outDir: resolve(frontendRoot, 'dist'), emptyOutDir: true},
});