# Wiki conventions for easy-cheese

You — the agent writing entries in this wiki — are bound by a few
conventions the hallouminate indexer counts on, plus the durable-vs-
transient boundary that decides whether a fact belongs here at all.

This page is silent on per-entry lifecycle and frontmatter schema. That
contract is owned by a separate seam; do not invent frontmatter fields
here.

## Durable vs transient — the boundary that decides everything

Before writing anything, decide which lane the fact belongs in — and
note that **durability is not the same axis as git-tracking**. There are
three lanes, two of which live outside git (`skills/cheese/references/formatting.md:103`):

| Where | Git | Lifecycle | Use for |
|---|---|---|---|
| `.hallouminate/wiki/` (`repo:easy-cheese:wiki`) | **tracked** | durable across sessions | architecture, protocols, conventions, rationale, and specs explicitly promoted for repository review |
| `$XDG_DATA_HOME/cheese/<project>/` (`paths.py`) | **out of git** | durable across branches/clones | Mold specs and research reports by default |
| `.cheese/` (`cheese-local`) | **gitignored** | transient per-task | `/cook` `/age` `/press` `/cure` reports, notes, hard, handoffs, exploration |

**Durable ≠ git-tracked.** Architecture, conventions, and rationale are
durable and committed in this wiki. Mold specs and research reports default
to the stable XDG project corpus so they survive branch switches and clones.
The path math is owned by `shared/scripts/paths.py` (`project_corpus_root`,
`artifact_path`). Pipeline output stays repo-local and gitignored under
`.cheese/` (`.gitignore:2`).

A spec may be promoted from XDG into `.hallouminate/wiki/specs/` when a
human explicitly asks to review and approve the specification in a PR. The
tracked copy then becomes the implementation authority for that change; the
XDG original remains source provenance, not a second authority. This is an
intentional review exception, not the default Mold output path.

> **Migration note.** Some skill docs still name `.cheese/specs/<slug>.md`.
> That path predates the durable/transient split and is being moved onto
> the `paths.py` helpers (`skills/cheese/references/formatting.md:103`); treat
> the XDG corpus as the default home for specs unless a human promotes one
> for repository review.

Classify in two steps:

1. *Worth keeping past the task that produced it?* No → transient,
   `.cheese/`.
2. If durable: architecture, protocol, convention, or rationale → this
   wiki; ordinary spec or research report → XDG; explicitly review-promoted
   spec → `.hallouminate/wiki/specs/`.

Concrete classification examples:

- "The pipeline order is culture → mold → cook → press → age → cure" → **durable → wiki**.
- "The approved Mold spec for the durable-memory boundary" → **durable → XDG corpus by default**.
- "Review this spec and its ADRs in a PR" → **durable → tracked wiki spec**.
- "Curd #3 of the durable-memory spec failed its press pass" → **transient → `.cheese/`**.
- "The retired code-intelligence wrapper skills became a shared routing contract" → **durable → wiki**.
- "The age report for PR #107 flagged two medium findings" → **transient → `.cheese/`**.

## One topic per file

A wiki entry is a slice of knowledge with a clear scope. If you find
yourself drafting two unrelated topics in one file, split them. The
chunker breaks markdown by H1/H2/H3 headings — a file with two H1
sections will still chunk, but `ground` will rank both sections together,
which is almost never what you want.

## First non-blank line is the H1

The first non-blank line of every entry must be `# Topic Name`. The
chunker uses the H1 as the breadcrumb root for every chunk in the file,
and the auto-index reads it as the trailing gloss on the file's link
row. Skip the H1 and breadcrumbs degrade and the index row is ungloss'd.

## File stem matches the slug

Topic "Workflow invariants" → file `workflow-invariants.md`. Lowercase,
kebab-case, no spaces, no capitals, `.md` only. The stem is what other
pages link to and what shows up in `ground` outline paths.

## Idempotent writes

`add_markdown` rejects existing files by default. To update:

1. `read_markdown` to inspect current content.
2. Decide what changes.
3. `add_markdown` with `overwrite: true`.

This forces a look at current state before clobbering, so concurrent
authors don't silently lose each other's edits.

## Tree layout & progressive disclosure

Top-level files hold foundational topics (`architecture.md`,
`workflow-invariants.md`, `tooling.md`, `wiki-conventions.md`). Group
related entries under subdirectories as the wiki grows
(`add_markdown` accepts nested paths and creates parents on demand).

Every directory carries an `index.md`: the first H1 names the subtopic,
the body holds curated prose plus a link list to siblings and children.
The daemon scaffolds and maintains the link list between
`<!-- HALLOUMINATE:INDEX-START -->` / `<!-- HALLOUMINATE:INDEX-END -->`
markers — prose outside the markers is preserved verbatim. Remove the
marker pair to opt a file out of auto-indexing.

### Link convention

- `[stem](./stem.md)` for files in the same directory.
- `[subdir/](./subdir/index.md)` for child directories.
- Relative paths only — the wiki should survive moving the whole tree.

## When to update — the post-land cadence

`AGENTS.md` instructs every agent to refresh this wiki **after a change
lands on `main`**, but only when the change altered durable knowledge:
architecture, protocols, conventions, or a "why this design not that one"
decision. Routine bug fixes and per-task output stay in `.cheese/`.

Do the update through the hallouminate MCP (`read_markdown` →
`add_markdown { overwrite: true }`), not raw file edits, so the LanceDB
index and ancestor `index.md` link lists stay in sync.

## The authoring loop

```text
1. list_tree                            (see the existing shape)
2. ground "<topic adjacent search>"     (find related entries)
3. read_markdown index.md               (confirm naming + style)
4. draft the page (H1 first line, kebab slug, link siblings)
5. add_markdown { corpus: "repo:easy-cheese:wiki",
                  path: "<slug>.md", content: "<markdown>",
                  overwrite: false }
6. (the daemon rewrites ancestor index.md link lists for you)
```

## Style

Follow repository-specific terminology and voice first. For editorial questions that the repository does not answer, follow the Google developer documentation style guide.[^1]

- Lead with the conclusion. Don't bury the point under preamble.
- Address the reader directly, prefer active voice, and put conditions before instructions.
- Use sentence case for headings.
- Format filenames, commands, symbols, and other code-related text with backticks.
- Use descriptive link text instead of generic phrases such as "click here."
- Cite files and line ranges by path: `skills/mold/references/handshake.md:1-3`.
- Cite commits by SHA when behavior depends on history.
- Prefer concrete examples to abstract description.
- Keep entries short — ~50–150 lines is the right band. A wiki page is
  not a tutorial.

[^1]: https://developers.google.com/style/

_Source: repository documentation convention · Updated: 2026-08-28 · Supersedes: uncodified editorial fallback guidance_
