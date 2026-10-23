"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useApi } from "../../components/Providers";
import { HubPage, ErrorCard, Skeleton } from "../../components/hub/HubKit";
import { Gap, Row, Rows, Section, Sheet, TwoBubbles } from "../../components/pearl";
import { ORBIT_LABEL } from "../../components/Navigation";
import { CARED_OPTIONS, CONFLICT_OPTIONS, ledeFor, readHome, STATUS_OPTIONS, type OrbitHome } from "./orbit";
import { useOrbitCall } from "./OrbitKit";

export function OrbitHomeClient() {
  return (
    <HubPage title={ORBIT_LABEL}>
      <Home />
    </HubPage>
  );
}

function Home() {
  const call = useOrbitCall();
  const router = useRouter();
  const { dataVersion } = useApi();
  const [home, setHome] = useState<OrbitHome | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const { json } = await call("/orbit");
      const next = readHome(json);
      if (next) setHome(next);
      else setFailed(true);
    } catch {
      setFailed(true);
    }
  }, [call]);

  useEffect(() => {
    void load();
  }, [load, dataVersion]);

  if (failed) return <ErrorCard title="Orbit did not load" message="Check your connection and try again." onRetry={() => void load()} />;
  if (!home) return <Skeleton className="h-64 w-full" />;

  const asked = home.profile.status !== null;
  return (
    <div className="pearl-page pearl-rise">
      <div className="dusk" style={{ borderRadius: "var(--pearl-radius-l)", padding: "22px 22px 26px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <p className="pearl-eyebrow">{ORBIT_LABEL}</p>
          <button type="button" className="pearl-link" onClick={() => router.replace("/dashboard")}>Hide</button>
        </div>
        <TwoBubbles other={home.partnerName} paired={home.paired} />
        <p className="pearl-lede" style={{ color: "var(--dusk-text)" }}>{ledeFor(home)}</p>
      </div>

      {!asked ? (
        <FirstVisit onSaved={() => void load()} />
      ) : (
        <>
          <Section label="Together">
            <Rows>
              <Row label="Heart-to-heart" href="/orbit/talk" value="Talk it through" />
              <Row label="Help me reply" href="/orbit/reply" value="Find the words" />
              <Row label="Before I text them" href="/orbit/text" value="Pause, then say it softly" />
              <Row label="Today's question" href="/orbit/ritual" value={home.question.answered ? "Answered" : "Waiting"} />
              <Row label="After a fight" href="/orbit/fight" value="Repair" />
              <Row label="Understand them" href="/orbit/map" />
            </Rows>
          </Section>
          <Section label="You">
            <Rows>
              <Row label="About you in relationships" onClick={() => setEditing(true)} />
              <Row label="Partner connection" href="/partner" value={home.paired ? `Connected with ${home.partnerName ?? "your partner"}` : "Not connected"} />
              <Row label="How Bubbles understands you" href="/profile/understanding" />
            </Rows>
            {home.weatherPaused && <Gap>Gentle nudges to your partner are paused for now. Nothing changes on their side.</Gap>}
          </Section>
        </>
      )}

      <p style={{ marginTop: 40 }}>
        <Link href="/orbit/harbor" className="pearl-link">Feeling unsafe at home?</Link>
      </p>

      <Sheet open={editing} onClose={() => setEditing(false)} title="About you in relationships">
        <ProfileForm initial={home} onSaved={() => { setEditing(false); void load(); }} />
      </Sheet>
    </div>
  );
}

function FirstVisit({ onSaved }: { onSaved: () => void }) {
  return (
    <Section label="Where are you right now?">
      <p className="pearl-note">Pick what fits. You can change it any time, and Orbit works whatever you choose.</p>
      <ProfileForm initial={null} onSaved={onSaved} />
    </Section>
  );
}

function ProfileForm({ initial, onSaved }: { initial: OrbitHome | null; onSaved: () => void }) {
  const call = useOrbitCall();
  const [status, setStatus] = useState<string | null>(initial?.profile.status ?? null);
  const [cared, setCared] = useState<string[]>(initial?.profile.caredForBy ?? []);
  const [conflict, setConflict] = useState<string | null>(initial?.profile.conflictStyle ?? null);
  const [word, setWord] = useState(initial?.profile.partnerWord ?? "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setProblem(null);
    try {
      const { status: code, json } = await call("/orbit/profile", "PUT", { status, cared_for_by: cared, conflict_style: conflict, partner_word: word });
      if (code === 200 && (json as { status?: string } | null)?.status === "success") onSaved();
      else setProblem("That did not save. Please try again.");
    } catch {
      setProblem("That did not save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="pearl-chips" role="group" aria-label="Relationship status">
        {STATUS_OPTIONS.map((o) => (
          <button key={o.id} type="button" className="pearl-chip" aria-pressed={status === o.id} onClick={() => setStatus(o.id)}>{o.label}</button>
        ))}
      </div>
      <label className="pearl-label" htmlFor="partner-word">What do you call them? (optional)</label>
      <input id="partner-word" className="pearl-field" value={word} maxLength={20} onChange={(e) => setWord(e.target.value)} placeholder="my partner, my wife, my boyfriend" />
      <p className="pearl-label">What makes you feel cared for? (optional)</p>
      <div className="pearl-chips" role="group" aria-label="Feeling cared for">
        {CARED_OPTIONS.map((o) => (
          <button key={o.id} type="button" className="pearl-chip" aria-pressed={cared.includes(o.id)} onClick={() => setCared((c) => (c.includes(o.id) ? c.filter((x) => x !== o.id) : [...c, o.id]))}>{o.label}</button>
        ))}
      </div>
      <p className="pearl-label">In a disagreement, you tend to (optional)</p>
      <div className="pearl-chips" role="group" aria-label="In a disagreement">
        {CONFLICT_OPTIONS.map((o) => (
          <button key={o.id} type="button" className="pearl-chip" aria-pressed={conflict === o.id} onClick={() => setConflict(conflict === o.id ? null : o.id)}>{o.label}</button>
        ))}
      </div>
      {problem && <p role="alert" className="pearl-error">{problem}</p>}
      <p style={{ marginTop: 24 }}>
        <button type="button" className="pearl-btn primary" disabled={busy || !status} onClick={() => void save()}>{busy ? "Saving…" : "Save"}</button>
      </p>
    </div>
  );
}
