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
    is_public,
    is_used,
    names_in_content,
    names_in_line,
    own_tests_directory,
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

    def test_reports_the_definition_only_a_sibling_names(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition called only from its own file is reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(FULL_RUN)
        assert "helper" in stdout

    def test_the_defining_file_flag_credits_the_sibling(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """With the looser rule the sibling call counts and helper is not reported."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--count-defining-file"])
        assert "helper" not in stdout

    def test_without_own_tests_the_outer_bound_is_quiet_about_orphan(
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
            ["lib/python", "--consumer", "lib/python", "--consumer", "test",
             "--own-tests", "test/lib/python/test_{package}"]
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
            ["lib/python", "--consumer", "lib/python", "--consumer", "test",
             "--own-tests", "test/lib/python/test_{package}"]
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
        _, stdout, _ = run_cli(["lib/python", "--consumer", "lib/python", "--consumer", "src"])
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
        assert stdout == "2\n"

    def test_verbose_names_the_trees(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says how many consumer files it searched."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([*FULL_RUN, "--verbose"])
        assert "Searching 3 consumer file(s) for uses." in stdout

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

    def test_a_missing_consumer_is_an_error(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A consumer tree that does not exist marks the run."""
        write_tree(CLEAN_PROJECT)
        exit_code, _, _ = run_cli(
            ["lib/python", "--consumer", "src", "--consumer", "no/such/tree"]
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
        _, stdout, _ = run_cli(["lib/python", "--count-defining-file", "--verbose"])
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
        assert stdout == "3\n"

    def test_a_file_can_be_named_directly(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A single file is a tree of one."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli([os.path.join("lib", "python", "pkg", "__init__.py"), "--count"])
        assert stdout == "3\n"

    def test_a_recursive_glob_reaches_the_files(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A recursive pattern reaches the same files a directory does."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python/**/*.py", "--count"])
        assert stdout == "3\n"

    def test_a_glob_matching_a_directory_is_walked(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A pattern matching a directory reaches the files inside it."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python/*", "--count"])
        assert stdout == "3\n"

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
        assert stdout == "3\n"

    def test_an_exclude_drops_a_definition_file(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """An excluded file yields no definitions."""
        write_tree(PROJECT)
        _, stdout, _ = run_cli(["lib/python", "--exclude", "__init__.py", "--count"])
        assert stdout == "0\n"

    def test_an_exclude_drops_a_consumer_file(
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

    def test_names_in_line_matches_a_word(self) -> None:
        """A whole word on the line is a match."""
        assert names_in_line("kept", "kept()") is True

    def test_names_in_line_ignores_a_substring(self) -> None:
        """Part of a longer word is not a match."""
        assert names_in_line("kept", "keptic()") is False

    def test_names_in_content_reads_every_line(self) -> None:
        """Any line naming it is enough."""
        assert names_in_content("kept", CALLER) is True

    def test_names_in_content_skips_a_line(self) -> None:
        """The skipped line does not count."""
        assert names_in_content("orphan", "def orphan():\n    pass\n", skipped_line=1) is False

    def test_own_tests_directory_renders(self) -> None:
        """The package is substituted in."""
        assert own_tests_directory("test/{package}", "pkg") == "test/pkg/"

    def test_own_tests_directory_without_a_package(self) -> None:
        """No package means no directory."""
        assert own_tests_directory("test/{package}", None) is None

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

