# Skills parity: easy-cheese vs obra/superpowers brainstorm + mattpocock/skills

_Research pass. Two source slugs feed this synthesis:_
- `.cheese/research/superpowers-parity/superpowers-parity.md` (obra/superpowers, 14 skills, brainstorm deep-dive, web-UI audit)
- `.cheese/research/pocock-parity/pocock-parity.md` (mattpocock/skills, 25 skills)

## Verdict

**No — not full parity, on either axis.** One concrete, user-suspected gap is confirmed: superpowers' `brainstorming` skill ships an optional **local web server ("Visual Companion")** that hot-reloads HTML mockups/wireframes in a browser tab and streams the user's click choices back to the agent over WebSocket. easy-cheese has **no equivalent** — our `/mold` only renders a _static_ gate-graph diagram (dot/mermaid/svg/png); it is not an interactive live web companion. On every other brainstorm dimension, `/mold` matches or exceeds superpowers. Against Pocock, we directly cover ~3 of 15 plugin skills, several more partially.

## Axis 1 — superpowers `brainstorming` (9 steps) vs `/mold`

| superpowers brainstorm step | easy-cheese /mold | parity |
|---|---|---|
| 1. Explore project context (files/docs/commits) | Explore + Ground modes (cheez-search/read) | yes |
| 2. **Offer Visual Companion — local web server, HTML mockups, live reload, click events streamed back** | **none** | **GAP** |
| 3. Clarifying Qs, one per msg, multiple-choice | Dialogue: smallest useful question, lettered options | yes |
| 4. Propose 2-3 approaches w/ trade-offs, lead w/ rec | Shape mode (2+ options incl. Do Nothing, recommend) | yes (>=) |
| 5. Present design section-by-section, approve each | Sketch + dialogue + handshake | yes |
| 6. Write design doc + git commit | Curdle writes spec to durable corpus (commit deferred to /commit) | partial |
| 7. Spec self-review (placeholders/contradictions) | Agent coherence self-check + agent-introduced-scope check | yes |
| 8. User reviews spec, approval gate | Two-key handshake (explicit user verb) | yes |
| 9. Transition to writing-plans | curd-count handoff -> /cook / /cheese-factory / /ultracook | yes (>=) |

**/mold extras beyond brainstorm:** six explicit modes, Prototype Cycle, Validate Cycle, gate graph (dual-render from one model), ADRs, context-budget nudges, shape-check, curd-count decomposition routing, `--hard` propagation.

**Net:** `/mold` >= brainstorm on every dialogue/spec/gate axis **except** the Visual Companion web server. That single gap matches the user's intuition exactly.

## Axis 1b — superpowers full 14-skill graph vs easy-cheese

| superpowers skill | easy-cheese equivalent |
|---|---|
| brainstorming | /mold (minus Visual Companion) |
| dispatching-parallel-agents | /cheese-factory, /ultracook |
| executing-plans | /cook |
| finishing-a-development-branch | /gh, /pr-stack, /commit |
| receiving-code-review | /affinage, fromage-fort |
| requesting-code-review | /age (dispatches reviewer) |
| subagent-driven-development | /ultracook, /cheese-factory |
| systematic-debugging | /pasteurize (+ mold Diagnose mode) |
| test-driven-development | /cook TDD loop, /press, /tdd-assertions |
| using-git-worktrees | /worktree |
| using-superpowers (bootstrap) | preamble.md routing / CLAUDE.md |
| verification-before-completion | /self-eval, Rule 9, whey-drainer |
| writing-plans | /mold spec, /spec |
| writing-skills | /skill-creator, /skill-improver |

At the skill-graph level easy-cheese covers essentially all 14 superpowers functions **except** the brainstorm Visual Companion web server.

## Axis 2 — mattpocock/skills (15 plugin skills) vs easy-cheese

Covered: `diagnose` -> /pasteurize, `handoff` -> /wheypoint, `write-a-skill` -> /skill-creator.

Partial: `tdd` -> /cook+/press+/tdd-assertions; `grill-me` -> mold Grill mode; `prototype` -> mold Prototype Cycle (logic branch only; UI multi-variant branch needs a web companion); `to-prd` -> /spec; `zoom-out` -> /grok-codebase + code-review-graph; `triage` -> /affinage (PR-centric, not issue-centric).

No analog: `caveman` (token-reduction mode), `teach` (multi-session teaching), `to-issues` (plan->tickets), `setup-matt-pocock-skills` (repo config scaffold), `improve-codebase-architecture`, `grill-with-docs` (domain-model + live CONTEXT.md/ADR mutation).

Pocock repo ships **no** web UI / server / HTML / dashboard (116-path tree scan, 0 matches).

## The web companion gap (confirmed both ways)

**superpowers HAS it:** `skills/brainstorming/scripts/server.cjs` — ~250-line zero-dependency Node HTTP+WebSocket server, binds `127.0.0.1` random high port; `start-server.sh` backgrounds it; `frame-template.html` + `helper.js` provide the page and client. AI writes HTML fragments to a watched dir, server hot-reloads the browser, `[data-choice]` clicks stream back to the agent. Browser is NOT auto-opened (user navigates manually). No MCP, no dashboard, no auto-open. (superpowers slug, all `<certain>`.)

**easy-cheese does NOT** (Rule 12 audit):
- HTTP server in a skill — none. No `.cjs`/`.js`/`*server*` files in repo (tilth_list -> 0 files).
- WebSocket / createServer / listen / express — none in any source (regex search, 0 source hits).
- HTML assets — none (`*.html` -> 0 files).
- browser-launch / click-streaming — none.
- Closest: `justfile:65` `mkdocs serve` (static docs preview at :8000) — does not participate in any skill reasoning loop. Different purpose.

## Open questions (hand-off, not recommendations)

- Should `/mold` gain an optional interactive Visual-Companion-style web server for the design/UI branch? It is the one true feature gap vs superpowers. Counterweight: it requires Node.js (superpowers' does too) and an interactive web companion sits in tension with easy-cheese's run-anywhere / zero-hard-dep posture (the gate-graph was deliberately built dual-render to avoid even a Graphviz dependency). Decision for the user.
- Pocock's `prototype` UI branch (multi-variant UI) and superpowers' Visual Companion are the same capability cluster — both need a live browser surface. If we add one, it covers both.
- Which uncovered Pocock skills (caveman / teach / to-issues / grill-with-docs) are worth porting is a separate scoping question.
