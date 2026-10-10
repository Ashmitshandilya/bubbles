import Link from "next/link";
import type { ReactNode } from "react";

/** Plain, readable shell for the legal pages. Public (no sign-in), one column, comfortable line length. */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-12 sm:py-20">
      <Link href="/" className="inline-flex min-h-[44px] items-center text-body-sm font-extrabold text-bubbles-pink-ink no-underline hover:underline">
        Back to Bubbles
      </Link>
      <h1 className="mt-6 text-h1 text-ink">{title}</h1>
      <p className="mt-2 text-body-sm font-bold text-muted">{updated}</p>
      <p role="note" className="mt-5 rounded-2xl bg-tint-sun px-4 py-3 text-body-sm font-bold text-bubbles-sun-deep">
        This is a draft that a lawyer has not reviewed yet. It describes what Bubbles really does today and will be finalised before the public launch.
      </p>
      <div className="mt-8 space-y-8 text-body text-ink-soft [&_h2]:font-display [&_h2]:text-h3 [&_h2]:text-ink [&_li]:mt-1.5 [&_ul]:mt-2 [&_ul]:list-disc [&_ul]:pl-6 [&_p+p]:mt-3 [&_h2+*]:mt-2">
        {children}
      </div>
    </main>
  );
}
