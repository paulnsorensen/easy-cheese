# Decision ledger

The decision ledger is Mold's record of what the session knows, decided, and still asks.
Mold prints it each round (`../SKILL.md` § Rules).
This reference owns the shape of each ledger line.
[`adr.md`](adr.md) owns where the ledger persists at curdle.

## Line shapes

| Line | Shape |
| --- | --- |
| `Goal:` | The pinned goal sentence, verbatim from the bounds pass. |
| `G-n` | One outcome clause of the goal, in the user's words (`handshake.md` § Goal coverage). |
| `Evidence:` | `ev-n (<confidence>, <source>): <finding>`, or the grounding record `hallouminate: absent`. |
| `Decided:` | `F-n: <EARS requirement> (<basis ids>)` for each fork that the user settled. |
| `Asking:` | `F-n: <question> Basis: <ids>. Moves: <target>.` for each open consequential fork. |
| `[AGENT-DECIDED]` | `AD-n: <EARS requirement> · veto: <alternative> (<basis ids>)` for each call below the leverage line. |
| `Non-goals:` | One scope exclusion per item. |

The `Asking` line keeps the altitude tag (`Moves:`) and the basis of its fork card ([`fork-questions.md`](fork-questions.md) § Basis).
A claim that is not settled keeps its `[?]` marker on every line that uses it.
Each `ev-n` keeps its confidence: `certain`, `speculating`, or `don't know`.

## EARS requirements

Each `Decided` and `[AGENT-DECIDED]` entry states its outcome as one EARS requirement.
A free-text outcome such as "SQLite, one file" is not a ledger entry.
The five EARS patterns come from Mavin et al., "Easy Approach to Requirements Syntax" (IEEE RE'09):

| Pattern | Form |
| --- | --- |
| Ubiquitous | `THE <system> SHALL <response>` |
| Event-driven | `WHEN <trigger> THE <system> SHALL <response>` |
| State-driven | `WHILE <state> THE <system> SHALL <response>` |
| Unwanted behavior | `IF <condition>, THEN THE <system> SHALL <response>` |
| Optional feature | `WHERE <feature is included> THE <system> SHALL <response>` |

`WHEN`, `WHILE`, and `WHERE` can combine, also inside an `IF ... THEN` requirement.

Write each requirement to these rules:

- Name the narrowest subject that the decision binds: a component, a seam, or an artifact, for example `THE store`. Use `THE SYSTEM` only when no narrower subject exists.
- Give one requirement for each entry. A decision that binds two behaviors becomes two entries with the same fork id.
- State a response that a user, a caller, or a test can observe.
- Keep the fork id, the basis ids, and the veto alternative on the line. EARS replaces the free-text outcome, not the trace.
- When a decision binds no system response, such as a date, an owner, or a process, write prose and add `[prose-fallback]`. Acceptance uses the same marker (`curdle.md` § Spec template).

Three lines stay out of EARS.
The `Goal:` line and the `G-n` clauses stay in the user's words, because `goal-drift` and goal coverage compare text.
The Acceptance lines that cover a clause are EARS.
A non-goal names an exclusion, not a behavior, and feeds the non-goals audit (`handshake.md` § Non-goals audit).

At curdle, each `Decided` entry seeds the Acceptance line that carries its fork id.
Each `[AGENT-DECIDED]` entry becomes one `_Minor decisions:_` item with its veto alternative.

Example:

```text
Goal: Give the agent CLI a file-only database: no server, one directory, safe under concurrent agent writes.
  G-1 no server process · G-2 one directory under the repo · G-3 concurrent writes never corrupt
Evidence:
  ev-1 (certain, explorer digest): each CLI command runs in its own process; no daemon exists.
  ev-2 (certain, sqlite3 docs): WAL mode lets readers run while one writer commits.
Decided:
  F-1: THE store SHALL keep every record in one SQLite file at `.cheese/db/store.sqlite`. (ev-1, G-1, G-2)
  F-2: WHEN two agents write at once THE store SHALL serialize the writes through one lock file. (ev-2, G-3)
Asking:
  F-3: Which shape does the public interface take? Basis: F-1, F-2, ev-1. Moves: the Store seam, AC-4.
[AGENT-DECIDED]:
  AD-1: THE store SHALL import only the Python standard library. · veto: an ORM (ev-1)
Non-goals: no remote sync · no encryption at rest
```

## Review canvas

When the review canvas runs, publish each ledger entry with one text in two places ([`review-canvas.md`](review-canvas.md)):

- The `decided` and `agent-decided` rows of `ledger` hold each entry's EARS text, with its `F-n` or `AD-n` id.
- `requirements` holds the same entries. Each `Decided` and `[AGENT-DECIDED]` entry is `settled`. The requirement that an open fork will settle is `draft`. `fork_ids` names the fork.
- Each open question carries its `basis`.

`review publish` warns when a `decided` or `agent-decided` item, or a requirement, has no `SHALL` and no `[prose-fallback]`.
It also warns when an open question has no `basis`.
