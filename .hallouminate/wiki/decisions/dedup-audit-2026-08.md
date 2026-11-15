# Deduplication audit (2026-08) — decisions and non-obvious constraints

Full-src duplication/NIH audit (all 133 Python files under src/). Outcomes: PRs #520–#524, issues #517–#519. Facts below are the ones a future agent would otherwise rederive at real cost.

## cattrs migration of schema_runtime: evaluated and REJECTED — do not re-audit

`schema_runtime.py`'s hand-rolled `_structure`/`_unstructure` (~109 lines) looks like NIH next to the installed cattrs dep, but a spike against cattrs 26.1.0 proved the adapter would be no smaller than the code it replaces:

- The `$.field must be ...` error-path format is test-pinned (`tests/schemas/python/test_schema_runtime.py:446-451` regex-asserts it).
- Blocker is unions: `_structure` implements "try every union member, join all failure texts into `does not match any allowed shape:`". cattrs union dispatch is disambiguation-based (pick one member) — no try-all-and-merge. `X | None` is the dominant pattern across contract classes, so this is the hot path, not an edge case.
- Primitives and nested classes *could* migrate via the `__notes__`-walking pattern `compat.py` already uses — that half is fine; the union half isn't.

`compat.py` uses cattrs where its semantics fit; `schema_runtime.py` hand-rolls where they don't. Both are deliberate.

## compat.load gotcha: collection-level validators suppress per-item problems

`compat.py`'s `_field_problems` `continue`s when a collection-level field validator (e.g. `reject_shared_curd_files`) raises — nested per-item validation for that attribute is skipped, silently dropping per-item errors whenever a collection-level error coexists. This is why `validate_decomposition.py` loads each curd individually via `load(c, DecomposedCurd)` and runs cross-curd disjointness as a separate `load({"curds": ...})` pass filtered by `"curds[" not in problem`.

## Decomposition wiring is NOT delegated to WiringRow — permanent scope boundary

`WiringRow.status` is required, but decomposition-stage wiring rows never carry `status` (locked by `test_non_dict_wiring_entry_does_not_crash`). Delegating decomposition wiring validation to `Decomposition.wiring`/`WiringRow` flips accepts to rejects. `wiring.graph_errors` stays local in the fanout validator.

## manifest.py is a LOSSY mirror of validate_manifest.py — migration order matters

`easy_cheese_schemas/manifest.py` claims to mirror `fanout/validate_manifest.py`, but nine cross-field `agent_resolution` rules (`validate_manifest.py:227-315`) plus the post-review phase requirements exist ONLY in the fanout validator, and `RunManifest` has zero production consumers (the fanout validator is the live one, via `manifest_update.py`). Swapping in `compat.load(strict=True)` today silently drops those rules. Order: port the nine rules into `manifest.py` as attrs validators → wire `manifest_update.py` through `compat.load` → retire the fanout copy.

## Raw-source fanout scripts now require runtime deps

Since PRs #523/#524, `shared/manifest_io.py` and `fanout/validate_pr_plan.py` import `easy_cheese_schemas` (→ attrs/cattrs). The `install-script` CI job installs `requirements/runtime.txt` before the `pr_plan_to_branches` bats step for this reason. The formerly dep-free raw-source invocation path was never a documented contract (contrast `taste_test.py`, which explicitly declares stdlib-only and remains so).

## Known drift, needs design (open as of 2026-08-28)

- `TestContract` exists three times with real drift: `taste_test.py:69-148` (stdlib dataclass — stdlib-only is a locked constraint there), `gates.py:235-246` (attrs, wired), `contracts.py:2191-2200` (`TestContractRow`, renamed fields). `taste_test.py:26` admits a `"guard"` mode neither enum counterpart can represent. Reconcile the enums; do not merge the modules across the stdlib-only boundary.
- Byte-identical attrs validator helpers (`_non_empty_string` etc.) across five schemas modules (`manifest.py`, `curd.py`, `gates.py`, `pr_plan.py`, `decomposition.py`) → extract to a private `_validators.py` (~60 lines, near-zero risk).
- Two near-duplicate traversal denylists (`write_handoff_artifact.py`, `hard_cheese/append_attempt.py`) intentionally NOT merged into `cli.reject_path_segment` — they use a different predicate (no `:` check); reconcile deliberately or leave.

## Locked constraints confirmed during the audit

- `skills/*/commands.py` COMMANDS manifests must stay literal tuples — AST-asserted by `tests/python/test_bundle_commands.py:131-154` (commit 129cf61). Never factor them.
- `wheypoint/legacy.py` deliberately parallels `shared/handoff.py` — grammars differ (legacy accepts `gated:` and fenced slug wrapper); documented at legacy.py:62.
- Markdown renderer (`html_report.py`), stopword slugify, severity ladder: keep — tracked as issues #517–#519 with rationale.
