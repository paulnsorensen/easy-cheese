# Auto mode — complete process

Use this process for `/affinage --auto --stake <floor>`.
Also use it for `--plate`, which adds `--stake medium+ --open-pr`.
`SKILL.md` defines the decisions.
This file defines each step.

- Skip the selection gate.
- Send merge conflicts to `/melt` before `/cure`.
- Stop with `status: halt: merge-conflicts-need-human` when `/melt` cannot resolve them.
- Run fresh `/age` in standalone mode unless the user passes `--no-age`.
- Add `[from-age:…]` findings to the automatic selection.
- Select every finding that meets the floor.
- Include cheap, contained low findings when the floor is `medium+`.
- Send `/cure --auto --stake <floor>`.
- Wait for `/cure` and its `/age --scope --auto` chain to stop.
- Post replies only for the original graded claims.
- Do not grade findings from `/age --scope` again.
- Post the prepared push-back for each `Reviewer-rejected` claim.
- Post a specific follow-up note for each `Needs-investigation` claim.
- Name the test, prototype, or evidence that can confirm the claim.
- Use `Needs <evidence> to confirm — will follow up with the result.`
- Do not run the investigation in auto mode.
- Post all replies before terminal `/plate` publishes fixes.
- Send terminal `/plate --open-pr [--hard]` only when `/cure` applies a fix.

Keep the complete cure chain in the parent affinage context.
The parent must retain finding slugs, comment identifiers, tags, and reply text.
A child agent cannot post these replies reliably.

If no finding meets the floor, skip `/cure`.
Post only rejection and investigation replies.
Exit with `status: ok / next: done`.
