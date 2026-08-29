"""End-to-end test configuration."""

from __future__ import annotations

from test.runners import build_runner
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from test.runners import RunCli, RunOver, WriteTree


@pytest.fixture(name="run_over")
def run_over_fixture(write_tree: WriteTree, run_cli_subprocess: RunCli) -> RunOver:
    """Build a tree and run over it out of process, the way a workflow step does.

    Overriding the root fixture carries stdout_of, stderr_of and exit_code_of
    out of process too, so an e2e test asking for one of them drives the
    installed command rather than the imported one.

    Returns:
        A function taking a tree and arguments, returning what the step did.
    """
    return build_runner(write_tree, run_cli_subprocess)
