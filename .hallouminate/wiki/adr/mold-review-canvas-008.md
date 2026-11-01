# ADR: Replace subject layouts with Mold shape views and pins

Status: accepted (2026-09-27); implemented in PR #731. Supersedes [mold-review-canvas-004](./mold-review-canvas-004.md).

## Context

The first canvas composed frontend, TUI, backend, and mixed layout cards beside a question column.
Those cards held static placeholders and did not show the Mold ledger, placement, gates, or decision map.
The Mold Canvas v2 design puts the Mold artifacts beside the forks.

## Decision

The canvas shows shape views: `all`, `ledger`, `placement`, `diagram`, `gates`, and `decision map`.
A view is disabled when the review document does not supply its data.
The `all` view leaves out the gates and decision-map audit views.
A conversation rail holds the agent summary, the forks, the queued notes, and the composer.
In annotate mode, a click on a ledger item, placement row, or decision-map item adds a numbered pin.
Diagram artifacts get a `+ note` button, so Excalidraw and Mermaid keep their own pointer input.

The Mold companion keeps full settled and draft EARS requirements in a persistent pane outside the shape tabs.[^1]
Each requirement can show linked open forks and their waiting state.
Publish the complete current requirement list each round, with stable requirement and fork IDs.

Independent, already-explained forks can share one submission.
A dependent fork stays visible but disabled until the agent reconciles every prerequisite in a new revision.
Each prerequisite must appear in `settled_fork_ids` and disappear from the open `questions` list.
Local selection, autosave, submission, and restored feedback never settle a fork.
The browser excludes waiting answers from feedback and shows malformed or missing dependencies as errors.[^1]

## Feedback contract

Feedback drops `layout` and adds `view`, `pins` (`{id, anchor, text}`), and `end_session`.
`annotations` repeats the pins as numbered text, so text-only pollers still get the notes.
`send & end` sends `end_session: true` with operation ID `browser-<revision>-end`.
The distinct ID stops `review.py` from rejecting a second submit on the same revision.
`end_session` asks the agent to close the review; it is not Mold approval.
The browser coerces agent-supplied fields to the expected types, so a malformed document still renders.
It drops malformed requirement records and non-string fork references without removing valid requirements or conversation controls.[^3]
`review.py` still stores any JSON object; the field table lives in `skills/mold/references/review-canvas.md`.

## Alternatives

- Keep subject layouts and add Mold artifacts as another card. This keeps placeholder cards that show no review evidence.
- Validate the document and feedback shapes in `review.py` or a published schema. This moves the contract to the trust boundary but is a larger change; it stays open.

## Consequences

The TUI and backend layout cards are gone. A subject-specific mockup now arrives as a declared diagram artifact.
A phone viewport below 56rem keeps the bottom sheet for legacy documents without requirements.
Documents with requirements use separate viewport-bound scroll panes for requirements, shapes, and conversation.[^2]
A lowered legacy sheet does not hide conversation controls after switching to a requirements revision.[^3]

## Related records

- [Browser layouts ADR (superseded)](./mold-review-canvas-004.md)
- [Revision-bound feedback](./mold-review-canvas-005.md)


[^1]: skills/mold/references/review-canvas.md:39-72
[^2]: frontend/mold-review/src/style.css:125-131; frontend/mold-review/tests/canvas.spec.js:353-381
[^3]: frontend/mold-review/src/main.jsx:215-217,454; frontend/mold-review/tests/canvas.spec.js:423-468

_Source: Mold companion requirement and fork-settlement implementation · Updated: 2026-11-01 · Supersedes: unconditional phone bottom-sheet layout · 2026-11-01_
