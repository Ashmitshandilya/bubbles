"use client";

// Breathing and grounding catalogue with a timed breathing guide.

import { useState } from "react";
import { BTN_SECONDARY, PILL } from "../../components/hub/HubKit";
import { BreathingGuide } from "../../components/wellness/BreathingGuide";
import { Notice, Panel, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";
import type { Exercise } from "../../app/lib/wellness-types";

export function Calm() {
  const [data, reload] = useWellnessQuery<{ exercises: Exercise[]; note: string }>("/wellness/mind/exercises", { tz: false });
  return (
    <Panel id="calm" title="Calm space" kicker="Breathing and grounding">
      <QueryView query={data} onRetry={reload} what="the calm exercises">
        {(d) => (
          <>
            <Notice tone="info">{d.note}</Notice>
            <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
              {d.exercises.map((e) => (
                <ExerciseCard key={e.id} exercise={e} />
              ))}
            </ul>
          </>
        )}
      </QueryView>
    </Panel>
  );
}

function ExerciseCard({ exercise: e }: { exercise: Exercise }) {
  const [guide, setGuide] = useState(false);
  const breathing = e.kind === "breathing" && e.pattern;
  return (
    <li className="flex flex-col gap-3 rounded-2xl border-2 border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0 font-display text-h4 text-default">{e.name}</h3>
        <span className={`${PILL} ${breathing ? "bg-tint-sky text-bubbles-sky-deep" : "bg-tint-mint text-bubbles-mint-deep"}`}>
          {breathing ? "Breathing" : "Grounding"} · about {e.minutes} min
        </span>
      </div>
      <ol className="m-0 list-decimal space-y-1 pl-5 text-body-sm text-ink-soft">
        {e.steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      {breathing && (
        <>
          <button type="button" aria-expanded={guide} onClick={() => setGuide((v) => !v)} className={`${BTN_SECONDARY} self-start`}>
            {guide ? "Close the guide" : "Open the timed guide"}
          </button>
          {guide && <BreathingGuide exercise={e} />}
        </>
      )}
    </li>
  );
}
