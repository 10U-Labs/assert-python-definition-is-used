from __future__ import annotations

import ast
import os
import runpy
import sys
from test.samples import (
    CALLER,
    LIBRARY,
    PROJECT,
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
    names_in_text,
    names_used,
    read_searched,
    unsearched_directory,
    public_definitions,
    unused_definitions,
)

if TYPE_CHECKING:
    from test.runners import WriteTree


@pytest.mark.integration
class TestHelpersOverRealFiles:
    def test_walk_finds_the_python_files(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        assert len(_walk_python_files("lib/python")) == 1

    def test_expand_reports_a_directory_matched(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        assert _expand("lib/python")[1] is True

    def test_expand_skips_a_broken_link(self, write_tree: WriteTree) -> None:
        root = write_tree(PROJECT)
        os.symlink("nowhere", root / "src" / "broken.py")
        assert not _expand("src/broken.py*")[0]

    def test_expand_reports_a_missing_path(self) -> None:
        assert _expand("no/such/path")[1] is False

    def test_collect_maps_files_to_their_tree(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        assert set(collected.values()) == {"lib/python"}

    def test_collect_reports_what_is_missing(self) -> None:
        assert _collect(["no/such/path"], [])[1] == ["no/such/path"]

    def test_read_sources_reads_the_files(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        assert list(read_sources(collected, ScanResult()).values()) == [LIBRARY]

    def test_read_returns_the_text(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        assert _read(os.path.join("src", "app.py"), ScanResult(), False) == CALLER

    def test_read_marks_an_unreadable_file(self, write_tree: WriteTree) -> None:
        root = write_tree(PROJECT)
        os.symlink("nowhere", root / "broken.py")
        result = ScanResult()
        _read("broken.py", result, False)
        assert result.had_error is True

    def test_read_definitions_skips_what_was_not_read(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        assert not read_definitions({"gone.py": "."}, {}, ScanResult())

    def test_read_definitions_finds_them(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        found = read_definitions(collected, read_sources(collected, ScanResult()), ScanResult())
        assert [item.name for item in found] == ["kept", "orphan", "helper"]

    def test_read_definitions_names_files_when_verbose(
        self,
        write_tree: WriteTree,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        write_tree(PROJECT)
        collected, _ = _collect(["lib/python"], [])
        read_definitions(collected, read_sources(collected, ScanResult()), ScanResult(), True)
        assert "Scanning:" in capsys.readouterr().out


@pytest.mark.integration
class TestPathHelpers:
    def test_package_of_reads_the_tree(self) -> None:
        assert package_of(os.path.join("lib", "python", "pkg", "mod.py"), "lib/python") == "pkg"

    def test_package_of_a_loose_file_is_none(self) -> None:
        assert package_of(os.path.join("lib", "python", "mod.py"), "lib/python") is None

    def test_package_of_an_outside_file_is_none(self) -> None:
        assert package_of(os.path.join("other", "mod.py"), "lib/python") is None

    def test_tree_root_of_a_directory(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        assert _tree_root("lib/python") == "lib/python"

    def test_tree_root_of_a_glob(self) -> None:
        assert _tree_root("lib/python/**/*.py") == "lib/python"

    def test_tree_root_of_a_bare_glob(self) -> None:
        assert _tree_root("*.py") == "."

    def test_is_glob_pattern_reads_a_star(self) -> None:
        assert _is_glob_pattern("*.py") is True

    def test_is_glob_pattern_reads_a_plain_path(self) -> None:
        assert _is_glob_pattern("lib/python") is False

    def test_should_skip_matches(self) -> None:
        assert should_skip("lib/python/pkg/mod.py", ["mod.py"]) is True

    def test_should_skip_leaves_others(self) -> None:
        assert should_skip("lib/python/pkg/mod.py", ["other.py"]) is False

    def test_parse_patterns_splits(self) -> None:
        assert parse_patterns("a,b") == ["a", "b"]

    def test_parse_patterns_of_nothing(self) -> None:
        assert parse_patterns(None) == []

    def test_create_parser_reads_a_tree(self) -> None:
        assert create_parser().parse_args(["lib"]).trees == ["lib"]


@pytest.mark.integration
class TestReportingHelpers:
    def test_output_findings_prints(self, capsys: pytest.CaptureFixture[str]) -> None:
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        output_findings([Finding(definition=definition)])
        assert capsys.readouterr().out == "a.py:1:orphan\n"

    def test_output_findings_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        output_findings([Finding(definition=definition)], count_mode=True)
        assert capsys.readouterr().out == "1\n"

    def test_determine_exit_code_for_findings(self) -> None:
        definition = Definition(path="a.py", line_number=1, name="orphan", package=None)
        result = ScanResult(findings=[Finding(definition=definition)])
        assert determine_exit_code(result) == EXIT_FINDINGS

    def test_determine_exit_code_for_errors(self) -> None:
        assert determine_exit_code(ScanResult(had_error=True)) == EXIT_ERROR

    def test_determine_exit_code_for_success(self) -> None:
        assert determine_exit_code(ScanResult()) == EXIT_SUCCESS

    def test_running_the_package_as_a_module_calls_the_cli(self) -> None:
        with patch("assert_python_definition_is_used.cli.main") as entry_point:
            sys.modules.pop("assert_python_definition_is_used.__main__", None)
            runpy.run_module("assert_python_definition_is_used", run_name="__main__")
            assert entry_point.called

    def test_determine_exit_code_warn_only(self) -> None:
        assert determine_exit_code(ScanResult(had_error=True), warn_only=True) == EXIT_SUCCESS


@pytest.mark.integration
class TestScannerOverRealFiles:
    def test_public_definitions_reads_a_file(self, write_tree: WriteTree) -> None:
        write_tree(PROJECT)
        path = os.path.join("lib", "python", "pkg", "__init__.py")
        found = public_definitions(path, _read(path, ScanResult(), False) or "", "pkg")
        assert [item.name for item in found] == ["kept", "orphan", "helper"]

    def test_public_definitions_raises_on_bad_python(self) -> None:
        with pytest.raises(SyntaxError):
            public_definitions("bad.py", "def broken(:\n")

    def test_is_public_reads_a_plain_name(self) -> None:
        assert is_public("kept") is True

    def test_is_public_reads_an_underscore(self) -> None:
        assert is_public("_kept") is False

    def test_names_in_text_matches_a_word(self) -> None:
        assert names_in_text("kept", "kept()") is True

    def test_names_in_text_ignores_a_substring(self) -> None:
        assert names_in_text("kept", "keptic()") is False

    def test_names_in_text_reads_every_line(self) -> None:
        assert names_in_text("kept", CALLER) is True

    def test_names_used_reads_a_call(self) -> None:
        assert "kept" in names_used(ast.parse(LIBRARY))

    def test_names_used_ignores_a_definition(self) -> None:
        assert "orphan" not in names_used(ast.parse("def orphan():\n    pass\n"))

    def test_unsearched_directory_renders(self) -> None:
        assert unsearched_directory("test/{package}", "pkg") == "test/pkg/"

    def test_unsearched_directory_without_a_package(self) -> None:
        assert unsearched_directory("test/{package}", None) is None

    def test_is_used_reads_the_sources(self) -> None:
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=1, name="kept",
                                package="pkg")
        searched = read_searched({"lib/python/pkg/__init__.py": LIBRARY, "src/app.py": CALLER})
        assert is_used(definition, searched)

    def test_a_finding_exposes_its_path(self) -> None:
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).path == "lib/python/pkg/__init__.py"

    def test_a_finding_exposes_its_line(self) -> None:
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).line_number == 5

    def test_a_finding_exposes_its_name(self) -> None:
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        assert Finding(definition=definition).name == "orphan"

    def test_unused_definitions_reports(self) -> None:
        definition = Definition(path="lib/python/pkg/__init__.py", line_number=5, name="orphan",
                                package="pkg")
        found = unused_definitions(
            [definition], read_searched({"lib/python/pkg/__init__.py": LIBRARY})
        )
        assert len(found) == 1


@pytest.mark.integration
class TestAssumptionsOverRealFiles:
    def test_public_definitions_reads_the_decorators(self, write_tree: WriteTree) -> None:
        write_tree(RUNTIME_PROJECT)
        path = os.path.join("test", "pkg", "test_pkg.py")
        found = public_definitions(path, _read(path, ScanResult(), False) or "", "pkg")
        assert found[0].decorators == ("pytest.fixture",)

    def test_public_definitions_leaves_a_plain_definition_bare(self) -> None:
        assert public_definitions("a.py", RUNTIME_INVOKED)[1].decorators == ()

    def test_public_definitions_drops_an_unflattenable_decorator(self) -> None:
        found = public_definitions("a.py", '@table["a"]\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_public_definitions_reads_a_bare_decorator(self) -> None:
        found = public_definitions("a.py", "@task\ndef widget():\n    pass\n")
        assert found[0].decorators == ("task",)

    def test_is_assumed_used_by_name_matches_a_glob(self) -> None:
        assert is_assumed_used_by_name("pytest_configure", ["pytest_*"]) is True

    def test_is_assumed_used_by_name_leaves_the_rest(self) -> None:
        assert is_assumed_used_by_name("spare", ["pytest_*"]) is False

    def test_is_assumed_used_by_decorator_matches_a_path(self) -> None:
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["pytest.fixture"]) is True

    def test_is_assumed_used_by_decorator_leaves_the_rest(self) -> None:
        assert is_assumed_used_by_decorator([], ["pytest.fixture"]) is False

    def test_assumed_used_splits_on_the_name(self) -> None:
        held = public_definitions("a.py", RUNTIME_INVOKED)
        _, by_name, _ = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in by_name] == ["pytest_configure",
                                                   "test_it_reads_the_directory"]

    def test_assumed_used_splits_on_the_decorator(self) -> None:
        held = public_definitions("a.py", RUNTIME_INVOKED)
        _, _, by_decorator = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in by_decorator] == ["bootstrap_dir_fixture"]

    def test_assumed_used_keeps_the_rest(self) -> None:
        held = public_definitions("a.py", RUNTIME_INVOKED)
        checked, _, _ = assumed_used(held, ["test_*", "pytest_*"], ["pytest.fixture"])
        assert [item.name for item in checked] == ["spare"]

    def test_assumed_used_claims_nothing_by_default(self) -> None:
        held = public_definitions("a.py", RUNTIME_INVOKED)
        assert assumed_used(held, [], []) == (held, [], [])

    def test_assume_used_counts_the_names(self) -> None:
        result = ScanResult()
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, result)
        assert result.assumed_by_name == 2

    def test_assume_used_counts_the_decorators(self) -> None:
        result = ScanResult()
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, result)
        assert result.assumed_by_decorator == 1

    def test_assume_used_returns_what_is_left(self) -> None:
        arguments = create_parser().parse_args(RUNTIME_ASSUMED)
        left = assume_used(public_definitions("a.py", RUNTIME_INVOKED), arguments, ScanResult())
        assert [item.name for item in left] == ["spare"]

    def test_the_parser_reads_the_name_patterns(self) -> None:
        assert create_parser().parse_args(RUNTIME_ASSUMED).assume_used_matching == "test_*,pytest_*"

    def test_the_parser_reads_the_decorator_paths(self) -> None:
        parsed = create_parser().parse_args(RUNTIME_ASSUMED)
        assert parsed.assume_used_decorated_with == "pytest.fixture"

    def test_the_parser_defaults_both_to_none(self) -> None:
        parsed = create_parser().parse_args(RUNTIME_RUN)
        assert (parsed.assume_used_matching, parsed.assume_used_decorated_with) == (None, None)
