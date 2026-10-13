/**
 * A short in-memory cache for repeated API reads, so revisiting a screen is instant and identical reads in flight share
 * one request. Deliberately conservative, because the data is health data:
 * - one owner at a time: a different signed-in user (or signing out) empties it, so accounts never see each other's data;
 * - never caches /health (online/offline must come from a real answer), chat, consent, or the admin portal (always live);
 * - only successful (2xx) answers are kept;
 * - any write (POST/PUT/PATCH/DELETE) empties it before and after, whatever the write's outcome.
 */
// ponytail: whole-cache invalidation on every write; move to per-resource keys (e.g. SWR) if screens need finer control.

export const API_CACHE_TTL_MS = 20_000;
const NEVER_CACHED = ["/health", "/chat", "/me/consent", "/admin"];

function neverCached(path: string): boolean {
  return NEVER_CACHED.some((prefix) => path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`));
}

export function createApiCache(ttlMs = API_CACHE_TTL_MS, now: () => number = () => Date.now()) {
  const entries = new Map<string, { at: number; response: Response }>();
  const inflight = new Map<string, Promise<Response>>();
  let owner: string | null = null;
  let generation = 0; // bumped on every clear, so a read started before it cannot refill the cache afterwards

  function clear() {
    entries.clear();
    inflight.clear();
    generation += 1;
  }

  return {
    clear,
    /** Size, for tests. */
    get size() {
      return entries.size;
    },
    async fetch(user: string | null, path: string, method: string, run: () => Promise<Response>): Promise<Response> {
      if (user !== owner) {
        clear();
        owner = user;
      }
      if (method.toUpperCase() !== "GET") {
        clear();
        try {
          return await run();
        } finally {
          clear();
        }
      }
      if (neverCached(path)) return run();

      const hit = entries.get(path);
      if (hit && now() - hit.at < ttlMs) return hit.response.clone();
      let pending = inflight.get(path);
      if (!pending) {
        const startedIn = generation;
        pending = run().then((response) => {
          if (response.ok && startedIn === generation) entries.set(path, { at: now(), response: response.clone() });
          return response;
        });
        inflight.set(path, pending);
        void pending.catch(() => undefined).finally(() => {
          if (inflight.get(path) === pending) inflight.delete(path);
        });
      }
      return (await pending).clone();
    },
  };
}
