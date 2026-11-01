#!/usr/bin/env bash
# Prove a backup can actually be restored: decrypt it, load the public schema into a scratch database on this laptop,
# count tables and rows, then delete the scratch database. Run it once a month, and after any big migration.
#
#   sudo bubbles-restore-drill /path/to/bubbles-backup-key.txt [backup-file] [--keep]
#
# Bring the private key on a USB stick and remove it afterwards: it should not live on this laptop.
# "--keep" leaves the restored copy in the database bubbles_drill (plain, readable data: drop it when done).
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo "Please run with sudo."; exit 1; }

KEY="${1:-}"
[[ -n "${KEY}" && -f "${KEY}" ]] || { echo "Usage: sudo bubbles-restore-drill KEYFILE [backup-file] [--keep]"; exit 1; }
FILE="${2:-}"
KEEP=0
if [[ "${FILE}" == "--keep" ]]; then KEEP=1; FILE=""; fi
[[ "${3:-}" == "--keep" ]] && KEEP=1
if [[ -z "${FILE}" ]]; then
  FILE="$(ls -1t /var/backups/bubbles/supabase-*.dump.age 2>/dev/null | head -1 || true)"
fi
[[ -n "${FILE}" && -f "${FILE}" ]] || { echo "No backup found in /var/backups/bubbles."; exit 1; }

DB=bubbles_drill
as_pg() { sudo -u postgres "$@"; }

echo "Restoring $(basename "${FILE}") into ${DB} (public schema only) ..."
as_pg dropdb --if-exists "${DB}"
as_pg createdb "${DB}"
as_pg psql -q -d "${DB}" -c 'create extension if not exists vector; create extension if not exists pgcrypto;'

# Errors about Supabase-only roles, functions and links to auth.users are expected on a plain PostgreSQL: they are counted, not fatal.
errors="$(age --decrypt --identity "${KEY}" "${FILE}" \
  | as_pg pg_restore --no-owner --no-privileges --schema=public --dbname="${DB}" 2>&1 | grep -c '^pg_restore: error' || true)"

tables="$(as_pg psql -At -d "${DB}" -c "select count(*) from information_schema.tables where table_schema = 'public'")"
echo "Tables restored: ${tables}  (pg_restore errors, mostly Supabase-only objects: ${errors})"
echo "Largest tables by rows:"
as_pg psql -d "${DB}" -c "analyze;" >/dev/null
as_pg psql -d "${DB}" -c "select relname as table, n_live_tup as rows from pg_stat_user_tables order by n_live_tup desc limit 12;"

if (( KEEP )); then
  echo "Kept in database ${DB}. Remove it when done:  sudo -u postgres dropdb ${DB}"
else
  as_pg dropdb "${DB}"
  echo "Scratch database removed. Drill passed if the table count and row counts look right."
fi
