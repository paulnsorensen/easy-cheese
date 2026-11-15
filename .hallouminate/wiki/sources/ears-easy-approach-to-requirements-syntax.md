# Easy Approach to Requirements Syntax (EARS)

Alistair Mavin, Philip Wilkinson, Adrian Harwood, and Mark Novak's conference paper (IEEE RE'09, 2009), last verified 2026-10-17, supports the claim that EARS gives five basic requirement patterns that separate precondition, trigger, system, and response.
Canonical source: [Easy Approach to Requirements Syntax (EARS)](https://www.researchgate.net/profile/Alistair_Mavin/publication/224079416_Easy_approach_to_requirements_syntax_EARS/links/568ce3bf08aeb488ea311990/Easy-approach-to-requirements-syntax-EARS.pdf)

## EARS patterns used by easy-cheese research

The EARS generic form is `<optional preconditions> <optional trigger> the <system name> shall <system response>`. The clause order follows temporal logic (PDF p. 2).

The paper specialises the generic form into five types (pp. 2-3):

| Type | Keyword | Form |
| --- | --- | --- |
| Ubiquitous | none | The `<system>` shall `<response>` |
| Event-driven | When | WHEN `<trigger>` the `<system>` shall `<response>` |
| Unwanted behaviour | If / Then | IF `<trigger>`, THEN the `<system>` shall `<response>` |
| State-driven | While | WHILE `<state>` the `<system>` shall `<response>` |
| Optional feature | Where | WHERE `<feature is included>` the `<system>` shall `<response>` |

Section 4.7 permits combinations of When, While, and Where, including inside If-Then statements.

## Limits of the EARS evidence

EARS syntax does not establish that a requirement set is complete. It also does not define a test oracle. The transfer of system-oriented EARS to agent-workflow requirements is an adaptation, not a result that this paper establishes.

Used by: [behavioral-acceptance-ears-loops](../research/behavioral-acceptance-ears-loops.md).

_Source: https://www.researchgate.net/profile/Alistair_Mavin/publication/224079416_Easy_approach_to_requirements_syntax_EARS/links/568ce3bf08aeb488ea311990/Easy-approach-to-requirements-syntax-EARS.pdf · Updated: 2026-10-18_
