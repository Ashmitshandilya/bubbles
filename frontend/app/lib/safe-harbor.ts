/**
 * Safe Harbor on screen: the part of POST /chat (and a reloaded message) that sits next to a Safe Harbor reply.
 *
 * The backend (safe_harbor.payload) sends `harbor: { tier, mode, step, resources: [{ name, number, note }], actions: [{ id, label }] }`.
 * Everything is read defensively: an unknown tier is shown as tier 2, a missing list is empty, and a reply with no resources still
 * offers 112. The numbers come from the server only (India verified there; any other country gets words and no number).
 *
 * Privacy: this text is never put in a title, a notification or the offline cache. It is only drawn on the chat screen.
 */

export interface HarborResource {
  name: string;
  /** Digits to dial. Empty when there is nothing to dial ("your local emergency number", "a person you trust"). */
  number: string;
  note: string;
}

export interface HarborAction {
  id: string;
  /** Also the words sent as the next message when the chip is tapped (the server reads the choice from them). */
  label: string;
}

export interface Harbor {
  tier: 2 | 3;
  mode: string;
  step: string | null;
  resources: HarborResource[];
  actions: HarborAction[];
}

/** Shown when the server sent no resources at all: the one number that is right in India and never wrong to show. */
const EMERGENCY: HarborResource = { name: "Emergency services", number: "112", note: "Police, fire and ambulance. Free, open day and night." };
const MAX_ACTIONS = 5;
const MAX_RESOURCES = 8;

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

/** Digits only, 2 to 6 of them, with an optional leading "+". Anything else is not a number to dial. */
export function dialNumber(raw: unknown): string {
  const compact = text(raw).replace(/[\s\-().]/g, "");
  return /^\+?\d{2,6}$/.test(compact) ? compact : "";
}

/** The tel: link for a number, or null when there is nothing to dial. A link only: nothing ever dials by itself. */
export function telHref(raw: unknown): string | null {
  const digits = dialNumber(raw);
  return digits ? `tel:${digits}` : null;
}

/** Read `harbor` from a reply. Null when the reply carries none (an ordinary reply). Never throws. */
export function adaptHarbor(raw: unknown): Harbor | null {
  const data = record(raw);
  if (!data) return null;
  const resources = (Array.isArray(data.resources) ? data.resources : [])
    .map((item): HarborResource | null => {
      const r = record(item);
      const name = text(r?.name);
      return r && name ? { name, number: dialNumber(r.number), note: text(r.note) } : null;
    })
    .filter((r): r is HarborResource => r !== null)
    .slice(0, MAX_RESOURCES);
  const actions = (Array.isArray(data.actions) ? data.actions : [])
    .map((item): HarborAction | null => {
      const a = record(item);
      const id = text(a?.id);
      const label = text(a?.label);
      return a && id && label ? { id, label } : null;
    })
    .filter((a): a is HarborAction => a !== null)
    .slice(0, MAX_ACTIONS);
  return {
    tier: data.tier === 3 ? 3 : 2,
    mode: text(data.mode) || "disclosure",
    step: text(data.step) || null,
    resources: resources.length ? resources : [{ ...EMERGENCY }],
    actions,
  };
}
