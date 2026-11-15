import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {copyFileSync, mkdirSync, mkdtempSync, readdirSync, renameSync, rmSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, '../..');
const runtimeAssets = resolve(repoRoot, 'src/easy_cheese/skills/mold/assets');

// Replace the runtime assets in place without a gap. An archive build, the
// review server, or a test can read the tree while this build runs, so the
// tree must always hold an index.html and every file that it loads. Each file
// moves in with one atomic rename from a staging directory outside the
// packaged tree. The hashed files move before the index.html that loads them.
// Stale files go last.
function embedAssets() {
  return {
    name: 'embed-mold-review-assets',
    closeBundle() {
      const dist = resolve(frontendRoot, 'dist');
      const hashed = resolve(dist, 'assets');
      // A Map keeps insertion order, so index.html moves last.
      const sources = new Map(readdirSync(hashed).map((name) => [name, resolve(hashed, name)]));
      sources.set('NOTICE', resolve(dist, 'NOTICE'));
      sources.set('index.html', resolve(dist, 'index.html'));
      mkdirSync(runtimeAssets, {recursive: true});
      const cache = resolve(frontendRoot, 'node_modules/.cache');
      mkdirSync(cache, {recursive: true});
      const staging = mkdtempSync(resolve(cache, 'mold-assets-'));
      try {
        for (const [name, source] of sources) {
          const staged = resolve(staging, name);
          copyFileSync(source, staged);
          renameSync(staged, resolve(runtimeAssets, name));
        }
      } finally {
        rmSync(staging, {recursive: true, force: true});
      }
      for (const name of readdirSync(runtimeAssets)) {
        if (!sources.has(name)) {
          rmSync(resolve(runtimeAssets, name), {recursive: true, force: true});
        }
      }
    },
  };
}

export default defineConfig({
  root: frontendRoot,
  plugins: [react(), embedAssets()],
  build: {outDir: resolve(frontendRoot, 'dist'), emptyOutDir: true},
});