"""Command-line interface for assert-python-definition-is-used."""

from __future__ import annotations

import argparse
import fnmatch
import glob
import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .scanner import Definition, Finding, public_definitions, unused_definitions

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

GLOB_CHARACTERS = ("*", "?", "[")


@dataclass
class ScanResult:
    """The outcome of one run over a set of trees."""

    findings: list[Finding] = field(default_factory=list)
    definitions_read: int = 0
    files_scanned: int = 0
    had_error: bool = False


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="assert-python-definition-is-used",
        description=(
            "Assert that every public top-level definition in the given trees is named "
            "somewhere else. A definition whose last caller was deleted keeps its tests, "
            "keeps its coverage and is never called again, so nothing else reports it."
        ),
    )

    parser.add_argument(
        "trees",
        nargs="+",
        metavar="TREE",
        help=(
            "One or more file paths, directory paths, or glob patterns holding the "
            "definitions to check. Directories are read recursively for *.py files."
        ),
    )

    parser.add_argument(
        "--search-in",
        action="append",
        default=None,
        metavar="PATH",
        dest="search_in",
        help=(
            "A tree to search for uses, repeatable. Defaults to the definition trees, "
            "so pass it for every other place a caller may live."
        ),
    )

    parser.add_argument(
        "--dont-search-in",
        metavar="TEMPLATE",
        help=(
            "A path template containing {package} to leave out of the search, such as "
            "'test/lib/python/test_{package}'. Without it a module held at full coverage "
            "by its own tests always reads as used."
        ),
    )

    parser.add_argument(
        "--exclude",
        metavar="PATTERNS",
        help="Comma-separated glob patterns to exclude files, from both trees.",
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output. Exit code indicates success (0) or findings (1).",
    )
    output_group.add_argument(
        "--count",
        action="store_true",
        help="Output only the count of findings.",
    )
    output_group.add_argument(
        "--verbose",
        action="store_true",
        help="Show trees read, definitions found, findings and a summary.",
    )

    behavior_group = parser.add_mutually_exclusive_group()
    behavior_group.add_argument(
        "--fail-fast",
        action="store_true",
        help="Exit immediately after finding the first unused definition.",
    )
    behavior_group.add_argument(
        "--warn-only",
        action="store_true",
        help="Always exit with code 0, even if findings exist.",
    )

    return parser


def parse_patterns(patterns_str: str | None) -> list[str]:
    """Parse a comma-separated patterns string.

    Args:
        patterns_str: Comma-separated patterns, or None.

    Returns:
        The patterns, empty when the input is None or blank.
    """
    if not patterns_str:
        return []
    return [pattern.strip() for pattern in patterns_str.split(",") if pattern.strip()]


def _is_glob_pattern(path: str) -> bool:
    """Check whether a path holds glob wildcard characters."""
    return any(character in path for character in GLOB_CHARACTERS)


def _walk_python_files(directory: str) -> list[str]:
    """Find every *.py file under a directory, ignoring hidden directories."""
    found: list[str] = []
    for root, directories, filenames in os.walk(directory):
        directories[:] = [name for name in directories if not name.startswith(".")]
        found.extend(
            os.path.join(root, filename) for filename in filenames if filename.endswith(".py")
        )
    return found


def _expand(path: str) -> tuple[list[str], bool]:
    """Expand one path, directory or glob into the files it names.

    Args:
        path: A file path, directory path or glob pattern.

    Returns:
        The files it names, and whether it named anything at all.
    """
    if _is_glob_pattern(path):
        matched = glob.glob(path, recursive=True, include_hidden=True)
        found: list[str] = []
        for entry in matched:
            if os.path.isfile(entry):
                found.append(entry)
            elif os.path.isdir(entry):
                found.extend(_walk_python_files(entry))
        return (found, bool(matched))
    if os.path.isfile(path):
        return ([path], True)
    if os.path.isdir(path):
        return (_walk_python_files(path), True)
    return ([], False)


def package_of(path: str, tree: str) -> str | None:
    """Name the package a file belongs to, relative to the tree holding it.

    A file sitting directly in the tree belongs to no package, and so has no
    directory of its own to discount.

    Args:
        path: The file path.
        tree: The tree the file was found under.

    Returns:
        The first path component below the tree, or None.
    """
    relative = os.path.relpath(os.path.normpath(path), os.path.normpath(tree))
    parts = relative.split(os.sep)
    if len(parts) < 2 or parts[0] in ("", os.pardir):
        return None
    return parts[0]


def _tree_root(path: str) -> str:
    """Reduce a tree argument to the directory its files hang from."""
    if os.path.isdir(path):
        return path
    stripped = path.split("*")[0].split("?")[0].split("[")[0]
    directory = os.path.dirname(stripped)
    return directory if directory else "."


def should_skip(path: str, exclude_patterns: list[str]) -> bool:
    """Check whether a file matches any exclude pattern.

    Args:
        path: The file path to check.
        exclude_patterns: Glob patterns to exclude.

    Returns:
        True when the path or its basename matches a pattern.
    """
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern)
        for pattern in exclude_patterns
    )


def _collect(paths: Sequence[str], exclude_patterns: list[str]) -> tuple[dict[str, str], list[str]]:
    """Expand paths into files, keeping the tree each file came from.

    Args:
        paths: File paths, directory paths or glob patterns.
        exclude_patterns: Glob patterns to exclude.

    Returns:
        A mapping of normalised file path to the tree it came from, and the
        paths that named nothing.
    """
    trees: dict[str, str] = {}
    missing: list[str] = []
    for path in paths:
        found, matched = _expand(path)
        if not matched:
            missing.append(path)
            continue
        root = _tree_root(path)
        for entry in found:
            normalised = os.path.normpath(entry)
            if normalised.endswith(".py") and not should_skip(normalised, exclude_patterns):
                trees.setdefault(normalised, root)
    return (trees, missing)


def _read(path: str, result: ScanResult, verbose: bool) -> str | None:
    """Read one file, recording an error on the result if it cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        print(f"Error reading {path}: {error}", file=sys.stderr)
        result.had_error = True
        if verbose:
            print(f"Skipping (unreadable): {path}")
        return None


def read_sources(
    paths: dict[str, str], result: ScanResult, verbose: bool = False
) -> dict[str, str]:
    """Read every file, keyed by path.

    Args:
        paths: A mapping of file path to the tree it came from.
        result: The result to record read errors on.
        verbose: Whether to name each file read.

    Returns:
        A mapping of file path to content, skipping the unreadable.
    """
    sources: dict[str, str] = {}
    for path in sorted(paths):
        content = _read(path, result, verbose)
        if content is not None:
            sources[path] = content
    return sources


def read_definitions(
    paths: dict[str, str],
    sources: dict[str, str],
    result: ScanResult,
    verbose: bool = False,
) -> list[Definition]:
    """Parse every definition file for its public top-level definitions.

    Args:
        paths: A mapping of definition file path to the tree it came from.
        sources: Every readable file, keyed by path.
        result: The result to record parse errors and counts on.
        verbose: Whether to name each file scanned.

    Returns:
        Every public definition found, in path order.
    """
    definitions: list[Definition] = []
    for path in sorted(paths):
        if path not in sources:
            continue
        if verbose:
            print(f"Scanning: {path}")
        try:
            found = public_definitions(path, sources[path], package_of(path, paths[path]))
        except SyntaxError as error:
            print(f"Syntax error in {path}: {error}", file=sys.stderr)
            result.had_error = True
            continue
        result.files_scanned += 1
        definitions.extend(found)
    result.definitions_read = len(definitions)
    return definitions


def output_findings(findings: list[Finding], count_mode: bool = False) -> None:
    """Print findings in the requested format.

    Args:
        findings: The findings to print.
        count_mode: Print only how many there are.
    """
    if count_mode:
        print(len(findings))
        return
    for finding in findings:
        print(finding)


def determine_exit_code(result: ScanResult, warn_only: bool = False) -> int:
    """Choose the exit code for a result.

    Args:
        result: The scan result.
        warn_only: Always succeed when true.

    Returns:
        0 for success, 1 for findings, 2 for errors.
    """
    if warn_only:
        return EXIT_SUCCESS
    if result.findings:
        return EXIT_FINDINGS
    if result.had_error:
        return EXIT_ERROR
    return EXIT_SUCCESS


def _report(result: ScanResult, args: argparse.Namespace) -> None:
    """Print whatever the chosen output mode asks for."""
    if args.verbose:
        print()
        print(f"Files scanned: {result.files_scanned}")
        print(f"Definitions read: {result.definitions_read}")
        print(f"Findings: {len(result.findings)}")
        for finding in result.findings:
            print(f"  Unused: {finding}")
        if result.had_error:
            print("Errors occurred during scanning.")
        return
    if not args.quiet:
        output_findings(result.findings, args.count)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CLI.

    Args:
        argv: Command-line arguments, defaulting to sys.argv[1:].
    """
    args = create_parser().parse_args(argv)
    exclude_patterns = parse_patterns(args.exclude)
    result = ScanResult()

    definition_paths, missing = _collect(args.trees, exclude_patterns)
    search_paths, search_missing = _collect(args.search_in or args.trees, exclude_patterns)
    missing.extend(search_missing)

    for path in missing:
        print(f"Error: Path not found: {path}", file=sys.stderr)
    if not definition_paths and missing:
        sys.exit(EXIT_ERROR)
    if missing:
        result.had_error = True

    if args.verbose:
        print(f"Reading {len(definition_paths)} definition file(s)...")
        print(f"Searching {len(search_paths)} file(s) for uses.")
        if exclude_patterns:
            print(f"Excluding patterns: {', '.join(exclude_patterns)}")
        print()

    sources = read_sources({**search_paths, **definition_paths}, result, args.verbose)
    definitions = read_definitions(definition_paths, sources, result, args.verbose)
    searched = {path: content for path, content in sources.items() if path in search_paths}

    findings = unused_definitions(definitions, searched, args.dont_search_in)
    result.findings = findings[:1] if (args.fail_fast and findings) else findings

    _report(result, args)
    sys.exit(determine_exit_code(result, args.warn_only))
