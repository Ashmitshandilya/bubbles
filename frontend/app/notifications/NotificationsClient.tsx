"use client";

import { useState } from "react";
import Link from "next/link";
import { BTN_PRIMARY, BTN_SECONDARY, CARD, HubPage, PILL, Skeleton } from "../../components/hub/HubKit";
import { KIND_LABEL } from "../../components/wellness/NotificationBell";
import { BTN_TEXT, EmptyNote, ErrorNotice, LiveRegion, QueryView } from "../../components/wellness/ui";
import { useWellnessQuery, useWellnessSend } from "../../components/wellness/useWellness";
import { plural, timeAgo } from "../../app/lib/wellness-format";
import type { NotificationList } from "../../app/lib/wellness-types";

export function NotificationsClient() {
  return (
    <HubPage title="Notifications">
      <Notifications />
    </HubPage>
  );
}

const KIND_TONE: Record<string, string> = {
  water: "bg-tint-sky text-bubbles-sky-deep",
  med: "bg-tint-mint text-bubbles-mint-deep",
  winddown: "bg-tint-grape text-bubbles-grape-deep",
  system: "bg-blush text-ink-soft",
};

function Notifications() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [list, reload] = useWellnessQuery<NotificationList>(`/notifications?limit=100&unread_only=${unreadOnly}`, { tz: false });
  const send = useWellnessSend();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");

  async function mark(body: { all: true } | { ids: string[] }, message: string) {
    setBusy(true);
    setError("");
    const result = await send("/notifications/read", "POST", body, { tz: false });
    setBusy(false);
    if (!result.ok) return setError(result.message);
    setSaid(message);
    reload();
  }

  return (
    <div className="space-y-6">
      <header className="bubbles-rise flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-h1 text-ink">Notifications</h1>
          <p className="mt-1 text-body font-semibold text-muted">Gentle reminders you&apos;ve turned on. They never include health details.</p>
        </div>
        <Link href="/settings#notifications" className={`${BTN_SECONDARY} no-underline`}>
          Reminder settings
        </Link>
      </header>

      <QueryView query={list} onRetry={reload} what="your notifications" skeleton={<div className="space-y-3"><Skeleton className="h-20 rounded-3xl" /><Skeleton className="h-20 rounded-3xl" /></div>}>
        {(data) => (
          <section aria-label="Your notifications" className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="m-0 text-body font-bold text-ink-soft" aria-live="polite">
                {data.unread_count === 0 ? "You're all caught up." : `${plural(data.unread_count, "unread notification")}.`}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" aria-pressed={unreadOnly} onClick={() => setUnreadOnly((v) => !v)} className={BTN_SECONDARY}>
                  {unreadOnly ? "Showing unread only" : "Show unread only"}
                </button>
                <button type="button" disabled={busy || data.unread_count === 0} onClick={() => void mark({ all: true }, "All notifications marked as read.")} className={BTN_PRIMARY}>
                  Mark all read
                </button>
              </div>
            </div>
            <LiveRegion message={said} />
            {error && <ErrorNotice message={error} />}

            {data.notifications.length === 0 ? (
              <EmptyNote title={unreadOnly ? "Nothing unread" : "No notifications yet"}>
                {unreadOnly ? "Everything has been read." : "Water, medicine and wind-down reminders you turn on in Settings will appear here. In-app is the only channel for now."}
              </EmptyNote>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-3 p-0">
                {data.notifications.map((n) => (
                  <li key={n.id} className={`${CARD} p-4 sm:p-5 ${n.read ? "" : "border-bubbles-pink"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="m-0 flex flex-wrap items-center gap-2">
                        <span className={`${PILL} ${KIND_TONE[n.kind] ?? KIND_TONE.system}`}>{KIND_LABEL[n.kind] ?? "Bubbles"}</span>
                        {!n.read && <span className={`${PILL} bg-tint-pink text-bubbles-pink-deep`}>New</span>}
                      </p>
                      <time dateTime={n.created_at} className="text-body-sm font-bold text-muted">
                        {timeAgo(n.created_at)}
                      </time>
                    </div>
                    <p className="m-0 mt-2 font-display text-h4 text-default">{n.title}</p>
                    <p className="m-0 text-body text-ink-soft">{n.body}</p>
                    {!n.read && (
                      <button type="button" disabled={busy} onClick={() => void mark({ ids: [n.id] }, "Marked as read.")} className={`${BTN_TEXT} mt-1`}>
                        Mark read
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </QueryView>
    </div>
  );
}
