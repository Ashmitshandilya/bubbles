"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { NOTICE_TEXT, browserStore, dismissNotice, noticeBelongsOn, shouldShowNotice } from "../app/lib/privacy-notice";

/** One small notice about browser storage, shown once per browser. It never blocks the page and takes no focus. */
export function PrivacyNotice() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname() ?? "";

  // Read the stored choice after mount so the server and the first client render agree (nothing is shown until then).
  useEffect(() => {
    setOpen(shouldShowNotice(browserStore()));
  }, []);

  // Only on the pages a new visitor sees. Signed-in screens are full of controls the notice would cover, and everyone reaches them through the sign-in page.
  if (!open || !noticeBelongsOn(pathname)) return null;

  return (
    <section
      aria-label="Privacy notice"
      className="bubbles-rise fixed bottom-[calc(env(safe-area-inset-bottom)+5.5rem)] left-4 right-4 z-50 rounded-[22px] border-2 border-line bg-surface p-4 shadow-md sm:right-auto sm:max-w-sm lg:bottom-4"
    >
      <p className="m-0 text-body-sm font-semibold text-ink-soft">{NOTICE_TEXT}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={() => {
            dismissNotice(browserStore());
            setOpen(false);
          }}
          className="bubbles-press inline-flex min-h-[44px] items-center rounded-full bg-bubbles-pink-ink px-5 text-body-sm font-extrabold text-white"
        >
          Got it
        </button>
        <Link href="/privacy" className="text-body-sm font-extrabold text-bubbles-pink-ink underline">
          Read the privacy policy
        </Link>
      </div>
    </section>
  );
}
