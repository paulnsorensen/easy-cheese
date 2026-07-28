# Handoff branch menus

Read this when rendering `/mold`'s post-Curdle handoff menu (`SKILL.md` § Handoff) — the exact wording for each of the three blast-radius branches, and how the digest's `mode` signal picks among them.

**Decomposable specs (`decomposable: true`, `candidate_curds ≥ 2`, `mode: parallel`):**

The approved spec already contains file-disjoint candidate curds validated before the handshake. `/cook` is the dispatched skill either way: its curd-block gate routes 2+ file-disjoint curds to parallel mode and folds a single curd into the linear chain, so the approved plan informs execution without changing the command.

- **Run the full pipeline (parallel fan-out when disjoint, else linear)** *(recommended)* — `/cook --auto <spec-path>`. The decomposer picks parallel curd fan-out or the linear chain; `/plate` performs the final artifact-writing gate, resolves topology from the explicit choice and review shape, and publishes the ordinary or stacked layout.
- **Implement manually, one phase at a time** — `/cook <spec-path>`.
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, high-blast-radius specs (`decomposable: false`, verdict `high` only, `mode: linear`):**

The spec is large enough that per-phase context contamination becomes a real concern: review reasoning softens when the same window contains the cook reasoning, and the parent context bloats across phases. Offer fresh-context isolation and the manual compaction path:

- **Run the full pipeline in fresh-context isolation** *(recommended)* — `/cook --auto <spec-path>`, autonomous chain (`cook → press → age → cure → age → cure → age`, all `--auto`) with each phase running inside its own sub-agent, blind to prior phases.
- **Implement manually, one phase at a time** — `/cook <spec-path>`.
- **Compact and resume by hand** — dispatch none; clear context, then dispatch `/cook <spec-path>` directly. (`/cheese --continue` scans phase handoff slugs only — fresh specs don't surface there until cook lands a slug — so dispatching the explicit command is the resumption path here.)
- **Stop** — dispatch none; leave the spec for later.

**Non-decomposable, low- or medium-blast-radius specs (`decomposable: false`, verdict `low` or `medium`, `mode: null`):**

- **Implement the spec** *(recommended)* — `/cook <spec-path>`.
- **Implement and auto-review** — `/cook --auto <spec-path>`, chains through `/press → /age → /cure`. Opening or updating a PR remains a `/plate` step; a new PR follows its explicit-choice and review-shape policy.
- **Research more first** — `/briesearch`, gather more external evidence before implementing.
- **Stop** — dispatch none; leave the spec for later.

The internal `mode` signal is what distinguishes the branches above, never the offered command: `mode: parallel` or `mode: linear` means the spec crosses enough curds or module boundaries that the fresh-context, fully-autonomous `/cook --auto` chain is the recommended pick (the decomposable and high-blast-radius branches); `mode: null` means the footprint stays small enough that plain `/cook` is the recommended pick and `/cook --auto` remains a user-opt-in alternative (the low/medium branch). The no-pre-select-autonomous rule stated in `SKILL.md` still applies — the user opts into `--auto`, it is never the only path offered.
