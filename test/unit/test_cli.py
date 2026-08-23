"""Unit tests for the CLI module."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from assert_python_definition_is_used.cli import (
    EXIT_ERROR,
    EXIT_FINDINGS,
    EXIT_SUCCESS,
    ScanResult,
    _collect,
    _expand,
    _is_glob_pattern,
    _read,
    _tree_root,
    _walk_python_files,
    create_parser,
    determine_exit_code,
    output_findings,
    package_of,
    parse_patterns,
    read_definitions,
    read_sources,
    should_skip,
)
from assert_python_definition_is_used.scanner import Definition, Finding

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

TREE = {
    "lib/python/pkg/__init__.py": "def widget():\n    pass\n\n\ndef gadget():\n    pass\n",
    "src/app.py": "from pkg import gadget\n\ngadget()\n",
    "test/lib/python/test_pkg/test_pkg.py": "from pkg import widget\n\nwidget()\n",
}


def _finding(name: str = "widget", line: int = 1) -> Finding:
    """Build a finding to hand to the functions under test."""
    return Finding(
        definition=Definition(path="lib/python/pkg/__init__.py", line_number=line, name=name,
                              package="pkg")
    )


@pytest.mark.unit
class TestCreateParser:
    """Tests for create_parser."""

    def test_requires_a_tree(self) -> None:
        """At least one tree must be given."""
        with pytest.raises(SystemExit):
            create_parser().parse_args([])

    def test_accepts_one_tree(self) -> None:
        """A single tree is accepted."""
        assert create_parser().parse_args(["lib/python"]).trees == ["lib/python"]

    def test_accepts_several_trees(self) -> None:
        """More than one tree is accepted."""
        assert create_parser().parse_args(["lib", "scripts"]).trees == ["lib", "scripts"]

    def test_collects_repeated_consumers(self) -> None:
        """Every --consumer is kept, in order."""
        args = create_parser().parse_args(["lib", "--consumer", "src", "--consumer", "test"])
        assert args.consumers == ["src", "test"]

    def test_consumers_default_to_none(self) -> None:
        """Without --consumer the list is absent rather than empty."""
        assert create_parser().parse_args(["lib"]).consumers is None

    def test_reads_the_own_tests_template(self) -> None:
        """The --own-tests template is kept verbatim."""
        args = create_parser().parse_args(["lib", "--own-tests", "test/{package}"])
        assert args.own_tests == "test/{package}"

    def test_count_defining_file_defaults_off(self) -> None:
        """The defining file is discounted unless asked for."""
        assert create_parser().parse_args(["lib"]).count_defining_file is False

    def test_count_defining_file_can_be_set(self) -> None:
        """The flag turns the looser rule on."""
        assert create_parser().parse_args(["lib", "--count-defining-file"]).count_defining_file

    def test_reads_the_exclude_patterns(self) -> None:
        """The --exclude string is kept verbatim."""
        assert create_parser().parse_args(["lib", "--exclude", "*_pb2.py"]).exclude == "*_pb2.py"

    def test_reads_the_quiet_flag(self) -> None:
        """The --quiet flag is recognised."""
        assert create_parser().parse_args(["lib", "--quiet"]).quiet is True

    def test_reads_the_count_flag(self) -> None:
        """The --count flag is recognised."""
        assert create_parser().parse_args(["lib", "--count"]).count is True

    def test_reads_the_verbose_flag(self) -> None:
        """The --verbose flag is recognised."""
        assert create_parser().parse_args(["lib", "--verbose"]).verbose is True

    def test_output_flags_are_exclusive(self) -> None:
        """Two output modes at once is an error."""
        with pytest.raises(SystemExit):
            create_parser().parse_args(["lib", "--quiet", "--verbose"])

    def test_reads_the_fail_fast_flag(self) -> None:
        """The --fail-fast flag is recognised."""
        assert create_parser().parse_args(["lib", "--fail-fast"]).fail_fast is True

    def test_reads_the_warn_only_flag(self) -> None:
        """The --warn-only flag is recognised."""
        assert create_parser().parse_args(["lib", "--warn-only"]).warn_only is True

    def test_behaviour_flags_are_exclusive(self) -> None:
        """Failing fast and warning only at once is an error."""
        with pytest.raises(SystemExit):
            create_parser().parse_args(["lib", "--fail-fast", "--warn-only"])


@pytest.mark.unit
class TestParsePatterns:
    """Tests for parse_patterns."""

    def test_splits_on_commas(self) -> None:
        """A comma-separated string becomes a list."""
        assert parse_patterns("a.py,b.py") == ["a.py", "b.py"]

    def test_strips_whitespace(self) -> None:
        """Spaces around a pattern are removed."""
        assert parse_patterns(" a.py , b.py ") == ["a.py", "b.py"]

    def test_drops_empty_entries(self) -> None:
        """A trailing comma does not produce a blank pattern."""
        assert parse_patterns("a.py,,") == ["a.py"]

    def test_none_is_empty(self) -> None:
        """No patterns given is an empty list."""
        assert parse_patterns(None) == []

    def test_blank_is_empty(self) -> None:
        """A blank string is an empty list."""
        assert parse_patterns("") == []


@pytest.mark.unit
class TestIsGlobPattern:
    """Tests for _is_glob_pattern."""

    def test_star_is_a_glob(self) -> None:
        """A star makes a path a pattern."""
        assert _is_glob_pattern("lib/**/*.py") is True

    def test_question_mark_is_a_glob(self) -> None:
        """A question mark makes a path a pattern."""
        assert _is_glob_pattern("lib/a?.py") is True

    def test_bracket_is_a_glob(self) -> None:
        """A bracket makes a path a pattern."""
        assert _is_glob_pattern("lib/a[0-9].py") is True

    def test_plain_path_is_not_a_glob(self) -> None:
        """A path with no wildcards is not a pattern."""
        assert _is_glob_pattern("lib/python") is False


@pytest.mark.unit
class TestPackageOf:
    """Tests for package_of."""

    def test_names_the_first_component(self) -> None:
        """The directory below the tree is the package."""
        assert package_of("lib/python/pkg/__init__.py", "lib/python") == "pkg"

    def test_reads_through_a_deeper_path(self) -> None:
        """A file further down still belongs to the top package."""
        assert package_of("lib/python/pkg/inner/mod.py", "lib/python") == "pkg"

    def test_a_loose_file_has_no_package(self) -> None:
        """A file directly in the tree belongs to no package."""
        assert package_of("lib/python/mod.py", "lib/python") is None

    def test_a_file_outside_the_tree_has_no_package(self) -> None:
        """A path that climbs out of the tree belongs to no package."""
        assert package_of("other/mod.py", "lib/python") is None

    def test_normalises_a_trailing_separator(self) -> None:
        """A tree written with a trailing separator reads the same."""
        assert package_of("lib/python/pkg/__init__.py", "lib/python/") == "pkg"


@pytest.mark.unit
class TestTreeRoot:
    """Tests for _tree_root."""

    def test_a_directory_is_its_own_root(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A real directory is returned unchanged."""
        write_tree(TREE)
        assert _tree_root("lib/python") == "lib/python"

    def test_a_glob_reduces_to_its_directory(self) -> None:
        """The fixed part before the wildcard is the root."""
        assert _tree_root("lib/python/**/*.py") == "lib/python"

    def test_a_bare_glob_is_the_current_directory(self) -> None:
        """A pattern with no directory part hangs from the current directory."""
        assert _tree_root("*.py") == "."

    def test_a_missing_file_reduces_to_its_directory(self) -> None:
        """A path that is not a directory reduces to its parent."""
        assert _tree_root("lib/python/mod.py") == "lib/python"


@pytest.mark.unit
class TestShouldSkip:
    """Tests for should_skip."""

    def test_matches_the_whole_path(self) -> None:
        """A pattern covering the path excludes it."""
        assert should_skip("lib/python/pkg/mod.py", ["lib/*/pkg/mod.py"]) is True

    def test_matches_the_basename(self) -> None:
        """A pattern covering just the filename excludes it."""
        assert should_skip("lib/python/pkg/mod.py", ["mod.py"]) is True

    def test_leaves_a_non_match_alone(self) -> None:
        """A pattern matching nothing does not exclude."""
        assert should_skip("lib/python/pkg/mod.py", ["other.py"]) is False

    def test_no_patterns_skips_nothing(self) -> None:
        """With no patterns nothing is excluded."""
        assert should_skip("lib/python/pkg/mod.py", []) is False


@pytest.mark.unit
class TestWalkPythonFiles:
    """Tests for _walk_python_files."""

    def test_finds_a_nested_file(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """A file below the directory is found."""
        write_tree(TREE)
        assert "lib/python/pkg/__init__.py" in [
            os.path.normpath(path) for path in _walk_python_files("lib/python")
        ]

    def test_ignores_a_hidden_directory(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A dot directory is not walked."""
        write_tree({**TREE, "lib/python/.hidden/mod.py": "def buried():\n    pass\n"})
        assert not any("hidden" in path for path in _walk_python_files("lib/python"))

    def test_ignores_a_non_python_file(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A file that is not Python is not returned."""
        write_tree({**TREE, "lib/python/pkg/notes.txt": "text\n"})
        assert not any(path.endswith(".txt") for path in _walk_python_files("lib/python"))


@pytest.mark.unit
class TestExpand:
    """Tests for _expand."""

    def test_expands_a_directory(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """A directory yields the Python files under it."""
        write_tree(TREE)
        assert _expand("lib/python")[0]

    def test_expands_a_file(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """A file yields itself."""
        write_tree(TREE)
        assert _expand("src/app.py")[0] == ["src/app.py"]

    def test_expands_a_glob(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """A pattern yields what it matches."""
        write_tree(TREE)
        assert _expand("src/*.py")[0] == ["src/app.py"]

    def test_a_glob_matching_a_directory_is_walked(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A pattern matching a directory yields the files inside it."""
        write_tree(TREE)
        assert any(path.endswith("__init__.py") for path in _expand("lib/python/*")[0])

    def test_reports_a_missing_path(self) -> None:
        """A path naming nothing reports that it matched nothing."""
        assert _expand("no/such/place")[1] is False

    def test_a_glob_matching_a_broken_link_yields_nothing(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A pattern matching something that is neither file nor directory yields nothing."""
        root = write_tree(TREE)
        os.symlink("nowhere", root / "src" / "broken.py")
        assert _expand("src/broken.py*")[0] == []

    def test_reports_a_glob_matching_nothing(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A pattern matching nothing reports that it matched nothing."""
        write_tree(TREE)
        assert _expand("no/such/*.py")[1] is False


@pytest.mark.unit
class TestCollect:
    """Tests for _collect."""

    def test_maps_a_file_to_its_tree(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """Each file remembers the tree it was found under."""
        write_tree(TREE)
        assert _collect(["lib/python"], [])[0][os.path.normpath("lib/python/pkg/__init__.py")] == (
            "lib/python"
        )

    def test_applies_the_exclude_patterns(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """An excluded file is left out."""
        write_tree(TREE)
        assert not _collect(["lib/python"], ["__init__.py"])[0]

    def test_reports_a_missing_tree(self) -> None:
        """A tree naming nothing is reported as missing."""
        assert _collect(["no/such/place"], [])[1] == ["no/such/place"]

    def test_keeps_the_first_tree_for_a_shared_file(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A file reachable from two trees keeps the first tree named."""
        write_tree(TREE)
        collected, _ = _collect(["lib/python", "lib"], [])
        assert collected[os.path.normpath("lib/python/pkg/__init__.py")] == "lib/python"

    def test_ignores_a_non_python_file_named_directly(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A file that is not Python is not collected even when named."""
        write_tree({**TREE, "notes.txt": "text\n"})
        assert not _collect(["notes.txt"], [])[0]


@pytest.mark.unit
class TestRead:
    """Tests for _read and read_sources."""

    def test_reads_a_file(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """A readable file comes back as text."""
        write_tree(TREE)
        assert _read("src/app.py", ScanResult(), False) == TREE["src/app.py"]

    def test_a_missing_file_reads_as_none(self) -> None:
        """A file that cannot be opened reads as nothing."""
        assert _read("no/such/file.py", ScanResult(), False) is None

    def test_a_missing_file_records_an_error(self) -> None:
        """A file that cannot be opened marks the result."""
        result = ScanResult()
        _read("no/such/file.py", result, False)
        assert result.had_error is True

    def test_a_missing_file_is_named_when_verbose(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verbose output says which file was skipped."""
        _read("no/such/file.py", ScanResult(), True)
        assert "Skipping (unreadable)" in capsys.readouterr().out

    def test_read_sources_keys_by_path(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """Every readable file is returned, keyed by its path."""
        write_tree(TREE)
        expected = {"src/app.py": TREE["src/app.py"]}
        assert read_sources({"src/app.py": "src"}, ScanResult()) == expected

    def test_read_sources_drops_the_unreadable(self) -> None:
        """A file that cannot be read is left out rather than raising."""
        assert not read_sources({"no/such/file.py": "."}, ScanResult())


@pytest.mark.unit
class TestReadDefinitions:
    """Tests for read_definitions."""

    def test_finds_the_definitions(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """Every public definition in the file is returned."""
        write_tree(TREE)
        paths = {"lib/python/pkg/__init__.py": "lib/python"}
        found = read_definitions(paths, read_sources(paths, ScanResult()), ScanResult())
        assert [item.name for item in found] == ["widget", "gadget"]

    def test_counts_the_files_scanned(self, write_tree: Callable[[dict[str, str]], Path]) -> None:
        """The result records how many files were parsed."""
        write_tree(TREE)
        paths = {"lib/python/pkg/__init__.py": "lib/python"}
        result = ScanResult()
        read_definitions(paths, read_sources(paths, ScanResult()), result)
        assert result.files_scanned == 1

    def test_counts_the_definitions_read(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """The result records how many definitions were found."""
        write_tree(TREE)
        paths = {"lib/python/pkg/__init__.py": "lib/python"}
        result = ScanResult()
        read_definitions(paths, read_sources(paths, ScanResult()), result)
        assert result.definitions_read == 2

    def test_names_each_file_when_verbose(
        self, write_tree: Callable[[dict[str, str]], Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verbose output names each file scanned."""
        write_tree(TREE)
        paths = {"lib/python/pkg/__init__.py": "lib/python"}
        read_definitions(paths, read_sources(paths, ScanResult()), ScanResult(), True)
        assert "Scanning: lib/python/pkg/__init__.py" in capsys.readouterr().out

    def test_skips_a_file_that_could_not_be_read(self) -> None:
        """A file missing from the sources is passed over."""
        assert not read_definitions({"gone.py": "."}, {}, ScanResult())

    def test_records_an_error_for_unparseable_content(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A file that is not Python marks the result."""
        write_tree({"lib/python/pkg/bad.py": "def widget(:\n"})
        paths = {"lib/python/pkg/bad.py": "lib/python"}
        result = ScanResult()
        read_definitions(paths, read_sources(paths, ScanResult()), result)
        assert result.had_error is True

    def test_carries_the_package_through(
        self, write_tree: Callable[[dict[str, str]], Path]
    ) -> None:
        """A definition knows which package it came from."""
        write_tree(TREE)
        paths = {"lib/python/pkg/__init__.py": "lib/python"}
        found = read_definitions(paths, read_sources(paths, ScanResult()), ScanResult())
        assert found[0].package == "pkg"


@pytest.mark.unit
class TestOutputFindings:
    """Tests for output_findings."""

    def test_prints_each_finding(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Each finding is printed on its own line."""
        output_findings([_finding(), _finding("gadget", 5)])
        assert capsys.readouterr().out.splitlines() == [
            "lib/python/pkg/__init__.py:1:widget",
            "lib/python/pkg/__init__.py:5:gadget",
        ]

    def test_prints_a_count_when_asked(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Count mode prints only how many there are."""
        output_findings([_finding(), _finding("gadget", 5)], count_mode=True)
        assert capsys.readouterr().out == "2\n"

    def test_prints_nothing_for_no_findings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """No findings prints nothing at all."""
        output_findings([])
        assert capsys.readouterr().out == ""


@pytest.mark.unit
class TestDetermineExitCode:
    """Tests for determine_exit_code."""

    def test_clean_run_succeeds(self) -> None:
        """Nothing found and nothing broken is success."""
        assert determine_exit_code(ScanResult()) == EXIT_SUCCESS

    def test_findings_fail(self) -> None:
        """A finding is a failure."""
        assert determine_exit_code(ScanResult(findings=[_finding()])) == EXIT_FINDINGS

    def test_errors_fail_differently(self) -> None:
        """An error with no findings is its own exit code."""
        assert determine_exit_code(ScanResult(had_error=True)) == EXIT_ERROR

    def test_findings_outrank_errors(self) -> None:
        """A finding is reported even when something also went wrong."""
        result = ScanResult(findings=[_finding()], had_error=True)
        assert determine_exit_code(result) == EXIT_FINDINGS

    def test_warn_only_always_succeeds(self) -> None:
        """Warn-only turns every outcome into success."""
        result = ScanResult(findings=[_finding()], had_error=True)
        assert determine_exit_code(result, warn_only=True) == EXIT_SUCCESS


@pytest.mark.unit
class TestMain:
    """Tests for main, driven through the in-process runner."""

    def test_reports_an_unused_definition(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition only its own tests name is reported."""
        write_tree(TREE)
        _, stdout, _ = run_cli(
            ["lib/python", "--consumer", "lib/python", "--consumer", "src", "--consumer", "test",
             "--own-tests", "test/lib/python/test_{package}"]
        )
        assert "widget" in stdout

    def test_stays_quiet_about_a_used_definition(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A definition another tree names is not reported."""
        write_tree(TREE)
        _, stdout, _ = run_cli(
            ["lib/python", "--consumer", "lib/python", "--consumer", "src", "--consumer", "test",
             "--own-tests", "test/lib/python/test_{package}"]
        )
        assert "gadget" not in stdout

    def test_consumers_default_to_the_trees(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Without --consumer only the definition trees are searched."""
        write_tree(TREE)
        exit_code, _, _ = run_cli(["lib/python"])
        assert exit_code == EXIT_FINDINGS

    def test_exits_clean_when_nothing_is_unused(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A tree with nothing to report exits zero."""
        write_tree({"lib/python/pkg/__init__.py": "def widget():\n    pass\n",
                    "src/app.py": "widget()\n"})
        exit_code, _, _ = run_cli(["lib/python", "--consumer", "lib/python", "--consumer", "src"])
        assert exit_code == EXIT_SUCCESS

    def test_names_a_missing_tree(
        self, run_cli: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """A tree that does not exist is named on stderr."""
        _, _, stderr = run_cli(["no/such/place"])
        assert "Path not found: no/such/place" in stderr

    def test_a_missing_tree_alone_is_an_error(
        self, run_cli: Callable[[list[str]], tuple[int, str, str]]
    ) -> None:
        """With no definition files at all the run is an error."""
        exit_code, _, _ = run_cli(["no/such/place"])
        assert exit_code == EXIT_ERROR

    def test_a_missing_consumer_marks_an_error(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A missing consumer tree is an error even when definitions were read."""
        write_tree({"lib/python/pkg/__init__.py": "def widget():\n    pass\nwidget()\n"})
        exit_code, _, _ = run_cli(
            ["lib/python", "--consumer", "lib/python", "--consumer", "no/such/place",
             "--count-defining-file"]
        )
        assert exit_code == EXIT_ERROR

    def test_quiet_prints_nothing(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Quiet mode reports through the exit code alone."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--quiet"])
        assert stdout == ""

    def test_count_prints_a_number(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Count mode prints how many were found."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--count"])
        assert stdout == "2\n"

    def test_verbose_summarises(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode ends with a count of definitions read."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Definitions read: 2" in stdout

    def test_verbose_names_the_findings(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode lists each unused definition."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Unused: lib/python/pkg/__init__.py:1:widget" in stdout

    def test_verbose_names_the_exclude_patterns(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says what was excluded."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--verbose", "--exclude", "nothing.py"])
        assert "Excluding patterns: nothing.py" in stdout

    def test_verbose_reports_an_error(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Verbose mode says when something went wrong."""
        write_tree({"lib/python/pkg/bad.py": "def widget(:\n"})
        _, stdout, _ = run_cli(["lib/python", "--verbose"])
        assert "Errors occurred during scanning." in stdout

    def test_fail_fast_reports_one(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Failing fast stops after the first finding."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--fail-fast", "--count"])
        assert stdout == "1\n"

    def test_warn_only_exits_clean(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """Warn-only reports findings but succeeds."""
        write_tree(TREE)
        exit_code, _, _ = run_cli(["lib/python", "--warn-only"])
        assert exit_code == EXIT_SUCCESS

    def test_exclude_leaves_a_file_out(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """An excluded definition file yields no definitions."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python", "--exclude", "__init__.py", "--count"])
        assert stdout == "0\n"

    def test_count_defining_file_credits_a_sibling_call(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """With the flag a call from elsewhere in the same file is a use."""
        write_tree({"lib/python/pkg/__init__.py": "def widget():\n    pass\n\n\nwidget()\n"})
        _, stdout, _ = run_cli(["lib/python", "--count-defining-file", "--count"])
        assert stdout == "0\n"

    def test_a_glob_names_the_trees(
        self,
        write_tree: Callable[[dict[str, str]], Path],
        run_cli: Callable[[list[str]], tuple[int, str, str]],
    ) -> None:
        """A pattern works in place of a directory."""
        write_tree(TREE)
        _, stdout, _ = run_cli(["lib/python/**/*.py", "--count"])
        assert stdout == "2\n"
