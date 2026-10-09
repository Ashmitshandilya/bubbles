import { describe, expect, it } from "vitest";
import {
  addMedication, buildSettingsPayload, convertBbtText, draftFromSettings, fromForm, toForm, validateForm,
  type SettingsDraft,
} from "./cycle-form";
import { EMPTY_DAY_LOG, type CycleSettings, type DayLog } from "./cycle-types";

const FULL: DayLog = {
  ...EMPTY_DAY_LOG, flow: "medium", products: ["pad"], pain_level: 5, pain_types: ["cramps"], energy: 2, sleep_quality: 4,
  factors: ["tired"], custom_factors: ["sore knees"], discharge: "creamy", sex: { had: true, protection: "condom" },
  ovulation_test: "faint", bbt_c: 36.45, medications: ["ibuprofen"], birth_control_taken: false, period_start: true, notes: "ok",
};

describe("DayLog <-> form", () => {
  it("round-trips a full log in Celsius", () => {
    expect(fromForm(toForm(FULL, "c"), "c")).toEqual(FULL);
  });

  it("round-trips an empty log", () => {
    expect(fromForm(toForm(null, "c"), "c")).toEqual(EMPTY_DAY_LOG);
    expect(toForm(null, "c").bbt).toBe("");
  });

  it("shows Fahrenheit and converts back to Celsius", () => {
    expect(toForm({ ...EMPTY_DAY_LOG, bbt_c: 36.5 }, "f").bbt).toBe("97.7");
    const form = { ...toForm(null, "f"), bbt: "97.7" };
    expect(fromForm(form, "f").bbt_c).toBe(36.5);
  });

  it("drops the protection when no sex was logged and keeps it null for 'no'", () => {
    const form = { ...toForm(null, "c"), sex: "no" as const, protection: "condom" as const };
    expect(fromForm(form, "c").sex).toEqual({ had: false, protection: null });
    expect(fromForm({ ...form, sex: null }, "c").sex).toBeNull();
  });

  it("turns blank notes into null and trims", () => {
    expect(fromForm({ ...toForm(null, "c"), notes: "   " }, "c").notes).toBeNull();
    expect(fromForm({ ...toForm(null, "c"), notes: " hi " }, "c").notes).toBe("hi");
  });

  it("keeps tri-state birth-control-taken", () => {
    expect(toForm({ ...EMPTY_DAY_LOG, birth_control_taken: true }, "c").bcTaken).toBe("yes");
    expect(toForm({ ...EMPTY_DAY_LOG, birth_control_taken: false }, "c").bcTaken).toBe("no");
    expect(toForm(EMPTY_DAY_LOG, "c").bcTaken).toBeNull();
  });
});

describe("validation", () => {
  it("accepts a clean form", () => {
    expect(validateForm(toForm(FULL, "c"), "c")).toEqual({});
  });

  it("rejects an out-of-range temperature and over-long notes", () => {
    const form = { ...toForm(null, "c"), bbt: "41", notes: "x".repeat(2001) };
    const errors = validateForm(form, "c");
    expect(errors.bbt).toBeDefined();
    expect(errors.notes).toBeDefined();
  });

  it("converts the typed temperature when the unit flips", () => {
    expect(convertBbtText("36.5", "c", "f")).toBe("97.7");
    expect(convertBbtText("97.7", "f", "c")).toBe("36.5");
    expect(convertBbtText("abc", "c", "f")).toBe("abc");
    expect(convertBbtText("36.5", "c", "c")).toBe("36.5");
  });

  it("limits medications", () => {
    expect(addMedication([], "Paracetamol")).toEqual({ ok: true, list: ["Paracetamol"] });
    expect(addMedication([], "x".repeat(61)).ok).toBe(false);
    expect(addMedication(Array.from({ length: 10 }, (_, i) => `m${i}`), "extra").ok).toBe(false);
  });
});

describe("settings payload", () => {
  const base: SettingsDraft = { mode: "track", age_group: "adult", luteal: "", temp_unit: "c", lmp: "", due: "", delivery: "", breastfeeding: "skip" };
  const today = "2026-10-08";

  it("sends only the keys for the chosen mode", () => {
    expect(buildSettingsPayload(base, today)).toEqual({ payload: { mode: "track", age_group: "adult", luteal_days: null, temp_unit: "c" } });
  });

  it("validates the luteal override", () => {
    expect("error" in buildSettingsPayload({ ...base, luteal: "9" }, today)).toBe(true);
    expect("error" in buildSettingsPayload({ ...base, luteal: "12.5" }, today)).toBe(true);
    expect(buildSettingsPayload({ ...base, luteal: "12" }, today)).toMatchObject({ payload: { luteal_days: 12 } });
  });

  it("needs a pregnancy date and refuses the future", () => {
    expect("error" in buildSettingsPayload({ ...base, mode: "pregnancy" }, today)).toBe(true);
    expect("error" in buildSettingsPayload({ ...base, mode: "pregnancy", lmp: "2026-12-01" }, today)).toBe(true);
    expect(buildSettingsPayload({ ...base, mode: "pregnancy", lmp: "2026-08-01" }, today)).toMatchObject({
      payload: { mode: "pregnancy", pregnancy: { lmp: "2026-08-01", due_date: null } },
    });
    expect(buildSettingsPayload({ ...base, mode: "pregnancy", due: "2027-03-01" }, today)).toMatchObject({ payload: { pregnancy: { lmp: null, due_date: "2027-03-01" } } });
  });

  it("needs a postpartum delivery date and maps breastfeeding", () => {
    expect("error" in buildSettingsPayload({ ...base, mode: "postpartum" }, today)).toBe(true);
    expect(buildSettingsPayload({ ...base, mode: "postpartum", delivery: "2026-07-01", breastfeeding: "yes" }, today)).toMatchObject({
      payload: { postpartum: { delivery_date: "2026-07-01", breastfeeding: true } },
    });
    expect(buildSettingsPayload({ ...base, mode: "postpartum", delivery: "2026-07-01", breastfeeding: "skip" }, today)).toMatchObject({
      payload: { postpartum: { breastfeeding: null } },
    });
  });

  it("builds a draft from saved settings", () => {
    const s: CycleSettings = {
      mode: "postpartum", age_group: "teen", luteal_days: 12, temp_unit: "f", privacy: { local_only: false },
      partner_share: { enabled: false, created_at: null }, pregnancy: { lmp: null, due_date: null },
      postpartum: { delivery_date: "2026-07-01", breastfeeding: false }, mode_history: [],
    };
    expect(draftFromSettings(s)).toEqual({
      mode: "postpartum", age_group: "teen", luteal: "12", temp_unit: "f", lmp: "", due: "", delivery: "2026-07-01", breastfeeding: "no",
    });
  });
});
