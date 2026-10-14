"use client";

// Presentational pieces used by several cycle tabs. No mascot appears in anything urgent or safety-related.

import type { ReactNode } from "react";
import { CARD, ErrorCard, Skeleton } from "../hub/HubKit";
import type { Flag, SafetySignal } from "../../app/lib/cycle-types";

export function Card({ children, className = "", as: Tag = "section", labelledBy }: { children: ReactNode; className?: string; as?: "section" | "div"; labelledBy?: string }) {
  return (
    <Tag aria-labelledby={labelledBy} className={`${CARD} p-5 sm:p-6 ${className}`}>
      {children}
    </Tag>
  );
}

export function Notice({ children, tone = "sky", title }: { children: ReactNode; tone?: "sky" | "sun" | "grape"; title?: string }) {
  const style = { sky: "bg-tint-sky text-bubbles-sky-deep", sun: "bg-tint-sun text-bubbles-sun-deep", grape: "bg-tint-grape text-bubbles-grape-deep" }[tone];
  return (
    <div className={`rounded-3xl border border-current p-4 ${style}`}>
      {title && <p className="m-0 text-body-sm font-extrabold uppercase tracking-wide">{title}</p>}
      <div className="text-body font-semibold">{children}</div>
    </div>
  );
}

const FLAG_STYLE = {
  info: { box: "bg-tint-sky text-bubbles-sky-deep", label: "Good to know" },
  talk: { box: "bg-tint-sun text-bubbles-sun-deep", label: "Worth mentioning to a clinician" },
  urgent: { box: "bg-tint-urgent text-ink border-bubbles-urgent", label: "Please act on this" },
} as const;

/** Urgent flags first, each announced as an alert; no mascot here. */
export function FlagList({ flags, hideIds = [] }: { flags: Flag[]; hideIds?: string[] }) {
  const order = { urgent: 0, talk: 1, info: 2 } as const;
  const shown = flags.filter((f) => !hideIds.includes(f.id)).sort((a, b) => order[a.severity] - order[b.severity]);
  if (!shown.length) return null;
  return (
    <ul className="m-0 list-none space-y-3 p-0">
      {shown.map((flag) => {
        const s = FLAG_STYLE[flag.severity];
        return (
          <li
            key={flag.id}
            role={flag.severity === "urgent" ? "alert" : undefined}
            className={`rounded-3xl border p-4 ${s.box} ${flag.severity === "urgent" ? "" : "border-current"}`}
          >
            <p className="m-0 text-[0.8125rem] font-extrabold uppercase tracking-wide">{s.label}</p>
            <p className={`m-0 mt-1 font-display text-h4 ${flag.severity === "urgent" ? "text-bubbles-urgent" : ""}`}>{flag.title}</p>
            <p className={`m-0 mt-1 text-body ${flag.severity === "urgent" ? "font-extrabold" : "font-semibold"}`}>{flag.message}</p>
            {flag.detail && <p className="m-0 mt-1 text-body-sm font-semibold">{flag.detail}</p>}
          </li>
        );
      })}
    </ul>
  );
}

export function SafetyAlert({ safety }: { safety: SafetySignal }) {
  return (
    <div role="alert" className="rounded-3xl border border-bubbles-urgent bg-tint-urgent p-5 text-ink">
      <p className="m-0 font-display text-h3 text-bubbles-urgent">Please read this first</p>
      <p className="m-0 mt-2 text-body font-extrabold">{safety.message}</p>
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <p role="alert" className="m-0 rounded-2xl bg-tint-pink px-4 py-3 text-body-sm font-bold text-bubbles-pink-deep">
      {message}
    </p>
  );
}

export function TabHeading({ id, title, children }: { id: string; title: string; children?: ReactNode }) {
  return (
    <div>
      <h2 id={id} className="m-0 font-display text-h2 text-ink">{title}</h2>
      {children && <p className="m-0 mt-1 text-body text-muted">{children}</p>}
    </div>
  );
}

export function PanelSkeleton({ rows = 2 }: { rows?: number }) {
  return (
    <div className="space-y-4" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-40 rounded-3xl" />
      ))}
    </div>
  );
}

export function PanelError({ title = "This didn't load", message, onRetry }: { title?: string; message: string; onRetry: () => void }) {
  return <ErrorCard title={title} message={message} onRetry={onRetry} />;
}

export const FIELD_LABEL = "block text-body-sm font-extrabold text-ink";
export const SR_ONLY = "sr-only";
