# Verdict: reject

Two blocker findings prevent approval.
The review found four high findings, one medium finding, and one low finding.

## Findings

### Blocker

- **[correctness:blocker] Conflict resolution cannot reach publication.** `skills/affinage/references/merge-conflict.md:15-17` checks remote status before any commit or push. `src/easy_cheese/skills/affinage/pr_status.py:208-228` reads the unchanged GitHub merge state. `skills/affinage/SKILL.md:105-109` also skips Plate when Cure applies no fix. `skills/melt/SKILL.md:181-184` forbids Melt commits. The documented order checks unchanged remote state and then halts. Location: contract. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. **Fix:** Keep the resolved local merge for Plate. Treat conflict resolution as a publishable change. Let Plate commit and push before another remote status check.
- **[spec:blocker] The reply gate cannot approve Cure replies.** `skills/affinage/SKILL.md:101-104` requires applied and deferred replies. `skills/affinage/references/handoff-templates.md:30-38` offers options only for rejected and investigation replies. `skills/affinage/SKILL.md:244` forbids unapproved replies. The default flow must omit Cure replies or post them without approval. Line 30 also requires a gate before every reply call. Location: contract. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. **Fix:** Show one batch approval gate after Cure. Add applied and deferred replies to the gate options. Include those replies in `Post all` and `Per-finding`.

### High

- **[spec:high] Affinage contradicts the shared portability rules.** `skills/affinage/SKILL.md:59-64` permits `${CLAUDE_SKILL_DIR}` and quotes a host rule. `skills/cheese/references/harness-portability.md:15-17` prohibits that variable in invocation paths. Lines 70-80 call slash commands presentation, not host renderings. Location: contract. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Remove the variable fallback. Use the current portability term without a false quotation.
- **[spec:high] The halt instruction omits the required `status:` key.** `skills/affinage/SKILL.md:171-183` defines the preamble but tells the writer to use `halt: <reason>`. `skills/cheese/references/handback-contract.md:17-25` requires `status: <status>`. Other Affinage flow instructions use the correct form. Location: contract. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Replace the malformed value with `status: halt: <reason>`.
- **[spec:high] The report template emits an invalid location value.** `skills/affinage/references/report-template.md:30-32` uses `location: hot path`. `skills/age/references/dimensions.md:44-65` permits only `class`, `module`, `cross-module`, or `contract`. Location: contract. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Use `location: module` in the example. Keep hot-path evidence in the finding text.
- **[correctness:high] Review-body replies are not idempotent.** `skills/affinage/SKILL.md:81-86` fetches review bodies but checks replies only on inline threads. `src/easy_cheese/skills/affinage/post_reply.py:134-136` posts a review-body reply as an unlinked issue comment. A later run cannot associate that comment with the review body. It can post the same reply again. Location: contract. Fix cost now: contained. Fix cost later: spreading. Confidence: certain. **Fix:** Add a stable review identifier to each PR-level reply. Skip a review body when an existing issue comment has that identifier.

### Medium

- **[spec:medium] Four prose files violate the required STE100 rules.** `skills/affinage/SKILL.md:44,51,84,194,202` puts multiple instructions in one sentence. `skills/affinage/references/flow-details.md:75` and `handoff-templates.md:22` do the same. `SKILL.md:76,111,217`, `auto-mode.md:11`, and `flow-details.md:23` use three terms for one fresh review. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Split each multi-action sentence. Use `fresh review` for the process in every file.

### Low

- **[spec:low] One output instruction assigns Affinage sections to Age.** `skills/affinage/SKILL.md:92-95` calls them two Affinage sections. Line 168 says Age supplies `Needs-investigation` and `Reviewer-rejected`. Age does not define those sections. Location: module. Fix cost now: contained. Fix cost later: contained. Confidence: certain. **Fix:** Attribute only the severity sections to Age. Attribute the other two sections to Affinage.

## Simplifications

- Keep auto-mode decisions in `SKILL.md`. Keep the detailed process only in `references/auto-mode.md`.
- Keep conflict order and ownership only in `references/merge-conflict.md`. Link to that contract from `SKILL.md`.
- Use `fresh review` as the only term for the extra Age pass.
- Keep the four command wrappers. The static command manifest requires their decorators.
- No `_with_summary` helper remains. `derive_command` owns command summaries.

## Edge check

| Edge | State | Evidence |
| --- | --- | --- |
| Affinage to shared command manifest | ok | `commands.py:7-11,42-59`; `bundle_commands.py:61-83,140-164`; bundle help lists all four commands. |
| Affinage to shared review routing | ok | `age_route_cli.py:11-15`; `age_route.py:140-207`; `review_surface_cli.py:114-143`; both command probes returned valid JSON. |
| Affinage to shared paths and handback | broken | `paths.py:71-75` supports Affinage, but `SKILL.md:181-183` omits the required `status:` key. |
| Affinage to Age | broken | `report-template.md:30-32` emits a location value outside `dimensions.md:44-65`. |
| Affinage to Cheese | broken | `SKILL.md:59-64` contradicts `harness-portability.md:15-17,70-80`. |
| Affinage to Cure | ok | `cure/SKILL.md:190-194` returns control to Affinage; `cure/references/auto-mode.md:32-33` preserves publication ownership. |
| Affinage to Melt | broken | `merge-conflict.md:12,15-17` conflicts with `melt/SKILL.md:181-184` and checks remote state too early. |
| Affinage to Plate | broken | `SKILL.md:105-109` skips Plate after a conflict-only change; `plate/SKILL.md:61-65` owns commit and validation. |
| Affinage to hard-cheese | ok | `SKILL.md:229-234`, `plate/SKILL.md:45-46`, and `hard-cheese/SKILL.md:29-32` place the gate at Plate. |
| Affinage to Pasteurize | ok | `flow-details.md:83-89` requests a regression test; `pasteurize/SKILL.md:3-5` provides that path. |
| Affinage to Briesearch | ok | `flow-details.md:83-89`; `briesearch/SKILL.md:3-16` accepts external evidence requests. |
| Build to Affinage | ok | Generated-region validation passed; bundle help lists `age-route`, `post-reply`, `pr-status`, and `review-surface`. |

Live GitHub posting remains untested because this review must not run `gh`.
The focused contract suite passed 212 tests.
Skill validation and generated-region validation also passed.

## STE100 status

- `skills/affinage/SKILL.md` needs sentence splits and one fresh-review term.
- `skills/affinage/references/auto-mode.md` needs the same fresh-review term.
- `skills/affinage/references/flow-details.md` needs one sentence split and the same term.
- `skills/affinage/references/handoff-templates.md` needs one sentence split.

All prose sentences stay within the applicable word limit.

## Follow-ups

- The planned Affinage cure must apply all findings in this note.
- No separate cross-area follow-up is required.
