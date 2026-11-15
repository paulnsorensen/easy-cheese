# ADR: The planner owns semantic decomposition

Decision status: accepted
Spec: `/home/paul/.local/share/cheese/paulnsorensen-easy-cheese/specs/workflow-contract-milknado-seam.md`

## Context

<certain> Mold already delegates pre-approval decomposition, while Age and Pasteurize currently produce caller-specific findings or diagnosis handoffs.[^1] Allowing each evidence producer or executor to invent curds would create several planning authorities.

## Decision

<certain> PlannerRequest discriminates `decompose`, `remediate`, and `replan` and carries typed evidence. PlannerResult owns `complete`, `partial`, `no_work`, and `blocked` dispositions; invalid output and executor failure remain separate.

<certain> A partial result may carry a valid executable CurdPlan plus unresolved omitted work. Uncertainty affecting an emitted curd, dependency, or shared constraint makes the result blocked.

<certain> Decompose creates a new plan at revision 1. Replan retains plan identity, increments revision, and records `identity_action: new|retain|derive` plus prior curd IDs. Remediate creates a child plan. Split and merge derive new curd IDs with lineage.

<certain> ReviewResult contains typed findings and a coverage ledger. DiagnosisResult contains symptom, reproduction, hypotheses, optional confirmed cause, regression seam, and unresolved evidence. They share only EvidenceRef and SourceLocation and contain no remediation plan.

<certain> Age and Pasteurize produce evidence, then dispatch the planner. They do not create curds.

## Alternatives

- Let Cook or Cure decompose: rejected because execution would own semantic planning.
- Let review findings become curds directly: rejected because a finding is evidence, not executable work.
- Execute uncertain partial curds: rejected because partial means omitted uncertainty, not weakened emitted work.

## Consequences

<certain> Every route into Cook or Cure passes through one planner decision. F001 adopts Age and Pasteurize after the core Mold-to-Cook seam and Milknado importer prove the contracts.

[^1]: `skills/mold/references/curdle.md:232-242`; `skills/age/SKILL.md:191-203`; `skills/pasteurize/SKILL.md:184-210`.
