# ADR: Lead Mold forks from evidence and keep the ledger in EARS

Status: accepted (2026-11-17). Amends [mold-review-canvas-010](./mold-review-canvas-010.md).

## Context

Mold fork cards stated what a fork decides, but not why the fork came next.
The user saw a question without the evidence chain that opened it.
Ledger `Decided` and `[AGENT-DECIDED]` entries were free-text labels, such as "SQLite, one file".
The review canvas requirement pane showed EARS text, but the ledger beside it did not, so the two views disagreed.

## Decision

Each fork card opens with a `Basis:` line: "Based on X and Y, the next question is ...".[^1]
X and Y are ledger ids (a settled fork, an `ev-n` evidence item, a `G-n` clause, or an `AC-n` line) with their findings.
A basis cites only settled forks; a fork that needs an open fork waits for it (`depends_on` in the canvas).
A fork with no ledger entry to cite is not ready: ground it or demote it.

Each `Decided` and `[AGENT-DECIDED]` entry is one EARS requirement, or prose with `[prose-fallback]`.[^2]
The entry keeps its fork id (or `AD-n`), basis ids, and veto alternative.
The `Goal:` line and `G-n` clauses stay in the user's words, because `goal-drift` and goal coverage compare text.
Non-goals stay scope lines, because they name exclusions, not behavior.
At curdle, the spec `## Decisions` section copies the EARS text verbatim.

The canvas accepts `questions[].basis: [{ref?, text, confidence?}]` and renders the lead-in above the fork card.[^3]
The lead-in is the fieldset's accessible description. A confidence other than `certain` shows in parentheses.
The browser drops basis entries without text.
The agent publishes the ledger decisions as the requirement list, with one text in both places.

## Consequences

`review publish` adds two non-blocking warnings: an open question without a basis entry that has text, and a requirement or `decided`/`agent-decided` ledger item with no `SHALL` and no `[prose-fallback]`.[^4]
Warnings keep the ADR 008 rule that publish stores any JSON object.
Legacy documents still render unchanged, but they now receive basis warnings.
The three canvas examples publish with zero warnings, and a test pins that.
Example `01-bounds.json` now has requirements, so the legacy phone bottom-sheet test strips them.

The EARS check is lexical (`SHALL` present). It does not prove a correct EARS pattern.
The taste test still matches ledger decisions by fork id; EARS text makes the word-match fallback stricter, so fork-id tags stay the reliable form.

## Related records

- [Keep requirements and fork settlement visible in the review canvas](./mold-review-canvas-010.md)
- [Mold goal-drift gate and altitude tag](../decisions/mold-goal-drift-gate.md)
- [EARS source](../sources/ears-easy-approach-to-requirements-syntax.md)

[^1]: `skills/mold/references/fork-questions.md` § Fork card and § Basis; `skills/mold/SKILL.md` § Rules
[^2]: `skills/mold/references/decision-ledger.md`; `skills/mold/references/curdle.md` § Spec template
[^3]: `frontend/mold-review/src/components/Question.jsx`; `frontend/mold-review/src/main.jsx` `basisEntries`; `frontend/mold-review/tests/canvas.spec.js` basis tests
[^4]: `src/easy_cheese/skills/mold/review.py` `_basis_warnings`, `_ears_warnings`; `tests/python/test_mold_review.py`

_Source: branch `paulnsorensen/mold-forks-ears-ledger`; `skills/mold/references/decision-ledger.md`, `skills/mold/references/fork-questions.md`, `src/easy_cheese/skills/mold/review.py`, `frontend/mold-review/src/components/Question.jsx` · Updated: 2026-11-17_
