// Milknado native Workflow node-runner (harness-side, "ultracode").
//
// Runs INSIDE a Claude Code dynamic-Workflow session. It fans out ONE worker
// agent() per already-claimed milknado node. It runs ALONGSIDE — never replaces
// — the subprocess CLI dispatcher (Codex/opencode have no ultracode primitive).
//
// ── INSTALL / DISCOVERY ──────────────────────────────────────────────────────
// `workflows/` is not a recognized plugin component, so this file is NOT
// auto-loaded from the plugin payload. The plugin's SessionStart hook
// (hooks/hooks.json -> hooks/install-workflow.sh) closes that gap: it
// idempotently copies this file into the project's `.claude/workflows/`
// (copy when absent, no-op when identical, refresh when this copy changes,
// never delete) — installing the plugin IS the install step; the workflow is
// runnable as of the next session start. This file is the in-repo
// source-of-truth the hook copies from.
// Power-user shortcut (UNVERIFIED against public docs — only milknado's
// internal live test of 2026-06-15 corroborates it): skip the copy and invoke
// by explicit path: Workflow({ scriptPath: "<path>/node-runner.js",
// args: { claims: [...] } }). Do not rest tooling on it.
//
// ── WHY THIS IS FAN-OUT ONLY (hard runtime constraint) ───────────────────────
// A Workflow SCRIPT body can call only agent()/parallel()/pipeline()/log()/
// phase(); MCP tools are `undefined` in script scope — they are reachable ONLY
// from inside agents. (Verified 2026-06-15: a `typeof` probe returned "undefined"
// for milknado_todo_claim/node_verify/deposit_result/set_status, "function" for
// agent/parallel.) So this script does NOT call milknado MCP tools. All MCP
// claim/verify/mark-done work is the ORCHESTRATOR's job (the live session driving
// this Workflow), and the per-worker deposit is the WORKER AGENT's job.
//
// ── ORCHESTRATOR CONTRACT (the live session / driver runs these INLINE) ───────
// The orchestrator owns every milknado MCP call. Around each invocation of this
// script it runs, in order:
//   1. const plan = milknado_plan_batches(changes, budget)
//   2. resolve plan.batches' change_ids -> owning graph node IDs. plan_batches
//      never touches the graph: Batch.change_ids is a pure echo of the
//      caller-supplied FileChange.id strings, and no MCP tool maps a change_id
//      back to a node id after the fact.
//      CONVENTION (MUST): when batching already-existing graph nodes, set
//      id = str(node.id) on each change fed into plan_batches. Resolution is
//      then one line at fan-out time. Worked example:
//        changes = [{ id: "5", path: "src/a.py" }, { id: "9", path: "src/b.py" }]
//        plan.batches[0].change_ids            // == ["5", "9"]
//        nodeIds = plan.batches[0].change_ids.map(Number)   // -> [5, 9]
//   3. for each batch, in dependency order:
//        a. claims = batch.map(nodeId => milknado_todo_claim(nodeId, project_root))
//           Attach project_root to each claim payload before passing it in.
//        b. let pending = claims
//        c. for (iter = 0; iter < max_iterations && pending.length; iter++):
//             // run THIS script to fan out one worker per pending node:
//             Workflow({ scriptPath: <this file>, args: { claims: pending } })
//             verdicts = pending.map(c => milknado_node_verify(c.run_id, project_root))
//             ok      = verdicts.filter(v => v.ok)      // -> milknado_todo_set_status(node_id,'done')  (gated)
//             pending = verdicts.filter(v => !v.ok)     // attach v.feedback, re-dispatch (mode B redispatch)
//        // loop_mode "single" workers self-verify (below), so they pass on iter 0.
//   4. nodes still unverified after max_iterations stay RUNNING and are reclaimed
//      by milknado's existing fail_stale_running_runs / reconcile path.
//
// ── ARGS ─────────────────────────────────────────────────────────────────────
// The Workflow runtime delivers `args` as a JSON STRING (verified 2026-06-15),
// so this script JSON.parses it. Shape:
//   { claims: [ { run_id, node_id, brief, worktree_path, agent_type, model,
//                 max_turns, loop_mode, project_root, feedback? }, ... ] }

export const meta = {
  name: 'milknado-node-runner',
  description:
    'Fan out one milknado:milknado-worker agent per claimed node. The orchestrator does claim/verify/set_status inline around this (see header); the worker does the task + milknado_deposit_result itself.',
  phases: [{ title: 'Execute' }],
}

phase('Execute')

// `args` arrives as a JSON string; tolerate an already-parsed object defensively.
const input = typeof args === 'string' ? JSON.parse(args) : args || {}
const claims = Array.isArray(input.claims) ? input.claims : []
if (!claims.length) {
  throw new Error(
    'node-runner: args.claims must be a non-empty array of claim payloads. The ' +
      'orchestrator calls milknado_todo_claim INLINE (the script cannot — MCP is ' +
      'agent-only) and passes the payloads in as args.claims. Got: ' +
      JSON.stringify(input).slice(0, 200),
  )
}

function workerBrief(c) {
  const fb = c.feedback
    ? `\n\n## Verify feedback from the previous attempt — address this\n${c.feedback}\n`
    : ''
  const single =
    c.loop_mode === 'single'
      ? `\nThis node is loop_mode="single": after you believe the task is done, call ` +
        `milknado_node_verify(run_id="${c.run_id}", project_root="${c.project_root || ''}") ` +
        `yourself and keep working until it returns ok:true BEFORE you deposit.`
      : ''
  return (
    `${c.brief}${fb}\n\n` +
    `Work ONLY inside your worktree: ${c.worktree_path}\n` +
    `Your run_id is ${c.run_id}.${single}\n` +
    `As your final step, call milknado_deposit_result with run_id="${c.run_id}", ` +
    `project_root="${c.project_root || ''}", and payload set to your COMPLETE deliverable ` +
    `(the full text, not a reference). The deposited payload is what the coordinator reads back.`
  )
}

// One worker agent per claimed node, fanned out concurrently. The worker agent
// type (milknado:milknado-worker) carries the scoped tool allowlist; model is
// passed per-call (the structured field from the claim) so it routes correctly.
const results = await parallel(
  claims.map((c) => () =>
    agent(workerBrief(c), {
      agentType: c.agent_type || 'milknado:milknado-worker',
      model: c.model,
      maxTurns: c.max_turns,
      label: `worker-node-${c.node_id ?? c.run_id}`,
    }),
  ),
)

// Dispatch receipt only — NOT a completion verdict. The orchestrator calls
// milknado_node_verify per run_id next and decides done / re-dispatch.
log(`node-runner: dispatched ${claims.length} worker(s), ${results.filter(Boolean).length} returned`)
return {
  dispatched: claims.length,
  returned: results.filter(Boolean).length,
  run_ids: claims.map((c) => c.run_id),
}
