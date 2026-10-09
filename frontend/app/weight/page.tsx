import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Weight Tracking | Bubbles",
  description: "Body weight trends and changes.",
};

export default function WeightPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Weight"
          kicker="BODY WEIGHT"
          description="Weight can shift with your cycle, sleep and food — logging lets Bubbles read changes in context."
          endpoint="/health/weight"
          signal="mint"
          icon="weight"
          logLabel="Log weight"
          sheetTitle="Log your weight"
          submitLabel="Save weight"
          emptyTitle="No weigh-ins yet"
          entryLabel="Weigh-in"
          fields={[
            { id: "weight", label: "Weight", type: "number", unit: "lbs", min: 50, max: 700, step: 0.5, start: 150, required: true },
            { id: "time_of_day", label: "Time of day", type: "select", options: [
              { value: "morning", label: "Morning" },
              { value: "afternoon", label: "Afternoon" },
              { value: "evening", label: "Evening" },
            ]},
            { id: "notes", label: "Notes", type: "textarea", placeholder: "Before breakfast, after a workout…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Latest", kind: "latest", field: "weight", unit: "lbs" },
            { label: "7-day average", kind: "avg", field: "weight", days: 7, unit: "lbs" },
            { label: "Weigh-ins", kind: "count", note: "last 30 days" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
