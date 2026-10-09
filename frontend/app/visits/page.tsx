import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Doctor Visits | Bubbles",
  description: "Appointments, notes, and clinical recommendations.",
};

export default function VisitsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Doctor visits"
          kicker="APPOINTMENTS"
          description="Visit notes help Bubbles remember what your care team said and prepare questions for next time."
          endpoint="/health/visits"
          signal="sky"
          icon="visits"
          logLabel="Add visit"
          sheetTitle="Add a doctor visit"
          submitLabel="Save visit"
          emptyTitle="No visits added yet"
          entryLabel="Doctor visit"
          historyTitle="Your visits"
          fields={[
            { id: "doctor_name", label: "Doctor or clinic", type: "text", placeholder: "Dr. Rao", maxLength: 200 },
            { id: "specialty", label: "Specialty", type: "text", placeholder: "Gynaecology", maxLength: 100 },
            { id: "visit_date", label: "Visit date", type: "date" },
            { id: "reason", label: "Reason", type: "text", placeholder: "Irregular periods", maxLength: 500 },
            { id: "notes", label: "Visit notes", type: "textarea", placeholder: "What was said, tests ordered…", maxLength: 2000 },
            { id: "next_visit", label: "Next visit", type: "date" },
          ]}
          stats={[
            { label: "Visits", kind: "count" },
            { label: "Last 12 months", kind: "count", days: 365 },
            { label: "Specialties", kind: "distinct", field: "specialty" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
