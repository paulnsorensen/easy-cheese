# Cheese area review

## Verdict

**reject**

The review found two blockers, seven high findings, four medium findings, and no low findings.
The focused tests report 16 passes.
The generated guidance check passes.
The passing tests do not resolve the contract conflicts below.

## Blocker

- **[correctness:blocker] A classified Mold intent cannot reach the normal Mold dialogue.** <certain> `skills/cheese/SKILL.md:43-47` applies Cook's fast-path check to `mold`. `skills/cheese/references/escalation.md:8-26` then enters mini-spec mode or asks for Cook-level clarity. `skills/cheese/references/classification.md:75-100` classifies fuzzy work as `mold`. `skills/mold/SKILL.md:12-13,45-51` reserves mini-spec mode for clear Cook work. **Fix:** Apply Cook's fast-path check only to `cook`. Dispatch a `mold` intent to Mold's user mode.
- **[spec:blocker] Active guidance restores the obsolete `CurdBlock` as production state.** <certain> `skills/cheese/references/decomposer.md:3-29` requires Mold and Cook to produce the block. `skills/cook/SKILL.md:92-99` links that reference from its active fan path. `skills/mold/references/curdle.md:380-386` forbids this artifact outside explicit migration. `skills/cheese/references/schema-intertwine.md:9-16,23-30` lists the typed `PlannerRequest`, `CurdPlan`, and `CurdResult` path. **Fix:** Replace `decomposer.md` with typed planner guidance. Move legacy instructions under the retained Ultracook references.

## High

- **[spec:high] Three fast-path definitions use different eligibility rules.** <certain> `skills/cheese/references/classification.md:90-100` defines three checks. `skills/cheese/references/routing-receipt.md:41-46` requires a file or behavior and no design question. `skills/cook/SKILL.md:47-54` adds four clear values, one or two files, and a proving check. Agents can send ineligible work to Cook. **Fix:** Make Cook own one fast-path contract. Replace each local definition with a link.
- **[telemetry:high] The zero-probe receipt conflicts with mandatory probes.** <certain> `skills/cheese/references/routing-receipt.md:41-48` prohibits reads and wiki grounding on fast routes. `skills/cheese/references/coherence-check.md:9-13` requires a bounded path read. `skills/cheese/SKILL.md:50-58` requires a wiki call before every dispatch. A fast route must skip required work or emit a false count. **Fix:** Skip these probes on fast routes. Otherwise, count them and mark the route as `escalated`.
- **[correctness:high] The classifier has no Affinage intent.** <certain> `skills/cheese/references/classification.md:19-30,120-147` maps pull request references to Age or Plate. `skills/cheese/SKILL.md:179-197` omits Affinage from default targets. `skills/affinage/SKILL.md:30-37` accepts the missing review-feedback route. A request to address review comments can reach the wrong skill. **Fix:** Add an Affinage shape before the generic pull request rules. Add direct routing tests.
- **[spec:high] Publication flags disappear on Mold and debug routes.** <certain> `skills/cheese/SKILL.md:25-30,174-194` promises `--open-pr` and `--hard` propagation. `skills/mold/SKILL.md:127-131` forwards only `--hard`. `skills/pasteurize/SKILL.md:285-290` starts Cook without either flag. A full scan found no `--open-pr` contract in Mold or Pasteurize prose. **Fix:** Define accepted flags on both targets. Forward each flag through every implementation handoff.
- **[security:high] The top-level directive rule can waive resume integrity gates.** <certain> `skills/cheese/SKILL.md:37-40` says live directives override the handoff protocol. `skills/cheese/references/continue-resume.md:14-31,38-57` forbids directives from waiving lineage and integrity gates. An agent can follow the shorter rule and dispatch invalid state. **Fix:** State the integrity exception in `SKILL.md`. Keep the reference as the detailed owner.
- **[encapsulation:high] The planner contract both requires and forbids delegation.** <certain> `skills/cheese/references/agent-resolution.md:84,95-101` assigns Mold to a planner or integrator that agents never delegate. `skills/mold/SKILL.md:21,45-51` requires a fresh planner dispatch. The role contract cannot resolve this worker. **Fix:** Split `planner` from `integrator`. Mark only the integrator as parent-owned.
- **[spec:high] The handback contract overstates phase-registry coverage.** <certain> `skills/cheese/references/handback-contract.md:9-13,67-91` assigns one registry and writer to all phase artifacts. `skills/cheese/references/schema-intertwine.md:9-16` registers only Age, Cook, Cure, Mold, and Press as sources. Affinage and Pasteurize appear in the handback boundary but not the registry. **Fix:** Register their transitions and writer commands. Otherwise, narrow the shared contract to registered phases.

## Medium

- **[correctness:medium] Optional-plugin detection uses names that OMP does not expose.** <certain> `skills/cheese/references/optional-plugins.md:22-25,40-48` requires exact Claude-style MCP names. `skills/cheese/SKILL.md:50-56` repeats one exact name. This OMP session exposes Hallouminate through `xd://mcp__hallouminate_hallouminate_*`. The documented detector therefore selects the fallback while the server exists. **Fix:** Detect semantic capabilities through a host adapter. Keep exact names only as host examples.
- **[assertions:medium] The receipt test does not protect its terminal boundary.** <certain> `tests/python/test_cheese_routing_receipt.py:47-57` checks ordered phrases only. A probe added a duplicate receipt and output after it. The existing helper still passed. **Fix:** Assert one receipt. Assert that no router output follows it before dispatch.
- **[spec:medium] The `artifact` field has three incompatible meanings.** <certain> `skills/cheese/references/handback-contract.md:30-32` defines the consumed prior report. `skills/cheese/SKILL.md:120-122` uses a spec that Mold produced. `skills/cheese/references/continue-resume.md:104-108` uses a pull request reference for Affinage. Consumers must infer field meaning from `next:`. **Fix:** Define one reference union with explicit kinds. Validate each kind for its destination.
- **[deslop:medium] Every Cheese prose file violates the required STE100 rules.** <certain> Examples include `skills/cheese/SKILL.md:136`, `skills/cheese/references/ask-user-question-sources.md:13`, and `skills/cheese/references/handback-contract.md:74`. `skills/cheese/references/routing-policy.md:24-27` adds four long table entries. **Fix:** Rewrite every file listed under STE100 status. Preserve commands, paths, and identifiers.

## Low

none

## Simplifications

- Make Cook own the fast-path contract, and replace four copies with links.
- Replace the active legacy decomposition reference with the typed planner contract.
- Split planner work from parent-owned integration work.
- Give `artifact` one tagged reference contract.
- Put host tool aliases in one capability adapter.
- Add one table-driven routing test for every intent and flag path.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| cheese -> briesearch | ok | `skills/cheese/SKILL.md:46,182` matches the internal context in `skills/briesearch/SKILL.md:10-15`. |
| cheese -> culture | ok | `skills/cheese/SKILL.md:41,46,183` matches both modes in `skills/culture/SKILL.md:9-17`. |
| cheese -> mold | broken | The Cook clarity check blocks normal Mold routing at `skills/cheese/SKILL.md:43-47`. |
| cheese -> cook | broken | Fast-path criteria conflict across `classification.md:90-100`, `routing-receipt.md:41-46`, and `skills/cook/SKILL.md:47-54`. |
| cheese -> pasteurize | broken | Auto mode exists, but `skills/pasteurize/SKILL.md:285-290` drops publication flags. |
| cheese -> press | ok | `continue: press-corrective-cook` matches `skills/press/SKILL.md:130-151`. |
| cheese -> age | ok | `skills/cheese/SKILL.md:195-196` matches `skills/age/SKILL.md:17-42`. |
| cheese -> cure | ok | `skills/cheese/references/coherence-check.md:31-32` requires findings, as `skills/cure/SKILL.md:27-50` expects. |
| cheese -> plate | broken | The router promises publication flags, but Mold and Pasteurize lose them before Plate. |
| cheese -> affinage | broken | Resume support exists, but `classification.md:19-30` has no Affinage intent. |
| cheese -> wheypoint | ok | `continue-resume.md:14,58` matches `skills/wheypoint/SKILL.md:29-44`. |
| cheese -> shared | ok | `escalation.md:34-40` calls the existing `resolve_slug` at `src/easy_cheese/shared/paths.py:411-474`. |
| cheese -> schemas | broken | `handback-contract.md:67-91` names phases that `schema-intertwine.md:9-16` does not register. |
| build -> cheese | ok | `scripts/render_generated_regions.py --check` reports no drift. |
| routing policy -> dotfiles wiki | untested | `routing-policy.md:3-8` names an authoritative corpus that this session does not expose. |

## STE100 status

not compliant

- `skills/cheese/SKILL.md:136` has a procedural sentence longer than 20 words.
- `skills/cheese/references/agent-resolution.md:59` uses passive voice.
- `skills/cheese/references/ask-user-question-sources.md:13` has descriptive sentences longer than 25 words.
- `skills/cheese/references/ask-user-question.md:45-47` uses passive voice.
- `skills/cheese/references/classification.md:105` uses passive voice.
- `skills/cheese/references/code-intelligence-routing.md:23` has a procedural sentence longer than 20 words.
- `skills/cheese/references/coherence-check.md:12` uses passive voice.
- `skills/cheese/references/continue-resume.md:255` uses passive voice.
- `skills/cheese/references/decomposer.md:28-29` uses passive voice.
- `skills/cheese/references/escalation.md:37` has a procedural sentence longer than 20 words.
- `skills/cheese/references/formatting.md:190` has a sentence longer than 25 words.
- `skills/cheese/references/handback-contract.md:74-77` has a sentence longer than 25 words.
- `skills/cheese/references/handoff-gate.md:141` has a procedural sentence longer than 20 words.
- `skills/cheese/references/harness-portability.md:19` has a procedural sentence longer than 20 words.
- `skills/cheese/references/optional-plugins.md:25` has a table sentence longer than 25 words.
- `skills/cheese/references/routing-policy.md:24-27` has four table sentences longer than 25 words.
- `skills/cheese/references/routing-receipt.md:26` uses passive voice.
- `skills/cheese/references/schema-intertwine.md:3` has a sentence longer than 25 words.
