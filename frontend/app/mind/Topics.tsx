"use client";

// Anxiety, panic, loneliness and missing someone: short kind copy from the server, closed until tapped. Static text, no labels.

import Link from "next/link";
import { Fold } from "../../components/tracking/kit";
import { BTN_SECONDARY } from "../../components/hub/HubKit";
import { Panel, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery } from "../../components/wellness/useWellness";

interface Topic {
  title: string;
  body: string;
  tool: string;
}

export function Topics() {
  const [data, reload] = useWellnessQuery<{ topics: Record<string, Topic> }>("/wellness/mind/topics", { tz: false });
  return (
    <Panel id="topics" title="When it feels like a lot" kicker="Tap one">
      <QueryView query={data} onRetry={reload} what="these tips">
        {(d) => (
          <div className="flex flex-col gap-2">
            {Object.entries(d.topics).map(([id, t]) => (
              <Fold key={id} title={t.title}>
                <p className="m-0 text-body text-ink-soft">{t.body}</p>
                <a href={t.tool === "journal" ? "#journal" : "#calm"} className={`${BTN_SECONDARY} mt-3 inline-flex`}>
                  {t.tool === "journal" ? "Open my journal" : "Open a calming exercise"}
                </a>
              </Fold>
            ))}
            <Link href="/body?organ=brain" className={`${BTN_SECONDARY} self-start`}>See the brain on the body map</Link>
          </div>
        )}
      </QueryView>
    </Panel>
  );
}
