"""Tests for skills/briesearch/scripts/route_research.py.

Covers the routing decision table, --json output, sidecar JSON creation
(via --out-dir override), and the empty-question failure path. Loaded inline
via importlib so no conftest is needed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "skills" / "briesearch" / "scripts" / "route_research.py"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"


@pytest.fixture(scope="module")
def route_research() -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location("route_research", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["route_research"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------


class TestDocRouting:
    def test_how_do_i_use_routes_context7(self, route_research: ModuleType) -> None:
        d = route_research.classify("how do I use the Stripe SDK")
        assert d["tool"] == "context7"
        assert d["depth"] is None

    def test_sdk_api_routes_context7(self, route_research: ModuleType) -> None:
        d = route_research.classify("Stripe SDK API for refunds")
        assert d["tool"] == "context7"

    def test_api_for_routes_context7(self, route_research: ModuleType) -> None:
        d = route_research.classify("what's the API for pydantic v2 validators")
        assert d["tool"] == "context7"


class TestRecencyRouting:
    def test_latest_routes_tavily_basic(self, route_research: ModuleType) -> None:
        d = route_research.classify("latest Next.js release notes")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"

    def test_recent_routes_tavily_basic(self, route_research: ModuleType) -> None:
        d = route_research.classify("recent CVEs in openssl")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"

    def test_this_week_routes_tavily_basic(self, route_research: ModuleType) -> None:
        d = route_research.classify("what shipped in Rust this week")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"


class TestComparativeRouting:
    def test_compare_vs_routes_tavily_research(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("compare Postgres vs SQLite for embedded use")
        assert d["tool"] == "tavily-research"
        assert d["depth"] == "advanced"

    def test_best_practices_routes_tavily_research(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("Kubernetes secret rotation best practices")
        assert d["tool"] == "tavily-research"
        assert d["depth"] == "advanced"

    def test_deep_research_routes_tavily_research(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("deep research on RAG eval frameworks")
        assert d["tool"] == "tavily-research"


class TestLocalRouting:
    def test_in_this_repo_routes_cheez_search(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("where does retry happen in this repo")
        assert d["tool"] == "cheez-search"
        assert d["depth"] is None

    def test_show_me_callers_routes_cheez_search(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("show me callers of build_index")
        assert d["tool"] == "cheez-search"


class TestGithubRouting:
    def test_examples_on_github_routes_gh(self, route_research: ModuleType) -> None:
        d = route_research.classify("examples of asyncio.gather on GitHub")
        assert d["tool"] == "gh"

    def test_oss_precedent_routes_gh(self, route_research: ModuleType) -> None:
        d = route_research.classify("OSS precedent for plugin loaders")
        assert d["tool"] == "gh"


class TestDefault:
    def test_unmatched_question_falls_through_to_tavily_basic(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("explain monads")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"
        assert "default" in d["rationale"].lower()


# ---------------------------------------------------------------------------
# Tie-breaker flags
# ---------------------------------------------------------------------------


class TestPreferenceFlags:
    def test_prefer_docs_only_affects_doc_matches(
        self, route_research: ModuleType
    ) -> None:
        # Doc match -> Context7 with prefer-docs bias note.
        d = route_research.classify(
            "how do I use the Stripe SDK", prefer_docs=True
        )
        assert d["tool"] == "context7"
        assert "prefer-docs" in d["rationale"]

    def test_prefer_docs_does_nothing_when_no_doc_match(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("latest Next.js release", prefer_docs=True)
        # Recency still wins because no doc pattern matched.
        assert d["tool"] == "tavily-search"

    def test_prefer_recency_biases_to_tavily_basic(
        self, route_research: ModuleType
    ) -> None:
        d = route_research.classify("latest Kafka release", prefer_recency=True)
        assert d["tool"] == "tavily-search"
        assert "prefer-recency" in d["rationale"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TestEmptyQuestion:
    def test_empty_string_raises_clierror(self, route_research: ModuleType) -> None:
        import cli  # loaded via path-insert in fixture
        with pytest.raises(cli.CliError):
            route_research.classify("")

    def test_whitespace_only_raises_clierror(
        self, route_research: ModuleType
    ) -> None:
        import cli
        with pytest.raises(cli.CliError):
            route_research.classify("   \n  ")


# ---------------------------------------------------------------------------
# Sidecar JSON
# ---------------------------------------------------------------------------


class TestSidecarFile:
    def test_creates_sidecar_json_at_out_dir(
        self, route_research: ModuleType, tmp_path: Path
    ) -> None:
        decision = route_research.classify("how do I use the Stripe SDK")
        path = route_research._write_sidecar(decision, tmp_path)
        assert path.exists()
        assert path.parent == tmp_path
        assert path.suffix == ".json"
        payload = json.loads(path.read_text())
        assert payload["tool"] == "context7"
        assert payload["question"] == "how do I use the Stripe SDK"

    def test_slug_is_kebab_of_first_40_chars(
        self, route_research: ModuleType
    ) -> None:
        slug = route_research._slugify(
            "How do I use the Stripe SDK for refunds and disputes please"
        )
        assert slug.islower()
        assert " " not in slug
        assert len(slug) <= 40
        # First few words present.
        assert slug.startswith("how-do-i-use-the-stripe-sdk")

    def test_slug_strips_trailing_hyphens(self, route_research: ModuleType) -> None:
        # 41st char is a separator boundary; trailing hyphen must be stripped.
        slug = route_research._slugify("a" * 38 + "-bar")
        assert not slug.endswith("-")

    def test_empty_question_slug_is_untitled(
        self, route_research: ModuleType
    ) -> None:
        # _slugify is reachable with empty input even though classify rejects it.
        assert route_research._slugify("") == "untitled"

    def test_sidecar_creates_missing_dirs(
        self, route_research: ModuleType, tmp_path: Path
    ) -> None:
        nested = tmp_path / "a" / "b" / "c"
        decision = route_research.classify("compare Postgres vs SQLite")
        path = route_research._write_sidecar(decision, nested)
        assert path.exists()
        assert nested.exists()


# ---------------------------------------------------------------------------
# End-to-end CLI
# ---------------------------------------------------------------------------


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


class TestCliEndToEnd:
    def test_doc_question_prints_routing_block(self, tmp_path: Path) -> None:
        result = _run(
            ["--question", "how do I use the Stripe SDK", "--out-dir", str(tmp_path)],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "context7" in result.stdout.lower()
        assert "ROUTING DECISION" in result.stdout

    def test_json_mode_prints_json(self, tmp_path: Path) -> None:
        result = _run(
            [
                "--question",
                "how do I use the Stripe SDK",
                "--out-dir",
                str(tmp_path),
                "--json",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["tool"] == "context7"
        assert payload["depth"] is None

    def test_sidecar_written_at_out_dir(self, tmp_path: Path) -> None:
        result = _run(
            [
                "--question",
                "latest Next.js release",
                "--out-dir",
                str(tmp_path),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text())
        assert payload["tool"] == "tavily-search"
        assert payload["depth"] == "basic"

    def test_missing_question_exits_two(self, tmp_path: Path) -> None:
        # No --question -> cli.CliError -> exit 2 with ERROR on stderr.
        result = _run([], cwd=tmp_path)
        assert result.returncode == 2
        assert "ERROR" in result.stderr

    def test_recency_routes_tavily_basic_end_to_end(self, tmp_path: Path) -> None:
        result = _run(
            [
                "--question",
                "what shipped in Rust this week",
                "--out-dir",
                str(tmp_path),
                "--json",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["tool"] == "tavily-search"
        assert payload["depth"] == "basic"
