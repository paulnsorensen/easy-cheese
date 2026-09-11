# Spec landing block: the PR shape is settled at mold time

**Status:** landed on branch `feat/landing-shape` (issue #653); spec `landing-shape` in the durable corpus.

## Why

Landing-shape questions (single PR vs stack, how many PRs, whether each layer must be green, where review fixes go) used to surface at `/plate` time, after `/age`, `/cure`, and `/press` had already run, and blocked sessions for tens of minutes each. Nothing upstream recorded the answer, so `/plate`'s "do not ask twice" rule had nothing to reuse on the linear path.

## What

Every Mold spec may carry a closed-class `landing` block in its front matter, next to `gate_applicability`:

```yaml
landing:
  shape: single | orthogonal_flat | stacked_linear | diamond_stack   # absent block = single
  layers: []            # ordered groups of canonical CurdPlan curd ids, one-line flow list
  per_layer_green: required | tip-only
  review_fixes: fold | top-up
```

- `shape` reuses the `PrShape` values by design. `LandingShape` in `easy_cheese_schemas.contracts` mirrors `pr_plan.PrShape` value for value (pinned by a test) because `contracts.py` must stay dependency-free and cannot import `pr_plan.py`. `PlateLayout` is derived: `single` maps to `single`, every other shape to `stacked`.
- `layers` names canonical curd ids from the approved `CurdPlan`, so it is filled at Curdle; a mini-spec keeps `[]`.

## One decoder, three consumers

`easy_cheese_schemas.contracts.parse_landing_mapping(raw) -> Landing` is the only closed-class decoder. Every error starts with the rule id `landing-closed-class`, reports all unknown keys in one message, and escapes echoed values and keys with `repr` so a spec cannot forge an `ERROR:` line. The three consumers are thin adapters:

- `mold.pyz validate-spec --strict` (`validate_spec._typed_landing`) and the cook handoff digest (`taste_test.parse_landing`, front matter only; `curd-count` emits a top-level `landing` key and `handoff.metadata.landing`).
- `cook.pyz accept <pointer> --spec <spec-path>`: `landing_layer_errors(plan, landing)` refuses a plan whose `dependencies` cross the declared layers with three tokens: `landing-layer-order`, `landing-layer-missing-curd`, `landing-layer-unknown-curd`. Without `--spec` the gate does not run and `accept` prints `NOTE: landing layers not checked (no --spec)` on stderr; Mold's hand-off passes `--spec "$SPEC"`.
- `plate.pyz validate-publication` accepts a `landing` key and refuses `landing-topology-mismatch` when `topology` disagrees with the shape; explicit `landing: null` is refused like any non-mapping.

## Gotchas

- A caller-named spec path is read through one bounded reader, `easy_cheese.shared.taste_test.read_spec_text` (regular file only, `MAX_SPEC_BYTES` cap, explicit UTF-8), by both `curd-count` and `cook accept`.
- No handoff fabricates a landing default: an absent key means `single` by rule, so consumers can distinguish "declared single" from "not declared".
- The `landing_layer_errors` check reads declared `dependencies` only; final-state behavior embedded in code stays a review problem.
- Deferred by the spec's non-goals: repo hook exceptions (issue #653 ask 4) and affinage worktree-branch resolution.
