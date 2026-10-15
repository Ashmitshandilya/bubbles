"use client";

// Settings: notification channels, reminder types, quiet hours, daily cap, time zone.
// In-app always works. Email is offered only when the server can send it; browser push is not offered at all.

import { useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY } from "../hub/HubKit";
import { Stepper } from "../tracking/kit";
import { ErrorNotice, LiveRegion, QueryView, Switch, TimeField } from "./ui";
import { useWellnessQuery, useWellnessSend } from "./useWellness";
import { tzLabel, tzOffsetMinutes } from "../../app/lib/wellness-format";
import type { NotificationSettings, NotificationSettingsResponse } from "../../app/lib/wellness-types";

export function NotificationSettingsCard() {
  const [query, reload] = useWellnessQuery<NotificationSettingsResponse>("/notifications/settings", { tz: false });
  return (
    <section aria-label="Reminders" className="px-2 pb-1 pt-1">
      <div>
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
        <legend className="mb-2 p-0 font-display text-h4 text-default">Show reminders</legend>
        <Switch label="In Bubbles" checked={draft.channels.in_app} onChange={(v) => patch({ channels: { ...draft.channels, in_app: v } })} />
        {emailOk && (
          <Switch label="Email" hint="Same plain text, to your sign-in email." checked={draft.channels.email} onChange={(v) => patch({ channels: { ...draft.channels, email: v } })} />
        )}
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-2 p-0 font-display text-h4 text-default">Remind me about</legend>
        <Switch label="Water" checked={draft.types.water} onChange={(v) => patch({ types: { ...draft.types, water: v } })} />
        <Switch label="Medicines" hint="Never names the medicine." checked={draft.types.med} onChange={(v) => patch({ types: { ...draft.types, med: v } })} />
        <Switch label="Wind-down" checked={draft.types.winddown} onChange={(v) => patch({ types: { ...draft.types, winddown: v } })} />
      </fieldset>

      <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
        <legend className="mb-2 p-0 font-display text-h4 text-default">Quiet hours</legend>
        <Switch label="Quiet hours" checked={draft.quiet_hours.enabled} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, enabled: v } })} />
        {draft.quiet_hours.enabled && (
          <div className="grid gap-4 sm:grid-cols-2">
            <TimeField id="quiet-start" label="From" value={draft.quiet_hours.start} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, start: v } })} />
            <TimeField id="quiet-end" label="Until" value={draft.quiet_hours.end} onChange={(v) => patch({ quiet_hours: { ...draft.quiet_hours, end: v } })} />
          </div>
        )}
        <Stepper id="daily-cap" label="Most reminders a day (0 is off)" value={cap} onChange={(v) => { setCap(v); setSaid(""); }} min={0} max={20} step={1} fallback={5} signal="sky" />
      </fieldset>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-body-sm text-muted">
          Time zone: <strong className="text-ink">{tzLabel(draft.tz_offset_minutes)}</strong>
        </p>
        {draft.tz_offset_minutes !== detected && (
          <button type="button" onClick={() => patch({ tz_offset_minutes: detected })} className={BTN_SECONDARY}>
            Use my device ({tzLabel(detected)})
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
      <p className="m-0 text-chip text-muted">Reminders are not a safety system. If something feels urgent, call your local emergency number.</p>
    </form>
  );
}
