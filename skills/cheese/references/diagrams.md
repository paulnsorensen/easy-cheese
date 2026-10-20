# Diagram vocabulary

Use this reference when a skill adds a diagram to a spec, a pull request body, or a wiki page.
Also use it for a diagram in an explanation.
The diagram can show architecture, flow, data, or behavior.
The architecture vocabulary comes from the [C4 model](https://c4model.com/).
C4 defines the abstractions and the zoom levels. It does not fix a notation, so draw C4 views in Mermaid.
Copy a starting diagram from [`diagram-templates.md`](diagram-templates.md).

## When to draw

Work through this checklist before you write a spec Approach, a pull request body, or an architecture wiki page.
Draw the diagram for each item that applies. Draw no diagram when no item applies.

- [ ] The change spans two or more software systems that the organization owns. Draw a **System Landscape** view.
- [ ] The change adds a user type or an external system that the whole system depends on. Draw a **System Context** view.
- [ ] The change adds, removes, or rewires an application, a data store, a queue, or an external system. Draw a **Container** view.
- [ ] The change moves a responsibility between components, or adds a component, inside one container. Draw a **Component** view.
- [ ] The change adds, removes, or reorders messages between two or more elements. Draw a **sequence** diagram or a **Dynamic** view.
- [ ] The change adds a queue, a retry, a callback, or a background job. Draw an **asynchronous sequence** diagram.
- [ ] The change alters the handoff order between skills, agents, or sub-agents. Draw an **agent handoff sequence** diagram.
- [ ] The change moves a container to a new runtime, host, cluster, region, or environment. Draw a **Deployment** view.
- [ ] The change adds or alters tables, columns, keys, or relationships. Draw a **database** diagram.
- [ ] The change adds a status field, a lifecycle, or a transition. Draw a **state** diagram.
- [ ] A data or control flow crosses three or more modules. Draw a **flow** diagram.

Draw no diagram for a small fix, a docs-only pull request, or a test-only change.
Also draw none for a rename that keeps every boundary.
These rules do not apply to the spec opening diagram.
Each artifact keeps its own diagram limit:

- A spec follows the spec diagram rule in [`formatting.md`](formatting.md).
- A pull request body holds one diagram at most. The `/plate` diagram table decides whether the PR gets one.
- A `/mold` fork card follows [`fork-questions.md`](../../mold/references/fork-questions.md).

## Pick one view

Ask which question the reader has. Draw the one view that answers it.

| Reader question | View | Mermaid form |
| --- | --- | --- |
| Which systems does the organization own, and how do they connect? | C4 System Landscape | `flowchart` |
| Who uses the system, and which external systems does it depend on? | C4 System Context | `flowchart` |
| Which runnable or deployable units exist, and how do they talk? | C4 Container | `flowchart` |
| Which components inside one container change, and how do they connect? | C4 Component | `flowchart` |
| In which order do messages move between elements? | C4 Dynamic or UML sequence | `sequenceDiagram` |
| Where does each container run? | C4 Deployment | `flowchart` with one `subgraph` per node |
| Which tables, keys, and relationships exist? | entity relationship or UML tables | `erDiagram` or `classDiagram` |
| How does data or control move through modules? | flow | `flowchart` |
| Which states and transitions does one element have? | state | `stateDiagram-v2` |

Prefer the System Context and Container views. They are sufficient for most changes.
Draw a Component view only for the one container that the change restructures.
Draw a Dynamic view only for a complex or recurring interaction.
Do not draw the C4 Code level. The source code is the code view.
A change inside one module usually needs no C4 view. Use a flow or a sequence instead.

## C4 abstractions

- **Person:** a human user or role.
- **Software system:** the highest unit of value that one team owns and delivers.
- **Container:** a separately runnable or deployable unit, such as an application, a CLI, a function, or a data store.
  A C4 container is not a Docker container.
- **Component:** a group of related code behind one interface inside one container.

Keep one zoom level in each diagram.
A Container view also shows the people and external systems that connect to the containers.
A Component view also shows the containers and external systems that connect to the components.

## Notation rules

- Give each diagram a title that names the view and its scope, for example `Container view: Shop checkout`.
- Label each element with its name, its type and technology, and one line of responsibility.
  For example: `Pay["Payment provider<br>[External system]<br>Charges cards"]`.
- Draw each relationship in one direction.
  Label it with its intent, and add the protocol or technology between containers.
- Add a legend when a shape or a line style carries meaning.
  Mermaid has no legend element, so put a one-line `Legend:` under the diagram.
- Show only the elements that the change touches, plus their direct neighbors.
  Keep a diagram to 15 nodes or fewer.

## Mermaid rules

- Draw C4 views with `flowchart`, not with the Mermaid `C4Context` family.
  Mermaid marks its C4 syntax as experimental.
- A repository that keeps a C4 model in Structurizr DSL or LikeC4 is the source of truth.
  Derive the view from that model. Do not draw a second, divergent copy.
- Quote a label that holds punctuation.
- Never use `end` as a node id. Use `<br>` for a line break.
- Do not add theme or style directives.
- Use these shapes: `[(...)]` for a data store, `[[...]]` for a queue, and `-.->` for an asynchronous message.
- Do not start a label with `1.` because Mermaid can read it as a list. Write `(1)` instead.

## Templates

[`diagram-templates.md`](diagram-templates.md) holds a template for each view in the table above.
Draw a flow diagram as a plain `flowchart`. It has no template.
