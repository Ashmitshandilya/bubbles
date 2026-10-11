// Landing performance check (docs/autonomy/LANDING_PREMIUM_PLAN.md section 3.5). Run against a production build:
//   npm run build && npx next start -p 3200      (in another terminal)
//   node scripts/landing-perf.mjs http://localhost:3200 [--heap-seconds=120]
// Prints one JSON report per profile (desktop, phone): frame intervals and long tasks during a full scroll at a CPU throttle (default 4x, --throttle=N)
// throttle, world draws per second while idle, heap growth while idle, the tier and the WebGL renderer in use.
// Headless Chromium may render WebGL in software; the report says which, so read the frame numbers with that in mind.
import { chromium, devices } from "playwright";

const url = process.argv[2] || "http://localhost:3200";
const throttle = Number((process.argv.find((a) => a.startsWith("--throttle=")) || "=4").split("=")[1]);
const heapSeconds = Number((process.argv.find((a) => a.startsWith("--heap-seconds=")) || "=120").split("=")[1]);

// Counts frames, long tasks and WebGL clears per canvas class before any page script runs.
const probe = () => {
  const m = (window.__perf = { frames: [], longTasks: [], clears: {} });
  const tick = (t) => {
    m.frames.push(t);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) m.longTasks.push(Math.round(e.duration));
    }).observe({ type: "longtask", buffered: true });
  } catch {}
  const clear = WebGL2RenderingContext.prototype.clear;
  WebGL2RenderingContext.prototype.clear = function (mask) {
    const key = this.canvas?.className || "other";
    m.clears[key] = (m.clears[key] || 0) + 1;
    return clear.call(this, mask);
  };
};

const stats = (xs) => {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const at = (q) => s[Math.min(s.length - 1, Math.floor(q * s.length))];
  return { n: s.length, median: +at(0.5).toFixed(1), p95: +at(0.95).toFixed(1), max: +s[s.length - 1].toFixed(1) };
};

async function run(name, contextOptions, { heap }) {
  const browser = await chromium.launch({ args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"] });
  const context = await browser.newContext(contextOptions);
  await context.addInitScript(probe);
  const page = await context.newPage();
  const cdp = await context.newCDPSession(page);
  await cdp.send("Performance.enable");
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(4000); // hydration, world chunk, shader compile, tier warm-up

  const setup = await page.evaluate(() => {
    const gl = document.createElement("canvas").getContext("webgl2");
    const info = gl?.getExtension("WEBGL_debug_renderer_info");
    const renderer = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : "unknown";
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    const root = document.querySelector(".cw");
    return { renderer, world: root?.dataset.world ?? null, height: document.documentElement.scrollHeight, vh: innerHeight };
  });

  // Full scroll with real wheel input at 4x CPU throttle.
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: throttle });
  await page.evaluate(() => {
    window.__perf.frames.length = 0;
    window.__perf.longTasks.length = 0;
  });
  const steps = Math.ceil((setup.height - setup.vh) / 120);
  if (contextOptions.hasTouch) {
    for (let i = 0; i < steps; i += 1) {
      await page.evaluate(() => window.scrollBy(0, 120));
      await page.waitForTimeout(40);
    }
  } else {
    await page.mouse.move(contextOptions.viewport.width / 2, contextOptions.viewport.height / 2);
    for (let i = 0; i < steps; i += 1) {
      await page.mouse.wheel(0, 120);
      await page.waitForTimeout(40);
    }
  }
  await page.waitForTimeout(1500);
  const scroll = await page.evaluate(() => {
    const f = window.__perf.frames;
    const gaps = f.slice(1).map((t, i) => t - f[i]);
    return { gaps, longTasks: [...window.__perf.longTasks] };
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });

  // Idle: no input for 6 s, then count world draws over 5 s.
  await page.waitForTimeout(6000);
  const before = await page.evaluate(() => ({ ...window.__perf.clears }));
  await page.waitForTimeout(5000);
  const after = await page.evaluate(() => ({ ...window.__perf.clears, tier: document.querySelector(".cw")?.dataset.world }));
  const idleDraws = Object.fromEntries(
    Object.keys(after)
      .filter((k) => k !== "tier")
      .map((k) => [k, +(((after[k] || 0) - (before[k] || 0)) / 5).toFixed(1)]),
  );

  let heapReport = null;
  if (heap) {
    const used = async () => {
      await cdp.send("HeapProfiler.collectGarbage");
      const { metrics } = await cdp.send("Performance.getMetrics");
      return Math.round(metrics.find((m) => m.name === "JSHeapUsedSize").value / 1024);
    };
    const samples = [await used()];
    for (let s = 0; s < heapSeconds; s += 20) {
      await page.waitForTimeout(20000);
      samples.push(await used());
    }
    heapReport = { kb: samples, growthKb: samples[samples.length - 1] - samples[0] };
  }

  const report = {
    profile: name,
    renderer: setup.renderer,
    worldAtStart: setup.world,
    worldAtEnd: after.tier,
    cpuThrottle: throttle,
    scroll: { frameMs: stats(scroll.gaps), longTasksOver50ms: scroll.longTasks.filter((d) => d > 50).length, longestTaskMs: Math.max(0, ...scroll.longTasks) },
    idleDrawsPerSecond: idleDraws,
    heap: heapReport,
  };
  await browser.close();
  return report;
}

const desktop = await run("desktop 1440x900", { viewport: { width: 1440, height: 900 } }, { heap: true });
console.log(JSON.stringify(desktop, null, 2));
const phone = await run("phone (Pixel 7 emulation)", { ...devices["Pixel 7"] }, { heap: false });
console.log(JSON.stringify(phone, null, 2));
