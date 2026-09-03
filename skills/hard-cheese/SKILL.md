---
name: hard-cheese
description: Checks whether an author can explain a code change before review. Use when the user requests `/hard-cheese`, `/cheese --hard`, or an understanding check. Use it before a pull request or through the `--hard` pipeline flag. Do not use it for reviews, test hardening, or fixes.
license: MIT
metadata: {dispatches-agents: true}
---

# /hard-cheese

The gate reduces **epistemic debt**. This debt exists when code passes checks, but the author cannot explain it.

## Inputs

```text
/hard-cheese [<slug>] [--socratic-cap N=3] [--passing-score N=3] [--no-judge]
```

Arguments:

- `<slug>` identifies the artifact at `.cheese/hard-cheese/<slug>.md`. This argument is optional. Without it, use the short SHA of `HEAD`. An explicit slug overrides the SHA.
- `--socratic-cap N` sets the maximum number of retries. The gate then marks the artifact `FAILED` and returns a non-zero status. The default is `3`. Vibecheck has no limit, but easy-cheese prevents infinite loops.
- `--passing-score N` sets the minimum SOLO score for PASS. Use a value from `1` through `5`. The default is `3`. The gate treats a previous PASS below this value as stale.
- `--no-judge` enables log-only mode. Record the user's explanation with `status: LOGGED`. Do not start the judge sub-agent. This mode matches the optional JSONL telemetry mode in vibecheck.

## Invocation modes

| Mode | How it fires | Where the gate sits |
| --- | --- | --- |
| **standalone** | User runs `/hard-cheese <slug>` directly before opening a pull request. | Outside the pipeline. No upstream skill required. |
| **propagated** | `/plate --hard` invokes `/hard-cheese <slug>` after its final writing gate and before publication. | At the verified-artifacts → share-for-review boundary. |

`--hard` passes through `/cheese → /mold → /cook → /press → /age → /cure → /plate`. Only `/plate` calls `/hard-cheese`.

See [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md) for portability requirements. It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions.
Use the bundle or repository helper first. Use `${CLAUDE_SKILL_DIR}` only as an optional host fallback.
The handoff blocks define the portable contract because slash commands are host renderings, not the control model.

## Flow

1. **Resolve scope.**
   - Set `diff_base = origin/main` and `diff_head = <short-sha of HEAD>`.
   - Load `.cheese/specs/<slug>.md` as the optional intent reference when it exists. The diff remains the source of truth.
   - Use the short SHA of `HEAD` when no slug exists.
   - If the diff against `origin/main` is empty, return `0` with `"nothing to gate on"`. Do not write an artifact.

2. **Freshness check.**
   Check freshness before launching the gate:

   ```
   python3 skills/hard-cheese/scripts/hard-cheese.pyz freshness-check \
     --slug <slug> --passing-score <n>
   ```

   Exit `0` for `previously_passed`. Print `"previously passed"` and stop. Continue to step 3 for `stale` or `new`.
   A stale result has exit status `2`. A new result has exit status `3`.
   A result is stale when `HEAD` changes or the last PASS score is too low.

3. **Compose the vibecheck prompt.** Keep it faithful to Sankaranarayanan 2026. Use "share for review" to keep the gate implementation independent.

   > Before this is shared for review, explain its causal logic in your own words. How does *<feature or fix>* work? Why does it produce the desired behavior? What state, control flow, or invariants does it rely on?

   Show a diff summary with the prompt. For `/plate`, also show the final artifact inventory and each `{target, backend, verified}` row.

4. **Record the user's explanation** as free text. Do not provide coaching or example answers. The explanation is the artifact under test.

5. **Start the judge sub-agent** in a fresh context. Use the same pattern as the `/cook` fan pathway.
   - Use `references/judge-prompt.md` as the system prompt.
   - Provide the passing score, diff summary, optional spec excerpt, and user's explanation.
   - Require this JSON object: `{score, level, pass, feedback, socratic_qs}`.

   See `references/judge-prompt.md` for the full system prompt and output shape.

   Skip this step when the user sets `--no-judge`. Mark the attempt `status: LOGGED`, write the artifact, and return `0`.

6. **Process the judge result.**
   - Mark the attempt PASS when `score >= <passing-score>`.
   - Mark the attempt FAIL when `score < <passing-score>`. Show the Socratic questions. Return to step 4 while retries remain.
   - Mark the attempt ERROR when the judge fails. Print a warning and return `0`. See `## Divergence from the paper`.

   Append the attempt row:

   ```
   python3 skills/hard-cheese/scripts/hard-cheese.pyz append-attempt \
     --slug <slug> --status <PASS|FAIL|ERROR> --score <n> \
     --feedback "<judge feedback>" --explanation "<user explanation>"
   ```

7. **Process an exhausted limit.** Set the artifact `status: FAILED`. Print the artifact path and return a non-zero status. Stop downstream chains.

## Artifact

`.cheese/hard-cheese/<slug>.md` contains the audit trail. The `.gitignore` file excludes `.cheese/`, so the audit trail remains local.

Each file starts with this YAML frontmatter block:

```yaml
---
slug: <slug>
attribution: Sankaranarayanan 2026 / vibecheck
rubric: SOLO Taxonomy (1-5), pass threshold = <passing-score>
passing_score: <n>
divergence: fail-open on judge error (vibecheck fails closed)
diff_base: <sha>
diff_head: <short-sha>
status: PASS | FAIL | FAILED | LOGGED
attempts: <n>
---
```

`append-attempt` writes the attempt log as this six-column markdown table:

```markdown
| timestamp | head_sha | status | score | feedback | explanation |
| --- | --- | --- | --- | --- | --- |
| 2026-06-25T10:00:00+00:00 | a1b2c3d | FAIL | 2 | "Unistructural: lists steps but no causal link" | <user explanation verbatim> |
| 2026-06-25T10:05:00+00:00 | a1b2c3d | PASS | 4 | "Relational: explains why invariant holds" | <user explanation verbatim> |
```

Each invocation appends attempts and does not overwrite rows. If `HEAD` changes, append new rows below the earlier rows.

## Sub-agent contract — fresh judge

- **Use fresh context for every invocation.** The code-writing context can bias the judge.
- Resolve a no-tool or read-only `reviewer` at `default` power and `high` effort. Use the shared agent resolver.
- Use a general worker only with no-write enforcement. Set `degraded: true`.
- Use `references/judge-prompt.md` as the system prompt.
- Give the judge the diff summary, optional spec excerpt, and explanation. Require JSON and prohibit repository writes.
- **Parse the JSON output.** On a parse error, log an `ERROR` attempt and fail open.

The gate requires a host sub-agent feature. Without this feature, recommend `/hard-cheese --no-judge` to record the explanation without a grade.

## Attribution

> Sankaranarayanan, S. (2026). *Mitigating 'Epistemic Debt' in Generative AI-Scaffolded Novice Programming using Metacognitive Scripts.* Proceedings of the 13th ACM Conference on Learning at Scale. <https://arxiv.org/abs/2602.20206>

The implementation uses the open-source VS Code extension from the paper's author:

<https://github.com/sreecharansankaranarayanan/vibecheck>

This `SKILL.md`, `references/judge-prompt.md`, and each artifact include the attribution. Thus, the citation stays with the audit trail.

## Divergence from the paper

Hard-cheese has one difference from vibecheck:

**Vibecheck fails closed on a judge error.** The modal blocks code application until the judge recovers or the user retries.

**Hard-cheese fails open on a judge error.** The gate records an `ERROR`, prints a warning, and returns `0`.

This policy prevents API failures from blocking pull request work. Add each new difference to this section.

## Composition with `--auto`

`--hard` and `--auto` can operate together. Terminal `/plate --hard` pauses automation once before publication, after `/plate` verifies the final artifacts.
The user responds to the prompt. PASS permits publication. FAILED stops publication. ERROR uses the documented fail-open behavior.

Commit-only `/plate --hard` does not run the gate because it shares nothing. See `references/composition.md` for new pull requests and non-TTY behavior.

## Output

When the gate ends, print:

```
Hard-cheese artifact: .cheese/hard-cheese/<slug>.md
Status: PASS | FAILED | LOGGED | ERROR
Score: <n>/5 (<SOLO level>, pass ≥ <passing-score>)
Attempts: <n>
```

The `Score` line reports the latest judged attempt. Omit this line for LOGGED mode or an ERROR without a scored attempt.

Then print one applicable message:

- On PASS: `Ready to share for review.`
- On FAILED: `Cap exhausted. Improve understanding of the change before sharing.`
- On LOGGED: `Telemetry only — judge skipped via --no-judge.`
- On ERROR: Print one warning that identifies the failure. Include `Fail-open divergence active — gate exited 0; you may share for review at your discretion.`

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection for the user-facing summary | `delta` | `git diff --unified=3` |
| Reading the spec (when present) | bounded file read per [`code-intelligence-routing.md`](../cheese/references/code-intelligence-routing.md) | host file read |
| Spawning the judge | host sub-agent primitive (`Agent()` or harness equivalent) | none — without sub-agent spawn, run `--no-judge` mode and tell the user the judge is unavailable |
| GitHub / PR context (out of scope here) | n/a | n/a |

## Rules

- Run the judge sub-agent in fresh context. Do not use the code-writing context to grade the author's understanding.
- Do not coach the user before the answer. The explanation is the artifact under test.
- Show only the judge's Socratic questions after a FAIL. Do not add hints.
- Pass the user's explanation to the judge unchanged.
- Always run the freshness check. A changed `HEAD` requires a new attempt sequence.
- Record every ERROR attempt. Show a warning for each judge failure.
- Do not call `/gh` or a specific pull request tool. The gate operates before code enters review.
- Apply the shared voice rules from `../age/references/voice.md`. Report the result and classify residual risk as `certain | speculating | don't know`.
- Do not describe FAILED as `"almost passing"`.

## References

- `references/judge-prompt.md` defines the SOLO Taxonomy rubric, judge prompt, and JSON output.
- `references/composition.md` defines the complete `--hard` and `--auto` matrix.
- [`references/commands.md`](references/commands.md) lists the generated bundle commands.

## Agent resolution

Resolve the fresh judge through [`../cheese/references/agent-resolution.md`](../cheese/references/agent-resolution.md).

| Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback |
| --- | --- | --- | --- | --- | --- |
| Grade the explanation | reviewer | no-tool or read-only, fresh-context | default | high | compatible reviewer, then general |

The canonical hard-cheese audit includes the shared `agent_resolution` block.
