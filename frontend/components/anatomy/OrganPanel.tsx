"use client";

import { useRouter } from "next/navigation";
import { askHref } from "../../app/lib/ask-handoff";
import { CONFIDENCE_LABEL, STATUS_META, formatEvidenceDate, type Confidence, type Organ } from "../../app/lib/organ-map";
import { BubblesMascot } from "../BubblesMascot";

const LEVELS: Confidence[] = ["low", "medium", "high"];
/** Entries shown before "Show more": the server sends up to a dozen, flagged ones first. */
const SHOWN = 4;

function EvidenceRows({ items }: { items: Organ["evidence"] }) {
  return (
    <ul className="mt-2 divide-y divide-line rounded-2xl bg-blush">
      {items.map((item, i) => {
        const date = formatEvidenceDate(item.date);
        return (
          <li key={`${item.value}-${item.date}-${i}`} className="px-4 py-3">
            <span className="block text-body-sm font-bold text-ink">{item.value}</span>
            {(date || item.source) && (
              <span className="mt-0.5 block text-caption text-muted">{[date, item.source].filter(Boolean).join(" · ")}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function StatusPill({ organ }: { organ: Pick<Organ, "status"> }) {
  const meta = STATUS_META[organ.status];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-caption font-extrabold ${meta.pill}`}>
      <span className="h-2 w-2 rounded-full" style={{ background: `var(${meta.color})` }} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

/**
 * What Bubbles knows about one organ: status in plain words, the entries behind it, how sure it is and what is missing,
 * one next step, and a way into the chat. "Talk to a doctor" leads with safety wording and shows no mascot (the
 * mascot never appears in a safety state).
 */
export function OrganPanel({ organ }: { organ: Organ | null }) {
  const router = useRouter();

  if (!organ) {
    return (
      <article className="rounded-3xl border-2 border-line bg-surface p-5 sm:p-6">
        <h2 className="text-h3 text-ink">Choose a part of the body</h2>
        <p className="mt-2 text-body text-muted">
          Tap it on the body or pick it from the list to see what your entries say, how sure Bubbles is, and what it still
          doesn&apos;t know.
        </p>
        <p className="mt-4 text-caption text-muted">This is not a diagnosis.</p>
      </article>
    );
  }

  const meta = STATUS_META[organ.status];
  const urgent = organ.status === "talk_to_doctor";
  const titleId = `organ-panel-${organ.id}`;
  const lastEntry = formatEvidenceDate(organ.updatedAt);

  return (
    <article aria-labelledby={titleId} className="rounded-3xl border-2 border-line bg-surface p-5 sm:p-6" data-organ={organ.id}>
      {urgent && (
        <div className="mb-5 rounded-2xl border-l-4 border-bubbles-peach-deep bg-tint-urgent p-4" data-testid="organ-safety">
          <p className="font-extrabold text-ink">Please check this with a doctor.</p>
          <p className="mt-1 text-body-sm text-ink-soft">
            {organ.safety ??
              "If you feel severely unwell right now, for example chest pain, trouble breathing or fainting, call 112 or go to the nearest emergency department."}
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 id={titleId} className="text-h3 text-ink">
          {organ.name}
        </h2>
        <StatusPill organ={organ} />
      </div>
      <p className="mt-2 text-body text-muted">{organ.explanation ?? meta.meaning}</p>
      {organ.reasons.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-body-sm text-ink-soft">
          {organ.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      {organ.notes.map((note) => (
        <p key={note} className="mt-2 text-body-sm text-muted">
          {note}
        </p>
      ))}

      <section className="mt-5" aria-labelledby={`${titleId}-evidence`}>
        <h3 id={`${titleId}-evidence`} className="flex flex-wrap items-baseline justify-between gap-x-3 text-body-sm font-extrabold text-ink">
          From your entries
          {lastEntry && <span className="text-caption font-bold text-muted">Last entry {lastEntry}</span>}
        </h3>
        {organ.evidence.length ? (
          <>
            <EvidenceRows items={organ.evidence.slice(0, SHOWN)} />
            {organ.evidence.length > SHOWN && (
              <details className="group mt-2">
                <summary className="inline-flex min-h-[44px] cursor-pointer list-none items-center rounded-full px-1 text-body-sm font-extrabold text-bubbles-grape-deep underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden">
                  <span className="group-open:hidden">Show {organ.evidence.length - SHOWN} more</span>
                  <span className="hidden group-open:inline">Show fewer</span>
                </summary>
                <EvidenceRows items={organ.evidence.slice(SHOWN)} />
              </details>
            )}
          </>
        ) : (
          <p className="mt-1 text-body-sm text-muted">Nothing logged yet relates to this part of the body.</p>
        )}
      </section>

      <section className="mt-5" aria-labelledby={`${titleId}-confidence`}>
        <h3 id={`${titleId}-confidence`} className="text-body-sm font-extrabold text-ink">
          How sure Bubbles is
        </h3>
        <div className="mt-2 flex items-center gap-3">
          <span className="flex gap-1" aria-hidden="true">
            {LEVELS.map((level, i) => (
              <span
                key={level}
                className={`h-2 w-7 rounded-full ${organ.confidence && LEVELS.indexOf(organ.confidence) >= i ? "bg-bubbles-grape" : "bg-line"}`}
              />
            ))}
          </span>
          <span className="text-body-sm font-bold text-ink-soft">
            {organ.confidence ? `${CONFIDENCE_LABEL[organ.confidence]} confidence` : "Not enough to judge"}
          </span>
        </div>
        {organ.confidenceReason && <p className="mt-2 text-caption text-muted">{organ.confidenceReason}</p>}
        {organ.missing.length > 0 && (
          <>
            <p className="mt-3 text-body-sm font-bold text-ink-soft">Still missing</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-body-sm text-muted">
              {organ.missing.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="mt-5 rounded-2xl bg-tint-grape p-4" aria-labelledby={`${titleId}-next`}>
        <h3 id={`${titleId}-next`} className="text-body-sm font-extrabold text-bubbles-grape-deep">
          One next step
        </h3>
        <p className="mt-1 text-body-sm text-ink">{organ.nextStep ?? meta.nextStep}</p>
      </section>

      <p className="mt-5 text-caption text-muted">
        This is not a diagnosis. It sorts what you have logged so you and your doctor can talk about it.
      </p>

      <div className="mt-4 flex items-center gap-3">
        {!urgent && <BubblesMascot size={44} mood="calm" animated={false} />}
        <button
          type="button"
          onClick={() => router.push(askHref(organ.chatPrompt))}
          className="bubbles-press bubbles-glow inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-5 text-body-sm font-extrabold text-white"
        >
          Ask Bubbles about this
        </button>
      </div>
    </article>
  );
}
