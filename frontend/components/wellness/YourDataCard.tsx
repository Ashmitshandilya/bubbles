"use client";

// Settings: download everything Bubbles holds as JSON, and delete the Fitness / Cycle / plan documents (two-step).
// Tracker entries (sleep, weight, symptoms and so on) are separate records and are not touched by the delete.

import { useEffect, useRef, useState } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, CARD } from "../hub/HubKit";
import { ErrorNotice, LiveRegion, Notice } from "./ui";
import { useWellnessSend } from "./useWellness";
import { exportFilename, plural } from "../../app/lib/wellness-format";
import type { DeleteResult, ExportPayload } from "../../app/lib/wellness-types";

export function YourDataCard() {
  const send = useWellnessSend();
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [downloaded, setDownloaded] = useState("");

  const [step, setStep] = useState<0 | 1>(0);
  const [typed, setTyped] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [deleted, setDeleted] = useState("");
  const typedRef = useRef<HTMLInputElement>(null);
  const startRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (step === 1) typedRef.current?.focus();
  }, [step]);

  async function download() {
    setDownloading(true);
    setDownloadError("");
    setDownloaded("");
    const result = await send<ExportPayload>("/me/whole-health/export", "GET", undefined, { tz: false, timeoutMs: 60000 });
    setDownloading(false);
    if (!result.ok) return setDownloadError(result.message);
    const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFilename();
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setDownloaded(`Downloaded ${plural(result.data.count, "item")} as ${link.download}.${result.data.truncated ? " Your account holds more than one file can carry, so this copy is partial." : ""}`);
  }

  async function remove() {
    if (typed !== "DELETE") return;
    setDeleting(true);
    setDeleteError("");
    const result = await send<DeleteResult>("/me/whole-health/data?confirm=true", "DELETE", undefined, { tz: false, timeoutMs: 60000 });
    setDeleting(false);
    if (!result.ok) return setDeleteError(result.message);
    const copies = result.data.analytics_copies_removed ?? 0;
    setDeleted(`Deleted ${plural(result.data.deleted, "item")}${copies > 0 ? ` and ${plural(copies, "related analytics copy", "related analytics copies")}` : ""}. ${result.data.note ?? ""}`.trim());
    setStep(0);
    setTyped("");
    window.setTimeout(() => startRef.current?.focus(), 0);
  }

  return (
    <section id="your-data" aria-labelledby="your-data-title" className={`${CARD} scroll-mt-24 p-5 sm:p-6 lg:col-span-2`}>
      <h2 id="your-data-title" className="text-h3 text-ink">
        Your data
      </h2>
      <p className="mt-1 text-body text-muted">It&apos;s yours. You can take a copy, or remove what Bubbles keeps for your Fitness, Cycle and plans.</p>

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h3 className="m-0 font-display text-h4 text-default">Download my data</h3>
          <p className="m-0 text-body-sm text-muted">A JSON file with your profile, plans, food and workout logs, cycle days, medicine schedules and dose records, journal entries, sleep goals and tags, your water garden and reminders. Tracker entries (sleep hours, weight, symptoms and so on) are separate and can be exported from their own pages.</p>
          <button type="button" disabled={downloading} onClick={() => void download()} className={`${BTN_PRIMARY} self-start`}>
            {downloading ? "Preparing your file…" : "Download my data"}
          </button>
          <LiveRegion message={downloaded} />
          {downloaded && <p className="m-0 text-body-sm font-extrabold text-bubbles-mint-deep">{downloaded}</p>}
          {downloadError && <ErrorNotice message={downloadError} />}
        </div>

        <div className="flex flex-col gap-3">
          <h3 className="m-0 font-display text-h4 text-default">Delete my Fitness, Cycle and plan data</h3>
          <p className="m-0 text-body-sm text-muted">This removes everything in that file: Fitness plans and logs, Cycle days and settings, medicine schedules and dose records, journal entries, sleep goals and tags, your water garden and reminders. It can&apos;t be undone.</p>
          <p className="m-0 text-body-sm text-muted">
            It does <strong className="text-ink">not</strong> remove tracker entries such as sleep, hydration, mood, weight or symptoms, or your account. Consider downloading a copy first.
          </p>

          {step === 0 ? (
            <>
              <button ref={startRef} type="button" onClick={() => { setDeleted(""); setStep(1); }} className={`${BTN_SECONDARY} self-start`}>
                Delete my data…
              </button>
              <LiveRegion message={deleted} />
              {deleted && <p className="m-0 text-body-sm font-extrabold text-bubbles-mint-deep">{deleted}</p>}
            </>
          ) : (
            <div role="group" aria-labelledby="delete-confirm-title" className="flex flex-col gap-3 rounded-2xl border-2 border-bubbles-pink-ink bg-tint-pink p-4">
              <p id="delete-confirm-title" className="m-0 font-extrabold text-ink">
                Step 2 of 2: type DELETE to confirm
              </p>
              <Notice tone="calm">Everything listed above will be removed for good.</Notice>
              <label htmlFor="delete-typed" className="text-body-sm font-extrabold text-ink">
                Type the word DELETE
              </label>
              <input
                id="delete-typed" ref={typedRef} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" autoCapitalize="off" spellCheck={false}
                className="min-h-[48px] w-full rounded-[20px] border-2 border-line-strong bg-surface px-4 py-2 text-body text-default focus:border-bubbles-grape"
              />
              {deleteError && <ErrorNotice message={deleteError} />}
              <div className="flex flex-wrap gap-3">
                <button type="button" disabled={typed !== "DELETE" || deleting} onClick={() => void remove()} className={BTN_PRIMARY}>
                  {deleting ? "Deleting…" : "Delete everything listed"}
                </button>
                <button type="button" onClick={() => { setStep(0); setTyped(""); setDeleteError(""); window.setTimeout(() => startRef.current?.focus(), 0); }} className={BTN_SECONDARY}>
                  Keep my data
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
