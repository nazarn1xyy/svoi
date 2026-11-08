# Deploy runbook (single VPS, ADR 0001)

Merging to `main` runs `.github/workflows/deploy.yml`: images go to GHCR tagged with the commit
sha, `infra/` is copied to `/opt/svoi/infra`, and `infra/deploy.sh` pulls, migrates, restarts and
smoke-tests (`/health` inside the network, `getWebhookInfo` without errors).

## One-time setup (owner)

1. VPS with Docker Engine and Compose v2.24+, user with SSH key access, `/opt/svoi` owned by it.
2. DNS: an A record for the bot domain pointing at the VPS; ports 80 and 443 open.
3. `/opt/svoi/.env` from `.env.example` with real values:
   `ENV=production`, `BOT_TOKEN`, `BOT_MODE=webhook`, `WEBHOOK_BASE_URL=https://<domain>`,
   `WEBHOOK_SECRET`, `BOT_USE_FAKE_API=false`, `INTERNAL_API_TOKEN`,
   `DATABASE_URL=postgresql+asyncpg://svoi:<password>@postgres:5432/svoi`, `POSTGRES_PASSWORD`,
   `ADMIN_TG_IDS`, `SENTRY_DSN`, `SITE_ADDRESS=<domain>`, `GRAFANA_ADMIN_PASSWORD`,
   optional `RCLONE_REMOTE` for off-site backups.
4. GitHub repository secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (private key, ed25519).
5. `docker login ghcr.io` on the VPS if the packages are private.
6. First catalog seed: `docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m svoi_api.seed --no-demo-users`.

## Operations

- Grafana: `ssh -L 3000:localhost:3000 <vps>` after mapping the port in an override, or
  `docker compose exec grafana ...`; it is not published to the internet.
- Backups: the `backup` service dumps daily to `${BACKUP_HOST_DIR:-/var/backups/svoi}` and keeps
  14 days. Monthly: `infra/restore-check.sh /var/backups/svoi/<latest>.dump`.
- Rollback: re-run the deploy job of an earlier commit, or
  `IMAGE_TAG=<sha> GHCR_OWNER=<owner> /opt/svoi/infra/deploy.sh`.
