"use client";

import { Component, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import { CARD, PILL, ErrorCard, Skeleton, humanize, useBubblesQuery } from "../../components/hub/HubKit";
import { organLabel, type Anatomy } from "../../components/anatomy/presets";

// three.js only downloads when someone asks for the 3D view.
const Anatomy3D = dynamic(() => import("../../components/Anatomy3D"), {
  ssr: false,
  loading: () => <Skeleton className="h-[360px] w-full rounded-3xl" />,
});

type OrganStatus = "unknown" | "no_major_risk_signal" | "watch" | "needs_attention";

interface OrganAssessment {
  organ: string;
  status: OrganStatus;
  confidence: number;
  data_completeness: number;
  signals: Array<{ factor: string; direction: string }>;
  limitations: string[];
  recommended_actions: string[];
}

interface BodySystemsResponse {
  intelligence?: { systems?: OrganAssessment[]; systems_with_data?: number; total_systems?: number };
}


// Uncertainty language only: nothing here ever says "healthy".
const STATUS: Record<OrganStatus, { label: string; pill: string; dot: string }> = {
  no_major_risk_signal: { label: "No major risk signal", pill: "bg-tint-mint text-bubbles-mint-deep", dot: "bg-bubbles-mint" },
  watch: { label: "Watch", pill: "bg-tint-sun text-bubbles-sun-deep", dot: "bg-bubbles-sun" },
  needs_attention: { label: "Needs attention", pill: "bg-tint-peach text-bubbles-peach-deep", dot: "bg-bubbles-peach" },
  unknown: {
    label: "Not enough data",
    pill: "border-2 border-dashed border-line-strong text-ink-soft",
    dot: "border-2 border-dashed border-ink-faint",
  },
};

const DIRECTION: Record<string, string> = {
  risk: "Risk factor in your logs",
  protective: "Working in your favour",
  direct: "Clinical data on file",
};

function confidenceWord(value: number) {
  return value >= 0.7 ? "High" : value >= 0.4 ? "Medium" : "Low";
}

class ThreeBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
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

// Until the person's own setup says otherwise the map draws a neutral body (the onboarding experience profile will set this).
export function OrganTracker({ anatomy = "neutral" }: { anatomy?: Anatomy } = {}) {
  const [query, reload] = useBubblesQuery<BodySystemsResponse>("/intelligence/body-systems?days=90");
  const [picked, setPicked] = useState<string | null>(null);
  const [show3D, setShow3D] = useState(false);
  const [threeFailed, setThreeFailed] = useState(false);

  const systems = query.status === "ready" ? query.data.intelligence?.systems ?? [] : [];
  const withData = systems.filter((s) => s.status !== "unknown");
  const selected = systems.find((s) => s.organ === picked) ?? withData[0] ?? systems[0];

  return (
    <section aria-labelledby="body-systems-title" className={`${CARD} p-5 sm:p-7`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-label text-bubbles-grape-deep">Body systems · last 90 days</p>
          <h2 id="body-systems-title" className="mt-1 text-h2 text-ink">
            What your logs say about each system
          </h2>
          <p className="mt-2 text-body text-muted">
            Bubbles sorts your evidence by body system and shows where it is missing. It never says an organ is healthy or
            damaged. That&apos;s for your clinician.
          </p>
        </div>
        {systems.length > 0 && (
          <button
            type="button"
            aria-pressed={show3D}
            onClick={() => {
              setThreeFailed(false);
              setShow3D((v) => !v);
            }}
            className="bubbles-press inline-flex min-h-[44px] items-center gap-2 rounded-full bg-bubbles-grape px-5 text-body-sm font-extrabold text-white shadow-[0_5px_0_var(--bubbles-grape-deep)]"
          >
            {show3D ? "Hide 3D body" : "Show 3D body"}
          </button>
        )}
      </div>

      {query.status === "loading" && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3" role="status" aria-label="Loading body systems">
          {Array.from({ length: 9 }, (_, i) => (
            <Skeleton key={i} className="h-16 rounded-2xl" />
          ))}
        </div>
      )}

      {query.status === "error" && (
        <div className="mt-6">
          <ErrorCard title="Body systems didn't load" message={query.message} onRetry={reload} inset />
        </div>
      )}

      {query.status === "ready" && systems.length === 0 && (
        <p className="mt-6 rounded-3xl bg-blush p-5 text-body text-muted">Bubbles has no body-system view for you yet.</p>
      )}

      {query.status === "ready" && selected && (
        <>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className={`${PILL} bg-tint-grape text-bubbles-grape-deep`}>
              {withData.length} of {systems.length} systems have evidence
            </span>
            {(["needs_attention", "watch"] as const).map((status) => {
              const count = systems.filter((s) => s.status === status).length;
              return count ? (
                <span key={status} className={`${PILL} ${STATUS[status].pill}`}>
                  {count} {STATUS[status].label.toLowerCase()}
                </span>
              ) : null;
            })}
          </div>

          {withData.length === 0 && (
            <p className="mt-4 rounded-3xl bg-blush p-4 text-body-sm text-muted">
              No body-system evidence yet. Logging sleep, activity, vitals and lab results gives Bubbles something to work
              with. Until then every system stays &ldquo;not enough data&rdquo;, never &ldquo;fine&rdquo;.
            </p>
          )}

          {show3D && (
            <div className="mt-5 h-[380px] sm:h-[440px]">
              {threeFailed ? null : (
                <ThreeBoundary
                  onError={() => {
                    setThreeFailed(true);
                    setShow3D(false);
                  }}
                >
                  <Anatomy3D
                    selected={selected.organ}
                    anatomy={anatomy}
                    onSelect={setPicked}
                    organStatus={Object.fromEntries(systems.map((s) => [s.organ, s.status]))}
                  />
                </ThreeBoundary>
              )}
            </div>
          )}
          {threeFailed && (
            <p role="status" className="mt-4 text-body-sm font-bold text-muted">
              The 3D body couldn&apos;t start on this device, so here&apos;s the list instead.
            </p>
          )}

          <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <ul className="bubbles-stagger m-0 grid list-none content-start grid-cols-2 gap-3 p-0 xl:grid-cols-3" aria-label="Body systems">
              {systems.map((system) => {
                const isSelected = system.organ === selected.organ;
                const status = STATUS[system.status] ?? STATUS.unknown;
                return (
                  <li key={system.organ}>
                    <button
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => setPicked(system.organ)}
                      className={`bubbles-lift flex min-h-[64px] w-full items-center gap-3 rounded-2xl border-2 px-4 py-3 text-left ${
                        isSelected ? "border-bubbles-grape bg-tint-grape" : "border-line bg-surface hover:border-line-strong"
                      }`}
                    >
                      <span className={`h-3.5 w-3.5 shrink-0 rounded-full ${status.dot}`} aria-hidden="true" />
                      <span className="min-w-0">
                        <span className="block font-extrabold text-ink">{organLabel(system.organ, anatomy)}</span>
                        <span className="block text-[0.8125rem] font-bold text-muted">{status.label}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div aria-live="polite">
              <OrganDetail key={selected.organ} system={selected} anatomy={anatomy} />
            </div>
          </div>
        </>
      )}

      <p className="mt-5 text-body-sm text-muted">
        A pattern in your logs, not a diagnosis. Missing data lowers confidence. It is never read as &ldquo;all
        clear&rdquo;.
      </p>
    </section>
  );
}

function OrganDetail({ system, anatomy }: { system: OrganAssessment; anatomy: Anatomy }) {
  const status = STATUS[system.status] ?? STATUS.unknown;
  const evidence = Math.round((system.data_completeness ?? 0) * 100);
  const signals = system.signals ?? [];
  return (
    <div className="bubbles-rise rounded-3xl bg-blush p-5">
      <p className="text-label text-muted">Selected</p>
      <h3 className="mt-1 text-h3 text-ink">{organLabel(system.organ, anatomy)}</h3>
      <span className={`${PILL} mt-2 ${status.pill}`}>{status.label}</span>

      <div className="mt-4">
        <div className="flex justify-between text-body-sm font-bold text-ink-soft">
          <span>Evidence on file</span>
          <span>{evidence}%</span>
        </div>
        <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-surface" aria-hidden="true">
          <div className="h-full rounded-full bg-bubbles-grape" style={{ width: `${evidence}%` }} />
        </div>
        <p className="mt-1.5 text-[0.8125rem] font-bold text-muted">
          Confidence: {confidenceWord(system.confidence ?? 0)}
        </p>
      </div>

      {signals.length > 0 && (
        <div className="mt-4">
          <h4 className="text-body-sm font-extrabold text-ink">Signals Bubbles used</h4>
          <ul className="mt-2 space-y-2">
            {signals.slice(0, 4).map((signal) => (
              <li key={signal.factor + signal.direction} className="rounded-2xl bg-surface px-3 py-2 text-body-sm">
                <span className="font-bold text-ink">{humanize(signal.factor)}</span>
                <span className="block text-[0.8125rem] font-bold text-muted">{DIRECTION[signal.direction] ?? humanize(signal.direction)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {system.recommended_actions?.[0] && (
        <div className="mt-4">
          <h4 className="text-body-sm font-extrabold text-ink">What could help</h4>
          <p className="mt-1 text-body-sm text-muted">{system.recommended_actions[0]}</p>
        </div>
      )}

      <p className="mt-4 text-[0.8125rem] text-muted">
        {system.limitations?.[system.limitations.length - 1] ??
          "Bubbles needs more reliable data before saying anything stronger."}
      </p>
    </div>
  );
}
