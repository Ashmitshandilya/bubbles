import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Medical Reports | Bubbles",
  description: "Imaging, scans, and clinical reports.",
};

export default function ReportsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Reports"
          kicker="SCANS & CLINICAL REPORTS"
          description="Keeping key findings in one place helps Bubbles track changes and prepare you for appointments."
          endpoint="/health/reports"
          signal="sky"
          icon="reports"
          logLabel="Add report"
          sheetTitle="Add a report"
          submitLabel="Save report"
          emptyTitle="No reports added yet"
          entryLabel="Report"
          historyTitle="Your reports"
          titleField="title"
          fields={[
            { id: "title", label: "Report name", type: "text", placeholder: "Pelvic ultrasound", required: true, maxLength: 200 },
            { id: "report_type", label: "Type", type: "select", options: [
              { value: "imaging", label: "Imaging" },
              { value: "pathology", label: "Pathology" },
              { value: "cardiology", label: "Cardiology" },
              { value: "clinical", label: "Clinical" },
              { value: "other", label: "Other" },
            ]},
            { id: "report_date", label: "Report date", type: "date" },
            { id: "findings", label: "Key findings", type: "textarea", placeholder: "The main results or conclusions…", maxLength: 2000 },
            { id: "notes", label: "Notes", type: "textarea", placeholder: "Follow-up needed…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Reports", kind: "count" },
            { label: "Last 12 months", kind: "count", days: 365 },
            { label: "Types", kind: "distinct", field: "report_type" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
