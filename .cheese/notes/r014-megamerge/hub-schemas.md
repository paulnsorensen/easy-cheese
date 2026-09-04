# Schemas consumer hub review

## Verdict

reject

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `age -> schemas` | broken | `skills/age/SKILL.md:112-115,151-153` reuses the final report as body and removes upstream state. `test_age_review_lock.py:38-47` omits the body and baseline. |
| `cheese -> schemas` | broken | `continue-resume.md:98-122` uses hard-coded phases. `schema-intertwine.md:9-16` omits Affinage and Pasteurize. The tests check generated output, not boundary completeness. |
| `cook -> schemas` | broken | `contracts.py:862-903` validates dependency graphs. `workflow.py:1252-1277` executes declaration order. No workflow test sets `dependencies`. |
| `cure -> schemas` | broken | `SKILL.md:54-75` selects curds. `workflow.py:1180-1211` requires bindings for all plan curds. The tests do not cover successful Cure output. |
| `mold -> schemas` | broken | `validate_spec.py:447-459` maps `ui_surface`. `test_validate_spec.py:400-507` covers its closed classes. Lines 613-623 create unearned Grounding rows. |
| `wheypoint -> schemas` | ok | `records.py:30-39`, `checkpoint.py:54-64`, and `commit.py:49-64` consume record, status, and compaction contracts. `lineage.py:9-124` and `resolve.py:36-40` consume lineage and phase contracts. Tests cover these seams. |

The final focused runs report 767 passes and four failures.
`test_cook_contract_accept.py:136-146,159-168,215-235` contains all four failures.
`review-cook.md:11,23` already records these defects.

## Findings

### Blocker

- **[correctness:blocker] Age can leave a malformed report before transition validation.** `skills/age/SKILL.md:112-115,151-153` first writes the final report with its preamble. It then passes this full report as `--body-file`. `write_handoff_artifact.py:106-109,145-173` prepends another preamble after transition validation. A rejected transition can still leave the earlier report. `test_age_review_lock.py:38-47,128-129` omits `--body-file`, so it cannot detect either result. Fix: write only the body to a temporary file. Let the writer create the final report.
- **[correctness:blocker] Cook ignores valid plan dependencies during execution.** `contracts.py:862-903` checks references and cycles. `workflow.py:1252-1277` then executes each curd in declaration order. This order can run a dependent before its prerequisite. It also cannot block a dependent after prerequisite failure. No `test_workflow_thread.py` case sets `dependencies`. Fix: schedule ready curds from the graph. Block each dependent after a prerequisite fails. Add tests for reverse order and failed prerequisites.
- **[spec:blocker] Cure cannot apply a selected subset through its typed API.** `skills/cure/SKILL.md:54-75` requires one binding and result for each selected curd. `workflow.py:1192-1210` requires bindings for all plan curds. `workflow.py:1252-1277` also executes all plan curds. Age and Affinage handoffs provide only a report and selected identifiers. Fix: add an explicit selected-curd input. Validate only that subset. Execute only that subset. Keep plan identity checks for every selected curd.

### High

- **[correctness:high] Age removes required upstream handback state.** `skills/age/SKILL.md:92-100` consumes upstream reports. Lines 151-154 require `artifact` and `baseline`. The only command at line 115 sets `--artifact ""` and omits `--baseline`. The direct test preserves this incomplete shape at `test_age_review_lock.py:38-47`. Fix: pass the consumed report through `--artifact`. Pass the existing baseline through `--baseline`. Assert both fields in the direct writer test.
- **[spec:high] Cheese does not consume the full phase registry.** `continue-resume.md:98-122` uses a hard-coded phase list that includes Affinage. `schema-intertwine.md:9-16` registers only Age, Cook, Cure, Mold, and Press. `handback-contract.md:85-90` also assigns the writer to Affinage and Pasteurize. Generated-region tests compare output with declarations, but they do not test the required producers. Fix: register every declared producer and transition. Then derive Cheese routing from the compiled registry and catalog. Add one completeness test for all handback producers.

### Medium

- **[correctness:medium] Cook bypasses the schema error path for invalid UTF-8.** `contract_handlers.py:53-64,97-105` decodes files before schema validation and catches only `OSError`. `schema_runtime.py:499-518` converts byte decode failures into `ContractValidationError`. Current handlers can expose an uncaught `UnicodeDecodeError`. Fix: read bytes and pass them to the schema runtime. Add invalid UTF-8 tests for `normalize` and `validate`.
- **[assertions:medium] Cure has no successful direct seam test.** `test_workflow_thread.py:766-919` tests unconfirmed, missing, tampered, and unsupported Cure inputs. It does not assert one successful `cure()` result. Fix: add a successful call with confirmed bindings. Assert `CurdResult` type, count, plan reference, curd reference, digest, and provenance.
- **[correctness:medium] Mold records probes that did not occur.** `validate_spec.py:613-623` creates two `unavailable` Grounding rows when an accepted source omits Grounding. `contracts.py:2338-2356,2450-2455` defines these rows as recorded probe outcomes with evidence. Fix: model the permitted source omission directly. Do not create probe results during validation. Add a test that distinguishes omission from an unavailable probe.

### Low

none

## STE100 status

not compliant

- Age remains noncompliant. `review-age.md:90-107` records the file audit.
- Cheese remains noncompliant. `review-cheese.md:67-88` records the file audit.
- Cook remains noncompliant. `review-cook.md:54-61` records the file audit.
- Cure remains noncompliant. `review-cure.md:52-58` records the file audit.
- Mold remains noncompliant. `review-mold.md:56-69` records the file audit.
- Wheypoint complies. `review-wheypoint.md:48-50` records the file audit.
- This note complies.

## Follow-ups

- Fix Age report ownership and upstream field propagation.
- Make Cook schedule curds from the dependency graph.
- Make Cook convert invalid UTF-8 into one contract error.
- Add a selected-curd Cure API.
- Add one successful direct Cure seam test.
- Register every declared handback producer.
- Derive Cheese routing from the compiled registry and catalog.
- Model an omitted Mold Grounding section without false rows.
- Fix the four Cook bundle failures in `review-cook.md:11,23`.
