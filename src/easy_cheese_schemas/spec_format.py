"""Acceptance policy for the mold spec format, shared by every release channel.

The hardened spec format — the ``## Test Contracts`` table, the ``## Grounding``
table, and the ``gate_applicability`` frontmatter block — postdates v0.13, and
this package did
not exist then. v0.13-era specs already sitting in ``.cheese/specs/`` must stay
readable forever, so a *read* asks for a policy and gets a lenient one for them,
while every *mint or rewrite* asks for the strict policy and never gets anything
else. Legacy is a read-side grace, never a write-side option.

Legacy detection keys on Mold's provenance marker — the frontmatter ``source``
field — the same discriminator the taste gate already trusts. A spec carrying no
frontmatter at all is malformed, not legacy, and stays rejected.

This module is deliberately stdlib-only so the bundled validators can consume it
without reaching for the attrs-backed model stack.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Frontmatter ``source`` values that mark a spec as minted by a hardened Mold
# production path. Anything else — including an absent marker — reads as v0.13.
_HARDENED_SOURCES = frozenset({"agent-mini-spec", "mold-handshake"})

# The parts of the document the hardened format added after v0.13. Their
# *presence* is waived for a legacy spec; their *content*, when a legacy spec
# happens to carry it, is validated exactly as it is for a hardened one.
_POST_V013_SECTIONS = frozenset({"Test Contracts", "Grounding"})

_MINI_SPEC_REQUIRED_SECTIONS = frozenset(
    {"Contract", "Acceptance", "Test Contracts", "Non-goals"}
)

_LEGACY_NOTICE = (
    "NOTICE: legacy-spec-format this spec predates the current format "
    "(no mold provenance marker, so Test Contracts, Grounding and "
    "gate_applicability are not required); accepted on read — re-mint it with "
    "/mold to adopt them"
)


@dataclass(frozen=True)
class SpecFormatPolicy:
    """What one spec reader must enforce for one spec.

    Callers ask the policy questions; they never inspect how legacy was
    detected or which rules a legacy spec is excused from.
    """

    legacy: bool
    _source: str | None

    def requires_section(
        self, section_name: str, *, default_required: bool
    ) -> bool:
        """Whether a missing ``section_name`` heading is an error."""
        if self._source == "agent-mini-spec":
            return section_name in _MINI_SPEC_REQUIRED_SECTIONS
        required = default_required or section_name == "Test Contracts"
        return required and not (
            self.legacy and section_name in _POST_V013_SECTIONS
        )

    def requires_gate_applicability(self) -> bool:
        """Whether absent ``gate_applicability`` frontmatter is an error."""
        return not self.legacy

    @property
    def notice(self) -> str | None:
        """One-line, non-fatal notice to surface when a legacy spec is read."""
        return _LEGACY_NOTICE if self.legacy else None


def spec_format_policy(
    frontmatter: Mapping[str, object], *, strict: bool
) -> SpecFormatPolicy:
    """Resolve the policy for a spec whose frontmatter parsed to ``frontmatter``.

    ``strict=True`` is the mint/rewrite posture: the current hardened format,
    unconditionally. ``strict=False`` is the read posture, which accepts a
    v0.13-era spec and reports it through :attr:`SpecFormatPolicy.notice`.
    """
    source = frontmatter.get("source")
    normalized_source = source if isinstance(source, str) else None
    if strict or not frontmatter or source is not None and normalized_source is None:
        return SpecFormatPolicy(legacy=False, _source=normalized_source)
    return SpecFormatPolicy(
        legacy=source not in _HARDENED_SOURCES, _source=normalized_source
    )


def is_hardened_provenance(frontmatter: Mapping[str, object]) -> bool:
    """Whether frontmatter carries a hardened Mold provenance marker.

    Mint paths require this: a spec written without the marker would be read
    back as legacy forever, which is exactly the grace the write side refuses.
    """
    source = frontmatter.get("source")
    return isinstance(source, str) and source in _HARDENED_SOURCES
