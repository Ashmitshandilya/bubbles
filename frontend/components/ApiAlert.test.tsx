import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MESSAGES, parseHealth } from "../app/lib/connection";

// vitest compiles JSX with the classic runtime (tsconfig has jsx: "preserve"), so components expect `React` in scope.
(globalThis as { React?: typeof React }).React = React;

type Api = Record<string, unknown>;
let api: Api;

vi.mock("./Providers", () => ({ useApi: () => api }));
vi.mock("next/navigation", () => ({ usePathname: () => "/sleep" }));
vi.mock("next/link", () => ({
  default: (props: { href: string; children: unknown; className?: string }) =>
    createElement("a", { href: props.href, className: props.className }, props.children as never),
}));
vi.mock("./AskBubbles", () => ({ AskBubbles: () => null }));
vi.mock("./BubblesMascot", () => ({ BubblesMascot: () => null }));

import { ApiAlert } from "./Navigation";

const online = { apiStatus: "online", connectionError: null, nextRetryAt: null, retrying: false, checkApiHealth: async () => {} };
const compat = parseHealth({ status: "healthy", services: { api: "healthy", database: "permission_denied" }, compat_mode: true, denied_tables: ["profiles"] });
const healthy = parseHealth({ status: "healthy", services: { api: "healthy", database: "ok" }, compat_mode: false, denied_tables: [] });
const html = () => renderToStaticMarkup(createElement(ApiAlert));

beforeEach(() => {
  api = { ...online, health: healthy };
});

describe("ApiAlert", () => {
  it("renders nothing when Bubbles is healthy, still checking, or health is unknown", () => {
    expect(html()).toBe("");
    api = { ...online, apiStatus: "checking", health: null };
    expect(html()).toBe("");
    api = { ...online, health: null };
    expect(html()).toBe("");
  });

  it("waking: a calm status with no dismiss or settings buttons", () => {
    api = { ...online, apiStatus: "checking", health: null, waking: true };
    const out = html();
    expect(out).toMatch(/waking up/);
    expect(out).not.toMatch(/Dismiss|Settings|Try again/);
  });

  it("offline: a blocking alert with the plain message, the countdown, and a retry button", () => {
    api = { ...online, apiStatus: "offline", connectionError: MESSAGES.offline, health: null, nextRetryAt: Date.now() + 6000 };
    const out = html();
    expect(out).toContain('role="alert"');
    expect(out).toContain("Can&#x27;t connect to Bubbles");
    expect(out).toContain("start_bubbles.bat");
    expect(out).toMatch(/Trying again in [56]s/);
    expect(out).toContain("Try again now");
    // the ticking countdown is hidden from assistive tech so it is not re-announced every second
    expect(out).toMatch(/aria-hidden="true"[^>]*><span[^>]*><\/span>Trying again in/);
  });

  it("offline while a probe is running says so and disables the button", () => {
    api = { ...online, apiStatus: "offline", connectionError: null, health: null, retrying: true };
    const out = html();
    expect(out).toContain("Checking now…");
    expect(out).toMatch(/<button[^>]*disabled/);
    expect(out).toContain("start_bubbles.bat"); // falls back to the standard offline message
  });

  it("compatibility mode: a calm, dismissible status (not an alert) that points to Settings", () => {
    api = { ...online, health: compat };
    const out = html();
    expect(out).toContain('role="status"');
    expect(out).not.toContain('role="alert"');
    expect(out).toContain("compatibility mode");
    expect(out).toContain('href="/settings"');
    expect(out).toContain("Dismiss");
  });

  it("offline outranks compatibility mode", () => {
    api = { ...online, apiStatus: "offline", connectionError: MESSAGES.offline, health: compat };
    const out = html();
    expect(out).toContain('role="alert"');
    expect(out).not.toContain("compatibility mode");
  });
});
