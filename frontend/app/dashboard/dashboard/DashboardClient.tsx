"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Header, Sidebar, MobileNav, ApiAlert } from "../../../components/Navigation";
import { useAuth, useApi, useExperience } from "../../../components/Providers";
import { LoadingBubbles } from "../../../components/hub/HubKit";
import { isSupabaseConfigured } from "../../../lib/supabase";
import { SafetyBanner, type SafetyLevel } from "./SafetyBanner";
import { LivingSignalMap } from "./LivingSignalMap";
import {
  BodyMapCard, ComingUp, Greeting, Patterns, QuickLog, SignalTiles, TodayBrief,
  tileFromCycle, tileFromSignal, type HeroState, type Tile,
} from "./TodaySections";
import { PartnerCard, WholeHealthCards } from "./WholeHealthCards";
import { WeekRecapCard } from "./WeekRecapCard";
import { buildWeekRecap } from "./recap";
import {
  WINDOW_DAYS, buildPatterns, buildTodayItems, greeting, readTracker, summarizeCycle, summarizeSignal, upcomingVisits,
  type SignalSummary,
} from "./today";
import type {
  IntelligenceBrief, LivingMapData, Loadable, ProfileData, SignalSlug, TrackerEntry, TrackerResponse, WeeklyInsights,
} from "./types";

const DAILY = ["sleep", "mood", "activity", "hydration", "nutrition"] as const;
const TILE_ORDER: SignalSlug[] = ["cycle", "sleep", "mood", "activity", "hydration", "nutrition"];
// The cycle summary (average length, next period) is computed from the entries in the window, so Today asks for the
// same year the Cycle page does; a shorter window would show a different average than the page it links to.
const CYCLE_DAYS = 365;
// Today fires a dozen reads at once and several of them scan a few weeks of events. A slow answer is not an
// unreachable server: allow it time instead of letting the default 15 s abort flip the whole app to "offline".
// retries: 0 so a hung read fails once ("Try again") rather than replaying for minutes.
const TODAY_LIMITS = { timeoutMs: 30_000, retries: 0 } as const;
const LOADING = { status: "loading" } as const;
const allLoading = () => Object.fromEntries(TILE_ORDER.map((slug) => [slug, LOADING])) as Record<SignalSlug, Loadable<TrackerResponse>>;

type WaterState = "idle" | "saving" | "saved" | "error";

function Shell({ children }: { children: ReactNode }) {
  return <main className="flex min-h-dvh items-center justify-center bg-blush p-6 text-center">{children}</main>;
}

export function DashboardClient() {
  const router = useRouter();
  const { loading: authLoading, session, user } = useAuth();
  const { apiStatus, connectionError, fetchBubbles, checkApiHealth, reconnects } = useApi();
  const { experience } = useExperience();
  // the person's body decides what Today shows: no Cycle or Partner cards for a male body, no body-map card when the map is off
  const showCycle = experience?.cycleVisible !== false;
  const showBodyMap = experience?.bodyMap.visible !== false;
  const [reloadKey, setReloadKey] = useState(0);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [trackers, setTrackers] = useState(allLoading);
  const [visits, setVisits] = useState<Loadable<TrackerEntry[]>>(LOADING);
  const [brief, setBrief] = useState<Loadable<IntelligenceBrief>>(LOADING);
  const [weekly, setWeekly] = useState<Loadable<WeeklyInsights>>(LOADING);
  const [livingMap, setLivingMap] = useState<Loadable<LivingMapData>>(LOADING);
  const [water, setWater] = useState<WaterState>("idle");
  // fetchBubbles changes identity on every auth event (token refresh, tab refocus). Loading is keyed on the token, so
  // those events do not blank the page with skeletons and refire a dozen requests.
  const fetchRef = useRef(fetchBubbles);
  fetchRef.current = fetchBubbles;
  const token = session?.access_token;

  // Signed-out users go to /login (AuthProvider also redirects on auth changes).
  useEffect(() => {
    if (isSupabaseConfigured && !authLoading && !session) router.replace("/login");
  }, [authLoading, session, router]);

  useEffect(() => {
    if (!isSupabaseConfigured || !token) return;
    let alive = true;
    const get = async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const response = await fetchRef.current(path, init, TODAY_LIMITS);
      if (!response.ok) throw new Error(`${path} failed with ${response.status}`);
      return (await response.json()) as T;
    };
    function settle<T>(request: Promise<T>, set: (value: Loadable<T>) => void) {
      set(LOADING);
      request.then(
        (data) => { if (alive) set({ status: "ready", data }); },
        () => { if (alive) set({ status: "error" }); },
      );
    }
    const post = (days: number): RequestInit => ({ method: "POST", body: JSON.stringify({ days }) });

    for (const slug of TILE_ORDER) {
      settle(get<unknown>(`/health/${slug}?days=${slug === "cycle" ? CYCLE_DAYS : WINDOW_DAYS}`).then(readTracker), (value) =>
        setTrackers((current) => ({ ...current, [slug]: value })),
      );
    }
    settle(get<unknown>("/health/visits").then((r) => readTracker(r).entries), setVisits);
    settle(get<{ brief: IntelligenceBrief }>("/intelligence/brief", post(14)).then((r) => r.brief), setBrief);
    settle(get<{ insights: WeeklyInsights }>("/insights/weekly").then((r) => r.insights), setWeekly);
    settle(get<{ map: LivingMapData }>("/intelligence/living-map?days=14").then((r) => r.map), setLivingMap);
    get<{ profile?: ProfileData | null }>("/profile").then(
      (r) => { if (alive) setProfile(r.profile ?? null); },
      () => { /* greeting falls back to a neutral form */ },
    );
    return () => { alive = false; };
  }, [token, reloadKey]);

  useEffect(() => {
    if (water !== "saved" && water !== "error") return;
    const timer = window.setTimeout(() => setWater("idle"), 5000);
    return () => window.clearTimeout(timer);
  }, [water]);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  // Bubbles came back after being unreachable: refetch everything instead of leaving error cards on screen.
  const seenReconnects = useRef(reconnects);
  useEffect(() => {
    if (seenReconnects.current === reconnects) return;
    seenReconnects.current = reconnects;
    reload();
  }, [reconnects, reload]);

  const addWater = useCallback(async () => {
    const tempId = `pending-${Date.now()}`;
    const updateHydration = (change: (entries: TrackerEntry[]) => TrackerEntry[]) =>
      setTrackers((current) => {
        const hydration = current.hydration;
        return hydration.status === "ready"
          ? { ...current, hydration: { status: "ready", data: { ...hydration.data, entries: change(hydration.data.entries) } } }
          : current;
      });
    setWater("saving");
    updateHydration((entries) => [{ id: tempId, date: new Date().toISOString(), volume: 250 }, ...entries]);
    try {
      const response = await fetchBubbles("/health/hydration", { method: "POST", body: JSON.stringify({ volume: 250 }) });
      if (!response.ok) throw new Error(`Hydration save failed with ${response.status}`);
      const payload = (await response.json()) as { entry?: TrackerEntry };
      updateHydration((entries) => entries.map((e) => (e.id === tempId && payload.entry ? payload.entry : e)));
      setWater("saved");
    } catch {
      updateHydration((entries) => entries.filter((e) => e.id !== tempId));
      setWater("error");
    }
  }, [fetchBubbles]);

  if (!isSupabaseConfigured) {
    return (
      <Shell>
        <div role="alert" className="max-w-md rounded-[24px] border border-line bg-surface p-6">
          <h1 className="m-0 font-display text-2xl font-semibold">Bubbles isn&apos;t configured yet</h1>
          <p className="m-0 mt-2 text-[0.9375rem] text-ink-soft">
            Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to frontend/.env.local, then restart the app.
          </p>
        </div>
      </Shell>
    );
  }

  if (authLoading || !session) {
    return (
      <Shell>
        <div className="flex flex-col items-center gap-3">
          <LoadingBubbles label={authLoading ? "Getting your day ready…" : "Taking you to sign in…"} />
          {!authLoading && <Link href="/login" className="font-semibold text-bubbles-pink-ink">Go to sign in</Link>}
        </div>
      </Shell>
    );
  }

  // ── Derived view state (all from real responses) ──
  const now = new Date();
  const signals = DAILY.flatMap((slug): SignalSummary[] => {
    const t = trackers[slug];
    return t.status === "ready" ? [summarizeSignal(slug, t.data.entries ?? [], now)] : [];
  });
  const cycle = showCycle && trackers.cycle.status === "ready" ? summarizeCycle(trackers.cycle.data, now) : null;
  const briefData = brief.status === "ready" ? brief.data : null;

  const trackersLoading = TILE_ORDER.some((slug) => trackers[slug].status === "loading");
  const trackersFailed = TILE_ORDER.every((slug) => trackers[slug].status === "error");
  const items = buildTodayItems(signals, cycle, briefData?.actions ?? []);
  const heroState: HeroState =
    trackersLoading || brief.status === "loading" ? "loading"
    : trackersFailed ? "error"
    : !signals.some((s) => s.logged) && !cycle?.logged ? "empty"
    : items.length ? "items" : "clear";

  const tiles = TILE_ORDER.filter((slug) => showCycle || slug !== "cycle").map((slug): Tile => {
    const pending = { slug, state: trackers[slug].status === "error" ? "error" : "loading" } as const;
    if (slug === "cycle") return cycle ? tileFromCycle(cycle) : pending;
    const summary = signals.find((s) => s.slug === slug);
    return summary ? tileFromSignal(summary) : pending;
  });

  const patterns = buildPatterns(weekly.status === "ready" ? weekly.data.insights ?? [] : [], briefData?.state?.correlations?.items ?? []);
  const patternsState = weekly.status === "loading" || brief.status === "loading" ? "loading" : weekly.status === "error" && brief.status === "error" ? "error" : "ready";

  // ponytail: no endpoint the dashboard reads exposes the user's current triage level (only /chat replies do),
  // and companion.safety_note is generic guidance, so the page stays GREEN. Feed `level` once /intelligence/brief returns it.
  const safety: { level: SafetyLevel; reasons: string[] } = { level: "GREEN", reasons: [] };
  const showMascot = safety.level !== "RED";

  const name = (profile?.display_name ?? user?.display_name ?? "").trim().split(/\s+/)[0]?.slice(0, 40);
  const date = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const waterStatus =
    water === "saving" || water === "saved" ? { text: "Added 250 ml of water. Nice one!", tone: "ok" as const }
    : water === "error" ? { text: "Couldn't save your water. Please try again.", tone: "error" as const }
    : null;

  return (
    <div className="flex min-h-dvh bg-blush text-ink">
      <Sidebar apiStatus={apiStatus} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header apiStatus={apiStatus} />
        <ApiAlert connectionError={connectionError} onRetry={checkApiHealth} />

        <main id="main" className="bubbles-stagger mx-auto flex w-full max-w-[1180px] flex-1 flex-col gap-6 px-4 pb-10 pt-6 sm:px-8 sm:pt-7">
          <Greeting title={name ? `${greeting(now)}, ${name}` : greeting(now)} date={date} cycleDay={cycle?.day} />

          {safety.level !== "GREEN" && <SafetyBanner level={safety.level} reasons={safety.reasons} />}

          <TodayBrief state={heroState} items={items} showMascot={showMascot} onRetry={reload} onAddWater={addWater} waterBusy={water === "saving"} />

          <QuickLog onAddWater={addWater} waterBusy={water === "saving"} status={waterStatus} />

          {/* "Your week" sits under the tiles, so on wide screens the left column runs as long as the Patterns column */}
          <div className="flex flex-wrap items-start gap-6">
            <div className="flex min-w-0 flex-[2_1_520px] flex-col gap-6">
              <SignalTiles tiles={tiles} />
              <WeekRecapCard state={weekly.status} recap={weekly.status === "ready" ? buildWeekRecap(weekly.data) : null} />
            </div>
            <aside aria-labelledby="today-patterns" className="flex min-w-0 flex-[1_1_300px] flex-col gap-3.5">
              <Patterns
                state={patternsState}
                items={patterns}
                note={weekly.status === "error" && brief.status !== "error" ? "Weekly insights couldn't load right now." : undefined}
                onRetry={reload}
              />
              <ComingUp
                cycle={cycle}
                visits={visits.status === "ready" ? upcomingVisits(visits.data, now) : visits.status === "error" ? null : []}
                loading={visits.status === "loading" || trackers.cycle.status === "loading"}
                failed={visits.status === "error" || trackers.cycle.status === "error"}
              />
            </aside>
          </div>

          <WholeHealthCards cycle={showCycle} />
          {showCycle && <PartnerCard />}

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <LivingSignalMap state={livingMap.status} map={livingMap.status === "ready" ? livingMap.data : null} onRetry={reload} />
            {showBodyMap && <BodyMapCard />}
          </div>

          <footer className="flex flex-col gap-1 text-chip font-semibold leading-relaxed text-ink-soft">
            <p className="m-0">Bubbles shares patterns and general guidance, not diagnoses. Missing data is shown as a gap, never as &ldquo;all clear&rdquo;.</p>
            {briefData?.companion?.safety_note && <p className="m-0">{briefData.companion.safety_note}</p>}
          </footer>
        </main>

        <MobileNav />
      </div>
    </div>
  );
}
