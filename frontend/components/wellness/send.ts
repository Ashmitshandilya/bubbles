"use client";

// The write/read helper behind every wellness call. Kept free of HubKit imports so the notification bell, which the app
// shell (Navigation) imports, does not create an import cycle with the hub kit.

import { useCallback } from "react";
import { useApi } from "../Providers";
import { classifyFailure, failureFromError } from "../../app/lib/connection";
import { detailOf, tzOffsetMinutes, withQuery } from "../../app/lib/wellness-format";

export type SendResult<T> = { ok: true; data: T } | { ok: false; message: string; status: number };

/**
 * `send(path, method, body)` resolves to the parsed JSON or a message that is safe to show: the server's own `detail`
 * sentence for client errors (422, 404, ...), Bubbles' standard wording for everything else. It never throws.
 * `tz_offset_minutes` is appended automatically so the server knows the person's local day.
 */
export function useWellnessSend() {
  const { fetchBubbles } = useApi();
  return useCallback(
    async function send<T>(path: string, method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown, options: { tz?: boolean; timeoutMs?: number } = {}): Promise<SendResult<T>> {
      const url = options.tz === false ? path : withQuery(path, { tz_offset_minutes: tzOffsetMinutes() });
      try {
        const init: RequestInit = { method, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) };
        // A caller that expects a slow answer (a full data export) gets a longer single attempt and cannot flip the app offline.
        const response = await (options.timeoutMs ? fetchBubbles(url, init, { timeoutMs: options.timeoutMs, retries: 0 }) : fetchBubbles(url, init));
        const json: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          const general = classifyFailure({ status: response.status, body: json });
          // A database-permission answer carries server internals; everything else may show the server's own sentence.
          const message = general.kind === "database_permission" ? general.message : detailOf(response.status, json, general.message);
          return { ok: false, message, status: response.status };
        }
        return { ok: true, data: json as T };
      } catch (error) {
        return { ok: false, message: classifyFailure(failureFromError(error)).message, status: 0 };
      }
    },
    [fetchBubbles],
  );
}
