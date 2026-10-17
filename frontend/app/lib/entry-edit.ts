// What the Edit control on a tracker entry shows and sends. Entries come back from the API in the same field names the log forms
// send (the adapter unpacks the few combined fields), so editing sends the same names back; no per-tracker form is needed.

export interface EditableField {
  key: string;
  label: string;
  kind: "number" | "text";
  value: string;
}

const NOT_EDITABLE = new Set(["id", "date"]);
const LONG_TEXT = new Set(["notes", "description", "reason", "findings", "recommendations"]);

export function labelFor(key: string): string {
  const text = key.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The simple fields of an entry (numbers and text), in a stable order with notes last. Booleans, nulls and anything nested are skipped. */
export function editableFields(entry: Record<string, unknown>): EditableField[] {
  const fields: EditableField[] = [];
  for (const [key, value] of Object.entries(entry)) {
    if (NOT_EDITABLE.has(key)) continue;
    if (typeof value === "number" && Number.isFinite(value)) fields.push({ key, label: labelFor(key), kind: "number", value: String(value) });
    else if (typeof value === "string") fields.push({ key, label: labelFor(key), kind: "text", value });
  }
  return fields.sort((a, b) => Number(LONG_TEXT.has(a.key)) - Number(LONG_TEXT.has(b.key)));
}

/** The request body for the edit: numbers stay numbers, a cleared field is left out, and the entry keeps its date. Null when a number is not a number. */
export function buildEditBody(fields: EditableField[], values: Record<string, string>, date: string): Record<string, string | number> | null {
  const body: Record<string, string | number> = { date };
  for (const field of fields) {
    const raw = (values[field.key] ?? field.value).trim();
    if (raw === "") continue;
    if (field.kind === "number") {
      const n = Number(raw);
      if (!Number.isFinite(n)) return null;
      body[field.key] = n;
    } else {
      body[field.key] = raw;
    }
  }
  return body;
}

/** Whether anything actually changed, so Save is not offered for an untouched form. */
export function isChanged(fields: EditableField[], values: Record<string, string>): boolean {
  return fields.some((f) => (values[f.key] ?? f.value).trim() !== f.value.trim());
}
