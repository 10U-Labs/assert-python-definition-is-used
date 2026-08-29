from __future__ import annotations

from test.runners import build_runner
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from test.runners import RunCli, RunOver, WriteTree


@pytest.fixture(name="run_over")
def run_over_fixture(write_tree: WriteTree, run_cli_subprocess: RunCli) -> RunOver:
    return build_runner(write_tree, run_cli_subprocess)
