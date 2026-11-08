"""K2 acceptance: compose raises the full stack on fakes, per docs/tech.md sections 3.1 and 10."""

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"
# core v2: admin lives inside the main bot, so there is no admin-bot service
SERVICES = {"postgres", "redis", "api", "api-worker", "bot", "bot-worker", "caddy"}
APP_SERVICES = SERVICES - {"postgres", "redis", "caddy"}
DOCKERFILES = (ROOT / "apps/api/Dockerfile", ROOT / "apps/bot/Dockerfile")


def _compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((INFRA / "docker-compose.yml").read_text())
    return data


def _services() -> dict[str, Any]:
    services: dict[str, Any] = _compose()["services"]
    return services


def test_compose_defines_exactly_the_core_services() -> None:
    assert set(_services()) == SERVICES


def test_infra_images_are_pinned_to_core_versions() -> None:
    services = _services()
    assert services["postgres"]["image"] == "postgis/postgis:16-3.4"
    assert services["redis"]["image"] == "redis:7"


def test_api_and_its_worker_share_the_api_image() -> None:
    services = _services()
    assert services["api"]["image"] == services["api-worker"]["image"]
    assert services["api"]["build"]["dockerfile"] == "apps/api/Dockerfile"


def test_bot_processes_share_the_bot_image() -> None:
    services = _services()
    images = {services[name]["image"] for name in ("bot", "bot-worker")}
    assert len(images) == 1
    assert services["bot"]["build"]["dockerfile"] == "apps/bot/Dockerfile"


def test_entrypoints_match_core_layout() -> None:
    services = _services()
    expected = {
        "api": "svoi_api.main",
        "api-worker": "svoi_api.jobs.worker",
        "bot": "svoi_bot.main",
        "bot-worker": "svoi_bot.workers.main",
    }
    for name, module in expected.items():
        assert module in " ".join(services[name]["command"]), name


def test_only_caddy_publishes_ports() -> None:
    # API is reachable only inside the Docker network (tech.md 7.1)
    for name, service in _services().items():
        assert ("ports" in service) == (name == "caddy"), name


def test_app_services_wait_for_healthy_postgres_and_redis() -> None:
    services = _services()
    for name in ("postgres", "redis"):
        assert "healthcheck" in services[name], name
    for name in APP_SERVICES:
        depends = services[name]["depends_on"]
        assert depends["redis"]["condition"] == "service_healthy", name
    for name in ("api", "api-worker"):
        assert services[name]["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_app_services_start_on_fakes_without_real_secrets() -> None:
    for name in APP_SERVICES:
        env_files = _services()[name]["env_file"]
        assert env_files[0] == {"path": "../.env.example", "required": True}, name
        assert env_files[1] == {"path": "../.env", "required": False}, name


def test_migrations_never_run_on_container_start() -> None:
    # tech.md: migrations are applied only in the deploy step
    for name in APP_SERVICES:
        assert "alembic" not in " ".join(_services()[name]["command"]), name
    for dockerfile in DOCKERFILES:
        assert "alembic" not in dockerfile.read_text()


def test_dockerfiles_use_frozen_lock_and_non_root_user() -> None:
    for dockerfile in DOCKERFILES:
        text = dockerfile.read_text()
        assert text.startswith("# syntax=")
        assert "FROM python:3.12-slim" in text
        assert "--frozen" in text
        assert re.search(r"^USER (?!root)\S+", text, re.MULTILINE), dockerfile


def test_env_example_matches_core_verbatim() -> None:
    tech = (ROOT / "docs/tech.md").read_text()
    block = re.search(r"`\.env\.example`:\n\n```\n(.*?)```", tech, re.DOTALL)
    assert block is not None
    assert (ROOT / ".env.example").read_text() == block.group(1)


def test_env_example_defaults_to_fakes() -> None:
    env = dict(
        line.split("#")[0].strip().split("=", 1)
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line.strip()
    )
    assert env["BOT_USE_FAKE_API"] == "true"
    assert env["USE_FAKE_CLIENTS"] == "true"
    assert env["BOT_TOKEN"].endswith(":fake")
