"""Unit tests for the scanner module."""

from __future__ import annotations

import ast

import pytest

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

MODULE = "lib/python/pkg/__init__.py"


def _uses(name: str, content: str) -> bool:
    """Ask whether a file's code uses a name, parsing it the way the tool does."""
    return name in names_used(ast.parse(content))


def _definition(
    name: str = "widget",
    line: int = 1,
    package: str | None = "pkg",
    decorators: tuple[str, ...] = (),
) -> Definition:
    """Build a definition to hand to the functions under test."""
    return Definition(
        path=MODULE, line_number=line, name=name, package=package, decorators=decorators
    )


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

    def test_carries_no_decorators_by_default(self) -> None:
        """A definition built without decorators carries none."""
        assert not _definition().decorators

    def test_keeps_its_decorators(self) -> None:
        """A definition remembers the decorators it was given."""
        assert _definition(decorators=("pytest.fixture",)).decorators == ("pytest.fixture",)


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
class TestPublicDefinitionsReadingDecorators:
    """Tests for the decorators public_definitions records."""

    def test_an_undecorated_definition_carries_nothing(self) -> None:
        """A definition with no decorator line carries no decorator."""
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].decorators == ()

    def test_reads_a_bare_decorator(self) -> None:
        """A one-word decorator flattens to that word."""
        found = public_definitions(MODULE, "@task\ndef widget():\n    pass\n")
        assert found[0].decorators == ("task",)

    def test_reads_a_dotted_decorator(self) -> None:
        """An attribute decorator flattens to its dotted path."""
        found = public_definitions(MODULE, "@pytest.fixture\ndef widget():\n    pass\n")
        assert found[0].decorators == ("pytest.fixture",)

    def test_reads_a_called_decorator(self) -> None:
        """A decorator given arguments flattens the same way a bare one does."""
        content = '@pytest.fixture(name="other")\ndef widget():\n    pass\n'
        assert public_definitions(MODULE, content)[0].decorators == ("pytest.fixture",)

    def test_reads_a_deeply_dotted_decorator(self) -> None:
        """Every step of an attribute chain is kept."""
        found = public_definitions(MODULE, "@app.api.route\ndef widget():\n    pass\n")
        assert found[0].decorators == ("app.api.route",)

    def test_drops_a_decorator_it_cannot_flatten(self) -> None:
        """A decorator read out of a subscript matches nothing rather than raising."""
        found = public_definitions(MODULE, '@registry["a"]\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_drops_an_unflattenable_decorator_root(self) -> None:
        """An attribute hanging off a subscript flattens to nothing."""
        found = public_definitions(MODULE, '@registry["a"].wrap\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_reads_every_decorator(self) -> None:
        """A definition carrying two decorators keeps both, outermost first."""
        content = "@one\n@two.three\ndef widget():\n    pass\n"
        assert public_definitions(MODULE, content)[0].decorators == ("one", "two.three")

    def test_reads_a_decorated_class(self) -> None:
        """A class carries its decorators the way a function does."""
        found = public_definitions(MODULE, "@register\nclass Widget:\n    pass\n")
        assert found[0].decorators == ("register",)


@pytest.mark.unit
class TestNamesInText:
    """Tests for names_in_text."""

    def test_finds_a_whole_word(self) -> None:
        """A bare name in the text is a match."""
        assert names_in_text("widget", "value = widget()") is True

    def test_ignores_a_longer_word(self) -> None:
        """A name that is only part of a longer word is not a match."""
        assert names_in_text("widget", "value = widgetry()") is False

    def test_ignores_a_prefixed_word(self) -> None:
        """A name preceded by word characters is not a match."""
        assert names_in_text("widget", "value = my_widget") is False

    def test_finds_an_attribute_access(self) -> None:
        """A dot is not a word character, so an attribute is a match."""
        assert names_in_text("widget", "value = module.widget") is True

    def test_escapes_regex_characters(self) -> None:
        """A name is matched literally rather than as a pattern."""
        assert names_in_text("a.b", "value = a.b") is True

    def test_finds_a_name_on_any_line(self) -> None:
        """Any line naming the identifier is enough."""
        assert names_in_text("widget", "import x\nvalue = widget()\n") is True

    def test_absent_name_is_not_found(self) -> None:
        """Text that never names the identifier reports false."""
        assert names_in_text("widget", "import x\n") is False

    def test_counts_a_name_written_in_prose(self) -> None:
        """The fallback rule is blunt and credits a docstring too."""
        assert names_in_text("widget", '"""Call widget() to begin."""\n') is True


@pytest.mark.unit
class TestNamesUsed:
    """Tests for names_used, the rule every parseable file is read by."""

    def test_finds_a_call(self) -> None:
        """A call reads the name."""
        assert _uses("widget", "widget()\n") is True

    def test_finds_a_call_from_a_sibling(self) -> None:
        """A helper its own file calls is read."""
        content = "def widget():\n    pass\n\n\ndef entry():\n    return widget()\n"
        assert _uses("widget", content) is True

    def test_finds_a_decorator(self) -> None:
        """A decorator reads the name."""
        assert _uses("widget", "@widget\ndef wrapped():\n    pass\n") is True

    def test_finds_a_default(self) -> None:
        """A default reads the name."""
        assert _uses("widget", "def wrapped(maker=widget):\n    pass\n") is True

    def test_finds_a_base_class(self) -> None:
        """A base class reads the name."""
        assert _uses("widget", "class Sub(widget):\n    pass\n") is True

    def test_finds_an_annotation(self) -> None:
        """An annotation reads the name."""
        assert _uses("widget", "value: widget = None\n") is True

    def test_finds_a_parameter_of_that_name(self) -> None:
        """A parameter is how a fixture is asked for, so it reads the name."""
        assert _uses("widget", "def test_it(widget):\n    pass\n") is True

    def test_finds_an_attribute(self) -> None:
        """A call through the module that holds it reads the name."""
        assert _uses("widget", "import pkg\n\npkg.widget()\n") is True

    def test_finds_an_import(self) -> None:
        """An import brings the name in, which is a read."""
        assert _uses("widget", "from pkg import widget\n") is True

    def test_finds_a_renamed_import(self) -> None:
        """An import under another name still reads the name it imports."""
        assert _uses("widget", "from pkg import widget as gadget\n") is True

    def test_finds_a_string_constant(self) -> None:
        """A name written as data crosses a file boundary, as a route does."""
        assert _uses("widget", 'urls = ["views.widget"]\n') is True

    def test_ignores_a_definition_of_the_name(self) -> None:
        """A def binds its name without reading it."""
        assert _uses("widget", "def widget():\n    pass\n") is False

    def test_ignores_a_comment(self) -> None:
        """The parser discards a comment, so a note about a name is not a use."""
        assert _uses("widget", "# we used to call widget here\n") is False

    def test_ignores_a_docstring_mention(self) -> None:
        """Prose about a definition is not a use of it."""
        assert _uses("widget", '"""Call widget() to begin."""\n') is False

    def test_ignores_a_docstring_inside_a_function(self) -> None:
        """A docstring is prose wherever it sits, not only at the top of a file."""
        assert _uses("widget", 'def entry():\n    """Call widget()."""\n') is False

    def test_ignores_an_all_entry(self) -> None:
        """An __all__ entry advertises a name rather than reading it."""
        assert _uses("widget", '__all__ = ["widget"]\n') is False

    def test_ignores_an_extended_all_entry(self) -> None:
        """An __all__ added to is still an __all__."""
        assert _uses("widget", '__all__ = []\n__all__ += ["widget"]\n') is False

    def test_a_re_export_still_counts(self) -> None:
        """An __all__ entry comes with the import that brings the name in."""
        content = 'from .impl import widget\n\n__all__ = ["widget"]\n'
        assert _uses("widget", content) is True

    def test_ignores_a_rebinding(self) -> None:
        """Assigning to the name overwrites it rather than reading it."""
        assert _uses("widget", "widget = 3\n") is False

    def test_ignores_an_unrelated_name(self) -> None:
        """Code that never reads the identifier reports false."""
        assert _uses("widget", "other()\n") is False


@pytest.mark.unit
class TestReadSearched:
    """Tests for read_searched."""

    def test_reads_a_file_as_code(self) -> None:
        """A file that parses is reduced to the names it uses."""
        searched = read_searched({"src/app.py": "widget()\n"})
        assert searched.uses == {"src/app.py": frozenset({"widget"})}

    def test_a_file_that_parses_is_not_kept_as_text(self) -> None:
        """A file read as code has no text left to fall back to."""
        assert not read_searched({"src/app.py": "widget()\n"}).unparsed

    def test_keeps_the_text_of_a_file_that_will_not_parse(self) -> None:
        """A file Python cannot read keeps its raw text for the blunt rule."""
        searched = read_searched({"src/bad.py": "def widget(:\n"})
        assert searched.unparsed == {"src/bad.py": "def widget(:\n"}

    def test_a_file_that_will_not_parse_has_no_uses(self) -> None:
        """A file that will not parse contributes no names."""
        assert not read_searched({"src/bad.py": "def widget(:\n"}).uses

    def test_reads_the_files_in_path_order(self) -> None:
        """Files are read in path order, so a report of them is stable."""
        searched = read_searched({"src/b.py": "", "src/a.py": ""})
        assert list(searched.uses) == ["src/a.py", "src/b.py"]


@pytest.mark.unit
class TestIsAssumedUsedByName:
    """Tests for is_assumed_used_by_name."""

    def test_a_glob_matches(self) -> None:
        """A pattern the name matches claims it."""
        assert is_assumed_used_by_name("test_widget", ["test_*"]) is True

    def test_an_unmatched_name_is_not_claimed(self) -> None:
        """A name no pattern matches is left to the search."""
        assert is_assumed_used_by_name("widget", ["test_*"]) is False

    def test_no_patterns_claim_nothing(self) -> None:
        """The empty default claims nothing, so today's answers stand."""
        assert is_assumed_used_by_name("test_widget", []) is False

    def test_a_later_pattern_still_matches(self) -> None:
        """Any pattern in the list is enough."""
        assert is_assumed_used_by_name("pytest_configure", ["test_*", "pytest_*"]) is True

    def test_matching_is_case_sensitive(self) -> None:
        """Test* and test_* name different things, so case is kept."""
        assert is_assumed_used_by_name("test_widget", ["Test*"]) is False

    def test_an_exact_name_matches(self) -> None:
        """A pattern with no wildcard is an exact name."""
        assert is_assumed_used_by_name("lambda_handler", ["lambda_handler"]) is True


@pytest.mark.unit
class TestIsAssumedUsedByDecorator:
    """Tests for is_assumed_used_by_decorator."""

    def test_a_named_decorator_matches(self) -> None:
        """A decorator the caller named claims the definition."""
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["pytest.fixture"]) is True

    def test_another_decorator_is_not_claimed(self) -> None:
        """A decorator the caller did not name claims nothing."""
        assert is_assumed_used_by_decorator(["functools.cache"], ["pytest.fixture"]) is False

    def test_no_paths_claim_nothing(self) -> None:
        """The empty default claims nothing."""
        assert is_assumed_used_by_decorator(["pytest.fixture"], []) is False

    def test_an_undecorated_definition_is_not_claimed(self) -> None:
        """A definition carrying no decorator matches no path."""
        assert is_assumed_used_by_decorator([], ["pytest.fixture"]) is False

    def test_one_of_several_decorators_is_enough(self) -> None:
        """A definition matching on any decorator it carries is claimed."""
        assert is_assumed_used_by_decorator(["cache", "app.route"], ["app.route"]) is True

    def test_a_partial_path_does_not_match(self) -> None:
        """A path is matched whole, not by its last step."""
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["fixture"]) is False


@pytest.mark.unit
class TestAssumedUsed:
    """Tests for assumed_used."""

    def test_an_unclaimed_definition_is_still_checked(self) -> None:
        """A definition neither input names goes on to the search."""
        checked, _, _ = assumed_used([_definition()], [], [])
        assert checked == [_definition()]

    def test_a_name_match_leaves_the_search(self) -> None:
        """A definition a pattern names is not searched for."""
        checked, _, _ = assumed_used([_definition(name="test_widget")], ["test_*"], [])
        assert not checked

    def test_a_name_match_is_counted_by_name(self) -> None:
        """A definition a pattern names is reported under that ground."""
        _, by_name, _ = assumed_used([_definition(name="test_widget")], ["test_*"], [])
        assert [item.name for item in by_name] == ["test_widget"]

    def test_a_decorator_match_leaves_the_search(self) -> None:
        """A definition carrying a named decorator is not searched for."""
        held = [_definition(decorators=("pytest.fixture",))]
        assert not assumed_used(held, [], ["pytest.fixture"])[0]

    def test_a_decorator_match_is_counted_by_decorator(self) -> None:
        """A definition carrying a named decorator is reported under that ground."""
        held = [_definition(name="widget_fixture", decorators=("pytest.fixture",))]
        _, _, by_decorator = assumed_used(held, [], ["pytest.fixture"])
        assert [item.name for item in by_decorator] == ["widget_fixture"]

    def test_a_definition_matching_both_is_counted_once(self) -> None:
        """A definition both inputs claim is counted against its name alone."""
        held = [_definition(name="test_widget", decorators=("pytest.fixture",))]
        _, _, by_decorator = assumed_used(held, ["test_*"], ["pytest.fixture"])
        assert not by_decorator

    def test_empty_inputs_change_nothing(self) -> None:
        """Passing neither input leaves every definition to the search."""
        held = [_definition(name="test_widget", decorators=("pytest.fixture",))]
        assert assumed_used(held, [], []) == (held, [], [])

    def test_keeps_source_order(self) -> None:
        """The definitions still to check stay in the order they came in."""
        held = [_definition(name="one"), _definition(name="test_two"), _definition(name="three")]
        checked, _, _ = assumed_used(held, ["test_*"], [])
        assert [item.name for item in checked] == ["one", "three"]


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
        """A name another file's code reads is a use."""
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources)) is True

    def test_the_defining_file_counts_as_code(self) -> None:
        """A call from the defining file is a use, because a helper is used."""
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert is_used(_definition(), read_searched(sources)) is True

    def test_the_defining_file_does_not_count_as_prose(self) -> None:
        """A docstring in the defining file mentions the name without using it."""
        sources = {MODULE: '"""Call widget()."""\n\n\ndef widget():\n    pass\n'}
        assert is_used(_definition(), read_searched(sources)) is False

    def test_a_sibling_module_does_not_count_as_prose(self) -> None:
        """A comment left where a call used to be is not a use either."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/app.py": "# we used to call widget here\n",
        }
        assert is_used(_definition(), read_searched(sources)) is False

    def test_the_definition_never_counts_as_its_own_use(self) -> None:
        """A file holding nothing but the definition does not use it."""
        sources = {MODULE: "def widget():\n    pass\n"}
        assert is_used(_definition(), read_searched(sources)) is False

    def test_a_file_that_will_not_parse_falls_back_to_text(self) -> None:
        """A file Python cannot read is searched as text, prose and all."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/bad.py": "# widget was called here\ndef broken(:\n",
        }
        assert is_used(_definition(), read_searched(sources)) is True

    def test_an_unsearched_directory_is_discounted(self) -> None:
        """A use inside the package's own tests does not count."""
        sources = {MODULE: "def widget():\n    pass\n", "test/pkg/test_it.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is False

    def test_an_unsearched_directory_is_discounted_when_it_will_not_parse(self) -> None:
        """A file left out of the search is left out however it is read."""
        sources = {MODULE: "def widget():\n    pass\n", "test/pkg/test_it.py": "widget(:\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is False

    def test_other_tests_still_count(self) -> None:
        """A use in another package's tests is a real use."""
        sources = {MODULE: "def widget():\n    pass\n", "test/other/test_it.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is True

    def test_nothing_to_search_means_unused(self) -> None:
        """With nothing to search, nothing is used."""
        assert is_used(_definition(), read_searched({})) is False


@pytest.mark.unit
class TestUnusedDefinitions:
    """Tests for unused_definitions."""

    def test_reports_an_unused_definition(self) -> None:
        """A definition nothing names is reported."""
        sources = {MODULE: "def widget():\n    pass\n"}
        assert len(unused_definitions([_definition()], read_searched(sources))) == 1

    def test_stays_quiet_about_a_used_definition(self) -> None:
        """A definition something names is not reported."""
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert not unused_definitions([_definition()], read_searched(sources))

    def test_reports_a_definition_kept_alive_only_by_a_comment(self) -> None:
        """A note about a deleted call site no longer hides the dead definition."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/app.py": "# we used to call widget here, removed it last year\n",
        }
        assert len(unused_definitions([_definition()], read_searched(sources))) == 1

    def test_wraps_the_definition_in_a_finding(self) -> None:
        """A finding carries the definition it was made from."""
        sources = {MODULE: "def widget():\n    pass\n"}
        found = unused_definitions([_definition()], read_searched(sources))
        assert found[0].definition == _definition()

    def test_renders_the_template_per_package(self) -> None:
        """Each definition's discounted directory comes from its own package."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions(
            [_definition()], read_searched(sources), "test/lib/python/test_{package}"
        )
        assert len(found) == 1

    def test_a_definition_with_no_package_keeps_its_tests(self) -> None:
        """Without a package there is no directory to discount."""
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions(
            [_definition(package=None)], read_searched(sources), "test/lib/python/test_{package}"
        )
        assert not found

    def test_stays_quiet_about_a_helper_its_own_file_calls(self) -> None:
        """A definition the defining file calls reaches the per-definition check."""
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert not unused_definitions([_definition()], read_searched(sources))

    def test_no_definitions_means_no_findings(self) -> None:
        """An empty list of definitions yields no findings."""
        assert not unused_definitions([], read_searched({MODULE: ""}))
