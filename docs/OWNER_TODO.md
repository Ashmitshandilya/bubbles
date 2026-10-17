# Owner to-do (things only you can do)

## Database
- Apply migrations in order: `20261016_bubbles_ops_rollups.sql`, `20261016_bubbles_ops_funnel.sql`, `20261016_bubbles_community.sql` (plus the L5 consent/audit migrations). Undo scripts are in `supabase/undo/`.

## Secrets and env
- `COMMUNITY_ALIAS_SECRET` (16+ characters; unset = Community off).
- `BUBBLES_CRON_SECRET` (or `NOTIFY_CRON_SECRET`) on Render and as a GitHub secret (used by `keep-awake.yml`).
- `FIREBASE_SERVICE_ACCOUNT_JSON` on Render (not `FCM_SERVICE_ACCOUNT_B64`).

## Android push
- Create the Firebase project, add `google-services.json`, rebuild and re-sign the APK. The APK build (`./gradlew assembleDebug`, after `npx cap sync android`) is unverified.
- Render cron: hourly `POST /internal/push/run` (runs push sweep and `ops_rollups.run_rollups`).

## Nutrient knowledge
- `python rag_nutrient_ingest.py --check-urls`, then `--apply --from-dir pages`, then `python rag_links.py --apply`, then `python eval_retrieval.py`. Check each page's licence.

## Clinical sign-off
- Review thresholds in `docs/drafts/D1-intelligence.md` and the `*-clinical.md` drafts.

## Decisions pending
- Admin refusals return the same 404 as a missing path (hides `/admin`). Say if you want 401/403 instead.

## Not yet done
- Manual keyboard and screen-reader walkthroughs, Playwright screenshots, `next build`.
