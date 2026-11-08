"""K1 acceptance: svoi_api is importable and sees svoi_contracts from the workspace."""

import importlib
from pathlib import Path


def test_api_package_imports_and_ships_py_typed() -> None:
    module = importlib.import_module("svoi_api")
    assert module.__file__ is not None
    assert (Path(module.__file__).parent / "py.typed").is_file()


def test_api_resolves_contracts_from_workspace() -> None:
    # K5 acceptance: the contracts package imports from api
    contracts = importlib.import_module("svoi_contracts")
    cards = importlib.import_module("svoi_contracts.cards")
    assert contracts.CORE_VERSION >= 1
    assert "is_admin" in cards.UserState.model_fields
