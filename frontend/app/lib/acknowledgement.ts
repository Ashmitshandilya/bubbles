/** Sign-up: the person ticks that they read the Terms and the Privacy notice. That is an acknowledgement, not a consent to anything.
 *  It is remembered on this device until the first signed-in request can record it (the account may need an email confirmation first). */

import { PRIVACY_NOTICE_VERSION } from "./privacy-notice-version";

export const ACK_KEY = "bubbles.ack.pending";

export type AckStore = Pick<Storage, "getItem" | "setItem" | "removeItem"> | null;

export function ackStore(): AckStore {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function rememberAcknowledgement(store: AckStore, version: string = PRIVACY_NOTICE_VERSION): void {
  try {
    store?.setItem(ACK_KEY, version);
  } catch {
    /* storage is blocked: the acknowledgement is simply not recorded */
  }
}

export function pendingAcknowledgement(store: AckStore): string | null {
  try {
    const value = store?.getItem(ACK_KEY);
    return value ? value.slice(0, 24) : null;
  } catch {
    return null;
  }
}

/** Send a remembered acknowledgement once. It is forgotten only after the server accepted it, so a failed try is repeated next time. */
export async function flushAcknowledgement(store: AckStore, send: (version: string) => Promise<boolean>): Promise<boolean> {
  const version = pendingAcknowledgement(store);
  if (!version) return false;
  let accepted = false;
  try {
    accepted = await send(version);
  } catch {
    accepted = false;
  }
  if (accepted) {
    try {
      store?.removeItem(ACK_KEY);
    } catch {
      /* nothing to do */
    }
  }
  return accepted;
}
