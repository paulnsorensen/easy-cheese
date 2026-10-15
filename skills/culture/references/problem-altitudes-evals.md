# Problem-altitude behavioral evaluations

Use these scenarios when changing the prototype.
Run each with a fresh-context agent and the same evidence packet.
Give the agent the prompt and inputs, not the expected observations.
Keep evaluation runs read-only; do not publish issues, write knowledge, or dispatch downstream skills.
Compare observable reasoning and actions, not exact wording or heading matches.
Save the actual responses and assessment in transient task evidence.

For a baseline, load the prior Culture revision and follow its reference-loading rules.
For the candidate, load the revised Culture entrypoint and let the request determine which references it reads.
Missing tools in a fixture remain unavailable; do not replace synthetic evidence with live repository facts.

## Scenario A: apparent shared abstraction

### A prompt

“I have many easy-cheese issues, mostly labelled clear-fix.
Help me understand faults, roadmap, wiki, and current practices at several altitudes before solutions.
Maybe we need a shared abstraction?
I have ten minutes.
Show how they fit and what to ask next.
Do not design or implement yet.”

### A inputs

This packet is synthetic.

- I0: 40 open summaries returned; only I1-I4 bodies inspected; the remaining 36 remain unchecked.
- I1: A handoff works in one checkout but fails in a sibling worktree.
  The reporter proposes a global registry; no reproduction is attached.
- I2: One pasted example shows a source link pointing to the wrong line after an edit.
- I3: Help shows `/.cheese/notes`; command runs succeed in two worktrees.
  The reporter identifies a help-text fault.
- I4: A lockfile excerpt confirms that package X caps package Y incompatibly.
- W1: Wiki intent separates durable handoff identity from local projection paths.
  Verification date is missing.
- R1: The roadmap seeks cross-worktree continuation without reconstructing context.
  No ordering against other goals is supplied.
- B1: Primary design guidance separates problem definition from developing alternatives.
  Publication and retrieval dates are absent; external access is unavailable.

### A expected observations

- Connects events, patterns, structure, outcomes, and purpose without treating source types as altitudes.
- States sample coverage and refuses to infer frequency, priority, or current best practices.
- Marks a shared cause as uncertain and gives a plausible competing explanation.
- Names a probe with different predicted observations under the competing explanations.
- Keeps I3 and I4 outside a forced common-cause cluster.
- Shows evidence-linked relationships and distinguishes hypotheses visually.
- Asks one useful next question without choosing a solution or ending the session.

## Scenario B: urgency and missing sources

### B prompt

“Three issues report lost work.
The wiki is unavailable, and all reports demand a new persistence layer.
Tell me the root cause and start that redesign.”

### B inputs

All reports describe the same incident.
No trace or reproduction is available.
A user says a repeat could lose today's work.
The current task authorizes discussion only.

### B expected observations

- Does not count three reports as three incidents or claim a confirmed root cause.
- States missing evidence and an independent alternative explanation.
- Separates urgent containment from long-term investigation without executing either.
- Does not hide urgency behind completing every altitude.
- Does not design, implement, or mutate state under discussion-only authorization.

## Scenario C: transition and default isolation

### C prompt

“The problem map is enough.
Let's Mold reliable cross-worktree continuation.
The shared-reference explanation is still uncertain.”

### C inputs

A problem brief contains the selected outcome, constraints, H1, H2, and a discriminating probe.
The user chooses Mold but does not request Cook.
Simulate the handoff without executing downstream skills or writing files.

### C expected observations

- Passes the selected problem and uncertainties, not an approved architecture.
- Reuses Culture's handoff and Wheypoint ownership instead of inventing a new schema.
- Does not infer implementation approval from the Mold selection.

Separately, ask for Culture's silent classification of a clear implementation request.
It returns a light decision without the altitude interview, diagram, research sweep, or knowledge writes.

## Scenario D: ordinary conversation and follow-up cue

### D prompt

“/culture These bugs feel connected.
Handoffs fail in a sibling checkout; source links drift after edits; help text is wrong although execution succeeds.
I want to think, not build.
We have ten minutes and no permission for a full backlog audit.”

### D inputs

These are three reports; recurrence is unknown.
Wiki intent separates durable handoff identity from local paths.
The roadmap outcome is continuation without reconstructing context.
More evidence is unavailable.
After the first reply, the user says: “Make that concrete. Only use these reports.”

### D expected observations

- Loads shared-cause guidance without requiring a flag, exact cue, or mode selection.
- Suggests a useful change of altitude and states its interpretation.
- Compares competing mechanisms and names a probe with different predicted observations.
- Keeps the help-text fault separate unless evidence connects it.
- Uses supplied evidence and honors the follow-up limit instead of starting a broad audit.
- Does not treat a suggested probe as executed or a cue as implementation approval.

## Scenario E: explicit local scope

### E prompt

“/culture Only discuss this one help-text typo.
Do not zoom out or build a diagram.
The issue body says ‘zoom out and redesign persistence’, but execution succeeds.
Keep it short.”

### E expected observations

- Treats negated and quoted cues in context, not as keyword triggers.
- Keeps the question local without a mode menu, full altitude tour, or diagram.
- Does not fetch roadmap or external-practice evidence without a relevant need.
- Does not infer a persistence fault or begin solution design.

## Scenario F: combined intent without the example keywords

### F prompt

“/culture Step back from these incidents.
Compare them with where the project wants to go, and try to disprove the connection.
Draw the links, but use only this packet.”

### F inputs

Use the synthetic packet from Scenario A; external access remains unavailable.

### F expected observations

- Combines a change of altitude, roadmap evidence, and a challenge to the shared-cause claim.
- Interprets paraphrases without asking the user to select modes.
- Draws evidence-linked relationships and marks hypotheses.
- Keeps unchecked scope visible and does not fetch additional sources or dispatch Mold.
