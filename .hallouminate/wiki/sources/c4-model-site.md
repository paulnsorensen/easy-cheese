# The C4 model for visualising software architecture

Simon Brown's C4 model website (c4model.com), last verified 2026-10-19, supports the definition of the C4 abstractions, diagram levels, and notation rules, and the claim that System Context and Container diagrams are sufficient for most teams.
Canonical source: [The C4 model for visualising software architecture](https://c4model.com/)

## Claims used from the C4 model website

The C4 model website defines C4 as hierarchical abstractions (software systems, containers, components, code) and hierarchical diagrams. It calls itself notation independent and tooling independent.

- Diagram levels: "you don't need to use all 4 levels"; System Context and Container diagrams "are sufficient for most software development teams" (`/diagrams`).
- Component and Code diagrams are not recommended for most teams. Dynamic diagrams "should be used sparingly to show interesting/recurring patterns or features that require a complicated set of interactions" (`/diagrams/dynamic`).
- Notation: every diagram has a title and a key or legend; every element states its type, description, and technology; every relationship is a labelled, unidirectional line (`/diagrams/notation`).
- Tooling: modelling tools are "(recommended)" over diagramming tools, because the model is data (`/tooling`).
- Scope: the FAQ limits C4 to static structure and names embedded systems and configured platforms such as SAP and Salesforce as weaker fits (`/faq`).

## Limitations of the C4 model website as a source

The site is the author's own guidance, so it does not report criticism. Practitioner critiques used in [C4 model evaluation and alternatives](../research/c4-model-evaluation.md) come from other sources.

_Source: https://c4model.com/ · Updated: 2026-10-19_
