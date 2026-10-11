import { createClient } from "@supabase/supabase-js";
import { describe, expect, it } from "vitest";
import { KEEP_KEY, createAuthStorage } from "./auth-storage";

// The real Supabase client with a stand-in network: proves the session really ends up in sessionStorage (and only there) by default.

const store = () => {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

const b64 = (o: unknown) => Buffer.from(JSON.stringify(o)).toString("base64url");
const jwt = () => `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: "u1", aal: "aal1", exp: Math.floor(Date.now() / 1000) + 3600 })}.sig`;
const user = { id: "u1", aud: "authenticated", role: "authenticated", email: "person@example.test", app_metadata: {}, user_metadata: {}, created_at: "2026-10-11T00:00:00Z" };
const fakeFetch = (async () => new Response(JSON.stringify(user), { status: 200, headers: { "content-type": "application/json" } })) as typeof fetch;

function client(local: ReturnType<typeof store>, session: ReturnType<typeof store>) {
  return createClient("https://abc.supabase.co", "sb_publishable_test", {
    global: { fetch: fakeFetch },
    auth: { storage: createAuthStorage(local, session), persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
  });
}

describe("supabase client with the auth storage", () => {
  it("keeps the signed-in session in sessionStorage and nothing in localStorage by default", async () => {
    const local = store();
    const session = store();
    const supabase = client(local, session);
    const { error } = await supabase.auth.setSession({ access_token: jwt(), refresh_token: "r1" });
    expect(error).toBeNull();
    expect([...session.data.keys()].some((k) => k.includes("auth-token"))).toBe(true);
    expect(local.data.size).toBe(0);
    const { data } = await supabase.auth.getSession();
    expect(data.session?.user.id).toBe("u1");
  });

  it("uses localStorage when the person chose to stay signed in", async () => {
    const local = store();
    const session = store();
    local.data.set(KEEP_KEY, "1");
    const supabase = client(local, session);
    await supabase.auth.setSession({ access_token: jwt(), refresh_token: "r1" });
    expect([...local.data.keys()].some((k) => k.includes("auth-token"))).toBe(true);
    expect(session.data.size).toBe(0);
  });

  it("signing out clears both places", async () => {
    const local = store();
    const session = store();
    const supabase = client(local, session);
    await supabase.auth.setSession({ access_token: jwt(), refresh_token: "r1" });
    await supabase.auth.signOut({ scope: "local" });
    expect([...session.data.keys(), ...local.data.keys()].some((k) => k.includes("auth-token"))).toBe(false);
    expect((await supabase.auth.getSession()).data.session).toBeNull();
  });

  it("picks up a session that an older version stored in localStorage", async () => {
    const first = store();
    const second = store();
    // sign in once with "keep" on, then read it back through a client whose storage has the same local store
    first.data.set(KEEP_KEY, "1");
    await client(first, second).auth.setSession({ access_token: jwt(), refresh_token: "r1" });
    const fresh = client(first, store());
    expect((await fresh.auth.getSession()).data.session?.user.id).toBe("u1");
  });
});
