# Skill-Parity Follow-ups

Durable record of the gap-analysis findings from the obra/superpowers + Matt
Pocock parity research that are **not yet captured in a PR**. PR #138 shipped the
SKILL.md *format* slice (CSO descriptions, the Iron Law / Red Flags /
Rationalization-table template, the authoring checklist, the pressure-test gate)
as `shared/skill-authoring.md` plus cook/cure discipline docs. The remaining
findings below are non-format and have no PR home — this file is their durable
artifact so they survive the gitignored research scratch.

Full reconciled analysis (gitignored scratch, not durable):
`.cheese/research/easy-cheese-gap-analysis.md`. Sources: obra/superpowers
(commit `6fd4507`, v5.1.0) and mattpocock/skills (commit `694fa30`, 2026-06-10).

All easy-cheese claims are baselined against the 18-skill manifest
(`.claude-plugin/plugin.json`), not the author's ambient `~/.claude` session.

---

## In a PR already

| Finding | Where |
| --- | --- |
| CSO description rule, size budget, Iron Law / Red Flags / Rationalization template, authoring checklist, pressure-test gate, `disable-model-invocation` (documented as candidate) | PR #138 — `shared/skill-authoring.md` |
| Rationalization-rebuttal tables applied to cook (TDD) and cure (fix-application) | PR #138 — `skills/cook/references/cook-discipline.md`, `skills/cure/references/cure-discipline.md` |

The format brief (`.cheese/specs/skill-formats-brief.md`) is the source for the
above; its conclusions are committed in PR #138.

---

## Open follow-ups (no PR yet)

Severity and effort are from the reconciled analysis. "Source" cites the
benchmark the idea comes from.

### High severity

- **Promote mold's live-resolved glossary to durable, downstream-readable storage** (effort M; source: pocock CONTEXT.md). mold already resolves canonical terms live (`skills/mold/references/modes.md:26`) but logs them to the *transient* session state file; no downstream skill reads them. Write the resolved-term log alongside ADRs at curdle and have cook/age/press read it for naming consistency. Extension of existing curdle/ADR machinery, not a new feature.
- **Extend rationalization-rebuttal tables to the remaining high-stakes discipline skills** (effort S; source: superpowers). PR #138 covered cook + cure. Still uncovered: the cheez-* skills (silent-degrade rationalizations) and a verification-before-completion clause (below).

### Medium severity

- **`verification-before-completion` clause in cook/cure** (effort S; source: superpowers). Before writing any `status:ok` handoff slug: identify the gate command, run it fresh in the same turn, read full output, then claim — and ban hedging words ("should", "probably") in completion claims. Closes the fake-completion gap (Rule 9) with no new machinery.
- **Richer sub-agent status vocabulary + per-task model selection** (effort M; source: superpowers subagent-driven-development + dispatching-parallel-agents). Extend the handoff slug status beyond `ok|halt` with `NEEDS_CONTEXT` (request more rather than fail) and `DONE_WITH_CONCERNS`. Add per-phase model-selection guidance to ultracook/cheese-factory spawn prompts (sub-agents currently inherit the parent model uniformly).
- **Curd prompt stale-path fix** (effort M; source: pocock Agent Brief). `skills/cheese-factory/references/curd-prompt.md:10` binds scope to a hardcoded `{file_list}` HARD CONSTRAINT — a stale-path failure mode. Re-validate the file list against the decomposition at dispatch, or express scope behaviorally. Add a when-NOT-to-parallelize check to the decomposer.
- **Issue-intake / triage workflow (NEW category gap)** (effort M; source: pocock triage + to-issues). For an idea-to-PR plugin, the front-of-funnel is missing: nothing moves an issue backlog through a triage lifecycle (needs-triage / needs-info / ready-for-agent / ready-for-human / wontfix) into agent-ready Agent Briefs. Scope-check with the maintainer before building — confirm issue intake is in-scope for the thesis.
- **`wheypoint` focus argument** (effort S; source: pocock handoff). Accept an optional argument describing the next session's focus and tailor the handoff to it.

### Low severity

- **YAGNI grep-for-usage gate in affinage** (effort S; source: superpowers receiving-code-review). Before applying a reviewer suggestion that ADDS a feature/abstraction, grep for a real call site and reject if none exists. The broader anti-sycophancy posture is already covered by `skills/age/references/voice.md` + affinage push-back drafts — only this gate is missing.
- **Static HTML findings report for age** (effort M; source: pocock improve-codebase-architecture). Emit a Tailwind+Mermaid findings report (severity badges, grouped sections, before/after) to the OS temp dir — no daemon, nothing in-repo. Scope to age findings only; skip a gate-graph report (the existing Mermaid render covers it).
- **Optional, opt-in PreToolUse git-guardrail hook** (effort M; source: pocock git-guardrails-claude-code). Block dangerous git (push / reset --hard / clean -f / branch -D / checkout . / restore .). The one execution-time safety gap of the skills-only / no-hooks stance. (The worktree provenance/isolation ideas from the earlier synthesis are struck — those skills are not part of easy-cheese.)
- **`.out-of-scope/` rejected-decisions store** (effort S; source: pocock triage). A durable store the mold agent-introduced-scope audit and the cheese router check before re-proposing a previously-rejected direction.
- **mold Sketch concrete-seam rule** (effort S; source: superpowers writing-plans No-Placeholders + pocock prototype). When a seam is small enough to write completely, write the full implementation in the spec rather than pseudocode — narrows cook's re-derivation surface.
- **pasteurize escalation + seam-check** (effort S; source: superpowers systematic-debugging + pocock diagnose). Add a "3 failed fixes triggers architectural re-questioning, not a 4th attempt" escalation and a seam-correctness check before the regression test.
- **Optional SessionStart routing nudge + `disable-model-invocation`** (effort M; source: superpowers + pocock). Consider an opt-in bootstrap that nudges "route through /cheese for any dev task" so the router fires without explicit invocation; adopt immediate-execute frontmatter for the thinnest prompt skills once harness behavior is verified.

---

## Struck (false or misattributed against the source)

The earlier synthesis raised these; a critique pass falsified them against the
source. Do not re-open without re-checking the cited lines.

- "mold batches questions / lacks one-question cadence" — FALSE, `modes.md:46` mandates it.
- "mold has no live terminology resolution" — FALSE, `modes.md:26` resolves and logs terms live (rescoped to the durability follow-up above).
- "mold does not name the code-vs-intent contradiction hunt" — FALSE, `modes.md:75` defines `[CONFLICT <id>]`.
- "cook has no watch-it-fail proof" — OVERSTATED, observed-red is a required Cut report item (`cook/references/tdd-loop.md:13`).
- "add a general anti-sycophancy layer" — REDUNDANT, `age/references/voice.md` already covers steelman / do-not-manufacture-counterpoints.
- Worktree provenance/isolation recommendations — WRONG REPO, worktree/worktree-sweep are not easy-cheese skills (cheese-factory calls `/worktree-sweep` a host equivalent, `SKILL.md:434`).
- "caveman-style mid-dialogue compression for mold" — LOW VALUE, at odds with mold's disambiguation purpose.

---

## easy-cheese leads (preserve — no benchmark matches)

gate-prose-sync test; agent-introduced-scope audit; hard-fail-over-silent-degrade
invariant; dual-transport orchestration (cook --auto vs ultracook); melt
squash-residue detection; the runtime context-budget mechanic; durable ADRs to a
dynamically-probed hallouminate corpus; the per-phase handoff slug system;
hard-cheese SOLO epistemic-debt gate; the ten-dimension age review engine.
