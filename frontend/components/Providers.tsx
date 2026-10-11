"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { isSupabaseConfigured, supabase, uiPreview } from "../lib/supabase";
import { needsSecondStep } from "../lib/mfa";
import {
  classifyFailure, createReconnectLoop, databaseStatusOf, failureFromError, mayReplayAfterTimeout, parseHealth, shareInFlight,
  type DatabaseStatus, type HealthPayload,
} from "../app/lib/connection";

type User = {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
};

type Session = {
  access_token: string;
  user: {
    id: string;
    email: string | undefined;
    user_metadata: {
      display_name?: string;
    };
    created_at: string;
  } | null;
};

type AuthContextType = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  async function refreshSession() {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      setSession({
        access_token: session.access_token,
        user: session.user ? {
          id: session.user.id,
          email: session.user.email ?? "",
          user_metadata: session.user.user_metadata,
          created_at: session.user.created_at,
        } : null,
      });
      if (session.user) {
        setUser({
          id: session.user.id,
          email: session.user.email ?? "",
          display_name: session.user.user_metadata?.display_name ?? null,
          created_at: session.user.created_at,
        });
      } else {
        setUser(null);
      }
    } else {
      setSession(null);
      setUser(null);
    }
    setLoading(false);
  }

  useEffect(() => {
    let mounted = true;
    let subscription: { unsubscribe: () => void } | null = null;

    async function initializeAuth() {
      if (uiPreview) {   // dev-only: a fixed demo person, no Supabase (see lib/supabase.ts)
        const created_at = "2026-08-01T09:00:00.000Z";
        setSession({ access_token: "preview", user: { id: "preview-user", email: "riya@example.test", user_metadata: { display_name: "Riya" }, created_at } });
        setUser({ id: "preview-user", email: "riya@example.test", display_name: "Riya", created_at });
        if (mounted) setLoading(false);
        return;
      }
      if (!isSupabaseConfigured) {
        if (mounted) setLoading(false);
        return;
      }

      await refreshSession();

      // A password-only session on an account that turned on two-step sign-in cannot use the API: send the person to the code step
      // instead of letting every call fail with "session expired".
      try {
        const { data: level } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
        if (mounted && needsSecondStep(level)) {
          router.replace("/login?mfa=1");
          return;
        }
      } catch {
        /* no readable level: carry on, the API will say if a code is needed */
      }

      const { data } = await supabase.auth.onAuthStateChange(async (_event, s) => {
        if (!mounted) return;

        if (s) {
          setSession({
            access_token: s.access_token,
            user: s.user ? {
              id: s.user.id,
              email: s.user.email ?? "",
              user_metadata: s.user.user_metadata,
              created_at: s.user.created_at,
            } : null,
          });
          if (s.user) {
            setUser({
              id: s.user.id,
              email: s.user.email ?? "",
              display_name: s.user.user_metadata?.display_name ?? null,
              created_at: s.user.created_at,
            });
          } else {
            setUser(null);
            router.push("/login");
          }
        } else {
          setSession(null);
          setUser(null);
          router.push("/login");
        }
        setLoading(false);
      });

      subscription = data.subscription;
    }

    initializeAuth();

    return () => {
      mounted = false;
      if (subscription) {
        subscription.unsubscribe();
      }
    };
  }, [router]);

  async function signOut() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <AuthContext.Provider value={{ user, session, loading, signOut, refreshSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}

// API base URLs to try, in order: the configured URL, its localhost twin, and
// (in the browser on a LAN address) the same host on port 8000.
function getApiUrls(): string[] {
  const configured = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const urls = new Set<string>([configured]);
  if (configured === "http://127.0.0.1:8000" || configured === "http://localhost:8000") {
    urls.add("http://localhost:8000");
    urls.add("http://127.0.0.1:8000");
  }
  if (typeof window !== "undefined") {
    const { hostname } = window.location;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") urls.add(`http://${hostname}:8000`);
  }
  return Array.from(urls);
}

/** The API addresses worth trying from this page (an https page cannot call plain-http addresses). */
function candidateUrls(): string[] {
  return getApiUrls().filter((url) => {
    if (typeof window === "undefined") return true;
    return !(window.location.protocol === "https:" && url.startsWith("http://"));
  });
}

/**
 * True when some API address answers a no-cors request: the server is up and only the browser's CORS check failed.
 * (An opaque response resolves; a stopped server rejects.)
 */
async function answersDespiteCors(): Promise<boolean> {
  for (const url of candidateUrls()) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 3000);
    try {
      await fetch(`${url}/health`, { mode: "no-cors", cache: "no-store", signal: controller.signal });
      return true;
    } catch {
      // try the next address
    } finally {
      window.clearTimeout(timer);
    }
  }
  return false;
}

/** Per-call limits. The defaults (15 seconds, one retry) apply to every caller that passes none. */
export type FetchBubblesOptions = { timeoutMs?: number; retries?: number };

/** /health is a cheap probe: one attempt, a short timeout. It must not hold the offline banner up for 30 seconds. */
const HEALTH_LIMITS: FetchBubblesOptions = { timeoutMs: 8000, retries: 0 };
/** The very first /health after load may hit a sleeping free-plan host (up to about a minute to start). */
const FIRST_HEALTH_LIMITS: FetchBubblesOptions = { timeoutMs: 65000, retries: 0 };
/** Show "waking up" instead of nothing once the first probe has been quiet this long. */
const WAKING_AFTER_MS = 5000;

type ApiContextType = {
  apiStatus: "checking" | "online" | "offline";
  connectionError: string | null;
  fetchBubbles: (path: string, options?: RequestInit, limits?: FetchBubblesOptions) => Promise<Response>;
  checkApiHealth: () => Promise<void>;
  /** The parsed GET /health payload, or null before the first answer / when the answer was not a Bubbles payload. */
  health: HealthPayload | null;
  /** "permission_denied" means compatibility mode: the app works, the database needs a one-time grant. */
  databaseStatus: DatabaseStatus;
  /** Epoch ms of the next automatic reconnect attempt while offline; null otherwise (or while the tab is hidden). */
  nextRetryAt: number | null;
  /** The first /health is slow (the host is starting up); not an error. */
  waking: boolean;
  /** A reconnect probe is in flight. */
  retrying: boolean;
  /** Counts offline-to-online transitions; data hooks reload failed queries when it changes. */
  reconnects: number;
};

const ApiContext = createContext<ApiContextType | undefined>(undefined);

export function ApiProvider({ children }: { children: ReactNode }) {
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [nextRetryAt, setNextRetryAt] = useState<number | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [reconnects, setReconnects] = useState(0);
  const [waking, setWaking] = useState(false);
  const firstProbeDone = useRef(false);
  const wasWaking = useRef(false);
  // The latest probe (set below) and the one in flight, so many failed calls at once share one /health check.
  const probeRef = useRef<() => Promise<boolean>>(async () => false);
  const probing = useRef<Promise<boolean> | null>(null);
  // Read inside the probe: the long "waking up" retry is for a host that was up and fell asleep, not for every reconnect attempt while offline.
  const statusRef = useRef(apiStatus);
  useEffect(() => {
    statusRef.current = apiStatus;
  }, [apiStatus]);
  const { session } = useAuth();

  const fetchBubbles = useCallback(async (path: string, options: RequestInit = {}, limits: FetchBubblesOptions = {}) => {
    const { timeoutMs = 15000, retries = 1 } = limits;
    // A caller that asked for a custom timeout expects a slow answer, so running out of time says nothing about
    // whether the backend is reachable; it must not flip the whole app offline.
    const slowCall = limits.timeoutMs !== undefined;
    let lastError: unknown = null;
    const candidates = candidateUrls();

    if (candidates.length === 0) {
      setApiStatus("offline");
      const error = Object.assign(
        new Error("Bubbles' address uses plain http while this page is on https, so the browser blocked it. Set NEXT_PUBLIC_API_URL to an https address."),
        { timedOut: false, networkError: true },
      );
      setConnectionError(error.message);
      throw error;
    }

    candidateLoop: for (const baseUrl of candidates) {
      for (let attempt = 0; attempt <= retries; attempt += 1) {
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
        try {
          const response = await fetch(`${baseUrl}${path}`, {
            ...options,
            signal: controller.signal,
            cache: "no-store",
            headers: {
              ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
              "Content-Type": "application/json",
              // the user's clock, so "today" is their day and not UTC (the backend ignores a missing/invalid value)
              "X-Tz-Offset-Minutes": String(-new Date().getTimezoneOffset()),
              ...options.headers,
            },
          });
          setApiStatus("online");
          setConnectionError(null);
          return response;
        } catch (error) {
          lastError = error;
          // retries: 0 means "at most once", and a save is never sent twice: after a timeout the server may still be
          // working on the request, so neither another attempt nor the twin host may replay it.
          if (error instanceof DOMException && error.name === "AbortError" && (retries === 0 || !mayReplayAfterTimeout(options.method))) {
            break candidateLoop;
          }
          if (attempt < retries) {
            await new Promise((resolve) => window.setTimeout(resolve, 500));
          }
        } finally {
          window.clearTimeout(timeout);
        }
      }
    }

    const timedOut = lastError instanceof DOMException && lastError.name === "AbortError";
    // Only a rejected fetch lands here (an HTTP status returns above), so this is "no answer", never "bad answer".
    // A browser reports CORS refusal and a stopped server alike, so ask the server whether it is actually up.
    const corsOrigin = !timedOut && (await answersDespiteCors()) ? window.location.origin : undefined;
    const message = classifyFailure({ timedOut, networkError: !timedOut, corsOrigin }).message;
    // Until the first /health has answered, a slow or failed call says nothing yet: the probe decides offline.
    // After that one failed call is no proof either (a slow endpoint on a slow host), so ask /health to decide.
    if (!(timedOut && slowCall) && firstProbeDone.current && path !== "/health") {
      void shareInFlight(probing, () => probeRef.current());
    }
    throw Object.assign(new Error(message), { timedOut, networkError: !timedOut, corsOrigin });
  }, [session]);

  /** Any HTTP answer means the server is up (even a 5xx); only a rejected request means offline. */
  const probe = useCallback(async (): Promise<boolean> => {
    const first = !firstProbeDone.current;
    const wakeTimer = first
      ? window.setTimeout(() => {
          wasWaking.current = true;
          setWaking(true);
        }, WAKING_AFTER_MS)
      : undefined;
    try {
      let response: Response;
      try {
        response = await fetchBubbles("/health", {}, first ? FIRST_HEALTH_LIMITS : HEALTH_LIMITS);
      } catch (error) {
        // A later probe running out of time usually means the host fell asleep: show "waking up" and wait once, longer.
        if (first || !failureFromError(error).timedOut || statusRef.current === "offline") throw error;
        wasWaking.current = true;
        setWaking(true);
        setApiStatus("checking");
        response = await fetchBubbles("/health", {}, FIRST_HEALTH_LIMITS);
      }
      setHealth(parseHealth(await response.json().catch(() => null)));
      // Calls that ran while the host slept failed quietly; tell the data hooks to load again.
      if (wasWaking.current) setReconnects((n) => n + 1);
      return true;
    } catch (error) {
      setApiStatus("offline");
      setConnectionError(classifyFailure(failureFromError(error)).message);
      return false;
    } finally {
      window.clearTimeout(wakeTimer);
      firstProbeDone.current = true;
      wasWaking.current = false;
      setWaking(false);
    }
  }, [fetchBubbles]);

  const checkApiHealth = useCallback(async () => {
    await probe();
  }, [probe]);

  useEffect(() => {
    probeRef.current = probe;
  }, [probe]);

  // Check on mount and whenever the session changes.
  useEffect(() => {
    void probe();
  }, [probe]);

  // While offline, poll /health (4s, backing off to 15s). Stops when online, pauses while the tab is hidden
  // (resuming at once when it returns), and cleans up on unmount.
  useEffect(() => {
    if (apiStatus !== "offline") return;
    const loop = createReconnectLoop({
      probe: () => shareInFlight(probing, () => probeRef.current()),
      isHidden: () => document.hidden,
      onNextAttempt: setNextRetryAt,
      onProbing: setRetrying,
    });
    const onVisibility = () => loop.visibilityChanged();
    document.addEventListener("visibilitychange", onVisibility);
    loop.start();
    return () => {
      loop.stop();
      document.removeEventListener("visibilitychange", onVisibility);
      setNextRetryAt(null);
      setRetrying(false);
    };
  }, [apiStatus]);

  const previousStatus = useRef(apiStatus);
  useEffect(() => {
    if (previousStatus.current === "offline" && apiStatus === "online") setReconnects((n) => n + 1);
    previousStatus.current = apiStatus;
  }, [apiStatus]);

  return (
    <ApiContext.Provider
      value={{
        apiStatus, connectionError, fetchBubbles, checkApiHealth, health, databaseStatus: databaseStatusOf(health),
        nextRetryAt, retrying, reconnects, waking,
      }}
    >
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  const context = useContext(ApiContext);
  if (!context) throw new Error("useApi must be used within ApiProvider");
  return context;
}