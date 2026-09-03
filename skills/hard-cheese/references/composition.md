# Composition — `--hard` and `--auto`

`--hard` and `--auto` pass through the pipeline. They can operate together. The gate runs at one specified point.

## Propagation graph

```
/cheese --hard → /mold → /cook → /press → /age → /cure → /plate --hard
                                                                    │
                                                                    └──► /hard-cheese
```

Each upstream skill passes the flags forward. Only `/plate` calls `/hard-cheese`, after it writes and verifies all required durable artifacts.

## The matrix

| Invocation | Gate fires? | When | Notes |
| --- | --- | --- | --- |
| `/hard-cheese <slug>` standalone | Yes | Immediately. | No pipeline state required. |
| `/plate --hard` commit-only | No | n/a | Nothing is shared for review. |
| `/plate --hard` existing PR | Yes | After final writes and validation, before update. | No layout question. |
| `/plate --hard` new PR | Yes | After topology resolution and final validation, before publication. | Explicit choices and cohesive single changes skip the question. Other shapes can require a question. |
| Upstream `--hard` without terminal `/plate` | No | n/a | The flag remains pending. |

## The single puncture point

Terminal `/plate` pauses `--auto` once. It pauses after final artifact verification and before publication. Intermediate phases do not pause.

## Non-TTY guard

`/hard-cheese` stops when it has no interactive input stream. The gate requires a human response.

Do not pass `--hard` in automated CI. Otherwise, the gate returns `"--hard requires an interactive TTY; remove --hard or run interactively"`.

## Flag precedence summary

- With only `--auto`, run the chain and apply the `/plate` policy for a new pull request.
- With `--hard` and no publication, do not run the gate.
- With `--auto --hard`, resolve the topology and verify final writes. Then run the gate once.
- With `--auto --hard` and no TTY, return the documented error.

The flags have no hidden precedence. This document identifies the only override point.
