"""Development-only prompt optimization proxy.

This module is intentionally standalone. It does not execute tools or publish prompts.
"""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable, Protocol, cast, final


MAX_TEXT = 120_000
SPLITS = ("train", "validation", "holdout")
Message = dict[str, str]

JsonValue = object
JsonObject = dict[str, object]
MAX_REPEATS = 100
MAX_CALLS = 10_000
MAX_OUTPUT_TOKENS = 8_192


class _MessageObject(Protocol):
    content: str | None


class _Choice(Protocol):
    message: _MessageObject


class _Usage(Protocol):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class _Response(Protocol):
    choices: list[_Choice]
    usage: _Usage | None


class _Completions(Protocol):
    def create(self, **kwargs: object) -> _Response: ...


class _Chat(Protocol):
    completions: _Completions


class _OpenAIClient(Protocol):
    chat: _Chat


class PromptLabError(ValueError):
    """A user-correctable prompt laboratory input error."""


class ProviderError(RuntimeError):
    """The model provider failed; this is not a model score."""


class BudgetExhausted(RuntimeError):
    """The explicit provider request budget was exhausted."""


@dataclass(frozen=True)
class Turn:
    user: str
    fields: dict[str, str]
    expected: JsonObject
    hard: frozenset[str]


@dataclass(frozen=True)
class Case:
    identifier: str
    family: str
    split: str
    turns: tuple[Turn, ...]


@dataclass(frozen=True)
class Dataset:
    cases: tuple[Case, ...]
    provenance: str

    @property
    def train(self) -> tuple[Case, ...]:
        return tuple(case for case in self.cases if case.split == "train")

    @property
    def validation(self) -> tuple[Case, ...]:
        return tuple(case for case in self.cases if case.split == "validation")

    @property
    def holdout(self) -> tuple[Case, ...]:
        return tuple(case for case in self.cases if case.split == "holdout")


@dataclass(frozen=True)
class ProviderReply:
    text: str
    usage: dict[str, int]


@dataclass(frozen=True)
class RunArgs:
    dataset: str
    model: str
    output_dir: str
    max_calls: int
    max_output_tokens: int
    repeats: int
    prompt: str = ""
    split: str = "validation"
    seed_prompt: str = ""
    max_metric_calls: int = 8
    reflection_model: str = ""


class Provider(Protocol):
    def complete(
        self, messages: list[Message], model: str, max_output_tokens: int
    ) -> ProviderReply: ...


def require_mapping(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise PromptLabError(f"{label} must be an object")
    return cast(JsonObject, value)


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PromptLabError(f"{label} must be a non-empty string")
    return value


def _json_type(value: object, label: str) -> str:
    if not isinstance(value, str) or value not in {"string", "boolean", "number"}:
        raise PromptLabError(f"{label} has unsupported type")
    return value


def load_dataset(path: Path) -> Dataset:
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise PromptLabError(f"cannot read dataset: {path}") from error
    root = require_mapping(raw, "dataset")
    if root.get("version") != 1:
        raise PromptLabError("dataset version must be 1")
    cases_raw = root.get("cases")
    if not isinstance(cases_raw, list) or not cases_raw:
        raise PromptLabError("dataset cases must be a non-empty list")
    cases: list[Case] = []
    for index, case_raw in enumerate(cast(list[object], cases_raw)):
        case = require_mapping(case_raw, f"cases[{index}]")
        identifier = require_text(case.get("id"), f"cases[{index}].id")
        family = require_text(case.get("family"), f"{identifier}.family")
        split = require_text(case.get("split"), f"{identifier}.split")
        if split not in SPLITS:
            raise PromptLabError(f"{identifier}.split is invalid")
        fields_raw = require_mapping(case.get("fields"), f"{identifier}.fields")
        if not fields_raw:
            raise PromptLabError(f"{identifier}.fields must not be empty")
        fields = {name: _json_type(kind, f"{identifier}.fields.{name}") for name, kind in fields_raw.items()}
        turns_raw = case.get("turns")
        if not isinstance(turns_raw, list) or not turns_raw:
            raise PromptLabError(f"{identifier}.turns must be non-empty")
        turns: list[Turn] = []
        for turn_index, turn_raw in enumerate(cast(list[object], turns_raw)):
            turn = require_mapping(turn_raw, f"{identifier}.turns[{turn_index}]")
            expected = require_mapping(turn.get("expect"), f"{identifier}.turns[{turn_index}].expect")
            if set(expected) != set(fields):
                raise PromptLabError(f"{identifier} expectation fields do not match contract")
            hard_raw = turn.get("hard", list(fields))
            hard_items = cast(list[object], hard_raw) if isinstance(hard_raw, list) else []
            if not hard_items or not all(isinstance(item, str) for item in hard_items):
                raise PromptLabError(f"{identifier}.hard must be a list of field names")
            hard_names = [cast(str, item) for item in hard_items]
            if not set(hard_names) <= set(fields):
                raise PromptLabError(f"{identifier}.hard names an unknown field")
            turns.append(Turn(require_text(turn.get("user"), f"{identifier}.user"), fields, expected, frozenset(hard_names)))
        cases.append(Case(identifier, family, split, tuple(turns)))
    dataset = Dataset(tuple(cases), require_text(root.get("provenance"), "dataset.provenance"))
    validate_dataset(dataset)
    return dataset


def validate_dataset(dataset: Dataset) -> None:
    if not dataset.provenance.strip():
        raise PromptLabError("dataset provenance is required")
    if not dataset.cases:
        raise PromptLabError("dataset must not be empty")
    by_split = {split: [case for case in dataset.cases if case.split == split] for split in SPLITS}
    if any(not cases for cases in by_split.values()):
        raise PromptLabError("each split must be non-empty")
    identifiers = [case.identifier for case in dataset.cases]
    if len(identifiers) != len(set(identifiers)):
        raise PromptLabError("case ids must be unique")
    family_splits: dict[str, str] = {}
    for case in dataset.cases:
        previous = family_splits.setdefault(case.family, case.split)
        if previous != case.split:
            raise PromptLabError(f"family {case.family!r} leaks across splits")
        for turn in case.turns:
            for field, value in turn.expected.items():
                kind = turn.fields[field]
                if kind == "string" and not isinstance(value, str):
                    raise PromptLabError(f"{case.identifier}.{field} must be a string")
                if kind == "boolean" and type(value) is not bool:
                    raise PromptLabError(f"{case.identifier}.{field} must be a boolean")
                if kind == "number" and (type(value) not in (int, float) or isinstance(value, bool)):
                    raise PromptLabError(f"{case.identifier}.{field} must be a number")


def score_output(output: object, expected: Mapping[str, object]) -> tuple[float, list[str]]:
    if not isinstance(output, dict):
        return 0.0, ["output must be a JSON object"]
    actual_output = cast(Mapping[str, object], output)
    failures: list[str] = []
    if set(actual_output) != set(expected):
        failures.append("output fields do not match the fixed contract")
    for field, wanted in expected.items():
        actual = actual_output.get(field)
        if type(actual) is not type(wanted) or actual != wanted:
            failures.append(f"{field}: expected {wanted!r}, received {actual!r}")
    return (1.0 if not failures else 0.0), failures




def _usage(value: _Usage | None) -> dict[str, int]:
    if value is None:
        return {}
    return {
        name: cast(int, getattr(value, name))
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        if getattr(value, name, None) is not None
    }


@final
class OpenAIProvider:
    def __init__(self, api_key: str, max_calls: int) -> None:
        if not api_key:
            raise PromptLabError("OPENAI_API_KEY is required")
        try:
            module = import_module("openai")
            openai_type = cast(Callable[..., _OpenAIClient], getattr(module, "OpenAI"))
        except ImportError as error:
            raise PromptLabError("install requirements/prompt-lab.txt for paid commands") from error
        try:
            self._client: _OpenAIClient = openai_type(api_key=api_key, timeout=60.0, max_retries=0)
        except Exception:
            raise PromptLabError("provider setup failed") from None
        self._max_calls: int = max_calls
        self.calls: int = 0
        self.usage: list[dict[str, int]] = []

    def _take_call(self) -> None:
        if self.calls >= self._max_calls:
            raise BudgetExhausted("max-calls budget exhausted")
        self.calls += 1

    def complete(self, messages: list[Message], model: str, max_output_tokens: int) -> ProviderReply:
        self._take_call()
        try:
            response = self._client.chat.completions.create(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
                max_completion_tokens=max_output_tokens,
                timeout=60.0,
            )
            text = response.choices[0].message.content or ""
            usage = _usage(response.usage)
            self.usage.append(usage)
            return ProviderReply(text, usage)
        except BudgetExhausted:
            raise
        except Exception:
            raise ProviderError("provider request failed") from None

    def reflect(self, messages: str | list[Message], model: str, max_output_tokens: int) -> str:
        self._take_call()
        prompt_messages = (
            [{"role": "user", "content": messages}]
            if isinstance(messages, str)
            else messages
        )
        try:
            response = self._client.chat.completions.create(
                messages=prompt_messages,
                model=model,
                max_completion_tokens=max_output_tokens,
                timeout=60.0,
            )
            usage = _usage(response.usage)
            self.usage.append(usage)
            return response.choices[0].message.content or ""
        except BudgetExhausted:
            raise
        except Exception:
            raise ProviderError("reflection request failed") from None


def _contract_prompt(candidate: str, fields: dict[str, str]) -> str:
    contract = ", ".join(f"{name}: {kind}" for name, kind in fields.items())
    return (
        candidate[:MAX_TEXT]
        + "\n\nFixed evaluator contract: reply with one JSON object containing only these "
        + f"typed fields: {contract}. Never explain the JSON."
    )


def evaluate_candidate(
    candidate: str,
    cases: list[Case] | tuple[Case, ...],
    provider: Provider,
    *,
    model: str = "",
    repeats: int = 1,
    max_calls: int = 100,
    max_output_tokens: int = 512,
) -> JsonObject:
    if not candidate.strip() or len(candidate) > MAX_TEXT:
        raise PromptLabError("candidate prompt must be non-empty and within size limit")
    if not 1 <= repeats <= MAX_REPEATS or not 1 <= max_calls <= MAX_CALLS:
        raise PromptLabError("repeats and max_calls are outside the supported bounds")
    if not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise PromptLabError("max_output_tokens is outside the supported bounds")
    if not cases:
        raise PromptLabError("cases must not be empty")
    call_count = 0
    case_results: list[JsonObject] = []
    total_usage: dict[str, int] = {}
    for case in cases:
        checkpoint_results: list[JsonObject] = []
        case_failed_hard = False
        for repeat in range(repeats):
            history: list[Message] = []
            for turn_index, turn in enumerate(case.turns):
                if call_count >= max_calls:
                    raise BudgetExhausted("max-calls budget exhausted")
                messages = [{"role": "system", "content": _contract_prompt(candidate, turn.fields)}]
                messages.extend(history)
                messages.append({"role": "user", "content": turn.user})
                reply = provider.complete(messages, model, max_output_tokens)
                call_count += 1
                for name, value in reply.usage.items():
                    total_usage[name] = total_usage.get(name, 0) + value
                try:
                    parsed = cast(JsonValue, json.loads(reply.text))
                except json.JSONDecodeError:
                    parsed = None
                    failures = ["invalid JSON provider output"]
                else:
                    _, failures = score_output(parsed, turn.expected)
                hard_failure = not isinstance(parsed, dict) or any(
                    failure.startswith(f"{field}:")
                    for failure in failures
                    for field in turn.hard
                )
                case_failed_hard = case_failed_hard or hard_failure
                checkpoint_results.append(
                    {
                        "repeat": repeat + 1,
                        "turn": turn_index + 1,
                        "score": 0.0 if failures else 1.0,
                        "failures": failures,
                        "hard_failure": hard_failure,
                        "response": parsed,
                    }
                )
                history.extend(
                    [
                        {"role": "user", "content": turn.user},
                        {"role": "assistant", "content": reply.text},
                    ]
                )
        checkpoint_score = sum(cast(float, item["score"]) for item in checkpoint_results) / len(checkpoint_results)
        case_results.append(
            {
                "case_id": case.identifier,
                "family": case.family,
                "score": 0.0 if case_failed_hard else checkpoint_score,
                "checkpoints": checkpoint_results,
                "failures": [failure for item in checkpoint_results for failure in cast(list[str], item["failures"])],
                "hard_failure": case_failed_hard,
                "eligible": not case_failed_hard,
            }
        )
    aggregate = sum(cast(float, item["score"]) for item in case_results) / len(case_results) if case_results else 0.0
    eligible = all(not cast(bool, item["hard_failure"]) for item in case_results)
    return {
        "aggregate_score": aggregate if eligible else 0.0,
        "eligible": eligible,
        "case_results": case_results,
        "calls": call_count,
        "usage": total_usage,
    }


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_prompt(value: str, root: Path) -> str:
    if value == "baseline":
        return "Return the required JSON state for each user turn. Preserve history and do not invent fields."
    if value == "current":
        paths = [root / "skills/cheese/SKILL.md", root / "skills/cheese/references/classification.md"]
        return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)
    path = Path(value)
    text = path.read_text(encoding="utf-8")
    if not text.strip() or len(text) > MAX_TEXT:
        raise PromptLabError("prompt file is empty or too large")
    return text


def new_output_dir(path: Path) -> None:
    if path.exists():
        raise PromptLabError(f"output directory already exists: {path}")
    path.mkdir(parents=True)


def write_json(path: Path, value: object) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True)
    if len(encoded) > 2_000_000:
        raise PromptLabError("artifact exceeds output size limit")
    _ = path.write_text(encoded + "\n", encoding="utf-8")


def _run_args(namespace: argparse.Namespace) -> RunArgs:
    return RunArgs(
        dataset=cast(str, getattr(namespace, "dataset", "")),
        model=cast(str, getattr(namespace, "model", "")),
        output_dir=cast(str, getattr(namespace, "output_dir", "")),
        max_calls=cast(int, getattr(namespace, "max_calls", 0)),
        max_output_tokens=cast(int, getattr(namespace, "max_output_tokens", 0)),
        repeats=cast(int, getattr(namespace, "repeats", 0)),
        prompt=cast(str, getattr(namespace, "prompt", "")),
        split=cast(str, getattr(namespace, "split", "validation")),
        seed_prompt=cast(str, getattr(namespace, "seed_prompt", "")),
        max_metric_calls=cast(int, getattr(namespace, "max_metric_calls", 8)),
        reflection_model=cast(str, getattr(namespace, "reflection_model", "")),
    )


def _provider(args: RunArgs) -> OpenAIProvider:
    if not 1 <= args.max_calls <= MAX_CALLS or not 1 <= args.max_output_tokens <= MAX_OUTPUT_TOKENS or not 1 <= args.repeats <= MAX_REPEATS:
        raise PromptLabError("call, token, and repeat limits are outside the supported bounds")
    if args.max_metric_calls < 1:
        raise PromptLabError("metric-call limit must be positive")
    if not args.model:
        raise PromptLabError("--model is required for paid commands")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise PromptLabError("OPENAI_API_KEY is required for paid commands")
    return OpenAIProvider(key, args.max_calls)


def _run_evaluate(args: RunArgs, root: Path) -> int:
    dataset_path = Path(args.dataset)
    dataset = load_dataset(dataset_path)
    cases = cast(tuple[Case, ...], getattr(dataset, args.split))
    candidate = _read_prompt(args.prompt, root)
    output_dir = Path(args.output_dir)
    new_output_dir(output_dir)
    provider = _provider(args)
    result = evaluate_candidate(
        candidate,
        cases,
        provider,
        model=args.model,
        repeats=args.repeats,
        max_calls=args.max_calls,
        max_output_tokens=args.max_output_tokens,
    )
    _ = write_json(
        output_dir / "result.json",
        {
            "dataset_sha256": sha256_hex(dataset_path.read_bytes()),
            "prompt_sha256": sha256_hex(candidate.encode()),
            "model": args.model,
            "split": args.split,
            "repeats": args.repeats,
            "max_calls": args.max_calls,
            "max_output_tokens": args.max_output_tokens,
            **result,
        },
    )
    print(json.dumps({"aggregate_score": result["aggregate_score"], "eligible": result["eligible"]}))
    return 0


def _run_optimize(args: RunArgs, root: Path) -> int:
    dataset_path = Path(args.dataset)
    dataset = load_dataset(dataset_path)
    seed = _read_prompt(args.seed_prompt, root)
    output_dir = Path(args.output_dir)
    new_output_dir(output_dir)
    provider = _provider(args)
    reflection_model = args.reflection_model or args.model
    try:
        module = import_module("gepa.optimize_anything")
        engine_config = cast(Callable[..., object], getattr(module, "EngineConfig"))
        gepa_config = cast(Callable[..., object], getattr(module, "GEPAConfig"))
        reflection_config = cast(Callable[..., object], getattr(module, "ReflectionConfig"))
        optimize_anything = cast(Callable[..., object], getattr(module, "optimize_anything"))
    except ImportError as error:
        raise PromptLabError("install requirements/prompt-lab.txt for optimization") from error
    evaluation_records: list[JsonObject] = []

    def evaluator(candidate: str, example: JsonObject) -> tuple[float, JsonObject]:
        case = next(case for case in dataset.train + dataset.validation if case.identifier == cast(str, example["id"]))
        result = evaluate_candidate(
            candidate, [case], provider, model=args.model, repeats=args.repeats,
            max_calls=args.max_calls, max_output_tokens=args.max_output_tokens,
        )
        case_results = cast(list[JsonObject], result["case_results"])
        case_result = case_results[0]
        side_info: JsonObject = {
            "case_id": case.identifier,
            "score": result["aggregate_score"],
            "eligible": result["eligible"],
            "hard_failure": case_result["hard_failure"],
            "failures": cast(list[str], case_result["failures"])[:20],
            "checkpoints": cast(list[JsonObject], case_result["checkpoints"])[:20],
        }
        evaluation_records.append({"candidate_sha256": sha256_hex(candidate.encode()), **side_info})
        return float(cast(float, result["aggregate_score"])), side_info

    def reflection(messages: str | list[Message]) -> str:
        return provider.reflect(messages, reflection_model, args.max_output_tokens)

    config = gepa_config(
        engine=engine_config(max_metric_calls=args.max_metric_calls, parallel=False),
        reflection=reflection_config(reflection_lm=reflection),
    )
    optimized = optimize_anything(
        seed_candidate=seed,
        evaluator=evaluator,
        dataset=[{"id": case.identifier} for case in dataset.train],
        valset=[{"id": case.identifier} for case in dataset.validation],
        config=config,
    )
    best = cast(str, getattr(optimized, "best_candidate"))
    best_result = evaluate_candidate(
        best,
        dataset.train + dataset.validation,
        provider,
        model=args.model,
        repeats=args.repeats,
        max_calls=args.max_calls,
        max_output_tokens=args.max_output_tokens,
    )
    if cast(bool, best_result["eligible"]):
        _ = (output_dir / "best_candidate.md").write_text(best, encoding="utf-8")
    _ = write_json(
        output_dir / "result.json",
        {
            "dataset_sha256": sha256_hex(dataset_path.read_bytes()),
            "seed_prompt_sha256": sha256_hex(seed.encode()),
            "best_prompt_sha256": sha256_hex(best.encode()),
            "model": args.model,
            "reflection_model": reflection_model,
            "timeout_seconds": 60,
            "repeats": args.repeats,
            "max_output_tokens": args.max_output_tokens,
            "max_calls": args.max_calls,
            "max_metric_calls": args.max_metric_calls,
            "calls": provider.calls,
            "usage": provider.usage,
            "evaluation_records": evaluation_records[-100:],
            "best_result": best_result,
            "exported": cast(bool, best_result["eligible"]),
        },
    )
    if not cast(bool, best_result["eligible"]):
        print("Best candidate failed mandatory checks; no candidate was exported.", file=sys.stderr)
        return 2
    print(f"Wrote {output_dir / 'best_candidate.md'}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prompt_lab.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    _ = validate.add_argument("dataset")
    for command in ("evaluate", "optimize"):
        subparser = subparsers.add_parser(command)
        _ = subparser.add_argument("--dataset", required=True)
        _ = subparser.add_argument("--model", required=True)
        _ = subparser.add_argument("--output-dir", required=True)
        _ = subparser.add_argument("--max-calls", type=int, default=64)
        _ = subparser.add_argument("--max-output-tokens", type=int, default=512)
        _ = subparser.add_argument("--repeats", type=int, default=1)
    evaluate = subparsers.choices["evaluate"]
    _ = evaluate.add_argument("--prompt", required=True)
    _ = evaluate.add_argument("--split", choices=SPLITS, default="validation")
    optimize = subparsers.choices["optimize"]
    _ = optimize.add_argument("--seed-prompt", required=True)
    _ = optimize.add_argument("--max-metric-calls", type=int, default=8)
    _ = optimize.add_argument("--reflection-model")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        command = cast(str, getattr(args, "command", ""))
        if command == "validate":
            dataset = load_dataset(Path(cast(str, getattr(args, "dataset", ""))))
            split_counts = {split: len(cast(tuple[Case, ...], getattr(dataset, split))) for split in SPLITS}
            print(json.dumps({"cases": len(dataset.cases), "splits": split_counts}))
            return 0
        run_args = _run_args(args)
        if command == "evaluate":
            return _run_evaluate(run_args, root)
        return _run_optimize(run_args, root)
    except (PromptLabError, ProviderError, BudgetExhausted) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
