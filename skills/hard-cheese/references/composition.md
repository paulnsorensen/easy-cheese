# Composition — `--hard` and `--auto`

`--hard` and `--auto` pass through the pipeline. They can operate together. The gate runs at one specified point.

## Propagation graph

```
/cheese --hard → /mold → /cook → /press → /age → /cure → /plate --hard
                                                                    │
                                                                    └──► /hard-cheese
```

Each upstream skill passes the flags forward. Only `/plate` runs `/hard-cheese`. `/plate` first writes and verifies every required durable artifact.

## The matrix

| Invocation | Does the gate run? | When | Notes |
| --- | --- | --- | --- |
| `/hard-cheese <slug>` standalone | Yes | Immediately. | No pipeline state is required. |
| `/plate --hard` commit-only | No | n/a | Nothing is shared for review. |
| `/plate --hard` existing PR | Yes | After final writes and validation, before update. | No layout question. |
| `/plate --hard` new PR | Yes | After topology resolution and final validation, before publication. | An explicit choice skips the question. A cohesive single change also skips the question. Other shapes can require a question. |
| Upstream `--hard` without terminal `/plate` | No | n/a | The flag remains pending. |

## The single puncture point

Terminal `/plate` pauses `--auto` once. It pauses after final artifact verification and before publication. Intermediate phases do not pause.

## Non-TTY guard

`/hard-cheese` stops when it has no interactive input stream. The gate requires a human response.

Do not pass `--hard` in automated CI. Otherwise, the gate returns `"--hard requires an interactive TTY; remove --hard or run interactively"`.

## Plate status matrix

`/plate` maps each gate status to one publication decision:

| Gate status | Gate exit status | Plate decision |
| --- | --- | --- |
| `PASS` | `0` | Publish. |
| `LOGGED` | `0` | Publish. The user chose `--no-judge`. |
| `ERROR` | `0` | Ask the user before you publish. The fail-open divergence applies. |
| `FAILED` | non-zero | Do not publish. Stop the chain. |

The exit status is the machine contract. The decision column is the Plate policy.

## Flag precedence summary

- With only `--auto`, run the chain. Then apply the `/plate` policy for a new pull request.
- With `--hard` and no publication, do not run the gate.
- With `--auto --hard`, resolve the topology. Verify the final writes. Then run the gate once.
- With `--auto --hard` and no TTY, return the documented error.

The flags have no hidden precedence. This document identifies the only override point.
