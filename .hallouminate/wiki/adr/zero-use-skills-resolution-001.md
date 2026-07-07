# ADR: Zero-use skill resolution — retire hard-cheese, re-trigger pasteurize

The 2026-07-07 skill audit's S6 finding (two skills at zero invocations since
launch while every sibling grew) was resolved with measured trigger evals plus
real-traffic mining, not intuition. Verdicts: retire `hard-cheese`; keep
`pasteurize` and fix its description.

## Context

Both skills showed 0 invocations across ~8 weeks of ingested sessions
(hard-cheese since 2026-05-13, pasteurize since 2026-05-17). Two competing
hypotheses: the triggers never fire (activation bug) or the capability is not
wanted (dead weight). Trigger evals (10 should-fire + 8 near-miss queries per
skill, 2 runs each, `claude -p` against the live installed skill surface) and
8-week typed-prompt mining in the session-analytics DB separated the two.

## Decision

**Retire hard-cheese.** Its description routed near-perfectly (90% positive
trigger rate, 0% false positives) — the trigger was never the problem. Demand
was: zero explicit `/hard-cheese` invocations ever, `--hard` never passed in
29 `--auto` pipeline runs (its sole pipeline puncture point), zero gate-shaped
typed prompts in 8 weeks. The capability is an interactive human self-test;
every channel that could express wanting it read zero. The `--hard`
propagation plumbing was removed from cheese/mold/cook/press/age/cure/
affinage/ultracook, `shared/scripts/handoff.py` (`ALWAYS_PROPAGATE` is now
empty), and `shared/scripts/paths.py` (the `hard` phase and the one divergent
`PHASE_DIRS` entry).

**Fix pasteurize's triggers, keep the skill.** Its old description fired on
only 30% of realistic bug reports (0% false positives): the three hits all
contained the description's verbatim meta-verbs ("debug this", "diagnose");
all seven symptom-only reports (flaky CI test, broken button, perf
regression) routed to *no skill* — the model starts debugging inline. The
replacement description names symptoms ahead of meta-verbs and explicitly
forbids the observed default ("Do NOT start debugging inline without this
skill"); it measured 90%/0% on the identical eval set.

## Consequences

- Skills that gate on the *user wanting a discipline applied to themselves*
  need a demand signal before they earn catalog space; description quality
  cannot manufacture demand. Do not re-add a comprehension gate without
  observed asks for one.
- Descriptions for capabilities the model believes are core competency
  (debugging, writing, explaining) under-trigger unless they (a) enumerate
  symptom shapes, not just meta-verbs, and (b) name and forbid the inline
  default. This generalizes to future skills — validate with trigger evals,
  not review.
- The retirement evidence and eval artifacts live at
  `.cheese/skill-improver/2026-07-07-s6-zero-use-verdicts.md` (porto-v1
  workspace scratch; the durable reasoning is this page).
- Re-baseline pasteurize ~4 weeks after the description ships; if usage is
  still zero, fold the six-phase discipline into a `/cook` reference and
  retire the standalone skill per the same evidence bar.
