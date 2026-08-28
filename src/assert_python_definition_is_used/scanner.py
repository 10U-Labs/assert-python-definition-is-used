"""Core logic for finding public definitions that nothing else names."""

from __future__ import annotations

import ast
import fnmatch
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFINITION_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)
DOCSTRING_HOLDERS = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Module)

DocstringHolder = ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef | ast.Module

WORDS = re.compile(r"\w+")


@dataclass(frozen=True)
class Definition:
    """A public top-level definition found in a source file."""

    path: str
    line_number: int
    name: str
    package: str | None
    decorators: tuple[str, ...] = ()

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


@dataclass(frozen=True)
class Searched:
    """Every searched file, read as code where it parses."""

    uses: dict[str, frozenset[str]]
    unparsed: dict[str, str]


def is_public(name: str) -> bool:
    """Check whether a name is public, meaning it has no leading underscore."""
    return not name.startswith("_")


def _decorator_path(node: ast.expr) -> str | None:
    """Flatten one decorator expression to a dotted name, or None."""
    if isinstance(node, ast.Call):
        return _decorator_path(node.func)
    if isinstance(node, ast.Attribute):
        parent = _decorator_path(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return None


def _decorators_of(node: ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef) -> tuple[str, ...]:
    """Read the dotted names of the decorators a definition carries.

    A decorator that does not flatten to a dotted name, such as one read out
    of a subscript, is left out rather than raising, so that it matches
    nothing and the run carries on.
    """
    flattened = (_decorator_path(item) for item in node.decorator_list)
    return tuple(dotted for dotted in flattened if dotted is not None)


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
        Definition(
            path=path,
            line_number=node.lineno,
            name=node.name,
            package=package,
            decorators=_decorators_of(node),
        )
        for node in tree.body
        if isinstance(node, DEFINITION_NODES) and is_public(node.name)
    ]


@lru_cache(maxsize=4096)
def _word_pattern(name: str) -> re.Pattern[str]:
    """Compile, and remember, a whole-word pattern for a name."""
    return re.compile(rf"\b{re.escape(name)}\b")


def names_in_text(name: str, text: str) -> bool:
    """Check whether text names an identifier as a whole word.

    This is the fallback for a file that will not parse, where there is no
    syntax tree to ask. Any file that writes the name, in code or in prose,
    counts as naming it, so a repository holding a file Python cannot read
    keeps the blunt rule on that file rather than failing.

    Args:
        name: The identifier to look for.
        text: The text to search.

    Returns:
        True if the text names the identifier as a whole word.
    """
    return _word_pattern(name).search(text) is not None


def _names_read(node: ast.AST) -> tuple[str, ...]:
    """Read the names one syntax node reads."""
    if isinstance(node, ast.Name):
        return (node.id,) if isinstance(node.ctx, ast.Load) else ()
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, ast.alias):
        imported = node.name.split(".")
        return (*imported, node.asname) if node.asname else tuple(imported)
    if isinstance(node, ast.arg):
        return (node.arg,)
    return ()


def _string_value(node: ast.AST) -> str | None:
    """Read the text of one string constant, or None if the node is not one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _docstring_of(node: DocstringHolder) -> ast.expr | None:
    """Read the docstring of a module, class or function, if it has one."""
    first = node.body[0] if node.body else None
    if isinstance(first, ast.Expr) and _string_value(first.value) is not None:
        return first.value
    return None


def _all_value(node: ast.AST) -> ast.expr | None:
    """Read the value a statement assigns to ``__all__``, if it assigns one."""
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return None
    named = any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets)
    return node.value if named else None


def _prose_constants(tree: ast.Module) -> set[int]:
    """Find the string constants that talk about a name rather than write it.

    A docstring is the first statement of a module, class or function, and an
    ``__all__`` entry sits in the value assigned to that name, so both are
    identifiable by structure rather than by guessing at their contents.

    Args:
        tree: The parsed file.

    Returns:
        The identities of the string constant nodes to discount.
    """
    prose: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, DOCSTRING_HOLDERS):
            docstring = _docstring_of(node)
            if docstring is not None:
                prose.add(id(docstring))
        advertised = _all_value(node)
        if advertised is not None:
            prose.update(
                id(child) for child in ast.walk(advertised) if _string_value(child) is not None
            )
    return prose


def names_used(tree: ast.Module) -> frozenset[str]:
    """Read every name a file uses.

    A file uses a name when its syntax tree reads it, which a call, a
    decorator, a default, a base class, an annotation, an attribute, an import,
    and a parameter of that name all do, the last being how a fixture is asked
    for. A file also uses a name when it writes it in a string constant, which
    is how a name crosses a file boundary as data, the way a Django route
    reaches a view.

    A comment is not a use: the parser discards it, so it cannot be found in a
    tree at all. A docstring and an ``__all__`` entry are not either, because
    both are prose about a definition rather than a use of it, and crediting
    them would leave a dead definition unreported. A re-export still counts,
    because the ``__all__`` entry naming a definition is always accompanied by
    the import that brings it in, and the import is a read.

    A ``def`` or ``class`` statement binds its name without reading it, so a
    definition never counts as its own use.

    Args:
        tree: The parsed file.

    Returns:
        Every name the file uses.
    """
    prose = _prose_constants(tree)
    names: set[str] = set()
    for node in ast.walk(tree):
        names.update(_names_read(node))
        written = _string_value(node)
        if written is not None and id(node) not in prose:
            names.update(WORDS.findall(written))
    return frozenset(names)


def read_searched(sources: dict[str, str]) -> Searched:
    """Read every searched file as code, keeping the text of what will not parse.

    Every file this tool reads is a Python file, so every one of them is read
    as code. A file that raises ``SyntaxError`` keeps its raw text for the
    blunt rule instead of failing the run.

    Args:
        sources: Every searched file, keyed by path, mapped to its content.

    Returns:
        The names used by each file that parses, and the raw text of each file
        that does not, both in path order.
    """
    uses: dict[str, frozenset[str]] = {}
    unparsed: dict[str, str] = {}
    for path in sorted(sources):
        try:
            tree = ast.parse(sources[path], filename=path)
        except SyntaxError:
            unparsed[path] = sources[path]
            continue
        uses[path] = names_used(tree)
    return Searched(uses=uses, unparsed=unparsed)


def is_assumed_used_by_name(name: str, patterns: Sequence[str]) -> bool:
    """Check whether a caller's name patterns claim a definition is invoked.

    Args:
        name: The definition's name.
        patterns: Glob patterns, matched case sensitively.

    Returns:
        True if any pattern matches the name.
    """
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def is_assumed_used_by_decorator(decorators: Sequence[str], paths: Sequence[str]) -> bool:
    """Check whether a caller's decorator paths claim a definition is invoked.

    Args:
        decorators: The dotted decorator names the definition carries.
        paths: The dotted paths the caller named.

    Returns:
        True if the definition carries any of the named decorators.
    """
    return any(decorator in paths for decorator in decorators)


def assumed_used(
    definitions: list[Definition],
    name_patterns: Sequence[str],
    decorator_paths: Sequence[str],
) -> tuple[list[Definition], list[Definition], list[Definition]]:
    """Take out the definitions a caller says a runtime invokes.

    A definition invoked by a runtime rather than by written Python has no
    call site to find, so no search can answer for it. The caller names those
    definitions instead, by the shape of their names or by the decorators they
    carry, and what it names is neither searched for nor reported.

    Args:
        definitions: The definitions read from the trees.
        name_patterns: Glob patterns matched against a definition's name.
        decorator_paths: Dotted paths matched against a definition's decorators.

    Returns:
        The definitions still to check, those a name pattern claimed, and
        those a decorator path claimed. A definition matching both is
        counted against its name.
    """
    to_check: list[Definition] = []
    by_name: list[Definition] = []
    by_decorator: list[Definition] = []
    for definition in definitions:
        if is_assumed_used_by_name(definition.name, name_patterns):
            by_name.append(definition)
        elif is_assumed_used_by_decorator(definition.decorators, decorator_paths):
            by_decorator.append(definition)
        else:
            to_check.append(definition)
    return (to_check, by_name, by_decorator)


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


def _is_unsearched(path: str, unsearched: str | None) -> bool:
    """Check whether a file sits in the directory left out of the search."""
    return unsearched is not None and path.startswith(unsearched)


def is_used(
    definition: Definition,
    searched: Searched,
    unsearched: str | None = None,
) -> bool:
    """Check whether anything uses a definition.

    Every file is read the same way, the file the definition lives in
    included. A definition its own file calls is a helper doing its job and is
    used; one that any file only mentions in a comment, a docstring or an
    ``__all__`` entry is not.

    Args:
        definition: The definition to look for.
        searched: The searched files, read as code where they parse.
        unsearched: A directory to leave out of the search, if any, however
            often its files name the definition.

    Returns:
        True if any searched file uses the definition.
    """
    name = definition.name
    for path, used in searched.uses.items():
        if not _is_unsearched(path, unsearched) and name in used:
            return True
    for path, content in searched.unparsed.items():
        if not _is_unsearched(path, unsearched) and names_in_text(name, content):
            return True
    return False


def unused_definitions(
    definitions: list[Definition],
    searched: Searched,
    unsearched_template: str | None = None,
) -> list[Finding]:
    """Find the definitions nothing uses.

    Args:
        definitions: The definitions to check.
        searched: The searched files, read as code where they parse.
        unsearched_template: A path template containing ``{package}`` whose
            files are left out of the search, if any.

    Returns:
        A finding for each definition nothing uses.
    """
    findings = []
    for definition in definitions:
        unsearched = unsearched_directory(unsearched_template, definition.package)
        if not is_used(definition, searched, unsearched):
            findings.append(Finding(definition=definition))
    return findings
