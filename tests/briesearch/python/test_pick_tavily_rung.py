"""Tests for skills/briesearch/scripts/pick_tavily_rung.py.

No conftest: load the script and cli.py inline via importlib so the test
module is self-contained (matches curd #17 spec).
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
SCRIPT_PATH = REPO_ROOT / "skills" / "briesearch" / "scripts" / "pick_tavily_rung.py"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"


@pytest.fixture(scope="module")
def rung() -> ModuleType:
    # Make `import cli` work for the script under test.
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location("pick_tavily_rung", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["pick_tavily_rung"] = module
    spec.loader.exec_module(module)
    return module


class TestRecentShape:
    def test_latest_maps_to_search_basic_week(self, rung: ModuleType) -> None:
        d = rung.pick("latest X")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"
        assert d["filters"] == {"time_range": "week"}

    def test_recent_maps_to_search_basic_week(self, rung: ModuleType) -> None:
        d = rung.pick("recent changes to the protocol")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"
        assert d["filters"]["time_range"] == "week"

    def test_this_week_phrase(self, rung: ModuleType) -> None:
        d = rung.pick("notable releases this week")
        assert d["tool"] == "tavily-search"
        assert d["filters"]["time_range"] == "week"


class TestCompareShape:
    def test_compare_vs_maps_to_research_advanced(self, rung: ModuleType) -> None:
        d = rung.pick("compare X vs Y")
        assert d["tool"] == "tavily-research"
        assert d["depth"] == "advanced"
        assert d["filters"] == {}

    def test_deep_research_phrase(self, rung: ModuleType) -> None:
        d = rung.pick("deep research on managed actors")
        assert d["tool"] == "tavily-research"
        assert d["depth"] == "advanced"


class TestOpinionShape:
    def test_opinion_on_maps_to_search_advanced(self, rung: ModuleType) -> None:
        d = rung.pick("opinion on tilth MCP")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "advanced"
        assert d["filters"] == {}

    def test_review_of_maps_to_search_advanced(self, rung: ModuleType) -> None:
        d = rung.pick("review of the Sonnet 4.7 release")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "advanced"


class TestUrlShape:
    def test_url_alone_maps_to_extract(self, rung: ModuleType) -> None:
        d = rung.pick("read https://example.com/post")
        assert d["tool"] == "tavily-extract"
        assert d["depth"] is None
        assert d["filters"] == {"url": "https://example.com/post"}

    def test_map_the_docs_maps_to_tavily_map(self, rung: ModuleType) -> None:
        d = rung.pick("map the docs at https://docs.example.com")
        assert d["tool"] == "tavily-map"
        assert d["depth"] is None
        assert d["filters"] == {"url": "https://docs.example.com"}

    def test_crawl_maps_to_tavily_crawl(self, rung: ModuleType) -> None:
        d = rung.pick("crawl https://docs.example.com/auth")
        assert d["tool"] == "tavily-crawl"
        assert d["depth"] is None
        assert d["filters"] == {"url": "https://docs.example.com/auth"}


class TestDefaultShape:
    def test_plain_factual_question_is_search_basic_no_filters(self, rung: ModuleType) -> None:
        d = rung.pick("how does rerere work")
        assert d["tool"] == "tavily-search"
        assert d["depth"] == "basic"
        assert d["filters"] == {}


class TestEmptyQuestion:
    def test_empty_string_raises_cli_error(self, rung: ModuleType) -> None:
        # Reuse the same cli module the script loaded.
        cli = sys.modules["cli"]
        with pytest.raises(cli.CliError):
            rung.pick("")

    def test_whitespace_only_raises_cli_error(self, rung: ModuleType) -> None:
        cli = sys.modules["cli"]
        with pytest.raises(cli.CliError):
            rung.pick("   ")


class TestSubprocess:
    """End-to-end shape via the script's CLI entrypoint."""

    def test_missing_question_exits_two(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "ERROR: --question is required" in result.stderr

    def test_latest_subprocess_emits_json_dict(self) -> None:
        # Dicts are always JSON per cli.emit contract; --json is redundant but valid.
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--question", "latest X"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["tool"] == "tavily-search"
        assert payload["depth"] == "basic"
        assert payload["filters"] == {"time_range": "week"}

    def test_compare_subprocess_emits_research_advanced(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--question", "compare X vs Y", "--json"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["tool"] == "tavily-research"
        assert payload["depth"] == "advanced"
        assert payload["filters"] == {}
