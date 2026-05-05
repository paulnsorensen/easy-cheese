# The Validate Cycle

Any mode can invoke a Validate Cycle. Always **announce the cycle** before dispatching — the announcement is part of the discipline.

## The frame

```text
Launching a validate cycle on hypothesis: "<single declarative sentence>"

Plan:
  /briesearch  — fetch evidence
  Judge        — support, contradict, or refine?
  Settle       — accept, revise, or reject. Continue from current mode.
```

A bare `/briesearch` call without this frame is discouraged. The frame forces commitment to a hypothesis plus a judgment step.

## Outcomes

| Outcome | Meaning | Next action |
| --- | --- | --- |
| **SUPPORTED** | Evidence aligns with the hypothesis | Promote to a decision |
| **CONTRADICTED** | Evidence disagrees | Mark `[CONFLICT <id>]`, revise or abandon |
| **REFINED** | Evidence partially aligns | Restate with new precision and re-validate or accept |

Diagnose's parallel hypothesis ranking IS this cycle, parallelized.

## Budget

- **Cap:** 2 `/briesearch` calls per mold session unless the user requests more.
- Cycles backed by `cheez-search` evidence alone are unbudgeted — they do not count toward the cap.

## When to skip

- The claim is already grounded (a `cheez-read` or earlier cycle settled it).
- The decision is reversible and small — running a cycle costs more than just trying it.
- The user explicitly said "skip the cycle".

## Logging

Every launched cycle is logged in the mold state file:

```yaml
validate_cycles:
  - id: vc-1
    hypothesis: "Express's Router supports per-route middleware arrays"
    outcome: SUPPORTED
    sources: [Context7]
  - id: vc-2
    hypothesis: "We can hot-swap the auth middleware without restart"
    outcome: CONTRADICTED
    conflict_id: cf-1
```

Open hypotheses (no `outcome:`) block Curdle until they settle or are explicitly accepted as `[TBD]`.
