"use client";

// One tap from the Mind page: calm words, a longer-exhale breathing guide that starts at once, and the support line. No mascot (this is a hard moment).

import { useEffect, useRef } from "react";
import { BTN_SECONDARY } from "../../components/hub/HubKit";
import { BreathingGuide } from "../../components/wellness/BreathingGuide";
import { Notice, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";
import type { Exercise, MindOverview } from "../../app/lib/wellness-types";
import { CRISIS_NOTE } from "./copy";

export function PanicFlow({ copy, onClose }: { copy: MindOverview["support"]["panic"]; onClose: () => void }) {
  const [data, reload] = useWellnessQuery<{ exercises: Exercise[] }>("/wellness/mind/exercises", { tz: false });
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
    heading.current?.scrollIntoView({ block: "center" });
  }, []);
  return (
    <section aria-labelledby="panic-title" className="flex flex-col gap-4 rounded-[24px] border border-line bg-tint-sky p-5 sm:p-6">
      <h2 id="panic-title" ref={heading} tabIndex={-1} className="m-0 font-display text-h3 text-default outline-none">
        {copy.text}
      </h2>
      <QueryView query={data} onRetry={reload} what="the breathing guide">
        {(d) => {
          const longer = d.exercises.find((e) => e.kind === "breathing") ?? d.exercises[0];
          return longer ? <BreathingGuide exercise={longer} autoStart /> : null;
        }}
      </QueryView>
      <ol className="m-0 list-decimal space-y-1 pl-5 text-body-sm text-ink-soft">
        {copy.steps.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      <Notice tone="calm">{CRISIS_NOTE}</Notice>
      <button type="button" onClick={onClose} className={`${BTN_SECONDARY} self-start`}>
        I feel a bit better
      </button>
    </section>
  );
}
