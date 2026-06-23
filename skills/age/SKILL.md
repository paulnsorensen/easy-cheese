---
name: age
description: Review a diff, PR, branch, or path across ten orthogonal dimensions (correctness, security, encapsulation, spec, complexity, deslop, assertions, NIH, efficiency, telemetry) and emit a severity-grouped findings report. Use when the user wants a code review — phrases like "review this", "/age", "is this safe to merge", "find bugs", "spot security issues", "check for slop", "review my PR", "look for problems", "what's wrong with this code". Report (`## Blocker / ## High / ## Medium / ## Low`) lands at `.cheese/age/<slug>.md`, each finding tagged by dimension. Use even when the user only asks for one dimension — the report scopes itself. Findings only — no fixes; after the report lands, age auto-applies the recommended set (mediums-and-above plus cheap lows) via `/cure`, gating only when a fix is sprawling/structural or findings conflict; `--safe` restores the selection gate. Supports `--auto` (propagated from `/cook --auto`) for the autonomous chain into `/cure`. After `/press` (optional); before `/cure`.
license: MIT
---

# /age

Use this skill to review a diff or scoped path before merging, after `/press`, or whenever the user wants evidence-backed observations rather than an approval verdict.

Do not use it to apply fixes directly. Hand fix work to `/cure`, which owns applying findings.

## Inputs

Accept:

```text
/age [<ref-or-range>] [--scope <path>] [--comprehensive] [--full] [--safe] [--open-pr] [--auto]
/age <slug> [--full] [--safe] [--open-pr] [--auto]
```

`--full` un-collapses the `## Low` section when 10 or more low-severity findings exist (the default report collapses them to a one-line summary). Suppressed lows feed the cure-selection table only when `--full` is passed.

`--safe` re-introduces the cure-selection gate that the autonomous default skips (see `## Handoff`). Use it when you want to choose findings before anything is fixed. `--open-pr` propagates to `/cure` so a clean cure may open a *new* PR when none exists (otherwise `/cure` only pushes an already-open one); see `skills/cure/SKILL.md`. Both flags propagate forward to `/cure` at the handoff.

When called with a `<slug>`, resolve `.cheese/press/<slug>.md` (if present) for press context and review the current working diff. When called with a `<ref-or-range>`, review that range. Default to the current working diff when neither is supplied. If the base branch is unclear, ask or use the repository's documented default.

`--auto` is the propagated autonomous-mode flag from `/cook --auto`. It changes the handoff (see `## Handoff`). Track the cure-pass count internally so the two-cure-pass cap can be enforced — increment after each `/cure --auto` returns. The full chain is `age → cure → age → cure → age → stop`: up to three `/age --auto` invocations and up to two `/cure --auto` passes. Once two cure passes have completed, the next `/age --auto` writes the final report and stops without invoking `/cure` again. (This in-session contract uses conversation memory to track passes — it works because `/cook --auto` runs every phase in the same context. When invoked from `/ultracook`, each phase boots in fresh context with no shared memory; see `### When invoked from /ultracook` below for the no-shared-memory variant.)

`--hard` is the propagated metacognitive-gate flag from `/cook --hard` (or `/cheese --hard`). Age does not fire the gate; it only passes `--hard` forward to `/cure` at the handoff so the gate can fire at the share-for-review boundary. See `skills/hard-cheese/SKILL.md`.

## Review dimensions

Dimensions answer **what kind of problem**. Severity (`blocker / high / medium / low`) is per-finding, computed from base + location + compounding modifiers (see `references/dimensions.md` § Severity computation).

| Dimension | Base range | Look for |
| --- | --- | --- |
| correctness | low → blocker | broken behaviour, silent failures, ordering, null/empty edge cases, races, lost writes |
| security | low → blocker | auth, injection, secrets, unsafe parsing, tainted inputs, weak crypto |
| encapsulation | low → blocker | class-private peeks, module-internal leaks, cross-slice internals, ingress/egress contract violations, caller-shadowed domain invariants |
| spec | low → blocker | drift from stated requirements or acceptance criteria; silent drift on security/data/correctness reqs |
| complexity | low → high | unnecessary nesting, long functions, speculative abstractions, redundant state, parameter sprawl, stringly-typed code |
| deslop | low → high | dead code, AI residue, duplicated logic, copy-paste-with-variation, vague names |
| assertions | low → blocker | weak tests, shallow existence checks, swallowed errors, mocked SUT |
| nih | low → high | reinvented dependency, stdlib, or existing project helper / utility / component |
| efficiency | low → blocker | unnecessary work, missed concurrency, hot-path bloat, no-op updates, time-of-check/time-of-use (TOCTOU) pre-checks, memory leaks, overly broad reads |
| telemetry | low → blocker | silent error branches on non-interactive paths (servers, daemons, workers, outbound API/DB/queue calls), un-instrumented outbound calls, silent worker loops, hand-rolled logging infrastructure, missing rotation/retention/config hygiene on new file logging, unstructured logs, wrong log levels, double-logging, errors logged without context, missing correlation/trace ids, high-cardinality metric labels or span names, logs-as-metrics, `print()`/`console.log` in production, tests asserting on log strings |

Per-dimension base-severity tables, location-sensitivity, fix-cost-now / fix-cost-later, and recommendation shapes live in `references/dimensions.md`. This reduced workflow intentionally omits the git-history/precedent dimension.

## Flow

1. Identify the diff, scope, and relevant spec or issue. **Mode check (one decision point):** if the scale threshold is met — `(diff > 15 files) OR (review context > ~25 KB) OR (caller graph crosses multiple subsystems)` — and `/age` is not itself a sub-agent, switch to `### Scale-triggered fan-out mode`; steps 2–4 (evidence-gather, per-dimension review, severity computation) are replaced by the fan-out path — both modes converge on steps 5–6.
2. Gather evidence: diff, touched files, tests, callers/imports. If `.cheese/press/<slug>.md` exists, read it and include a `## Press findings` sub-section in the age report summarising unresolved items — `/cure` reads only `.cheese/age/<slug>.md` and cannot access the press report directly.
3. Review every dimension; dimensions with no findings simply omit themselves.
4. Compute severity per finding (base + location bump + compounding bump, capped at `blocker`). Group findings by severity (`## Blocker → ## High → ## Medium → ## Low`); within a severity group, order by file.
5. Write the report to `.cheese/age/<slug>.md` and print the path.
6. Hand off (see `## Handoff` below). By default age auto-selects the recommended fix set and dispatches `/cure` in the same turn, gating for a human decision only when there is a genuine reason (a sprawling/structural fix in the set, or conflicting findings) or when `--safe` is passed. Age never *applies* fixes itself — `/cure` owns application — it only owns the *selection* and the dispatch.

## Preferred tools and fallbacks

Code search and reading go through the `cheez-*` skills (`/cheez-search`, `/cheez-read`) — see those skills for tool selection rules. For caller graphs specifically, age uses `cheez-search` with `kind: "callers"` and `tilth_deps` (cheez-search owns the routing).

Beyond `cheez-*` there are review-specific tools:

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection | `delta` | `git diff --unified=3` |
| Risk-scored impact + curated review context | code-review-graph: `get_review_context_tool`, `get_impact_radius_tool`, `detect_changes_tool` | `tilth_deps` + manual scoping |
| Architecture / hotspot framing for large diffs | code-review-graph: `get_architecture_overview_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool` | skip and note in confidence |
| Design rationale for encapsulation/spec dimensions (optional) | `mcp__hallouminate__list_corpora` / `mcp__hallouminate__ground` on `repo:<repo>:wiki` corpus — if available, ground design intent before grading encapsulation and spec findings | skip; proceed with diff + code evidence only; cap at `speculating` when rationale is the primary evidence |
| GitHub/PR context | `gh` | local git commands or user-provided PR data |
| Merge/conflict awareness | mergiraf | manual conflict checks |

**Freshness:** before the first code-review-graph query in a run, call `build_or_update_graph_tool`. The graph is persistent and goes stale between sessions. See [`/cheez-search`](../cheez-search/SKILL.md#when-code-review-graph-beats-tilth-if-your-harness-has-it) for the full freshness contract and when semantic search beats tilth — steel threads across renamed layers, concepts under divergent names, spec-vs-code vocabulary mismatch.

**Optional MCPs:** code-review-graph, hallouminate, and milknado follow the detect-and-degrade contract in [`shared/optional-plugins.md`](shared/optional-plugins.md) — state absence once, fall back, reduce confidence only if evidence quality suffers, never block.

Missing optional tools should not block review. State which evidence was unavailable and reduce confidence accordingly.

## Sub-agent context gate

`/age` should fork a read-only review-context sub-agent when evidence gathering is likely to exceed the parent context, especially for `--comprehensive` reviews.

Spawn when any of these are true:

- The diff spans more than 15 files.
- Touched code or generated review context is larger than roughly 25 KB (about 5 K tokens of raw output the parent would not read line-by-line).
- Caller / dependency graph expansion crosses multiple subsystems.
- code-review-graph or `tilth_deps` output is needed for hotspot, bridge-node, or blast-radius framing.

The sub-agent returns a digest: orientation paragraph, high-signal `path:line` citations, gap list. In single-parent mode (below threshold), the parent owns the ten-dimension review, severity grading, and the `.cheese/age/<slug>.md` report — do not spawn for small diffs, to outsource severity grading, or to outsource the final verdict. In fan-out mode, per-dimension severity is delegated to workers; the parent retains cross-dimension reconciliation, the final verdict, and the report — see `### Scale-triggered fan-out mode` below.

Digest size, parent-vs-sub-agent split, and harness-agnostic sub-agent selection live in `references/sub-agent-gate.md` — single source of truth for the cross-cutting rules.

### Scale-triggered fan-out mode

Activates when **all** hold: the size threshold above is met AND `/age` is not itself a sub-agent (no `invoked-from:` marker). Below threshold, or when running as a sub-agent, the single-parent path applies unchanged.

**Seam 1 — Predicate.** Fan out when `(diff > 15 files) OR (review context > ~25 KB) OR (caller graph crosses multiple subsystems)` — the threshold from `## Sub-agent context gate`, reused verbatim — AND `/age` is not itself a sub-agent.

**Seam 2 — Shared context packet.** The orchestrator assembles the packet once and writes it to `.cheese/age/<slug>-packet.md` (transient — rebuilt every run, no cross-run cache). Each worker reads this file. Eight components are documented in `references/packet.md`. The existing review-context digester above is reused as the packet's orientation + citations block — not duplicated.

**Seam 3 — Worker contract.** One worker per dimension. Each worker:
- Reviews only its assigned dimension.
- Computes **full per-finding severity** for that dimension (base + location bump + compounding bump).
- Tags each finding with its dimension and an `also-relevant-to: [<dim>, ...]` field when cross-dimension overlap is suspected.
- Returns its dimension's findings as full per-finding rows in the `SKILL.md § Output` finding format (`**[dim:sev]** path:line — claim` + `location / fix-cost-now / fix-cost-later` + `recommendation`). Not an orientation digest — the `§ Digest contract` size ceiling does not apply.
- Does **not** dedup, apply boundary tiebreakers, reconcile severity across dimensions, or write the report.

**Seam 4 — Orchestrator reconciliation.** After all workers return, apply the `## Dimension boundaries` table (`references/dimensions.md:319-340`) verbatim to any line meeting EITHER condition: (1) flagged by two or more workers at the same `file:line`; (2) tagged `also-relevant-to: [d]` by any worker — the orchestrator re-evaluates dimension `d` against that line and applies the tiebreaker (keep the higher-base finding / suppress / emit-both-with-cross-reference per the 15 rules). This consumes the `also-relevant-to` signal and provides the cross-dimension coverage single-parent gets for free. Lines neither flagged by ≥2 workers nor tagged `also-relevant-to` need no reconciliation. Group by severity. The parent owns the canonical artifact. After reconciliation, continue at step 5 (write + print the report path) and `## Handoff` exactly as the single-parent path does.

**Seam 5 — Graph freshness.** The orchestrator calls `build_or_update_graph_tool` **once** before fan-out (per `## Preferred tools and fallbacks` above). The packet carries a "graph fresh as of this run" marker. Workers never call `build_or_update_graph_tool`, but they MAY issue read-only code-review-graph queries (e.g. `get_impact_radius_tool`, `get_review_context_tool`, `get_hub_nodes_tool`, `get_bridge_nodes_tool`) against the pre-built graph for impact and hotspot framing — the same evidence the single-parent path uses for large diffs.

**Output mode-invariance (invariant).** The findings report (`.cheese/age/<slug>.md`) is identical in shape — same dedup rule, same severity grouping, same finding format — whether produced by the single-parent path or fan-out mode. Only the internal execution path differs. (Mirrors the inline-degrade invariant at `### Inline-degrade mode` below.)

## Output

Cross-cutting house style and citation form: [`shared/formatting.md`](shared/formatting.md). This section owns the findings-report shape; formatting.md owns the voice rules and the footnote primitive.

Write to `.cheese/age/<slug>.md` with a minimum handoff slug at the top so `/ultracook` and `/cheese --continue` can chain without re-parsing the report:

```markdown
status: ok | halt: <one-line reason>
next: cure | done
artifact: <path-to-press-report-or-prior-cure-if-any>
<one-line orientation: what the diff does>

# Age Report — <slug>

## Orientation
<one or two factual sentences about what the diff does>

## Press findings
<omit this section when `.cheese/press/<slug>.md` does not exist. When it does, summarise unresolved press items in one or two bullets so `/cure` (which never reads the press report directly) sees them.>

## Blocker
- **[encapsulation:blocker]** `src/users/index.ts:42` — `index` re-exports `SqlPgUser` (infra ORM type) across slice boundary. 3 consumer slices already import it.
  - location: contract · fix-cost-now: sprawling · fix-cost-later: structural
  - recommendation: define `User` in the slice's public types, map at the boundary, deprecate the leaked export.

## High
- **[security:high]** `src/api/admin/users.ts:55` — admin route accepts user-supplied filter without validation.
  - location: contract · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: validate against `AdminFilter` schema at boundary.

## Medium
- **[complexity:medium]** `src/utils/format.ts:200-240` — 60-line function, 5 params.
  - location: module · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: extract `formatHeader` / `formatBody`.

## Low
- **[deslop:low]** `src/utils/format.ts:18` — variable `data` shadows outer `data`.
  - location: class · fix-cost-now: contained · fix-cost-later: contained
  - recommendation: rename to `lineItems`.

## Confidence
<`certain` | `speculating` | `don't know`> — <one-line justification including which evidence sources were unavailable>

## Next step
Auto-fixing the recommended set via `/cure` (or, on a reason to ask / `--safe`, the selection prompt rendered inline — pick findings to cure or `none` to stop).
```

Empty severity sections are omitted entirely. When ten or more `low` findings exist, collapse the `## Low` section to a single line:

```markdown
## Low
*N low-severity findings suppressed.* Re-run with `--full` (or `/age --full`) to see them.
```

Suppressed lows feed the cure-selection table only when `--full` is passed.

`status: ok` when the review completed. `status: halt: <reason>` when evidence was unreachable in a way that blocks honest review. `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low) and the chain has cure passes remaining; `next: done` when no finding meets the `medium+` floor or the two-cure-pass cap has been reached.

Then print:

```
Age report: .cheese/age/<slug>.md
```

## Handoff

**Pipeline:** culture → mold → cook → press → **[age]** → cure → ship

After the report is on disk, age decides whether to *act* or *ask*. The default is to act: auto-select the recommended fix set and dispatch `/cure` in the same turn, no gate. The gate is reserved for the cases that genuinely need a human decision. Age never *applies* fixes — `/cure` owns application — it only owns the *selection*.

**Compute the recommended set.** The recommended selection is the composite `all-medium, cheap` — floor at medium (blockers + high + medium) unioned with every `Low` whose `fix-cost-now: contained`. Expand it against the report into `resolved_ids`.

**Decide act vs ask:**

- **Empty set** — no finding meets the medium floor and no cheap lows exist. Nothing to cure: write `next: done`, print the report path, and stop. No question.
- **Reason to ask present** — render the selection gate (below) and wait for a choice. A reason to ask is any of:
  - a finding in the recommended set has `fix-cost-now: sprawling` **or** `fix-cost-later: structural` (auto-applying a large/structural change is unrequested scope);
  - findings in the set conflict, or a fix forces a design decision the user should make;
  - `--safe` was passed (always gate).

  When the only reason is heavy findings, pre-select the recommended composite in the gate and flag the heavy rows so the user can drop them while the rest still go.
- **Otherwise** — act. Announce the selection in one line (e.g. `Auto-fixing 4 findings (all-medium, cheap) → /cure`) and dispatch `/cure` immediately (see **Dispatch** below). No gate.

### Selection gate (`--safe`, or a reason to ask)

Use the shared handoff gate in [`shared/handoff-gate.md`](shared/handoff-gate.md). Age's finding selection is the gate's *core* decision; the shared **Standard forward-step menu**'s tail (**Ship it**, **Checkpoint & stop**, **Stop**) rides after the selection options per that menu's tail rule.

1. Render the numbered selection table per `../cure/references/selection.md` directly inline (one row per finding, grouped by severity); mark any sprawling/structural-fix row as *heavy*.
2. Ask which findings to cure. Lead each option with the verb (what the user wants to *do* next); the underlying selection verb is the backing detail. Lead with the recommended composite, then present the same four severity-floor options below it, in the same most-inclusive-to-least order, so the gate is predictable across every run:
   - **Fix mediums-and-above plus cheap lows** *(recommended)* — equivalent to `all-medium, cheap` (floor at medium — blockers + high + medium — unioned with every `Low` whose `fix-cost-now: contained`). The cheap lows are the small valid nits that are cheaper to fix than to defer; sprawling/structural lows are left out.
   - **Fix everything** — equivalent to `all` (every finding regardless of severity).
   - **Fix medium-severity and above** — equivalent to `all-medium` (floor at medium: blockers + high + medium — the severity-floor portion of the `medium+` auto-floor; add `cheap` to also union the contained-fix lows, i.e. the recommended composite above).
   - **Fix high-severity and blockers** — equivalent to `all-high` (floor at high, includes blockers).
   - **Fix blockers only** *(strict; land only the must-fix blockers and defer the rest to a follow-up)* — equivalent to `all-blocker`.

   Then offer the non-floor and standard-tail options last:
   - **Pick findings to fix** — accept a free-text reply using the verbs from `../cure/references/selection.md` (`1,3,5`, `all-blocker`, `all-medium`, `all-high`, `cheap`, `all`, `none`, `skip N`; comma-compose to union).
   - **Ship it** — apply the recommended composite and run cure headless: `/cure <slug> --auto --open-pr --stake medium+` (the `medium+` floor *is* the recommended composite). Carries `--hard` when in scope.
   - **Checkpoint & stop** — `/wheypoint`: write a resumable handoff and pause instead of curing now.
   - **Stop — leave the report for later** — equivalent to `none`.

   Present all four severity options on every run even when a severity band is empty (e.g. no blockers): a floor that resolves to an empty set is a valid, predictable no-op — do not drop or reorder options based on which bands happen to be populated. If the user selects a floor (or the recommended composite) that resolves to an empty set, treat the selection as `none`: report that no findings match and do not dispatch `/cure` with empty `resolved_ids` (the non-empty-selection contract in **Dispatch** still holds).

### Dispatch

On a non-empty selection — whether auto-selected by default or chosen at the gate — immediately dispatch `/cure <slug> [--safe] [--open-pr] [--hard]` with the selection locked in via context, not a CLI flag:

```yaml
handoff_context:
  source_skill: /age
  source_report: .cheese/age/<slug>.md
  selection: "<recognized verb or explicit ids>"
  resolved_ids: [<expanded ids>]
```

`/cure` skips its own selection prompt when this context is present, re-confirms the cited ids still exist, then owns the apply / validate / push loop. Always emit `resolved_ids` alongside `selection` — expand the verb yourself rather than leaving the field empty; `/cure` re-confirms against the report regardless. Propagate `--safe`, `--open-pr`, and `--hard` to `/cure` when they are in scope.

On `none` / `Stop` (only reachable via the gate), exit cleanly with the report path.

`--auto` substitutes a severity-floor selection and its own chain — see `### Auto mode` below.

### Auto mode

When invoked with `--auto`:

- Skip the handoff gate.
- If two cure passes have already completed (cap reached), stop and surface the final report — do not invoke `/cure` again even if findings remain.
- Otherwise, if any finding meets the `medium+` floor (medium-or-above, or a `Low` whose `fix-cost-now: contained`), invoke `/cure <slug> --auto --stake medium+` (forward `--open-pr` when it is in scope) and increment the cure-pass count when it returns.
- If no finding meets the `medium+` floor (no medium-or-above and no cheap lows remain), stop the chain with a one-line "auto chain clean" note and the report path.

### When invoked from /ultracook

`/ultracook` spawns age as a fresh-context sub-agent and owns the chain itself. Honour the no-chain override:

- Write `.cheese/age/<slug>.md` (with the handoff slug at the top) and stop. Do not invoke `/cure <slug> --auto --stake medium+` from inside the sub-agent.
- Set `next:` from what you observe on this run, not from any guess about chain position. `next: cure` when at least one finding meets the `medium+` floor (medium-or-above, or a cheap contained-fix low); `next: done` when none do.
- The two-cure-pass cap is enforced by ultracook's fixed chain length, not by age's `next:` field. Fresh-context age cannot count prior cure passes anyway, so this is the only honest contract. The orchestrator uses `next: done` for early-stop signalling; the natural terminal stop is the chain table running out of entries.

### Inline-degrade mode (invoked from a sub-agent, e.g. /cheese-factory curd worker)

When `/age` detects it is running as a sub-agent (the parent passes the `invoked-from: cheese-factory-curd` marker or equivalent context line in the prompt), it runs its ten dimensions inline within its own context instead of spawning per-dimension sub-agents. This honours the host's nesting-depth limit (harnesses cap sub-agent nesting depth, and the orchestrator's own spawn may already sit at that cap).

Detection mechanism: scan the invoking prompt for an `invoked-from:` line — values like `cheese-factory-curd`, `fromagerie-curd`, or any harness-specific marker the orchestrator passes in. When present, switch modes:

- Run every dimension's review inline. Do not fork the read-only review-context sub-agent gate (`## Sub-agent context gate` above is skipped under inline-degrade).
- Output (the findings report + handoff slug) is identical between fan-out and inline-degrade modes — only the internal execution differs.
- Honour the no-chain-forward directive as usual: write the slug and stop. Do not invoke `/cure` from the sub-agent — the orchestrator owns the chain.

Inline-degrade is forced when the marker is present; there is no opt-out. Even above the scale-triggered fan-out threshold, the marker takes precedence — fan-out is forbidden when `/age` runs as a sub-agent because the harness nesting depth is already consumed. Spawning a deeper sub-agent from inside a curd worker can exceed the harness's nesting limit and fail silently — the marker is the only honest signal that the parent has already consumed the available depth.

## Rules

- Review is not a verdict; explain where to look and why.
- Do not edit production files. Age never *applies* fixes — it owns the *selection* and dispatches `/cure`, which owns application.
- Default to acting: auto-select the recommended set and dispatch `/cure` without a gate. Ask first only on a genuine reason (a sprawling/structural fix in the set, or conflicting findings) or under `--safe`. An empty recommended set is a clean stop, not a question.
- Do not invent evidence. Cite files, diffs, commands, or unavailable-source notes.
- Agree when the diff is fine. Do not manufacture findings to fill a dimension; an empty dimension is a valid outcome.
- Keep confidence qualitative (`certain | speculating | don't know`); never emit a numeric score.
- Findings carry location + recommendation. Do not write JSON sidecars or hash-anchored fix payloads — `/cure` reads the markdown directly.
- Apply `references/voice.md` (output discipline, reasoning posture, confidence vocabulary).

## References

- `references/dimensions.md` — per-dimension rubrics and recommendation shapes.
- `references/voice.md` — shared output discipline, reasoning posture, and confidence vocabulary.
- `references/sub-agent-gate.md` — shared sub-agent kernel: digest contract, harness-agnostic selection, what the parent never delegates.
