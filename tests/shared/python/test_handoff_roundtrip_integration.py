"""Cross-script integration tests for the handoff seam.

The skill-scripts spec wires together three scripts that the SKILL.md prose
for /cook, /press, /age, /cure invokes in sequence:

    slugify.py from-task → emits {slug, path}
    write_handoff_artifact.py --slug <slug> --next <phase> → writes .cheese/<next>/<slug>.md
    read_handoff_slug.py --phase <phase> --slug <slug> → parses the same artifact

Per-script unit tests cover each piece in isolation, but never exercise the
seam where one script's output flows into the next via subprocess. These
hardening tests catch drift at the seam — e.g. a slug shape that slugify
accepts but write_handoff rejects, or a preamble shape write emits that
read cannot parse back. The contract is the four-line preamble (status,
next, artifact, orientation) plus the on-disk path `.cheese/<next>/<slug>.md`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED = REPO_ROOT / "shared" / "scripts"
SLUGIFY = SHARED / "slugify.py"
WRITER = SHARED / "write_handoff_artifact.py"
READER = SHARED / "read_handoff_slug.py"


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


class TestSlugifyToWriterRoundTrip:
    """A slug produced by slugify.py must be accepted as --slug by write_handoff_artifact."""

    def test_slugify_output_writes_clean(self, tmp_path: Path) -> None:
        # slugify needs an empty .cheese/specs to avoid the collision exit.
        # Use a clean tmp cwd so .cheese/specs/<slug>.md is absent.
        slug_proc = _run(
            SLUGIFY,
            "from-task",
            "--task",
            "Fix the off-by-one when tailing trailing newline",
            "--json",
            cwd=tmp_path,
        )
        assert slug_proc.returncode == 0, slug_proc.stderr
        payload = json.loads(slug_proc.stdout)
        slug = payload["slug"]
        # Sanity: slugify produces a kebab string (anchors the contract press
        # depends on — every downstream script will reject non-kebab slugs).
        assert slug == slug.lower()
        assert " " not in slug
        assert "--" not in slug

        # The very same slug must flow into write_handoff_artifact without
        # any munging.
        write_proc = _run(
            WRITER,
            "--slug",
            slug,
            "--status",
            "ok",
            "--next",
            "press",
            "--artifact",
            "",
            "--orientation",
            "cook done",
            cwd=tmp_path,
        )
        assert write_proc.returncode == 0, write_proc.stderr
        # Writer prints the final path on stdout.
        written = Path(write_proc.stdout.strip())
        assert written.name == f"{slug}.md"
        assert written.parent.name == "press"


class TestWriterToReaderRoundTrip:
    """write_handoff_artifact and read_handoff_slug must agree on the preamble shape.

    Both scripts are tested in isolation against synthetic strings or the
    handoff library. The CLI-to-CLI seam (subprocess emits → subprocess parses)
    is untested. A subtle change in either side — e.g. trailing-whitespace
    handling, blank-artifact rendering — could silently break /age and /cure
    when they pick up press / age output respectively. This test locks the
    CLI-to-CLI contract.
    """

    def _write_and_read(
        self,
        tmp_path: Path,
        *,
        slug: str,
        status: str,
        next_phase: str,
        artifact: str,
        orientation: str,
    ) -> dict[str, object]:
        write_proc = _run(
            WRITER,
            "--slug",
            slug,
            "--status",
            status,
            "--next",
            next_phase,
            "--artifact",
            artifact,
            "--orientation",
            orientation,
            cwd=tmp_path,
        )
        assert write_proc.returncode == 0, write_proc.stderr

        read_proc = _run(
            READER, "--phase", next_phase, "--slug", slug, cwd=tmp_path
        )
        assert read_proc.returncode == 0, read_proc.stderr
        return json.loads(read_proc.stdout)

    def test_ok_status_survives_cli_roundtrip(self, tmp_path: Path) -> None:
        payload = self._write_and_read(
            tmp_path,
            slug="cook-to-press",
            status="ok",
            next_phase="press",
            artifact=".cheese/cook/cook-to-press.md",
            orientation="implemented widget",
        )
        assert payload == {
            "status": "ok",
            "next": "press",
            "artifact": ".cheese/cook/cook-to-press.md",
            "orientation": "implemented widget",
            "halt_reason": None,
        }

    def test_halt_status_survives_cli_roundtrip(self, tmp_path: Path) -> None:
        # The halt reason has a colon-and-space inside it — a real-world
        # blocked message ("spinning: gap-X"). The render uses
        # 'status: halt: <reason>' and the reader must reconstruct the exact
        # original reason or downstream skills mis-attribute the halt.
        payload = self._write_and_read(
            tmp_path,
            slug="halt-with-colon",
            status="halt: spinning: gap-3-flaky-seam",
            next_phase="age",
            artifact=".cheese/press/halt-with-colon.md",
            orientation="three attempts on same gap",
        )
        assert payload["status"] == "halt"
        assert payload["halt_reason"] == "spinning: gap-3-flaky-seam"
        assert payload["next"] == "age"

    def test_empty_artifact_roundtrips_as_none(self, tmp_path: Path) -> None:
        # cook is the chain head — it has no prior artifact, so cook passes
        # --artifact "". Read must yield artifact=None (not "") so downstream
        # `if payload["artifact"]:` checks behave correctly.
        payload = self._write_and_read(
            tmp_path,
            slug="chain-head",
            status="ok",
            next_phase="press",
            artifact="",
            orientation="first phase in the chain",
        )
        assert payload["artifact"] is None

    def test_orientation_with_punctuation_survives(self, tmp_path: Path) -> None:
        # Real orientation lines have colons, parens, slashes — none of
        # which should confuse the four-line parser.
        orientation = "added 4 boundary tests (off-by-one, eof, empty, max); no defects exposed"
        payload = self._write_and_read(
            tmp_path,
            slug="punct-orientation",
            status="ok",
            next_phase="age",
            artifact=".cheese/press/punct-orientation.md",
            orientation=orientation,
        )
        assert payload["orientation"] == orientation


class TestThreeScriptChain:
    """Full /cook-style chain: slugify → write → read.

    Mirrors the SKILL.md prose pattern for cook: derive slug, write handoff
    targeting press, then /press's own read step retrieves the same slug.
    """

    def test_full_chain_preserves_slug_and_payload(self, tmp_path: Path) -> None:
        slug_proc = _run(
            SLUGIFY,
            "from-task",
            "--task",
            "Wire the chain through slugify then handoff",
            "--json",
            cwd=tmp_path,
        )
        assert slug_proc.returncode == 0, slug_proc.stderr
        slug = json.loads(slug_proc.stdout)["slug"]

        write_proc = _run(
            WRITER,
            "--slug",
            slug,
            "--status",
            "ok",
            "--next",
            "press",
            "--artifact",
            "",
            "--orientation",
            "cook step complete",
            cwd=tmp_path,
        )
        assert write_proc.returncode == 0, write_proc.stderr

        read_proc = _run(READER, "--phase", "press", "--slug", slug, cwd=tmp_path)
        assert read_proc.returncode == 0, read_proc.stderr
        payload = json.loads(read_proc.stdout)
        # The slug-derived artifact lives on disk and parses back cleanly.
        assert payload["next"] == "press"
        assert payload["orientation"] == "cook step complete"
        assert payload["status"] == "ok"

    def test_reader_reports_missing_artifact_when_writer_skipped(
        self, tmp_path: Path
    ) -> None:
        # If a phase writes nothing (e.g. /cook crashed mid-handoff), the
        # next phase's read must fail loudly — not silently return an empty
        # payload that downstream skills would treat as a successful chain.
        slug_proc = _run(
            SLUGIFY, "from-task", "--task", "Missing artifact path", "--json", cwd=tmp_path
        )
        slug = json.loads(slug_proc.stdout)["slug"]

        read_proc = _run(READER, "--phase", "press", "--slug", slug, cwd=tmp_path)
        assert read_proc.returncode == 2
        assert "artifact not found" in read_proc.stderr

    def test_cross_phase_chain_cook_press_age_paths_resolve(
        self, tmp_path: Path
    ) -> None:
        # Regression test for the H1 handoff path-contract break: each phase
        # writes ITS OWN .cheese/<phase>/<slug>.md, and the next phase reads
        # from that same path. Before --phase existed, the writer derived the
        # path from --next, so press's report landed at .cheese/age/<slug>.md
        # and age could not find it via `--phase press`. This test locks the
        # full cook → press → age chain to the now-canonical convention.
        slug = "cross-phase-chain"

        # 1. Cook writes its handoff to .cheese/cook/<slug>.md.
        cook_proc = _run(
            WRITER,
            "--slug", slug,
            "--status", "ok",
            "--phase", "cook",
            "--next", "press",
            "--artifact", "",
            "--orientation", "cook implemented widget",
            cwd=tmp_path,
        )
        assert cook_proc.returncode == 0, cook_proc.stderr
        cook_path = tmp_path / ".cheese" / "cook" / f"{slug}.md"
        assert cook_path.exists(), f"cook artifact missing at {cook_path}"

        # 2. Press reads cook's handoff via `--phase cook --slug <slug>`.
        press_read = _run(READER, "--phase", "cook", "--slug", slug, cwd=tmp_path)
        assert press_read.returncode == 0, press_read.stderr
        cook_payload = json.loads(press_read.stdout)
        assert cook_payload["next"] == "press"
        assert cook_payload["orientation"] == "cook implemented widget"

        # 3. Press writes its own handoff to .cheese/press/<slug>.md while the
        #    preamble points the chain at age. Critically: the file does NOT
        #    land in .cheese/age/<slug>.md (the H1 defect).
        press_proc = _run(
            WRITER,
            "--slug", slug,
            "--status", "ok",
            "--phase", "press",
            "--next", "age",
            "--artifact", str(cook_path.relative_to(tmp_path)),
            "--orientation", "press hardened 4 boundary tests",
            cwd=tmp_path,
        )
        assert press_proc.returncode == 0, press_proc.stderr
        press_path = tmp_path / ".cheese" / "press" / f"{slug}.md"
        assert press_path.exists(), f"press artifact missing at {press_path}"
        assert not (tmp_path / ".cheese" / "age" / f"{slug}.md").exists()

        # 4. Age reads the press handoff via `--phase press --slug <slug>` —
        #    the exact invocation skills/age/SKILL.md advertises.
        age_read = _run(READER, "--phase", "press", "--slug", slug, cwd=tmp_path)
        assert age_read.returncode == 0, age_read.stderr
        press_payload = json.loads(age_read.stdout)
        assert press_payload["next"] == "age"
        assert press_payload["orientation"] == "press hardened 4 boundary tests"
        assert press_payload["artifact"] == str(cook_path.relative_to(tmp_path))
