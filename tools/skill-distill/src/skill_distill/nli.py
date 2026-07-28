"""NLI remains bidirectional diagnostic evidence, never semantic authority."""

from __future__ import annotations

from .retrieval import BidirectionalNliEvidence


def contradiction_signal(evidence: BidirectionalNliEvidence) -> float:
    """Return the stronger directional contradiction for deterministic reporting."""
    return max(evidence.left_contradicts_right, evidence.right_contradicts_left)


def mutual_entailment_signal(evidence: BidirectionalNliEvidence) -> float:
    """Return the weaker directional entailment; both directions must support it."""
    return min(evidence.left_entails_right, evidence.right_entails_left)
