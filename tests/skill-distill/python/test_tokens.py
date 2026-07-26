from skill_distill.tokens import build_tokenizer_identity, loaded_tokens, measure_load_events, token_savings


class Words:
    def encode(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return text.split()


def test_load_events_are_encoded_independently_and_repeated_loads_repeat_cost():
    identity = build_tokenizer_identity("tok", "rev", "hash", "runtime")
    profile = measure_load_events(identity, [("skill", "a.md", b"one two"), ("reference", "r.md", b"three"), ("reference", "r.md", b"three")], Words())
    assert [event.token_count for event in profile.load_events] == [2, 1, 1]
    assert loaded_tokens(profile) == 4
    assert token_savings(profile, measure_load_events(identity, [("skill", "a.md", "one")], Words())) == 3


def test_tokenizer_identity_is_stable_and_does_not_include_load_events():
    first = build_tokenizer_identity("tok", "rev", "hash", "runtime")
    second = build_tokenizer_identity("tok", "rev", "hash", "runtime")
    assert first.identity_digest == second.identity_digest
