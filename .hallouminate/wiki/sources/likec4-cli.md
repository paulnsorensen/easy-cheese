# LikeC4 CLI

The LikeC4 project's CLI documentation page, last verified 2026-10-19, supports the claims about LikeC4's command-line validation, formatting, export, and code generation.
Canonical source: [LikeC4 CLI](https://likec4.dev/tooling/cli/)

## Claims used from the LikeC4 CLI page

The LikeC4 CLI page documents the `likec4` npm package (`npx likec4 ...` or `npm i -D likec4`) with these commands:

- `likec4 validate` and `likec4 format --check` for CI gates.
- `likec4 gen mermaid`, `gen dot`, `gen d2`, `gen plantuml` for text exports.
- `likec4 export png`, `export jpg`, `export json`, `export drawio` for images and model dumps. PNG export needs a Playwright Chromium.
- `likec4 build -o ./dist` for a static site, `likec4 serve` for a live preview, and `likec4 lsp --stdio` for a language server.

Related LikeC4 pages (fetched 2026-10-19): the LikeC4 MCP server exposes read, query, and preview tools only; the README says LikeC4 is "inspired by C4 Model and Structurizr DSL, but provides some flexibility", so it does not enforce C4 element rules by default.

_Source: https://likec4.dev/tooling/cli/ · Updated: 2026-10-19_
