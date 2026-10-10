"use client";

import { useEffect, useRef, useState } from "react";

/* Real, working mini versions of the product screens. They use example data and say so. */

/* ---------- chat ---------- */

type Source = { label: string; href: string };
type Example = { ask: string; short: string; reply: string[]; sources: Source[] };

const EXAMPLES: Example[] = [
  {
    ask: "Mujhe 3 din se sar dard hai aur neend kam aa rahi hai",
    short: "Headache and poor sleep",
    reply: [
      "That sounds draining. Poor sleep and headaches often feed each other, so it helps to look at both together.",
      "Note when the headache starts and how long you slept the night before. I can show you that link in your own logs.",
      "If the headache is sudden and severe, or comes with weakness, confusion or trouble speaking, get urgent care now.",
    ],
    sources: [
      { label: "NHS: Headaches", href: "https://www.nhs.uk/symptoms/headaches/" },
      { label: "MedlinePlus: Insomnia", href: "https://medlineplus.gov/insomnia.html" },
    ],
  },
  {
    ask: "My period is 6 days late",
    short: "A late period",
    reply: [
      "A late period has many common causes, including stress, travel, illness and a change in routine. Pregnancy is worth ruling out first if it could apply.",
      "One late cycle is common. If it keeps happening, or you also have severe pain, tell a clinician.",
    ],
    sources: [
      { label: "NHS: Periods", href: "https://www.nhs.uk/conditions/periods/" },
      { label: "NHS: Missed or late periods", href: "https://www.nhs.uk/symptoms/missed-or-late-periods/" },
    ],
  },
  {
    ask: "I feel tired all the time",
    short: "Constant tiredness",
    reply: [
      "Tiredness has many causes: poor sleep, stress, low iron, thyroid changes and low mood among them. I can't tell which one applies to you, but your logs can narrow it down.",
      "If you also have heavy periods, breathlessness or paleness, mention it to a clinician. A simple blood test can check.",
    ],
    sources: [
      { label: "MedlinePlus: Fatigue", href: "https://medlineplus.gov/fatigue.html" },
      { label: "NHS: Iron deficiency anaemia", href: "https://www.nhs.uk/conditions/iron-deficiency-anaemia/" },
    ],
  },
];

export function ChatPreview() {
  const [index, setIndex] = useState(0);
  const [typing, setTyping] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const pick = (i: number) => {
    if (i === index && !typing) return;
    if (timer.current) clearTimeout(timer.current);
    setIndex(i);
    setTyping(true);
    timer.current = setTimeout(() => setTyping(false), 1000);
  };
  const ex = EXAMPLES[index];

  return (
    <div className="lp-pv" role="group" aria-label="Example conversation with Bubbles">
      <div className="lp-chips" role="group" aria-label="Pick an example question">
        {EXAMPLES.map((e, i) => (
          <button key={e.short} type="button" className="lp-chip" aria-pressed={i === index} onClick={() => pick(i)}>
            {e.short}
          </button>
        ))}
      </div>
      <div className="lp-chat" aria-live="polite">
        <div className="lp-msg lp-msg--me">{ex.ask}</div>
        <div className="lp-msg lp-msg--bot">
          {typing ? (
            <span className="lp-typing" role="status" aria-label="Bubbles is replying">
              <i /><i /><i />
            </span>
          ) : (
            <>
              {ex.reply.map((p) => (
                <p key={p}>{p}</p>
              ))}
              <div className="lp-src">
                {ex.sources.map((s) => (
                  <a key={s.href} href={s.href} target="_blank" rel="noopener noreferrer">
                    {s.label}
                  </a>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
      <p className="lp-pv__note">Example conversation. The sources are real pages you can open.</p>
    </div>
  );
}

/* ---------- patterns ---------- */

const SLEEP = [6.2, 7.5, 5.8, 8.1, 7.0, 6.4, 8.4, 5.5, 7.8, 6.9, 8.0, 6.1, 7.3, 8.2];
const MOOD = [5, 7, 4, 8, 6, 5, 8, 4, 7, 6, 8, 5, 6, 8];

function Bars({ values, max, alt }: { values: number[]; max: number; alt?: boolean }) {
  return (
    <div className={`lp-bars ${alt ? "lp-bars--b" : ""}`} aria-hidden="true">
      {values.map((v, i) => (
        <i key={i} style={{ height: `${Math.round((v / max) * 100)}%` }} />
      ))}
    </div>
  );
}

export function PatternsPreview() {
  return (
    <div className="lp-pv" role="group" aria-label="Example of links between logged sleep and mood">
      <div className="lp-link">
        <div className="lp-link__meta">
          <span className="lp-pill">moderate link</span>
          <span className="lp-pill lp-pill--ok">seen in two periods</span>
          <span className="lp-pv__note">42 days</span>
        </div>
        <p>On days after you slept longer, your logged mood tended to be higher.</p>
        <Bars values={SLEEP} max={9} />
        <Bars values={MOOD} max={10} alt />
        <details>
          <summary>Things to keep in mind</summary>
          <p>
            This is an association in your own logs. It does not show that one thing causes the other, and other things that changed on the same days are not
            accounted for.
          </p>
        </details>
      </div>
      <div className="lp-link">
        <div className="lp-link__meta">
          <span className="lp-pill">weak link</span>
          <span className="lp-pv__note">31 days</span>
        </div>
        <p>After days you were active for longer, your next sleep rating tended to be better.</p>
      </div>
      <p className="lp-pv__note">Example data. A link only appears when it is clear and repeated enough to trust.</p>
    </div>
  );
}

/* ---------- cycle ---------- */

export function CyclePreview() {
  return (
    <div className="lp-pv" role="group" aria-label="Example of the cycle view">
      <div className="lp-cycle">
        <div className="lp-ring" style={{ ["--p" as string]: 50 }}>
          <div>
            <strong>Day 14</strong>
            <span>of about 28</span>
          </div>
        </div>
        <span className="lp-pill lp-pill--ok">Fertile window, estimated</span>
        <p className="lp-cycle__range">Your next period is expected in 12 to 16 days. Bubbles shows a range because bodies are not clocks.</p>
      </div>
      <p className="lp-pv__note">Example data. Predictions are estimates, never a medical result.</p>
    </div>
  );
}

/* ---------- partner sharing ---------- */

const SHARE_ITEMS = [
  { id: "cycle", title: "Cycle estimate", hint: "With gentle tips for them" },
  { id: "sleep", title: "Sleep average", hint: "Seven nights, no detail" },
  { id: "note", title: "A note from you", hint: "Something you want them to know" },
];

export function PartnerPreview() {
  const [on, setOn] = useState<Record<string, boolean>>({ cycle: true, sleep: false, note: true });
  const count = Object.values(on).filter(Boolean).length;
  const toggle = (id: string) => setOn((prev) => ({ ...prev, [id]: !prev[id] }));

  return (
    <div className="lp-pv" role="group" aria-label="Example of partner sharing settings">
      {SHARE_ITEMS.map((item) => (
        <div key={item.id} className="lp-toggle">
          <div>
            <strong id={`lp-sw-${item.id}`}>{item.title}</strong>
            <small>{item.hint}</small>
          </div>
          <button type="button" role="switch" aria-checked={on[item.id]} aria-labelledby={`lp-sw-${item.id}`} className="lp-switch" onClick={() => toggle(item.id)} />
        </div>
      ))}
      <p className="lp-partner__sum" role="status">
        {count === 0 ? "Nothing is shared." : `Your partner would see ${count} ${count === 1 ? "thing" : "things"}. Never your chats, symptoms, medicines or lab results.`}
      </p>
      <div className="lp-hero__cta">
        <button type="button" className="lp-btn lp-btn--quiet lp-btn--sm" onClick={() => setOn({ cycle: false, sleep: false, note: false })}>
          Stop sharing
        </button>
      </div>
      <p className="lp-pv__note">Try the switches. Sharing is off until you turn it on.</p>
    </div>
  );
}
