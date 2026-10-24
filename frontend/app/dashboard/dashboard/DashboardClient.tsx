"use client";

import { isNativeApp } from "../../../lib/native";
import { AppHome } from "../../../components/AppHome";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Header, Sidebar, MobileNav, ApiAlert } from "../../../components/Navigation";
import { useAuth, useApi, useExperience } from "../../../components/Providers";
import { LoadingBubbles } from "../../../components/hub/HubKit";
import { isSupabaseConfigured } from "../../../lib/supabase";
import { SafetyBanner, type SafetyLevel } from "./SafetyBanner";
import { BodyMapRow, ComingUp, LogInput, MoreFold, QuickLog, WorthALook, comingUpRows } from "./TodaySections";
import { Lede, LivingBubbles, Row, Rows, Section } from "../../../components/pearl";
import { type Nudge } from "../../lib/nutrients";
import { InsightSheetProvider } from "../../insights/InsightDetailSheet";
import { LastUpdatedCard } from "./LastUpdatedCard";
import { pickLastUpdate } from "../../lib/data-sync";
import { buildWeekRecap } from "./recap";
import { TODAY_PATH, bubbleSignals, readBundle } from "./bundle";
import { SIGNAL_META, buildPatterns, buildTodayItems, greeting, summarizeCycle, summarizeSignal, upcomingVisits, type SignalSummary } from "./today";
import type { IntelligenceBrief, LivingMapData, Loadable, ProfileData, SignalSlug, TrackerEntry, TrackerResponse, WeeklyInsights } from "./types";

// What sits behind a closed fold loads when the fold is opened, not with the Today screen.
const Patterns = dynamic(() => import("./TodayPatterns").then((m) => m.Patterns), { ssr: false });
const LivingSignalMap = dynamic(() => import("./LivingSignalMap").then((m) => m.LivingSignalMap), { ssr: false });
const WholeHealthCards = dynamic(() => import("./WholeHealthCards").then((m) => m.WholeHealthCards), { ssr: false });
const PartnerCard = dynamic(() => import("./WholeHealthCards").then((m) => m.PartnerCard), { ssr: false });
const NutrientNudges = dynamic(() => import("./NutrientNudges").then((m) => m.NutrientNudges), { ssr: false });
const WeekRecapCard = dynamic(() => import("./WeekRecapCard").then((m) => m.WeekRecapCard), { ssr: false });

// Only brand-new accounts see the tour, so its code loads on demand instead of with the Today screen.
const FirstRunTour = dynamic(() => import("../../onboarding/FirstRunTour").then((m) => m.FirstRunTour), { ssr: false });


const DAILY = ["sleep", "mood", "activity", "hydration", "nutrition"] as const;
const TILE_ORDER: SignalSlug[] = ["cycle", "sleep", "mood", "activity", "hydration", "nutrition"];
// Today is one call (GET /today) that reads everything side by side on the server, and some of it scans a few weeks of events. A slow answer is not an
// unreachable server: allow it time instead of letting the default 15 s abort flip the whole app to "offline".
// retries: 0 so a hung read fails once ("Try again") rather than replaying for minutes.
const TODAY_LIMITS = { timeoutMs: 30_000, retries: 0 } as const;
const LOADING = { status: "loading" } as const;
const allLoading = () => Object.fromEntries(TILE_ORDER.map((slug) => [slug, LOADING])) as Record<SignalSlug, Loadable<TrackerResponse>>;

type WaterState = "idle" | "saving" | "saved" | "error";
type Bundle = ReturnType<typeof readBundle>;

// The last good answer, kept in memory only (never written to disk) so coming back to Today shows it at once while a fresh one loads behind it.
// It belongs to one person and is dropped the moment nobody is signed in.
let snapshot: { uid: string; bundle: Bundle } | null = null;

function Shell({ children }: { children: ReactNode }) {
  return <main className="flex min-h-dvh items-center justify-center bg-blush p-6 text-center">{children}</main>;
}

export function DashboardClient() {
  const router = useRouter();
  const { loading: authLoading, session, user } = useAuth();
  const { apiStatus, connectionError, fetchBubbles, checkApiHealth, reconnects, dataVersion, lastUpdate } = useApi();
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
  const [nudges, setNudges] = useState<Nudge[]>([]);
  const [lede, setLede] = useState<string | null>(null);
  const [orbitQuestion, setOrbitQuestion] = useState<{ text?: string; answered?: boolean } | null>(null);
  const [water, setWater] = useState<WaterState>("idle");
  const [serverLastUpdate, setServerLastUpdate] = useState<string | null>(null);
  const seenVersion = useRef(dataVersion);
  const restored = useRef(false);
  const userId = (user as { id?: string } | null)?.id;
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
    // A change made elsewhere (another screen, tab or Companion) refreshes quietly: what is on screen stays until the newer answer replaces it.
    const earlier = userId && snapshot?.uid === userId && !restored.current ? snapshot.bundle : null;
    const quiet = seenVersion.current !== dataVersion || earlier !== null;
    seenVersion.current = dataVersion;
    if (earlier) {
      restored.current = true;
      setTrackers((current) => Object.fromEntries(TILE_ORDER.map((slug) => [slug, earlier.trackers[slug] ? { status: "ready", data: earlier.trackers[slug] } : current[slug]])) as typeof current);
      if (earlier.visits) setVisits({ status: "ready", data: earlier.visits });
      if (earlier.brief) setBrief({ status: "ready", data: earlier.brief });
      if (earlier.weekly) setWeekly({ status: "ready", data: earlier.weekly });
      if (earlier.livingMap) setLivingMap({ status: "ready", data: earlier.livingMap });
      setNudges(earlier.nudges); setProfile(earlier.profile ?? null); setLede(earlier.lede?.text ?? null); setOrbitQuestion(earlier.orbit?.question ?? null);
    }
    const get = async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const response = await fetchRef.current(path, init, TODAY_LIMITS);
      if (!response.ok) throw new Error(`${path} failed with ${response.status}`);
      return (await response.json()) as T;
    };
    function settle<T>(request: Promise<T>, set: (value: Loadable<T>) => void) {
      if (!quiet) set(LOADING);
      request.then(
        (data) => { if (alive) set({ status: "ready", data }); },
        () => { if (alive && !quiet) set({ status: "error" }); },
      );
    }
    // One call carries everything Today shows. A part the server could not read is missing from it and shows as a gap or "Try again".
    const bundle = get<unknown>(TODAY_PATH).then(readBundle).then((b) => { if (userId) snapshot = { uid: userId, bundle: b }; return b; });
    const part = <T,>(read: (b: ReturnType<typeof readBundle>) => T | undefined) => bundle.then((b) => {
      const value = read(b);
      if (value === undefined) throw new Error("part missing");
      return value;
    });
    for (const slug of TILE_ORDER) settle(part((b) => b.trackers[slug]), (value) => setTrackers((current) => ({ ...current, [slug]: value })));
    settle(part((b) => b.visits), setVisits);
    settle(part((b) => b.brief), setBrief);
    settle(part((b) => b.weekly), setWeekly);
    settle(part((b) => b.livingMap), setLivingMap);
    bundle.then(
      (b) => { if (alive) { setNudges(b.nudges); setProfile(b.profile ?? null); setLede(b.lede?.text ?? null); setOrbitQuestion(b.orbit?.question ?? null); } },
      () => { /* every part above shows its own error; the greeting and lede fall back to neutral */ },
    );
    get<{ last_update?: string | null; summary?: { last_update?: string } }>("/health/summary?last_only=true").then(
      (r) => { if (alive) setServerLastUpdate(r.last_update ?? r.summary?.last_update ?? null); },
      () => { /* the card falls back to what this browser saw */ },
    );
    return () => { alive = false; };
  }, [token, reloadKey, dataVersion, userId]);

  useEffect(() => {
    if (!userId && !authLoading) snapshot = null;
  }, [userId, authLoading]);

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

  const items = buildTodayItems(signals, cycle, briefData?.actions ?? [], briefData?.state?.deviations);
  const comingVisits = visits.status === "ready" ? upcomingVisits(visits.data, now) : null;
  const nextUp = comingUpRows(cycle, comingVisits)[0];
  const bubbles = bubbleSignals(signals);

  const patterns = buildPatterns(weekly.status === "ready" ? weekly.data.insights ?? [] : [], briefData?.state?.correlations?.items ?? []);
  const patternsState = weekly.status === "loading" || brief.status === "loading" ? "loading" : weekly.status === "error" && brief.status === "error" ? "error" : "ready";

  // ponytail: no endpoint the dashboard reads exposes the user's current triage level (only /chat replies do),
  // and companion.safety_note is generic guidance, so the page stays GREEN. Feed `level` once /intelligence/brief returns it.
  const safety: { level: SafetyLevel; reasons: string[] } = { level: "GREEN", reasons: [] };

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
          {safety.level !== "GREEN" && <SafetyBanner level={safety.level} reasons={safety.reasons} />}

          <InsightSheetProvider>

          {isNativeApp && <AppHome />}

          <div className="pearl-page wide" style={{ padding: 0, maxWidth: 720, margin: "0 auto", width: "100%" }}>
            <p className="pearl-eyebrow">{date}{cycle?.day ? ` · Cycle day ${cycle.day}` : ""}</p>
            <h1 className="pearl-title">{name ? `${greeting(now)}, ${name}.` : `${greeting(now)}.`}</h1>
            {lede ? <Lede>{lede}</Lede> : brief.status === "error" && trackers.sleep.status === "error" ? (
              <Lede>Bubbles couldn&apos;t load today. Your data is safe. <button type="button" onClick={reload} className="pearl-link">Try again</button></Lede>
            ) : null}

            <Section label="Today's signals">
              <LivingBubbles signals={bubbles} onOpen={(id) => router.push(SIGNAL_META[id as SignalSlug].href)} />
            </Section>

            <LogInput />
            <QuickLog onAddWater={addWater} waterBusy={water === "saving"} status={waterStatus} cycle={showCycle} />

            <Section label="Worth a look">
              <WorthALook items={items} onAddWater={addWater} waterBusy={water === "saving"} />
              <Rows>
                {nextUp && <Row label="Coming up" value={`${nextUp.label}, ${nextUp.value}`} href={nextUp.href} />}
                <Row label="Orbit" value={orbitQuestion?.answered === false ? "Today's question is waiting" : undefined} href="/orbit" />
              </Rows>
            </Section>

            <LastUpdatedCard update={pickLastUpdate(lastUpdate, serverLastUpdate)} />

          {/* Everything else is one tap away. */}
          <div className="flex flex-col" style={{ marginTop: 28 }}>
            <MoreFold title="Patterns" hint={patternsState === "ready" && patterns.length ? String(patterns.length) : undefined}>
              <Patterns
                state={patternsState}
                items={patterns}
                note={weekly.status === "error" && brief.status !== "error" ? "Weekly insights couldn't load right now." : undefined}
                onRetry={reload}
              />
            </MoreFold>
            {nudges.length > 0 && (
              <MoreFold title="Blood test ideas" hint={String(nudges.length)}>
                <NutrientNudges items={nudges} />
              </MoreFold>
            )}
            <MoreFold title="Your week">
              <WeekRecapCard state={weekly.status} recap={weekly.status === "ready" ? buildWeekRecap(weekly.data) : null} onRetry={reload} />
            </MoreFold>
            <MoreFold title="Coming up">
              <ComingUp
                cycle={cycle}
                visits={visits.status === "ready" ? upcomingVisits(visits.data, now) : visits.status === "error" ? null : []}
                loading={visits.status === "loading" || trackers.cycle.status === "loading"}
                failed={visits.status === "error" || trackers.cycle.status === "error"}
              />
            </MoreFold>
            <MoreFold title="Whole health">
              <WholeHealthCards cycle={showCycle} />
              {showCycle && <PartnerCard />}
            </MoreFold>
            <MoreFold title="What Bubbles picked up from chat">
              <LivingSignalMap state={livingMap.status} map={livingMap.status === "ready" ? livingMap.data : null} onRetry={reload} />
            </MoreFold>
            {showBodyMap && !isNativeApp && <BodyMapRow />}
          </div>
          </div>
          </InsightSheetProvider>

          <footer className="text-chip font-semibold leading-relaxed text-ink-soft">
            <p className="m-0">Patterns and guidance, not diagnoses. Missing data is a gap, never an all-clear.</p>
            {briefData?.companion?.safety_note && <p className="m-0 mt-1">{briefData.companion.safety_note}</p>}
          </footer>
        </main>

        <MobileNav />
      </div>
      <FirstRunTour />
    </div>
  );
}
