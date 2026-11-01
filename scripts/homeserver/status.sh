#!/usr/bin/env bash
# One look at the Bubbles home server:  bubbles-home-status   (sudo shows the LLM speed test and Funnel too)
set -uo pipefail

ok()  { printf '  \033[32mok\033[0m    %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; }

echo "Services"
for s in ollama nginx postgresql tailscaled fail2ban bubbles-backup.timer; do
  if systemctl is-active --quiet "$s"; then ok "$s"; else bad "$s"; fi
done

echo "Machine"
echo "  uptime: $(uptime -p)   load: $(cut -d' ' -f1-3 /proc/loadavg)"
free -h | awk '/Mem:/ {print "  memory: " $3 " used of " $2}'
df -h / | awk 'NR==2 {print "  disk:   " $3 " used of " $2 " (" $5 ")"}'
temp="$(sensors 2>/dev/null | grep -m1 -E 'Package id 0|Tctl|temp1' | grep -oE '\+[0-9.]+°C' | head -1)"
[[ -n "${temp}" ]] && echo "  cpu temperature: ${temp}"
if [[ -r /sys/class/power_supply/BAT0/capacity ]]; then
  echo "  battery: $(cat /sys/class/power_supply/BAT0/capacity)% ($(cat /sys/class/power_supply/BAT0/status))"
fi

echo "LLM"
ollama ps 2>/dev/null | sed 's/^/  /' || bad "ollama not answering"
if [[ ${EUID} -eq 0 && -r /etc/bubbles-home/llm_token ]]; then
  model="$(sed -n 's/^HOME_LLM_MODEL=//p' /etc/bubbles-home/llm.env 2>/dev/null)"
  start=$(date +%s%N)
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 120 http://127.0.0.1:8088/v1/chat/completions \
    -H "Authorization: Bearer $(cat /etc/bubbles-home/llm_token)" -H 'Content-Type: application/json' \
    -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word ok.\"}],\"max_tokens\":5}")
  ms=$(( ( $(date +%s%N) - start ) / 1000000 ))
  secs="$(( ms / 1000 )).$(( ms % 1000 / 100 ))"
  if [[ "${code}" == "200" ]]; then ok "token door answers (${model}, ${secs}s for a tiny reply)"; else bad "token door returned HTTP ${code}"; fi
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -X POST http://127.0.0.1:8088/v1/chat/completions -d '{}')
  if [[ "${code}" == "401" ]]; then ok "no token is refused (401)"; else bad "no-token request returned HTTP ${code} (expected 401)"; fi
  echo "Tailscale Funnel"
  tailscale funnel status 2>/dev/null | sed 's/^/  /' || bad "tailscale funnel status failed"
else
  echo "  (run with sudo for the speed test and Funnel check)"
fi

echo "Backups"
last="$(ls -1t /var/backups/bubbles/supabase-*.dump.age 2>/dev/null | head -1)"
if [[ -n "${last}" ]]; then
  age_h=$(( ( $(date +%s) - $(stat -c %Y "${last}") ) / 3600 ))
  if (( age_h <= 36 )); then ok "latest $(basename "${last}") (${age_h} h ago)"; else bad "latest backup is ${age_h} h old"; fi
else
  bad "no backups yet (fill in /etc/bubbles-home/backup.env, then: sudo systemctl start bubbles-backup)"
fi
systemctl list-timers bubbles-backup.timer --no-pager 2>/dev/null | sed -n 2p | sed 's/^/  next: /'
