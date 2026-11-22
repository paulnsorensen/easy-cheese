"""Streaming and batching of the ast-grep runner, proved against fake binaries."""

from __future__ import annotations

import json
import sys
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import pytest

from easy_cheese_review import _ast_grep
from easy_cheese_review._ast_grep import AstGrepError
from tests.review.python.support import WriteTree, fake_ast_grep

CONFIG = Path("sgconfig.yml")

# Echo one row per path after `--`, shaped for the command that was called.
_ECHO = """#!__PY__
import json, sys
from pathlib import Path

argv = sys.argv[1:]
with Path(__file__).with_name("calls.log").open("a") as log:
    log.write(json.dumps(argv) + "\\n")
for path in argv[argv.index("--") + 1:]:
    if "outline" in argv:
        row = {"path": path, "items": [{"name": path}, "skipped"]}
    elif "--inline-rules" in argv:
        row = {"ruleId": "import-py", "file": "./" + path, "text": "import " + path}
    else:
        row = {"ruleId": "rule", "file": path}
    print(json.dumps(row))
"""

# Write 2000 import rows of about 10 KB each: 20 MB in total.
_FLOOD = """#!__PY__
import json

pad = "x" * 10_000
for index in range(2000):
    print(json.dumps({"ruleId": "import-py", "file": f"f{index}.py", "text": "import x", "pad": pad}))
"""


def _binary(tmp_path: Path, write_tree: WriteTree, script: str) -> str:
    return fake_ast_grep(tmp_path, write_tree, script.replace("__PY__", sys.executable))


def _calls(binary: str) -> list[list[str]]:
    log = Path(binary).with_name("calls.log")
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_imports_streams_output_without_holding_it_in_memory(
    tmp_path: Path, write_tree: WriteTree
) -> None:
    binary = _binary(tmp_path, write_tree, _FLOOD)
    tracemalloc.start()
    try:
        found = _ast_grep.imports(binary, CONFIG, tmp_path, ["."])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert len(found) == 2000
    assert found["f0.py"] == ["import x"]
    assert peak < 5_000_000  # holding the 20 MB of output would exceed this


def test_timeout_bounds_a_run_whose_stream_stays_open(
    tmp_path: Path, write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = '#!/bin/sh\necho \'{"ruleId": "r", "file": "a.py"}\'\nsleep 30\n'
    binary = _binary(tmp_path, write_tree, script)
    monkeypatch.setattr(_ast_grep, "_TIMEOUT_SECONDS", 0.5)
    started = time.monotonic()
    with pytest.raises(AstGrepError, match="^timeout$"):
        _ = _ast_grep.scan(binary, CONFIG, tmp_path, ["a.py"])
    assert time.monotonic() - started < 10


def test_a_non_zero_exit_wins_over_bad_json(tmp_path: Path, write_tree: WriteTree) -> None:
    binary = _binary(tmp_path, write_tree, "#!/bin/sh\necho 'not json'\nexit 4\n")
    with pytest.raises(AstGrepError, match="^exit-4$"):
        _ = _ast_grep.scan(binary, CONFIG, tmp_path, ["a.py"])


def test_bad_json_in_the_middle_of_the_stream_still_raises(
    tmp_path: Path, write_tree: WriteTree
) -> None:
    script = "#!/bin/sh\necho '{\"ruleId\": \"r\"}'\necho 'oops'\necho '{\"ruleId\": \"r\"}'\n"
    binary = _binary(tmp_path, write_tree, script)
    with pytest.raises(AstGrepError, match="^bad-json$"):
        _ = _ast_grep.scan(binary, CONFIG, tmp_path, ["a.py"])


def test_a_missing_binary_is_an_exec_error(tmp_path: Path) -> None:
    with pytest.raises(AstGrepError, match="^exec-error$"):
        _ = _ast_grep.scan(str(tmp_path / "nope"), CONFIG, tmp_path, ["a.py"])


def _scan(binary: str, paths: list[str], cwd: Path) -> object:
    return _ast_grep.scan(binary, CONFIG, cwd, paths)


def _imports(binary: str, paths: list[str], cwd: Path) -> object:
    return _ast_grep.imports(binary, CONFIG, cwd, paths)


def _outline(binary: str, paths: list[str], cwd: Path) -> object:
    return _ast_grep.outline(binary, CONFIG, cwd, paths, "exports")


@pytest.mark.parametrize("call", [_scan, _imports, _outline], ids=["scan", "imports", "outline"])
def test_paths_go_out_in_batches_and_the_rows_merge_in_order(
    tmp_path: Path,
    write_tree: WriteTree,
    monkeypatch: pytest.MonkeyPatch,
    call: Callable[[str, list[str], Path], object],
) -> None:
    paths = [f"src/file_{index:02d}.py" for index in range(20)]
    single = _binary(tmp_path / "single", write_tree, _ECHO)
    batched = _binary(tmp_path / "batched", write_tree, _ECHO)

    expected = call(single, paths, tmp_path)
    assert len(_calls(single)) == 1

    monkeypatch.setattr(_ast_grep, "_ARG_BYTE_BUDGET", 100)
    merged = call(batched, paths, tmp_path)

    runs = _calls(batched)
    assert len(runs) >= 2
    sent = [path for run in runs for path in run[run.index("--") + 1 :]]
    assert sent == paths  # every path once, in input order
    assert merged == expected


def test_a_path_larger_than_the_budget_still_runs_alone(
    tmp_path: Path, write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = _binary(tmp_path, write_tree, _ECHO)
    monkeypatch.setattr(_ast_grep, "_ARG_BYTE_BUDGET", 1)
    rows = _ast_grep.scan(binary, CONFIG, tmp_path, ["a.py", "b.py", "c.py"])
    assert [row["file"] for row in rows] == ["a.py", "b.py", "c.py"]
    assert len(_calls(binary)) == 3
