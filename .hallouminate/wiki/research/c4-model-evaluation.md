# C4 model evaluation and alternatives

Research pass, 2026-10-19. Question: is the C4 model a good way to diagram software architecture in easy-cheese specs, pull requests, and wiki pages, and which alternatives exist? This page grounds `skills/cheese/references/diagrams.md` and `skills/cheese/references/diagram-templates.md`.

## Answer: C4 is a good default for static structure

The C4 model is a good default for the static structure of software that a team builds. It is a shared vocabulary and a set of zoom levels, not a notation, so agents can draw it in plain Mermaid. Its own guidance says System Context and Container diagrams are sufficient for most teams; Component and Code diagrams are optional, and Dynamic diagrams are for sparing use ([The C4 model for visualising software architecture](../sources/c4-model-site.md)).

C4 is weak at behavior, data flow, and data models. Pair it with sequence, state, and database diagrams for those questions.

## What the C4 model defines

The C4 model defines four abstractions and their diagrams:

| Level | Abstraction | Diagram |
| --- | --- | --- |
| 1 | Software system | System Context (plus System Landscape for several systems) |
| 2 | Container: a separately runnable or deployable unit | Container |
| 3 | Component: related code behind one interface | Component |
| 4 | Code | Code (rarely worth drawing) |

Supplementary diagrams: System Landscape, Dynamic, and Deployment. Notation rules: a title and a legend on every diagram; type, technology, and description on every element; a labelled, one-direction line for every relationship.

## Limits of the C4 model

- Static structure only. The C4 FAQ names embedded systems and configured platforms (SAP, Salesforce) as weaker fits.
- The word "container" collides with Docker containers, and teams often confuse containers with components. One practitioner blog ([Misuses and mistakes of the C4 model](https://www.workingsoftware.dev/misuses-and-mistakes-of-the-c4-model)) lists this as a common misuse. Treat it as a single source.
- Hand-drawn diagrams drift. The C4 site recommends modelling tools that generate views from one model. See [C4 models-as-code tools comparison](./c4-models-as-code-tools.md).
- Event-driven and data-flow designs need Dynamic or sequence views. This is an inference from the static-structure scope, not a sourced claim.

## Alternatives and complements to C4

C4 alternatives answer different questions. Primary sources back the arc42, UML, and 4+1 rows. The other rows rest on background knowledge.

| Model | Best use | Relation to C4 |
| --- | --- | --- |
| arc42 | A 12-section architecture document template | Holds C4 views in sections 3, 5, 6, and 7, plus decisions and risks |
| UML sequence, state, class, deployment | Precise behavior and data models | Complements C4 where C4 stays informal |
| Entity relationship diagram | Tables, keys, cardinality | Complements C4 for data stores |
| Kruchten 4+1 view model | Logical, process, development, physical views tied by scenarios | Overlaps C4; adds process and development views |
| ArchiMate | Enterprise layers: business, application, technology | Wider scope than C4; overkill for one product team |
| Data flow diagram with trust boundaries | Threat modelling | Complements C4 for security review |
| Event Storming | Domain discovery workshops | Precedes design; not a structure view |
| ISO/IEC/IEEE 42010 | Standard for viewpoints and views | C4, arc42, and 4+1 fit inside it |

## Consequence for easy-cheese diagrams

easy-cheese adopts the C4 vocabulary and draws every view in Mermaid:

- `skills/cheese/references/diagrams.md` holds the when-to-draw checklist, the view table, and the notation and Mermaid rules.
- `skills/cheese/references/diagram-templates.md` holds the starting templates. They cover the Structurizr view types: Landscape, Context, Container, Component, Dynamic in two forms, and Deployment. They also cover three sequence diagrams, two database diagrams, and a state diagram.
- Agents draw C4 views with Mermaid `flowchart`, not Mermaid `C4Context`. Mermaid marks its C4 syntax as experimental, and that syntax rendered worst in the local test ([Mermaid C4 diagram syntax](../sources/mermaid-c4-diagrams.md)).

_Source: briesearch pass 2026-10-19 (c4model.com, mermaid.js.org, practitioner blogs) · Updated: 2026-10-19_
