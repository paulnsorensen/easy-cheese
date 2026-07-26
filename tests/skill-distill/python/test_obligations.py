import pytest

from skill_distill.obligations import (
    ObligationAtomV1,
    ObligationCategory,
    Polarity,
    SourceSpan,
)


def test_signed_obligation_retains_every_behavioral_field_and_exact_span():
    span = SourceSpan("skills/cheese/SKILL.md", 42, 44)
    atom = ObligationAtomV1(
        ObligationCategory.HALT,
        Polarity.PROHIBITED,
        "advance",
        "run state",
        "when digests differ",
        3,
        span,
    )

    assert atom.category is ObligationCategory.HALT
    assert atom.polarity is Polarity.PROHIBITED
    assert (atom.action, atom.object, atom.condition, atom.order) == (
        "advance", "run state", "when digests differ", 3
    )
    assert atom.source_span == span


@pytest.mark.parametrize("start,end", [(0, 1), (2, 1)])
def test_source_span_rejects_non_exact_ranges(start, end):
    with pytest.raises(ValueError):
        SourceSpan("source.md", start, end)
