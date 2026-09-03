"""Contract tests for issue #550 — a terminal routing boundary for `/cheese`.

The measured 31.7-minute "cheese episode" was downstream work charged to the
router because no event said where routing ended. The receipt is that event, so
these tests pin the properties that make it measurable and keep it from growing
into an artifact:

1. **Emitted on every route, last, including `clarify`** — skipping "obvious"
   routes is what produced the unattributable sample.
2. **No duration and no timestamp** — the router cannot measure wall-clock time,
   so the boundary is the line's own position and the host derives the span.
3. **Not an artifact** — one line of ordinary output, not a schema, a `.cheese/`
   file, or a handoff field with authority over the pipeline.
4. **A countable probe budget and a zero-probe fast path** — with Culture
   escalation preserved for genuinely ambiguous input.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "cheese"
CHEESE = SKILL_DIR / "SKILL.md"
RECEIPT = SKILL_DIR / "references" / "routing-receipt.md"

RECEIPT_LINE = "route: intent=<intent> target=<skill> path=<fast|escalated> probes=<n>"


def _assert_in_order(body: str, *phrases: str) -> None:
    folded = body.casefold()
    last = -1
    for phrase in phrases:
        idx = folded.find(phrase.casefold())
        assert idx != -1, f"missing phrase: {phrase!r}"
        assert idx > last, f"phrase out of order: {phrase!r}"
        last = idx


def _output_section() -> str:
    text = CHEESE.read_text(encoding="utf-8")
    start = text.index("\n## Output\n") + 1
    end = text.find("\n## ", start + len("## Output"))
    return text[start:] if end == -1 else text[start:end]


def test_skill_output_ends_with_the_receipt_then_dispatch() -> None:
    # Property 1: the receipt is the LAST thing before dispatch, so its position
    # in the transcript is the routing boundary.
    _assert_in_order(
        _output_section(),
        "**routing receipt**",
        "the last line before dispatch, always emitted",
        RECEIPT_LINE,
        "terminal routing boundary",
        "then dispatch in the same turn",
    )


def test_clarify_still_prints_a_receipt() -> None:
    _assert_in_order(
        _output_section(),
        "replace the dispatch with the single clarifying question",
        "the receipt still prints, with `target=clarify`",
    )


def test_receipt_carries_no_self_measured_time() -> None:
    # Property 2: pinned with the reason, so a later edit cannot "helpfully" add
    # a duration field back.
    _assert_in_order(
        _output_section(),
        RECEIPT_LINE,
        "never put a duration or a timestamp in it",
    )
    _assert_in_order(
        RECEIPT.read_text(encoding="utf-8"),
        "never a duration and never a timestamp",
        "the router cannot measure wall-clock time",
        "analytics take the boundary from when this line was emitted",
    )


def test_receipt_is_not_a_new_artifact_or_authority() -> None:
    # Property 3 plus the portability requirement: plain text, no harness
    # capability, no `.cheese/` write, no control over what runs.
    _assert_in_order(
        RECEIPT.read_text(encoding="utf-8"),
        "never a new artifact",
        "not written to `.cheese/`, not a schema, not a handoff field",
        "carries no authority over the pipeline",
        "portable by construction",
        "no harness capability is required",
        "optional to consume, mandatory to emit",
    )


def test_the_four_receipt_fields_are_defined() -> None:
    text = RECEIPT.read_text(encoding="utf-8")
    for field in ("`intent`", "`target`", "`path`", "`probes`"):
        assert f"| {field} |" in text, f"receipt field row missing: {field}"
    _assert_in_order(text, "`fast` when the route spent zero evidence probes")


def test_probe_budget_is_countable_and_bounded_in_the_skill() -> None:
    # Property 4: "keep it light" was unmeasurable; the budget is an integer and
    # overspending routes the work to a skill whose measurement includes it.
    _assert_in_order(
        CHEESE.read_text(encoding="utf-8"),
        "one evidence probe is one file read, one search call, one `gh` call",
        "the router spends at most three",
        "the fast path spends zero",
    )
    _assert_in_order(
        RECEIPT.read_text(encoding="utf-8"),
        "the router's budget is **three**",
        "exceeding three is a routing signal",
        "escalate to `/culture` or `/briesearch`",
        "under a skill whose measurement is supposed to include them",
    )


def test_fast_path_conditions_are_enumerated_and_spend_no_probes() -> None:
    _assert_in_order(
        RECEIPT.read_text(encoding="utf-8"),
        "## the fast path",
        "with **zero** probes",
        "an explicit skill command",
        "a resolvable durable pointer",
        "a bounded implementation request",
        "no repository exploration",
        "`path=fast probes=0`",
    )


def test_fast_path_never_removes_culture_escalation_or_adds_approval() -> None:
    # The issue's non-goals: ambiguity keeps its Culture reasoning, and an
    # already-unambiguous route gains no new user gate.
    _assert_in_order(
        RECEIPT.read_text(encoding="utf-8"),
        "everything else is `escalated`, and stays escalated",
        "genuinely ambiguous input still gets `/culture` reasoning",
        "never removes a tier from unclear ones",
        "never adds an approval step to a route that was already unambiguous",
    )
