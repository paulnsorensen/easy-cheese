# Composition — `--hard` and `--auto`

`--hard` and `--auto` are both propagated flags. They may coexist. The gate fires at exactly one named point; everywhere else, each flag's normal semantics apply.

## Propagation graph

```
/cheese --hard <input>
        │
        ├──► /mold --hard            (passes --hard through to /cook)
        │       │
        │       └──► /cook --hard    (passes --hard through to /press)
        │
        └──► /cook --hard            (or invoked directly)
                │
                └──► /press --hard
                        │
                        └──► /age --hard
                                │
                                └──► /cure --hard   ← gate fires here
                                        │
                                        └──► /hard-cheese <slug>
```

Upstream skills (`cheese`, `mold`, `cook`, `press`, `age`) are pure pass-through for `--hard`. They never invoke the gate themselves. `/cure` is the only pipeline skill that calls `/hard-cheese`.

## The matrix

| Invocation | Gate fires? | When | Notes |
| --- | --- | --- | --- |
| `/hard-cheese <slug>` standalone | Yes | Immediately. | No pipeline state required. Always idempotent up to the freshness check. |
| `/cure --hard <slug>` interactive | Conditionally | Only when the user picks the share-for-review handoff option. | Picking "re-review" or "stop" → no gate. |
| `/cure --auto --hard --stake medium+` | Yes | When cure reads `next: done` from the age slug it just invoked (chain-clean or two-cure-pass cap reached). Fires from that cure frame *before returning to the caller*. | This is the single sanctioned `--auto` puncture point. |
| `/cure --auto` (no `--hard`) | No | n/a | Existing behaviour preserved. |
| `/cook --hard` (without continuing through cure) | No | n/a | The flag is set but the pipeline stops before the firing point. No gate, no artifact. |
| `/cheese --hard <input>` | No (at routing) | Router only propagates the flag; whatever target it dispatches to carries `--hard`. | Gate still fires at the eventual `/cure` invocation, if any. |

## The single puncture point

`--hard` punctures `--auto` exactly once, at the end of `/cure --auto --hard`'s final pass. Everywhere else, `--auto`'s skip-handoff semantics apply: cook does not pause, press does not pause, age does not pause, the intermediate cure passes do not pause. Only the *terminal* moment — when the chain is about to exit and the user is about to share the code — triggers the gate.

Vibecheck's faithful analogue is "before code is applied" — singular, not per-step.

## Non-TTY guard

If `/hard-cheese` detects it is running without an interactive input stream (no human can respond to the vibecheck prompt), it fails closed and aborts. The puncture only makes sense when a human is in the loop. A vacuous "auto-pass" with no human present would defeat the entire mechanism.

Auto-driven CI pipelines should not pass `--hard`. If they do, the gate aborts with a clear error: `"--hard requires an interactive TTY; remove --hard or run interactively"`.

## Flag precedence summary

- `--auto` without `--hard`: chain runs forward without pause. Unchanged from today.
- `--hard` without `--auto`: gate fires at cure's interactive share-for-review handoff (if selected).
- `--auto --hard`: chain runs forward without pause through all intermediate steps; gate fires once at the terminal moment; user must clear it; chain then exits.
- `--auto --hard` on a non-TTY: aborts with the non-TTY error above.

There is no silent precedence. The only point where one flag overrides the other is named here.
