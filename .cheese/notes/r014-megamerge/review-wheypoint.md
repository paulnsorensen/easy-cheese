# Wheypoint Area Review

## Verdict

reject

## Findings

### Blocker

- **[correctness] Failed mirror writes leave false durability evidence.** `src/easy_cheese/skills/wheypoint/commit.py:336-347` promotes the record before the finalizer writes the mirror at `src/easy_cheese/skills/wheypoint/wheypoint.py:295-310`. A failed-finalizer probe left a current record whose projection said `durability: repo-snapshot`. The applied retry fix still publishes false canonical evidence. **Fix:** Run the mirror finalizer before `store.promote` while the record lock is held.
- **[spec] The normal authoring path drops documented handoff data.** `skills/wheypoint/SKILL.md:120-132,237-243` requires flags, lineage, baselines, and parallel tasks. `skills/wheypoint/references/parallel-handoffs.md:11-85` adds `mode`, `order`, `parallel`, and `tasks`. `CheckpointIntent` has none of these fields at `src/easy_cheese/skills/wheypoint/checkpoint.py:85-107`. The projection cannot render them at `src/easy_cheese/skills/wheypoint/projection.py:68-95`. An input probe showed that `mode` and `tasks` disappear without an error. **Fix:** Define typed fields before the prose advertises them. Reject unknown intent keys. Remove unsupported instructions.
- **[correctness] The generated projection breaks the shared handoff parser.** Projection metadata precedes the orientation at `src/easy_cheese/skills/wheypoint/projection.py:38-49,68-95`. The shared parser accepts only three optional keys at `src/easy_cheese/shared/handoff.py:105-160`. One probe returned `work_id: demo` as the orientation. A gated probe failed because the projection emits `status: gated` without a required reason. **Fix:** Make the first four projection lines match `parse_handoff_slug()`. Emit a valid gated reason. Add round-trip tests.
- **[spec] `cut` can enter an authoritative record, but Cheese cannot dispatch it.** `NextMove.CUT` exists at `src/easy_cheese_schemas/wheypoint.py:86-101`. The delta contract permits it at `skills/wheypoint/references/delta-contract.md:47-49`. Wheypoint omits it at `skills/wheypoint/SKILL.md:163-180`. Cheese also omits it at `skills/cheese/references/continue-resume.md:109-124`. **Fix:** Add Cut to both dispatch contracts. Update the test that requires Cut to remain absent.

### High

- **[correctness] Lint accepts a prior compaction from the same revision or a descendant.** `_compaction_findings` checks only membership and compaction presence at `src/easy_cheese/skills/wheypoint/lint.py:399-452`. It never checks the prior revision's position in the current-first chain. A self-reference therefore passes this check. **Fix:** Require each prior compaction to occur later in the current-first chain. Add self-reference and descendant-reference tests.
- **[assertions] Contract tests assert prose tokens instead of edge behavior.** `tests/python/test_wheypoint_skill_contract.py:156-161` passes when the shared parser breaks. Lines 173-184 require Cut to remain absent while the schema requires its round trip. The focused suite passed 325 tests despite three failing behavior probes. **Fix:** Round-trip generated projections through the shared parser. Exercise gated status and Cut dispatch.

### Medium

- **[correctness] Coverage validates only the digest when both pins exist.** `src/easy_cheese/skills/wheypoint/records.py:189-209` returns after the digest check. `skills/wheypoint/references/delta-contract.md:56-59` requires each supplied revision and digest to remain valid. A probe accepted a matching digest with an unknown revision. **Fix:** Validate every supplied pin before accepting coverage. Add a dual-pin failure test.

### Low

none

## Simplifications

- Choose one canonical handoff format. Delete legacy authoring instructions that the typed record cannot represent.
- Replace `lint._Chain` and `_walk_chain` with `lineage.Lineage` plus direct finding conversion. The types duplicate state at `lint.py:335-364` and `lineage.py:34-55`.
- Move the mirror transaction behind the commit or storage boundary. Keep `wheypoint.py` as command transport, as its module contract states.
- Replace prose-presence contract tests with behavior tests at each actual edge.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `wheypoint -> schemas` | ok | Runtime imports resolve for records, status, compaction, lineage, and phase contracts. The focused suite passed. |
| `wheypoint -> shared` | broken | Shared paths and manifest symbols resolve. `parse_handoff_slug()` misreads an `ok` projection and rejects a gated projection. |
| `cheese -> wheypoint` | broken | Cheese can consume validated scalar moves, but it has no Cut dispatch. The projection also breaks the shared preamble contract. |
| `wheypoint -> cook` | broken | Prose requires baseline carry-forward at `skills/wheypoint/SKILL.md:124-130`. The canonical intent and projection have no baseline field. |
| `wheypoint -> build` | ok | `COMMANDS` has five decorated entries. `skills/wheypoint/references/commands.md:5-11` matches them. |

Focused check: `pytest -q tests/python/test_wheypoint_skill_contract.py tests/wheypoint/python` passed 325 tests.

## STE100 status

compliant

## Follow-ups

- Cure all blocker, high, and medium findings in this review.
