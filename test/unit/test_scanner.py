from __future__ import annotations

import ast

import pytest

from assert_python_definition_is_used.scanner import (
    Definition,
    Finding,
    assumed_used,
    imported_modules,
    is_assumed_used_by_decorator,
    is_assumed_used_by_name,
    is_imported,
    is_public,
    is_used,
    names_in_text,
    names_used,
    read_searched,
    unimported_packages,
    unsearched_directory,
    public_definitions,
    unused_definitions,
)

MODULE = "lib/python/pkg/__init__.py"


def _uses(name: str, content: str) -> bool:
    return name in names_used(ast.parse(content))


def _imports(content: str) -> frozenset[str]:
    return imported_modules(ast.parse(content))


def _definition(
    name: str = "widget",
    line: int = 1,
    package: str | None = "pkg",
    decorators: tuple[str, ...] = (),
) -> Definition:
    return Definition(
        path=MODULE, line_number=line, name=name, package=package, decorators=decorators
    )


@pytest.mark.unit
class TestDefinition:
    def test_formats_as_path_line_name(self) -> None:
        assert str(_definition(line=7)) == f"{MODULE}:7:widget"

    def test_keeps_its_package(self) -> None:
        assert _definition().package == "pkg"

    def test_is_hashable(self) -> None:
        assert len({_definition(), _definition()}) == 1

    def test_carries_no_decorators_by_default(self) -> None:
        assert not _definition().decorators

    def test_keeps_its_decorators(self) -> None:
        assert _definition(decorators=("pytest.fixture",)).decorators == ("pytest.fixture",)


@pytest.mark.unit
class TestFinding:
    def test_exposes_path(self) -> None:
        assert Finding(definition=_definition()).path == MODULE

    def test_exposes_line_number(self) -> None:
        assert Finding(definition=_definition(line=12)).line_number == 12

    def test_exposes_name(self) -> None:
        assert Finding(definition=_definition(name="gadget")).name == "gadget"

    def test_formats_as_path_line_name(self) -> None:
        assert str(Finding(definition=_definition(line=3))) == f"{MODULE}:3:widget"


@pytest.mark.unit
class TestIsPublic:
    def test_plain_name_is_public(self) -> None:
        assert is_public("widget") is True

    def test_underscore_name_is_not_public(self) -> None:
        assert is_public("_widget") is False

    def test_dunder_is_not_public(self) -> None:
        assert is_public("__init__") is False


@pytest.mark.unit
class TestPublicDefinitions:
    def test_finds_a_function(self) -> None:
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].name == "widget"

    def test_finds_an_async_function(self) -> None:
        found = public_definitions(MODULE, "async def widget():\n    pass\n")
        assert found[0].name == "widget"

    def test_finds_a_class(self) -> None:
        found = public_definitions(MODULE, "class Widget:\n    pass\n")
        assert found[0].name == "Widget"

    def test_records_the_line(self) -> None:
        found = public_definitions(MODULE, "\n\ndef widget():\n    pass\n")
        assert found[0].line_number == 3

    def test_skips_a_private_definition(self) -> None:
        assert not public_definitions(MODULE, "def _widget():\n    pass\n")

    def test_skips_a_method(self) -> None:
        found = public_definitions(MODULE, "class Widget:\n    def spin(self):\n        pass\n")
        assert [item.name for item in found] == ["Widget"]

    def test_skips_a_nested_function(self) -> None:
        found = public_definitions(MODULE, "def widget():\n    def spin():\n        pass\n")
        assert [item.name for item in found] == ["widget"]

    def test_keeps_source_order(self) -> None:
        found = public_definitions(MODULE, "def one():\n    pass\ndef two():\n    pass\n")
        assert [item.name for item in found] == ["one", "two"]

    def test_carries_the_package_through(self) -> None:
        found = public_definitions(MODULE, "def widget():\n    pass\n", package="pkg")
        assert found[0].package == "pkg"

    def test_package_defaults_to_none(self) -> None:
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].package is None

    def test_empty_file_yields_nothing(self) -> None:
        assert not public_definitions(MODULE, "")

    def test_raises_on_unparseable_content(self) -> None:
        with pytest.raises(SyntaxError):
            public_definitions(MODULE, "def widget(:\n")


@pytest.mark.unit
class TestPublicDefinitionsReadingDecorators:
    def test_an_undecorated_definition_carries_nothing(self) -> None:
        found = public_definitions(MODULE, "def widget():\n    pass\n")
        assert found[0].decorators == ()

    def test_reads_a_bare_decorator(self) -> None:
        found = public_definitions(MODULE, "@task\ndef widget():\n    pass\n")
        assert found[0].decorators == ("task",)

    def test_reads_a_dotted_decorator(self) -> None:
        found = public_definitions(MODULE, "@pytest.fixture\ndef widget():\n    pass\n")
        assert found[0].decorators == ("pytest.fixture",)

    def test_reads_a_called_decorator(self) -> None:
        content = '@pytest.fixture(name="other")\ndef widget():\n    pass\n'
        assert public_definitions(MODULE, content)[0].decorators == ("pytest.fixture",)

    def test_reads_a_deeply_dotted_decorator(self) -> None:
        found = public_definitions(MODULE, "@app.api.route\ndef widget():\n    pass\n")
        assert found[0].decorators == ("app.api.route",)

    def test_drops_a_decorator_it_cannot_flatten(self) -> None:
        found = public_definitions(MODULE, '@registry["a"]\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_drops_an_unflattenable_decorator_root(self) -> None:
        found = public_definitions(MODULE, '@registry["a"].wrap\ndef widget():\n    pass\n')
        assert found[0].decorators == ()

    def test_reads_every_decorator(self) -> None:
        content = "@one\n@two.three\ndef widget():\n    pass\n"
        assert public_definitions(MODULE, content)[0].decorators == ("one", "two.three")

    def test_reads_a_decorated_class(self) -> None:
        found = public_definitions(MODULE, "@register\nclass Widget:\n    pass\n")
        assert found[0].decorators == ("register",)


@pytest.mark.unit
class TestNamesInText:
    def test_finds_a_whole_word(self) -> None:
        assert names_in_text("widget", "value = widget()") is True

    def test_ignores_a_longer_word(self) -> None:
        assert names_in_text("widget", "value = widgetry()") is False

    def test_ignores_a_prefixed_word(self) -> None:
        assert names_in_text("widget", "value = my_widget") is False

    def test_finds_an_attribute_access(self) -> None:
        assert names_in_text("widget", "value = module.widget") is True

    def test_escapes_regex_characters(self) -> None:
        assert names_in_text("a.b", "value = a.b") is True

    def test_finds_a_name_on_any_line(self) -> None:
        assert names_in_text("widget", "import x\nvalue = widget()\n") is True

    def test_absent_name_is_not_found(self) -> None:
        assert names_in_text("widget", "import x\n") is False

    def test_counts_a_name_written_in_prose(self) -> None:
        assert names_in_text("widget", '"""Call widget() to begin."""\n') is True


@pytest.mark.unit
class TestNamesUsed:
    def test_finds_a_call(self) -> None:
        assert _uses("widget", "widget()\n") is True

    def test_finds_a_call_from_a_sibling(self) -> None:
        content = "def widget():\n    pass\n\n\ndef entry():\n    return widget()\n"
        assert _uses("widget", content) is True

    def test_finds_a_decorator(self) -> None:
        assert _uses("widget", "@widget\ndef wrapped():\n    pass\n") is True

    def test_finds_a_default(self) -> None:
        assert _uses("widget", "def wrapped(maker=widget):\n    pass\n") is True

    def test_finds_a_base_class(self) -> None:
        assert _uses("widget", "class Sub(widget):\n    pass\n") is True

    def test_finds_an_annotation(self) -> None:
        assert _uses("widget", "value: widget = None\n") is True

    def test_finds_a_parameter_of_that_name(self) -> None:
        assert _uses("widget", "def test_it(widget):\n    pass\n") is True

    def test_finds_an_attribute(self) -> None:
        assert _uses("widget", "import pkg\n\npkg.widget()\n") is True

    def test_finds_an_import(self) -> None:
        assert _uses("widget", "from pkg import widget\n") is True

    def test_finds_a_renamed_import(self) -> None:
        assert _uses("widget", "from pkg import widget as gadget\n") is True

    def test_finds_a_string_constant(self) -> None:
        assert _uses("widget", 'urls = ["views.widget"]\n') is True

    def test_ignores_a_definition_of_the_name(self) -> None:
        assert _uses("widget", "def widget():\n    pass\n") is False

    def test_ignores_a_comment(self) -> None:
        assert _uses("widget", "# we used to call widget here\n") is False

    def test_ignores_a_docstring_mention(self) -> None:
        assert _uses("widget", '"""Call widget() to begin."""\n') is False

    def test_ignores_a_docstring_inside_a_function(self) -> None:
        assert _uses("widget", 'def entry():\n    """Call widget()."""\n') is False

    def test_ignores_an_all_entry(self) -> None:
        assert _uses("widget", '__all__ = ["widget"]\n') is False

    def test_ignores_an_extended_all_entry(self) -> None:
        assert _uses("widget", '__all__ = []\n__all__ += ["widget"]\n') is False

    def test_a_re_export_still_counts(self) -> None:
        content = 'from .impl import widget\n\n__all__ = ["widget"]\n'
        assert _uses("widget", content) is True

    def test_ignores_a_rebinding(self) -> None:
        assert _uses("widget", "widget = 3\n") is False

    def test_ignores_an_unrelated_name(self) -> None:
        assert _uses("widget", "other()\n") is False


@pytest.mark.unit
class TestReadSearched:
    def test_reads_a_file_as_code(self) -> None:
        searched = read_searched({"src/app.py": "widget()\n"})
        assert searched.uses == {"src/app.py": frozenset({"widget"})}

    def test_a_file_that_parses_is_not_kept_as_text(self) -> None:
        assert not read_searched({"src/app.py": "widget()\n"}).unparsed

    def test_keeps_the_text_of_a_file_that_will_not_parse(self) -> None:
        searched = read_searched({"src/bad.py": "def widget(:\n"})
        assert searched.unparsed == {"src/bad.py": "def widget(:\n"}

    def test_a_file_that_will_not_parse_has_no_uses(self) -> None:
        assert not read_searched({"src/bad.py": "def widget(:\n"}).uses

    def test_reads_the_files_in_path_order(self) -> None:
        searched = read_searched({"src/b.py": "", "src/a.py": ""})
        assert list(searched.uses) == ["src/a.py", "src/b.py"]

    def test_reads_the_imports_of_a_file(self) -> None:
        searched = read_searched({"src/app.py": "import pkg\n"})
        assert searched.imports == {"src/app.py": frozenset({"pkg"})}

    def test_a_file_that_will_not_parse_has_no_imports(self) -> None:
        assert not read_searched({"src/bad.py": "def widget(:\n"}).imports


@pytest.mark.unit
class TestIsAssumedUsedByName:
    def test_a_glob_matches(self) -> None:
        assert is_assumed_used_by_name("test_widget", ["test_*"]) is True

    def test_an_unmatched_name_is_not_claimed(self) -> None:
        assert is_assumed_used_by_name("widget", ["test_*"]) is False

    def test_no_patterns_claim_nothing(self) -> None:
        assert is_assumed_used_by_name("test_widget", []) is False

    def test_a_later_pattern_still_matches(self) -> None:
        assert is_assumed_used_by_name("pytest_configure", ["test_*", "pytest_*"]) is True

    def test_matching_is_case_sensitive(self) -> None:
        assert is_assumed_used_by_name("test_widget", ["Test*"]) is False

    def test_an_exact_name_matches(self) -> None:
        assert is_assumed_used_by_name("lambda_handler", ["lambda_handler"]) is True


@pytest.mark.unit
class TestIsAssumedUsedByDecorator:
    def test_a_named_decorator_matches(self) -> None:
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["pytest.fixture"]) is True

    def test_another_decorator_is_not_claimed(self) -> None:
        assert is_assumed_used_by_decorator(["functools.cache"], ["pytest.fixture"]) is False

    def test_no_paths_claim_nothing(self) -> None:
        assert is_assumed_used_by_decorator(["pytest.fixture"], []) is False

    def test_an_undecorated_definition_is_not_claimed(self) -> None:
        assert is_assumed_used_by_decorator([], ["pytest.fixture"]) is False

    def test_one_of_several_decorators_is_enough(self) -> None:
        assert is_assumed_used_by_decorator(["cache", "app.route"], ["app.route"]) is True

    def test_a_partial_path_does_not_match(self) -> None:
        assert is_assumed_used_by_decorator(["pytest.fixture"], ["fixture"]) is False


@pytest.mark.unit
class TestAssumedUsed:
    def test_an_unclaimed_definition_is_still_checked(self) -> None:
        checked, _, _ = assumed_used([_definition()], [], [])
        assert checked == [_definition()]

    def test_a_name_match_leaves_the_search(self) -> None:
        checked, _, _ = assumed_used([_definition(name="test_widget")], ["test_*"], [])
        assert not checked

    def test_a_name_match_is_counted_by_name(self) -> None:
        _, by_name, _ = assumed_used([_definition(name="test_widget")], ["test_*"], [])
        assert [item.name for item in by_name] == ["test_widget"]

    def test_a_decorator_match_leaves_the_search(self) -> None:
        held = [_definition(decorators=("pytest.fixture",))]
        assert not assumed_used(held, [], ["pytest.fixture"])[0]

    def test_a_decorator_match_is_counted_by_decorator(self) -> None:
        held = [_definition(name="widget_fixture", decorators=("pytest.fixture",))]
        _, _, by_decorator = assumed_used(held, [], ["pytest.fixture"])
        assert [item.name for item in by_decorator] == ["widget_fixture"]

    def test_a_definition_matching_both_is_counted_once(self) -> None:
        held = [_definition(name="test_widget", decorators=("pytest.fixture",))]
        _, _, by_decorator = assumed_used(held, ["test_*"], ["pytest.fixture"])
        assert not by_decorator

    def test_empty_inputs_change_nothing(self) -> None:
        held = [_definition(name="test_widget", decorators=("pytest.fixture",))]
        assert assumed_used(held, [], []) == (held, [], [])

    def test_keeps_source_order(self) -> None:
        held = [_definition(name="one"), _definition(name="test_two"), _definition(name="three")]
        checked, _, _ = assumed_used(held, ["test_*"], [])
        assert [item.name for item in checked] == ["one", "three"]


@pytest.mark.unit
class TestUnsearchedDirectory:
    def test_renders_the_package(self) -> None:
        assert unsearched_directory("test/lib/python/test_{package}", "pkg") == (
            "test/lib/python/test_pkg/"
        )

    def test_keeps_an_existing_separator(self) -> None:
        assert unsearched_directory("test/{package}/", "pkg") == "test/pkg/"

    def test_no_template_means_no_directory(self) -> None:
        assert unsearched_directory(None, "pkg") is None

    def test_no_package_means_no_directory(self) -> None:
        assert unsearched_directory("test/{package}", None) is None


@pytest.mark.unit
class TestIsUsed:
    def test_a_sibling_module_counts(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources)) is True

    def test_the_defining_file_counts_as_code(self) -> None:
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert is_used(_definition(), read_searched(sources)) is True

    def test_the_defining_file_does_not_count_as_prose(self) -> None:
        sources = {MODULE: '"""Call widget()."""\n\n\ndef widget():\n    pass\n'}
        assert is_used(_definition(), read_searched(sources)) is False

    def test_a_sibling_module_does_not_count_as_prose(self) -> None:
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/app.py": "# we used to call widget here\n",
        }
        assert is_used(_definition(), read_searched(sources)) is False

    def test_the_definition_never_counts_as_its_own_use(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n"}
        assert is_used(_definition(), read_searched(sources)) is False

    def test_a_file_that_will_not_parse_falls_back_to_text(self) -> None:
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/bad.py": "# widget was called here\ndef broken(:\n",
        }
        assert is_used(_definition(), read_searched(sources)) is True

    def test_an_unsearched_directory_is_discounted(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n", "test/pkg/test_it.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is False

    def test_an_unsearched_directory_is_discounted_when_it_will_not_parse(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n", "test/pkg/test_it.py": "widget(:\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is False

    def test_other_tests_still_count(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n", "test/other/test_it.py": "widget()\n"}
        assert is_used(_definition(), read_searched(sources), unsearched="test/pkg/") is True

    def test_nothing_to_search_means_unused(self) -> None:
        assert is_used(_definition(), read_searched({})) is False


@pytest.mark.unit
class TestUnusedDefinitions:
    def test_reports_an_unused_definition(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n"}
        assert len(unused_definitions([_definition()], read_searched(sources))) == 1

    def test_stays_quiet_about_a_used_definition(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n", "src/app.py": "widget()\n"}
        assert not unused_definitions([_definition()], read_searched(sources))

    def test_reports_a_definition_kept_alive_only_by_a_comment(self) -> None:
        sources = {
            MODULE: "def widget():\n    pass\n",
            "src/app.py": "# we used to call widget here, removed it last year\n",
        }
        assert len(unused_definitions([_definition()], read_searched(sources))) == 1

    def test_wraps_the_definition_in_a_finding(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n"}
        found = unused_definitions([_definition()], read_searched(sources))
        assert found[0].definition == _definition()

    def test_renders_the_template_per_package(self) -> None:
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions(
            [_definition()], read_searched(sources), "test/lib/python/test_{package}"
        )
        assert len(found) == 1

    def test_a_definition_with_no_package_keeps_its_tests(self) -> None:
        sources = {
            MODULE: "def widget():\n    pass\n",
            "test/lib/python/test_pkg/test_it.py": "widget()\n",
        }
        found = unused_definitions(
            [_definition(package=None)], read_searched(sources), "test/lib/python/test_{package}"
        )
        assert not found

    def test_stays_quiet_about_a_helper_its_own_file_calls(self) -> None:
        sources = {MODULE: "def widget():\n    pass\nwidget()\n"}
        assert not unused_definitions([_definition()], read_searched(sources))

    def test_no_definitions_means_no_findings(self) -> None:
        assert not unused_definitions([], read_searched({MODULE: ""}))


@pytest.mark.unit
class TestImportedModules:
    def test_reads_a_plain_import(self) -> None:
        assert _imports("import pkg\n") == frozenset({"pkg"})

    def test_reads_only_the_top_level_of_a_dotted_import(self) -> None:
        assert _imports("import pkg.inner.mod\n") == frozenset({"pkg"})

    def test_reads_a_renamed_import(self) -> None:
        assert _imports("import pkg as shortcut\n") == frozenset({"pkg"})

    def test_reads_every_name_in_one_import(self) -> None:
        assert _imports("import one, two\n") == frozenset({"one", "two"})

    def test_reads_a_from_import(self) -> None:
        assert _imports("from pkg import widget\n") == frozenset({"pkg"})

    def test_reads_only_the_top_level_of_a_dotted_from_import(self) -> None:
        assert _imports("from pkg.inner import widget\n") == frozenset({"pkg"})

    def test_reads_an_import_buried_in_a_function(self) -> None:
        assert _imports("def entry():\n    import pkg\n") == frozenset({"pkg"})

    def test_a_bare_relative_import_names_no_package(self) -> None:
        assert not _imports("from . import widget\n")

    def test_a_relative_module_import_names_no_package(self) -> None:
        assert not _imports("from .inner import widget\n")

    def test_naming_a_module_is_not_importing_it(self) -> None:
        assert not _imports("pkg.widget()\n")

    def test_an_empty_file_imports_nothing(self) -> None:
        assert not _imports("")


@pytest.mark.unit
class TestIsImported:
    def test_a_sibling_module_importing_it_counts(self) -> None:
        sources = {MODULE: "", "src/app.py": "import pkg\n"}
        assert is_imported(_definition(name="pkg"), read_searched(sources)) is True

    def test_a_from_import_counts(self) -> None:
        sources = {MODULE: "", "src/app.py": "from pkg import widget\n"}
        assert is_imported(_definition(name="pkg"), read_searched(sources)) is True

    def test_a_name_written_as_a_bare_word_is_not_an_import(self) -> None:
        sources = {MODULE: "", "src/app.py": "def get_client():\n    pass\n"}
        package = _definition(name="get_client", package="get_client")
        assert is_imported(package, read_searched(sources)) is False

    def test_a_file_that_will_not_parse_does_not_import(self) -> None:
        sources = {MODULE: "", "src/bad.py": "import pkg(\n"}
        assert is_imported(_definition(name="pkg"), read_searched(sources)) is False

    def test_an_unsearched_directory_is_discounted(self) -> None:
        sources = {MODULE: "", "test/pkg/test_it.py": "import pkg\n"}
        found = is_imported(_definition(name="pkg"), read_searched(sources), "test/pkg/")
        assert found is False

    def test_another_directory_still_counts(self) -> None:
        sources = {MODULE: "", "test/other/test_it.py": "import pkg\n"}
        found = is_imported(_definition(name="pkg"), read_searched(sources), "test/pkg/")
        assert found is True

    def test_nothing_to_search_means_unimported(self) -> None:
        assert is_imported(_definition(name="pkg"), read_searched({})) is False


@pytest.mark.unit
class TestUnimportedPackages:
    def test_reports_a_package_nothing_imports(self) -> None:
        sources = {MODULE: "def widget():\n    pass\n"}
        found = unimported_packages([_definition(name="pkg")], read_searched(sources))
        assert len(found) == 1

    def test_stays_quiet_about_a_package_a_sibling_imports(self) -> None:
        sources = {MODULE: "", "src/app.py": "import pkg\n"}
        assert not unimported_packages([_definition(name="pkg")], read_searched(sources))

    def test_reports_a_package_only_its_own_tests_import(self) -> None:
        sources = {MODULE: "", "test/lib/python/test_pkg/test_it.py": "import pkg\n"}
        found = unimported_packages(
            [_definition(name="pkg")], read_searched(sources), "test/lib/python/test_{package}"
        )
        assert len(found) == 1

    def test_reports_the_package_whose_name_is_only_ever_a_bare_word(self) -> None:
        sources = {MODULE: "", "src/app.py": "def get_client():\n    return 1\n"}
        packages = [_definition(name="get_client", package="get_client")]
        assert len(unimported_packages(packages, read_searched(sources))) == 1

    def test_anchors_the_finding_on_the_init_file(self) -> None:
        found = unimported_packages([_definition(name="pkg")], read_searched({MODULE: ""}))
        assert str(found[0]) == f"{MODULE}:1:pkg"

    def test_no_packages_means_no_findings(self) -> None:
        assert not unimported_packages([], read_searched({MODULE: ""}))
