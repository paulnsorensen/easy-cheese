# Hard-cheese gate contract

Hard-cheese is the explanation-quality gate that runs once, at Plate's final boundary, when the user passed `--hard`. The r014 edge reviews (`edge-mold-hard-cheese.md`, `edge-cure-hard-cheese.md`, `edge-plate-hard-cheese.md`, `edge-affinage-hard-cheese.md`) fixed who invokes it, how the flag travels, and what each outcome means. Why the skill exists at all is in [hard-cheese-retained-001](../adr/hard-cheese-retained-001.md).

## Only Plate invokes it

`/plate --hard` is the single trigger (`skills/hard-cheese/SKILL.md:29-32`, `skills/plate/SKILL.md:45-46`). Mold prose once named Cure as the firing point; that was wrong. Upstream skills forward `--hard` and never call hard-cheese themselves.

## `--hard` travels only in dispatch text

No `HandoffPointer` or phase-contract payload has a field for the flag. Cook, Cure, and Mold must copy `--hard` into the next `/skill` command or the gate silently never runs. Mold's mini-spec and some full-mode Cook dispatch lines omitted it during the review. See [handoff-preamble-grammar](./handoff-preamble-grammar.md).

## Outcomes and exit status

The outcomes are `PASS`, `FAILED`, `ERROR`, and `LOGGED`. `ERROR` (judge failure or unparsable JSON) prints a warning and returns exit `0`; the gate fails open (`skills/hard-cheese/SKILL.md:85,136,156`). Cure continues on `ERROR` (`skills/cure/SKILL.md:264`). Plate's status matrix separately asks the user before it publishes on `ERROR`. Do not read the exit code as "safe to publish"; the gate status and the publication policy are two contracts.

## Rubric levels

The judge scores on the SOLO taxonomy with the Biggs and Collis mapping: level 3 is Multistructural and level 4 is Relational. Default `passing_score` is 3 (`skills/hard-cheese/references/judge-prompt.md:23-39`). Level 3 identifies the elements of a change; it does not credit causal linkage. The paper's "Relational pass condition" and `score >= 3` name the same operational gate.

## Judge input is untrusted

The diff and the author's explanation reach the judge model as data. The prompt marks them untrusted, rejects embedded instructions before scoring, and the caller validates the returned object independently.

## Freshness binds to a digest

A freshness check that compares only a recorded `HEAD` SHA and score accepts a changed working tree. Compute one digest over `HEAD`, the working diff, the optional specification, and prior evidence, as [age-review-lock-invariants](../gotchas/age-review-lock-invariants.md) does.

## Question targeting ranks branch hunks

`rank-hunks` compares the feature branch with its merge base. It ranks up to three hunks from churn, history, author experience, and risk patterns. The gate shows those regions before the first explanation. It includes every ranked region in the judge's bounded diff summary. A failed judgment anchors at least one Socratic question to a ranked region.[^1]

The source paper and vibecheck do not select question targets. Hard-cheese adds this behavior through [targeting ADR 001](../adr/hard-cheese-question-targeting-001.md), [presentation ADR 002](../adr/hard-cheese-question-targeting-002.md), and [prompt ADR 003](../adr/hard-cheese-question-targeting-003.md).

[^1]: `skills/hard-cheese/SKILL.md:58-93`; `src/easy_cheese/skills/hard_cheese/rank_hunks.py:118-367`

_Source: r014 skill-review round notes (ingest hash 499c49c7b67d5eb6), verified against `skills/hard-cheese/` on 2026-09-18 · Updated: 2026-09-18_
