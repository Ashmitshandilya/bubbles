/**
 * Where the sign-in session is kept in the browser.
 *
 * By default it lives in sessionStorage: it is gone when the tab closes, and other tabs and other people on the same device never see it.
 * Only when the person ticks "Keep me signed in on this device" is it written to localStorage, which survives restarts. The choice itself
 * (a single flag) is the only thing that is always in localStorage. Anything the browser blocks falls back to memory, so sign-in never throws.
 */

export const KEEP_KEY = "bubbles.keep-signed-in";

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function pick(kind: "local" | "session"): Store | null {
  try {
    if (typeof window === "undefined") return null;
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

/** Builds a storage the Supabase client can use. Stores are passed in so the rules can be tested without a browser. */
export function createAuthStorage(local: Store | null, session: Store | null) {
  const memory = new Map<string, string>();

  const read = (store: Store | null, key: string): string | null => {
    try {
      return store ? store.getItem(key) : null;
    } catch {
      return null;
    }
  };
  const write = (store: Store | null, key: string, value: string): boolean => {
    try {
      if (!store) return false;
      store.setItem(key, value);
      return true;
    } catch {
      return false;
    }
  };
  const drop = (store: Store | null, key: string) => {
    try {
      store?.removeItem(key);
    } catch {
      /* nothing to remove */
    }
  };

  const keep = () => read(local, KEEP_KEY) === "1";

  return {
    /** The session tab's copy wins; an older copy in localStorage (from before this rule, or a kept sign-in) is still found. */
    getItem(key: string): string | null {
      return read(session, key) ?? read(local, key) ?? memory.get(key) ?? null;
    },
    setItem(key: string, value: string): void {
      const [target, other] = keep() ? [local, session] : [session, local];
      if (write(target, key, value)) memory.delete(key);
      else memory.set(key, value);
      drop(other, key);
    },
    removeItem(key: string): void {
      drop(local, key);
      drop(session, key);
      memory.delete(key);
    },
  };
}

/** The ready-made storage for the browser. */
export const authStorage = createAuthStorage(pick("local"), pick("session"));

/** The person's last choice: stay signed in on this device? */
export function keepSignedInChoice(): boolean {
  try {
    return pick("local")?.getItem(KEEP_KEY) === "1";
  } catch {
    return false;
  }
}

/** Remember the choice. Call it before signing in so the new session is written to the right place. */
export function setKeepSignedIn(on: boolean): void {
  try {
    const local = pick("local");
    if (!local) return;
    if (on) local.setItem(KEEP_KEY, "1");
    else local.removeItem(KEEP_KEY);
  } catch {
    /* storage is blocked: the session simply stays per tab */
  }
}
