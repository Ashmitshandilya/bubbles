"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "../../../components/Providers";
import { ErrorCard, HubPage, Skeleton } from "../../../components/hub/HubKit";
import { Gap, Lede, Row, Rows, Section } from "../../../components/pearl";
import { changeBody, readOverview, type ConsentPurpose } from "../../lib/consents";
import { describePlacement, formProblems, readPlaces, readStars, saveBody, type PlaceHit, type Stars } from "./stars";

export function StarsClient() {
  return (
    <HubPage title="Stars lens">
      <StarsLens />
    </HubPage>
  );
}

function StarsLens() {
  const { fetchBubbles } = useApi();
  const [stars, setStars] = useState<Stars | null>(null);
  const [purpose, setPurpose] = useState<ConsentPurpose | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const [s, c] = await Promise.all([fetchBubbles("/me/stars"), fetchBubbles("/consents")]);
      const next = s.ok ? readStars(await s.json()) : null;
      const overview = c.ok ? readOverview(await c.json()) : null;
      if (!next || !overview) throw new Error("stars");
      setStars(next);
      setPurpose(overview.purposes.find((p) => p.id === "stars_lens") ?? null);
    } catch {
      setFailed(true);
    }
  }, [fetchBubbles]);

  useEffect(() => {
    void load();
  }, [load]);

  async function decide(granted: boolean) {
    if (!purpose) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await fetchBubbles(`/consents/${purpose.id}`, { method: "PUT", body: changeBody(purpose, granted, "settings") });
      if (!res.ok) throw new Error("consent");
      setEditing(false);
      await load();
    } catch {
      setProblem("That did not save. Nothing changed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function turnOff() {
    setBusy(true);
    setProblem(null);
    try {
      const res = await fetchBubbles("/me/stars", { method: "DELETE" });
      if (!res.ok) throw new Error("off");
      await load();
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <ErrorCard title="Couldn't load the Stars lens" message="Check your connection and try again." onRetry={() => void load()} />;
  if (!stars) return <Skeleton className="h-48 rounded-3xl" />;

  return (
    <div className="pearl-page" style={{ padding: 0 }}>
      <p className="pearl-eyebrow">Me</p>
      <h1 className="pearl-title">Stars lens</h1>
      <Lede>{stars.intro}</Lede>
      {problem && <p role="alert" className="pearl-error">{problem}</p>}

      {!stars.consent && (
        <Section label="Off for now">
          <p className="m-0 text-body text-ink-soft">{purpose?.description ?? "Lets Bubbles keep your birth details to show a traditional lens."}</p>
          <p className="pearl-note">It never predicts anything and is never used for health, safety or relationship decisions. Controlled studies find that charts do not predict personality, so Bubbles only uses it to choose words, and only where your own history agrees.</p>
          <p style={{ marginTop: 16 }}><button type="button" className="pearl-btn primary" disabled={busy || !purpose} onClick={() => void decide(true)}>{busy ? "Saving…" : "Turn on the Stars lens"}</button></p>
        </Section>
      )}

      {stars.consent && (!stars.enabled || editing) && <BirthForm initial={stars} onSaved={async () => { setEditing(false); await load(); }} onCancel={stars.enabled ? () => setEditing(false) : undefined} />}

      {stars.consent && stars.enabled && !editing && (
        <>
          <Section label="Your lens">
            <Rows>
              <Row label={describePlacement("Moon", stars.moon)} />
              <Row label={describePlacement("Sun", stars.sun)} />
              <Row label={describePlacement("Ascendant", stars.timeKnown ? stars.ascendant : null)} />
            </Rows>
            {stars.birth && <p className="pearl-note">Born {stars.birth.date}{stars.birth.time ? ` at ${stars.birth.time}` : ", time not known"}{stars.birth.place ? `, ${stars.birth.place}` : ""}.</p>}
          </Section>

          <Section label="Traditional words, checked against what Bubbles has seen">
            {stars.items.length === 0 ? <Gap>No words to show.</Gap> : (
              <ul className="m-0 list-none p-0">
                {stars.items.map((item) => (
                  <li key={item.id} className="border-b border-[color:var(--hairline)] py-3">
                    <p className="m-0 font-display text-lg">{item.text}</p>
                    <p className="pearl-note" style={{ margin: "2px 0 0" }}>{item.source}{item.uncertain ? " (one of two it could be)" : ""} · <strong>{item.match}</strong></p>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          <p style={{ marginTop: 24 }}>
            <button type="button" className="pearl-btn" onClick={() => setEditing(true)}>Change my details</button>{" "}
            <button type="button" className="pearl-btn" disabled={busy} onClick={() => void turnOff()}>Turn off and delete my birth details</button>
          </p>
          <p className="pearl-note">Turning it off deletes your birth date, time and place, and removes what the lens added to how Bubbles understands you.</p>
        </>
      )}
    </div>
  );
}

function BirthForm({ initial, onSaved, onCancel }: { initial: Stars; onSaved: () => Promise<void>; onCancel?: () => void }) {
  const { fetchBubbles } = useApi();
  const [date, setDate] = useState(initial.birth?.date ?? "");
  const [time, setTime] = useState(initial.birth?.time ?? "");
  const [timeUnknown, setTimeUnknown] = useState(initial.birth ? initial.birth.time === null : false);
  const [query, setQuery] = useState(initial.birth?.place ?? "");
  const [places, setPlaces] = useState<PlaceHit[]>([]);
  const [placeId, setPlaceId] = useState<string | null>(null);
  const [errors, setErrors] = useState<ReturnType<typeof formProblems>>({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (placeId || query.trim().length < 2) {
      setPlaces([]);
      return;
    }
    let alive = true;
    const timer = window.setTimeout(async () => {
      try {
        const res = await fetchBubbles(`/me/stars/places?q=${encodeURIComponent(query.trim())}`);
        if (alive && res.ok) setPlaces(readPlaces(await res.json()));
      } catch {
        /* the list simply stays empty */
      }
    }, 250);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [query, placeId, fetchBubbles]);

  async function submit() {
    const values = { date, time, timeUnknown, placeId };
    const found = formProblems(values);
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    setProblem(null);
    try {
      const res = await fetchBubbles("/me/stars", { method: "PUT", body: saveBody(values) });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setProblem(typeof body?.detail === "string" ? body.detail : "That did not save. Please try again.");
        return;
      }
      await onSaved();
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section label="Your birth details">
      <label className="pearl-label" htmlFor="stars-date">Birth date</label>
      <input id="stars-date" type="date" className="pearl-field" value={date} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} aria-invalid={Boolean(errors.date)} />
      {errors.date && <p role="alert" className="pearl-error">{errors.date}</p>}

      <label className="pearl-label" htmlFor="stars-time">Birth time</label>
      <input id="stars-time" type="time" className="pearl-field" value={time} disabled={timeUnknown} onChange={(e) => setTime(e.target.value)} aria-invalid={Boolean(errors.time)} />
      <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, minHeight: 44 }}>
        <input type="checkbox" checked={timeUnknown} onChange={(e) => setTimeUnknown(e.target.checked)} /> I do not know my birth time
      </label>
      {errors.time && <p role="alert" className="pearl-error">{errors.time}</p>}

      <label className="pearl-label" htmlFor="stars-place">Birth place</label>
      <input id="stars-place" type="text" className="pearl-field" value={query} autoComplete="off" placeholder="Start typing a city" onChange={(e) => { setQuery(e.target.value); setPlaceId(null); }} aria-invalid={Boolean(errors.place)} />
      {places.length > 0 && (
        <ul className="m-0 list-none p-0" aria-label="Matching places">
          {places.map((p) => (
            <li key={p.id}>
              <button type="button" className="pearl-row" onClick={() => { setPlaceId(p.id); setQuery(p.name); setPlaces([]); }}>
                <span className="pearl-row-label">{p.name}</span><span className="pearl-row-value">{p.region === p.country ? p.country : `${p.region}, ${p.country}`}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {errors.place && <p role="alert" className="pearl-error">{errors.place}</p>}
      <p className="pearl-note">The list covers Indian cities of about 100,000 people or more and world capitals. If yours is missing, pick the nearest one. Nothing leaves Bubbles to look it up.</p>

      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      <p style={{ marginTop: 20 }}>
        <button type="button" className="pearl-btn primary" disabled={busy} onClick={() => void submit()}>{busy ? "Saving…" : "Show my lens"}</button>{" "}
        {onCancel && <button type="button" className="pearl-btn" onClick={onCancel}>Cancel</button>}
      </p>
    </Section>
  );
}
