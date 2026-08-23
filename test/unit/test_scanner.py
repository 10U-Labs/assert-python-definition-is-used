"""Unit tests for the scanner module."""

from __future__ import annotations

import pytest

from assert_python_definition_is_used.scanner import (
    Definition,
    Finding,
    is_public,
    is_used,
    names_in_content,
    names_in_line,
    unsearched_directory,
    public_definitions,
    unused_definitions,
)

MODULE = "lib/python/pkg/__init__.py"


def _definition(name: str = "widget", line: int = 1, package: str | None = "pkg") -> Definition:
    """Build a definition to hand to the functions under test."""
    return Definition(path=MODULE, line_number=line, name=name, package=package)


@pytest.mark.unit
class TestDefinition:
    """Tests for the Definition record."""

    def test_formats_as_path_line_name(self) -> None:
        """A definition prints as path:line:name."""
        assert str(_definition(line=7)) == f"{MODULE}:7:widget"

    def test_keeps_its_package(self) -> None:
        """A definition remembers the package it came from."""
        assert _definition().package == "pkg"

    def test_is_hashable(self) -> None:
        """A definition is frozen, so it can go in a set."""
        assert len({_definition(), _definition()}) == 1


@pytest.mark.unit
class TestFinding:
    """Tests for the Finding record."""

    def test_exposes_path(self) -> None:
        """A finding reads its path from the definition it holds."""
        assert Finding(definition=_definition()).path == MODULE

    def test_exposes_line_number(self) -> None:
        """A finding reads its line from the definition it holds."""
        assert Finding(definition=_definition(line=12)).line_number == 12

    def test_exposes_name(self) -> None:
        """A finding reads its name from the definition it holds."""
        assert Finding(definition=_definition(name="gadget")).name == "gadget"

    def test_formats_as_path_line_name(self) -> None:
        """A finding prints the same way its definition does."""
        assert str(Finding(definition=_definition(line=3))) == f"{MODULE}:3:widget"


@pytest.mark.unit
class TestIsPublic:
    """Tests for is_public."""

    def test_plain_name_is_public(self) -> None:
        """A name with no leading underscore is public."""
        assert is_public("widget") is True

    def test_underscore_name_is_not_public(self) -> None:
        """A name with a leading underscore is not public."""
        assert is_public("_widget") is False

    def test_dunder_is_not_public(self) -> None:
        """A dunder starts with an underscore, so it is not public."""
        assert is_public("__init__") is False


@pytest.mark.unit
class TestPublicDefinitions:
    """Tests for public_definitions."""

    def test_finds_a_function(self) -> None:
        """A top-level function is a definition."""
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].name == "widget"

    def test_finds_an_async_function(self) -> None:
        """A top-level async function is a definition."""
        found = public_definitions(MODULE, "async def widget():\n    pass\n")
        assert found[0].name == "widget"

    def test_finds_a_class(self) -> None:
        """A top-level class is a definition."""
        found = public_definitions(MODULE, "class Widget:\n    pass\n")
        assert found[0].name == "Widget"

    def test_records_the_line(self) -> None:
        """A definition carries the line it starts on."""
        found = public_definitions(MODULE, "\n\ndef widget():\n    pass\n")
        assert found[0].line_number == 3

    def test_skips_a_private_definition(self) -> None:
        """A leading underscore takes a definition out of scope."""
        assert not public_definitions(MODULE, "def _widget():\n    pass\n")

    def test_skips_a_method(self) -> None:
        """A method is reached through its class, so it is not counted."""
        found = public_definitions(MODULE, "class Widget:\n    def spin(self):\n        pass\n")
        assert [item.name for item in found] == ["Widget"]

    def test_skips_a_nested_function(self) -> None:
        """A function inside a function is not top level."""
        found = public_definitions(MODULE, "def widget():\n    def spin():\n        pass\n")
        assert [item.name for item in found] == ["widget"]

    def test_keeps_source_order(self) -> None:
        """Definitions come back in the order they appear."""
        found = public_definitions(MODULE, "def one():\n    pass\ndef two():\n    pass\n")
        assert [item.name for item in found] == ["one", "two"]

    def test_carries_the_package_through(self) -> None:
        """The package given is attached to every definition found."""
        found = public_definitions(MODULE, "def widget():\n    pass\n", package="pkg")
        assert found[0].package == "pkg"

    def test_package_defaults_to_none(self) -> None:
        """A file belonging to no package yields definitions with no package."""
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].package is None

    def test_empty_file_yields_nothing(self) -> None:
        """A file with no definitions yields none."""
        assert not public_definitions(MODULE, "")

    def test_raises_on_unparseable_content(self) -> None:
        """Content that is not Python raises, for the caller to report."""
        with pytest.raises(SyntaxError):
            public_definitions(MODULE, "def widget(:\n")


@pytest.mark.unit
class TestNamesInLine:
    """Tests for names_in_line."""

    def test_finds_a_whole_word(self) -> None:
        """A bare name on the line is a match."""
        assert names_in_line("widget", "value = widget()") is True

    def test_ignores_a_longer_word(self) -> None:
        """A name that is only part of a longer word is not a match."""
        assert names_in_line("widget", "value = widgetry()") is False

    def test_ignores_a_prefixed_word(self) -> None:
        """A name preceded by word characters is not a match."""
        assert names_in_line("widget", "value = my_widget") is False

    def test_finds_an_attribute_access(self) -> None:
        """A dot is not a word character, so an attribute is a match."""
        assert names_in_line("widget", "value = module.widget") is True

    def test_escapes_regex_characters(self) -> None:
        """A name is matched literally rather than as a pattern."""
        assert names_in_line("a.b", "value = a.b") is True


@pytest.mark.unit
class TestNamesInContent:
    """Tests for names_in_content."""

    def test_finds_a_name_anywhere(self) -> None:
        """Any line naming the identifier is enough."""
        assert names_in_content("widget", "import x\nvalue = widget()\n") is True

    def test_absent_name_is_not_found(self) -> None:
        """Content that never names the identifier reports false."""
        assert names_in_content("widget", "import x\n") is False

    def test_skips_the_named_line(self) -> None:
        """The skipped line does not count as a use."""
        assert names_in_content("widget", "def widget():\n    pass\n", skipped_line=1) is False

    def test_reads_the_other_lines(self) -> None:
        """A line other than the skipped one still counts."""
        content = "def widget():\n    pass\nwidget()\n"
        assert names_in_content("widget", content, skipped_line=1) is True


@pytest.mark.unit
class TestUnsearchedDirectory:
    """Tests for unsearched_directory."""

    def test_renders_the_package(self) -> None:
        """The package is substituted into the template."""
        assert unsearched_directory("test/lib/python/test_{package}", "pkg") == (
            "test/lib/python/test_pkg/"
        )

    def test_keeps_an_existing_separator(self) -> None:
        """A template already ending in a separator is not doubled."""
        assert unsearched_directory("test/{package}/", "pkg") == "test/pkg/"

    def test_no_template_means_no_directory(self) -> None:
        """Without a template nothing is discounted."""
        assert unsearched_directory(None, "pkg") is None

    def test_no_package_means_no_directory(self) -> None:
        """A file belonging to no package has no directory of its own to discount."""
        assert unsearched_directory("test/{package}", None) is None


@pytest.mark.unit
class TestIsUsed:
    """Tests for is_used."""

    def test_a_sibling_module_counts(self) -> None:
        """A name written in another file is a use."""
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert is_used(_definition(), sources) is True

    def test_the_defining_file_does_not_count(self) -> None:
        """By default the whole defining file is discounted."""
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert is_used(_definition(), sources) is False

    def test_the_defining_file_counts_when_asked(self) -> None:
        """With the flag, another line of the defining file is a use."""
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert is_used(_definition(), sources, count_defining_file=True) is True

    def test_the_defining_line_never_counts(self) -> None:
        """Even with the flag, the definition's own line is not a use."""
        sources = {MODULE: "def widget():\n    pass\n"}
        assert is_used(_definition(), sources, count_defining_file=True) is False

    def test_an_unsearched_directory_is_discounted(self) -> None:
        """A use inside the package's own tests does not count."""
        sources = {MODULE: "def widget():\n    pass\n", "test/pkg/test_it.py": "widget()\n"}
        assert is_used(_definition(), sources, unsearched="test/pkg/") is False

    def test_other_tests_still_count(self) -> None:
        """A use in another package's tests is a real use."""
        sources = {MODULE: "def widget():\n    pass\n", "test/other/test_it.py": "widget()\n"}
        assert is_used(_definition(), sources, unsearched="test/pkg/") is True

    def test_nothing_to_search_means_unused(self) -> None:
        """With nothing to search, nothing is used."""
        assert is_used(_definition(), {}) is False


@pytest.mark.unit
class TestUnusedDefinitions:
    """Tests for unused_definitions."""

    def test_reports_an_unused_definition(self) -> None:
        """A definition nothing names is reported."""
        sources = {MODULE: "def widget():\n    pass\n"}
        assert len(unused_definitions([_definition()], sources)) == 1

    def test_stays_quiet_about_a_used_definition(self) -> None:
        """A definition something names is not reported."""
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert not unused_definitions([_definition()], sources)

    def test_wraps_the_definition_in_a_finding(self) -> None:
        """A finding carries the definition it was made from."""
        sources = {MODULE: "def widget():\n    pass\n"}
        assert unused_definitions([_definition()], sources)[0].definition == _definition()

    def test_renders_the_template_per_package(self) -> None:
        """Each definition's discounted directory comes from its own package."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions([_definition()], sources, "test/lib/python/test_{package}")
        assert len(found) == 1

    def test_a_definition_with_no_package_keeps_its_tests(self) -> None:
        """Without a package there is no directory to discount."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions(
            [_definition(package=None)], sources, "test/lib/python/test_{package}"
        )
        assert not found

    def test_passes_the_defining_file_flag_through(self) -> None:
        """The flag reaches the per-definition check."""
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert not unused_definitions([_definition()], sources, count_defining_file=True)

    def test_no_definitions_means_no_findings(self) -> None:
        """An empty list of definitions yields no findings."""
        assert not unused_definitions([], {MODULE: ""})
