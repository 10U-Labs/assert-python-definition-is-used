"""Integration tests driving the CLI over real source trees."""

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
    """The tool run over a tree laid out the way a repository is."""

    def test_reports_the_definition_only_its_tests_name(self, stdout_of: StdoutOf) -> None:
        """A definition kept alive only by its own tests is reported."""
        assert "orphan" in stdout_of(PROJECT, FULL_RUN)

    def test_leaves_the_called_definition_alone(self, stdout_of: StdoutOf) -> None:
        """A definition another tree calls is not reported."""
        assert "kept" not in stdout_of(PROJECT, FULL_RUN)

    def test_leaves_the_helper_its_own_file_calls_alone(self, stdout_of: StdoutOf) -> None:
        """A helper the defining file calls is used, so it is not reported."""
        assert "helper" not in stdout_of(PROJECT, FULL_RUN)

    def test_reports_the_definition_its_own_file_only_mentions(self, stdout_of: StdoutOf) -> None:
        """A name its own file writes only in prose is not used by it."""
        assert "documented" in stdout_of({"lib/python/pkg/__init__.py": PROSE}, ["lib/python"])

    def test_without_the_flag_the_outer_bound_is_quiet_about_orphan(
        self, stdout_of: StdoutOf
    ) -> None:
        """The outer bound counts the module's own tests, so orphan reads as used."""
        assert "orphan" not in stdout_of(PROJECT, OUTER_BOUND)

    def test_findings_exit_one(self, exit_code_of: ExitCodeOf) -> None:
        """A run with findings exits one."""
        assert exit_code_of(PROJECT, FULL_RUN) == EXIT_FINDINGS

    def test_a_clean_tree_exits_zero(self, exit_code_of: ExitCodeOf) -> None:
        """A tree where everything is called exits zero."""
        assert exit_code_of(CLEAN_PROJECT, CLEAN_RUN) == EXIT_SUCCESS

    def test_reports_in_path_order(self, stdout_of: StdoutOf) -> None:
        """Findings come out sorted by the file they sit in."""
        stdout = stdout_of(
            {
                "lib/python/a/__init__.py": "def one():\n    pass\n",
                "lib/python/b/__init__.py": "def two():\n    pass\n",
            },
            ["lib/python"],
        )
        assert [line.split(":")[2] for line in stdout.splitlines()] == ["one", "two"]

    def test_a_loose_file_keeps_its_tests(self, stdout_of: StdoutOf) -> None:
        """A file directly in the tree has no package, so nothing is discounted."""
        stdout = stdout_of(
            {
                "lib/python/loose.py": "def solo():\n    pass\n",
                "test/lib/python/test_loose/test_it.py": "solo()\n",
            },
            LIB_AND_TEST_RUN,
        )
        assert stdout == ""

    def test_another_packages_tests_still_count(self, stdout_of: StdoutOf) -> None:
        """A fixture package used from another package's tests is in use."""
        stdout = stdout_of(
            {
                "lib/python/fixtures/__init__.py": "def helper():\n    pass\n",
                "test/lib/python/test_other/test_it.py": "helper()\n",
            },
            LIB_AND_TEST_RUN,
        )
        assert stdout == ""

    def test_a_private_definition_is_never_reported(self, stdout_of: StdoutOf) -> None:
        """Renaming with a leading underscore takes a definition out of scope."""
        tree = {"lib/python/pkg/__init__.py": "def _hidden():\n    pass\n"}
        assert stdout_of(tree, ["lib/python"]) == ""

    def test_a_method_is_never_reported(self, stdout_of: StdoutOf) -> None:
        """Only top-level definitions are in scope, so an unused method is not reported."""
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
    """The tool run over a tree where a note is all that names a definition."""

    def test_reports_the_definition_the_note_is_about(self, stdout_of: StdoutOf) -> None:
        """The comment that explains a removal no longer hides the removal."""
        assert "noted" in stdout_of(NOTED_PROJECT, CLEAN_RUN)

    def test_leaves_the_really_called_definition_alone(self, stdout_of: StdoutOf) -> None:
        """A real call still counts in a file that also holds a note."""
        assert "called" not in stdout_of(NOTED_PROJECT, CLEAN_RUN)

    def test_reports_only_what_is_dead(self, stdout_of: StdoutOf) -> None:
        """One finding, for the definition whose only call was commented out."""
        assert stdout_of(NOTED_PROJECT, CLEAN_RUN).splitlines() == [
            "lib/python/pkg/__init__.py:5:noted"
        ]

    def test_a_name_written_as_data_is_still_a_use(self, stdout_of: StdoutOf) -> None:
        """A route naming a view in a string reaches it, so the view is used."""
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
    """The tool run over a tree whose __all__ still advertises a dead name."""

    def test_reports_the_definition_only_the_export_list_names(self, stdout_of: StdoutOf) -> None:
        """An entry advertises a definition rather than using it."""
        assert "dropped" in stdout_of(ADVERTISING_PROJECT, CLEAN_RUN)

    def test_leaves_the_re_exported_definition_alone(self, stdout_of: StdoutOf) -> None:
        """The import beside an entry is a real use, so its name is kept."""
        assert "shown" not in stdout_of(ADVERTISING_PROJECT, CLEAN_RUN)


@pytest.mark.integration
class TestOutputModes:
    """The output the CLI produces over a real tree."""

    def test_quiet_says_nothing(self, stdout_of: StdoutOf) -> None:
        """Quiet mode prints nothing at all."""
        assert stdout_of(PROJECT, [*FULL_RUN, "--quiet"]) == ""

    def test_quiet_still_fails(self, exit_code_of: ExitCodeOf) -> None:
        """Quiet mode still reports through the exit code."""
        assert exit_code_of(PROJECT, [*FULL_RUN, "--quiet"]) == EXIT_FINDINGS

    def test_count_gives_a_number(self, stdout_of: StdoutOf) -> None:
        """Count mode prints how many findings there were."""
        assert stdout_of(PROJECT, [*FULL_RUN, "--count"]) == "1\n"

    def test_verbose_names_the_trees(self, stdout_of: StdoutOf) -> None:
        """Verbose mode says how many files it searched."""
        assert "Searching 3 file(s) for uses." in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_counts_the_files(self, stdout_of: StdoutOf) -> None:
        """Verbose mode says how many definition files it read."""
        assert "Files scanned: 1" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_names_each_scan(self, stdout_of: StdoutOf) -> None:
        """Verbose mode names each file as it is read."""
        scanned = os.path.join("lib", "python", "pkg", "__init__.py")
        assert f"Scanning: {scanned}" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_lists_the_findings(self, stdout_of: StdoutOf) -> None:
        """Verbose mode names every unused definition."""
        assert "Unused:" in stdout_of(PROJECT, [*FULL_RUN, "--verbose"])

    def test_verbose_names_the_excludes(self, stdout_of: StdoutOf) -> None:
        """Verbose mode repeats the exclude patterns it was given."""
        run = [*FULL_RUN, "--verbose", "--exclude", "app.py"]
        assert "Excluding patterns: app.py" in stdout_of(PROJECT, run)

    def test_fail_fast_stops_at_one(self, stdout_of: StdoutOf) -> None:
        """Failing fast reports a single finding."""
        assert stdout_of(PROJECT, [*FULL_RUN, "--fail-fast", "--count"]) == "1\n"

    def test_warn_only_succeeds(self, exit_code_of: ExitCodeOf) -> None:
        """Warn-only reports but does not fail."""
        assert exit_code_of(PROJECT, [*FULL_RUN, "--warn-only"]) == EXIT_SUCCESS


@pytest.mark.integration
class TestBrokenInput:
    """What the CLI does with trees it cannot read."""

    def test_a_missing_tree_is_named(self, stderr_of: StderrOf) -> None:
        """A tree that does not exist is reported on stderr."""
        assert "Path not found: no/such/tree" in stderr_of({}, ["no/such/tree"])

    def test_a_missing_tree_exits_two(self, exit_code_of: ExitCodeOf) -> None:
        """A run that read no definitions at all is an error."""
        assert exit_code_of({}, ["no/such/tree"]) == EXIT_ERROR

    def test_a_missing_search_tree_is_an_error(self, exit_code_of: ExitCodeOf) -> None:
        """A search tree that does not exist marks the run."""
        run = ["lib/python", "--search-in", "src", "--search-in", "no/such/tree"]
        assert exit_code_of(CLEAN_PROJECT, run) == EXIT_ERROR

    def test_unparseable_python_is_named(self, stderr_of: StderrOf) -> None:
        """A file that will not parse is reported on stderr."""
        tree = {"lib/python/pkg/bad.py": "def broken(:\n"}
        assert "Syntax error in" in stderr_of(tree, ["lib/python"])

    def test_unparseable_python_does_not_stop_the_run(self, stdout_of: StdoutOf) -> None:
        """A bad file is passed over and the good ones are still read."""
        stdout = stdout_of(
            {
                "lib/python/pkg/bad.py": "def broken(:\n",
                "lib/python/pkg/good.py": "def orphan():\n    pass\n",
            },
            ["lib/python"],
        )
        assert "orphan" in stdout

    def test_an_unparseable_search_file_falls_back_to_text(self, stdout_of: StdoutOf) -> None:
        """A file the parser cannot read is searched as text, prose and all."""
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "# orphan was called here\ndef broken(:\n",
            },
            ["lib/python", "--search-in", "lib/python", "--search-in", "src"],
        )
        assert stdout == ""

    def test_an_unparseable_search_file_is_named_verbosely(self, stdout_of: StdoutOf) -> None:
        """Verbose mode names the file running the blunt rule, so it is visible."""
        stdout = stdout_of(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "def broken(:\n",
            },
            ["lib/python", "--search-in", "lib/python", "--search-in", "src", "--verbose"],
        )
        assert "Searching as text (will not parse): src/bad.py" in stdout

    def test_an_unreadable_file_is_named(self, write_tree: WriteTree, run_cli: RunCli) -> None:
        """A path that ends in .py but is a directory cannot be read."""
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, _, stderr = run_cli(["lib/python"])
        assert "Error reading" in stderr

    def test_an_unreadable_file_is_skipped_verbosely(
        self, write_tree: WriteTree, run_cli: RunCli
    ) -> None:
        """Verbose mode says an unreadable file was skipped."""
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Skipping (unreadable)" in stdout

    def test_an_unreadable_file_reports_an_error_verbosely(
        self, write_tree: WriteTree, run_cli: RunCli
    ) -> None:
        """Verbose mode ends by saying something went wrong."""
        root = write_tree({"lib/python/pkg/__init__.py": "def kept():\n    pass\nkept()\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Errors occurred during scanning." in stdout


@pytest.mark.integration
class TestSelectingFiles:
    """How trees, globs and excludes choose the files read."""

    def test_a_directory_is_walked(self, stdout_of: StdoutOf) -> None:
        """A directory reaches the files below it."""
        assert stdout_of(PROJECT, ["lib/python", "--count"]) == "1\n"

    def test_a_file_can_be_named_directly(self, stdout_of: StdoutOf) -> None:
        """A single file is a tree of one."""
        named = os.path.join("lib", "python", "pkg", "__init__.py")
        assert stdout_of(PROJECT, [named, "--count"]) == "1\n"

    def test_a_recursive_glob_reaches_the_files(self, stdout_of: StdoutOf) -> None:
        """A recursive pattern reaches the same files a directory does."""
        assert stdout_of(PROJECT, ["lib/python/**/*.py", "--count"]) == "1\n"

    def test_a_glob_matching_a_directory_is_walked(self, stdout_of: StdoutOf) -> None:
        """A pattern matching a directory reaches the files inside it."""
        assert stdout_of(PROJECT, ["lib/python/*", "--count"]) == "1\n"

    def test_a_glob_matching_nothing_is_missing(self, stderr_of: StderrOf) -> None:
        """A pattern that matches no file is reported as missing."""
        assert "Path not found" in stderr_of(PROJECT, ["lib/python/*.rs"])

    def test_a_hidden_directory_is_not_walked(self, stdout_of: StdoutOf) -> None:
        """A dot directory holds nothing the walk reaches."""
        buried = {**PROJECT, "lib/python/.tox/mod.py": "def buried():\n    pass\n"}
        assert "buried" not in stdout_of(buried, ["lib/python"])

    def test_a_non_python_file_is_ignored(self, stdout_of: StdoutOf) -> None:
        """A file that is not Python is not parsed."""
        noted = {**PROJECT, "lib/python/pkg/notes.txt": "def orphan():\n"}
        assert stdout_of(noted, ["lib/python", "--count"]) == "1\n"

    def test_an_exclude_drops_a_definition_file(self, stdout_of: StdoutOf) -> None:
        """An excluded file yields no definitions."""
        run = ["lib/python", "--exclude", "__init__.py", "--count"]
        assert stdout_of(PROJECT, run) == "0\n"

    def test_an_exclude_drops_a_searched_file(self, stdout_of: StdoutOf) -> None:
        """Excluding the caller makes the definition it calls look unused."""
        run = [*CLEAN_RUN, "--exclude", "app.py", "--count"]
        assert stdout_of(CLEAN_PROJECT, run) == "1\n"

    def test_several_trees_are_read_together(self, stdout_of: StdoutOf) -> None:
        """Definitions come from every tree named."""
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
    """The tool run over definitions a runtime invokes rather than Python."""

    def test_reports_every_definition_without_the_inputs(self, stdout_of: StdoutOf) -> None:
        """A pytest tree has no call sites, so today it is refused whole."""
        assert stdout_of(RUNTIME_PROJECT, RUNTIME_RUN).count("\n") == 4

    def test_the_named_definitions_are_left_alone(self, stdout_of: StdoutOf) -> None:
        """A definition a name pattern claims is not reported."""
        assert "test_it_reads_the_directory" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_hook_is_left_alone(self, stdout_of: StdoutOf) -> None:
        """A plugin hook the manager calls is claimed by its prefix."""
        assert "pytest_configure" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_renamed_fixture_is_left_alone(self, stdout_of: StdoutOf) -> None:
        """A fixture asked for under another name is claimed by its decorator."""
        assert "bootstrap_dir_fixture" not in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_an_ordinary_definition_is_still_reported(self, stdout_of: StdoutOf) -> None:
        """A definition neither input claims is searched for as before."""
        assert "spare" in stdout_of(RUNTIME_PROJECT, RUNTIME_ASSUMED)

    def test_the_verbose_summary_counts_both_grounds(self, stdout_of: StdoutOf) -> None:
        """Verbose says how many were claimed by name and how many by decorator."""
        stdout = stdout_of(RUNTIME_PROJECT, [*RUNTIME_ASSUMED, "--verbose"])
        assert "Assumed used by name: 2\nAssumed used by decorator: 1\n" in stdout

    def test_the_verbose_summary_is_unchanged_without_the_inputs(self, stdout_of: StdoutOf) -> None:
        """A run naming nothing prints the summary it always printed."""
        stdout = stdout_of(RUNTIME_PROJECT, [*RUNTIME_RUN, "--verbose"])
        assert "Definitions read: 4\nFindings: 4\n" in stdout
