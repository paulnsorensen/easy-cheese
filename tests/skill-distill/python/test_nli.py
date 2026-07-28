from skill_distill.nli import contradiction_signal, mutual_entailment_signal
from skill_distill.retrieval import BidirectionalNliEvidence


def test_bidirectional_nli_keeps_both_directions_as_diagnostic_evidence() -> None:
    evidence = BidirectionalNliEvidence(0.9, 0.7, 0.2, 0.4)

    assert mutual_entailment_signal(evidence) == 0.7
    assert contradiction_signal(evidence) == 0.4
