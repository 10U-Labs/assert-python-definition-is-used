"""Core logic for finding public definitions that nothing else names."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

DEFINITION_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)


@dataclass(frozen=True)
class Definition:
    """A public top-level definition found in a source file."""

    path: str
    line_number: int
    name: str
    package: str | None

    def __str__(self) -> str:
        """Format as path:line:name."""
        return f"{self.path}:{self.line_number}:{self.name}"


@dataclass(frozen=True)
class Finding:
    """A definition that nothing in the searched trees names."""

    definition: Definition

    @property
    def path(self) -> str:
        """The file the definition sits in."""
        return self.definition.path

    @property
    def line_number(self) -> int:
        """The line the definition starts on."""
        return self.definition.line_number

    @property
    def name(self) -> str:
        """The name of the definition."""
        return self.definition.name

    def __str__(self) -> str:
        """Format as path:line:name."""
        return str(self.definition)


def is_public(name: str) -> bool:
    """Check whether a name is public, meaning it has no leading underscore."""
    return not name.startswith("_")


def public_definitions(path: str, content: str, package: str | None = None) -> list[Definition]:
    """Find every public top-level definition in a source file.

    Only top-level statements are read. A method on a class and a function
    nested inside another function are reached through the name of the thing
    that holds them, so neither is a definition this tool can speak about.

    Args:
        path: The file path, used for reporting.
        content: The file content to parse.
        package: The package the file belongs to, if any.

    Returns:
        The public definitions, in the order they appear.

    Raises:
        SyntaxError: If the content cannot be parsed as Python.
    """
    tree = ast.parse(content, filename=path)
    return [
        Definition(path=path, line_number=node.lineno, name=node.name, package=package)
        for node in tree.body
        if isinstance(node, DEFINITION_NODES) and is_public(node.name)
    ]


@lru_cache(maxsize=4096)
def _word_pattern(name: str) -> re.Pattern[str]:
    """Compile, and remember, a whole-word pattern for a name."""
    return re.compile(rf"\b{re.escape(name)}\b")


def names_in_line(name: str, line: str) -> bool:
    """Check whether a line names an identifier as a whole word."""
    return _word_pattern(name).search(line) is not None


def names_in_content(name: str, content: str, skipped_line: int | None = None) -> bool:
    """Check whether content names an identifier as a whole word.

    Args:
        name: The identifier to look for.
        content: The text to search.
        skipped_line: A 1-indexed line to ignore, if any.

    Returns:
        True if any line other than the skipped one names the identifier.
    """
    if skipped_line is None:
        return names_in_line(name, content)
    return any(
        names_in_line(name, line)
        for number, line in enumerate(content.splitlines(), 1)
        if number != skipped_line
    )


def unsearched_directory(template: str | None, package: str | None) -> str | None:
    """Render the directory left out of the search for a package's definitions.

    The usual case is a package's own tests, which name every definition they
    exercise and so make a module kept alive only by them read as used.

    Args:
        template: A path template containing ``{package}``, or None.
        package: The package name to substitute, or None.

    Returns:
        The rendered directory with a trailing separator, or None when there
        is no template or the file belongs to no package.
    """
    if template is None or package is None:
        return None
    rendered = template.format(package=package)
    return rendered if rendered.endswith("/") else rendered + "/"


def _searchable(
    sources: dict[str, str],
    definition: Definition,
    unsearched: str | None,
    count_defining_file: bool,
) -> Iterator[tuple[str, int | None]]:
    """Yield each file to search, with the line to ignore within it."""
    for path, content in sources.items():
        if unsearched is not None and path.startswith(unsearched):
            continue
        if path == definition.path:
            if not count_defining_file:
                continue
            yield content, definition.line_number
        else:
            yield content, None


def is_used(
    definition: Definition,
    sources: dict[str, str],
    unsearched: str | None = None,
    count_defining_file: bool = False,
) -> bool:
    """Check whether anything names a definition.

    Args:
        definition: The definition to look for.
        sources: Every searched file, keyed by path, mapped to its content.
        unsearched: A directory to leave out of the search, if any, however
            often its files name the definition.
        count_defining_file: Whether a name written elsewhere in the defining
            file counts as a use. A docstring example, an ``__all__`` entry and
            a call from a function that is itself dead all read alike, so this
            is off by default.

    Returns:
        True if any file names the definition.
    """
    searchable = _searchable(sources, definition, unsearched, count_defining_file)
    return any(
        names_in_content(definition.name, content, skipped) for content, skipped in searchable
    )


def unused_definitions(
    definitions: list[Definition],
    sources: dict[str, str],
    unsearched_template: str | None = None,
    count_defining_file: bool = False,
) -> list[Finding]:
    """Find the definitions nothing names.

    Args:
        definitions: The definitions to check.
        sources: Every searched file, keyed by path, mapped to its content.
        unsearched_template: A path template containing ``{package}`` whose
            files are left out of the search, if any.
        count_defining_file: Whether a name written elsewhere in the defining
            file counts as a use.

    Returns:
        A finding for each definition nothing names.
    """
    findings = []
    for definition in definitions:
        unsearched = unsearched_directory(unsearched_template, definition.package)
        if not is_used(definition, sources, unsearched, count_defining_file):
            findings.append(Finding(definition=definition))
    return findings
