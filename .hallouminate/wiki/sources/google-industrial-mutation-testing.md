# An Industrial Application of Mutation Testing: Lessons, Challenges, and Research Directions

Google Research's industrial research paper (2018), last verified 2026-10-17, supports the claim that mutation analysis tests whether checks detect seeded faults, but that full mutation adequacy is costly and not a desirable goal.
Canonical source: [An Industrial Application of Mutation Testing: Lessons, Challenges, and Research Directions](https://research.google/pubs/an-industrial-application-of-mutation-testing-lessons-challenges-and-research-directions/)

## What mutation analysis measures

The Google mutation testing paper defines mutation analysis as evaluating "a testing or debugging technique by measuring how well it detects mutants, which are systematically seeded, artificial faults" (source L114-116).

## Mutation testing costs and limits

The paper says that mutation analysis "is inherently expensive due to the large number of mutants it generates", and that many "mutants are not effective; they are redundant, equivalent, or simply uninteresting" (L117-120). It concludes that "achieving mutation adequacy is neither practical nor desirable" (L131-132).

## How easy-cheese research applies it

Use a targeted seeded fault or a deliberate no-op candidate to show that an acceptance check rejects a plausible defect. Investigate surviving mutants before adding tests. Do not add tests only to raise a mutation score. A high mutation score cannot reveal an omitted requirement.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://research.google/pubs/an-industrial-application-of-mutation-testing-lessons-challenges-and-research-directions/ · Updated: 2026-10-18_
