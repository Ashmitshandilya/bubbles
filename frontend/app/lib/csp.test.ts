import { afterEach, describe, expect, it, vi } from "vitest";
import { contentSecurityPolicy } from "../../next.config";

describe("content security policy", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("closes the dangerous doors", () => {
    const csp = contentSecurityPolicy();
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
    expect(csp).toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("lets the browser talk only to the API and the sign-in service", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test/");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://abc123.supabase.co");
    const connect = contentSecurityPolicy().split("; ").find((d) => d.startsWith("connect-src")) ?? "";
    expect(connect).toBe("connect-src 'self' https://api.example.test https://abc123.supabase.co wss://abc123.supabase.co");
  });

  it("falls back to the live API and the whole supabase.co family when the variables are missing", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    const connect = contentSecurityPolicy().split("; ").find((d) => d.startsWith("connect-src")) ?? "";
    expect(connect).toContain("https://bubbles-dk3v.onrender.com");
    expect(connect).toContain("https://*.supabase.co");
    expect(connect).not.toMatch(/\bhttp:/);
  });
});
