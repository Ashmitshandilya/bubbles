import * as React from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

(globalThis as { React?: typeof React }).React = React;

const flags = { native: false };
vi.mock("../../lib/native", () => ({ get isNativeApp() { return flags.native; } }));
vi.mock("../Providers", () => ({ useApi: () => ({ fetchBubbles: async () => new Response("{}") }) }));
vi.mock("./useWellness", () => ({ useWellnessSend: () => async () => ({ ok: true, data: {} }), useWellnessQuery: () => [{ status: "loading" }, () => undefined] }));
vi.mock("../hub/HubKit", () => ({ BTN_PRIMARY: "p", BTN_SECONDARY: "s" }));
vi.mock("../tracking/kit", () => ({ Stepper: () => null }));
vi.mock("next/link", () => ({ default: (p: { href: string; children: unknown }) => createElement("a", { href: p.href }, p.children as never) }));

import { Form } from "./NotificationSettingsCard";
import type { NotificationSettingsResponse } from "../../app/lib/wellness-types";

const data = (push: boolean, available: boolean): NotificationSettingsResponse => ({
  settings: { channels: { in_app: true, email: false, push }, quiet_hours: { enabled: true, start: "23:00", end: "07:00" }, daily_cap: 5, types: { water: true, med: true, winddown: true }, tz_offset_minutes: 0 },
  channels: { in_app: { available: true }, email: { available: false }, push: { available } },
});
const html = (d: NotificationSettingsResponse) => renderToStaticMarkup(createElement(Form, { data: d, onSaved: () => undefined }));

describe("reminders card: the phone switch", () => {
  it("is not on the website, whatever the server says, and a saved yes is not shown there", () => {
    flags.native = false;
    expect(html(data(true, true))).not.toContain("On this phone");
  });

  it("waits for the phone to say Firebase is in the build before offering the switch (never at launch, never a prompt)", () => {
    flags.native = true;
    expect(html(data(false, true))).not.toContain("On this phone");
  });

  it("is hidden when the server has no Firebase", () => {
    flags.native = true;
    expect(html(data(false, false))).not.toContain("On this phone");
  });
});
