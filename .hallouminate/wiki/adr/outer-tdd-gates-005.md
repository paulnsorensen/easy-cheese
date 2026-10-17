# ADR: Gate applicability is explicit and uses existing project runners

Status: accepted (2026-08-06)

Spec: outer-tdd-gates (durable specs corpus).

## Context

Inferring whether work needs RED evidence from filenames or prose is unstable, especially for UI work where appearance and behavior often overlap. Introducing a new test framework during Cut would also turn a gate into an unapproved infrastructure migration.

## Decision

Mold records `gate_applicability` from an explicit `work_class`. Behavioral work is `red-required`; documentation, refactor-only, test-only, and appearance-only work receive a closed `not-applicable` receipt. Appearance-only means no interaction, state, event, or data behavior changes. Functional UI work remains `red-required` and uses the project's existing browser or E2E seam. Cut uses the existing project runner or standard library; if neither can express the contract, it halts for an explicit harness decision.

## Consequences

Applicability is reviewable and deterministic rather than inferred. Functional UI changes cannot hide behind an appearance label. Projects without a suitable runner fail explicitly instead of silently installing or hand-rolling a framework.

## Mold-to-Cook consequence (2026-09-17)

The boundary's browser regression is an explicit separate gate:
`just test-workflow-browser`. Its Playwright package and browser setup live
under `tests/fixtures/mold_cook_browser`; runtime skill bundles do not gain a
browser dependency. The hermetic Python suite exercises frozen traces and
does not claim browser or live-agent evidence. A missing browser prerequisite
fails the browser gate rather than being reported as a skipped pass.
