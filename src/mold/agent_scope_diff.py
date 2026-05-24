#!/usr/bin/env python3
"""Diff agent-introduced nouns: words proposed in a transcript but absent from the spec.

Replaces the LLM-judged "are any distinguishing nouns in this draft *not* in
the user's prior turns?" sweep at the top of /mold's Curdle approval gate.
Forces a deterministic verdict so the gate cannot silently ratify an
agent-introduced feature.

Inputs are two file paths:

    --spec        Path to the user-grounded ask (typically the original prompt
                  captured before drafting, or the prior approved spec).
    --transcript  Path to the agent's proposed draft (Approach / Decisions /
                  Interface sketches block).

Output (JSON list on stdout): every alphanumeric word that appears in the
transcript but not in the spec, lowercased, deduplicated, and stripped of
stopwords + bare numerics. Words are compared after normalising case and
collapsing internal hyphens — `retry-loop` matches `Retry-Loop`.

Exit codes:

    0   normal verdict (whether the list is empty or not).
    2   --spec or --transcript path is missing / unreadable.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import cli  # noqa: E402

# Filler words that show up in prose but never carry scope meaning. Kept
# small on purpose — the goal is to keep `tail`-like content words, not to
# build a full English stopword list.
STOPWORDS = frozenset(
    {
        "a", "an", "and", "any", "are", "as", "at",
        "be", "been", "being", "but", "by",
        "can", "could",
        "do", "does", "doing",
        "for", "from",
        "had", "has", "have", "having", "he", "her", "here", "him", "his", "how",
        "i", "if", "in", "into", "is", "it", "its",
        "just",
        "may", "might", "must",
        "no", "not", "now",
        "of", "on", "only", "or", "other", "our", "out", "over",
        "should", "so", "some", "still", "such",
        "than", "that", "the", "their", "them", "then", "there", "these", "they",
        "this", "those", "to",
        "up", "us",
        "very",
        "was", "we", "well", "were", "what", "when", "where", "which", "while",
        "who", "why", "will", "with", "would",
        "you", "your",
    }
)

# Word: identifier-shaped tokens (letters/digits/_/-). Hyphens are kept so
# `retry-loop` stays one noun, not two.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def _normalise(token: str) -> str:
    return token.lower().strip("-_")


def _tokens(text: str) -> set[str]:
    """Lowercased word set with stopwords + pure-numeric tokens removed."""
    out: set[str] = set()
    for match in _WORD_RE.finditer(text):
        word = _normalise(match.group(0))
        if not word or word in STOPWORDS:
            continue
        if word.isdigit():
            continue
        out.add(word)
    return out


def _read_text(path: Path, label: str) -> str:
    if not path.exists():
        raise cli.CliError(f"--{label} not found: {path}")
    if not path.is_file():
        raise cli.CliError(f"--{label} is not a file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise cli.CliError(f"--{label} unreadable: {exc}") from exc


def diff(spec_text: str, transcript_text: str) -> list[str]:
    """Return sorted list of nouns in transcript but not in spec."""
    spec_words = _tokens(spec_text)
    transcript_words = _tokens(transcript_text)
    return sorted(transcript_words - spec_words)


def _cmd_diff(args: argparse.Namespace) -> None:
    spec_path = Path(args.spec)
    transcript_path = Path(args.transcript)
    spec_text = _read_text(spec_path, "spec")
    transcript_text = _read_text(transcript_path, "transcript")
    introduced = diff(spec_text, transcript_text)
    cli.emit(
        {
            "spec": str(spec_path),
            "transcript": str(transcript_path),
            "agent_introduced": introduced,
            "count": len(introduced),
        },
        json_mode=True,
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Diff agent-introduced nouns against the user's spec."
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to the user-grounded spec / prompt (the vocabulary baseline).",
    )
    parser.add_argument(
        "--transcript",
        required=True,
        help="Path to the agent's proposed draft to check for scope creep.",
    )
    parser.set_defaults(func=_cmd_diff)


if __name__ == "__main__":
    cli.run(_setup)
