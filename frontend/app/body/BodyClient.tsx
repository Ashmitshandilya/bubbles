"use client";

import { Component, useEffect, useMemo, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { SECTION, ErrorCard, HubPage, Skeleton, useBubblesQuery } from "../../components/hub/HubKit";
import { useExperience } from "../../components/Providers";
import { BodyFallback2D } from "../../components/anatomy/BodyFallback2D";
import { OrganList } from "../../components/anatomy/OrganList";
import { OrganPanel, SafetyNotice } from "../../components/anatomy/OrganPanel";
import { organFromSearch } from "./organParam";
import { STATUS_META, countByStatus, defaultOrganId, prefer3D, readDeviceHints, readOrganMap, readUnavailable, type DeviceHints } from "../lib/organ-map";

// three.js and the model only download when the device is going to show them.
const BodyViewer = dynamic(() => import("../../components/anatomy/BodyViewer"), {
  ssr: false,
  loading: () => <Skeleton className="h-full w-full" />,
});

class ViewerBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onError();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

const LINK = "underline underline-offset-2 hover:text-ink";
const SOURCE_NAME: Record<string, string> = { labs: "lab results", conditions: "conditions", cycle: "cycle data" };
const STAGE = "relative h-[40dvh] min-h-[280px] overflow-hidden rounded-3xl border-2 border-line sm:h-[540px]";
// Pearl studio backdrop from the palette: white light falling onto blush.
const PEARL = { background: "radial-gradient(120% 90% at 50% 30%, var(--bubbles-white) 0%, var(--bubbles-blush) 55%, var(--tint-pink) 100%)" };

export function BodyClient() {
  const { experience } = useExperience();
  return (
    <HubPage title="Body map">
      {experience && !experience.bodyMap.visible ? <BodyMapOff /> : <BodyMap />}
    </HubPage>
  );
}

/** A profile that chose no body map: say so plainly and show how to change it. Nothing is loaded or drawn. */
function BodyMapOff() {
  return (
    <section className={`${SECTION} bubbles-rise max-w-2xl`} aria-labelledby="body-off-title">
      <h1 id="body-off-title" className="text-h2 text-ink">The body map is switched off</h1>
      <p className="mt-2 text-body text-muted">
        Your setup says Bubbles should not show a body map for you. Everything else in Bubbles works the same. You can change this any time.
      </p>
      <Link href="/onboarding?edit=1" className="bubbles-press bubbles-glow mt-5 inline-flex min-h-[52px] items-center rounded-full bg-bubbles-pink-ink px-6 font-extrabold text-white no-underline">
        Change my setup
      </Link>
    </section>
  );
}

function BodyMap() {
  const { experience } = useExperience();
  const anatomy = experience?.bodyMap.anatomy ?? "neutral";
  const [query, reload] = useBubblesQuery<unknown>("/organs/map");
  const organs = useMemo(() => (query.status === "ready" ? readOrganMap(query.data) : []), [query]);
  const unavailable = query.status === "ready" ? readUnavailable(query.data) : [];
  const [picked, setPicked] = useState<string | null>(null);
  // /body?organ=brain opens on that organ (the Mind page links here)
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("organ");
    if (wanted) setPicked(wanted);
  }, []);
  const [hovered, setHovered] = useState<string | null>(null);
  const [hints, setHints] = useState<DeviceHints | null>(null);
  const [mode, setMode] = useState<"3d" | "flat" | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPicked(organFromSearch(window.location.search));   // /body?organ=brain
  }, []);

  useEffect(() => {
    const probed = readDeviceHints();
    setHints(probed);
    setMode(prefer3D(probed) ? "3d" : "flat");
  }, []);

  const selectedId = organs.some((o) => o.id === picked) ? picked : defaultOrganId(organs);
  const selected = organs.find((o) => o.id === selectedId) ?? null;
  const counts = countByStatus(organs);
  const nothingYet = organs.length > 0 && counts.no_data === organs.length;
  const show3D = mode === "3d" && !failed;
  const view = { anatomy, organs, selected: selectedId, hovered, onSelect: setPicked, onHover: setHovered };
  const caption = organs.find((o) => o.id === (hovered ?? selectedId));
  const urgent = selected?.status === "talk_to_doctor" ? selected : null;

  return (
    <div className="space-y-8">
      <h1 className="bubbles-rise text-h1 text-ink">Body map</h1>

      {query.status === "loading" && (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]" role="status" aria-label="Loading your body map">
          <Skeleton className={STAGE} />
          <div className="space-y-6">
            <Skeleton className="h-[320px] rounded-3xl" />
            <Skeleton className="h-[240px] rounded-3xl" />
          </div>
        </div>
      )}

      {query.status === "error" && <ErrorCard title="Your body map didn't load" message={query.message} onRetry={reload} />}

      {query.status === "ready" && organs.length === 0 && (
        <p className={`${SECTION} text-body text-muted`}>Bubbles has no body map for you yet. Try again in a little while.</p>
      )}

      {query.status === "ready" && organs.length > 0 && (
        <>
          {/* On a phone the panel sits under a tall body, so its safety message is repeated up here (the panel's copy is
              hidden below lg, so it is read once). */}
          {urgent && <SafetyNotice organ={urgent} titled className="lg:hidden" />}

          {unavailable.length > 0 && (
            <p role="status" className="rounded-2xl bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
              Couldn&apos;t read your {unavailable.map((u) => SOURCE_NAME[u] ?? u.replaceAll("_", " ")).join(" and ")} just now, so some parts may be missing.
            </p>
          )}

          {nothingYet && (
            <section className={`${SECTION} flex flex-wrap items-center justify-between gap-4`} aria-labelledby="body-empty-title">
              <div className="max-w-xl">
                <h2 id="body-empty-title" className="text-h4 text-ink">
                  Nothing to map yet
                </h2>
                <p className="mt-1 text-body-sm text-muted">Log a symptom, vital or lab result and the matching part fills in. Until then it stays &ldquo;No data yet&rdquo;.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href="/symptoms" className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border-2 border-ink bg-surface px-5 text-body-sm font-extrabold text-ink">
                  Log a symptom
                </Link>
                <Link href="/labs" className="bubbles-press inline-flex min-h-[44px] items-center rounded-full border-2 border-ink bg-surface px-5 text-body-sm font-extrabold text-ink">
                  Add a lab result
                </Link>
              </div>
            </section>
          )}

          <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start">
            {/* On a phone the body stays pinned under the header while the list scrolls past, so a tap on a part is always seen. */}
            <section aria-label="Body" className="contents lg:block lg:sticky lg:top-[calc(var(--header-height)+1.5rem)]">
              <div className={`${STAGE} sticky top-[calc(var(--header-height-mobile)+0.5rem)] z-20 lg:static`} style={PEARL}>
                {mode === null ? (
                  <Skeleton className="h-full w-full" />
                ) : show3D ? (
                  <ViewerBoundary onError={() => setFailed(true)}>
                    <BodyViewer {...view} />
                  </ViewerBoundary>
                ) : (
                  <div className="h-full w-full px-6 pb-10 pt-6">
                    <BodyFallback2D {...view} />
                  </div>
                )}

                {caption && (
                  <p className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center" aria-hidden="true">
                    <span className="inline-flex items-center gap-2 rounded-full bg-surface/90 px-4 py-2 text-body-sm font-extrabold text-ink shadow-[var(--shadow-sm)] backdrop-blur">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: `var(${STATUS_META[caption.status].color})` }} />
                      {caption.name}
                      <span className="font-bold text-muted">{STATUS_META[caption.status].label}</span>
                    </span>
                  </p>
                )}

                {hints?.webgl && !failed && mode !== null && (
                  <button
                    type="button"
                    onClick={() => setMode(show3D ? "flat" : "3d")}
                    className="absolute right-3 top-3 inline-flex min-h-[44px] items-center rounded-full border border-line bg-surface/90 px-4 text-body-sm font-extrabold text-ink-soft shadow-[var(--shadow-xs)] backdrop-blur hover:bg-blush focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-bubbles-grape"
                  >
                    {show3D ? "Flat view" : "3D view"}
                  </button>
                )}
              </div>

              {failed && (
                <p role="status" className="mt-3 text-body-sm font-bold text-muted">
                  The 3D body couldn&apos;t load, so here is the flat view.
                </p>
              )}
              <p className="mt-3 text-caption text-muted">{show3D ? "Drag to turn, pinch to zoom, tap a part." : "Tap a part to open it."}</p>
              {show3D && (
                <details className="mt-1 text-caption text-muted">
                  <summary className="inline-flex min-h-[44px] cursor-pointer items-center font-bold">Model credits</summary>
                  <p className="m-0">
                    3D anatomy adapted from{" "}
                    <a href="https://lifesciencedb.jp/bp3d/" target="_blank" rel="noopener noreferrer" className={LINK}>
                      BodyParts3D
                    </a>{" "}
                    (&copy; The Database Center for Life Science,{" "}
                    <a href="https://creativecommons.org/licenses/by-sa/2.1/jp/deed.en" target="_blank" rel="noopener noreferrer" className={LINK}>
                      CC BY-SA 2.1 JP
                    </a>
                    ) and{" "}
                    <a href="https://github.com/Z-Anatomy/Models-of-human-anatomy" target="_blank" rel="noopener noreferrer" className={LINK}>
                      Z-Anatomy
                    </a>{" "}
                    (Gauthier Kervyn and contributors), changed for Bubbles. The eyes
                    {organs.some((o) => o.id === "uterus_ovaries") && ", uterus and ovaries"} are illustrative. Model licence{" "}
                    <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer" className={LINK}>
                      CC BY-SA 4.0
                    </a>
                    .
                  </p>
                </details>
              )}
            </section>

            <div className="space-y-6">
              <OrganPanel key={selected?.id ?? "none"} organ={selected} />
              <OrganList organs={organs} selected={selectedId} hovered={hovered} onSelect={setPicked} onHover={setHovered} />
            </div>
          </div>

          <p className="sr-only" aria-live="polite">
            {selected ? `${selected.name}: ${STATUS_META[selected.status].label}` : ""}
          </p>
        </>
      )}
    </div>
  );
}
