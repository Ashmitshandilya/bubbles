import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Eyes | Bubbles",
  description: "Screen time, eye comfort and symptoms.",
};

export default function EyesPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Eyes"
          kicker="EYES & SCREEN TIME"
          description="Long screen days and tired eyes often go together. Logging both lets Bubbles notice the link for you."
          endpoint="/health/eyes"
          signal="sky"
          icon="eyes"
          logLabel="Log my eyes"
          sheetTitle="How are your eyes?"
          submitLabel="Save eye check"
          emptyTitle="No eye checks yet"
          entryLabel="Eye check"
          titleField="comfort"
          requireOneOf={["screen_hours", "comfort", "symptoms", "glasses", "breaks", "last_exam"]}
          callout={{
            title: "Sudden changes in your sight need urgent care",
            text: "Sudden loss of vision, a curtain or shadow over your sight, or severe eye pain should be seen urgently: call your local emergency number or go to an emergency department or eye casualty now. Logging here does not alert anyone.",
          }}
          fields={[
            { id: "screen_hours", label: "Screen time today", type: "number", unit: "h", min: 0, max: 18, step: 0.5, start: 6, hint: "Phone, laptop, TV and tablet together." },
            { id: "comfort", label: "How do your eyes feel?", type: "select", scale: true, hint: "1 is very uncomfortable, 5 is very comfortable.", options: [
              { value: "1", label: "1 · Awful" },
              { value: "2", label: "2 · Poor" },
              { value: "3", label: "3 · Okay" },
              { value: "4", label: "4 · Good" },
              { value: "5", label: "5 · Great" },
            ]},
            { id: "symptoms", label: "Anything you notice?", type: "select", multi: true, hint: "Pick any that apply.", options: [
              { value: "dry", label: "Dry" },
              { value: "itchy", label: "Itchy" },
              { value: "red", label: "Red" },
              { value: "strained", label: "Tired or strained" },
              { value: "blurry", label: "Blurry" },
              { value: "watery", label: "Watery" },
              { value: "headache", label: "Headache" },
            ]},
            { id: "glasses", label: "Glasses or lenses today", type: "select", options: [
              { value: "yes", label: "Wore them" },
              { value: "no", label: "Did not" },
            ]},
            { id: "breaks", label: "Screen breaks taken", type: "number", min: 0, max: 48, step: 1, start: 3, hint: "Looking at something far away for 20 seconds counts." },
            { id: "last_exam", label: "Date of your last eye exam", type: "date", hint: "Only if you know it. Bubbles keeps it for your care checklist." },
            { id: "notes", label: "Notes", type: "textarea", placeholder: "After a long day of calls…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Screen time (last log)", kind: "latest", field: "screen_hours", unit: "h", decimals: 1 },
            { label: "Average screen time", kind: "avg", field: "screen_hours", days: 7, unit: "h", decimals: 1, note: "days you logged it, last 7 days" },
            { label: "Average eye comfort", kind: "avg", field: "comfort", days: 7, unit: "/5", decimals: 1, note: "last 7 days" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
