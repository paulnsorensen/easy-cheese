# Decomposer curd-block schema

The curd block is the spec-locked decomposition artifact both `/mold`'s curdle
step and `/cook`'s fallback decompose gate produce. Same schema both doors —
consumers cannot tell which door wrote it.

```yaml
curds:
  - slug: <kebab>
    contract: <one paragraph>
    files: [<disjoint allowlist>]
    test_target: <command or test id>
    acceptance: [<verifiable checks>]
    seed: [<frozen interfaces this curd implements>]
waves: [[<slug>, ...], ...]   # <=4 slugs per wave
decomposer: {source: mold | cook, model: <id>, prompt_version: <hash>}
```

## Producers

- **`/mold` curdle step** — dispatches the decomposer on the draft spec text
  during design; the resulting curd block is embedded into the approved spec
  artifact.
- **`/cook` fallback decompose gate** — when `/cook` receives an un-curded
  task that sizes above the linear threshold, it runs the same decomposer
  inline and gates on the resulting wave plan before implementing.

Both producers must emit a block that satisfies the schema above verbatim —
field names are locked and must not drift per-caller.

## Validator

`src/fanout/curd_block.py` is the single source of truth for parsing and
validating a curd block:

- `validate_curd_block(block) -> list[str]` — every schema violation, empty
  list means valid. Checks: every curd has slug/contract/files/test_target/
  acceptance/seed; `files` are pairwise disjoint across every curd in the
  block; every `waves` entry has at most 4 slugs and only references slugs
  present in `curds`.
- `parse_curd_block(source: dict | str) -> dict` — parses a YAML/JSON string
  (or accepts an already-parsed dict), validates it, and raises
  `CurdBlockError` with every violation joined into one message on any
  failure. Never returns a falsy value in place of raising.

This is a **distinct concept** from `src/fanout/curd.py`, which validates an
`/ultracook` *run manifest*'s in-flight curd records (`behavior` /
`acceptance_criterion` / `status` / `retry_count`) once a run already exists.
The curd block here is the pre-run decomposition artifact; the two schemas
are deliberately not merged and share no field names.
