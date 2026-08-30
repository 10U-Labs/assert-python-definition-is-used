from __future__ import annotations

import ast
import fnmatch
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

DEFINITION_NODES = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)
DOCSTRING_HOLDERS = (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Module)

DocstringHolder = ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef | ast.Module

WORDS = re.compile(r"\w+")


@dataclass(frozen=True)
class Definition:
    path: str
    line_number: int
    name: str
    package: str | None
    decorators: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.path}:{self.line_number}:{self.name}"


@dataclass(frozen=True)
class Finding:
    definition: Definition

    @property
    def path(self) -> str:
        return self.definition.path

    @property
    def line_number(self) -> int:
        return self.definition.line_number

    @property
    def name(self) -> str:
        return self.definition.name

    def __str__(self) -> str:
        return str(self.definition)


@dataclass(frozen=True)
class Searched:
    uses: dict[str, frozenset[str]]
    unparsed: dict[str, str]
    imports: dict[str, frozenset[str]]


def is_public(name: str) -> bool:
    return not name.startswith("_")


def _decorator_path(node: ast.expr) -> str | None:
    if isinstance(node, ast.Call):
        return _decorator_path(node.func)
    if isinstance(node, ast.Attribute):
        parent = _decorator_path(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return None


def _decorators_of(node: ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef) -> tuple[str, ...]:
    flattened = (_decorator_path(item) for item in node.decorator_list)
    return tuple(dotted for dotted in flattened if dotted is not None)


def public_definitions(path: str, content: str, package: str | None = None) -> list[Definition]:
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
    return re.compile(rf"\b{re.escape(name)}\b")


def names_in_text(name: str, text: str) -> bool:
    return _word_pattern(name).search(text) is not None


def _names_read(node: ast.AST) -> tuple[str, ...]:
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
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _docstring_of(node: DocstringHolder) -> ast.expr | None:
    first = node.body[0] if node.body else None
    if isinstance(first, ast.Expr) and _string_value(first.value) is not None:
        return first.value
    return None


def _all_value(node: ast.AST) -> ast.expr | None:
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return None
    named = any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets)
    return node.value if named else None


def _prose_constants(tree: ast.Module) -> set[int]:
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
    prose = _prose_constants(tree)
    names: set[str] = set()
    for node in ast.walk(tree):
        names.update(_names_read(node))
        written = _string_value(node)
        if written is not None and id(node) not in prose:
            names.update(WORDS.findall(written))
    return frozenset(names)


def imported_modules(tree: ast.Module) -> frozenset[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            modules.add(node.module.split(".")[0])
    return frozenset(modules)


def read_searched(sources: dict[str, str]) -> Searched:
    uses: dict[str, frozenset[str]] = {}
    imports: dict[str, frozenset[str]] = {}
    unparsed: dict[str, str] = {}
    for path in sorted(sources):
        try:
            tree = ast.parse(sources[path], filename=path)
        except SyntaxError:
            unparsed[path] = sources[path]
            continue
        uses[path] = names_used(tree)
        imports[path] = imported_modules(tree)
    return Searched(uses=uses, unparsed=unparsed, imports=imports)


def is_assumed_used_by_name(name: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def is_assumed_used_by_decorator(decorators: Sequence[str], paths: Sequence[str]) -> bool:
    return any(decorator in paths for decorator in decorators)


def assumed_used(
    definitions: list[Definition],
    name_patterns: Sequence[str],
    decorator_paths: Sequence[str],
) -> tuple[list[Definition], list[Definition], list[Definition]]:
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
    if template is None or package is None:
        return None
    rendered = template.format(package=package)
    return rendered if rendered.endswith("/") else rendered + "/"


def _is_unsearched(path: str, unsearched: str | None) -> bool:
    return unsearched is not None and path.startswith(unsearched)


def is_used(
    definition: Definition,
    searched: Searched,
    unsearched: str | None = None,
) -> bool:
    name = definition.name
    for path, used in searched.uses.items():
        if not _is_unsearched(path, unsearched) and name in used:
            return True
    for path, content in searched.unparsed.items():
        if not _is_unsearched(path, unsearched) and names_in_text(name, content):
            return True
    return False


def is_imported(
    definition: Definition, searched: Searched, unsearched: str | None = None
) -> bool:
    return any(
        definition.name in imported
        for path, imported in searched.imports.items()
        if not _is_unsearched(path, unsearched)
    )


def _findings_over(
    definitions: list[Definition],
    searched: Searched,
    unsearched_template: str | None,
    reached: Callable[[Definition, Searched, str | None], bool],
) -> list[Finding]:
    findings = []
    for definition in definitions:
        unsearched = unsearched_directory(unsearched_template, definition.package)
        if not reached(definition, searched, unsearched):
            findings.append(Finding(definition=definition))
    return findings


def unused_definitions(
    definitions: list[Definition],
    searched: Searched,
    unsearched_template: str | None = None,
) -> list[Finding]:
    return _findings_over(definitions, searched, unsearched_template, is_used)


def unimported_packages(
    packages: list[Definition],
    searched: Searched,
    unsearched_template: str | None = None,
) -> list[Finding]:
    return _findings_over(packages, searched, unsearched_template, is_imported)
