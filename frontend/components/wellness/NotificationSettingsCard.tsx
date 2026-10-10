"use client";

// Settings: notification channels, reminder types, quiet hours, daily cap, time zone.
// In-app always works. Email is offered only when the server can send it; browser push is not offered at all.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD } from "../hub/HubKit";
import { Stepper } from "../tracking/kit";
import { ErrorNotice, LiveRegion, Notice, QueryView, Switch, TimeField } from "./ui";
import { useWellnessQuery, useWellnessSend } from "./useWellness";
import { tzLabel, tzOffsetMinutes } from "../../app/lib/wellness-format";
import type { NotificationSettings, NotificationSettingsResponse } from "../../app/lib/wellness-types";

export function NotificationSettingsCard() {
  const [query, reload] = useWellnessQuery<NotificationSettingsResponse>("/notifications/settings", { tz: false });
  return (
    <section id="notifications" aria-labelledby="notifications-title" className={`${CARD} scroll-mt-24 p-5 sm:p-6 lg:col-span-2`}>
      <h2 id="notifications-title" className="text-h3 text-ink">
        Reminders & notifications
      </h2>
      <p className="mt-1 text-body text-muted">Gentle nudges for water, medicines and winding down. They show up inside Bubbles and never include health details.</p>
      <div className="mt-4">
        <QueryView query={query} onRetry={reload} what="your reminder settings">
          {(data) => <Form key={JSON.stringify(data.settings)} data={data} onSaved={reload} />}
        </QueryView>
      </div>
    </section>
  );
}

function Form({ data, onSaved }: { data: NotificationSettingsResponse; onSaved: () => void }) {
  const send = useWellnessSend();
  const detected = tzOffsetMinutes();
  const saved = data.settings;
  // A fresh account has offset 0; if the device is somewhere else, start from the device's zone so reminders land at the right local time.
  const [draft, setDraft] = useState<NotificationSettings>(() => ({ ...saved, tz_offset_minutes: saved.tz_offset_minutes === 0 && detected !== 0 ? detected : saved.tz_offset_minutes }));
  const [cap, setCap] = useState(String(saved.daily_cap));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [said, setSaid] = useState("");
  const emailOk = data.channels.email.available;

  const patch = (p: Partial<NotificationSettings>) => {
    setDraft((d) => ({ ...d, ...p }));
    setSaid("");
  };

  async function save() {
    const n = Number(cap);
    if (!cap.trim() || !Number.isInteger(n) || n < 0 || n > 20) {
      setError("Choose a whole number from 0 to 20 for the daily limit.");
      return;
    }
    setBusy(true);
    setError("");
    const body = {
      channels: { in_app: draft.channels.in_app, email: emailOk && draft.channels.email, push: false },
      types: draft.types,
      quiet_hours: draft.quiet_hours,
      daily_cap: n,
      tz_offset_minutes: draft.tz_offset_minutes,
    };
    const result = await send("/notifications/settings", "PUT", body, { tz: false });
    setBusy(false);
    if (!result.ok) return setError(`${result.message} Your changes are still here.`);
    setSaid("Reminder settings saved.");
    onSaved();
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      className="flex flex-col gap-6"
    >
      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 font-display text-h4 text-default">Where reminders appear</legend>
        <Switch label="In Bubbles" hint="The bell at the top of the app and the Notifications page." checked={draft.channels.in_app} onChange={(v) => patch({ channels: { ...draft.channels, in_app: v } })} />
        {emailOk && (
          <Switch label="Email" hint="Sends the same generic text to your sign-in email." checked={draft.channels.email} onChange={(v) => patch({ channels: { ...draft.channels, email: v } })} />
        )}
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 font-display text-h4 text-default">What to remind me about</legend>
        <Switch label="Water" hint="Only when you're behind your day's pace, and never after you've reached your target." checked={draft.types.water} onChange={(v) => patch({ types: { ...draft.types, water: v } })} />
        <Switch label="Medicines" hint="When a scheduled dose is due. The text never names the medicine." checked={draft.types.med} onChange={(v) => patch({ types: { ...draft.types, med: v } })} />
        <Switch label="Wind-down" hint="A gentle evening nudge before your usual bedtime." checked={draft.types.winddown} onChange={(v) => patch({ types: { ...draft.types, winddown: v } })} />
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
        <legend className="mb-2 p-0 font-display text-h4 text-default">Quiet hours and limits</legend>
        <Switch label="Quiet hours" hint="No reminders are created during this window." checked={draft.quiet_hours.enabled} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, enabled: v } })} />
        {draft.quiet_hours.enabled && (
          <div className="grid gap-4 sm:grid-cols-2">
            <TimeField id="quiet-start" label="From" value={draft.quiet_hours.start} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, start: v } })} />
            <TimeField id="quiet-end" label="Until" value={draft.quiet_hours.end} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, end: v } })} />
          </div>
        )}
        <Stepper id="daily-cap" label="Most reminders in a day" value={cap} onChange={(v) => { setCap(v); setSaid(""); }} min={0} max={20} step={1} fallback={5} signal="sky" hint="0 turns reminders off." />
      </fieldset>

      <div className="flex flex-col gap-2">
        <h3 className="m-0 font-display text-h4 text-default">Time zone</h3>
        <p className="m-0 text-body-sm text-muted">
          Bubbles times reminders using <strong className="text-ink">{tzLabel(draft.tz_offset_minutes)}</strong>. Your device is on <strong className="text-ink">{tzLabel(detected)}</strong>.
        </p>
        {draft.tz_offset_minutes !== detected && (
          <button type="button" onClick={() => patch({ tz_offset_minutes: detected })} className={`${BTN_SECONDARY} self-start`}>
            Use my device&apos;s time zone
          </button>
        )}
      </div>

      {error && <ErrorNotice message={error} />}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={busy} className={BTN_PRIMARY}>
          {busy ? "Saving…" : "Save reminder settings"}
        </button>
        <LiveRegion message={said} />
        {said && <span className="text-body-sm font-extrabold text-bubbles-mint-deep">{said}</span>}
      </div>
      <Notice tone="calm">Reminders are never a safety system. If something feels urgent, don&apos;t wait for a notification: contact your local emergency number.</Notice>
    </form>
  );
}
