# How Much Testing is Enough?

Google Testing Blog's engineering article (June 2021), last verified 2026-10-17, supports the claim that behavior coverage of critical user journeys is distinct from code coverage, and that covered code can still contain bugs.
Canonical source: [How Much Testing is Enough?](https://testing.googleblog.com/2021/06/how-much-testing-is-enough.html)

## Test layers and critical user journeys

The Google Testing Blog article recommends end-to-end testing for Critical User Journeys (CUJs) (source L13). It defines an integration test as one that "takes a small group of units, often only two units, and tests their behavior as a whole" (L29). End-to-end tests "test the product end to end as a user would use it" (L33).

The article also names fault-tolerance testing: "testing your application's behavior as different dependencies either fail or go down entirely" (L40).

## Behavior coverage versus code coverage

The article states that "just because you have coverage for a particular area of code, this code can still have bugs" (L63). For behavior coverage, "the emphasis is on identifying the CUJs and creating the appropriate tests to track them" (L65).

## Limits of the testing-blog evidence

The article is general guidance. It does not prescribe a test-layer ratio or a coverage threshold. Unit tests keep their value in its model.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://testing.googleblog.com/2021/06/how-much-testing-is-enough.html · Updated: 2026-10-18_
