"""Pick the Mold tier from the Bounds-pass facts.

The rows of `skills/mold/references/tiers.md` decide the tier. The agent supplies
the facts: fired leverage triggers, the shape-check verdict, and the fork, curd,
and seam counts. A fired trigger never lands in Quick.
"""

from __future__ import annotations

from typing import Literal

import fromargs

Trigger = Literal[
    "auth",
    "irreversible",
    "concurrency",
    "contract",
    "destructive",
    "new-slice",
    "cross-slice-dep",
    "invariant-gap",
]
Verdict = Literal["low", "medium", "high", "unknown", "skipped"]


def pick_tier(
    triggers: list[Trigger],
    verdict: Verdict,
    forks: int,
    curds: int,
    public_seam: bool,
    diagnose: bool,
) -> tuple[str, list[str]]:
    """Return the tier and the reasons that set it."""
    full = [
        reason
        for hit, reason in (
            (verdict in ("high", "unknown"), f"shape-check verdict {verdict}"),
            (forks >= 3, f"{forks} consequential forks"),
            (curds >= 2, f"{curds} expected curds"),
            (public_seam, "new cross-module public seam"),
            (diagnose, "Diagnose input"),
        )
        if hit
    ]
    if full:
        return "full", full
    light = [f"fired leverage trigger: {t}" for t in dict.fromkeys(triggers)]
    if forks:
        light.append(f"{forks} consequential fork{'s' if forks > 1 else ''}")
    if verdict == "medium":
        light.append("shape-check verdict medium")
    if light:
        return "light", light
    return "quick", ["no fired trigger, verdict " + verdict + ", no open fork"]


def tier_cmd(
    *,
    verdict: Verdict,
    trigger: list[Trigger] | None = None,
    forks: int = 0,
    curds: int = 1,
    public_seam: bool = False,
    diagnose: bool = False,
) -> dict[str, object]:
    """Pick the Mold tier from the Bounds-pass facts.

    Parameters
    ----------
    verdict
        Shape-check verdict; `unknown` stands for `[?]`, `skipped` for a greenfield or single private function.
    trigger
        One fired leverage trigger id; repeat the flag for each.
    forks
        Consequential forks open after the Bounds pass.
    curds
        Expected curd count.
    public_seam
        A new public seam crosses modules.
    diagnose
        The input is a symptom, failure, or trace.
    """
    if forks < 0 or curds < 0:
        raise fromargs.CliError("forks and curds must be zero or more")
    tier, reasons = pick_tier(trigger or [], verdict, forks, curds, public_seam, diagnose)
    return {"tier": tier, "reasons": reasons, "line": f"tier: {tier} ({'; '.join(reasons)})"}


def build_app() -> fromargs.App:
    return fromargs.App(
        "tier",
        help=(__doc__ or "").splitlines()[0],
        help_formatter="plain",
        default_command=tier_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)
