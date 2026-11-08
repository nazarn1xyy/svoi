#!/usr/bin/env bash
# Monthly check (tech.md section 2): restore a dump into a throwaway PostGIS and count rows.
# Usage: infra/restore-check.sh <file.dump>
set -euo pipefail

dump="${1:?path to a .dump file}"
name="svoi-restore-check-$$"
docker run -d --rm --name "${name}" -e POSTGRES_USER=svoi -e POSTGRES_PASSWORD=check \
  -e POSTGRES_DB=svoi postgis/postgis:16-3.4 >/dev/null
trap 'docker stop "${name}" >/dev/null' EXIT
until docker exec "${name}" pg_isready -U svoi -d svoi -q; do sleep 1; done
sleep 3
# template0 has no PostGIS objects, so the dump's own CREATE EXTENSION lines apply cleanly
docker exec "${name}" createdb -U svoi -T template0 restored
docker exec -i "${name}" pg_restore -U svoi -d restored --no-owner --exit-on-error < "${dump}"
docker exec "${name}" psql -U svoi -d restored -tAc \
  "SELECT 'users=' || count(*) FROM users UNION ALL SELECT 'cities=' || count(*) FROM cities"
