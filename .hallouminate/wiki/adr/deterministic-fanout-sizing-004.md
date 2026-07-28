# ADR-004 — Curd blocks declare a size estimate; the validator gates it

**Status:** accepted · **Spec:** `deterministic-fanout-sizing`

## Context

`src/fanout/curd_block.py` validates disjointness, wave size (`MAX_WAVE_SIZE=4`),
required keys, and decomposer provenance. It never asks whether a curd is **worth
a dispatch**.

That is the same defect this spec fixes one level up in the review router:
counting units without measuring surface. It produced a real 8-curd block for
this very spec, whose second wave contained a curd editing **three lines of a
dict** — a fresh coder agent whose context setup costs more than the edit it
performs.

## The measurement problem

`review_surface` cannot be reused directly. At decomposition time **the diff does
not exist yet**.

Sizing a curd from the LOC of the files it touches was tried and is disproven:
`scripts/build_pyz.py` is 335 lines while the edit against it is 3. File size
carries no information about edit size.

## Decision

The curd-block schema gains a **declared** estimate, mechanically gated.

- `est_edit_lines: int` — a required curd key, covering source **and** tests: the
  whole dispatch's work.
- `MIN_CURD_SURFACE = 25` — a curd below the floor is a validation **error**
  naming it a merge candidate.

One check. A block of eight one-liners fails eight times and must merge until
every curd clears the floor, which is exactly the failure mode being fixed. A
wave-total and a wave-balance check were both considered and dropped as
unnecessary once the per-curd floor exists.

The floor value is a judgment call `<speculative>` — below roughly 25 lines of
edit, dispatch overhead exceeds the work — and is a named tunable constant, not a
literal.

## Why this does not contradict ADR-003

[ADR-003](./deterministic-fanout-sizing-003.md) rejects judgment in the sizing
path. The distinction is the existence of the artifact being sized:

| | artifact | discipline |
|---|---|---|
| `/age` router | the diff **exists** | measure it; judgment is unnecessary and harmful |
| curd decomposition | the diff **does not exist yet** | measurement impossible; judgment declares **once**, deterministic code **gates** |

The invariant common to both: *a number that decides how many agents run is
checked by code, never re-derived by an agent at dispatch time.* ADR-003 achieves
that by measuring; this ADR achieves it by freezing a declaration and validating
it. Neither lets an agent decide fan-out width in the moment.

This is also consistent with existing practice — `contract` single-verb-ness is
likewise a judgment the decomposer makes and the validator checks.

## Consequence

The decomposer's producer contract (`skills/cheese/references/decomposer.md`)
must emit `est_edit_lines`. Both doors — `/mold`'s pre-approval dispatch and
`/cook`'s fallback decompose gate — share that contract, so both gain the field.

`est_edit_lines` does not collide with `curd.py`'s manifest-lifecycle vocabulary,
so the AST-derived field-disjointness test in
`tests/fanout/python/test_curd_block.py` continues to hold.

## Related

- [ADR-003](./deterministic-fanout-sizing-003.md) — no LLM in the sizing path
- [fanout-engine-entities](../fanout-engine-entities.md) — the Curd block entity this extends
