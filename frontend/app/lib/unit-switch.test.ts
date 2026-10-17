import { describe, expect, it } from "vitest";
import { toShownUnit, toStoredUnit } from "./unit-switch";

describe("unit switch", () => {
  it("leaves pounds unchanged", () => {
    expect(toShownUnit(143.3, "lbs")).toBe(143.3);
    expect(toStoredUnit(143.3, "lbs")).toBe(143.3);
  });

  it("shows stored pounds in kilograms to one decimal", () => {
    expect(toShownUnit(143.3, "kg")).toBe(65);
    expect(toShownUnit(150, "kg")).toBe(68);
  });

  it("turns typed kilograms back into pounds for the API", () => {
    expect(toStoredUnit(65, "kg")).toBe(143.3);
    expect(toStoredUnit(toShownUnit(176.4, "kg"), "kg")).toBeCloseTo(176.4, 0);
  });
});
