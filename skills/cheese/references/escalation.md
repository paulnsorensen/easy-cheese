# Escalation tiers and the spec-discovery check

Read this before dispatching a `cook` or `mold` intent — the full three-tier escalation mechanics behind `skills/cheese/SKILL.md` § Escalation, plus the spec-discovery check that runs inside tier 1.

## Escalation tiers

For `cook` and `mold` intents, `/cheese` runs cook's fast-path check (§ "Standalone fast-path" in `skills/cook/SKILL.md`) and escalates through three tiers:

**Tier 1 — clear (all three checks pass).** First run the `## Spec-discovery check` below — if an existing spec in `.cheese/specs/` substantially matches the request, dispatch `/cook --auto` against it and skip the mini-spec write. Otherwise the agent invokes `/mold`'s agent-invoked mini-spec mode (see `skills/mold/SKILL.md` § Agent-invoked mini-spec mode) to write `.cheese/specs/<slug>.md`, then dispatches `/cook --auto <spec-path>` in the same turn as the announce, where `<spec-path>` is the explicit mini-spec path returned by `/mold`. Do not collapse that path to a bare `<slug>`. No user interaction. When the input already names a spec path under `.cheese/specs/`, skip both the discovery scan and the mini-spec write and dispatch `/cook --auto` against the existing path directly.

**Tier 2 — borderline (any check fails or is uncertain).** Agent autonomously invokes `/culture` (internal thinking) and/or `/briesearch` (internal research), in any order, to fill the missing context. After the internal pass, re-run the cook fast-path check on the refined understanding. If all three checks now pass, drop into tier 1 (the mini-spec records the culture / briesearch synthesis under `## Provenance`). Otherwise tier 3.

**Tier 3 — still borderline after tier 2.** Block on the human via a single targeted host-routed question whose answer closes the failing check. On the answer, re-enter classification with the augmented input. This is the only sanctioned user-facing prompt in the autonomous-by-default path; the `clarify` intent and the below-`medium`-confidence path both map here.

`--safe` does not skip the escalation logic — the tiers still run silently — but it inserts a handoff gate before the final dispatch in every tier. The recommended option stays auto-flavoured (`/cook --auto <spec-path>` etc., using the explicit mini-spec path); the non-auto variant is offered as the alternative.

## Spec-discovery check

Before minting a new mini-spec for a tier-1 `cook` or `mold` dispatch, look for an existing spec that already covers the request. Specs land in the durable XDG corpus (`default_root_for_phase("specs")`), not repo-local, so probe there:

- **hallouminate present** — `ground` the candidate spec text against the `cheese-durable` corpus for a near-duplicate (semantic match across every project's durable specs). Detect-and-degrade per [`optional-plugins.md`](optional-plugins.md).
- **hallouminate absent** — fall back to `resolve_slug(candidate_slug, phase_hint="specs")` (the XDG-correct `difflib` resolver in `shared/scripts/paths.py`), and note the degrade once: name-based rather than semantic matching. This keeps slug-level dedup on the headless/cron path where hallouminate is routinely unavailable.

Act on the result, do not guess:

1. **One clear match (high confidence)** — surface the resolved spec path in one line and dispatch against it (`/cook --auto <resolved-spec-path>`) instead of writing a duplicate.
2. **Multiple plausible matches, or a weak best match** — under `--safe`, present the candidates in the handoff gate for the user to pick; without `--safe`, fall back to minting a fresh mini-spec rather than risk dispatching against the wrong spec.

Skip silently when no specs exist yet, and when the user already named a spec path (the path is authoritative).
