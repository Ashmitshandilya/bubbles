import { describe, expect, it } from "vitest";
import { createApiCache } from "./api-cache";

function counter(status = 200) {
  let calls = 0;
  const run = async () => {
    calls += 1;
    return new Response(JSON.stringify({ n: calls }), { status });
  };
  return { run, calls: () => calls };
}

describe("createApiCache", () => {
  it("serves a repeated read from the cache within the TTL, then refetches", async () => {
    let t = 0;
    const cache = createApiCache(20_000, () => t);
    const api = counter();
    expect(await (await cache.fetch("u1", "/profile", "GET", api.run)).json()).toEqual({ n: 1 });
    expect(await (await cache.fetch("u1", "/profile", "GET", api.run)).json()).toEqual({ n: 1 });
    t = 20_001;
    expect(await (await cache.fetch("u1", "/profile", "GET", api.run)).json()).toEqual({ n: 2 });
  });

  it("never caches the /health probe, chat, consent or the admin portal", async () => {
    const cache = createApiCache();
    for (const path of ["/health", "/health?x=1", "/chat/history", "/chat", "/me/consent", "/consents", "/consents/history", "/admin/overview?range=1h", "/admin/events/live?after=3", "/admin"]) {
      const api = counter();
      await cache.fetch("u1", path, "GET", api.run);
      await cache.fetch("u1", path, "GET", api.run);
      expect(api.calls()).toBe(2);
    }
  });

  it("caches /health/<tracker> reads (short TTL) and a write empties them", async () => {
    let t = 0;
    const cache = createApiCache(20_000, () => t);
    const api = counter();
    const path = "/health/sleep?days=30";
    await cache.fetch("u1", path, "GET", api.run);
    await cache.fetch("u1", path, "GET", api.run);
    await cache.fetch("u1", "/health/summary", "GET", api.run);
    await cache.fetch("u1", "/health/summary", "GET", api.run);
    expect(api.calls()).toBe(2);
    await cache.fetch("u1", "/health/sleep", "POST", counter().run);
    await cache.fetch("u1", path, "GET", api.run);
    expect(api.calls()).toBe(3);
    t = 20_001;
    await cache.fetch("u1", path, "GET", api.run);
    expect(api.calls()).toBe(4);
  });

  it("does not cache errors or non-2xx answers", async () => {
    const cache = createApiCache();
    const failing = counter(503);
    await cache.fetch("u1", "/profile", "GET", failing.run);
    await cache.fetch("u1", "/profile", "GET", failing.run);
    expect(failing.calls()).toBe(2);
    const throwing = async () => {
      throw new Error("network");
    };
    await expect(cache.fetch("u1", "/x", "GET", throwing)).rejects.toThrow("network");
    expect(cache.size).toBe(0);
  });

  it("empties on a different user and on clear (sign-out)", async () => {
    const cache = createApiCache();
    const a = counter();
    await cache.fetch("u1", "/profile", "GET", a.run);
    const b = counter();
    expect(await (await cache.fetch("u2", "/profile", "GET", b.run)).json()).toEqual({ n: 1 });
    expect(b.calls()).toBe(1);
    cache.clear();
    await cache.fetch("u2", "/profile", "GET", b.run);
    expect(b.calls()).toBe(2);
  });

  it("empties on any write, even a failed one", async () => {
    const cache = createApiCache();
    const api = counter();
    await cache.fetch("u1", "/profile", "GET", api.run);
    await cache.fetch("u1", "/profile", "POST", counter(500).run);
    await cache.fetch("u1", "/profile", "GET", api.run);
    expect(api.calls()).toBe(2);
    await expect(cache.fetch("u1", "/x", "DELETE", async () => Promise.reject(new Error("offline")))).rejects.toThrow();
    expect(cache.size).toBe(0);
  });

  it("shares one request for identical reads in flight", async () => {
    const cache = createApiCache();
    const api = counter();
    const [r1, r2] = await Promise.all([cache.fetch("u1", "/a", "GET", api.run), cache.fetch("u1", "/a", "GET", api.run)]);
    expect(api.calls()).toBe(1);
    expect(await r1.json()).toEqual(await r2.json());
  });

  it("a read started before a user switch cannot fill the new user's cache", async () => {
    const cache = createApiCache();
    let release: (r: Response) => void = () => undefined;
    const slow = cache.fetch("u1", "/profile", "GET", () => new Promise<Response>((resolve) => (release = resolve)));
    const other = counter();
    await cache.fetch("u2", "/other", "GET", other.run);
    release(new Response("{}", { status: 200 }));
    await slow;
    const fresh = counter();
    await cache.fetch("u2", "/profile", "GET", fresh.run);
    expect(fresh.calls()).toBe(1);
  });
});
