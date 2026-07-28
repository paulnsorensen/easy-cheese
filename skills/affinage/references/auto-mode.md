# Auto mode — full mechanics

Read this when running (or dispatching) `/affinage --auto --stake <floor>` (or `--plate`, which enters this mode with `--stake medium+ --open-pr`). The body's `## Auto mode` states the decision spine; this is the full step detail.

- Skip the selection gate.
- If the PR has merge conflicts, resolve them via `/melt` first (see `merge-conflict.md`). If `/melt` cannot resolve, halt with `status: halt: merge-conflicts-need-human` before any `/cure` dispatch.
- If standalone (and `--no-age` not passed), run the fresh `/age` pass so `[from-age:…]` findings join the floor-based auto-selection.
- Auto-select every finding (comment-sourced, CI-sourced, OR fresh-`/age`-sourced) that meets the floor — severity at or above the floor, plus cheap contained-fix lows when the floor is `medium+` (same floor semantics as `/cure`).
- Dispatch `/cure --auto --stake <floor>`.
- After `/cure --auto` and its downstream `/age --scope --auto` chain settle, post replies for the originally graded items only. Do NOT re-grade for findings discovered by `/age --scope`.
- Reviewer-rejected items: post the pre-drafted push-back.
- Needs-investigation items: post the explicit follow-up note naming the evidence that would settle the claim (`"Needs <named test/prototype> to confirm — will follow up with the result."`). Auto mode does not pause to run the spike; it posts the honest follow-up note, never a blind acknowledgement.
- After the cure chain settles and **all** replies are posted (previous two bullets), `/affinage` dispatches terminal `/plate --open-pr [--hard]` to publish cure's fixes — the final writes precede publication. `/cure` suppresses its own terminal `/plate` for the `/affinage` chain (keyed on `source_skill: /affinage`). Skip the dispatch when no fix was applied.

The whole cure chain (cure → `/age --scope --auto` → up to the two-cure-pass cap) must run in the parent affinage context so the post-cure reply step still has the original graded findings (slug, ids, `from-comment:<id>` tags, drafted push-back text) in memory. Spawning the cure chain in a sub-agent breaks reply posting — do not.

If no findings meet the floor, skip the `/cure` dispatch, post replies for `Reviewer-rejected` + `Needs-investigation` items only, and exit with `status: ok / next: done`.
