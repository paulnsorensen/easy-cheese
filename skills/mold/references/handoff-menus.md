# Handoff branch menus

Read this when the user selects Cook after Mold saves a draft. A saved draft alone renders no Cook command. The `curd-count` digest is advisory sizing; finalization owns readiness and execution authority.

- A `ready` finalization result carries a consumer-valid pointer. A
  `saved-not-ready` result carries only durable preparation requirements and
  holds, so render no pointer command and no automatic command. Show each
  requirement and hold. Cook does not read these saved requirements, so offer
  **Let Cook prepare the spec** — `/cook --spec "$SPEC"` only when the result
  has no hold and every requirement `kind` is `approval`, `scope`, or `plan`.
  Cook preparation then asks for each missing plan and approval. Offer this only after the user selects Cook. For any other
  requirement, such as a failed taste verdict, render no Cook choice.
- For a ready result, a non-null `handoff` means `red-required`; a null
  `handoff` means closed `not-applicable` or legacy input. Both route to Cook
  with the canonical pointer from finalization: auto choices use
  `/cook --auto <pointer-path> --spec "$SPEC"` and manual choices use
  `/cook <pointer-path> --spec "$SPEC"`.

Only after explicit Cook selection, render the branch selected by `mode`:

**Decomposable specs (`decomposable: true`, `candidate_curds ≥ 2`, `mode: parallel`):**

- **Run the full pipeline (parallel fan-out when disjoint, else linear)** *(recommended)* — use the disposition-selected auto command above. Cook later uses the approved curds to select parallel or linear execution; `/plate` publishes the selected ordinary or stacked layout.
- **Implement manually, one phase at a time** — use the disposition-selected manual command above.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, high-blast-radius specs (`decomposable: false`, verdict `high` only, `mode: linear`):**

- **Run the full pipeline in fresh-context isolation** *(recommended)* — use the disposition-selected auto command. Red-required behavior continues `cook → press → age → cure → age → cure → age`; closed N/A skips Press and continues `cook → age → cure → age → cure → age`.
- **Implement manually, one phase at a time** — use the disposition-selected manual command.
- **Compact and resume by hand** — dispatch none; clear context, then use the disposition-selected manual command. `/cheese --continue` scans phase handoff slugs, so a fresh spec must be resumed through its explicit path.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, low- or medium-blast-radius specs (`decomposable: false`, verdict `low` or `medium`, `mode: null`):**

- **Implement the spec** *(recommended)* — use the disposition-selected manual command.
- **Implement and auto-review** — use the disposition-selected auto command. Opening or updating a PR remains `/plate`'s explicit step.
- **Research more first** — `/briesearch`.
- **Stop** — dispatch none; leave the spec for later.

`mode: parallel|linear` selects fresh-context Cook execution; `mode: null` selects the smaller in-session path. The user must still opt into `--auto`.
