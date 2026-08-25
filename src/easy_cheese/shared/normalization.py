"""Schema-runtime normalization adapter for writer views."""

from __future__ import annotations

from easy_cheese.shared.handoffs import InvocationContext
from easy_cheese_schemas.contracts import AgentWriterView
from easy_cheese_schemas.schema_runtime import CanonicalArtifact, normalize_agent_output


def normalize_writer_view(
    writer_view: AgentWriterView, invocation: InvocationContext
) -> CanonicalArtifact:
    """Normalize through the canonical schema runtime without semantic coercion."""
    return normalize_agent_output(writer_view, invocation.as_mapping())


__all__ = ["normalize_writer_view"]