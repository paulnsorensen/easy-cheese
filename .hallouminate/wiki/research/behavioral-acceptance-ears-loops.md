# Behavioral acceptance: EARS, BDD, tests, and bounded loops

Promoted research report. It answers one question: when unit tests pass but
the delivered behavior fails live, which checks, requirement formats, and
loops close that gap? The answer is a small set of checks that reject
plausible false successes at the real boundary, not more unit tests.

This report holds candidate practices, not adopted skill changes. The
easy-cheese application lives in
[behavioral-acceptance-easy-cheese-suggestions](./behavioral-acceptance-easy-cheese-suggestions.md).
The visual summary is
[`artifacts/behavioral-acceptance-ears-loops/summary.html`](./artifacts/behavioral-acceptance-ears-loops/summary.html).

## Findings in brief

- **EARS and BDD do different jobs.** EARS states the condition, trigger, and
  required response. BDD turns that rule into concrete examples and connects
  them to observable checks. Neither format guarantees that the check tests
  the useful result. See [ears](../sources/ears-easy-approach-to-requirements-syntax.md),
  [gherkin](../sources/cucumber-gherkin-reference.md), and
  [bdd](../sources/cucumber-behaviour-driven-development.md).
- **Code coverage is not behavior coverage.** Covered code can still contain
  bugs; critical user journeys need end-to-end checks
  ([google testing](../sources/google-how-much-testing-is-enough.md)).
- **A check must prove it can fail.** Run it on a known-broken case (it must
  fail for the expected reason) and a known-working reference (it must pass).
  That detects both permissive and impossible checks
  ([anthropic evals](../sources/anthropic-demystifying-evals-for-ai-agents.md)).
- **A loop repeats a process; it does not improve the definition of success.**
  Evaluator-optimizer loops need clear criteria and environment ground truth
  ([anthropic agents](../sources/anthropic-building-effective-agents.md)).
  Self-correction works with reliable external feedback and can degrade
  without it ([survey](../sources/when-can-llms-correct-their-own-mistakes.md),
  [iclr](../sources/llms-cannot-self-correct-reasoning-yet.md)).
- **No inspected source shows that loops beat one-pass workflows for coding,
  or that hill climbs prevent tangled code.** Those claims need a local
  comparison.

## Behavioral checks that reject false success

Select checks by claim and failure risk. Do not generate every check for
every task. The rows are authored applications of the evidence, not observed
product behavior.

| Claim under test | Candidate check | False success it rejects |
| --- | --- | --- |
| The delivered path works. | Start the installed or packaged entrypoint in an isolated destination. Inspect the user-visible result. | Helpers pass, but packaging, configuration, permissions, or wiring fails. |
| An exported candidate is usable. | Apply the exported patch to its declared clean base. Run the target's real entrypoint. | A patch file exists but is empty, inapplicable, or ineffective. |
| A failure remains a failure. | Deny a required permission or remove one dependency. Check the specified error and unchanged protected state. | An unexpected error satisfies a success scenario. |
| Retry or resume preserves the contract. | Interrupt at a durable boundary and resume. Check the effects through the public read path. | Duplicate work, lost state, or a success label without the effect. |
| The check detects the complaint. | Replay a known-broken base or a no-op candidate through the same check. | A vacuous assertion passes both working and broken behavior. |
| The change improves useful outcomes. | Evaluate baseline and candidate on reserved representative tasks, with repeated trials when outcomes vary. | Machinery completes, but task quality does not improve. |

A failed live dependency is not a successful completion. An expected denial
can pass a denial scenario; it cannot pass the success scenario. For
experiments, keep three claims separate: the experiment runs, its artifact
reproduces the candidate, and the candidate improves the target behavior. An
inconclusive result is a valid outcome, not demonstrated improvement.

## EARS with BDD examples

Use only the EARS patterns that the behavior needs: event (When), unwanted
behavior (If/Then), state (While), optional feature (Where), and
always-active. A practical acceptance record holds a stable ID and one EARS
statement, concrete normal and failure examples, the real entrypoint and live
boundaries, an observable result with an independent source of truth, a
bounded observation period when time matters, and a false-success case.

EARS conditions map to Given, triggers to When, and responses to Then. This
mapping is an adaptation, not a formal standard. A "While" requirement needs
observations across the relevant transitions; one snapshot does not establish
it. An eventual requirement needs a deadline, not a fixed sleep.

```gherkin
Feature: Deliver the evaluated candidate
  Rule: An exported patch works on its declared base

    Scenario: Use the exported patch
      Given a clean checkout at base B
      And "./fixture double 7" incorrectly prints "7" at B
      When I apply the exported patch to that checkout
      And I run "./fixture double 7"
      Then the exit status is 0
      And stdout is exactly "14"

    Scenario: Reject false success
      Given the same clean checkout at base B
      When I evaluate a no-op patch with the same acceptance check
      Then the acceptance check fails
      And it identifies the incorrect output
```

The no-op scenario tests the evaluator, not a production feature. Keep the
current test framework when it can run the examples; Cucumber alone does not
establish BDD ([myths](../sources/cucumber-myths-about-bdd.md)).

## Avoiding weak tests and unit-test overproduction

Ask one admission question for each test: *which distinct observable failure
does this test reject, and why is this the cheapest faithful place to reject
it?* Keep fast low-level tests for parsing, transforms, boundary values,
invalid input, state transitions, and failure handling. Prefer stable public
boundaries over one test per private helper. A mocked return value is not
evidence that the mocked integration works.

Use generated properties for invariants and stateful tests when order
matters ([hypothesis](../sources/hypothesis-stateful-tests.md)). Use a
targeted mutant or a no-op candidate to challenge assertions, and investigate
survivors before adding tests; full mutation adequacy is not a goal
([mutation](../sources/google-industrial-mutation-testing.md)).

Growth signals to review: tests fail after a behavior-preserving private
rename; fixtures outgrow the behavior; several layers assert one
implementation detail; a test passes after the required effect is removed;
snapshots change without independent review; the suite grows while the live
complaint still reproduces.

## Acceptance loops versus optimization loops

A scheduler repeats work. A repair loop changes a failing candidate after
observed feedback. An optimization loop compares candidates on a metric.

- **Acceptance repair loop:** freeze the requirement and evaluator, prove the
  check rejects the broken result, run the real path, fix one observed
  failure, re-run acceptance and regressions. Stop when acceptance and the
  required gates pass, or earlier on budget, no progress, or a needed
  decision. Do not keep editing because budget remains.
- **Optimization loop:** start from an accepted baseline, name one objective,
  hold behavior and architecture constraints fixed, change one hypothesis,
  compare under matched conditions, keep only a justified gain. Deterministic
  costs support strict ratchets. Agent quality needs repeated trials and an
  uncertainty policy. A repeatedly consulted reserve becomes development
  evidence ([holdout](../sources/adaptive-data-analysis-holdout-reuse.md)).

## Constraints, not a single score, against spaghetti

A hill climb can optimize a proxy while making code harder to change. Retain a
candidate only if required behavior passes, security and architecture
constraints pass, relevant regressions stay covered, and the objective shows
a justified gain. A quality score must not compensate for a failed hard
constraint. Dependency and cycle rules can be executable tests
([archunit](../sources/archunit-use-cases.md)). Complexity, changed lines, and
interface counts are review signals; a universal LOC ratchet can reward
compression or fragmentation.

## Provenance and limits

- Researched 2026-10-17 in the dotfiles worktree `t3code/agentic-coding-improvements`
  (checkout `75b72713`) by three parallel researchers. Raw excerpts became the
  [sources/](../sources/index.md) pages; call ledgers are the
  [`manifest*.json`](./artifacts/behavioral-acceptance-ears-loops/manifest.json)
  files.
- Budget compliance is not clean: 16 searches, 22 extracts against a
  20-extract plan, 7 failed calls. Two inaccessible Google posts are not
  evidence.
- No product tests, live acceptance runs, or controlled comparisons ran.
  Confidence: certain on source definitions; speculating on their effect on
  this workflow.
- Open: which real failure and live-call budget should anchor a pilot.

_Source: dotfiles `.cheese/research/behavioral-acceptance-ears-loops/` report, sub-reports (ears, checks, loops), and verification record (ingest hash 6d02516f78fb5bc0), promoted for repository review · Updated: 2026-10-18 · Supersedes: none_
