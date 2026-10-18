// The Android app's side of Firebase (docs/FIREBASE.md): phone reminders (Cloud Messaging) and crash reports (Crashlytics).
// App-only: import it with import() behind isNativeApp, like components/NativeBridge.tsx, so the website never loads Capacitor.
// Everything resolves to "off" on an app built without google-services.json, and on older APKs without the BubblesFirebase plugin.

import type { PluginListenerHandle } from "@capacitor/core";
import { routeForReminder, type PhoneProblem } from "../app/lib/phone-reminders";

/** The app's own plugin (android/.../BubblesFirebasePlugin.java). */
type BubblesFirebase = {
  status(): Promise<{ configured?: boolean; crashReports?: boolean }>;
  setCrashReports(options: { enabled: boolean }): Promise<{ crashReports?: boolean }>;
};
export type FirebaseStatus = { configured: boolean; crashReports: boolean };
type ApiFetch = (path: string, options?: RequestInit) => Promise<Response>;
export type PhoneResult = { ok: true } | { ok: false; problem: PhoneProblem };

const CHANNEL = "reminders";             // the channel the server names in every message (backend/push_fcm.py)
const SAVED_TOKEN = "bubbles.phoneToken"; // app-private storage: the token this phone gave the server, so it can be taken back
const refreshed = new Set<string>();

let plugin: Promise<BubblesFirebase> | null = null;
function firebase(): Promise<BubblesFirebase> {
  plugin ??= import("@capacitor/core").then(({ registerPlugin }) => registerPlugin<BubblesFirebase>("BubblesFirebase"));
  return plugin;
}

function savedToken(): string | null {
  try {
    return window.localStorage.getItem(SAVED_TOKEN);
  } catch {
    return null;
  }
}

function saveToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(SAVED_TOKEN, token);
    else window.localStorage.removeItem(SAVED_TOKEN);
  } catch {
    // storage can be unavailable; the server still drops a token FCM reports as gone
  }
}

export async function firebaseStatus(): Promise<FirebaseStatus> {
  try {
    const status = await (await firebase()).status();
    return { configured: status.configured === true, crashReports: status.crashReports === true };
  } catch {
    return { configured: false, crashReports: false };
  }
}

/** Turns crash reports on or off for this phone and resolves to the new state. Rejects when Firebase isn't in the build. */
export async function setCrashReports(enabled: boolean): Promise<boolean> {
  const result = await (await firebase()).setCrashReports({ enabled });
  return result.crashReports === true;
}

/** This phone's notification token. `ask` shows Android's permission prompt (only from a tap on the switch). */
export async function phoneToken(ask: boolean): Promise<{ ok: true; token: string } | { ok: false; problem: PhoneProblem }> {
  if (!(await firebaseStatus()).configured) return { ok: false, problem: "unavailable" };
  const { PushNotifications } = await import("@capacitor/push-notifications");
  const handles: PluginListenerHandle[] = [];
  try {
    let permission = await PushNotifications.checkPermissions();
    if (permission.receive !== "granted" && ask) permission = await PushNotifications.requestPermissions();
    if (permission.receive !== "granted") return { ok: false, problem: "denied" };
    // Private on the lock screen; the text is plain anyway (the server only sends fixed templates).
    await PushNotifications.createChannel({ id: CHANNEL, name: "Reminders", description: "Plain reminders from Bubbles", importance: 3, visibility: 0 }).catch(() => undefined);
    const token = await new Promise<string>((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error("timeout")), 20_000);
      void Promise.all([
        PushNotifications.addListener("registration", ({ value }) => {
          window.clearTimeout(timer);
          resolve(value);
        }),
        PushNotifications.addListener("registrationError", () => {
          window.clearTimeout(timer);
          reject(new Error("registration"));
        }),
      ])
        .then((listeners) => {
          handles.push(...listeners);
          return PushNotifications.register();
        })
        .catch(reject);
    });
    return { ok: true, token };
  } catch {
    return { ok: false, problem: "failed" };
  } finally {
    handles.forEach((handle) => void handle.remove());
  }
}

/** Gives this phone's token to the server for the signed-in person. The server refuses it until the person's yes is saved. */
export async function registerPhone(api: ApiFetch, token: string): Promise<PhoneResult> {
  try {
    const response = await api("/notifications/devices", { method: "POST", body: JSON.stringify({ token, platform: "android" }) });
    if (!response.ok) return { ok: false, problem: "failed" };
  } catch {
    return { ok: false, problem: "failed" };
  }
  saveToken(token);
  return { ok: true };
}

/** Gets this phone's token and gives it to the server (the yes is already saved). */
export async function connectPhone(api: ApiFetch, ask: boolean): Promise<PhoneResult> {
  const result = await phoneToken(ask);
  return result.ok ? registerPhone(api, result.token) : result;
}

/** Takes the token back from the server (when it can) and deletes it on the phone, so nothing more can arrive. Never throws. */
export async function disconnectPhone(api?: ApiFetch): Promise<void> {
  const token = savedToken();
  if (api && token) {
    await api("/notifications/devices/remove", { method: "POST", body: JSON.stringify({ token }) }).catch(() => undefined);
  }
  saveToken(null);
  if (!(await firebaseStatus()).configured) return;
  try {
    const { PushNotifications } = await import("@capacitor/push-notifications");
    await PushNotifications.unregister();   // deletes the token: the server drops it on its next send
  } catch {
    // nothing to remove
  }
}

/**
 * After sign-in: if this person turned phone reminders on, reconnect this phone without asking again (the token can change,
 * and a new sign-in on a shared phone takes the phone over). Once per person per app run. Never throws.
 */
export async function refreshPhone(uid: string, api: ApiFetch): Promise<void> {
  if (refreshed.has(uid)) return;
  refreshed.add(uid);
  try {
    if (!(await firebaseStatus()).configured) return;
    const response = await api("/notifications/settings");
    if (!response.ok) return;
    const body = (await response.json()) as { settings?: { channels?: { push?: boolean } }; channels?: { push?: { available?: boolean } } };
    if (body.settings?.channels?.push === true && body.channels?.push?.available === true) await connectPhone(api, false);
    else if (body.settings?.channels?.push === false && savedToken()) await disconnectPhone(api);   // withdrawn elsewhere (Privacy choices)
  } catch {
    refreshed.delete(uid);
  }
}

/**
 * Sign-out: tell the server to forget this phone (while the session still works), then delete the token on the phone, so the next
 * person to sign in here never gets this person's reminders. `api` is optional so a failed or offline call still deletes the token.
 */
export async function forgetPhoneOnSignOut(api?: ApiFetch): Promise<void> {
  refreshed.clear();
  await disconnectPhone(api);
}

/** A tap on a reminder (also the tap that launched the app) opens the matching screen. Resolves to a function that stops listening. */
export async function onReminderTap(go: (path: string) => void): Promise<() => void> {
  try {
    if (!(await firebaseStatus()).configured) return () => undefined;
    const { PushNotifications } = await import("@capacitor/push-notifications");
    const handle = await PushNotifications.addListener("pushNotificationActionPerformed", ({ notification }) => go(routeForReminder(notification.data?.kind)));
    return () => void handle.remove();
  } catch {
    return () => undefined;
  }
}

const ASKED = "bubbles.phoneRemindersAsked";   // this phone already showed the first-run card (either answer)

/** First-run card: offer phone reminders once per phone, only when they can work and are not on yet. Never throws. */
export async function shouldOfferPhone(api: ApiFetch): Promise<boolean> {
  try {
    if (window.localStorage.getItem(ASKED)) return false;
    if (!(await firebaseStatus()).configured) return false;
    const response = await api("/notifications/settings");
    if (!response.ok) return false;
    const body = (await response.json()) as { settings?: { channels?: { push?: boolean } }; channels?: { push?: { available?: boolean } } };
    return body.channels?.push?.available === true && body.settings?.channels?.push !== true;
  } catch {
    return false;
  }
}

export function markPhoneOffered() {
  try {
    window.localStorage.setItem(ASKED, "1");
  } catch {
    // the card may show once more; harmless
  }
}

/**
 * "Turn on" on the first-run card. The in-app switch (and with it the server's consent yes) is saved first, because the server
 * refuses a phone's token until that yes exists; then Android's prompt, then the token. If either later step fails, the switch is put back.
 */
export async function turnOnPhoneReminders(api: ApiFetch): Promise<PhoneResult> {
  if (!(await firebaseStatus()).configured) return { ok: false, problem: "unavailable" };
  const setSwitch = async (push: boolean): Promise<boolean> => {
    try {
      return (await api("/notifications/settings", { method: "PUT", body: JSON.stringify({ channels: { push } }) })).ok;
    } catch {
      return false;
    }
  };
  if (!(await setSwitch(true))) return { ok: false, problem: "failed" };
  const connected = await connectPhone(api, true);
  if (!connected.ok) await setSwitch(false);
  return connected;
}
