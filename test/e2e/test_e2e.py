"""End-to-end tests running the installed command the way a workflow step does."""

from __future__ import annotations

import os
import subprocess
import sys
from test.samples import CLEAN_PROJECT, CLEAN_RUN, FULL_RUN, OUTER_BOUND, PROJECT
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

@pytest.mark.e2e
class TestTheCommandAsAStepRunsIt:
    """The command as a workflow step invokes it."""

    def test_reports_the_test_only_definition(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition only its own tests name is reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli_subprocess(FULL_RUN)
        assert "orphan" in stdout

    def test_leaves_the_called_definition_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition another tree calls is not reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli_subprocess(FULL_RUN)
        assert "kept" not in stdout

    def test_findings_fail_the_step(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A finding exits non-zero, which is what fails a job."""
        write_tree(PROJECT)
        exit_code, _, _ = run_cli_subprocess(FULL_RUN)
        assert exit_code == 1

    def test_a_clean_tree_passes_the_step(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A tree with nothing to report exits zero."""
        write_tree(CLEAN_PROJECT)
        exit_code, _, _ = run_cli_subprocess(CLEAN_RUN)
        assert exit_code == 0

    def test_the_outer_bound_is_quiet_on_a_tested_module(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Without --dont-search-in a module its own tests exercise reads as used."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli_subprocess(OUTER_BOUND)
        assert "orphan" not in stdout

    def test_the_console_script_is_installed(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """The packaged entry point runs under its own name."""
        write_tree(PROJECT)
        result = subprocess.run(
            ["assert-python-definition-is-used", *FULL_RUN],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "orphan" in result.stdout

    def test_help_names_the_program(
        self, run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """The help text names the command a workflow would call."""
        _, stdout, _ = run_cli_subprocess(["--help"])
        assert "assert-python-definition-is-used" in stdout

    def test_no_arguments_is_a_usage_error(
        self, run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """Called with nothing, the command explains itself and fails."""
        exit_code, _, _ = run_cli_subprocess([])
        assert exit_code == 2

    def test_a_missing_tree_exits_two(
        self, run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """A tree that does not exist is an error rather than a finding."""
        exit_code, _, _ = run_cli_subprocess(["no/such/tree"])
        assert exit_code == 2

    def test_quiet_reports_through_the_exit_code(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Quiet mode prints nothing but still fails."""
        write_tree(PROJECT)
        exit_code, stdout, _ = run_cli_subprocess([*FULL_RUN, "--quiet"])
        assert (exit_code, stdout) == (1, "")

    def test_warn_only_keeps_a_job_green(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli_subprocess: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Warn-only lets a job report without failing."""
        write_tree(PROJECT)
        exit_code, _, _ = run_cli_subprocess([*FULL_RUN, "--warn-only"])
        assert exit_code == 0

    def test_it_reads_its_own_source_tree(self) -> None:
        """Run against this package, every public definition is used."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "assert_python_definition_is_used",
                "src",
                "--search-in",
                "src",
                "--search-in",
                "test",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
        )
        assert result.stdout == ""
