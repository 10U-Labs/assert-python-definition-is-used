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

ADVERTISED = """\
def shown():
    return 1


def dropped():
    return 2
"""

REEXPORT = """\
from pkg import shown

__all__: list[str] = ["shown"]
__all__ += ["dropped"]
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

LIB_AND_TEST_RUN = [
    "lib/python",
    "--search-in",
    "lib/python",
    "--search-in",
    "test",
    "--dont-search-in",
    "test/lib/python/test_{package}",
]

NOTED_PROJECT = {
    "lib/python/pkg/__init__.py": NOTED,
    "src/app.py": NOTE,
}

ADVERTISING_PROJECT = {
    "lib/python/pkg/__init__.py": ADVERTISED,
    "src/api.py": REEXPORT,
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

CLIENTS = """\
def get_client(service_name):
    return service_name


def get_ssm_client():
    return get_client("ssm")


def reset_clients():
    return None
"""

HANDLER = """\
import boto3


def get_ssm_client():
    return boto3.client("ssm")


def handler(event, context):
    return get_ssm_client()
"""

RELATIVE = """\
from .helper import gadget


def ring():
    return gadget()
"""

SHADOWING_PROJECT = {
    "lib/python/aws_clients/__init__.py": CLIENTS,
    "src/handler.py": HANDLER,
}

PACKAGED_PROJECT = {
    "lib/python/live/__init__.py": "def widget():\n    return 1\n",
    "lib/python/live/inner/__init__.py": "def spin():\n    return 2\n",
    "lib/python/dead/__init__.py": RELATIVE,
    "lib/python/dead/helper.py": "def gadget():\n    return 3\n",
    "lib/python/loose.py": "def solo():\n    return 4\n",
    "src/app.py": "import live\n\nlive.widget()\n",
    "test/lib/python/test_dead/test_it.py": "import dead\n\ndead.ring()\n",
}

PACKAGES_RUN = [*FULL_RUN, "--unimported-packages"]

SHADOWED_PACKAGES_RUN = [*CLEAN_RUN, "--unimported-packages"]
