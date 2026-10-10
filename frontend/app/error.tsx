"use client";

import Link from "next/link";
import { BubblesMascot } from "../components/BubblesMascot";
import { BTN_PRIMARY, BTN_SECONDARY } from "../components/hub/HubKit";

/** A page crashed while rendering. Keep the message kind and offer a way out; the details stay out of sight. */
export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-4 py-10 text-ink">
      <div role="alert" className="w-full max-w-md rounded-3xl border-2 border-line bg-surface p-6 text-center sm:p-8">
        <BubblesMascot size={80} mood="resting" animated={false} className="mx-auto" />
        <h1 className="m-0 mt-4 font-display text-h2">Something went wrong</h1>
        <p className="m-0 mt-2 text-body text-muted">Bubbles hit a snag showing this page. Your entries are safe. Please try again.</p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <button type="button" onClick={reset} className={BTN_PRIMARY}>Try again</button>
          <Link href="/dashboard" className={`${BTN_SECONDARY} no-underline`}>Go to Today</Link>
        </div>
      </div>
    </main>
  );
}
