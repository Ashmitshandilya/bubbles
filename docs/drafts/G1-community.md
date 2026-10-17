# G1 Community (lane L10) - draft for the lead to fold in

## Decision log entry (newest first)

**Community v1: text-only, consented, alias-anonymous, bot-moderated, owner-reviewed.**
- Text only. No images, video, files or link previews. Checking images for nudity needs a vision classifier, which the $0-AI policy does not provide. Images stay out of scope until the owner decides.
- Off until `COMMUNITY_ALIAS_SECRET` (16+ characters) is set on the API host. There is no default secret on purpose. Unset means every community route answers "off" and the admin Moderation tab says why.
- Aliases ("Quiet Otter 4821") come from an HMAC of (author, thread) with that secret: stable inside one thread, different across threads. No response ever carries `author_id`. Only the admin can resolve an alias (`POST /admin/community/resolve`), and the lookup is written to the moderation log before the answer leaves.
- Who can post: signed in, 18+ (birth date from setup), `community_visibility` consent granted, not banned. Reading needs only sign-in and 18+. Deleting your own posts and comments works even after withdrawing consent.
- Limits: 5 posts/hour, 20 comments/hour, 10 reports/hour, post 1,200 and comment 600 characters, duplicate text refused for 24 hours. Deleting leaves a stub so the hourly limit cannot be dodged.
- Moderation order: deterministic filters (`community_moderation.py`, word lists as data), crisis wording kept and held for the owner with the caring banner (112, Tele-MANAS 14416 / 1-800-891-4416, findahelpline.com via `safety_engine.CRISIS_LINES`), held when unsure (visible to the author only), removed when certain, 3 distinct reporters auto-hide, admin decides. No AI text classifier in v1 (consent for `ai_chat_processing` does not cover posts).
- Crisis posts are held (not on the feed) until the owner looks, then approved or removed. Frontend shows the banner without the mascot.
- The admin sees post text in the Moderation tab: the owner is the data controller of a shared space. Add one plain line to the privacy notice.
- Delete-my-data wipes posts, comments, reactions, reports and blocks (`community_api.forget`); the moderation log keeps codes only.

## Frontend

- `frontend/app/community/` (page, `CommunityClient.tsx`, pure `community.ts` + test): feed with topic chips and My posts, big "Ask or share" button opening a sheet (anonymous switch, topic, text), reactions (Me too, Helpful), closed Comments row, report / block, delete own, "Show more" cursor paging, mascot empty state, permanent line "Shared by people, not medical advice."
- Posting needs consent: the button is disabled with a link to Privacy choices (`/privacy-choices`) when `reason` is `consent_needed`.
- Admin: `frontend/app/admin/panels-moderation.tsx`, registered in `registry.tsx`, tab `moderation` in `format.ts` (queue with crisis first, approve / remove / remove and ban, "Who wrote this", audit log).

## For the lead (not done by this lane)

- Navigation: add **Community** to `SECTIONS`, route `/community`. Palette entry: "Community / Ask or share" -> `/community`.
- Owner: apply `supabase/migrations/20261016_bubbles_community.sql` (undo file beside it), set `COMMUNITY_ALIAS_SECRET` on Render, and add the privacy-notice line about moderators reading shared posts.
- Clinical packet (new numbered section): the crisis banner wording (reuses the frozen CRISIS_LINES), the unsafe-advice filter (dosing, "stop your medicine", diagnosis as fact), and the held-on-crisis rule. Hinglish terms live in `backend/data/` word lists.
- RLS note for the PR: all `community_*` tables have RLS on and no client policy; every read and write goes through the service-role backend.

## Verification

Mutation checks (each caught by `tests/test_community_api.py`, code restored after each):
- Consent gate disabled in `require_writer` -> `test_a_post_without_the_consent_is_refused_and_nothing_is_stored` fails.
- Weak default alias secret -> `test_without_the_alias_secret_the_feature_refuses_with_no_weak_default` fails.
- Rate limit disabled (`over_limit` returns False) -> `test_five_posts_an_hour_and_the_sixth_is_slowed` fails.
