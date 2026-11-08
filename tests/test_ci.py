"""K3 acceptance: the PR gate runs the jobs from FRONTEND.md section 5 and never deploys."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE_JOBS = {"lint", "types", "contracts", "api", "bot", "build"}


def _workflow() -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load((ROOT / ".github/workflows/pr.yml").read_text())
    return data


def _runs(job: str) -> str:
    steps = _workflow()["jobs"][job]["steps"]
    return "\n".join(step.get("run", "") for step in steps)


def test_gate_triggers_on_pull_requests_to_main() -> None:
    # PyYAML reads the bare `on` key as boolean True
    trigger = _workflow()[True]
    assert trigger["pull_request"]["branches"] == ["main"]
    assert "push" not in trigger


def test_gate_has_exactly_the_documented_jobs() -> None:
    assert set(_workflow()["jobs"]) == GATE_JOBS


def test_lint_job_checks_ruff_and_format() -> None:
    runs = _runs("lint")
    assert "uv run ruff check ." in runs
    assert "uv run ruff format --check ." in runs


def test_types_job_runs_strict_mypy_on_all_code() -> None:
    assert "uv run mypy packages apps tests" in _runs("types")


def test_contracts_job_runs_contracts_and_repo_tests() -> None:
    runs = _runs("contracts")
    assert "uv run pytest packages/contracts" in runs
    assert "uv run pytest tests" in runs


def test_api_job_uses_core_services_and_checks_migrations() -> None:
    job = _workflow()["jobs"]["api"]
    assert job["services"]["postgres"]["image"] == "postgis/postgis:16-3.4"
    assert job["services"]["redis"]["image"] == "redis:7"
    runs = _runs("api")
    assert "alembic -c apps/api/alembic.ini upgrade head" in runs
    assert "alembic -c apps/api/alembic.ini check" in runs
    assert "uv run pytest apps/api" in runs


def test_migration_steps_wait_for_alembic_config() -> None:
    # alembic arrives in K6; until then the steps skip instead of failing the gate
    for step in _workflow()["jobs"]["api"]["steps"]:
        if "alembic" in step.get("run", ""):
            assert step["if"] == "hashFiles('apps/api/alembic.ini') != ''"


def test_bot_job_runs_bot_tests_against_redis() -> None:
    job = _workflow()["jobs"]["bot"]
    assert job["services"]["redis"]["image"] == "redis:7"
    assert "postgres" not in job["services"]
    assert "uv run pytest apps/bot" in _runs("bot")


def test_build_job_builds_both_images_without_pushing() -> None:
    steps = _workflow()["jobs"]["build"]["steps"]
    builds = [s for s in steps if s.get("uses", "").startswith("docker/build-push-action@")]
    assert sorted(s["with"]["file"] for s in builds) == [
        "apps/api/Dockerfile",
        "apps/bot/Dockerfile",
    ]
    for step in builds:
        assert step["with"]["push"] is False
        assert step["with"]["context"] == "."


def test_gate_installs_from_frozen_lock() -> None:
    for job in GATE_JOBS - {"build"}:
        assert "uv sync --frozen" in _runs(job), job


def test_gate_never_deploys_or_touches_registries() -> None:
    text = (ROOT / ".github/workflows/pr.yml").read_text()
    for forbidden in ("ssh", "ghcr.io", "docker/login-action", "packages: write"):
        assert forbidden not in text, forbidden


def test_gate_has_read_only_token_and_cancels_stale_runs() -> None:
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is True
