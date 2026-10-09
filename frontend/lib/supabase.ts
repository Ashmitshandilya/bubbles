import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabasePublishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const isSupabaseConfigured = Boolean(
  supabaseUrl && supabasePublishableKey
);

// Importing this module must never crash the app: pages check
// `isSupabaseConfigured` and show a configuration message instead. When it is
// false the client points at the reserved `.invalid` TLD, which can never
// resolve, so nothing can silently contact a placeholder project.
export const supabase: SupabaseClient = createClient(
  supabaseUrl || "https://supabase-not-configured.invalid",
  supabasePublishableKey || "not-configured"
);
