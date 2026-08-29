"""The shapes a test asks the CLI for, and the pairing that builds them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    WriteTree = Callable[[dict[str, str]], Path]
    RunCli = Callable[[list[str]], tuple[int, str, str]]
    RunOver = Callable[[dict[str, str], list[str]], tuple[int, str, str]]
    StdoutOf = Callable[[dict[str, str], list[str]], str]
    StderrOf = Callable[[dict[str, str], list[str]], str]
    ExitCodeOf = Callable[[dict[str, str], list[str]], int]


def build_runner(write: WriteTree, run: RunCli) -> RunOver:
    """Pair building a tree with running over it, the two steps a test starts with.

    Both tiers pair the same builder with a different runner, so the pairing
    itself lives here rather than once in each conftest.

    Returns:
        A function taking a tree and arguments, returning what the run did.
    """

    def runner(files: dict[str, str], args: list[str]) -> tuple[int, str, str]:
        write(files)
        return run(args)

    return runner
