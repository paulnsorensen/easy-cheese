export const meta = {
  name: 'cheese-factory',
  description:
    'Spec-driven easy-cheese pipeline: resolve a spec (or list candidates), decide fan-out vs single-pass, run cook->taste->press per curd, then barrier-integrate, age, cure, and re-age the whole diff before plating clean branches into (stacked) PRs.',
  phases: [
    { title: 'Resolve', detail: 'cheap agent resolves the spec + curd-count digest, or lists candidates with no further dispatch' },
    { title: 'Decompose', detail: 'curds arrive as an upstream curd-block artifact (mold curdle or cook fallback decompose), or an opus decomposer agent produces and self-validates one against src/fanout/curd_block.py before returning; no JS-side merge logic' },
    { title: 'Cook', detail: 'sonnet coder implements one curd in an isolated worktree via /cook --auto; a blocked/halted cook gets up to 2 fresh-coder continuations that commit the partial work first' },
    { title: 'Taste', detail: 'opus reviewer 5-lens gate over the cook diff; revise triggers a bounded corrective pass' },
    { title: 'Press', detail: 'sonnet coder hardens tests via /press --auto' },
    { title: 'Integrate', detail: 'one coder merges surviving curd branches into an integration branch, slug-sorted, --no-ff; conflicts exclude that curd downstream' },
    { title: 'Age', detail: 'barrier review of the whole integrated diff; sizing (N/effort) comes from a routing agent that calls src/fanout/age_route.py, then either the age-fanout child workflow or one opus reviewer runs /age --auto and routes findings per curd' },
    { title: 'Cure', detail: 'parallel sonnet coders fix only curds with medium+ routed findings via /cure --auto --stake medium+' },
    { title: 'Re-age', detail: 'once, only if a cure committed: re-merge cured branches, then re-review scoped to the prior findings; still medium+ marks the curd dirty' },
    { title: 'Plate', detail: 'one opus barrier stacks clean curd branches into (stacked) PRs; never merges' },
    { title: 'Report', detail: 'per-curd status, branch, PR url, integration summary, and excluded-curd reasons' },
  ],
}

// Tracked source: workflows/cheese-factory.js in the easy-cheese repo (ported
// from the dotfiles-side claude/workflows/cheese-factory.js). Spec:
// specs/subagent-routing-overhaul.md — PR1 workstream item 8. See
// skills/cheese/references/decomposer.md for the curd-block schema and
// src/fanout/age_route.py for the age-router sizing function.
//
// Review moved from per-curd to a barrier whole-diff age before plate
// (ADR-006): reviewing each curd's diff in isolation left cross-curd
// behavioral interactions reviewed by nobody — curd A and curd B can each
// look correct alone and still break when their changes compose. The union
// diff is now aged once at the Integrate barrier instead, with /age's
// dimension fan-out (via the shared age-fanout child workflow) sized by
// src/fanout/age_route.py's routing decision instead of a hardcoded
// files/lines threshold.
//
// Args: { spec?: string /* slug | path */, correctiveRounds? = 2, curdBlock?:
//   object /* curd-block schema, skills/cheese/references/decomposer.md */ } —
//   a bare (non-JSON) string arg is treated as the spec itself, since the
//   harness invoke hint passes slash arguments as bare strings. Absolute and
//   ~/ spec paths are accepted.
//   - no spec: Resolve lists durable-corpus candidates and the workflow
//     returns them, dispatching no further agent.
//   - spec given but missing on disk: Resolve fails loud with a usage
//     message; the workflow returns { error } and stops.
//   - correctiveRounds bounds the taste `revise` -> corrective-coder loop,
//     default 2, clamped to a max of 3 (curd-flock's clamp pattern).
//   - curdBlock: when supplied, it is treated as an already-decomposed
//     curd-block artifact (e.g. embedded in the spec by /mold's curdle step)
//     — the Decompose phase only validates it against
//     src/fanout/curd_block.py, it never re-derives or merges curds itself.
//     When absent, Decompose dispatches one decomposer agent that produces
//     and self-validates a curd block against the same validator — this is
//     execution (an agent invocation), not routing logic embedded in JS.
//
// Handoff artifacts land repo-local in each curd worktree's `.cheese/` (they
// travel with the branch) — every phase agent must cd into the worktree
// before invoking a skill. Plate opens/updates PRs but never merges.

const NO_CHAIN_DIRECTIVE = 'Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. The /cheese-factory orchestrator is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window: first commit any work-in-progress locally on your branch (write phases), then write a partial slug with status: halt: <reason> and stop; do not silently timeout.'

const input = typeof args === 'string'
  ? (() => {
      try {
        const parsed = JSON.parse(args)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed
        if (typeof parsed === 'string' && parsed.length) return { spec: parsed.trim() }
      } catch { /* not JSON — fall through */ }
      log('args was a bare string — treating it as the spec')
      return { spec: args.trim() }
    })()
  : args || {}
const SPEC_ARG = typeof input.spec === 'string' && input.spec.length ? input.spec : null
const CURD_BLOCK_ARG = input.curdBlock && typeof input.curdBlock === 'object' && !Array.isArray(input.curdBlock) ? input.curdBlock : null
const MAX_CORRECTIVE_ROUNDS = 3
let CORRECTIVE_ROUNDS = Number.isInteger(input.correctiveRounds) && input.correctiveRounds >= 0 ? input.correctiveRounds : 2
if (CORRECTIVE_ROUNDS > MAX_CORRECTIVE_ROUNDS) {
  log(`Requested correctiveRounds ${CORRECTIVE_ROUNDS} exceeds max ${MAX_CORRECTIVE_ROUNDS}; clamping to ${MAX_CORRECTIVE_ROUNDS}.`)
  CORRECTIVE_ROUNDS = MAX_CORRECTIVE_ROUNDS
}

const COOK_CONTINUATIONS = 2
const CONTINUABLE_COOK_RE = /^(blocked|halt)\b/i

const SLUG_RE = /^[a-z0-9][a-z0-9._-]*$/
const SPEC_ARG_RE = /^(?:~\/|\/)?[a-zA-Z0-9._][a-zA-Z0-9._/-]*$/ // slug, relative, absolute, or ~/ path ('..' rejected separately)
const PATH_RE = /^[A-Za-z0-9._/-]+$/
const isValidPath = (p) => typeof p === 'string' && PATH_RE.test(p)
if (SPEC_ARG !== null && (!SPEC_ARG_RE.test(SPEC_ARG) || SPEC_ARG.includes('..'))) {
  log(`Invalid spec arg: ${SPEC_ARG}`)
  return { error: `Invalid spec arg: ${SPEC_ARG}` }
}
const branchFor = (slug) => `curd/${slug}`

// ---- schemas ----
const FINDING_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    severity: { type: 'string', enum: ['blocker', 'high', 'medium', 'low'] },
    file: { type: 'string' },
    line: { type: 'integer' },
    claim: { type: 'string' },
    why_it_matters: { type: 'string' },
    fix_direction: { type: 'string' },
  },
}

const RESOLVE_SCHEMA = {
  type: 'object',
  required: ['mode'],
  properties: {
    mode: { type: 'string', enum: ['candidates', 'resolved', 'missing'] },
    candidates: { type: 'array', items: { type: 'string' } },
    spec_path: { type: 'string' },
    spec_text: { type: 'string' },
    usage: { type: 'string' },
    curd_count: {
      type: 'object',
      properties: {
        slug: { type: 'string' },
        candidate_curds: { type: 'integer' },
        blast_radius: { type: 'string' },
      },
    },
  },
}

const CURD_BLOCK_SCHEMA = {
  type: 'object',
  required: ['curds', 'waves', 'decomposer', 'valid'],
  properties: {
    valid: { type: 'boolean' },
    validation_errors: { type: 'array', items: { type: 'string' } },
    curds: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'contract', 'files', 'test_target', 'acceptance', 'seed'],
        properties: {
          slug: { type: 'string' },
          contract: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          test_target: { type: 'string' },
          acceptance: { type: 'array', items: { type: 'string' } },
          seed: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    waves: { type: 'array', items: { type: 'array', items: { type: 'string' } } },
    decomposer: {
      type: 'object',
      required: ['source', 'model', 'prompt_version'],
      properties: {
        source: { type: 'string' },
        model: { type: 'string' },
        prompt_version: { type: 'string' },
      },
    },
  },
}

const MINISPEC_SCHEMA = {
  type: 'object',
  required: ['curds'],
  properties: {
    curds: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slug', 'spec_path'],
        properties: { slug: { type: 'string' }, spec_path: { type: 'string' } },
      },
    },
  },
}

const COOK_SCHEMA = {
  type: 'object',
  required: ['status', 'worktree_path'],
  properties: {
    status: { type: 'string' },
    artifact: { type: 'string' },
    worktree_path: { type: 'string' },
    orientation: { type: 'string' },
  },
}

const TASTE_SCHEMA = {
  type: 'object',
  required: ['verdict', 'lenses', 'issues'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'revise'] },
    lenses: { type: 'array', items: { type: 'object', required: ['lens', 'verdict'], properties: { lens: { type: 'string' }, verdict: { type: 'string' }, note: { type: 'string' } } } },
    issues: { type: 'array', items: { type: 'string' } },
    recommendation: { type: 'string' },
  },
}

const CORRECT_SCHEMA = {
  type: 'object',
  required: ['status', 'committed'],
  properties: { status: { type: 'string' }, summary: { type: 'string' }, committed: { type: 'boolean' } },
}

const PHASE_SCHEMA = {
  type: 'object',
  required: ['status'],
  properties: { status: { type: 'string' }, artifact: { type: 'string' }, orientation: { type: 'string' } },
}

const INTEGRATE_SCHEMA = {
  type: 'object',
  required: ['worktree_path', 'merged', 'conflicted', 'files_changed', 'lines_changed'],
  properties: {
    worktree_path: { type: 'string' },
    merged: { type: 'array', items: { type: 'string' } },
    conflicted: { type: 'array', items: { type: 'string' } },
    files_changed: { type: 'integer' },
    lines_changed: { type: 'integer' },
  },
}

const AGE_ROUTE_SCHEMA = {
  type: 'object',
  required: ['n', 'lenses', 'effort'],
  properties: {
    n: { type: 'integer', enum: [1, 4, 10] },
    lenses: { type: 'array', items: { type: 'array', items: { type: 'string' } } },
    effort: { type: 'string', enum: ['medium', 'high'] },
    overrides_hit: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
  },
}

const AGE_BARRIER_SCHEMA = {
  type: 'object',
  required: ['status', 'has_medium_plus_findings'],
  properties: {
    status: { type: 'string' },
    artifact: { type: 'string' },
    has_medium_plus_findings: { type: 'boolean' },
    per_curd: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          slug: { type: 'string' },
          has_medium_plus_findings: { type: 'boolean' },
          findings: {
            type: 'array',
            items: FINDING_ITEM_SCHEMA,
          },
        },
      },
    },
  },
}

const CURE_SCHEMA = {
  type: 'object',
  required: ['status', 'committed'],
  properties: { status: { type: 'string' }, committed: { type: 'boolean' }, artifact: { type: 'string' } },
}

const PLATE_SCHEMA = {
  type: 'object',
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: { type: 'object', required: ['slug', 'status'], properties: { slug: { type: 'string' }, status: { type: 'string' }, pr_url: { type: 'string' } } },
    },
  },
}

// ---- pure helpers (validation only — no merge/decompose/threshold logic) ----
function findInvalidSlugs(curds) {
  return curds.filter((c) => typeof c.slug !== 'string' || !c.slug.length || !SLUG_RE.test(c.slug)).map((c) => c.slug || '(missing slug)')
}

function findDuplicateSlugs(curds) {
  const seen = new Set(); const dupes = new Set()
  for (const c of curds) { if (seen.has(c.slug)) dupes.add(c.slug); seen.add(c.slug) }
  return [...dupes]
}

// ---- prompts ----
function resolvePrompt() {
  return `You are a cheap resolver agent for the /cheese-factory workflow. Use Bash.

${SPEC_ARG
  ? `A spec was given: "${SPEC_ARG}" (slug or path).
1. Resolve it: \`SPEC=$(python3 ~/.claude/skills/mold/scripts/mold.pyz artifact-path specs ${SPEC_ARG})\`, falling back to treating the arg as a literal path if it already looks like one.
2. If the resolved file does not exist, return {"mode":"missing","usage":"Usage: /cheese-factory { spec: <slug-or-path> } — spec not found at <resolved path>"}.
3. Otherwise read the spec's full text, then run: \`python3 ~/.claude/skills/mold/scripts/mold.pyz curd-count "$SPEC" --blast-radius medium\` (omit --blast-radius if the spec states one and use that instead). Return {"mode":"resolved","spec_path":"<resolved path>","spec_text":"<full spec text>","curd_count":{"slug":"...","candidate_curds":<n>,"blast_radius":"..."}}.`
  : `No spec was given. Scan the durable spec corpus ($XDG_DATA_HOME/cheese/<project>/specs/ or ~/.local/share/cheese/<project>/specs/) plus legacy .cheese/specs/ for candidate spec files. Return {"mode":"candidates","candidates":["<slug-or-path>", ...]}.`}

Return only the structured JSON described above.`
}

function decomposePrompt(specText, parentSlug) {
  return `You are an opus decomposer for the /cheese-factory workflow, invoked because no upstream curd block was supplied as this run's args. Use Bash and your write tool.

Read \`skills/cheese/references/decomposer.md\` (fallback if missing: \`~/.claude/skills/cheese/references/decomposer.md\`) for the locked curd-block schema and producer contract — do not invent the schema from memory. You are acting as the same fallback decompose gate /cook runs for an un-curded task above the linear threshold: split the spec below into file-disjoint, independently implementable curds per that schema.

Spec:
${specText}

Produce a curd block: {"curds":[{"slug":"<kebab>","contract":"<one paragraph — what this curd must do>","files":["<path>", ...],"test_target":"<command or test id>","acceptance":["<verifiable check>", ...],"seed":["<frozen interface this curd implements>", ...]}, ...],"waves":[["<slug>", ...], ...],"decomposer":{"source":"cook","model":"opus","prompt_version":"${parentSlug}-v1"}}. Each slug must match ${SLUG_RE} and be unique; each wave has at most 4 slugs.

Before returning, self-validate: write the block to a temp JSON file, then validate it against the schema (repo-local first, deployed-bundle fallback — never trust your own judgment over this validator's output): if \`src/fanout/curd_block.py\` exists in this checkout, run \`PYTHONPATH=src:shared/scripts python3 src/fanout/curd_block.py < <tmpfile>\`; otherwise run \`python3 ~/.claude/skills/ultracook/scripts/ultracook.pyz curd-block < <tmpfile>\` (stdin only — do not pass a literal \`-\` or a path arg). Exit 0 with "OK: valid curd block" means valid; exit 1 prints one \`ERROR: <msg>\` line per violation on stderr plus a \`FAIL: N validation error(s)\` summary — strip the \`ERROR: \` prefix from each line (except the FAIL summary) into your validation_errors list. If it reports any errors, fix the block and re-run until it reports none.

Return {"curds":[...],"waves":[...],"decomposer":{...},"valid":true,"validation_errors":[]} — "valid" and "validation_errors" must reflect the actual output of that validator call, never an assumption.`
}

function validateCurdBlockPrompt(curdBlock) {
  return `You are a cheap validator agent for the /cheese-factory workflow. An upstream curd block was supplied as this run's args — do not regenerate, re-decompose, or merge it, only validate it.

Curd block:
${JSON.stringify(curdBlock)}

Write it to a temp JSON file, then validate it against the schema (repo-local first, deployed-bundle fallback — never trust your own judgment over this validator's output): if \`src/fanout/curd_block.py\` exists in this checkout, run \`PYTHONPATH=src:shared/scripts python3 src/fanout/curd_block.py < <tmpfile>\`; otherwise run \`python3 ~/.claude/skills/ultracook/scripts/ultracook.pyz curd-block < <tmpfile>\` (stdin only — do not pass a literal \`-\` or a path arg). Exit 0 with "OK: valid curd block" means valid; exit 1 prints one \`ERROR: <msg>\` line per violation on stderr plus a \`FAIL: N validation error(s)\` summary — strip the \`ERROR: \` prefix from each line (except the FAIL summary) into your validation_errors list, and do not attempt to fix it yourself.

If it reports any errors, return the block UNCHANGED with "valid":false and "validation_errors" set to that error list — do not attempt to fix it yourself. Otherwise return it unchanged with "valid":true,"validation_errors":[].

Return {"curds":<the supplied curds array, unchanged>,"waves":<the supplied waves array, unchanged>,"decomposer":<the supplied decomposer object, unchanged>,"valid":true|false,"validation_errors":[...]}.`
}

function miniSpecPrompt(parentSlug, curds) {
  return `You are a coder agent for the /cheese-factory workflow. Use Bash and your write tool.

For each curd below, resolve its mini-spec path with \`python3 ~/.claude/skills/mold/scripts/mold.pyz artifact-path specs ${parentSlug}--<slug>\` and write the mini-spec there using mold's agent-invoked mini-spec schema (see skills/mold/SKILL.md § Agent-invoked mini-spec mode), deriving the mini-spec content from the curd's contract, test_target, acceptance, and seed fields:

${JSON.stringify(curds.map((c) => ({ slug: c.slug, contract: c.contract, files: c.files, test_target: c.test_target, acceptance: c.acceptance, seed: c.seed })))}

Return {"curds":[{"slug":"<slug>","spec_path":"<resolved path>"}, ...]} — one entry per curd, in the same order.`
}

function isoContract(branch) {
  return `
## Isolation contract
- First command: \`git checkout -B ${branch} origin/main\` (or, if the worktree already exists on ${branch} from an earlier phase, just confirm you're on it — recreate with \`git worktree add <path> ${branch}\` if it was reaped).
- Work ONLY this curd's scope. Do NOT touch sibling curds' files. Do NOT push, open a PR, or merge — /cheese-factory's plate barrier handles publication after every curd chain finishes.
- Commit locally on ${branch} only, Conventional Commits, no flair/emojis.
`
}

function cookPrompt(curd) {
  const branch = branchFor(curd.slug)
  return `You are the Cook phase of the /cheese-factory pipeline for curd "${curd.slug}".
${isoContract(branch)}
Run \`/cook ${curd.spec_path} --auto\` via the Skill tool.

${NO_CHAIN_DIRECTIVE}

Report the resolved worktree path (\`git rev-parse --show-toplevel\`) and your /cook handoff slug fields. Return {"status":"...","artifact":"...","worktree_path":"...","orientation":"..."}.`
}

function cookContinuationPrompt(curd, prevCook, round) {
  const branch = branchFor(curd.slug)
  return `You are a FRESH Cook continuation (round ${round}/${COOK_CONTINUATIONS}) of the /cheese-factory pipeline for curd "${curd.slug}". A previous cook exhausted its context and stopped partway (its handoff: status "${prevCook.status}"${prevCook.orientation ? `, orientation "${prevCook.orientation}"` : ''}).

1. cd ${prevCook.worktree_path} — if that worktree was reaped, recreate it: \`git worktree add ${prevCook.worktree_path} ${branch}\`.
2. FIRST ACTION inside the worktree: preserve any partial work — \`git add -A && git commit -m "wip(${curd.slug}): partial cook (continuation seed)"\` (skip if the tree is clean).
3. Orient from what exists: \`git diff origin/main...${branch}\` plus the previous partial handoff${prevCook.artifact && isValidPath(prevCook.artifact) ? ` at ${prevCook.artifact}` : ''} — then resume \`/cook ${curd.spec_path} --auto\` via the Skill tool, completing ONLY the remaining acceptance criteria. Do not redo work already committed.

## Isolation contract (continuation)
- Do NOT run \`git checkout -B ${branch} origin/main\` — ${branch} carries the partial work.
- Work ONLY this curd's scope. Do NOT touch sibling curds' files. Do NOT push, open a PR, or merge.
- Commit locally on ${branch} only, Conventional Commits, no flair/emojis.

${NO_CHAIN_DIRECTIVE}

Report the resolved worktree path (\`git rev-parse --show-toplevel\`) and your /cook handoff slug fields. Return {"status":"...","artifact":"...","worktree_path":"...","orientation":"..."}.`
}

function tastePrompt(curd, branch) {
  return `You are a read-only opus reviewer running the Taste phase (5-lens gate) for curd "${curd.slug}".

Diff under review: \`git diff origin/main...${branch}\` (read-only — do not check out or edit anything).

## Lenses (judge each pass | revise)
- drift: the diff implements the curd's intent, not an adjacent or weaker thing.
- readability: minimal, clean, matches surrounding style.
- scope: only files traceable to the curd changed.
- production-path: reachable on the real code path, not just asserted in prose/tests.
- wired-callers: any changed signature/export has its callers updated.

Return {"verdict":"pass"|"revise","lenses":[{"lens":"...","verdict":"...","note":"..."}],"issues":["..."],"recommendation":"..."}. Overall verdict is revise if any lens is revise.`
}

function correctivePrompt(curd, worktreePath, branch, taste) {
  return `You are a coder applying a bounded corrective pass in worktree ${worktreePath} (already on ${branch}) for curd "${curd.slug}" after the Taste phase returned "revise".

Findings to fix:
${JSON.stringify({ issues: taste.issues, lenses: taste.lenses })}

Address ONLY these findings — no scope expansion. Commit on ${branch} (no push). Return {"status":"fixed"|"partial"|"blocked","summary":"...","committed":true|false}.`
}

function pressPrompt(curd, worktreePath) {
  return `You are the Press phase for curd "${curd.slug}". cd ${worktreePath} first.

Run \`/press ${curd.slug} --auto\` via the Skill tool.

${NO_CHAIN_DIRECTIVE}

Return {"status":"...","artifact":"...","orientation":"..."}.`
}

function mergeInstructions(refs) {
  return `Surviving curd branches (slug-sorted): ${JSON.stringify(refs)}

Merge each branch in the listed order: \`git merge --no-ff <branch>\` (the branches are local to this repo; fall back to \`origin/<branch>\` only if the local ref is missing). If a merge conflicts, run \`git merge --abort\`, record that entry's slug as conflicted, and continue with the remaining branches.`
}

function integratePrompt(parentSlug, refs) {
  return `You are the Integrate barrier for the /cheese-factory workflow. You are in an isolated worktree of the project repo (worktrees share the repo's branches).

1. \`git checkout -B integration/${parentSlug} origin/main\`.
2. ${mergeInstructions(refs)}
3. Report stats for the integrated diff by parsing \`git diff --shortstat origin/main...HEAD\`: files_changed, and lines_changed = insertions + deletions.

Do not push. Do not edit any file yourself. ${NO_CHAIN_DIRECTIVE}

Return {"worktree_path":"<git rev-parse --show-toplevel>","merged":["<slug>", ...],"conflicted":["<slug>", ...],"files_changed":<n>,"lines_changed":<n>}.`
}

function ageRoutePrompt(worktreePath) {
  return `You are a cheap routing-resolver agent for the /cheese-factory workflow's Age barrier. Use Bash. cd ${worktreePath} first.

1. Get diff stats: \`git diff --shortstat origin/main...HEAD\` for files_changed/insertions/deletions.
2. The hard-override risk-flag vocabulary is exactly: auth, secrets, crypto, tenant-isolation, payments, ledgers, irreversible-effects, concurrency, idempotency, ordering, retries, schema-migration, protocol-change, public-api-change, production-destructive, weak-integration-coverage. Judge which (if any) genuinely apply by reading \`git diff origin/main...HEAD\` — do not guess.
3. Call the router — the single source of truth for fan-out sizing, do not compute n/effort yourself (repo-local first, deployed-bundle fallback): if \`src/fanout/age_route_cli.py\` exists in this checkout, run \`echo '{"files_changed":<n>,"insertions":<n>,"deletions":<n>,"risk_flags":<your judged list>,"entry":"age"}' | PYTHONPATH=src:shared/scripts python3 src/fanout/age_route_cli.py\`; otherwise \`echo '{...same payload...}' | python3 ~/.claude/skills/age/scripts/age.pyz age-route\`, substituting the real numbers and your judged risk_flags list. Both print the route() JSON verbatim to stdout on exit 0.

Return the route() output verbatim: {"n":1|4|10,"lenses":[[...], ...],"effort":"medium"|"high","overrides_hit":[...],"rationale":"..."}.`
}

function ageBarrierPrompt(worktreePath, refs, label, priorFindings) {
  return `You are a read-only opus reviewer running the ${label} barrier of the /cheese-factory workflow. cd ${worktreePath} first (the integration branch merging the surviving curd branches).

${label === 'Re-age'
    ? `A cure pass just ran and the integration branch was re-merged. Re-review \`git diff origin/main...HEAD\` SCOPED to these previously reported findings (HEAD now includes the cure commits) and judge each resolved or still present:
${JSON.stringify(priorFindings)}`
    : `Run \`/age origin/main...HEAD --auto\` via the Skill tool over the whole integrated diff.`}

Curd branches in this integration: ${JSON.stringify(refs)}. Route every medium+ finding to the curd whose branch touched the file (curds are file-disjoint, so ownership is deterministic — use \`git log <branch> --name-only\` if unsure).

${NO_CHAIN_DIRECTIVE} In particular: do NOT invoke /cure yourself even if /age --auto documents that chain.

Return {"status":"ok","artifact":"<.cheese/age/... report path>","has_medium_plus_findings":true|false,"per_curd":[{"slug":"...","has_medium_plus_findings":true|false,"findings":[{"dimension":"...","severity":"blocker|high|medium|low","file":"...","line":<n>,"claim":"...","why_it_matters":"...","fix_direction":"..."}]}]} — one per_curd entry per curd branch, findings limited to medium+.`
}

function curePrompt(curd, branch, findings) {
  return `You are the Cure phase for curd "${curd.slug}".

cd into the curd worktree for branch ${branch}: if the Cook phase's worktree still exists (\`git worktree list\`), use it; otherwise recreate one with \`git worktree add <path> ${branch}\`. Do NOT re-checkout the branch from origin/main — it carries the cook/press commits.

Run \`/cure --auto --stake medium+\` via the Skill tool, giving it this routed finding list as its input (the /cure skill accepts a finding list directly):
${JSON.stringify(findings)}

Commit locally on ${branch}. Do not push. ${NO_CHAIN_DIRECTIVE}

Return {"status":"ok|partial|blocked","committed":true|false,"artifact":"..."}.`
}

function remergePrompt(parentSlug, worktreePath, refs) {
  return `You are the re-merge step of the Re-age barrier for the /cheese-factory workflow. cd ${worktreePath} first.

A cure pass added commits to some curd branches. Rebuild the integration branch: \`git checkout -B integration/${parentSlug} origin/main\`, then run the merge loop below.

${mergeInstructions(refs)}

${NO_CHAIN_DIRECTIVE}

Return {"worktree_path":"<git rev-parse --show-toplevel>","merged":[...],"conflicted":[...],"files_changed":<n>,"lines_changed":<n>} (stats from \`git diff --shortstat origin/main...HEAD\`).`
}

function platePrompt(cleanCurds, singlePass) {
  return `You are the Plate barrier for the /cheese-factory workflow. Run once, after every curd chain has finished.

Clean curd branches (slug-sorted): ${JSON.stringify(cleanCurds.map((c) => ({ slug: c.slug, branch: branchFor(c.slug) })))}

${singlePass
  ? 'Single-pass mode: run /plate for an ordinary single PR on the one branch above.'
  : 'Fan-out mode: run /plate to stack these branches into a stacked-PR chain in slug-sorted order, stating the order in the PR bodies.'}

Push and open/update PRs. NEVER merge.

Return {"results":[{"slug":"...","status":"...","pr_url":"..."}]}.`
}

// ---- Resolve ----
phase('Resolve')
const resolved = await agent(resolvePrompt(), { label: 'resolve', phase: 'Resolve', model: 'haiku', schema: RESOLVE_SCHEMA })

if (resolved.mode === 'missing') {
  log(`Spec not resolved: ${resolved.usage || 'spec not found'}`)
  return { error: resolved.usage || `Spec not found: ${SPEC_ARG}` }
}

if (resolved.mode === 'candidates') {
  const candidates = resolved.candidates || []
  log(`No spec given — ${candidates.length} candidate(s) found.`)
  return { candidates }
}

const parentSpecPath = resolved.spec_path
if (!isValidPath(parentSpecPath)) {
  log(`Invalid parent spec_path from resolver: ${parentSpecPath}`)
  return { error: `Invalid parent spec_path: ${parentSpecPath}` }
}
const parentSlug = resolved.curd_count && resolved.curd_count.slug ? resolved.curd_count.slug : 'spec'
if (!SLUG_RE.test(parentSlug)) {
  log(`Invalid parent slug from resolver: ${parentSlug}`)
  return { error: `Invalid parent slug: ${parentSlug}` }
}
const candidateCurds = resolved.curd_count ? resolved.curd_count.candidate_curds : 0

// ---- Decompose (only when candidate_curds >= 2, or an upstream curd block was supplied) ----
let curds
let singlePass = false

if (candidateCurds >= 2 || CURD_BLOCK_ARG) {
  phase('Decompose')
  const decomposed = CURD_BLOCK_ARG
    ? await agent(validateCurdBlockPrompt(CURD_BLOCK_ARG), { label: 'decompose:validate', phase: 'Decompose', model: 'haiku', schema: CURD_BLOCK_SCHEMA })
    : await agent(decomposePrompt(resolved.spec_text, parentSlug), { label: 'decompose:plan', phase: 'Decompose', agentType: 'coder', model: 'opus', schema: CURD_BLOCK_SCHEMA })

  if (!decomposed.valid) {
    const errs = (decomposed.validation_errors || []).join('; ')
    log(`Curd block failed schema validation: ${errs}`)
    return { error: `Invalid curd block: ${errs}` }
  }

  if (decomposed.curds.length < 2) {
    log(`Curd block has ${decomposed.curds.length} curd(s) — running single-pass against the parent spec.`)
    singlePass = true
    curds = [{ slug: parentSlug, spec_path: parentSpecPath, contract: null, files: [] }]
  } else {
    const invalidSlugs = findInvalidSlugs(decomposed.curds)
    if (invalidSlugs.length) {
      log(`Invalid curd slug(s) from decomposer: ${invalidSlugs.join(', ')}`)
      return { error: `Invalid curd slug(s): ${invalidSlugs.join(', ')}` }
    }
    const duplicateSlugs = findDuplicateSlugs(decomposed.curds)
    if (duplicateSlugs.length) {
      log(`Duplicate curd slug(s) from decomposer: ${duplicateSlugs.join(', ')}`)
      return { error: `Duplicate curd slug(s): ${duplicateSlugs.join(', ')}` }
    }

    const miniSpecs = await agent(miniSpecPrompt(parentSlug, decomposed.curds), { label: 'decompose:write-minispecs', phase: 'Decompose', agentType: 'coder', model: 'opus', schema: MINISPEC_SCHEMA })
    const pathBySlug = new Map(miniSpecs.curds.map((c) => [c.slug, c.spec_path]))
    const unresolvedSlugs = decomposed.curds.filter((c) => !pathBySlug.get(c.slug)).map((c) => c.slug)
    if (unresolvedSlugs.length) {
      log(`Mini-spec agent did not resolve a spec_path for curd slug(s): ${unresolvedSlugs.join(', ')}`)
      return { error: `Unresolved mini-spec path(s) for curd slug(s): ${unresolvedSlugs.join(', ')}` }
    }
    const invalidSpecPaths = decomposed.curds.filter((c) => !isValidPath(pathBySlug.get(c.slug))).map((c) => c.slug)
    if (invalidSpecPaths.length) {
      log(`Invalid spec_path from mini-spec agent for curd slug(s): ${invalidSpecPaths.join(', ')}`)
      return { error: `Invalid spec_path(s) for curd slug(s): ${invalidSpecPaths.join(', ')}` }
    }
    curds = decomposed.curds.map((c) => ({ ...c, spec_path: pathBySlug.get(c.slug) }))
  }
} else {
  singlePass = true
  curds = [{ slug: parentSlug, spec_path: parentSpecPath, contract: null, files: [] }]
}

// ---- Per-curd chain (pipelined) ----
phase('Cook')
log(`Running ${curds.length} curd chain(s)${singlePass ? ' (single-pass)' : ''}: ${curds.map((c) => c.slug).join(', ')}`)

const chainResults = await pipeline(
  curds,

  async (curd) => {
    const branch = branchFor(curd.slug)
    try {
      let cook = await agent(cookPrompt(curd), { label: `cook:${curd.slug}`, phase: 'Cook', agentType: 'coder', isolation: 'worktree', model: 'sonnet', schema: COOK_SCHEMA })
      let round = 0
      while (cook && typeof cook.status === 'string' && CONTINUABLE_COOK_RE.test(cook.status) && isValidPath(cook.worktree_path) && round < COOK_CONTINUATIONS) {
        round++
        log(`${curd.slug}: cook returned "${cook.status}" — dispatching fresh-coder continuation ${round}/${COOK_CONTINUATIONS}.`)
        cook = await agent(cookContinuationPrompt(curd, cook, round), { label: `cook:${curd.slug}:c${round}`, phase: 'Cook', agentType: 'coder', model: 'sonnet', schema: COOK_SCHEMA })
      }
      return { curd, branch, cook, failure: null }
    } catch (e) {
      log(`${curd.slug}: cook failed — ${e.message}; curd excluded downstream`)
      return { curd, branch, cook: null, failure: { stage: 'cook', message: e.message } }
    }
  },

  async ({ curd, branch, cook, failure }) => {
    if (failure) return { curd, branch, cook, taste: null, tasteRounds: 0, failure }
    if (!cook || cook.status !== 'ok' || !cook.worktree_path || !isValidPath(cook.worktree_path)) {
      const message = `cook did not reach status ok with a worktree_path (last status: ${cook ? cook.status : 'none'}) — ${branch} may carry committed WIP from continuation rounds`
      log(`${curd.slug}: cook failed — ${message}; curd excluded downstream`)
      return { curd, branch, cook, taste: null, tasteRounds: 0, failure: { stage: 'cook', message } }
    }
    let taste
    try {
      taste = await agent(tastePrompt(curd, branch), { label: `taste:${curd.slug}`, phase: 'Taste', agentType: 'reviewer', model: 'opus', schema: TASTE_SCHEMA })
    } catch (e) {
      log(`${curd.slug}: taste failed — ${e.message}; curd excluded downstream`)
      return { curd, branch, cook, taste: null, tasteRounds: 0, failure: { stage: 'taste', message: e.message } }
    }
    let round = 0
    while (taste.verdict === 'revise' && round < CORRECTIVE_ROUNDS) {
      let correction
      try {
        correction = await agent(correctivePrompt(curd, cook.worktree_path, branch, taste), { label: `correct:${curd.slug}:r${round + 1}`, phase: 'Taste', agentType: 'coder', model: 'sonnet', schema: CORRECT_SCHEMA })
      } catch (e) {
        log(`${curd.slug}: taste-correct failed — ${e.message}; curd excluded downstream`)
        return { curd, branch, cook, taste, tasteRounds: round, failure: { stage: 'taste-correct', message: e.message } }
      }
      round++
      if (!correction.committed) {
        log(`${curd.slug}: corrective round ${round} produced an uncommitted correction — stopping the taste loop.`)
        break
      }
      try {
        taste = await agent(tastePrompt(curd, branch), { label: `taste:${curd.slug}:r${round}`, phase: 'Taste', agentType: 'reviewer', model: 'opus', schema: TASTE_SCHEMA })
      } catch (e) {
        log(`${curd.slug}: taste failed — ${e.message}; curd excluded downstream`)
        return { curd, branch, cook, taste, tasteRounds: round, failure: { stage: 'taste', message: e.message } }
      }
    }
    return { curd, branch, cook, taste, tasteRounds: round, failure: null }
  },

  async ({ curd, branch, cook, taste, tasteRounds, failure }) => {
    if (!failure && (!taste || taste.verdict === 'revise')) {
      failure = { stage: 'taste', message: 'taste did not reach pass within correctiveRounds' }
      log(`${curd.slug}: ${failure.stage} failed — ${failure.message}; curd excluded downstream`)
    }
    if (failure) return { curd, branch, cook, taste, tasteRounds, press: null, failure }
    let press
    try {
      press = await agent(pressPrompt(curd, cook.worktree_path), { label: `press:${curd.slug}`, phase: 'Press', agentType: 'coder', model: 'sonnet', schema: PHASE_SCHEMA })
    } catch (e) {
      log(`${curd.slug}: press failed — ${e.message}; curd excluded downstream`)
      return { curd, branch, cook, taste, tasteRounds, press: null, failure: { stage: 'press', message: e.message } }
    }
    return { curd, branch, cook, taste, tasteRounds, press, failure: null }
  },
)

// ---- Integrate (barrier — merge surviving branches into one integration worktree) ----
const surviving = chainResults.filter((r) => r && !r.failure)

let integrate = null
let integratedRefs = []
if (surviving.length) {
  phase('Integrate')
  const refs = surviving
    .map((r) => ({ slug: r.curd.slug, branch: r.branch }))
    .sort((a, b) => (a.slug < b.slug ? -1 : 1))
  try {
    integrate = await agent(integratePrompt(parentSlug, refs), { label: 'integrate', phase: 'Integrate', agentType: 'coder', model: 'sonnet', isolation: 'worktree', schema: INTEGRATE_SCHEMA })
  } catch (e) {
    log(`Integrate failed (${e.message}) — all surviving curds excluded.`)
  }

  if (integrate && !isValidPath(integrate.worktree_path)) {
    log(`Integrate returned an invalid worktree_path: ${integrate.worktree_path}`)
    integrate = null
  }
  if (integrate) {
    const conflicted = new Set(integrate.conflicted || [])
    integratedRefs = refs.filter((r) => !conflicted.has(r.slug))
    if (conflicted.size) log(`Integration conflicts excluded curd(s): ${[...conflicted].join(', ')}`)
  }
}

// ---- Age (barrier — whole integrated diff; sizing comes from src/fanout/age_route.py) ----
let ageResult = null
let ageMode = null
if (integrate && integratedRefs.length) {
  phase('Age')
  let route = null
  try {
    route = await agent(ageRoutePrompt(integrate.worktree_path), { label: 'age:route', phase: 'Age', model: 'haiku', schema: AGE_ROUTE_SCHEMA })
  } catch (e) {
    log(`Age routing agent failed (${e.message}) — falling back to a single-reviewer barrier age.`)
  }

  if (route && route.n > 1) {
    try {
      const fan = await workflow('age-fanout', { worktree_path: integrate.worktree_path, range: 'origin/main...HEAD', slug: parentSlug, route_curds: integratedRefs, n: route.n, lenses: route.lenses, effort: route.effort })
      if (!fan || fan.status !== 'ok') throw new Error((fan && fan.error) || 'age-fanout returned non-ok')
      ageResult = fan
      ageMode = 'fanout'
      if (fan.workers_lost > 0) log(`age-fanout lost ${fan.workers_lost}/${fan.workers_total} review worker(s) — coverage degraded.`)
    } catch (e) {
      log(`age-fanout unavailable (${e.message}) — falling back to a single-reviewer barrier age.`)
    }
  }
  if (!ageResult) {
    try {
      ageResult = await agent(ageBarrierPrompt(integrate.worktree_path, integratedRefs, 'Age', null), { label: 'age:barrier', phase: 'Age', agentType: 'reviewer', model: 'opus', schema: AGE_BARRIER_SCHEMA, ...(route && route.effort ? { effort: route.effort } : {}) })
      ageMode = 'single'
    } catch (e) {
      log(`Barrier age failed (${e.message}) — integrated curds cannot be verified; excluding them from plate.`)
    }
  }
}

// ---- Cure (parallel — only curds with medium+ routed findings) ----
let toCure = []
let cureBySlug = new Map()
let lostCureSlug = new Set()
if (ageResult && ageResult.has_medium_plus_findings) {
  phase('Cure')
  toCure = (ageResult.per_curd || []).filter((p) => p && p.has_medium_plus_findings && integratedRefs.some((r) => r.slug === p.slug))
  const cures = await parallel(toCure.map((p) => () => {
    const ref = integratedRefs.find((r) => r.slug === p.slug)
    const entry = surviving.find((r) => r.curd.slug === p.slug)
    return agent(curePrompt(entry.curd, ref.branch, p.findings || []), { label: `cure:${p.slug}`, phase: 'Cure', agentType: 'coder', model: 'sonnet', schema: CURE_SCHEMA })
      .then((cure) => ({ slug: p.slug, cure }))
  }))
  cureBySlug = new Map(cures.filter(Boolean).map((c) => [c.slug, c.cure]))
  lostCureSlug = new Set(toCure.map((p) => p.slug).filter((slug) => !cureBySlug.has(slug)))
  if (lostCureSlug.size) log(`${lostCureSlug.size} of ${toCure.length} cure worker(s) lost: ${[...lostCureSlug].join(', ')}`)
}

// ---- Re-age (once — only if a cure committed) ----
let remerge = null
let reage = null
if ([...cureBySlug.values()].some((c) => c && c.committed)) {
  phase('Re-age')
  try {
    remerge = await agent(remergePrompt(parentSlug, integrate.worktree_path, integratedRefs), { label: 're-merge', phase: 'Re-age', model: 'haiku', schema: INTEGRATE_SCHEMA })
  } catch (e) {
    log(`Re-merge failed (${e.message}) — cured curds stay dirty.`)
  }
  if (remerge) {
    try {
      reage = await agent(ageBarrierPrompt(integrate.worktree_path, integratedRefs, 'Re-age', toCure.flatMap((p) => p.findings || [])), { label: 'age:reage', phase: 'Re-age', agentType: 'reviewer', model: 'opus', schema: AGE_BARRIER_SCHEMA })
    } catch (e) {
      log(`Re-age failed (${e.message}) — cured curds stay dirty.`)
    }
  }
}

// ---- Status resolution ----
const agePerCurdBySlug = new Map(((ageResult && ageResult.per_curd) || []).map((p) => [p.slug, p]))
const reageBySlug = new Map(((reage && reage.per_curd) || []).map((p) => [p.slug, p]))
const remergeConflicted = new Set((remerge && remerge.conflicted) || [])
const unroutedFindings = Boolean(ageResult && ageResult.has_medium_plus_findings && agePerCurdBySlug.size === 0)
if (unroutedFindings) log('Barrier age reported medium+ findings but no per-curd routing — integrated curds marked dirty.')
const reageUnrouted = Boolean(reage && reage.has_medium_plus_findings && reageBySlug.size === 0)
if (reageUnrouted) log('Re-age reported medium+ findings but no per-curd routing — cured curds marked dirty.')

const withStatus = chainResults.map((r) => {
  if (!r) return null
  const { curd, branch, failure } = r
  if (failure) return { curd, branch, status: 'failed', excluded_reason: `${failure.stage}: ${failure.message}` }
  if (!integrate) return { curd, branch, status: 'failed', excluded_reason: 'integrate: barrier integration failed' }
  if (!integratedRefs.some((ref) => ref.slug === curd.slug)) return { curd, branch, status: 'failed', excluded_reason: 'integrate: merge conflict' }
  if (!ageResult) return { curd, branch, status: 'failed', excluded_reason: 'age: barrier age failed' }
  if (unroutedFindings) return { curd, branch, status: 'dirty', excluded_reason: 'age reported medium+ findings without per-curd routing' }
  const p = agePerCurdBySlug.get(curd.slug)
  if (!p) {
    if (ageResult.has_medium_plus_findings) return { curd, branch, status: 'dirty', excluded_reason: 'missing from age per_curd despite barrier-level medium+ findings' }
    return { curd, branch, status: 'clean' }
  }
  if (!p.has_medium_plus_findings) return { curd, branch, status: 'clean' }
  const cure = cureBySlug.get(curd.slug)
  if (!cure || !cure.committed) return { curd, branch, status: 'dirty', excluded_reason: lostCureSlug.has(curd.slug) ? 'cure worker lost' : 'cure did not commit a fix' }
  if (remergeConflicted.has(curd.slug)) return { curd, branch, status: 'dirty', excluded_reason: 're-merge conflicted after cure' }
  if (!reage) return { curd, branch, status: 'dirty', excluded_reason: 're-age did not run after cure' }
  if (reageUnrouted) return { curd, branch, status: 'dirty', excluded_reason: 're-age reported medium+ findings without per-curd routing' }
  const rp = reageBySlug.get(curd.slug)
  if (!rp) {
    if (reage.has_medium_plus_findings) return { curd, branch, status: 'dirty', excluded_reason: 'missing from re-age per_curd despite barrier-level medium+ findings' }
    return { curd, branch, status: 'clean' }
  }
  if (rp.has_medium_plus_findings) return { curd, branch, status: 'dirty', excluded_reason: 're-age still reports medium+ findings' }
  return { curd, branch, status: 'clean' }
})

const cleanEntries = withStatus.filter((r) => r && r.status === 'clean')

phase('Plate')
let plateBySlug = new Map()
if (cleanEntries.length) {
  const plated = await agent(platePrompt(cleanEntries.map((r) => r.curd), singlePass), { label: 'plate', phase: 'Plate', agentType: 'coder', model: 'opus', schema: PLATE_SCHEMA })
  plateBySlug = new Map(plated.results.map((r) => [r.slug, r]))
} else {
  log('No clean curds — skipping plate.')
}

// ---- Report ----
phase('Report')
const curdsOut = withStatus.map((r) => {
  if (!r) return null
  const plate = plateBySlug.get(r.curd.slug)
  const p = agePerCurdBySlug.get(r.curd.slug)
  return {
    slug: r.curd.slug,
    branch: r.branch,
    status: r.status,
    pr_url: plate ? plate.pr_url : undefined,
    excluded_reason: r.excluded_reason,
    age: ageMode ? { mode: ageMode, has_medium_plus_findings: Boolean(p && p.has_medium_plus_findings) } : undefined,
  }
})

const summary = { clean: 0, dirty: 0, failed: 0 }
for (const c of curdsOut) if (c) summary[c.status] = (summary[c.status] || 0) + 1
log(`Report: ${curdsOut.length} curd(s) — clean:${summary.clean} dirty:${summary.dirty} failed:${summary.failed}`)

return {
  curds: curdsOut,
  summary,
  integration: integrate ? { merged: integrate.merged, conflicted: integrate.conflicted } : null,
}
