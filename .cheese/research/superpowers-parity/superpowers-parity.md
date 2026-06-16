# Research: obra/superpowers — Parity Analysis

**Date:** 2026-06-16
**Source:** gh api obra/superpowers (default branch: main), primary files read directly

---

## 1. Full Skill Inventory

14 skills ship under `skills/`. Each has a `SKILL.md` with a frontmatter `description` field.

| Skill dir | Name | One-line purpose |
|---|---|---|
| `skills/brainstorming` | `brainstorming` | Turns ideas into fully-formed specs via structured dialogue before ANY implementation begins. Includes optional visual companion (local web server). |
| `skills/dispatching-parallel-agents` | `dispatching-parallel-agents` | Delegates 2+ independent tasks to isolated subagents running concurrently rather than sequentially. |
| `skills/executing-plans` | `executing-plans` | Loads and executes a written implementation plan in a fresh session with review checkpoints (no-subagent fallback path). |
| `skills/finishing-a-development-branch` | `finishing-a-development-branch` | Guides post-implementation completion: verify tests → detect environment → choose merge/PR/cleanup path. |
| `skills/receiving-code-review` | `receiving-code-review` | Enforces technical evaluation of incoming review feedback (verify before implementing, reasoned pushback allowed). |
| `skills/requesting-code-review` | `requesting-code-review` | Dispatches a focused code-reviewer subagent with precisely crafted context (SHAs, diff, reviewer prompt). |
| `skills/subagent-driven-development` | `subagent-driven-development` | Executes implementation plans task-by-task with a fresh subagent per task + two-stage review (spec compliance then code quality). |
| `skills/systematic-debugging` | `systematic-debugging` | Mandates root-cause investigation before any fix attempt; structured phases for hypothesis, isolation, and tracing. |
| `skills/test-driven-development` | `test-driven-development` | Enforces red-green-refactor TDD: write test first, watch it fail, write minimal code to pass. |
| `skills/using-git-worktrees` | `using-git-worktrees` | Ensures feature work runs in an isolated workspace; prefers native harness worktree tools, falls back to git worktree. |
| `skills/using-superpowers` | `using-superpowers` | Bootstrap skill — loaded at conversation start; establishes how to find and invoke all other skills; sets priority ordering (user > superpowers > default). |
| `skills/verification-before-completion` | `verification-before-completion` | Gates any completion claim or status assertion behind fresh verification command output ("evidence before assertions"). |
| `skills/writing-plans` | `writing-plans` | Writes comprehensive implementation plans from a spec: file-structure map, bite-sized tasks, TDD guidance, frequent commits. |
| `skills/writing-skills` | `writing-skills` | TDD-for-documentation: write test scenarios (pressure prompts), watch agent fail without skill, write skill, verify compliance. |

**Cited source:** `gh api repos/obra/superpowers/git/trees/main?recursive=1` + individual `gh api repos/obra/superpowers/contents/skills/<name>/SKILL.md` reads.

---

## 2. The Brainstorming Skill — Deep Dive

**Skill path:** `skills/brainstorming/SKILL.md`
**GitHub URL:** <https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md>

### Verbatim frontmatter description

```
"You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
```

### Process it runs (in order — enforced via HARD-GATE)

1. **Explore project context** — reads files, docs, recent commits before any question.
2. **Offer visual companion** (optional, if visual questions are expected) — this offer is its own standalone message; not combined with anything else. Waits for user consent.
3. **Ask clarifying questions** — one at a time, preferring multiple-choice. Understands purpose, constraints, success criteria.
4. **Propose 2–3 approaches** — with trade-offs; leads with recommendation.
5. **Present design** — section-by-section, scaled to complexity (a few sentences for simple; 200–300 words for nuanced). User approves each section.
6. **Write design doc** — saves to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, commits.
7. **Spec self-review** — inline scan for placeholders, contradictions, ambiguity, scope.
8. **User reviews written spec** — waits for explicit approval before proceeding.
9. **Transition** — invokes `writing-plans` skill only. No other skill may be invoked.

**HARD-GATE:** No implementation, no code, no scaffolding until the user has approved a design. Applies to every project regardless of perceived simplicity.

**Terminal state:** The only skill invoked after brainstorming is `writing-plans`.

**Artifacts produced:**
- Design document at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (committed to git)
- Optionally: visual mockups/diagrams served via local web companion (see §3)

**Interaction style:** Fully interactive dialogue. One question per message. User must explicitly approve design and written spec before the skill proceeds.

---

## 3. Local Webpage / Web UI — Verdict

**VERDICT: YES — superpowers ships and runs a local HTTP+WebSocket server as part of the brainstorming skill's "Visual Companion" feature.**

### Candidate-by-candidate audit

#### Candidate 1: A local HTTP server script
**PRESENT. Ruled IN.**

- `skills/brainstorming/scripts/server.cjs` — a ~250-line zero-dependency Node.js HTTP+WebSocket server (uses only `http`, `crypto`, `fs`, `path` builtins; RFC 6455 WebSocket implemented manually). Binds to `127.0.0.1` on a random high port (49152–65535).
- `skills/brainstorming/scripts/start-server.sh` — shell script that invokes `node server.cjs`; supports foreground (Windows/Codex CI) and background (nohup+disown) modes; writes PID and outputs `{"type":"server-started","port":<N>,"url":"http://localhost:<N>","screen_dir":"...","state_dir":"..."}`.
- `skills/brainstorming/scripts/stop-server.sh` — stops the background server.
- `skills/brainstorming/scripts/frame-template.html` — full HTML page with OS-aware light/dark theming, injected as the wrapper for content fragments the AI writes.
- `skills/brainstorming/scripts/helper.js` — client-side JS injected into served pages; opens a WebSocket back to the server; listens for `reload` messages; captures `[data-choice]` click events and sends them to the server.

**Citations:**
- `server.cjs`: <https://github.com/obra/superpowers/blob/main/skills/brainstorming/scripts/server.cjs> — `const PORT = process.env.BRAINSTORM_PORT || (49152 + Math.floor(Math.random() * 16383));` + `const http = require('http');`
- `start-server.sh`: <https://github.com/obra/superpowers/blob/main/skills/brainstorming/scripts/start-server.sh> — `env BRAINSTORM_DIR="$SESSION_DIR" ... node server.cjs`

#### Candidate 2: An npm/Node package or package.json with a web frontend / dev server
**PARTIALLY present — NOT for a dev server, but the test suite for the brainstorm server has deps.**

- Top-level `package.json`: `{"name":"superpowers","version":"5.1.0","type":"module","main":".opencode/plugins/superpowers.js"}` — no dependencies, no dev server.
- `tests/brainstorm-server/package.json`: `{"dependencies":{"ws":"^8.19.0"}}` — the `ws` package is used only in the test suite to drive WebSocket connections against the server. It is not shipped to users.

**Citation:** <https://github.com/obra/superpowers/blob/main/package.json> (no deps); <https://github.com/obra/superpowers/blob/main/tests/brainstorm-server/package.json> (`ws` test dep only).

#### Candidate 3: An MCP server that opens or serves a browser page
**NOT PRESENT.**

The tree contains no `mcp` directory and no MCP server registration. The `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` install skills, not MCP servers. No file in the tree matches an MCP server pattern.

**What was checked:** Full tree via `gh api repos/obra/superpowers/git/trees/main?recursive=1` — no `mcp/`, no `mcpServers`, no `@modelcontextprotocol` dependency.

#### Candidate 4: A dashboard / viewer / report UI (skills browser, skills-search web page)
**NOT PRESENT as a standalone feature.** The visual companion IS a browser UI, but it is purpose-built for brainstorming content (mockups, wireframes, diagrams) — not a skills browser or general dashboard.

**What was checked:** Full tree. No `dashboard/`, `viewer/`, `skills-browser/` directory. The only `.html` file is `frame-template.html` which is the brainstorm content wrapper.

#### Candidate 5: Any `open`/`xdg-open`/browser-launching command in scripts or hooks
**NOT PRESENT.** The server script explicitly does NOT auto-open a browser. The visual-companion guide states: "tell user to open the URL." The AI tells the human user to navigate to `http://localhost:<PORT>` themselves.

**What was checked:** `gh search code --repo obra/superpowers "open http"` — returned only documentation/plan content quoting the URL pattern, no shell `open` invocation. `start-server.sh` has no `open` call.

### How the web server is launched

The AI agent (within the brainstorming skill flow) runs:
```bash
skills/brainstorming/scripts/start-server.sh --project-dir /path/to/project
```
This starts `node server.cjs` in the background (or foreground on Windows/Codex CI). The server:
1. Picks a random high port (49152+)
2. Outputs startup JSON with the URL, `screen_dir`, and `state_dir`
3. Serves whatever `.html` file the AI writes to `screen_dir` (most recent wins)
4. Sends `reload` messages via WebSocket when new content is written
5. Records `[data-choice]` click events to `state_dir/events` for the AI to read next turn

The human user opens `http://localhost:<PORT>` manually (the AI tells them the URL). The AI then iteratively writes HTML content fragments (mockups, wireframes, architecture diagrams) to `screen_dir` and reads back user selection events.

**Design doc spec:** `docs/superpowers/specs/2026-03-11-zero-dep-brainstorm-server-design.md` — confirms the server was refactored from vendored express+ws+chokidar to a zero-dependency single-file Node.js implementation.

---

## Evidence Table

| Claim | Source | Confidence |
|---|---|---|
| obra/superpowers ships 14 skills under `skills/` | `gh api repos/obra/superpowers/git/trees/main?recursive=1` | certain |
| Each skill has a SKILL.md with frontmatter `description` | Individual SKILL.md reads via gh api | certain |
| Brainstorming is a 9-step interactive dialogue skill with a HARD-GATE against premature implementation | `skills/brainstorming/SKILL.md` (read in full) | certain |
| Brainstorming writes a spec doc to `docs/superpowers/specs/` and transitions to `writing-plans` | Same file | certain |
| Brainstorming ships a local HTTP+WebSocket server (`server.cjs`) on a random high port | `skills/brainstorming/scripts/server.cjs` | certain |
| Server is started via `start-server.sh` using Node.js builtins (zero external deps) | `skills/brainstorming/scripts/start-server.sh` | certain |
| Browser is NOT auto-opened; user navigates manually to the URL the AI provides | `start-server.sh` (no `open` call) + visual-companion.md instructions | certain |
| Top-level `package.json` has no npm dependencies (no web dev server) | `package.json`: `{"name":"superpowers","version":"5.1.0",...}` (no deps key) | certain |
| No MCP server is registered or shipped | Full tree scan — no `mcp/` directory, no `@modelcontextprotocol` dep | certain |
| No dashboard or skills-browser UI exists separately from the brainstorm companion | Full tree scan — no `dashboard/`, `viewer/`, `skills-browser/` | certain |
| `express` appeared in gh search results but only in historical plan docs (not current code) | `docs/superpowers/specs/2026-03-11-zero-dep-brainstorm-server-design.md` confirms express was REMOVED | certain |

---

## Open Questions

- The `using-superpowers` skill establishes that skills override default behavior but user instructions take precedence. Whether easy-cheese's `CLAUDE.md` would conflict with any superpowers skill (e.g., TDD mandate, brainstorm HARD-GATE) is worth reviewing for parity.
- The `writing-skills` skill references `anthropic-best-practices.md` — this file is at `skills/writing-skills/anthropic-best-practices.md` and may contain Anthropic-specific skill-authoring conventions not covered by this research.
- The brainstorm server is Node.js-only. If easy-cheese users do not have Node.js installed, the visual companion will not work. Whether a fallback is documented is not confirmed here.

---

## Confidence

**Overall: certain** — all findings derived from primary source files read directly via `gh api`. No secondary sources needed for the core questions. The web-UI finding required checking 5 distinct candidate mechanisms; all were ruled in or out with direct file citations.
