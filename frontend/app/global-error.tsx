"use client";

// Replaces the root layout when it fails, so it brings its own <html> and plain inline styles (no app CSS is loaded).

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", background: "#FBF8F6", color: "#1E1B2E", fontFamily: "system-ui, sans-serif", padding: 16 }}>
        <main role="alert" style={{ maxWidth: 420, textAlign: "center", background: "#fff", border: "2px solid #E7E0EC", borderRadius: 24, padding: 32 }}>
          <h1 style={{ margin: 0, fontSize: 26 }}>Something went wrong</h1>
          <p style={{ margin: "12px 0 20px", fontSize: 16, lineHeight: 1.5 }}>Bubbles could not start. Your entries are safe. Please try again.</p>
          <button type="button" onClick={reset} style={{ minHeight: 44, padding: "0 24px", borderRadius: 999, border: 0, background: "#6B46D6", color: "#fff", fontSize: 15, fontWeight: 800, cursor: "pointer" }}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
