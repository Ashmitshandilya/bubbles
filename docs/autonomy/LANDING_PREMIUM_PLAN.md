# Bubbles landing: premium direction and build plan

Author: LIXIE (CTO and art director). Date: 2026-10-10. Branch: ui-intelligence-overhaul-2026-10-10.
Status: plan for founder approval. No code was changed to write this file.
Paths: relative to `frontend/app/landing/` unless they start with `frontend/`, `scripts/` or `docs/`.
Effort scale: 1 chunk = one scheduled wake-up of one or two agents (PLAN.md rule 8). Owners: EXP = experience agent, ENG = engineering agent, TEST = tester, CHK = checker, NOAH = acceptance.

## 0. Read this first

The founder is right. The page is not premium yet, and the reasons are specific, not taste. The old landing has the right bones (one scroll director, one persistent canvas, chapters, portals, honest demos). What it lacks is a real character, real light, real air and real type. The v2 page is a competent template and nothing more.

The plan keeps the old soul (body, numbers, track, cycle, connect, memory, companion, care, start) and rebuilds the skin: a cinematic color script across one continuous day, a living portrait of the approved unicorn doctor placed inside the 3D scene, a shader sky with real depth, iridescent soap bubbles that refract, and a type voice that is not the default tech-startup look. It is built as three quality tiers (static, lite, full) so phones stay at 60fps and reduced-motion visitors get a calm, complete page.

### Decisions needed from the founder

| # | Decision | Default if no answer | Blocks |
|---|---|---|---|
| D1 | Approve the direction "A day in Bubbles' sky" (section 2.1) | Approved | Step 1 |
| D2 | Save the ORIGINAL concept 2 file from Canva as PNG, at least 2048 px on the long side (a clean one with no watermark). The current `frontend/public/brand/bubbles-hero.jpg` is 149x199 and 10.6 KB: nothing premium can be built on it | None. Hard blocker | Step 2 final assets, Step 12 |
| D3 | Type voice: A = Fraunces headlines, Nunito body, Fredoka logo and chips (recommended). B = keep Bricolage Grotesque | A | Step 7 |
| D4 | Accept that the figure is a depth-extruded relief of the painting (about 8 degrees of orbit, not a free 3D model). Blink and mane may need an artist-layered file if the shader versions look cheap | Accepted | Step 3 |
| D5 | One Bubbles everywhere: the in-app mascot (18+ screens) is still the OLD SVG drawing and must become a crop of concept 2 | Yes | Step 12 |
| D6 | Sound: off by default, one toggle | Off | Step 6 |
| D7 | Shorten the story from 2620vh to about 1890vh (same eight chapters) | Yes | Step 1 |
| D8 | Confirm or remove two v2 claims: "over five thousand passages" (must match the live corpus count from `/knowledge/health`) and "free while in early access" | Remove until confirmed | Step 13 |

---

## 1. Audit

### 1.1 Facts verified in the repo today

- `frontend/app/page.tsx` still mounts the OLD `Landing`. `landing/v2/` is untracked and not routed anywhere.
- `frontend/public/brand/bubbles-hero.jpg` is 149x199 (10,642 bytes). On screen it is enlarged to about 500x670, so it is visibly soft.
- `story/store.ts` `CHAPTERS` lengths sum to 2620vh (170, 280, 210, 240, 400, 260, 330, 300, 250, 180). That is 26 screens of scroll.
- Fonts on the old landing: Bricolage Grotesque (display), Geist Mono (labels), Fredoka (logo). The app uses Fredoka and Nunito. Three families on one page and a split from the product.
- Eight of ten old chapters are flat plum hexes (`#170A14`, `#120814`, `#170B1A`, `#240A1B`, `#110A18`, `#120C1C`, `#160C1D`). Chapter color is mixed in sRGB by `mixBg` in `story/ScrollDirector.tsx`.
- The figure on the old page is `BubblesFigure` (flat SVG, the OLD drawing) layered over the WebGL canvas by `story/BubblesHost.tsx`. It is not the approved concept 2.
- `components/BubblesMascot.tsx` renders `landing/BubblesMark.tsx` (the old drawing) on 18+ screens. Two different Bubbles would exist after the landing changes.
- Installed: three 0.186.1, @react-three/fiber 9.8, @react-three/drei 10.7, motion 14.1, lenis 1.3, @axe-core/playwright, playwright (unpinned "latest"), vitest 4. NOT installed: any postprocessing package, gsap, leva. `three/examples/jsm/postprocessing` does contain EffectComposer, RenderPass, UnrealBloomPass, OutputPass, ShaderPass, BokehPass, so no new dependency is needed for post effects.
- `CLAUDE.md` says Next.js 16; `frontend/package.json` pins Next 15.5.27 and React 19.3.0. This plan assumes the installed 15.5.27. Anything Next-specific must be checked against `frontend/node_modules/next/dist/docs/` first.
- `frontend/next.config.ts` has no image or header configuration, so static textures get default caching and AVIF is not enabled for `next/image`.

### 1.2 What the old landing does well (keep all of this)

| Keep | Where | Why it is premium-grade |
|---|---|---|
| One rAF director writes `--p`, `--in`, `--out` and `--bg` as CSS variables. No scroll listeners, no React state at scroll rate | `story/ScrollDirector.tsx`, `story/store.ts` | This is how studio sites stay smooth. Do not replace it. It also already damps scroll, which is why Lenis is unnecessary |
| Chapters are fixed layers that cross-fade, with clip-path portals (dive into the body, bloom out of the horn) | `landing.css` story mode, `ScrollDirector` portal vars | Reads as one film, not as stacked sections |
| One persistent canvas; one recurring object (28 beads) morphs: spine, data, orbit, 28-day ring, lattice, timeline, halo | `world/Spine.tsx`, `world/rig.ts` | A single motif across the whole story is the strongest storytelling device we have |
| HTML labels pinned to 3D points (nerve labels) | `world/Spine.tsx`, `story/SystemLabels.tsx` | Text stays crisp and accessible; WebGL never draws copy |
| Demos that behave like the product: typed message becomes three records awaiting confirmation; companion shows safety check, memory, logs, sources, then the answer; everything labelled "Example" | `story/TypedIntake.tsx`, `story/CompanionDemo.tsx` | Honest and convincing. Far better than the v2 mock screens |
| Honest degradation: reduced motion gives a calm document, weak device gate, WebGL error boundary, `resetStory` on client navigation, `noscript` | `Landing.tsx`, `world/WorldMount.tsx`, `store.ts` | Keep the contract, widen the tiers |
| Character voice: greeting by time of day, boops, "Hoof promise", event bus (`bubbles:say`, `bubbles:boop`, `bubbles:spark`) | `story/SpeechBubble.tsx`, `store.ts` | Charm that cannot be bought. Keep the events and lines |
| Tests on story state | `story/story-state.test.ts` | Keep and extend |

### 1.3 Why the old landing still feels basic (blunt)

| Dimension | Problem |
|---|---|
| Imagery | The hero character is a flat SVG sticker, and it is the old drawing, not the approved realistic art. There is no photographic or painterly richness anywhere on the page. Everything is CSS, SVG or primitive geometry |
| Depth | Two worlds that never touch: a vector mascot over a 3D scene. It receives no light, casts no shadow, is never occluded by anything. This is the "sticker on a render" tell |
| Lighting | One static three-light rig for ten chapters. No time of day, no light direction continuity, no rim from the sky, no volumetric light. Nothing is ever lit by anything |
| Materials | Pearl `MeshPhysicalMaterial` with `RoomEnvironment` (the stock R3F studio look), matte, identical on every bead. No transmission, iridescence or refraction. The page's own name is "Bubbles" and nothing in it looks like a soap bubble |
| Backgrounds | Flat plum fills with 820 identical additive dots (`world/Motes.tsx`). No horizon, haze, parallax layers, bokeh, god rays or dithering. Linear sRGB mixing makes muddy mid-tones between chapters |
| Color and mood | Eight of ten chapters are near-black plum. The brand is pearl, blush, pastel and "cute on the outside". The page mood is sci-fi anatomy |
| Type | Three families, uppercase mono micro-labels everywhere (cold, developer-tool tone), one display weight (720, width 84) for every heading. No scale contrast, no voice, no emphasis style |
| Pacing | 2620vh. Chapters of 330 to 400vh where one idea is repeated. No rest beats. The only conversion buttons are the nav and the first and last screens |
| Motion language | Everything scrubs linearly with scroll, so everything moves all the time. No hierarchy of motion, no idle life that is separate from scroll, no arrival and settle phases |
| Micro-interactions | Pointer parallax on the camera, a boop, hover lift of 2px on buttons. Cards, chips and rail have no craft |
| Grain | A 200%-viewport fixed layer with `mix-blend-mode: soft-light` (costly on phones) and a static SVG noise tile that never moves |

### 1.4 Why v2 feels AI-made (blunt)

1. The hero is a 149x199 thumbnail enlarged, inside a white 6px arch frame with a drop shadow: a photo in a card. The character is not part of any environment.
2. The section order is the standard 2024 to 2025 template: split hero, outlined-text marquee, scroll-highlight statement, pinned tabs with mock UI, three-cell bento, FAQ accordion, giant footer wordmark. Each piece is fine. The sequence is recognizable from a hundred generated sites.
3. `-webkit-text-stroke` outline marquee of feature names is a 2022 trope, and it lists features instead of creating a feeling.
4. Everything sits on one plane: white cards, 28px radius, the same pink shadow on every surface. No depth hierarchy, no real light.
5. The mock UIs (CSS chat bubbles, bars, a conic-gradient ring) are stock dashboard shapes. The old landing's live typed intake and companion demo were more convincing.
6. The soap bubbles are one pre-drawn 2D sprite, identical color, 15 copies, uniform drift. It reads as clip art, with no refraction, no thin-film color, no wobble.
7. Motion is one generic fade-up used everywhere, plus a tilt on the portrait. Only the word-by-word statement is authored.
8. Color is the safe token palette only: pink on blush, plum finale. No color script, no change of mood.
9. Nothing in the first three seconds is a "moment". Premium pages have one unforgettable beat on load.

### 1.5 One-line diagnosis

Both pages show the character as a picture next to the product. A premium page puts the character inside a lit world, lets the world react to her, and lets the visitor touch it.

---

## 2. The premium direction

### 2.1 Concept: "A day in Bubbles' sky"

The approved painting is a unicorn doctor in a peach sky full of soap bubbles. The whole page is one continuous day in that sky, from dawn to dawn. The light changes with what the chapter means. Soap bubbles are the recurring object: the 28 beads become soap pearls, each record becomes a bubble, the cycle is a ring of bubbles, and Bubbles herself lives inside a larger bubble (the "locket") for chapters 2 to 8, then steps back into full frame at the end.

Honesty rule: she is a portrait, so she does not wave or walk. She acts with light, gaze, breath, bubbles and hearts. The old path choreography (carry hop, memory walk) still works, because the locket floats along the same paths like a bubble drifting.

### 2.2 Hero storyboard (the first five seconds)

Desktop 1440x900:

1. t=0, server HTML: dawn sky as CSS gradient (OKLab), headline left in the display serif, the portrait poster bleeding off the right edge and fading into haze at the bottom (no frame, no arch, no border). CTA and "See how it works".
2. t about 0.9 to 1.4s: world chunk loaded after idle, textures decoded off the main thread, poster cross-fades to the canvas. Frame 0 of the canvas is baked into the poster, so nothing pops.
3. First visible motion: three layers of soap bubbles rise (back layer blurred, middle sharp, front large and refractive), each at a different speed.
4. t about 1.6s: first blink, mane catches a breath of wind, a golden glint travels up the horn, the speech bubble says the time-of-day greeting already in `story/SpeechBubble.tsx`.
5. Idle forever: breathing (4.2 s cycle, 0.6 percent scale), blink every 3 to 6 s (12 percent double blink), mane flow, god rays rotating about 0.3 degrees per second, a bubble popping now and then. Pointer moves the head by up to 8 degrees of parallax and the eye sparkle follows. Hovering the main CTA raises `story.excite` (already exists), which swells the horn glow and the bubbles.
6. Scroll cue: a small bubble with a chevron at bottom center, label "Scroll".

Mobile 390x844: portrait fills the top 56 percent and bleeds off both sides, headline over a soft peach haze in the lower 40 percent, CTA in thumb reach. Poster is a pre-encoded AVIF of 640 px. After the first scroll, a sticky "Start with Bubbles" pill appears and stays until the final chapter.

The wake-up sequence plays once per session (`sessionStorage`), is skipped for reduced motion, and never delays text (text and poster are already visible).

### 2.3 Color script per chapter (starting values, tuned by eye in step 4, contrast-tested in step 1)

Time of day is the storytelling device. Cold clinical noon says "a number alone". Warm golden hour says "tell it like to a friend". Phase colors say "your rhythm". Night says "memory". The horn is the lamp for the companion. Pearl first light says "careful and calm".

| Chapter | Tone | Time and place | Sky top / mid / horizon | Key light and accents | Grade |
|---|---|---|---|---|---|
| enter | light | Dawn | `#E6D3FF` / `#FFC9E3` / `#FFD9B5` | warm key `#FFF2DC` from upper left, rim `#FFB6D5`, sun `#FFF0D2` | warm, lifted blacks, bloom 0.35 |
| body | dark | Inside the bubble, luminous deep aqua and indigo | `#13294B` / `#2A3E86` / `#6E5BC9` | aqua core glow `#66E0E6`, nerves `#FF8CC2` | cool, saturation +8, bloom 0.5 |
| noise (Numbers) | light | Clinical noon | `#D6E8FF` / `#EEF5FF` / `#FFFFFF` | neutral white key, hard shadows | desaturated -15, contrast +8, bloom 0.15 |
| track | light | Golden hour | `#FFD9A8` / `#FFB7A0` / `#FF9DB8` | key `#FFE0B0`, long soft shadows | warm, saturation +10, bloom 0.45 |
| cycle | dark | Phase dusk: base `#2B1038` / `#5A2058` / `#B8467A`, then mix 45 percent of the phase color (`PHASE_COLORS`: period `#E8336F`, follicular `#FF8A7A`, ovulation `#FFC37A`, luteal `#B49BFF`) into mid and horizon as the example day scrubs | phase tint on key | rose to coral to apricot to lilac, bloom 0.5 |
| connect | dark | Twilight with stars | `#12123A` / `#2B2A78` / `#9A5BB5` | star `#FFE9F6`, thread glow | cool, bloom 0.6 |
| remember | dark | Night, moon, fireflies (full tier) | `#0A0A22` / `#1D1A4D` / `#5B3A78` | moon `#FFF1DE` | deep, vignette 0.14 |
| companion | dark | Warm night, the horn is the lamp | `#170C2B` / `#3A1A4A` / `#A04574` | horn gold `#FFD98A`, volumetric cone | warm, bloom 0.9 (the one big bloom) |
| care | light | First light, pearl mist | `#F1E6F8` / `#FAEFF4` / `#FFF4EA` | soft low-contrast key | high key, bloom 0.2, lowest motion |
| start | light | Sunrise, full painting returns | `#F4C9E2` / `#FFD0C0` / `#FFE6B5` | sun `#FFF3D6`, bubbles rise again | warm, bloom 0.4 |

Rules:
- Gradients are mixed in OKLab (CSS `linear-gradient(in oklab, ...)`, GLSL oklab helper). No sRGB mixing, which is what made the old transitions muddy.
- Text colors stay the existing ink (`#2B1A3F`) on light tones and blush (`#FFF6FA`) on dark tones. Each chapter ships a `--scrim` (radial, 25 to 40 percent) behind copy where the sky is busy.
- `atmosphere/palette.test.ts` samples each gradient at five heights inside the copy zone (12 to 78 percent of the height) and asserts WCAG contrast of at least 4.5 for body text and 3 for large text. The cycle horizon (`#E8567F` family) fails with light text, so copy there must stay above the 78 percent line or use the scrim. The test is what enforces this.
- The app stays light-only. The night chapters are scene lighting on a marketing page, not a theme switch. No `prefers-color-scheme` branching. Also honor `prefers-contrast`, `prefers-reduced-transparency` and `forced-colors`.

### 2.4 Lighting and materials rules

- One key light direction for the whole page (upper left, matching the painting), changing color and strength per chapter. A rim light on the opposite side takes the horizon color of the current sky.
- No `RoomEnvironment`. `world/Studio.tsx` builds its environment from the current sky: a small gradient dome built from the palette goes through `PMREMGenerator` (1 ms class cost), regenerated at most 4 times a second during chapter blends only. Beads, pearls and bubbles reflect the actual sky, so materials belong to the world.
- Beads: `MeshPhysicalMaterial` with built-in `iridescence` (IOR about 1.33, thickness range about 180 to 520), clearcoat, low roughness, no transmission (no extra scene pass). Vertebrae stay pearl with sheen. Bones become bubbles once they leave the body (the old code comment "bones become data" becomes "bones become bubbles").
- Hero bubbles (the big, near ones): custom thin-film shader (section 2.6).
- Portrait: relit from the depth map (normals from the depth gradient, wrap light, rim), always subtle (plus or minus 15 percent of the painted values) so the art stays the art. `toneMapped: false` on portrait and sky materials so the painted pastels are not shifted by `NeutralToneMapping` (set in `world/WorldCanvas.tsx`). Texture color spaces: color `SRGBColorSpace`, depth and mask `NoColorSpace`.

### 2.5 The living figure now, and the slot for the real .glb later

Technique: a depth-extruded relief of the painting, rendered in the real scene.

- Assets (made once by `scripts/portrait/`, committed): color RGBA (cut-out, colors dilated 16 px beyond the alpha so stretched edges carry plausible color), depth (8-bit, 0 far to 1 near, smoothed), packed mask (R mane, G horn, B eye region, A stethoscope piece), `manifest.json` with uv anchors (eye centers, horn base and tip, chest anchor, mane root, stethoscope piece) and a `quality` flag (`placeholder` or `final`).
- Geometry: a grid plane (96x128 in full, 48x64 in lite) whose vertices are displaced by the depth texture in the vertex shader. It is real geometry, so the existing camera rig, the scroll orbit (plus or minus 8 degrees, clamped) and the soap bubbles passing between horn and mane all get correct occlusion. Depth is smoothed at build time and displacement is clamped to avoid edge stretching.
- Fragment effects, one shader (`figure/portrait.glsl.ts`):
  - breathing: scale about the chest anchor by up to 0.6 percent, masked to near depth;
  - mane: curl-noise flow in the mane mask, amplitude growing with distance from the mane root, driven by wind from scroll velocity (reuse the wind spring from `story/BubblesHost.tsx`, moved to `figure/expression.ts` and unit-tested);
  - blink: vertical squash of the eye region mask plus a lid color sampled from the brow plus a darker lash line. Ship gate: it must pass a look test by the founder. If it looks cheap it is turned off (`FEATURES.blink = false`) and Option B below is raised;
  - horn: gold glint sweep every 6 to 9 s plus emissive scaled by a `glow` uniform (`story.excite`, companion "thinking");
  - relight and rim from depth normals; fake bloom by adding a high-mip sample of the color texture where luminance exceeds 0.8 (zero extra passes);
  - dither on output.
- Interaction: eye sparkle and head parallax follow the pointer. On touch, a slow Lissajous idle sway replaces it (no device-orientation permission prompt). A real `<button aria-label="Say hi to Bubbles">` over the figure triggers the existing boop and speech events.
- Chapters 2 to 8: the same mesh renders through a circular soft mask (`uCircle`) as the locket, with a rim-only bubble shell in front. The dive and bloom portal origins read `story.bubbles.anchor` instead of the hard-coded `63% 50%`.
- Pose names (`PoseName` in `world/rig.ts`) map to expression presets, not skeleton poses: `idle`, `think` (slower breath, gaze up, dots bubble), `surprised` (gasp ring of tiny bubbles), `cheer` (hearts and glow), `present`, `pointA`, `pointB` (gaze direction and a small turn).

Honest limits of the relief: it holds up to about 8 degrees of orbit. Painted depth from a model is imperfect, so a human reviews and corrects it in the dev viewer. Real 3D comes only with the .glb.

Option B (artist-led, if the shader blink or mane fails the look test): a layered file from an artist (head, eyes open and closed, eyelids, ears, three mane locks, tail, stethoscope, with the hidden areas painted in), animated as separate relief planes with a small spring chain for the mane. About 2 to 4 artist days. More convincing than any shader hack and still cheap at runtime.

The GLB slot contract (defined in step 3, implemented in step 14, never shipped as a stub):

```ts
// figure/handle.ts
export type FigureFrame = {
  pos: THREE.Vector3; scale: number; yaw: number;
  look: { x: number; y: number }; pose: PoseName;
  glow: number; wind: number; dt: number; time: number;
  tier: "lite" | "full"; mode: "full" | "locket";
};
export interface FigureHandle { update(f: FigureFrame): void; anchor: THREE.Vector3; horn: THREE.Vector3 }
```

`figure/FigureSlot.tsx` renders the figure that exists. Step 14 adds `figure/Glb.tsx` and the second branch. The rig, the host events and the portals only talk to `FigureHandle`.

GLB brief for the artist or image-to-3D pipeline (step 14): glTF 2.0, Y up, meters, about 1.2 m tall, facing +Z, A-pose. Meshopt compression and WebP textures (KTX2 only if VRAM becomes an issue). Budget: 15k triangles and 2.5 MB for full, 8k triangles and 700 KB for lite (1024 px textures), at most 4 materials and 40 bones. Mane and tail as 6+ bone chains or baked loops. Morph targets: `blinkL`, `blinkR`, `smile`, `mouthOpen`, `browUp`. Clips named after `PoseName`. Horn emissive map, eyes as separate glossy meshes (clearcoat), pearl coat with sheen. Image-to-3D output (Meshy, Tripo, Rodin, Hunyuan3D and similar) normally needs retopology and rigging by a person, so budget artist time. `useGLTF.setDecoderPath("/draco/")` and local meshopt decoder so nothing loads from a third-party CDN.

### 2.6 Atmosphere: real air, not a void

Layers, back to front:

1. Sky (shader, `atmosphere/Sky.tsx`): 3-stop gradient mixed in OKLab, sun disc and glow, analytic god rays (angular noise, falloff with distance from the sun, slow rotation), dithering to kill banding.
2. Clouds: two domain-warped fbm layers (3 octaves) at different parallax speeds with a fake silver lining (offset sample toward the key light). Rendered into a half-resolution target in full tier. In lite tier the sky is a baked plate (below).
3. Far bokeh: instanced additive discs (about 40 full, 8 lite), sized and blurred by depth, drifting slowly. At night chapters they become warm fireflies (replaces the uniform dots in `world/Motes.tsx`).
4. Portrait and spine (the scene).
5. Soap bubbles: thin-film shader (`bubbles/soap.glsl.ts`). Fresnel alpha, thickness from slow noise that drains toward the bottom (bands where real films show them), cosine-palette interference color, two soft window highlights, vertex wobble. Full tier: refraction by sampling a half-resolution copy of the scene (sky and portrait rendered once to a target, bubbles read it with a normal-based offset: one extra pass total, not one per bubble, unlike `MeshTransmissionMaterial`). Lite tier: no copy, refraction samples the baked sky plate by screen UV.
6. Light: god-ray overlay, horn cone, one anamorphic streak on the hero sun (full only).
7. Post (full only): bloom, grade, edge chromatic aberration (0.5 px), vignette, dither.
8. DOM grain: a pre-rendered 256 px tile at 4 percent opacity moving in 4 steps at 8 fps, replacing the 200%-viewport blend-mode layer. Static on reduced motion. No `mix-blend-mode` on phones.

Static and lite fallback: `scripts/bake-sky.mjs` (Playwright, already installed) renders each chapter palette from a dev page to `frontend/public/brand/sky/<chapter>-{720,1440}.webp` (targets 45 KB and 90 KB). `atmosphere/StaticSky.tsx` is a server component: CSS gradient in OKLab plus the baked plate for the chapter. The same plates are the poster backgrounds, the Open Graph image source and the reduced-motion look.

Depth of field without an extra pass: background layers sample their texture with a mip bias driven by `abs(layerDepth - focus)`; bubbles blur by the same rule.

### 2.7 Chapter staging

| Chapter | New length (old) | Figure | Signature moment | Motion budget (max two systems at once) |
|---|---|---|---|---|
| enter | 140vh (170) | Full painting, large, right | Wake-up, bubbles rise, then the camera pushes into the biggest bubble (dive portal from the bubble) | idle life + bubbles |
| body | 200vh (280) | Locket, low left, gaze follows the growing nerve | 28 pearls stand as a spine, nerves grow as light threads to six labels with a soft pulse along each | nerves + camera |
| noise | 140vh (210) | Locket low center, surprised then thinking | Numbers as crisp chips at different depths with bokeh blur on the far ones. Cold noon, then the page warms at the end | chips |
| track | 190vh (240) | Locket left, looks at the field then the records | Typed message becomes three records, each lifts off as a bubble, then the locket and records float in an arc to the cycle ring (the old carry hop) | typing + hop |
| cycle | 300vh (400) | Locket on the top of the ring (`mode: "ring"`) | Ring of 28 phase-tinted soap pearls; the sky itself passes through the four phase colors as the example day advances; honest "Example cycle" label; history rings | ring + sky |
| connect | 160vh (260) | Locket low center, gaze follows the hovered signal | Beads become stars, signals link with fine light threads (existing `ConnectWeb`) | threads |
| remember | 230vh (330) | Locket floats along the road (same `walkPoint` path) | Four zoom levels (today, week, season, story); a river of bubbles as the timeline under the moon | path + zoom |
| companion | 230vh (300) | Locket larger, the horn is the lamp | Streams of safety check, memory, logs and sources end at the horn; the horn glows; bloom is strongest here; then light blooms out of the horn into pearl (existing bloom portal, now from the real horn position) | streams + bloom |
| care | 160vh (250) | Small locket | Five statements as frosted glass cards on pearl mist. Lowest motion on the page: trust is calm | cards only |
| start | 140vh (180) | Full painting returns, centered | Sunrise, bubbles rise, bubbles burst softly from the CTA on hover | idle + CTA |

Total about 1890vh on desktop. Mobile length multiplier 0.8 (about 1510vh). Every chapter has an arrive (0 to 0.15), do (0.15 to 0.85) and settle (0.85 to 1) phase so there are rest beats.

### 2.8 Motion language

- Three verbs: float (6 to 9 s sine, bubbles), breathe (4.2 s, figure), bloom (light expands from the horn).
- One entrance curve `cubic-bezier(0.16, 1, 0.3, 1)`; interactions use spring easing (CSS `linear()` easing or Motion springs, stiffness about 120, damping about 18); bounce only for a bubble pop.
- Timing: micro 160 ms, element 600 to 900 ms, chapter hand-over 1.2 s, word stagger 40 ms capped at 0.8 s total.
- Idle life is separate from scroll: scroll scrubs the story, idle life runs on its own clock. Never two focal motions at once.
- No scroll hijack: native scroll, the director only reads and damps it.

### 2.9 Type and copy

Option A (recommended): Fraunces (variable, axes `opsz` and `SOFT`, weight 500 to 600) for headlines with an italic for the one emphasized phrase; Nunito for body and data (`font-variant-numeric: tabular-nums` replaces the mono labels); Fredoka only for the wordmark, buttons and chips. One new family; both existing ones are already loaded. Fonts through `next/font` with size-adjusted fallbacks. Budget 100 KB total. Fall back to option B if the italic costs too much: use color emphasis instead.

Copy rules: no em-dashes, no fake testimonials, user counts, press logos or invented statistics. Everything illustrative stays labelled "Example". Keep the existing chapter copy, which is already honest and in character. Proposed additions:

- Hero H1 (keep): "Your body keeps a story. Bubbles remembers it."
- Hero sub (keep): "A health companion that listens, remembers and connects your sleep, mood, cycle and symptoms over time."
- Buttons: "Start with Bubbles", "See how it works".
- Scroll cue: "Scroll to follow the story".
- Pause control: "Pause motion" and "Play motion".
- Portrait alt text: "Bubbles, a white unicorn doctor with a pastel mane, a golden horn, a nurse cap and a stethoscope".
- Boop lines (add to existing): "Tell me how today feels." and "I only keep what you confirm."
- Footer note (keep): "Bubbles is a wellness companion, not a medical device, and does not diagnose. In an emergency, contact your local emergency number."

### 2.10 Techniques for 2026: what we adopt, what we refuse

| Technique | Why | Cost (estimates, measure in step 10) | Mobile fallback |
|---|---|---|---|
| Depth-extruded relief mesh plus shader (hero figure) | Gives a real, moving, lit figure from the approved art, with true occlusion against bubbles | About 6 KB code, 4 textures about 350 KB, under 1.5 ms GPU | Grid 48x64, one quad-class cost, no relight samples beyond 2 |
| Shader sky: OKLab gradient, analytic god rays, 2 cloud layers, dithering | Realistic atmosphere that follows the color script | Full: under 1.2 ms at half resolution | Baked WebP plate per chapter plus CSS OKLab gradient; no per-frame cloud shader |
| Thin-film soap bubbles with refraction | The brand object, finally real. Reads as high budget instantly | Under 1.5 ms for 12 bubbles with one shared scene copy | 6 bubbles, refraction samples the baked sky plate, no scene copy |
| Sky-derived PMREM environment | Materials reflect the actual sky; removes the stock studio look | About 1 ms, 4 Hz during blends only | Same, at lower PMREM size |
| Post stack: bloom, grade, edge chromatic aberration, vignette, dither (three `examples/jsm`, no new dependency) | Cinematic finish, one coherent grade across chapters | 1.5 to 2.5 ms integrated GPU | Off. In-shader fake bloom and CSS grain only |
| Mip-bias depth of field and in-shader bloom | DOF and glow without extra passes | About 0 | Same |
| CSS scroll-driven animations (`animation-timeline: view()`) for DOM reveals | Runs on the compositor, zero JS, never janks | 0 JS | Works at last check in Chromium and Safari 26; Firefox was behind a flag, so `@supports` guard plus the director's `data-on` hook as fallback |
| View transitions (landing to login to dashboard, mascot mark shared element) | Route changes feel like one product | CSS only | Chromium and Safari 18.2+ for cross-document; Firefox gets an instant swap. For App Router client navigation check the Next 15.5 docs for the `viewTransition` option before using; skip if absent |
| Motion (installed) for UI springs, gestures and DOM-only scroll hooks | Already in the project | 0 extra | Reduced-motion branch already used in v2 |
| GSAP | Refused. ScrollDirector plus CSS plus Motion cover everything; about 70 KB for no new capability | n/a | n/a |
| Lenis | Refused on the landing. `ScrollDirector` already damps scroll; a second smoothing layer makes scrubbing mushy and breaks fixed-layer measurement. Remove it from the landing | Saves about 5 KB | n/a |
| Text split reveals (words rise inside a masked line, transform and opacity only, no blur) | Editorial feel at no cost | Server-rendered spans, CSS only | Instant text on reduced motion; `aria-label` on the heading, `aria-hidden` on the spans |
| Magnetic CTAs (max 8 px pull, `hover: hover` only, hit box unchanged) | Tactile premium cue | About 25 lines | Not mounted on touch or reduced motion |
| Custom cursor | Refused as a replacement (accessibility). Optional later: a 24 px bubble ring that trails the real cursor, `pointer: fine` only, never hides the system cursor, hides on keyboard focus and reduced motion | About 0.3 ms/frame | Not rendered |
| Audio | Off by default, one nav toggle (remembered): a soft pop tick and one chime, under 10 KB each, WebAudio after a gesture. No music, no audio-reactive visuals | Tiny | Same |
| Haptics | `navigator.vibrate(8)` on bubble pop and CTA press, Android Chrome only, feature-detected, off on reduced motion; iOS gets none | Tiny | n/a |
| Variable-font micro-animation (Fraunces `SOFT` axis on hover and on heading arrival) | Typographic craft with CSS only | 0 | Static weight |
| CSS `linear()` spring easing, `@starting-style`, registered `@property` colors | Spring physics and animatable sky gradients without JS | 0 | Standard easing fallback |
| Speculation rules for `/login?mode=signup` (prefetch on first scroll, prerender on CTA hover) | Sign-up feels instant | A few lines of JSON | Chromium only; others ignore it |
| `ImageBitmapLoader` texture decode, AVIF and WebP, `fetchpriority="high"`, explicit width and height | Keeps decode off the main thread, protects LCP and CLS | 0 | Same |
| Time-of-day sky from the visitor's clock (4 palette variants, grade shift only after load) | "Her sky follows your clock": a small delight, no tracking | Palette table | Static morning poster stays |
| Visible Pause motion control (WCAG 2.2.2: moving content over 5 seconds needs a pause) | Compliance and kindness | Small | Always shown |
| WebGPU and TSL | Deferred. No feature we need requires it; larger bundle and renderer init complexity. Revisit with the .glb | n/a | n/a |
| OffscreenCanvas worker | Refused. Main thread is light; complexity not justified | n/a | n/a |
| Spline, Rive, Lottie, video backgrounds | Refused. Black-box runtimes or extra bytes with less control than what we already have | n/a | n/a |

### 2.11 Beyond the founder's list

1. Time-of-day sky that matches the visitor (above).
2. A "soap bubble game" in the hero: bubbles contain signal words (sleep, mood, water, cycle). Pop one and a small labelled "Example" chip appears. It teaches the product by play, with no fake numbers.
3. The locket idea: Bubbles inside a bubble, with the dive and bloom portals starting from it.
4. A heartbeat touch: the stethoscope hotspot gives a soft light pulse on tap (sound only if the visitor turned sound on). It fits the product line "listens".
5. Rail ticks become tiny bubbles that fill as chapters pass; the sticky mobile CTA; a soap-film sheen sweep on the primary button.
6. Light-aware text scrims so every chapter stays legible.
7. In-character 404 and error pages that reuse the same sky.
8. One Bubbles across site and app (step 12), plus favicon, apple icon and Open Graph image from the same art.

### 2.12 What we will not do

No analytics added. No third-party CDN for textures or decoders. No fake counts or reviews. No stock photos. No scroll hijack. No cursor replacement. No autoplay audio. No more than two focal motions on screen. No parallax on every layer. No 3D text. No importing `@react-three/drei` from the package root inside the landing chunk (it can pull in large dependencies); use deep imports, or write the few helpers ourselves (a 30-line frame monitor).

---

## 3. Mobile and performance budget

### 3.1 Targets

| Metric | Target | How we hit it |
|---|---|---|
| LCP (Lighthouse mobile, simulated slow 4G, Moto G class) | 2.5 s maximum, aim 1.9 s | Pre-encoded AVIF poster of 640 px (70 KB maximum) is the LCP element, preloaded with `fetchpriority="high"`; text and CTA server-rendered; fonts `swap` with size-adjusted fallback; no JS needed to paint the hero |
| CLS | 0.05 maximum | Explicit width and height on the poster, fixed hero box, font fallback metrics |
| TBT | 200 ms maximum | World chunk loads after `requestIdleCallback`; textures decode through `ImageBitmapLoader` |
| INP | 200 ms maximum | One rAF loop, no layout reads per frame outside the existing pattern |
| Frame rate | 60 fps median on a mid phone (Snapdragon 6 series class, 6 GB), 55 fps floor during scroll | Lite tier, DPR cap 1.5, baked sky, 6 bubbles |
| First-view transfer on mobile | 350 KB maximum before the first scroll | Poster 70 KB, CSS and JS route chunk, fonts 100 KB, textures lazy |
| Whole page transfer | 1.2 MB maximum | Only the current and next sky plate in memory |
| Route JS (excluding the lazy world chunk) | 110 KB gzip maximum | Server components for all static copy, split reveals and sections |
| World chunk (three, R3F, our code) | 300 KB gzip maximum | Deep imports, no drei root import, no postprocessing library |
| Textures on mobile | 1024 px color 160 KB, depth 512 px 40 KB, masks 30 KB; GPU memory under 48 MB | Mip-mapped, disposed on unmount |
| Draw calls and triangles (lite) | 40 and 60k | Instanced beads and bubbles, grid 48x64 |
| Per-frame JS | 4 ms maximum | No per-frame allocation; verified with a heap capture over 2 minutes |
| Per-frame GPU (lite) | 8 ms on the mid phone | One textured relief, instanced bubbles, no full-screen shader |

### 3.2 Tier ladder (automatic, measured, never guessed from one signal)

| Tier | When | What renders |
|---|---|---|
| static | `prefers-reduced-motion`, no WebGL2, Save-Data, user pressed Pause motion, WebGL context lost, JS off | Poster, CSS sky plates, calm scrolling document with the same copy and CTAs, instant reveals |
| lite | Phones, integrated GPUs, or desktop that fails the start-up measurement | Relief grid 48x64, baked sky plates cross-faded, 6 bubbles (no scene copy), 80 fireflies at night, no composer, DPR 1.5 at most, 30 fps idle throttle |
| full | Desktop that measures 12 ms p95 or better over the first 60 frames | Relief 96x128, live sky target, 12 bubbles with refraction, bokeh 40, composer, DPR 1.75 at most |

Rules: start in lite and promote to full on desktop only after the first 60 frames pass; never promote mobile. Demote one tier when p95 frame time is above 24 ms over 90 frames; remember the demotion in `sessionStorage` (`bubbles-tier`) so it does not thrash. The old `WorldMount` rule that turns 3D fully off for 4 or fewer cores becomes lite instead of static, because many capable phones report few cores. `perf/tier.ts` holds a pure `pickInitialTier(env)` and a `FrameMonitor` ring buffer, both unit-tested.

### 3.3 Battery, thermals, lifecycle

- Idle throttle: after 2 s with no scroll or pointer input, lite renders at 30 fps (`frameloop="never"` with a manual `advance()`), and resumes on input.
- Pause rendering when the tab is hidden and when the canvas is off screen (`IntersectionObserver`, `visibilitychange`).
- Handle `webglcontextlost`: drop to static without a crash.
- DPR ladder 1.75, 1.5, 1.25 driven by the same frame monitor.
- Dispose textures, geometries and render targets on unmount (the old code already does this well; keep the pattern).

### 3.4 Delivery details

- `frontend/next.config.ts`: add `headers()` so `/brand/portrait/*`, `/brand/sky/*` and `/brand/fx/*` are `public, max-age=31536000, immutable` (content-hashed file names). Do not rely on the default `max-age=0` for static textures.
- The poster is a pre-encoded `<picture>` with AVIF and WebP sources at 640, 1024 and 1600 px, not a runtime-optimized `next/image`. That keeps exact bytes, avoids image-optimization quota use, and allows `ReactDOM.preload` with `imageSrcSet`.
- Poster equals baked frame 0. A script renders the real scene at the desktop and mobile hero crops and writes the poster files, so the cross-fade to the canvas cannot flash.

### 3.5 Measurement protocol (each result goes in the PLAN.md log)

Lighthouse mobile on the production build (`npx lighthouse`, no dependency added); Chrome performance trace at 4x CPU throttle during a full scroll (no long task above 50 ms); a real mid-range Android and an iPhone SE class device for frame rate; heap capture for 2 minutes; axe at 390, 768 and 1440 widths; reduced-motion and JS-off screenshots.

### 3.6 Quality bar, the "does it look expensive" checks

Freeze-frame test (pause at 10 random scroll positions: none may look like a template); squint test (the focal point reads at 10 percent size); 5-second hero test with three people; blind A/B against v2; sound-off test; 200 percent zoom reflow; 4x CPU throttle; and a banding check on a 1920x1080 gradient with dithering toggled in the dev page.

---

## 4. Implementation plan (13 steps, then a later GLB step)

Concurrency is at most two workers per wave, with disjoint file ownership. Gates for every step: `npx tsc --noEmit`, `npm run lint`, `npx vitest run`, `npm run build` (in `frontend/`), and the step's own checks. Backend is untouched, so pytest is not required for this work. New dependencies: none (check `git diff frontend/package.json` stays empty).

Founder review checkpoints: after step 4 (stills and short screen capture of the living portrait and sky), after step 5 (hero on a Vercel preview of the branch), after step 8 (the full story), before step 13.

| Wave | Steps |
|---|---|
| A | 1 and 2 in parallel |
| B | 3 and 4 in parallel |
| C | 5 alone |
| D | 6 and 7 in parallel |
| E | 8 and 9 in parallel |
| F | 10 and 11 in parallel |
| G | 12 alone |
| H | 13 alone (merge) |
| Later | 14 when the .glb exists |

### Step 1: Foundation (EXP or ENG, 1 chunk). Wave A, parallel with 2.

Owns: `atmosphere/palette.ts` (typed `COLOR_SCRIPT`, section 2.3, plus the 4 time-of-day variants for enter), `atmosphere/palette.test.ts`, `perf/tier.ts`, `perf/tier.test.ts`, `story/store.ts` (retimed `CHAPTERS` lengths, `tier`, `paused` fields), `story/story-state.test.ts`, removal of Lenis use from the landing.
Acceptance: palette contrast tests pass (4.5 body, 3 large) for all chapters; tier tests cover Save-Data to static, mobile never promoted, demotion after 90 frames above 24 ms; total length about 1890vh with a 0.8 mobile factor; no visual change yet; no dependency change; gates green.

### Step 2: Portrait asset pipeline and dev viewer (ENG, 2 chunks; final assets blocked by D2). Wave A, parallel with 1.

Owns: `scripts/portrait/make_layers.py` (dev-time tool, outputs committed), `frontend/public/brand/portrait/*` (color AVIF and WebP at 1600, 1024 and 640, depth, mask, posters), `figure/manifest.ts` (typed, with uv anchors and `quality`), `frontend/app/dev/portrait/page.tsx` (calls `notFound()` in production).
Tooling notes: background removal with rembg (MIT) using a BiRefNet-class model; depth with Depth Anything V2 Small (Apache-2.0; at last check only the Small checkpoint has that license, the larger ones are non-commercial, so verify before use); mane mask by hue and saturation segmentation inside the alpha; horn mask by gold hue; eye region and stethoscope piece placed by hand from measured uv coordinates. The Canva tools `remove-background` and `separate-image-layers` available to the agents are an alternative path; their output quality is unverified.
Acceptance: no peach or pink halo at 200 percent zoom over `#170A14`, `#FFFFFF` and `#B49BFF`; viewer shows color, depth, mask channels and an orbit slider with no tearing at 6 degrees; file sizes within section 3.1 (color AVIF at 1600 px 260 KB maximum, 1024 px 160 KB, depth 70 KB, mask 50 KB, mobile poster 70 KB); until the real art exists, the pipeline runs on the placeholder and writes `quality: "placeholder"`, and step 13's gate refuses to merge while it says that.

### Step 3: The living portrait (EXP, 2 chunks). Wave B, parallel with 4.

Owns: `figure/Portrait.tsx`, `figure/portrait.glsl.ts`, `figure/expression.ts`, `figure/expression.test.ts`, `figure/handle.ts`, `figure/usePortraitTextures.ts`, `figure/FigureSlot.tsx` (portrait only, no unimplemented branch).
Acceptance: behaviors in section 2.5 all present and tunable by uniforms; `expression.test.ts` is deterministic (seeded RNG: blink spacing 3 to 6 s, 12 percent double blinks, wind spring settles); no per-frame allocation (heap capture flat over 60 s); reduced motion renders one still frame with no loop; grid 96x128 full and 48x64 lite; founder look test on blink and mane, and if either fails the feature flag is off and Option B is raised.

### Step 4: Sky and atmosphere (EXP, 2 chunks). Wave B, parallel with 3.

Owns: `atmosphere/Sky.tsx`, `atmosphere/sky.glsl.ts`, `atmosphere/skyEnv.ts` (PMREM from the palette), `atmosphere/Bokeh.tsx`, `atmosphere/StaticSky.tsx`, `frontend/public/brand/fx/grain.webp`, `scripts/bake-sky.mjs`, `frontend/app/dev/sky/page.tsx` (production 404), `frontend/public/brand/sky/*`.
Acceptance: any (chapter A, chapter B, blend t) renders correct palette in OKLab; god rays and two cloud layers; dither toggle shows no banding on a 1920x1080 gradient with it on; baked plates within 45 KB (720) and 90 KB (1440); `StaticSky` and the shader match at three chapters side by side; full-tier sky pass 1.2 ms or less on an integrated GPU; grain is a tile with stepped motion and no blend mode on phones.

### Step 5: Integration, hero and LCP (EXP and ENG, 2 chunks). Wave C, alone (hot files).

Owns: `Landing.tsx` (split into `chapters/Enter.tsx`, `Body.tsx`, `Noise.tsx`, `Track.tsx`, `Cycle.tsx`, `Connect.tsx`, `Remember.tsx`, `Companion.tsx`, `Care.tsx`, `Start.tsx`; copy and DOM unchanged apart from hero and finale), `landing.css`, empty `type.css` and `ui.css` with their imports (so step 7 never edits `Landing.tsx`), `figure/PosterHero.tsx`, `world/World.tsx`, `world/WorldCanvas.tsx`, `world/WorldMount.tsx`, `story/ScrollDirector.tsx` (palette to CSS variables and shader uniforms, tier, pause), `story/BubblesHost.tsx` (the SVG host is not mounted in WebGL mode; its boop and say events move to a real `<button>` on the portrait), `story/SpeechBubble.tsx` (anchor), `frontend/next.config.ts` (immutable cache headers).
Acceptance: Lighthouse mobile LCP 2.5 s or better (aim 1.9), CLS 0.05 or better, TBT 200 ms or better, on the production build; poster-to-canvas cross-fade has no visible pop at three viewport sizes; wake sequence once per session; Pause motion control (nav, `aria-pressed`, keyboard operable, freezes the canvas and CSS animation, persisted in `sessionStorage`); calm mode (reduced motion and JS off) shows the poster and static sky with the same copy and CTAs; `Landing.tsx` is a short composition file; gates green.

### Step 6: Soap bubbles, locket, pop (EXP, 2 chunks). Wave D, parallel with 7.

Owns: `bubbles/SoapBubbles.tsx`, `bubbles/soap.glsl.ts`, `bubbles/BubbleLocket.tsx`, `bubbles/pop.ts` (pop, droplets, optional sound and vibrate, off by default), `story/keepOut.ts` (copy-block rectangles measured on resize), and one mount line in `world/World.tsx`.
Acceptance: distinct iridescent bands that shift with view angle, visible refraction in full tier, no scene copy in lite; bubbles never cover the headline or CTAs in the hero at three sizes (keep-out); pop works with mouse and touch and creates no allocation spike; sound is off until the visitor toggles it; 55 fps or better on the mid phone with 6 bubbles.

### Step 7: Type, reveals, UI craft (EXP, 1 chunk). Wave D, parallel with 6.

Owns: `type/fonts.ts`, `type/Split.tsx` (server component), `type.css`, `ui/Magnetic.tsx`, `ui/StickyCta.tsx`, `ui.css`, rail tick styles, chapter copy edits inside `chapters/*.tsx` (copy only), speculation rules for `/login?mode=signup`.
Acceptance: Fraunces plus Nunito and Fredoka loaded with size-adjusted fallback, no CLS from font swap; headline reveal uses transform and opacity only, with `aria-label` on the heading and `aria-hidden` spans; Magnetic never changes the hit box and is not mounted on touch or reduced motion; sticky CTA appears after chapter 2, hides on the last chapter, 44 px target; `@supports` guard for scroll-driven animations with the director as fallback.

### Step 8: Spine, rig and chapter restaging (EXP, 2 chunks). Wave E, parallel with 9.

Owns: `world/Spine.tsx` (iridescent bead material, bones become bubbles), `world/rig.ts` (locket staging, pose to expression presets, dive origin from `story.bubbles.anchor`), `world/geometry.ts`, `world/Studio.tsx` (sky-derived environment, key and rim from the palette), `world/World.tsx`, `world/Motes.tsx` (fireflies at night chapters only), and the visual alignment of `story/ConnectWeb.tsx`, `TravelRoutes.tsx`, `CycleDay.tsx`, `CompanionDemo.tsx`, `TypedIntake.tsx`, `SystemLabels.tsx`.
Acceptance: all ten chapters reviewed at 390, 768 and 1440 widths against the section 2.7 table; the sky passes through four phase colors in the cycle chapter; nerve labels still anchor to nerve tips; carry hop and memory walk still read; `story-state.test.ts` and new rig tests pass; reduced-motion calm mode unchanged.

### Step 9: Post stack and grade (ENG, 1 chunk). Wave E, parallel with 8.

Owns: `post/Composer.tsx` (RenderPass, UnrealBloomPass at half resolution, strength about 0.35, radius about 0.7, threshold about 0.85, OutputPass), `post/GradePass.ts` (lift, gamma, gain per chapter from the palette, vignette 0.12, 0.5 px edge chromatic aberration, dither), and the single mount line in `world/WorldCanvas.tsx`. Full tier only.
Acceptance: at most 2.5 ms added on an integrated GPU; copy never blooms (DOM is untouched); unmounting on demotion causes no visible color jump beyond a small, reviewed shift; no banding.

### Step 10: Performance pass (ENG, 1 chunk). Wave F, parallel with 11.

Owns: `perf/*` wiring, `world/WorldMount.tsx`, `world/World.tsx` (frame monitor, DPR ladder, idle throttle, hidden and off-screen pause, context-lost handling), `bubbles/*` and `atmosphere/Sky.tsx` (counts and target sizes by tier).
Acceptance: the section 3.1 table measured and logged: 55 fps or better median on the mid phone in lite, 60 fps on desktop full, no long task above 50 ms during a full scroll at 4x throttle, flat heap over 2 minutes, demotion triggers and persists; findings fixed.

### Step 11: Accessibility and reduced-motion pass (TEST and EXP, 1 chunk). Wave F, parallel with 10.

Owns: `chapters/*.tsx`, `landing.css`, `type.css`, `ui.css`, `frontend/e2e/landing.spec.ts`, a minimal `frontend/playwright.config.ts`, pinning the Playwright version in `package.json` if the team agrees (it is currently unpinned "latest").
Acceptance: axe via `@axe-core/playwright` at 390, 768 and 1440 widths with zero serious or critical; keyboard path (skip link, nav, CTA, rail, Pause) with visible focus not hidden by fixed UI (WCAG 2.4.11); one h1 and sequential headings; Pause motion satisfies WCAG 2.2.2; 44 px targets; `prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast` and `forced-colors` screenshots reviewed; 200 percent zoom reflow without horizontal scroll.

### Step 12: One Bubbles: mascot, icons, share image (EXP, 1 chunk; needs D2). Wave G, alone.

Owns: `components/BubblesMascot.tsx`, `landing/BubblesMark.tsx` and its test (same props: `size`, `title`, `className`, `style`, so the 18+ call sites do not change), `landing/BubblesHead.tsx`, `frontend/public/brand/mark/bubbles-face-{64,128,256}.{avif,webp}`, `frontend/app/icon.svg` or PNG, `frontend/app/apple-icon.png`, `frontend/app/favicon.ico`, `frontend/app/opengraph-image.png`.
Acceptance: every screen that shows the mascot renders the concept 2 face crop; moods keep their small signs; cute and recognizable at 40 and 64 px; no layout shift; Open Graph preview shows the hero art; the legal note in section 6 has been sent to the founder.

### Step 13: Swap, cleanup, merge (ENG, then NOAH, 1 chunk). Wave H, alone.

Owns: `frontend/app/page.tsx` mounting the new landing, deletion of `landing/v2/` (ideas already harvested) and of any old illustrated figure files with no remaining importer (check with grep before deleting; `BubblesMark` and `BubblesHead` are replaced in step 12), docs updates (`README.md`, `DEPLOY.md`, `docs/autonomy/PLAN.md` log line).
Acceptance (all gates from PLAN.md rule 9): tsc, lint, vitest, build green; `figure/manifest.ts` says `quality: "final"`; claims in D8 resolved; founder looks at the Vercel preview; NOAH accepts; after merge, smoke test live (landing 200, `/login?mode=signup` loads, CORS unchanged, health GET and HEAD). Never print or touch secrets.

### Step 14 (later, when the .glb exists): Real 3D figure (ENG, 2 chunks).

Owns: `figure/Glb.tsx` (second branch of `FigureSlot`, `AnimationMixer` clips named after `PoseName`, morph targets for blink and mood, horn emissive), `frontend/public/models/bubbles.glb` and lite LOD, `frontend/public/draco/` and local meshopt decoder, `world/rig.ts` (full-body staging may replace the locket where it helps).
Acceptance: budgets in section 2.5 met; no third-party decoder requests; 60 fps full and 55 fps lite re-baselined; poster regenerated from the new frame 0; the portrait remains as the lite fallback until the .glb is proven on the mid phone.

---

## 5. Beyond the landing: ten upgrades for the signed-in app

Each is small, safe and honest: nothing diagnoses, nothing is invented, missing data is shown as missing. Effort S = 1 chunk, M = 2 chunks.

| # | Upgrade | What and why it feels premium | Files | Effort | Risk and guardrails |
|---|---|---|---|---|---|
| 1 | Living Today and one shared bead ring (dashboard and cycle) | One glanceable ring of 28 soap pearls: on Today it shows what you logged today (water, sleep, mood) with hollow pearls and the words "not logged yet"; on Cycle it replaces the plain arc with 28 pearls plus an honest estimated range band instead of a single point. Same object as the landing story, so the promise and the product match | new `frontend/components/BeadRing.tsx`; edit `components/cycle/PhaseRing.tsx`, `app/dashboard/dashboard/TodaySections.tsx`; data from existing `today.ts` | M | Low. Never shows zero as healthy; estimates keep the "estimated" wording; pearls fill with a 40 ms stagger, none on reduced motion |
| 2 | AI-native composer | Slash templates (`/sleep`, `/mood`, `/water`, `/period`) insert a sentence stem; numbered source chips `[1]` focus the matching source in the reply; "What Bubbles used" collapses under the reply from the payload; copy-for-my-doctor action | `app/companion/CompanionClient.tsx` (composer block), new `app/companion/Composer.tsx`, `ChatBits.tsx` (`EvidenceRow`) | M | Low. Chips come only from fields the backend returns; no pre-send guesses about context; confirmation flow for memory is unchanged |
| 3 | Command palette: "Ask or jump" (Ctrl or Cmd + K) | Extends the existing native `<dialog>` in `components/AskBubbles.tsx`: type to jump to any of the 29 pages or run a quick action (log water, new conversation, open Today); free text still asks Bubbles. The escape hatch that makes the planned 7-entry navigation safe | `components/AskBubbles.tsx`, export the nav list from `components/Navigation.tsx` | S | Low. Combobox and listbox ARIA; recent items store route ids only, never queries |
| 4 | Soap-pop confirmation and touch feedback | A small bubble-pop on successful save, spring-press easing, optional 8 ms vibration on Android; setting "Touch feedback" | `app/globals.css`, `components/tracking/kit.tsx`, new `lib/feedback.ts`, Settings toggle | S | Low. Pop only after the API confirms the save; never on errors or safety states; off on reduced motion |
| 5 | Privacy veil | When the tab is hidden or the window loses focus, cover the app with a solid blush card ("Hidden. Tap to show."); "Hide numbers" toggle masks metric values until tap-and-hold. Trust made visible for shared phones | new `components/PrivacyVeil.tsx`, `app/globals.css`, Settings | S | Low. Clearly described as privacy cover, not a lock; an overlay card, not a heavy blur filter; announced to screen readers |
| 6 | Weekly recap card | "Your week with Bubbles" as a shareable image drawn locally on a canvas (nothing uploaded): days logged, average sleep on logged nights, water-logged days. Share through the Web Share API, or download | new `app/insights/Recap.tsx`, `lib/recap-canvas.ts`; uses `/insights/weekly` and `today.ts` derivations | M | Medium (privacy). Per-line opt-in, default excludes cycle, symptoms, medicines and labs; preview before sharing; no grades or judgments; missing days read "not logged" |
| 7 | Partner preview | "This is exactly what they will see" panel inside partner sharing, built from the same server summary the partner page uses, plus a clear one-tap stop sharing | `app/partner/PartnerSharingClient.tsx`, new `app/partner/ShareSummaryPreview.tsx` | M | Medium. Verify the partner endpoints in `backend/` first; the preview must call the same function as the partner page so it can never differ from what is served; no backend change in this plan |
| 8 | Calm reminders | Group reminders by kind, mark all read, snooze until tomorrow, show quiet hours if the backend already stores them | `components/wellness/NotificationBell.tsx`, `app/notifications/NotificationsClient.tsx`, `components/wellness/NotificationSettingsCard.tsx` | S | Low. Uses existing endpoints; no new data; no push notifications in this scope |
| 9 | PWA install polish and read-only offline shell | Add 192 and 512 px icons, a maskable icon, `shortcuts` (Log water, Talk to Bubbles) and screenshots to `app/manifest.ts`; an install card in Settings (`beforeinstallprompt`, plain "Add to Home Screen" steps for iOS); a tiny service worker caching only static assets and an offline page | `app/manifest.ts`, new `public/sw.js`, `public/icons/*`, new `components/InstallCard.tsx`, new `app/offline/page.tsx` | M | Medium. Never cache API responses or authenticated HTML; versioned cache with an update path; copy never promises offline logging. Web widgets do not exist, so none are proposed |
| 10 | Hinglish voice to text with review | Mic button in the composer (English India by default, Hindi option) that fills the text box for the person to edit; never auto-sends. Reuse the recognition code already in `app/fitness/calories/CaloriesClient.tsx` | new `lib/useSpeech.ts`, `app/companion/Composer.tsx` | S | Medium (privacy). Browser speech services may process audio off device: show a one-time, plain consent line, default off, remember the choice, hide where unsupported, store no audio. Transcripts can be wrong, so always editable |

Honorable mentions (not in the ten): cycle-phase ambient tint (opt-in only, off by default, because a color on screen reveals phase to anyone nearby); a pattern bubble field for Insights where bubble size means days of data, never importance, with every link labelled "possible link, not a cause"; route view transitions with the mascot as a shared element; in-character empty states and 404.

---

## 6. Risks, honest limits and guardrails

1. The 2.5D relief is not a free 3D model: about 8 degrees of orbit, and painted depth needs human review. Blink and mane may need Option B (artist-layered file, 2 to 4 days).
2. The character is AI-generated. Before launch confirm that the tool's terms allow commercial use, file for trademark on the name and mark, and consider having an artist refine the final mark. This is a legal and brand risk, not a technical one.
3. The original file (D2) is a hard blocker. The 149x199 placeholder can only be used to wire code.
4. Premium on phones depends on discipline: lite tier is the product for most visitors, and full tier is the bonus. Step 10 exists to prove it on real hardware.
5. v2 copy contains two claims that need verification (D8). The live landing must never state a number that `/knowledge/health` or the product does not support.
6. Safety and honesty: no medical claims added; all data in demos stays labelled "Example"; RED safety wording on the page matches `CLAUDE.md` (urgent messages are handled by fixed rules before any AI model).
7. Text legibility on moving skies is enforced by `palette.test.ts` and scrims, not by hope.
8. Playwright and axe packages are unpinned or loosely pinned; pin before relying on CI results.
9. Next version mismatch (CLAUDE.md says 16, installed 15.5.27): confirm any Next-specific feature (view transitions, image formats) against the installed docs first.
10. Scope control: this plan changes the landing, the mascot component, icons and `next.config.ts` headers. It does not touch auth, RLS, the backend, environment secrets, DNS or billing.

---

## 7. Executive summary

1. Diagnosis: the old story has the right bones (one director, one canvas, chapters, portals, honest demos) but a flat SVG mascot, plum voids, stock materials, three font families and 2620vh of pacing; v2 is the generic template sequence with a 149 px thumbnail in a frame.
2. Direction: "A day in Bubbles' sky", one continuous day from dawn to dawn with a ten-chapter color script (cold noon for numbers, golden hour for talking, phase-colored dusk for the cycle, night for memory, horn-lit companion, pearl first light for care).
3. Figure: the approved painting becomes a depth-extruded relief in the real scene (breath, blink, mane wind from scroll speed, horn glint, relight, 8 degrees of orbit), living inside a soap-bubble locket in chapters 2 to 8, with a clean `FigureHandle` slot for the .glb later.
4. Backgrounds: shader sky in OKLab with god rays, two cloud layers, bokeh and dithering, plus baked plates for phones and reduced motion, and a sky-derived environment map so every material reflects the current sky.
5. Bubbles: the 28 beads become iridescent soap pearls, hero bubbles use a thin-film refraction shader, popping them is the playful interaction; sound and vibration are off or optional.
6. Techniques adopted: CSS scroll-driven animation with fallback, OKLab gradients, transform-only split reveals, magnetic CTAs, speculation rules, desktop-only bloom and grade; refused: GSAP, Lenis, WebGPU, custom cursor replacement, Spline.
7. Budget: LCP 2.5 s or better via a pre-encoded AVIF poster equal to baked frame 0, world chunk 300 KB gzip after idle, three tiers (static, lite, full) with measured demotion, 30 fps idle throttle, and a visible Pause motion control.
8. Plan: 13 steps plus a later GLB step in 8 waves, never more than two workers on disjoint files, about 19 chunks, with founder checkpoints after the portrait stills, the hero preview and the full story.
9. Blocker: the full-size original of concept 2 (at least 2048 px) is needed before anything can look premium; the current 149x199 file cannot ship.
10. Also found: the in-app mascot on 18+ screens is still the old SVG drawing (step 12 makes it one Bubbles), `CLAUDE.md` says Next 16 while 15.5.27 is installed, and the shortened story is about 1890vh.
11. Beyond the landing: a shared 28-pearl Today and cycle ring, AI-native composer, Ctrl+K palette, soap-pop feedback, privacy veil, local weekly recap card, partner preview, calm reminders, PWA install and consented voice to text; none diagnose or invent data.
12. Honest limits: 2.5D is not full 3D, blink and mane may need an artist-layered file, two v2 claims need verification, and the AI-made character needs a commercial-use and trademark check.
