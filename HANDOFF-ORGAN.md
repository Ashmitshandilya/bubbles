# Handoff: Body map (organ tracker, 3D)

Branch `organ-tracker-3d`, cut from `origin/main` 328ecca. Do not push or merge it to `main` without the owner's go-ahead, because `main` deploys heybubbles.in.

Review status: Sir Noah gave "accept with conditions". All three must-fix items are now fixed, along with every should-fix item except a real-device frame-time measurement (see "What remains").

## What was built

A new **Body map** tab under Patterns (`/body`). It shows ten areas of the body on a 3D anatomical model, with a flat SVG fallback. For each area it shows what the user's own entries say, how sure Bubbles is, what is still missing, and one next step. Bubbles is not a diagnostic engine, so the page follows these rules:

- **Safety first.** Recent symptoms (from the last 7 days) go through the same `safety_engine` that chat uses before any status is set. `safety` is the first key of every organ object, and no area can show a calmer status than its safety result. In the urgent state the page hides the mascot. Below the `lg` breakpoint, the safety message sits above the body view, so a phone never has to scroll to reach it.
- **Missing data is a gap, never "healthy".** An area with nothing logged shows as "No data yet", and the page says so in three places.
- **Only the user's own data.** Every read filters on the signed-in user's id. There are no analytics, no schema change, no new dependencies and no secrets.
- **Truthful dates.** The predicted cycle phase is shown as a note. It is not counted as evidence, so it never sets "Last entry" and never raises the confidence level.
- **Uterus and ovaries are opt-in.** They appear only for people who use Cycle or who have logged something about that area. Otherwise they are left out of the map and the model, and `GET /organs/uterus_ovaries` returns 404 with a plain explanation.

### Files

| Area | Files |
|---|---|
| Engine | `backend/organ_map_engine.py`, with constants added to `backend/clinical_constants.py` (additive only, marked pending clinician review) |
| API | `backend/organ_map_api.py` (router) and 2 lines in `backend/main.py` |
| Backend tests | `backend/tests/test_organ_map_engine.py`, `backend/tests/test_organ_map_api.py` |
| Page | `frontend/app/body/page.tsx`, `frontend/app/body/BodyClient.tsx` |
| Components | `frontend/components/anatomy/BodyViewer.tsx` (react-three-fiber), `BodyFallback2D.tsx` (SVG), `OrganPanel.tsx`, `OrganList.tsx`, `anatomy.test.tsx` |
| Client logic | `frontend/app/lib/organ-map.ts`, `frontend/app/lib/organ-map.test.ts` (includes the `body.glb` guard) |
| Shared edits | `frontend/components/Navigation.tsx` (1 line: the Body map tab), `frontend/components/AskBubbles.tsx` (1 line: the floating button is hidden on `/body`, because the panel has its own "Ask Bubbles about this" button) |
| Model | `frontend/public/models/body.glb` |
| Model build | `scripts/anatomy/*`: `build_body_model.mjs`, `female_pelvis.mjs`, `inspect_body_model.mjs`, `organs.json`, `CREDITS.md`, and a separate `package.json` with pinned `@gltf-transform` and `meshoptimizer` |
| Screens | `docs/organ-tracker/screens/*.png` (12 files) |

### Endpoints

Both endpoints need a Bearer token. `days` accepts 7 to 180 (default 30); a value outside that range returns 422.

- `GET /organs/map?days=30` returns `{status, window_days, as_of, organs[], counts, not_a_diagnosis, unavailable[]}`. If labs, conditions or cycle data can't be read, the map is still returned and the failed source is named in `unavailable`. If the events read fails, the endpoint returns an error, never an empty map.
- `GET /organs/{organ_id}?days=30` returns one organ. An unknown id returns 404, and so does a hidden opt-in organ.

Each organ object contains `safety` (always first), `status` (`talk_to_doctor` / `worth_watching` / `steady` / `no_data`), the evidence (newest first, red flags first, at most 12), `confidence {level, reason}`, `missing[]`, `notes[]`, `next_step` and `updated_at`.

The ten organ ids are `heart`, `lungs`, `brain`, `stomach_intestines`, `liver_pancreas`, `kidneys_bladder`, `thyroid`, `uterus_ovaries` (opt-in), `skeleton_muscles` and `skin`.

### Model

- `body.glb` is 5,759,880 bytes with 410,189 triangles. The only required extension is `KHR_mesh_quantization`, so no decoder is needed and nothing conflicts with the site's security policy (CSP).
- It has 14 named meshes: skeleton, brain, thyroid, heart, lungs, liver, stomach, pancreas, intestines, kidneys, bladder, uterus, ovaries and skin.
- **Credits** (full detail in `scripts/anatomy/CREDITS.md`, also stored in the GLB's `asset.copyright` field and per-node extras):
  - Most parts come from BodyParts3D, © The Database Center for Life Science, CC BY-SA 2.1 JP.
  - Thyroid, stomach, bladder and lungs come from Z-Anatomy (Gauthier Kervyn and contributors), CC BY-SA 4.0, through the export in DrMuratAltun/anatomi-simulatoru at commit 37e85df, whose 3D data is CC BY-SA 4.0.
  - The uterus and ovaries are procedural and **illustrative**.
  - The combined model is CC BY-SA 4.0.
- The 3D view's caption says the anatomy was "adapted" and links both licences.
- On touch devices, organs use a plain satin material without clearcoat or sheen, to save GPU work.

## Gate results (run on dcf0bff)

| Gate | Result |
|---|---|
| Backend `python -m pytest tests` | **2065 passed, 2 skipped** (111 s). The organ tests alone: **140 passed** |
| Frontend `tsc --noEmit` | clean |
| Frontend `npm run lint` | clean |
| Frontend `vitest run` | **807 / 807 passed** in 65 files (includes 3 new `body.glb` guard tests) |
| Frontend `npm run build` | compiled successfully. `/body` is 13.3 kB, first load 207 kB. three.js and the model load only when the device gets the 3D view |
| Merge check | `git merge-tree` shows no conflicts against `origin/main` or against the local `redesign-pearl-lab` (7ac182c) |
| Browser console | zero errors in all 8 runs. The only warnings come from three.js and ANGLE: a "THREE.Clock deprecated" notice raised inside @react-three/fiber, and the shader compiler's X4122 precision notes. Neither comes from our code |
| Layout | no horizontal scroll at 375 px or 1440 px |

## Screenshots

All screenshots are in `docs/organ-tracker/screens/`. They were taken from a production build (`next start`) against the real API running on the test FakeDB with two seeded users: Riya (who uses Cycle and has a PCOS entry) and Arjun (chest pain yesterday and raised blood pressure readings).

- `desktop-1-initial.png`: first view at 1440 px.
- `desktop-2-selected-uterus.png`: "Last entry 7 Oct" (the predicted phase now shows as a note), and no floating button covering the panel.
- `desktop-3-flat-no-webgl.png`: the flat view with WebGL disabled. The uterus and ovaries sit behind the gut, and the caption no longer credits 3D anatomy.
- `desktop-4-urgent-heart.png`: Arjun's map. The safety message comes first, and the uterus and ovaries are not shown.
- `phone-*.png` and `phone-*-panel.png`: the same four states at 375 px. In `phone-4-urgent-heart.png` the safety message is above the body without scrolling.

## Run it on localhost

1. **Backend.** In `backend/.env`, set `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Then run:
   ```
   cd backend
   python -m uvicorn main:app --reload
   ```
   It serves on 127.0.0.1:8000.
2. **Frontend.** This clone has no `node_modules` of its own. Link the shared copy with a junction, and do not run `npm install` into it:
   ```
   cmd /c mklink /J frontend\node_modules D:\COCO\bubbles\frontend\node_modules
   ```
   In `frontend/.env.local`, set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`, `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Then run `npm run dev` and open http://localhost:3000/body after signing in.
3. **Rebuilding the model** (optional):
   ```
   cd scripts/anatomy
   npm ci
   npm run build
   npm run inspect
   ```
   The build downloads the BodyParts3D and Z-Anatomy sources listed in `CREDITS.md`. Afterwards, re-run vitest: the guard test fails if the file goes over 6,000,000 bytes, if a mesh name drifts from `ORGAN_PARTS`, or if meshopt or Draco compression comes back.

## What remains

- **Frame time on a real mid-range Android phone has not been measured.** Phones already skip clearcoat and sheen, but the model still has 410k triangles. If that phone stays under 30 fps, the next steps are a decimated phone LOD or a flat view by default on low-memory devices (`prefer3D` already reads device memory and core count).
- **Clinician review of the thresholds.** The constants in `clinical_constants.py` are marked `PENDING CLINICIAN REVIEW`.
- **No "hide this area" setting.** Uterus and ovaries are shown automatically, based on Cycle use or entries. A manual toggle or a profile-based choice would need a profile field, which means a schema change. That was left out on purpose.
- **The anatomy is approximate.** The uterus and ovaries are illustrative and placed in a male pelvis, and the model has a single body shape.
- **Evidence order is not strictly by date.** Within an organ, red flags and notable readings come first, so blood-pressure rows can read 10 Oct, 6 Oct, 13 Oct. This is intended, but it may be worth a small "notable" label.

## Merging with the landing redesign

The redesign is happening in `D:\COCO\bubbles` on the local branch `redesign-pearl-lab`. As of 7ac182c it has not been pushed. So far it changes only `frontend/app/layout.tsx` (fonts) and `frontend/tsconfig.json`.

- **Recommended order:** merge `organ-tracker-3d` into `main` first through a PR, then rebase or merge the redesign onto the new `main`. Either order works, because this branch is almost entirely new files.
- **Expected conflicts: none today.** `git merge-tree` against `redesign-pearl-lab` is clean. If the redesign later edits these shared files, the conflict will be one line in each:
  - `frontend/components/Navigation.tsx`: the Patterns section's `match` array and `tabs` list (keep `"/body"` and the `{ label: "Body map", href: "/body" }` tab).
  - `frontend/components/AskBubbles.tsx`: the `pathname !== "/dashboard" && pathname !== "/body"` condition.
  - `backend/main.py`: one import and one `include_router` line, next to the partner router.
- **Visual follow-up after the merge.** The body map uses only existing tokens from `frontend/app/tokens.css` and the HubKit components, so it will pick up the new fonts and theme automatically. Retake the screenshots afterwards. The pearl backdrop behind the body (`PEARL` in `BodyClient.tsx`) is built from palette tokens and should be checked against the new pearl theme.
