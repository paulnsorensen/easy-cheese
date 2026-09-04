# Edge review: Cheese to Wheypoint

## State

broken

The router cannot consume every handoff that Wheypoint accepts or documents.

## Evidence

Cheese has no direct Python import from Wheypoint.
Cheese invokes the `resolve` and `lint` commands.
Wheypoint emits `.cheese/notes/<slug>.md`, and Cheese consumes that projection.

| Contract | Cheese consumer | Wheypoint producer | State |
| --- | --- | --- | --- |
| `resolve --ref` command | `skills/cheese/SKILL.md:107-117` | `src/easy_cheese/skills/wheypoint/commands.py:29-33`; `src/easy_cheese/skills/wheypoint/wheypoint.py:107-117` | ok |
| Result identity | `skills/cheese/SKILL.md:111-116`; `skills/cheese/references/continue-resume.md:14-66` | `src/easy_cheese/skills/wheypoint/resolve.py:70-89,254-319`; `src/easy_cheese/skills/wheypoint/wheypoint.py:462-491` | ok |
| Result errors | `skills/cheese/references/continue-resume.md:33-66` | `src/easy_cheese/skills/wheypoint/wheypoint.py:470-491,535-583` | ok |
| `status`, `next`, `artifact`, orientation | `skills/cheese/references/handback-contract.md:15-32`; `skills/cheese/references/continue-resume.md:67-180` | `src/easy_cheese/skills/wheypoint/projection.py:38-49,68-95` | broken |
| `mode`, `order`, `parallel`, `tasks` | `skills/cheese/references/continue-resume.md:71-97,148-159` | `skills/wheypoint/references/parallel-handoffs.md:11-85`; `src/easy_cheese/skills/wheypoint/checkpoint.py:85-107` | broken |
| `baseline` and durable flags | `skills/cheese/SKILL.md:120-122`; `skills/cheese/references/continue-resume.md:115-120,178-181` | `skills/wheypoint/SKILL.md:120-130`; `src/easy_cheese_schemas/wheypoint.py:282-290` | broken |
| Legacy status disposition | `skills/cheese/references/continue-resume.md:98-147`; `skills/cheese/references/handback-contract.md:34-65` | `src/easy_cheese/skills/wheypoint/legacy.py:64-90`; `src/easy_cheese/skills/wheypoint/resolve.py:414-469` | broken |
| Legacy Affinage artifact | `skills/cheese/references/continue-resume.md:104-108` | `skills/wheypoint/SKILL.md:108-112`; `src/easy_cheese/skills/wheypoint/resolve.py:421-452` | broken |
| `lint <projection-path>` command | `skills/cheese/references/continue-resume.md:54-59` | `src/easy_cheese/skills/wheypoint/lint.py:148-190,193-256` | broken |
| Edge tests | `tests/python/test_wheypoint_skill_contract.py:63-73,173-186` | `tests/wheypoint/python/test_cli.py:403-450`; `tests/schemas/python/test_wheypoint_conformance.py:806-824` | broken |

The focused test command passed four selected tests.
Those tests prove that both incompatible Cut rules currently pass.

## Findings by severity

### Blocker

- **Wheypoint drops fields that Cheese requires.** `CheckpointIntent` omits mode, task, order, baseline, and durable flag fields (`src/easy_cheese/skills/wheypoint/checkpoint.py:85-107`). `NextAction` stores only move, orientation, and artifact (`src/easy_cheese_schemas/wheypoint.py:282-290`). The projection omits every extra field (`src/easy_cheese/skills/wheypoint/projection.py:68-95`). Cheese requires those fields for flags, baselines, and parallel work (`skills/cheese/SKILL.md:120-122`; `skills/cheese/references/continue-resume.md:71-95,115-120,148-181`). A focused decoder probe removed `mode` and `tasks` without an error. **Fix:** Add typed fields to the canonical record and projection. Reject unknown intent fields. Add round-trip tests for each field.
- **An authoritative Cut handoff has no Cheese route.** `NextMove.CUT` accepts Cut (`src/easy_cheese_schemas/wheypoint.py:86-101`). The delta contract also accepts Cut (`skills/wheypoint/references/delta-contract.md:47-49`). Wheypoint and Cheese omit Cut from resume prose (`skills/wheypoint/SKILL.md:163-180`; `skills/cheese/references/continue-resume.md:109-124`). Two passing tests enforce opposite rules (`tests/schemas/python/test_wheypoint_conformance.py:810-824`; `tests/python/test_wheypoint_skill_contract.py:173-186`). **Fix:** Add Cut to both dispatch contracts. Replace the obsolete absence test with an edge behavior test.

### High

- **The canonical projection violates the Cheese status grammar.** Cheese requires a reason on every non-`ok` status (`skills/cheese/references/handback-contract.md:34-65`). Cheese also expects the decision in `status: gated:` (`skills/cheese/references/continue-resume.md:129-145`). Wheypoint emits bare `status: gated` and inserts metadata before orientation (`src/easy_cheese/skills/wheypoint/projection.py:38-49,68-95`). **Fix:** Emit a valid reason and one shared preamble. Add `parse_handoff_slug()` round-trip tests for `ok` and `gated`.
- **Cheese does not route every legacy status disposition.** Wheypoint returns `ok-with-concerns` as a non-gated legacy result (`tests/wheypoint/python/test_resolve.py:745-769`). Cheese defines its trust and dispatch branches only for exact `ok` (`skills/cheese/references/continue-resume.md:24-31,98-128`). Wheypoint says a legacy `halt` dispatches, but Cheese and the resolver stop (`skills/wheypoint/SKILL.md:156-160`; `src/easy_cheese/skills/wheypoint/resolve.py:466-469`). **Fix:** Route legacy values by `disposition`. Carry the concern on `proceed`. Keep every `stop` value non-dispatchable.
- **Legacy validation rejects the documented Affinage artifact.** Both skills allow `PR#<n>` or a URL for `next: affinage` (`skills/wheypoint/SKILL.md:108-112`; `skills/cheese/references/continue-resume.md:104-108`). The resolver treats every non-empty legacy artifact as a repository file (`src/easy_cheese/skills/wheypoint/resolve.py:421-452`). It therefore gates each documented pull request reference. **Fix:** Validate artifact values by destination. Accept a pull request reference only for Affinage. Keep the repository file rule for file artifacts.
- **Tests protect prose fragments instead of the edge.** The Cheese-side tests search Markdown tokens (`tests/python/test_wheypoint_skill_contract.py:34-184`). Runtime tests verify resolver output without a Cheese decision (`tests/wheypoint/python/test_cli.py:403-450`). No test passes a resolved handoff through the complete routing decision. **Fix:** Add table-driven edge tests for every outcome, status, move, field, and artifact kind.

### Medium

- **Cheese overstates the `lint` command.** Cheese says that `lint` checks lineage (`skills/cheese/references/continue-resume.md:54-59`). The command calls `lint_projection_file`, which checks only the document digest and status (`src/easy_cheese/skills/wheypoint/lint.py:148-190`). Full lineage checks occur in `lint_work` during `resolve` (`src/easy_cheese/skills/wheypoint/lint.py:193-256`). **Fix:** Use the `resolve` findings for lineage. Describe `lint` as a projection-only check.

### Low

none

## STE100 status

not compliant

- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words.
- `skills/cheese/references/continue-resume.md:255` uses passive voice.
- `skills/wheypoint/SKILL.md` passed the area STE100 audit.
- This note complies with the STE100 rules.

## Follow-ups

- Add canonical fields for flags, baselines, and parallel work.
- Add Cut to the Cheese and Wheypoint dispatch contracts.
- Unify status and artifact validation across canonical and legacy handoffs.
- Correct the `lint` prose and add complete edge behavior tests.
