import contextlib
import io
import json
from pathlib import Path
from importlib import import_module
from typing import cast, final, override

import pytest

import prompt_lab
from prompt_lab import (
    BudgetExhausted,
    ProviderError,
    Case,
    ProviderReply,
    Turn,
    evaluate_candidate,
    load_dataset,
    main,
    score_output,
    validate_dataset,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "prompt_lab" / "dataset.json"


class FakeProvider:
    def __init__(self, replies: list[object]) -> None:
        self._replies: list[object] = list(replies)
        self.requests: list[list[dict[str, str]]] = []
        self.calls: int = 0
        self.usage: list[dict[str, int]] = []

    def complete(
        self, messages: list[dict[str, str]], model: str, max_output_tokens: int
    ) -> ProviderReply:
        del model, max_output_tokens
        self.requests.append([dict(message) for message in messages])
        self.calls += 1
        if not self._replies:
            raise ProviderError("provider request failed")
        reply = self._replies.pop(0)
        return ProviderReply(
            reply if isinstance(reply, str) else json.dumps(reply),
            {"total_tokens": 3},
        )

    def reflect(
        self, messages: str | list[dict[str, str]], model: str, max_output_tokens: int
    ) -> str:
        del messages, model, max_output_tokens
        self.calls += 1
        self.usage.append({"total_tokens": 2})
        return "Improve the candidate."



@final
class OptimizationProvider(FakeProvider):
    @override
    def complete(
        self, messages: list[dict[str, str]], model: str, max_output_tokens: int
    ) -> ProviderReply:
        del model, max_output_tokens
        self.requests.append([dict(message) for message in messages])
        self.calls += 1
        contract = messages[0]["content"].rsplit("typed fields: ", 1)[1].rstrip(".")
        output: dict[str, object] = {}
        for item in contract.split(", "):
            name, kind = item.split(": ")
            output[name] = False if kind == "boolean" else "pending"
        self.usage.append({"total_tokens": 3})
        return ProviderReply(json.dumps(output), {"total_tokens": 3})




def _case(split: str = "validation"):
    dataset = load_dataset(FIXTURE)
    return next(case for case in dataset.cases if case.split == split)




def _case_result(result: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], cast(list[object], result["case_results"])[0])


def _fixture_payload() -> dict[str, object]:
    return cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _payload_cases(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["cases"])


def test_fixture_validates_and_splits_without_leakage() -> None:
    dataset = load_dataset(FIXTURE)
    _ = validate_dataset(dataset)
    assert {case.family for case in dataset.train} == {"iterative", "override"}
    assert {case.family for case in dataset.validation} == {"relation", "revision"}
    assert {case.family for case in dataset.holdout} == {"deferral", "investigation"}
    identifiers = [case.identifier for case in dataset.train + dataset.validation + dataset.holdout]
    assert len(identifiers) == len(set(identifiers))


def test_scoring_requires_typed_values_and_rejects_extra_keys() -> None:
    expected = {"prototype_authorized": True}
    assert score_output(expected, expected) == (1.0, [])
    assert score_output({"prototype_authorized": False}, expected)[0] == 0.0
    assert score_output({"prototype_authorized": 1}, expected)[0] == 0.0
    assert score_output({"prototype_authorized": True, "extra": False}, expected)[0] == 0.0


def test_multiturn_history_does_not_include_hidden_expectations_or_future_turns() -> None:
    case = _case("train")
    provider = FakeProvider(
        [
            {"full_spec_required": False, "prototype_authorized": False, "publication_authorized": False},
            {"full_spec_required": False, "prototype_authorized": True, "publication_authorized": False},
            {"full_spec_required": False, "prototype_authorized": True, "publication_authorized": True},
        ]
    )
    result = evaluate_candidate("Return JSON.", [case], provider, repeats=1, max_calls=4)
    assert _case_result(result)["score"] == 1.0
    assert len(provider.requests) == 3
    second = provider.requests[1]
    assert any(message["role"] == "assistant" and "prototype_authorized" in message["content"] for message in second)
    assert any(message["role"] == "user" and "Sketch a short" in message["content"] for message in second)
    assert "expected" not in provider.requests[0][0]["content"]
    assert "publication_authorized" in provider.requests[0][0]["content"]
    assert "open a PR" not in provider.requests[1][-1]["content"]

    sentinel_case = Case(
        "sentinel", "sentinel", "validation",
        (
            Turn("first user turn", {"state": "string"}, {"state": "GOLD_CHECKPOINT_SENTINEL"}, frozenset({"state"})),
            Turn("future user FUTURE_TURN_SENTINEL", {"state": "string"}, {"state": "GOLD_CHECKPOINT_SENTINEL"}, frozenset({"state"})),
        ),
    )
    sentinel_provider = FakeProvider([{"state": "observed"}, {"state": "observed"}])
    _ = evaluate_candidate("Return JSON.", [sentinel_case], sentinel_provider)
    assert "GOLD_CHECKPOINT_SENTINEL" not in " ".join(message["content"] for message in sentinel_provider.requests[0])
    assert "FUTURE_TURN_SENTINEL" not in " ".join(message["content"] for message in sentinel_provider.requests[0])
    assert "GOLD_CHECKPOINT_SENTINEL" not in " ".join(message["content"] for message in sentinel_provider.requests[1])
    assert "FUTURE_TURN_SENTINEL" not in sentinel_provider.requests[0][-1]["content"]


def test_malformed_provider_output_scores_zero_with_diagnostic() -> None:
    provider = FakeProvider(["not json"] * 3)
    result = evaluate_candidate("Return JSON.", [_case()], provider, repeats=1, max_calls=3)
    case_result = _case_result(result)
    assert case_result["score"] == 0.0
    assert case_result["eligible"] is False
    assert "invalid JSON" in cast(list[str], case_result["failures"])[0]


def test_provider_budget_failure_is_not_a_model_error() -> None:
    provider = FakeProvider([{"prototype_authorized": False}])
    with pytest.raises(BudgetExhausted):
        _ = evaluate_candidate("Return JSON.", [_case("train")], provider, repeats=3, max_calls=1)


def test_ordinary_failure_keeps_average_but_hard_failure_disqualifies() -> None:
    case = Case(
        "ordinary", "ordinary", "validation",
        (Turn("ordinary", {"soft": "boolean", "hard": "boolean"}, {"soft": True, "hard": True}, frozenset({"hard"})),
         Turn("ordinary2", {"soft": "boolean", "hard": "boolean"}, {"soft": True, "hard": True}, frozenset({"hard"}))),
    )
    provider = FakeProvider([{"soft": True, "hard": True}, {"soft": False, "hard": True}])
    ordinary = evaluate_candidate("Return JSON.", [case], provider)
    assert ordinary["eligible"] is True
    assert 0.0 < cast(float, ordinary["aggregate_score"]) < 1.0

    hard_case = _case("train")
    hard_provider = FakeProvider(
        [
            {"full_spec_required": False, "prototype_authorized": False, "publication_authorized": False},
            {"full_spec_required": False, "prototype_authorized": False, "publication_authorized": False},
            {"full_spec_required": False, "prototype_authorized": True, "publication_authorized": True},
        ]
    )
    hard = evaluate_candidate("Return JSON.", [hard_case], hard_provider)
    assert hard["eligible"] is False
    assert hard["aggregate_score"] == 0.0


def test_non_object_output_is_a_hard_failure() -> None:
    result = evaluate_candidate("Return JSON.", [_case()], FakeProvider(["[]"] * 3))
    assert result["eligible"] is False


def test_evaluate_writes_artifact_and_does_not_mutate_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "prompt.md"
    _ = source.write_text("Keep this seed.", encoding="utf-8")
    before = source.read_bytes()
    fake = FakeProvider([
        {"category_relation": True, "dependency_relation": False},
        {"category_relation": False, "dependency_relation": True},
        {"category_relation": False, "dependency_relation": True},
        {"head_revision": "r1", "review_revision": "r1", "ci_revision": "r1", "evidence_ready_to_merge": True},
        {"head_revision": "r2", "review_revision": "r1", "ci_revision": "pending", "evidence_ready_to_merge": False},
        {"head_revision": "r2", "review_revision": "r1", "ci_revision": "r2", "evidence_ready_to_merge": False},
    ])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    def make_fake(_key: str, _limit: int) -> FakeProvider:
        return fake
    monkeypatch.setattr(prompt_lab, "OpenAIProvider", make_fake)
    output = tmp_path / "evaluation"
    code = main(
        [
            "evaluate",
            "--dataset",
            str(FIXTURE),
            "--prompt",
            str(source),
            "--split",
            "validation",
            "--model",
            "test-model",
            "--output-dir",
            str(output),
        ]
    )
    assert code == 0
    assert source.read_bytes() == before
    artifact = cast(dict[str, object], json.loads((output / "result.json").read_text(encoding="utf-8")))
    case_results = cast(list[dict[str, object]], artifact["case_results"])
    assert cast(list[object], case_results[0]["checkpoints"])
    assert artifact["calls"] == 6


def test_no_key_refusal_and_existing_output_rejected_before_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "prompt.md"
    _ = source.write_text("Prompt.", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    existing = tmp_path / "existing"
    existing.mkdir()
    error = io.StringIO()
    with contextlib.redirect_stderr(error):
        code = main(
            [
                "evaluate",
                "--dataset",
                str(FIXTURE),
                "--prompt",
                str(source),
                "--model",
                "test-model",
                "--output-dir",
                str(existing),
            ]
        )
    assert code == 2
    assert "already exists" in error.getvalue()
    assert "OPENAI_API_KEY" not in error.getvalue()


def test_provider_error_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingCompletions:
        def create(self, **kwargs: object) -> object:
            del kwargs
            raise RuntimeError("provider-body-secret")

    @final
    class FailingChat:
        def __init__(self) -> None:
            self.completions = FailingCompletions()

    @final
    class FailingClient:
        def __init__(self) -> None:
            self.chat = FailingChat()

    class FailingModule:
        @staticmethod
        def OpenAI(**kwargs: object) -> FailingClient:
            del kwargs
            return FailingClient()

    def fake_import(_name: str) -> FailingModule:
        return FailingModule()

    monkeypatch.setattr(prompt_lab, "import_module", fake_import)
    provider = prompt_lab.OpenAIProvider("do-not-print", 1)
    with pytest.raises(ProviderError, match="provider request failed") as raised:
        _ = provider.complete([{"role": "user", "content": "hello"}], "model", 32)
    assert "provider-body-secret" not in str(raised.value)


def test_invalid_dataset_contract_is_rejected(tmp_path: Path) -> None:
    payload = _fixture_payload()
    _payload_cases(payload)[0]["fields"] = {}
    path = tmp_path / "bad.json"
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fields"):
        _ = load_dataset(path)


def test_invalid_split_is_rejected(tmp_path: Path) -> None:
    payload = _fixture_payload()
    cases = _payload_cases(payload)
    cases[1]["family"] = cases[0]["family"]
    cases[1]["split"] = "validation"
    path = tmp_path / "bad.json"
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="family"):
        dataset = load_dataset(path)
        _ = validate_dataset(dataset)


def test_real_gepa_optimization_uses_only_train_validation_and_rejects_hard_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        _ = import_module("gepa.optimize_anything")
    except ImportError:
        pytest.skip("gepa is not installed")
    source = tmp_path / "seed.md"
    _ = source.write_text("Seed candidate.", encoding="utf-8")
    provider = OptimizationProvider([])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    def make_provider(_key: str, _limit: int) -> OptimizationProvider:
        return provider
    monkeypatch.setattr(prompt_lab, "OpenAIProvider", make_provider)
    output = tmp_path / "optimization"
    code = main([
        "optimize", "--dataset", str(FIXTURE), "--seed-prompt", str(source),
        "--model", "test-model", "--output-dir", str(output), "--max-calls", "64",
        "--max-metric-calls", "2",
    ])
    assert code == 2
    assert provider.calls > 6
    assert provider.usage
    assert all("A saved audit verifies" not in message["content"] for request in provider.requests for message in request)
    assert not (output / "best_candidate.md").exists()
    artifact = cast(dict[str, object], json.loads((output / "result.json").read_text(encoding="utf-8")))
    assert artifact["exported"] is False
    assert cast(list[dict[str, int]], artifact["usage"])
    assert cast(dict[str, object], artifact["best_result"])["eligible"] is False