from __future__ import annotations

import os
import subprocess
import sys
from test.samples import (
    CLEAN_PROJECT,
    CLEAN_RUN,
    FULL_RUN,
    NOTED_PROJECT,
    OUTER_BOUND,
    PROJECT,
    RUNTIME_ASSUMED,
    RUNTIME_PROJECT,
    RUNTIME_RUN,
)
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from test.runners import ExitCodeOf, RunOver, StdoutOf, WriteTree


@pytest.mark.e2e
class TestTheCommandAsAStepRunsIt:
    def test_reports_the_test_only_definition(self, stdout_of: StdoutOf) -> None:
        assert "orphan" in stdout_of(PROJECT, FULL_RUN)

    def test_leaves_the_called_definition_alone(self, stdout_of: StdoutOf) -> None:
        assert "kept" not in stdout_of(PROJECT, FULL_RUN)

    def test_findings_fail_the_step(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(PROJECT, FULL_RUN) == 1

    def test_a_clean_tree_passes_the_step(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(CLEAN_PROJECT, CLEAN_RUN) == 0

    def test_the_outer_bound_is_quiet_on_a_tested_module(self, stdout_of: StdoutOf) -> None:
        assert "orphan" not in stdout_of(PROJECT, OUTER_BOUND)

    def test_the_console_script_is_installed(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        result = subprocess.run(
            ["assert-python-definition-is-used", *FULL_RUN],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "orphan" in result.stdout

    def test_help_names_the_program(self, stdout_of: StdoutOf) -> None:
        assert "assert-python-definition-is-used" in stdout_of({}, ["--help"])

    def test_no_arguments_is_a_usage_error(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of({}, []) == 2

    def test_a_missing_tree_exits_two(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of({}, ["no/such/tree"]) == 2

    def test_quiet_reports_through_the_exit_code(self, run_over: RunOver) -> None:
        exit_code, stdout, _ = run_over(PROJECT, [*FULL_RUN, "--quiet"])
        assert (exit_code, stdout) == (1, "")

    def test_warn_only_keeps_a_job_green(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(PROJECT, [*FULL_RUN, "--warn-only"]) == 0

    def test_it_reads_its_own_source_tree(self) -> None:
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


@pytest.mark.e2e
class TestANoteAsAStepRunsIt:
    def test_reports_the_definition_the_note_is_about(self, stdout_of: StdoutOf) -> None:
        assert "noted" in stdout_of(NOTED_PROJECT, CLEAN_RUN)

    def test_the_note_fails_the_step(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(NOTED_PROJECT, CLEAN_RUN) == 1


@pytest.mark.e2e
class TestARuntimeInvokedTreeAsAStepRunsIt:
    def test_the_tree_is_refused_without_the_inputs(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(RUNTIME_PROJECT, RUNTIME_RUN) == 1

    def test_naming_what_the_runtime_invokes_clears_the_tree(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)
        assert stdout.splitlines() == ["test/pkg/test_pkg.py:17:spare"]

    def test_the_step_still_fails_on_what_is_left(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(RUNTIME_PROJECT, RUNTIME_ASSUMED) == 1

    def test_a_tree_of_nothing_else_passes(self, exit_code_of: ExitCodeOf) -> None:
        tree = {"test/pkg/test_pkg.py": "def test_it():\n    assert True\n"}
        assert exit_code_of(tree, RUNTIME_ASSUMED) == 0

    def test_the_verbose_summary_names_both_grounds(self, stdout_of: StdoutOf) -> None:
        assert "Assumed used by name: 2" in stdout_of(
            RUNTIME_PROJECT, [*RUNTIME_ASSUMED, "--verbose"]
        )
