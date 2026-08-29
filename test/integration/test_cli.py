from __future__ import annotations

import os
from test.samples import (
    ADVERTISING_PROJECT,
    CLEAN_PROJECT,
    CLEAN_RUN,
    FULL_RUN,
    LIB_AND_TEST_RUN,
    NOTED_PROJECT,
    OUTER_BOUND,
    PROJECT,
    PROSE,
    RUNTIME_ASSUMED,
    RUNTIME_PROJECT,
    RUNTIME_RUN,
)
from typing import TYPE_CHECKING

import pytest

from assert_python_definition_is_used.cli import EXIT_ERROR, EXIT_FINDINGS, EXIT_SUCCESS

if TYPE_CHECKING:
    from test.runners import ExitCodeOf, RunCli, StderrOf, StdoutOf, WriteTree


@pytest.mark.integration
class TestAgainstARealTree:
    def test_reports_the_definition_only_its_tests_name(self, stdout_of: StdoutOf) -> None:
        assert "orphan" in stdout_of(PROJECT, FULL_RUN)

    def test_leaves_the_called_definition_alone(self, stdout_of: StdoutOf) -> None:
        assert "kept" not in stdout_of(PROJECT, FULL_RUN)

    def test_leaves_the_helper_its_own_file_calls_alone(self, stdout_of: StdoutOf) -> None:
        assert "helper" not in stdout_of(PROJECT, FULL_RUN)

    def test_reports_the_definition_its_own_file_only_mentions(self, stdout_of: StdoutOf) -> None:
        assert "documented" in stdout_of({"lib/python/pkg/__init__.py": PROSE}, ["lib/python"])

    def test_without_the_flag_the_outer_bound_is_quiet_about_orphan(
        self, stdout_of: StdoutOf
    ) -> None:
        assert "orphan" not in stdout_of(PROJECT, OUTER_BOUND)

    def test_findings_exit_one(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(PROJECT, FULL_RUN) == EXIT_FINDINGS

    def test_a_clean_tree_exits_zero(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(CLEAN_PROJECT, CLEAN_RUN) == EXIT_SUCCESS

    def test_reports_in_path_order(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/a/__init__.py": "def one():\n    pass\n",
                "lib/python/b/__init__.py": "def two():\n    pass\n",
            },
            ["lib/python"],
        )
        assert [line.split(":")[2] for line in stdout.splitlines()] == ["one", "two"]

    def test_a_loose_file_keeps_its_tests(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/loose.py": "def solo():\n    pass\n",
                "test/lib/python/test_loose/test_it.py": "solo()\n",
            },
            LIB_AND_TEST_RUN,
        )
        assert stdout == ""

    def test_another_packages_tests_still_count(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/fixtures/__init__.py": "def helper():\n    pass\n",
                "test/lib/python/test_other/test_it.py": "helper()\n",
            },
            LIB_AND_TEST_RUN,
        )
        assert stdout == ""

    def test_a_private_definition_is_never_reported(self, stdout_of: StdoutOf) -> None:
        tree = {"lib/python/pkg/__init__.py": "def _hidden():\n    pass\n"}
        assert stdout_of(tree, ["lib/python"]) == ""

    def test_a_method_is_never_reported(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "class Kept:\n    def spin(self):\n        pass\n",
                "src/app.py": "Kept()\n",
            },
            ["lib/python", "--search-in", "lib/python", "--search-in", "src"],
        )
        assert stdout == ""


@pytest.mark.integration
class TestAgainstATreeHoldingANote:
    def test_reports_the_definition_the_note_is_about(self, stdout_of: StdoutOf) -> None:
        assert "noted" in stdout_of(NOTED_PROJECT, CLEAN_RUN)

    def test_leaves_the_really_called_definition_alone(self, stdout_of: StdoutOf) -> None:
        assert "called" not in stdout_of(NOTED_PROJECT, CLEAN_RUN)

    def test_reports_only_what_is_dead(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(NOTED_PROJECT, CLEAN_RUN).splitlines() == [
            "lib/python/pkg/__init__.py:5:noted"
        ]

    def test_a_name_written_as_data_is_still_a_use(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def handle_login():\n    return 1\n",
                "src/app.py": 'urlpatterns = ["views.handle_login"]\n',
            },
            CLEAN_RUN,
        )
        assert stdout == ""


@pytest.mark.integration
class TestAgainstAStaleExportList:
    def test_reports_the_definition_only_the_export_list_names(self, stdout_of: StdoutOf) -> None:
        assert "dropped" in stdout_of(ADVERTISING_PROJECT, CLEAN_RUN)

    def test_leaves_the_re_exported_definition_alone(self, stdout_of: StdoutOf) -> None:
        assert "shown" not in stdout_of(ADVERTISING_PROJECT, CLEAN_RUN)


@pytest.mark.integration
class TestOutputModes:
    def test_quiet_says_nothing(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, [*FULL_RUN, "--quiet"]) == ""

    def test_quiet_still_fails(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(PROJECT, [*FULL_RUN, "--quiet"]) == EXIT_FINDINGS

    def test_count_gives_a_number(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, [*FULL_RUN, "--count"]) == "1\n"

    def test_verbose_names_the_trees(self, stdout_of: StdoutOf) -> None:
        assert "Searching 3 file(s) for uses." in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_counts_the_files(self, stdout_of: StdoutOf) -> None:
        assert "Files scanned: 1" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_names_each_scan(self, stdout_of: StdoutOf) -> None:
        scanned = os.path.join("lib", "python", "pkg", "__init__.py")
        assert f"Scanning: {scanned}" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_lists_the_findings(self, stdout_of: StdoutOf) -> None:
        assert "Unused:" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_names_the_excludes(self, stdout_of: StdoutOf) -> None:
        run = [*FULL_RUN, "--verbose", "--exclude", "app.py"]
        assert "Excluding patterns: app.py" in stdout_of(PROJECT, run)

    def test_fail_fast_stops_at_one(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, [*FULL_RUN, "--fail-fast", "--count"]) == "1\n"

    def test_warn_only_succeeds(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of(PROJECT, [*FULL_RUN, "--warn-only"]) == EXIT_SUCCESS


@pytest.mark.integration
class TestBrokenInput:
    def test_a_missing_tree_is_named(self, stderr_of: StderrOf) -> None:
        assert "Path not found: no/such/tree" in stderr_of({}, ["no/such/tree"])

    def test_a_missing_tree_exits_two(self, exit_code_of: ExitCodeOf) -> None:
        assert exit_code_of({}, ["no/such/tree"]) == EXIT_ERROR

    def test_a_missing_search_tree_is_an_error(self, exit_code_of: ExitCodeOf) -> None:
        run = ["lib/python", "--search-in", "src", "--search-in", "no/such/tree"]
        assert exit_code_of(CLEAN_PROJECT, run) == EXIT_ERROR

    def test_unparseable_python_is_named(self, stderr_of: StderrOf) -> None:
        tree = {"lib/python/pkg/bad.py": "def broken(:\n"}
        assert "Syntax error in" in stderr_of(tree, ["lib/python"])

    def test_unparseable_python_does_not_stop_the_run(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/bad.py": "def broken(:\n",
                "lib/python/pkg/good.py": "def orphan():\n    pass\n",
            },
            ["lib/python"],
        )
        assert "orphan" in stdout

    def test_an_unparseable_search_file_falls_back_to_text(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "# orphan was called here\ndef broken(:\n",
            },
            ["lib/python", "--search-in", "lib/python", "--search-in", "src"],
        )
        assert stdout == ""

    def test_an_unparseable_search_file_is_named_verbosely(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "def broken(:\n",
            },
            ["lib/python", "--search-in", "lib/python", "--search-in", "src", "--verbose"],
        )
        assert "Searching as text (will not parse): src/bad.py" in stdout

    def test_an_unreadable_file_is_named(self, write_tree: WriteTree, run_cli: RunCli) -> None:
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, _, stderr = run_cli(["lib/python"])
        assert "Error reading" in stderr

    def test_an_unreadable_file_is_skipped_verbosely(
        self, write_tree: WriteTree, run_cli: RunCli
    ) -> None:
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Skipping (unreadable)" in stdout

    def test_an_unreadable_file_reports_an_error_verbosely(
        self, write_tree: WriteTree, run_cli: RunCli
    ) -> None:
        root = write_tree({"lib/python/pkg/__init__.py": "def kept():\n    pass\nkept()\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Errors occurred during scanning." in stdout


@pytest.mark.integration
class TestSelectingFiles:
    def test_a_directory_is_walked(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, ["lib/python", "--count"]) == "1\n"

    def test_a_file_can_be_named_directly(self, stdout_of: StdoutOf) -> None:
        named = os.path.join("lib", "python", "pkg", "__init__.py")
        assert stdout_of(PROJECT, [named, "--count"]) == "1\n"

    def test_a_recursive_glob_reaches_the_files(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, ["lib/python/**/*.py", "--count"]) == "1\n"

    def test_a_glob_matching_a_directory_is_walked(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(PROJECT, ["lib/python/*", "--count"]) == "1\n"

    def test_a_glob_matching_nothing_is_missing(self, stderr_of: StderrOf) -> None:
        assert "Path not found" in stderr_of(PROJECT, ["lib/python/*.rs"])

    def test_a_hidden_directory_is_not_walked(self, stdout_of: StdoutOf) -> None:
        buried = {**PROJECT, "lib/python/.tox/mod.py": "def buried():\n    pass\n"}
        assert "buried" not in stdout_of(buried, ["lib/python"])

    def test_a_non_python_file_is_ignored(self, stdout_of: StdoutOf) -> None:
        noted = {**PROJECT, "lib/python/pkg/notes.txt": "def orphan():\n"}
        assert stdout_of(noted, ["lib/python", "--count"]) == "1\n"

    def test_an_exclude_drops_a_definition_file(self, stdout_of: StdoutOf) -> None:
        run = ["lib/python", "--exclude", "__init__.py", "--count"]
        assert stdout_of(PROJECT, run) == "0\n"

    def test_an_exclude_drops_a_searched_file(self, stdout_of: StdoutOf) -> None:
        run = [*CLEAN_RUN, "--exclude", "app.py", "--count"]
        assert stdout_of(CLEAN_PROJECT, run) == "1\n"

    def test_several_trees_are_read_together(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def one():\n    pass\n",
                "scripts/tool.py": "def two():\n    pass\n",
            },
            ["lib/python", "scripts", "--count"],
        )
        assert stdout == "2\n"


@pytest.mark.integration
class TestAgainstARuntimeInvokedTree:
    def test_reports_every_definition_without_the_inputs(self, stdout_of: StdoutOf) -> None:
        assert stdout_of(RUNTIME_PROJECT, RUNTIME_RUN).count("\n") == 4

    def test_the_named_definitions_are_left_alone(self, stdout_of: StdoutOf) -> None:
        assert "test_it_reads_the_directory" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_hook_is_left_alone(self, stdout_of: StdoutOf) -> None:
        assert "pytest_configure" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_renamed_fixture_is_left_alone(self, stdout_of: StdoutOf) -> None:
        assert "bootstrap_dir_fixture" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_an_ordinary_definition_is_still_reported(self, stdout_of: StdoutOf) -> None:
        assert "spare" in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_verbose_summary_counts_both_grounds(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(RUNTIME_PROJECT, [*RUNTIME_ASSUMED, "--verbose"])
        assert "Assumed used by name: 2\nAssumed used by decorator: 1\n" in stdout

    def test_the_verbose_summary_is_unchanged_without_the_inputs(self, stdout_of: StdoutOf) -> None:
        stdout = stdout_of(RUNTIME_PROJECT, [*RUNTIME_RUN, "--verbose"])
        assert "Definitions read: 4\nFindings: 4\n" in stdout
