# Docs Mermaid rendering

The documentation site deliberately has no Mermaid runtime integration. The generated docs currently contain no fenced Mermaid diagrams, so the former global `astro-mermaid` integration only added bootstrap code to every page, including the static homepage.[^1]

Text that documents the `--render mermaid` command is an example, not an embedded diagram. Adding the first real Mermaid fence requires restoring a renderer. Prefer a route-scoped mechanism so pages without diagrams remain script-free; do not restore unconditional global injection.[^2]

[^1]: astro.config.mjs:1-35; package.json:13-18
[^2]: skills/mold/references/gate-graph.md:12-22
