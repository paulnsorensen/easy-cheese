# Mold review

## Verdict

`reject`

## Findings

### Blocker

- **Security:** `skills/mold/references/grounding.md:18-25` selects the first global wiki corpus. It does not match the current repository. This can copy private rationale across repositories. Fix: use the workspace default or match the current repository exactly. Record ambiguity as unavailable.
- **Correctness:** `skills/mold/references/grounding.md:21-22` returns silently when no wiki exists. `skills/mold/SKILL.md:63-65` requires an explicit ledger result. The flow can bypass the gate or stop. Fix: record one named unavailable outcome before return.
- **Correctness:** `skills/mold/references/grounding.md:58` treats `no prior evidence` as `grounding-recorded`. `skills/mold/SKILL.md:63-65` requires citations or `hallouminate: absent`. This intake marker can bypass the required probe. Fix: keep intake and probe records separate.
- **Security:** `skills/mold/references/curdle.md:19-20` uses a user slug without validation. Lines 12-13, 300, and 337 interpolate it into direct paths. A traversal slug can write outside `.cheese`. Fix: call `validate_slug` before every Curdle write.
- **Encapsulation:** `src/easy_cheese/skills/mold/contract_handlers.py:94-95,107-108,130-131` exposes and forwards caller-selected phases. A caller can publish the valid `cook -> cook` route through `mold.pyz`. Fix: remove both phase options. Set `mold -> cook` inside the Mold adapter.
- **Specification:** `skills/mold/SKILL.md:158` requires `agent_resolution` in each canonical Mold spec. Both templates omit it. `src/easy_cheese_schemas/contracts.py:2400-2417,2549-2568` cannot model it. Fix: add the shared block to both templates and typed contracts. Make strict validation require it.
- **Correctness:** The normal flow in `skills/mold/SKILL.md:21-24,127-134` never invokes `mold.pyz publish`. `skills/mold/references/commands.md:11` only lists the command. Cook requires the returned pointer at `skills/cook/SKILL.md:35-36`. Fix: publish the validated plan before handoff. Pass the returned pointer to Cook.
- **Specification:** `skills/mold/SKILL.md:98-102` permits only `tracer` and `contract-matrix` modes. Curdle and executable rules also permit supplementary `guard` rows. See `skills/mold/references/curdle.md:101-106` and `tests/python/test_mold_taste_test.py:456-497`. Fix: document `guard`. Keep one executable red mode mandatory.

### High

- **Correctness:** Strict validation accepts an unknown source marker at `src/easy_cheese/skills/mold/validate_spec.py:637-645`. Taste classification rejects the same document at `src/easy_cheese/shared/taste_test.py:549-570`. The probe used `source: mold-handshake # comment`. Fix: share one source policy. Reject unknown sources during strict validation.
- **Assertions:** `tests/python/test_mold_contract_publish.py:101-106` does not assert route or schema fields. The test passes with the valid `age -> cure` route. Fix: assert exact source, destination, schema URI, payload, and pointer fields.
- **Complexity:** `src/easy_cheese/skills/mold/validate_spec.py:223-730` repeats raw parsing and typed reconstruction. It also repeats closed classes from shared rules and schema enums. This creates several authorities for one document. Fix: keep one schema constructor and one enum authority. Leave only Markdown shape extraction in the adapter.

### Medium

- **Efficiency:** Each probe repeats `list_corpora` at `skills/mold/references/grounding.md:14-25`. Decision points call the probe again at lines 33-40. Fix: retain the selected corpus for one Mold episode. Repeat discovery only after an unavailable result or registry change.

### Low

- **Complexity:** `src/easy_cheese/skills/mold/gate_graph.py:227-276` reads and validates `--state`, then discards it. `skills/mold/references/gate-graph.md:23-24` confirms that state cannot change output. Fix: remove the option until state changes the graph.

## Simplifications

- Extract one local `_read_json_object` helper for `publish_main` and `migrate_main`.
- Generate the handshake checklist region from `GATE_MODEL`. Keep `mold.dot` under the same generator.
- Remove gate graph narration and hard-coded gate counts from docstrings.
- Make the typed Mold document the only semantic parse result. Reuse it in validation and taste checks.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| `mold -> shared` | broken | `contract_handlers.py:94-95` leaks phase ownership. Validator and taste source policies also disagree. |
| `mold -> schemas` | ok | `validate_spec.py:38-55,517-632` uses typed rows and validates `ui_surface`. |
| `mold -> cook` | broken | The flow omits `publish`, so Cook receives no canonical `HandoffPointer`. |
| `cheese -> mold` | ok | `skills/cheese/SKILL.md:43-46` routes tier-one mini-spec work to Mold. |
| `mold -> cheese` | broken | The emitted spec cannot carry the required shared `agent_resolution` block. |
| `mold -> briesearch` | ok | `skills/mold/references/validate-cycle.md:11-16` requests framed external evidence. |
| `culture -> mold` | ok | `skills/mold/references/mini-spec-mode.md:62-66` records tier-two provenance. |
| `mold -> hard-cheese` | ok | `skills/mold/SKILL.md:121-125,131` preserves `--hard` for the final gate. |
| `mold -> spec-verify` | ok | `skills/mold/references/curdle.md:357-359` defines the optional skill probe. |
| `build -> mold` | ok | Generated commands match `COMMANDS`. Three bundle publication tests pass. |

## STE100 status

Noncompliant.

- `skills/mold/SKILL.md:3,12,19,24,131` joins instructions and exceeds sentence limits.
- `skills/mold/references/context-budget.md:26,30,43-44` joins instructions inside table cells.
- `skills/mold/references/curdle.md:15,20,300,357-359,388-397` uses fragments, passive voice, and two handoff terms.
- `skills/mold/references/evals.md:31-32` contains long conditional instructions.
- `skills/mold/references/gate-graph.md:3-8,23-24` uses passive constructions and sentence fragments.
- `skills/mold/references/grounding.md:50` uses passive voice.
- `skills/mold/references/handshake.md:151` uses past tense.
- `skills/mold/references/mini-spec-mode.md:10,31` uses passive voice and the alternate term `behaviour`.
- `skills/mold/references/modes.md:24,40` uses passive voice.
- `skills/mold/references/shape-check.md:16` uses a sentence fragment.

## Verification

- The focused test set reports 191 passed and 4 skipped.
- Graphviz absence skips one binary render test.
- Missing build tools skip three bundle tests in the focused run.
- A second bundle run installs `requirements-build.txt` and reports 3 passed.
- Runtime probes confirm the strict-source disagreement and the valid alternate publication route.
