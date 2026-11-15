# Behaviour-Driven Development

Cucumber's official BDD guide, last verified 2026-10-17, supports the claim that BDD is a three-step practice of discovery, formulation, and automation, and that it is more than using Cucumber.
Canonical source: [Behaviour-Driven Development](https://cucumber.io/docs/bdd/)

## BDD as discovery, formulation, and automation

The Cucumber BDD guide describes day-to-day BDD as a three-step iterative process (source L53-59):

1. Discuss concrete examples of a small upcoming change to agree on the details.
2. Document those examples in a form that can be automated, and check for agreement.
3. Implement the behaviour of each example, "starting with an automated test to guide the development of the code."

The guide calls these practices Discovery, Formulation, and Automation. It says each example is connected to the system as a test that fails first, and then lower-level examples guide the implementation (L93).

## Limits of the BDD guide evidence

The guide states that "there's much more to BDD than just using Cucumber" (L32). A feature file alone does not establish BDD practice. See [cucumber-myths-about-bdd](./cucumber-myths-about-bdd.md).

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://cucumber.io/docs/bdd/ · Updated: 2026-10-18_
