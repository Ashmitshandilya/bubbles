import { describe, expect, it, vi } from "vitest";
import { adaptHealthEvents } from "../lib/bubbles-events";
import {
  applyOptimistic,
  cardView,
  decisionError,
  isAmbiguous,
  markChecking,
  markRetracted,
  parseBatch,
  rollback,
  settleFromRead,
  settleFromServer,
  statusesFromRows,
  submitDecisions,
  type Decisions,
  type Fetcher,
} from "./event-decisions";

const events = (statuses: string[]) =>
  adaptHealthEvents(
    statuses.map((status, i) => ({ id: `e${i + 1}`, event_type: "symptom", extracted_data: { note: "x" }, status })),
    undefined
  );
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("optimistic reducer", () => {
  it("flips every pending id at once and ignores an id that already has a decision", () => {
    const first = applyOptimistic({}, ["e1", "e2"], true);
    expect(first).toEqual({ e1: { status: "saved", phase: "optimistic" }, e2: { status: "saved", phase: "optimistic" } });
    expect(applyOptimistic(first, ["e1"], false)).toBe(first);
  });

  it("rolls back only unconfirmed ids and never undoes a settled one", () => {
    const state: Decisions = {
      e1: { status: "saved", phase: "optimistic" },
      e2: { status: "saved", phase: "settled" },
      e3: { status: "dismissed", phase: "checking" },
    };
    expect(rollback(state, ["e1", "e2", "e3"])).toEqual({ e2: { status: "saved", phase: "settled" } });
  });

  it("marks only optimistic ids as being checked", () => {
    const next = markChecking({ e1: { status: "saved", phase: "optimistic" }, e2: { status: "saved", phase: "settled" } }, ["e1", "e2"]);
    expect(next.e1.phase).toBe("checking");
    expect(next.e2.phase).toBe("settled");
  });
});

describe("settleFromServer", () => {
  it("commits each id from the real status and reports the rest", () => {
    const sent = ["e1", "e2", "e3", "e4"];
    const start = applyOptimistic({}, sent, true);
    const out = settleFromServer(
      start,
      [
        { id: "e1", status: "confirmed", projection: "done" },
        { id: "e2", status: "confirmed", projection: "queued" },
        { id: "e3", status: "retracted" },
      ],
      sent,
      true
    );
    expect(out.state.e1).toEqual({ status: "saved", phase: "settled", projection: "done" });
    expect(out.state.e2.projection).toBe("queued");
    expect(out.state.e3).toMatchObject({ status: "retracted", phase: "settled" });
    expect(out.state.e4).toBeUndefined();
    expect(out.missing).toEqual(["e4"]);
    expect(out.withdrawn).toEqual(["e3"]);
  });

  it("shows what is really stored when a skip hits an event that was already saved", () => {
    const start = applyOptimistic({}, ["e1"], false);
    const out = settleFromServer(start, [{ id: "e1", status: "confirmed" }], ["e1"], false);
    expect(out.state.e1.status).toBe("saved");
    expect(out.differed).toEqual(["e1"]);
  });

  it("a status that is not a decision counts as no answer", () => {
    const start = applyOptimistic({}, ["e1"], true);
    const out = settleFromServer(start, [{ id: "e1", status: "pending" }], ["e1"], true);
    expect(out.state.e1).toBeUndefined();
    expect(out.missing).toEqual(["e1"]);
  });
});

describe("re-reading after a lost answer", () => {
  it("reads event statuses out of message rows", () => {
    const rows = [{ health_events: [{ id: "e1", status: "confirmed" }, { id: "e2", status: "pending" }] }, { content: "no events" }];
    expect(statusesFromRows(rows)).toEqual({ e1: "confirmed", e2: "pending" });
    expect(statusesFromRows(null)).toEqual({});
  });

  it("settles what the server did commit and returns the buttons for what it did not", () => {
    const checking = markChecking(applyOptimistic({}, ["e1", "e2"], true), ["e1", "e2"]);
    const out = settleFromRead(checking, ["e1", "e2"], { e1: "confirmed", e2: "pending" });
    expect(out.state.e1).toMatchObject({ status: "saved", phase: "settled" });
    expect(out.state.e2).toBeUndefined();
    expect(out.missing).toEqual(["e2"]);
  });
});

describe("submitDecisions", () => {
  const noRefresh = async () => null;

  it("sends one request for ten events and returns every answer", async () => {
    const ids = Array.from({ length: 10 }, (_, i) => `e${i}`);
    const fetcher = vi.fn<Fetcher>(async (_path, init) => {
      const sent = JSON.parse(String(init?.body)).decisions as Array<{ id: string }>;
      return json({ status: "success", results: sent.map((d) => ({ id: d.id, status: "confirmed", projection: "queued" })) });
    });
    const out = await submitDecisions(fetcher, ids, true, noRefresh);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe("/health-events/confirmation");
    expect(JSON.parse(String(fetcher.mock.calls[0][1]?.body)).decisions).toHaveLength(10);
    expect(out.results).toHaveLength(10);
    expect(out.unanswered).toEqual([]);
  });

  it("splits more than 30 into batches of at most 30", async () => {
    const ids = Array.from({ length: 65 }, (_, i) => `e${i}`);
    const fetcher = vi.fn<Fetcher>(async (_p, init) => {
      const sent = JSON.parse(String(init?.body)).decisions as Array<{ id: string }>;
      expect(sent.length).toBeLessThanOrEqual(30);
      return json({ results: sent.map((d) => ({ id: d.id, status: "confirmed" })) });
    });
    const out = await submitDecisions(fetcher, ids, true, noRefresh);
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(out.results).toHaveLength(65);
  });

  it("refreshes the session once on a 401 and sends again with the new token", async () => {
    const fetcher = vi.fn<Fetcher>(async (_p, init) => {
      const auth = (init?.headers as Record<string, string> | undefined)?.Authorization;
      return auth === "Bearer fresh" ? json({ results: [{ id: "e1", status: "confirmed" }] }) : json({}, 401);
    });
    const refresh = vi.fn(async () => "fresh");
    const out = await submitDecisions(fetcher, ["e1"], true, refresh);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(out.results[0].status).toBe("confirmed");
  });

  it("reports a refusal with its status and a lost answer with none", async () => {
    const refused = await submitDecisions(async () => json({}, 429), ["e1"], true, noRefresh);
    expect(refused).toMatchObject({ unanswered: ["e1"], status: 429 });
    expect(isAmbiguous(refused.status)).toBe(false);

    const lost = await submitDecisions(
      async () => {
        throw new Error("timeout");
      },
      ["e1"],
      true,
      noRefresh
    );
    expect(lost).toMatchObject({ unanswered: ["e1"], status: null });
    expect(isAmbiguous(lost.status)).toBe(true);
    expect(isAmbiguous(503)).toBe(true);
  });

  it("treats ids missing from an OK answer as unanswered", async () => {
    const out = await submitDecisions(async () => json({ results: [{ id: "e1", status: "confirmed" }] }), ["e1", "e2"], true, noRefresh);
    expect(out.unanswered).toEqual(["e2"]);
  });

  it("parseBatch drops rows that are not part of the contract", () => {
    expect(parseBatch({ results: [{ id: "a", status: "confirmed", projection: "done" }, { id: 3 }, null, { id: "b", status: "rejected", projection: "weird" }] })).toEqual([
      { id: "a", status: "confirmed", projection: "done" },
      { id: "b", status: "rejected", projection: undefined },
    ]);
    expect(parseBatch(null)).toEqual([]);
  });
});

describe("cardView", () => {
  it("counts events the server already settled (a reloaded message)", () => {
    const view = cardView(events(["confirmed", "confirmed"]), {});
    expect(view.resolved).toBe(true);
    expect(view.saved).toHaveLength(2);
    expect(view.pendingIds).toEqual([]);
  });

  it("is unresolved while something waits for a press and lists those ids", () => {
    const view = cardView(events(["confirmed", "pending"]), {});
    expect(view.resolved).toBe(false);
    expect(view.pendingIds).toEqual(["e2"]);
  });

  it("flips instantly on an optimistic save and says 'record' only when every projection is done", () => {
    const evs = events(["pending", "pending"]);
    const optimistic = applyOptimistic({}, ["e1", "e2"], true);
    expect(cardView(evs, optimistic)).toMatchObject({ resolved: true, recordSaved: false });
    const mixed = settleFromServer(
      optimistic,
      [
        { id: "e1", status: "confirmed", projection: "done" },
        { id: "e2", status: "confirmed", projection: "queued" },
      ],
      ["e1", "e2"],
      true
    ).state;
    expect(cardView(evs, mixed).recordSaved).toBe(false);
    const allDone = settleFromServer(
      optimistic,
      [
        { id: "e1", status: "confirmed", projection: "done" },
        { id: "e2", status: "confirmed", projection: "done" },
      ],
      ["e1", "e2"],
      true
    ).state;
    expect(cardView(evs, allDone).recordSaved).toBe(true);
  });

  it("is not resolved while checking, and a correction withdraws an event", () => {
    const evs = events(["pending"]);
    const checking = markChecking(applyOptimistic({}, ["e1"], true), ["e1"]);
    expect(cardView(evs, checking)).toMatchObject({ checking: true, resolved: false });
    expect(cardView(evs, markRetracted({}, ["e1"])).withdrawn).toHaveLength(1);
  });
});

describe("decisionError", () => {
  it("is silent on success and honest about how many failed", () => {
    expect(decisionError(true, 0, 3, null)).toBeNull();
    expect(decisionError(true, 1, 3, null)).toBe("Bubbles couldn't save 1 of these just now. Try again.");
    expect(decisionError(false, 1, 1, null)).toBe("Bubbles couldn't skip this just now. Try again.");
    expect(decisionError(true, 2, 2, 401)).toMatch(/session has expired/);
  });
});
