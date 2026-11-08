#!/bin/sh
# Runs backup.sh once a day inside the backup container.
set -eu
while true; do
  sh /backup/backup.sh || echo "backup failed" >&2
  sleep 86400
done
