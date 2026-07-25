export const meta = {
  name: 'age-fanout',
  description:
    "Shared child workflow implementing /age's scale-triggered fan-out (Seams 2-4: Packet, Review, Reconcile) for parent workflows (cheese-factory, move-my-cheese) via workflow('age-fanout', args). Zero copied review semantics -- agent prompts point at the deployed skill files, which agents read at runtime.",
  phases: [
    { title: 'Packet', detail: 'one explorer agent assembles the shared review packet per references/packet.md and parses the dimension list off dimensions.md headings' },
    { title: 'Review', detail: 'one opus reviewer per lens group -- caller-supplied groups (src/fanout/age_route.py sizing), or one dimension per group as the degraded default -- fanned out in parallel, each reading only its group\'s dimension rubrics and reviewing the diff read-only' },
    { title: 'Reconcile', detail: 'one opus reviewer applies the dimension-boundaries table, dedups, writes the findings report, and (when route_curds given) attributes findings per curd branch' },
  ],
}

// Tracked source: workflows/age-fanout.js in the easy-cheese repo (ported
// from the dotfiles-deployed claude/workflows/age-fanout.js). Shared child
// workflow implementing /age's scale-triggered fan-out (Seams 2-4) for
// parent workflows (cheese-factory, move-my-cheese) via
// workflow('age-fanout', args). Zero copied review semantics: every agent
// prompt below POINTS at the deployed skill files
// (~/.claude/skills/age/SKILL.md, references/dimensions.md,
// references/packet.md), which the dispatched agents read at runtime rather
// than this workflow duplicating rubric or output-format text.
//
// Args: { worktree_path: string, range: string, slug: string, route_curds?:
//   [{slug, branch}], n?: 1|4|10, lenses?: [[dim, ...], ...], effort?:
//   'medium'|'high' } -- worktree_path, range, and slug are required and
//   validated before any agent() call; invalid args return
//   { status: 'blocked', error } with zero agents dispatched. route_curds is
//   optional and, when present, is forwarded to Reconcile so it can
//   attribute findings per curd branch. n/lenses/effort come from
//   src/fanout/age_route.py's routing decision (the caller resolves that,
//   this workflow only consumes it): when lenses is supplied, the Review
//   phase fans out one reviewer per caller-supplied lens group instead of
//   unconditionally one-per-dimension; when absent, the degraded default is
//   one dimension per group (the prior behavior). effort, when supplied, is
//   forwarded into each Review agent() call; reviewer model pin stays
//   hardcoded 'opus' regardless of effort (spec: "reviewer model pins in the
//   migrated scripts stay opus").
//
// Return: { status: 'ok'|'blocked', artifact, has_medium_plus_findings,
//   dimensions: [...], per_curd: route_curds ? (reconcile.per_curd || []) :
//   null, error? }

const NO_CHAIN_DIRECTIVE = 'Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. The parent workflow orchestrating /age-fanout is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with status: halt: <reason> and stop; do not silently timeout.'

const input = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { log(`args was a string but not valid JSON (${e.message})`); return {} } })() : args || {}

// SLUG_RE / SAFE_REF_RE match cheese-factory.js / move-my-cheese.js verbatim.
const SLUG_RE = /^[a-z0-9][a-z0-9._-]*$/
const SAFE_REF_RE = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/
// SAFE_REF_RE extended to allow one ".." or "..." range separator: a diff
// range like "origin/main...HEAD" is otherwise indistinguishable from the
// ref-shape SAFE_REF_RE already accepts (dots are legal ref characters), so
// this is the same char class without move-my-cheese's extra `..` exclusion.
const RANGE_RE = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/
const PATH_RE = /^[A-Za-z0-9._/-]+$/
// Verbatim slug of a `### heading` in ~/.claude/skills/age/references/dimensions.md's
// "## Per-dimension rubrics" section (e.g. "correctness", "deslop") -- the
// packet phase must return exactly these, byte-matched, so the Review
// phase's `### ${dim}` heading lookup resolves.
const DIM_SLUG_PATTERN = '^[a-z][a-z-]*$'
const DIM_SLUG_RE = new RegExp(DIM_SLUG_PATTERN)
const VALID_N = new Set([1, 4, 10])
const VALID_EFFORT = new Set(['medium', 'high'])

const isValidPath = (p) => typeof p === 'string' && PATH_RE.test(p)
const isValidRange = (r) => typeof r === 'string' && RANGE_RE.test(r)
const isValidSlug = (s) => typeof s === 'string' && SLUG_RE.test(s)
const isValidRef = (r) => typeof r === 'string' && SAFE_REF_RE.test(r)
const isValidRouteCurds = (rc) => {
  if (rc === undefined) return true
  if (!Array.isArray(rc)) return false
  return rc.every((c) => c && typeof c === 'object' && isValidSlug(c.slug) && isValidRef(c.branch))
}
const isValidN = (n) => n === undefined || VALID_N.has(n)
const isValidEffort = (e) => e === undefined || VALID_EFFORT.has(e)
const isValidLenses = (l) => {
  if (l === undefined) return true
  if (!Array.isArray(l) || l.length === 0) return false
  return l.every((group) => Array.isArray(group) && group.length > 0 && group.every((d) => typeof d === 'string' && DIM_SLUG_RE.test(d)))
}

const errors = []
if (!isValidPath(input.worktree_path)) errors.push('worktree_path missing or contains invalid characters')
if (!isValidRange(input.range)) errors.push('range missing or invalid')
if (!isValidSlug(input.slug)) errors.push('slug missing or invalid')
if (!isValidRouteCurds(input.route_curds)) errors.push('route_curds malformed')
if (!isValidN(input.n)) errors.push('n must be 1, 4, or 10 when supplied')
if (!isValidEffort(input.effort)) errors.push("effort must be 'medium' or 'high' when supplied")
if (!isValidLenses(input.lenses)) errors.push('lenses must be a non-empty array of non-empty dimension-slug arrays when supplied')
if (errors.length) {
  log(`Invalid args: ${errors.join('; ')}`)
  return { status: 'blocked', error: errors.join('; ') }
}

const WORKTREE_PATH = input.worktree_path
const RANGE = input.range
const SLUG = input.slug
const ROUTE_CURDS = input.route_curds || null
const CALLER_LENSES = input.lenses || null
const CALLER_EFFORT = input.effort || null

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
const PACKET_SCHEMA = {
  type: 'object',
  required: ['skill_files_ok', 'dimensions', 'packet_path'],
  properties: {
    skill_files_ok: { type: 'boolean' },
    blocked_reason: { type: 'string' },
    dimensions: { type: 'array', items: { type: 'string', pattern: DIM_SLUG_PATTERN } },
    packet_path: { type: 'string' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        ...FINDING_ITEM_SCHEMA,
        properties: { ...FINDING_ITEM_SCHEMA.properties, also_relevant_to: { type: 'array', items: { type: 'string' } } },
      },
    },
  },
}

const RECONCILE_SCHEMA = {
  type: 'object',
  required: ['has_medium_plus_findings', 'artifact'],
  properties: {
    has_medium_plus_findings: { type: 'boolean' },
    artifact: { type: 'string' },
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

// ---- prompts ----
function packetPrompt(worktreePath, range, slug) {
  // Explorer agents carry Bash, so the packet is assembled and written via
  // shell redirection rather than a write tool.
  return `You are the Packet phase for /age-fanout. Use Bash.

cd ${worktreePath} first.

First verify these files exist and are readable: \`~/.claude/skills/age/SKILL.md\`, \`~/.claude/skills/age/references/dimensions.md\`, \`~/.claude/skills/age/references/packet.md\`. If any is missing or unreadable, stop here and return {"skill_files_ok":false,"blocked_reason":"<which file, and why>","dimensions":[],"packet_path":""} -- do not guess a dimension list or improvise a packet from memory.

Assemble the shared context packet per \`~/.claude/skills/age/references/packet.md\` for the diff range \`${range}\`, and write it to \`.cheese/age/${slug}-packet.md\` (via Bash redirection).

Then parse the dimension list from \`~/.claude/skills/age/references/dimensions.md\`: find its \`## Per-dimension rubrics\` section and list exactly the \`###\` heading text beneath it, verbatim and lowercase, one entry per heading -- do not invent, rename, expand, or title-case any heading. These strings feed directly into a \`### <dim>\` heading lookup in the Review phase, so they must byte-match the heading text exactly. If that section is absent or its headings don't parse cleanly, return {"skill_files_ok":false,"blocked_reason":"<what went wrong>","dimensions":[],"packet_path":""} instead of guessing.

Return {"skill_files_ok":true,"dimensions":["<dim>", ...],"packet_path":".cheese/age/${slug}-packet.md"}.`
}

function reviewPrompt(group, worktreePath, range, packetPath) {
  const dimList = group.join(', ')
  const headingList = group.map((d) => `\`### ${d}\``).join(', ')
  return `You are a read-only reviewer for dimension${group.length > 1 ? 's' : ''} ${dimList} in the /age-fanout Review phase. Use Bash for read-only inspection only — do not edit, commit, or push anything.

cd ${worktreePath} first.

Read the packet at ${packetPath}, and read ONLY the ${headingList} section${group.length > 1 ? 's' : ''} of \`~/.claude/skills/age/references/dimensions.md\` (each \`### <dim>\` heading through its next heading). If "deslop" is among ${dimList}, also read the matching de-slop language reference for every language present in the diff.

Review only \`git diff ${range}\`. For each finding, tag it with whichever of ${dimList} it belongs to and compute its full severity per that dimension's rubric you just read — base tier, then the location bump and compounding bump described in dimensions.md's severity-computation section, capped at blocker. Tag \`also_relevant_to\` with any other dimension (in or out of this group) a finding also touches, per that dimension's own rubric. Do NOT dedup against other workers' findings — the orchestrator reconciles those. Do NOT invoke any Skill tool (no /age, no /cure, no other skill) — read the referenced files directly and review from first principles.

${NO_CHAIN_DIRECTIVE}

Return {"findings":[{"dimension":"<one of ${dimList}>","severity":"blocker|high|medium|low","file":"<path>","line":<int>,"claim":"<what's wrong>","why_it_matters":"<impact>","fix_direction":"<how to fix>","also_relevant_to":["<dim>", ...]}]}.`
}

function reconcilePrompt(worktreePath, slug, findings, routeCurds, packetPath, range) {
  return `You are the Reconcile phase for /age-fanout, curd "${slug}". cd ${worktreePath} first.

Context packet: ${packetPath}. Diff range reviewed: \`${range}\`.

Worker findings (JSON, not yet deduped):
${JSON.stringify(findings)}

Apply the "§ Dimension boundaries" table (verbatim) from \`~/.claude/skills/age/references/dimensions.md\` to (a) any file:line flagged by 2 or more workers, and (b) every \`also_relevant_to\` tag. Dedup findings describing the same defect. Write the findings report to \`.cheese/age/${slug}.md\` in the format described in \`~/.claude/skills/age/SKILL.md § Output\`, including the handoff slug at the top per that section's template — read it there rather than assuming the shape. Ground the report's Orientation and Confidence sections in the context packet and the diff range above.

${routeCurds ? `This review spans multiple curd branches. Determine per-finding ownership by running \`git log <branch> --name-only\` for each of these branches and matching each finding's file to the branch that touched it:
${JSON.stringify(routeCurds)}

Return a "per_curd" array: one entry per curd with its slug, whether it has any medium-or-above finding, and the full deduped finding objects attributed to it (same field shape as the worker findings, minus also_relevant_to) — downstream cure agents consume these objects, so keep file/line/fix_direction intact.` : ''}

Return {"has_medium_plus_findings":true|false,"artifact":".cheese/age/${slug}.md"${routeCurds ? ',"per_curd":[{"slug":"...","has_medium_plus_findings":true|false,"findings":[{"dimension":"...","severity":"...","file":"...","line":<int>,"claim":"...","why_it_matters":"...","fix_direction":"..."}]}]' : ''}}.`
}

// ---- Packet ----
phase('Packet')
let packet
try {
  packet = await agent(packetPrompt(WORKTREE_PATH, RANGE, SLUG), { label: 'packet', phase: 'Packet', agentType: 'explorer', model: 'sonnet', schema: PACKET_SCHEMA })
} catch (e) {
  log(`Packet phase failed: ${e.message}`)
  return { status: 'blocked', error: `packet phase failed: ${e.message}` }
}

if (!packet.skill_files_ok) {
  log(`Packet phase reported the age skill file contract is broken: ${packet.blocked_reason || 'unspecified'}`)
  return { status: 'blocked', error: packet.blocked_reason || 'age skill files missing or unreadable' }
}

if (!isValidPath(packet.packet_path)) {
  log('Packet phase returned a packet_path missing or containing invalid characters.')
  return { status: 'blocked', error: 'packet_path missing or contains invalid characters' }
}

if (!Array.isArray(packet.dimensions) || packet.dimensions.length === 0) {
  log('Packet phase returned no dimensions.')
  return { status: 'blocked', error: 'packet phase returned no dimensions' }
}

// Authoritative in-script guard, kept alongside the schema `pattern` above: some agent-runtime schema validators silently ignore `pattern`, so this check enforces the slug shape regardless of what the runtime validated.
const invalidDimensions = packet.dimensions.filter((d) => !DIM_SLUG_RE.test(d))
if (invalidDimensions.length) {
  log(`Packet phase returned non-slug dimension(s): ${invalidDimensions.join(', ')}`)
  return { status: 'blocked', error: `invalid dimension slug(s): ${invalidDimensions.join(', ')}` }
}

const dimensions = packet.dimensions

// ---- Review (fanned out, one worker per lens group) ----
// A lens group is an array of dimension slugs reviewed together by one
// worker. The caller (age_route.py's routing decision) may supply grouped
// lenses sized for the diff (n=1/4/10); absent that, the degraded default
// is one dimension per group -- the prior unconditional per-dimension
// behavior.
phase('Review')
const lensGroups = CALLER_LENSES || dimensions.map((d) => [d])
const reviewResults = await parallel(
  lensGroups.map((group) => () => agent(
    reviewPrompt(group, WORKTREE_PATH, RANGE, packet.packet_path),
    {
      label: `review:${group.join('+')}`,
      phase: 'Review',
      agentType: 'reviewer',
      model: 'opus',
      schema: REVIEW_SCHEMA,
      ...(CALLER_EFFORT ? { effort: CALLER_EFFORT } : {}),
    },
  )),
)

const lostCount = reviewResults.filter((r) => r == null).length
if (lostCount) log(`${lostCount} of ${lensGroups.length} review worker(s) lost (thrown or invalid response).`)

const survivors = reviewResults.filter(Boolean)
if (survivors.length === 0) {
  log('All review workers lost — cannot reconcile.')
  return { status: 'blocked', error: 'all review workers lost' }
}

const allFindings = survivors.flatMap((r) => r.findings || [])

// ---- Reconcile ----
phase('Reconcile')
let reconcile
try {
  reconcile = await agent(reconcilePrompt(WORKTREE_PATH, SLUG, allFindings, ROUTE_CURDS, packet.packet_path, RANGE), { label: 'reconcile', phase: 'Reconcile', agentType: 'reviewer', model: 'opus', schema: RECONCILE_SCHEMA })
} catch (e) {
  log(`Reconcile phase failed: ${e.message}`)
  return { status: 'blocked', error: `reconcile phase failed: ${e.message}` }
}

return {
  status: 'ok',
  artifact: reconcile.artifact,
  has_medium_plus_findings: reconcile.has_medium_plus_findings,
  dimensions,
  per_curd: ROUTE_CURDS ? (reconcile.per_curd || []) : null,
  workers_lost: lostCount,
  workers_total: lensGroups.length,
}
