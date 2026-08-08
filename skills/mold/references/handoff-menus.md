# Handoff branch menus

Read this when rendering `/mold`'s post-Curdle handoff. The `curd-count` digest selects the entry skill before these blast-radius branches:

- `recommended_skill: /cut` and a non-null `handoff` means `red-required`. Auto choices use `/cut --auto <spec-path>` and manual choices use `/cut <spec-path>`; Cut issues the receipt, then hands off to Cook.
- `recommended_skill: /cook` means closed `not-applicable` or legacy input. Auto choices use `/cook --auto <spec-path>` and manual choices use `/cook <spec-path>`.

Never replace a `/cut` recommendation with Cook. Then render the branch selected by `mode`:

**Decomposable specs (`decomposable: true`, `candidate_curds ≥ 2`, `mode: parallel`):**

- **Run the full pipeline (parallel fan-out when disjoint, else linear)** *(recommended)* — use the disposition-selected auto command above. Cook later uses the approved curds to select parallel or linear execution; `/plate` publishes the selected ordinary or stacked layout.
- **Implement manually, one phase at a time** — use the disposition-selected manual command above.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, high-blast-radius specs (`decomposable: false`, verdict `high` only, `mode: linear`):**

- **Run the full pipeline in fresh-context isolation** *(recommended)* — use the disposition-selected auto command. Active RED continues `cut → cook → press → age → cure → age → cure → age`; closed N/A skips Press and continues `cook → age → cure → age → cure → age`.
- **Implement manually, one phase at a time** — use the disposition-selected manual command.
- **Compact and resume by hand** — dispatch none; clear context, then use the disposition-selected manual command. `/cheese --continue` scans phase handoff slugs, so a fresh spec must be resumed through its explicit path.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, low- or medium-blast-radius specs (`decomposable: false`, verdict `low` or `medium`, `mode: null`):**

- **Implement the spec** *(recommended)* — use the disposition-selected manual command.
- **Implement and auto-review** — use the disposition-selected auto command. Opening or updating a PR remains `/plate`'s explicit step.
- **Research more first** — `/briesearch`.
- **Stop** — dispatch none; leave the spec for later.

`mode: parallel|linear` selects fresh-context Cook execution after any required Cut receipt; `mode: null` selects the smaller in-session path. The user must still opt into `--auto`.
