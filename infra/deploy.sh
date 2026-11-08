#!/usr/bin/env bash
# Runs on the VPS from /opt/svoi/infra: pull, migrate, restart, smoke test (FRONTEND.md 5).
# Needs IMAGE_TAG and GHCR_OWNER in the environment and /opt/svoi/.env with the secrets.
set -euo pipefail

cd "$(dirname "$0")"
compose=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

"${compose[@]}" pull --quiet
# migrations run only here, never when a container starts
"${compose[@]}" run --rm api alembic -c /app/alembic.ini upgrade head
"${compose[@]}" up -d --remove-orphans

for _ in $(seq 1 30); do
  if "${compose[@]}" exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"; then
    break
  fi
  sleep 2
done
"${compose[@]}" exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

# shellcheck disable=SC1091
set -a && . ../.env && set +a
info="$(curl -fsS "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")"
if echo "${info}" | grep -q '"last_error_message"'; then
  echo "webhook reports an error: ${info}" >&2
  exit 1
fi
echo "deployed ${IMAGE_TAG}"
