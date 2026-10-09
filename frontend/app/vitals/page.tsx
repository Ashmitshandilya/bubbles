import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Vital Signs | Bubbles",
  description: "Heart rate, blood pressure, and vital signs.",
};

export default function VitalsPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Vital signs"
          kicker="VITALS & MEASUREMENTS"
          description="Heart rate, blood pressure and temperature give Bubbles a baseline to compare against when you feel off."
          endpoint="/health/vitals"
          signal="pink"
          icon="vitals"
          logLabel="Log vitals"
          sheetTitle="Add a reading"
          submitLabel="Save reading"
          emptyTitle="No readings yet"
          entryLabel="Reading"
          requireOneOf={["heart_rate", "blood_pressure", "temperature"]}
          fields={[
            { id: "heart_rate", label: "Heart rate", type: "number", unit: "bpm", min: 20, max: 300, step: 1, start: 70 },
            { id: "blood_pressure", label: "Blood pressure", type: "text", placeholder: "120/80", hint: "Top number / bottom number, like 120/80.",
              pattern: "\\d{2,3}\\s*/\\s*\\d{2,3}", patternHint: "Blood pressure should look like 120/80.", maxLength: 20 },
            { id: "temperature", label: "Temperature", type: "number", unit: "°F", min: 80, max: 115, step: 0.1, start: 98.6 },
            { id: "notes", label: "Notes", type: "textarea", placeholder: "Resting, after a walk, feeling feverish…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Heart rate", kind: "latest", field: "heart_rate", unit: "bpm", decimals: 0 },
            { label: "Blood pressure", kind: "latest", field: "blood_pressure" },
            { label: "Temperature", kind: "latest", field: "temperature", unit: "°F" },
            { label: "Readings", kind: "count", note: "last 30 days" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
