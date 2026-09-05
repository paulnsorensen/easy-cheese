"""The host's session transcripts, read for the user's own words (L3, AC-27/28).

A transcript is one JSON object per line under `~/.claude/projects/<encoded cwd>/`.
Only `type: user` entries whose content is text are the user's turns; host
wrappers inside a turn are stripped, tool results and skill preambles are not
turns at all. The layout is the host's, not ours, so the caller can always pass
an explicit path instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

_PROJECTS_DIR = Path(".claude") / "projects"
_NOT_PATH_CHAR = re.compile(r"[^A-Za-z0-9]")
SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
# Host wrappers that ride inside a user turn but are not the user's words.
_WRAPPER_TAGS = (
    "system-reminder",
    "task-notification",
    "local-command-caveat",
    "local-command-stdout",
    "command-name",
    "command-message",
    "command-args",
)
_WRAPPER_RE = re.compile(
    r"<(?P<tag>" + "|".join(_WRAPPER_TAGS) + r")\b[^>]*>.*?</(?P=tag)>|<(?:"
    + "|".join(_WRAPPER_TAGS)
    + r")\b[^>]*/?>",
    re.S,
)


def projects_dir(cwd: Path) -> Path:
    """The host's transcript directory for `cwd`: every non-alphanumeric becomes `-`."""
    return Path.home() / _PROJECTS_DIR / _NOT_PATH_CHAR.sub("-", str(cwd))


def _turn_text(content: object) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in cast(list[object], content):
            if not isinstance(item, dict):
                continue
            block = cast(dict[str, object], item)
            text = block.get("text")
            if block.get("type") == "text" and isinstance(text, str):
                parts.append(text)
        return "\n".join(parts) if parts else None
    return None


def user_turns(path: Path) -> tuple[list[dict[str, str]], int]:
    """The user's turns, plus how many lines were not readable JSON.

    A live transcript is still being appended to, so its last line is often a
    partial record; the count makes that loss visible instead of silent.
    """
    turns: list[dict[str, str]] = []
    skipped = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                entry = cast(object, json.loads(line))
            except ValueError:
                skipped += 1
                continue
            if not isinstance(entry, dict):
                continue
            entry_map = cast(dict[str, object], entry)
            if entry_map.get("type") != "user":
                continue
            message = entry_map.get("message")
            content = (
                cast(dict[str, object], message).get("content") if isinstance(message, dict) else None
            )
            text = _turn_text(content)
            if text is None:
                continue
            # Host wrappers, tool results, and skill preambles are not the user's
            # words: strip the wrappers and keep whatever the user typed around them.
            stripped = _WRAPPER_RE.sub("", text).strip()
            if not stripped or "Base directory for this skill" in stripped:
                continue
            turns.append({"timestamp": str(entry_map.get("timestamp", "")), "text": stripped})
    return turns, skipped
