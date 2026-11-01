# Bubbles home server (a spare laptop running lean Ubuntu)

A spare laptop becomes a small always-on server for Bubbles:

- **LLM fallback.** Ollama runs one small model. It is the **last** link in the backend's keyed AI chain (`HomeServer` in
  `backend/ai_provider.py`), after Gemini, Groq, NVIDIA and Mistral. It costs nothing and no third party sees the prompt.
- **Database safety copy.** Every night the laptop takes a copy of the Supabase database, encrypts it, and keeps 14 days.
  A monthly drill restores one into PostgreSQL + pgvector on the laptop to show it actually works.
- **Lean and locked down.** Ubuntu Server with no desktop, firewall on, automatic security updates, no sleep with the lid shut.
  Nothing listens on the internet except one https address (Tailscale Funnel) that accepts only the chat endpoint, and only
  with a 64-character token.

```
Render backend ──https + token──▶ Tailscale Funnel ──▶ nginx 127.0.0.1:8088 ──▶ Ollama 127.0.0.1:11434
Your PC / phone ──Tailscale (private)──▶ SSH, PostgreSQL (localhost only)
Laptop ──nightly pg_dump──▶ Supabase      (stored encrypted with age; the key is NOT on the laptop)
```

Everything here is in `scripts/homeserver/`. Allow about an hour from a blank laptop.

---

## Part A: Get back into the laptop (forgotten password)

**There is no data on it, so the cleanest recovery is a fresh install (Part B).** It wipes the disk and you set a new
password. You do not need the old password for that: you only need to boot from a USB stick.

Only if you want to keep what is already installed (and it is Ubuntu), you can reset the password instead:

1. Turn it on and hold **Shift** (BIOS machines) or tap **Esc** (UEFI machines) until the GRUB menu shows.
2. Highlight the Ubuntu entry and press **e**.
3. On the line that starts with `linux`, replace `ro quiet splash` (or whatever ends the line) with `rw init=/bin/bash`.
4. Press **Ctrl+X** or **F10**. You get a root prompt.
5. `passwd YOUR_USERNAME` (run `ls /home` if you forgot the name too), type the new password twice.
6. `sync` then `reboot -f`.

This does not work if the disk was encrypted at install time (it asks for a disk passphrase before GRUB finishes). If you
forgot that passphrase too, the disk cannot be opened: do the fresh install.

**If a BIOS/UEFI (firmware) password blocks the boot menu:** a fresh install still needs USB boot. Try the one-time boot menu key
first (it is often not locked). If it is, the fix is vendor-specific (clearing the CMOS battery on many older laptops; a
manufacturer service unlock with proof of purchase on most business laptops). Search "<your model> reset BIOS password".

---

## Part B: Install Ubuntu Server (lean)

You need a USB stick of 4 GB or more (it gets wiped) and your Windows PC.

1. **Download** Ubuntu Server LTS from <https://ubuntu.com/download/server> (26.04 LTS; 24.04 LTS also works). Server, not
   Desktop: no graphical desktop is the "lean" part.
2. **Make the USB** with Rufus (<https://rufus.ie>): pick the stick, pick the ISO, partition scheme **GPT**, target **UEFI**,
   Start. If Rufus asks, write in **ISO mode**.
3. **Boot from it:** plug it in, power on, tap the boot-menu key (Dell/Lenovo F12, HP F9, ASUS Esc or F8, Acer F12, MSI F11).
   If the stick does not show, enter the firmware setup (F2 or Del), turn **Secure Boot** off only if needed, and enable USB boot.
4. **Installer choices:**
   - Language and keyboard: yours.
   - Install type: **Ubuntu Server (minimized)**.
   - Network: plug in **Ethernet** if you can (most reliable for a server). Wi-Fi also works if the installer lists it.
   - Storage: **Use an entire disk**, keep "Set up this disk as an LVM group".
     - Disk encryption ("Encrypt the LVM group with LUKS"): safer if the laptop is stolen, but after every power cut someone has
       to type the passphrase on the keyboard before the server comes back. The backups are encrypted either way (Part E), and
       the LLM keeps no prompts, so **leaving it off is acceptable**. If you turn it on, write the passphrase in your password
       manager.
   - Profile: your name, server name **`bubbles-home`**, user name **`bubbles`**, and a new password. **Save it in a password
     manager now**, so this does not happen again.
   - **Install OpenSSH server: yes.** "Import SSH key from GitHub" with your GitHub user name lets you log in from your PC without
     the password.
   - Featured snaps: select **none**.
5. Remove the USB when told and let it reboot. Log in on the laptop once and run `ip -4 addr` to note its home-network IP.
6. **In the firmware setup (optional, recommended):**
   - "Restore on AC power loss" / "Power on after AC loss": **On** (it comes back after a power cut). Not all laptops have it.
   - Battery charge limit (often called "Battery conservation", "Primarily AC use", or a 60 to 80 percent cap): **On**. A laptop
     kept plugged in at 100 percent all year wears and can swell its battery.

From now on you can work from your Windows PC: `ssh bubbles@<laptop-ip>` in PowerShell.

---

## Part C: Run the setup script

From PowerShell on your PC, in the repository folder:

```powershell
scp -r scripts\homeserver bubbles@<laptop-ip>:~/
ssh bubbles@<laptop-ip>
```

On the laptop:

```bash
sudo bash ~/homeserver/setup.sh
```

It is safe to run again; it skips what is already done. It picks the model from the RAM (`llama3.2:3b` with 8 GB or more,
`llama3.2:1b` below). To choose another allowed model: `sudo HOME_LLM_MODEL=qwen2.5:3b bash ~/homeserver/setup.sh`.

**Tailscale** (step 7 of the script):

1. Make a free account at <https://tailscale.com> (sign in with Google or GitHub). Install Tailscale on your PC and phone too:
   that is how you reach the laptop from anywhere, privately.
2. The script prints a login link; open it and approve the laptop.
3. The first time, Funnel is off for your account; the command prints a link to turn it on. Approve it, then run
   `sudo tailscale funnel --bg 8088`.
4. The address looks like `https://bubbles-home.tail1234.ts.net`. Only `/v1/chat/completions` (POST, with the token) and
   `/healthz` answer there; everything else is 404, no token is 401.

The script ends by printing three lines: `HOME_LLM_URL`, `HOME_LLM_TOKEN`, `HOME_LLM_MODEL`. Then:

```bash
sudo reboot
```

After it is back: `sudo bubbles-home-status` shows every service, temperature, battery, a timed test reply, the Funnel and the
latest backup.

---

## Part D: Connect Bubbles to the laptop's LLM

In the Render dashboard (backend service > Environment), add the three printed values and redeploy:

| Variable | Value |
|---|---|
| `HOME_LLM_URL` | `https://bubbles-home.<tailnet>.ts.net` (https only; plain http is refused except `127.0.0.1` for local tests) |
| `HOME_LLM_TOKEN` | the 64-character token (a secret, like an API key) |
| `HOME_LLM_MODEL` | the model the script pulled; must be on `FREE_MODEL_ALLOWLIST["HomeServer"]` |
| `HOME_LLM_TIMEOUT_S` | optional, default 45: the most one call may take (the reply budget still caps it) |

What changes:

- With both URL and token set, `HomeServer` joins the end of the keyed fallback pool. Without them it is not in the pool at all.
- The admin console's provider pause list gains **HomeServer**, so you can switch it off without a redeploy.
- Safety is unchanged: RED and Safe Harbor replies never reach any model, and the outside-AI consent still gates every model call.
- The laptop keeps no prompts or replies: nginx logs nothing and Ollama does not store conversations.

**Be realistic about speed.** A 3B model on a laptop CPU reads a Bubbles prompt (a few thousand tokens) and writes a reply in
roughly 15 to 60 seconds; the first call after a reboot is slowest. With an NVIDIA GPU it is a few seconds. Because it is last,
it helps most in the common outage, when the cloud providers fail fast (rate limits, 5xx, missing keys). If every cloud
provider instead hangs until its timeout, the 50-second reply budget may be spent before the laptop's turn, and the person gets
the usual calm fallback message. Check `bubbles-home-status` for your laptop's real time.

Local test from your PC (inside Tailscale or through the Funnel URL):

```bash
curl -s https://bubbles-home.<tailnet>.ts.net/v1/chat/completions -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d "{\"model\":\"llama3.2:3b\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello\"}]}"
```

---

## Part E: Database safety copy

**What "database fallback" means here, honestly.** The backend talks to Supabase through its REST API and Supabase Auth, not
plain SQL, so a PostgreSQL on a laptop cannot silently take over if Supabase goes down. What the laptop gives you is a
**tested, off-site, encrypted copy** you can restore into a new Supabase project (or into the laptop's PostgreSQL to read it) if
the project is lost, corrupted or deleted by mistake. Live failover would mean self-hosting the whole Supabase stack; that is a
separate project.

Set it up once:

1. **On your PC** (not the laptop), make an encryption key pair. Windows: `winget install FiloSottile.age`, then
   `age-keygen -o bubbles-backup-key.txt`. It prints `Public key: age1...`. Keep `bubbles-backup-key.txt` in your password
   manager or on a USB stick you keep safe. **Without it no backup can ever be opened.**
2. In the Supabase dashboard: **Connect** > **Session pooler**, copy the connection string, put in the database password.
3. On the laptop: `sudo nano /etc/bubbles-home/backup.env` and fill in `SUPABASE_DB_URL` and `AGE_RECIPIENT` (the `age1...`
   public key).
4. Test now: `sudo systemctl start bubbles-backup && journalctl -u bubbles-backup -n 5`.

It runs every night at about 02:30 India time (and on next boot if the laptop was off), keeps 14 days in `/var/backups/bubbles`,
and dumps the `public` and `auth` schemas. Uploaded files in Supabase Storage are **not** included.

If no recipient is set, it writes nothing. A plain, readable copy of people's health data never sits on the laptop.

**Restore drill, once a month and after any big migration:** copy the key on a USB stick, then

```bash
sudo bubbles-restore-drill /media/usb/bubbles-backup-key.txt
```

It loads the newest backup into a scratch database `bubbles_drill`, prints the tables and row counts, then deletes it. Some
errors about Supabase-only roles and links to `auth.users` are expected on plain PostgreSQL. Take the USB out afterwards.

Restoring into a new Supabase project: decrypt on your PC with `age -d -i bubbles-backup-key.txt -o supabase.dump <file>`,
then follow Supabase's "restore from a backup" guide with `pg_restore`.

---

## Day 2

- **Health check:** `sudo bubbles-home-status`.
- **Updates:** security updates install by themselves. Monthly: `sudo apt update && sudo apt full-upgrade && sudo reboot`.
  Ollama: run its installer again (`curl -fsSL https://ollama.com/install.sh | sh`).
- **SSH with keys only** (after you confirmed key login works): `sudo nano /etc/ssh/sshd_config.d/10-keys-only.conf` with
  `PasswordAuthentication no`, then `sudo systemctl restart ssh`.
- **Change the token:** `sudo rm /etc/bubbles-home/llm_token && sudo bash ~/homeserver/setup.sh`, then update `HOME_LLM_TOKEN`
  on Render.
- **If the laptop is lost or stolen:** remove `HOME_LLM_URL` on Render (or pause HomeServer in the admin console), remove the
  device in the Tailscale admin page, and rotate the Supabase database password. The backups on it are encrypted.
- **Heat:** keep the lid open a little or the laptop on a stand; a closed lid traps heat on many models.

## Files

| File | Installed as |
|---|---|
| `scripts/homeserver/setup.sh` | run once with sudo |
| `scripts/homeserver/nginx-bubbles-llm.conf` | `/etc/nginx/sites-available/bubbles-llm` |
| `scripts/homeserver/backup-supabase.sh` | `/usr/local/sbin/bubbles-backup` |
| `scripts/homeserver/bubbles-backup.service`, `.timer` | `/etc/systemd/system/` |
| `scripts/homeserver/backup.env.example` | `/etc/bubbles-home/backup.env` |
| `scripts/homeserver/restore-drill.sh` | `/usr/local/sbin/bubbles-restore-drill` |
| `scripts/homeserver/status.sh` | `/usr/local/bin/bubbles-home-status` |
| `backend/ai_provider.py` (`call_home_server`) | the backend side; tests in `backend/tests/test_home_server_provider.py` |
