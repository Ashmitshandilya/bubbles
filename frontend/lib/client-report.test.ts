import { afterEach, describe, expect, it, vi } from "vitest";
import { codeForError, reportClientProblem, reportUrl } from "./client-report";

afterEach(() => vi.unstubAllGlobals());

describe("client problem reports", () => {
  it("goes through the website's own route on https, directly in the app and in development", () => {
    expect(reportUrl("https://api.x.test/", { protocol: "https:", origin: "https://heybubbles.in" }, false)).toBe("https://heybubbles.in/bubbles-api/telemetry/client");
    expect(reportUrl("https://api.x.test/", { protocol: "https:", origin: "https://localhost" }, true)).toBe("https://api.x.test/telemetry/client");
    expect(reportUrl(undefined, { protocol: "http:", origin: "http://localhost:3000" }, false)).toBe("http://127.0.0.1:8000/telemetry/client");
  });

  it("names a failed script download and any other crash, from the error's kind only", () => {
    expect(codeForError(Object.assign(new Error("x"), { name: "ChunkLoadError" }))).toBe("chunk_load_failed");
    expect(codeForError(new Error("Loading chunk 12 failed."))).toBe("chunk_load_failed");
    expect(codeForError(new TypeError("Cannot read properties of undefined (reading 'name')"))).toBe("render_error");
    expect(codeForError(undefined)).toBe("render_error");
  });

  it("sends the fixed code and nothing else, once per page load, and never throws", async () => {
    const beacon = vi.fn(() => true);
    vi.stubGlobal("window", { location: { protocol: "http:", origin: "http://localhost:3000" } });
    vi.stubGlobal("navigator", { sendBeacon: beacon });
    reportClientProblem("stream_fallback");
    reportClientProblem("stream_fallback");
    expect(beacon).toHaveBeenCalledTimes(1);
    const [url, blob] = beacon.mock.calls[0] as unknown as [string, Blob];
    expect(url).toMatch(/\/telemetry\/client$/);
    expect(JSON.parse(await blob.text())).toEqual({ code: "stream_fallback" });
    vi.stubGlobal("navigator", { sendBeacon: () => { throw new Error("blocked"); } });
    expect(() => reportClientProblem("render_error")).not.toThrow();
  });
});
