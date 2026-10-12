// Regenerates the Android launcher icons, adaptive-icon layers and splash artwork from app/icon.svg (the approved
// BubblesMark). The mascot is only re-framed and composited, never redrawn. Run from frontend/:
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

for (const [density, scale] of Object.entries(DENSITIES)) {
  const mipmap = `${res}mipmap-${density}/`;

  // Legacy icon (API 24-25): the full round badge, 44dp of the 48dp square, transparent corners.
  const legacy = await render(source, 0, -30, (198 * 48) / 44, 48 * scale).toBuffer();
  await sharp(legacy).toFile(`${mipmap}ic_launcher.png`);
  await sharp(legacy).toFile(`${mipmap}ic_launcher_round.png`);

  // Adaptive foreground: 108dp canvas, head fitted inside a 64dp circle so it stays within the 66dp safe zone.
  const px = 108 * scale;
  const foreground = await render(headOnly, head.cx, head.cy, (head.r * 54) / 32, px).toBuffer();
  await sharp(foreground).toFile(`${mipmap}ic_launcher_foreground.png`);

  // Themed-icon (Android 13) monochrome layer: the same silhouette; the system tints it, only alpha matters.
  const { data, info } = await sharp(foreground).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) data[i] = data[i + 1] = data[i + 2] = 255;
  await sharp(data, { raw: info }).png().toFile(`${mipmap}ic_launcher_monochrome.png`);

  // Android 12+ splash icon: 288dp transparent canvas, badge 64% wide so it sits inside the system's 192dp mask.
  mkdirSync(`${res}drawable-${density}`, { recursive: true });
  await render(source, 0, -30, 198 / 0.64, 288 * scale).toFile(`${res}drawable-${density}/splash_icon.png`);
}

// Legacy splash (pre-Android 12 launch theme): every existing splash.png keeps its size, blush fill, badge
// centred at 28% of the shorter side.
for (const dir of readdirSync(res).filter((d) => d.startsWith("drawable"))) {
  const file = `${res}${dir}/splash.png`;
  if (!existsSync(file)) continue;
  const { width, height } = await sharp(file).metadata();
  const size = Math.round(Math.min(width, height) * 0.28);
  const badge = await render(source, 0, -30, 200, size).toBuffer();
  await sharp({ create: { width, height, channels: 3, background: BLUSH } })
    .composite([{ input: badge, left: Math.round((width - size) / 2), top: Math.round((height - size) / 2) }])
    .removeAlpha()
    .png()
    .toFile(file);
}

console.log(`Android assets written (head circle ${head.cx.toFixed(1)}, ${head.cy.toFixed(1)}, r ${head.r.toFixed(1)})`);
