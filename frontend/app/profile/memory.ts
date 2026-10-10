// Pure view-model for the memory page (GET /memory/diagnostics, PATCH /health-events/{id}/confirmation).
// Only L1 rows ever carry readable content from the API; L2 and L3 arrive as counts, so that is all the page can show.

export interface MemoryRow {
  id?: string;
  event_type?: string;
  extracted_data?: Record<string, unknown> | null;
  confidence?: number;
  created_at?: string;
  extraction_status?: string;
  user_confirmed?: boolean;
}

export interface MemoryItem {
  /** Null when the API sent no id: such a row can be read but not acted on. */
  id: string | null;
  kind: string;
  title: string;
  detail: string;
  when: string | null;
  confirmed: boolean;
}

const TITLE_KEYS = ["name", "symptom", "concept", "medication", "condition", "category"];
const HIDDEN_KEY = /^_|(^|_)(id|source|user|provenance)(_|$)/;

const human = (value: string) => {
  const s = value.replaceAll("_", " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : s;
};

/** memory_diagnostics reads at most 200 rows per level, so 200 means "200 or more". Null = no number to show. */
export function countLabel(n: number | undefined | null): string | null {
  if (typeof n !== "number" || !Number.isFinite(n) || n < 0) return null;
  return n >= 200 ? "200+" : String(n);
}

export function memoryItems(rows: readonly MemoryRow[] | undefined | null): MemoryItem[] {
  return (rows ?? []).map((row): MemoryItem => {
    const data = row.extracted_data && typeof row.extracted_data === "object" ? row.extracted_data : {};
    const titleKey = TITLE_KEYS.find((k) => typeof data[k] === "string" && (data[k] as string).trim());
    const kind = human(row.event_type || "entry");
    const detail = Object.entries(data)
      .filter(([key, value]) => key !== titleKey && !HIDDEN_KEY.test(key) && ["string", "number", "boolean"].includes(typeof value) && value !== "")
      .slice(0, 3)
      .map(([key, value]) => `${human(key)}: ${String(value)}`)
      .join(" · ");
    return {
      id: row.id ? String(row.id) : null,
      kind,
      title: titleKey ? human(String(data[titleKey]).trim()) : kind,
      detail,
      when: row.created_at ?? null,
      confirmed: row.user_confirmed === true || row.extraction_status === "confirmed",
    };
  });
}
