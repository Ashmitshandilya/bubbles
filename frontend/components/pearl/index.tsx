"use client";

// Pearl Journal components (renovation plan 10.3). The page is the surface: grouping comes from spacing, type and hairlines. A box is used
// only for a sheet, an input or an urgent notice. Styles live in app/tokens.css (.pearl-*).

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { describeBubble, layoutBubbles, type BubbleSignal } from "../../app/lib/bubbles-layout";

export function Page({ eyebrow, title, lede, wide = false, children }: { eyebrow?: string; title?: string; lede?: string; wide?: boolean; children?: ReactNode }) {
  return (
    <div className={`pearl-page pearl-rise${wide ? " wide" : ""}`}>
      {eyebrow && <p className="pearl-eyebrow">{eyebrow}</p>}
      {title && <h1 className="pearl-title">{title}</h1>}
      {lede && <Lede>{lede}</Lede>}
      {children}
    </div>
  );
}

/** The one-sentence Bubbles voice line. */
export function Lede({ children }: { children: ReactNode }) {
  return <p className="pearl-lede">{children}</p>;
}

/** An unboxed group with a small-caps label. */
export function Section({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <section className="pearl-section" aria-label={label}>
      {label && <p className="pearl-eyebrow">{label}</p>}
      {children}
    </section>
  );
}

export function Rows({ children }: { children: ReactNode }) {
  return <ul className="pearl-rows">{children}</ul>;
}

const Chevron = () => (
  <svg className="pearl-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 6l6 6-6 6" />
  </svg>
);

/** A tappable line: label, quiet value, chevron; hairline below. Pass `href` for a link or `onClick` for an action. */
export function Row({ label, value, href, onClick, hint }: { label: string; value?: string; href?: string; onClick?: () => void; hint?: string }) {
  const inner = (
    <>
      <span className="pearl-row-label">{label}{hint ? <span className="sr-only">. {hint}</span> : null}</span>
      {value && <span className="pearl-row-value">{value}</span>}
      <Chevron />
    </>
  );
  return (
    <li>
      {href ? (
        <Link href={href} className="pearl-row">{inner}</Link>
      ) : (
        <button type="button" className="pearl-row" onClick={onClick}>{inner}</button>
      )}
    </li>
  );
}

/** The honest "nothing here yet" state, with at most one action. */
export function Gap({ children }: { children: ReactNode }) {
  return <p className="pearl-gap">{children}</p>;
}

/** A draft or a note, set like a quotation. */
export function Quote({ tone, children, why }: { tone?: string; children: ReactNode; why?: string }) {
  return (
    <blockquote className="pearl-quote">
      {tone && <p className="pearl-quote-tone">{tone}</p>}
      <p className="pearl-quote-text">{children}</p>
      {why && <p className="pearl-quote-why">{why}</p>}
    </blockquote>
  );
}

/** A single quiet confirmation line ("Noted: slept 6h"). */
export function InlineNote({ children }: { children: ReactNode }) {
  return <p className="pearl-note" role="status">{children}</p>;
}

export function Field({ id, label, value, onChange, rows = 3, maxLength, placeholder }: { id: string; label: string; value: string; onChange: (v: string) => void; rows?: number; maxLength?: number; placeholder?: string }) {
  return (
    <>
      <label className="pearl-label" htmlFor={id}>{label}</label>
      <textarea id={id} className="pearl-field" rows={rows} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </>
  );
}

/** Detail on demand: rises from the bottom. Uses the native dialog, so focus is trapped and Escape closes it. */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="pearl-sheet" aria-label={title} onClose={onClose} onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <h2 className="pearl-title" style={{ fontSize: "1.5rem", marginTop: 0 }}>{title}</h2>
      {children}
      <p style={{ marginTop: 20 }}>
        <button type="button" className="pearl-btn" onClick={onClose}>Close</button>
      </p>
    </dialog>
  );
}

/** Two soft bubbles joined by a dotted path: you, and someone in your orbit. Static under reduced motion. */
export function TwoBubbles({ you = "you", other, paired }: { you?: string; other?: string | null; paired: boolean }) {
  return (
    <svg viewBox="0 0 320 120" role="img" aria-label={paired && other ? `You and ${other}` : "You, and the people in your orbit"} style={{ width: "100%", maxWidth: 360, height: "auto", marginTop: 22 }}>
      <defs>
        <radialGradient id="pj-b1" cx="35%" cy="30%" r="75%"><stop offset="0%" stopColor="#fff" stopOpacity="0.85" /><stop offset="45%" stopColor="#E9C98B" stopOpacity="0.28" /><stop offset="100%" stopColor="#B8A2FF" stopOpacity="0.35" /></radialGradient>
        <radialGradient id="pj-b2" cx="35%" cy="30%" r="75%"><stop offset="0%" stopColor="#fff" stopOpacity="0.85" /><stop offset="45%" stopColor="#FFB5D2" stopOpacity="0.3" /><stop offset="100%" stopColor="#B8A2FF" stopOpacity="0.35" /></radialGradient>
      </defs>
      <g className="bubbles-drift"><circle cx="70" cy="60" r="44" fill="url(#pj-b1)" stroke="currentColor" strokeOpacity="0.35" /></g>
      <g className="bubbles-drift" style={{ animationDelay: "-4s" }}>
        <circle cx="250" cy="60" r="38" fill={paired ? "url(#pj-b2)" : "none"} stroke="currentColor" strokeOpacity={paired ? 0.35 : 0.5} strokeDasharray={paired ? undefined : "4 5"} />
      </g>
      <path d="M118 60 C 150 40, 170 80, 208 60" fill="none" stroke="#E3C58C" strokeWidth="1.5" strokeDasharray="2 7" strokeLinecap="round" opacity={paired ? 1 : 0.5} />
      <text x="70" y="64" textAnchor="middle" fontSize="13" fill="currentColor" opacity="0.85">{you}</text>
      <text x="250" y="64" textAnchor="middle" fontSize="13" fill="currentColor" opacity="0.85">{paired && other ? other.slice(0, 10) : "someone"}</text>
    </svg>
  );
}

/** The signature visual: one soft bubble per signal. Size is amount, drift is trend, an empty outline means no entries. Each is a button that opens detail. */
export function LivingBubbles({ signals, onOpen, width = 360 }: { signals: BubbleSignal[]; onOpen?: (id: string) => void; width?: number }) {
  const placed = layoutBubbles(signals, width);
  return (
    <ul className="pearl-bubbles" style={{ maxWidth: width }}>
      {placed.map((b, i) => {
        const size = b.r * 2 + 4;
        const gradient = `pj-film-${b.id}`;
        return (
          <li key={b.id}>
            <button type="button" className="pearl-bubble" onClick={() => onOpen?.(b.id)} aria-label={describeBubble(signals[i])}>
              <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true" className="pearl-bubble-svg"
                style={{ ["--drift" as string]: `${b.drift}px`, animationDelay: `${-i * 1.7}s` }}>
                <defs>
                  <radialGradient id={gradient} cx="34%" cy="28%" r="78%">
                    <stop offset="0%" style={{ stopColor: "#fff", stopOpacity: 0.95 }} />
                    <stop offset="48%" style={{ stopColor: b.color, stopOpacity: 0.2 }} />
                    <stop offset="100%" style={{ stopColor: b.color, stopOpacity: 0.42 }} />
                  </radialGradient>
                </defs>
                <circle cx={b.r + 2} cy={b.r + 2} r={b.r} fill={b.empty ? "none" : `url(#${gradient})`} stroke={b.empty ? "currentColor" : b.color}
                  strokeOpacity={b.empty ? 0.45 : 0.85} strokeWidth="1.25" strokeDasharray={b.empty ? "3 5" : undefined} />
                {!b.empty && <ellipse cx={b.r * 0.78} cy={b.r * 0.62} rx={b.r * 0.22} ry={b.r * 0.12} fill="#fff" opacity="0.7" transform={`rotate(-28 ${b.r * 0.78} ${b.r * 0.62})`} />}
                <text x={b.r + 2} y={b.r + 6} textAnchor="middle" className="pearl-bubble-value">{b.empty ? "–" : b.valueText ?? ""}</text>
              </svg>
              <span className="pearl-bubble-label">{b.label}</span>
              {b.empty && <span className="pearl-bubble-gap">no entries</span>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Patterns: two signals joined by a soft line, the plain sentence, and how sure we are in words. */
export function Thread({ from, to, sentence, sure, onOpen }: { from: string; to: string; sentence: string; sure: string; onOpen?: () => void }) {
  return (
    <div className="pearl-thread">
      <p className="pearl-thread-ends" aria-hidden="true"><span>{from}</span><i /><span>{to}</span></p>
      <p className="pearl-thread-text">{sentence}</p>
      <p className="pearl-note">{sure}{onOpen && <> · <button type="button" className="pearl-link" onClick={onOpen}>See the days</button></>}</p>
    </div>
  );
}
