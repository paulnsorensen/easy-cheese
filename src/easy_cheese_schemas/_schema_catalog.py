"""Generated dependency-free canonical contract schema catalogue."""

from __future__ import annotations

SCHEMA_ROOT = 'https://schemas.easy-cheese.dev'
AGENT_WRITER_VIEW_SCHEMA_URI = f"{SCHEMA_ROOT}/agent-writer-view"
CURD_PLAN_SCHEMA_URI = f"{SCHEMA_ROOT}/curd-plan"
CURD_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/curd-result"
DIAGNOSIS_REQUEST_SCHEMA_URI = f"{SCHEMA_ROOT}/diagnosis-request"
DIAGNOSIS_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/diagnosis-result"
PHASE_CONTRACT_SCHEMA_URI = f"{SCHEMA_ROOT}/phase-contract"
PLANNER_REQUEST_SCHEMA_URI = f"{SCHEMA_ROOT}/planner-request"
PLANNER_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/planner-result"
REVIEW_REQUEST_SCHEMA_URI = f"{SCHEMA_ROOT}/review-request"
REVIEW_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/review-result"

REGISTERED_CONTRACT_SCHEMA_URIS = frozenset(
    {
        AGENT_WRITER_VIEW_SCHEMA_URI,
        CURD_PLAN_SCHEMA_URI,
        CURD_RESULT_SCHEMA_URI,
        DIAGNOSIS_REQUEST_SCHEMA_URI,
        DIAGNOSIS_RESULT_SCHEMA_URI,
        PHASE_CONTRACT_SCHEMA_URI,
        PLANNER_REQUEST_SCHEMA_URI,
        PLANNER_RESULT_SCHEMA_URI,
        REVIEW_REQUEST_SCHEMA_URI,
        REVIEW_RESULT_SCHEMA_URI,
    }
)
