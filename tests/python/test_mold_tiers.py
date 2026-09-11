"""Contract guard for mold's tiered routing — ceremony scaled to the job.

`/mold` used to have one user-facing shape: the full Explore → … → two-key
handshake ceremony, with the mini-spec reachable only from `/cheese`'s tier-1
escalation. A small, clear ask typed as `/mold` paid the whole bill. The tiers
reference makes the Bounds pass pick Quick / Light / Full, pins what each tier
may skip, and pins what no tier may skip. These tests keep the three files
that state the contract (`SKILL.md`, `tiers.md`, `modes.md`) from drifting
apart.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOLD = REPO_ROOT / "skills" / "mold"
SKILL = MOLD / "SKILL.md"
TIERS = MOLD / "references" / "tiers.md"
MODES = MOLD / "references" / "modes.md"
MINI_SPEC = MOLD / "references" / "mini-spec-mode.md"


def _section(text: str, heading: str) -> str:
    """Body of the markdown section titled ``heading`` up to the next heading
    of the same or a higher level."""
    match = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert match, f"section {heading!r} missing"
    level = len(match.group(1))
    rest = text[match.end() :]
    stop = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: stop.start()] if stop else rest


def _table_rows(text: str, first_header: str) -> list[list[str]]:
    lines = text.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith(f"| {first_header} |")
    )
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
    return rows


def _flow_step(n: int) -> str:
    flow = _section(SKILL.read_text(encoding="utf-8"), "Flow")
    step = re.search(rf"^{n}\. \*\*(.*?)(?=^\d+\. \*\*|\Z)", flow, re.M | re.S)
    assert step, f"Flow step {n} missing"
    return step.group(0)


def test_bounds_pass_picks_the_tier_and_never_downgrades_silently() -> None:
    step1 = _flow_step(1)
    assert "references/tiers.md" in step1, "Bounds pass must link the tier contract"
    assert "Quick exits here" in step1
    assert re.search(r"never downgrade silently", step1, re.I), (
        "tier changes must be announced upgrades; a silent downgrade drops gates"
    )


def test_three_tiers_each_name_entry_runs_skips_and_handoff() -> None:
    rows = _table_rows(TIERS.read_text(encoding="utf-8"), "Tier")
    names = [re.sub(r"\W", "", row[0]).lower() for row in rows]
    assert names == ["quick", "light", "full"], names
    for row in rows:
        assert len(row) == 5 and all(row), f"tier row incomplete: {row}"
    quick, light, full = rows
    assert "Standalone fast-path" in quick[1], "Quick reuses Cook's clarity check"
    assert "mini-spec" in quick[4] and "/cook --auto <spec-path>" in quick[4]
    assert "validate-spec --strict" in quick[4], "Quick still validates its spec"
    assert "two-key handshake" in light[2] and "fork taste test" in light[2], (
        "Light skips dialogue, not the coherence gates"
    )
    assert "typed planner" in light[3], "a single curd needs no CurdPlan"
    assert full[2] == "The whole Flow" and full[3] == "Nothing"


def test_no_tier_skips_the_invariant_gates() -> None:
    section = _section(TIERS.read_text(encoding="utf-8"), "What no tier skips").lower()
    for gate in (
        "grounding-recorded",
        "agent-introduced-scope",
        "validate-spec --strict",
        "consequential fork",
    ):
        assert gate in section, f"{gate!r} left the never-skip list"


def test_quick_tier_reuses_mini_spec_mode_with_one_confirm() -> None:
    mini = _section(SKILL.read_text(encoding="utf-8"), "Agent-invoked mini-spec mode")
    assert "Quick tier" in mini and "one confirm" in mini
    tiers = TIERS.read_text(encoding="utf-8")
    assert "[`mini-spec-mode.md`](mini-spec-mode.md)" in tiers
    assert MINI_SPEC.exists()
    assert "one confirm" in _section(tiers, "Relationship to `/cheese`")


def test_light_single_curd_skips_the_planner_not_the_handshake() -> None:
    step5 = _flow_step(5)
    assert "Light with one expected curd" in step5 and "no planner" in step5
    assert "/cook --auto <spec-path>" in step5
    assert "taste-test" in step5.split("Light with one expected curd")[0], (
        "the taste test runs before the Light shortcut, so Light cannot skip it"
    )
    assert "6. **Two-key handshake**" in _flow_step(6)


def test_upgrade_rules_and_user_knobs() -> None:
    tiers = TIERS.read_text(encoding="utf-8")
    upgrade = _section(tiers, "Upgrade rules")
    assert "Downgrade only on the user's knob" in upgrade
    assert "`high` or `[?]`" in upgrade and "Grill mandatory" in upgrade
    assert "reaches two" in upgrade and "typed planner" in upgrade
    knobs = _section(MODES.read_text(encoding="utf-8"), "User knobs (free-form interrupts)")
    for knob in ("`quick`", "`light`", "`full`"):
        assert knob in knobs, f"tier knob {knob} missing from modes.md"
