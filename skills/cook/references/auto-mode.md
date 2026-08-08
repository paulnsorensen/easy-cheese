# /cook — Auto mode chain mechanics

Full mechanics for `--auto`, the autonomous-pipeline switch: the per-step chain, the two-cure-pass cap's enforcement, early-stop conditions, the fan-pathway no-chain isolation directive, and the final-report template. `SKILL.md`'s `## Auto mode` keeps the one-paragraph summary and the publishable-gate rule; this file is everything downstream of that summary.

## Cook entry preflight

`--auto` uses the same `cook(spec_ref, receipt? = null, correction = false)`
contract as manual Cook; it never bypasses the canonical GateReceipt boundary.
Before any production mutation, Cook verifies the same spec/work/project
identity, protected-file hashes, and guard graph, then runs
`red-gate validate <receipt> --state red`. An absent or invalid receipt
synchronously invokes `/cut`, consumes the returned receipt exactly once, and
does not recursively hand off from Cut back to Cook. Adopted reproductions
remain `producer: cut` with case `origin: adopted`.

Closed `not-applicable` receipts retain identity and structural validation but
skip RED replay and production work; Cook returns promptly. Once inner TDD
completes, Cook runs `red-gate validate <receipt> --state green` and requires
the active case plus every transitive guard GREEN before invoking `/press`.
When `correction = true`, only the active Press RED receipt is in scope;
transitive guards remain immutable and cannot be weakened or bypassed.

## What auto mode does

1. After Cook's completed GateReceipt preflight, inner implementation, and
   `red-gate validate <receipt> --state green` for active and transitive
   guards, write the package-ready report and invoke `/press <slug> --auto`;
   append `--open-pr` so terminal `/plate` may publish a new PR.
2. `/press --auto` runs its hardening pass and, if readiness is `ready for /age` or `follow-up recommended`, invokes `/age <slug> --auto`. Both states mean the cooked contract is sound and every changed behaviour has a hardening test; documented follow-ups are review-safe. Only `blocked` stops auto — blocked criteria: defined once in [`../../press/references/gap-analysis.md`](../../press/references/gap-analysis.md).
3. `/age <slug> --auto` writes the report and invokes `/cure <slug> --auto --stake medium+`.
4. `/cure --auto --stake medium+` bypasses the selection gate, applies every finding of `blocker`, `high`, or `medium` severity plus every cheap (contained-fix) `Low`, then invokes `/age --scope <touched-paths> --auto` for verification.
5. The age → cure cycle is capped at **two cure passes total**. Pass 1 fixes the initial findings. Pass 2 fixes anything the re-age surfaces. After pass 2 the chain stops with a final summary, regardless of whether new findings remain.
6. `/cook` itself never invokes `/plate`. At the chain terminal, `/cure` dispatches `/plate` for an existing PR, and for a new PR only when `--open-pr` is in scope. `/plate` honors explicit topology, selects an obviously cohesive single without asking, and asks before mutation when stacked is recommended or shape is ambiguous, including under auto.

## Cap enforcement

The two-cure-pass cap is enforced by chain length, not by age — age boots in fresh context each pass and cannot count prior passes. Each age pass writes `next:` from what it observes on that one run (`next: cure` when a medium+ finding remains, `next: done` when none do); before the terminal position this drives an early stop, but the value itself is informational for cap purposes — the loop's fixed two-pass structure, not age's own `next:` value, is what terminates the chain. `/cook` does not pass a pass-ordinal hint to age: age has no need to know whether it is the first or second post-cure check, since the orchestrator owns the position.

## When auto mode stops early

- A quality gate fails **new** or **changed** against baseline (see [`quality-gates.md`](quality-gates.md)) and the 2 fix rounds exhaust, the no-progress check trips, or the fix is design-shaped. Identical-to-baseline failures outside the cooked contract are recorded and never stop auto.
- `/press` returns `blocked` (blocked criteria: [`../../press/references/gap-analysis.md`](../../press/references/gap-analysis.md)).
- A cure pass cannot apply any finding (every selected fix breaks tests on revert-or-keep evaluation).
- Two cure passes complete (success path).

In every early-stop case, surface the report from the failing skill and tell the user the cap reached or the blocker hit. Do not silently downgrade.

## No-chain isolation directive

Each phase's existing `--auto` contract chains forward in-session —
`/cook --auto` invokes `/press --auto`, which invokes `/age --auto`, and so
on. Cook's synchronous Cut preflight is the exception: it returns a receipt
to the current Cook call and never chains Cook recursively. When `/cook` is
running as its own fan-pathway orchestrator (`fan-pathway.md`), that default
is overridden for every per-curd or post-merge dispatch: each phase sub-agent
runs only its own phase, writes its handoff slug, and stops — it never chains
forward to the next phase itself, even though its own `--auto` contract
documents that behavior. The fan-pathway orchestrator loop
(`fan-pathway.md`'s `## Deterministic phase loop`) owns deciding and
dispatching what runs next, exactly as the retired `/ultracook` orchestrator
once did.

The override travels in the spawn prompt as an explicit no-chain directive, carried over verbatim from `/ultracook`'s original wording: "Do not chain forward to the next phase even though your auto-mode contract documents that. Write your handoff slug and stop. `/cook`'s fan pathway is driving the chain. Run in the foreground — do not background yourself, spawn detached processes, or defer work to a later session. If you cannot complete the phase within your context window, write a partial slug with `status: halt: <reason>` and stop; do not silently timeout."

Each phase's own `SKILL.md` `## Auto mode` section honours this under its `### When invoked from /ultracook` heading (now: when invoked from `/cook`'s fan pathway) — see e.g. `skills/press/SKILL.md`, `skills/age/SKILL.md`, `skills/cure/SKILL.md`.

## Failure handling inside cure

See `skills/cure/SKILL.md` `## Auto mode` for cure's per-finding revert/defer behaviour. Cook does not duplicate the contract — cure owns it.

## Final report

The skill that ends the chain prints the summary below. On the success path that is the final `/age --auto` (after the two-cure-pass cap is reached); on an early stop it is the skill that surfaced the blocker.

```
Auto-mode summary
Passes:        <1|2>
Findings fixed: <count by severity>
Deferred:       <count, with cure-report path>
Final age:      <path>
Next step:      review the diff, then /plate when ready
```
