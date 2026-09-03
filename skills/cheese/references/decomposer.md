# Decomposer curd-block schema

The curd block is the specification-locked decomposition artifact.
Both `/mold` and `/cook` produce it.
Consumers cannot identify which skill produced it.

```yaml
curds:
  - slug: <kebab>
    contract: <one paragraph>
    files: [<disjoint allowlist>]
    test_target: <command or test id>
    acceptance: [<verifiable checks>]
    seed: [<frozen interfaces this curd implements>]
    est_edit_lines: <int, required — declared estimate of edit lines, source
                     plus tests, the whole dispatch's work>
waves: [[<slug>, ...], ...]   # <=4 slugs per wave
decomposer: {source: mold | cook, model: <id>, prompt_version: <hash>}
```

## Producers

- **`/mold` curdle step** — dispatch the decomposer with the draft specification.
  Add the resulting curd block to the approved specification.
- **`/cook` fallback decompose gate** — dispatch a fresh-context decomposer for a large un-curded task.
  Gate implementation on the resulting wave plan.

Both producers must emit a block that satisfies the schema above verbatim —
field names are locked and must not drift per-caller.

## Validator

`src/easy_cheese/shared/fanout/curd_block.py` is the single source of truth for parsing and
validating a curd block:

- `validate_curd_block(block) -> list[str]` returns every schema violation.
  An empty list means valid.
  Each curd needs `slug`, `contract`, `files`, `test_target`, `acceptance`, `seed`, and `est_edit_lines`.
  The `files` values must be pairwise disjoint.
  Each `waves` entry has at most four known slugs.
  Each `est_edit_lines` value is an integer at or above `MIN_CURD_SURFACE` (25).
  A smaller curd fails because dispatch setup costs more than the edit.
- `parse_curd_block(source: dict | str) -> dict` — parses a YAML/JSON string
  (or accepts an already-parsed dict), validates it, and raises
  `CurdBlockError` with every violation joined into one message on any
  failure. Never returns a falsy value in place of raising.

This schema differs from `src/easy_cheese/shared/fanout/curd.py`.
That module validates an `/ultracook` run manifest after a run starts.
The curd block is the decomposition artifact before a run.
The two schemas share no field names.
