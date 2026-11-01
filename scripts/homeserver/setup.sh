#!/usr/bin/env bash
# Bubbles home server: one-time setup of a fresh Ubuntu Server LTS laptop (24.04 or 26.04). Safe to run again.
#
#   sudo bash setup.sh
#
# What it does (docs/HOME_SERVER.md explains each part):
#   1. updates, automatic security updates, firewall, fail2ban
#   2. keeps running with the lid closed and never sleeps
#   3. Ollama with one small model, reachable only on this machine
#   4. nginx in front of Ollama: only /v1/chat/completions, only with a long random token
#   5. PostgreSQL + pgvector, listening on this machine only
#   6. a nightly, encrypted copy of the Supabase database (off until /etc/bubbles-home/backup.env is filled in)
#   7. Tailscale: private SSH from anywhere, and a public https address (Funnel) for the token-protected LLM door only
#
# Environment overrides: HOME_LLM_MODEL (default picked from RAM), PG_MAJOR (default 17), TS_HOSTNAME (default bubbles-home),
# SKIP_TAILSCALE=1 (set everything else up, connect Tailscale later by running this again).
set -euo pipefail

[[ ${EUID} -eq 0 ]] || { echo "Please run with sudo:  sudo bash $0"; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF=/etc/bubbles-home
PORT=8088
PG_MAJOR="${PG_MAJOR:-17}"
TS_HOSTNAME="${TS_HOSTNAME:-bubbles-home}"
export DEBIAN_FRONTEND=noninteractive

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

. /etc/os-release
case "${VERSION_ID}" in
  24.04|26.04) ;;
  *) echo "Note: written for Ubuntu Server 24.04 / 26.04 LTS. This is ${PRETTY_NAME}; continuing." ;;
esac

install -d -m 700 "${CONF}"

# ---------------------------------------------------------------------------------------------------------------------------
step "1/7 Updates, automatic security updates, firewall"
apt-get update -y
apt-get -y upgrade
apt-get install -y --no-install-recommends \
  curl ca-certificates gnupg ufw unattended-upgrades fail2ban nginx age openssl jq lm-sensors
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH            # SSH from your home network
ufw allow in on tailscale0   # anything from your own Tailscale devices
ufw --force enable
systemctl enable --now fail2ban

# ---------------------------------------------------------------------------------------------------------------------------
step "2/7 Run with the lid closed, never sleep"
install -d /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/bubbles-lid.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null

# ---------------------------------------------------------------------------------------------------------------------------
step "3/7 Ollama (local LLM)"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
install -d /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/bubbles.conf <<'EOF'
[Service]
# Only this machine can talk to Ollama; the outside world reaches it through nginx and the token.
Environment="OLLAMA_HOST=127.0.0.1:11434"
# Keep the model in memory: loading it again costs many seconds on every first call.
Environment="OLLAMA_KEEP_ALIVE=-1"
# Bubbles prompts are a few thousand tokens; the default window would cut them off.
Environment="OLLAMA_CONTEXT_LENGTH=8192"
# One reply at a time and one model: a laptop has no room for more.
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
EOF
systemctl daemon-reload
systemctl enable ollama >/dev/null
systemctl restart ollama
for _ in $(seq 1 30); do curl -fs http://127.0.0.1:11434/api/version >/dev/null && break; sleep 1; done

mem_gb=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
if [[ -n "${HOME_LLM_MODEL:-}" ]]; then
  MODEL="${HOME_LLM_MODEL}"
elif (( mem_gb >= 7 )); then
  MODEL="llama3.2:3b"     # about 2 GB; reads Hindi; the best speed/quality trade on a laptop CPU
else
  MODEL="llama3.2:1b"     # for 4 GB machines
fi
case "${MODEL}" in
  llama3.2:1b|llama3.2:3b|qwen2.5:3b|qwen2.5:7b|llama3.1:8b|gemma3:4b) ;;
  *) echo "WARNING: ${MODEL} is not on the backend allowlist (FREE_MODEL_ALLOWLIST['HomeServer'] in backend/ai_provider.py)."
     echo "         The backend will refuse it until it is added there." ;;
esac
echo "RAM: ${mem_gb} GB -> model ${MODEL}"
ollama pull "${MODEL}"
printf 'HOME_LLM_MODEL=%s\n' "${MODEL}" > "${CONF}/llm.env"

# ---------------------------------------------------------------------------------------------------------------------------
step "4/7 nginx: the one token-protected door to the LLM"
if [[ ! -s "${CONF}/llm_token" ]]; then
  openssl rand -hex 32 > "${CONF}/llm_token"
fi
chmod 600 "${CONF}/llm_token"
TOKEN="$(cat "${CONF}/llm_token")"
rm -f /etc/nginx/sites-enabled/default
sed -e "s/__TOKEN__/${TOKEN}/" -e "s/__PORT__/${PORT}/" "${HERE}/nginx-bubbles-llm.conf" > /etc/nginx/sites-available/bubbles-llm
chmod 640 /etc/nginx/sites-available/bubbles-llm
ln -sf /etc/nginx/sites-available/bubbles-llm /etc/nginx/sites-enabled/bubbles-llm
nginx -t
systemctl enable nginx >/dev/null
systemctl reload nginx || systemctl restart nginx

# ---------------------------------------------------------------------------------------------------------------------------
step "5/7 PostgreSQL ${PG_MAJOR} + pgvector (this machine only)"
apt-get install -y --no-install-recommends postgresql-common
if [[ ! -f /etc/apt/sources.list.d/pgdg.list && ! -f /etc/apt/sources.list.d/pgdg.sources ]]; then
  /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
fi
apt-get install -y --no-install-recommends "postgresql-${PG_MAJOR}" "postgresql-${PG_MAJOR}-pgvector" "postgresql-client-${PG_MAJOR}"
# Ubuntu's default is listen_addresses = 'localhost'; make sure nobody widened it.
PGCONF="/etc/postgresql/${PG_MAJOR}/main/postgresql.conf"
if grep -Eq "^\s*listen_addresses\s*=\s*'\*'" "${PGCONF}"; then
  sed -i -E "s/^\s*listen_addresses\s*=.*/listen_addresses = 'localhost'/" "${PGCONF}"
fi
systemctl enable --now postgresql >/dev/null
systemctl restart postgresql

# ---------------------------------------------------------------------------------------------------------------------------
step "6/7 Nightly encrypted Supabase backup"
id bubblesbackup >/dev/null 2>&1 || useradd --system --home /var/backups/bubbles --shell /usr/sbin/nologin bubblesbackup
install -d -m 700 -o bubblesbackup -g bubblesbackup /var/backups/bubbles
install -m 755 "${HERE}/backup-supabase.sh" /usr/local/sbin/bubbles-backup
install -m 755 "${HERE}/restore-drill.sh"   /usr/local/sbin/bubbles-restore-drill
install -m 755 "${HERE}/status.sh"          /usr/local/bin/bubbles-home-status
if [[ ! -f "${CONF}/backup.env" ]]; then
  install -m 600 "${HERE}/backup.env.example" "${CONF}/backup.env"
fi
sed "s/__PG_MAJOR__/${PG_MAJOR}/" "${HERE}/bubbles-backup.service" > /etc/systemd/system/bubbles-backup.service
install -m 644 "${HERE}/bubbles-backup.timer" /etc/systemd/system/bubbles-backup.timer
systemctl daemon-reload
systemctl enable --now bubbles-backup.timer >/dev/null

# ---------------------------------------------------------------------------------------------------------------------------
step "7/7 Tailscale (private SSH + the public https door)"
PUBLIC_URL=""
if [[ "${SKIP_TAILSCALE:-0}" == "1" ]]; then
  echo "Skipped (SKIP_TAILSCALE=1). Run this script again without it to connect."
else
  command -v tailscale >/dev/null 2>&1 || curl -fsSL https://tailscale.com/install.sh | sh
  systemctl enable --now tailscaled >/dev/null
  if ! tailscale status >/dev/null 2>&1; then
    echo "Open the link below on your phone or PC and sign in to Tailscale to add this laptop:"
    tailscale up --ssh --hostname "${TS_HOSTNAME}"
  fi
  # Funnel publishes ONLY nginx's port (127.0.0.1:${PORT}) at https://<name>.<tailnet>.ts.net. TLS ends on this laptop.
  if ! tailscale funnel --bg "${PORT}"; then
    echo "Funnel is not allowed yet. Follow the link above (or Tailscale admin > Access controls) to enable it, then run:"
    echo "  sudo tailscale funnel --bg ${PORT}"
  fi
  DNS="$(tailscale status --json | jq -r '.Self.DNSName // empty' | sed 's/\.$//')"
  [[ -n "${DNS}" ]] && PUBLIC_URL="https://${DNS}"
fi

# ---------------------------------------------------------------------------------------------------------------------------
step "Done"
cat <<EOF

Put these in the backend's environment (Render dashboard > Environment, or backend/.env), then redeploy:

  HOME_LLM_URL=${PUBLIC_URL:-https://${TS_HOSTNAME}.<your-tailnet>.ts.net}
  HOME_LLM_TOKEN=${TOKEN}
  HOME_LLM_MODEL=${MODEL}

The token is also in ${CONF}/llm_token (root only). Treat it like a password.

Next:
  1. Fill in ${CONF}/backup.env (sudo nano ${CONF}/backup.env), then test:  sudo systemctl start bubbles-backup
  2. Check everything:  bubbles-home-status
  3. Reboot once so the lid setting applies:  sudo reboot
EOF
