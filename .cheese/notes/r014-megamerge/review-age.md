# Age Area Review

## Verdict

reject

## Blocker

- `src/easy_cheese/skills/age/review_lock.py:63-67,172-181` permits Git text conversion during the review lock. Git can run a configured `textconv` command with reviewer privileges. A behavior probe created the configured marker during `review-lock`. Fix: add `--no-textconv` and disable command-valued Git helpers.
- `skills/age/SKILL.md:111-115,149-154` gives Age and the writer ownership of the final report. A failed gate can leave the prewritten report for Cure at `SKILL.md:95`. The writer can also prepend a second preamble. Fix: use a separate body file and let the gated writer create the final report.
- `src/easy_cheese/skills/age/review_lock.py:50-52,157-160,204-209` treats every Git detection error as a non-repository. The gate then permits the report write. Fix: distinguish a non-repository from Git errors, and fail closed on errors.
- `src/easy_cheese/skills/age/review_lock.py:161-182` omits staged content when the repository has no `HEAD`. Plain `git diff` compares the worktree to the index. Re-staged changes can keep the same digest. Fix: hash the index against the empty tree and hash the worktree delta.
- `src/easy_cheese/skills/age/review_lock.py:55-58,93-96,178-182` excludes every `.cheese/age/*.md` file. This set includes the packet required by `skills/age/references/packet.md:3-4,31-32`. The gate can certify a report after its evidence changes. Fix: hash the packet before dispatch and exclude only the lock and final report.

## High

- `skills/age/SKILL.md:113-115,168-181,186-209` gives a low-only review incompatible outcomes. Age selects contained low findings but sets `next: done` without a medium finding. It can also remove selected lows from the durable report. Fix: resolve one selection, retain all durable findings, and derive `next` from that selection.
- `skills/age/SKILL.md:218-223` assigns the Cure pass counter to each Age invocation. `skills/age/references/handoff-detail.md:104-105` assigns that counter to the fixed Cook chain. Fix: keep the counter in Cook and let Age report only the current result.
- `skills/age/SKILL.md:112-116,151-155` drops required upstream state. The command hardcodes an empty artifact and omits baseline. `skills/age/references/report-example.md:39-44` requires both values when available. Fix: resolve and pass the consumed artifact and copied baseline.
- `skills/age/SKILL.md:157-166` documents a finding syntax that the selection parser rejects. The syntax omits the list marker and location backticks required by `src/easy_cheese/shared/findings.py:49-52`. Fix: document the exact parser syntax and add a parser contract test.
- `skills/age/SKILL.md:92-95` requires unresolved Press items in the Age report. `src/easy_cheese/shared/read_handoff_slug.py:25-37` returns only preamble fields. A body probe returned none of the Press findings. Fix: locate the Press artifact and read its complete body.
- `skills/age/references/fan-out.md:19-24` imports `src.fanout.age_route`, which does not exist. The live module is `easy_cheese.shared.fanout.age_route`. Fix: use the live import with the repository `src` directory on `PYTHONPATH`.
- `skills/age/references/fan-out.md:59-69` requires multi-dimension rows without a size limit. `skills/age/references/sub-agent-gate.md:9-28` permits one dimension and limits every response to about 2 KB. Fix: define one bounded exception for Age lens workers.
- `skills/age/references/packet.md:11,15,25-27` points to three missing section anchors. It also requests H2 dimension headings, but `dimensions.md` uses H3 headings. Fix: use the existing section names and exact H3 boundaries.
- `skills/age/references/fan-out.md:96-104` keeps a finding when its verifier cannot settle the claim. `skills/age/SKILL.md:179-180` requires more evidence or removal. Fix: keep unresolved claims outside the findings list until evidence confirms them.
- `skills/age/references/voice.md:24-28` tells Age to apply inexpensive review findings. `skills/age/SKILL.md:15,235-237` reserves every production edit for Cure. Fix: scope the apply rule to write-enabled phases.
- `skills/age/references/dimensions.md:150,260-272,397-398` assigns duplicate defects to different dimensions. The conflicts affect silent failures and existing helper reuse. Fix: keep one ownership rule in the boundary table.
- `skills/age/references/deslop-rust.md:38-41,103-112,140-147` gives incorrect error and assertion advice. `.expect()` panics, a regex literal is not a compile-time guarantee, and `assert_eq!(x, None)` requires extra traits. Fix: use `?` for propagation and choose assertions from the contract.
- `skills/age/references/deslop-rust.md:227-247,459-490,561-574` gives conflicting lint advice. It permits and rejects the same `unwrap_used` suppression. Its `RUSTFLAGS=-D warnings` replacement has the same failure mode as `deny(warnings)`. Fix: use one context-based rule and remove the equivalent replacement.
- `skills/age/references/deslop-shell.md:20-50,113-125,194-205` presents Bash rules as universal shell rules. `[[ ... ]]` fails in POSIX shell, strict mode can break sourced files, and `exit` can terminate the caller. Fix: detect the shell and use `return` in sourced functions.
- `skills/age/references/deslop-typescript.md:81-109,186-201` labels behavior changes as clean. Truth testing rejects an empty string, `void` does not handle rejection, and `structuredClone` changes clone semantics. Fix: preserve null semantics, handle rejection, and check clone requirements.
- `src/easy_cheese/skills/age/review_lock.py:50-183,239-272` uses the supplied directory as the repository root. A nested-directory probe duplicated the path and blocked a valid report. Tracked files outside that directory can also escape the lock. Fix: resolve the top-level repository before every digest and artifact path.
- `src/easy_cheese/skills/age/review_lock.py:186-200,239-242` follows symlinks in the lock path. A tracked `.cheese/age` symlink can redirect the write outside the repository. Fix: reject symlink components and use an atomic no-follow write.

## Medium

- `skills/age/SKILL.md:3-8,100-101` scopes a single-dimension request, but the flow reviews every dimension. Fix: review every requested dimension and use all ten only by default.
- `skills/age/SKILL.md:19-21,40-42` defines `--hard` behavior but omits the flag from both invocation forms. Fix: add `[--hard]` to both forms.
- `skills/age/SKILL.md:176-180,248` defines two finding confidence vocabularies. One set omits `don't know`, but the later rule includes it. Fix: reserve `don't know` for report-level gaps.
- `skills/age/SKILL.md:89,270-273` passes router effort but also fixes every Age worker at high effort. Fix: let the local table accept the router's low, medium, or high value.
- `skills/age/SKILL.md:151-166,267-275` requires an `agent_resolution` block in every canonical artifact. `skills/age/references/report-example.md:39-84` has no such block. The writer command also has no field for it. Fix: add a body section and show it in the report skeleton.
- `skills/age/references/fan-out.md:28-46` says returned `n` is only 1, 2, or 5. Override promotion sets `n` to the final lens count and can return 6 or 9. Fix: distinguish the base tier from the returned count.
- `skills/age/references/fan-out.md:68-71,93-95` starts one verifier for each candidate finding. This creates an extra agent call for every finding. Fix: verify bounded batches with one result object per claim.
- `skills/age/references/dimensions.md:32-38,91-100` starts two Python commands and one dependency traversal for each finding. Fix: add one batch grading command and reuse dependency evidence by file.
- `skills/age/references/packet.md:12-14` treats one keyword search as a project helper inventory. Projects can use other roots and names. Fix: detect source roots and verify task-specific helper candidates.
- `skills/age/references/deslop-go.md:31-59,81-84` makes context rules absolute. The Go guide permits more named-result cases, and interfaces are not reference types. Fix: separate named results from naked returns and describe interface values correctly.
- `skills/age/references/deslop-python.md:31-53,71-87` changes valid semantics and states false guarantees. Truth testing differs from a `None` check, logging can require lazy formatting, and dataclasses do not validate types. Fix: state each precondition and include valid alternatives.
- `skills/age/references/deslop-typescript.md:131-168,221-244` gives false bundle and lint mappings. Named barrel imports do not load every export, and the cited callback rule does not cover `catch` clauses. Fix: state tree-shaking conditions and cite the applicable lint rule.
- `skills/age/references/report-example.md:36-57` uses a stale Cook path and two overlong placeholders. Fix: change the path to `../../cook/` and split each placeholder into short instructions.
- `skills/age/references/handoff-detail.md:18-35,53-56` indents the high floor below the medium floor. The menu no longer has four peer options. Fix: outdent the high option.
- `tests/python/test_glossary_consumers.py:25-41` accepts a negated consumer rule. It checks only path and skill-name substrings. Fix: assert exact positive read and use directives, and reject nearby negation.
- `skills/age/references/commands.md:3,7` says every command supports `--help`. The `age-route --help` behavior probe returned status 2 because it parsed the flag as JSON. Fix: add help handling or document the JSON-only command.

## Low

- `skills/age/references/dimensions.md:22-29` says to merge severity contributors by maximum. The same section and runtime apply both bumps in sequence. Fix: state the sequential rule and blocker cap.
- `skills/age/references/commands.md:16` says `review-lock` records or verifies a digest. The command only records it at `review_lock.py:239-258`. Fix: describe capture only.
- `src/easy_cheese/skills/age/review_lock.py:93-154,193-206` hashes all ignored `.cheese` content for each lock operation. Unrelated historical files add two complete reads per review. Fix: hash a slug-specific input manifest.
- `src/easy_cheese/skills/age/review_lock.py:204-223` computes the complete digest before it checks the lock file. A missing or invalid lock pays for five Git commands first. Fix: validate the lock before the digest.
- `skills/age/references/deslop-shell.md:68-85,210-229` recommends external `fd` before its standard `find` solution. Fix: prefer the standard command unless the project declares `fd`.
- `skills/age/references/handoff-detail.md:90-109` retains retired `/ultracook` terms and undefined `curds`. Fix: name only the current Cook worker flow.
- `skills/age/references/packet.md:3-7` says packet rebuilding creates stale context and avoids YAGNI. Rebuilding prevents stale context. Fix: state that purpose directly.
- `skills/age/references/sub-agent-gate.md:3-4,42,50-55` uses undefined size terms and a missing section link. Fix: define the unit and link to `SKILL.md § Sub-agent fan-out`.

## Simplifications

- Remove unused `--comprehensive` from `skills/age/SKILL.md:20`. All default reviews already cover every dimension.
- Move the shared voice rules at `skills/age/references/voice.md:1-5` to the shared Cheese references. Seven other skills import this Age file.
- Move the shared gate at `skills/age/references/sub-agent-gate.md:1-7` to the shared Cheese references. Keep only Age router rules in this area.
- Remove the deferred v2 design at `skills/age/references/dimensions.md:411-426`. The live v1 rubric does not use it.
- Keep the router topology in one file. `fan-out.md:28-46` and `sub-agent-gate.md:50-55` currently repeat it.
- Generate the packet from named sections. This removes the manual extraction rules at `skills/age/references/packet.md:9-27`.
- Batch severity calculation and verifier work. This removes repeated commands without weakening independent verdicts.
- Keep the worked report once. Replace the repeated findings at `skills/age/references/report-example.md:59-77` with placeholders.
- Put the shared catalog preamble in `dimensions.md`. The five language catalogs repeat the same contract.
- Use one binary Git runner. `review_lock.py:50-89` now splits execution between shared and private runners.
- Remove the whole-file glossary test at `tests/python/test_glossary_consumers.py:25-34`. A stronger Flow test subsumes it.
- Add one lock-digest test helper for `tests/python/test_age_review_lock.py:54-94`. The tests repeat the same JSON parsing.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `age -> shared` | broken | `SKILL.md:112-115` loses handoff state. `fan-out.md:19-24` names a missing router import. `review_lock.py:50-209` also fails open. |
| `cook -> age` | broken | `SKILL.md:218-223` counts Cure passes in Age. `handoff-detail.md:104-105` assigns the count to Cook. |
| `affinage -> age` | broken | `affinage/SKILL.md:139-149` dispatches generic workers. `age/sub-agent-gate.md:52-55` claims that Affinage uses the Age router. |
| `age -> cure` | broken | `SKILL.md:92-95,186-209` loses Press findings and gives low findings incompatible handoff states. |
| `build -> age` | broken | The generated command exists, but `commands.md:3` promises unsupported `age-route --help` behavior. |

## STE100 status

not compliant

- `skills/age/SKILL.md:128,208,218` combines many instructions and uses undefined terms.
- `skills/age/references/commands.md:10-18` uses long noun clusters.
- `skills/age/references/deslop-go.md:4` uses the undefined term `AI tell`.
- `skills/age/references/deslop-python.md:58-68,243-247` uses conversational phrases and an undefined personal label.
- `skills/age/references/deslop-rust.md:232-270,342-360,503-524` uses metaphors and undefined abbreviations.
- `skills/age/references/deslop-shell.md:7,50-54,127-140,220-252` uses idioms and undefined abbreviations.
- `skills/age/references/deslop-typescript.md:5,131,141,186` uses undefined idioms as rule names.
- `skills/age/references/dimensions.md:156-169,224-226,320-346` uses undefined abbreviations and coined terms.
- `skills/age/references/fan-out.md:64,101` uses dense compound terms instead of direct instructions.
- `skills/age/references/handoff-detail.md:68,90-109` uses retired and undefined workflow terms.
- `skills/age/references/packet.md:3-7,15-17` gives a false purpose statement and uses dense noun clusters.
- `skills/age/references/report-example.md:54,57` puts several conditional instructions in one placeholder.
- `skills/age/references/sub-agent-gate.md:3-4,42,50-55` uses unsupported jargon and a broken term reference.
- `skills/age/references/voice.md:3,23-29,31-40` uses idioms and abstract noun clusters.
