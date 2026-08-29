"""Root pytest configuration and shared test utilities."""

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
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "e2e: end-to-end tests")


@pytest.fixture(name="run_cli")
def run_cli_fixture() -> RunCli:
    """Run the CLI in process, so that coverage sees it.

    Returns:
        A function taking arguments and returning exit code, stdout, stderr.
    """

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
    """Run the CLI as a subprocess, the way a workflow step does.

    Returns:
        A function taking arguments and returning exit code, stdout, stderr.
    """

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
    """Build a source tree and enter it, because every path here is relative.

    Returns:
        A function taking a mapping of relative path to content, writing each
        file, changing into the tree and returning its root.
    """

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
    """Build a tree and run over it in process, where coverage can see the run.

    Returns:
        A function taking a tree and arguments, returning what the run did.
    """
    return build_runner(write_tree, run_cli)


@pytest.fixture(name="stdout_of")
def stdout_of_fixture(run_over: RunOver) -> StdoutOf:
    """Run over a tree and hand back what was reported.

    Returns:
        A function taking a mapping of relative path to content and the
        arguments to run, returning stdout.
    """

    def printed(files: dict[str, str], args: list[str]) -> str:
        return run_over(files, args)[1]

    return printed


@pytest.fixture(name="stderr_of")
def stderr_of_fixture(run_over: RunOver) -> StderrOf:
    """Run over a tree and hand back what was complained about.

    Returns:
        A function taking a mapping of relative path to content and the
        arguments to run, returning stderr.
    """

    def complained(files: dict[str, str], args: list[str]) -> str:
        return run_over(files, args)[2]

    return complained


@pytest.fixture(name="exit_code_of")
def exit_code_of_fixture(run_over: RunOver) -> ExitCodeOf:
    """Run over a tree and hand back the code a job would read.

    Returns:
        A function taking a mapping of relative path to content and the
        arguments to run, returning the exit code.
    """

    def exited(files: dict[str, str], args: list[str]) -> int:
        return run_over(files, args)[0]

    return exited
