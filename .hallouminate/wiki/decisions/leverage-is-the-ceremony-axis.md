# Leverage is the ceremony axis — mold asks only about high-leverage forks

Decision from the 2026-09 mold ceremony assessment (PRs #632–#636). Facts below are the ones a future agent would otherwise rederive.

## The problem measured

Session analytics queried 2026-09-07 from `~/.cache/dotfiles/session-analytics/sessions.duckdb` (last 60 days, Claude harness, whole-session span, n=16 mold vs n=7 cook/cheese-without-mold): mold ran a median 320 tool calls, 6.5 AskUserQuestions, 6.5 sub-agent spawns, and 443 minutes wall clock; only 5 of 16 runs reached a spec write. The adherence page (`analytics/skill-adherence-2026-08-30.md:16`) reports n=20, ~10 questions per run, and 249 minutes because it uses a longer window and an active-minutes span with idle capped at 10 minutes. The two windows agree on the shape, not the digits. That page also measured **zero `tilth_deps` calls across every mold and cook run**, so the shape-check blast-radius verdict that gates Grill never fired.

Root cause: ceremony was keyed to ambiguity and scope size ("one or two files", "has a failing test", "missing acceptance criteria") and question volume was keyed to noun count (per-term scope approval, per-bullet non-goals, per-noun binding, four approvals per follow-up). Nothing keyed to stakes. "Sliced Bread", "spine", and "deep module" had zero hits across 127 skill files.

## The decision

**Leverage picks whether the user steers; ambiguity picks the artifact.**

- `cheese/references/routing-policy.md` § Leverage triggers is a closed table of ids: `auth`, `irreversible`, `concurrency`, `contract`, `destructive`, `new-slice`, `cross-slice-dep`, `invariant-gap`. Any fired trigger routes to `/mold`'s user mode; zero triggers keep the ask on the cook fast-path or a tier-1 mini-spec (`leverage: []` in frontmatter, refuses to mint when a trigger fires). Fired ids travel in the handoff packet's `leverage:` key, land in the spec's `leverage:` frontmatter (mini-spec and full template), and `/age` reads that list into its override flags via the table's `/age` column.
- **Consequential fork** is defined once, in `age/references/voice.md`: a fork that fires a leverage trigger, changes a crust or import direction, or changes user-visible behavior or output. Internal behavior the user cannot observe through a public interface does not qualify. Everything below that line is `[AGENT-DECIDED]` by default with a vetoable alternative in the ledger. Grill skips below-the-line items; `[AGENT-DECIDED]` calls never earn an ADR.
- **Sketch is placement, not signatures.** `## Interface sketches` keeps its schema name and carries a Placement block (slice, spine step, public interface, private, crust delta, arrows). The concrete-seam rule (write bodies under ~20 lines) is gone; bodies belong to `/cook`.
- **Four handshake audits, one table.** Agent-introduced scope, non-goals, entity binding, and follow-up disposition populate one scope audit table with defaults; one confirm approves the defaults. Only leverage rows and unresolved ALIAS / NEW ENTITY bindings keep their own approval turn; they render `needs your verb` and the confirm never covers them. A confirmed `drop` default writes the same rejection record as a typed drop.
- **Shape check is a precondition.** Cook's Contract requires the printed block, or the `shape check skipped: single-module change` line, before any edit. Mold's Sketch requires it when the change touches more than one module or adds a public interface. Cook stops before a new crust export, a cross-slice import of an internal, or a contract change the spec does not name.
- `cheese/references/sliced-bread.md` is the pipeline's shared architecture vocabulary, linked from mold Sketch, shape-check, cook Rules, and age `encapsulation`.

## Constraints that shaped the edits — do not re-litigate

- Skill bodies are capped at 3,600 estimated tokens (`TARGET_TOKENS` in `.github/scripts/validate_skills.py`; `.github/skill-budgets.json` only records per-skill grandfathered sizes). Mold's SKILL.md sits at the cap; every addition there must point at a reference instead of restating. Three of the five PRs tripped this, and the review fixes tripped it again.
- `age_route.OVERRIDE_FLAGS` ships inside all 13 `.pyz` bundles, so the trigger-to-flag crosswalk lives in prose (`routing-policy.md` § Leverage triggers, `age/references/fan-out.md`) rather than in the router. Adding the three new ids as flag tokens is a follow-up that costs a full bundle rebuild.
- The handshake checklist labels and `gate_graph.py` `COHERENCE_GATES` are compared by a prose-sync test; edit both, then regenerate `mold.dot` with `mold.pyz gate-graph --render dot --out skills/mold/scripts/mold.dot` and rebundle `mold.pyz`. `just bundle` rewrites every `.pyz`; restore the untouched ones before committing.
- The taste-test schema field `consequential` was kept; prose redefines what qualifies. Renaming it would touch published schemas for no behavior change.
- `## Interface sketches` was kept as the section name because it is a published `MoldSpecDocument` section with legacy fixtures. The content contract changed, not the name.
- Follow-up disposition phrases are pinned in order by `test_mold_followup_routing.py`; the batching was done around them, not by rewriting them.
- Gate ids `non-goals-audit` and identity nouns were not merged; `test_gate_graph.py` pins them and they still describe real gates.

## Why rules, not steps

The adherence page's core finding: imperative rules and preconditions on the next artifact are followed every run; numbered steps with a degrade clause see ~1% adherence. Every change above is phrased as a precondition ("no block, no code") or a closed definition, never as a step.

## Open

Whether `[AGENT-DECIDED]` by default actually drops questions per run to the 1–2 range is unverified until the next analytics pass. The 28 Bash calls per run vs 1 explorer is a delegation problem these PRs only partly address.
