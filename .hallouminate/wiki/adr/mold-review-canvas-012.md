# ADR: Scroll the review canvas as one page and give fork options room

Status: accepted (2026-11-22). Amends [mold-review-canvas-010](./mold-review-canvas-010.md) and [mold-review-canvas-011](./mold-review-canvas-011.md).

## Context

The canvas shell was bound to the viewport (`block-size: 100dvh`), and each pane scrolled on its own.[^1]
At 1280x640 the document never scrolled, the shapes pane fell to 0px, and a 1100px fork showed through a 160px window (issue #900).
On a phone, a document with requirements stacked three nested scroll panes, and a legacy document put the conversation in a fixed bottom sheet over the shapes (issue #901).
Fork options rendered as one 12px dim paragraph in a 400px rail, with the option id joined to the text and the legend on the card border (issue #902).

## Decision

The page is the only vertical scroller. No layout pane (requirements, shapes, conversation) scrolls its content on its own.[^2]
The shell grows with its content, so every fork, diagram, and the composer is reachable by page scroll on any viewport.
On desktop the composer is `position: sticky` at the viewport bottom while the conversation is on screen, so the send controls stay as reachable as in the viewport-bound shell.
Below 56rem the requirements, shapes, and conversation stack in page order. Documents with and without requirements share one layout. The bottom sheet and its lower and raise control are gone.
This replaces the ADR 010 phone rule of separate scroll panes with `svh` minimum heights, and its legacy-sheet rule.

The conversation rail is `clamp(26rem, 36vw, 36rem)` wide, so fork text holds about 45-75 characters on a line at 1440px.
Option detail is 14px in the main text color. The option id is a separate chip after the label. The fieldset legend floats inside the card.[^3]
An option accepts `gains`, `costs`, and `risks` string lists. The card renders one line for each item with the fork-card mark and word (`✔ gain`, `✘ cost`, `⚠ risk`). `tradeoff` still renders as one paragraph.

## Alternatives

- Keep viewport-bound panes and raise their minimum heights. A dense fork is taller than a short viewport, so a pane still clips it, and nested scroll traps wheel and swipe input.
- Keep the phone bottom sheet for legacy documents. The sheet covers the shapes, and two phone layouts double the test surface.

## Consequences

On desktop a long requirements list pushes the shapes down the page instead of scrolling inside its pane.
A sticky composer covers the bottom of the rail while the user scrolls; it takes about 150px at 640px height.
The publish warnings and decides, moves, and today fields that issue #904 proposes are not part of this record.

## Related records

- [Keep requirements and fork settlement visible in the review canvas](./mold-review-canvas-010.md)
- [Lead Mold forks from evidence and keep the ledger in EARS](./mold-review-canvas-011.md)

[^1]: issues #900, #901, #902 measured on `main` at `d5390ec`
[^2]: `frontend/mold-review/src/style.css` § Shell, § Conversation, and the 56rem media query; `skills/mold/references/review-canvas.md` § Review document; `frontend/mold-review/tests/canvas.spec.js` desktop and phone page-scroll tests
[^3]: `frontend/mold-review/src/components/Question.jsx` `OptionCard`; `frontend/mold-review/src/design/components.css` § Question and § OptionCard; `frontend/mold-review/tests/canvas.spec.js` fork-card readability test

_Source: issues #900, #901, #902; `frontend/mold-review/src/style.css`, `frontend/mold-review/src/components/Question.jsx`, `skills/mold/references/review-canvas.md` · Updated: 2026-11-22_
