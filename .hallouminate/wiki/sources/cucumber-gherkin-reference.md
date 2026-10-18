# Gherkin Reference

Cucumber's official documentation page, last verified 2026-10-17, supports the claim that a Gherkin scenario maps context to Given, event to When, and an observable outcome to Then.
Canonical source: [Gherkin Reference](https://cucumber.io/docs/gherkin/reference/)

## Gherkin scenario structure

The Gherkin reference defines a scenario as "a concrete example that illustrates a business rule" (source L159). A scenario has three step kinds:

- Given steps describe the initial context, "typically something that happened in the past" (L199).
- When steps describe an event or an action, by a person or another system (L213).
- Then steps describe an expected outcome (L229).

## Observable outcome rule

The Gherkin reference says that a Then step definition "should use an assertion to compare the actual outcome (what the system actually does) to the expected outcome" (L231). It also says that "an outcome should be on an observable output ... and not a behaviour deeply buried inside the system (like a record in a database)" (L233).

## Limits of the Gherkin evidence

Gherkin syntax does not make a Then step correct. The step implementation must exercise the real boundary and compare the real output.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://cucumber.io/docs/gherkin/reference/ · Updated: 2026-10-18_
