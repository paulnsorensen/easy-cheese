# Cook area review

## Verdict

reject

Cook has five blocker findings. The focused acceptance test has four failures.

## Blocker

- **[security:blocker] Cook can fetch a network artifact from an untrusted handoff pointer.** `src/easy_cheese/shared/publication.py:428-450` sends each pointer reference to `resolve_artifact`. `src/easy_cheese_schemas/artifacts.py:95-102,346-407` accepts HTTPS and performs the request. `tests/python/test_cook_contract_accept.py:226-235` requires rejection. The focused test reached `https://example.com` instead of rejecting the URI. **Fix:** Restrict publication pointers to local artifacts under the declared root. Keep HTTPS support only for explicit retrieval flows.
- **[correctness:blocker] Cook ignores plan dependencies during execution.** `skills/cook/references/fan-pathway.md:75-85` requires topological waves and blocks dependents. `src/easy_cheese_schemas/contracts.py:862-903` checks only graph validity. `src/easy_cheese_schemas/workflow.py:1252-1277` executes tuple order without dependency state. An earlier dependent can run before its prerequisite. **Fix:** Schedule ready curds from the dependency graph. Block descendants when a prerequisite fails.
- **[spec:blocker] Auto mode grants publication permission without the `--open-pr` input.** `skills/cook/SKILL.md:40-42` defines `--open-pr` as a separate permission. `skills/cook/references/auto-mode.md:25-28` always appends the flag. `skills/cure/SKILL.md:243-245` forwards it only when it is in scope. **Fix:** Forward `--open-pr` only when the user supplied it.
- **[spec:blocker] Fan mode has two conflicting recovery records.** `skills/cook/references/fan-pathway.md:15-19,330-356` makes the Cook handoff the resumable state. `skills/cook/references/quality-gates.md:7,56-67` writes active state into the retired Ultracook manifest. `src/easy_cheese/skills/cook/commands.py:63-109` still exposes its manifest commands. A resumed run can miss recorded gate or wave state. **Fix:** Make the typed Cook handoff the only live state. Remove the superseded manifest command cluster and its generated rows.
- **[spec:blocker] Cook and its downstream phases assign the Cure cap to different owners.** `skills/cook/references/auto-mode.md:59-81` says the fixed loop owns the cap. It also says Age cannot count passes. `skills/age/SKILL.md:218-223` counts the passes. `skills/cure/SKILL.md:242-245` assigns the cap to Age. **Fix:** Make Age own the cap in all three skills. Pass the completed count in each Age dispatch.

## High

- **[assertions:high] The happy acceptance tests do not verify the emitted plan.** `tests/python/test_cook_contract_accept.py:116-133,246-264` checks only `plan_id` or receipt presence. One assertion checks the input pointer instead of command output. The tests can pass after Cook drops the objective, curds, digest, or receipt fields. **Fix:** Assert the complete canonical wrapper for both accepted pointer forms.

## Medium

- **[assertions:medium] Three rejection tests assert obsolete or self-defeating messages.** `tests/python/test_cook_contract_accept.py:136-146` changes payload size while it expects a digest error. Lines `159-168` and `215-223` expect an old missing-file message. The focused run returned four failures and eight passes. **Fix:** Keep the tampered payload size unchanged. Assert the current unreadable-file error for missing artifacts.
- **[spec:medium] Six Cook prose files violate the required STE100 rules.** The evidence appears in the STE100 section. **Fix:** Split compound instructions. Replace passive instructions with active instructions.

## Low

- **[efficiency:low] Cook serializes each accepted canonical value twice.** `src/easy_cheese/skills/cook/contract_handlers.py:76-86,129-142` receives canonical bytes, then calls `canonical_digest` on the value. `src/easy_cheese_schemas/contracts.py:110-119` serializes the value again. **Fix:** Compute the digest from the existing canonical bytes.
- **[spec:low] Two reference labels do not exist.** `skills/cook/references/tdd-loop.md:64` names an absent Age `Router call` section. `skills/cook/references/auto-mode.md:136-138` names absent phase headings. **Fix:** Link to the current Age handoff reference, Press flow, and Cure auto-mode section.

## Simplifications

- Inline `_parse_normalize_args`, `_parse_validate_args`, and `_parse_accept_args` into their only callers.
- Remove the manifest command wrappers after the typed handoff becomes the only live state.
- Keep `_validate_against`. It prevents drift between the normalize and validate commands.
- Keep the decorated command wrappers. Their explicit lazy imports match the other skill bundles.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `cook -> shared` | broken | `contract_handlers.py:31,125-142` uses Publication. Publication permits HTTPS through `publication.py:428-450`. |
| `cook -> schemas` | broken | `workflow.py:1252-1277` ignores validated dependencies from `contracts.py:862-903`. |
| `mold -> cook` | ok | The phase registry declares Mold to Cook. The happy and receipt tests at `test_cook_contract_accept.py:116-133` passed. |
| `cook -> mold` | ok | `_compiled_phase_registry.py:105` declares the PlannerRequest route. `fan-pathway.md:62-71` uses it. |
| `cook -> press` | ok | `_compiled_phase_registry.py:105` declares the CurdResult route. `SKILL.md:69-72` applies its disposition rule. |
| `cook -> age` | broken | The typed route exists, but `auto-mode.md:59-81` contradicts `age/SKILL.md:218-223` on cap ownership. |
| `cook -> cure` | broken | `workflow.py:431-442,1305-1329` defines the binding seam. Cook contradicts Cure on cap and publication scope. |
| `cook -> plate` | broken | `auto-mode.md:25-28` adds publication permission. `cure/SKILL.md:243-245` requires existing permission. |
| `cook -> pasteurize` | ok | `quality-gates.md:52-71` defines the repair dispatch. `pasteurize/SKILL.md:178,289` accepts the Cook continuation. |
| `cook -> cheese` | ok | `fan-pathway.md:23-50` uses continuation. `cheese/SKILL.md:107-120` resolves that handoff. |
| `build -> cook` | ok | `build_pyz.py:334-347` packages Cook commands. The Cook bundle subset passed 37 tests. |

## STE100 status

- `skills/cook/SKILL.md:63,241-250` combines instructions and uses passive voice.
- `skills/cook/references/auto-mode.md:86` uses passive voice.
- `skills/cook/references/fan-pathway.md:248,387` uses passive voice.
- `skills/cook/references/package-report.md:70` uses passive voice.
- `skills/cook/references/quality-gates.md:29` uses passive voice.
- `skills/cook/references/tdd-loop.md:140` combines two instructions.
