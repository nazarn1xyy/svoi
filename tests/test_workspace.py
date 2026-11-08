"""K1 acceptance: the uv workspace and tooling match docs/tech.md sections 2, 3.2 and 12."""

import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("packages/contracts", "apps/api", "apps/bot")


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def test_workspace_declares_contracts_api_and_bot() -> None:
    workspace = _toml(ROOT / "pyproject.toml")["tool"]["uv"]["workspace"]
    assert sorted(workspace["members"]) == sorted(MEMBERS)


def test_every_member_targets_python_312() -> None:
    for member in (".", *MEMBERS):
        requires = _toml(ROOT / member / "pyproject.toml")["project"]["requires-python"]
        assert requires == ">=3.12,<3.13", member


def test_api_and_bot_depend_on_contracts_from_workspace() -> None:
    sources = _toml(ROOT / "pyproject.toml")["tool"]["uv"]["sources"]
    assert sources["svoi-contracts"] == {"workspace": True}
    for member in ("apps/api", "apps/bot"):
        deps = _toml(ROOT / member / "pyproject.toml")["project"]["dependencies"]
        assert "svoi-contracts" in deps, member


def test_ruff_uses_core_rule_set_and_line_length() -> None:
    ruff = _toml(ROOT / "pyproject.toml")["tool"]["ruff"]
    assert ruff["line-length"] == 100
    assert sorted(ruff["lint"]["select"]) == sorted(
        ["E", "F", "I", "B", "UP", "SIM", "ASYNC", "S", "PL", "RUF"]
    )


def test_mypy_is_strict() -> None:
    mypy = _toml(ROOT / "pyproject.toml")["tool"]["mypy"]
    assert mypy["strict"] is True
    assert mypy["python_version"] == "3.12"


def test_pre_commit_runs_ruff_and_mypy() -> None:
    config = (ROOT / ".pre-commit-config.yaml").read_text()
    for hook in ("id: ruff", "id: ruff-format", "id: mypy"):
        assert hook in config, hook


def test_claude_md_lives_at_repo_root_and_imports_core() -> None:
    assert "@docs/tech.md" in (ROOT / "CLAUDE.md").read_text()


def test_env_files_are_ignored_by_git() -> None:
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignored
