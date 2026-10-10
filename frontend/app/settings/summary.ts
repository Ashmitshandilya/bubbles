// One-line status for the partner-sharing row in Settings, from GET /partner-sharing. Pure.
import type { PartnerSharingStatus } from "../lib/partner-sharing";

type Partial_ = Pick<PartnerSharingStatus, "sharing" | "categories" | "available" | "connection">;

/** "Off" / "Sharing cycle and sleep" / "Connected to Sam". Null when the status could not be read: show nothing rather than guess. */
export function partnerSummary(status: Partial_ | null | undefined): string | null {
  if (!status) return null;
  const labels = status.categories.map((key) => status.available.find((c) => c.key === key)?.label.toLowerCase() ?? key);
  const list = labels.length > 1 ? `${labels.slice(0, -1).join(", ")} and ${labels.at(-1)}` : (labels[0] ?? "");
  if (status.sharing && list) return `Sharing ${list}`;
  if (status.connection?.name) return `Connected to ${status.connection.name}`;
  return "Off";
}
