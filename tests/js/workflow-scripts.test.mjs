import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Script } from 'node:vm';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// PR1 acceptance (subagent-routing-overhaul.md): "both workflow scripts
// parse and contain no threshold constants (grep-verifiable)". Neither half
// had a test before this file — `just test`/`just check` never ran
// `node --check` or `npm run workflows:check` against workflows/*.js.

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), '../../..');
const WORKFLOW_FILES = ['cheese-factory.js', 'age-fanout.js'];

function source(filename) {
	return readFileSync(path.join(REPO_ROOT, 'workflows', filename), 'utf8');
}

// Workflow scripts are executed by the Claude Code Workflow tool's own
// runner, which evaluates the script body in an async context (per the
// tool's own docs: "the script body runs in an async context — use await
// directly") rather than running the file as a standalone Node module.
// `node --check` on the raw file always fails here — the top-level
// `return`/`await` statements are invalid outside a function, and `export`
// is only legal at true module top level, so wrapping in a function would
// itself be a syntax error. This test instead reproduces the harness's
// execution shape: strip the one `export` keyword each script uses (the
// only export/import in either file — see the two `grep -n` results below
// this comment for how that was verified) and parse the remainder wrapped
// in an async function. A real syntax error (stray brace, unterminated
// template literal) still fails this check; the harness-specific wrapping
// convention does not.
function assertParsesUnderHarnessModel(filename) {
	const body = source(filename).replace(/^export const meta = /, 'const meta = ');
	assert.doesNotThrow(() => new Script(`(async function () {\n${body}\n})`));
}

// The no-routing-in-JS invariant (spec cross-cutting contract 3 / PR1 item
// 8): N/effort/lenses must come from src/fanout/age_route.py's route()
// output, never a hardcoded size threshold re-implemented in JS.
const THRESHOLD_PATTERN = /\b(?:files_changed|insertions|deletions|diff_lines)\s*[<>]=?\s*\d+/;

for (const filename of WORKFLOW_FILES) {
	test(`${filename} parses under the harness's async-wrapped execution model`, () => {
		assertParsesUnderHarnessModel(filename);
	});

	test(`${filename} contains no hardcoded size/threshold routing logic`, () => {
		assert.doesNotMatch(source(filename), THRESHOLD_PATTERN);
	});

	test(`${filename} declares exactly one export (the meta object)`, () => {
		const exportLines = source(filename)
			.split('\n')
			.filter((line) => /^export\b/.test(line));
		assert.deepEqual(exportLines, ['export const meta = {']);
	});
}
