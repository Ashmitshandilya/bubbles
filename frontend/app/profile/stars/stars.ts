// Pure pieces of the Stars lens screen: reading what the server sends and checking the form before it is sent. No React: tested in stars.test.ts.

export interface StarsItem {
  id: string;
  source: string;
  text: string;
  uncertain: boolean;
  match: "Matches what we've seen" | "Not what we've seen" | "Not enough to tell";
}

export interface Placement {
  rashi: string;
  nakshatra: string;
  rashiOptions: string[];
  nakshatraOptions: string[];
  pada: number | null;
  cusp: boolean;
}

export interface Stars {
  intro: string;
  consent: boolean;
  enabled: boolean;
  timeKnown: boolean;
  moon: Placement | null;
  sun: Placement | null;
  ascendant: Placement | null;
  items: StarsItem[];
  birth: { date: string; time: string | null; place: string } | null;
}

export interface PlaceHit {
  id: string;
  name: string;
  region: string;
  country: string;
}

const MATCHES = ["Matches what we've seen", "Not what we've seen", "Not enough to tell"] as const;
const object = (v: unknown): Record<string, unknown> | null => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null);
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

function readPlacement(raw: unknown): Placement | null {
  const p = object(raw);
  if (!p || typeof p.rashi !== "string") return null;
  return {
    rashi: p.rashi,
    nakshatra: typeof p.nakshatra === "string" ? p.nakshatra : "",
    rashiOptions: strings(p.rashi_options).length ? strings(p.rashi_options) : [p.rashi],
    nakshatraOptions: strings(p.nakshatra_options).length ? strings(p.nakshatra_options) : typeof p.nakshatra === "string" ? [p.nakshatra] : [],
    pada: typeof p.pada === "number" ? p.pada : null,
    cusp: p.cusp === true,
  };
}

export function readStars(raw: unknown): Stars | null {
  const body = object(raw);
  if (!body || typeof body.intro !== "string") return null;
  const chart = object(body.chart);
  const birth = object(body.birth);
  const place = object(birth?.place);
  return {
    intro: body.intro,
    consent: body.consent === true,
    enabled: body.enabled === true,
    timeKnown: chart?.time_known === true,
    moon: readPlacement(chart?.moon),
    sun: readPlacement(chart?.sun),
    ascendant: readPlacement(chart?.ascendant),
    items: (Array.isArray(body.items) ? body.items : []).flatMap((i): StarsItem[] => {
      const item = object(i);
      if (!item || typeof item.id !== "string" || typeof item.text !== "string" || typeof item.source !== "string") return [];
      const match = MATCHES.find((m) => m === item.match) ?? "Not enough to tell";
      return [{ id: item.id, source: item.source, text: item.text, uncertain: item.uncertain === true, match }];
    }),
    birth: birth && typeof birth.date === "string" ? { date: birth.date, time: typeof birth.time === "string" ? birth.time : null, place: typeof place?.name === "string" ? place.name : "" } : null,
  };
}

export function readPlaces(raw: unknown): PlaceHit[] {
  const list = object(raw)?.places;
  return (Array.isArray(list) ? list : []).flatMap((p): PlaceHit[] => {
    const o = object(p);
    return o && typeof o.id === "string" && typeof o.name === "string" ? [{ id: o.id, name: o.name, region: String(o.region ?? ""), country: String(o.country ?? "") }] : [];
  });
}

/** Words for a placement, with both options named when a birth time would settle it. */
export function describePlacement(label: string, p: Placement | null): string {
  if (!p) return `${label}: needs a birth time`;
  const sign = p.rashiOptions.length > 1 ? `${p.rashiOptions.join(" or ")}` : p.rashi;
  const nak = p.nakshatraOptions.length > 1 ? p.nakshatraOptions.join(" or ") : p.nakshatra;
  const base = `${label}: ${sign}${nak ? `, nakshatra ${nak}` : ""}`;
  if (p.rashiOptions.length > 1 || p.nakshatraOptions.length > 1) return `${base}. A birth time would settle it.`;
  return p.cusp ? `${base}, on the cusp` : base;
}

export interface FormValues {
  date: string;
  time: string;
  timeUnknown: boolean;
  placeId: string | null;
}

/** What is wrong with the form, in plain words; an empty object means it can be sent. */
export function formProblems(v: FormValues, today = new Date()): Partial<Record<"date" | "time" | "place", string>> {
  const out: Partial<Record<"date" | "time" | "place", string>> = {};
  const d = /^\d{4}-\d{2}-\d{2}$/.test(v.date) ? new Date(`${v.date}T00:00:00`) : null;
  if (!d || Number.isNaN(d.getTime())) out.date = "Enter your birth date.";
  else if (d > today) out.date = "Your birth date cannot be in the future.";
  else if (d.getFullYear() < 1900) out.date = "Birth years from 1900 are supported.";
  if (!v.timeUnknown && !/^([01]\d|2[0-3]):[0-5]\d$/.test(v.time)) out.time = "Enter the time as HH:MM, or tick that you do not know it.";
  if (!v.placeId) out.place = "Choose your birth place from the list.";
  return out;
}

export function saveBody(v: FormValues): string {
  return JSON.stringify({ birth_date: v.date, birth_time: v.timeUnknown ? null : v.time, city_id: v.placeId });
}
