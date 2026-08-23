"""Root pytest configuration and shared test utilities."""

from __future__ import annotations

import io
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from assert_python_definition_is_used.cli import main

if TYPE_CHECKING:
    from collections.abc import Callable


def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "unit: unit tests")
    config.addinivalue_line("markers", "integration: integration tests")
    config.addinivalue_line("markers", "e2e: end-to-end tests")


@pytest.fixture
def run_cli() -> Callable[[list[str]], tuple[int, str, str]]:
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


@pytest.fixture
def run_cli_subprocess() -> Callable[[list[str]], tuple[int, str, str]]:
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


@pytest.fixture
def write_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, str]], Path]:
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
