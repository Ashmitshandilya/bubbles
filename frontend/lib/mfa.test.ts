import { describe, expect, it } from "vitest";
import { cleanCode, friendlyMfaError, isValidCode, needsSecondStep, verifiedTotp } from "./mfa";

describe("two-step sign-in helpers", () => {
  it("asks for the code only when the account needs aal2 and the session is not there yet", () => {
    expect(needsSecondStep({ currentLevel: "aal1", nextLevel: "aal2" })).toBe(true);
    expect(needsSecondStep({ currentLevel: "aal2", nextLevel: "aal2" })).toBe(false);
    expect(needsSecondStep({ currentLevel: "aal1", nextLevel: "aal1" })).toBe(false);
    expect(needsSecondStep(null)).toBe(false);
    expect(needsSecondStep(undefined)).toBe(false);
  });

  it("picks only a verified authenticator-app factor", () => {
    expect(verifiedTotp([{ id: "a", factor_type: "totp", status: "unverified" }])).toBeNull();
    expect(verifiedTotp([{ id: "b", factor_type: "phone", status: "verified" }])).toBeNull();
    expect(verifiedTotp([{ id: "a", factor_type: "totp", status: "unverified" }, { id: "c", factor_type: "totp", status: "verified" }])?.id).toBe("c");
    expect(verifiedTotp(null)).toBeNull();
  });

  it("accepts a six digit code typed the way authenticator apps show it", () => {
    expect(cleanCode("123 456")).toBe("123456");
    expect(cleanCode("123-456")).toBe("123456");
    expect(isValidCode("123 456")).toBe(true);
    expect(isValidCode("12345")).toBe(false);
    expect(isValidCode("1234567")).toBe(false);
    expect(isValidCode("12a456")).toBe(false);
    expect(isValidCode("")).toBe(false);
  });

  it("explains errors in plain words without an em-dash", () => {
    expect(friendlyMfaError("Invalid TOTP code entered")).toMatch(/didn't work/);
    expect(friendlyMfaError("rate limit exceeded")).toMatch(/Too many tries/);
    expect(friendlyMfaError("Failed to fetch")).toMatch(/couldn't reach/);
    expect(friendlyMfaError(undefined)).toMatch(/couldn't check/);
    for (const m of ["invalid", "rate limit", "fetch", "x"]) expect(friendlyMfaError(m)).not.toContain("—");
  });
});
