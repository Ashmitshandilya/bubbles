import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ChatHttpError,
  createSseParser,
  emptyStream,
  loaderCalm,
  parseDelta,
  parseMeta,
  requestChat,
  resetStreamProbe,
  showPartial,
  type Fetcher,
} from "./stream";

const enc = new TextEncoder();
/** An SSE response whose body arrives in the given chunks. */
function sse(chunks: string[], init: ResponseInit = {}): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" }, ...init });
}
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

const REPLY = { status: "success", response: "Hi there.", conversation_id: "c1", message_id: "m1", user_message_id: "u1" };

describe("createSseParser", () => {
  it("joins events split across chunks and ignores pings", () => {
    const p = createSseParser();
    expect(p.push(": ping\n\nevent: delta\nda")).toEqual([]);
    expect(p.push('ta: {"text":"Hel"}\n\nevent: delta\ndata: {"text":"lo"}\n\n')).toEqual([
      { event: "delta", data: '{"text":"Hel"}' },
      { event: "delta", data: '{"text":"lo"}' },
    ]);
  });

  it("handles CRLF and multi-line data", () => {
    const p = createSseParser();
    expect(p.push("event: done\r\ndata: a\r\ndata: b\r\n\r\n")).toEqual([{ event: "done", data: "a\nb" }]);
  });
});

describe("meta and delta shapes", () => {
  it("reads the safety level from the nested or flat form", () => {
    expect(parseMeta({ conversation_id: "c", user_message_id: "u", safety: { level: "AMBER" }, kind: "reply", consent_required: true })).toEqual({
      conversationId: "c",
      userMessageId: "u",
      level: "AMBER",
      kind: "reply",
      consentRequired: true,
    });
    expect(parseMeta({ safety_level: "GREEN" }).level).toBe("GREEN");
    expect(parseMeta(null)).toMatchObject({ level: null, consentRequired: false });
  });

  it("reads a delta whatever its shape", () => {
    expect(parseDelta({ text: "a" })).toBe("a");
    expect(parseDelta({ delta: "b" })).toBe("b");
    expect(parseDelta("c")).toBe("c");
    expect(parseDelta(7)).toBe("");
  });

  it("shows words early only for a calm GREEN reply", () => {
    const calm = { meta: parseMeta({ safety: { level: "GREEN" }, kind: "reply" }), text: "Hi" };
    expect(showPartial(calm)).toBe(true);
    expect(showPartial({ ...calm, meta: parseMeta({ safety: { level: "AMBER" }, kind: "reply" }) })).toBe(false);
    expect(showPartial({ ...calm, meta: parseMeta({ safety: { level: "GREEN" }, kind: "emergency" }) })).toBe(false);
    expect(showPartial({ ...calm, meta: parseMeta({ safety: { level: "GREEN" }, consent_required: true }) })).toBe(false);
    expect(showPartial({ meta: null, text: "Hi" })).toBe(false);
  });

  it("drops the mascot from the loader once the gate says caution or urgent", () => {
    expect(loaderCalm(emptyStream)).toBe(true);
    expect(loaderCalm({ meta: parseMeta({ safety: { level: "GREEN" } }), text: "" })).toBe(true);
    expect(loaderCalm({ meta: parseMeta({ safety: { level: "RED" } }), text: "" })).toBe(false);
    expect(loaderCalm({ meta: parseMeta({ safety: { level: "AMBER" } }), text: "" })).toBe(false);
  });
});

describe("requestChat", () => {
  beforeEach(() => resetStreamProbe());

  it("delivers meta, deltas and the done payload in order from the stream", async () => {
    const seen: string[] = [];
    const fetcher = vi.fn<Fetcher>(async () =>
      sse([
        frame("meta", { conversation_id: "c1", user_message_id: "u1", safety: { level: "GREEN" }, kind: "reply" }),
        frame("delta", { text: "Hi " }).slice(0, 12),
        frame("delta", { text: "Hi " }).slice(12) + frame("delta", { text: "there." }),
        frame("done", REPLY),
      ])
    );
    const out = await requestChat({
      fetcher,
      body: "{}",
      onMeta: (m) => seen.push(`meta:${m.level}`),
      onDelta: (t) => seen.push(`delta:${t}`),
    });
    expect(out.via).toBe("stream");
    expect(out.payload).toEqual(REPLY);
    expect(seen).toEqual(["meta:GREEN", "delta:Hi ", "delta:there."]);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("/chat/stream");
  });

  it("falls back to POST /chat when /chat/stream is 404, and remembers that for the next message", async () => {
    const fetcher = vi.fn<Fetcher>(async (path) => (path === "/chat/stream" ? json({}, 404) : json(REPLY)));
    const first = await requestChat({ fetcher, body: "{}" });
    expect(first).toEqual({ payload: REPLY, via: "chat" });
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual(["/chat/stream", "/chat"]);

    fetcher.mockClear();
    await requestChat({ fetcher, body: "{}" });
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual(["/chat"]);
  });

  it("falls back on a network error, an error event, a stream that ends without done, and a server error", async () => {
    const cases: Array<() => Response | Promise<Response>> = [
      () => {
        throw new TypeError("network");
      },
      () => sse([frame("meta", {}), frame("error", { message: "x" })]),
      () => sse([frame("meta", {}), frame("delta", { text: "Hi" })]),
      () => json({}, 503),
    ];
    for (const make of cases) {
      resetStreamProbe();
      const fetcher = vi.fn<Fetcher>(async (path) => (path === "/chat/stream" ? make() : json(REPLY)));
      const out = await requestChat({ fetcher, body: "{}" });
      expect(out.via).toBe("chat");
      expect(out.payload).toEqual(REPLY);
    }
  });

  it("takes a plain JSON answer from the stream route as the reply", async () => {
    const out = await requestChat({ fetcher: async () => json(REPLY), body: "{}" });
    expect(out).toEqual({ payload: REPLY, via: "stream" });
  });

  it("shows a refusal /chat would repeat (429, 401, 409) instead of asking twice", async () => {
    for (const status of [401, 409, 422, 429]) {
      resetStreamProbe();
      const fetcher = vi.fn<Fetcher>(async () => json({}, status));
      await expect(requestChat({ fetcher, body: "{}" })).rejects.toMatchObject({ status });
      expect(fetcher).toHaveBeenCalledTimes(1);
    }
  });

  it("reports a refusal from the plain route with its status", async () => {
    const fetcher = vi.fn<Fetcher>(async (path) => (path === "/chat/stream" ? json({}, 404) : json({}, 429)));
    const err = await requestChat({ fetcher, body: "{}" }).catch((e) => e);
    expect(err).toBeInstanceOf(ChatHttpError);
    expect(err.status).toBe(429);
  });

  it("does not ask again when the stream request itself timed out", async () => {
    const fetcher = vi.fn<Fetcher>(async () => {
      throw Object.assign(new Error("slow"), { timedOut: true });
    });
    const err = await requestChat({ fetcher, body: "{}" }).catch((e) => e);
    expect(err).toMatchObject({ status: null, timedOut: true });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("gives up on a stream that goes quiet and asks the plain route", async () => {
    let controllerRef: ReadableStreamDefaultController<Uint8Array> | null = null;
    const stalled = new Response(
      new ReadableStream<Uint8Array>({
        start(c) {
          controllerRef = c;
          c.enqueue(enc.encode(frame("meta", { safety: { level: "GREEN" } })));
        },
      }),
      { status: 200, headers: { "Content-Type": "text/event-stream" } }
    );
    const fetcher = vi.fn<Fetcher>(async (path) => (path === "/chat/stream" ? stalled : json(REPLY)));
    const out = await requestChat({ fetcher, body: "{}", idleMs: 30 });
    expect(controllerRef).not.toBeNull();
    expect(out).toEqual({ payload: REPLY, via: "chat" });
  });
});
