// Phone reminders (Android app, Firebase Cloud Messaging) and crash reports: the decisions and wording, kept free of Capacitor so
// they are tested here and the website can import them. The phone side lives in lib/firebase-native.ts. See docs/FIREBASE.md.

/** "ready": the switch is offered. "hidden": the website, an app built without Firebase, or a server without it. */
export type PhoneRow = "hidden" | "checking" | "ready";

export function phoneRow(nativeApp: boolean, firebase: boolean | null, serverAvailable: boolean): PhoneRow {
  if (!nativeApp || !serverAvailable || firebase === false) return "hidden";
  return firebase === null ? "checking" : "ready";
}

/** The push value to save. Only the app can change it: saving on the website keeps what the phone chose. */
export function pushToSave(row: PhoneRow, draft: boolean, saved: boolean): boolean {
  return row === "ready" ? draft : saved;
}

export type PhoneProblem = "unavailable" | "denied" | "failed";

export function phoneProblemMessage(problem: PhoneProblem): string {
  if (problem === "denied") return "Notifications are off for Bubbles on this phone. Turn them on in your phone's settings, then try again.";
  if (problem === "unavailable") return "Phone reminders aren't available in this version of the app.";
  return "Couldn't connect this phone. Check your connection and try again.";
}

export type PushTestResult = { sent?: number; removed?: number; reason?: string };

export function pushTestMessage(result: PushTestResult): string {
  if (result.reason === "wait") return "A test was just sent. Try again in a minute.";
  if ((result.sent ?? 0) > 0) return "Test sent. It can take a few seconds to arrive.";
  if (result.reason === "no_devices" || (result.removed ?? 0) > 0) return "This phone isn't connected. Turn phone reminders off and on again.";
  return "Couldn't send the test right now. Your reminders still show in Bubbles.";
}

/** Where a tap on a reminder goes. Only the reminder kind travels in the message, never anything about the person. */
export function routeForReminder(kind: unknown): string {
  if (kind === "water") return "/hydration";
  if (kind === "med") return "/medications";
  if (kind === "winddown") return "/sleep";
  return "/notifications";
}
