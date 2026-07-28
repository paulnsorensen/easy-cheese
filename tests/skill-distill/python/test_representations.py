import pytest

from skill_distill.representations import RepresentationCandidate, choose_representation


def test_lower_passing_invocation_loaded_variant_is_selected():
    chosen = choose_representation(100, [RepresentationCandidate("physical-reference", 80, True), RepresentationCandidate("compact-inline", 60, True)])
    assert chosen.name == "compact-inline"
    assert chosen.loaded_token_savings == 40


def test_static_size_cannot_override_invocation_loaded_tokens_or_behavior_gate():
    chosen = choose_representation(100, [RepresentationCandidate("compact-inline", 20, False, static_bytes=1), RepresentationCandidate("physical-reference", 70, True, static_bytes=999)])
    assert chosen.name == "physical-reference"
    with pytest.raises(ValueError, match="positive invocation-loaded"):
        choose_representation(50, [RepresentationCandidate("compact-inline", 50, True)])
