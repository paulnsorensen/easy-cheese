# Cheese to Briesearch Edge Review

## State

`broken`

## Evidence

- Cheese maps `research` to `/briesearch` for external evidence questions (`skills/cheese/references/classification.md:22,47-58`).
  Briesearch accepts the complete user prompt as the research question (`skills/briesearch/SKILL.md:10-19`).
  These direct-route names agree.
- Cheese invokes Briesearch at tier 2 before the tier-1 Mold action (`skills/cheese/references/escalation.md:10-22`).
  Briesearch requires a parent mini-spec slug and a mini-spec link (`skills/briesearch/SKILL.md:10-13`).
- Briesearch defines `report`, `raw_dir`, and `manifest` paths in `ResearchLayout` (`src/easy_cheese/skills/briesearch/research_layout.py:26-50`).
  Invalid slugs return an error status (`src/easy_cheese/skills/briesearch/research_layout.py:54-64`).
- Another-skill calls use `invocation: sidechain` (`skills/briesearch/references/context-isolation.md:41-65`).
  The parser defaults a missing invocation to `top-level` (`src/easy_cheese/skills/briesearch/ledger.py:329-337`).
- The checked Briesearch command manifest imports only shared and Briesearch modules (`src/easy_cheese/skills/briesearch/commands.py:7-39`).
  Its command list has no internal dispatch command (`src/easy_cheese/skills/briesearch/commands.py:42-56`).
  Cheese uses the `/briesearch` skill dispatch instead of a Python import.
- Briesearch requests one provenance line in internal mode (`skills/briesearch/SKILL.md:13`).
  Its synthesis contract requires a full short form for every caller (`skills/briesearch/references/synthesis.md:80-110`).
- Cheese reserves the only user prompt for tier 3 (`skills/cheese/references/escalation.md:19-26`).
  Briesearch can ask one question when criteria change the source plan (`skills/briesearch/SKILL.md:17-19`).
- The Cheese test checks only that escalation names `/briesearch` (`tests/python/test_cheese_routing_receipt.py:105-120`).
  Briesearch tests validate manifest values without a Cheese handoff (`tests/python/test_briesearch_ledger.py:124-126`; `tests/python/test_briesearch_budget.py:251-268`).
  Briesearch declares its route evals manual (`skills/briesearch/references/evals.md:3-7,54-56`).
  No test runs either Cheese route into Briesearch.
- The focused test run passed all 77 edge-adjacent tests.
  Those tests do not exercise the complete seam.

## Findings

### Blocker

none

### High

- **The tier-2 artifact contract is impossible at its current position.**
  Cheese calls Briesearch before Mold creates the parent mini-spec (`skills/cheese/references/escalation.md:10-22`).
  Briesearch requires that parent slug and a link from the same file (`skills/briesearch/SKILL.md:13`).
  The call therefore lacks its required input and write target.
  **Fix:** Cheese must allocate and pass a slug before the call.
  Mold must write the returned artifact link into `## Provenance`.
- **Internal question ownership conflicts.**
  Cheese reserves user questions for tier 3 (`skills/cheese/references/escalation.md:19-26`).
  Briesearch permits a question in every context (`skills/briesearch/SKILL.md:10-19`).
  A silent tier-2 call can therefore expose a user question.
  **Fix:** Internal Briesearch must return `needs_input` without asking.
  Cheese must ask that question in tier 3.

### Medium

- **The internal mode and result have no defined packet.**
  Cheese names only an internal skill dispatch (`skills/cheese/SKILL.md:44-48,81-92,145`).
  Briesearch defines no mode argument or typed result (`skills/briesearch/SKILL.md:10-19,60-62`).
  Its one-line result also conflicts with the mandatory short form (`skills/briesearch/references/synthesis.md:80-110`).
  **Fix:** Define input fields for `question`, `slug`, and `invocation`.
  Define result fields for `provenance`, `artifact`, `confidence`, and `needs_input`.
- **A sidechain run can silently become a top-level run.**
  Briesearch requires `sidechain` when another skill asks (`skills/briesearch/references/context-isolation.md:63`).
  The parser defaults an omitted value to `top-level` (`src/easy_cheese/skills/briesearch/ledger.py:329-337`).
  Cheese does not pass an invocation field.
  **Fix:** The internal dispatch must set `invocation: sidechain`.
  The consumer must reject a missing value for internal mode.
- **Tests do not exercise the seam from both sides.**
  The Cheese test protects one phrase only (`tests/python/test_cheese_routing_receipt.py:105-120`).
  The Briesearch tests protect ledger parsing only (`tests/python/test_briesearch_ledger.py:124-126`).
  **Fix:** Add one direct-route test and one tier-2 test.
  Each test must verify mode, slug, invocation, output, artifact, and failure behavior.

### Low

none

## Contract Change

Briesearch now records `invocation: sidechain` when another skill asks (`skills/briesearch/references/context-isolation.md:63`).
Cheese did not add this field to its internal dispatch (`skills/cheese/SKILL.md:44-48,81-92`).
This contract change is not complete across the edge.

## STE100 Status

- `skills/cheese/SKILL.md` is not compliant.
  Line 41 puts four instructions in one sentence.
  Line 206 puts three instructions in one sentence.
  Split each instruction into a separate sentence.
- `skills/briesearch/SKILL.md` is not compliant.
  Line 19 puts two instructions in one sentence.
  Split the instruction into two sentences.
- This note is compliant.

## Follow-ups

- Define the Cheese-to-Briesearch sidechain packet.
- Make Mold store the returned provenance and artifact path.
- Give Cheese sole ownership of tier-3 questions.
- Require `invocation: sidechain` for internal research.
- Add direct-route and tier-2 seam tests.
