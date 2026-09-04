# Briesearch to Cook Edge Review

## State

`untested`

Current prose keeps the route separate from implementation authorization. No listed test or evaluation protects this seam.

## Evidence

| Contract item | State | Evidence |
| --- | --- | --- |
| Route name | The producer and consumer use `/cook`. | Briesearch permits `/cook` in `### Next step` (`skills/briesearch/references/synthesis.md:84-109`). Cook defines `/cook` as its entry name (`skills/cook/SKILL.md:16-20`). |
| Authorization | The producer requires explicit user authorization. Cook starts from explicit implementation requests or a clear task. | Briesearch stops after research unless the current prompt requests implementation (`skills/briesearch/SKILL.md:23-30`). Cook lists its user triggers and accepted inputs (`skills/cook/SKILL.md:3-11,30-36`). |
| Type and fields | Briesearch emits a Markdown recommendation. Cook does not parse this field. | The output has a free-text `### Next step` field (`skills/briesearch/references/synthesis.md:84-109`). Cook accepts a typed Curd plan only through its phase contract (`skills/cook/phase-contract.yaml:5-16`). |
| Emitted files | A long research report is optional. Cook defines no command for this report. | Briesearch can emit `research/<slug>/<slug>.md` (`skills/briesearch/SKILL.md:60-62`). Cook reserves `accept` for a Mold pointer (`skills/cook/SKILL.md:30-36`). |
| Calls and imports | Briesearch has no direct Cook call or import. | Its command surface exposes artifact, budget, grounding, and layout commands only (`src/easy_cheese/skills/briesearch/commands.py:14-60`). |
| Cook command | Cook's machine entry accepts a Mold pointer and a Curd plan. It does not accept a Briesearch report. | The command table names the Mold pointer (`src/easy_cheese/skills/cook/commands.py:126-130,230-235`). The handler fixes the destination and schema (`src/easy_cheese/skills/cook/contract_handlers.py:119-143`). |
| Defaults and errors | The advisory edge has no defaults or edge-specific error mode. Cook reports errors only for its typed pointer path. | Briesearch defines only the free-text recommendation (`skills/briesearch/references/synthesis.md:101-102`). Cook catches pointer and contract failures (`src/easy_cheese/skills/cook/contract_handlers.py:125-143`). |
| Tests | Neither side tests the authorization seam. | Briesearch omits this check from its manual trace list (`skills/briesearch/references/evals.md:31-56`). Cook's test module covers only Mold pointers (`tests/python/test_cook_contract_accept.py:1-6`). |

No unmatched contract change appears at HEAD. The producer and consumer agree that a route does not authorize implementation.

## Findings

### Blocker

none

### High

- **No test protects implementation authorization.** Briesearch omits the route from its trace list (`skills/briesearch/references/evals.md:31-56`). Cook tests only Mold pointers (`tests/python/test_cook_contract_accept.py:1-6`). A prompt edit can turn advice into unauthorized implementation. **Fix:** Add one Briesearch trace test and one Cook entry test. The research-only case can recommend `/cook`, but it must stop. The combined case can enter Cook only after an explicit user implementation request.

### Medium

none

### Low

none

## STE100 status

compliant

The reviewed prose in both `SKILL.md` files complies with the stated rules. This note also complies with those rules.

## Follow-ups

- Add a Briesearch trace that recommends `/cook` for research-only work and then stops.
- Add a Cook entry trace that requires an explicit user implementation request.
