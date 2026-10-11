import { uiPreview } from "./supabase";

let warmed = false;

/** Starts a sleeping free-plan API waking before sign-in. Fire-and-forget, once per page load, errors ignored. */
export function warmApi(): void {
  const api = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (warmed || !api || uiPreview) return;
  if (api.startsWith("http://") && window.location.protocol === "https:") return;
  warmed = true;
  fetch(`${api}/health`, { mode: "no-cors", cache: "no-store" }).catch(() => {});
}
