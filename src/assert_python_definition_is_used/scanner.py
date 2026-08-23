"""Core logic for finding public definitions that nothing else names."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache

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


def names_in_text(name: str, text: str) -> bool:
    """Check whether text names an identifier as a whole word.

    This is the blunt cross-file rule. Any file that writes the name, in code
    or in prose, counts as naming it, because the alternative is resolving
    imports across a repository that may not even be importable.

    Args:
        name: The identifier to look for.
        text: The text to search.

    Returns:
        True if the text names the identifier as a whole word.
    """
    return _word_pattern(name).search(text) is not None


def _reads(node: ast.AST, name: str) -> bool:
    """Check whether one syntax node reads an identifier."""
    if isinstance(node, ast.Name):
        return node.id == name and isinstance(node.ctx, ast.Load)
    if isinstance(node, ast.arg):
        return node.arg == name
    return False


def names_in_code(name: str, content: str) -> bool:
    """Check whether a file's code reads an identifier.

    This is the rule for the file a definition lives in, where the parsed
    module is already to hand. Only a read counts: a call, a decorator, a
    default, a base class, an annotation, or a parameter of that name, which
    is how a fixture is asked for. The same word inside a docstring, a comment
    or an ``__all__`` entry is prose about the definition rather than a use of
    it, and crediting it would leave a dead definition unreported.

    A ``def`` or ``class`` statement binds its name without reading it, so a
    definition never counts as its own use and needs no line discounted.

    Args:
        name: The identifier to look for.
        content: The file content, which must parse.

    Returns:
        True if the file's code reads the identifier.

    Raises:
        SyntaxError: If the content cannot be parsed as Python.
    """
    return any(_reads(node, name) for node in ast.walk(ast.parse(content)))


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


def is_used(
    definition: Definition,
    sources: dict[str, str],
    unsearched: str | None = None,
) -> bool:
    """Check whether anything reads a definition.

    The file that holds the definition is read as code, every other file as
    text. A definition its own file calls is a helper doing its job and is
    used; one its own file only mentions in prose is not.

    Args:
        definition: The definition to look for.
        sources: Every searched file, keyed by path, mapped to its content.
        unsearched: A directory to leave out of the search, if any, however
            often its files name the definition.

    Returns:
        True if any file reads the definition.
    """
    for path, content in sources.items():
        if unsearched is not None and path.startswith(unsearched):
            continue
        if path == definition.path:
            if names_in_code(definition.name, content):
                return True
        elif names_in_text(definition.name, content):
            return True
    return False


def unused_definitions(
    definitions: list[Definition],
    sources: dict[str, str],
    unsearched_template: str | None = None,
) -> list[Finding]:
    """Find the definitions nothing names.

    Args:
        definitions: The definitions to check.
        sources: Every searched file, keyed by path, mapped to its content.
        unsearched_template: A path template containing ``{package}`` whose
            files are left out of the search, if any.

    Returns:
        A finding for each definition nothing names.
    """
    findings = []
    for definition in definitions:
        unsearched = unsearched_directory(unsearched_template, definition.package)
        if not is_used(definition, sources, unsearched):
            findings.append(Finding(definition=definition))
    return findings
