# ADR: Harness-neutral core with thin model overlays

**Status:** accepted (2026-10-18, overlay rule 2026-10-22)

Easy-cheese targets generic agents, and the harness must not matter.
Shared skill text names roles and model tiers, not models.
A thin overlay per harness and model holds the rest, and it is generated where possible.

## Context

Fork A in the manifesto evidence (#829, `docs/architecture/manifesto-evidence.md` section 5) asked which harness easy-cheese is designed for.
The Agent Skills spec has only `compatibility`, `metadata`, and an experimental `allowed-tools` field, and no portability section.
Capability declaration therefore lives in the skill pack, not in the spec.
milknado ships one plugin on Claude Code, Codex, and opencode, which shows that one pack can serve several harnesses.

On 2026-10-22 three places in shared skill text still named one model family:

- `skills/cook/references/tdd-loop.md:72` routed review to "1 fresh opus reviewer".
- `skills/cheese/references/routing-policy.md:71` justified a reviewer contract by "Opus 5 recall behavior".
- `skills/pasteurize/SKILL.md:153` told the agent to run `/model opus`.

## Decision

- Design for generic agents. Opinionated defaults ship later behind a config.
- Shared skill text names a role (coder, reviewer, verifier) and a tier (`cheap | default | powerful`).
- One overlay maps each role and tier to a model and an upgrade command per harness. Today the overlay is the roles-by-tiers table in `skills/cheese/references/routing-policy.md`.
- The overlay stays thin. It holds model names, tier-upgrade commands, and model-specific notes, and nothing else.
- A code check rejects a model name in shared skill text outside the overlay.

The owner's words: "we shouldn't have opus instructions for a codex model".

## Consequences

- The size heuristics in [deterministic-fanout-sizing-005](./deterministic-fanout-sizing-005.md) read harness capabilities, such as sub-agent support and prompt caching, from a declaration, not from the harness name.
- The config shape (file location, precedence, exposed heuristics) is an open design question. Precedents: spec-kit resolves overrides, presets, extensions, then core; OpenSpec uses `openspec/config.yaml`; milknado uses `~/.config/milknado/milknado.toml`.
- [codex-omp-portability-001](./codex-omp-portability-001.md) still holds: one shared portability reference, with host-specific examples labelled as examples.

## Source

Owner rulings of 2026-10-18 (fork A) and 2026-10-22 (overlay), recorded in Wheypoint `tenet-reconciliation-rulings` and in #832.
