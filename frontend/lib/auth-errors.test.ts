import { describe, expect, it } from "vitest";
import { RESEND_COOLDOWN_SECONDS, friendlyAuthError } from "./auth-errors";

describe("friendlyAuthError", () => {
  it("explains an unconfirmed email and offers a resend", () => {
    const f = friendlyAuthError("Email not confirmed");
    expect(f.needsConfirmation).toBe(true);
    expect(f.text).toMatch(/confirm your email/i);
  });

  it("does not reveal whether an address has an account on wrong credentials", () => {
    const f = friendlyAuthError("Invalid login credentials");
    expect(f.needsConfirmation).toBe(false);
    expect(f.text).not.toMatch(/no account|not registered/i);
  });

  it("turns rate limits and waits into calm sentences", () => {
    expect(friendlyAuthError("For security purposes, you can only request this after 42 seconds.").text).toBe(
      "Please wait 42 seconds before asking for another email.",
    );
    expect(friendlyAuthError("email rate limit exceeded").text).toMatch(/wait a few minutes/);
  });

  it("handles an existing account, a weak password, and unknown text", () => {
    expect(friendlyAuthError("User already registered").text).toMatch(/Try signing in/);
    expect(friendlyAuthError("Password should be at least 6 characters").text).toMatch(/at least 6/);
    expect(friendlyAuthError("Some other thing").text).toBe("Some other thing");
    expect(friendlyAuthError(undefined).text).toMatch(/Something went wrong/);
    expect(RESEND_COOLDOWN_SECONDS).toBeGreaterThanOrEqual(30);
  });

  it("never uses an em-dash", () => {
    for (const m of ["Email not confirmed", "Invalid login credentials", "User already registered", "rate limit", "x"])
      expect(friendlyAuthError(m).text).not.toContain("—");
  });
});
