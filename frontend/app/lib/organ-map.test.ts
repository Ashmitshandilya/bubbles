import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  ORGAN_PARTS,
  ORGAN_TINT,
  STATUS_META,
  countByStatus,
  defaultOrganId,
  formatEvidenceDate,
  partOwners,
  partsOf,
  prefer3D,
  readConfidence,
  readOrganMap,
  readUnavailable,
} from "./organ-map";

// Shaped like backend organ_map_engine.assess_organ / build_organ_map output.
const API = {
  status: "success",
  window_days: 30,
  unavailable: ["labs"],
  counts: { no_data: 1, steady: 1, worth_watching: 0, talk_to_doctor: 1 },
  organs: [
    {
      safety: { state: "EMERGENCY", level: "RED", message: "On 12 Oct you logged chest pain. If it is happening now, call 112." },
      organ_id: "heart",
      name: "Heart",
      status: "talk_to_doctor",
      summary: "You logged chest pain on 12 Oct, which can be serious.",
      reasons: ["You logged chest pain on 12 Oct, which can be serious.", "1 of your 2 readings was 140/90 or higher."],
      notes: [],
      updated_at: "2026-10-12",
      evidence: [{ id: "e1", date: "2026-10-12", label: "Chest pain", value: "7/10", unit: null, source: "chat" }],
      confidence: { level: "high", reason: "A recent entry needs attention whatever else the data says." },
      missing: ["Resting heart rate"],
      next_step: "Speak to a doctor today.",
      chat_prompt: { text: "Explain my heart", organ_id: "heart", status: "talk_to_doctor", evidence: [] },
    },
    {
      safety: null,
      organ_id: "kidneys_bladder",
      name: "Kidneys and bladder",
      status: "steady",
      summary: "None of the checks for this area were crossed.",
      evidence: [{ id: "e2", date: "2026-10-10T08:00:00+00:00", label: "Water", value: 2.1, unit: "L", source: "tracker" }],
      confidence: { level: "medium", reason: "Some entries." },
      missing: [],
      next_step: "",
      chat_prompt: { text: "Explain my kidneys and bladder" },
    },
    {
      safety: null,
      organ_id: "thyroid",
      name: "Thyroid",
      status: "no_data",
      summary: "Nothing in the last 30 days touches this area yet.",
      evidence: [],
      confidence: { level: "low", reason: "Nothing logged." },
      missing: ["A TSH result"],
      next_step: "Add your last thyroid test.",
      chat_prompt: { text: "Explain my thyroid" },
    },
  ],
};

describe("readOrganMap", () => {
  it("reads the server payload into the panel's shape", () => {
    const [heart, kidneys, thyroid] = readOrganMap(API);
    expect(heart).toEqual({
      id: "heart",
      name: "Heart",
      status: "talk_to_doctor",
      explanation: "You logged chest pain on 12 Oct, which can be serious.",
      reasons: ["1 of your 2 readings was 140/90 or higher."],
      notes: [],
      updatedAt: "2026-10-12",
      evidence: [{ date: "2026-10-12", value: "Chest pain: 7/10", source: "Chat" }],
      confidence: "high",
      confidenceReason: "A recent entry needs attention whatever else the data says.",
      missing: ["Resting heart rate"],
      nextStep: "Speak to a doctor today.",
      chatPrompt: "Explain my heart",
      safety: "On 12 Oct you logged chest pain. If it is happening now, call 112.",
    });
    expect(kidneys.evidence[0].value).toBe("Water: 2.1 L");
    expect(kidneys.nextStep).toBeNull(); // empty string -> the status fallback
    expect(thyroid.confidence).toBeNull(); // no data, nothing to be confident about
    expect(thyroid.confidenceReason).toBe("Nothing logged.");
  });

  it("accepts a bare list and survives junk", () => {
    expect(readOrganMap(null)).toEqual([]);
    expect(readOrganMap("nope")).toEqual([]);
    expect(readOrganMap({ organs: "nope" })).toEqual([]);
    const organs = readOrganMap([null, 4, {}, { name: "No id" }, { id: "lungs" }, { organ_id: "lungs", status: "steady" }]);
    expect(organs).toHaveLength(1); // the repeated id keeps the first
    expect(organs[0]).toMatchObject({
      id: "lungs",
      name: "Lungs",
      status: "no_data",
      evidence: [],
      missing: [],
      nextStep: null,
      safety: null,
      chatPrompt: "What do my recent entries say about my lungs?",
    });
  });

  it("never turns an unknown or empty status into reassurance", () => {
    const [weird, emptySteady, junkEvidence] = readOrganMap([
      { organ_id: "brain", status: "healthy", evidence: ["Slept 8h"] },
      { organ_id: "skin", status: "steady", evidence: [] },
      { organ_id: "lungs", status: "steady", evidence: [null, {}, { date: "2026-10-01" }] },
    ]);
    expect(weird.status).toBe("no_data");
    expect(emptySteady.status).toBe("no_data");
    expect(junkEvidence.status).toBe("no_data");
  });

  it("is never calmer than its own safety message", () => {
    const [organ] = readOrganMap([{ organ_id: "brain", status: "steady", evidence: ["x"], safety: { message: "Call 112 now." } }]);
    expect(organ.status).toBe("talk_to_doctor");
    expect(organ.safety).toBe("Call 112 now.");
  });

  it("keeps a string chat prompt and string evidence", () => {
    const [organ] = readOrganMap([{ organ_id: "heart", status: "worth_watching", evidence: ["Palpitations twice"], chat_prompt: "Tell me about my heart" }]);
    expect(organ.chatPrompt).toBe("Tell me about my heart");
    expect(organ.evidence).toEqual([{ date: null, value: "Palpitations twice", source: null }]);
  });
});

describe("readConfidence", () => {
  it.each([
    ["high", "high"],
    [" Medium ", "medium"],
    [0.85, "high"],
    [0.5, "medium"],
    [0.1, "low"],
    [72, "high"],
    ["0.4", "medium"],
    [-1, null],
    [250, null],
    ["sure", null],
    ["", null],
    [null, null],
    [Number.NaN, null],
  ])("%j -> %j", (input, expected) => {
    expect(readConfidence(input)).toBe(expected);
  });
});

describe("parts and owners", () => {
  it("draws grouped organs as their separate parts", () => {
    const owners = partOwners(readOrganMap(API));
    expect(owners.get("kidneys")?.id).toBe("kidneys_bladder");
    expect(owners.get("bladder")?.id).toBe("kidneys_bladder");
    expect(owners.get("heart")?.id).toBe("heart");
    expect(owners.has("liver")).toBe(false);
    expect(partsOf("pancreas")).toEqual(["pancreas"]); // unknown ids draw by their own name
  });

  it("covers every mesh in the 3D model", () => {
    const organs = JSON.parse(readFileSync(new URL("../../../scripts/anatomy/organs.json", import.meta.url), "utf8")) as {
      organs: Array<{ id: string }>;
    };
    const drawn = new Set(Object.values(ORGAN_PARTS).flat());
    for (const mesh of organs.organs) expect(drawn, mesh.id).toContain(mesh.id);
  });
});

describe("status choices", () => {
  it("opens on the most serious organ with data, or none", () => {
    expect(defaultOrganId(readOrganMap(API))).toBe("heart");
    expect(defaultOrganId(readOrganMap([{ organ_id: "a", status: "steady", evidence: ["x"] }, { organ_id: "b", status: "worth_watching" }]))).toBe("b");
    expect(defaultOrganId(readOrganMap([{ organ_id: "a" }, { organ_id: "b" }]))).toBeNull();
  });

  it("counts every status", () => {
    expect(countByStatus(readOrganMap(API))).toEqual({ talk_to_doctor: 1, worth_watching: 0, steady: 1, no_data: 1 });
  });

  it("reads which sources were skipped", () => {
    expect(readUnavailable(API)).toEqual(["labs"]);
    expect(readUnavailable(null)).toEqual([]);
    expect(readUnavailable({ unavailable: "labs" })).toEqual([]);
  });

  it("only uses colours that exist in tokens.css", () => {
    const tokens = readFileSync(new URL("../tokens.css", import.meta.url), "utf8");
    const vars = [...Object.values(STATUS_META).map((m) => m.color), ...Object.values(ORGAN_TINT)];
    for (const name of vars) expect(tokens, name).toMatch(new RegExp(`${name}:`));
    for (const name of Object.values(ORGAN_TINT).filter((n) => n.startsWith("--tint-"))) {
      expect(tokens, name).toMatch(new RegExp(`${name.replace("--tint-", "--bubbles-")}:`)); // the 3D fill partner
    }
  });

  it("says plainly that steady and no data are not all-clear", () => {
    expect(STATUS_META.steady.meaning).toMatch(/not an all-clear/);
    expect(STATUS_META.no_data.meaning).toMatch(/never read as healthy/);
  });
});

describe("prefer3D", () => {
  const capable = { webgl: true, reducedMotion: false, saveData: false, hardwareConcurrency: 8 };
  it.each([
    [{}, true],
    [{ webgl: false }, false],
    [{ reducedMotion: true }, false],
    [{ saveData: true }, false],
    [{ hardwareConcurrency: 2 }, false],
    [{ hardwareConcurrency: 4 }, true],
    [{ hardwareConcurrency: undefined }, true],
  ])("%j -> %s", (change, expected) => {
    expect(prefer3D({ ...capable, ...change })).toBe(expected);
  });
});

describe("formatEvidenceDate", () => {
  const now = new Date(2026, 9, 15);
  it("keeps calendar days on their day and adds the year only when it differs", () => {
    expect(formatEvidenceDate("2026-10-12", now)).toBe("12 Oct");
    expect(formatEvidenceDate("2026-10-02T00:00:00+00:00", now)).toBe("2 Oct");
    expect(formatEvidenceDate("2025-03-01", now)).toBe("1 Mar 2025");
  });
  it("returns null for nothing usable", () => {
    expect(formatEvidenceDate(null, now)).toBeNull();
    expect(formatEvidenceDate("not a date", now)).toBeNull();
  });
});
