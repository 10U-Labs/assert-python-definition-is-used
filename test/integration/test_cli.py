"""Integration tests driving the CLI over real source trees."""

from __future__ import annotations

import os
from test.samples import (
    ADVERTISING_PROJECT,
    CLEAN_PROJECT,
    CLEAN_RUN,
    FULL_RUN,
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
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.integration
class TestAgainstARealTree:
    """The tool run over a tree laid out the way a repository is."""

    def test_reports_the_definition_only_its_tests_name(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition kept alive only by its own tests is reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(FULL_RUN)
        assert "orphan" in stdout

    def test_leaves_the_called_definition_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition another tree calls is not reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(FULL_RUN)
        assert "kept" not in stdout

    def test_leaves_the_helper_its_own_file_calls_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A helper the defining file calls is used, so it is not reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(FULL_RUN)
        assert "helper" not in stdout

    def test_reports_the_definition_its_own_file_only_mentions(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A name its own file writes only in prose is not used by it."""
        write_tree({"lib/python/pkg/__init__.py": PROSE})
        _, stdout, _ = run_cli(["lib/python"])
        assert "documented" in stdout

    def test_without_the_flag_the_outer_bound_is_quiet_about_orphan(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """The outer bound counts the module's own tests, so orphan reads as used."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(OUTER_BOUND)
        assert "orphan" not in stdout

    def test_findings_exit_one(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A run with findings exits one."""
        write_tree(PROJECT)
        exit_code, _, _ = run_cli(FULL_RUN)
        assert exit_code == EXIT_FINDINGS

    def test_a_clean_tree_exits_zero(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A tree where everything is called exits zero."""
        write_tree(CLEAN_PROJECT)
        exit_code, _, _ = run_cli(CLEAN_RUN)
        assert exit_code == EXIT_SUCCESS

    def test_reports_in_path_order(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Findings come out sorted by the file they sit in."""
        write_tree(
            {
                "lib/python/a/__init__.py": "def one():\n    pass\n",
                "lib/python/b/__init__.py": "def two():\n    pass\n",
            }
        )
        _, stdout, _ = run_cli(["lib/python"])
        assert [line.split(":")[2] for line in stdout.splitlines()] == ["one", "two"]

    def test_a_loose_file_keeps_its_tests(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A file directly in the tree has no package, so nothing is discounted."""
        write_tree(
            {
                "lib/python/loose.py": "def solo():\n    pass\n",
                "test/lib/python/test_loose/test_it.py": "solo()\n",
            }
        )
        _, stdout, _ = run_cli(
            ["lib/python", "--search-in", "lib/python", "--search-in", "test",
             "--dont-search-in", "test/lib/python/test_{package}"]
        )
        assert stdout == ""

    def test_another_packages_tests_still_count(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A fixture package used from another package's tests is in use."""
        write_tree(
            {
                "lib/python/fixtures/__init__.py": "def helper():\n    pass\n",
                "test/lib/python/test_other/test_it.py": "helper()\n",
            }
        )
        _, stdout, _ = run_cli(
            ["lib/python", "--search-in", "lib/python", "--search-in", "test",
             "--dont-search-in", "test/lib/python/test_{package}"]
        )
        assert stdout == ""

    def test_a_private_definition_is_never_reported(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Renaming with a leading underscore takes a definition out of scope."""
        write_tree({"lib/python/pkg/__init__.py": "def _hidden():\n    pass\n"})
        _, stdout, _ = run_cli(["lib/python"])
        assert stdout == ""

    def test_a_method_is_never_reported(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Only top-level definitions are in scope, so an unused method is not reported."""
        write_tree(
            {
                "lib/python/pkg/__init__.py": "class Kept:\n    def spin(self):\n        pass\n",
                "src/app.py": "Kept()\n",
            }
        )
        _, stdout, _ = run_cli(["lib/python", "--search-in", "lib/python", "--search-in", "src"])
        assert stdout == ""


@pytest.mark.integration
class TestAgainstATreeHoldingANote:
    """The tool run over a tree where a note is all that names a definition."""

    def test_reports_the_definition_the_note_is_about(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """The comment that explains a removal no longer hides the removal."""
        write_tree(NOTED_PROJECT)
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert "noted" in stdout

    def test_leaves_the_really_called_definition_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A real call still counts in a file that also holds a note."""
        write_tree(NOTED_PROJECT)
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert "called" not in stdout

    def test_reports_only_what_is_dead(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """One finding, for the definition whose only call was commented out."""
        write_tree(NOTED_PROJECT)
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert stdout.splitlines() == ["lib/python/pkg/__init__.py:5:noted"]

    def test_a_name_written_as_data_is_still_a_use(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A route naming a view in a string reaches it, so the view is used."""
        write_tree(
            {
                "lib/python/pkg/__init__.py": "def handle_login():\n    return 1\n",
                "src/app.py": 'urlpatterns = ["views.handle_login"]\n',
            }
        )
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert stdout == ""


@pytest.mark.integration
class TestAgainstAStaleExportList:
    """The tool run over a tree whose __all__ still advertises a dead name."""

    def test_reports_the_definition_only_the_export_list_names(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """An entry advertises a definition rather than using it."""
        write_tree(ADVERTISING_PROJECT)
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert "dropped" in stdout

    def test_leaves_the_re_exported_definition_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """The import beside an entry is a real use, so its name is kept."""
        write_tree(ADVERTISING_PROJECT)
        _, stdout, _ = run_cli(CLEAN_RUN)
        assert "shown" not in stdout


@pytest.mark.integration
class TestOutputModes:
    """The output the CLI produces over a real tree."""

    def test_quiet_says_nothing(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Quiet mode prints nothing at all."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--quiet"])
        assert stdout == ""

    def test_quiet_still_fails(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Quiet mode still reports through the exit code."""
        write_tree(PROJECT)
        exit_code, _, _ = run_cli([*FULL_RUN, "--quiet"])
        assert exit_code == EXIT_FINDINGS

    def test_count_gives_a_number(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Count mode prints how many findings there were."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--count"])
        assert stdout == "1\n"

    def test_verbose_names_the_trees(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says how many files it searched."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose"])
        assert "Searching 3 file(s) for uses." in stdout

    def test_verbose_counts_the_files(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says how many definition files it read."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose"])
        assert "Files scanned: 1" in stdout

    def test_verbose_names_each_scan(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode names each file as it is read."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose"])
        assert f"Scanning: {os.path.join('lib', 'python', 'pkg', '__init__.py')}" in stdout

    def test_verbose_lists_the_findings(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode names every unused definition."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose"])
        assert "Unused:" in stdout

    def test_verbose_names_the_excludes(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode repeats the exclude patterns it was given."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose", "--exclude", "app.py"])
        assert "Excluding patterns: app.py" in stdout

    def test_fail_fast_stops_at_one(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Failing fast reports a single finding."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--fail-fast", "--count"])
        assert stdout == "1\n"

    def test_warn_only_succeeds(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Warn-only reports but does not fail."""
        write_tree(PROJECT)
        exit_code, _, _ = run_cli([*FULL_RUN, "--warn-only"])
        assert exit_code == EXIT_SUCCESS


@pytest.mark.integration
class TestBrokenInput:
    """What the CLI does with trees it cannot read."""

    def test_a_missing_tree_is_named(
        self, run_cli: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """A tree that does not exist is reported on stderr."""
        _, _, stderr = run_cli(["no/such/tree"])
        assert "Path not found: no/such/tree" in stderr

    def test_a_missing_tree_exits_two(
        self, run_cli: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """A run that read no definitions at all is an error."""
        exit_code, _, _ = run_cli(["no/such/tree"])
        assert exit_code == EXIT_ERROR

    def test_a_missing_search_tree_is_an_error(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A search tree that does not exist marks the run."""
        write_tree(CLEAN_PROJECT)
        exit_code, _, _ = run_cli(
            ["lib/python", "--search-in", "src", "--search-in", "no/such/tree"]
        )
        assert exit_code == EXIT_ERROR

    def test_unparseable_python_is_named(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A file that will not parse is reported on stderr."""
        write_tree({"lib/python/pkg/bad.py": "def broken(:\n"})
        _, _, stderr = run_cli(["lib/python"])
        assert "Syntax error in" in stderr

    def test_unparseable_python_does_not_stop_the_run(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A bad file is passed over and the good ones are still read."""
        write_tree({"lib/python/pkg/bad.py": "def broken(:\n",
                    "lib/python/pkg/good.py": "def orphan():\n    pass\n"})
        _, stdout, _ = run_cli(["lib/python"])
        assert "orphan" in stdout

    def test_an_unparseable_search_file_falls_back_to_text(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A file the parser cannot read is searched as text, prose and all."""
        write_tree(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "# orphan was called here\ndef broken(:\n",
            }
        )
        _, stdout, _ = run_cli(["lib/python", "--search-in", "lib/python", "--search-in", "src"])
        assert stdout == ""

    def test_an_unparseable_search_file_is_named_verbosely(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode names the file running the blunt rule, so it is visible."""
        write_tree(
            {
                "lib/python/pkg/__init__.py": "def orphan():\n    pass\n",
                "src/bad.py": "def broken(:\n",
            }
        )
        _, stdout, _ = run_cli(
            ["lib/python", "--search-in", "lib/python", "--search-in", "src", "--verbose"]
        )
        assert "Searching as text (will not parse): src/bad.py" in stdout

    def test_an_unreadable_file_is_named(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A path that ends in .py but is a directory cannot be read."""
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, _, stderr = run_cli(["lib/python"])
        assert "Error reading" in stderr

    def test_an_unreadable_file_is_skipped_verbosely(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says an unreadable file was skipped."""
        root = write_tree({"lib/python/pkg/__init__.py": "def orphan():\n    pass\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Skipping (unreadable)" in stdout

    def test_an_unreadable_file_reports_an_error_verbosely(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode ends by saying something went wrong."""
        root = write_tree({"lib/python/pkg/__init__.py": "def kept():\n    pass\nkept()\n"})
        os.symlink("nowhere", root / "lib" / "python" / "pkg" / "broken.py")
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Errors occurred during scanning." in stdout


@pytest.mark.integration
class TestSelectingFiles:
    """How trees, globs and excludes choose the files read."""

    def test_a_directory_is_walked(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A directory reaches the files below it."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python", "--count"])
        assert stdout == "1\n"

    def test_a_file_can_be_named_directly(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A single file is a tree of one."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([os.path.join("lib", "python", "pkg", "__init__.py"), "--count"])
        assert stdout == "1\n"

    def test_a_recursive_glob_reaches_the_files(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A recursive pattern reaches the same files a directory does."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python/**/*.py", "--count"])
        assert stdout == "1\n"

    def test_a_glob_matching_a_directory_is_walked(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A pattern matching a directory reaches the files inside it."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python/*", "--count"])
        assert stdout == "1\n"

    def test_a_glob_matching_nothing_is_missing(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A pattern that matches no file is reported as missing."""
        write_tree(PROJECT)
        _, _, stderr = run_cli(["lib/python/*.rs"])
        assert "Path not found" in stderr

    def test_a_hidden_directory_is_not_walked(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A dot directory holds nothing the walk reaches."""
        write_tree({**PROJECT, "lib/python/.tox/mod.py": "def buried():\n    pass\n"})
        _, stdout, _ = run_cli(["lib/python"])
        assert "buried" not in stdout

    def test_a_non_python_file_is_ignored(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A file that is not Python is not parsed."""
        write_tree({**PROJECT, "lib/python/pkg/notes.txt": "def orphan():\n"})
        _, stdout, _ = run_cli(["lib/python", "--count"])
        assert stdout == "1\n"

    def test_an_exclude_drops_a_definition_file(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """An excluded file yields no definitions."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python", "--exclude", "__init__.py", "--count"])
        assert stdout == "0\n"

    def test_an_exclude_drops_a_searched_file(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Excluding the caller makes the definition it calls look unused."""
        write_tree(CLEAN_PROJECT)
        _, stdout, _ = run_cli([*CLEAN_RUN, "--exclude", "app.py", "--count"])
        assert stdout == "1\n"

    def test_several_trees_are_read_together(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Definitions come from every tree named."""
        write_tree({"lib/python/pkg/__init__.py": "def one():\n    pass\n",
                    "scripts/tool.py": "def two():\n    pass\n"})
        _, stdout, _ = run_cli(["lib/python", "scripts", "--count"])
        assert stdout == "2\n"


@pytest.mark.integration
class TestAgainstARuntimeInvokedTree:
    """The tool run over definitions a runtime invokes rather than Python."""

    def test_reports_every_definition_without_the_inputs(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A pytest tree has no call sites, so today it is refused whole."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli(RUNTIME_RUN)
        assert stdout.count("\n") == 4

    def test_the_named_definitions_are_left_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition a name pattern claims is not reported."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli(RUNTIME_ASSUMED)
        assert "test_it_reads_the_directory" not in stdout

    def test_the_hook_is_left_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A plugin hook the manager calls is claimed by its prefix."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli(RUNTIME_ASSUMED)
        assert "pytest_configure" not in stdout

    def test_the_renamed_fixture_is_left_alone(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A fixture asked for under another name is claimed by its decorator."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli(RUNTIME_ASSUMED)
        assert "bootstrap_dir_fixture" not in stdout

    def test_an_ordinary_definition_is_still_reported(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition neither input claims is searched for as before."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli(RUNTIME_ASSUMED)
        assert "spare" in stdout

    def test_the_verbose_summary_counts_both_grounds(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose says how many were claimed by name and how many by decorator."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli([*RUNTIME_ASSUMED, "--verbose"])
        assert "Assumed used by name: 2\nAssumed used by decorator: 1\n" in stdout

    def test_the_verbose_summary_is_unchanged_without_the_inputs(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A run naming nothing prints the summary it always printed."""
        write_tree(RUNTIME_PROJECT)
        _, stdout, _ = run_cli([*RUNTIME_RUN, "--verbose"])
        assert "Definitions read: 4\nFindings: 4\n" in stdout
