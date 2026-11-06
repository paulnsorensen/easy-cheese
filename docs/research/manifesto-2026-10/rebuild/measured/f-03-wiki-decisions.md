# Wiki prior-decision digest (sub-agent report, 2026-09-21)

Source: Hallouminate corpus `repo:easy-cheese:wiki`, rooted at `/home/paul/Dev/easy-cheese/.hallouminate/wiki/`. Quotes are as the explorer reported them. The parent confirmed that each cited page exists. The parent did not re-read the quoted lines.

| Claim | Quote | Wiki page, lines |
|---|---|---|
| Fan-out sizing is deterministic file-glob arithmetic, not an LLM classifier. | "judgment decides what a diff means; deterministic code decides how many agents look at it" | adr/deterministic-fanout-sizing-003.md, 50-60 |
| The decision was measured. | "file classification only changes the tier of 4 of 30 commits... The upside is small and bounded. The costs are not" | adr/deterministic-fanout-sizing-003.md, 23-48 |
| Skill-size gates use a stdlib byte estimate. | "Token estimation is body_bytes // 4 in pure stdlib." | adr/skill-size-ratchet-002.md, 1-14 |
| The schema catalog is a published contract. | "easy-cheese-schemas 1.1 published resolve_artifact(..., schema_validator=...)... Preserve artifact schema-validator injection until a major release" | adr/artifact-schema-validator-compatibility-001.md, 1-20 |
| A consolidation audit found no safe merges. | "zero safe root-contract merges" | architecture/schema-similarity-and-consolidation-audit.md, 394-409 |
| Ultracook was retired because review was not independent. | "The previous parallel worker performed cook, press, age, and cure in one context, so review was not independent" | architecture/ultracook-agent-topology.md, 1-28 and 58-75 |
| The Curd-block size gate was deleted. | "PR #672 removes the Curd-block parser and its MIN_CURD_SURFACE gate" | adr/deterministic-fanout-sizing-004.md, 1-21 |
| Checkpoints fixed an unsafe writer-exhaustion resume. | "A compact worker reply is an observation set, not a Wheypoint record... The retry cannot rehash its own edits as proof of earlier completed work" | gotchas/wheypoint-resume-traps.md, 32-67 |
| The review lock came from security findings. | "The r014 review of Age... turned four security findings into standing invariants" | gotchas/age-review-lock-invariants.md, 1-11 |
| Review fan-out is heavier than its use. | "51 /age runs with zero reviewers and 73 with one or two" (of 83 sessions) | research/review-fanout-policy-comparison.md, 107-123 |
| A rejection log exists for simplification proposals. | "the record of which proposed changes were ruled out and why, so they are not re-litigated" | skill-parity-analysis.md, 1-19 |
| The RED-gate gotcha page claims a live import. | "press.pyz red-gate was removed as a dispatchable subcommand, but src/fanout/press_route.py still imports cut.red_gate at runtime" | red-gate-environment-gotchas.md, 23-25 |
| Multi-harness support uses one shared reference. | "one shared-reference-first documentation contract" | adr/codex-omp-portability-001.md, 1-25 |

Parent check on the RED-gate row: `git grep -i red_gate` over `src/` and `skills/*/SKILL.md` returned 0 lines on 2026-09-21. Commit `681820f0` (#560) removed `cut` and RED-gate enforcement.

Not found within 10 calls: a wiki page on the `cheez-*` wrapper retirement, and a wiki page on `pocock-parity`.
