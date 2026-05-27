#!/usr/bin/env python3
"""Generate categorized release notes from main's git history.

`gh release create --generate-notes` is useless here: the release workflow
force-retargets each version tag onto a single-commit orphan `release`-branch
snapshot (so `gh skill install` can read the built .pyz from the tag tree).
That orphan has no main history, so GitHub has nothing to diff and emits empty
notes.

Instead we walk main directly. The previous version tag records its main commit
in its subject (`release: vX.Y.Z from main@<sha>`); we recover that, then group
`git log <prev_source>..<curr_source>` by conventional-commit type.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# type/scope: description (optional ! before the colon marks a breaking change)
_CONVENTIONAL = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$"
)
_PR_SUFFIX = re.compile(r"\s*\(#(?P<num>\d+)\)\s*$")
_SOURCE_SHA = re.compile(r"main@(?P<sha>[0-9a-f]{7,40})")
_SEMVER = re.compile(r"^v(?P<maj>\d+)\.(?P<min>\d+)\.(?P<patch>\d+)")

# Conventional type -> section heading, in render order.
_SECTIONS = [
    ("breaking", "Breaking changes"),
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("docs", "Documentation"),
    ("deps", "Dependencies"),
    ("maint", "Maintenance"),
    ("other", "Other"),
]
_MAINT_TYPES = {"chore", "build", "ci", "refactor", "test", "style", "revert"}


def _git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _semver_key(tag: str) -> tuple[int, int, int] | None:
    m = _SEMVER.match(tag)
    if not m:
        return None
    return int(m["maj"]), int(m["min"]), int(m["patch"])


def find_previous_tag(tag: str, cwd: str | None = None) -> str | None:
    """The version tag with the highest semver strictly below `tag`."""
    current = _semver_key(tag)
    if current is None:
        return None
    candidates = []
    for line in _git("tag", "--list", "v[0-9]*", cwd=cwd).splitlines():
        key = _semver_key(line.strip())
        if key is not None and key < current:
            candidates.append((key, line.strip()))
    if not candidates:
        return None
    return max(candidates)[1]


def resolve_source_sha(ref: str, cwd: str | None = None) -> str:
    """Recover the main commit a release tag was built from.

    Tags from the orphan-retarget era carry `release: vX from main@<sha>` in
    their subject. Older tags point straight at a main commit, so the ref itself
    is the source.
    """
    subject = _git("log", "-1", "--format=%s", ref, cwd=cwd)
    m = _SOURCE_SHA.search(subject)
    return m["sha"] if m else ref


def collect_commits(from_ref: str | None, to_ref: str, cwd: str | None = None) -> list[str]:
    rng = to_ref if from_ref is None else f"{from_ref}..{to_ref}"
    out = _git("log", "--no-merges", "--format=%s", rng, cwd=cwd)
    return [line for line in out.splitlines() if line.strip()]


def _classify(subject: str) -> tuple[str, str, str | None]:
    """(section_key, cleaned_description, pr_number)."""
    pr = None
    pr_match = _PR_SUFFIX.search(subject)
    if pr_match:
        pr = pr_match["num"]
        subject = subject[: pr_match.start()].rstrip()

    m = _CONVENTIONAL.match(subject)
    if not m:
        return "other", subject, pr

    ctype, scope, bang, desc = m["type"], m["scope"] or "", m["bang"], m["desc"]
    if bang:
        return "breaking", desc, pr
    if (ctype in {"chore", "build"} and "deps" in scope) or desc.lower().startswith("bump "):
        return "deps", desc, pr
    if ctype in {"feat", "fix", "perf", "docs"}:
        return ctype, desc, pr
    if ctype in _MAINT_TYPES:
        return "maint", desc, pr
    return "other", desc, pr


def _bullet(desc: str, pr: str | None) -> str:
    desc = desc[0].upper() + desc[1:] if desc else desc
    return f"- {desc} (#{pr})" if pr else f"- {desc}"


def categorize(subjects: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {key: [] for key, _ in _SECTIONS}
    for subject in subjects:
        key, desc, pr = _classify(subject)
        buckets[key].append(_bullet(desc, pr))
    return buckets


def render(
    tag: str,
    subjects: list[str],
    repo: str,
    prev_source: str | None,
    to_sha: str,
) -> str:
    buckets = categorize(subjects)
    lines: list[str] = ["## What's Changed", ""]
    for key, heading in _SECTIONS:
        if buckets[key]:
            lines.append(f"### {heading}")
            lines.extend(buckets[key])
            lines.append("")
    if len(lines) == 2:  # nothing categorized
        lines.append("_No notable changes._")
        lines.append("")
    if prev_source:
        link = f"https://github.com/{repo}/compare/{prev_source}...{to_sha}"
        lines.append(f"**Full Changelog**: {link}")
    return "\n".join(lines).rstrip() + "\n"


def generate(tag: str, to_sha: str, repo: str, cwd: str | None = None) -> str:
    prev_tag = find_previous_tag(tag, cwd=cwd)
    prev_source = resolve_source_sha(prev_tag, cwd=cwd) if prev_tag else None
    subjects = collect_commits(prev_source, to_sha, cwd=cwd)
    return render(tag, subjects, repo, prev_source, to_sha)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="version tag being released, e.g. v0.5.3")
    parser.add_argument("--to", default="HEAD", help="end of the commit range (the main SHA)")
    parser.add_argument("--repo", required=True, help="owner/repo for the changelog link")
    args = parser.parse_args()
    sys.stdout.write(generate(args.tag, args.to, args.repo))


if __name__ == "__main__":
    main()
