"""Sample source trees the integration and end-to-end tiers are run against."""

from __future__ import annotations

LIBRARY = """\
def kept():
    return 1


def orphan():
    return 2


def helper():
    return kept()


DEFAULT = helper()
"""

CALLER = """\
from pkg import kept

kept()
"""

OWN_TESTS = """\
from pkg import orphan

orphan()
"""

PROSE = """\
\"\"\"Call documented() to begin.\"\"\"


def documented():
    return 3
"""

NOTED = """\
def called():
    return 1


def noted():
    return 2
"""

NOTE = """\
from pkg import called

called()

# we used to call noted here, removed it last year
# noted()
"""

RUNTIME_INVOKED = """\
import pytest


@pytest.fixture(name="bootstrap_dir")
def bootstrap_dir_fixture():
    return "/tmp"


def pytest_configure(config):
    return config


def test_it_reads_the_directory(bootstrap_dir):
    assert bootstrap_dir


def spare():
    return 4
"""

PROJECT = {
    "lib/python/pkg/__init__.py": LIBRARY,
    "src/app.py": CALLER,
    "test/lib/python/test_pkg/test_pkg.py": OWN_TESTS,
}

CLEAN_PROJECT = {
    "lib/python/pkg/__init__.py": "def kept():\n    return 1\n",
    "src/app.py": CALLER,
}

FULL_RUN = [
    "lib/python",
    "--search-in",
    "lib/python",
    "--search-in",
    "src",
    "--search-in",
    "test",
    "--dont-search-in",
    "test/lib/python/test_{package}",
]

OUTER_BOUND = FULL_RUN[:-2]

CLEAN_RUN = ["lib/python", "--search-in", "lib/python", "--search-in", "src"]

NOTED_PROJECT = {
    "lib/python/pkg/__init__.py": NOTED,
    "src/app.py": NOTE,
}

RUNTIME_PROJECT = {"test/pkg/test_pkg.py": RUNTIME_INVOKED}

RUNTIME_RUN = ["test", "--search-in", "test"]

RUNTIME_ASSUMED = [
    *RUNTIME_RUN,
    "--assume-used-matching",
    "test_*,pytest_*",
    "--assume-used-decorated-with",
    "pytest.fixture",
]
