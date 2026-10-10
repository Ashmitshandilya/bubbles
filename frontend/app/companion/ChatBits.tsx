"use client";

import { Fragment, useEffect, useRef } from "react";
import { BubblesMascot } from "../../components/BubblesMascot";
import { TONE, type Tone } from "../../components/hub/HubKit";
import {
  confidenceLabel,
  eventNote,
  isUrgentMessage,
  parseChatMarkdown,
  reasonSentence,
  retractionNote,
  settledState,
  splitBold,
  type EvidenceItem,
  type ExtractedHealthEvent,
  type ReplyKind,
  type SafetyLevel,
  type SafetyState,
} from "../lib/bubbles-events";

export type { SafetyLevel };
export type EventStatus = "busy" | "saved" | "dismissed" | "retracted";

export interface ChatMessage {
  id: string;
  /** The id the browser first gave this message. Keeps the React key stable when `id` becomes the server id. */
  clientId?: string;
  role: "user" | "assistant";
  content: string;
  /** Effective level: RED covers URGENT and EMERGENCY. Check `retracted` before treating it as an alert. */
  safetyLevel?: SafetyLevel;
  safetyState?: SafetyState | null;
  safetyReasons?: string[];
  /** The user corrected Bubbles and the warning was withdrawn. The original text is kept, collapsed. */
  retracted?: boolean;
  retractionConcepts?: string[];
  kind?: ReplyKind;
  evidence?: EvidenceItem[];
  confidence?: string | null;
  suggestions?: string[];
  healthEvents?: ExtractedHealthEvent[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  when: string;
}

export const ICONS = {
  plus: "M12 5v14M5 12h14",
  send: "M12 19V5M5 12l7-7 7 7",
  warn: "M12 3 2 20h20zM12 10v4M12 17h.01",
  urgent: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 8v5M12 16.5v.01",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 5v14",
  check: "M5 12l5 5 9-10",
  menu: "M4 6h16M4 12h16M4 18h10",
  close: "M6 6l12 12M18 6 6 18",
};

export function Icon({ d, size = 18, strokeWidth = 2.4 }: { d: string; size?: number; strokeWidth?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
    >
      <path d={d} />
    </svg>
  );
}

function Inline({ text }: { text: string }) {
  return (
    <>
      {splitBold(text).map((part, i) =>
        part.bold ? (
          <strong key={i} className="font-extrabold">
            {part.text}
          </strong>
        ) : (
          <Fragment key={i}>{part.text}</Fragment>
        )
      )}
    </>
  );
}

/** Safe markdown-ish rendering: parsed blocks rendered as text nodes, never as HTML. */
export function MessageBody({ content }: { content: string }) {
  return (
    <div className="flex flex-col gap-3">
      {parseChatMarkdown(content).map((block, i) => {
        if (block.kind === "heading") {
          return (
            <h3 key={i} className="m-0 font-display text-h4 font-semibold">
              <Inline text={block.text} />
            </h3>
          );
        }
        if (block.kind === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List
              key={i}
              className={`m-0 flex flex-col gap-1.5 pl-5 ${block.ordered ? "list-decimal marker:font-extrabold" : "list-disc marker:text-bubbles-pink"}`}
            >
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} />
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={i} className="m-0 whitespace-pre-line">
            <Inline text={block.text} />
          </p>
        );
      })}
    </div>
  );
}

export function ThinkingBubble() {
  return (
    <li
      role="status"
      aria-live="polite"
      className="bubbles-rise flex items-center gap-3 self-start rounded-[22px_22px_22px_8px] border-2 border-bubbles-grape/15 bg-surface px-[18px] py-3"
    >
      <BubblesMascot size={32} mood="thinking" />
      <span className="text-body-sm font-extrabold text-bubbles-grape-deep">Checking your history and trusted sources</span>
      <span className="inline-flex shrink-0 gap-1" aria-hidden="true">
        <span className="bubbles-thinking-dot" />
        <span className="bubbles-thinking-dot" />
        <span className="bubbles-thinking-dot" />
      </span>
    </li>
  );
}

export interface PromptCard {
  tag: string;
  tone: Tone;
  text: string;
}

/** Empty-state starters. Each card sends its prompt as the user's first message. */
export function PromptCards({ cards, disabled, onPick }: { cards: PromptCard[]; disabled: boolean; onPick: (text: string) => void }) {
  return (
    <div role="group" aria-label="Ways to start" className="bubbles-stagger grid w-full max-w-2xl gap-3 sm:grid-cols-3">
      {cards.map((card) => (
        <button
          key={card.text}
          type="button"
          disabled={disabled}
          onClick={() => onPick(card.text)}
          className="bubbles-lift flex min-h-[44px] flex-col items-start gap-2.5 rounded-3xl border-2 border-line bg-surface p-4 text-left hover:border-bubbles-grape/40 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[0.75rem] font-extrabold ${TONE[card.tone].chip}`}>{card.tag}</span>
          <span className="text-body font-bold leading-snug text-ink">{card.text}</span>
        </button>
      ))}
    </div>
  );
}

function EvidenceRow({ evidence, confidence }: { evidence: EvidenceItem[]; confidence?: string | null }) {
  if (!evidence.length && !confidence) return null;
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {evidence.map((ev, idx) => {
        const label = (
          <>
            <Icon d={ICONS.book} size={14} />
            <span className="truncate">
              {ev.title} · {ev.publisher ?? ev.sourceName}
            </span>
          </>
        );
        const chip =
          "inline-flex min-h-[44px] max-w-full items-center gap-1.5 rounded-full bg-tint-grape px-3 py-1.5 text-[0.8125rem] font-extrabold text-bubbles-grape-deep no-underline";
        return ev.sourceUrl ? (
          <a key={ev.chunkId ?? `${ev.title}-${idx}`} href={ev.sourceUrl} target="_blank" rel="noopener noreferrer" className={`${chip} hover:bg-bubbles-grape/15`}>
            {label}
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        ) : (
          <span key={ev.chunkId ?? `${ev.title}-${idx}`} className={chip}>
            {label}
          </span>
        );
      })}
      {confidence && (
        <span className="inline-flex min-h-[32px] items-center rounded-full bg-tint-mint px-3 py-1.5 text-[0.8125rem] font-extrabold text-bubbles-mint-deep">
          Confidence {confidence}
        </span>
      )}
    </div>
  );
}

function eventLabel(event: ExtractedHealthEvent) {
  const text = event.eventType.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const btn = "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-full px-4 text-body-sm font-extrabold disabled:cursor-not-allowed disabled:opacity-60";

/** "Should I save these?" — explicit user confirmation before AI-proposed events count. */
function EventCard({
  events,
  status,
  error,
  onDecide,
}: {
  events: ExtractedHealthEvent[];
  status: Record<string, EventStatus>;
  error?: string;
  onDecide: (ids: string[], confirmed: boolean) => void;
}) {
  const resultRef = useRef<HTMLDivElement>(null);
  // This session's decision wins; otherwise show whatever the server already settled (a reloaded message).
  const stateOf = (e: ExtractedHealthEvent): EventStatus | null => (e.id ? status[e.id] : undefined) ?? settledState(e);
  const confirmable = events.filter((e): e is ExtractedHealthEvent & { id: string } => e.isConfirmable && e.id !== null);
  const pending = confirmable.filter((e) => !status[e.id]);
  const busy = confirmable.some((e) => status[e.id] === "busy");
  const resolved = confirmable.length > 0 && pending.length === 0 && !busy;
  const saved = confirmable.filter((e) => status[e.id] === "saved");
  const skipped = confirmable.filter((e) => status[e.id] === "dismissed");
  const withdrawn = confirmable.filter((e) => status[e.id] === "retracted");

  // The buttons that had focus disappear on resolve; hand focus to the result so keyboard users aren't dropped.
  useEffect(() => {
    if (resolved && document.activeElement === document.body) resultRef.current?.focus();
  }, [resolved]);

  if (resolved) {
    if (saved.length) {
      return (
        <div ref={resultRef} tabIndex={-1} role="status" className="bubbles-pop-in flex items-center gap-3 rounded-3xl bg-tint-mint px-4 py-3 outline-offset-4">
          <BubblesMascot size={44} mood="happy" />
          <div className="min-w-0">
            <strong className="block font-display text-h4 font-semibold text-bubbles-mint-deep">Saved to your health record</strong>
            <span className="block text-body-sm text-ink-soft">
              {saved.map(eventLabel).join(", ")}
              {skipped.length ? ` · skipped ${skipped.length}` : ""}
            </span>
          </div>
        </div>
      );
    }
    return (
      <div ref={resultRef} tabIndex={-1} role="status" className="rounded-3xl border-2 border-line bg-surface px-4 py-3 text-body-sm text-ink-soft outline-offset-4">
        {withdrawn.length === confirmable.length
          ? "Bubbles withdrew this after your correction. Nothing was saved."
          : "Okay, nothing from this message was saved."}
      </div>
    );
  }

  const many = confirmable.length > 1;
  return (
    <section
      aria-label="Health details Bubbles noticed"
      className="flex flex-col gap-3 rounded-3xl border-2 border-dashed border-bubbles-pink/60 bg-blush px-4 py-4 sm:px-5"
    >
      <h3 className="m-0 font-display text-h4 font-semibold">
        {confirmable.length ? `Should I save ${many ? "these" : "this"} to your health record?` : "Bubbles noticed"}
      </h3>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {events.map((event, idx) => {
          const state = stateOf(event);
          const conf = confidenceLabel(event.confidence);
          const note = eventNote(event);
          const denied = event.notPresent.length > 0;
          const struck = state === "retracted" ? "line-through" : "";
          return (
            <li key={event.id ?? `${event.eventType}-${idx}`} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border-2 border-line bg-surface px-3 py-2">
              <div className="min-w-0 text-body-sm">
                {denied ? (
                  <>
                    <strong className="font-extrabold">Not present</strong>
                    <span className="text-ink-soft"> · {event.notPresent.join(", ")}</span>
                  </>
                ) : (
                  <>
                    <strong className={`font-extrabold ${struck}`}>{eventLabel(event)}</strong>
                    <span className={`text-ink-soft ${struck}`}> · {event.description}</span>
                  </>
                )}
                {conf && !denied && <span className="block text-[0.8125rem] text-ink-soft">Bubbles&apos; confidence: {conf}</span>}
                {note && <span className="block text-[0.8125rem] text-ink-soft">{note}</span>}
              </div>
              {state === "saved" && (
                <span className="inline-flex items-center gap-1 text-body-sm font-extrabold text-bubbles-mint-deep">
                  <Icon d={ICONS.check} size={16} strokeWidth={3} />
                  Saved
                </span>
              )}
              {state === "dismissed" && <span className="text-body-sm font-extrabold text-ink-soft">Skipped</span>}
              {state === "retracted" && <span className="text-body-sm font-extrabold text-ink-soft">Withdrawn</span>}
              {state === "busy" && <span className="text-body-sm font-extrabold text-ink-soft">Working…</span>}
              {many && event.isConfirmable && event.id && !state && (
                <div className="flex gap-2">
                  <button type="button" disabled={busy} onClick={() => onDecide([event.id!], true)} className={`${btn} bg-tint-mint text-bubbles-mint-deep`} aria-label={`Save ${eventLabel(event)}`}>
                    Save
                  </button>
                  <button type="button" disabled={busy} onClick={() => onDecide([event.id!], false)} className={`${btn} text-ink-soft`} aria-label={`Don't save ${eventLabel(event)}`}>
                    Skip
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {pending.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecide(pending.map((e) => e.id), true)}
            className={`${btn} bg-bubbles-mint text-ink shadow-[0_4px_0_var(--bubbles-mint-deep)]`}
          >
            <Icon d={ICONS.check} size={16} strokeWidth={3} />
            {pending.length === 1 ? "Yes, save it" : "Yes, save all"}
          </button>
          <button type="button" disabled={busy} onClick={() => onDecide(pending.map((e) => e.id), false)} className={`${btn} text-ink-soft hover:text-ink`}>
            Don&apos;t save
          </button>
        </div>
      )}
      {busy && <p role="status" className="m-0 text-body-sm font-bold text-ink-soft">Saving your choice…</p>}
      {error && (
        <p role="alert" className="m-0 text-body-sm font-bold text-bubbles-urgent">
          {error}
        </p>
      )}
    </section>
  );
}

/** One Bubbles reply: safety banner, the answer, sources, and the save-to-record card. */
export function BubblesReply({
  message,
  eventStatus,
  eventError,
  onDecide,
  showAvatar = false,
  chips = [],
  onChip,
  chipsDisabled = false,
}: {
  message: ChatMessage;
  eventStatus: Record<string, EventStatus>;
  eventError?: string;
  onDecide: (ids: string[], confirmed: boolean) => void;
  /** First reply of a run: show the small Bubbles avatar. Urgent and withdrawn replies never show it. */
  showAvatar?: boolean;
  /** Follow-up chips for the newest reply only. Never passed for urgent replies. */
  chips?: string[];
  onChip?: (text: string) => void;
  chipsDisabled?: boolean;
}) {
  if (message.retracted) {
    // The user corrected Bubbles: a calm card, no alert role, no red, no events or sources. The original text stays
    // available behind a disclosure so nothing is silently erased.
    return (
      <li data-kind={message.kind} className="flex w-full flex-col gap-3 self-start sm:max-w-[88%]">
        <div className="flex flex-col gap-2 rounded-[20px] border-2 border-line bg-surface px-5 py-4 text-ink">
          <div role="status" className="flex flex-col gap-1.5">
            <h3 className="m-0 font-display text-h4 font-semibold">Earlier warning withdrawn</h3>
            <p className="m-0 text-body-sm text-ink-soft">{retractionNote(message.retractionConcepts)}</p>
          </div>
          <details className="text-body-sm text-ink-soft">
            <summary className="flex min-h-[44px] cursor-pointer items-center font-extrabold">Show the original message</summary>
            <div className="pt-2 text-body leading-relaxed opacity-80">
              <MessageBody content={message.content} />
            </div>
          </details>
        </div>
      </li>
    );
  }

  if (isUrgentMessage(message)) {
    // Plain and unmistakable: no mascot, no motion, no playful styling, nothing else competing.
    const today = message.safetyState === "URGENT";
    return (
      <li data-kind={message.kind} className="flex w-full flex-col gap-3 self-start sm:max-w-[88%]">
        <div role="alert" className="rounded-[20px] bg-bubbles-urgent px-5 py-4 text-white">
          <h3 className="m-0 flex items-center gap-2 text-h3 font-extrabold text-white">
            <Icon d={ICONS.urgent} size={22} />
            {today ? "Please get medical care today" : "Get urgent help now"}
          </h3>
          <p className="m-0 mt-1.5 text-body font-bold">
            {reasonSentence(message.safetyReasons, message.safetyState)}
            {today
              ? "Please contact a clinician or urgent care today. If it gets worse or you feel unsafe, call your local emergency number."
              : "If this is happening now or feels severe, call your local emergency number or go to the nearest emergency department."}
          </p>
        </div>
        <div className="rounded-[20px] border-2 border-bubbles-urgent bg-surface px-5 py-4 text-body leading-relaxed text-ink">
          <MessageBody content={message.content} />
        </div>
      </li>
    );
  }

  const unsure = message.safetyState === "POTENTIAL_REDFLAG_NEEDS_CLARIFICATION";
  return (
    <li data-kind={message.kind} className="bubbles-rise flex w-full items-start gap-2.5 self-start sm:max-w-[min(92%,44rem)]">
      {/* Fixed gutter so consecutive replies line up; only the first reply of a run shows Bubbles. */}
      <span className="mt-1 flex w-9 shrink-0 justify-center">{showAvatar && <BubblesMascot size={36} animated={false} />}</span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
      {message.safetyLevel === "AMBER" && (
        <div className="flex items-start gap-2.5 rounded-[18px] bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
          <span className="mt-0.5">
            <Icon d={ICONS.warn} size={20} />
          </span>
          {unsure ? (
            <p className="m-0">
              <span className="sr-only">Caution. </span>
              <span className="block font-extrabold">Bubbles isn&apos;t sure whether this is happening right now</span>
              {reasonSentence(message.safetyReasons, message.safetyState)}If it is happening now or feels severe, call your local emergency number.
            </p>
          ) : (
            <p className="m-0">
              <span className="sr-only">Caution. </span>
              Take care. {reasonSentence(message.safetyReasons, message.safetyState)}If it gets worse, feels severe or doesn&apos;t settle, contact a clinician or urgent care.
            </p>
          )}
        </div>
      )}
      <div className="flex flex-col gap-3 rounded-[22px_22px_22px_8px] border-2 border-bubbles-grape/15 bg-surface px-5 py-4 text-body leading-relaxed text-ink shadow-[0_3px_0_var(--tint-grape)]">
        <MessageBody content={message.content} />
        <EvidenceRow evidence={message.evidence ?? []} confidence={message.confidence} />
      </div>
      {message.healthEvents && message.healthEvents.length > 0 && (
        <EventCard events={message.healthEvents} status={eventStatus} error={eventError} onDecide={onDecide} />
      )}
      {chips.length > 0 && onChip && (
        <div role="group" aria-label="Suggested follow-ups" className="flex flex-wrap gap-2">
          {chips.map((chip, i) => (
            <button
              key={`${i}-${chip}`}
              type="button"
              disabled={chipsDisabled}
              onClick={() => onChip(chip)}
              className="bubbles-press min-h-[44px] rounded-full border-2 border-bubbles-grape/20 bg-surface px-4 text-left text-body-sm font-extrabold text-bubbles-grape-deep hover:border-bubbles-grape disabled:cursor-not-allowed disabled:opacity-60"
            >
              {chip}
            </button>
          ))}
        </div>
      )}
      </div>
    </li>
  );
}

export function ConversationList({
  items,
  state,
  activeId,
  onSelect,
  onNew,
  onRetry,
}: {
  items: ConversationSummary[];
  state: "loading" | "error" | "ready";
  activeId?: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      <button
        type="button"
        onClick={onNew}
        className="bubbles-press flex min-h-[48px] items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-4 text-body font-extrabold text-white shadow-[0_5px_0_var(--bubbles-pink-deep)]"
      >
        <Icon d={ICONS.plus} strokeWidth={2.6} />
        New conversation
      </button>
      <h2 className="m-0 px-1.5 pb-0.5 pt-3 text-label font-extrabold uppercase tracking-wide text-ink-soft">Recent</h2>
      {state === "loading" && (
        <div role="status" aria-label="Loading conversations" className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <span key={i} className="bubbles-skeleton block h-14 rounded-2xl" />
          ))}
        </div>
      )}
      {state === "error" && (
        <div role="alert" className="flex flex-col items-start gap-2 rounded-2xl bg-tint-pink px-3.5 py-3 text-body-sm text-ink">
          Bubbles couldn&apos;t load your conversations.
          <button type="button" onClick={onRetry} className="min-h-[44px] rounded-full border-2 border-ink bg-surface px-4 text-body-sm font-extrabold">
            Try again
          </button>
        </div>
      )}
      {state === "ready" && items.length === 0 && (
        <p className="m-0 px-1.5 text-body-sm text-ink-soft">No conversations yet. Your chats with Bubbles will appear here.</p>
      )}
      {state !== "loading" && items.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {items.map((c) => {
            const active = c.id === activeId;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  aria-current={active ? "true" : undefined}
                  className={`flex min-h-[48px] w-full flex-col gap-0.5 rounded-2xl px-3.5 py-2.5 text-left transition-colors ${
                    active ? "bg-tint-pink" : "hover:bg-blush"
                  }`}
                >
                  <strong className="block w-full truncate text-body-sm font-extrabold text-ink">{c.title}</strong>
                  <span className="text-[0.8125rem] text-ink-soft">{c.when}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
