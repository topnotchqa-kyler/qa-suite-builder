import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.warn(
    "SuiteGen: VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY not set — " +
    "auth features disabled, generation still works."
  );
}

// Export null when env vars are missing so the app works without auth configured.
// All auth call sites check `if (!supabase) return` defensively.
export const supabase =
  supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null;
