// affinage-fanout — run safe-mode /affinage across many open PRs in parallel,
// then synthesize a cross-PR fold/supersession map.
//
// Each PR is triaged independently (review comments + CI failures + merge state,
// plus a fresh inline /age pass) and a report is written to
// .cheese/affinage/pr-<n>.md with drafted replies. SAFE mode only: nothing is
// posted, cured, melted, committed, or pushed — the workflow produces reports
// and a supersession analysis for a human to act on.
//
// Usage:
//   Workflow({ name: 'affinage-fanout', args: { prs: [74, 108, 133] } })
//   Workflow({ name: 'affinage-fanout', args: [74, 108, 133] })   // shorthand
//
// Owner/repo is auto-detected by gh (the {owner}/{repo} placeholders and bare
// `gh pr` commands resolve against the current repo), so this workflow is
// portable across repos that ship skills/affinage/scripts/affinage.pyz.

export const meta = {
  name: 'affinage-fanout',
  description: 'Safe-mode /affinage across many open PRs (report+draft only) + cross-PR supersession analysis',
  phases: [
    { title: 'Affinage', detail: 'safe-mode triage per PR: comments + CI + fresh /age, write report' },
    { title: 'Supersede', detail: 'cross-PR fold/supersession map with keep/close recs' },
  ],
}

const PRS = (Array.isArray(args) ? args : (args && Array.isArray(args.prs) ? args.prs : []))
  .map(Number)
  .filter((n) => Number.isInteger(n) && n > 0)

if (PRS.length === 0) {
  throw new Error('affinage-fanout: pass PR numbers via args, e.g. { prs: [74, 108] } or [74, 108]')
}

const AFFINAGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    pr: { type: 'number' },
    title: { type: 'string' },
    intent: { type: 'string', description: 'one sentence: what the PR does' },
    filesTouched: { type: 'array', items: { type: 'string' } },
    buildStatus: { type: 'string' },
    mergeStatus: { type: 'string' },
    commentsTriaged: { type: 'number' },
    commentsSkipped: { type: 'number' },
    freshAgeFindings: { type: 'number' },
    counts: {
      type: 'object',
      additionalProperties: false,
      properties: {
        blocker: { type: 'number' },
        high: { type: 'number' },
        medium: { type: 'number' },
        low: { type: 'number' },
        needsInvestigation: { type: 'number' },
        reviewerRejected: { type: 'number' },
      },
      required: ['blocker', 'high', 'medium', 'low', 'needsInvestigation', 'reviewerRejected'],
    },
    topFindings: { type: 'array', items: { type: 'string' }, description: '<=6 one-line findings with severity+source tags' },
    recommendedCure: { type: 'string', description: 'the recommended composite (mediums+ plus cheap lows) and how many findings it covers' },
    draftReplies: { type: 'number' },
    themes: { type: 'array', items: { type: 'string' }, description: '2-5 short keywords for cross-PR overlap detection' },
    reportPath: { type: 'string' },
    status: { type: 'string', description: 'ok | halt: <reason>' },
  },
  required: ['pr', 'intent', 'counts', 'recommendedCure', 'themes', 'reportPath', 'status'],
}

const SUPERSEDE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    clusters: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          theme: { type: 'string' },
          prs: { type: 'array', items: { type: 'number' } },
          relationship: { type: 'string', enum: ['independent', 'overlap', 'supersedes'] },
          supersededBy: { type: 'number', description: 'PR number that supersedes the others in this cluster, or 0 if none' },
          recommendation: { type: 'string', description: 'keep/close which PR(s) and why' },
          valueToExtract: { type: 'string', description: 'unique value (files/findings/tests) to port before closing a superseded PR' },
        },
        required: ['theme', 'prs', 'relationship', 'recommendation'],
      },
    },
    independentPRs: { type: 'array', items: { type: 'number' } },
    summary: { type: 'string' },
  },
  required: ['clusters', 'summary'],
}

const reportTemplate = (pr) => `\`\`\`
status: ok | halt: <reason>
next: cure | done
artifact:
<one-line orientation: what PR #${pr} does and what was graded>
\`\`\`

# Affinage Report — PR #${pr}

## Orientation
<one or two factual sentences>

## PR status
- Build: passing | failing (N jobs)
- Merge: clean | conflicts (route to /melt — human)
- Comments: K triaged (M skipped as outdated/already-replied)
- Fresh review: ran inline /age (N findings)

## Blocker / ## High / ## Medium / ## Low   (omit empty sections)
- **[from-comment:<id>] [<dim>:<sev>]** <reviewer> on \`<file>:<line>\` — <claim>.
  - location: <contract|class|hot path> · fix-cost-now: <contained|moderate|sprawling> · fix-cost-later: <contained|structural>
  - reviewer-asserted: <changes-requested|none>
  - recommendation: <what to do>

## Needs-investigation
- **[from-comment:<id>]** <reviewer> on \`<file>:<line>\` — <claim>.
  - reason: <why evidence is outside the diff>
  - suggested action: <what a human checks>

## Reviewer-rejected
- **[from-comment:<id>]** <reviewer> on \`<file>:<line>\` — <claim>.
  - reason: <wrong/ungrounded, or valid-but-large>
  - draft reply: "<push-back text — NOT posted in safe mode>"

## Confidence
<certain | speculating | don't know> — <one-line justification>

## Next step
Safe mode: report written, replies drafted but NOT posted. Recommended cure selection if the user proceeds: <composite>.`

const affinagePrompt = (pr) => `You are running \`/affinage\` in **--safe mode** on PR #${pr} of the current GitHub repo. Working directory is the repo root. This is SAFE: you must NOT post any GitHub comment, NOT run /cure or /melt or any fix, NOT checkout/commit/push. Your ONLY write is the report file \`.cheese/affinage/pr-${pr}.md\`. Do ALL reasoning in this context — do NOT spawn sub-agents.

GOAL: triage every external claim on this PR (inline review comments, review-body comments, CI failures, merge conflicts) through the /age review lens, PLUS run a fresh inline /age-style review of the PR diff, and produce a graded report + drafted replies.

STEP 1 — PR status. Run: \`python3 skills/affinage/scripts/affinage.pyz pr-status ${pr}\` (fall back to \`gh pr checks ${pr}\` + \`gh pr view ${pr} --json mergeable,mergeStateStatus\` if the helper is absent). Parse: build.status, each failing check (failure_summary, failed_tests) → finding tagged [from-check:<job>]; merge.mergeable / merge.state. If CONFLICTING or DIRTY: in safe mode DO NOT resolve — record "Merge: conflicts (route to /melt — human)" and note it; do not checkout.

STEP 2 — Read the PR (no checkout): \`gh pr diff ${pr}\` and \`gh pr view ${pr} --json title,body,files,headRefName,additions,deletions\`.

STEP 3 — Fetch comments:
- Inline: \`gh api repos/{owner}/{repo}/pulls/${pr}/comments\` — skip comments whose \`position\` is null (outdated).
- Review bodies: \`gh api repos/{owner}/{repo}/pulls/${pr}/reviews\` — keep non-empty bodies; dedupe against inline via pull_request_review_id.
- Resolve your handle: \`gh api user --jq .login\`. Skip any thread whose latest comment is from that handle (already responded).

STEP 4 — Fresh inline review (fold-in). Review the diff yourself across the ten /age dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH, efficiency, telemetry). Read \`skills/age/references/dimensions.md\` (severity rubric) and \`skills/age/references/voice.md\` (voice) via tilth. Fold each fresh finding into the buckets tagged [from-age:<dimension>] (these get NO reply). Dedupe against comment-sourced items echoing the same defect — keep the comment-sourced one.

STEP 5 — Grade every input. For each comment / CI-finding / fresh-finding:
- Classify dimension from code+claim.
- Compute severity from the rubric (base + location + compounding). IGNORE reviewer-asserted urgency — CHANGES_REQUESTED is metadata only, surfaced as a \`reviewer-asserted:\` line, never a severity bump.
- Bucket:
  - **Blocker/High/Medium/Low** — claim grounded in the diff AND fix is contained. Route grounded cheap nits to Low (not Reviewer-rejected). Tag [<dim>:<sev>] plus [from-comment:<id>] / [from-check:<job>] / [from-age:<dim>].
  - **Needs-investigation** — plausible but needs evidence outside the diff.
  - **Reviewer-rejected** — claim wrong/ungrounded, OR valid but large (fix-cost sprawling/structural). Draft a push-back reply (NOT posted).

STEP 6 — Write the report to \`.cheese/affinage/pr-${pr}.md\` via tilth_write (mkdir -p the dir first with Bash if needed). Use exactly this structure (omit empty severity sections; omit Needs-investigation / Reviewer-rejected if empty):

${reportTemplate(pr)}

STEP 7 — Return the structured digest. topFindings: <=6 one-liners each with severity + source tag. themes: 2-5 short keywords describing what the PR changes (used for cross-PR overlap detection — be precise). recommendedCure: describe the recommended composite (mediums-and-above unioned with cheap contained-fix lows) and how many findings it covers. reportPath: ".cheese/affinage/pr-${pr}.md". status: "ok" or "halt: <reason>".

Reminder: SAFE mode — no posting, no cure, no melt, no push. Reasoning inline only.`

phase('Affinage')
log(`Fanning out safe-mode /affinage across ${PRS.length} PRs: ${PRS.join(', ')}`)
const perPR = await parallel(PRS.map((pr) => () =>
  agent(affinagePrompt(pr), {
    label: `affinage:pr-${pr}`,
    phase: 'Affinage',
    schema: AFFINAGE_SCHEMA,
    agentType: 'general-purpose',
  })
))

const ok = perPR.filter(Boolean)
log(`Affinage complete: ${ok.length}/${PRS.length} returned. Building supersession map.`)

phase('Supersede')
const supersession = await agent(
  `You are the cross-PR SUPERSESSION analyst for the current repo. Working dir is the repo root. The user is triaging these open PRs and wants to know which fold into / supersede which, and what value to extract before closing any. Produce a fold/supersession map with KEEP/CLOSE recommendations. RECOMMENDATIONS ONLY — do NOT close, edit, comment, or push anything. Do all work inline; no sub-agents.

Per-PR affinage digests (from phase 1):
${JSON.stringify(ok, null, 2)}

For each PR confirm scope by reading \`gh pr view <n> --json title,body,files,headRefName,additions,deletions\` and skim \`gh pr diff <n>\` where overlap is suspected. Detect overlap by: PRs touching the same files, PRs in the same subsystem/theme, and PRs whose intents subsume one another. For each cluster decide relationship: independent | overlap (partial, both keepable) | supersedes (one obsoletes another). When one supersedes another, name the SPECIFIC unique value in the to-be-closed PR that must be ported first (files, tests, findings, doc sections) before closing it. List genuinely independent PRs separately.

Return the structured map.`,
  { label: 'supersede', phase: 'Supersede', schema: SUPERSEDE_SCHEMA, agentType: 'general-purpose' }
)

return { perPR: ok, supersession }
