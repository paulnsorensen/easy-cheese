# Cook writer-view schemas

Cook writer agents emit `AgentWriterView` documents that contain `kind` and `payload`.

Before the host persists each document, it normalizes the document and validates its structure against the catalog contracts.

For each `WriterViewKind`, a writer agent must produce the applicable payload shape below.

The `scripts/render_generated_regions.py` script refreshes these shapes from `src/easy_cheese_schemas/contracts.py`.

Do not edit the generated region manually.

<!-- BEGIN GENERATED: cook-writer-views -->
// A `?` marks an optional field. `= value` shows the applied default.
map WriterViewKind -> WriterPayload {
  curd_plan -> CurdPlanWriterView
  curd_result -> CurdResultWriterView
  diagnosis_result -> DiagnosisResultWriterView
  planner_result -> PlannerResultWriterView
  review_result -> ReviewResultWriterView
}

type AgentWriterView {
  kind WriterViewKind
  payload WriterPayload
}

type BoundedContextWriterView {
  shared_input_keys? tuple[str, ...] = ()
  constraints? tuple[str, ...] = ()
  invariants? tuple[str, ...] = ()
}

type BoundedScope {
  paths? tuple[str, ...] = ()
  excluded_paths? tuple[str, ...] = ()
}

type CriterionResultWriterView {
  disposition CriterionDisposition
  evidence_keys? tuple[str, ...] = ()
  reason? str | None = None
}

type CriterionWriterView {
  description str
  check str
}

type CurdPlanWriterView {
  objective str
  curds tuple[SemanticCurdWriterView, ...]
  context? BoundedContextWriterView | None = None
}

type CurdResultWriterView {
  criterion_results tuple[CriterionResultWriterView, ...]
  deliverables? tuple[DeliverableWriterView, ...] = ()
  unresolved_work? tuple[str, ...] = ()
}

type DeliverableWriterView {
  role str
  path str
  media_type str
}

type DiagnosisCauseWriterView {
  summary str
  evidence_keys tuple[str, ...]
  location? SourceLocationWriterView | None = None
}

type DiagnosisHypothesisWriterView {
  statement str
  disposition HypothesisDisposition
  evidence_keys? tuple[str, ...] = ()
}

type DiagnosisResultWriterView {
  disposition DiagnosisDisposition
  reproduction ReproductionWriterView
  hypotheses tuple[DiagnosisHypothesisWriterView, ...]
  confirmed_cause? DiagnosisCauseWriterView | None = None
  regression_seam? SourceLocationWriterView | None = None
  unresolved_evidence_keys? tuple[str, ...] = ()
  reason? str | None = None
}

type PlannerResultWriterView {
  disposition PlannerDisposition
  plan? CurdPlanWriterView | None = None
  unresolved_work? tuple[PlannerUncertaintyWriterView, ...] = ()
  reason? str | None = None
}

type PlannerUncertaintyWriterView {
  description str
  scope UncertaintyScope
  evidence_keys? tuple[str, ...] = ()
}

type ReproductionWriterView {
  status ReproductionDisposition
  steps tuple[str, ...]
  observed? str | None = None
  evidence_keys? tuple[str, ...] = ()
}

type ReviewFindingWriterView {
  severity ReviewSeverity
  summary str
  evidence_keys tuple[str, ...]
  location? SourceLocationWriterView | None = None
}

type ReviewResultWriterView {
  disposition ReviewDisposition
  findings tuple[ReviewFindingWriterView, ...]
  reason? str | None = None
}

type SemanticCurdWriterView {
  key str
  outcome str
  scope BoundedScope
  outputs tuple[str, ...]
  criteria tuple[CriterionWriterView, ...]
  input_keys? tuple[str, ...] = ()
  dependencies? tuple[str, ...] = ()
}

type SourceLocationWriterView {
  path str
  start_line int
  end_line int
  start_column? int | None = None
  end_column? int | None = None
}

enum CriterionDisposition = "passed" | "failed" | "blocked" | "skipped"

enum DiagnosisDisposition = "confirmed" | "inconclusive" | "not_reproduced" | "blocked" | "invalid" | "executor_failure"

enum HypothesisDisposition = "confirmed" | "rejected" | "unresolved"

enum PlannerDisposition = "complete" | "partial" | "no_work" | "blocked" | "invalid" | "executor_failure"

enum ReproductionDisposition = "reproduced" | "not_reproduced" | "blocked"

enum ReviewDisposition = "clean" | "findings" | "blocked" | "invalid" | "executor_failure"

enum ReviewSeverity = "critical" | "high" | "medium" | "low"

enum UncertaintyScope = "omitted_work" | "emitted_work" | "dependency" | "shared_constraint"

enum WriterViewKind = "curd_plan" | "planner_result" | "review_result" | "diagnosis_result" | "curd_result"
<!-- END GENERATED -->
