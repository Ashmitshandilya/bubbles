-- Undo for supabase/migrations/20261013_bubbles_ops.sql. Removes the admin telemetry and settings tables and their rows.
-- The API keeps working afterwards (telemetry falls back to memory only, settings to their defaults).
begin;
drop table if exists public.bubbles_ops_events;
drop table if exists public.bubbles_admin_settings;
commit;
