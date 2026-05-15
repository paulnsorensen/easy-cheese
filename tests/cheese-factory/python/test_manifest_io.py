"""Direct tests for manifest_io.

manifest_io is the shared YAML/JSON loader used by validate_manifest,
validate_pr_plan, and pr_plan_to_branches. It's exercised indirectly through
their CLI tests, but the error paths deserve dedicated coverage because two
unrelated callers depend on identical failure semantics (exit codes, error
strings, exception class).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import ModuleType

import pytest


class TestParseMapping:
    def test_json_parses(self, manifest_io: ModuleType) -> None:
        assert manifest_io.parse_mapping('{"a": 1, "b": "two"}') == {"a": 1, "b": "two"}

    def test_yaml_parses_when_not_valid_json(self, manifest_io: ModuleType) -> None:
        # `a: 1` is invalid JSON but valid YAML — the fallback path must engage.
        assert manifest_io.parse_mapping("a: 1\nb: two\n") == {"a": 1, "b": "two"}

    def test_neither_json_nor_yaml_fails(self, manifest_io: ModuleType) -> None:
        # `{` is invalid JSON and YAML can't recover it either — the error
        # message must mention both attempts so a human can debug.
        with pytest.raises(manifest_io.ManifestLoadError) as exc:
            manifest_io.parse_mapping("{this is broken: : :")
        message = str(exc.value)
        assert "invalid JSON" in message
        assert "invalid YAML" in message

    def test_non_mapping_root_list_fails(self, manifest_io: ModuleType) -> None:
        # Manifests are always documents-at-the-root; a top-level list must
        # be rejected so downstream code can rely on dict access.
        with pytest.raises(manifest_io.ManifestLoadError, match="expected a mapping"):
            manifest_io.parse_mapping("[1, 2, 3]")

    def test_non_mapping_root_scalar_fails(self, manifest_io: ModuleType) -> None:
        with pytest.raises(manifest_io.ManifestLoadError, match="expected a mapping"):
            manifest_io.parse_mapping("42")

    def test_source_appears_in_error_message(self, manifest_io: ModuleType) -> None:
        # The source argument exists so error messages can point at the file
        # the user actually edited, not "<stdin>".
        with pytest.raises(manifest_io.ManifestLoadError, match=r"my-plan\.yaml"):
            manifest_io.parse_mapping("not: valid: yaml:", source="my-plan.yaml")

    def test_pyyaml_missing_is_reported(
        self,
        manifest_io: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate an environment where PyYAML isn't installed. The function
        # imports `yaml` lazily inside the function body, so blocking the
        # module in sys.modules forces ImportError on the import statement.
        monkeypatch.setitem(sys.modules, "yaml", None)
        with pytest.raises(manifest_io.ManifestLoadError, match="PyYAML is not installed"):
            manifest_io.parse_mapping("a: 1")


class TestReadMappingArgOrStdin:
    def test_reads_from_path(
        self,
        manifest_io: ModuleType,
        tmp_path: Path,
    ) -> None:
        plan = tmp_path / "plan.yaml"
        plan.write_text("shape: single\ngroups: []\n", encoding="utf-8")
        result = manifest_io.read_mapping_arg_or_stdin(
            ["prog", str(plan)], "usage: prog [<plan>]"
        )
        assert result == {"shape": "single", "groups": []}

    def test_reads_from_stdin_when_no_arg(
        self,
        manifest_io: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"hello": "world"}'))
        result = manifest_io.read_mapping_arg_or_stdin(
            ["prog"], "usage: prog [<plan>]"
        )
        assert result == {"hello": "world"}

    def test_missing_file_reports_not_found(
        self,
        manifest_io: ModuleType,
        tmp_path: Path,
    ) -> None:
        bogus = tmp_path / "does-not-exist.yaml"
        with pytest.raises(manifest_io.ManifestLoadError, match="manifest not found"):
            manifest_io.read_mapping_arg_or_stdin(
                ["prog", str(bogus)], "usage: prog [<plan>]"
            )

    def test_too_many_args_yields_usage(self, manifest_io: ModuleType) -> None:
        # The CLI scripts inspect the error message — anything starting with
        # "usage:" maps to exit code 2 (argument error), anything else to 1
        # (load failure). Don't break that contract by changing the prefix.
        usage = "usage: prog [<plan>]"
        with pytest.raises(manifest_io.ManifestLoadError) as exc:
            manifest_io.read_mapping_arg_or_stdin(
                ["prog", "a", "b"], usage
            )
        assert str(exc.value) == usage
