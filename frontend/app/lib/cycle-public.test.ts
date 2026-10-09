import { describe, expect, it } from "vitest";
import { apiBase, partnerEndpoint, partnerErrorMessage } from "./cycle-public";

describe("partner page helpers", () => {
  it("builds the anonymous endpoint, encoding the token", () => {
    expect(apiBase("https://api.example.com/")).toBe("https://api.example.com");
    expect(apiBase(undefined)).toMatch(/^https?:\/\//);
    expect(partnerEndpoint("abc_123-x", "https://api.example.com")).toBe("https://api.example.com/cycle/partner/abc_123-x");
    expect(partnerEndpoint("a/b?c", "https://api.example.com")).toBe("https://api.example.com/cycle/partner/a%2Fb%3Fc");
  });

  it("uses kind wording for each failure", () => {
    expect(partnerErrorMessage(404)).toBe("This link is no longer active.");
    expect(partnerErrorMessage(410)).toBe("This link is no longer active.");
    expect(partnerErrorMessage(null)).toContain("could not be reached");
    expect(partnerErrorMessage(429)).toContain("Too many");
    expect(partnerErrorMessage(500)).toContain("try again later");
  });
});
