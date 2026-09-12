"""Bucket a captured review report's findings against a case's expected defect.

Each finding is classified by an LLM judge transport as exactly one of
"Bug Hit", "Valid Suggestion", or "Noise", then tallied into recall,
precision, and a signal-to-noise ratio. The transport is swappable: tests
inject a recorded transport (a canned sequence of responses) so the harness
never makes a live LLM call in CI.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from easy_cheese.shared import cli
from easy_cheese.shared.findings import Finding, parse_findings_report
from easy_cheese.skills.age_bench.cases import Case, load_case

JudgeTransport = Callable[[str], str]

BUCKETS: tuple[str, ...] = ("Bug Hit", "Valid Suggestion", "Noise")


class JudgeTransportUnavailableError(Exception):
    """Raised by the default transport: curd/3 wires no live LLM call."""


class JudgeTransportError(Exception):
    """Raised when a transport response can't be classified, or is exhausted."""


def default_transport(_prompt: str) -> str:
    raise JudgeTransportUnavailableError(
        "no live LLM transport is wired in age-bench; pass --transport-fixture"
    )


def recorded_transport(fixture_path: Path) -> JudgeTransport:
    responses: list[str] = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    pending: Iterator[str] = iter(responses)

    def _transport(_prompt: str) -> str:
        try:
            return next(pending)
        except StopIteration as exc:
            raise JudgeTransportError("recorded transport fixture exhausted") from exc

    return _transport


def _bucket_prompt(case: Case, finding: Finding) -> str:
    return (
        f"Case overlap area: {case.overlap_area}\n"
        f"Expected defect: {case.description} ({case.defect_file}:{case.defect_line})\n"
        f"Finding [{finding.dimension}:{finding.severity}] at {finding.location}: "
        f"{finding.summary}\n"
        f"Classify this finding as exactly one of: {', '.join(BUCKETS)}."
    )


def _bucket_of(response: str) -> str:
    lowered = response.lower()
    for bucket in BUCKETS:
        if bucket.lower() in lowered:
            return bucket
    raise JudgeTransportError(f"transport response did not name a bucket: {response!r}")


@dataclass(frozen=True)
class JudgeResult:
    case_id: str
    tool: str
    hits: int
    suggestions: int
    noise: int
    buckets: list[str]
    recall: float
    precision: float
    snr: float

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "tool": self.tool,
            "hits": self.hits,
            "suggestions": self.suggestions,
            "noise": self.noise,
            "buckets": self.buckets,
            "recall": self.recall,
            "precision": self.precision,
            "snr": self.snr,
        }


def judge_report(
    *,
    tool: str,
    case_id: str,
    report_text: str,
    transport: JudgeTransport = default_transport,
    repo_root: Path | str | None = None,
) -> JudgeResult:
    case = load_case(case_id, repo_root=repo_root)
    findings = parse_findings_report(report_text)
    buckets = [_bucket_of(transport(_bucket_prompt(case, finding))) for finding in findings]
    hits = buckets.count("Bug Hit")
    suggestions = buckets.count("Valid Suggestion")
    noise = buckets.count("Noise")
    recall = 1.0 if hits else 0.0
    precision = hits / len(findings) if findings else 0.0
    snr = hits / noise if noise else float(hits)
    return JudgeResult(
        case_id=case_id,
        tool=tool,
        hits=hits,
        suggestions=suggestions,
        noise=noise,
        buckets=buckets,
        recall=recall,
        precision=precision,
        snr=snr,
    )


def _cmd_judge(args: argparse.Namespace) -> int:
    report_text = Path(args.report).read_text(encoding="utf-8")
    transport: JudgeTransport = (
        recorded_transport(Path(args.transport_fixture))
        if args.transport_fixture
        else default_transport
    )
    try:
        result = judge_report(
            tool=args.tool,
            case_id=args.case_id,
            report_text=report_text,
            transport=transport,
            repo_root=args.repo_root,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a CliError below
        raise cli.CliError(str(exc)) from exc
    print(json.dumps(result.to_dict()), file=args.stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("--tool", required=True, choices=("age", "code-review"))
    _ = parser.add_argument("--case", dest="case_id", required=True)
    _ = parser.add_argument("--report", required=True)
    _ = parser.add_argument("--transport-fixture", dest="transport_fixture", default=None)
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.set_defaults(func=_cmd_judge)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
