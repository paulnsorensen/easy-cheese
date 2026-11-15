# Journey eval gates

The deterministic gates of the `/skillz autoimprove` journey suites live as Python sources under `scripts/journey_gates/`.
`scripts/journey_gate_compiler.py` inlines them into each `skills/<skill>/evals/autoimprove.json` as `kinds.journey.argv = ["python3", "-I", "-c", SOURCE]`.
Edit the sources, then run the compiler. `tests/python/test_journey_gates.py` and `tests/python/test_journey_gates_core_loop.py` (age, cure, wheypoint) fail on drift, so `just check` catches a hand edit of the JSON.
The compiler finds each skill from its gate module, so a new suite needs only `scripts/journey_gates/<skill>.py` and its contract.

## Why the sources live outside `skills/`

- The bundle doctrine forbids hand-written Python under `skills/` (see [skill-python-bundle-doctrine](./skill-python-bundle-doctrine.md)).
- skillz also accepts a `gate` file under `evals/gates/`, but that file would be Python under `skills/`.
- Inline `argv` keeps the doctrine and still gives the sources lint, type checks, and unit tests.
- `common.py` holds the shared code. Each skill module imports it inside a `# gate:strip-begin` / `# gate:strip-end` block, which the compiler drops. The compiler exits 2 on an unpaired marker or CRLF.
- The strip block also drops the skill module's own imports. A module that `common.py` does not import (for example `shutil` or `tempfile`) must sit below `# gate:strip-end`, or the compiled gate raises `NameError`. Put the `# pyright:` pragma inside the strip block.

## Runtime limits that shape the code

- skillz runs the whole gate in its task sandbox with `SANDBOX_SECONDS = 20` (skillz `packages/skillz/src/skillz_experiments/_runtime.py:18`). A timeout scores 0.
- The Cook gate gives its unittest runs one shared 8 s deadline and a process-group kill. When no time remains, a run counts as unknown, not as a fail or a pass.
- skillz scores 0 unless stdout is exactly one JSON object with a numeric `score` (skillz `packages/skillz/src/skillz_experiments/_graders.py:188-205`). The gate prints one line `{"score": 0|1, "fails": [...]}` and captures every child's output.
- The code is standard library only and must run on Python 3.9 or later. Hosts can have an old system `python3`.

## Two trace shapes

- Claude writes stream-json events: `type: assistant` content blocks, with `tool_use` names `Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.
- Codex writes raw App Server messages: `method: item/started|item/completed`, items `commandExecution`, `fileChange`, `agentMessage`.
- `common.py` normalizes both into ordered `text`, `shell`, and `write` steps. A gate that reads only the Claude shape sees no tool calls on Codex, so every gate must read both shapes.
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
- A Cook correction may change source without a test in one case. The fixture suite fails and the output suite passes, because an existing Press attack test now passes. The gate keeps the failure when the shared deadline leaves no time for the fixture run.
- `unverified-ok` needs a test-run shell step after the last Python write. Press needs a test-run step before any `ok` claim, also with no write.
- A step counts as a test run only when it names a test. These count: `pytest`, `tox`, `nox`, `python -m unittest|pytest`, `just|make` with a target that contains `test` or `check`, `uv run` followed by a test run, `python x.py` where `x` is `test_*.py`, `*_test.py`, or `repro*.py`, and the `repro-rerun` archive call. Steps such as `ls`, `just fmt`, `uv run ruff`, and `python3 scripts/tool.py` do not count.
- A test run that also redirects or tees its output still counts as a run. A redirect to a log is not a source write.
- A write tool call that the host denies or that fails is an `attempt` step. Claude marks it with an `is_error` tool result; Codex marks it with a `failed` or `declined` file change. An attempt changes no file, so `unverified-ok` ignores it. The forbidden-edit rules (Mold source writes, Press production writes, Cook holds) still fail on it.
- A shell step writes a file through a redirect, `tee`, `sed -i`, `perl -i`, or the target of `cp`, `mv`, or `install`.
- `source-without-test` exempts an `__init__.py` only when its body is empty, a docstring, or imports. Executable logic in it needs a test.
- Only write targets inside the workspace root count. A write to `/tmp` never trips a hold or a production rule.
- Interpreter code on stdin (`python3 - <<EOF`) gets the same publication scan as `python3 -c`.
- One `CODE_EXT` tuple in `common.py` defines the code extensions for the Mold and Press rules.
- Age replays the case's `restore-repo.sh` in a temp dir and fails `production-changed` when the visible output tree differs. This catches a write by any route, including `python -c` and `git checkout --`.
- Cure fails `test-regressed` when a test that passed on the fixture tree fails or vanishes in the output. A deferred finding may leave its own test red.

## Fixture convention

`skills/<skill>/evals/journey-gates.json` is an easy-cheese convention, not a skillz format.
A fixture names a `case`, an expected `score`, and the exact sorted `fails`.
Its replayed output is the case `files`, overlaid by the fixture `output` map, minus `output_deleted`.
Keep only changed files in `output`, so a case edit does not break the fixture.
A restored Press finding report carries `digest: sha256:<hex> (<test path>)`, the SHA-256 of the seeded attack test file. Press stops when the digest is missing. Recompute it when you edit that test file.

A `restore-repo.sh` fixture runs inside the Claude Code sandbox, which keeps `.git/config` and `.git/hooks` read-only and puts dotfile placeholders in the workspace root (skillz-that-grillz#703).
Write the Git identity and any `core.hooksPath` to `$HOME/.config/git/config`, keep a hook in a visible `githooks/` directory, and stage regular non-dot files by name instead of `git add -A`.
The age gate replays the script with a private `HOME`; a replay that fails skips the tree check, so `test_age_replay_catches_a_change_in_every_case` proves the replay for each case.

## Gate sources per skill

- The compiler derives each skill from a gate file stem, so the stem equals the skill directory: `scripts/journey_gates/hard-cheese.py`, not `hard_cheese.py`.
- Each gate module keeps `# pyright:` pragmas inside its `gate:strip` block, as `common.py` does. The compiled source drops `from __future__ import annotations`, so annotations run on Python 3.9: use `Optional` and built-in generics, never `X | Y`.
- `tests/python/test_journey_gates.py` runs the shared checks (compile, stdlib, fixture replay, Codex parity) over `GATE_SKILLS`. Its synthetic `clean()` scenarios model a Cook workspace, so the generic push and pull-request tests cover only `SKILLS`. Rule tests for affinage, melt, and hard-cheese live in `tests/python/test_journey_gates_<skill>.py` and import helpers from `tests.python.test_journey_gates`.
- Age, cure, and wheypoint (`CORE_LOOP_SKILLS`) keep their fixture replay, Codex parity, and rule tests in `tests/python/test_journey_gates_core_loop.py`. The shared file still checks that every gate source belongs to `GATE_SKILLS` or `CORE_LOOP_SKILLS` and fits one argv string.
- Affinage cases stub `gh` in `bin/gh` (including `pr checkout` and `repo view`), and requests stop at the `/cure` handoff, because sibling skills are not staged.
- Melt cases build the conflict with `restore-repo.sh` under `GIT_CONFIG_GLOBAL=/dev/null`; the gate fails `not-restored` when no step runs it.
- Hard-cheese cases expect `--no-judge` (LOGGED) when no judge sub-agent can run; an `ERROR` attempt without a judge run is a dealbreaker.
- The journey judge receives only the user and agent text of each turn, never tool calls or their arguments (skillz `evaluation/_evaluator.py` `_judge_data`; skillz issue #649 tracks showing commands). A criterion such as "the agent SHALL run `append-attempt`" cannot be graded and scores low. Grade the agent's report in criteria and check commands in the gate.
## Intake minimums

skillz intake has these minimums (skillz `packages/skillz/src/skillz_experiments/_intake.py:24-31`).
It needs at least 4 scored families. It trains on 4 cases from 2 families. It validates on 1 family, the smallest. It holds out at least 6 cases.
Every scored journey case needs EARS `expected.criteria`.
`skillz-experiment.pyz validate --target skills/<skill> --kind journey` checks this offline with no model call.

Run `/skillz autoimprove` against the skill directory inside the repository, not a copy. Each `skills/<skill>/wedge.toml` inherits `skills/wedge.toml`, whose paths are repo-relative, so a copied skill stops with `wedge-config-invalid`.
skillz checks the `family` of every `evals.json` task entry even in a `--kind journey` run, and a seed task entry with `files: []` fails the draft loader.


## Case hardness and run planning

Evidence from the 2026-11-15 harder-case run (Pasteurize and Mold, skillz dist `47b57bb1`):

- skillz stops with `cases-too-easy` when any train or validation family has a seed mean of 0.9 or more. One saturated family stops the run, even when other families have headroom.
- A run draft must hold every case in `journeys.json`. To keep a saturated family out of train and validation, pick a `--seed` that puts it in holdout. `run` without approvals prints the split in the `cases-unapproved` question, so a seed survey costs no model call.
- The plan sits near the 1000-call ceiling and cannot be approved lower. A Mold suite with 7 or more holdout cases fits only with `--repeats 1`.
- `--edit` is recorded when `run.json` is first written. Pass `--edit prose` on that call, or the run records the default `prose+cli`.
- Measured cost: about $0.24 per scored Pasteurize outcome and $0.40 per scored Mold outcome (Sonnet task, Opus judge and reflection, list prices).
- Saturated families at that time: Pasteurize `trace`, Mold `mini`. The seed also solved the drafted Pasteurize `decoy` and `verify` families (0.98 and 1.00), so they were dropped before merge.
- A gutted SKILL.md (three generic steps) scored 0.00 on every new case. Use it as the weak arm when a suite needs a discrimination check.

