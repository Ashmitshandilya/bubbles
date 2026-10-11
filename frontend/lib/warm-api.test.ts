import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const preview = vi.hoisted(() => ({ on: false }));
vi.mock("./supabase", () => ({
  get uiPreview() {
    return preview.on;
  },
}));

const fetchMock = vi.fn();

async function freshWarmApi() {
  vi.resetModules();
  return (await import("./warm-api")).warmApi;
}

beforeEach(() => {
  preview.on = false;
  fetchMock.mockReset().mockResolvedValue(new Response(null));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("window", { location: { protocol: "https:" } });
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("warmApi", () => {
  it("pings /health once per page load, no-cors and uncached", async () => {
    const warmApi = await freshWarmApi();
    warmApi();
    warmApi();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("https://api.example.test/health", { mode: "no-cors", cache: "no-store" });
  });

  it("swallows a failed ping", async () => {
    // A plain function, not vi.fn: vi.fn observes returned promises, which would hide an unhandled rejection.
    let calls = 0;
    vi.stubGlobal("fetch", () => {
      calls += 1;
      return Promise.reject(new TypeError("Failed to fetch"));
    });
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    (await freshWarmApi())();
    await new Promise((r) => setTimeout(r, 10));
    process.off("unhandledRejection", unhandled);
    expect(calls).toBe(1);
    expect(unhandled).not.toHaveBeenCalled();
  });

  it("does nothing without an API address, for plain http on an https page, or in UI preview", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    (await freshWarmApi())();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://api.example.test");
    (await freshWarmApi())();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test");
    preview.on = true;
    (await freshWarmApi())();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("allows plain http from a plain http page (local development)", async () => {
    vi.stubGlobal("window", { location: { protocol: "http:" } });
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000");
    (await freshWarmApi())();
    expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8000/health", { mode: "no-cors", cache: "no-store" });
  });
});
