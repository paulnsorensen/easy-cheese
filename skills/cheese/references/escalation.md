# Escalation tiers and the spec-discovery check

Read this file before you dispatch a `cook` or `mold` intent.
It defines the three escalation tiers and the tier-1 specification discovery check.

## Escalation tiers

For `cook` and `mold`, `/cheese` runs cook's fast-path check and uses three escalation tiers:

**Tier 1: clear.** Run the specification discovery check.
When one specification matches, dispatch `/cook --auto` against it.
Otherwise, invoke `/mold`'s agent mode to write `.cheese/specs/<slug>.md`.
Then dispatch `/cook --auto <spec-path>` in the same turn.
Use the explicit path that `/mold` returns.
Do not reduce it to a bare slug.
When the input names a specification path, use it directly.
Do not scan or write another specification.

**Tier 2: borderline.** Invoke `/culture` or `/briesearch` internally to get the missing context.
Repeat cook's fast-path check.
When all checks pass, continue with tier 1.
Otherwise, continue with tier 3.

**Tier 3: still borderline.** Ask one targeted host-routed question that closes the failed check.
Classify the answer again.
This is the only user prompt in the default autonomous path.

`--safe` does not skip escalation.
For `--safe`, it inserts a handoff gate before the final dispatch.
The auto variant stays recommended, and the non-auto variant stays available.

## Spec-discovery check

Before a tier-1 dispatch, look for an existing specification that covers the request.
Specifications use the durable XDG corpus from `default_root_for_phase("specs")`.

- **hallouminate present** — `ground` the candidate spec text against the `cheese-durable` corpus for a near-duplicate (semantic match across every project's durable specs). Detect-and-degrade per [`optional-plugins.md`](optional-plugins.md).
- **hallouminate absent** — use `resolve_slug(candidate_slug, phase_hint="specs")` from `src/easy_cheese/shared/paths.py`.
  Report once that matching uses names instead of semantics.
  This preserves slug deduplication without hallouminate.

Act on the result, do not guess:

1. **One clear match (high confidence)** — surface the resolved spec path in one line and dispatch against it (`/cook --auto <resolved-spec-path>`) instead of writing a duplicate.
2. **Multiple plausible matches or one weak match** — under `--safe`, let the user select a candidate.
   Without `--safe`, write a new mini-specification to avoid the wrong match.

Skip silently when no specs exist yet, and when the user already named a spec path (the path is authoritative).
