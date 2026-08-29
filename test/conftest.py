from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from test.runners import build_runner
from typing import TYPE_CHECKING

import pytest

from assert_python_definition_is_used.cli import main

if TYPE_CHECKING:
    from test.runners import ExitCodeOf, RunCli, RunOver, StderrOf, StdoutOf, WriteTree


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "e2e: end-to-end tests")


@pytest.fixture(name="run_cli")
def run_cli_fixture() -> RunCli:
    def runner(args: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                main(args)
            except SystemExit as exit_request:
                exit_code = int(exit_request.code) if exit_request.code is not None else 0
        return exit_code, stdout.getvalue(), stderr.getvalue()

    return runner


@pytest.fixture(name="run_cli_subprocess")
def run_cli_subprocess_fixture() -> RunCli:
    def runner(args: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(
            [sys.executable, "-m", "assert_python_definition_is_used", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr

    return runner


@pytest.fixture(name="write_tree")
def write_tree_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> WriteTree:
    def builder(files: dict[str, str]) -> Path:
        for relative, content in files.items():
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        return tmp_path

    return builder


@pytest.fixture(name="run_over")
def run_over_fixture(write_tree: WriteTree, run_cli: RunCli) -> RunOver:
    return build_runner(write_tree, run_cli)


@pytest.fixture(name="stdout_of")
def stdout_of_fixture(run_over: RunOver) -> StdoutOf:
    def printed(files: dict[str, str], args: list[str]) -> str:
        return run_over(files, args)[1]

    return printed


@pytest.fixture(name="stderr_of")
def stderr_of_fixture(run_over: RunOver) -> StderrOf:
    def complained(files: dict[str, str], args: list[str]) -> str:
        return run_over(files, args)[2]

    return complained


@pytest.fixture(name="exit_code_of")
def exit_code_of_fixture(run_over: RunOver) -> ExitCodeOf:
    def exited(files: dict[str, str], args: list[str]) -> int:
        return run_over(files, args)[0]

    return exited
