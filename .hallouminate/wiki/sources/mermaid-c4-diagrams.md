# Mermaid C4 diagram syntax

This page records the Mermaid documentation page for its C4 diagram syntax, last verified 2026-10-19. The page supports the claim that Mermaid C4 is still experimental.
Canonical source: [C4 Diagrams | Mermaid](https://mermaid.js.org/syntax/c4.html)

## Claims used from the Mermaid C4 page

The Mermaid C4 page states: "C4 Diagram: This is an experimental diagram for now. The syntax and properties can change in future releases. Proper documentation will be provided when the syntax is stable." It also says the syntax is compatible with C4-PlantUML.

Project relevance: `skills/cheese/references/diagrams.md` tells agents to draw C4 views with Mermaid `flowchart`, not with `C4Context` or `C4Container`. The local render test in [C4 models-as-code tools comparison](../research/c4-models-as-code-tools.md) confirmed the risk. The Mermaid C4 output drew edges through boxes and labels on top of boxes. Open issue mermaid-js/mermaid#8419 reports the same label overlap.

_Source: https://mermaid.js.org/syntax/c4.html · Updated: 2026-10-19_
