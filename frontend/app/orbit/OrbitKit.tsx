"use client";

// Pieces shared by the Orbit screens: the frame (navigation shell, back link, Hide), a JSON helper over useApi, and the plain safety notice.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, type ReactNode } from "react";
import { useApi } from "../../components/Providers";
import { HubPage } from "../../components/hub/HubKit";
import { Page } from "../../components/pearl";
import { dial, type SafetyAnswer } from "./orbit";

/** Calls an Orbit route and hands back the status and the parsed body (or null). Never throws for an HTTP error. */
export function useOrbitCall() {
  const { fetchBubbles } = useApi();
  return useCallback(
    async (path: string, method: "GET" | "POST" | "PUT" | "DELETE" = "GET", body?: unknown): Promise<{ status: number; json: unknown }> => {
      const response = await fetchBubbles(path, method === "GET" ? {} : { method, body: body === undefined ? undefined : JSON.stringify(body) });
      let json: unknown = null;
      try {
        json = await response.json();
      } catch {
        json = null;
      }
      return { status: response.status, json };
    },
    [fetchBubbles],
  );
}

/** One Orbit screen: the usual navigation, a small Orbit link and a Hide button that leaves Orbit for Today and does not come back on Back. */
export function OrbitFrame({ title, eyebrow = "Orbit", lede, children }: { title: string; eyebrow?: string; lede?: string; children: ReactNode }) {
  const router = useRouter();
  return (
    <HubPage title={title}>
      <Page eyebrow={eyebrow} title={title} lede={lede}>
        <p style={{ margin: "12px 0 0", display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Link href="/orbit" className="pearl-link">Orbit</Link>
          <button type="button" className="pearl-link" onClick={() => router.replace("/dashboard")}>Hide</button>
        </p>
        {children}
      </Page>
    </HubPage>
  );
}

/** What the server said instead of doing the thing: plain text, no mascot, tap-to-call numbers. Nothing here was saved. */
export function SafetyNotice({ safety }: { safety: SafetyAnswer }) {
  return (
    <div role="alert" style={{ marginTop: 24, paddingLeft: 16, borderLeft: "3px solid var(--urgent)" }}>
      <p style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--ink)" }}>{safety.message}</p>
      {safety.resources.length > 0 && (
        <ul style={{ margin: "14px 0 0", padding: 0, listStyle: "none" }}>
          {safety.resources.map((r) => (
            <li key={`${r.name}-${r.number}`} style={{ padding: "6px 0" }}>
              <strong>{r.name}</strong>
              {dial(r.number) ? (
                <>
                  {" "}
                  <a className="pearl-link" href={`tel:${dial(r.number)}`}>{r.number}</a>
                </>
              ) : r.number ? (
                <> {r.number}</>
              ) : null}
              {r.note && <span style={{ display: "block", color: "var(--ink-soft)", fontSize: "0.9rem" }}>{r.note}</span>}
            </li>
          ))}
        </ul>
      )}
      <p className="pearl-note">Nothing you typed here was saved.</p>
    </div>
  );
}

export function copyText(text: string): void {
  try {
    void navigator.clipboard?.writeText(text);
  } catch {
    // clipboard blocked: the text stays on screen for the person to select
  }
}
