# Cheese to Age edge review

## State

broken

Cheese can select Age. The complete edge contract does not agree.

The edge uses skill dispatch and handback files. Cheese does not import an Age Python module.

## Evidence

| Contract | Cheese side | Age side | State |
| --- | --- | --- | --- |
| Selection | `skills/cheese/references/classification.md:120-143` selects `age` or `age-then-cure`. | `skills/age/SKILL.md:17-35` accepts a reference, range, slug, or path scope. | ok |
| Command | `skills/cheese/SKILL.md:195-196` emits `/age <ref>`, `/age <slug>`, or `/age --scope <path>`. | `skills/age/SKILL.md:19-35` accepts these command shapes. | ok |
| Flags | `skills/cheese/SKILL.md:25-30,120-122` promises flag preservation. | `skills/age/SKILL.md:19-22,40-42` defines `--hard` behavior but omits the flag from both command forms. | broken |
| Receipt | `skills/cheese/SKILL.md:159-165` emits one plain-text route receipt. | `skills/cheese/references/routing-receipt.md:27-31` makes consumption optional. Age does not need to consume it. | ok |
| Context | `skills/cheese/SKILL.md:50-59` attaches `handoff_context.wiki_hits`. | `skills/age/SKILL.md:157-166` defines report output but does not accept routed wiki hits. | broken |
| Files | `skills/cheese/SKILL.md:64-66` prohibits router file writes. | `skills/age/SKILL.md:44-49,151-193` emits the Age report and optional HTML. | ok |
| Handback | `skills/cheese/references/handback-contract.md:17-32,83-89` defines the required fields. | `skills/age/SKILL.md:112-115,151-188` sets the result but clears `artifact` and omits `baseline`. | broken |
| Errors | `skills/cheese/references/coherence-check.md:28-32` can change the route to `clarify`. | `skills/age/SKILL.md:31-35,183-187` accepts a reference and halts only when evidence is unavailable. | broken |

The shared handback fields are scalar lines. The required fields are `status`, `next`, `artifact`, and orientation.

The optional fields include `durable_flags` and `baseline`. Age defaults `durable_flags` to `none`.

Age sets `next: cure` for a medium-or-higher finding. Age sets `next: done` otherwise.

Cheese handles `halt` and `gated` as stop states. It handles `ok` as a proceed state.

## Findings by severity

### Blocker

none

### High

- **The resume handoff loses source state.** Cheese preserves `artifact` and flags at `skills/cheese/SKILL.md:120-122`. The Age report requires source fields at `skills/age/references/report-example.md:39-44`. The Age writer clears `artifact` and omits `baseline` at `skills/age/SKILL.md:112-115`. Fix: pass the resolved source report and baseline to the gated writer. Preserve the accepted flags in the Age dispatch.

- **A valid pull request route can stop before Age.** Cheese accepts pull request references at `skills/cheese/references/classification.md:120-131`. Its coherence rule requires local branch divergence or a path scope at `skills/cheese/references/coherence-check.md:28-32`. Age accepts review references at `skills/age/SKILL.md:19-35`. Fix: treat a pull request, branch, reference, or range as a valid review source. Let Age validate that source.

### Medium

- **Age has no input rule for routed wiki hits.** Cheese sends `wiki_hits` with `{page, line, why}` at `skills/cheese/references/handoff-gate.md:113-138`. Age only describes new grounding results at `skills/age/SKILL.md:157-166`. Fix: define `handoff_context.wiki_hits` as optional Age input. Reuse valid hits before Age performs more grounding.

- **The `--hard` command grammar does not match the router promise.** Cheese accepts and preserves `--hard` at `skills/cheese/SKILL.md:29-30,120-122`. Age defines the behavior at `skills/age/SKILL.md:40-42`, but its command forms omit the flag at `skills/age/SKILL.md:19-22`. Fix: add `[--hard]` to both Age command forms. Add one flag propagation rule.

- **Tests do not exercise the edge from both sides.** `tests/python/test_cheese_routing_receipt.py:47-57,98-103` checks only receipt shape and order. `tests/shared/python/test_write_handoff_artifact.py:179-201` checks only generic Age preamble parsing. A repository test search finds no Age target receipt, `age-then-cure` route, or routed `wiki_hits` case. Fix: add table tests for pull request, range, path, and slug routes. Add flag, context, and handback round-trip tests.

### Low

none

## STE100 status

not compliant

- `skills/cheese/SKILL.md:42` puts two routing instructions in one sentence. Split the selection and fallback instructions.
- `skills/age/SKILL.md:128` uses a long table sentence and a gerund chain. Split the evidence rules into direct sentences.

## Follow-ups

- Preserve Age source state and accepted flags during Cheese dispatch.
- Accept routed wiki hits in Age.
- Permit pull request and reference routes in the Cheese coherence check.
- Add direct Cheese-to-Age contract tests.
