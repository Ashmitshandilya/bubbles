import { describe, expect, it } from "vitest";
import { describePlacement, formProblems, readPlaces, readStars, saveBody } from "./stars";

const moon = { rashi: "Makara", nakshatra: "Shravana", rashi_options: ["Makara"], nakshatra_options: ["Uttara Ashadha", "Shravana"], pada: null, degrees: null, cusp: true };

describe("readStars", () => {
  it("is null for junk and reads an off state", () => {
    expect(readStars(null)).toBeNull();
    expect(readStars({ nope: 1 })).toBeNull();
    const s = readStars({ intro: "A traditional lens.", consent: false, enabled: false });
    expect(s).toMatchObject({ consent: false, enabled: false, items: [], moon: null });
  });

  it("reads a chart and clamps unknown match words to 'Not enough to tell'", () => {
    const s = readStars({
      intro: "x", consent: true, enabled: true, chart: { time_known: false, moon, sun: null, ascendant: null },
      items: [{ id: "a", source: "Moon in Makara", text: "disciplined", uncertain: false, match: "Matches what we've seen" }, { id: "b", source: "s", text: "t", match: "Definitely yours" }, { nope: true }],
      birth: { date: "1999-03-14", time: null, place: { name: "Delhi" } },
    });
    expect(s?.items.map((i) => i.match)).toEqual(["Matches what we've seen", "Not enough to tell"]);
    expect(s?.birth).toEqual({ date: "1999-03-14", time: null, place: "Delhi" });
    expect(s?.moon?.nakshatraOptions).toEqual(["Uttara Ashadha", "Shravana"]);
  });
});

describe("describePlacement", () => {
  it("names both when a birth time would settle it", () => {
    const text = describePlacement("Moon", readStars({ intro: "x", chart: { moon } })!.moon);
    expect(text).toContain("Uttara Ashadha or Shravana");
    expect(text).toContain("A birth time would settle it");
  });
  it("says what is missing for the ascendant", () => {
    expect(describePlacement("Ascendant", null)).toBe("Ascendant: needs a birth time");
  });
  it("notes a cusp", () => {
    expect(describePlacement("Sun", { rashi: "Kumbha", nakshatra: "", rashiOptions: ["Kumbha"], nakshatraOptions: [], pada: 1, cusp: true })).toBe("Sun: Kumbha, on the cusp");
  });
});

describe("form", () => {
  const ok = { date: "1999-03-14", time: "06:30", timeUnknown: false, placeId: "000-delhi" };
  it("accepts a good form and builds the body", () => {
    expect(formProblems(ok)).toEqual({});
    expect(JSON.parse(saveBody(ok))).toEqual({ birth_date: "1999-03-14", birth_time: "06:30", city_id: "000-delhi" });
  });
  it("lets the time be unknown", () => {
    expect(formProblems({ ...ok, time: "", timeUnknown: true })).toEqual({});
    expect(JSON.parse(saveBody({ ...ok, timeUnknown: true })).birth_time).toBeNull();
  });
  it("names each problem", () => {
    const bad = formProblems({ date: "2999-01-01", time: "7pm", timeUnknown: false, placeId: null });
    expect(Object.keys(bad).sort()).toEqual(["date", "place", "time"]);
    expect(formProblems({ ...ok, date: "1800-01-01" }).date).toMatch(/1900/);
    expect(formProblems({ ...ok, date: "" }).date).toMatch(/Enter/);
  });
});

describe("readPlaces", () => {
  it("keeps only well-formed places", () => {
    expect(readPlaces({ places: [{ id: "1", name: "Pune", region: "Maharashtra", country: "India" }, { id: 2 }, null] })).toEqual([{ id: "1", name: "Pune", region: "Maharashtra", country: "India" }]);
    expect(readPlaces(undefined)).toEqual([]);
  });
});
