# Cure round 2 — hard-cheese

This note records every finding from the eight input notes for the `hard-cheese` area.

The area has five paths. Two hard-cheese runtime modules are outside those paths:
`src/easy_cheese/skills/hard_cheese/freshness_check.py` and
`src/easy_cheese/skills/hard_cheese/append_attempt.py`.
The megamerge diff does not change either module.
No other area owns them.
This node defers every finding whose root cause is in those two modules.

## Findings

| # | Source note | Severity | State | Commit | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | review-hard-cheese | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| 2 | review-hard-cheese | blocker | rejected: the fix contradicts the rubric in the same file and an out-of-area test. Applied the underlying contradiction fix instead. | `docs(hard-cheese): remove the causal-understanding claim` | `skills/hard-cheese/references/judge-prompt.md:29-35`; `tests/python/test_hard_cheese.py:83-120` |
| 3 | review-hard-cheese | blocker | applied | `fix(hard-cheese): pin the judge reviewer to powerful power` | `skills/hard-cheese/SKILL.md:130,218` |
| 4 | review-hard-cheese | blocker | deferred: root cause in `append_attempt.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/append_attempt.py:110-117` |
| 5 | review-hard-cheese | high | applied | `fix(hard-cheese): isolate untrusted judge input from instructions` | `skills/hard-cheese/references/judge-prompt.md:33-40` |
| 6 | review-hard-cheese | high | applied | `docs(hard-cheese): record the telemetry content-retention divergence` | `skills/hard-cheese/SKILL.md:23,155-167` |
| 7 | review-hard-cheese | high | applied | `fix(hard-cheese): add ERROR to the artifact status list` | `skills/hard-cheese/SKILL.md:111` |
| 8 | review-hard-cheese | low | applied | `docs(hard-cheese): apply ASD-STE100 to the skill and composition prose` | `skills/hard-cheese/SKILL.md:27-32,47,135,173,213`; `skills/hard-cheese/references/composition.md:13,17,19,22,49,51` |
| 9 | edge-affinage-hard-cheese | high | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:44-58` |
| 10 | edge-cure-hard-cheese | high | deferred: owned by `cure`. The hard-cheese side now publishes the status matrix. | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/references/composition.md:35-46`; `skills/cure/SKILL.md:232` |
| 11 | edge-cure-hard-cheese | medium | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:81-91` |
| 12 | edge-mold-hard-cheese | blocker | deferred: owned by `mold` | none | `skills/mold/SKILL.md:47,131`; `skills/mold/references/mini-spec-mode.md:5-8` |
| 13 | edge-mold-hard-cheese | high | deferred: owned by `mold` | none | `tests/python/test_hard_cheese.py:150-153` |
| 14 | edge-plate-hard-cheese | blocker | deferred: root cause in `freshness_check.py`, outside the five area paths | none | `src/easy_cheese/skills/hard_cheese/freshness_check.py:165-189` |
| 15 | edge-plate-hard-cheese | high | applied for the prose contract; the validating command is deferred with finding 14 | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/SKILL.md:62-71` |
| 16 | edge-plate-hard-cheese | high | applied | `fix(hard-cheese): require the complete Plate evidence and define the status matrix` | `skills/hard-cheese/references/composition.md:35-46` |
| 17 | edge-plate-hard-cheese | high | applied | `test(hard-cheese): add hard gate seam regression tests` | `tests/hard-cheese/python/test_hard_gate_seam.py:65-91` |
| 18 | hub-shared (`hard-cheese -> shared`) | ok | no change required | none | `src/easy_cheese/skills/hard_cheese/commands.py:7-39` |
| 19 | hub-schemas | n/a | no `hard-cheese` row | none | `.cheese/notes/r014-megamerge/hub-schemas.md` |
| 20 | hub-build | n/a | no `hard-cheese` row | none | `.cheese/notes/r014-megamerge/hub-build.md` |

## Simplifications

| Simplification | State | Reason |
| --- | --- | --- |
| Make `append-attempt` the only artifact writer | deferred | The change belongs to `append_attempt.py`, outside the area paths. |
| Replace the freshness fields with one reviewed-state digest | deferred | The change belongs to `freshness_check.py`, outside the area paths. |
| Remove `pass` from the judge JSON | rejected | `tests/python/test_hard_cheese.py:330` requires the `pass` field. That test is outside the area paths. |
| Keep the two decorated command wrappers | applied | `src/easy_cheese/skills/hard_cheese/commands.py:14-35` is unchanged. |
| Remove no other helper from the five reviewed paths | applied | No helper was removed. |

## Disagreements

- `judge-prompt.md` SOLO level 3. `review-hard-cheese.md` states that score 3 is Relational.
  The rubric in the same file, the Biggs & Collis mapping, and `tests/python/test_hard_cheese.py:83-120` all state that score 3 is Multistructural.
  Choice: keep the typed rubric contract. Level 3 stays Multistructural.
  The real defect was the claim that level 3 shows sufficient causal understanding. That claim is now removed.
- `ERROR` outcome. `edge-cure-hard-cheese.md` requires a fail-open continuation. `edge-plate-hard-cheese.md` requires a question before publication.
  Choice: keep the typed exit-status contract. The gate returns `0` for `ERROR`.
  The new Plate status matrix requires the caller to ask the user before publication.

## STE100 status

compliant

- `skills/hard-cheese/SKILL.md` uses `run` as the single gate-execution term. Each compound instruction is now a separate sentence.
- `skills/hard-cheese/references/composition.md` uses the same term and sentence rules.
- `skills/hard-cheese/references/judge-prompt.md` splits the long threshold paragraphs. Quoted rubric material stays unchanged.
- `skills/hard-cheese/references/commands.md` is generated and compliant.

## Gate

`bash .milknado/reconcile-gate.sh` exits `0`.
`uv run pytest -q tests/hard-cheese/python tests/python/test_hard_cheese.py` passes 86 tests.

## Follow-ups

- Bind hard-cheese freshness to a digest of `HEAD`, the working diff, the specification, and the Plate context. The change belongs to `freshness_check.py`.
- Make `append-attempt` write the complete artifact schema, including the frontmatter and the `agent_resolution` block. The change belongs to `append_attempt.py`.
- Add a hard-cheese command that validates the Plate evidence object.
- Mold must append `--hard` to every Cook command it emits.
- Cure must stop only for `FAILED` and non-TTY errors.
