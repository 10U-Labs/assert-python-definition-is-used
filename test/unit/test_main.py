from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestMainModule:
    def test_calls_main(self) -> None:
        with patch("assert_python_definition_is_used.cli.main") as entry_point:
            sys.modules.pop("assert_python_definition_is_used.__main__", None)
            importlib.import_module("assert_python_definition_is_used.__main__")
            assert entry_point.called

    def test_calls_main_once(self) -> None:
        with patch("assert_python_definition_is_used.cli.main") as entry_point:
            sys.modules.pop("assert_python_definition_is_used.__main__", None)
            importlib.import_module("assert_python_definition_is_used.__main__")
            assert entry_point.call_count == 1
