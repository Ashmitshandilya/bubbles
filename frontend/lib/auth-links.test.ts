import { describe, expect, it } from "vitest";
import { authCallbackUrl, looksLikeAuthReturn, siteUrl } from "./auth-links";

describe("authCallbackUrl", () => {
  it("keeps local development local", () => {
    expect(authCallbackUrl("http://localhost:3000")).toBe("http://localhost:3000/callback");
    expect(authCallbackUrl("http://127.0.0.1:3100/")).toBe("http://127.0.0.1:3100/callback");
  });
  it("never sends an email link to a vercel.app address", () => {
    expect(authCallbackUrl("https://bubbles-abc123.vercel.app")).toBe("https://heybubbles.in/callback");
  });
  it("uses the configured site address and trims a trailing slash", () => {
    expect(authCallbackUrl("https://heybubbles.in", "https://example.test/")).toBe("https://example.test/callback");
    expect(siteUrl("  ")).toBe("https://heybubbles.in");
  });
  it("falls back to the site address when the origin is unreadable", () => {
    expect(authCallbackUrl("not a url")).toBe("https://heybubbles.in/callback");
  });
});

describe("looksLikeAuthReturn", () => {
  it("catches tokens, errors and codes that land on the wrong page", () => {
    expect(looksLikeAuthReturn("/", "", "#access_token=a&refresh_token=b&type=signup")).toBe(true);
    expect(looksLikeAuthReturn("/login", "", "#error=access_denied&error_code=otp_expired&error_description=x")).toBe(true);
    expect(looksLikeAuthReturn("/", "?code=abc", "")).toBe(true);
    expect(looksLikeAuthReturn("/", "?token_hash=abc&type=signup", "")).toBe(true);
  });
  it("leaves /callback and ordinary pages alone", () => {
    expect(looksLikeAuthReturn("/callback", "", "#access_token=a")).toBe(false);
    expect(looksLikeAuthReturn("/dashboard", "", "")).toBe(false);
    expect(looksLikeAuthReturn("/care", "?code=abc", "")).toBe(false);
  });
});
