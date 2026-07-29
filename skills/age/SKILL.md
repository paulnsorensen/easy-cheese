---
name: age
description: Review a diff, PR, branch, or path across ten orthogonal dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH, efficiency, telemetry) and emit a severity-grouped findings report. Use when the user wants a code review — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "what's wrong with this code". Use even when the user only asks for one dimension — the report scopes itself. Do NOT use for applying fixes (route to /cure) or test hardening (route to /press).
license: MIT
metadata: {dispatches-agents: true}
---

# /age

Review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict. Do not apply fixes here — `/cure` owns application.

## Inputs

```text
/age [<ref-or-range>] [--scope <path>] [--comprehensive] [--full] [--safe] [--open-pr] [--auto] [--html]
/age <slug> [--full] [--safe] [--open-pr] [--auto] [--html]
```

`--full` un-collapses the `## Low` section when 10 or more low-severity findings exist (the default report collapses them to a one-line summary).

`--safe` re-introduces cure selection. `--open-pr` propagates through `/cure` to terminal `/plate`; a new PR follows `/plate`'s explicit-choice and review-shape policy.

When called with a `<slug>`, resolve `.cheese/press/<slug>.md` (if present) for press context and review the current working diff. When called with a `<ref-or-range>`, review that range. Default to the current working diff when neither is supplied. If the base branch is unclear, ask or use the repository's documented default.

`--auto` is the propagated autonomous-mode flag from `/cook --auto`. It changes the handoff (see `## Handoff` and `## Auto mode` for the cap rule and full chain).

`--hard` propagates through `/cure` to `/plate`. Age never fires the gate; `/plate` gives `/hard-cheese` the final verified artifact state before publication.

`--html` emits a static HTML copy alongside `.cheese/age/<slug>.md`: write the markdown first, then `python3 src/age/age-html-report.py --report .cheese/age/<slug>.md --slug <slug>` (bundle fallback: `age.pyz html-report` with the same flags), and print the returned path. It groups findings by severity into the shared HTML shell (`shared/scripts/html_report.render_document`) — offline, no CDN, no JS.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback. The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Review dimensions

Dimensions answer **what kind of problem**. Severity (`blocker / high / medium / low`) is per-finding, computed from base + location + compounding modifiers (see `references/dimensions.md` § Severity computation).

| Dimension | Base range |
| --- | --- |
| correctness | low → blocker |
| security | low → blocker |
| encapsulation | low → blocker |
| spec | low → blocker |
| complexity | low → high |
| deslop | low → high |
| assertions | low → blocker |
| nih | low → high |
| efficiency | low → blocker |
| telemetry | low → blocker |

Per-dimension base-severity tables, location-sensitivity, fix-cost-now / fix-cost-later, and recommendation shapes live in `references/dimensions.md` — read it before computing any finding's severity. This reduced workflow intentionally omits the git-history/precedent dimension.

## Flow

1. Identify the diff, scope, and relevant spec or issue. **Mode check:** compute the review range's `review_surface` score and risk flags, then call `age_route.route(score=..., risk_flags=..., entry="age")` (`src/fanout/age_route.py`). `n=1` — steps 2–4 below, unchanged. Any `n>1` — read `references/fan-out.md` first; its `lenses` list, not a fixed label, sets worker count. Fan-out also requires `/age` not itself be a sub-agent — stay single-parent when it is. Thread the router's `effort` into the reviewer dispatch.
2. Gather evidence: diff, touched files, tests, callers/imports. If a press report exists for this slug, read it via `python3 shared/scripts/read_handoff_slug.py --phase press --slug <slug>` (bundle fallback: `common.pyz read_handoff_slug --phase press --slug <slug>`) and summarise unresolved items in a `## Press findings` sub-section — `/cure` only reads `.cheese/age/<slug>.md`.

   No press report but a cook handoff exists: record `press: skipped` (see `## Output`) and print the warning at handoff. No cook artifact either: skip the marker and continue.

   If `.cheese/glossary/<slug>.md` exists, read it so naming drift can be flagged as a deslop finding.
3. Review every dimension; dimensions with no findings simply omit themselves. Report every defect, however minor — never self-filter on perceived significance; filtering happens downstream in the verifier pass (`n>1`) or in severity computation (single-parent). Do not raise a finding for a gate failure identical to the diff's recorded `baseline:` block — see [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md); flag only new or changed failures.
4. Compute severity per finding (base + location bump + compounding bump, capped at `blocker`). Group findings by severity (`## Blocker → ## High → ## Medium → ## Low`); within a severity group, order by file.
5. Write the report (see `## Output`), then `python3 shared/scripts/write_handoff_artifact.py --phase age --slug <slug> --status ok --next cure --artifact "" --orientation "<one-line orientation>" --durable-flags "<none | one line per flag>" --body-file "$report_file"` (bundle fallback: `${CLAUDE_SKILL_DIR}/scripts/common.pyz write_handoff_artifact` with the same flags). Print the path.
6. Hand off (see `## Handoff` below).

## Preferred tools and fallbacks

Call source-code backends directly according to the shared [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) contract. For caller graphs, use the selected semantic backend's caller query plus `tilth_deps` when available.

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection | `delta` | `git diff --unified=3` |
| Caller/dependency impact + curated review context | semantic caller search + `tilth_deps` | manual scoping; note the precision loss |
| Architecture / hotspot framing for large diffs | changed-file map + caller/dependency evidence | skip and note in confidence |
| Design rationale for encapsulation/spec dimensions (optional) | `mcp__hallouminate__list_corpora` / `mcp__hallouminate__ground` on `repo:<repo>:wiki`, grounding design intent before grading, rendering consulted pages in `## Wiki context` | skip; omit `## Wiki context`; proceed with diff + code evidence only; cap at `speculating` when rationale is the primary evidence |
| GitHub/PR context | `gh` | local git commands or user-provided PR data |
| Merge/conflict awareness | mergiraf | manual conflict checks |

**Optional MCPs:** hallouminate and milknado follow the detect-and-degrade contract in [`../cheese/references/optional-plugins.md`](../cheese/references/optional-plugins.md) — state absence once, fall back, reduce confidence only if evidence quality suffers, never block.

## Sub-agent fan-out

`/age` sizes its own fan-out via the age router (`src/fanout/age_route.py`), not a size-only threshold, and resolves every dispatched worker through `../cheese/references/agent-resolution.md` (read-only, fresh-context; exact specialist, then compatible specialist, then a prompt-constrained general agent with `degraded: true`). Mechanics: `references/fan-out.md`, `references/packet.md`, `references/sub-agent-gate.md`.

## Output

Cross-cutting house style and citation form: [`../cheese/references/formatting.md`](../cheese/references/formatting.md). This section owns the findings-report shape; formatting.md owns the voice rules and the footnote primitive.

Write to `.cheese/age/<slug>.md` with a minimum handoff slug at the top — `status`, `next`, `artifact`, `durable_flags`, `baseline`, one-line orientation. `press: skipped` is the first body line after the blank separator when a cook artifact exists but no press report does; omit it otherwise.

Body, in order: `# Age Report — <slug>`; `## Orientation` (1-2 sentences); `## Press findings` (omit unless a press report exists); `## Wiki context` (omit unless hallouminate grounding hit); severity sections (`**[dim:sev]** path:line — claim`, then `location: <tier> · fix-cost-now: <tier> · fix-cost-later: <tier> · confidence: <tier>`, then `recommendation: <action>`); `## Confidence`; `## Next step`. See `references/report-example.md` for the full skeleton plus a worked instantiation.

Empty severity sections are omitted entirely. When ten or more `low` findings exist, collapse the `## Low` section to a single line:

```markdown
## Low
*N low-severity findings suppressed.* Re-run with `--full` (or `/age --full`) to see them.
```

Per-finding `confidence:` uses the voice-kernel scale (`references/voice.md` § Reasoning posture): `certain` — verified by direct evidence (diff/code read, command output); `speculating` — inferred from indirect signal. A `don't know` grading never ships as a finding row — gather the missing evidence or drop the claim. Suppressed lows feed the cure-selection table only when `--full` is passed.

`status: ok` when the review completed; `status: halt: <reason>` when evidence was unreachable. `next: cure` when any finding meets the **medium+ floor**; `next: done` otherwise. `durable_flags:` mirrors cook's gate: default `none`.

Then print `Age report: .cheese/age/<slug>.md`. When `press: skipped` is set, also print: `Warning: no /press report for <slug> — hardening was skipped. Run /press <slug> first, or continue with /cure.` When `--html` is passed, also print the HTML path returned by `html-report` (render command under `--html` in `## Inputs`).

## Handoff

**Pipeline:** culture → mold → cook → press → **[age]** → cure → plate

**Compute the recommended set.** Composite `all-medium, cheap`: the medium floor (blocker+high+medium) unioned with every `Low` at `fix-cost-now: contained`.

**Decide act vs ask:**

- **Empty set** — write `next: done`, print the report path, stop.
- **Reason to ask** — a set member has `fix-cost-now: sprawling` or `fix-cost-later: structural`, findings conflict, or `--safe` was passed: read `references/handoff-detail.md` and render the gate per `../cheese/references/handoff-gate.md`, pre-selecting the composite and flagging heavy rows.
- **Otherwise** — act: announce the selection and dispatch `/cure` per `references/handoff-detail.md` § Dispatch. No gate.

`--auto` substitutes a severity-floor selection (`## Auto mode` below); `references/handoff-detail.md` also covers the no-chain override under `/cook`'s fan pathway.

## Auto mode

When invoked with `--auto`:

- Skip the handoff gate.
- If two cure passes have already completed (cap reached), stop and surface the final report — do not invoke `/cure` again even if findings remain.
- Otherwise, if any finding meets the **medium+ floor** — invoke `/cure <slug> --auto --stake medium+` (forward `--open-pr` when it is in scope) and increment the cure-pass count when it returns.
- If no finding meets the **medium+ floor**, stop the chain with a one-line "auto chain clean" note and the report path.

### Within cook's own fan pathway

`/cook`'s fan pathway spawns age as a fresh-context sub-agent and owns the chain itself. Read `references/handoff-detail.md` § Within cook's own fan pathway for the no-chain isolation directive before writing the report.

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files; `/cure` owns application.
- Do not raise a finding for a gate failure identical to the diff's recorded `baseline:` block; flag only new/changed failures per [`../cook/references/quality-gates.md`](../cook/references/quality-gates.md).
- Default to acting: auto-select the recommended set, dispatch `/cure` without a gate. Ask first only on a genuine reason or `--safe`. An empty recommended set is a clean stop, not a question.
- Do not invent evidence; cite files, diffs, commands, or unavailable-source notes.
- Agree when the diff is fine — an empty dimension is a valid outcome, not a gap to fill.
- Keep confidence qualitative (`certain | speculating | don't know`) at both the report and per-finding level; never a numeric score.
- Findings carry location + recommendation, not JSON sidecars or tag-anchored fix payloads — `/cure` reads the markdown directly.
- Apply `references/voice.md` (output discipline, reasoning posture, confidence vocabulary).

## References

- `references/dimensions.md` — before grading any finding: rubrics, location sensitivity, fix-cost tables, recommendation shapes.
- `references/fan-out.md` — before any `n>1` dispatch: router mechanics, lens partitions, six-seam sequence, verifier pass.
- `references/packet.md` — when assembling the Seam-2 shared context packet for a fan-out run.
- `references/sub-agent-gate.md` — before any sub-agent dispatch: digest contract, harness-agnostic selection, what the parent never delegates.
- `references/handoff-detail.md` — before the selection gate or a `/cure` dispatch: gate menu, dispatch payload, cook-fan-pathway no-chain override.
- `references/report-example.md` — alongside `## Output`: worked rendering plus the full placeholder skeleton.
- `references/voice.md` — when writing the report: output discipline, reasoning posture, confidence vocabulary.
- `references/deslop-rust.md`, `references/deslop-typescript.md`, `references/deslop-python.md`, `references/deslop-shell.md`, `references/deslop-go.md` — when grading `deslop` in that language: pattern catalogs with lint-rule mappings.

## Agent resolution

Resolve every dimension worker and fresh-context review through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Review a diff or one dimension | reviewer | read-only, fresh-context | powerful | high | compatible reviewer, then general |

The canonical age report/handoff carries the shared `agent_resolution` block.
