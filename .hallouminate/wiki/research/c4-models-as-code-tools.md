# C4 models-as-code tools comparison

Research pass and local render test, 2026-10-19. Question: which open-source tool best supports C4 "models as code", which tools have a CLI, and which produce the best rendered output? Candidates: Structurizr, LikeC4, C4-PlantUML, Mermaid C4, D2, and goadesign/model.

## Answer: LikeC4 is the best-supported open-source alternative to Structurizr

LikeC4 (MIT) is the best-supported open-source alternative to Structurizr. It has one model with many views, the most contributors and releases, a CLI, a language server, and a read-only MCP server ([LikeC4 CLI](../sources/likec4-cli.md)). It does not enforce C4 element rules unless you write a specification.

Structurizr is itself open source now (Apache-2.0 in `structurizr/structurizr`), with a free `local` viewer and a free `export` command ([Structurizr export command](../sources/structurizr-export.md)). It is the C4 reference implementation, but one person made every commit in the last year.

For static images, C4-PlantUML produced the best output in the local test. No tool renders natively in GitHub pull requests except plain Mermaid.

## Maintenance health, last 12 months

Measured with `gh api repos/<repo>/commits` and `/releases` on 2026-10-19.

| Tool | License | Commits | Human authors | Releases | Note |
| --- | --- | --- | --- | --- | --- |
| LikeC4 | MIT | 1968 (408 bot) | 49 | 27 | about half the commits from one maintainer |
| Structurizr | Apache-2.0 | 468 | 1 | 12 | `java` and `cli` repos archived into `structurizr/structurizr` |
| C4-PlantUML | MIT | 20 | 3 | 2 | stable, near maintenance mode |
| D2 | MPL-2.0 | 328 | about 1-2 | 2 | general diagram tool with a C4 theme |
| goadesign/model | MIT | 96 | 1 | 14 | C4 model as Go code |

## Command-line support for C4 tools

Every candidate has a CLI, so agents do not need an MCP server:

- LikeC4: `likec4 validate`, `likec4 format --check`, `likec4 gen mermaid`, `likec4 export json|png|drawio`, `likec4 build`.
- Structurizr: `export -workspace workspace.dsl -format mermaid|plantuml/c4plantuml|png|svg|static`, plus `validate` and `inspect`. PNG and SVG need the browser-based renderer.
- goadesign/model: `mdl` (editor, SVG) and `stz` (Structurizr JSON).
- C4-PlantUML, Mermaid, and D2 use `plantuml`, `mmdc`, and `d2`.

An MCP server adds targeted queries (search, relationship paths) without loading the whole model. `likec4 export json` plus `jq` covers the same need from the CLI.

## Rendered output quality from the local test

On 2026-10-19 the test rendered one identical Container view (8 elements, 7 relationships) in each tool. One rater scored layout, label readability, C4 fidelity, and looks by eye. No published side-by-side comparison exists.

1. C4-PlantUML: clean, full C4 notation, automatic legend and boundary. Needs Java or Docker and fetches its library from GitHub at render time.
2. Structurizr: classic C4 look with technology on edges. External systems overlapped the boundary. The CLI needs the browser renderer for PNG.
3. D2 with ELK layout: orthogonal edges, no overlaps; technology must be typed into labels.
4. LikeC4: modern look, but tall, no legend, and no technology on edges. The model may have put technology in the wrong field; left-to-right layout was not tried.
5. Mermaid `flowchart` with C4 labels: readable and GitHub-native, but not true C4 notation.
6. D2 with dagre layout: labels collided.
7. Mermaid C4: edges through boxes and labels on boxes ([Mermaid C4 diagram syntax](../sources/mermaid-c4-diagrams.md)).

Caveats: one small model, one rater. Large nested models stress layout engines differently. D2's TALA engine (now MPL-2.0) and goadesign/model were not rendered.

## Consequence for easy-cheese tooling

Keep Mermaid `flowchart` for spec and pull-request diagrams, because only Mermaid renders in GitHub. When a repository keeps a durable C4 model, prefer LikeC4 for agent use and browsable docs. Prefer Structurizr with a C4-PlantUML export for the cleanest static images. `skills/cheese/references/diagrams.md` already tells agents to derive views from such a model instead of drawing a divergent copy.

_Source: briesearch passes and local render test 2026-10-19 (gh api, likec4.dev, docs.structurizr.com, mermaid.js.org, d2lang.com) · Updated: 2026-10-19_
