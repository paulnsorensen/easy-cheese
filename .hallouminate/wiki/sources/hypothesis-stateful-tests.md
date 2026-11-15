# Stateful tests

The Hypothesis project's official documentation page (version 6.170.1), last verified 2026-10-17, supports the claim that stateful property tests generate action sequences and can compare an implementation with a simpler independent model.
Canonical source: [Stateful tests](https://hypothesis.readthedocs.io/en/latest/stateful.html)

## Hypothesis stateful testing

The Hypothesis stateful testing page says: "You specify a number of primitive actions that can be combined together" (source L48). Rules "can be chained together - a single test run may involve multiple rule invocations" (L55). The documented example compares "one implementation ... to a simplified in memory model of its behaviour" (L64). A failing sequence shrinks to "a very short program that will demonstrate the problem" (L133).

## When stateful tests fit

The page notes that "a standard test with `@given` might be enough" for simpler cases (L52). Stateful testing fits when the order of actions matters, such as retry, resume, export then apply, or cancellation.

## Limits of the stateful-test evidence

A model can repeat the implementation's mistake. A small fixed reproduction should come before a generated sequence.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://hypothesis.readthedocs.io/en/latest/stateful.html · Updated: 2026-10-18_
