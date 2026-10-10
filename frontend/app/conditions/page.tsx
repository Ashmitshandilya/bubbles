import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Conditions | Bubbles",
  description: "Chronic conditions, diagnoses, and medical history.",
};

export default function ConditionsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Conditions"
          kicker="MEDICAL HISTORY"
          description="Knowing your diagnoses helps Bubbles keep its suggestions relevant, and careful."
          endpoint="/health/conditions"
          signal="sky"
          icon="conditions"
          logLabel="Add condition"
          sheetTitle="Add a condition"
          submitLabel="Save condition"
          emptyTitle="No conditions added yet"
          entryLabel="Condition"
          historyTitle="Your conditions"
          fields={[
            { id: "condition_name", label: "Condition or diagnosis", type: "text", placeholder: "PCOS, asthma, migraine…", required: true, maxLength: 200 },
            { id: "status", label: "Status", type: "select", options: [
              { value: "active", label: "Active" },
              { value: "managed", label: "Managed" },
              { value: "resolved", label: "Resolved" },
            ]},
            { id: "diagnosed_date", label: "Diagnosed on", type: "date" },
            { id: "notes", label: "Notes", type: "textarea", placeholder: "Treatment, who looks after it…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Total", kind: "count" },
            { label: "Active", kind: "countWhere", field: "status", equals: "active" },
            { label: "Managed", kind: "countWhere", field: "status", equals: "managed" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
