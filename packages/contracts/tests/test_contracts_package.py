"""K1 acceptance: the contracts package is importable and typed."""

import importlib
from pathlib import Path


def test_contracts_package_imports_and_ships_py_typed() -> None:
    module = importlib.import_module("svoi_contracts")
    assert module.__file__ is not None
    assert (Path(module.__file__).parent / "py.typed").is_file()
