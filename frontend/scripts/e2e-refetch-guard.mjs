// Refetch-loop guard: opening a section must settle. A screen that announces "your data changed" on load makes every screen refetch,
// which announces it again (the 2026-10 lag: hundreds of requests a minute and the rate limit answering 429). This counts API
// requests while each section sits idle and fails if any section keeps asking.
//
//   BUBBLES_PREVIEW=1 python backend/preview_server.py                              (API on :8001, token "preview")
//   NEXT_PUBLIC_UI_PREVIEW=1 NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 npx next dev -p 3100
//   node scripts/e2e-refetch-guard.mjs [http://localhost:3100] [--idle=6] [--max=40]
//
// Exit code 0 = every section settled, 1 = a storm (or a 429) was seen.
import { chromium } from "playwright";

const base = process.argv.find((a) => a.startsWith("http")) || "http://localhost:3100";
const arg = (name, fallback) => Number((process.argv.find((a) => a.startsWith(`--${name}=`)) || `=${fallback}`).split("=")[1]);
const idleSeconds = arg("idle", 6);
const maxRequests = arg("max", 40);   // a healthy load makes ~10-15 calls once; a storm makes hundreds
const sections = ["/dashboard", "/health", "/insights", "/care", "/cycle", "/mind", "/fitness", "/community", "/profile"];

const browser = await chromium.launch();
const failures = [];
for (const path of sections) {
  const page = await browser.newPage();
  let api = 0;
  let throttled = 0;
  page.on("response", (res) => {
    if (!res.url().includes(":8001")) return;
    api += 1;
    if (res.status() === 429) throttled += 1;
  });
  await page.goto(base + path, { waitUntil: "networkidle" }).catch(() => {});
  api = 0;   // only what happens AFTER the first load counts: nothing should be asked while idle
  throttled = 0;
  await page.waitForTimeout(idleSeconds * 1000);
  const verdict = api > maxRequests || throttled > 0 ? "FAIL" : "ok";
  console.log(`${verdict.padEnd(4)} ${path.padEnd(12)} ${api} idle requests, ${throttled} x 429`);
  if (verdict === "FAIL") failures.push(path);
  await page.close();
}
await browser.close();
if (failures.length) {
  console.error(`Refetch storm in: ${failures.join(", ")}`);
  process.exit(1);
}
