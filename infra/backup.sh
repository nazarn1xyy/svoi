#!/bin/sh
# Daily pg_dump with BACKUP_KEEP_DAYS rotation; copies off-site when RCLONE_REMOTE is set.
set -eu

dir="${BACKUP_DIR:?}"
keep="${BACKUP_KEEP_DAYS:-14}"
stamp="$(date -u +%Y%m%d-%H%M%S)"
file="${dir}/svoi-${stamp}.dump"

mkdir -p "${dir}"
pg_dump --format=custom --no-owner --file="${file}.tmp"
mv "${file}.tmp" "${file}"
find "${dir}" -name 'svoi-*.dump' -type f -mtime "+$((keep - 1))" -delete

if [ -n "${RCLONE_REMOTE:-}" ]; then
  rclone copy "${file}" "${RCLONE_REMOTE}"
fi
echo "backup ${file}"
