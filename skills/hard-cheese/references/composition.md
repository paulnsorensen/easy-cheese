# Composition — `--hard` and `--auto`

`--hard` and `--auto` are both propagated flags. They may coexist. The gate fires at exactly one named point; everywhere else, each flag's normal semantics apply.

## Propagation graph

```
/cheese --hard → /mold → /cook → /press → /age → /cure → /plate --hard
                                                                    │
                                                                    └──► /hard-cheese
```

Every upstream skill is pass-through. `/plate` is the only pipeline skill that calls `/hard-cheese`, after it inventories, writes, and reads back all required durable artifacts.

## The matrix

| Invocation | Gate fires? | When | Notes |
| --- | --- | --- | --- |
| `/hard-cheese <slug>` standalone | Yes | Immediately. | No pipeline state required. |
| `/plate --hard` commit-only | No | n/a | Nothing is shared for review. |
| `/plate --hard` existing PR | Yes | After final writes and validation, before update. | No layout question. |
| `/plate --hard` new PR | Yes | After topology resolution, final writes, and validation, before publish. | Explicit choices and cohesive singles skip the question; stack recommendations and ambiguous shapes ask under auto. |
| Upstream `--hard` without terminal `/plate` | No | n/a | The flag remains pending. |

## The single puncture point

`--hard` punctures `--auto` exactly once inside terminal `/plate`, after the final artifact-writing gate and before publication. Intermediate cook, press, age, and cure phases do not pause.

## Non-TTY guard

If `/hard-cheese` detects it is running without an interactive input stream (no human can respond to the vibecheck prompt), it fails closed and aborts. The puncture only makes sense when a human is in the loop. A vacuous "auto-pass" with no human present would defeat the entire mechanism.

Auto-driven CI pipelines should not pass `--hard`. If they do, the gate aborts with a clear error: `"--hard requires an interactive TTY; remove --hard or run interactively"`.

## Flag precedence summary

- `--auto` without `--hard`: chain runs forward; `/plate` applies its new-PR review-shape policy.
- `--hard` without publication: no gate.
- `--auto --hard`: `/plate` resolves topology, verifies final writes, then fires the gate once.
- `--auto --hard` on a non-TTY: aborts with the documented error.

There is no silent precedence. The only point where one flag overrides the other is named here.
