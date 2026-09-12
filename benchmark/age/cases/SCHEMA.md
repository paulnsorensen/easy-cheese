# case.toml manifest schema

Each case lives at `benchmark/age/cases/<case-id>/` and carries three files:

- `case.toml` — the manifest described below, parsed with the stdlib `tomllib`.
- `seed.patch` — a unified diff with `a/…`/`b/…` prefixes, applied from the
  case directory with `git apply` (default `-p1`); it applies cleanly to `base/`
  and touches the file named by `defect.file`.
- `base/` — the pre-defect source tree the patch applies to.

## Fields

| Field | TOML type | Meaning |
| --- | --- | --- |
| `overlap_area` | string | The single review dimension this case exercises (e.g. `correctness`, `security`, `resource-leak`, `error-handling`, `concurrency`, `api-misuse`, `injection`, `off-by-one`, `null-deref`, `type-confusion`). At most one case in the corpus claims a given area. |
| `description` | string | A one-line (no embedded newline) plain-English description of the expected defect, written for a judge to compare findings against. |
| `defect.file` | string | Path to the defective file, relative to that case's `base/` directory. Must be the file `seed.patch` modifies. |
| `defect.line` | integer | The 1-indexed line, in `base/<defect.file>`, at or nearest to which the defect is planted. |

## Example

```toml
overlap_area = "off-by-one"
description = "Loop upper bound excludes the last element, dropping it from the sum."

[defect]
file = "module.py"
line = 5
```

No other top-level or `[defect]` keys are required; loaders should not assume
the absence of additional keys, but curd/3's harness reads only the four
fields above.
