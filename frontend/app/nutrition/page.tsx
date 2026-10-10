import { Metadata } from "next";
import { AuthProvider, ApiProvider } from "../../components/Providers";
import { GenericTrackingClient } from "../../components/GenericTrackingClient";

export const metadata: Metadata = {
  title: "Nutrition Tracking | Bubbles",
  description: "Meals, macros, and dietary patterns.",
};

export default function NutritionPage() {
  return (
    <AuthProvider>
      <ApiProvider>
        <GenericTrackingClient
          title="Food"
          kicker="MEALS & NUTRITION"
          description="What you eat shapes energy, mood and digestion. Meal logs let Bubbles connect the dots."
          endpoint="/health/nutrition"
          signal="mint"
          icon="nutrition"
          logLabel="Log a meal"
          sheetTitle="What did you eat?"
          submitLabel="Save meal"
          emptyTitle="No meals logged yet"
          entryLabel="Meal"
          titleField="description"
          fields={[
            { id: "meal_type", label: "Meal", type: "select", options: [
              { value: "breakfast", label: "Breakfast" },
              { value: "lunch", label: "Lunch" },
              { value: "dinner", label: "Dinner" },
              { value: "snack", label: "Snack" },
              { value: "other", label: "Other" },
            ]},
            { id: "description", label: "What did you eat?", type: "textarea", placeholder: "Dal, rice and a salad…", required: true, maxLength: 500 },
            { id: "calories", label: "Calories (estimate)", type: "number", unit: "kcal", min: 0, max: 10000, step: 50, start: 400 },
            { id: "notes", label: "How did you feel after?", type: "textarea", placeholder: "Full, bloated, energised…", maxLength: 2000 },
          ]}
          stats={[
            { label: "Meals today", kind: "count", days: 1 },
            { label: "Calories today", kind: "sum", field: "calories", days: 1, unit: "kcal", decimals: 0, note: "from meals with an estimate" },
            { label: "Meals this week", kind: "count", days: 7, note: "last 7 days" },
          ]}
        />
      </ApiProvider>
    </AuthProvider>
  );
}
