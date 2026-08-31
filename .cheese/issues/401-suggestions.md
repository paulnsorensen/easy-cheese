# Issue #401 — suggestions

`bug: Mold-produced specs can fail Cut contract inference`

## Channel — and why this one is different

**Not reproducible on `main`, and the premise is partly stale on `next`.**

Two separate reasons this issue cannot be actioned as written:

1. **`main` cannot reproduce it.** PR #560 removed `/cut`; #562 dropped cut and
   red-gate expectations from the `.pyz` bundle suite. `main` builds no
   `cut.pyz`, so the reproduction step

   ```text
   python3 ~/.agents/skills/cut/scripts/cut.pyz red-gate contracts <spec>
   ```

   has no command to run. Anyone reproducing it today is running a previously
   installed bundle, not anything `main` produces.

2. **`next`'s Mold already emits the shape Cut demands.** The issue describes
   Mold producing "narrative `Goals` and `Required cases`, but no acceptance
   IDs, `gate_applicability`, or Test Contract table". On `origin/next`, Mold's
   own grammar requires all three:

   - `skills/mold/SKILL.md:74-98` — "Every spec declares `gate_applicability`";
     "`red-required` requires `behavior` plus a complete `## Test Contracts`
     table".
   - `skills/mold/references/curdle.md:45,75,86-95` — the emitted spec carries
     a `gate_applicability` block, an `## Acceptance` section, and a
     `## Test Contracts` table with the exact seven columns
     `_contract_table` parses.
   - `skills/mold/references/curdle.md:159` — rule `ac-coverage-exactly-once`,
     mirroring `red_gate.py:625-628`.
   - `skills/mold/references/mini-spec-mode.md:21,32,36-37` — same shape in the
     mini-spec path.

Retag to a next-channel label **and** `triage/stale` on the reproduction, then
keep the two genuinely-live pieces below. Do not close it outright: the
integration test it asks for was never written, and the legacy-spec path it
exposed is still a live refusal.

## What is still real

### The exact failure path, for the record

`_parse_spec` (`src/easy_cheese/shared/cut/red_gate.py:538`) reaches legacy
inference at `:616-620`:

```python
elif declaration is None:
    if criteria:
        for acceptance_id, statement in criteria.items():
            contracts.append(_infer_contract(acceptance_id, statement))
    else:
        problems.append("legacy spec has no acceptance IDs to infer")
```

`criteria` comes from `_acceptance_criteria` (`:335-364`), which needs **both**:

1. a heading whose text lower-cases to exactly `acceptance` or
   `acceptance criteria` (`:341-345`), and
2. at least one line inside it matching `_ACCEPTANCE_ID`
   (`red_gate.py:176`: `\bAC-[0-9]+(?:[-.][A-Za-z0-9_-]+)?\b`).

A spec with `## Goals` / `## Required cases` satisfies neither. `criteria` is
empty, the first problem fires, and then — because `disposition_value` defaults
to `red-required` with `work_class: behavior` (`:639-646`) — `:672-673` adds
the second: `red-required requires at least one Test Contract`. Two errors, one
cause.

### The error messages name no remedy

Both strings state what is missing and nothing about what to do. For a spec the
same skill suite produced, that is the worst possible failure mode. Cheapest
fix in this whole issue set:

```text
legacy spec has no acceptance IDs to infer: add a `## Acceptance` section whose
items carry AC-<n> identifiers, or declare gate_applicability explicitly (see
skills/mold/references/curdle.md)
```

Applies to `red_gate.py:620` and `:672`.

### The integration test the issue asks for was never written

`tests/python/` on `next` has `test_cut_spec_format_tracers.py`,
`test_cut_skill_contract.py`, `test_cut_pressure_eval.py`, and the fixtures
under `tests/python/fixtures/cut_spec_format/` — but nothing that drives a
**Mold-shaped** spec end-to-end into a canonical receipt. That gap is why a
schema disagreement between two skills in one repo could ship at all.

## Proposal

### 1. Pin the handshake with a real integration test (do this one)

New `tests/python/test_cut_mold_spec_handshake.py`:

- Fixture `tests/python/fixtures/mold_handshake/red_required_spec.md`, written
  to Mold's **current** emitted grammar, copied structurally from
  `skills/mold/references/curdle.md:45-95` — `gate_applicability` frontmatter,
  `## Acceptance` with `AC-1`/`AC-2`, and the seven-column `## Test Contracts`
  table.
- Assert `_parse_spec` returns `disposition == RED`, `work_class == "behavior"`,
  `contract_source == "approved"` for every contract, and **zero problems**.
- Drive the full path — `begin_phase` -> oracle install -> `issue_gate` -> a
  canonical receipt on disk — proving Cook preflight can obtain one. This is
  literally the issue's "Expected" section.
- Second fixture `not_applicable_spec.md` (`docs-only` + reason, no table) ->
  N/A receipt.
- **The load-bearing part:** derive the fixtures from the Mold reference docs,
  and add an assertion that fails if
  `skills/mold/references/curdle.md`'s Test Contracts column list and
  `_contract_table`'s expected headers (`red_gate.py:381`) diverge. A fixture
  that is hand-maintained will silently drift back into exactly this bug. A
  fixture that is checked against the grammar cannot.

### 2. Improve the two error messages

As above. Two string edits, covered by an assertion in the new test module on
the legacy-spec fixture.

### 3. Decide the legacy-compat question explicitly — recommend "no"

The issue offers two remedies; the first ("Mold emits acceptance IDs, an
explicit `gate_applicability` declaration, and at least one valid Test
Contract") is **already done** on `next`. The second — teach
`_acceptance_criteria` to recognize `Required cases` and synthesize positional
IDs — is a live option only for specs approved under an older Mold.

**Recommend rejecting it.** Reasons:

- `_infer_contract` (`red_gate.py:443-456`) already stamps inferred contracts
  `mode=GateMode.TRACER` and `contract_source="inferred"`, so nothing gets
  promoted — but widening the *heading* vocabulary means Cut silently invents
  contracts from arbitrary prose sections. The blast radius is every spec in
  every consuming repo with a section named `Required cases`, whether or not
  its author meant it as acceptance criteria.
- The workaround for a genuinely stale spec is one paste of a
  `gate_applicability` block, which the improved error message from item 2 now
  tells the author to do.
- Legacy inference already exists as an escape hatch for specs that *do* carry
  `AC-<n>` IDs. Widening it twice is how a compat shim becomes permanent.

If the release owner disagrees and wants the shim: scope it to the single
literal heading `required cases`, keep `mode=TRACER` and
`contract_source="inferred"`, synthesize IDs as `AC-1`… by list position, and
emit a deprecation line on stdout naming the spec path. Add a fixture asserting
the shim never produces `contract_source="approved"`.

## Tradeoffs

- **Closing this as stale loses the test.** That is the trap. If the issue is
  closed on the "not reproducible" finding alone, the handshake stays untested
  and the next Mold grammar change reintroduces it. Item 1 is the deliverable;
  the staleness finding is context.
- **Item 1 is not free.** Driving `begin_phase` -> `issue_gate` in a test needs
  a temp project tree, a real runner, and a real oracle file — the existing cut
  suites already do this, so copy their harness rather than inventing one.
- **Ordering.** Independent of #542, #546, #425, and #457. If #542 lands first,
  add a `red-gate cut` leg to the same test so the transaction path is covered
  too.

## Effort

Small-to-medium. Items 2 and the grammar-drift assertion are hours; the
full `begin` -> `issue` leg is the bulk of it.
