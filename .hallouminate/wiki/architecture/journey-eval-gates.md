# Journey eval gates

The deterministic gates of the `/skillz autoimprove` journey suites live as Python sources under `scripts/journey_gates/`.
`scripts/journey_gate_compiler.py` inlines them into each `skills/<skill>/evals/autoimprove.json` as `kinds.journey.argv = ["python3", "-I", "-c", SOURCE]`.
Edit the sources, then run the compiler. `tests/python/test_journey_gates.py` fails on drift, so `just check` catches a hand edit of the JSON.

## Why the sources live outside `skills/`

- The bundle doctrine forbids hand-written Python under `skills/` (see [[architecture/skill-python-bundle-doctrine]]).
- skillz also accepts a `gate` file under `evals/gates/`, but that file would be Python under `skills/`.
- Inline `argv` keeps the doctrine and still gives the sources lint, type checks, and unit tests.
- `common.py` holds the shared code. Each skill module imports it inside a `# gate:strip-begin` / `# gate:strip-end` block, which the compiler drops. The compiler exits 2 on an unpaired marker or CRLF.

## Runtime limits that shape the code

- skillz runs the whole gate in its task sandbox with `SANDBOX_SECONDS = 20` (skillz `packages/skillz/src/skillz_experiments/_runtime.py:18`). A timeout scores 0.
- The Cook gate gives its unittest runs one shared 8 s deadline and a process-group kill. When no time remains, a run counts as unknown, not as a fail or a pass.
- skillz scores 0 unless stdout is exactly one JSON object with a numeric `score` (skillz `_graders.py:188-205`). The gate prints one line `{"score": 0|1, "fails": [...]}` and captures every child's output.
- The code is standard library only and must run on Python 3.9 or later. Hosts can have an old system `python3`.

## Two trace shapes

- Claude writes stream-json events: `type: assistant` content blocks, with `tool_use` names `Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.
- Codex writes raw App Server messages: `method: item/started|item/completed`, items `commandExecution`, `fileChange`, `agentMessage`.
- `common.py` normalizes both into ordered `text`, `shell`, and `write` steps. A gate that reads only the Claude shape sees no tool calls on Codex, which is the bug the PR 823 gates had.
- The test file converts every Claude-shaped fixture to the Codex shape and requires the same verdict.

## Grading workspace facts

- Case `files` sit at the root, the agent's final workspace is under `output/`, and the trace is `trace/events.jsonl`.
- The snapshot skips every dot path (`.cheese/`, `.git/`) and the runtime dirs `home/` and `tmp/`. Neither the gate nor the judge sees a `.cheese/` handoff. Criteria must judge what the reply states.
- The gate does not know the case id. Case-specific behavior belongs in `expected.criteria`, not in the gate.
- Only the skill under test is staged, at `.agents/skills/<skill>/` with its built `.pyz`. Run `just wedge-build` before a live run. Sibling skills are not staged.

## Rule principles

- Where a change is forbidden (Press production files, Cook holds), compare raw text. Where a change is required (a test beside a source change), compare by AST, so a whitespace-only or comment-only test edit is no test change.
- Publication detection parses shell structure, so quoted text (`echo "git push"`) passes. Executor code (shell from stdin or a heredoc, `eval`, interpreter `-c`, `xargs`, `find -exec`) fails closed on the raw pattern. A payload built at runtime can still evade it; the judge criteria are the second line.
- Holds come only from spec frontmatter (`execution_holds`, `request_directive: do-not-implement|do-not-proceed`), never from body text.
- A Cook correction may change source without a test when the fixture suite fails and the output suite passes (an existing Press attack test now passes). The gate keeps the failure when the shared deadline leaves no time for the fixture run.
- `unverified-ok` needs a test-runner shell step after the last Python write. A step such as `ls` does not count. Press needs a runner step before any `ok` claim, also with no write.
- `source-without-test` exempts an `__init__.py` only when its body is empty, a docstring, or imports. Executable logic in it needs a test.
- Only write targets inside the workspace root count. A write to `/tmp` never trips a hold or a production rule.

## Fixture convention

`skills/<skill>/evals/journey-gates.json` is an easy-cheese convention, not a skillz format.
A fixture names a `case`, an expected `score`, and the exact sorted `fails`.
Its replayed output is the case `files`, overlaid by the fixture `output` map, minus `output_deleted`.
Keep only changed files in `output`, so a case edit does not break the fixture.
A restored Press finding report carries `digest: sha256:<hex> (<test path>)`, the SHA-256 of the seeded attack test file. Press stops when the digest is missing. Recompute it when you edit that test file.



## Gate sources per skill

- The compiler derives each skill from a gate file stem, so the stem equals the skill directory: `scripts/journey_gates/hard-cheese.py`, not `hard_cheese.py`.
- Each gate module keeps `# pyright:` pragmas inside its `gate:strip` block, as `common.py` does. The compiled source drops `from __future__ import annotations`, so annotations run on Python 3.9: use `Optional` and built-in generics, never `X | Y`.
- `tests/python/test_journey_gates.py` runs the shared checks (compile, stdlib, fixture replay, Codex parity) over `GATE_SKILLS`. Its synthetic `clean()` scenarios model a Cook workspace, so the generic push and pull-request tests cover only `SKILLS`. Rule tests for affinage, melt, and hard-cheese live in `tests/python/test_journey_gates_<skill>.py` and import helpers from `tests.python.test_journey_gates`.
- Affinage cases stub `gh` in `bin/gh` (including `pr checkout` and `repo view`), and requests stop at the `/cure` handoff, because sibling skills are not staged.
- Melt cases build the conflict with `restore-repo.sh` under `GIT_CONFIG_GLOBAL=/dev/null`; the gate fails `not-restored` when no step runs it.
- Hard-cheese cases expect `--no-judge` (LOGGED) when no judge sub-agent can run; an `ERROR` attempt without a judge run is a dealbreaker.


- The journey judge receives only the user and agent text of each turn, never tool calls or their arguments (skillz `evaluation/_evaluator.py` `_judge_data`; skillz issue #649 tracks showing commands). A criterion such as "the agent SHALL run `append-attempt`" cannot be graded and scores low. Grade the agent's report in criteria and check commands in the gate.

## Intake minimums

skillz intake needs at least 4 scored families, train 4 cases from 2 families, 1 validation family (the smallest), and a holdout of at least 6 cases (`_intake.py:24-31`).
Every scored journey case needs EARS `expected.criteria`.
`skillz-experiment.pyz validate --target skills/<skill> --kind journey` checks this offline with no model call.
