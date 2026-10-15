import Link from "next/link";
import { BubblesMascot } from "../components/BubblesMascot";

// Class string repeated here: a server component cannot read constants exported from a client module.
const BTN = "bubbles-press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-bubbles-pink-ink px-5 text-body-sm font-extrabold text-white bubbles-glow";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-blush px-4 py-10 text-ink">
      <div className="w-full max-w-md rounded-3xl border border-line bg-surface p-6 text-center sm:p-8">
        <BubblesMascot size={80} mood="resting" animated={false} className="mx-auto" />
        <h1 className="m-0 mt-4 font-display text-h2">We couldn&apos;t find that page</h1>
        <p className="m-0 mt-2 text-body text-muted">The link may be old or mistyped. Let&apos;s get you back to Bubbles.</p>
        <Link href="/dashboard" className={`${BTN} mt-5 no-underline`}>Go to Today</Link>
      </div>
    </main>
  );
}
