"use client";

import { useState, type FormEvent } from "react";
import { BTN_PRIMARY } from "../hub/HubKit";
import { buildSettingsPayload, draftFromSettings, type SettingsDraft } from "../../app/lib/cycle-form";
import { MODES } from "../../app/lib/cycle-types";
import { useCycle } from "./CycleStore";
import { EducationSection } from "./Education";
import { INPUT, Segmented } from "./fields";
import { PostpartumCard, PregnancyCard } from "./ModeCards";
import { PrivacyPanel } from "./PrivacyPanel";
import { Card, InlineError, PanelError, PanelSkeleton, TabHeading } from "./shared";

const CHOICE_CARD =
  "relative flex min-h-[64px] cursor-pointer gap-3 rounded-3xl border-2 p-4 has-[:checked]:border-bubbles-pink-ink has-[:checked]:bg-tint-pink has-[:focus-visible]:outline has-[:focus-visible]:outline-[3px] has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-bubbles-grape border-line bg-surface";

export function ModesTab() {
  const { settings, settingsStatus, settingsError, reloadSettings, overview, saveSettings, today, announce } = useCycle();
  const [edit, setEdit] = useState<SettingsDraft | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);

  if (settingsStatus === "loading") return <PanelSkeleton rows={3} />;
  if (!settings) return <PanelError title="Settings didn't load" message={settingsError} onRetry={reloadSettings} />;

  const d = edit ?? draftFromSettings(settings);
  const change = (patch: Partial<SettingsDraft>) => {
    setEdit({ ...d, ...patch });
    setSaved("");
  };

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    const built = buildSettingsPayload(d, today);
    if ("error" in built) {
      setError(built.error);
      return;
    }
    setBusy(true);
    const failure = await saveSettings(built.payload);
    setBusy(false);
    if (failure) {
      setError(failure);
      return;
    }
    setEdit(null);
    const text = "Saved. Your earlier entries are all still here.";
    setSaved(text);
    announce(text);
  }

  return (
    <div className="space-y-5">
      <TabHeading id="cycle-h-modes" title="Modes & privacy">Tell Bubbles where you are so the wording and estimates fit.</TabHeading>

      {overview?.pregnancy && <PregnancyCard info={overview.pregnancy} />}
      {overview?.postpartum && <PostpartumCard info={overview.postpartum} />}

      <form onSubmit={save} noValidate>
        <Card as="div" className="space-y-5">
          <fieldset className="m-0 min-w-0 border-0 p-0">
            <legend className="mb-2 p-0 font-display text-h3 text-ink">Your mode</legend>
            <ul className="m-0 grid list-none gap-3 p-0 sm:grid-cols-2">
              {MODES.map((m) => (
                <li key={m.id}>
                  <label className={CHOICE_CARD}>
                    <input type="radio" name="cycle-mode" className="sr-only" checked={d.mode === m.id} onChange={() => change({ mode: m.id })} />
                    <span aria-hidden="true" className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-sm font-extrabold ${d.mode === m.id ? "border-bubbles-pink-ink bg-bubbles-pink-ink text-white" : "border-line-strong"}`}>
                      {d.mode === m.id ? "✓" : ""}
                    </span>
                    <span>
                      <span className="block text-body font-extrabold text-ink">{m.label}</span>
                      <span className="block text-body-sm text-muted">{m.blurb}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="m-0 mt-3 text-body-sm font-bold text-bubbles-mint-deep">Switching never deletes your data.</p>
          </fieldset>

          {d.mode === "pregnancy" && (
            <div className="space-y-3 rounded-3xl bg-tint-grape p-4 text-bubbles-grape-deep">
              <p className="m-0 text-body font-bold">Add either date. Your midwife or doctor confirms the due date.</p>
              <DateField id="cycle-lmp" label="First day of your last period" value={d.lmp} max={today} onChange={(v) => change({ lmp: v })} />
              <DateField id="cycle-due" label="Due date (if you know it)" value={d.due} onChange={(v) => change({ due: v })} />
            </div>
          )}
          {d.mode === "postpartum" && (
            <div className="space-y-3 rounded-3xl bg-tint-grape p-4 text-bubbles-grape-deep">
              <DateField id="cycle-delivery" label="Date you gave birth" value={d.delivery} max={today} onChange={(v) => change({ delivery: v })} />
              <Segmented
                legend="Are you breastfeeding or chestfeeding?"
                options={[{ value: "yes" as const, label: "Yes" }, { value: "no" as const, label: "No" }]}
                value={d.breastfeeding === "skip" ? null : d.breastfeeding}
                onChange={(v) => change({ breastfeeding: v ?? "skip" })}
              />
              <p className="m-0 text-body-sm">Optional. It can change how soon periods return.</p>
            </div>
          )}
          {d.mode === "birth_control" && (
            <p className="m-0 rounded-3xl bg-tint-sky p-4 text-body font-semibold text-bubbles-sky-deep">
              Hormonal methods often change bleeding, and they change ovulation, so Bubbles hides fertile-window and ovulation estimates in this mode. Bleeding you log is still tracked.
            </p>
          )}
          {d.mode === "perimenopause" && (
            <p className="m-0 rounded-3xl bg-tint-sky p-4 text-body font-semibold text-bubbles-sky-deep">
              Cycles often become shorter, longer or skip around this time, so ranges here are wide and marked low-confidence. Heavy or very frequent bleeding is worth raising with a clinician.
            </p>
          )}

          <Segmented
            legend="Age group"
            allowClear={false}
            options={[{ value: "adult" as const, label: "Adult" }, { value: "teen" as const, label: "Teen" }]}
            value={d.age_group}
            onChange={(v) => v && change({ age_group: v })}
          />
          <p className="m-0 -mt-3 text-body-sm text-muted">Cycles are often longer and less regular in the first years of periods, so teen ranges are wider.</p>

          <div>
            <label htmlFor="cycle-luteal" className="block text-body-sm font-extrabold text-ink">Luteal phase length in days (optional, 10 to 16)</label>
            <input
              id="cycle-luteal"
              inputMode="numeric"
              value={d.luteal}
              placeholder="14"
              aria-describedby="cycle-luteal-hint"
              onChange={(e) => change({ luteal: e.target.value })}
              className={`${INPUT} mt-2 max-w-[10rem]`}
            />
            <p id="cycle-luteal-hint" className="m-0 mt-1 text-body-sm text-muted">
              The default is 14 days, the time between ovulation and the next period. Only change it if a clinician or your own temperature charts suggest a different length.
            </p>
          </div>

          <Segmented
            legend="Temperature unit"
            allowClear={false}
            options={[{ value: "c" as const, label: "°C" }, { value: "f" as const, label: "°F" }]}
            value={d.temp_unit}
            onChange={(v) => v && change({ temp_unit: v })}
          />

          {error && <InlineError message={error} />}
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={busy} className={BTN_PRIMARY}>{busy ? "Saving…" : "Save changes"}</button>
            {saved && <p role="status" className="m-0 text-body-sm font-bold text-bubbles-mint-deep">{saved}</p>}
          </div>
        </Card>
      </form>

      <PrivacyPanel />
      <EducationSection mode={settings.mode} title="Learn more" />
    </div>
  );
}

function DateField({ id, label, value, max, onChange }: { id: string; label: string; value: string; max?: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label htmlFor={id} className="block text-body-sm font-extrabold">{label}</label>
      <input id={id} type="date" value={value} max={max} onChange={(e) => onChange(e.target.value)} className={`${INPUT} mt-2 max-w-[16rem] text-ink`} />
    </div>
  );
}
