# Press telemetry path classification and attempt bounds

`press-telemetry` (`src/easy_cheese/shared/fanout/press_telemetry.py`) classifies each `changed_files` entry as `tests`, `metadata`, or `production_source` and derives `boundary_consistent` from that. Three non-obvious rules came out of the PR #580 review (`78b8e929`).

## Keep the trailing slash through normalization

`PurePosixPath("tests/").as_posix()` returns `tests`. `git status --porcelain` prints an untracked directory as `?? tests/`, so a request that copies porcelain output loses the directory marker if the path is normalized naively. `_changed_paths` re-appends `/` when the raw entry ended with one, and `classify_path` treats every part of a slash-terminated path as a directory segment. Without both halves, `tests/` classifies as `production_source` and a tests-only attempt reports `boundary_consistent: false`.

## Directory rules scan every ancestor

Both the test-dir and metadata-dir rules test `pure.parts[:-1]` (or all parts for a directory entry). Never index `parts[0]`: `"."` and `"./"` have empty `parts` and raise `IndexError`, which `json_command` does not catch, so the CLI dies with a traceback instead of `ERROR:` exit 1. `_changed_paths` rejects empty-normalized entries before classification.

## One attempt bound, owned by press_route

`MAX_ATTEMPTS = 3` lives in `press_route.py`; `press_telemetry.py` imports it. The import direction is fixed (telemetry depends on route for `coerce_outcome`), so the constant cannot live in telemetry without a cycle. `_check_repair_cycles` rejects `repair_cycles >= MAX_ATTEMPTS`, so `press-route` and `press-telemetry` fail the same over-counted attempt instead of routing it and then silently skipping the record.

## Exception contract for the shared fanout CLIs

`json_command` catches `TypeError` and `ValueError`. Public helpers such as `coerce_outcome` raise `ValueError` for every rejected input so a direct caller can catch one type. Do not re-wrap `TypeError` in a `*_cli.py` module.

## basedpyright and key-set checks

Compare request keys against a plain `set`, not a `frozenset`. `set(payload) != frozenset(...)` trips `reportUnnecessaryComparison` under the repository's basedpyright config; the sibling `press_route_cli.py` uses `{...}` literals for this reason.

## Deferred

- The telemetry request is agent-retyped; nothing cross-checks it against `route.json` or git ([#611](https://github.com/paulnsorensen/easy-cheese/issues/611)).
- `attempt` is always `repair_cycles + 1`; it stays a required field as a boundary cross-check until the validator toolkit is promoted ([#612](https://github.com/paulnsorensen/easy-cheese/issues/612)).
