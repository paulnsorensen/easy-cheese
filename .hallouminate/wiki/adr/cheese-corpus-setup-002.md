# ADR-002: spec-discovery falls back to `resolve_slug` when hallouminate is absent  [status: accepted]

- **Context:** hallouminate is optional and routinely absent on the headless/cron/autonomous path (`optional-plugins.md:17`) — the same path `/cook --auto` runs spec-discovery on. Grounding against `cheese-durable` is the primary dedup, but it can't be a hard dependency.
- **Decision:** When hallouminate is unavailable, fall back to `resolve_slug(candidate_slug, phase_hint="specs")` — the existing difflib resolver (`paths.py:372`), which already enumerates the XDG spec dir — and note the degrade once.
- **Alternatives:** (C1) skip the dedup check entirely when absent — rejected: reintroduces the #267 silent-duplicate-spec failure on the headless path. Keeping a scoring engine (the dropped `spec_match`) — rejected separately (ADR-003).
- **Consequences:** Buys slug-level dedup on the headless path for zero new code (reuses an existing function). Costs only name-based (not semantic) matching when the daemon is down — an accepted degrade.
