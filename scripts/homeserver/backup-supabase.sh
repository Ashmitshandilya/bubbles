#!/usr/bin/env bash
# Nightly Supabase backup: pg_dump (custom format) of the public and auth schemas, encrypted with age before it touches disk.
# Installed as /usr/local/sbin/bubbles-backup and run by bubbles-backup.timer. Settings come from /etc/bubbles-home/backup.env.
# Fails closed: without an age recipient nothing is written, so no readable health data ever sits on this laptop.
set -euo pipefail
umask 077

OUT_DIR="${OUT_DIR:-/var/backups/bubbles}"
KEEP_DAYS="${KEEP_DAYS:-14}"
PG_BIN="${PG_BIN:-/usr/lib/postgresql/17/bin}"

if [[ -z "${SUPABASE_DB_URL:-}" || -z "${AGE_RECIPIENT:-}" ]]; then
  echo "bubbles-backup: SUPABASE_DB_URL and AGE_RECIPIENT are not both set in /etc/bubbles-home/backup.env; nothing backed up."
  exit 0
fi
[[ "${AGE_RECIPIENT}" == age1* ]] || { echo "bubbles-backup: AGE_RECIPIENT must be an age public key (age1...)."; exit 2; }

# pg_dump must be at least as new as the server.
server_major="$("${PG_BIN}/psql" "${SUPABASE_DB_URL}" -Atc 'show server_version_num' | cut -c1-2)"
client_major="$("${PG_BIN}/pg_dump" --version | grep -oE '[0-9]+' | head -1)"
if (( server_major > client_major )); then
  echo "bubbles-backup: Supabase runs PostgreSQL ${server_major}, this pg_dump is ${client_major}."
  echo "Install postgresql-client-${server_major} and set PG_BIN in bubbles-backup.service."
  exit 3
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
final="${OUT_DIR}/supabase-${stamp}.dump.age"
partial="${final}.partial"
trap 'rm -f "${partial}"' EXIT

"${PG_BIN}/pg_dump" "${SUPABASE_DB_URL}" \
  --format=custom --compress=6 --no-owner --no-privileges \
  --schema=public --schema=auth \
  | age --encrypt --recipient "${AGE_RECIPIENT}" --output "${partial}"

size="$(stat -c %s "${partial}")"
if (( size < 1024 )); then
  echo "bubbles-backup: the backup is only ${size} bytes; keeping the older ones and failing."
  exit 4
fi
mv "${partial}" "${final}"
trap - EXIT

find "${OUT_DIR}" -name 'supabase-*.dump.age' -type f -mtime "+${KEEP_DAYS}" -delete
echo "bubbles-backup: wrote $(basename "${final}") (${size} bytes); kept $(find "${OUT_DIR}" -name 'supabase-*.dump.age' | wc -l) backups."
