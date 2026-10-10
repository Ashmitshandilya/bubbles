import { describe, expect, it } from "vitest";
import {
  FrameMonitor,
  TIER_STORAGE_KEY,
  canPromote,
  demote,
  pickInitialTier,
  promote,
  readStoredTier,
  writeStoredTier,
  type TierEnv,
} from "./tier";

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

  it("promotes a desktop at 12 ms p95 over 60 frames, not before and not when slower", () => {
    const m = new FrameMonitor({ mobile: false });
    feed(m, 8, 59);
    expect(m.shouldPromote()).toBe(false);
    m.push(8);
    expect(m.shouldPromote()).toBe(true);
    m.reset();
    feed(m, 12, 60);
    expect(m.shouldPromote()).toBe(true);
    m.reset();
    feed(m, 13, 60);
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
