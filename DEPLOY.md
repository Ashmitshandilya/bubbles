# Deploying Bubbles (heybubbles.in)

Bubbles has been live since 2026-10-10 (see "Current production setup" below). This is the checklist, in the order that avoids breaking the app, and the record of how it is set up. Items marked **YOU** need your accounts or decisions.

## 0. Before anything else
- **Back up** the Supabase project (Dashboard → Database → Backups), or at least confirm you are on the intended project.
- **Name check (YOU):** `heybubbles.app` is a live AI assistant called "Bubbles". Have a trademark attorney search "Bubbles"/"Hey Bubbles" (India classes 9, 42, 44, 35) before spending on branding.

## 1. Database (Supabase) — do this BEFORE starting the renamed backend
1. Open the Supabase SQL editor and run `supabase/migrations/20261010_bubbles_rename.sql` once. It renames the two Coco tables, their constraints, indexes and policy, and rewrites four value columns (chat role, feature-document type, event sources, RAG source name). It prints counts; every `*_left` number must be `0`.
2. Why first: the renamed backend reads `bubbles_*` tables and the value `bubbles` for chat roles. Until the script runs, saved games/preferences, stored plans and the chat history roles look empty.
3. Rollback: restore the backup, or reverse the renames (the script is a set of simple renames and four `update`s).
4. Auth settings (Dashboard → Authentication → URL configuration): Site URL `https://heybubbles.in`; add redirect URLs `https://heybubbles.in/**` and `https://www.heybubbles.in/**` (the app uses `/callback`). Update email templates that still say "Coco".

## 2. Backend (FastAPI)
Environment (names are `BUBBLES_*`; old `COCO_*` names are still mapped by `env_compat.py`, so an existing `.env` keeps working):

| Variable | Notes |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Server only. Never put the secret key in the frontend. |
| `BUBBLES_FRONTEND_ORIGINS` | `https://heybubbles.in,https://www.heybubbles.in` (also the built-in default) |
| `BUBBLES_DOC_SIGNING_KEY` | **Do not change it** once users have saved plans (signatures would stop verifying). If you used `COCO_DOC_SIGNING_KEY` or relied on the fallback to the service key, keep the same value. |
| `ALLOW_PAID_AI`, `ALLOW_KEYLESS_AI`, `ALLOW_KEYLESS_HEALTH_DATA` | Keep `false` (the $0 AI policy). |
| `GROQ_*` / `NVIDIA_*` / `MISTRAL_*` | Only providers you verified as free. |
| `BUBBLES_CLINICALLY_REVIEWED` | Leave `false` until a clinician signs `docs/clinical/BUBBLES_CLINICAL_REVIEW_PACKET.md`. |
| `BUBBLES_ENABLE_RXNAV` | Leave unset (drug names are not sent to an outside service). |

Run: `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'` (see `backend/Procfile`). Python packages: `pip install -r backend/requirements.txt` (versions are pinned; use the same Python minor version you develop with; test tools are in `backend/requirements-dev.txt`, which the server does not need). Health check: `GET /health` (answers HEAD too, for uptime monitors).
- **RAG switches (all optional, defaults are the tested setting):** `RAG_EXPAND=0` turns off lay-term expansion, `RAG_EXPAND_MODE=or|embed|and`, `RAG_LINKS=0` turns off link-aware retrieval. After any new ingest run `python rag_links.py` (dry run) and `--apply` to keep the `link:` tags current, then `python eval_retrieval.py`.
- **Run ONE instance for now.** The request rate limiter is in memory per process; several instances would each have their own counters.
- Put it on its own address, for example `https://api.heybubbles.in`.

## 3. Frontend (Next.js)
Set on the host (see `frontend/.env.example`): `NEXT_PUBLIC_API_URL` (https), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_SITE_URL=https://heybubbles.in`, `NEXT_PUBLIC_ALLOW_INDEXING=false`.
Build: `cd frontend && npm ci && npm run build` (verified locally); start with `npm start` or let the host build it. When you are ready to be found on Google, set `NEXT_PUBLIC_ALLOW_INDEXING=true` and redeploy.

## 4. DNS and HTTPS (YOU)
Point `heybubbles.in` and `www` at the frontend host and `api` at the backend host, using the records your hosts show. Turn on HTTPS (usually automatic). The app refuses to call an `http://` API from an `https://` page.

## 5. Smoke test after deploy
1. `GET https://api.heybubbles.in/health` returns ok and database `ok`.
2. Open the site, sign up, sign in, send a chat message, log a meal.
3. Partner sharing, with two real accounts A and B: A opens **Partner sharing**, saves choices, makes an invite code; B signs in, enters the code under **Shared with you** and sees A's summary; A changes the choices and B sees the change; A disconnects and B sees nothing. Then make a quick link, open it in a private window (no login), turn it off, reload: it must say the link is no longer active.
4. Try an emergency phrase in chat: the reply must be the emergency message, not a model answer.

## Android app
See `docs/ANDROID.md`. `cd frontend && npm run android:release` builds, signs and copies the APK to `frontend/public/android/`; deploying the website publishes it at `https://heybubbles.in/android`. Back up `%USERPROFILE%\.bubbles-signing` — without that key no update can be installed.

## 6. Not done / needs a person
- Trademark clearance and a decision on the logo and mascot (file and component names changed to Bubbles; the artwork itself did not).
- Privacy policy, terms of use, a contact address, and the consent wording — required before real users.
- Clinical review of the safety rules, stroke-sign patterns and drug-brand aliases (see `docs/clinical/`).
- Monitoring, alerts and a backup schedule; rotating any key that was ever shared.
- The RAG knowledge load is separate (`backend/rag_bulk_ingest.py`); the editorial source is now named "Bubbles editorial".

---

## Current production setup (live since 2026-10-10)

| Part | Where | Notes |
|---|---|---|
| Website | Vercel project `bubbles-7x74` (team `hey-bubbles`), deploys from GitHub `Ashmitshandilya/bubbles`, branch `main`, Root Directory `frontend` | Main address **https://heybubbles.in**; `www.heybubbles.in` redirects to it. Next.js 15.5.27. |
| Backend API | Render Web Service `bubbles`, Singapore, **Free plan** (sleeps after ~15 min idle) | https://bubbles-dk3v.onrender.com. Root Directory `backend`. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`. Health check path `/health`. `PYTHON_VERSION=3.14.7`. |
| Database | Supabase, region ap-northeast-2 (Seoul) | Rename script `supabase/migrations/20261010_bubbles_rename.sql` applied 2026-10-10 (undo script in `supabase/undo/`). |
| DNS | GoDaddy: `A @ -> 216.198.79.1`, `CNAME www -> 4fe0e7f393824a0d.vercel-dns-017.com` | Verified working. |

Vercel settings (names only): `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_ALLOW_INDEXING` (false = hidden from Google), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_URL` (the Render address).
Render settings (names only): `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `BUBBLES_FRONTEND_ORIGINS`, `BUBBLES_DOC_SIGNING_KEY`, `PYTHON_VERSION`, the AI provider keys and models, `ALLOW_PAID_AI=false`, `ALLOW_KEYLESS_AI=false`, `ALLOW_KEYLESS_HEALTH_DATA=false`.


### Addresses and sign-in links (read this if "Can't connect to Bubbles" or a confirmation email lands on a Vercel address)
- Use **https://heybubbles.in** only. The API accepts browser requests only from the origins in `BUBBLES_FRONTEND_ORIGINS`, so the app cannot work from `bubbles-7x74.vercel.app` or `bubbles-7x74-hey-bubbles.vercel.app` (those also sit behind Vercel's own login). `frontend/next.config.ts` redirects both to the real site; preview deployments are not redirected.
- Confirmation and magic-link emails always ask Supabase to return to `https://heybubbles.in/callback` (`frontend/lib/auth-links.ts`). Supabase only honours that if it is in Authentication -> URL Configuration -> Redirect URLs, otherwise it falls back to the Site URL. So keep **Site URL = `https://heybubbles.in`** and **Redirect URLs = `https://heybubbles.in/**`** (item 2 above). The built-in Supabase email sender has a very low hourly limit: add custom SMTP before inviting more than a handful of people, and consider CAPTCHA if signups get abused.
- Backend routes added since launch (no schema change): `/wellness/associations`, `/chat/feedback`, partner sharing and the privacy/terms pages. After a backend deploy, `GET /chat/feedback` without a token should answer 401 (not 404).


### Security settings (see `docs/security/SECURITY_STATUS.md` for the full list)
- `BUBBLES_DOC_SIGNING_KEY` (Render): signs partner links, plans and settings. Set it to the value the service key has TODAY before you rotate `SUPABASE_SECRET_KEY`; if it is unset the service key is used, and rotating that key would invalidate every signed document at once.
- `BUBBLES_ADMIN_USER_IDS` (Render, optional): comma-separated user ids allowed to read the four operational routes (`/ai/telemetry`, `/production/readiness`, `/models/registry`, `/privacy/security-baseline`). Leave it unset and nobody can.
- `BUBBLES_IP_RATE_LIMIT` (default 900 per minute per address), `BUBBLES_AUTH_FAIL_LIMIT` (default 30 bad tokens per minute per address), `BUBBLES_CONNECT_RATE_LIMIT` (default 20 invite attempts per hour per address): tune only if real users are being slowed. Keep ONE server instance while these live in memory.
- The API docs (`/docs`, `/redoc`, `/openapi.json`) and the debug trace are off on Render. Set `BUBBLES_ENABLE_DOCS=1` only for a short debugging session.
- Two-step sign-in (authenticator app) needs TOTP enabled in Supabase (Authentication, then Multi-factor). It is on by default.
- The website sends a Content Security Policy built from `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SUPABASE_URL`. If you move the API to another address (for example `api.heybubbles.in`), change the variable and redeploy, otherwise the browser will block the calls.

### Still to do before inviting real users
1. Replace every secret that was ever pasted into a chat (Supabase secret key, all AI provider keys); update them in Render and your local `.env`.
2. Supabase -> Authentication -> URL Configuration: Site URL `https://heybubbles.in`, Redirect URLs `https://heybubbles.in/**` and `https://www.heybubbles.in/**`.
3. Move Render from Free to a paid plan (the free server sleeps; the first message after a pause is very slow).
4. Optional: `api.heybubbles.in` (Render -> Custom Domains, GoDaddy CNAME `api`), then change `NEXT_PUBLIC_API_URL` in Vercel and redeploy.
5. Delete the old empty Vercel project `bubbles`; remove the extra Supabase/Postgres variables Vercel's Supabase integration added to the website project.
6. Trademark check for "Bubbles", privacy policy, terms of use, clinical review; then set `NEXT_PUBLIC_ALLOW_INDEXING=true` to launch.
7. Test with two real accounts: sign up, chat, partner sharing (invite code and quick link).
