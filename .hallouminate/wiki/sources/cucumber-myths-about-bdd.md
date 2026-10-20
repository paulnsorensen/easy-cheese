# Myths about BDD

Cucumber's official documentation page, last verified 2026-10-17, supports the claim that using Cucumber is neither necessary nor sufficient for BDD, and that scenarios written after implementation are test automation, not BDD.
Canonical source: [Myths about BDD](https://cucumber.io/docs/bdd/myths/)

## BDD myths relevant to acceptance checks

The Cucumber myths page makes three points that matter for agent acceptance checks:

- "Unless you've already done effective discovery work, trying to formulate scenarios is a waste of time" (source L37).
- Teams that use Cucumber to check for bugs after implementation do "a perfectly reasonable" kind of test automation, "but it's not BDD" (L41).
- "Just because you're using Cucumber, doesn't mean you're doing BDD" (L49).

## Limits of the myths evidence

The page argues for collaborative discovery. It does not say which test framework to use. A pytest or shell acceptance check can carry the same examples.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://cucumber.io/docs/bdd/myths/ · Updated: 2026-10-18_
