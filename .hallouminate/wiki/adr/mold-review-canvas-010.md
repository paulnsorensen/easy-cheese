# ADR: Keep requirements and fork settlement visible in the review canvas

Status: accepted (2026-11-01). Amends [mold-review-canvas-008](./mold-review-canvas-008.md).

## Context

The canvas showed forks but not the EARS requirements that the forks settle.
A fork that depends on another fork had no way to wait for the agent.
A phone viewport below 56rem put the conversation in a bottom sheet over the shapes.

## Decision

The canvas keeps full settled and draft EARS requirements in a persistent pane outside the shape tabs.[^1]
Draft requirements list before settled ones, so the requirements under active shaping show first.
Each requirement can show linked forks: an open fork shows its prompt and, when not answerable, its waiting or dependency-error state.
A settled fork shows its ID with `settled`, and an unresolved link stays visible.
The agent publishes the complete current requirement list each round, with stable requirement and fork IDs.

Independent, already-explained forks can share one submission.
A dependent fork stays visible but disabled until the agent reconciles every prerequisite in a new revision.
`settled_fork_ids` is cumulative: the agent republishes every fork settled so far in each round.
Each prerequisite must appear in `settled_fork_ids` and disappear from the open `questions` list.
Local selection, autosave, submission, and restored feedback never settle a fork.
The browser disables waiting and dependency-error questions, shows no restored answer on them, and excludes them from feedback.
It shows malformed or missing dependencies as errors.[^2]

The browser drops malformed requirement records and non-string fork references without removing valid requirements or conversation controls.[^3]

A phone viewport below 56rem keeps the bottom sheet for legacy documents without requirements.
A document with requirements stacks separate scroll panes for requirements, shapes, and conversation.
Each pane keeps a usable minimum height in small-viewport (`svh`) units, so a collapsing browser toolbar does not resize the panes.
The shapes minimum applies to the shape content below the view tabs, so tabs that wrap on a narrow screen do not shrink it.
The page scrolls on short screens.[^4]
A lowered legacy sheet does not hide conversation controls after switching to a requirements revision.[^5]

## Alternatives

- Split a viewport-bound phone screen into equal fractions. Under a multi-line goal at 375x667, the requirements and fork panes collapsed to 0-1 px, so this fails.
- Read settlement from local answers. A local answer is not agent reconciliation, so this breaks the rule that only a new revision unlocks a fork.

## Consequences

On a phone, a requirements document scrolls the page past the panes. Each pane scrolls its own content.
`review.py` does not validate these fields; that validation stays open.

## Related records

- [Replace subject layouts with Mold shape views and pins](./mold-review-canvas-008.md)

[^1]: `skills/mold/references/review-canvas.md:40-71`; `frontend/mold-review/src/main.jsx:260`
[^2]: `frontend/mold-review/src/main.jsx:243-255`; `frontend/mold-review/tests/canvas.spec.js:258-322`, `:325-357`, and `:463-504`
[^3]: `frontend/mold-review/src/main.jsx:215-217`; `frontend/mold-review/tests/canvas.spec.js:531-557`
[^4]: `frontend/mold-review/src/style.css:125-131`; `frontend/mold-review/tests/canvas.spec.js:359-390`, `:392-437`, and `:439-461`
[^5]: `frontend/mold-review/tests/canvas.spec.js:506-529`

_Source: PR #848; `skills/mold/references/review-canvas.md`, `frontend/mold-review/src/main.jsx`, `frontend/mold-review/src/style.css`, `frontend/mold-review/tests/canvas.spec.js` · Updated: 2026-11-02_
