---
name: hard-cheese
description: Metacognitive vibecheck gate before code is shared for review — make the author explain the diff's causal logic, graded by a fresh-context judge against the SOLO Taxonomy. Use when the user wants this gate — phrases like "/hard-cheese", "/cheese --hard", "gate this before I push", "vibecheck me", "make sure I understand this diff", "epistemic-debt check". Reads the working diff, asks the human author to explain it in their own words, spawns the judge sub-agent (pass ≥ Multistructural), and either accepts (PASS) or returns Socratic feedback for retry (FAIL, capped at `--socratic-cap N`). Writes the audit trail to `.cheese/hard-cheese/<slug>.md`. Use standalone before opening a PR, or as the `--hard` flag propagated through `/cook`, `/press`, `/age` to `/cure` — the sole pipeline step where the gate actually fires, at the share-for-review handoff. Do NOT use for code review (`/age`), test hardening (`/press`), or fix application (`/cure`).
license: MIT
---

# /hard-cheese

The gate mitigates **epistemic debt** — the failure mode where AI-scaffolded code passes review, type-checks, and tests green while the author cannot explain it to a reviewer.

## Inputs

```text
/hard-cheese [<slug>] [--socratic-cap N=3] [--passing-score N=3] [--no-judge]
```

Arguments:

- `<slug>` — optional. Identifies the artifact at `.cheese/hard-cheese/<slug>.md`. When omitted, fall back to the git short SHA of `HEAD`. An explicit slug always wins.
- `--socratic-cap N` — max retry attempts before the gate marks the artifact `FAILED` and exits non-zero. Default `3`. Vibecheck does not cap; easy-cheese does to avoid infinite loops.
- `--passing-score N` — minimum SOLO score that counts as PASS. Valid range `1..5`; default `3` (Multistructural-or-higher). A previous PASS below the requested threshold is treated as stale and must be re-judged.
- `--no-judge` — log-only mode. Capture the user's explanation, write the artifact with `status: LOGGED`, skip the judge sub-agent spawn. Mirrors vibecheck's optional JSONL telemetry mode.

## Invocation modes

| Mode | How it fires | Where the gate sits |
| --- | --- | --- |
| **standalone** | User runs `/hard-cheese <slug>` directly before opening a pull request. | Outside the pipeline. No upstream skill required. |
| **propagated** | `/cure` invokes `/hard-cheese <slug>` when `--hard` is in scope and the user selects the share-for-review option at cure's handoff (or, under `--auto --hard`, at the end of cure's final auto pass). | At the `cure → share for review` boundary — the moment code escapes the local machine. |

`--hard` propagates through `/cheese → /mold → /cook → /press → /age → /cure`. Upstream skills only pass the flag along; `/cure` is the only skill that actually invokes `/hard-cheese`. See `references/composition.md` for the full matrix.

Portability reference: [`../cheese/references/harness-portability.md`](../cheese/references/harness-portability.md). It covers helper resolution, sub-agent dispatch, GitHub operations, and handoff transitions; prefer the bundled or repo-local helper first, and treat `${CLAUDE_SKILL_DIR}` as optional host-provided fallback.
The handoff blocks below are the portable contract; slash commands are host renderings, not the control model.

## Flow

1. **Resolve scope.**
   - `diff_base = origin/main`, `diff_head = <short-sha of HEAD>`.
   - If `.cheese/specs/<slug>.md` exists, load it as the intent reference (optional — diff is the ground truth).
   - Slug fallback when none supplied: the HEAD short SHA.
   - If the working tree has no diff against `origin/main`, exit `0` with `"nothing to gate on"` and write no artifact.

2. **Freshness check.**
   Check freshness before launching the gate:

   ```
   python3 skills/hard-cheese/scripts/hard-cheese.pyz freshness-check \
     --slug <slug> --passing-score <n>
   ```

   Exit 0 (`previously_passed`): print `"previously passed"` and exit `0`. Exit 2 (`stale`: HEAD moved or the last PASS score is below `--passing-score`) or 3 (`new`): continue to step 3.

3. **Compose the vibecheck prompt** (faithful to Sankaranarayanan 2026, generalised to "share for review" so the gate stays implementation-agnostic):

   > Before this is shared for review, explain its causal logic in your own words. How does *<feature or fix>* work? Why does it produce the desired behavior? What state, control flow, or invariants does it rely on?

   Render a diff summary alongside the prompt: files changed, key hunks. Cap the diff excerpt at roughly 80 lines. The spec excerpt (if loaded) is shown above the diff summary.

4. **Capture the user's explanation** as free text. No coaching, no example answers — the explanation is the artifact under test.

5. **Spawn the judge sub-agent** in fresh context (same pattern `/ultracook` uses for adversarial review). The judge:
   - Reads `references/judge-prompt.md` as its system prompt.
   - Receives the passing score threshold, the diff summary, the spec excerpt (if any), and the user's explanation as context.
   - Returns a JSON object: `{score, level, pass, feedback, socratic_qs}`.

   See `references/judge-prompt.md` for the full system prompt and output shape.

   Skip this step when `--no-judge` is set: mark the attempt `status: LOGGED`, write the artifact, exit `0`.

6. **On judge result:**
   - `score >= <passing-score>` → PASS. `score < <passing-score>` → FAIL, render Socratic questions, loop to step 4 if `attempts < --socratic-cap`. Judge error → ERROR attempt, print warning, exit `0` (fail-open — see `## Divergence from the paper`).

   Append the attempt row:

   ```
   python3 skills/hard-cheese/scripts/hard-cheese.pyz append-attempt \
     --slug <slug> --status <PASS|FAIL|ERROR> --score <n> \
     --feedback "<judge feedback>" --explanation "<user explanation>"
   ```

7. **On cap exhaustion:** set the artifact `status: FAILED`, print the path, exit non-zero. Downstream chains must not proceed.

## Artifact

`.cheese/hard-cheese/<slug>.md` is the audit trail. The directory is gitignored by repo convention (`.gitignore` already ignores `.cheese/`), so the trail stays local — matching vibecheck's local-only stance on telemetry.

Each file opens with a YAML frontmatter block that travels with the audit trail:

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

The attempt log uses a 6-column markdown table (written by `append-attempt`):

```markdown
| timestamp | head_sha | status | score | feedback | explanation |
| --- | --- | --- | --- | --- | --- |
| 2026-06-25T10:00:00+00:00 | a1b2c3d | FAIL | 2 | "Unistructural: lists steps but no causal link" | <user explanation verbatim> |
| 2026-06-25T10:05:00+00:00 | a1b2c3d | PASS | 4 | "Relational: explains why invariant holds" | <user explanation verbatim> |
```

Attempts append; nothing is overwritten within a single invocation. If a re-invocation finds the artifact stale (HEAD moved), new attempt rows are appended below the prior ones — the trail is cumulative.

## Sub-agent contract — fresh peer, not diminutive

- **Fresh context, every invocation.** Same-context judging is biased toward "yes you understand it" because the model that helped write the code believes the code is good. The fresh context is the entire reason the judge means anything.
- **`subagent_type: "general-purpose"`** with `references/judge-prompt.md` as the system prompt. Model inherits from the parent — do not pass `haiku` or any other tier downgrade.
- **No tools needed for the judge.** It reads the prompt, diff summary, spec excerpt, and explanation, then returns JSON. No file access, no shell, no MCP — the judge is a graded read-only call.
- **JSON output is parsed.** If parsing fails, the attempt is logged as `ERROR` and the gate fails open (see `## Divergence from the paper`).

If the host harness has no sub-agent primitive, `/hard-cheese` is the wrong skill — the gate cannot run without a fresh judge. Recommend `/hard-cheese --no-judge` for users who still want the explanation captured as telemetry without the grading step.

## Attribution

> Sankaranarayanan, S. (2026). *Mitigating 'Epistemic Debt' in Generative AI-Scaffolded Novice Programming using Metacognitive Scripts.* Proceedings of the 13th ACM Conference on Learning at Scale. <https://arxiv.org/abs/2602.20206>

The implementation reference (intercept-at-acceptance, SOLO rubric, Socratic retry) is the open-source VS Code extension by the paper's author:

<https://github.com/sreecharansankaranarayanan/vibecheck>

The attribution appears in this `SKILL.md`, in `references/judge-prompt.md`, and in every `.cheese/hard-cheese/<slug>.md` artifact so the citation travels with the audit trail.

## Divergence from the paper

Hard-cheese departs from vibecheck in exactly one place, and the divergence is called out explicitly so it stays legible:

**Vibecheck fails closed on judge error.** If the Judge LLM cannot produce a verdict, the modal blocks code application until the judge recovers or the user retries with a different model.

**Hard-cheese fails open on judge error.** If the fresh-context judge sub-agent crashes, times out, or returns malformed JSON, the gate writes an `ERROR` attempt, prints a clear warning, and exits `0` — the user is allowed to proceed.

Rationale: judge invocation is per-PR-attempt and per-retry, and a strict fail-closed policy creates a worse experience under API hiccups than the epistemic-debt cost it averts. New divergences must be added here.

## Composition with `--auto`

`--hard` and `--auto` may coexist. The gate is the **only** point at which `--hard` punctures `--auto`. Everywhere else, auto's skip-handoff semantics apply.

Concretely, under `/cure --auto --hard --stake medium+`:

- The pipeline runs auto through `cook → press → age → cure` per `--auto`'s normal contract.
- At the end of cure's final auto pass, the chain pauses and `/hard-cheese <slug>` fires once.
- The user must respond to the vibecheck prompt. The judge grades.
- On PASS: chain exits with `"gate passed → ready to share for review"`.
- On FAILED (cap exhausted): chain exits non-zero with the artifact path; the user must improve their understanding before sharing.
- On ERROR: chain exits `0` with a warning (the fail-open divergence).

Non-TTY guard: see `references/composition.md` `## Non-TTY guard`.

`/cure --auto` alone (no `--hard`) is unchanged — the gate never fires. The single puncture point is documented in `references/composition.md` and in `skills/cure/SKILL.md`.

## Output

When the gate ends, print:

```
Hard-cheese artifact: .cheese/hard-cheese/<slug>.md
Status: PASS | FAILED | LOGGED | ERROR
Attempts: <n>
```

Followed by:

- On PASS: `Ready to share for review.`
- On FAILED: `Cap exhausted. Improve understanding of the change before sharing.`
- On LOGGED: `Telemetry only — judge skipped via --no-judge.`
- On ERROR: a one-line warning naming the failure mode and `Fail-open divergence active — gate exited 0; you may share for review at your discretion.`

## Preferred tools and fallbacks

| Need | Prefer | Fallback |
| --- | --- | --- |
| Diff inspection for the user-facing summary | `delta` | `git diff --unified=3` |
| Reading the spec (when present) | `cheez-read` | host file read |
| Spawning the judge | host sub-agent primitive (`Agent()` or harness equivalent) | none — without sub-agent spawn, run `--no-judge` mode and tell the user the judge is unavailable |
| GitHub / PR context (out of scope here) | n/a | n/a |

## Rules

- The judge sub-agent runs in fresh context. Do not let the same conversation that wrote the code grade the human's understanding of it.
- Do not coach the user before they answer. The explanation is the artifact under test. Socratic questions appear only *after* a FAIL, and only the questions returned by the judge — no extra hints from the parent.
- Do not paraphrase the user's explanation before passing it to the judge. The judge grades what the user wrote, verbatim.
- Do not skip the freshness check. Re-invoking after HEAD has moved must trigger a fresh attempt sequence — prior comprehension is stale once the code changes.
- Do not silently drop ERROR attempts. The fail-open divergence requires that every judge failure is recorded in the artifact and surfaced to the user as a warning.
- Do not invoke `/gh` or any specific PR-creation tool. The gate's contract is "before code is shared for review" — implementation-agnostic.
- Apply the shared voice kernel (lives at `../age/references/voice.md`): say what the gate result was, flag residual risk as `certain | speculating | don't know`, do not soften FAILED into "almost passing".

## References

- `references/judge-prompt.md` — SOLO Taxonomy rubric, judge sub-agent system prompt, JSON output shape.
- `references/composition.md` — the full `--hard` / `--auto` matrix and the single puncture point.
- `skills/hard-cheese/scripts/hard-cheese.pyz freshness-check` — checks whether a previous PASS is still fresh for the current HEAD and passing score (step 2).
- `skills/hard-cheese/scripts/hard-cheese.pyz append-attempt` — atomically appends an attempt row to the audit trail (step 6).
