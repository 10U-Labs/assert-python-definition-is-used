"""Integration tests driving the CLI over real source trees."""

from __future__ import annotations

import os
import runpy
import sys
from test.samples import (
    CALLER,
    CLEAN_PROJECT,
    CLEAN_RUN,
    FULL_RUN,
    LIBRARY,
    OUTER_BOUND,
    PROJECT,
    PROSE,
    RUNTIME_ASSUMED,
    RUNTIME_INVOKED,
    RUNTIME_PROJECT,
    RUNTIME_RUN,
)
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from assert_python_definition_is_used.cli import (
    _collect,
    _expand,
    _is_glob_pattern,
    _read,
    _tree_root,
    _walk_python_files,
)
from assert_python_definition_is_used.cli import (
    EXIT_ERROR,
    EXIT_FINDINGS,
    EXIT_SUCCESS,
    ScanResult,
    assume_used,
    create_parser,
    determine_exit_code,
    output_findings,
    package_of,
    parse_patterns,
    read_definitions,
    read_sources,
    should_skip,
)
from assert_python_definition_is_used.scanner import (
    Definition,
    Finding,
    assumed_used,
    is_assumed_used_by_decorator,
    is_assumed_used_by_name,
    is_public,
    is_used,
    names_in_code,
    names_in_text,
    unsearched_directory,
    public_definitions,
    unused_definitions,
)

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
class TestHelpersOverRealFiles:
    """The functions behind the CLI, exercised against files on disk."""

    def test_walk_finds_the_python_files(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Walking a directory finds the Python below it."""
        write_tree(PROJECT)
        assert len(_walk_python_files("lib/python")) == 1

    def test_expand_reports_a_directory_matched(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A directory that exists reports as matched."""
        write_tree(PROJECT)
        assert _expand("lib/python")[1] is True

    def test_expand_skips_a_broken_link(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A pattern matching neither a file nor a directory yields nothing."""
        root = write_tree(PROJECT)
        os.symlink("nowhere", root / "src" / "broken.py")
        assert not _expand("src/broken.py*")[0]

    def test_expand_reports_a_missing_path(self) -> None:
        """A path that does not exist reports as unmatched."""
        assert _expand("no/such/path")[1] is False

    def test_collect_maps_files_to_their_tree(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Collecting keeps the tree each file was found under."""
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        assert set(collected.values()) == {"lib/python"}

    def test_collect_reports_what_is_missing(self) -> None:
        """Collecting reports the paths that named nothing."""
        assert _collect(["no/such/path"], [])[1] == ["no/such/path"]

    def test_read_sources_reads_the_files(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Reading returns the text of every file collected."""
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        assert list(read_sources(collected, ScanResult()).values()) == [LIBRARY]

    def test_read_returns_the_text(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """Reading one file returns its text."""
        write_tree(PROJECT)
        assert _read(os.path.join("src", "app.py"), ScanResult(), False) == CALLER

    def test_read_marks_an_unreadable_file(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A directory named like a module cannot be read."""
        root = write_tree(PROJECT)
        os.symlink("nowhere", root / "broken.py")
        result = ScanResult()
        _read("broken.py", result, False)
        assert result.had_error is True

    def test_read_definitions_skips_what_was_not_read(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A file missing from the sources yields no definitions."""
        write_tree(PROJECT)
        assert not read_definitions({"gone.py": "."}, {}, ScanResult())

    def test_read_definitions_finds_them(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Every public definition in the tree is found."""
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        found = read_definitions(collected, read_sources(collected, ScanResult()), ScanResult())
        assert [item.name for item in found] == ["kept", "orphan", "helper"]

    def test_read_definitions_names_files_when_verbose(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verbose reading names the file it is on."""
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        read_definitions(collected, read_sources(collected, ScanResult()), ScanResult(), True)
        assert "Scanning:" in capsys.readouterr().out


@pytest.mark.integration
class TestPathHelpers:
    """The path helpers behind the CLI."""

    def test_package_of_reads_the_tree(self) -> None:
        """The package is the first component below the tree."""
        assert package_of(os.path.join("lib", "python", "pkg", "mod.py"), "lib/python") == "pkg"

    def test_package_of_a_loose_file_is_none(self) -> None:
        """A file directly in the tree belongs to no package."""
        assert package_of(os.path.join("lib", "python", "mod.py"), "lib/python") is None

    def test_package_of_an_outside_file_is_none(self) -> None:
        """A file that is not under the tree belongs to no package."""
        assert package_of(os.path.join("other", "mod.py"), "lib/python") is None

    def test_tree_root_of_a_directory(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A directory is its own root."""
        write_tree(PROJECT)
        assert _tree_root("lib/python") == "lib/python"

    def test_tree_root_of_a_glob(self) -> None:
        """A pattern reduces to the directory before its wildcard."""
        assert _tree_root("lib/python/**/*.py") == "lib/python"

    def test_tree_root_of_a_bare_glob(self) -> None:
        """A pattern with no directory hangs from the current one."""
        assert _tree_root("*.py") == "."

    def test_is_glob_pattern_reads_a_star(self) -> None:
        """A star marks a pattern."""
        assert _is_glob_pattern("*.py") is True

    def test_is_glob_pattern_reads_a_plain_path(self) -> None:
        """A plain path is not a pattern."""
        assert _is_glob_pattern("lib/python") is False

    def test_should_skip_matches(self) -> None:
        """A matching pattern excludes the file."""
        assert should_skip("lib/python/pkg/mod.py", ["mod.py"]) is True

    def test_should_skip_leaves_others(self) -> None:
        """A pattern matching nothing excludes nothing."""
        assert should_skip("lib/python/pkg/mod.py", ["other.py"]) is False

    def test_parse_patterns_splits(self) -> None:
        """Patterns are split on commas."""
        assert parse_patterns("a,b") == ["a", "b"]

    def test_parse_patterns_of_nothing(self) -> None:
        """No patterns is an empty list."""
        assert parse_patterns(None) == []

    def test_create_parser_reads_a_tree(self) -> None:
        """The parser keeps the trees it is given."""
        assert create_parser().parse_args(["lib"]).trees == ["lib"]


@pytest.mark.integration
class TestReportingHelpers:
    """The helpers that turn a result into output and an exit code."""

    def test_output_findings_prints(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Findings print one per line."""
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        output_findings([Finding(definition=definition)])
        assert capsys.readouterr().out == "a.py:1:orphan\n"

    def test_output_findings_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Count mode prints only the number."""
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        output_findings([Finding(definition=definition)], count_mode=True)
        assert capsys.readouterr().out == "1\n"

    def test_determine_exit_code_for_findings(self) -> None:
        """Findings mean exit one."""
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        result = ScanResult(findings=[Finding(definition=definition)])
        assert determine_exit_code(result) == EXIT_FINDINGS

    def test_determine_exit_code_for_errors(self) -> None:
        """An error alone means exit two."""
        assert determine_exit_code(ScanResult(had_error=True)) == EXIT_ERROR

    def test_determine_exit_code_for_success(self) -> None:
        """A clean result means exit zero."""
        assert determine_exit_code(ScanResult()) == EXIT_SUCCESS

    def test_running_the_package_as_a_module_calls_the_cli(self) -> None:
        """Executing the package as a module runs the CLI."""
        with patch("assert_python_definition_is_used.cli.main") as entry_point:
            sys.modules.pop("assert_python_definition_is_used.__main__", None)
            runpy.run_module("assert_python_definition_is_used", run_name="__main__")
            assert entry_point.called

    def test_determine_exit_code_warn_only(self) -> None:
        """Warn-only always means exit zero."""
        assert determine_exit_code(ScanResult(had_error=True), warn_only=True) == EXIT_SUCCESS


@pytest.mark.integration
class TestScannerOverRealFiles:
    """The scanner functions, exercised against text read from disk."""

    def test_public_definitions_reads_a_file(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Parsing a real file finds its definitions."""
        write_tree(PROJECT)
        path = os.path.join("lib", "python", "pkg", "__init__.py")
        found = public_definitions(path, _read(path, ScanResult(), False) or "", "pkg")
        assert [item.name for item in found] == ["kept", "orphan", "helper"]

    def test_public_definitions_raises_on_bad_python(self) -> None:
        """Content that will not parse raises."""
        with pytest.raises(SyntaxError):
            public_definitions("bad.py", "def broken(:\n")

    def test_is_public_reads_a_plain_name(self) -> None:
        """A plain name is public."""
        assert is_public("kept") is True

    def test_is_public_reads_an_underscore(self) -> None:
        """A leading underscore is not public."""
        assert is_public("_kept") is False

    def test_names_in_text_matches_a_word(self) -> None:
        """A whole word in the text is a match."""
        assert names_in_text("kept", "kept()") is True

    def test_names_in_text_ignores_a_substring(self) -> None:
        """Part of a longer word is not a match."""
        assert names_in_text("kept", "keptic()") is False

    def test_names_in_text_reads_every_line(self) -> None:
        """Any line naming it is enough."""
        assert names_in_text("kept", CALLER) is True

    def test_names_in_code_reads_a_call(self) -> None:
        """A call in the file's code is a use."""
        assert names_in_code("kept", LIBRARY) is True

    def test_names_in_code_ignores_a_definition(self) -> None:
        """A def binds its name without reading it."""
        assert names_in_code("orphan", "def orphan():\n    pass\n") is False

    def test_unsearched_directory_renders(self) -> None:
        """The package is substituted in."""
        assert unsearched_directory("test/{package}", "pkg") == "test/pkg/"

    def test_unsearched_directory_without_a_package(self) -> None:
        """No package means no directory."""
        assert unsearched_directory("test/{package}", None) is None

    def test_is_used_reads_the_sources(self) -> None:
        """A name in another file is a use."""
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=1, name="kept",
                                package="pkg")
        assert is_used(definition, {"lib/python/pkg/__init__.py": LIBRARY, "src/app.py": CALLER})

    def test_a_finding_exposes_its_path(self) -> None:
        """A finding reads its path from the definition it holds."""
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).path == "lib/python/pkg/__init__.py"

    def test_a_finding_exposes_its_line(self) -> None:
        """A finding reads its line from the definition it holds."""
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).line_number == 5

    def test_a_finding_exposes_its_name(self) -> None:
        """A finding reads its name from the definition it holds."""
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).name == "orphan"

    def test_unused_definitions_reports(self) -> None:
        """A definition nothing names is reported."""
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        found = unused_definitions([definition], {"lib/python/pkg/__init__.py": LIBRARY})
        assert len(found) == 1


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


@pytest.mark.integration
class TestAssumptionsOverRealFiles:
    """The assumption rules, exercised against text read from disk."""

    def test_public_definitions_reads_the_decorators(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Parsing a real file records the decorators each definition carries."""
        write_tree(RUNTIME_PROJECT)
        path = os.path.join("test", "pkg", "test_pkg.py")
        found = public_definitions(path, _read(path, ScanResult(), False) or "", "pkg")
        assert found[0].decorators == ("pytest.fixture",)

    def test_public_definitions_leaves_a_plain_definition_bare(self) -> None:
        """A definition with no decorator line carries none."""
        assert public_definitions("a.py", RUNTIME_INVOKED)[1].decorators == ()

    def test_public_definitions_drops_an_unflattenable_decorator(self) -> None:
        """A decorator read out of a subscript is left out rather than raising."""
        found = public_definitions("a.py", '@table["a"]\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_public_definitions_reads_a_bare_decorator(self) -> None:
        """A one-word decorator flattens to that word."""
        found = public_definitions("a.py", "@task\ndef widget():\n    pass\n")
        assert found[0].decorators == ("task",)

    def test_is_assumed_used_by_name_matches_a_glob(self) -> None:
        """A pattern the name matches claims it."""
        assert is_assumed_used_by_name("pytest_configure", ["pytest_*"]) is True

    def test_is_assumed_used_by_name_leaves_the_rest(self) -> None:
        """A name no pattern matches is left to the search."""
        assert is_assumed_used_by_name("spare", ["pytest_*"]) is False

    def test_is_assumed_used_by_decorator_matches_a_path(self) -> None:
        """A decorator the caller named claims the definition."""
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["pytest.fixture"]) is True

    def test_is_assumed_used_by_decorator_leaves_the_rest(self) -> None:
        """A definition carrying no named decorator is left to the search."""
        assert is_assumed_used_by_decorator([], ["pytest.fixture"]) is False

    def test_assumed_used_splits_on_the_name(self) -> None:
        """A definition a pattern names is counted against its name."""
        held = public_definitions("a.py", RUNTIME_INVOKED)
        _, by_name, _ = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in by_name] == ["pytest_configure",
                                                   "test_it_reads_the_directory"]

    def test_assumed_used_splits_on_the_decorator(self) -> None:
        """A definition carrying a named decorator is counted against it."""
        held = public_definitions("a.py", RUNTIME_INVOKED)
        _, _, by_decorator = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in by_decorator] == ["bootstrap_dir_fixture"]

    def test_assumed_used_keeps_the_rest(self) -> None:
        """What neither input claims still goes to the search."""
        held = public_definitions("a.py", RUNTIME_INVOKED)
        checked, _, _ = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in checked] == ["spare"]

    def test_assumed_used_claims_nothing_by_default(self) -> None:
        """Empty inputs leave every definition to the search."""
        held = public_definitions("a.py", RUNTIME_INVOKED)
        assert assumed_used(held, [], []) == (held, [], [])

    def test_assume_used_counts_the_names(self) -> None:
        """The CLI helper records how many a name pattern claimed."""
        result = ScanResult()
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, result)
        assert result.assumed_by_name == 2

    def test_assume_used_counts_the_decorators(self) -> None:
        """The CLI helper records how many a decorator path claimed."""
        result = ScanResult()
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, result)
        assert result.assumed_by_decorator == 1

    def test_assume_used_returns_what_is_left(self) -> None:
        """The CLI helper hands back the definitions still to search for."""
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        left = assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, ScanResult())
        assert [item.name for item in left] == ["spare"]

    def test_the_parser_reads_the_name_patterns(self) -> None:
        """The name patterns reach the namespace."""
        assert create_parser().parse_args(RUNTIME_ASSUMED).assume_used_matching == "test_*,pytest_*"

    def test_the_parser_reads_the_decorator_paths(self) -> None:
        """The decorator paths reach the namespace."""
        parsed = create_parser().parse_args(RUNTIME_ASSUMED)
        assert parsed.assume_used_decorated_with == "pytest.fixture"

    def test_the_parser_defaults_both_to_none(self) -> None:
        """A run naming neither leaves both unset."""
        parsed = create_parser().parse_args(RUNTIME_RUN)
        assert (parsed.assume_used_matching, parsed.assume_used_decorated_with) == (None, None)
