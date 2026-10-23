"use client";

import { useEffect, useState } from "react";
import { HubPage } from "../../components/hub/HubKit";
import { Page, Section } from "../../components/pearl";
import { clearPlan, dial, loadPlan, readHarbor, SAFETY_PLAN_ITEMS, savePlan } from "./orbit";
import { useOrbitCall } from "./OrbitKit";

/** Feeling unsafe at home: plain, calm, no mascot, no colour tags. Numbers you can tap, and a safety plan that stays in this browser. */
export function HarborClient() {
  const call = useOrbitCall();
  const [harbor, setHarbor] = useState<ReturnType<typeof readHarbor>>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setChecked(loadPlan(typeof window === "undefined" ? undefined : window.localStorage));
    call("/orbit/harbor")
      .then(({ json }) => {
        const h = readHarbor(json);
        if (h) setHarbor(h);
        else setFailed(true);
      })
      .catch(() => setFailed(true));
  }, [call]);

  function toggle(id: string) {
    const next = checked.includes(id) ? checked.filter((x) => x !== id) : [...checked, id];
    setChecked(next);
    savePlan(window.localStorage, next);
  }

  return (
    <HubPage title="Feeling unsafe at home?">
      <Page eyebrow="Help" title="Feeling unsafe at home?" lede="You do not have to explain anything here. These lines are free and private.">
        <Section label="People who can help">
          {failed && <p className="pearl-error" role="alert">The list did not load. If you are in danger, call your local emergency number now.</p>}
          {harbor && (
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {harbor.resources.map((r) => (
                <li key={`${r.name}-${r.number}`} style={{ padding: "14px 0", borderBottom: "1px solid var(--hairline)" }}>
                  <strong>{r.name}</strong>
                  {dial(r.number) ? (
                    <a href={`tel:${dial(r.number)}`} className="pearl-btn" style={{ marginLeft: 12 }}>Call {r.number}</a>
                  ) : r.number ? (
                    <span style={{ marginLeft: 12 }}>{r.number}</span>
                  ) : null}
                  {r.note && <span style={{ display: "block", color: "var(--ink-soft)", marginTop: 4 }}>{r.note}</span>}
                </li>
              ))}
            </ul>
          )}
          {harbor?.note && <p className="pearl-note">{harbor.note}</p>}
        </Section>
        <Section label="A safety plan">
          <p className="pearl-note" style={{ marginTop: 0 }}>Tick what you have done. This list stays only in this browser. It is not sent anywhere or saved to your account.</p>
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {SAFETY_PLAN_ITEMS.map((item) => (
              <li key={item.id} style={{ padding: "6px 0" }}>
                <label style={{ display: "flex", gap: 12, alignItems: "flex-start", minHeight: 44, cursor: "pointer" }}>
                  <input type="checkbox" checked={checked.includes(item.id)} onChange={() => toggle(item.id)} style={{ width: 22, height: 22, marginTop: 2 }} />
                  <span>{item.text}</span>
                </label>
              </li>
            ))}
          </ul>
          <p style={{ marginTop: 12 }}>
            <button type="button" className="pearl-link" onClick={() => { clearPlan(window.localStorage); setChecked([]); }}>Clear this list from this browser</button>
          </p>
        </Section>
      </Page>
    </HubPage>
  );
}
