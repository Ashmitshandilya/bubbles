import { beforeEach, describe, expect, it, vi } from "vitest";

// The phone side of reminders with the Capacitor plugins faked: denied permission, offline, withdrawal and sign-out.
type Listener = (event: never) => void;
const state = {
  configured: true,
  permission: "prompt" as "prompt" | "granted" | "denied",
  registerOutcome: "token" as "token" | "error" | "never",
  listeners: new Map<string, Listener>(),
  unregistered: 0,
  asked: 0,
};
const store = new Map<string, string>();

vi.mock("@capacitor/core", () => ({
  registerPlugin: () => ({
    status: async () => ({ configured: state.configured, crashReports: false }),
    setCrashReports: async () => ({ crashReports: false }),
  }),
}));
vi.mock("@capacitor/push-notifications", () => ({
  PushNotifications: {
    checkPermissions: async () => ({ receive: state.permission }),
    requestPermissions: async () => {
      state.asked += 1;
      if (state.permission === "prompt") state.permission = "denied";
      return { receive: state.permission };
    },
    createChannel: async () => undefined,
    addListener: async (name: string, fn: Listener) => {
      state.listeners.set(name, fn);
      return { remove: async () => void state.listeners.delete(name) };
    },
    register: async () => {
      if (state.registerOutcome === "token") state.listeners.get("registration")?.({ value: "tok-1" } as never);
      if (state.registerOutcome === "error") state.listeners.get("registrationError")?.({} as never);
    },
    unregister: async () => void (state.unregistered += 1),
  },
}));

import { connectPhone, disconnectPhone, forgetPhoneOnSignOut, onReminderTap, phoneToken, refreshPhone, registerPhone, turnOnPhoneReminders } from "./firebase-native";

const ok = () => Promise.resolve(new Response("{}", { status: 200 }));

beforeEach(() => {
  Object.assign(state, { configured: true, permission: "prompt", registerOutcome: "token", unregistered: 0, asked: 0 });
  state.listeners.clear();
  store.clear();
  vi.stubGlobal("window", {
    localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), removeItem: (k: string) => void store.delete(k) },
    setTimeout,
    clearTimeout,
  });
});

describe("asking for the token", () => {
  it("never shows the prompt unless asked from a tap, and reports a refusal as denied", async () => {
    expect(await phoneToken(false)).toEqual({ ok: false, problem: "denied" });
    expect(state.asked).toBe(0);
    expect(await phoneToken(true)).toEqual({ ok: false, problem: "denied" });
    expect(state.asked).toBe(1);
  });

  it("gives the token once the person allowed notifications", async () => {
    state.permission = "granted";
    expect(await phoneToken(false)).toEqual({ ok: true, token: "tok-1" });
  });

  it("is unavailable in a build without Firebase and fails soft when registration errors", async () => {
    state.configured = false;
    expect(await phoneToken(true)).toEqual({ ok: false, problem: "unavailable" });
    state.configured = true;
    state.permission = "granted";
    state.registerOutcome = "error";
    expect(await phoneToken(true)).toEqual({ ok: false, problem: "failed" });
    expect(state.listeners.size).toBe(0);
  });
});

describe("handing the token to the server", () => {
  it("keeps nothing on the phone when offline or refused", async () => {
    expect(await registerPhone(() => Promise.reject(new Error("offline")), "tok-1")).toEqual({ ok: false, problem: "failed" });
    expect(await registerPhone(() => Promise.resolve(new Response("{}", { status: 422 })), "tok-1")).toEqual({ ok: false, problem: "failed" });
    expect(store.size).toBe(0);
  });

  it("remembers the token that was accepted so it can be taken back", async () => {
    const api = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>(ok);
    expect(await registerPhone(api, "tok-1")).toEqual({ ok: true });
    expect(JSON.parse(api.mock.calls[0][1]?.body as string)).toEqual({ token: "tok-1", platform: "android" });
    state.permission = "granted";
    store.clear();
    expect(await connectPhone(api, false)).toEqual({ ok: true });
    expect(store.get("bubbles.phoneToken")).toBe("tok-1");
  });
});

describe("withdrawal and sign-out", () => {
  it("sign-out tells the server first, then deletes the token on the phone, even when offline", async () => {
    store.set("bubbles.phoneToken", "tok-1");
    const api = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>(ok);
    await forgetPhoneOnSignOut(api);
    expect(api.mock.calls[0][0]).toBe("/notifications/devices/remove");
    expect(state.unregistered).toBe(1);
    expect(store.size).toBe(0);
    store.set("bubbles.phoneToken", "tok-2");
    await forgetPhoneOnSignOut(() => Promise.reject(new Error("offline")));
    expect(state.unregistered).toBe(2);
    expect(store.size).toBe(0);
  });

  it("disconnecting with no token saved does not call the server", async () => {
    const api = vi.fn<(path: string, init?: RequestInit) => Promise<Response>>(ok);
    await disconnectPhone(api);
    expect(api).not.toHaveBeenCalled();
  });

  it("reconnects silently when the switch is on, and lets go when it was withdrawn somewhere else", async () => {
    state.permission = "granted";
    const settings = (push: boolean) => () => Promise.resolve(new Response(JSON.stringify({ settings: { channels: { push } }, channels: { push: { available: true } } })));
    const calls: string[] = [];
    await refreshPhone("u-on", async (path) => (calls.push(path), path === "/notifications/settings" ? settings(true)() : ok()));
    expect(calls).toEqual(["/notifications/settings", "/notifications/devices"]);
    expect(state.asked).toBe(0);
    calls.length = 0;
    await refreshPhone("u-off", async (path) => (calls.push(path), path === "/notifications/settings" ? settings(false)() : ok()));
    expect(calls).toEqual(["/notifications/settings", "/notifications/devices/remove"]);
    expect(state.unregistered).toBe(1);
    expect(store.size).toBe(0);
  });

  it("does nothing offline and tries again next time", async () => {
    const down = vi.fn(() => Promise.reject(new Error("offline")));
    await refreshPhone("u-net", down);
    await refreshPhone("u-net", down);
    expect(down).toHaveBeenCalledTimes(2);
  });
});

describe("tapping a reminder", () => {
  it("opens the screen for the kind and ignores a forged path", async () => {
    const go = vi.fn();
    const stop = await onReminderTap(go);
    const tap = state.listeners.get("pushNotificationActionPerformed")!;
    tap({ notification: { data: { kind: "water" } } } as never);
    tap({ notification: { data: { kind: "/admin" } } } as never);
    tap({ notification: {} } as never);
    expect(go.mock.calls.map((c) => c[0])).toEqual(["/hydration", "/notifications", "/notifications"]);
    stop();
  });

  it("does not listen in a build without Firebase", async () => {
    state.configured = false;
    await onReminderTap(vi.fn());
    expect(state.listeners.size).toBe(0);
  });
});

describe("turning phone reminders on from the first-run card", () => {
  /** A server that, like the real one, refuses a token until the switch (and the consent yes) is saved. */
  function server() {
    const calls: string[] = [];
    let on = false;
    const api = async (path: string, init?: RequestInit) => {
      calls.push(path + (init?.body ? ` ${init.body}` : ""));
      if (path === "/notifications/settings") on = JSON.parse(String(init?.body)).channels.push;
      if (path === "/notifications/devices" && !on) return new Response("{}", { status: 422 });
      return new Response("{}", { status: 200 });
    };
    return { api, calls };
  }

  it("saves the switch first, then asks Android, then registers, so a fresh account works", async () => {
    state.permission = "granted";
    const { api, calls } = server();
    expect(await turnOnPhoneReminders(api)).toEqual({ ok: true });
    expect(calls).toEqual(['/notifications/settings {"channels":{"push":true}}', '/notifications/devices {"token":"tok-1","platform":"android"}']);
  });

  it("puts the switch back when Android's prompt is refused", async () => {
    const { api, calls } = server();
    expect(await turnOnPhoneReminders(api)).toEqual({ ok: false, problem: "denied" });
    expect(calls).toEqual(['/notifications/settings {"channels":{"push":true}}', '/notifications/settings {"channels":{"push":false}}']);
  });

  it("changes nothing on a build without Firebase", async () => {
    state.configured = false;
    const { api, calls } = server();
    expect(await turnOnPhoneReminders(api)).toEqual({ ok: false, problem: "unavailable" });
    expect(calls).toEqual([]);
  });
});
