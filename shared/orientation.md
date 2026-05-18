# Codebase orientation

Use this reference when a workflow skill needs a one-screen mental model of the repo before it does anything else. Orientation is **codebase-level** (vital signs → entry points → domain models → architecture → key deps), not symbol-level — for single-symbol blast-radius checks see `skills/mold/references/shape-check.md`.

## Why it lives here

`/cheese`, `/culture`, and `/mold` all benefit from the same map, and any of them might be the first skill the user invokes in a fresh session. Without a shared cache they each run the same five-step walk and burn the same tokens. This reference is the recipe; the cache file is the deduplication mechanism.

## Cache contract

| Field | Value |
| --- | --- |
| Path | `.cheese/orient/<slug>.md` |
| Slug | basename of `git rev-parse --show-toplevel` (e.g. `new-york-v2`) |
| Persistence | gitignored under `.cheese/` — survives the session, never committed |
| Owner | whichever skill writes it first; later callers read it |

### Read-or-write procedure

Every caller runs this exact sequence before doing any orientation work:

1. Compute the slug: `slug=$(basename "$(git rev-parse --show-toplevel)")`.
2. Check whether `.cheese/orient/<slug>.md` exists.
3. **If it exists**, read it and load its contents into the parent context. Print a one-line acknowledgement (`Orientation: loaded from .cheese/orient/<slug>.md (HEAD <sha>)`). Skip the recipe. Done.
4. **If it does not exist**, run the five-step recipe below, write the result to `.cheese/orient/<slug>.md` with the frontmatter spec'd below, then load the contents into the parent context. Print a one-line acknowledgement (`Orientation: generated at .cheese/orient/<slug>.md`). Done.

### Staleness

The cached file's frontmatter records the HEAD SHA and the generation timestamp. A caller MAY regenerate when:

- The current `HEAD` differs from the cached `head` AND the diff is large (rough heuristic: `git diff --shortstat <cached-head>..HEAD` reports > 200 lines or > 20 files changed).
- The cached `generated_at` is more than 7 days old.
- The user explicitly asks for a refresh (`refresh orientation`, `re-orient`, `redo grounding`).

When regenerating, overwrite the file in place — do not version it. There is one cache slot per repo.

Skills MUST NOT regenerate on every invocation. The whole point of the cache is to avoid triplicate work; pessimistic invalidation defeats it.

## File format

```markdown
---
slug: <basename>
generated_at: <ISO-8601 UTC timestamp>
head: <git short SHA at generation time>
branch: <branch name at generation time>
---

# Orientation: <repo name>

**Stack:** <language>, <framework>, <database or storage>
**Size:** ~<N> source files | ~<LOC> lines
**Shape:** <one-line architecture pattern — e.g. "vertical slices under src/domains/", "layered Rails app", "single Go binary with cmd/ pkg/ split">

## Domain models

- **<Model>** — <one-line description in business terms>
- **<Model>** — <one-line description in business terms>

## Entry points

- `<path>` — <what starts here>
- `<path>` — <what starts here>

## Architecture

<2-3 sentences on how the system is structured: where business logic lives, where infrastructure lives, how modules communicate.>

## Key dependencies

- **<dep>** — <what it's used for in this repo>
- **<dep>** — <what it's used for in this repo>

## First impressions

- <one observation a reader should carry into the work>
- <one concern or open question worth flagging>
```

Keep the whole file to one screen — roughly 40 lines of body. Callers will load this verbatim into context, and a thesis-length orientation defeats the purpose.

## The five-step recipe

Run these in order. The whole pass should fit in a handful of tool calls.

### 1. Vital signs

- Detect language and package manager from manifest files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `mix.exs`, etc.
- Count source files (exclude tests, vendored, generated). Rough LOC via `tokei` if available, else `wc -l` on a glob.
- First commit date and last 10 commits for activity colour.

### 2. Entry points

Find how the system starts and what it exposes:

- Process entrypoints: `main.*`, `index.*`, `app.*`, `server.*`, `cmd/*/main.go`, `bin/*`.
- CLI scripts: `bin/`, `scripts/`, `cmd/`.
- HTTP / RPC routes or handlers, if the framework registers them in a discoverable place.
- Configuration / bootstrap files (where wiring happens).

### 3. Domain models

Identify the nouns of the system — what business concepts the code is built around:

- Look for type / class / struct / record definitions in the main source directory.
- Name them in business terms ("Orders, Customers, Invoices") rather than technical types ("OrderModel, OrderEntity").
- Note where they live and whether they import infrastructure (a smell worth flagging in *First impressions*).

### 4. Architecture shape

Determine the high-level structure in one paragraph:

- Monolith, modular monolith, or service-style split?
- Vertical slices, layered, hexagonal, or mixed?
- Where does business logic live? Where does infrastructure live?
- How do modules communicate — direct imports, events, RPC, a registry?

### 5. Key dependencies

From the manifest files, name the dependencies that shape the architecture (framework, database client, queue / event bus, validation, auth). Skip noisy transitive deps and dev tooling — only call out what a reader needs to know to navigate.

## Tool preferences

| Need | Prefer | Fallback |
| --- | --- | --- |
| Manifest detection | `cheez-read` `tilth_files` | host `ls` / `Glob` |
| Source file counting | `tokei` | `cheez-read` `tilth_files` with extension filter |
| Symbol discovery | `cheez-search` `tilth_search kind: "symbol"` | LSP `documentSymbol`, then text search |
| Dependency / import map | `cheez-search` `tilth_deps` on an entry point | inspecting top-of-file imports manually |
| Git activity | `git log` (plain) | — |

If `tilth` MCP is unavailable, fall back to LSP and host tools per the cheez-* portability rule — but do not skip the recipe entirely. Mark anything you could not verify with `[?]` in the orientation body so downstream readers know.

## What orientation never does

- Reads file contents to understand business logic line-by-line (skim only — domain *names*, not domain *logic*).
- Renders a code review or severity-rates anything (`/age` owns that).
- Fetches external documentation (`/briesearch` owns that).
- Modifies any files outside the cache slot.
- Spans multiple files in the cache — there is one cache slot per repo.

## Calling-skill checklist

A workflow skill wiring this in should:

1. Run the read-or-write procedure as the first substantive step (after the input parse, before classification / dialogue / mode routing).
2. Print the one-line acknowledgement so the user knows whether orientation was cached or freshly generated.
3. Reference orientation in subsequent reasoning (`per orientation, the domain models are X, Y, Z`) rather than re-deriving facts the cache already supplies.
4. Honour explicit refresh verbs from the user (`re-orient`, `refresh orientation`) by deleting the cache and re-running the recipe.
