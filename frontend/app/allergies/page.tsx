import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Allergies | Bubbles",
  description: "Known allergies and sensitivities.",
};

export default function AllergiesPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Allergies"
          kicker="ALLERGIES & SENSITIVITIES"
          description="Your triggers help Bubbles explain symptom flare-ups and keep them on hand for care visits."
          endpoint="/health/allergies"
          signal="sky"
          icon="allergies"
          logLabel="Add allergy"
          sheetTitle="Add an allergy"
          submitLabel="Save allergy"
          emptyTitle="No allergies added yet"
          entryLabel="Allergy"
          historyTitle="Your allergies"
          fields={[
            { id: "allergen", label: "Allergen or trigger", type: "text", placeholder: "Peanuts, penicillin, pollen…", required: true, maxLength: 200 },
            { id: "reaction_type", label: "Type", type: "select", options: [
              { value: "food", label: "Food" },
              { value: "medication", label: "Medication" },
              { value: "environmental", label: "Environmental" },
              { value: "topical", label: "Skin" },
              { value: "other", label: "Other" },
            ]},
            { id: "severity", label: "Severity", type: "select", options: [
              { value: "mild", label: "Mild" },
              { value: "moderate", label: "Moderate" },
              { value: "severe", label: "Severe" },
            ]},
            { id: "notes", label: "What happens", type: "textarea", placeholder: "Hives, swelling, sneezing…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Total", kind: "count" },
            { label: "Severe", kind: "countWhere", field: "severity", equals: "severe" },
            { label: "Food", kind: "countWhere", field: "reaction_type", equals: "food" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
