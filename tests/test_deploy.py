"""K13 acceptance: merge to main deploys to the VPS; backups rotate after 14 days (ADR 0001)."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra"


class _ComposeLoader(yaml.SafeLoader):
    """Understands compose's !reset tag."""


_ComposeLoader.add_constructor("!reset", lambda loader, node: None)


def _yaml(path: Path) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.load(path.read_text(), Loader=_ComposeLoader)  # noqa: S506 - SafeLoader subclass
    return data


def test_deploy_runs_on_push_to_main_only() -> None:
    workflow = _yaml(ROOT / ".github/workflows/deploy.yml")
    assert workflow[True] == {"push": {"branches": ["main"]}}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    assert workflow["permissions"] == {"contents": "read", "packages": "write"}


def test_images_are_pushed_to_ghcr_tagged_with_the_commit() -> None:
    images = _yaml(ROOT / ".github/workflows/deploy.yml")["jobs"]["images"]
    assert images["strategy"]["matrix"]["app"] == ["api", "bot"]
    (build,) = [s for s in images["steps"] if s.get("uses", "").startswith("docker/build-push")]
    assert build["with"]["push"] is True
    assert build["with"]["tags"].endswith(":${{ github.sha }}")


def test_deploy_job_runs_the_script_over_ssh_with_secrets() -> None:
    deploy = _yaml(ROOT / ".github/workflows/deploy.yml")["jobs"]["deploy"]
    assert deploy["needs"] == "images"
    script = "\n".join(s.get("run", "") for s in deploy["steps"])
    assert "secrets.VPS_SSH_KEY" in str(deploy)
    assert "/opt/svoi/infra/deploy.sh" in script
    assert "IMAGE_TAG=${{ github.sha }}" in script


def test_deploy_script_migrates_before_restarting_and_smoke_tests() -> None:
    lines = (INFRA / "deploy.sh").read_text().splitlines()
    order = [i for i, line in enumerate(lines) if "upgrade head" in line or "up -d" in line]
    assert len(order) == 2
    assert "upgrade head" in lines[order[0]]
    text = "\n".join(lines)
    assert "/health" in text
    assert "getWebhookInfo" in text


def test_prod_compose_uses_ghcr_images_webhook_and_tls_domain() -> None:
    services = _yaml(INFRA / "docker-compose.prod.yml")["services"]
    for name in ("api", "api-worker", "bot", "bot-worker"):
        assert services[name]["image"].startswith("ghcr.io/${GHCR_OWNER:?}/svoi-"), name
        assert services[name]["image"].endswith(":${IMAGE_TAG:?}"), name
    assert services["bot"]["environment"]["BOT_MODE"] == "webhook"
    assert "SITE_ADDRESS" in services["caddy"]["environment"]
    assert {"prometheus", "grafana", "backup"} <= set(services)
    published = [n for n, s in services.items() if "ports" in s]
    assert published == []  # only caddy publishes, from the base file


def test_caddy_routes_webhook_to_the_bot() -> None:
    caddyfile = (INFRA / "Caddyfile").read_text()
    assert "{$SITE_ADDRESS::80}" in caddyfile
    assert "handle /tg/webhook" in caddyfile
    assert "reverse_proxy bot:8080" in caddyfile


def test_backups_keep_fourteen_days() -> None:
    backup = _yaml(INFRA / "docker-compose.prod.yml")["services"]["backup"]
    assert backup["environment"]["BACKUP_KEEP_DAYS"] == "14"
    script = (INFRA / "backup.sh").read_text()
    assert "pg_dump --format=custom" in script
    assert "-mtime" in script and "-delete" in script


def test_api_image_carries_migrations_for_the_deploy_step() -> None:
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "apps/api/alembic.ini /app/alembic.ini" in dockerfile
    assert "apps/api/migrations /app/migrations" in dockerfile
