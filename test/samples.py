"""Sample source trees the integration and end-to-end tiers are run against."""

from __future__ import annotations

LIBRARY = """\
def kept():
    return 1


def orphan():
    return 2


def helper():
    return kept()
"""

CALLER = """\
from pkg import kept

kept()
"""

OWN_TESTS = """\
from pkg import orphan

orphan()
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
    "--consumer",
    "lib/python",
    "--consumer",
    "src",
    "--consumer",
    "test",
    "--own-tests",
    "test/lib/python/test_{package}",
]

OUTER_BOUND = FULL_RUN[:-2]

CLEAN_RUN = ["lib/python", "--consumer", "lib/python", "--consumer", "src"]
