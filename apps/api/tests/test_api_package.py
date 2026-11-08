"""K1 acceptance: svoi_api is importable and sees svoi_contracts from the workspace."""

import importlib
from pathlib import Path


def test_api_package_imports_and_ships_py_typed() -> None:
    module = importlib.import_module("svoi_api")
    assert module.__file__ is not None
    assert (Path(module.__file__).parent / "py.typed").is_file()


def test_api_resolves_contracts_from_workspace() -> None:
    importlib.import_module("svoi_contracts")
