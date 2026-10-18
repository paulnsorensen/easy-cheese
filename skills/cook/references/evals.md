# Cook evals

Run these trace scenarios against a fresh task agent in an isolated fixture repository. Supply the changed Mold bundle explicitly.

## Finalized direct inputs reach execution

1. Give the agent a selected Mold spec and a typed planner result.
2. Require Mold finalization to return ready `spec_ref`, `planner_result_ref`, `plan_ref`, and `coverage`.
3. Require host validation of the retained result before any feature writer dispatch.
4. If runner setup is needed, retain an explicit response to exact command and path limits, then successful setup evidence.
5. Capture the input route, bound references, setup evidence, actual execution, and final artifact.

The trace passes only when the checker accepts it, the real bound validator loads every reference, and Cook executes the requested curd.

## Missing planning remains saved-not-ready

Give the agent a strict spec without planner output. Mold finalization must return `saved-not-ready`; no writer may run. Supply a typed planner result and the same selected scope before retrying. Changed scope needs a new user selection.

## User hold stays locked

Start with a named execution hold or whole-request stop directive. Re-finalization, `--auto`, or arbitrary setup evidence must not clear it. Only a fresh user decision and updated bound spec can change the selection.

## Stale or detached inputs fail closed

Tamper with a retained spec or plan digest, or pair the planner with a different plan. The bound validator must reject it before writer dispatch.

## Trace acceptance

Capture each trace with `python3 -m tests.python.mold_cook_agent_driver --fixture-repository <repo> --mold-bundle <pyz> --responses <json> --output <trace.json> -- <command>`; it exits non-zero when the transcript check fails. Frozen fixtures cover checker regressions, but they do not replace one live captured run for this workflow change.
