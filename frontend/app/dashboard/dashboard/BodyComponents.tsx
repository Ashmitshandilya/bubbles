"use client";

import Anatomy3D from "../../../components/Anatomy3D";

export interface OrganSystem {
  organ: string;
  status: "unknown" | "no_major_risk_signal" | "watch" | "needs_attention";
  score?: number | null;
  data_completeness?: number;
  confidence?: number;
  signals?: Array<{ factor: string; direction: string }>;
  limitations?: string[];
}

export interface OrganData {
  systems: OrganSystem[];
  systems_with_data?: number;
  total_systems?: number;
}

const ORGAN_LABELS: Record<string, string> = {
  brain: "Brain", heart: "Heart", lungs: "Lungs", liver: "Liver", kidneys: "Kidneys",
  pancreas: "Pancreas", digestive_system: "Digestive", reproductive_system: "Reproductive",
  musculoskeletal_system: "Musculoskeletal",
};

const STATUS_PILL: Record<OrganSystem["status"], string> = {
  no_major_risk_signal: "bg-tint-mint text-bubbles-mint-deep",
  watch: "bg-tint-sun text-bubbles-sun-deep",
  needs_attention: "bg-tint-urgent text-bubbles-urgent",
  unknown: "border-2 border-dashed border-line-strong text-ink-soft",
};

const STATUS_TEXT: Record<OrganSystem["status"], string> = {
  no_major_risk_signal: "No major risk signal",
  watch: "Worth watching",
  needs_attention: "Needs attention",
  unknown: "Not enough data",
};

/** Body-system evidence panel (previously shared with /health). Organises evidence; it does not measure organ health. */
export function OrganPanel({
  data,
  selected,
  onSelect,
  loading,
}: {
  data: OrganData | null;
  selected: string;
  onSelect: (id: string) => void;
  loading: boolean;
}) {
  const systems = Array.isArray(data?.systems) ? data.systems : [];
  const selectedRow = systems.find((s) => s.organ === selected);
  const status = selectedRow?.status ?? "unknown";
  const completeness = Math.round((selectedRow?.data_completeness ?? 0) * 100);

  return (
    <section className="flex flex-col gap-5 rounded-[24px] border-2 border-line bg-surface p-5 sm:p-6" aria-labelledby="organ-panel-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="organ-panel-title" className="m-0 font-display text-[1.375rem] font-semibold">Your body map</h2>
          <p className="m-0 text-[0.9375rem] text-ink-soft">Where Bubbles has evidence, where it has gaps, and what may deserve a closer look.</p>
        </div>
        <span className="rounded-full bg-tint-grape px-3 py-1.5 text-chip font-extrabold text-bubbles-grape-deep" aria-live="polite">
          {loading ? "Updating…" : `${data?.systems_with_data ?? 0} of ${data?.total_systems ?? 9} with data`}
        </span>
      </div>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
        <div className="relative min-h-[420px] overflow-hidden rounded-[20px] border-2 border-line bg-blush sm:min-h-[560px]">
          <Anatomy3D
            onSelect={onSelect}
            organStatus={Object.fromEntries(systems.map((sys) => [sys.organ, sys.status ?? "unknown"]))}
          />
        </div>
        <div className="flex flex-col gap-4 rounded-[20px] bg-blush p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="m-0 font-display text-2xl font-semibold">{ORGAN_LABELS[selected] ?? selected}</h3>
            <span className={`rounded-full px-3 py-1 text-xs font-extrabold ${STATUS_PILL[status] ?? STATUS_PILL.unknown}`}>{STATUS_TEXT[status] ?? STATUS_TEXT.unknown}</span>
          </div>
          <p className="m-0 text-[0.9375rem] font-bold text-bubbles-grape-deep">
            {selectedRow?.score == null ? "Not enough evidence yet" : `${selectedRow.score} risk-context index`}
            <span className="block text-sm font-semibold text-ink-soft">This is not an organ-health percentage.</span>
          </p>
          <div>
            <div className="h-2 overflow-hidden rounded-full bg-surface" role="img" aria-label={`Evidence completeness ${completeness}%`}>
              <span className="block h-full rounded-full bg-bubbles-grape" style={{ width: `${completeness}%` }} />
            </div>
            <p className="m-0 mt-2 text-chip font-semibold text-ink-soft">
              Evidence completeness {completeness}% · confidence {Math.round((selectedRow?.confidence ?? 0) * 100)}%
            </p>
          </div>
          {(selectedRow?.signals ?? []).length > 0 && (
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              {(selectedRow?.signals ?? []).slice(0, 4).map((signal) => (
                <li key={`${signal.factor}-${signal.direction}`} className="flex justify-between gap-4 rounded-2xl bg-surface px-3 py-2.5">
                  <span className="text-sm capitalize text-ink-soft">{signal.factor.replaceAll("_", " ")}</span>
                  <b className="text-xs font-extrabold uppercase text-bubbles-grape-deep">{signal.direction}</b>
                </li>
              ))}
            </ul>
          )}
          <p className="m-0 rounded-2xl bg-surface px-4 py-3 text-sm leading-relaxed text-ink-soft">
            {selectedRow?.limitations?.[0] ?? "Bubbles needs more reliable data before drawing a stronger conclusion."}
          </p>
        </div>
      </div>
    </section>
  );
}
