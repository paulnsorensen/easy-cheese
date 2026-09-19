# Schema intertwine

Run `scripts/render_generated_regions.py` to generate this file. Do not edit it manually. The generator joins the phase registry (`_compiled_phase_registry`), the schema catalog (`_schema_catalog`), and the registered contract models (contracts.py, pr_plan.py) for each phase transition.

## Phase transitions

| Source phase | Contract version | Input schemas | Destination | Payload schema | Payload contract |
| --- | --- | --- | --- | --- | --- |
| age | 1.0 | curd-result | cure | curd-plan | CurdPlan |
| cook | 1.0 | mold-cook-handoff | age | curd-result | CurdResult |
| cook | 1.0 | mold-cook-handoff | mold | planner-request | PlannerRequest |
| cook | 1.0 | mold-cook-handoff | press | curd-result | CurdResult |
| cure | 1.0 | curd-plan | age | curd-result | CurdResult |
| mold | 1.0 | planner-request | cook | mold-cook-handoff | MoldCookHandoff |
| press | 1.0 | curd-result | age | curd-result | CurdResult |

## Registered schema catalog

| Slug | Contract model | Input to phase | Output of phase |
| --- | --- | --- | --- |
| agent-writer-view | AgentWriterView | — | — |
| checkpoint-intent | CheckpointIntent | — | — |
| cook-preparation-result | CookPreparationResult | — | — |
| curd-plan | CurdPlan | cure | age |
| curd-result | CurdResult | age, press | cook, cure, press |
| diagnosis-request | DiagnosisRequest | — | — |
| diagnosis-result | DiagnosisResult | — | — |
| handoff-pointer | HandoffPointer | — | — |
| mold-cook-approval | MoldCookApproval | — | — |
| mold-cook-handoff | MoldCookHandoff | cook | mold |
| normalization-receipt | NormalizationReceipt | — | — |
| phase-contract | PhaseContract | — | — |
| planner-request | PlannerRequest | mold | cook |
| planner-result | PlannerResult | — | — |
| pr-plan | PrPlan | — | — |
| review-request | ReviewRequest | — | — |
| review-result | ReviewResult | — | — |
| wheypoint-record | WheypointRecord | — | — |
| wheypoint-revision | WheypointRevision | — | — |
