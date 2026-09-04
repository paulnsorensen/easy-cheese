# Briesearch Area Review

## Verdict

reject

The scoped tests pass with 69 tests.
Behavioral probes expose contract failures.
The review covers correctness, security, encapsulation, specification alignment, complexity, AI slop, assertions, NIH, efficiency, and telemetry.

## Findings

### Blocker

- **[security:blocker] `ground-check` accepts signed URLs in reports.** `ground_check.py:263-293` accepts a citation when its digest matches the manifest. `safety.md:29-36` and `synthesis.md:114-115` forbid persisted query values. A probe with `?token=secret` returns no violations. **Fix:** Reject user information before digest matching. Reject query values and fragments before digest matching. Add a regression test.
- **[spec:blocker] The budget gate permits a missing budget.** `SKILL.md:26` and `budgets.md:5-21` require a declaration before the first call. `ledger.py:308-319` converts a missing budget to an empty map. `budget.py:166-175` checks only declared keys. `test_briesearch_budget.py:310-316` accepts a search call without a budget. **Fix:** Require a budget when the manifest contains calls. Require a limit for each used call kind.
- **[correctness:blocker] The local citation checks implement the wrong path contract.** `ground_check.py:63-77,199-236` validates only `.cheese` and `raw` paths with colon anchors. The checker accepts `missing.py:999999`. It rejects the required `raw/a.md#L1-1` format. `context-isolation.md:34-37` and `synthesis.md:114-115` require that format. `test_briesearch_ledger.py:231-237` asserts the invalid acceptance. **Fix:** Parse colon anchors and `#L` anchors. Resolve every local citation under its allowed root. Verify every referenced line range.
- **[correctness:blocker] The ledger does not bind evidence to its report.** `context-isolation.md:34-67` requires the slug, raw file, and fetch date. `ledger.py:101-123,268-294,329-348` discards the slug, title, and fetch date. It also permits a successful extraction without a file. A probe accepts a mismatched slug, a 2020 fetch, and a missing file for a 2026 claim. **Fix:** Retain the documented manifest fields. Match the manifest slug to the report stem. Compare each report date with its manifest fetch date. Require a confined raw file for each deep capture.

### High

- **[spec:high] `research-layout` accepts slugs outside the documented size.** `SKILL.md:40,62` and `context-isolation.md:19-20` require four to six words. `research_layout.py:37-43` delegates to the generic validator. `shared/paths.py:98-107` accepts one to 64 characters. A probe accepts one-word and seven-word slugs. **Fix:** Enforce the Briesearch word count in `research_layout`.
- **[correctness:high] The table parser rejects valid escaped pipes.** `ground_check.py:115-122` splits every pipe without Markdown escape handling. A probe with `\|` reports the next cell as the confidence value. **Fix:** Use an escape-aware table row parser. Add tests for escaped pipes and code spans.

### Medium

- **[correctness:medium] Cached records consume the provider call budget.** `context-isolation.md:66` defines a cached record as an earlier run entry. `budget.py:104-107,166-175` counts it as a new call. A zero-budget probe reports `BUDGET` for one cached search. **Fix:** Exclude cached records from spent call counts. Report them only in cached metrics.
- **[spec:medium] Confidence labels are case-insensitive.** `synthesis.md:24` requires exact lowercase labels. `ground_check.py:320,367-375` lowercases labels before validation. A probe accepts `CERTAIN`. **Fix:** Compare the stripped label with the exact allowed values. Add a case-variance test.

### Low

- **[efficiency:low] Local line checks rescan each evidence file.** `ground_check.py:169-177,334-359` opens and counts the complete file for each citation row. **Fix:** Cache line counts by resolved path for one report check.
- **[spec:low] Seven prose files violate the required STE100 rules.** The `STE100 status` section gives file and line evidence. **Fix:** Split each listed instruction. Use present active voice.

## Simplifications

- `ledger.py:114-120,157,265,290` keeps `Call.canonical` as a compatibility alias for `url_digest`. Repository search finds no separate consumer. Delete the alias. Return two URL fields from `_url_fields`.
- `commands.py:42-55` already uses the shared `derive_command` helper. Keep this implementation. Do not restore the removed local summary helper.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `briesearch -> shared`: `bundle_command`, `derive_command`, and `dispatch` | ok | `commands.py:7-11,42-60` matches `shared/bundle_commands.py:61-83,138-154`. |
| `briesearch -> shared`: `artifact_path.main` | ok | `commands.py:14-18` resolves to `shared/artifact_path.py:40-53`. |
| `briesearch -> shared`: `project_corpus_root` | ok | `research_layout.py:20,42-50` matches `shared/paths.py:247-249`. |
| `briesearch -> shared`: `validate_slug` | broken | `research_layout.py:37-43` needs four to six words. `shared/paths.py:98-107` enforces only generic kebab-case. |
| `briesearch -> cheese`: question, format, code routing, and agent rules | ok | `SKILL.md:19,55,62,94` points to existing Cheese contracts. |
| `briesearch -> age`: voice and sub-agent rules | ok | `SKILL.md:40,74,90` points to existing Age contracts. |
| `briesearch -> mold`: research handoff | ok | `synthesis.md:26-38,101-102` keeps design choices open. `mold/references/grounding.md:48` consumes prior research. |
| `briesearch -> cook`: implementation handoff | ok | `synthesis.md:101-102` emits only a next skill. `cook/SKILL.md:3-11` owns implementation. |
| `build -> briesearch`: bundle and command reference | ok | `build_pyz.py:40-43` discovers the skill. `render_generated_regions.py:265-297` renders `COMMANDS`. The bundled `--help` lists all four commands. |

## STE100 status

not compliant

- `skills/briesearch/SKILL.md:19` puts two instructions in one sentence.
- `skills/briesearch/references/budgets.md:44-45` puts multiple actions in each sentence.
- `skills/briesearch/references/context-isolation.md:3` joins two instructions with a semicolon.
- `skills/briesearch/references/evals.md:42-43,52` uses past or passive forms.
- `skills/briesearch/references/query-planning.md:7,23,42,46,65` combines instructions or uses future tense.
- `skills/briesearch/references/synthesis.md:3,24,69,112` combines instructions or uses past tense.
- `skills/briesearch/references/unavailable.md:26` combines separate instructions.

The audit finds no violation in `commands.md`, `routing.md`, or `safety.md`.

## Follow-ups

none
