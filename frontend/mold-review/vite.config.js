import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {cpSync, mkdirSync, readdirSync, rmSync} from 'node:fs';
import {resolve} from 'node:path';

const runtimeAssets = resolve(process.cwd(), 'src/easy_cheese/skills/mold/assets');

function embedAssets() {
  return {
    name: 'embed-mold-review-assets',
    closeBundle() {
      const dist = resolve(process.cwd(), 'frontend/mold-review/dist');
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
  root: 'frontend/mold-review',
  plugins: [react(), embedAssets()],
  build: {outDir: 'dist', emptyOutDir: true},
});