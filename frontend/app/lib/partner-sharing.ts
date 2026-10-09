// Partner sharing: types and small helpers shared by the owner page and the public partner page.
// The partner page is public (no login), so its request is built here without the signed-in API provider.

import { apiBase } from "./cycle-public";

export type ShareKey = "cycle" | "sleep" | "support_note";

export interface ShareCategory {
  key: ShareKey;
  label: string;
  description: string;
}

export interface PartnerSharingStatus {
  status: "success";
  available: ShareCategory[];
  categories: ShareKey[];
  note: string;
  owner_name: string;
  /** true once the person has chosen what to share (nothing is visible to anyone before that) */
  configured: boolean;
  link: { active: boolean; expired: boolean; expires_at: string | null; views: { count: number; last_at: string | null } };
  invite: { active: boolean; expires_at: string | null };
  connection: { name: string; since: string } | null;
  sharing: boolean;
  never_shared: string[];
  /** Present ONLY in the answer to creating a link / invite: never stored or shown again. */
  token?: string;
  share_path?: string;
  code?: string;
}

export interface PartnerSection {
  key: string;
  title: string;
  text?: string | null;
  detail?: string | null;
  caveat?: string | null;
  range?: { earliest: string; latest: string } | null;
  tips?: string[] | null;
  tips_caveat?: string | null;
}

export interface PartnerShareView {
  status: "success";
  label: string;
  expires_at: string;
  sections: PartnerSection[];
  notice: string;
}

export interface SharedWithMe {
  status: "success";
  shares: { id: string; from_name: string; since: string | null; sections: PartnerSection[]; notice: string }[];
}

export const EXPIRY_OPTIONS = [7, 30, 90] as const;
export const NOTE_MAX = 500;
export const NAME_MAX = 40;

export function shareEndpoint(token: string, base: string = apiBase()): string {
  return `${base}/partner/${encodeURIComponent(token)}`;
}

/** The address the partner opens (the site, not the API). */
export function shareLink(origin: string, token: string): string {
  return `${origin.replace(/\/+$/, "")}/partner/${encodeURIComponent(token)}`;
}

export function whatsappLink(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

/** The message sent with an invite code. It carries the code and where to type it, never any health data. */
export function inviteMessage(code: string, origin: string): string {
  return `I'd like to share a few things with you on Bubbles. Sign in at ${origin.replace(/\/+$/, "")}/partner and enter this code: ${code} (it works for 48 hours).`;
}

/** Whole days left, never negative; null when there is no date. */
export function daysLeft(expiresAt: string | null | undefined, now: number = Date.now()): number | null {
  if (!expiresAt) return null;
  const end = Date.parse(expiresAt);
  if (Number.isNaN(end)) return null;
  return Math.max(0, Math.ceil((end - now) / 86_400_000));
}

/** Whole hours left (for the 48-hour invite), never negative; null when there is no date. */
export function hoursLeft(expiresAt: string | null | undefined, now: number = Date.now()): number | null {
  if (!expiresAt) return null;
  const end = Date.parse(expiresAt);
  if (Number.isNaN(end)) return null;
  return Math.max(0, Math.ceil((end - now) / 3_600_000));
}

/** A choice is valid when at least one thing is picked and a note exists whenever the note is picked. */
export function canSave(categories: ShareKey[], note: string): boolean {
  if (categories.length === 0) return false;
  if (categories.includes("support_note") && note.trim().length === 0) return false;
  return note.length <= NOTE_MAX;
}

/** Tidy what a person types as an invite code: letters and digits only, upper case, shown as XXXX-XXXX. */
export function formatCodeInput(raw: string): string {
  const clean = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);
  return clean.length > 4 ? `${clean.slice(0, 4)}-${clean.slice(4)}` : clean;
}

export function codeIsComplete(code: string): boolean {
  return code.replace(/[^A-Z0-9]/gi, "").length === 8;
}
