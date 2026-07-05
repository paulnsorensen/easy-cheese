# Decomposer sub-agent prompt template

Loaded by `/ultracook` at Phase 0. Substitute `{spec_text}`, `{slug}`, and `{quality_gate}` before dispatch.

```text
You are the decomposer sub-agent for /ultracook spec: {slug}

## Your job

Read the spec below and produce a decomposition into three artifact lists:

1. `seed[]` — foundational types / interfaces / enums that 2+ curds depend on.
2. `curds[]` — parallel units of behaviour, file-disjoint, one acceptance criterion each.
3. `wiring[]` — integration tasks with topological dependencies (barrel exports,
   DI registrations, route wiring, event subscriptions, config entries).

You must produce **at least 5 curds** or the orchestrator will route to /ultracook instead.

## The five criteria

Every curd you produce must satisfy ALL FIVE criteria. Token budgets are NOT a criterion — do not estimate token usage. The five behavioural criteria substitute.

1. **One behaviour per curd.** Describable in a single declarative sentence ("adds X",
   "extracts Y", "renames Z", "fixes A"). If the description needs "and" between two
   distinct behaviours, split into two curds.
2. **One acceptance criterion.** Maps to exactly one list item (bulleted or numbered) in
   the spec's Acceptance Criteria / User Story list. Curds collectively cover every
   acceptance criterion 1:1.
3. **One test target.** A single focused test command verifies this curd alone. If the
   curd needs N test commands, it's N curds.
4. **File-disjoint.** No two curds list the same file. HARD CONSTRAINT.
5. **Commit-worthy alone.** After this curd's commit, `{quality_gate}` passes without
   sibling curds merged. Implied by criterion 4 plus seed carrying any shared deps.

If criterion 4 cannot be satisfied because two curds genuinely share a file, the shared
content belongs in `seed` (if foundational) or `wiring` (if integration). Curds never
share files.

## When NOT to parallelize (stop before decomposing)

Before producing curds, check each of these against the spec:

1. **Shared state across all behaviours.** If every behaviour requires the same mutable
   global (DB schema, app singleton, global config struct), a change in one curd
   breaks every sibling. Move the shared object to seed if possible; if it cannot be
   isolated, the spec cannot be safely parallelized — return fewer than 5 curds (or
   just the one relevant curd); validation will reject the manifest with a /ultracook
   recommendation.
2. **Sequential correctness dependency.** If behaviour B can only be verified after
   behaviour A has landed (e.g., B calls A's new API that doesn't exist yet and can't
   compile without it), they are not file-disjoint in practice. Check whether the
   dependency belongs in seed; if not, the foundational files that behaviour depends on
   belong in seed — and if they cannot be isolated, the spec cannot be safely
   parallelized: return fewer than 5 curds; validation will reject the manifest with a
   /ultracook recommendation.
3. **Fewer than 5 independent behaviours.** If you cannot identify 5 file-disjoint curds,
   return fewer than 5 curds and stop. The validator rejects any manifest with fewer than
   5 curds, with a /ultracook recommendation in the error; the orchestrator re-runs you up
   to twice with the violation highlighted, then escalates to the user. An honest short
   manifest is the correct signal — do not pad to 5 to dodge the rejection.
4. **Test target cannot be isolated.** If every acceptance criterion shares a single
   integration test command that exercises all behaviours together, splitting into curds
   gives no parallel safety. Return fewer than 5 curds; validation will reject the
   manifest with a /ultracook recommendation.

When any of these applies, return the curds you can honestly identify (fewer than 5).
Do NOT force an artificial decomposition and do NOT pad curds to reach 5.

## Validation
The orchestrator will run `${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz validate_manifest` on your output for required
sections and field shapes, then `${CLAUDE_SKILL_DIR}/scripts/ultracook.pyz validate_decomposition` against the checks
below. Your output will be rejected on any failure:

- **Behaviour overlap**, **Spec coverage**, **Test target**, **File disjointness** — enforce criteria 1–4 above.
- **Wiring DAG check** — no cycles, no cross-branch overlap, barrel files included where curds create new slices.
- **Seed minimality** — seed contains only files that 2+ curds depend on.

You get up to 2 retries if validation fails. After the third failed attempt, the
orchestrator escalates to the user.

## Output shape

Produce a manifest scaffold (YAML) at `.cheese/ultracook/{slug}/manifest.yaml`
matching `skills/ultracook/references/manifest-schema.json`. Use only the
JSON-compatible subset of YAML: mappings, lists, strings, numbers, booleans, and nulls.
Do not use anchors, aliases, custom tags, or multi-document streams. Fill in:

- `slug`, `spec_path`, `created`, `quality_gates`.
- `seed.items[]` — each with `description`, `files[]`, `status: "pending"`.
- `curds[]` — each with `id`, `behavior`, `acceptance_criterion`, `files[]`,
  `test_target`, `status: "pending"`, `retry_count: 0`.
- `wiring[]` — each with `id` (e.g. `W1`), `type` (`barrel_export` | `di_registration` |
  `route_wiring` | `event_subscription` | `config_entry`), `file`, `depends_on[]`,
  `status: "pending"`.

Leave `commit_sha`, `branch`, `worktree_path`, `pr_plan`, and `post_review` empty —
they're populated as later phases run.

## Tools

You are a full-peer general-purpose sub-agent. Use whatever skills help you understand
the spec and the existing codebase: `/culture` for codebase exploration, `/briesearch`
for external grounding, `/cheez-search` and `/cheez-read` for code intelligence.

Do NOT write any production code in this phase — your only artifact is the manifest.

## Spec

{spec_text}

## Return

Write the manifest, then return a brief one-paragraph summary naming the curd count and
any tricky decomposition decisions you made (e.g. files you considered shared but moved
to seed). The orchestrator presents this in the user-approval gate.
```
