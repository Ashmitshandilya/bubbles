import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Lab Results | Bubbles",
  description: "Blood work, tests, and lab values.",
};

export default function LabsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Lab results"
          kicker="BLOOD WORK & TESTS"
          description="Test results over time let Bubbles show trends and bring the right numbers to your next visit."
          endpoint="/health/labs"
          signal="sky"
          icon="labs"
          logLabel="Add result"
          sheetTitle="Add a lab result"
          submitLabel="Save result"
          emptyTitle="No lab results yet"
          entryLabel="Lab result"
          historyTitle="Your results"
          fields={[
            { id: "test_name", label: "Test name", type: "text", placeholder: "Ferritin, HbA1c, TSH…", required: true, maxLength: 200 },
            { id: "value", label: "Result", type: "text", placeholder: "5.8", unitField: "unit", rangeField: "reference_range", maxLength: 50 },
            { id: "unit", label: "Unit", type: "text", placeholder: "%, ng/mL…", hideInHistory: true, maxLength: 50 },
            { id: "reference_range", label: "Reference range", type: "text", placeholder: "4.0-6.0", hint: "Copy it from your report, like 4.0-6.0.", maxLength: 50 },
            { id: "test_date", label: "Test date", type: "date" },
            { id: "notes", label: "Notes", type: "textarea", placeholder: "Fasting, lab name, what your doctor said…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Results", kind: "count" },
            { label: "Last 90 days", kind: "count", days: 90 },
            { label: "Outside given range", kind: "outOfRange", field: "value", rangeField: "reference_range", note: "vs. each result's own range" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
