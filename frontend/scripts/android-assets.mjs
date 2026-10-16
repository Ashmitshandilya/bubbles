// Regenerates the Android launcher icons, adaptive-icon layers and splash artwork from app/icon.svg (the approved
// BubblesMark). The mascot is only re-framed and composited, never redrawn. Android 2.0: the app's own premium badge,
// the head on a deep grape-to-pink gradient with a soft glow, glossy bubbles and a gentle shadow (the website keeps
// app/icon.svg). Run from frontend/:
//   node scripts/android-assets.mjs
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = fileURLToPath(new URL("..", import.meta.url));
const res = `${root}android/app/src/main/res/`;
const source = readFileSync(`${root}app/icon.svg`, "utf8");
const BLUSH = "#FFF6FA";
const DENSITIES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };

// The badge disc (centre 0,-30, r 198). The adaptive foreground drops it so the launcher's own mask and the
// pink background layer take its place; the head keeps its badge clip, which rounds off the neck.
const BADGE = '<circle cx="0" cy="-30" r="198" fill="url(#cm36-badge)"/>';
if (!source.includes(BADGE)) throw new Error("app/icon.svg changed: badge circle not found, update this script");
const headOnly = source.replace(BADGE, "");

// Renders the SVG through a square window centred on (cx, cy), `half` user units each way, at px by px.
function render(svg, cx, cy, half, px) {
  const open = `<svg viewBox="${cx - half} ${cy - half} ${half * 2} ${half * 2}" width="${px}" height="${px}" xmlns="http://www.w3.org/2000/svg">`;
  return sharp(Buffer.from(svg.replace(/<svg [^>]*>/, open))).png();
}

// Centre and radius (user units) of the circle around the visible head, measured from a high-res render.
async function headCircle() {
  const N = 2000;
  const u = 400 / N;
  const { data } = await render(headOnly, 0, -30, 200, N).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const visible = (i, j) => data[(j * N + i) * 4 + 3] > 0;
  let [x0, y0, x1, y1] = [N, N, 0, 0];
  for (let j = 0; j < N; j++) {
    for (let i = 0; i < N; i++) {
      if (visible(i, j)) [x0, y0, x1, y1] = [Math.min(x0, i), Math.min(y0, j), Math.max(x1, i), Math.max(y1, j)];
    }
  }
  const ci = (x0 + x1) / 2;
  const cj = (y0 + y1) / 2;
  let r = 0;
  for (let j = y0; j <= y1; j++) {
    for (let i = x0; i <= x1; i++) if (visible(i, j)) r = Math.max(r, Math.hypot(i - ci, j - cj));
  }
  return { cx: -200 + (ci + 0.5) * u, cy: -230 + (cj + 0.5) * u, r: (r + 1) * u };
}

const head = await headCircle();

// The app badge background (108 x 108 units = the adaptive canvas): grape into pink, a top-left glow, three soap bubbles.
const BACKGROUND = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8E5BFF"/><stop offset="0.55" stop-color="#C2338F"/><stop offset="1" stop-color="#E0306E"/></linearGradient>
    <radialGradient id="glow" cx="0.3" cy="0.22" r="0.6"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.45"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient>
    <radialGradient id="b" cx="0.35" cy="0.3" r="0.7"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.55"/><stop offset="0.6" stop-color="#FFFFFF" stop-opacity="0.08"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0.25"/></radialGradient>
  </defs>
  <rect width="108" height="108" fill="url(#g)"/>
  <rect width="108" height="108" fill="url(#glow)"/>
  <circle cx="86" cy="24" r="9" fill="url(#b)"/>
  <circle cx="20" cy="84" r="6" fill="url(#b)"/>
  <circle cx="92" cy="80" r="4" fill="url(#b)"/>
</svg>`;

const backgroundPng = (px) => sharp(Buffer.from(BACKGROUND)).resize(px, px).png().toBuffer();

// A soft plum shadow under the head, offset down a little, so it lifts off the gradient.
async function withShadow(headPng, px) {
  const { data, info } = await sharp(headPng).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) [data[i], data[i + 1], data[i + 2], data[i + 3]] = [60, 10, 60, Math.round(data[i + 3] * 0.45)];
  const shadow = await sharp(data, { raw: info }).blur(Math.max(0.5, px / 43)).png().toBuffer();
  return sharp({ create: { width: px, height: px, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite([{ input: shadow, top: Math.round(px / 54), left: 0 }, { input: headPng }])
    .png()
    .toBuffer();
}

// The full round badge at px (legacy launchers, the Android 12 splash and the pre-12 splash).
async function badge(px) {
  const headPng = await render(headOnly, head.cx, head.cy, (head.r * 54) / 32, px).toBuffer();
  const mask = Buffer.from(`<svg width="${px}" height="${px}"><circle cx="${px / 2}" cy="${px / 2}" r="${px / 2}" fill="#fff"/></svg>`);
  return sharp(await backgroundPng(px)).composite([{ input: await withShadow(headPng, px) }, { input: mask, blend: "dest-in" }]).png().toBuffer();
}

const transparent = (px) => ({ create: { width: px, height: px, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } });

for (const [density, scale] of Object.entries(DENSITIES)) {
  const mipmap = `${res}mipmap-${density}/`;

  // Legacy icon (API 24-25): the full round badge, 44dp of the 48dp square, transparent corners.
  const inner = Math.round(44 * scale);
  const pad = Math.round((48 * scale - inner) / 2);
  const legacy = await sharp(transparent(48 * scale)).composite([{ input: await badge(inner), top: pad, left: pad }]).png().toBuffer();
  await sharp(legacy).toFile(`${mipmap}ic_launcher.png`);
  await sharp(legacy).toFile(`${mipmap}ic_launcher_round.png`);

  // Adaptive foreground: 108dp canvas, head fitted inside a 64dp circle so it stays within the 66dp safe zone.
  const px = 108 * scale;
  const foreground = await render(headOnly, head.cx, head.cy, (head.r * 54) / 32, px).toBuffer();
  await sharp(await withShadow(foreground, px)).toFile(`${mipmap}ic_launcher_foreground.png`);
  await sharp(await backgroundPng(px)).toFile(`${mipmap}ic_launcher_background.png`);

  // Themed-icon (Android 13) monochrome layer: the same silhouette; the system tints it, only alpha matters.
  const { data, info } = await sharp(foreground).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) data[i] = data[i + 1] = data[i + 2] = 255;
  await sharp(data, { raw: info }).png().toFile(`${mipmap}ic_launcher_monochrome.png`);

  // Android 12+ splash icon: 288dp transparent canvas, badge 64% wide so it sits inside the system's 192dp mask.
  mkdirSync(`${res}drawable-${density}`, { recursive: true });
  const splash = Math.round(288 * scale);
  const disc = Math.round(splash * 0.64);
  const at = Math.round((splash - disc) / 2);
  await sharp(transparent(splash)).composite([{ input: await badge(disc), top: at, left: at }]).png().toFile(`${res}drawable-${density}/splash_icon.png`);
}

// Legacy splash (pre-Android 12 launch theme): every existing splash.png keeps its size, blush fill, badge
// centred at 28% of the shorter side.
for (const dir of readdirSync(res).filter((d) => d.startsWith("drawable"))) {
  const file = `${res}${dir}/splash.png`;
  if (!existsSync(file)) continue;
  const { width, height } = await sharp(file).metadata();
  const size = Math.round(Math.min(width, height) * 0.28);
  const disc = await badge(size);
  await sharp({ create: { width, height, channels: 3, background: BLUSH } })
    .composite([{ input: disc, left: Math.round((width - size) / 2), top: Math.round((height - size) / 2) }])
    .removeAlpha()
    .png()
    .toFile(file);
}

console.log(`Android assets written (head circle ${head.cx.toFixed(1)}, ${head.cy.toFixed(1)}, r ${head.r.toFixed(1)})`);
