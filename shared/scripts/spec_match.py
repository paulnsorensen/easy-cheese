"""Deterministic keyword-match scoring for existing-artifact reuse scans.

Shared by the two /cheese glob+score checks that look for a candidate
markdown artifact matching an incoming request: spec-discovery
(.cheese/specs/*.md) and rejected-directions (.cheese/.out-of-scope/*.md).
Both scans have the identical shape -- glob candidates, score against a few
text fields, act on the top score -- so the scoring itself lives once here.

Stdlib only (difflib.SequenceMatcher); no interactive picker.
"""

from __future__ import annotations

import difflib

# Score threshold for a 'high' tier match, and the minimum margin over the
# second-best candidate required to call it unambiguous. Tunable -- see the
# call sites in skills/cheese/SKILL.md for how each tier is acted on.
HIGH_SCORE_THRESHOLD = 0.60
HIGH_MARGIN_THRESHOLD = 0.15


def _field_score(request_text: str, candidate: dict) -> float:
    """Max SequenceMatcher ratio of request_text against slug/title/first_heading."""
    fields = (
        candidate.get("slug") or "",
        candidate.get("title") or "",
        candidate.get("first_heading") or "",
    )
    return max(
        difflib.SequenceMatcher(None, request_text, field).ratio() for field in fields
    )


def score_candidates(request_text: str, candidates: list[dict]) -> list[dict]:
    """Rank candidates against request_text; return [{path, score, tier}] desc by score.

    Each candidate carries {slug, title, first_heading, path}. Tier is 'high'
    when the top score >= HIGH_SCORE_THRESHOLD *and* its margin over the
    second-best score >= HIGH_MARGIN_THRESHOLD; every other candidate (and the
    top one when either condition fails) is 'weak'. An empty candidate list
    returns an empty result.
    """
    scored = [
        {"path": c["path"], "raw": _field_score(request_text, c)}
        for c in candidates
    ]
    scored.sort(key=lambda r: (-r["raw"], r["path"]))
    if not scored:
        return []
    top = scored[0]["raw"]
    margin = top - (scored[1]["raw"] if len(scored) > 1 else 0.0)
    top_is_high = top >= HIGH_SCORE_THRESHOLD and margin >= HIGH_MARGIN_THRESHOLD
    results = []
    for i, r in enumerate(scored):
        tier = "high" if (i == 0 and top_is_high) else "weak"
        results.append({"path": r["path"], "score": round(r["raw"], 3), "tier": tier})
    return results
