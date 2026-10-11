# Bubbles security status

Last reviewed 2026-10-11. This is an honest list: what is in place, what was added in this pass, and what only the founder can do (dashboards, keys, legal). "Verified" means it was checked against the live site or by a test, not just read.

## Launch checklist

| # | Item | Status |
|---|---|---|
| 1 | Privacy policy page | In place: `/privacy` (draft, marked as not yet reviewed by a lawyer). |
| 2 | Terms page | In place: `/terms` (same draft marking). |
| 3 | No secrets in the frontend | Verified: the code reads only `NEXT_PUBLIC_*` values (the Supabase publishable key and project address are public by design); the live bundle was scanned and contains no secret key. |
| 4 | Favicon | In place: `favicon.ico`, `icon.svg`, `apple-icon.png`, web manifest. |
| 5 | sitemap.xml and robots.txt | Added: `app/sitemap.ts` (public pages only) and `app/robots.ts`. Search engines stay blocked until `NEXT_PUBLIC_ALLOW_INDEXING=true`; share links and the sign-in callback are always blocked. |
| 6 | Social preview image | Added: `app/opengraph-image.tsx` and `app/twitter-image.tsx` (1200x630, generated at build). |
| 7 | Page titles and descriptions | In place for every page; added for the sign-in and callback pages; Open Graph and Twitter card tags added. |
| 8 | Cookie / storage notice | Added: a one-time notice. Bubbles sets no tracking or advertising cookies and loads no analytics, so this is a notice with one button, not a consent wall. If analytics or ads are ever added, this must become a real consent choice first. |
| 9 | Force HTTPS | Verified: http redirects to https on both the website (308) and the API (301); HSTS is sent (website and API). |
| 10 | No mistakes | Every change is covered by tests, and was reviewed by a second agent before release. The live checks listed in the release notes are run right after each deploy; this table is updated only after they pass. |

## Defence checklist

| # | Item | Status |
|---|---|---|
| 1 | SQL injection | Pass (audited). No raw SQL in the backend; every database call is parameterised through the Supabase client with the user value as a value, never as part of a filter string. Event ids are now checked as UUIDs before use. |
| 2 | Cross-site scripting | Pass in code (no unsafe HTML; chat text is rendered as text; links are limited to http and https). Added this pass: a Content Security Policy that limits where the browser may connect (only the API and the sign-in service), forbids plugins, framing and other form targets. Scripts still allow inline code because Next.js needs it to start pages; a nonce-based policy is a later step. |
| 3 | CSRF | Not applicable by design: sign-in is a Bearer header, there are no cookies, and the API refuses cross-origin credentials. Verified with a live preflight from another origin. |
| 4 | File uploads | There are no file uploads. The one import (CSV pasted as text) is capped at 1 MB / 2,000 rows; this pass adds a hard cap on request bodies everywhere (including chunked ones) and turns a malformed file into a plain error. |
| 5 | Broken access control | Pass (audited): every route except health and the two share links requires sign-in, and every table query is scoped to the signed-in user. Added: the four operational routes (`/ai/telemetry`, `/production/readiness`, `/models/registry`, `/privacy/security-baseline`) are administrators only (`BUBBLES_ADMIN_USER_IDS`); with none set, nobody can read them. |
| 6 | Rate limiting | Added: a limit per address in front of every route (900 per minute), a block for an address that keeps sending bad tokens (so it cannot make the sign-in service work for free), a limit on partner invite guessing (20 per hour per address), a body-size cap, and a limiter that no longer grows without bound. The address limits use the visitor address that Cloudflare supplies; if a request arrives without it they stand aside rather than risk putting every user in one shared bucket. Chat (30 per minute per user) and the existing per-route limits stay. |
| 7 | JWT / signing secrets | Supabase signs and verifies sign-in tokens (the backend checks every token with Supabase). Signed documents use `BUBBLES_DOC_SIGNING_KEY`. **Founder: set it on Render to the value the service key has today before rotating the service key**, or every partner link, plan and setting stops verifying. The server now logs a warning when it is missing and never falls back to a published value on Render. |
| 8 | API secrets server side | Verified (item 3 above and the audit). |
| 9 | Password hashing | Handled by Supabase Auth (bcrypt); Bubbles never sees, stores or logs a password. **Founder: in Supabase set the minimum password length to 8 or more and turn on leaked-password protection.** |
| 10 | Multi-factor authentication | Added: optional two-step sign-in with an authenticator app (Settings, then Account). The server enforces it too: once an account turns it on, a password-only session cannot use the API. There are no recovery codes (Supabase has none), so the setup screen tells people to save the key. Needs TOTP enabled in Supabase (Authentication, then Multi-factor; it is on by default). |
| 11 | Tighter CORS | Verified: only `https://heybubbles.in` (and www) are allowed, no credentials, fixed methods and headers; the localhost allowance is off on Render. |
| 12 | Auth tokens out of local storage | Done: the session now lives in sessionStorage (gone when the tab closes) unless the person ticks "Keep me signed in on this device". Honest limit: any script running on the page can read either store, which is why the Content Security Policy matters. Cookies with HttpOnly would need a different sign-in design. Trade-off: a new browser tab starts signed out. |
| 13 | Permissions enforced server side | Pass for partner sharing (whitelisted categories, checked on every read), cycle privacy modes, two-step sign-in and now consent: a message goes to an outside AI model only after the person says yes, the server checks that answer (signed record, versioned, fail closed) before anything is sent, and it can be withdrawn in Settings. Emergencies, corrections, daily logs and fitness questions never depend on it. |
| 14 | Row Level Security | Verified on the live database (read-only catalog check): every public table has RLS, no policy is open to everyone, the anonymous role has no table access, and signed-in users can only read their own chat rows. **Founder (database):** the repo and the live schema have drifted (see below). |
| 15 | Webhook signatures | Not applicable: Bubbles has no inbound webhooks. |
| 16 | SSRF | Pass (audited): no route takes a URL or host from a user; outbound calls go to fixed hosts from settings. |
| 17 | Source maps and debug pages | Verified: no browser source maps are published. Fixed this pass: the API docs, schema and redoc pages were public; they are now off on Render. The debug trace is refused on Render. |
| 18 | Default credentials | None in code. The development token "preview" works only in the local preview server, which refuses to start without `BUBBLES_PREVIEW=1`. The local start script now binds to this computer only. |
| 19 | Sensitive data in logs | Improved: share tokens and query strings are removed from the server access log; the chat log line no longer lists symptom concepts. Logs already scrub emails, long tokens and numbers. Dead code that printed full prompts (`omniroute_client.py`) was deleted. |
| 20 | Vulnerable dependencies | Checked and fixed: server (pip-audit) reported 3 packages; all updated and tested, now clean. Website (npm audit, production packages): the PostCSS issue inside Next.js is fixed with an override; clean. Two development-only tools (`braces`, `eslint-config-next`) still report issues; they do not ship to visitors. An automated weekly check is a good next step. |

## Before real users (founder and later work)

1. **Rotate every key that was ever pasted in a chat** (Supabase secret key, AI provider keys). First set `BUBBLES_DOC_SIGNING_KEY` on Render to the current service-key value.
2. **Supabase dashboard:** Site URL `https://heybubbles.in`; Redirect URLs `https://heybubbles.in/**`; password minimum 8+; leaked-password protection; custom SMTP; CAPTCHA if signups get abused.
3. **Database (SQL editor, one time):** `revoke execute on function public.rag_hybrid_search(text, extensions.vector, integer, uuid, text, text) from authenticated;` The live function trusts a caller-supplied user id; it is not exploitable today because signed-in users have no read access to the evidence tables, but the permission should not exist. The hardened version in `supabase/migrations/20260919_coco_r5_rag_scope_hardening.sql` is not what is live.
4. **Render:** move from the free plan (it sleeps, and the in-memory limits reset when it restarts); keep one instance while the limiters are in memory.
5. **Legal:** a lawyer's review of Privacy and Terms; trademark check; clinical review of the safety rules.
6. **Database drift:** about 219 tables on the live database have no definition in the repo, and the migration files do not replay in filename order. Export the live schema as the new baseline before anyone else sets up a copy.

## Live verification (2026-10-11, after release c7e5c7a)

Checked on https://heybubbles.in and https://bubbles-dk3v.onrender.com:
- Website headers present: Content-Security-Policy, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy (microphone allowed for Bubbles only), Cross-Origin-Opener-Policy, HSTS with includeSubDomains.
- Landing page and sign-in page load with no CSP violations and no console errors; no cookies are set; the sign-in session is not in localStorage. An outside script (the accessibility checker from a CDN) was refused by the browser, which shows the policy is enforced.
- `/sitemap.xml`, `/robots.txt` (still `Disallow: /`), `/opengraph-image` and `/twitter-image` return 200.
- API `/docs`, `/redoc` and `/openapi.json` now return 404; `/health` GET and HEAD return 200; CORS still allows only https://heybubbles.in.
- Bad-token block: 30 requests with a made-up token answered 401, the next ones 429 with `Retry-After: 60`, `/health` stayed 200, and the block cleared by itself after a minute. This also shows Cloudflare supplies the visitor address to the server, so the address limits are active.

Not verified live (needs a real account or dashboard access): sign-in and the authenticator-app setup on the live site, the share preview in WhatsApp or another app, and the Supabase dashboard settings.

### Live verification of the consent release (2026-10-11, commit 842e900)
- Vercel deployment READY; the privacy page shows the new "only after you say yes" wording; `GET /me/consent` without a token answers 401 (the route is deployed); all public pages, `/health` GET and HEAD, and CORS from https://heybubbles.in are fine; API docs still 404; the GitHub tests workflow is green on this commit.
- Not verified live (needs a real signed-in session): the consent card in the chat, saving the yes, and the Settings switch. They were checked in the local preview and by 10 server tests.
