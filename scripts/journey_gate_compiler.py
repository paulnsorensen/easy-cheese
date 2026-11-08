#!/usr/bin/env python3
"""Compile the journey-gate sources into the autoimprove contracts.

Each `skills/<skill>/evals/autoimprove.json` carries the gate program inline in
`kinds.journey.argv`, because hand-written Python never lives under `skills/`.
The program is `scripts/journey_gates/common.py` followed by
`scripts/journey_gates/<skill>.py`, minus the `gate:strip` blocks.

Usage: journey_gate_compiler.py [--check] [--root PATH]
"""

# pyright: reportAny=false, reportUnusedCallResult=false
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STRIP = re.compile(
    r"^# gate:strip-begin\n.*?^# gate:strip-end\n", re.DOTALL | re.MULTILINE
)
DEFAULT_ROOT = Path(__file__).resolve().parents[1]


class SourceError(Exception):
    """A gate source file the compiler cannot strip safely."""


def stripped(path: Path) -> str:
    text = path.read_bytes().decode("utf-8")
    if "\r" in text:
        raise SourceError(f"{path.name}: CRLF line endings; use LF")
    begins = len(re.findall(r"^# gate:strip-begin$", text, re.MULTILINE))
    ends = len(re.findall(r"^# gate:strip-end$", text, re.MULTILINE))
    pairs = len(STRIP.findall(text))
    if begins != ends or pairs != begins:
        raise SourceError(
            f"{path.name}: unpaired gate:strip markers ({begins} begin, {ends} end)"
        )
    return STRIP.sub("", text)


def skills(root: Path) -> list[str]:
    """Every skill with a gate source: `scripts/journey_gates/*.py` minus common."""
    gates = root / "scripts" / "journey_gates"
    return sorted(p.stem for p in gates.glob("*.py") if p.stem != "common")


def compiled_source(root: Path, skill: str) -> str:
    gates = root / "scripts" / "journey_gates"
    parts = [stripped(gates / name) for name in ("common.py", f"{skill}.py")]
    return "\n\n".join(part.strip("\n") for part in parts) + "\n"


def contract_path(root: Path, skill: str) -> Path:
    return root / "skills" / skill / "evals" / "autoimprove.json"


def rendered_contract(root: Path, skill: str) -> str:
    contract = json.loads(contract_path(root, skill).read_text(encoding="utf-8"))
    contract["kinds"]["journey"]["argv"] = [
        "python3",
        "-I",
        "-c",
        compiled_source(root, skill),
    ]
    return json.dumps(contract, indent=2) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="exit 1 when a contract drifts"
    )
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="repository root"
    )
    args = parser.parse_args(argv)
    drifted: list[str] = []
    for skill in skills(args.root):
        path = contract_path(args.root, skill)
        try:
            wanted = rendered_contract(args.root, skill)
        except SourceError as error:
            print(f"journey gate source error: {error}", file=sys.stderr)
            return 2
        if path.read_text(encoding="utf-8") == wanted:
            continue
        drifted.append(skill)
        if not args.check:
            path.write_text(wanted, encoding="utf-8")
    if args.check and drifted:
        print(
            "journey gate drift: "
            + ", ".join(drifted)
            + " (run scripts/journey_gate_compiler.py)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
