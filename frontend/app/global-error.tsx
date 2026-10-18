"use client";

// Replaces the root layout when it fails, so it brings its own <html> and plain inline styles (no app CSS is loaded).
import { useEffect } from "react";
import { codeForError, reportClientProblem } from "../lib/client-report";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => reportClientProblem(codeForError(error)), [error]);   // a fixed code only, never the message
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", background: "#FFF6FA", color: "#2B1A3F", fontFamily: "system-ui, sans-serif", padding: 16 }}>
        <main role="alert" style={{ maxWidth: 420, textAlign: "center", background: "#fff", border: "2px solid #E7E0EC", borderRadius: 24, padding: 32 }}>
          <h1 style={{ margin: 0, fontSize: 26 }}>Something went wrong</h1>
          <p style={{ margin: "12px 0 20px", fontSize: 16, lineHeight: 1.5 }}>Bubbles could not start. Your entries are safe. Please try again.</p>
          <button type="button" onClick={reset} style={{ minHeight: 44, padding: "0 24px", borderRadius: 999, border: 0, background: "#D6246F", color: "#fff", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
