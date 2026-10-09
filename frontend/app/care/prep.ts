// Pure view-model for the Doctor prep screen (POST /doctor/prepare, POST /medical/summary, GET /health/labs|reports).
//
// /medical/summary reads the medical_reports and lab_results tables only, and flags a lab from a `flag`/`status`
// key those tables do not have (they hold `abnormal_flag` and a numeric range). Entries saved on the Labs and
// Reports pages also never reach it while the database runs in compatibility mode. So the page counts records, and
// flags results outside the range the user entered, from the same /health/<slug> lists those pages show.
import { parseRange, toNumber, type Entry } from "../../components/tracking/data";

export interface FlaggedLab {
  label: string;
  flag: string;
  value?: string | number | null;
  unit?: string | null;
}

export interface MedicalSummary {
  lab_count?: number;
  report_count?: number;
  flagged_labs?: FlaggedLab[];
}

/** Labs whose numeric result sits outside the "lo-hi" reference range stored with them. Never interpreted further. */
export function labsOutOfRange(labs: readonly Entry[]): FlaggedLab[] {
  return labs.flatMap((lab): FlaggedLab[] => {
    const value = toNumber(lab.value);
    const range = parseRange(lab.reference_range);
    if (value === null || !range || (value >= range[0] && value <= range[1])) return [];
    return [{
      label: String(lab.test_name || "Lab result"),
      flag: value < range[0] ? "low" : "high",
      value,
      unit: typeof lab.unit === "string" && lab.unit ? lab.unit : null,
    }];
  });
}

export interface RecordsOnFile {
  labCount: number;
  reportCount: number;
  flagged: FlaggedLab[];
}

/** `labs` / `reports` are null when their list could not be loaded; the summary alone is then all there is. */
export function mergeRecords(summary: MedicalSummary | undefined, labs: readonly Entry[] | null, reports: readonly Entry[] | null): RecordsOnFile {
  const fromBackend = summary?.flagged_labs ?? [];
  const known = new Set(fromBackend.map((l) => `${l.label}|${l.value}`));
  const fromEntries = labs ? labsOutOfRange(labs).filter((l) => !known.has(`${l.label}|${l.value}`)) : [];
  return {
    labCount: Math.max(summary?.lab_count ?? 0, labs?.length ?? 0),
    reportCount: Math.max(summary?.report_count ?? 0, reports?.length ?? 0),
    flagged: [...fromBackend, ...fromEntries],
  };
}
