import { describe, expect, it } from "vitest";
import {
  FrameMonitor,
  IDLE_AFTER_MS,
  TIER_STORAGE_KEY,
  canPromote,
  demote,
  pickInitialTier,
  promote,
  readStoredTier,
  shouldDrawWorld,
  worldAllowed,
  worldDprCap,
  writeStoredTier,
  type TierEnv,
} from "./tier";

describe("world pacing (one loop, idle throttle, pause, pixel ratio)", () => {
  const draws = (opts: Omit<Parameters<typeof shouldDrawWorld>[0], "frame">, frames = 10) =>
    Array.from({ length: frames }, (_, frame) => shouldDrawWorld({ ...opts, frame })).filter(Boolean).length;

  it("draws every frame while the visitor is active, in lite and full, paused or not", () => {
    for (const tier of ["lite", "full"] as const) {
      expect(draws({ tier, idleMs: 0, paused: false })).toBe(10);
      expect(draws({ tier, idleMs: IDLE_AFTER_MS - 1, paused: true })).toBe(10);
    }
  });

  it("idle: lite halves to about 30 fps, full keeps every frame", () => {
    expect(draws({ tier: "lite", idleMs: IDLE_AFTER_MS, paused: false })).toBe(5);
    expect(draws({ tier: "full", idleMs: 60_000, paused: false })).toBe(10);
  });

  it("an idle page under Pause motion draws nothing", () => {
    for (const tier of ["lite", "full", "static"] as const) expect(draws({ tier, idleMs: IDLE_AFTER_MS, paused: true })).toBe(0);
  });

  it("a page demoted to static for slow frames keeps its world at about 30 fps", () => {
    expect(draws({ tier: "static", idleMs: 0, paused: false })).toBe(5);
    expect(draws({ tier: "static", idleMs: IDLE_AFTER_MS, paused: false })).toBe(5);
  });

  it("steps the pixel ratio down the ladder (full 1.75, lite 1.5, static 1.25)", () => {
    expect(worldDprCap("full")).toBe(1.75);
    expect(worldDprCap("lite")).toBe(1.5);
    expect(worldDprCap("static")).toBe(1.25);
  });
});

describe("worldAllowed: who gets the 3D world at all", () => {
  const capable = { reducedMotion: false, webgl2: true, saveData: false, deviceMemory: 8, storedTier: null };

  it("a capable device mounts it, including one that reports 4 or fewer cores (it starts in lite)", () => {
    expect(worldAllowed(capable)).toBe(true);
    expect(worldAllowed({ ...capable, deviceMemory: undefined })).toBe(true);
  });

  it("stays off for reduced motion, no WebGL2, Save-Data, little memory or a remembered drop to static", () => {
    expect(worldAllowed({ ...capable, reducedMotion: true })).toBe(false);
    expect(worldAllowed({ ...capable, webgl2: false })).toBe(false);
    expect(worldAllowed({ ...capable, saveData: true })).toBe(false);
    expect(worldAllowed({ ...capable, deviceMemory: 2 })).toBe(false);
    expect(worldAllowed({ ...capable, storedTier: "static" })).toBe(false);
    expect(worldAllowed({ ...capable, storedTier: "lite" })).toBe(true);
  });
});

const desktop: TierEnv = {
  reducedMotion: false,
  webgl2: true,
  saveData: false,
  mobile: false,
  deviceMemory: 8,
  hardwareConcurrency: 12,
  pausedByUser: false,
  storedTier: null,
};
const phone: TierEnv = { ...desktop, mobile: true, deviceMemory: 4, hardwareConcurrency: 8 };

describe("pickInitialTier", () => {
  it("gives static for Save-Data, reduced motion, no WebGL2 and a user pause", () => {
    expect(pickInitialTier({ ...desktop, saveData: true })).toBe("static");
    expect(pickInitialTier({ ...phone, saveData: true })).toBe("static");
    expect(pickInitialTier({ ...desktop, reducedMotion: true })).toBe("static");
    expect(pickInitialTier({ ...desktop, webgl2: false })).toBe("static");
    expect(pickInitialTier({ ...desktop, pausedByUser: true })).toBe("static");
  });

  it("starts phones and desktops in lite (desktop is promoted later by measurement)", () => {
    expect(pickInitialTier(phone)).toBe("lite");
    expect(pickInitialTier(desktop)).toBe("lite");
  });

  it("treats few cores or little memory as lite, not static", () => {
    expect(pickInitialTier({ ...desktop, hardwareConcurrency: 2 })).toBe("lite");
    expect(pickInitialTier({ ...desktop, deviceMemory: 2 })).toBe("lite");
    expect(pickInitialTier({ ...desktop, deviceMemory: null, hardwareConcurrency: undefined })).toBe("lite");
  });

  it("honours a stored demotion and never restores full from storage", () => {
    expect(pickInitialTier({ ...desktop, storedTier: "static" })).toBe("static");
    expect(pickInitialTier({ ...desktop, storedTier: "lite" })).toBe("lite");
    expect(pickInitialTier({ ...desktop, storedTier: "full" })).toBe("lite");
  });
});

describe("canPromote", () => {
  it("is false for phones, weak desktops and true for capable desktops", () => {
    expect(canPromote(phone)).toBe(false);
    expect(canPromote({ ...desktop, mobile: true, deviceMemory: 16, hardwareConcurrency: 16 })).toBe(false);
    expect(canPromote({ ...desktop, hardwareConcurrency: 4 })).toBe(false);
    expect(canPromote({ ...desktop, deviceMemory: 2 })).toBe(false);
    expect(canPromote(desktop)).toBe(true);
    expect(canPromote({ mobile: false })).toBe(true); // browsers that report nothing (Safari, Firefox)
  });
});

describe("tier steps", () => {
  it("demotes one rung at a time and promotes lite only", () => {
    expect(demote("full")).toBe("lite");
    expect(demote("lite")).toBe("static");
    expect(demote("static")).toBe("static");
    expect(promote("lite")).toBe("full");
    expect(promote("full")).toBe("full");
    expect(promote("static")).toBe("static");
  });
});

describe("FrameMonitor", () => {
  const feed = (m: FrameMonitor, ms: number, n: number) => {
    for (let i = 0; i < n; i += 1) m.push(ms);
  };

  it("demotes after 90 slow frames and not before", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 30, 89);
    expect(m.shouldDemote()).toBe(false);
    m.push(30);
    expect(m.size).toBe(90);
    expect(m.p95()).toBe(30);
    expect(m.shouldDemote()).toBe(true);
  });

  it("does not demote at 24 ms exactly, or for a few hitches", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 24, 90);
    expect(m.shouldDemote()).toBe(false);
    m.reset();
    feed(m, 8, 90);
    for (let i = 0; i < 4; i += 1) m.push(200); // 4 of 90 frames is under 5 percent
    expect(m.shouldDemote()).toBe(false);
    for (let i = 0; i < 3; i += 1) m.push(200); // now more than 5 percent are slow
    expect(m.shouldDemote()).toBe(true);
  });

  it("forgets old frames: the ring keeps the newest 90", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 40, 90);
    expect(m.shouldDemote()).toBe(true);
    feed(m, 8, 90);
    expect(m.shouldDemote()).toBe(false);
    expect(m.p95()).toBe(8);
  });

  it("promotes a steady 60 Hz desktop (16.7 ms frames), not before 60 frames", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 16.7, 59);
    expect(m.shouldPromote()).toBe(false);
    m.push(16.7);
    expect(m.shouldPromote()).toBe(true);
  });

  it("promotes 120 and 144 Hz displays too, and tolerates a few hitches", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 8.3, 60);
    expect(m.shouldPromote()).toBe(true);
    m.reset();
    feed(m, 6.9, 60);
    expect(m.shouldPromote()).toBe(true);
    m.reset();
    feed(m, 16.7, 57);
    for (let i = 0; i < 3; i += 1) m.push(40); // 3 of 60 is 5 percent: p95 still lands on a normal frame
    expect(m.shouldPromote()).toBe(true);
  });

  it("does not promote a throttled or uneven loop", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 33.3, 60); // 30 fps: median too slow
    expect(m.shouldPromote()).toBe(false);
    m.reset();
    feed(m, 16.7, 54);
    feed(m, 40, 6); // 10 percent hitches: p95 above 1.35x the median
    expect(m.shouldPromote()).toBe(false);
  });

  it("never promotes mobile, however fast, and never a desktop marked not promotable", () => {
    const phoneMonitor = new FrameMonitor({ mobile: true });
    feed(phoneMonitor, 4, 200);
    expect(phoneMonitor.shouldPromote()).toBe(false);
    const weak = new FrameMonitor({ mobile: false, promotable: canPromote({ mobile: false, hardwareConcurrency: 2 }) });
    feed(weak, 4, 200);
    expect(weak.shouldPromote()).toBe(false);
  });

  it("ignores NaN and negative samples", () => {
    const m = new FrameMonitor({ mobile: false });
    m.push(Number.NaN);
    m.push(-5);
    m.push(Number.POSITIVE_INFINITY);
    expect(m.size).toBe(0);
  });
});

describe("stored tier", () => {
  const store = (initial: Record<string, string> = {}) => {
    const data = { ...initial };
    return {
      getItem: (k: string) => data[k] ?? null,
      setItem: (k: string, v: string) => {
        data[k] = v;
      },
    };
  };

  it("round-trips and rejects junk", () => {
    const s = store();
    expect(readStoredTier(s)).toBeNull();
    writeStoredTier(s, "lite");
    expect(readStoredTier(s)).toBe("lite");
    expect(readStoredTier(store({ [TIER_STORAGE_KEY]: "ultra" }))).toBeNull();
    expect(readStoredTier(null)).toBeNull();
  });

  it("survives blocked storage", () => {
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(readStoredTier(blocked)).toBeNull();
    expect(() => writeStoredTier(blocked, "static")).not.toThrow();
  });
});
